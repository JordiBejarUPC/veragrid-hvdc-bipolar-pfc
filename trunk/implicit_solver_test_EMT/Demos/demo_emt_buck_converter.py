# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
EMT simulation of a DC-DC Buck Converter using BlockSolver.

This demo compares:
  - Symbolic Jacobian (legacy)
  - Automatic Jacobian (Sparse AD + Graph Coloring)

Both simulations use:
  - identical model
  - identical timestep
  - identical PWM control
"""

import time
import numpy as np
import matplotlib.pyplot as plt

from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.block_solver import BlockSolver
from VeraGridEngine.Utils.Symbolic.diagnostic import NewtonTraceCollector

from VeraGridEngine.enumerations import (
    DynamicIntegrationMethod,
    SimulationBackend,
    JacobianBackend,
)

# -----------------------------------------------------------------------------
# Model definition
# -----------------------------------------------------------------------------

def create_buck_converter_system():
    i_L = Var("i_L")
    v_C = Var("v_C")

    Vin_sw = Var("Vin_sw")
    R = Var("R")
    L = Var("L")
    C = Var("C")

    block = Block(
        name="BuckConverter",
        state_vars=[i_L, v_C],
        state_eqs=[
            (Vin_sw - v_C) / L,
            (i_L - v_C / R) / C,
        ],
        parameters={
            Vin_sw: Const(0.0),
            R: Const(5.0),
            L: Const(100e-6),
            C: Const(470e-6),
        },
    )

    return block, Vin_sw


# -----------------------------------------------------------------------------
# Simulation runner
# -----------------------------------------------------------------------------

def run_case(jacobian_backend: JacobianBackend):
    print("\n" + "=" * 70)
    print(f"Running Buck Converter with JacobianBackend = {jacobian_backend}")
    print("=" * 70)

    # --- Electrical / control parameters ---
    V_IN = 48.0
    V_OUT_REF = 12.0
    F_SW = 20e3
    T_SW = 1.0 / F_SW
    DUTY = V_OUT_REF / V_IN

    DT = 1e-6
    T_TOTAL = 0.020

    # --- Build model ---
    block, vin_var = create_buck_converter_system()
    glob_time = Var("t_glob")

    solver = BlockSolver(
        block_system=block,
        glob_time=glob_time,
        use_jit=True,
        backend=SimulationBackend.SymbolicImplicit,
        jacobian_backend=jacobian_backend,
    )

    solver.newton_trace_collector = NewtonTraceCollector()

    # --- PWM controller ---
    def pwm_controller(t, x, params):
        t_mod = t % T_SW
        val = V_IN if t_mod < (DUTY * T_SW) else 0.0

        offset = len(solver._event_parameters)
        idx = offset + solver.uid2idx_params[vin_var.uid]
        params[idx] = val

    # --- Initial state ---
    x0 = np.zeros(solver._n_vars)

    # --- Run simulation ---
    t_start = time.time()
    t_arr, y_arr = solver.simulate_unified(
        t0=0.0,
        t_end=T_TOTAL,
        h=DT,
        x0=x0,
        dx0=None,
        params0=None,
        method=DynamicIntegrationMethod.Trapezoid,
        boundary_update_fn=pwm_controller,
        verbose=False,
        dense_threshold=100,
    )
    elapsed = time.time() - t_start

    # --- Extract variables ---
    idx_iL = solver.uid2idx_vars[block.state_vars[0].uid]
    idx_vC = solver.uid2idx_vars[block.state_vars[1].uid]

    sol_i = y_arr[:, idx_iL]
    sol_v = y_arr[:, idx_vC]

    print(f"Elapsed time : {elapsed:.4f} s")
    print(f"Final V_out  : {sol_v[-1]:.6f} V")
    print(f"Final I_L    : {sol_i[-1]:.6f} A")
    print(f"Newton iters : {len(solver.newton_trace_collector.records)}")

    return t_arr, sol_v, sol_i, elapsed


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main():
    # --- Run both backends ---
    t_sym, v_sym, i_sym, time_sym = run_case(JacobianBackend.Symbolic)
    t_ad,  v_ad,  i_ad,  time_ad  = run_case(JacobianBackend.Automatic)

    # --- Comparison summary ---
    print("\n" + "-" * 70)
    print("COMPARISON SUMMARY")
    print("-" * 70)
    print(f"Symbolic time : {time_sym:.4f} s")
    print(f"AD time       : {time_ad:.4f} s")
    print(f"Speedup       : {time_sym / time_ad:.2f} x")
    print(f"ΔV_out final  : {abs(v_sym[-1] - v_ad[-1]):.3e} V")
    print(f"ΔI_L final    : {abs(i_sym[-1] - i_ad[-1]):.3e} A")

    # --- Sanity checks ---
    assert np.allclose(v_sym, v_ad, atol=1e-6)
    assert np.allclose(i_sym, i_ad, atol=1e-6)

    # -------------------------------------------------------------------------
    # Plot comparison
    # -------------------------------------------------------------------------

    plt.figure(figsize=(10, 8))

    # Voltage
    plt.subplot(2, 1, 1)
    plt.plot(t_sym * 1000, v_sym, 'b-', label='V_out (Symbolic)')
    plt.plot(t_ad * 1000,  v_ad,  'r--', label='V_out (AD)')
    plt.ylabel('Voltage [V]')
    plt.title('Buck Converter EMT – Symbolic vs AD Jacobian')
    plt.legend()
    plt.grid(True)

    # Current
    plt.subplot(2, 1, 2)
    plt.plot(t_sym * 1000, i_sym, 'b-', label='I_L (Symbolic)')
    plt.plot(t_ad * 1000,  i_ad,  'r--', label='I_L (AD)')
    plt.ylabel('Current [A]')
    plt.xlabel('Time [ms]')
    plt.legend()
    plt.grid(True)

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()
