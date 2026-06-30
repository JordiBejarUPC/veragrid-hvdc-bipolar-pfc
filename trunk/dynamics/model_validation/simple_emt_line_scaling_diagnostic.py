# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")))

import VeraGridEngine.api as gce


def build_case():
    grid = gce.MultiCircuit()
    grid.Sbase = 100.0
    grid.fBase = 50.0

    bus1 = gce.Bus("Slack", Vnom=20.0)
    bus2 = gce.Bus("Load", Vnom=20.0)
    grid.add_bus(bus1)
    grid.add_bus(bus2)

    gen = gce.Generator(name="G", P=1.0, vset=1.0, Snom=grid.Sbase)
    load = gce.Load(name="L", P=1.0, Q=0.35)
    line = gce.Line(
        name="Line",
        bus_from=bus1,
        bus_to=bus2,
        r=0.03,
        x=0.07,
        b=0.02,
        rate=100.0,
    )

    grid.add_generator(bus=bus1, api_obj=gen)
    grid.add_load(bus=bus2, api_obj=load)
    grid.add_line(line)

    options = gce.PowerFlowOptions(
        solver_type=gce.SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        tolerance=1e-10,
        max_iter=50,
    )
    results = gce.power_flow(grid, options=options)
    return grid, line, results


def inst_from_phasor(x: complex) -> float:
    return float(np.sqrt(2.0) * np.imag(x))


def check_convention(
        label: str,
        r_value: float,
        x_value: float,
        b_value: float,
        g_damp: float,
        vf: complex,
        vt: complex,
        i_f: complex,
        i_t: complex,
        omega_base: float,
) -> None:
    z = complex(r_value, x_value)
    b_half = b_value / 2.0
    i_ser_from = i_f - 1j * b_half * vf - g_damp * vf
    i_ser_to = -i_t + 1j * b_half * vt + g_damp * vt
    i_ser_z = (vf - vt) / z
    residual_from = vf - vt - z * i_ser_from
    residual_to = vf - vt - z * i_ser_to

    vf0 = inst_from_phasor(vf)
    vt0 = inst_from_phasor(vt)
    i_ser0 = inst_from_phasor(0.5 * (i_ser_from + i_ser_to))
    rhs_di = (vf0 - vt0 - r_value * i_ser0) / (x_value / omega_base)
    expected_di = omega_base * np.sqrt(2.0) * np.real(i_ser_z)

    print(label)
    print(f"  z={z.real:.9e}+j{z.imag:.9e}, b={b_value:.9e}, G_damp={g_damp:.9e}")
    print(f"  i_ser_from={i_ser_from:.9e}, i_ser_to={i_ser_to:.9e}, i_ser_z={i_ser_z:.9e}")
    print(f"  |voltage residual from|={abs(residual_from):.9e}")
    print(f"  |voltage residual to|  ={abs(residual_to):.9e}")
    print(f"  instantaneous di rhs={rhs_di:.9e}, expected from z={expected_di:.9e}, err={rhs_di - expected_di:.9e}")


def check_power_convention(
        v_phase: complex,
        s_total: complex,
        current_candidates: dict[str, complex],
) -> None:
    alpha = 2.0 * np.pi / 3.0
    rotations = (1.0 + 0.0j, np.exp(-1j * alpha), np.exp(1j * alpha))

    print("\nPower convention checks")
    print(f"  target PF total S: {s_total:.9e}")
    print("  Lower error identifies the convention matching the PF branch total.")

    for current_label, i_phase in current_candidates.items():
        v_abc = [v_phase * rot for rot in rotations]
        i_abc = [i_phase * rot for rot in rotations]
        s_abc_sum = sum(v * np.conj(i) for v, i in zip(v_abc, i_abc))
        p_abc_sum = sum(inst_from_phasor(v) * inst_from_phasor(i) for v, i in zip(v_abc, i_abc))
        v_a0, v_b0, v_c0 = (inst_from_phasor(v) for v in v_abc)
        i_a0, i_b0, i_c0 = (inst_from_phasor(i) for i in i_abc)
        p_line_to_line_over_9 = -(
            (v_a0 - v_c0) * i_a0
            + (v_b0 - v_a0) * i_b0
            + (v_c0 - v_b0) * i_c0
        ) / 9.0

        complex_candidates = {
            "sum(Va*conj(Ia)+Vb*conj(Ib)+Vc*conj(Ic))": s_abc_sum,
            "sum(...)/3": s_abc_sum / 3.0,
            "Va*conj(Ia)": v_abc[0] * np.conj(i_abc[0]),
        }
        active_candidates = {
            "sum(va*ia+vb*ib+vc*ic) at t=0": p_abc_sum,
            "sum(...)/3 at t=0": p_abc_sum / 3.0,
            "-sum(vll_edge*i)/9 at t=0": p_line_to_line_over_9,
        }

        print(f"  {current_label} current")
        for convention, value in complex_candidates.items():
            print(f"    {convention}: {value:.9e}, |err S|={abs(value - s_total):.9e}")
        for convention, value in active_candidates.items():
            print(f"    {convention}: {value:.9e}, err P={value - s_total.real:.9e}")


def main() -> None:
    grid, line, res = build_case()
    print(f"Converged: {res.converged}")
    print(res.get_bus_df())
    print(res.get_branch_df())

    omega_base = 2.0 * np.pi * grid.fBase
    g_damp = 1e-5
    line_idx = grid.lines.index(line)
    vf = complex(res.voltage[grid.buses.index(line.bus_from)])
    vt = complex(res.voltage[grid.buses.index(line.bus_to)])
    sf_total = complex(res.Sf[line_idx]) / grid.Sbase
    st_total = complex(res.St[line_idx]) / grid.Sbase

    print("\nBalanced PF totals on system base")
    print(f"  Vf={vf:.9e}, Vt={vt:.9e}")
    print(f"  Sf={sf_total:.9e}, St={st_total:.9e}")
    print(f"  raw line z={line.R:.9e}+j{line.X:.9e}, B={line.B:.9e}")

    i_f_total = np.conj(sf_total / vf)
    i_t_total = np.conj(st_total / vt)
    i_f_phase = np.conj((sf_total / 3.0) / vf)
    i_t_phase = np.conj((st_total / 3.0) / vt)

    print("\nCurrent phasor candidates")
    print(f"  total-power current: i_f={i_f_total:.9e}, i_t={i_t_total:.9e}")
    print(f"  phase-power current: i_f={i_f_phase:.9e}, i_t={i_t_phase:.9e}")
    print(f"  ratio i_f_total/i_f_phase={i_f_total / i_f_phase:.9e}")

    check_power_convention(
        vf,
        sf_total,
        {
            "total-power": i_f_total,
            "phase-power": i_f_phase,
        },
    )

    print("\nPhase A line-equation checks")
    check_convention(
        "raw R/X/B with total-power current",
        line.R,
        line.X,
        line.B,
        g_damp,
        vf,
        vt,
        i_f_total,
        i_t_total,
        omega_base,
    )
    check_convention(
        "raw R/X/B with phase-power current",
        line.R,
        line.X,
        line.B,
        g_damp,
        vf,
        vt,
        i_f_phase,
        i_t_phase,
        omega_base,
    )
    check_convention(
        "3R/3X/B3 with phase-power current",
        3.0 * line.R,
        3.0 * line.X,
        line.B / 3.0,
        g_damp,
        vf,
        vt,
        i_f_phase,
        i_t_phase,
        omega_base,
    )


if __name__ == "__main__":
    main()
