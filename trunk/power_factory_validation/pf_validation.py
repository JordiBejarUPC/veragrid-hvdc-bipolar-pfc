# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""
Validate the VeraGrid PowerFactory (DGS) parser against a PowerFactory
load-flow solution.

The reference is a SEPARATE, controlled PowerFactory export (balanced,
positive-sequence AC load flow, with generator Q-control OFF and tap
changers fixed) so that both tools solve the *same* equations. NR
tolerance / iteration count are irrelevant: a converged NR solution is a
fixed point of those equations, so the two solvers must agree well below
1e-3 if the parser builds the model correctly.

Reference file format (.csv or .xlsx), one row per bus, header row with
flexible column names (case-insensitive):
    name  | bus | busname     -> bus name (must match DGS terminal name)
    vm    | v   | u  | u_pu    -> voltage magnitude [p.u.]
    va    | ang | phi| phiu    -> voltage angle [deg]  (use --va-rad if radians)

This script:
  1. loads the reference,
  2. opens the .dgs with VeraGrid and runs NR (controls off),
  3. compares Vm / Va by bus name (max |dVm|, max |dVa|, tol 1e-3),
  4. runs an independent residual sanity check: injects the reference
     voltages into VeraGrid's compiled Ybus/Sbus and reports the power
     mismatch, to tell "invalid/misconfigured reference" apart from a
     genuine parser bug.

Run with the repo `src` on PYTHONPATH (Git Bash):
    cd powerfactory_validation && \
    PYTHONPATH="C:/Users/ilanm/PycharmProjects/VeraGrid/src" \
    python pf_validation.py COES_dgsv6.dgs COES_dgsv6_ref.xlsx

Client .dgs / reference files live in this folder and are git-ignored.
"""
from __future__ import annotations

import os
import sys
import argparse
import numpy as np
import pandas as pd

import VeraGridEngine.api as vg
from VeraGridEngine.IO.file_open import FileOpen
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver

TOL = 1e-3

_NAME_COLS = ("name", "bus", "busname", "bus_name", "loc_name", "terminal")
_VM_COLS = ("vm", "v", "u", "u_pu", "vm_pu", "voltage", "m:u")
_VA_COLS = ("va", "ang", "angle", "phi", "phiu", "m:phiu", "va_deg")


def _pick(cols, candidates):
    low = {c.lower().strip(): c for c in cols}
    for cand in candidates:
        if cand in low:
            return low[cand]
    return None


def read_reference(path: str, va_in_rad: bool):
    """Load {bus_name: (Vm_pu, Va_rad)} from a separate PF export (.csv/.xlsx)."""
    if path.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)

    name_c = _pick(df.columns, _NAME_COLS)
    vm_c = _pick(df.columns, _VM_COLS)
    va_c = _pick(df.columns, _VA_COLS)
    if name_c is None or vm_c is None or va_c is None:
        raise ValueError(
            f"Could not find name/Vm/Va columns in {path}. "
            f"Found columns: {list(df.columns)}")

    ref = {}
    for _, row in df.iterrows():
        name = str(row[name_c]).strip()
        vm = float(row[vm_c])
        va = float(row[va_c])
        if not va_in_rad:
            va = np.deg2rad(va)
        ref[name] = (vm, va)
    return ref


def make_options():
    """Same conditions as the PSSe parser validation."""
    return vg.PowerFlowOptions(
        tolerance=1e-5,
        solver_type=vg.SolverType.NR,
        retry_with_other_methods=False,
        control_q=False,
        ignore_single_node_islands=True,
        initialize_angles=True,
        control_taps_modules=False,
        control_taps_phase=False,
        control_remote_voltage=False,
        orthogonalize_controls=False,
        apply_temperature_correction=False,
    )


def residual_sanity_check(grid, ref, top: int):
    """
    Inject the reference voltages into VeraGrid's compiled model and report the
    power mismatch S_calc - Sbus. Near-zero everywhere => the reference solves
    the same balanced model VeraGrid solves (so any PF mismatch is a parser bug
    in the *solver path*, not the model). Large entries localize model errors.
    """
    nc = vg.compile_numerical_circuit_at(grid)
    Ybus = nc.get_admittance_matrices().Ybus
    Sbus = nc.get_power_injections_pu()
    names = nc.bus_data.names

    V = np.ones(nc.nbus, dtype=complex)
    n_set = 0
    for i, nm in enumerate(names):
        if nm in ref:
            vm, va = ref[nm]
            V[i] = vm * np.exp(1j * va)
            n_set += 1

    S_calc = V * np.conj(Ybus @ V)
    mismatch = np.abs(S_calc - Sbus)

    print(f"Residual sanity check: injected {n_set}/{nc.nbus} bus voltages "
          f"from reference")
    print(f"  max |S_calc - Sbus| = {mismatch.max():.3e} p.u. "
          f"(Sbase={nc.Sbase} MVA)")
    order = np.argsort(mismatch)[::-1]
    print(f"  {'bus':<28}{'|dS|[pu]':>12}{'|dS|[MVA]':>12}")
    for i in order[:top]:
        print(f"  {str(names[i])[:27]:<28}{mismatch[i]:>12.2e}"
              f"{mismatch[i]*nc.Sbase:>12.2e}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate DGS parser vs PowerFactory.")
    parser.add_argument("dgs", help="DGS file (relative to this folder or absolute)")
    parser.add_argument("ref", help="Reference PF result file (.csv/.xlsx)")
    parser.add_argument("--va-rad", action="store_true",
                        help="Reference angle column is in radians (default: degrees)")
    parser.add_argument("--top", type=int, default=25, help="How many worst buses to print")
    args = parser.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))

    def _resolve(p):
        return p if os.path.isabs(p) else os.path.join(here, p)

    dgs_path = _resolve(args.dgs)
    ref_path = _resolve(args.ref)
    for p in (dgs_path, ref_path):
        if not os.path.exists(p):
            print(f"File not found: {p}")
            return 2

    # --- reference from a controlled PowerFactory export ------------------
    ref = read_reference(ref_path, args.va_rad)
    print(f"Reference buses: {len(ref)}")

    # --- VeraGrid NR (same conditions as the PSSe parser) ----------------
    grid = FileOpen(dgs_path).open()
    options = make_options()

    # --- independent reference sanity check (before solving) -------------
    residual_sanity_check(grid, ref, args.top)
    print("-" * 74)

    pf = PowerFlowDriver(grid, options)
    pf.run()
    if not pf.results.converged:
        print(f"WARNING: VeraGrid power flow did NOT converge "
              f"(error={pf.results.error}).")

    buses = grid.buses
    v = pf.results.voltage
    vm_vg = np.abs(v)
    va_vg = np.angle(v)

    # --- compare ----------------------------------------------------------
    rows = []
    matched = 0
    unmatched = []
    for i, bus in enumerate(buses):
        if bus.name not in ref:
            unmatched.append(bus.name)
            continue
        vm_pf, va_pf = ref[bus.name]
        dvm = abs(vm_vg[i] - vm_pf)
        dva = abs(va_vg[i] - va_pf)
        rows.append((bus.name, dvm, dva, vm_vg[i], vm_pf, va_vg[i], va_pf))
        matched += 1

    print(f"Matched buses: {matched}   "
          f"(VeraGrid buses without a PF ref: {len(unmatched)})")
    if matched == 0:
        print("No buses matched by name - cannot validate.")
        return 1

    dvm_all = np.array([r[1] for r in rows])
    dva_all = np.array([r[2] for r in rows])
    max_dvm, max_dva = dvm_all.max(), dva_all.max()
    n_bad_vm = int((dvm_all > TOL).sum())
    n_bad_va = int((dva_all > TOL).sum())

    print("-" * 74)
    print(f"max |dVm| = {max_dvm:.3e} p.u.   buses > {TOL:g}: {n_bad_vm}")
    print(f"max |dVa| = {max_dva:.3e} rad    buses > {TOL:g}: {n_bad_va}")
    print("-" * 74)

    rows.sort(key=lambda r: max(r[1], r[2]), reverse=True)
    print(f"{'bus':<28}{'dVm':>10}{'dVa[rad]':>12}"
          f"{'Vm_vg':>9}{'Vm_pf':>9}{'Va_vg':>9}{'Va_pf':>9}")
    for name, dvm, dva, vmvg, vmpf, vavg, vapf in rows[:args.top]:
        print(f"{name[:27]:<28}{dvm:>10.2e}{dva:>12.2e}"
              f"{vmvg:>9.4f}{vmpf:>9.4f}{vavg:>9.4f}{vapf:>9.4f}")

    ok = (max_dvm < TOL) and (max_dva < TOL)
    print("-" * 74)
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
