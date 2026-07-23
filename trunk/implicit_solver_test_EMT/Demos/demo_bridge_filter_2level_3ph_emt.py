# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import os
import sys

import matplotlib.pyplot as plt
import numpy as np

SCRIPT_DIR: str = os.path.abspath(os.path.dirname(__file__))
REPO_ROOT: str = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..', '..'))
SRC_ROOT: str = os.path.join(REPO_ROOT, 'src')

if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)
else:
    pass

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
else:
    pass

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver, StructuralCompiledWarmupPolicy
from VeraGridEngine.Templates.Emt.bridge_filter_2level_3ph_emt_template import get_bridge_filter_2level_3ph_emt_template
from VeraGridEngine.Utils.procedural_logic import build_boundary_updater_from_block
from VeraGridEngine.Utils.Symbolic.block import Block, find_name_in_block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
from VeraGridEngine.enumerations import DynamicIntegrationMethod


class GenericEmtProblem(EmtProblemTemplate):
    """
    Minimal EMT problem used by the standalone bridge + filter demo.
    """

    __slots__ = []


def _build_constant_algebraic_var(vf: VarFactory, name: str, value: float) -> Tuple[Var, Expr]:
    """
    Build one algebraic variable constrained to a constant reference value.

    :param vf: Shared symbolic variable factory.
    :param name: Variable name.
    :param value: Constant reference value.
    :return: Tuple ``(variable, equation)``.
    """
    variable: Var = vf.add_var(name=name)
    reference_value: Const = Const(float(value))
    equation: Expr = variable - reference_value
    return variable, equation


def build_bridge_filter_problem() -> Tuple[GenericEmtProblem, dict[str, Var]]:
    """
    Build the standalone bridge + filter EMT problem used by this demo.

    :return: EMT problem and tracked variables.
    """
    vf: VarFactory = VarFactory()
    block_name: str = "bridge_filter_demo"
    theta_pll: Var
    theta_pll_eq: Expr
    omega_base: Var
    omega_base_eq: Expr
    v_A: Var
    v_A_eq: Expr
    v_B: Var
    v_B_eq: Expr
    v_C: Var
    v_C_eq: Expr
    v_cmd_d: Var
    v_cmd_d_eq: Expr
    v_cmd_q: Var
    v_cmd_q_eq: Expr
    v_cmd_0: Var
    v_cmd_0_eq: Expr
    v_dc: Var
    v_dc_eq: Expr
    k_v_conv: Var
    k_v_conv_eq: Expr
    m_max: Var
    m_max_eq: Expr
    vdc_floor: Var
    vdc_floor_eq: Expr
    omega_sw: Var = vf.add_var(name="omega_sw_demo")
    carrier_phase: Var = vf.add_var(name="carrier_phase_demo")
    R_f: Var
    R_f_eq: Expr
    L_f: Var
    L_f_eq: Expr
    bridge_filter_block: Block = get_bridge_filter_2level_3ph_emt_template(vf=vf, name=block_name).block
    root_block: Block
    problem: GenericEmtProblem
    tracked_vars: dict[str, Var] = dict()
    all_problem_vars: list[Var]
    init_values: dict[str, float] = dict()
    init_name: str
    init_var: Var | None

    theta_pll, theta_pll_eq = _build_constant_algebraic_var(vf=vf, name="theta_pll_demo", value=0.0)
    omega_base, omega_base_eq = _build_constant_algebraic_var(vf=vf, name="omega_base_demo", value=2.0 * np.pi * 50.0)
    v_A, v_A_eq = _build_constant_algebraic_var(vf=vf, name="v_A_demo", value=0.0)
    v_B, v_B_eq = _build_constant_algebraic_var(vf=vf, name="v_B_demo", value=0.0)
    v_C, v_C_eq = _build_constant_algebraic_var(vf=vf, name="v_C_demo", value=0.0)
    v_cmd_d, v_cmd_d_eq = _build_constant_algebraic_var(vf=vf, name="v_cmd_d_demo", value=0.3)
    v_cmd_q, v_cmd_q_eq = _build_constant_algebraic_var(vf=vf, name="v_cmd_q_demo", value=0.0)
    v_cmd_0, v_cmd_0_eq = _build_constant_algebraic_var(vf=vf, name="v_cmd_0_demo", value=0.0)
    v_dc, v_dc_eq = _build_constant_algebraic_var(vf=vf, name="v_dc_demo", value=1.0)
    k_v_conv, k_v_conv_eq = _build_constant_algebraic_var(vf=vf, name="k_v_conv_demo", value=0.5)
    m_max, m_max_eq = _build_constant_algebraic_var(vf=vf, name="m_max_demo", value=0.95)
    vdc_floor, vdc_floor_eq = _build_constant_algebraic_var(vf=vf, name="vdc_floor_demo", value=0.05)
    R_f, R_f_eq = _build_constant_algebraic_var(vf=vf, name="R_f_demo", value=0.02)
    L_f, L_f_eq = _build_constant_algebraic_var(vf=vf, name="L_f_demo", value=0.08)

    bridge_filter_block.connect(
        bridge_filter_block.in_vars,
        list([
            theta_pll,
            omega_base,
            v_A,
            v_B,
            v_C,
            v_cmd_d,
            v_cmd_q,
            v_cmd_0,
            v_dc,
            k_v_conv,
            m_max,
            vdc_floor,
            omega_sw,
            carrier_phase,
            R_f,
            L_f,
        ]),
    )

    root_block = Block(
        name="BridgeFilter2LevelStandaloneDemo",
        children=list([bridge_filter_block]),
        algebraic_vars=list([theta_pll, omega_base, v_A, v_B, v_C, v_cmd_d, v_cmd_q, v_cmd_0, v_dc, k_v_conv, m_max, vdc_floor, R_f, L_f]),
        algebraic_eqs=list([theta_pll_eq, omega_base_eq, v_A_eq, v_B_eq, v_C_eq, v_cmd_d_eq, v_cmd_q_eq, v_cmd_0_eq, v_dc_eq, k_v_conv_eq, m_max_eq, vdc_floor_eq, R_f_eq, L_f_eq]),
        event_dict=dict([
            (omega_sw, Const(2.0 * np.pi * 1000.0)),
            (carrier_phase, Const(0.0)),
        ]),
        init_eqs=dict([
            (theta_pll, Const(0.0)),
            (omega_base, Const(2.0 * np.pi * 50.0)),
            (v_A, Const(0.0)),
            (v_B, Const(0.0)),
            (v_C, Const(0.0)),
            (v_cmd_d, Const(0.3)),
            (v_cmd_q, Const(0.0)),
            (v_cmd_0, Const(0.0)),
            (v_dc, Const(1.0)),
            (k_v_conv, Const(0.5)),
            (m_max, Const(0.95)),
            (vdc_floor, Const(0.05)),
            (R_f, Const(0.02)),
            (L_f, Const(0.08)),
        ]),
    )
    root_block.unify_blocks()

    static_parameter_values_mapping: Dict[Var, Const] = dict(root_block.parameters)
    problem = GenericEmtProblem(
        sys_block=root_block,
        glob_time=vf.add_var("t_bridge_filter_demo"),
        static_parameter_values_mapping=static_parameter_values_mapping,
    )

    tracked_vars["i_A"] = find_name_in_block("i_A", problem.sys_block)
    tracked_vars["i_B"] = find_name_in_block("i_B", problem.sys_block)
    tracked_vars["i_C"] = find_name_in_block("i_C", problem.sys_block)
    tracked_vars["gate_a"] = find_name_in_block(f"gate_a_{block_name}_bridge", problem.sys_block)
    tracked_vars["gate_b"] = find_name_in_block(f"gate_b_{block_name}_bridge", problem.sys_block)
    tracked_vars["gate_c"] = find_name_in_block(f"gate_c_{block_name}_bridge", problem.sys_block)
    tracked_vars["v_conv_a"] = find_name_in_block(f"v_conv_a_{block_name}_bridge", problem.sys_block)
    tracked_vars["v_conv_b"] = find_name_in_block(f"v_conv_b_{block_name}_bridge", problem.sys_block)
    tracked_vars["v_conv_c"] = find_name_in_block(f"v_conv_c_{block_name}_bridge", problem.sys_block)

    all_problem_vars = list(problem.get_state_vars()) + list(problem.get_algebraic_vars())
    init_values = dict([
        ("theta_pll_demo", 0.0),
        ("omega_base_demo", 2.0 * np.pi * 50.0),
        ("v_A_demo", 0.0),
        ("v_B_demo", 0.0),
        ("v_C_demo", 0.0),
        ("v_cmd_d_demo", 0.3),
        ("v_cmd_q_demo", 0.0),
        ("v_cmd_0_demo", 0.0),
        ("v_dc_demo", 1.0),
        ("k_v_conv_demo", 0.5),
        ("m_max_demo", 0.95),
        ("vdc_floor_demo", 0.05),
        ("R_f_demo", 0.02),
        ("L_f_demo", 0.08),
        (f"i_A_{block_name}", 0.0),
        (f"i_B_{block_name}", 0.0),
        (f"i_C_{block_name}", 0.0),
    ])

    for init_name, init_value in init_values.items():
        init_var = next((var for var in all_problem_vars if var.name == init_name), None)
        if init_var is not None:
            problem.init_guess[init_var.uid] = float(init_value)
        else:
            pass

    return problem, tracked_vars


def run_bridge_filter_demo(enable_plots: bool = True) -> None:
    """
    Run the standalone bridge + filter EMT demo.

    :param enable_plots: Display matplotlib figures when ``True``.
    :return: None.
    """
    problem: GenericEmtProblem
    tracked_vars: dict[str, Var]
    boundary_updater = None
    solver: StructuralCompiledSolver
    time_s: np.ndarray
    state_traj: np.ndarray
    i_A_trace: np.ndarray
    i_B_trace: np.ndarray
    i_C_trace: np.ndarray
    gate_a_trace: np.ndarray
    gate_b_trace: np.ndarray
    gate_c_trace: np.ndarray
    v_conv_a_trace: np.ndarray
    v_conv_b_trace: np.ndarray
    v_conv_c_trace: np.ndarray

    problem, tracked_vars = build_bridge_filter_problem()
    boundary_updater = build_boundary_updater_from_block(problem)
    solver = StructuralCompiledSolver(
        problem=problem,
        t0=0.0,
        t_end=5.0e-4,
        h=1.0e-5,
        method=DynamicIntegrationMethod.DaeBackEuler,
        verbose=False,
        warmup_policy=StructuralCompiledWarmupPolicy.Off,
    )
    time_s, state_traj, _ = solver.simulate(boundary_updater=boundary_updater)

    i_A_trace = np.array(state_traj[:, problem.get_var_idx(tracked_vars["i_A"])], copy=True)
    i_B_trace = np.array(state_traj[:, problem.get_var_idx(tracked_vars["i_B"])], copy=True)
    i_C_trace = np.array(state_traj[:, problem.get_var_idx(tracked_vars["i_C"])], copy=True)
    gate_a_trace = np.array(state_traj[:, problem.get_var_idx(tracked_vars["gate_a"])], copy=True)
    gate_b_trace = np.array(state_traj[:, problem.get_var_idx(tracked_vars["gate_b"])], copy=True)
    gate_c_trace = np.array(state_traj[:, problem.get_var_idx(tracked_vars["gate_c"])], copy=True)
    v_conv_a_trace = np.array(state_traj[:, problem.get_var_idx(tracked_vars["v_conv_a"])], copy=True)
    v_conv_b_trace = np.array(state_traj[:, problem.get_var_idx(tracked_vars["v_conv_b"])], copy=True)
    v_conv_c_trace = np.array(state_traj[:, problem.get_var_idx(tracked_vars["v_conv_c"])], copy=True)

    print("=" * 72)
    print("BRIDGE + FILTER EMT DEMO SUMMARY")
    print("=" * 72)
    print(f"Gate A range : {float(np.min(gate_a_trace)): .3f} .. {float(np.max(gate_a_trace)): .3f}")
    print(f"Gate B range : {float(np.min(gate_b_trace)): .3f} .. {float(np.max(gate_b_trace)): .3f}")
    print(f"Gate C range : {float(np.min(gate_c_trace)): .3f} .. {float(np.max(gate_c_trace)): .3f}")
    print(f"Max |i_A|    : {float(np.max(np.abs(i_A_trace))): .6f} p.u.")
    print(f"Max |i_B|    : {float(np.max(np.abs(i_B_trace))): .6f} p.u.")
    print(f"Max |i_C|    : {float(np.max(np.abs(i_C_trace))): .6f} p.u.")

    if enable_plots:
        fig, axes = plt.subplots(3, 1, figsize=(13.0, 9.0), sharex=True)

        # The converter-side phase voltages show the switched bridge waveforms.
        axes[0].plot(time_s, v_conv_a_trace, label="v_conv_a", color="tab:blue")
        axes[0].plot(time_s, v_conv_b_trace, label="v_conv_b", color="tab:red")
        axes[0].plot(time_s, v_conv_c_trace, label="v_conv_c", color="tab:green")
        axes[0].set_ylabel("Voltage [p.u.]")
        axes[0].set_title("Bridge + Filter EMT - Converter Phase Voltages")
        axes[0].grid(True)
        axes[0].legend(loc="best")

        # The RL filter currents confirm the electrical response remains bounded.
        axes[1].plot(time_s, i_A_trace, label="i_A", color="tab:blue")
        axes[1].plot(time_s, i_B_trace, label="i_B", color="tab:red")
        axes[1].plot(time_s, i_C_trace, label="i_C", color="tab:green")
        axes[1].set_ylabel("Current [p.u.]")
        axes[1].set_title("Bridge + Filter EMT - Filter Currents")
        axes[1].grid(True)
        axes[1].legend(loc="best")

        # The PWM logic must toggle all three retained gate states.
        axes[2].step(time_s, gate_a_trace, where="post", label="gate_A", color="tab:blue")
        axes[2].step(time_s, gate_b_trace, where="post", label="gate_B", color="tab:red")
        axes[2].step(time_s, gate_c_trace, where="post", label="gate_C", color="tab:green")
        axes[2].set_xlabel("Time [s]")
        axes[2].set_ylabel("Gate [-]")
        axes[2].set_title("Bridge + Filter EMT - Gates")
        axes[2].grid(True)
        axes[2].legend(loc="best")

        fig.tight_layout()
        plt.show()
    else:
        pass


if __name__ == "__main__":
    run_bridge_filter_demo(enable_plots=True)
