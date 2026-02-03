# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Electromagnetic Transient (EMT) simulation of a DC-DC Buck Converter using the BlockSolver architecture.

This demo showcases:
1. Modeling a switched-mode power supply using differential equations.
2. Using JIT-compiled implicit solvers (Trapezoidal method) for stiff systems.
3. Implementing discrete control logic (PWM) via boundary update callbacks.
4. Visualizing cause-effect relationships in microsecond-scale transients.
"""

import numpy as np
import matplotlib.pyplot as plt

from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.block_solver import BlockSolver
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.Utils.Symbolic.diagnostic import NewtonTraceCollector
from VeraGridEngine.Simulations.Rms.numerical.compiled_integrator_fx import CompiledIntegration
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae


def create_buck_converter_system():
    """
    Creates the symbolic Block representation of a Buck Converter.

    System Equations:
      di_L/dt = (Vin_sw - v_C) / L
      dv_C/dt = (i_L - v_C / R) / C

    :return: Tuple containing the initialized Block and the input voltage variable (Vin_sw).
    """
    i_L = Var("i_L")
    v_C = Var("v_C")

    Vin_sw = Var("Vin_sw")
    R = Var("R")
    L = Var("L")
    C = Var("C")

    buck_block = Block(
        name="BuckConverter",
        state_vars=[i_L, v_C],
        state_eqs=[
            (Vin_sw - v_C) / L,
            (i_L - v_C / R) / C
        ],
        parameters={
            Vin_sw: Const(0.0),
            R: Const(5.0),
            L: Const(100e-6),
            C: Const(470e-6)
        }
    )

    return buck_block, Vin_sw


def run_emt_demo():
    """
    Executes the time-domain simulation of the Buck Converter startup and steady-state operation.
    """
    print("=== EMT DEMO: BUCK CONVERTER (Powered by BlockSolver) ===")

    V_IN = 48.0
    V_OUT_REF = 12.0
    F_SW = 20e3
    T_SW = 1.0 / F_SW
    DUTY = V_OUT_REF / V_IN

    DT = 1e-6
    T_TOTAL = 0.020

    sys_block, vin_var = create_buck_converter_system()
    glob_time = Var("t_glob")


    solver = CompiledIntegration(block = sys_block,
                                 t0 = 0.0,
                                 t_end = T_TOTAL,
                                 h = DT,
                                 max_iter= 100)

    solver.newton_trace_collector = NewtonTraceCollector()

    def pwm_controller(t, x, params):
        """
        Callback to update the switched input voltage (Vin_sw) based on the current simulation time.
        Implements a simple open-loop PWM strategy.
        """
        t_mod = t % T_SW
        if t_mod < (DUTY * T_SW):
            val = V_IN
        else:
            val = 0.0

        offset = len(sys_block.parameters)
        idx = offset + solver.uid2idx_params[vin_var.uid]

        params[idx] = val

    print(f" > Simulating {T_TOTAL * 1000} ms with dt={DT * 1e6} us...")

    x0 = np.zeros(len(sys_block.state_vars))
    dx0 = np.zeros(len(sys_block.diff_vars))
    params0 = np.zeros(len(sys_block.parameters))

    t_arr, y_arr = solver.simulate_unified(
        t0=0.0,
        t_end=T_TOTAL,
        h=DT,
        x0=x0,
        dx0=dx0,
        params0=params0,
        method=DynamicIntegrationMethod.Trapezoid,
        boundary_update_fn=pwm_controller,
        verbose=True,
        dense_threshold=100,
    )

    # Solver diagnostics (optional)
    collector = solver.newton_trace_collector
    print(f"Collected {len(collector.records)} Newton iterations")
    df = collector.to_dataframe()
    df.to_csv("newton_diagnostics.csv")

    idx_iL = solver.uid2idx_vars[sys_block.state_vars[0].uid]
    idx_vC = solver.uid2idx_vars[sys_block.state_vars[1].uid]

    sol_i = y_arr[:, idx_iL]
    sol_v = y_arr[:, idx_vC]

    sol_pwm = np.array([V_IN if (t % T_SW) < (DUTY * T_SW) else 0.0 for t in t_arr])

    print(f" > Simulación finalizada. Generando gráficas...")

    plt.figure(figsize=(10, 8))

    plt.subplot(3, 1, 1)
    plt.plot(t_arr * 1000, sol_v, 'b-', label='V_out')
    plt.axhline(V_OUT_REF, color='k', linestyle='--', alpha=0.5, label='Ref 12V')
    plt.title('Arranque Buck Converter (BlockSolver JIT)')
    plt.ylabel('Voltaje [V]')
    plt.legend()
    plt.grid(True)

    plt.subplot(3, 1, 2)
    zoom = int(len(t_arr) * 0.8)
    plt.plot(t_arr[zoom:] * 1000, sol_i[zoom:], 'r-', label='I_L (Rizado)')
    plt.title('Detalle Rizado de Corriente')
    plt.ylabel('Corriente [A]')
    plt.grid(True)

    plt.subplot(3, 1, 3)

    points_per_period = int(T_SW / DT)
    window_size = 3 * points_per_period

    start_idx = int(len(t_arr) * 0.9)
    end_idx = start_idx + window_size

    if end_idx > len(t_arr):
        end_idx = len(t_arr)
        start_idx = end_idx - window_size

    t_zoom = t_arr[start_idx:end_idx] * 1000
    pwm_zoom = sol_pwm[start_idx:end_idx]
    current_zoom = sol_i[start_idx:end_idx]

    ax1 = plt.gca()
    l1, = ax1.plot(t_zoom, pwm_zoom, 'k-', linewidth=1.5, alpha=0.6, label='PWM (Vin)')
    ax1.set_ylabel('Voltaje Entrada [V]')
    ax1.set_xlabel('Tiempo [ms]')
    ax1.set_ylim(-5, V_IN + 5)
    ax1.grid(True, alpha=0.5)

    ax2 = ax1.twinx()
    l2, = ax2.plot(t_zoom, current_zoom, 'r--', linewidth=2, label='Corriente Inductor')
    ax2.set_ylabel('Corriente [A]', color='r')
    ax2.tick_params(axis='y', labelcolor='r')

    lines = [l1, l2]
    ax1.legend(lines, [l.get_label() for l in lines], loc='upper center')

    plt.title('Detalle Microsegundos (Estado Estacionario): Causa (PWM) y Efecto (Rizado)')
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    run_emt_demo()
