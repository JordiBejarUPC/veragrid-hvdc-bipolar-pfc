# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Templates.Emt.arbitrary_source_emt_template import get_arbitrary_waveform_current_source_emt_template
from VeraGridEngine.Templates.Emt.arbitrary_source_emt_template import get_arbitrary_waveform_voltage_source_emt_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from trunk.dynamics_emt.support.emt_plot_exports import get_plot_results_directory


ARBITRARY_SOURCE_END_TIME_S: float = 0.04


class ArbitrarySourceEmtDemoProblem(EmtProblemTemplate):
    """
    Minimal EMT problem used by the arbitrary-waveform source demos.
    """

    __slots__ = ["grid"]

    def __init__(self, grid: MultiCircuit, sys_block: Block, glob_time: Var) -> None:
        self.grid = grid
        super().__init__(sys_block=sys_block, glob_time=glob_time)


class ArbitrarySourceEmtCaseResult:
    """
    Time-domain traces exported by one arbitrary-source EMT demo case.
    """

    __slots__ = ["case_name", "time", "bus_voltage", "source_current", "load_current", "png_path"]

    def __init__(self,
                 case_name: str,
                 time: np.ndarray,
                 bus_voltage: np.ndarray,
                 source_current: np.ndarray,
                 load_current: np.ndarray,
                 png_path: Path) -> None:
        self.case_name: str = str(case_name)
        self.time: np.ndarray = np.asarray(time, dtype=np.float64)
        self.bus_voltage: np.ndarray = np.asarray(bus_voltage, dtype=np.float64)
        self.source_current: np.ndarray = np.asarray(source_current, dtype=np.float64)
        self.load_current: np.ndarray = np.asarray(load_current, dtype=np.float64)
        self.png_path: Path = png_path


def _build_arbitrary_source_case_problem(case_name: str,
                                         voltage_source: bool,
                                         time_points: tuple[float, ...],
                                         value_points: tuple[float, ...],
                                         load_conductance: float = 1.0,
                                         source_conductance: float = 100.0) -> tuple[ArbitrarySourceEmtDemoProblem, Var, Var, Var, Path]:
    """
    Build one minimal arbitrary-source EMT case.

    :param case_name: Case identifier.
    :param voltage_source: Whether the source is voltage-driven.
    :param time_points: Waveform times in seconds.
    :param value_points: Matching waveform values.
    :param load_conductance: Conductive shunt load.
    :param source_conductance: Norton conductance for voltage-source variants.
    :return: Problem, bus voltage, source current, load current, and PNG path.
    """
    vf: VarFactory = VarFactory()
    glob_time: Var = vf.add_var(f"t_glob_{case_name}")
    bus_voltage: Var = vf.add_var(f"v_bus_{case_name}")
    load_current: Var = vf.add_var(f"i_load_{case_name}")

    if voltage_source:
        source_block = get_arbitrary_waveform_voltage_source_emt_template(
            vf=vf,
            phN=False,
            phA=True,
            phB=False,
            phC=False,
            time_points=time_points,
            value_points=value_points,
            source_conductance_value=source_conductance,
            name=case_name,
        ).block
    else:
        source_block = get_arbitrary_waveform_current_source_emt_template(
            vf=vf,
            phN=False,
            phA=True,
            phB=False,
            phC=False,
            time_points=time_points,
            value_points=value_points,
            name=case_name,
        ).block

    source_current: Var = source_block.out_vars[0]
    source_block.update_model(source_block.in_vars[0], bus_voltage)

    root_block = Block(
        name=case_name,
        algebraic_vars=[bus_voltage, load_current],
        algebraic_eqs=[
            source_current + load_current,
            load_current + Const(float(load_conductance)) * bus_voltage,
        ],
        children=[source_block],
        init_eqs={bus_voltage: Const(0.0), load_current: Const(0.0)},
    )
    root_block.unify_blocks()

    grid: MultiCircuit = MultiCircuit()
    problem: ArbitrarySourceEmtDemoProblem = ArbitrarySourceEmtDemoProblem(grid=grid, sys_block=root_block, glob_time=glob_time)
    output_dir: Path = get_plot_results_directory("arbitrary_source_emt", "symbolic")
    png_path: Path = output_dir / f"{case_name}.png"
    return problem, bus_voltage, source_current, load_current, png_path


def run_arbitrary_source_case(case_name: str,
                              voltage_source: bool,
                              time_points: tuple[float, ...],
                              value_points: tuple[float, ...],
                              enable_plots: bool = True) -> ArbitrarySourceEmtCaseResult:
    """
    Run one arbitrary-waveform EMT source case and export one PNG.

    :param case_name: Case identifier.
    :param voltage_source: Whether the source is voltage-driven.
    :param time_points: Waveform times in seconds.
    :param value_points: Matching waveform values.
    :param enable_plots: Whether to show the figure.
    :return: Exported case result.
    """
    problem, bus_voltage, source_current, load_current, png_path = _build_arbitrary_source_case_problem(
        case_name=case_name,
        voltage_source=voltage_source,
        time_points=time_points,
        value_points=value_points,
    )
    solver = JitSymbolicSolver(
        problem=problem,
        t0=0.0,
        t_end=ARBITRARY_SOURCE_END_TIME_S,
        h=1.0e-4,
        method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=False,
    )
    time_values, state_history, _diff_history, _converged, _diag = solver.simulate(boundary_updater=None)
    bus_voltage_idx: int = problem.get_var_idx(bus_voltage)
    source_current_idx: int = problem.get_var_idx(source_current)
    load_current_idx: int = problem.get_var_idx(load_current)

    figure, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    axes[0].plot(time_values, state_history[:, bus_voltage_idx], color="tab:blue", label="Bus voltage")
    axes[0].grid(True)
    axes[0].legend()
    axes[0].set_ylabel("Voltage [pu]")
    axes[0].set_title(case_name)

    axes[1].plot(time_values, state_history[:, source_current_idx], color="tab:green", label="Source current")
    axes[1].plot(time_values, state_history[:, load_current_idx], color="tab:red", linestyle="--", label="Load current")
    axes[1].grid(True)
    axes[1].legend()
    axes[1].set_xlabel("Time [s]")
    axes[1].set_ylabel("Current [pu]")
    figure.tight_layout()
    figure.savefig(png_path, dpi=200, bbox_inches="tight")

    if enable_plots:
        plt.show()
    else:
        plt.close(figure)

    return ArbitrarySourceEmtCaseResult(
        case_name=case_name,
        time=np.asarray(time_values, dtype=np.float64),
        bus_voltage=np.asarray(state_history[:, bus_voltage_idx], dtype=np.float64),
        source_current=np.asarray(state_history[:, source_current_idx], dtype=np.float64),
        load_current=np.asarray(state_history[:, load_current_idx], dtype=np.float64),
        png_path=png_path,
    )


def run_all_arbitrary_source_cases(enable_plots: bool = True) -> dict[str, ArbitrarySourceEmtCaseResult]:
    """
    Run the arbitrary current-source and arbitrary voltage-source EMT demos.

    :param enable_plots: Whether to show matplotlib windows.
    :return: Case results keyed by case name.
    """
    time_points: tuple[float, ...] = (0.0, 0.01, 0.02, 0.03, 0.04)
    current_values: tuple[float, ...] = (0.0, 0.5, -0.25, 0.75, 0.0)
    voltage_values: tuple[float, ...] = (0.0, 0.6, 0.2, 1.0, 0.0)
    return dict({
        "arbitrary_waveform_current_source": run_arbitrary_source_case(
            case_name="arbitrary_waveform_current_source",
            voltage_source=False,
            time_points=time_points,
            value_points=current_values,
            enable_plots=enable_plots,
        ),
        "arbitrary_waveform_voltage_source": run_arbitrary_source_case(
            case_name="arbitrary_waveform_voltage_source",
            voltage_source=True,
            time_points=time_points,
            value_points=voltage_values,
            enable_plots=enable_plots,
        ),
    })
