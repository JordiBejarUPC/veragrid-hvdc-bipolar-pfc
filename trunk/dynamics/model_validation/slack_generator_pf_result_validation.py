#!/usr/bin/env python3
"""
Validate how solved slack-generator power is reported by power-flow results.

The purpose of this script is to show, explicitly, whether a slack generator's
``pf_results.gen_p`` value matches the solved net bus injection stored in
``pf_results.Sbus``.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np

import rms_gfl_validation as base_validation


def print_generator_power_result_check() -> None:
    """
    Run the Grid 2 power flow and print generator result consistency.

    :return: None.
    """
    grid = base_validation.create_grid_2()
    pf_results = base_validation.run_power_flow(grid, "slack-generator result check")

    print("\n" + "-" * 90)
    print("Generator PF Result Check")
    print("-" * 90)
    print(f"Sbase = {grid.Sbase:.6f} MVA")

    for gen_idx in range(len(grid.generators)):
        gen = grid.generators[gen_idx]
        bus_idx: int = list(grid.buses).index(gen.bus)
        gen_p_mw: float = float(pf_results.gen_p[gen_idx])
        gen_q_mvar: float = float(pf_results.gen_q[gen_idx])
        sbus_value: complex = complex(pf_results.Sbus[bus_idx])
        diff_p_mw: float = gen_p_mw - float(np.real(sbus_value))
        diff_q_mvar: float = gen_q_mvar - float(np.imag(sbus_value))

        print(f"\nGenerator index {gen_idx}: {gen.name}")
        print(f"  Bus:                    {gen.bus.name}")
        print(f"  Bus is slack:           {gen.bus.is_slack}")
        print(f"  Device P setpoint:      {float(gen.P): .9f} MW")
        print(f"  pf_results.gen_p:       {gen_p_mw: .9f} MW")
        print(f"  pf_results.gen_q:       {gen_q_mvar: .9f} MVAr")
        print(f"  pf_results.Sbus.real:   {float(np.real(sbus_value)): .9f} MW")
        print(f"  pf_results.Sbus.imag:   {float(np.imag(sbus_value)): .9f} MVAr")
        print(f"  gen_p - Sbus.real:      {diff_p_mw: .9f} MW")
        print(f"  gen_q - Sbus.imag:      {diff_q_mvar: .9f} MVAr")

        if gen.bus.is_slack and abs(diff_p_mw) > 1e-9:
            print("  RESULT: slack gen_p does NOT match solved Sbus active injection")
        elif gen.bus.is_slack:
            print("  RESULT: slack gen_p matches solved Sbus active injection")
        else:
            print("  RESULT: non-slack generator")


if __name__ == "__main__":
    print_generator_power_result_check()
