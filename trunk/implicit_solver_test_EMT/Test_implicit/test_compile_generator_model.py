# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Unit test for compiling and executing a complex Generator Model (DAE system).

This test validates:
1. Definition of a Synchronous Machine model using the Block API.
2. Parameter extraction and system flattening.
3. JIT compilation of a large Differential-Algebraic Equation (DAE) system.
4. Numerical evaluation of the compiled residual function.
"""

import unittest
import numpy as np

from VeraGridEngine.Utils.Symbolic.symbolic import Var, cos, sin, Const
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.jit_compiler import EquationCompiler


class EmtModelTemplate:
    """Mock container for the block model."""

    def __init__(self):
        self.block = None


def get_generator_emt_template() -> EmtModelTemplate:
    """
    Constructs the EMT template of a Synchronous Generator.
    """
    templ = EmtModelTemplate()

    # Variables
    theta, omega = Var("theta"), Var("omega")
    psi_d, psi_q, psi_f, psi_0, et = Var("psi_d"), Var("psi_q"), Var("psi_f"), Var("psi_0"), Var("et")

    # Differential Variables
    d_omega = Var(name='d_omega', base_var=omega)
    d_theta = Var(name='d_theta', base_var=theta)
    d_psi_d = Var(name='d_psi_d', base_var=psi_d)
    d_psi_q = Var(name='d_psi_q', base_var=psi_q)
    d_psi_0 = Var(name='d_psi_0', base_var=psi_0)
    d_psi_f = Var(name='d_psi_f', base_var=psi_f)
    d_et = Var(name='d_et', base_var=et)

    # Algebraic Variables
    i_a, i_b, i_c = Var("i_a"), Var("i_b"), Var("i_c")
    v_d, v_q, v_0 = Var("v_d"), Var("v_q"), Var("v_0")
    i_d, i_q, i_0 = Var("i_d"), Var("i_q"), Var("i_0")
    v_f, i_f, Te, Tm = Var("v_f"), Var("i_f"), Var("Te"), Var("Tm")
    Pe, Qe, Pm = Var('Pe'), Var('Qe'), Var("Pm")

    # Parameters
    omega_base, H, D, Ra, La = Var("omega_base"), Var("H"), Var("D"), Var("Ra"), Var("La")
    Lmd, Lmq, Lf, Rf, R0, L0 = Var("Lmd"), Var("Lmq"), Var("Lf"), Var("Rf"), Var("R0"), Var("L0")
    omega_ref, Kp, Ki, v_f0 = Var("omega_ref"), Var("Kp"), Var("Ki"), Var("v_f0")

    # Inputs (External)
    v_a, v_b, v_c = Var("v_a"), Var("v_b"), Var("v_c")

    templ.block = Block(
        name="SynchronousGenerator",
        state_eqs=[
            v_d - Ra * i_d - omega * psi_q,
            v_q - Ra * i_q + omega * psi_d,
            v_0 - R0 * i_0,
            v_f - Rf * i_f,
            omega_base * omega,  # d_theta
            (Tm - Te - D * (omega - omega_ref)) / (2 * H),  # d_omega
            omega_base * (omega_ref - omega),  # d_et
        ],
        state_vars=[psi_d, psi_q, psi_0, psi_f, theta, omega, et],

        algebraic_eqs=[
            psi_d - ((Lmd + La) * i_d + Lmd * i_f),
            psi_q - ((Lmq + La) * i_q),
            psi_f - (Lmd * i_d + (Lmd + Lf) * i_f),
            psi_0 - L0 * i_0,
            v_d - (2 / 3) * (v_a * cos(theta) + v_b * cos(theta - 2 * np.pi / 3) + v_c * cos(theta + 2 * np.pi / 3)),
            v_q - (2 / 3) * (v_a * sin(theta) + v_b * sin(theta - 2 * np.pi / 3) + v_c * sin(theta + 2 * np.pi / 3)),
            v_0 - (2 / 3) * (v_a * 0.5 + v_b * 0.5 + v_c * 0.5),
            i_a - (i_d * cos(theta) + i_q * sin(theta) + i_0),
            i_b - (i_d * cos(theta - 2 * np.pi / 3) + i_q * sin(theta - 2 * np.pi / 3) + i_0),
            i_c - (i_d * cos(theta + 2 * np.pi / 3) + i_q * sin(theta + 2 * np.pi / 3) + i_0),
            Te + (3 / 2) * (psi_d * i_q - psi_q * i_d),
            Pe - (i_a * v_a + i_b * v_b + i_c * v_c),
            Qe - (1 / np.sqrt(3)) * ((v_a - v_b) * i_c + (v_b - v_c) * i_a + (v_c - v_a) * i_b),
            Tm - (Te + Kp * (omega_ref - omega) + Ki * et),
            v_f - v_f0,
            Pm - Pe
        ],
        algebraic_vars=[i_d, i_q, i_f, i_0, v_d, v_q, v_0, i_a, i_b, i_c, Te, Pe, Qe, Tm, v_f, Pm],
        in_vars=[v_a, v_b, v_c],
        out_vars=[i_a, i_b, i_c],

        parameters={
            omega_base: Const(376.99), H: Const(3.0), D: Const(0.0),
            Ra: Const(0.003), La: Const(0.2), Lmd: Const(1.0), Lmq: Const(0.6),
            Lf: Const(0.1), Rf: Const(0.001), R0: Const(0.01), L0: Const(0.1),
            omega_ref: Const(1.0), Kp: Const(10.0), Ki: Const(1.0), v_f0: Const(1.0)
        }
    )

    templ.block.diff_vars = [d_psi_d, d_psi_q, d_psi_0, d_psi_f, d_theta, d_omega, d_et]
    return templ


class TestGeneratorModel(unittest.TestCase):

    def test_compile_and_run_generator(self):
        """
        Tests the full pipeline using ONLY the official Block API.
        """
        print("\n=== Generator Model Compilation Test ===")

        # 1. Get Model
        template = get_generator_emt_template()
        block = template.block

        # 2. Unified System (DAE)
        all_eqs = block.state_eqs + block.algebraic_eqs
        all_unknowns = block.state_vars + block.algebraic_vars

        params = list(block.parameters.keys()) + block.in_vars

        print(f"States: {len(block.state_vars)}")
        print(f"Algebraics: {len(block.algebraic_vars)}")
        print(f"Parameters & Inputs: {len(params)}")

        # 4. Compile (Using Trapezoidal)
        compiler = EquationCompiler(variables=all_unknowns, parameters=params, method='trapezoidal')
        step_fn = compiler.compile(all_eqs, func_name='generator_step_fn')
        print("\n[OK] Function compiled successfully.")

        # 5. Execute Test Step
        n_unknowns = len(all_unknowns)
        n_params = len(params)

        current_state = np.zeros(n_unknowns)

        unknown_names = [v.name for v in all_unknowns]
        if 'omega' in unknown_names:
            current_state[unknown_names.index('omega')] = 1.0

        history = current_state.copy()
        d_history = np.zeros(n_unknowns)
        history2 = np.zeros(n_unknowns)
        param_vals = np.zeros(n_params)

        for i, p_var in enumerate(params):
            if p_var in block.parameters:
                param_vals[i] = block.parameters[p_var].value
            elif p_var.name == 'v_a':
                param_vals[i] = 1.0
            elif p_var.name == 'v_b':
                param_vals[i] = -0.5
            elif p_var.name == 'v_c':
                param_vals[i] = -0.5

        # Execute
        h = 0.001
        residuals = step_fn(current_state, param_vals, history, d_history, h, history2)

        print(f"Residuals shape: {residuals.shape}")

        self.assertIsInstance(residuals, np.ndarray)
        self.assertEqual(len(residuals), n_unknowns)
        self.assertTrue(np.all(np.isfinite(residuals)))

if __name__ == '__main__':
    unittest.main()