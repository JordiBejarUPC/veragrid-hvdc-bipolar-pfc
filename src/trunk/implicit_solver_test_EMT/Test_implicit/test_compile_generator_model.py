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

from VeraGridEngine.Utils.Symbolic.symbolic import Var, DiffVar, cos, sin
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.jit_compiler import EquationCompiler


class EmtModelTemplate:
    """Mock container for the block model."""
    def __init__(self):
        self.block = None


def get_generator_emt_template() -> EmtModelTemplate:
    """
    Constructs the EMT template of a Synchronous Generator.

    :return: EmtModelTemplate containing the configured Block.
    """
    templ = EmtModelTemplate()

    # Variables
    theta = Var("theta")
    omega = Var("omega")
    psi_d = Var("psi_d")
    psi_q = Var("psi_q")
    psi_f = Var("psi_f")
    psi_0 = Var("psi_0")
    et = Var("et")

    # Differential Variables (DiffVars) - Using constructor instead of get_or_create
    d_omega = DiffVar(name='d_omega', base_var=omega)
    d_theta = DiffVar(name='d_theta', base_var=theta)
    d_psi_d = DiffVar(name='d_psi_d', base_var=psi_d)
    d_psi_q = DiffVar(name='d_psi_q', base_var=psi_q)
    d_psi_0 = DiffVar(name='d_psi_0', base_var=psi_0)
    d_psi_f = DiffVar(name='d_psi_f', base_var=psi_f)
    d_et = DiffVar(name='d_et', base_var=et)

    # Algebraic Variables
    i_a = Var("i_a")
    i_b = Var("i_b")
    i_c = Var("i_c")
    v_d = Var("v_d")
    v_q = Var("v_q")
    v_0 = Var("v_0")
    i_d = Var("i_d")
    i_q = Var("i_q")
    i_0 = Var("i_0")
    v_f = Var("v_f")
    i_f = Var("i_f")
    Te = Var("Te")
    Tm = Var("Tm")
    Pe = Var('Pe')
    Qe = Var('Qe')
    Pm = Var("Pm")

    # Parameters
    omega_base = Var("omega_base")
    H = Var("H")
    D = Var("D")
    Ra = Var("Ra")
    La = Var("La")
    Lmd = Var("Lmd")
    Lmq = Var("Lmq")
    Lf = Var("Lf")
    Rf = Var("Rf")
    R0 = Var("R0")
    L0 = Var("L0")
    omega_ref = Var("omega_ref")
    Kp = Var("Kp")
    Ki = Var("Ki")
    v_f0 = Var("v_f0")

    # Inputs (External)
    v_a = Var("v_a")
    v_b = Var("v_b")
    v_c = Var("v_c")

    # Block Definition
    templ.block = Block(
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
        algebraic_vars=[i_d, i_q, i_f, i_0,
                        v_d, v_q, v_0, i_a, i_b, i_c, Te, Pe, Qe,
                        Tm, v_f, Pm],
        in_vars=[v_a, v_b, v_c],
        out_vars=[i_a, i_b, i_c],
    )

    # Manually assign DiffVars to maintain order for testing
    templ.block.diff_vars = [d_psi_d, d_psi_q, d_psi_0, d_psi_f, d_theta, d_omega, d_et]
    return templ


def extract_parameters(equations, unknowns):
    """
    Identifies all symbolic variables in the equations that are not unknowns (states or algebraic).
    These are classified as parameters or inputs.
    """
    all_vars = set()
    for eq in equations:
        vars_in_eq = eq.get_vars()
        for v in vars_in_eq:
            all_vars.add(v)

    unknown_names = {u.name for u in unknowns}
    params = []
    for v in all_vars:
        if v.name not in unknown_names:
            params.append(v)

    return sorted(params, key=lambda x: x.name)


class TestGeneratorModel(unittest.TestCase):

    def test_compile_and_run_generator(self):
        """
        Tests the full pipeline: Model creation -> Parameter extraction -> JIT Compilation -> Numerical Evaluation.
        """
        print("\n=== Generator Model Compilation Test ===")

        # 1. Get Model
        template = get_generator_emt_template()
        block = template.block

        # 2. Unified System (DAE)
        all_eqs = block.state_eqs + block.algebraic_eqs
        all_unknowns = block.state_vars + block.algebraic_vars
        unknown_names = [v.name for v in all_unknowns]

        # 3. Detect Parameters
        params = extract_parameters(all_eqs, all_unknowns)
        param_names = [p.name for p in params]

        print(f"States: {len(block.state_vars)}")
        print(f"Algebraics: {len(block.algebraic_vars)}")
        print(f"Parameters: {len(params)}")

        # 4. Compile (Using Trapezoidal)
        compiler = EquationCompiler(variables=unknown_names, parameters=param_names, method='trapezoidal')
        step_fn = compiler.compile(all_eqs, func_name='generator_step_fn')

        print("\n[OK] Function compiled successfully.")

        # 5. Execute Test Step
        n_unknowns = len(all_unknowns)
        n_params = len(params)

        current_state = np.zeros(n_unknowns)
        # Avoid division by zero if omega is in denominator
        if 'omega' in unknown_names:
            idx_omega = unknown_names.index('omega')
            current_state[idx_omega] = 1.0

        history = current_state.copy()
        d_history = np.zeros(n_unknowns)
        history2 = np.zeros(n_unknowns)  # Buffer for BDF2 compatibility

        param_vals = np.ones(n_params)

        # Inject default values from event_dict if available
        if hasattr(block, 'event_dict'):
            for p_var, val_const in block.event_dict.items():
                if p_var.name in param_names:
                    idx = param_names.index(p_var.name)
                    param_vals[idx] = val_const.value

        # Set Inputs (Balanced 3-phase voltage)
        for v_name in ['v_a', 'v_b', 'v_c']:
            if v_name in param_names:
                idx = param_names.index(v_name)
                if v_name == 'v_a': param_vals[idx] = 1.0
                if v_name == 'v_b': param_vals[idx] = -0.5
                if v_name == 'v_c': param_vals[idx] = -0.5

        # Execute
        h = 0.001
        residuals = step_fn(current_state, param_vals, history, d_history, h, history2)

        print(f"Residuals shape: {residuals.shape}")

        self.assertIsInstance(residuals, np.ndarray)
        self.assertEqual(len(residuals), n_unknowns)


if __name__ == '__main__':
    unittest.main()