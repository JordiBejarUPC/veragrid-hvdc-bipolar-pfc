# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np


def triangular_carrier(t: float, f_sw: float) -> float:
    """Evaluate the unit triangular PWM carrier.

    :param t: Simulation time in seconds.
    :param f_sw: Carrier switching frequency in hertz.
    :return: Carrier value in the interval [-1, 1].
    """

    half_period: float = 0.5 / float(f_sw)
    interval_index: int = int(np.floor(float(t) / half_period))
    interval_start: float = float(interval_index) * half_period
    alpha: float = float(np.clip((float(t) - interval_start) / half_period, 0.0, 1.0))
    if interval_index % 2 == 0:
        carrier: float = -1.0 + 2.0 * alpha
    else:
        carrier = 1.0 - 2.0 * alpha
    return float(carrier)


def ensure_repo_import_paths() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    src_root = repo_root / "src"
    for path in (str(src_root), str(repo_root)):
        if path not in sys.path:
            sys.path.insert(0, path)


ensure_repo_import_paths()

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.emt_solver_factory import build_emt_solver
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Utils.Symbolic.block import Block, find_name_in_block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.Utils.Symbolic.symbolic_ml import ml_three_phase_carrier_pwm_direct
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtSolverTypes


class GenericEmtProblem(EmtProblemTemplate):
    """Minimal EMT problem for the standalone soft PWM comparator."""

    __slots__ = []


class SoftPwmBoundaryUpdater:
    __slots__ = [
        "ref_indices",
        "carrier_index",
        "gate_indices",
        "f_ref",
        "f_sw",
        "modulation_index",
        "trace_t",
        "trace_refs",
        "trace_carrier",
        "trace_gates",
    ]

    def __init__(
        self,
        ref_indices: tuple[int, int, int],
        carrier_index: int,
        gate_indices: tuple[int, int, int],
        f_ref: float,
        f_sw: float,
        modulation_index: float,
    ) -> None:
        self.ref_indices = tuple(int(i) for i in ref_indices)
        self.carrier_index = int(carrier_index)
        self.gate_indices = tuple(int(i) for i in gate_indices)
        self.f_ref = float(f_ref)
        self.f_sw = float(f_sw)
        self.modulation_index = float(modulation_index)
        self.trace_t: list[float] = []
        self.trace_refs: list[tuple[float, float, float]] = []
        self.trace_carrier: list[float] = []
        self.trace_gates: list[tuple[float, float, float]] = []

    def _refs(self, t: float) -> tuple[float, float, float]:
        theta = 2.0 * np.pi * self.f_ref * float(t)
        return (
            float(self.modulation_index * np.sin(theta)),
            float(self.modulation_index * np.sin(theta - 2.0 * np.pi / 3.0)),
            float(self.modulation_index * np.sin(theta + 2.0 * np.pi / 3.0)),
        )

    def _carrier(self, t: float) -> float:
        return triangular_carrier(t=float(t), f_sw=self.f_sw)

    def update(self, t: float, x: np.ndarray, params: np.ndarray) -> None:
        refs = self._refs(float(t))
        carrier = self._carrier(float(t))
        for idx, value in zip(self.ref_indices, refs):
            params[idx] = value
        params[self.carrier_index] = carrier

        self.trace_t.append(float(t))
        self.trace_refs.append(refs)
        self.trace_carrier.append(carrier)
        self.trace_gates.append(tuple(float(x[i]) for i in self.gate_indices))

    def get_next_forced_event_time(self, t_prev: float, t_target: float):
        _unused = (t_prev, t_target)
        return None

    def arrays(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        return (
            np.asarray(self.trace_t, dtype=float),
            np.asarray(self.trace_refs, dtype=float),
            np.asarray(self.trace_carrier, dtype=float),
            np.asarray(self.trace_gates, dtype=float),
        )


def _soft_pwm_values(refs: tuple[float, float, float], carrier: float, lamda: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x = np.asarray(refs, dtype=float) - float(carrier)
    radicand = x * x + float(lamda)
    denom = np.sqrt(radicand)
    softsign = x / denom
    gates = 0.5 * (1.0 + softsign)
    return softsign, radicand, gates


def _set_init(problem: GenericEmtProblem, block: Block, name: str, value: float) -> None:
    var = find_name_in_block(name, block)
    if var is not None:
        problem.init_guess[var.uid] = float(value)


def build_soft_pwm_problem(
    f_ref: float = 50.0,
    f_sw: float = 1000.0,
    modulation_index: float = 0.8,
    lamda: float = 1.0e-3,
) -> tuple[GenericEmtProblem, SoftPwmBoundaryUpdater]:
    vf = VarFactory()
    t_var = Var("t_soft_pwm_compare")
    ref_a = vf.add_var("u_ref_a_soft_pwm_compare")
    ref_b = vf.add_var("u_ref_b_soft_pwm_compare")
    ref_c = vf.add_var("u_ref_c_soft_pwm_compare")
    carrier = vf.add_var("u_carrier_soft_pwm_compare")

    pwm_block, gate_a, gate_b, gate_c = ml_three_phase_carrier_pwm_direct(
        vf=vf,
        ref_a=ref_a,
        ref_b=ref_b,
        ref_c=ref_c,
        carrier=carrier,
        lamda=lamda,
        name="standalone_soft_pwm",
    )
    carrier0 = triangular_carrier(t=0.0, f_sw=f_sw)
    block = Block(
        name="StandaloneSoftPwmComparator",
        event_dict={
            ref_a: Const(0.0),
            ref_b: Const(float(modulation_index * np.sin(-2.0 * np.pi / 3.0))),
            ref_c: Const(float(modulation_index * np.sin(2.0 * np.pi / 3.0))),
            carrier: Const(carrier0),
        },
        children=[pwm_block],
    )
    block.unify_blocks()

    problem = GenericEmtProblem(
        sys_block=block,
        glob_time=t_var,
        static_parameter_values_mapping={},
    )

    refs0 = (0.0, float(modulation_index * np.sin(-2.0 * np.pi / 3.0)), float(modulation_index * np.sin(2.0 * np.pi / 3.0)))
    softsign0, radicand0, gates0 = _soft_pwm_values(refs0, carrier0, lamda)
    for phase, x_value, softsign_value, radicand_value, gate_value in zip(
        ("a", "b", "c"),
        np.asarray(refs0) - carrier0,
        softsign0,
        radicand0,
        gates0,
    ):
        denom_value = float(np.sqrt(radicand_value))
        denom_pos_value = float(np.sqrt(denom_value))
        _set_init(problem, block, f"softsign_pwm_{phase}_standalone_soft_pwm", float(softsign_value))
        _set_init(problem, block, f"softsign_x_aux_pwm_{phase}_standalone_soft_pwm", float(x_value))
        _set_init(problem, block, f"softsign_radicand_pwm_{phase}_standalone_soft_pwm", float(radicand_value))
        _set_init(problem, block, f"softsign_denom_a_pwm_{phase}_standalone_soft_pwm", denom_value)
        _set_init(problem, block, f"softsign_denom_b_pwm_{phase}_standalone_soft_pwm", denom_value)
        _set_init(problem, block, f"softsign_denom_pos_a_pwm_{phase}_standalone_soft_pwm", denom_pos_value)
        _set_init(problem, block, f"softsign_denom_pos_b_pwm_{phase}_standalone_soft_pwm", denom_pos_value)
        _set_init(problem, block, f"gate_pwm_{phase}_standalone_soft_pwm", float(gate_value))

    ref_indices = (
        problem.uid2idx_event_params[ref_a.uid],
        problem.uid2idx_event_params[ref_b.uid],
        problem.uid2idx_event_params[ref_c.uid],
    )
    gate_indices = (
        problem.get_var_idx(gate_a),
        problem.get_var_idx(gate_b),
        problem.get_var_idx(gate_c),
    )
    updater = SoftPwmBoundaryUpdater(
        ref_indices=ref_indices,
        carrier_index=problem.uid2idx_event_params[carrier.uid],
        gate_indices=gate_indices,
        f_ref=f_ref,
        f_sw=f_sw,
        modulation_index=modulation_index,
    )
    return problem, updater


def run_soft_pwm_case(
    f_ref: float = 50.0,
    f_sw: float = 1000.0,
    modulation_index: float = 0.8,
    lamda: float = 1.0e-3,
    t_end: float = 4.0e-3,
    h: float = 20.0e-6,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, bool, bool]:
    problem, updater = build_soft_pwm_problem(
        f_ref=f_ref,
        f_sw=f_sw,
        modulation_index=modulation_index,
        lamda=lamda,
    )
    options = EmtOptions()
    options.solver_type = EmtSolverTypes.Symbolic
    options.init_newton_max_iter = 50
    solver = build_emt_solver(
        options=options,
        problem=problem,
        t0=0.0,
        t_end=float(t_end),
        h=float(h),
        method=DynamicIntegrationMethod.DaeBackEuler,
    )
    trace_t, y, _dy, well_initialized, converged = solver.simulate(boundary_updater=updater)
    refs = np.asarray([updater._refs(float(t)) for t in trace_t], dtype=float)
    carrier = np.asarray([updater._carrier(float(t)) for t in trace_t], dtype=float)
    gates = y[:, list(updater.gate_indices)]
    return trace_t, refs, carrier, gates, bool(well_initialized), bool(converged)


def procedural_gates(refs: np.ndarray, carrier: np.ndarray) -> np.ndarray:
    return (refs >= carrier[:, None]).astype(float)


def plot_soft_pwm(trace_t: np.ndarray, refs: np.ndarray, carrier: np.ndarray, gates: np.ndarray, lamda: float) -> Path:
    out_path = Path(__file__).resolve().with_name("pwm_soft_direct_compare.png")
    labels = ["A", "B", "C"]
    hard_gates = procedural_gates(refs, carrier)
    fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True)
    for idx, label in enumerate(labels):
        axes[0].plot(trace_t, refs[:, idx], label=f"ref {label}")
        gate_axis = axes[idx + 1]
        gate_axis.plot(trace_t, gates[:, idx], label=f"soft gate {label}")
        gate_axis.step(trace_t, hard_gates[:, idx], where="post", linestyle="--", linewidth=1.0, label=f"hard gate {label}")
        gate_axis.set_ylabel(f"Gate {label}")
        gate_axis.grid(True, alpha=0.3)
        gate_axis.legend(loc="upper right")
    axes[0].plot(trace_t, carrier, label="carrier", color="black", linewidth=1.2)
    axes[0].set_ylabel("Comparator input")
    axes[3].set_xlabel("Time [s]")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend(loc="upper right")
    fig.suptitle(f"Standalone soft-sign carrier PWM, lamda={lamda:g}")
    fig.tight_layout()
    fig.savefig(out_path, dpi=170)
    plt.close(fig)
    return out_path


def main() -> None:
    lamda = 1.0e-3
    trace_t, refs, carrier, gates, well_initialized, converged = run_soft_pwm_case(lamda=lamda)
    hard_gates = procedural_gates(refs, carrier)
    print(f"Standalone soft PWM well initialized: {well_initialized}")
    print(f"Standalone soft PWM converged: {converged}")
    print(f"Samples: {len(trace_t)}")
    print(f"Gate min/max: {np.nanmin(gates):.9e} / {np.nanmax(gates):.9e}")
    print(f"Mean abs gate error vs procedural: {np.mean(np.abs(gates - hard_gates)):.9e}")
    out_path = plot_soft_pwm(trace_t, refs, carrier, gates, lamda=lamda)
    print(f"Plot saved to: {out_path}")


if __name__ == "__main__":
    main()
