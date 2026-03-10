# ==============================================================================
# Unit test for compiling and executing a complex Generator Model (DAE system)
# ==============================================================================

import unittest
import numpy as np
from typing import List, Dict, Callable

from VeraGridEngine.Utils.Symbolic.symbolic import Var, cos, sin, Const, Expr
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.jit_compiler import EquationCompiler
from VeraGridEngine.enumerations import DynamicIntegrationMethod


class EmtModelTemplate:
    """Mock container for the block model."""
    __slots__ = ['block']

    def __init__(self) -> None:
        self.block: Block | None = None


def get_generator_emt_template() -> EmtModelTemplate:
    """
    Constructs the EMT template of a Synchronous Generator.
    """
    templ: EmtModelTemplate = EmtModelTemplate()

    # Variables
    theta: Var = Var("theta")
    omega: Var = Var("omega")
    psi_d: Var = Var("psi_d")
    psi_q: Var = Var("psi_q")
    psi_f: Var = Var("psi_f")
    psi_0: Var = Var("psi_0")
    et: Var = Var("et")

    # Differential Variables
    d_omega: Var = Var(name='d_omega', base_var=omega)
    d_theta: Var = Var(name='d_theta', base_var=theta)
    d_psi_d: Var = Var(name='d_psi_d', base_var=psi_d)
    d_psi_q: Var = Var(name='d_psi_q', base_var=psi_q)
    d_psi_0: Var = Var(name='d_psi_0', base_var=psi_0)
    d_psi_f: Var = Var(name='d_psi_f', base_var=psi_f)
    d_et: Var = Var(name='d_et', base_var=et)

    # Algebraic Variables
    i_a: Var = Var("i_a")
    i_b: Var = Var("i_b")
    i_c: Var = Var("i_c")
    v_d: Var = Var("v_d")
    v_q: Var = Var("v_q")
    v_0: Var = Var("v_0")
    i_d: Var = Var("i_d")
    i_q: Var = Var("i_q")
    i_0: Var = Var("i_0")
    v_f: Var = Var("v_f")
    i_f: Var = Var("i_f")
    Te: Var = Var("Te")
    Tm: Var = Var("Tm")
    Pe: Var = Var('Pe')
    Qe: Var = Var('Qe')
    Pm: Var = Var("Pm")

    # Parameters
    omega_base: Var = Var("omega_base")
    H: Var = Var("H")
    D: Var = Var("D")
    Ra: Var = Var("Ra")
    La: Var = Var("La")
    Lmd: Var = Var("Lmd")
    Lmq: Var = Var("Lmq")
    Lf: Var = Var("Lf")
    Rf: Var = Var("Rf")
    R0: Var = Var("R0")
    L0: Var = Var("L0")
    omega_ref: Var = Var("omega_ref")
    Kp: Var = Var("Kp")
    Ki: Var = Var("Ki")
    v_f0: Var = Var("v_f0")

    # Inputs (External)
    v_a: Var = Var("v_a")
    v_b: Var = Var("v_b")
    v_c: Var = Var("v_c")

    state_eqs: List[Expr] = list([
        v_d - Ra * i_d - omega * psi_q,
        v_q - Ra * i_q + omega * psi_d,
        v_0 - R0 * i_0,
        v_f - Rf * i_f,
        omega_base * omega,  # d_theta
        (Tm - Te - D * (omega - omega_ref)) / (2.0 * H),  # d_omega
        omega_base * (omega_ref - omega),  # d_et
    ])
    state_vars: List[Var] = list([psi_d, psi_q, psi_0, psi_f, theta, omega, et])

    algebraic_eqs: List[Expr] = list([
        psi_d - ((Lmd + La) * i_d + Lmd * i_f),
        psi_q - ((Lmq + La) * i_q),
        psi_f - (Lmd * i_d + (Lmd + Lf) * i_f),
        psi_0 - L0 * i_0,
        v_d - (2.0 / 3.0) * (
                    v_a * cos(theta) + v_b * cos(theta - 2.0 * np.pi / 3.0) + v_c * cos(theta + 2.0 * np.pi / 3.0)),
        v_q - (2.0 / 3.0) * (
                    v_a * sin(theta) + v_b * sin(theta - 2.0 * np.pi / 3.0) + v_c * sin(theta + 2.0 * np.pi / 3.0)),
        v_0 - (2.0 / 3.0) * (v_a * 0.5 + v_b * 0.5 + v_c * 0.5),
        i_a - (i_d * cos(theta) + i_q * sin(theta) + i_0),
        i_b - (i_d * cos(theta - 2.0 * np.pi / 3.0) + i_q * sin(theta - 2.0 * np.pi / 3.0) + i_0),
        i_c - (i_d * cos(theta + 2.0 * np.pi / 3.0) + i_q * sin(theta + 2.0 * np.pi / 3.0) + i_0),
        Te + (3.0 / 2.0) * (psi_d * i_q - psi_q * i_d),
        Pe - (i_a * v_a + i_b * v_b + i_c * v_c),
        Qe - (1.0 / np.sqrt(3.0)) * ((v_a - v_b) * i_c + (v_b - v_c) * i_a + (v_c - v_a) * i_b),
        Tm - (Te + Kp * (omega_ref - omega) + Ki * et),
        v_f - v_f0,
        Pm - Pe
    ])
    algebraic_vars: List[Var] = list([i_d, i_q, i_f, i_0, v_d, v_q, v_0, i_a, i_b, i_c, Te, Pe, Qe, Tm, v_f, Pm])

    in_vars: List[Var] = list([v_a, v_b, v_c])
    out_vars: List[Var] = list([i_a, i_b, i_c])

    parameters: Dict[Var, Const] = dict({
        omega_base: Const(376.99), H: Const(3.0), D: Const(0.0),
        Ra: Const(0.003), La: Const(0.2), Lmd: Const(1.0), Lmq: Const(0.6),
        Lf: Const(0.1), Rf: Const(0.001), R0: Const(0.01), L0: Const(0.1),
        omega_ref: Const(1.0), Kp: Const(10.0), Ki: Const(1.0), v_f0: Const(1.0)
    })

    templ.block = Block(
        name="SynchronousGenerator",
        state_eqs=state_eqs,
        state_vars=state_vars,
        algebraic_eqs=algebraic_eqs,
        algebraic_vars=algebraic_vars,
        in_vars=in_vars,
        out_vars=out_vars,
        parameters=parameters
    )

    templ.block.diff_vars = list([d_psi_d, d_psi_q, d_psi_0, d_psi_f, d_theta, d_omega, d_et])
    return templ


class TestGeneratorModel(unittest.TestCase):

    def test_compile_and_run_generator(self) -> None:
        """
        Tests the full pipeline using ONLY the official Block API.
        """
        print("\n=== Generator Model Compilation Test ===")

        # 1. Get Model
        template: EmtModelTemplate = get_generator_emt_template()
        block: Block = template.block

        # 2. Unified System (DAE)
        all_eqs: List[Expr] = list(block.state_eqs)
        all_eqs.extend(block.algebraic_eqs)

        all_unknowns: List[Var] = list(block.state_vars)
        all_unknowns.extend(block.algebraic_vars)

        params: List[Var] = list(block.parameters.keys())
        params.extend(block.in_vars)

        print(f"States: {len(block.state_vars)}")
        print(f"Algebraics: {len(block.algebraic_vars)}")
        print(f"Parameters & Inputs: {len(params)}")

        # 4. Compile (Using Trapezoidal)
        compiler: EquationCompiler = EquationCompiler(
            variables=all_unknowns,
            parameters=params,
            method=DynamicIntegrationMethod.DaeTrapezoidal
        )
        step_fn: Callable = compiler.compile(all_eqs, func_name='generator_step_fn')
        print("\n[OK] Function compiled successfully.")

        # 5. Execute Test Step
        n_unknowns: int = len(all_unknowns)
        n_params: int = len(params)

        current_state: np.ndarray = np.zeros(n_unknowns, dtype=np.float64)

        unknown_names: List[str] = list([v.name for v in all_unknowns])
        if 'omega' in unknown_names:
            current_state[unknown_names.index('omega')] = 1.0
        else:
            pass

        history: np.ndarray = current_state.copy()
        d_history: np.ndarray = np.zeros(n_unknowns, dtype=np.float64)
        history2: np.ndarray = np.zeros(n_unknowns, dtype=np.float64)
        param_vals: np.ndarray = np.zeros(n_params, dtype=np.float64)

        for i, p_var in enumerate(params):
            if p_var in block.parameters:
                param_vals[i] = float(block.parameters[p_var].value)
            elif p_var.name == 'v_a':
                param_vals[i] = 1.0
            elif p_var.name == 'v_b':
                param_vals[i] = -0.5
            elif p_var.name == 'v_c':
                param_vals[i] = -0.5
            else:
                pass
        # Execute
        h: float = 0.001
        residuals: np.ndarray = step_fn(current_state, param_vals, history, d_history, h, history2)

        print(f"Residuals shape: {residuals.shape}")

        self.assertIsInstance(residuals, np.ndarray)
        self.assertEqual(len(residuals), n_unknowns)
        self.assertTrue(bool(np.all(np.isfinite(residuals))))


if __name__ == '__main__':
    unittest.main()