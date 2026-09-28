#!/usr/bin/env python3
"""Audit the two phase-domain per-unit conventions relevant to VeraGrid EMT.

The script deliberately does not build an EMT problem.  It runs balanced and
three-phase power flows for a small balanced network and expresses the same
physical operating point in both possible EMT current coordinates:

* conventional: Ibase = Sbase / (sqrt(3) VLLbase)
* legacy EMT:   Ibase = Sbase / Vphasebase = 3 Ibase_conventional

PF3 phase powers are stored as S_phase / Sbase_3ph.  Consequently they require
``3 * conj(S_phase_pu / V_phase_pu)`` for conventional current pu, but only
``conj(S_phase_pu / V_phase_pu)`` for the legacy EMT current coordinate.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import VeraGridEngine.api as gce
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_driver_3ph import PowerFlowDriver3Ph


def _max_abs(values: np.ndarray) -> float:
    values = np.asarray(values)
    return float(np.max(np.abs(values))) if values.size else 0.0


def build_audit_grid() -> gce.MultiCircuit:
    """Return a small balanced system with non-trivial voltage drop and Q."""
    grid = gce.MultiCircuit(name="EMT three-phase pu audit", Sbase=100.0, fbase=50.0)
    source = gce.Bus(name="Source", Vnom=230.0, is_slack=True)
    demand = gce.Bus(name="Demand", Vnom=230.0)
    grid.add_bus(source)
    grid.add_bus(demand)

    grid.add_generator(source, gce.Generator(name="Grid", vset=1.02, Snom=200.0))
    grid.add_line(gce.Line(
        name="Audit line",
        bus_from=source,
        bus_to=demand,
        r=0.015,
        x=0.12,
        b=0.02,
        rate=200.0,
    ))
    grid.add_load(demand, gce.Load(name="Audit load", P=60.0, Q=25.0))
    return grid


def _run_power_flows(grid: gce.MultiCircuit):
    options = PowerFlowOptions(
        solver_type=gce.SolverType.NR,
        retry_with_other_methods=True,
        tolerance=1.0e-10,
        max_iter=50,
        control_q=False,
    )
    balanced = PowerFlowDriver(grid=grid, options=options)
    balanced.run()
    three_phase = PowerFlowDriver3Ph(grid=grid, options=options)
    three_phase.run()
    if not bool(balanced.results.converged) or not bool(three_phase.results.converged):
        raise RuntimeError("Balanced PF or PF3 did not converge")
    return balanced.results, three_phase.results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path(__file__).with_suffix(".csv"),
        help="Output table (default: next to this script)",
    )
    args = parser.parse_args()

    grid = build_audit_grid()
    pf, pf3 = _run_power_flows(grid)
    alpha = np.exp(1j * 2.0 * np.pi / 3.0)

    voltage = np.vstack((pf3.voltage_A, pf3.voltage_B, pf3.voltage_C))
    phase_power = np.vstack((pf3.Sbus_A, pf3.Sbus_B, pf3.Sbus_C)) / grid.Sbase
    pf3_current = np.vstack((pf3.If_A, pf3.If_B, pf3.If_C))

    conventional_bus_current = 3.0 * np.conj(phase_power / voltage)
    legacy_bus_current = np.conj(phase_power / voltage)
    reconstructed_branch_current = np.vstack((pf.If, pf.If / alpha, pf.If * alpha))

    vll_base_kv = float(grid.buses[0].Vnom)
    vphase_base_kv = vll_base_kv / np.sqrt(3.0)
    conventional_current_base_ka = grid.Sbase / (np.sqrt(3.0) * vll_base_kv)
    legacy_current_base_ka = grid.Sbase / vphase_base_kv
    impedance_base_ohm = vll_base_kv**2 / grid.Sbase

    print("Physical bases at the audit voltage level")
    print(f"  Sbase_3ph                  = {grid.Sbase:.9f} MVA")
    print(f"  Vbase_LL                   = {vll_base_kv:.9f} kV")
    print(f"  Vbase_phase                = {vphase_base_kv:.9f} kV")
    print(f"  Ibase_conventional         = {conventional_current_base_ka:.9f} kA")
    print(f"  Ibase_legacy_EMT           = {legacy_current_base_ka:.9f} kA")
    print(f"  Ibase_legacy/conventional  = "
          f"{legacy_current_base_ka/conventional_current_base_ka:.9f}")
    print(f"  Zbase_standard             = {impedance_base_ohm:.9f} ohm")
    print()

    print("PF3 storage convention")
    print("  S_phase_pu(stored) = S_phase / Sbase_3ph")
    print("  sum(S_phase_pu)    = S_3ph / Sbase_3ph")
    print("  V_phase_pu         = V_phase / (VLLbase/sqrt(3))")
    print()
    print("Current coordinates for the same physical current")
    print("  conventional: I_pu = 3*conj(S_phase_pu/V_phase_pu)")
    print("  legacy EMT:   i_pu =   conj(S_phase_pu/V_phase_pu)")
    print("  identity:     I_pu = 3*i_pu")
    print()
    print("Direct numerical checks")
    print(f"  max |PF3 If - balanced reconstructed If| = "
          f"{_max_abs(pf3_current-reconstructed_branch_current):.12e}")
    print(f"  max |I_conventional - 3 I_legacy|       = "
          f"{_max_abs(conventional_bus_current-3.0*legacy_bus_current):.12e}")

    # KCL uses PF3 branch currents, which reveal which current coordinate PF3
    # exposes.  Net injection current is positive into the network.
    branch_sum = np.zeros_like(voltage, dtype=complex)
    bus_index = {bus.idtag: idx for idx, bus in enumerate(grid.buses)}
    if_abc = np.vstack((pf3.If_A, pf3.If_B, pf3.If_C))
    it_abc = np.vstack((pf3.It_A, pf3.It_B, pf3.It_C))
    for idx, branch in enumerate(grid.lines):
        branch_sum[:, bus_index[branch.bus_from.idtag]] += if_abc[:, idx]
        branch_sum[:, bus_index[branch.bus_to.idtag]] += it_abc[:, idx]
    print(f"  PF3 KCL using conventional current       = "
          f"{_max_abs(conventional_bus_current-branch_sum):.12e}")
    print(f"  PF3 KCL using legacy current             = "
          f"{_max_abs(legacy_bus_current-branch_sum):.12e}")
    print()

    print("Equivalent model equations (same standard R/X pu)")
    print("  conventional current:  dV = Zpu * I_conventional")
    print("  legacy EMT current:     dV/3 = Zpu * i_legacy")
    print("  Rpu and Xpu do not change; the current coordinate and equation do.")
    print()

    rows: list[dict[str, object]] = []
    for load in grid.loads:
        idx = bus_index[load.bus.idtag]
        vpu = voltage[0, idx]
        s_total_pu = complex(load.P, load.Q) / grid.Sbase
        s_phase_stored_pu = s_total_pu / 3.0
        i_conventional = 3.0 * np.conj(s_phase_stored_pu / vpu)
        i_legacy = np.conj(s_phase_stored_pu / vpu)
        r_standard = abs(vpu) ** 2 / s_total_pu.real
        r_from_stored_phase = abs(vpu) ** 2 / s_phase_stored_pu.real
        rows.append({
            "load": load.name,
            "V_phase_pu": abs(vpu),
            "P_total_pu": s_total_pu.real,
            "P_phase_stored_pu": s_phase_stored_pu.real,
            "I_conventional_abs_pu": abs(i_conventional),
            "I_legacy_abs_pu": abs(i_legacy),
            "R_standard_pu": r_standard,
            "R_if_phase_power_is_misread_as_total_pu": r_from_stored_phase,
            "wrong_R_over_standard_R": r_from_stored_phase / r_standard,
        })
        print(f"Load {load.name}")
        print(f"  standard Rpu = Vpu^2/Ptotal_pu       = {r_standard:.9f}")
        print(f"  same Rpu = Vpu^2/(3*Pphase_stored)   = "
              f"{abs(vpu)**2/(3.0*s_phase_stored_pu.real):.9f}")
        print(f"  misread phase-power result            = {r_from_stored_phase:.9f} (3x too large)")

    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nCSV: {args.csv.resolve()}")


if __name__ == "__main__":
    main()
