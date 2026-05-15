# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import os
import sys

SCRIPT_DIR: str = os.path.abspath(os.path.dirname(__file__))
REPO_ROOT: str = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
SRC_ROOT: str = os.path.join(REPO_ROOT, "src")

if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)
else:
    pass

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
else:
    pass

import matplotlib.pyplot as plt
import numpy as np

import VeraGridEngine.api as gce
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Templates.Emt.converter_switched_emt_template import get_switched_emt_converter
from VeraGridEngine.Templates.Emt.dc_line_emt_template import get_dc_line_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template_with_ref
from VeraGridEngine.Templates.Emt.transformer_emt_template import get_transformer_emt_template
from VeraGridEngine.Utils.Symbolic.block import Block, find_name_in_block
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Utils.Symbolic.static_parameter_mapping_rms import converter_control_code
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.enumerations import ConverterControlType, DynamicIntegrationMethod, EmtInitializationMethod, EmtSolverTypes, SolverType


def get_signal(problem: EmtProblemDae, block: Block, variable_name: str, trajectory: np.ndarray) -> np.ndarray:
    """
    Extract one signal from the EMT result matrix.

    :param problem: EMT problem with the variable index map.
    :param block: Root block where the signal is searched.
    :param variable_name: Symbolic variable name.
    :param trajectory: EMT state trajectory matrix.
    :return: Selected signal trajectory.
    """
    variable: Optional[Var] = find_name_in_block(variable_name, block)

    # Missing optional variables are handled with zeros so plotting never breaks
    # the whole study for one absent signal.
    if variable is not None:
        return np.array(trajectory[:, problem.get_var_idx(variable)], copy=True)
    else:
        print(f"Warning: variable '{variable_name}' was not found in block '{block.name}'.")
        return np.zeros(trajectory.shape[0], dtype=np.float64)
def main() -> None:
    """
    Build and run one simple point-to-point HVDC EMT example.

    :return: None.
    """
    ####################################################################################################################
    # Build VeraGrid object
    ####################################################################################################################

    sbase_mva: float = 100.0
    fbase_hz: float = 50.0
    ac_voltage_ll_kv: float = 90.0
    dc_voltage_kv: float = 145.0
    grid_resistance_ohm: float = 4.8 * 0.669
    grid_inductance_h: float = 0.052 * 0.669
    coupling_resistance_ohm: float = 3.68 / 10.0
    coupling_inductance_h: float = 30.0e-3
    inner_loop_tau_s: float = 1.0 / 3100.0
    # The switched two-level converter model is much stiffer and more expensive
    # than the averaged pseudo model, so keep the example horizon short.
    simulation_time_s: float = 2.0e-4
    time_step_s: float = 1.0e-5
    q_setpoint_1_mvar: float = 0.0
    q_setpoint_2_mvar: float = 0.0
    transfer_power_mw: float = 100.0

    grid: gce.MultiCircuit = gce.MultiCircuit(
        name="Point-to-point HVDC EMT example",
        Sbase=sbase_mva,
        fbase=fbase_hz,
    )

    ac_base_impedance_ohm: float = (ac_voltage_ll_kv * ac_voltage_ll_kv) / sbase_mva
    dc_base_impedance_ohm: float = (dc_voltage_kv * dc_voltage_kv) / sbase_mva
    omega_base_rad_s: float = 2.0 * np.pi * fbase_hz
    grid_r_pu: float = grid_resistance_ohm / ac_base_impedance_ohm
    grid_x_pu: float = omega_base_rad_s * grid_inductance_h / ac_base_impedance_ohm
    coupling_r_pu: float = coupling_resistance_ohm / ac_base_impedance_ohm
    coupling_x_pu: float = omega_base_rad_s * coupling_inductance_h / ac_base_impedance_ohm
    coupling_l_pu_s: float = coupling_inductance_h / ac_base_impedance_ohm
    dc_line_r_pu: float = (0.5 + 0.25 + 0.4) / dc_base_impedance_ohm
    current_kp: float = coupling_l_pu_s / inner_loop_tau_s
    current_ki: float = coupling_r_pu / inner_loop_tau_s

    ####################################################################################################################
    # Create buses
    ####################################################################################################################

    # The bus split is explicit so the AC grids, converter AC terminals and DC terminals
    # all remain visible when reading the script and when plotting results.
    bus_grid_1: gce.Bus = gce.Bus(name="Bus_Grid_1", Vnom=ac_voltage_ll_kv, is_slack=True)
    bus_pcc_1: gce.Bus = gce.Bus(name="Bus_PCC_1", Vnom=ac_voltage_ll_kv)
    bus_dc_1: gce.Bus = gce.Bus(name="Bus_DC_1", Vnom=dc_voltage_kv, is_dc=True)
    bus_dc_2: gce.Bus = gce.Bus(name="Bus_DC_2", Vnom=dc_voltage_kv, is_dc=True)
    bus_pcc_2: gce.Bus = gce.Bus(name="Bus_PCC_2", Vnom=ac_voltage_ll_kv)
    bus_grid_2: gce.Bus = gce.Bus(name="Bus_Grid_2", Vnom=ac_voltage_ll_kv, is_slack=True)

    grid.add_bus(bus_grid_1)
    grid.add_bus(bus_pcc_1)
    grid.add_bus(bus_dc_1)
    grid.add_bus(bus_dc_2)
    grid.add_bus(bus_pcc_2)
    grid.add_bus(bus_grid_2)

    ####################################################################################################################
    # Create devices
    ####################################################################################################################

    # Two Thevenin generators represent the two AC systems at the ends of the link.
    generator_1: gce.Generator = gce.Generator(
        name="Generator_Grid_1",
        P=0.0,
        Q=0.0,
        vset=1.0,
        Snom=sbase_mva,
        freq=fbase_hz,
        r1=grid_r_pu,
        x1=grid_x_pu,
    )
    generator_2: gce.Generator = gce.Generator(
        name="Generator_Grid_2",
        P=0.0,
        Q=0.0,
        vset=1.0,
        Snom=sbase_mva,
        freq=fbase_hz,
        r1=grid_r_pu,
        x1=grid_x_pu,
    )
    grid.add_generator(bus_grid_1, generator_1)
    grid.add_generator(bus_grid_2, generator_2)

    # The transformer objects are used as the AC-side RL coupling branches because
    # the EMT catalog already provides a matching branch template for them.
    transformer_1: gce.Transformer2W = gce.Transformer2W(
        name="Transformer_Filter_1",
        bus_from=bus_grid_1,
        bus_to=bus_pcc_1,
        rate=sbase_mva,
        r=coupling_r_pu,
        x=coupling_x_pu,
        tap_module=1.0,
        tap_phase=0.0,
    )
    transformer_2: gce.Transformer2W = gce.Transformer2W(
        name="Transformer_Filter_2",
        bus_from=bus_grid_2,
        bus_to=bus_pcc_2,
        rate=sbase_mva,
        r=coupling_r_pu,
        x=coupling_x_pu,
        tap_module=1.0,
        tap_phase=0.0,
    )
    grid.add_transformer2w(transformer_1)
    grid.add_transformer2w(transformer_2)

    # Converter 1 regulates the DC voltage. Converter 2 imposes a constant active-power
    # transfer order so the power flow starts from a real transmitted-power operating point.
    converter_1: gce.VSC = gce.VSC(
        name="VSC_1",
        bus_from=bus_dc_1,
        bus_to=bus_pcc_1,
        rate=sbase_mva,
        control1=ConverterControlType.Vm_dc,
        control2=ConverterControlType.Qac,
        control1_val=1.0,
        control2_val=q_setpoint_1_mvar,
    )
    converter_2: gce.VSC = gce.VSC(
        name="VSC_2",
        bus_from=bus_dc_2,
        bus_to=bus_pcc_2,
        rate=sbase_mva,
        control1=ConverterControlType.Pdc,
        control2=ConverterControlType.Qac,
        control1_val=transfer_power_mw,
        control2_val=q_setpoint_2_mvar,
    )
    grid.add_vsc(converter_1)
    grid.add_vsc(converter_2)

    # The static DC line stays resistive for power flow, while the EMT RL behavior is
    # injected later through a custom symbolic EMT template.
    dc_line: gce.DcLine = gce.DcLine(
        name="HVDC_Line",
        bus_from=bus_dc_1,
        bus_to=bus_dc_2,
        r=dc_line_r_pu,
        rate=sbase_mva,
    )
    grid.add_dc_line(dc_line)

    ####################################################################################################################
    # Build EMT bus shells and device EMT models
    ####################################################################################################################

    # Every branch model later connects to the bus EMT shell voltages, so the bus shells
    # must exist before attaching the branch and converter models.
    bus: gce.Bus
    for bus in grid.buses:
        get_bus_emt_template(grid, bus)

    generator_1_mdl: Block = get_generator_thevenin_rl_emt_template_with_ref(vf=grid.var_factory, name="grid1_thevenin_emt").block
    generator_2_mdl: Block = get_generator_thevenin_rl_emt_template_with_ref(vf=grid.var_factory, name="grid2_thevenin_emt").block
    transformer_1_mdl: Block = get_transformer_emt_template(vf=grid.var_factory, name="transformer_filter_1_emt").block
    transformer_2_mdl: Block = get_transformer_emt_template(vf=grid.var_factory, name="transformer_filter_2_emt").block
    converter_1_mdl: Block = get_switched_emt_converter(vf=grid.var_factory, name="vsc1_pseudo_emt").block
    converter_2_mdl: Block = get_switched_emt_converter(vf=grid.var_factory, name="vsc2_pseudo_emt").block
    # The built-in DC line EMT template is used here as requested so the script stays
    # aligned with the standard VeraGrid EMT catalog instead of defining a local model.
    dc_line_mdl: Block = get_dc_line_emt_template(vf=grid.var_factory, name="hvdc_link_rl_emt").block

    # Converter 1 regulates DC voltage in EMT, but the pseudo-EMT converter template uses
    # `P0` as the active-power feedforward when the converter is not in an explicit active-
    # power mode. Because this study starts from a loaded HVDC operating point, `P0` must be
    # non-zero here so converter 1 is initialized around the transmitted-power equilibrium.
    converter_1_mdl.set_parameter_in_model(var_name="sbase_vsc1_pseudo_emt", new_value=sbase_mva)
    converter_1_mdl.set_parameter_in_model(var_name="omega_base_vsc1_pseudo_emt", new_value=omega_base_rad_s)
    converter_1_mdl.set_parameter_in_model(var_name="control1_vsc1_pseudo_emt", new_value=converter_control_code(ConverterControlType.Vm_dc))
    converter_1_mdl.set_parameter_in_model(var_name="control2_vsc1_pseudo_emt", new_value=converter_control_code(ConverterControlType.Qac))
    converter_1_mdl.set_parameter_in_model(var_name="control1_val_vsc1_pseudo_emt", new_value=1.0)
    converter_1_mdl.set_parameter_in_model(var_name="control2_val_vsc1_pseudo_emt", new_value=q_setpoint_1_mvar)
    converter_1_mdl.set_parameter_in_model(var_name="R_eq_vsc1_pseudo_emt", new_value=coupling_r_pu)
    converter_1_mdl.set_parameter_in_model(var_name="L_eq_vsc1_pseudo_emt", new_value=coupling_x_pu)
    converter_1_mdl.set_parameter_in_model(var_name="C_dc_vsc1_pseudo_emt", new_value=0.08)
    converter_1_mdl.set_parameter_in_model(var_name="R_dc_vsc1_pseudo_emt", new_value=1e6)
    converter_1_mdl.set_parameter_in_model(var_name="R_dc_term_vsc1_pseudo_emt", new_value=0.0001)
    converter_1_mdl.set_parameter_in_model(var_name="P0_vsc1_pseudo_emt", new_value=transfer_power_mw)
    converter_1_mdl.set_parameter_in_model(var_name="pll_kp_vsc1_pseudo_emt", new_value=40.0)
    converter_1_mdl.set_parameter_in_model(var_name="pll_ki_vsc1_pseudo_emt", new_value=400.0)
    converter_1_mdl.set_parameter_in_model(var_name="i_kp_vsc1_pseudo_emt", new_value=current_kp)
    converter_1_mdl.set_parameter_in_model(var_name="i_ki_vsc1_pseudo_emt", new_value=current_ki)
    converter_1_mdl.set_parameter_in_model(var_name="vdc_kp_vsc1_pseudo_emt", new_value=2.0)
    converter_1_mdl.set_parameter_in_model(var_name="vdc_ki_vsc1_pseudo_emt", new_value=30.0)
    converter_1_mdl.set_parameter_in_model(var_name="q_kp_vsc1_pseudo_emt", new_value=0.8)
    converter_1_mdl.set_parameter_in_model(var_name="q_ki_vsc1_pseudo_emt", new_value=20.0)
    converter_1_mdl.set_parameter_in_model(var_name="i_max_vsc1_pseudo_emt", new_value=1.3)
    converter_1_mdl.set_parameter_in_model(var_name="m_max_vsc1_pseudo_emt", new_value=0.95)
    converter_1_mdl.set_parameter_in_model(var_name="P_loss_i1_vsc1_pseudo_emt", new_value=0.01)
    converter_1_mdl.set_parameter_in_model(var_name="P_loss_i2_vsc1_pseudo_emt", new_value=0.01)
    converter_1_mdl.set_parameter_in_model(var_name="tau_meas_vsc1_pseudo_emt", new_value=0.01)
    converter_1_mdl.set_parameter_in_model(var_name="aw_gain_vsc1_pseudo_emt", new_value=0.1)
    converter_1_mdl.set_parameter_in_model(var_name="vdc_floor_vsc1_pseudo_emt", new_value=0.05)

    # Converter 2 parameters are written explicitly so the active-power-control side is visible.
    converter_2_mdl.set_parameter_in_model(var_name="sbase_vsc2_pseudo_emt", new_value=sbase_mva)
    converter_2_mdl.set_parameter_in_model(var_name="omega_base_vsc2_pseudo_emt", new_value=omega_base_rad_s)
    converter_2_mdl.set_parameter_in_model(var_name="control1_vsc2_pseudo_emt", new_value=converter_control_code(ConverterControlType.Pdc))
    converter_2_mdl.set_parameter_in_model(var_name="control2_vsc2_pseudo_emt", new_value=converter_control_code(ConverterControlType.Qac))
    converter_2_mdl.set_parameter_in_model(var_name="control1_val_vsc2_pseudo_emt", new_value=transfer_power_mw)
    converter_2_mdl.set_parameter_in_model(var_name="control2_val_vsc2_pseudo_emt", new_value=q_setpoint_2_mvar)
    converter_2_mdl.set_parameter_in_model(var_name="R_eq_vsc2_pseudo_emt", new_value=coupling_r_pu)
    converter_2_mdl.set_parameter_in_model(var_name="L_eq_vsc2_pseudo_emt", new_value=coupling_x_pu)
    converter_2_mdl.set_parameter_in_model(var_name="C_dc_vsc2_pseudo_emt", new_value=0.08)
    converter_2_mdl.set_parameter_in_model(var_name="R_dc_vsc2_pseudo_emt", new_value=1e6)
    converter_2_mdl.set_parameter_in_model(var_name="R_dc_term_vsc2_pseudo_emt", new_value=0.0001)
    converter_2_mdl.set_parameter_in_model(var_name="P0_vsc2_pseudo_emt", new_value=transfer_power_mw)
    converter_2_mdl.set_parameter_in_model(var_name="pll_kp_vsc2_pseudo_emt", new_value=40.0)
    converter_2_mdl.set_parameter_in_model(var_name="pll_ki_vsc2_pseudo_emt", new_value=400.0)
    converter_2_mdl.set_parameter_in_model(var_name="i_kp_vsc2_pseudo_emt", new_value=current_kp)
    converter_2_mdl.set_parameter_in_model(var_name="i_ki_vsc2_pseudo_emt", new_value=current_ki)
    converter_2_mdl.set_parameter_in_model(var_name="vdc_kp_vsc2_pseudo_emt", new_value=2.0)
    converter_2_mdl.set_parameter_in_model(var_name="vdc_ki_vsc2_pseudo_emt", new_value=30.0)
    converter_2_mdl.set_parameter_in_model(var_name="q_kp_vsc2_pseudo_emt", new_value=0.8)
    converter_2_mdl.set_parameter_in_model(var_name="q_ki_vsc2_pseudo_emt", new_value=20.0)
    converter_2_mdl.set_parameter_in_model(var_name="i_max_vsc2_pseudo_emt", new_value=1.3)
    converter_2_mdl.set_parameter_in_model(var_name="m_max_vsc2_pseudo_emt", new_value=0.95)
    converter_2_mdl.set_parameter_in_model(var_name="P_loss_i1_vsc2_pseudo_emt", new_value=0.01)
    converter_2_mdl.set_parameter_in_model(var_name="P_loss_i2_vsc2_pseudo_emt", new_value=0.01)
    converter_2_mdl.set_parameter_in_model(var_name="tau_meas_vsc2_pseudo_emt", new_value=0.01)
    converter_2_mdl.set_parameter_in_model(var_name="aw_gain_vsc2_pseudo_emt", new_value=0.1)
    converter_2_mdl.set_parameter_in_model(var_name="vdc_floor_vsc2_pseudo_emt", new_value=0.05)

    ####################################################################################################################
    # Attach EMT models to devices
    ####################################################################################################################

    # The static objects and EMT blocks are attached here so the EMT problem builder can
    # traverse one grid object and recover both topology and equations.
    set_emt_model(device=generator_1, model=generator_1_mdl, var_factory=grid.var_factory)
    set_emt_model(device=generator_2, model=generator_2_mdl, var_factory=grid.var_factory)
    set_emt_model(device=transformer_1, model=transformer_1_mdl, var_factory=grid.var_factory)
    set_emt_model(device=transformer_2, model=transformer_2_mdl, var_factory=grid.var_factory)
    set_emt_model(device=converter_1, model=converter_1_mdl, var_factory=grid.var_factory)
    set_emt_model(device=converter_2, model=converter_2_mdl, var_factory=grid.var_factory)
    set_emt_model(device=dc_line, model=dc_line_mdl, var_factory=grid.var_factory)

    ####################################################################################################################
    # Balanced AC/DC power flow
    ####################################################################################################################

    # The balanced power flow creates the steady-state point that seeds the EMT initial values.
    pf_options: PowerFlowOptions = PowerFlowOptions(
        solver_type=SolverType.NR,
        retry_with_other_methods=True,
        verbose=False,
        tolerance=1e-6,
        max_iter=100,
        control_q=True,
        control_taps_modules=False,
        control_taps_phase=False,
        orthogonalize_controls=False,
    )
    pf_results: gce.PowerFlowResults = gce.power_flow(grid=grid, options=pf_options)

    print("=" * 80)
    print("BALANCED AC/DC POWER FLOW RESULTS")
    print("=" * 80)
    print(f"Converged: {pf_results.converged}")
    if pf_results.converged:
        print(pf_results.get_bus_df())
        print(pf_results.get_branch_df())
    else:
        print("The balanced AC/DC power flow did not converge.")
        return

    ####################################################################################################################
    # EMT problem
    ####################################################################################################################

    # Explicit initialization is used because the EMT study now starts directly from the
    # loaded power-flow point and does not need any scheduled reference step.
    emt_options: EmtOptions = EmtOptions(
        time_step=time_step_s,
        simulation_time=simulation_time_s,
        tolerance=1e-6,
        solver_type=EmtSolverTypes.Symbolic,
        initialization_method=EmtInitializationMethod.Explicit,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        verbose=1,
    )

    problem: EmtProblemDae = EmtProblemDae(
        grid=grid,
        options=emt_options,
        pf_results_3ph=None,
        pf_results=pf_results,
    )
    problem.set_events_group(None)

    print("=" * 80)
    print("EMT INITIALIZATION REPORT")
    print("=" * 80)
    print(f"Finite x0 : {bool(np.all(np.isfinite(problem.get_x0())))}")
    print(f"Finite dx0: {bool(np.all(np.isfinite(problem.get_dx0())))}")
    if problem.initialization_report is not None:
        print(f"Method    : {problem.initialization_report.method_used.name}")
        print(f"Status    : {problem.initialization_report.status.name}")
        print(f"Residual  : {problem.initialization_report.final_residual_inf:.3e}")
    else:
        print("The EMT initialization report is not available.")

    ####################################################################################################################
    # EMT solver
    ####################################################################################################################

    # The switched converter path is exercised through the symbolic backend in the
    # current EMT test suite, so keep this example on the same backend.
    solver: JitSymbolicSolver = JitSymbolicSolver(
        problem=problem,
        t0=0.0,
        t_end=simulation_time_s,
        h=time_step_s,
        method=emt_options.integration_method,
        pred_method=DynamicIntegrationMethod.OdeEuler,
        dense_threshold=0,
        verbose=False,
    )
    solver.build_jit_kernel(emt_options.integration_method)
    solver._build_jit_symbolic_hybrid(emt_options.integration_method, use_sparse=True)

    if emt_options.integration_method == DynamicIntegrationMethod.DaeTrapezoidal:
        solver.build_jit_kernel(DynamicIntegrationMethod.DaeBackEuler)
        solver._build_jit_symbolic_hybrid(DynamicIntegrationMethod.DaeBackEuler, use_sparse=True)
    else:
        pass

    time_s: np.ndarray
    trajectory: np.ndarray
    diff_trajectory: np.ndarray
    well_initialized: bool
    converged: bool
    time_s, trajectory, diff_trajectory, well_initialized, converged = solver.simulate()

    if diff_trajectory.shape[0] >= 0:
        pass
    else:
        print("Warning: unexpected differential trajectory shape returned by the solver.")

    print("=" * 80)
    print("EMT SIMULATION REPORT")
    print("=" * 80)
    print(f"well_initialized = {well_initialized}")
    print(f"converged        = {converged}")

    if converged is False:
        print("The EMT solver did not converge for the requested horizon.")
        return
    else:
        pass

    ####################################################################################################################
    # Build signals for plotting
    ####################################################################################################################

    # The power reference stays constant during EMT because the transient now starts
    # from the transferred-power operating point without any scheduled event.
    power_reference_trace_pu: np.ndarray = np.full(time_s.shape[0], transfer_power_mw / sbase_mva, dtype=np.float64)

    v_pcc1_a: np.ndarray = get_signal(problem, bus_pcc_1.emt_model, f"v_A_{bus_pcc_1.emt_model.name}", trajectory)
    v_pcc1_b: np.ndarray = get_signal(problem, bus_pcc_1.emt_model, f"v_B_{bus_pcc_1.emt_model.name}", trajectory)
    v_pcc1_c: np.ndarray = get_signal(problem, bus_pcc_1.emt_model, f"v_C_{bus_pcc_1.emt_model.name}", trajectory)
    v_pcc2_a: np.ndarray = get_signal(problem, bus_pcc_2.emt_model, f"v_A_{bus_pcc_2.emt_model.name}", trajectory)
    v_pcc2_b: np.ndarray = get_signal(problem, bus_pcc_2.emt_model, f"v_B_{bus_pcc_2.emt_model.name}", trajectory)
    v_pcc2_c: np.ndarray = get_signal(problem, bus_pcc_2.emt_model, f"v_C_{bus_pcc_2.emt_model.name}", trajectory)
    i_vsc1_a: np.ndarray = get_signal(problem, converter_1_mdl, "i_A_vsc1_pseudo_emt", trajectory)
    i_vsc1_b: np.ndarray = get_signal(problem, converter_1_mdl, "i_B_vsc1_pseudo_emt", trajectory)
    i_vsc1_c: np.ndarray = get_signal(problem, converter_1_mdl, "i_C_vsc1_pseudo_emt", trajectory)
    i_vsc2_a: np.ndarray = get_signal(problem, converter_2_mdl, "i_A_vsc2_pseudo_emt", trajectory)
    i_vsc2_b: np.ndarray = get_signal(problem, converter_2_mdl, "i_B_vsc2_pseudo_emt", trajectory)
    i_vsc2_c: np.ndarray = get_signal(problem, converter_2_mdl, "i_C_vsc2_pseudo_emt", trajectory)
    v_dc_1: np.ndarray = get_signal(problem, bus_dc_1.emt_model, f"v_DC_{bus_dc_1.emt_model.name}", trajectory)
    v_dc_2: np.ndarray = get_signal(problem, bus_dc_2.emt_model, f"v_DC_{bus_dc_2.emt_model.name}", trajectory)
    i_line: np.ndarray = get_signal(problem, dc_line_mdl, "i_f_dc_hvdc_link_rl_emt", trajectory)
    p_vsc1: np.ndarray = get_signal(problem, converter_1_mdl, "P_vsc1_pseudo_emt", trajectory)
    q_vsc1: np.ndarray = get_signal(problem, converter_1_mdl, "Q_vsc1_pseudo_emt", trajectory)
    p_vsc2: np.ndarray = get_signal(problem, converter_2_mdl, "P_vsc2_pseudo_emt", trajectory)
    q_vsc2: np.ndarray = get_signal(problem, converter_2_mdl, "Q_vsc2_pseudo_emt", trajectory)

    ####################################################################################################################
    # Plot results
    ####################################################################################################################

    # The plot layout groups AC terminal quantities, DC corridor quantities and converter powers.
    figure, axes = plt.subplots(4, 2, figsize=(16, 14), sharex=True)

    axes[0, 0].plot(time_s, v_pcc1_a, label="Va PCC1")
    axes[0, 0].plot(time_s, v_pcc1_b, label="Vb PCC1")
    axes[0, 0].plot(time_s, v_pcc1_c, label="Vc PCC1")
    axes[0, 0].set_ylabel("Voltage [pu]")
    axes[0, 0].set_title("Converter 1 AC terminal voltages")
    axes[0, 0].grid(True)
    axes[0, 0].legend(loc="upper right")

    axes[0, 1].plot(time_s, v_pcc2_a, label="Va PCC2")
    axes[0, 1].plot(time_s, v_pcc2_b, label="Vb PCC2")
    axes[0, 1].plot(time_s, v_pcc2_c, label="Vc PCC2")
    axes[0, 1].set_ylabel("Voltage [pu]")
    axes[0, 1].set_title("Converter 2 AC terminal voltages")
    axes[0, 1].grid(True)
    axes[0, 1].legend(loc="upper right")

    axes[1, 0].plot(time_s, i_vsc1_a, label="Ia VSC1")
    axes[1, 0].plot(time_s, i_vsc1_b, label="Ib VSC1")
    axes[1, 0].plot(time_s, i_vsc1_c, label="Ic VSC1")
    axes[1, 0].set_ylabel("Current [pu]")
    axes[1, 0].set_title("Converter 1 AC currents")
    axes[1, 0].grid(True)
    axes[1, 0].legend(loc="upper right")

    axes[1, 1].plot(time_s, i_vsc2_a, label="Ia VSC2")
    axes[1, 1].plot(time_s, i_vsc2_b, label="Ib VSC2")
    axes[1, 1].plot(time_s, i_vsc2_c, label="Ic VSC2")
    axes[1, 1].set_ylabel("Current [pu]")
    axes[1, 1].set_title("Converter 2 AC currents")
    axes[1, 1].grid(True)
    axes[1, 1].legend(loc="upper right")

    axes[2, 0].plot(time_s, v_dc_1, label="Vdc bus 1")
    axes[2, 0].plot(time_s, v_dc_2, label="Vdc bus 2")
    axes[2, 0].set_ylabel("Voltage [pu]")
    axes[2, 0].set_title("DC bus voltages")
    axes[2, 0].grid(True)
    axes[2, 0].legend(loc="upper right")

    axes[2, 1].plot(time_s, i_line, label="HVDC line current")
    axes[2, 1].set_ylabel("Current [pu]")
    axes[2, 1].set_title("HVDC line current")
    axes[2, 1].grid(True)
    axes[2, 1].legend(loc="upper right")

    axes[3, 0].plot(time_s, p_vsc1, label="P VSC1")
    axes[3, 0].plot(time_s, q_vsc1, label="Q VSC1")
    axes[3, 0].set_xlabel("Time [s]")
    axes[3, 0].set_ylabel("Power [pu]")
    axes[3, 0].set_title("Converter 1 active/reactive power")
    axes[3, 0].grid(True)
    axes[3, 0].legend(loc="upper right")

    axes[3, 1].plot(time_s, p_vsc2, label="P VSC2")
    axes[3, 1].plot(time_s, q_vsc2, label="Q VSC2")
    axes[3, 1].plot(time_s, power_reference_trace_pu, "--", label="P ref VSC2")
    axes[3, 1].set_xlabel("Time [s]")
    axes[3, 1].set_ylabel("Power [pu]")
    axes[3, 1].set_title("Converter 2 active/reactive power and reference")
    axes[3, 1].grid(True)
    axes[3, 1].legend(loc="upper right")

    figure.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
