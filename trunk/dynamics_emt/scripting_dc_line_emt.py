# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import os
import sys
from typing import Tuple

import matplotlib.pyplot as plt
import numpy as np

SCRIPT_DIR: str = os.path.abspath(os.path.dirname(__file__))
REPO_ROOT: str = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
SRC_ROOT: str = os.path.join(REPO_ROOT, 'src')

if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)
else:
    pass

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
else:
    pass

import VeraGridEngine.api as gce
from VeraGridEngine.Devices.Branches.dc_line import DcLine
from VeraGridEngine.Devices.Branches.vsc import VSC
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import BoundaryUpdateWrapper, JitSymbolicSolver
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.Emt.converter_emt_template import get_emt_ideal_converter
from VeraGridEngine.Templates.Emt.dc_line_emt_template import get_dc_line_emt_template
from VeraGridEngine.Templates.Emt.dc_load_emt_template import get_dc_load_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template_with_ref
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.enumerations import DynamicIntegrationMethod, ConverterControlType, SolverType, VarPowerFlowReferenceType


class LoadStepBoundaryUpdater(BoundaryUpdateWrapper):
    """
    Apply a DC load-power step while preserving the EMT-problem boundary update.
    """

    __slots__ = [
        '_problem',
        '_param_full_idx',
        '_step_time_s',
        '_initial_value_pu',
        '_final_value_pu',
        '_record_time_s',
        '_record_value_pu',
        '_record_count',
    ]

    def __init__(
            self,
            problem: EmtProblemDae,
            param_full_idx: int,
            step_time_s: float,
            initial_value_pu: float,
            final_value_pu: float,
            max_records: int,
    ) -> None:
        """
        Build one DC load-step boundary updater.

        :param problem: EMT problem owning the runtime state.
        :param param_full_idx: Full-parameter-vector index of the DC load power parameter.
        :param step_time_s: Time instant of the power step.
        :param initial_value_pu: Initial load conductance in p.u.
        :param final_value_pu: Final load conductance in p.u.
        :param max_records: Maximum number of recorded samples.
        :return: None.
        """
        self._problem = problem
        self._param_full_idx = int(param_full_idx)
        self._step_time_s = float(step_time_s)
        self._initial_value_pu = float(initial_value_pu)
        self._final_value_pu = float(final_value_pu)
        self._record_time_s = np.zeros(max_records, dtype=float)
        self._record_value_pu = np.zeros(max_records, dtype=float)
        self._record_count = 0

    def _get_scheduled_value(self, time_s: float) -> float:
        """
        Return the scheduled load value at one time instant.

        :param time_s: Current simulation time.
        :return: Scheduled load conductance in p.u.
        """
        if time_s < self._step_time_s:
            return self._initial_value_pu
        else:
            return self._final_value_pu

    def update(self, t: float, x: np.ndarray, params: np.ndarray) -> None:
        """
        Apply the scheduled load step and forward the update to the EMT problem.

        :param t: Current simulation time.
        :param x: Accepted EMT state vector.
        :param params: Full parameter vector.
        :return: None.
        """
        applied_value_pu: float = self._get_scheduled_value(float(t))

        # The new load level is written before the problem update so the accepted EMT step
        # solves the correct algebraic operating point for that time interval.
        params[self._param_full_idx] = applied_value_pu
        self._problem.emt_boundary_update(float(t), x, params)

        if self._record_count < len(self._record_time_s):
            self._record_time_s[self._record_count] = float(t)
            self._record_value_pu[self._record_count] = applied_value_pu
            self._record_count += 1
        else:
            pass

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> float | None:
        """
        Return the earliest forced event from the load step or the wrapped problem.

        :param t_prev: Previous solver time.
        :param t_target: Nominal target time.
        :return: Earliest forced event time or ``None``.
        """
        local_time: float | None
        problem_time: float | None

        if float(t_prev) < self._step_time_s <= float(t_target):
            local_time = self._step_time_s
        else:
            local_time = None

        problem_time = self._problem.get_next_forced_event_time(float(t_prev), float(t_target))

        if local_time is None:
            return problem_time
        else:
            pass

        if problem_time is None:
            return local_time
        else:
            pass

        if local_time <= problem_time:
            return local_time
        else:
            return problem_time

    def get_record_time_s(self) -> np.ndarray:
        """
        Return the recorded load-step time vector.

        :return: Recorded load-step time vector.
        """
        return np.array(self._record_time_s[:self._record_count], copy=True)

    def get_record_value_pu(self) -> np.ndarray:
        """
        Return the recorded applied load-conductance trace.

        :return: Recorded applied load-conductance trace.
        """
        return np.array(self._record_value_pu[:self._record_count], copy=True)


def build_balanced_power_flow_options() -> PowerFlowOptions:
    """
    Build the balanced PF options used by the EMT DC-line script.

    :return: Balanced PF options.
    """
    return PowerFlowOptions(
        solver_type=SolverType.NR,
        verbose=False,
        retry_with_other_methods=True,
        max_iter=100,
        tolerance=1e-6,
        control_q=True,
        control_taps_modules=False,
        control_taps_phase=False,
        orthogonalize_controls=False,
    )


def build_default_emt_options() -> EmtOptions:
    """
    Build the EMT options used by the DC-line script.

    :return: EMT options instance.
    """
    return EmtOptions(
        time_step=1.0e-5,
        simulation_time=1.0e-2,
        tolerance=1e-6,
        initialization_method=gce.EmtInitializationMethod.Auto,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        solver_type=gce.EmtSolverTypes.Symbolic,
        verbose=0,
    )


def build_demo_grid() -> Tuple[gce.MultiCircuit, Bus, Bus, DcLine, Load, Generator, VSC]:
    """
    Build the compact AC/DC grid used by the EMT DC-line script.

    :return: Circuit and the main devices.
    """
    grid: gce.MultiCircuit = gce.MultiCircuit(name='Grid - VSC + DC Line + DC Load', Sbase=100.0, fbase=50.0)

    # The AC side provides a physically meaningful energy source through the VSC.
    bus_ac: Bus = gce.Bus(name='Bus_AC', Vnom=230.0, is_slack=True)
    bus_dc_source: Bus = gce.Bus(name='Bus_DC_Source', Vnom=320.0, is_dc=True)
    bus_dc_load: Bus = gce.Bus(name='Bus_DC_Load', Vnom=320.0, is_dc=True)

    generator: Generator = gce.Generator(name='Generator', vset=1.0, Snom=100.0, freq=50.0, r1=0.001, x1=0.4)
    vsc: VSC = gce.VSC(
        name='VSC',
        bus_from=bus_dc_source,
        bus_to=bus_ac,
        rate=100.0,
        control1=ConverterControlType.Qac,
        control2=ConverterControlType.Vm_dc,
        control1_val=0.0,
        control2_val=1.0,
    )
    dc_line: DcLine = gce.DcLine(name='DC_Line_EMT', bus_from=bus_dc_source, bus_to=bus_dc_load, r=0.02, rate=100.0)
    dc_load: Load = gce.Load(name='DC_Load', P=30.0, Q=0.0)

    grid.add_bus(bus_ac)
    grid.add_bus(bus_dc_source)
    grid.add_bus(bus_dc_load)
    grid.add_generator(bus_ac, generator)
    grid.add_vsc(vsc)
    grid.add_dc_line(dc_line)
    grid.add_load(bus_dc_load, dc_load)

    return grid, bus_dc_source, bus_dc_load, dc_line, dc_load, generator, vsc


def assign_emt_models(grid: gce.MultiCircuit, generator: Generator, vsc: VSC, dc_line: DcLine, dc_load: Load) -> None:
    """
    Attach EMT models to the DC-line scripting case.

    :param grid: Circuit under test.
    :param generator: Slack generator.
    :param vsc: AC/DC converter.
    :param dc_line: DC line branch.
    :param dc_load: DC load.
    :return: None.
    """
    bus: Bus
    generator_model: Block
    vsc_model: Block
    dc_line_model: Block
    dc_load_model: Block

    # The bus shells are built first so every EMT branch can bind to the correct algebraic bus variables.
    for bus in grid.buses:
        get_bus_emt_template(grid=grid, bus=bus)

    # The device templates are then attached to the existing static grid objects used by EmtProblemDae.
    generator_model = get_generator_thevenin_rl_emt_template_with_ref(vf=grid.var_factory).block
    vsc_model = get_emt_ideal_converter(vf=grid.var_factory, name=vsc.name).block
    dc_line_model = get_dc_line_emt_template(vf=grid.var_factory, name=dc_line.name).block
    dc_load_model = get_dc_load_emt_template(vf=grid.var_factory, name='dc_load_emt').block

    set_emt_model(device=generator, model=generator_model, var_factory=grid.var_factory)
    set_emt_model(device=vsc, model=vsc_model, var_factory=grid.var_factory)
    set_emt_model(device=dc_line, model=dc_line_model, var_factory=grid.var_factory)
    set_emt_model(device=dc_load, model=dc_load_model, var_factory=grid.var_factory)


def create_symbolic_solver(problem: EmtProblemDae, options: EmtOptions) -> JitSymbolicSolver:
    """
    Create the symbolic EMT solver used by this script.

    :param problem: EMT DAE problem.
    :param options: EMT options.
    :return: Configured symbolic EMT solver.
    """
    return JitSymbolicSolver(
        problem=problem,
        t0=0.0,
        t_end=options.simulation_time,
        h=options.time_step,
        method=options.integration_method,
        pred_method=DynamicIntegrationMethod.OdeEuler,
        dense_threshold=0,
        verbose=False,
    )


def get_constant_parameter_full_index(problem: EmtProblemDae, parameter_name: str) -> int:
    """
    Return the full-parameter-vector index of one constant parameter.

    :param problem: EMT problem under inspection.
    :param parameter_name: Constant-parameter symbolic name.
    :return: Full-parameter-vector index.
    """
    parameter: Var
    runtime_parameter_count: int = problem.get_variable_parameter_number()

    for parameter in problem.get_constant_parameters():
        if parameter.name == parameter_name:
            return int(runtime_parameter_count + problem.uid2idx_params[parameter.uid])
        else:
            pass

    raise KeyError(f"Constant parameter '{parameter_name}' was not found")


def run_dc_line_case(enable_plots: bool = False) -> None:
    """
    Run the EMT DC-line scripting case.

    Expected behaviour:

    - the source DC bus should remain close to the VSC setpoint,
    - the load DC bus should drop after the load step,
    - the DC-line current magnitude should increase after the load step,
    - the branch powers should remain bounded and positive at the source side.

    :param enable_plots: Display matplotlib figures when ``True``.
    :return: None.
    """
    grid: gce.MultiCircuit
    bus_dc_source: Bus
    bus_dc_load: Bus
    dc_line: DcLine
    dc_load: Load
    generator: Generator
    vsc: VSC
    pf_results: Any
    options: EmtOptions
    problem: EmtProblemDae
    solver: JitSymbolicSolver
    load_param_idx: int
    boundary_updater: LoadStepBoundaryUpdater
    time_s: np.ndarray
    state_traj: np.ndarray
    _diff_traj: np.ndarray
    v_source_var: Var
    v_load_var: Var
    i_from_var: Var
    i_to_var: Var
    p_from_var: Var
    p_to_var: Var
    v_source_trace: np.ndarray
    v_load_trace: np.ndarray
    i_from_trace: np.ndarray
    i_to_trace: np.ndarray
    p_from_trace: np.ndarray
    p_to_trace: np.ndarray

    grid, bus_dc_source, bus_dc_load, dc_line, dc_load, generator, vsc = build_demo_grid()
    assign_emt_models(grid=grid, generator=generator, vsc=vsc, dc_line=dc_line, dc_load=dc_load)
    pf_results = gce.power_flow(grid=grid, options=build_balanced_power_flow_options())

    print("=" * 60)
    print("BALANCED POWER FLOW RESULTS")
    print("=" * 60)
    print(f"Converged: {pf_results.converged}")
    if pf_results.converged:
        print(pf_results.get_bus_df())
        print(pf_results.get_branch_df())
    else:
        pass

    options = build_default_emt_options()
    problem = EmtProblemDae(grid=grid, options=options, pf_results=pf_results, pf_results_3Ph=None)
    solver = create_symbolic_solver(problem=problem, options=options)
    load_param_idx = get_constant_parameter_full_index(problem, 'g_dc_load_emt')
    boundary_updater = LoadStepBoundaryUpdater(
        problem=problem,
        param_full_idx=load_param_idx,
        step_time_s=5.0e-3,
        initial_value_pu=0.30,
        final_value_pu=0.45,
        max_records=4000,
    )

    time_s, state_traj, _diff_traj, _, _ = solver.simulate(boundary_updater=boundary_updater)

    # The variables are taken directly from the EMT external mapping to avoid fragile name heuristics.
    v_source_var = bus_dc_source.emt_model.external_mapping[VarPowerFlowReferenceType.Vdc]
    v_load_var = bus_dc_load.emt_model.external_mapping[VarPowerFlowReferenceType.Vdc]
    i_from_var = dc_line.emt_model.external_mapping[VarPowerFlowReferenceType.If_dc]
    i_to_var = dc_line.emt_model.external_mapping[VarPowerFlowReferenceType.It_dc]
    p_from_var = dc_line.emt_model.external_mapping[VarPowerFlowReferenceType.Pf]
    p_to_var = dc_line.emt_model.external_mapping[VarPowerFlowReferenceType.Pt]

    v_source_trace = np.array(state_traj[:, problem.get_var_idx(v_source_var)], copy=True)
    v_load_trace = np.array(state_traj[:, problem.get_var_idx(v_load_var)], copy=True)
    i_from_trace = np.array(state_traj[:, problem.get_var_idx(i_from_var)], copy=True)
    i_to_trace = np.array(state_traj[:, problem.get_var_idx(i_to_var)], copy=True)
    p_from_trace = np.array(state_traj[:, problem.get_var_idx(p_from_var)], copy=True)
    p_to_trace = np.array(state_traj[:, problem.get_var_idx(p_to_var)], copy=True)

    print("=" * 72)
    print("DC LINE EMT SUMMARY")
    print("=" * 72)
    print(f"Final source voltage  : {v_source_trace[-1]: .6f} p.u.")
    print(f"Final load voltage    : {v_load_trace[-1]: .6f} p.u.")
    print(f"Final If_dc           : {i_from_trace[-1]: .6f} p.u.")
    print(f"Final Pf              : {p_from_trace[-1]: .6f} p.u.")

    if enable_plots:
        _plot_dc_line_results(
            time_s=time_s,
            v_source_trace=v_source_trace,
            v_load_trace=v_load_trace,
            i_from_trace=i_from_trace,
            i_to_trace=i_to_trace,
            p_from_trace=p_from_trace,
            p_to_trace=p_to_trace,
            load_step_time_s=boundary_updater.get_record_time_s(),
            load_step_trace=boundary_updater.get_record_value_pu(),
        )
    else:
        pass


def _plot_dc_line_results(
        time_s: np.ndarray,
        v_source_trace: np.ndarray,
        v_load_trace: np.ndarray,
        i_from_trace: np.ndarray,
        i_to_trace: np.ndarray,
        p_from_trace: np.ndarray,
        p_to_trace: np.ndarray,
        load_step_time_s: np.ndarray,
        load_step_trace: np.ndarray,
) -> None:
    """
    Plot the EMT DC-line results.

    :param time_s: EMT time vector.
    :param v_source_trace: Source-bus voltage trace.
    :param v_load_trace: Load-bus voltage trace.
    :param i_from_trace: From-side current trace.
    :param i_to_trace: To-side current trace.
    :param p_from_trace: From-side power trace.
    :param p_to_trace: To-side power trace.
    :param load_step_time_s: Time vector of the applied load step.
    :param load_step_trace: Applied load-conductance trace.
    :return: None.
    """
    fig, axes = plt.subplots(3, 1, figsize=(13.0, 9.0), sharex=True)

    # The voltage subplot reveals the new steady state after the DC load increases.
    axes[0].plot(time_s, v_source_trace, label='Vdc source', color='tab:blue')
    axes[0].plot(time_s, v_load_trace, label='Vdc load', color='tab:orange')
    axes[0].set_ylabel('Voltage [p.u.]')
    axes[0].set_title('DC Line EMT - Bus Voltages')
    axes[0].grid(True)
    axes[0].legend(loc='best')

    # The current subplot shows the branch-current increase once the load step is applied.
    axes[1].plot(time_s, i_from_trace, label='If_dc', color='tab:green')
    axes[1].plot(time_s, i_to_trace, label='It_dc', color='tab:red')
    axes[1].set_ylabel('Current [p.u.]')
    axes[1].set_title('DC Line EMT - Currents')
    axes[1].grid(True)
    axes[1].legend(loc='best')

    # The power subplot overlays the branch powers with the scheduled DC load conductance.
    axes[2].plot(time_s, p_from_trace, label='Pf', color='tab:purple')
    axes[2].plot(time_s, p_to_trace, label='Pt', color='tab:brown')
    axes[2].step(load_step_time_s, load_step_trace, where='post', label='Load g', color='black')
    axes[2].set_xlabel('Time [s]')
    axes[2].set_ylabel('Power [p.u.]')
    axes[2].set_title('DC Line EMT - Power Transfer')
    axes[2].grid(True)
    axes[2].legend(loc='best')

    fig.tight_layout()
    plt.show()


def main() -> None:
    """
    Run the EMT DC-line scripting example.

    :return: None.
    """
    run_dc_line_case(enable_plots=True)


if __name__ == '__main__':
    main()
