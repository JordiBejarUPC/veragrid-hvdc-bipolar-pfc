from __future__ import annotations

from typing import Any

import numpy as np
from matplotlib import pyplot as plt

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver, PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_driver_3ph import PowerFlowDriver3Ph
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.small_signal_stability_emt_driver import SmallSignalStabilityEmtDriver
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.small_signal_stability_emt_options import SmallSignalStabilityEmtOptions
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.small_signal_stability_emt_results import SmallSignalStabilityEmtResults
from VeraGridEngine.Simulations.SmallSignalStabilityRms.small_signal_driver import SmallSignalStabilityRmsDriver
from VeraGridEngine.Simulations.SmallSignalStabilityRms.small_signal_options import RmsSmallSignalStabilityOptions
from VeraGridEngine.Templates.Emt.generator_emt_type_template_floquet_version import get_floquet_generator_template_emt
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_rlc_combo_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.transformer_emt_template import get_transformer_emt_template
from VeraGridEngine.Templates.Rms.genrow1_rms_template import get_genrow1_rms_template
from VeraGridEngine.Templates.Rms.genrow2_rms_template import get_genrow2_rms_template
from VeraGridEngine.Templates.Rms.genrow3_rms_template import get_genrow3_rms_template
from VeraGridEngine.Templates.Rms.genrow4_rms_template import get_genrow4_rms_template
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Templates.Rms.transformer_rms_template import get_transformer2w_rms
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model, set_rms_model
from VeraGridEngine.enumerations import (
    DynamicIntegrationMethod,
    EmtSolverTypes,
    RmsInitializationMethod,
    ShuntConnectionType,
    SmallSignalEmtBuildTypes,
    WindingType,
)

import VeraGridEngine.api as gce


GRID_SBASE_MVA: float = 100.0
KUNDUR_FBASE_HZ: float = 60.0
KUNDUR_PERIOD_S: float = 1.0 / KUNDUR_FBASE_HZ
KUNDUR_LINE_VNOM_KV: float = 230.0
KUNDUR_GEN_VNOM_KV: float = 20.0
KUNDUR_MACHINE_SN_MVA: float = 900.0
KUNDUR_MACHINE_TO_SYSTEM_Z: float = GRID_SBASE_MVA / KUNDUR_MACHINE_SN_MVA
KUNDUR_MACHINE_TO_SYSTEM_H: float = KUNDUR_MACHINE_SN_MVA / GRID_SBASE_MVA
KUNDUR_RA_SYS_PU: float = 0.0025 * KUNDUR_MACHINE_TO_SYSTEM_Z
KUNDUR_XD_SYS_PU: float = 1.80 * KUNDUR_MACHINE_TO_SYSTEM_Z
KUNDUR_XQ_SYS_PU: float = 1.70 * KUNDUR_MACHINE_TO_SYSTEM_Z
KUNDUR_XDP_SYS_PU: float = 0.30 * KUNDUR_MACHINE_TO_SYSTEM_Z
KUNDUR_XQP_SYS_PU: float = 0.55 * KUNDUR_MACHINE_TO_SYSTEM_Z
KUNDUR_XDPP_SYS_PU: float = 0.25 * KUNDUR_MACHINE_TO_SYSTEM_Z
KUNDUR_XQPP_SYS_PU: float = 0.25 * KUNDUR_MACHINE_TO_SYSTEM_Z
KUNDUR_XL_SYS_PU: float = 0.20 * KUNDUR_MACHINE_TO_SYSTEM_Z
KUNDUR_TD0P_S: float = 8.0
KUNDUR_TQ0P_S: float = 0.4
KUNDUR_TD0PP_S: float = 0.03
KUNDUR_TQ0PP_S: float = 0.05
KUNDUR_TRANSFORMER_X_PU: float = 0.15 * GRID_SBASE_MVA / 900.0
KUNDUR_RMS_M: list[float] = [2.0 * 6.50 * KUNDUR_MACHINE_TO_SYSTEM_H, 2.0 * 6.50 * KUNDUR_MACHINE_TO_SYSTEM_H, 2.0 * 6.175 * KUNDUR_MACHINE_TO_SYSTEM_H, 2.0 * 6.175 * KUNDUR_MACHINE_TO_SYSTEM_H]
KUNDUR_EMT_H: list[float] = [6.50 * KUNDUR_MACHINE_TO_SYSTEM_H, 6.50 * KUNDUR_MACHINE_TO_SYSTEM_H, 6.175 * KUNDUR_MACHINE_TO_SYSTEM_H, 6.175 * KUNDUR_MACHINE_TO_SYSTEM_H]
EMT_STEPS_PER_PERIOD: int = 4000
EMT_TIME_STEP_S: float = KUNDUR_PERIOD_S / EMT_STEPS_PER_PERIOD
FLOQUET_ASSESSMENT_TIME_S: float = 0.40
EMT_SIMULATION_TIME_S: float = FLOQUET_ASSESSMENT_TIME_S + 4.0 * KUNDUR_PERIOD_S
EMT_MODE_FREQUENCY_TOLERANCE_HZ: float = 0.20
EMT_ELECTROMECHANICAL_STATE_PREFIXES: tuple[str, ...] = (
    'delta_',
    'omega_',
    'theta_abs_',
    'e_qp_',
    'e_dp_',
    'psi_pp_d_',
    'psi_pp_q_',
)
SEQUENCE_ROTATION: complex = np.exp(1j * 2.0 * np.pi / 3.0)
T_012_TO_ABC: np.ndarray = np.array([[1.0, 1.0, 1.0], [1.0, SEQUENCE_ROTATION ** 2, SEQUENCE_ROTATION], [1.0, SEQUENCE_ROTATION, SEQUENCE_ROTATION ** 2]], dtype=complex)
T_ABC_TO_012: np.ndarray = np.linalg.inv(T_012_TO_ABC)


def plot_s_domain_eigenvalues(eigenvalues_rms: np.ndarray, eigenvalues_emt: np.ndarray) -> None:
    """
    Plot RMS and EMT eigenvalues together.

    :param eigenvalues_rms: RMS eigenvalues.
    :param eigenvalues_emt: EMT eigenvalues.
    :return: None.
    """
    values_rms: np.ndarray = np.asarray(eigenvalues_rms, dtype=complex).ravel()
    values_emt: np.ndarray = np.asarray(eigenvalues_emt, dtype=complex).ravel()
    valid_rms: np.ndarray = np.isfinite(values_rms.real) & np.isfinite(values_rms.imag)
    valid_emt: np.ndarray = np.isfinite(values_emt.real) & np.isfinite(values_emt.imag)
    values_rms = values_rms[valid_rms]
    values_emt = values_emt[valid_emt]

    if values_rms.size == 0 and values_emt.size == 0:
        pass
    else:
        all_values_list: list[np.ndarray] = list()
        if values_rms.size > 0:
            all_values_list.append(values_rms)
        else:
            pass
        if values_emt.size > 0:
            all_values_list.append(values_emt)
        else:
            pass

        all_values: np.ndarray = np.concatenate(all_values_list)
        real_part: np.ndarray = all_values.real
        imag_part: np.ndarray = all_values.imag
        slope: float = 1.0 / 0.05
        x_min_ref: float = min(float(np.min(real_part)), -1e-6)
        x_z: np.ndarray = np.linspace(x_min_ref * 1.05, 0.0, 400)
        y_z: np.ndarray = slope * x_z

        plt.figure(figsize=(9, 7))
        plt.plot(x_z, y_z, '--', color='grey', label='zeta = 5%')
        plt.plot(x_z, -y_z, '--', color='grey')

        if values_rms.size > 0:
            plt.scatter(values_rms.real, values_rms.imag, marker='o', color='tab:blue', label='RMS')
        else:
            pass
        if values_emt.size > 0:
            plt.scatter(values_emt.real, values_emt.imag, marker='x', color='tab:orange', label='EMT/Floquet')
        else:
            pass

        real_span: float = float(np.max(real_part) - np.min(real_part))
        imag_span: float = float(np.max(imag_part) - np.min(imag_part))
        margin_x: float = 0.1 * real_span if real_span > 0.0 else 1.0
        margin_y: float = 0.1 * imag_span if imag_span > 0.0 else 1.0

        plt.xlim(float(np.min(real_part)) - margin_x, float(np.max(real_part)) + margin_x)
        plt.ylim(float(np.min(imag_part)) - margin_y, float(np.max(imag_part)) + margin_y)
        plt.axhline(0.0, color='black', linewidth=1.0)
        plt.axvline(0.0, color='black', linewidth=1.0)
        plt.xlabel('Re')
        plt.ylabel('Im [rad/s]')
        plt.title('Kundur small-signal eigenvalues: RMS vs EMT/Floquet')
        plt.legend(loc='upper left')
        plt.tight_layout()


def plot_participation_factors(participation_factors: np.ndarray, title: str) -> None:
    """
    Plot one participation-factor matrix.

    :param participation_factors: Participation-factor matrix.
    :param title: Figure title.
    :return: None.
    """
    values: np.ndarray = np.asarray(participation_factors, dtype=float)
    if values.ndim != 2 or values.size == 0:
        pass
    else:
        n_rows: int = int(values.shape[0])
        n_cols: int = int(values.shape[1])
        fig_width: float = max(9.0, 0.35 * n_cols)
        fig_height: float = max(6.0, 0.25 * n_rows)
        mode_labels: list[str] = [f"Mode {idx + 1}" for idx in range(n_cols)]
        state_labels: list[str] = [f"State {idx + 1}" for idx in range(n_rows)]

        plt.figure(figsize=(fig_width, fig_height))
        image = plt.imshow(values, aspect='auto')
        plt.colorbar(image, label='Participation factor')
        plt.xticks(np.arange(n_cols), mode_labels, rotation=90)
        plt.yticks(np.arange(n_rows), state_labels)
        plt.xlabel('Modes')
        plt.ylabel('States')
        plt.title(title)
        plt.tight_layout()


def _safe_positive_ratio(numerator: float, denominator: float, default: float) -> float:
    """
    Compute a safe positive ratio.

    :param numerator: Numerator.
    :param denominator: Denominator.
    :param default: Fallback ratio.
    :return: Positive ratio.
    """
    if abs(denominator) <= 1e-14:
        ratio_value: float = default
    else:
        trial_ratio: float = float(numerator / denominator)
        if not np.isfinite(trial_ratio) or trial_ratio <= 0.0:
            ratio_value = default
        else:
            ratio_value = trial_ratio
    return ratio_value


def _build_kundur_230kv_tower(grid: gce.MultiCircuit) -> tuple[gce.OverheadLineType, gce.Wire]:
    """
    Build the line tower used for PF3 and EMT lines.

    :param grid: Circuit.
    :return: Tower and wire.
    """
    wire: gce.Wire = gce.Wire(name='Kundur 230-kV phase conductor', diameter=30.0, diameter_internal=0.0, is_tube=False, r=0.040, max_current=2.5)
    tower: gce.OverheadLineType = gce.OverheadLineType(name='Kundur 230-kV reference tower', Vnom=KUNDUR_LINE_VNOM_KV, earth_resistivity=100.0, frequency=grid.fBase)
    tower.add_wire_relationship(wire=wire, xpos=-8.0, ypos=25.0, phase=1)
    tower.add_wire_relationship(wire=wire, xpos=0.0, ypos=32.0, phase=2)
    tower.add_wire_relationship(wire=wire, xpos=8.0, ypos=25.0, phase=3)
    tower.compute()
    if tower.is_computed():
        pass
    else:
        raise RuntimeError('The Kundur 230-kV overhead-line tower could not be computed.')
    return tower, wire


def _set_transposed_kundur_line_matrices(line: gce.Line, r1: float, x1: float, b1: float, rate: float) -> None:
    """
    Rebuild one line ABC representation while preserving the positive sequence.

    :param line: Line object.
    :param r1: Positive-sequence resistance.
    :param x1: Positive-sequence reactance.
    :param b1: Positive-sequence susceptance.
    :param rate: Line rate.
    :return: None.
    """
    tower_r1: float = float(line.R)
    tower_x1: float = float(line.X)
    tower_b1: float = float(line.B)
    tower_r0: float = float(line.R0)
    tower_x0: float = float(line.X0)
    tower_b0: float = float(line.B0)
    r0_ratio: float = _safe_positive_ratio(tower_r0, tower_r1, default=3.0)
    x0_ratio: float = _safe_positive_ratio(tower_x0, tower_x1, default=3.0)
    b0_ratio: float = _safe_positive_ratio(tower_b0, tower_b1, default=1.0)
    r0: float = r1 * r0_ratio
    x0: float = x1 * x0_ratio
    b0: float = b1 * b0_ratio

    z012: np.ndarray = np.diag(np.array([complex(r0, x0), complex(r1, x1), complex(r1, x1)], dtype=complex))
    zabc: np.ndarray = T_012_TO_ABC @ z012 @ T_ABC_TO_012
    yabc_series: np.ndarray = np.linalg.inv(zabc)
    y012_shunt_stored: np.ndarray = np.diag(1j * 1e6 * np.array([b0, b1, b1], dtype=float))
    yabc_shunt_stored: np.ndarray = T_012_TO_ABC @ y012_shunt_stored @ T_ABC_TO_012
    ys_nabc: np.ndarray = np.zeros((4, 4), dtype=complex)
    ysh_nabc: np.ndarray = np.zeros((4, 4), dtype=complex)
    ys_nabc[1:4, 1:4] = yabc_series
    ysh_nabc[1:4, 1:4] = yabc_shunt_stored

    line.ys.values = ys_nabc
    line.ysh.values = ysh_nabc
    line.ys.phN = False
    line.ys.phA = True
    line.ys.phB = True
    line.ys.phC = True
    line.ysh.phN = False
    line.ysh.phA = True
    line.ysh.phB = True
    line.ysh.phC = True

    line.R = r1
    line.X = x1
    line.B = b1
    line.R0 = r0
    line.X0 = x0
    line.B0 = b0
    line.R2 = r1
    line.X2 = x1
    line.B2 = b1
    line.rate = rate


def _make_kundur_line(grid: gce.MultiCircuit, tower: gce.OverheadLineType, name: str, bus_from: gce.Bus, bus_to: gce.Bus, r: float, x: float, b: float, rate: float, length_km: float) -> gce.Line:
    """
    Create one Kundur line.

    :param grid: Circuit.
    :param tower: Tower template.
    :param name: Name.
    :param bus_from: From bus.
    :param bus_to: To bus.
    :param r: Resistance.
    :param x: Reactance.
    :param b: Susceptance.
    :param rate: Rate.
    :param length_km: Length.
    :return: Line object.
    """
    line: gce.Line = gce.Line(name=name, bus_from=bus_from, bus_to=bus_to, r=r, x=x, b=b, rate=rate, length=length_km)
    line.apply_template(tower, grid.Sbase, grid.fBase)
    _set_transposed_kundur_line_matrices(line=line, r1=r, x1=x, b1=b, rate=rate)
    line.length = length_km
    return line


def _make_kundur_transformer(name: str, bus_hv: gce.Bus, bus_lv: gce.Bus) -> gce.Transformer2W:
    """
    Create one Kundur transformer.

    :param name: Name.
    :param bus_hv: HV bus.
    :param bus_lv: LV bus.
    :return: Transformer.
    """
    trafo: gce.Transformer2W = gce.Transformer2W(name=name, bus_from=bus_hv, bus_to=bus_lv, HV=KUNDUR_LINE_VNOM_KV, LV=KUNDUR_GEN_VNOM_KV, nominal_power=900.0, design_rate=900.0, rate=900.0, r=0.0, x=KUNDUR_TRANSFORMER_X_PU, g=0.0, b=0.0, r0=0.0, x0=KUNDUR_TRANSFORMER_X_PU, b0=0.0, r2=0.0, x2=KUNDUR_TRANSFORMER_X_PU, b2=0.0)
    trafo.conn_f = WindingType.GroundedStar
    trafo.conn_t = WindingType.GroundedStar
    trafo.vector_group_number = 0
    trafo.phases = np.array([1, 2, 3], dtype=int)
    return trafo


def _validate_kundur_line_positive_sequence(lines: list[gce.Line]) -> None:
    """
    Validate positive-sequence consistency of the ABC lines.

    :param lines: Line list.
    :return: None.
    """
    max_z_error: float = 0.0
    max_b_error: float = 0.0
    line: gce.Line
    for line in lines:
        zabc: np.ndarray = np.linalg.inv(np.asarray(line.ys.values[1:4, 1:4], dtype=complex))
        z012: np.ndarray = T_ABC_TO_012 @ zabc @ T_012_TO_ABC
        yabc: np.ndarray = np.asarray(line.ysh.values[1:4, 1:4], dtype=complex) / 1e6
        y012: np.ndarray = T_ABC_TO_012 @ yabc @ T_012_TO_ABC
        max_z_error = max(max_z_error, abs(z012[1, 1] - complex(line.R, line.X)))
        max_b_error = max(max_b_error, abs(y012[1, 1].imag - line.B))

    if max_z_error > 1e-10 or max_b_error > 1e-10:
        raise RuntimeError(f'Kundur line ABC conversion is inconsistent with positive-sequence data: max |dZ1|={max_z_error:.3e}, max |dB1|={max_b_error:.3e}.')
    else:
        pass


def _available_model_parameter_names(block: Block) -> set[str]:
    """
    Collect model parameter names.

    :param block: Root block.
    :return: Parameter-name set.
    """
    names: set[str] = set()
    child: Block
    for child in block.get_all_blocks():
        event_var: Any
        for event_var in child.event_dict.keys():
            names.add(event_var.name)
        parameter_var: Any
        for parameter_var in child.parameters:
            names.add(parameter_var.name)
    return names


def _set_model_parameters(block: Block, values: dict[str, float], model_label: str) -> None:
    """
    Set template parameters when they are exposed.

    :param block: Model block.
    :param values: Parameter map.
    :param model_label: Label.
    :return: None.
    """
    available: set[str] = _available_model_parameter_names(block)
    missing: list[str] = list()
    name: str
    value: float
    for name, value in values.items():
        if name in available:
            block.set_parameter_in_model(var_name=name, new_value=value)
        else:
            missing.append(name)
    if len(missing) > 0:
        print(f'{model_label}: parameters not exposed by this template: {missing}')
    else:
        pass


def _patch_emt_governor_to_constant_mechanical_torque(generator_model: Block) -> bool:
    """
    Patch the EMT governor to a constant mechanical torque behavior.

    :param generator_model: Generator model.
    :return: True when patched.
    """
    block: Block
    for block in generator_model.get_all_blocks():
        lower_name: str = block.name.lower()
        if 'governor' in lower_name:
            y_gov0: Any = None
            t1_gov: Any = None
            state_var: Any
            for state_var in block.state_vars:
                if state_var.name == 'y_gov0':
                    y_gov0 = state_var
                else:
                    pass
            event_var: Any
            for event_var in block.event_dict.keys():
                if event_var.name == 'T1_gov':
                    t1_gov = event_var
                else:
                    pass

            if y_gov0 is None or t1_gov is None or len(block.state_eqs) == 0:
                patch_applied: bool = False
            else:
                block.state_eqs[0] = -y_gov0 / t1_gov
                patch_applied = True
            return patch_applied
        else:
            pass
    return False


def _patch_emt_exciter_to_constant_field(generator_model: Block) -> bool:
    """
    Replace EMT exciter dynamics by a constant-field behavior when possible.

    :param generator_model: Generator model.
    :return: True when the patch was applied.
    """
    block: Block
    for block in generator_model.get_all_blocks():
        lower_name: str = block.name.lower()
        if 'exciter' in lower_name:
            if len(block.state_eqs) >= 5:
                vf_state: Any = None
                y1_state: Any = None
                y2_state: Any = None
                y3_state: Any = None
                y4_state: Any = None
                algebraic_var: Any
                for algebraic_var in block.state_vars:
                    if algebraic_var.name == 'Vf':
                        vf_state = algebraic_var
                    else:
                        if algebraic_var.name == 'y_exciter1':
                            y1_state = algebraic_var
                        else:
                            if algebraic_var.name == 'y_exciter2':
                                y2_state = algebraic_var
                            else:
                                if algebraic_var.name == 'y_exciter3':
                                    y3_state = algebraic_var
                                else:
                                    if algebraic_var.name == 'y_exciter4':
                                        y4_state = algebraic_var
                                    else:
                                        pass

                if vf_state is None or y1_state is None or y2_state is None or y3_state is None or y4_state is None:
                    patch_applied: bool = False
                else:
                    block.state_eqs[0] = -y1_state
                    block.state_eqs[1] = -y2_state
                    block.state_eqs[2] = -y3_state
                    block.state_eqs[3] = -y4_state
                    block.state_eqs[4] = -vf_state
                    patch_applied = True
                return patch_applied
            else:
                return False
        else:
            pass
    return False


def _patch_emt_pss_to_zero_output(generator_model: Block) -> bool:
    """
    Replace EMT PSS dynamics by stable zero-output dynamics when possible.

    :param generator_model: Generator model.
    :return: True when the patch was applied.
    """
    patch_count: int = 0
    block: Block
    for block in generator_model.get_all_blocks():
        lower_name: str = block.name.lower()
        if 'stabilizer' in lower_name or 'pss' in lower_name:
            state_index: int
            for state_index in range(len(block.state_eqs)):
                state_var: Any = block.state_vars[state_index]
                block.state_eqs[state_index] = -state_var
            patch_count += 1
        else:
            pass
    return patch_count > 0


def _print_top_participation_states_for_mode(results: SmallSignalStabilityEmtResults, mode_index: int, top_count: int) -> None:
    """
    Print the top EMT participation states for one mode.

    :param results: EMT results.
    :param mode_index: Mode index.
    :param top_count: Number of states to print.
    :return: None.
    """
    pf_matrix: np.ndarray = np.asarray(results.participation_factors, dtype=float)
    state_names: np.ndarray = np.asarray(results.stat_vars_array, dtype=str)
    mode_pf: np.ndarray = pf_matrix[:, mode_index]
    order: np.ndarray = np.argsort(mode_pf)[::-1]
    display_count: int = min(top_count, int(order.size))
    display_index: int
    for display_index in range(display_count):
        state_index: int = int(order[display_index])
        print(f'    state {display_index}: {state_names[state_index]} -> {mode_pf[state_index]:.6e}')


def _read_positive_sequence_voltage_vector(pf_results: Any) -> np.ndarray:
    """
    Read the positive-sequence voltage vector.

    :param pf_results: Power-flow results.
    :return: Complex voltage vector.
    """
    voltage_field: Any = pf_results.voltage
    if voltage_field is None:
        frame: Any = pf_results.get_bus_df()
        vm: np.ndarray = np.asarray(frame['Vm'], dtype=float)
        va_rad: np.ndarray = np.deg2rad(np.asarray(frame['Va'], dtype=float))
        voltage_array: np.ndarray = vm * np.exp(1j * va_rad)
    else:
        voltage_array = np.asarray(voltage_field, dtype=complex).ravel()
    return voltage_array


def _seed_bus_guesses_from_positive_sequence(grid: gce.MultiCircuit, pf_results: Any) -> np.ndarray:
    """
    Seed bus initial guesses from the positive-sequence solution.

    :param grid: Circuit.
    :param pf_results: Power-flow results.
    :return: Voltage vector.
    """
    voltage_array: np.ndarray = _read_positive_sequence_voltage_vector(pf_results)
    if voltage_array.size != len(grid.buses):
        raise RuntimeError('Cannot seed PF3: positive-sequence voltage vector size does not match buses.')
    else:
        bus: gce.Bus
        value: complex
        for bus, value in zip(grid.buses, voltage_array):
            bus.Vm0 = float(abs(value))
            bus.Va0 = float(np.angle(value))
    return voltage_array


def _read_pf3_voltage_a_vector(pf3_results: Any) -> np.ndarray | None:
    """
    Read the PF3 phase-A voltage vector.

    :param pf3_results: PF3 results.
    :return: Phase-A vector or None.
    """
    voltage_a_field: Any = pf3_results.voltage_A
    if voltage_a_field is None:
        voltage_a: np.ndarray | None = None
    else:
        voltage_a = np.asarray(voltage_a_field, dtype=complex).ravel()
    return voltage_a


def _seed_bus_guesses_from_pf3(grid: gce.MultiCircuit, pf3_results: Any) -> bool:
    """
    Seed buses from a PF3 solution.

    :param grid: Circuit.
    :param pf3_results: PF3 results.
    :return: True when seeding succeeded.
    """
    voltage_array: np.ndarray | None = _read_pf3_voltage_a_vector(pf3_results)
    if voltage_array is None:
        seed_ok: bool = False
    else:
        if voltage_array.size != len(grid.buses):
            seed_ok = False
        else:
            magnitudes: np.ndarray = np.abs(voltage_array)
            finite: np.ndarray = np.isfinite(voltage_array.real) & np.isfinite(voltage_array.imag)
            plausible: np.ndarray = (magnitudes > 0.2) & (magnitudes < 2.0)
            if np.all(finite & plausible):
                bus: gce.Bus
                value: complex
                for bus, value in zip(grid.buses, voltage_array):
                    bus.Vm0 = float(abs(value))
                    bus.Va0 = float(np.angle(value))
                seed_ok = True
            else:
                seed_ok = False
    return seed_ok


def _set_scaled_static_loading(load1: gce.Load, load2: gce.Load, gen1: gce.Generator, gen2: gce.Generator, gen3: gce.Generator, gen4: gce.Generator, scale: float) -> None:
    """
    Scale the static PF3 operating point.

    :param load1: First load.
    :param load2: Second load.
    :param gen1: First generator.
    :param gen2: Second generator.
    :param gen3: Third generator.
    :param gen4: Fourth generator.
    :param scale: Scaling factor.
    :return: None.
    """
    load1.P = scale * 967.0
    load1.Q = scale * 100.0
    load1.P1 = load1.P / 3.0
    load1.P2 = load1.P / 3.0
    load1.P3 = load1.P / 3.0
    load1.Q1 = load1.Q / 3.0
    load1.Q2 = load1.Q / 3.0
    load1.Q3 = load1.Q / 3.0
    load2.P = scale * 1767.0
    load2.Q = scale * 100.0
    load2.P1 = load2.P / 3.0
    load2.P2 = load2.P / 3.0
    load2.P3 = load2.P / 3.0
    load2.Q1 = load2.Q / 3.0
    load2.Q2 = load2.Q / 3.0
    load2.Q3 = load2.Q / 3.0
    gen1.P = scale * 700.0
    gen2.P = scale * 700.0
    gen3.P = scale * 719.091
    gen4.P = scale * 700.0


def _seed_interpolated_loading_guess(grid: gce.MultiCircuit, full_voltage: np.ndarray, scale: float) -> None:
    """
    Seed PF3 continuation using interpolation from flat start.

    :param grid: Circuit.
    :param full_voltage: Solved voltage vector.
    :param scale: Load scale.
    :return: None.
    """
    bus: gce.Bus
    target: complex
    for bus, target in zip(grid.buses, full_voltage):
        target_vm: float = float(abs(target))
        target_va: float = float(np.angle(target))
        bus.Vm0 = 1.0 + scale * (target_vm - 1.0)
        bus.Va0 = scale * target_va


def _run_pf3_with_continuation(grid: gce.MultiCircuit, load1: gce.Load, load2: gce.Load, gen1: gce.Generator, gen2: gce.Generator, gen3: gce.Generator, gen4: gce.Generator, pf_options: PowerFlowOptions, full_voltage: np.ndarray) -> Any:
    """
    Run PF3 continuation if the direct solve fails.

    :param grid: Circuit.
    :param load1: First load.
    :param load2: Second load.
    :param gen1: First generator.
    :param gen2: Second generator.
    :param gen3: Third generator.
    :param gen4: Fourth generator.
    :param pf_options: PF options.
    :param full_voltage: Positive-sequence voltage vector.
    :return: PF3 results.
    """
    last_converged_scale: float = 0.0
    trial_scale: float = 0.10
    step: float = 0.10
    min_step: float = 0.0125
    last_results: Any = None
    current_results: Any = None

    try:
        _set_scaled_static_loading(load1, load2, gen1, gen2, gen3, gen4, scale=0.0)
        bus: gce.Bus
        for bus in grid.buses:
            bus.Vm0 = 1.0
            bus.Va0 = 0.0

        while last_converged_scale < 1.0 - 1e-12:
            trial_scale = min(1.0, trial_scale)
            _set_scaled_static_loading(load1, load2, gen1, gen2, gen3, gen4, scale=trial_scale)
            if last_results is None:
                _seed_interpolated_loading_guess(grid, full_voltage, scale=trial_scale)
            else:
                pass

            power_flow_3ph: PowerFlowDriver3Ph = PowerFlowDriver3Ph(grid, pf_options)
            power_flow_3ph.run()
            current_results = power_flow_3ph.results
            if bool(current_results.converged):
                last_results = current_results
                last_converged_scale = trial_scale
                _seed_bus_guesses_from_pf3(grid, current_results)
                if last_converged_scale >= 1.0 - 1e-12:
                    break
                else:
                    trial_scale = min(1.0, last_converged_scale + step)
            else:
                step *= 0.5
                if step < min_step:
                    break
                else:
                    trial_scale = last_converged_scale + step
    finally:
        _set_scaled_static_loading(load1, load2, gen1, gen2, gen3, gen4, scale=1.0)

    if last_results is None:
        if current_results is None:
            raise RuntimeError('PF3 continuation did not execute any attempt.')
        else:
            final_results: Any = current_results
    else:
        final_results = last_results
    return final_results


def _print_eigenvalue_summary(label: str, eigenvalues: np.ndarray, period: float | None = None) -> None:
    """
    Print a compact eigenvalue summary.

    :param label: Label.
    :param eigenvalues: Eigenvalues.
    :param period: Period for Floquet magnitude.
    :return: None.
    """
    eig: np.ndarray = np.asarray(eigenvalues, dtype=complex).ravel()
    valid: np.ndarray = np.isfinite(eig.real) & np.isfinite(eig.imag)
    eig = eig[valid]
    if eig.size == 0:
        print(f'\n{label}: no finite eigenvalues.')
    else:
        order: np.ndarray = np.argsort(eig.real)[::-1]
        eig = eig[order]
        print(f'\n=== {label} eigenvalue summary ===')
        header: str = ' idx       Re[1/s]       Im[rad/s]       f[Hz]       zeta       tau[s]'
        if period is None:
            pass
        else:
            header += '       |mu|'
        print(header)
        idx: int
        value: complex
        for idx, value in enumerate(eig[:20]):
            magnitude: float = abs(value)
            frequency_hz: float = abs(value.imag) / (2.0 * np.pi)
            zeta: float = -value.real / magnitude if magnitude > 1e-14 else np.nan
            tau: float = 1.0 / abs(value.real) if abs(value.real) > 1e-12 else np.inf
            row: str = f'{idx:4d}  {value.real:13.6e}  {value.imag:13.6e}  {frequency_hz:10.6f}  {zeta:9.5f}  {tau:11.4g}'
            if period is None:
                pass
            else:
                row += f'  {np.exp(value.real * period):11.8f}'
            print(row)


def _print_floquet_multiplier_summary(results: SmallSignalStabilityEmtResults) -> None:
    """
    Print Floquet-multiplier diagnostics.

    :param results: EMT results.
    :return: None.
    """
    multipliers: np.ndarray = np.asarray(results.multipliers, dtype=complex).ravel()
    valid: np.ndarray = np.isfinite(multipliers.real) & np.isfinite(multipliers.imag)
    mu: np.ndarray = multipliers[valid]
    if mu.size == 0:
        print('Floquet multiplier array contains no finite values.')
    else:
        abs_mu: np.ndarray = np.abs(mu)
        print('\n=== Floquet multiplier diagnostics ===')
        print(f'finite multipliers: {mu.size}')
        print(f'max |mu|: {abs_mu.max():.10f}')
        print(f'min |mu|: {abs_mu.min():.10f}')


def _print_pf_vs_pf3_consistency(res: Any, res_3ph: Any) -> None:
    """
    Print consistency metrics between PF and PF3 operating points.

    :param res: Positive-sequence PF results.
    :param res_3ph: Three-phase PF results.
    :return: None.
    """
    pf_voltage: np.ndarray = np.asarray(res.voltage, dtype=complex).ravel()
    pf3_voltage_a: np.ndarray = np.asarray(res_3ph.voltage_A, dtype=complex).ravel()
    pf3_voltage_b: np.ndarray = np.asarray(res_3ph.voltage_B, dtype=complex).ravel()
    pf3_voltage_c: np.ndarray = np.asarray(res_3ph.voltage_C, dtype=complex).ravel()
    vm_pf: np.ndarray = np.abs(pf_voltage)
    va_pf: np.ndarray = np.angle(pf_voltage)
    vm_pf3_a: np.ndarray = np.abs(pf3_voltage_a)
    va_pf3_a: np.ndarray = np.angle(pf3_voltage_a)
    vm_error: np.ndarray = vm_pf3_a - vm_pf
    va_error: np.ndarray = va_pf3_a - va_pf
    va_error = (va_error + np.pi) % (2.0 * np.pi) - np.pi

    max_negative_sequence_ratio: float = 0.0
    max_zero_sequence_ratio: float = 0.0
    bus_index: int
    for bus_index in range(len(pf3_voltage_a)):
        abc: np.ndarray = np.array([pf3_voltage_a[bus_index], pf3_voltage_b[bus_index], pf3_voltage_c[bus_index]], dtype=complex)
        seq: np.ndarray = T_ABC_TO_012 @ abc
        positive_magnitude: float = max(abs(seq[1]), 1e-12)
        negative_ratio: float = abs(seq[2]) / positive_magnitude
        zero_ratio: float = abs(seq[0]) / positive_magnitude
        max_negative_sequence_ratio = max(max_negative_sequence_ratio, negative_ratio)
        max_zero_sequence_ratio = max(max_zero_sequence_ratio, zero_ratio)

    print('\n=== PF vs PF3 consistency ===')
    print(f'max |Vm_A - Vm_pos| = {float(np.max(np.abs(vm_error))):.6e} pu')
    print(f'max |Va_A - Va_pos| = {float(np.max(np.abs(va_error))):.6e} rad')
    print(f'max negative-sequence voltage ratio = {max_negative_sequence_ratio:.6e}')
    print(f'max zero-sequence voltage ratio = {max_zero_sequence_ratio:.6e}')


def _print_selected_emt_modes_near_rms(rms_eigenvalues: np.ndarray, emt_results: SmallSignalStabilityEmtResults) -> None:
    """
    Print EMT modes close to the RMS oscillatory frequencies.

    :param rms_eigenvalues: RMS eigenvalues.
    :param emt_results: EMT results.
    :return: None.
    """
    rms_values: np.ndarray = np.asarray(rms_eigenvalues, dtype=complex).ravel()
    emt_values: np.ndarray = np.asarray(emt_results.eigenvalues, dtype=complex).ravel()
    emt_multipliers: np.ndarray = np.asarray(emt_results.multipliers, dtype=complex).ravel()
    emt_pf: np.ndarray = np.asarray(emt_results.participation_factors, dtype=float)
    emt_state_names: np.ndarray = np.asarray(emt_results.stat_vars_array, dtype=str)
    rms_freqs_hz: np.ndarray = np.abs(rms_values.imag) / (2.0 * np.pi)
    target_freqs_hz: list[float] = list()

    freq_value: float
    for freq_value in rms_freqs_hz:
        if freq_value > 1e-9:
            if any(abs(freq_value - existing) < 1e-6 for existing in target_freqs_hz):
                pass
            else:
                target_freqs_hz.append(float(freq_value))
        else:
            pass

    print('\n=== EMT modes near RMS oscillatory frequencies ===')
    target_freq_hz: float
    for target_freq_hz in target_freqs_hz:
        emt_freqs_hz: np.ndarray = np.abs(emt_values.imag) / (2.0 * np.pi)
        distance: np.ndarray = np.abs(emt_freqs_hz - target_freq_hz)
        candidate_indices: np.ndarray = np.where(distance <= EMT_MODE_FREQUENCY_TOLERANCE_HZ)[0]
        if candidate_indices.size == 0:
            print(f'target {target_freq_hz:.6f} Hz: no EMT mode within +/- {EMT_MODE_FREQUENCY_TOLERANCE_HZ:.3f} Hz')
        else:
            ordered: np.ndarray = candidate_indices[np.argsort(distance[candidate_indices])]
            best_index: int = int(ordered[0])
            dominant_state_index: int = int(np.argmax(emt_pf[:, best_index]))
            dominant_state_name: str = str(emt_state_names[dominant_state_index])
            print(f'target {target_freq_hz:.6f} Hz: mode {best_index} -> Re={emt_values[best_index].real:.6e}, Im={emt_values[best_index].imag:.6e}, f={emt_freqs_hz[best_index]:.6f} Hz, |mu|={abs(emt_multipliers[best_index]):.8f}, dominant state={dominant_state_name}')
            _print_top_participation_states_for_mode(emt_results, best_index, top_count=5)


def _print_emt_low_frequency_modes(emt_results: SmallSignalStabilityEmtResults) -> None:
    """
    Print low-frequency EMT mode candidates.

    :param emt_results: EMT results.
    :return: None.
    """
    emt_values: np.ndarray = np.asarray(emt_results.eigenvalues, dtype=complex).ravel()
    emt_multipliers: np.ndarray = np.asarray(emt_results.multipliers, dtype=complex).ravel()
    emt_pf: np.ndarray = np.asarray(emt_results.participation_factors, dtype=float)
    emt_state_names: np.ndarray = np.asarray(emt_results.stat_vars_array, dtype=str)
    valid: np.ndarray = np.isfinite(emt_values.real) & np.isfinite(emt_values.imag)
    emt_values = emt_values[valid]
    emt_multipliers = emt_multipliers[valid]
    freqs_hz: np.ndarray = np.abs(emt_values.imag) / (2.0 * np.pi)
    low_frequency_indices: np.ndarray = np.where(freqs_hz <= 3.0)[0]

    print('\n=== EMT low-frequency mode candidates ===')
    if low_frequency_indices.size == 0:
        print('no EMT modes below 3 Hz')
    else:
        ordering_metric: np.ndarray = np.argsort(emt_values.real[low_frequency_indices])[::-1]
        ordered_indices: np.ndarray = low_frequency_indices[ordering_metric]
        display_count: int = min(12, int(ordered_indices.size))
        display_index: int
        for display_index in range(display_count):
            mode_index: int = int(ordered_indices[display_index])
            dominant_state_index: int = int(np.argmax(emt_pf[:, mode_index]))
            dominant_state_name: str = str(emt_state_names[dominant_state_index])
            print(f'mode {mode_index}: Re={emt_values[mode_index].real:.6e}, Im={emt_values[mode_index].imag:.6e}, f={freqs_hz[mode_index]:.6f} Hz, |mu|={abs(emt_multipliers[mode_index]):.8f}, dominant state={dominant_state_name}')
            _print_top_participation_states_for_mode(emt_results, mode_index, top_count=5)


def _get_emt_electromechanical_scores(emt_results: SmallSignalStabilityEmtResults) -> np.ndarray:
    """
    Compute one electromechanical participation score per EMT mode.

    :param emt_results: EMT results.
    :return: Electromechanical score vector.
    """
    pf_matrix: np.ndarray = np.asarray(emt_results.participation_factors, dtype=float)
    state_names: np.ndarray = np.asarray(emt_results.stat_vars_array, dtype=str)
    state_mask: np.ndarray = np.zeros(len(state_names), dtype=bool)
    state_index: int
    for state_index in range(len(state_names)):
        state_name: str = str(state_names[state_index])
        if any(state_name.startswith(prefix) for prefix in EMT_ELECTROMECHANICAL_STATE_PREFIXES):
            state_mask[state_index] = True
        else:
            pass
    if np.any(state_mask):
        scores: np.ndarray = np.sum(pf_matrix[state_mask, :], axis=0)
    else:
        scores = np.zeros(pf_matrix.shape[1], dtype=float)
    return scores


def _print_emt_electromechanical_modes(emt_results: SmallSignalStabilityEmtResults) -> None:
    """
    Print EMT modes ranked by electromechanical participation.

    :param emt_results: EMT results.
    :return: None.
    """
    emt_values: np.ndarray = np.asarray(emt_results.eigenvalues, dtype=complex).ravel()
    emt_multipliers: np.ndarray = np.asarray(emt_results.multipliers, dtype=complex).ravel()
    emt_scores: np.ndarray = _get_emt_electromechanical_scores(emt_results)
    emt_state_names: np.ndarray = np.asarray(emt_results.stat_vars_array, dtype=str)
    valid: np.ndarray = np.isfinite(emt_values.real) & np.isfinite(emt_values.imag)
    candidate_indices: np.ndarray = np.where(valid)[0]
    ordering: np.ndarray = candidate_indices[np.argsort(emt_scores[candidate_indices])[::-1]]
    display_count: int = min(16, int(ordering.size))

    print('\n=== EMT electromechanical mode candidates ===')
    display_index: int
    for display_index in range(display_count):
        mode_index: int = int(ordering[display_index])
        dominant_state_index: int = int(np.argmax(np.asarray(emt_results.participation_factors, dtype=float)[:, mode_index]))
        dominant_state_name: str = str(emt_state_names[dominant_state_index])
        frequency_hz: float = float(abs(emt_values[mode_index].imag) / (2.0 * np.pi))
        print(f'mode {mode_index}: score={emt_scores[mode_index]:.6e}, Re={emt_values[mode_index].real:.6e}, Im={emt_values[mode_index].imag:.6e}, f={frequency_hz:.6f} Hz, |mu|={abs(emt_multipliers[mode_index]):.8f}, dominant state={dominant_state_name}')
        _print_top_participation_states_for_mode(emt_results, mode_index, top_count=5)


def kundur_small_signal_rms_vs_emt() -> None:
    """
    Run the Kundur RMS versus EMT small-signal comparison.

    :return: None.
    """
    ###########################################################################################################################
    # Build VeraGrid object
    ###########################################################################################################################

    grid: gce.MultiCircuit = gce.MultiCircuit(name='Kundur small-signal RMS vs EMT', Sbase=GRID_SBASE_MVA, fbase=KUNDUR_FBASE_HZ)

    # Buses
    bus1: gce.Bus = gce.Bus(name='Bus1', Vnom=20)
    bus2: gce.Bus = gce.Bus(name='Bus2', Vnom=20)
    bus3: gce.Bus = gce.Bus(name='Bus3', Vnom=20, is_slack=True)
    bus4: gce.Bus = gce.Bus(name='Bus4', Vnom=20)
    bus5: gce.Bus = gce.Bus(name='Bus5', Vnom=230)
    bus6: gce.Bus = gce.Bus(name='Bus6', Vnom=230)
    bus7: gce.Bus = gce.Bus(name='Bus7', Vnom=230)
    bus8: gce.Bus = gce.Bus(name='Bus8', Vnom=230)
    bus9: gce.Bus = gce.Bus(name='Bus9', Vnom=230)
    bus10: gce.Bus = gce.Bus(name='Bus10', Vnom=230)
    bus11: gce.Bus = gce.Bus(name='Bus11', Vnom=230)

    grid.add_bus(bus1)
    grid.add_bus(bus2)
    grid.add_bus(bus3)
    grid.add_bus(bus4)
    grid.add_bus(bus5)
    grid.add_bus(bus6)
    grid.add_bus(bus7)
    grid.add_bus(bus8)
    grid.add_bus(bus9)
    grid.add_bus(bus10)
    grid.add_bus(bus11)

    bus: gce.Bus
    for bus in grid.buses:
        initialize_bus_rms(bus, vf=grid.var_factory)
        get_bus_emt_template(grid, bus)

    # Line
    kundur_tower: gce.OverheadLineType
    kundur_wire: gce.Wire
    kundur_tower, kundur_wire = _build_kundur_230kv_tower(grid)
    grid.add_wire(kundur_wire)
    grid.add_overhead_line(kundur_tower)

    line0: gce.Line = _make_kundur_line(grid, kundur_tower, 'line 5-6-1', bus5, bus6, 0.00500, 0.05000, 0.02187, 750.0, 50.0)
    line1: gce.Line = _make_kundur_line(grid, kundur_tower, 'line 5-6-2', bus5, bus6, 0.00500, 0.05000, 0.02187, 750.0, 50.0)
    line2: gce.Line = _make_kundur_line(grid, kundur_tower, 'line 6-7-1', bus6, bus7, 0.00300, 0.03000, 0.00583, 700.0, 30.0)
    line3: gce.Line = _make_kundur_line(grid, kundur_tower, 'line 6-7-2', bus6, bus7, 0.00300, 0.03000, 0.00583, 700.0, 30.0)
    line4: gce.Line = _make_kundur_line(grid, kundur_tower, 'line 6-7-3', bus6, bus7, 0.00300, 0.03000, 0.00583, 700.0, 30.0)
    line5: gce.Line = _make_kundur_line(grid, kundur_tower, 'line 7-8-1', bus7, bus8, 0.01100, 0.11000, 0.19250, 400.0, 110.0)
    line6: gce.Line = _make_kundur_line(grid, kundur_tower, 'line 7-8-2', bus7, bus8, 0.01100, 0.11000, 0.19250, 400.0, 110.0)
    line7: gce.Line = _make_kundur_line(grid, kundur_tower, 'line 8-9-1', bus8, bus9, 0.01100, 0.11000, 0.19250, 400.0, 110.0)
    line8: gce.Line = _make_kundur_line(grid, kundur_tower, 'line 8-9-2', bus8, bus9, 0.01100, 0.11000, 0.19250, 400.0, 110.0)
    line9: gce.Line = _make_kundur_line(grid, kundur_tower, 'line 9-10-1', bus9, bus10, 0.00300, 0.03000, 0.00583, 700.0, 30.0)
    line10: gce.Line = _make_kundur_line(grid, kundur_tower, 'line 9-10-2', bus9, bus10, 0.00300, 0.03000, 0.00583, 700.0, 30.0)
    line11: gce.Line = _make_kundur_line(grid, kundur_tower, 'line 9-10-3', bus9, bus10, 0.00300, 0.03000, 0.00583, 700.0, 30.0)
    line12: gce.Line = _make_kundur_line(grid, kundur_tower, 'line 10-11-1', bus10, bus11, 0.00500, 0.05000, 0.02187, 750.0, 50.0)
    line13: gce.Line = _make_kundur_line(grid, kundur_tower, 'line 10-11-2', bus10, bus11, 0.00500, 0.05000, 0.02187, 750.0, 50.0)
    transmission_lines: list[gce.Line] = [line0, line1, line2, line3, line4, line5, line6, line7, line8, line9, line10, line11, line12, line13]
    _validate_kundur_line_positive_sequence(transmission_lines)

    # Transformers
    trafo_G1: gce.Transformer2W = _make_kundur_transformer('trafo 5-1', bus5, bus1)
    trafo_G2: gce.Transformer2W = _make_kundur_transformer('trafo 6-2', bus6, bus2)
    trafo_G3: gce.Transformer2W = _make_kundur_transformer('trafo 11-3', bus11, bus3)
    trafo_G4: gce.Transformer2W = _make_kundur_transformer('trafo 10-4', bus10, bus4)

    # load
    load1: gce.Load = gce.Load(name='load1', P=967.0, Q=100.0, P1=967.0 / 3.0, P2=967.0 / 3.0, P3=967.0 / 3.0, Q1=100.0 / 3.0, Q2=100.0 / 3.0, Q3=100.0 / 3.0)
    load2: gce.Load = gce.Load(name='load2', P=1767.0, Q=100.0, P1=1767.0 / 3.0, P2=1767.0 / 3.0, P3=1767.0 / 3.0, Q1=100.0 / 3.0, Q2=100.0 / 3.0, Q3=100.0 / 3.0)
    load1.conn = ShuntConnectionType.GroundedStar
    load2.conn = ShuntConnectionType.GroundedStar

    # Generators
    fn_1: float = 60.0
    M_1: float = KUNDUR_RMS_M[0]
    D_1: float = 0.0
    ra_1: float = KUNDUR_RA_SYS_PU
    xd_1: float = KUNDUR_XD_SYS_PU
    omega_ref_1: float = 1.0
    Kp_1: float = 0.0
    Ki_1: float = 0.0

    fn_2: float = 60.0
    M_2: float = KUNDUR_RMS_M[1]
    D_2: float = 0.0
    ra_2: float = KUNDUR_RA_SYS_PU
    xd_2: float = KUNDUR_XD_SYS_PU
    omega_ref_2: float = 1.0
    Kp_2: float = 0.0
    Ki_2: float = 0.0

    fn_3: float = 60.0
    M_3: float = KUNDUR_RMS_M[2]
    D_3: float = 0.0
    ra_3: float = KUNDUR_RA_SYS_PU
    xd_3: float = KUNDUR_XD_SYS_PU
    omega_ref_3: float = 1.0
    Kp_3: float = 0.0
    Ki_3: float = 0.0

    fn_4: float = 60.0
    M_4: float = KUNDUR_RMS_M[3]
    D_4: float = 0.0
    ra_4: float = KUNDUR_RA_SYS_PU
    xd_4: float = KUNDUR_XD_SYS_PU
    omega_ref_4: float = 1.0
    Kp_4: float = 0.0
    Ki_4: float = 0.0

    # Generators
    gen1: gce.Generator = gce.Generator(name='Gen1', P=700.0, vset=1.03, Snom=900.0, x1=xd_1, r1=ra_1, freq=fn_1)
    gen2: gce.Generator = gce.Generator(name='Gen2', P=700.0, vset=1.01, Snom=900.0, x1=xd_2, r1=ra_2, freq=fn_2)
    gen3: gce.Generator = gce.Generator(name='Gen3', P=719.091, vset=1.03, Snom=900.0, x1=xd_3, r1=ra_3, freq=fn_3)
    gen4: gce.Generator = gce.Generator(name='Gen4', P=700.0, vset=1.01, Snom=900.0, x1=xd_4, r1=ra_4, freq=fn_4)
    gen1.R0 = KUNDUR_RA_SYS_PU
    gen1.X0 = KUNDUR_XDPP_SYS_PU
    gen1.R2 = KUNDUR_RA_SYS_PU
    gen1.X2 = KUNDUR_XDPP_SYS_PU
    gen2.R0 = KUNDUR_RA_SYS_PU
    gen2.X0 = KUNDUR_XDPP_SYS_PU
    gen2.R2 = KUNDUR_RA_SYS_PU
    gen2.X2 = KUNDUR_XDPP_SYS_PU
    gen3.R0 = KUNDUR_RA_SYS_PU
    gen3.X0 = KUNDUR_XDPP_SYS_PU
    gen3.R2 = KUNDUR_RA_SYS_PU
    gen3.X2 = KUNDUR_XDPP_SYS_PU
    gen4.R0 = KUNDUR_RA_SYS_PU
    gen4.X0 = KUNDUR_XDPP_SYS_PU
    gen4.R2 = KUNDUR_RA_SYS_PU
    gen4.X2 = KUNDUR_XDPP_SYS_PU

    ######################################################################################################
    # Build RMS and EMT models
    ######################################################################################################

    # Build rms models from template
    # generators
    genrow_mdl1: Block = get_genrow1_rms_template(grid.var_factory).block
    genrow_mdl2: Block = get_genrow2_rms_template(grid.var_factory).block
    genrow_mdl3: Block = get_genrow3_rms_template(grid.var_factory).block
    genrow_mdl4: Block = get_genrow4_rms_template(grid.var_factory).block

    # lines
    line0_mdl: Block = get_line_rms_template(grid.var_factory).block
    line1_mdl: Block = get_line_rms_template(grid.var_factory).block
    line2_mdl: Block = get_line_rms_template(grid.var_factory).block
    line3_mdl: Block = get_line_rms_template(grid.var_factory).block
    line4_mdl: Block = get_line_rms_template(grid.var_factory).block
    line5_mdl: Block = get_line_rms_template(grid.var_factory).block
    line6_mdl: Block = get_line_rms_template(grid.var_factory).block
    line7_mdl: Block = get_line_rms_template(grid.var_factory).block
    line8_mdl: Block = get_line_rms_template(grid.var_factory).block
    line9_mdl: Block = get_line_rms_template(grid.var_factory).block
    line10_mdl: Block = get_line_rms_template(grid.var_factory).block
    line11_mdl: Block = get_line_rms_template(grid.var_factory).block
    line12_mdl: Block = get_line_rms_template(grid.var_factory).block
    line13_mdl: Block = get_line_rms_template(grid.var_factory).block

    # trafos
    trafo1_mdl: Block = get_transformer2w_rms(grid.var_factory).block
    trafo2_mdl: Block = get_transformer2w_rms(grid.var_factory).block
    trafo3_mdl: Block = get_transformer2w_rms(grid.var_factory).block
    trafo4_mdl: Block = get_transformer2w_rms(grid.var_factory).block

    # loads
    load1_mdl: Block = get_load_rms_template(grid.var_factory).block
    load2_mdl: Block = get_load_rms_template(grid.var_factory).block

    # emt generators
    gen1_emt_mdl: Block = get_floquet_generator_template_emt(vf=grid.var_factory, name='Gen1_emt').block
    gen2_emt_mdl: Block = get_floquet_generator_template_emt(vf=grid.var_factory, name='Gen2_emt').block
    gen3_emt_mdl: Block = get_floquet_generator_template_emt(vf=grid.var_factory, name='Gen3_emt').block
    gen4_emt_mdl: Block = get_floquet_generator_template_emt(vf=grid.var_factory, name='Gen4_emt').block

    # emt lines
    line0_emt_mdl: Block = get_pi_line_emt_template(vf=grid.var_factory, phN=False, phA=True, phB=True, phC=True, name='Pi_kundur_line_0').block
    line1_emt_mdl: Block = get_pi_line_emt_template(vf=grid.var_factory, phN=False, phA=True, phB=True, phC=True, name='Pi_kundur_line_1').block
    line2_emt_mdl: Block = get_pi_line_emt_template(vf=grid.var_factory, phN=False, phA=True, phB=True, phC=True, name='Pi_kundur_line_2').block
    line3_emt_mdl: Block = get_pi_line_emt_template(vf=grid.var_factory, phN=False, phA=True, phB=True, phC=True, name='Pi_kundur_line_3').block
    line4_emt_mdl: Block = get_pi_line_emt_template(vf=grid.var_factory, phN=False, phA=True, phB=True, phC=True, name='Pi_kundur_line_4').block
    line5_emt_mdl: Block = get_pi_line_emt_template(vf=grid.var_factory, phN=False, phA=True, phB=True, phC=True, name='Pi_kundur_line_5').block
    line6_emt_mdl: Block = get_pi_line_emt_template(vf=grid.var_factory, phN=False, phA=True, phB=True, phC=True, name='Pi_kundur_line_6').block
    line7_emt_mdl: Block = get_pi_line_emt_template(vf=grid.var_factory, phN=False, phA=True, phB=True, phC=True, name='Pi_kundur_line_7').block
    line8_emt_mdl: Block = get_pi_line_emt_template(vf=grid.var_factory, phN=False, phA=True, phB=True, phC=True, name='Pi_kundur_line_8').block
    line9_emt_mdl: Block = get_pi_line_emt_template(vf=grid.var_factory, phN=False, phA=True, phB=True, phC=True, name='Pi_kundur_line_9').block
    line10_emt_mdl: Block = get_pi_line_emt_template(vf=grid.var_factory, phN=False, phA=True, phB=True, phC=True, name='Pi_kundur_line_10').block
    line11_emt_mdl: Block = get_pi_line_emt_template(vf=grid.var_factory, phN=False, phA=True, phB=True, phC=True, name='Pi_kundur_line_11').block
    line12_emt_mdl: Block = get_pi_line_emt_template(vf=grid.var_factory, phN=False, phA=True, phB=True, phC=True, name='Pi_kundur_line_12').block
    line13_emt_mdl: Block = get_pi_line_emt_template(vf=grid.var_factory, phN=False, phA=True, phB=True, phC=True, name='Pi_kundur_line_13').block

    # emt trafos
    trafo1_emt_mdl: Block = get_transformer_emt_template(vf=grid.var_factory, conn_f=WindingType.FloatingStar, conn_t=WindingType.FloatingStar, name='Kundur_transformer_0_emt').block
    trafo2_emt_mdl: Block = get_transformer_emt_template(vf=grid.var_factory, conn_f=WindingType.FloatingStar, conn_t=WindingType.FloatingStar, name='Kundur_transformer_1_emt').block
    trafo3_emt_mdl: Block = get_transformer_emt_template(vf=grid.var_factory, conn_f=WindingType.FloatingStar, conn_t=WindingType.FloatingStar, name='Kundur_transformer_2_emt').block
    trafo4_emt_mdl: Block = get_transformer_emt_template(vf=grid.var_factory, conn_f=WindingType.FloatingStar, conn_t=WindingType.FloatingStar, name='Kundur_transformer_3_emt').block

    # emt loads
    load1_emt_mdl: Block = get_shunt_rlc_combo_emt_template(vf=grid.var_factory, include_r=True, include_l=True, include_c=False, phA=True, phB=True, phC=True, connection_type=ShuntConnectionType.FloatingStar, name='load1_RL_emt').block
    load2_emt_mdl: Block = get_shunt_rlc_combo_emt_template(vf=grid.var_factory, include_r=True, include_l=True, include_c=False, phA=True, phB=True, phC=True, connection_type=ShuntConnectionType.FloatingStar, name='load2_RL_emt').block

    # set models parameters
    load1_mdl.set_parameter_in_model(var_name='Pl0', new_value=-9.670000000007317)
    load1_mdl.set_parameter_in_model(var_name='Ql0', new_value=-0.9999999999967969)
    load2_mdl.set_parameter_in_model(var_name='Pl0', new_value=-17.6699999999199)
    load2_mdl.set_parameter_in_model(var_name='Ql0', new_value=-0.999999999989467)

    emt_params_1: dict[str, float] = dict()
    emt_params_1['xq_Gen1_emt_gen'] = 1.70
    emt_params_1['xdp_Gen1_emt_gen'] = 0.30
    emt_params_1['xqp_Gen1_emt_gen'] = 0.55
    emt_params_1['xdpp_Gen1_emt_gen'] = 0.25
    emt_params_1['xqpp_Gen1_emt_gen'] = 0.25
    emt_params_1['xl_Gen1_emt_gen'] = 0.20
    emt_params_1['x0_Gen1_emt_gen'] = 0.14
    emt_params_1['Td0p_Gen1_emt_gen'] = KUNDUR_TD0P_S
    emt_params_1['Tq0p_Gen1_emt_gen'] = KUNDUR_TQ0P_S
    emt_params_1['Td0pp_Gen1_emt_gen'] = KUNDUR_TD0PP_S
    emt_params_1['Tq0pp_Gen1_emt_gen'] = KUNDUR_TQ0PP_S
    emt_params_1['H_Gen1_emt_gen'] = 6.5
    emt_params_1['D_Gen1_emt_gen'] = 0.0
    emt_params_1['omega_s_Gen1_emt_gen'] = 1.0
    _set_model_parameters(gen1_emt_mdl, emt_params_1, 'EMT Gen1')

    emt_params_2: dict[str, float] = dict()
    emt_params_2['xq_Gen2_emt_gen'] = 1.70
    emt_params_2['xdp_Gen2_emt_gen'] = 0.30
    emt_params_2['xqp_Gen2_emt_gen'] = 0.55
    emt_params_2['xdpp_Gen2_emt_gen'] = 0.25
    emt_params_2['xqpp_Gen2_emt_gen'] = 0.25
    emt_params_2['xl_Gen2_emt_gen'] = 0.20
    emt_params_2['x0_Gen2_emt_gen'] = 0.14
    emt_params_2['Td0p_Gen2_emt_gen'] = KUNDUR_TD0P_S
    emt_params_2['Tq0p_Gen2_emt_gen'] = KUNDUR_TQ0P_S
    emt_params_2['Td0pp_Gen2_emt_gen'] = KUNDUR_TD0PP_S
    emt_params_2['Tq0pp_Gen2_emt_gen'] = KUNDUR_TQ0PP_S
    emt_params_2['H_Gen2_emt_gen'] = 6.5
    emt_params_2['D_Gen2_emt_gen'] = 0.0
    emt_params_2['omega_s_Gen2_emt_gen'] = 1.0
    _set_model_parameters(gen2_emt_mdl, emt_params_2, 'EMT Gen2')

    emt_params_3: dict[str, float] = dict()
    emt_params_3['xq_Gen3_emt_gen'] = 1.70
    emt_params_3['xdp_Gen3_emt_gen'] = 0.30
    emt_params_3['xqp_Gen3_emt_gen'] = 0.55
    emt_params_3['xdpp_Gen3_emt_gen'] = 0.25
    emt_params_3['xqpp_Gen3_emt_gen'] = 0.25
    emt_params_3['xl_Gen3_emt_gen'] = 0.20
    emt_params_3['x0_Gen3_emt_gen'] = 0.14
    emt_params_3['Td0p_Gen3_emt_gen'] = KUNDUR_TD0P_S
    emt_params_3['Tq0p_Gen3_emt_gen'] = KUNDUR_TQ0P_S
    emt_params_3['Td0pp_Gen3_emt_gen'] = KUNDUR_TD0PP_S
    emt_params_3['Tq0pp_Gen3_emt_gen'] = KUNDUR_TQ0PP_S
    emt_params_3['H_Gen3_emt_gen'] = 6.175
    emt_params_3['D_Gen3_emt_gen'] = 0.0
    emt_params_3['omega_s_Gen3_emt_gen'] = 1.0
    _set_model_parameters(gen3_emt_mdl, emt_params_3, 'EMT Gen3')

    emt_params_4: dict[str, float] = dict()
    emt_params_4['xq_Gen4_emt_gen'] = 1.70
    emt_params_4['xdp_Gen4_emt_gen'] = 0.30
    emt_params_4['xqp_Gen4_emt_gen'] = 0.55
    emt_params_4['xdpp_Gen4_emt_gen'] = 0.25
    emt_params_4['xqpp_Gen4_emt_gen'] = 0.25
    emt_params_4['xl_Gen4_emt_gen'] = 0.20
    emt_params_4['x0_Gen4_emt_gen'] = 0.14
    emt_params_4['Td0p_Gen4_emt_gen'] = KUNDUR_TD0P_S
    emt_params_4['Tq0p_Gen4_emt_gen'] = KUNDUR_TQ0P_S
    emt_params_4['Td0pp_Gen4_emt_gen'] = KUNDUR_TD0PP_S
    emt_params_4['Tq0pp_Gen4_emt_gen'] = KUNDUR_TQ0PP_S
    emt_params_4['H_Gen4_emt_gen'] = 6.175
    emt_params_4['D_Gen4_emt_gen'] = 0.0
    emt_params_4['omega_s_Gen4_emt_gen'] = 1.0
    _set_model_parameters(gen4_emt_mdl, emt_params_4, 'EMT Gen4')

    grid.add_line(line0)
    grid.add_line(line1)
    grid.add_line(line2)
    grid.add_line(line3)
    grid.add_line(line4)
    grid.add_line(line5)
    grid.add_line(line6)
    grid.add_line(line7)
    grid.add_line(line8)
    grid.add_line(line9)
    grid.add_line(line10)
    grid.add_line(line11)
    grid.add_line(line12)
    grid.add_line(line13)

    grid.add_transformer2w(trafo_G1)
    grid.add_transformer2w(trafo_G2)
    grid.add_transformer2w(trafo_G3)
    grid.add_transformer2w(trafo_G4)

    grid.add_load(bus=bus7, api_obj=load1)
    grid.add_load(bus=bus9, api_obj=load2)

    grid.add_generator(bus=bus1, api_obj=gen1)
    grid.add_generator(bus=bus2, api_obj=gen2)
    grid.add_generator(bus=bus3, api_obj=gen3)
    grid.add_generator(bus=bus4, api_obj=gen4)

    # add models to opi objects
    set_rms_model(device=gen1, model=genrow_mdl1, var_factory=grid.var_factory)
    set_rms_model(device=gen2, model=genrow_mdl2, var_factory=grid.var_factory)
    set_rms_model(device=gen3, model=genrow_mdl3, var_factory=grid.var_factory)
    set_rms_model(device=gen4, model=genrow_mdl4, var_factory=grid.var_factory)
    set_rms_model(device=line0, model=line0_mdl, var_factory=grid.var_factory)
    set_rms_model(device=line1, model=line1_mdl, var_factory=grid.var_factory)
    set_rms_model(device=line2, model=line2_mdl, var_factory=grid.var_factory)
    set_rms_model(device=line3, model=line3_mdl, var_factory=grid.var_factory)
    set_rms_model(device=line4, model=line4_mdl, var_factory=grid.var_factory)
    set_rms_model(device=line5, model=line5_mdl, var_factory=grid.var_factory)
    set_rms_model(device=line6, model=line6_mdl, var_factory=grid.var_factory)
    set_rms_model(device=line7, model=line7_mdl, var_factory=grid.var_factory)
    set_rms_model(device=line8, model=line8_mdl, var_factory=grid.var_factory)
    set_rms_model(device=line9, model=line9_mdl, var_factory=grid.var_factory)
    set_rms_model(device=line10, model=line10_mdl, var_factory=grid.var_factory)
    set_rms_model(device=line11, model=line11_mdl, var_factory=grid.var_factory)
    set_rms_model(device=line12, model=line12_mdl, var_factory=grid.var_factory)
    set_rms_model(device=line13, model=line13_mdl, var_factory=grid.var_factory)
    set_rms_model(device=trafo_G1, model=trafo1_mdl, var_factory=grid.var_factory)
    set_rms_model(device=trafo_G2, model=trafo2_mdl, var_factory=grid.var_factory)
    set_rms_model(device=trafo_G3, model=trafo3_mdl, var_factory=grid.var_factory)
    set_rms_model(device=trafo_G4, model=trafo4_mdl, var_factory=grid.var_factory)
    set_rms_model(device=load1, model=load1_mdl, var_factory=grid.var_factory)
    set_rms_model(device=load2, model=load2_mdl, var_factory=grid.var_factory)

    set_emt_model(device=gen1, model=gen1_emt_mdl, var_factory=grid.var_factory)
    set_emt_model(device=gen2, model=gen2_emt_mdl, var_factory=grid.var_factory)
    set_emt_model(device=gen3, model=gen3_emt_mdl, var_factory=grid.var_factory)
    set_emt_model(device=gen4, model=gen4_emt_mdl, var_factory=grid.var_factory)
    set_emt_model(device=line0, model=line0_emt_mdl, var_factory=grid.var_factory)
    set_emt_model(device=line1, model=line1_emt_mdl, var_factory=grid.var_factory)
    set_emt_model(device=line2, model=line2_emt_mdl, var_factory=grid.var_factory)
    set_emt_model(device=line3, model=line3_emt_mdl, var_factory=grid.var_factory)
    set_emt_model(device=line4, model=line4_emt_mdl, var_factory=grid.var_factory)
    set_emt_model(device=line5, model=line5_emt_mdl, var_factory=grid.var_factory)
    set_emt_model(device=line6, model=line6_emt_mdl, var_factory=grid.var_factory)
    set_emt_model(device=line7, model=line7_emt_mdl, var_factory=grid.var_factory)
    set_emt_model(device=line8, model=line8_emt_mdl, var_factory=grid.var_factory)
    set_emt_model(device=line9, model=line9_emt_mdl, var_factory=grid.var_factory)
    set_emt_model(device=line10, model=line10_emt_mdl, var_factory=grid.var_factory)
    set_emt_model(device=line11, model=line11_emt_mdl, var_factory=grid.var_factory)
    set_emt_model(device=line12, model=line12_emt_mdl, var_factory=grid.var_factory)
    set_emt_model(device=line13, model=line13_emt_mdl, var_factory=grid.var_factory)
    set_emt_model(device=trafo_G1, model=trafo1_emt_mdl, var_factory=grid.var_factory)
    set_emt_model(device=trafo_G2, model=trafo2_emt_mdl, var_factory=grid.var_factory)
    set_emt_model(device=trafo_G3, model=trafo3_emt_mdl, var_factory=grid.var_factory)
    set_emt_model(device=trafo_G4, model=trafo4_emt_mdl, var_factory=grid.var_factory)
    load1.conn = ShuntConnectionType.FloatingStar
    load2.conn = ShuntConnectionType.FloatingStar
    set_emt_model(device=load1, model=load1_emt_mdl, var_factory=grid.var_factory)
    set_emt_model(device=load2, model=load2_emt_mdl, var_factory=grid.var_factory)

    pf_options: PowerFlowOptions = PowerFlowOptions(solver_type=gce.SolverType.NR, retry_with_other_methods=False, verbose=0, initialize_with_existing_solution=True, tolerance=1e-8, max_iter=50, control_q=False, control_taps_modules=True, control_taps_phase=True, control_remote_voltage=True, orthogonalize_controls=True, apply_temperature_correction=True, branch_impedance_tolerance_mode=gce.BranchImpedanceMode.Specified, distributed_slack=False, ignore_single_node_islands=False, trust_radius=1.0, backtracking_parameter=0.05, use_stored_guess=False, initialize_angles=False, generate_report=False)
    load1.conn = ShuntConnectionType.GroundedStar
    load2.conn = ShuntConnectionType.GroundedStar

    power_flow: PowerFlowDriver = PowerFlowDriver(grid, pf_options)
    power_flow.run()
    res: Any = power_flow.results
    if bool(res.converged):
        pass
    else:
        raise RuntimeError('Positive-sequence Kundur power flow did not converge.')

    full_voltage: np.ndarray = _seed_bus_guesses_from_positive_sequence(grid, res)
    power_flow_3ph: PowerFlowDriver3Ph = PowerFlowDriver3Ph(grid, pf_options)
    power_flow_3ph.run()
    res_3ph: Any = power_flow_3ph.results
    if bool(res_3ph.converged):
        pass
    else:
        res_3ph = _run_pf3_with_continuation(grid, load1, load2, gen1, gen2, gen3, gen4, pf_options, full_voltage)
    if bool(res_3ph.converged):
        pass
    else:
        raise RuntimeError('Three-phase Kundur power flow did not converge.')

    _print_pf_vs_pf3_consistency(res, res_3ph)

    rms_options: RmsOptions = RmsOptions(time_step=0.001, simulation_time=1.0, tolerance=1e-7, integration_method=DynamicIntegrationMethod.DaeBackEuler, initialization_method=RmsInitializationMethod.Explicit, use_init_values=False, max_iter=1000, verbose=0)
    sss_options: RmsSmallSignalStabilityOptions = RmsSmallSignalStabilityOptions(k=0, ss_assessment_time=0.0, verbose=1)
    emt_options: EmtOptions = EmtOptions(time_step=EMT_TIME_STEP_S, simulation_time=EMT_SIMULATION_TIME_S, tolerance=1e-6, solver_type=EmtSolverTypes.Automatic, integration_method=DynamicIntegrationMethod.DaeTrapezoidal, verbose=1)
    floquet_options: SmallSignalStabilityEmtOptions = SmallSignalStabilityEmtOptions(k=200, target_period=KUNDUR_PERIOD_S, ss_assessment_time=FLOQUET_ASSESSMENT_TIME_S, build_type=SmallSignalEmtBuildTypes.Arnoldi, verbose=1)

    small_signal_driver: SmallSignalStabilityRmsDriver = SmallSignalStabilityRmsDriver(grid=grid, rms_options=rms_options, sss_options=sss_options, pf_results=res)
    floquet_driver: SmallSignalStabilityEmtDriver = SmallSignalStabilityEmtDriver(grid=grid, pf_results=res_3ph, emt_options=emt_options, sss_options=floquet_options)

    print('\nRunning RMS small-signal analysis...')
    small_signal_driver.run()
    rms_eigenvalues: np.ndarray = np.asarray(small_signal_driver.results.eigenvalues, dtype=complex)
    rms_pfactors: np.ndarray = np.asarray(small_signal_driver.results.participation_factors, dtype=float)
    _print_eigenvalue_summary('RMS', rms_eigenvalues)

    print('\nRunning EMT/Floquet small-signal analysis...')
    floquet_driver.run()
    emt_eigenvalues: np.ndarray = np.asarray(floquet_driver.results.eigenvalues, dtype=complex)
    emt_pfactors: np.ndarray = np.asarray(floquet_driver.results.participation_factors, dtype=float)
    _print_eigenvalue_summary('EMT/Floquet', emt_eigenvalues, period=KUNDUR_PERIOD_S)
    _print_floquet_multiplier_summary(floquet_driver.results)
    _print_selected_emt_modes_near_rms(rms_eigenvalues, floquet_driver.results)
    _print_emt_low_frequency_modes(floquet_driver.results)
    _print_emt_electromechanical_modes(floquet_driver.results)

    plot_s_domain_eigenvalues(rms_eigenvalues, emt_eigenvalues)
    plot_participation_factors(rms_pfactors, 'RMS participation factors')
    plot_participation_factors(emt_pfactors, 'EMT/Floquet participation factors')
    plt.show(block=False)


if __name__ == '__main__':
    kundur_small_signal_rms_vs_emt()
