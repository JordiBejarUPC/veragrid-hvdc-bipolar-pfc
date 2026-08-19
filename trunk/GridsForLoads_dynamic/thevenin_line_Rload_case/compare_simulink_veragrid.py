from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt


class ComparisonSignal:
    """Store one pair of physically equivalent comparison signals.

    The Simulink values are already converted to the VeraGrid sign convention.
    Keeping both column descriptions in the object makes the generated summary
    auditable without relying on the plotting code.

    :param group_name: Identifier of the output plot group.
    :param name: Human-readable signal name.
    :param unit: Unit displayed on the vertical axis.
    :param simulink_reference: Simulink column or derived expression.
    :param veragrid_reference: VeraGrid column or derived expression.
    :param simulink_multiplier: Sign applied to the raw Simulink signal.
    :param simulink_values: Simulink values in the VeraGrid convention.
    :param veragrid_values: VeraGrid values interpolated to the common time.
    :param phase_offset_deg: Simulink-minus-VeraGrid phase offset at 50 Hz.
    """

    __slots__ = (
        "_group_name",
        "_name",
        "_unit",
        "_simulink_reference",
        "_veragrid_reference",
        "_simulink_multiplier",
        "_simulink_values",
        "_veragrid_values",
        "_phase_offset_deg",
    )

    def __init__(self,
                 group_name: str,
                 name: str,
                 unit: str,
                 simulink_reference: str,
                 veragrid_reference: str,
                 simulink_multiplier: float,
                 simulink_values: np.ndarray,
                 veragrid_values: np.ndarray,
                 phase_offset_deg: float) -> None:
        """Initialize one aligned comparison signal.

        :param group_name: Identifier of the output plot group.
        :param name: Human-readable signal name.
        :param unit: Unit displayed on the vertical axis.
        :param simulink_reference: Simulink column or derived expression.
        :param veragrid_reference: VeraGrid column or derived expression.
        :param simulink_multiplier: Sign applied to the raw Simulink signal.
        :param simulink_values: Simulink values in the VeraGrid convention.
        :param veragrid_values: VeraGrid values on the common time base.
        :param phase_offset_deg: Simulink-minus-VeraGrid phase offset at 50 Hz.
        :return: None.
        """
        self._group_name: str = group_name
        self._name: str = name
        self._unit: str = unit
        self._simulink_reference: str = simulink_reference
        self._veragrid_reference: str = veragrid_reference
        self._simulink_multiplier: float = simulink_multiplier
        self._simulink_values: np.ndarray = simulink_values
        self._veragrid_values: np.ndarray = veragrid_values
        self._phase_offset_deg: float = phase_offset_deg

    def get_group_name(self) -> str:
        """Return the output plot group identifier.

        :return: Plot group identifier.
        """
        return self._group_name

    def get_name(self) -> str:
        """Return the human-readable signal name.

        :return: Signal name.
        """
        return self._name

    def get_unit(self) -> str:
        """Return the signal unit.

        :return: Vertical-axis unit.
        """
        return self._unit

    def get_simulink_reference(self) -> str:
        """Return the Simulink column or expression description.

        :return: Simulink signal reference.
        """
        return self._simulink_reference

    def get_veragrid_reference(self) -> str:
        """Return the VeraGrid column or expression description.

        :return: VeraGrid signal reference.
        """
        return self._veragrid_reference

    def get_simulink_multiplier(self) -> float:
        """Return the sign applied to the raw Simulink values.

        :return: Simulink polarity multiplier.
        """
        return self._simulink_multiplier

    def get_simulink_values(self) -> np.ndarray:
        """Return Simulink values in the VeraGrid convention.

        :return: Aligned Simulink values.
        """
        return self._simulink_values

    def get_veragrid_values(self) -> np.ndarray:
        """Return VeraGrid values on the common time base.

        :return: Interpolated VeraGrid values.
        """
        return self._veragrid_values

    def get_phase_offset_deg(self) -> float:
        """Return the 50 Hz Simulink-minus-VeraGrid phase offset.

        :return: Phase offset in degrees, or NaN for non-periodic signals.
        """
        return self._phase_offset_deg


def validate_columns(frame: pd.DataFrame,
                     required_columns: tuple[str, ...],
                     source_name: str) -> bool:
    """Check that one CSV contains every column required by the mapping.

    :param frame: Loaded CSV table.
    :param required_columns: Columns needed by the comparison workflow.
    :param source_name: Name printed when a required column is absent.
    :return: ``True`` when every required column is present.
    """
    valid: bool = True
    column_name: str

    # Report all missing channels together so a renamed exporter can be fixed
    # in one pass rather than failing repeatedly on the first missing column.
    for column_name in required_columns:
        if column_name in frame.columns:
            pass
        else:
            print("Missing column in " + source_name + ": " + column_name)
            valid = False

    return valid


def interpolate_column(frame: pd.DataFrame,
                       source_time: np.ndarray,
                       target_time: np.ndarray,
                       column_name: str) -> np.ndarray:
    """Interpolate one numeric CSV column to the common comparison time.

    :param frame: Source CSV table.
    :param source_time: Time vector associated with ``frame``.
    :param target_time: Common comparison time vector.
    :param column_name: Numeric column to interpolate.
    :return: Column values evaluated on ``target_time``.
    """
    source_values: np.ndarray = frame[column_name].to_numpy(dtype=float)
    interpolated_values: np.ndarray = np.interp(target_time, source_time, source_values)
    return interpolated_values


def choose_simulink_polarity(simulink_values: np.ndarray,
                             veragrid_values: np.ndarray) -> float:
    """Choose the Simulink polarity that best matches VeraGrid.

    Only ``+1`` and ``-1`` are considered because a current sensor orientation
    can reverse a waveform but must not rescale it. This automatic check is
    deliberately applied after the physical channel mapping has been defined.

    :param simulink_values: Raw Simulink signal.
    :param veragrid_values: Equivalent VeraGrid signal.
    :return: Multiplicative Simulink sign, either ``+1`` or ``-1``.
    """
    same_error: float = float(np.sqrt(np.mean((simulink_values - veragrid_values) ** 2)))
    opposite_error: float = float(np.sqrt(np.mean((-simulink_values - veragrid_values) ** 2)))

    if same_error <= opposite_error:
        return 1.0
    else:
        return -1.0


def calculate_phase_offset_deg(time_s: np.ndarray,
                               simulink_values: np.ndarray,
                               veragrid_values: np.ndarray) -> float:
    """Calculate the 50 Hz phasor offset over the final 100 ms.

    :param time_s: Common comparison time in seconds.
    :param simulink_values: Sign-corrected Simulink waveform.
    :param veragrid_values: VeraGrid waveform.
    :return: Simulink-minus-VeraGrid phase offset in degrees.
    """
    window_start_s: float = max(float(time_s[0]), float(time_s[-1]) - 0.1)
    window_mask: np.ndarray = time_s >= window_start_s
    window_time_s: np.ndarray = time_s[window_mask]
    angular_kernel: np.ndarray = np.exp(-1j * 2.0 * np.pi * 50.0 * window_time_s)
    simulink_phasor: complex = complex(np.sum(simulink_values[window_mask] * angular_kernel))
    veragrid_phasor: complex = complex(np.sum(veragrid_values[window_mask] * angular_kernel))
    minimum_magnitude: float = 1.0e-12

    if abs(simulink_phasor) > minimum_magnitude and abs(veragrid_phasor) > minimum_magnitude:
        phase_offset_deg: float = float(np.angle(simulink_phasor / veragrid_phasor, deg=True))
        return phase_offset_deg
    else:
        return float("nan")


def calculate_instantaneous_reactive_power(voltage_abc: np.ndarray,
                                           current_abc: np.ndarray) -> np.ndarray:
    """Calculate three-phase instantaneous reactive power.

    The expression matches the VeraGrid generator convention for balanced
    three-wire quantities. Currents must already follow the positive injection
    convention before this function is called.

    :param voltage_abc: Phase voltages with columns A, B and C.
    :param current_abc: Phase currents with columns A, B and C.
    :return: Instantaneous reactive power in per unit.
    """
    reactive_power: np.ndarray = (
        (voltage_abc[:, 1] - voltage_abc[:, 2]) * current_abc[:, 0]
        + (voltage_abc[:, 2] - voltage_abc[:, 0]) * current_abc[:, 1]
        + (voltage_abc[:, 0] - voltage_abc[:, 1]) * current_abc[:, 2]
    ) / np.sqrt(3.0)
    return reactive_power


def build_direct_signal(group_name: str,
                        signal_name: str,
                        unit: str,
                        simulink_frame: pd.DataFrame,
                        veragrid_frame: pd.DataFrame,
                        simulink_time: np.ndarray,
                        veragrid_time: np.ndarray,
                        common_time: np.ndarray,
                        simulink_column: str,
                        veragrid_column: str,
                        calculate_phase: bool) -> ComparisonSignal:
    """Build one direct column-to-column comparison with sign detection.

    :param group_name: Identifier of the output plot group.
    :param signal_name: Human-readable signal name.
    :param unit: Signal unit.
    :param simulink_frame: Loaded Simulink CSV.
    :param veragrid_frame: Loaded VeraGrid CSV.
    :param simulink_time: Original Simulink time vector.
    :param veragrid_time: Original VeraGrid time vector.
    :param common_time: Shared time vector used for comparison.
    :param simulink_column: Direct Simulink column name.
    :param veragrid_column: Equivalent VeraGrid column name.
    :param calculate_phase: Whether to calculate a 50 Hz phase offset.
    :return: Fully aligned comparison signal.
    """
    simulink_raw: np.ndarray = np.interp(
        common_time,
        simulink_time,
        simulink_frame[simulink_column].to_numpy(dtype=float),
    )
    veragrid_values: np.ndarray = interpolate_column(
        veragrid_frame,
        veragrid_time,
        common_time,
        veragrid_column,
    )
    simulink_multiplier: float = choose_simulink_polarity(simulink_raw, veragrid_values)
    simulink_values: np.ndarray = simulink_multiplier * simulink_raw

    if calculate_phase:
        phase_offset_deg: float = calculate_phase_offset_deg(
            common_time,
            simulink_values,
            veragrid_values,
        )
    else:
        phase_offset_deg = float("nan")

    signal: ComparisonSignal = ComparisonSignal(
        group_name=group_name,
        name=signal_name,
        unit=unit,
        simulink_reference=simulink_column,
        veragrid_reference=veragrid_column,
        simulink_multiplier=simulink_multiplier,
        simulink_values=simulink_values,
        veragrid_values=veragrid_values,
        phase_offset_deg=phase_offset_deg,
    )
    return signal


def build_derived_signal(group_name: str,
                         signal_name: str,
                         unit: str,
                         simulink_reference: str,
                         veragrid_reference: str,
                         common_time: np.ndarray,
                         simulink_values: np.ndarray,
                         veragrid_values: np.ndarray,
                         calculate_phase: bool) -> ComparisonSignal:
    """Build one comparison from explicitly derived values.

    :param group_name: Identifier of the output plot group.
    :param signal_name: Human-readable signal name.
    :param unit: Signal unit.
    :param simulink_reference: Description of the Simulink expression.
    :param veragrid_reference: Description of the VeraGrid expression.
    :param common_time: Shared comparison time vector.
    :param simulink_values: Derived Simulink values in the target convention.
    :param veragrid_values: Derived VeraGrid values in the target convention.
    :param calculate_phase: Whether to calculate a 50 Hz phase offset.
    :return: Fully described comparison signal.
    """
    if calculate_phase:
        phase_offset_deg: float = calculate_phase_offset_deg(
            common_time,
            simulink_values,
            veragrid_values,
        )
    else:
        phase_offset_deg = float("nan")

    signal: ComparisonSignal = ComparisonSignal(
        group_name=group_name,
        name=signal_name,
        unit=unit,
        simulink_reference=simulink_reference,
        veragrid_reference=veragrid_reference,
        simulink_multiplier=1.0,
        simulink_values=simulink_values,
        veragrid_values=veragrid_values,
        phase_offset_deg=phase_offset_deg,
    )
    return signal


def create_comparison_signals(simulink_frame: pd.DataFrame,
                              veragrid_frame: pd.DataFrame,
                              simulink_time: np.ndarray,
                              veragrid_time: np.ndarray,
                              common_time: np.ndarray) -> list[ComparisonSignal]:
    """Map all available equivalent variables and construct derived channels.

    Simulink ``bus0`` is the VeraGrid sending bus ``Bus 1`` and Simulink
    ``bus1`` is the VeraGrid receiving bus ``Bus 0``. The source-side Simulink
    current sensor is reversed relative to the VeraGrid generator injection;
    direct current polarity is nevertheless verified numerically.

    :param simulink_frame: Loaded Simulink CSV.
    :param veragrid_frame: Loaded VeraGrid CSV.
    :param simulink_time: Original Simulink time vector.
    :param veragrid_time: Original VeraGrid time vector.
    :param common_time: Shared comparison time vector.
    :return: All direct and derived comparison signals.
    """
    signals: list[ComparisonSignal] = list()
    phase_names: tuple[str, ...] = ("A", "B", "C")
    simulink_phase_suffixes: tuple[str, ...] = ("a", "b", "c")
    veragrid_phase_names: tuple[str, ...] = ("A", "B", "C")
    phase_index: int

    # Bus numbers are reversed between the two exported models, so the mapping
    # follows the physical sending and receiving locations rather than labels.
    for phase_index in range(3):
        phase_name: str = phase_names[phase_index]
        simulink_suffix: str = simulink_phase_suffixes[phase_index]
        veragrid_phase: str = veragrid_phase_names[phase_index]
        signals.append(build_direct_signal(
            "01_sending_bus_voltages",
            "Sending-bus voltage phase " + phase_name,
            "p.u.",
            simulink_frame,
            veragrid_frame,
            simulink_time,
            veragrid_time,
            common_time,
            "Vac_bus0_" + simulink_suffix + "_pu",
            "v_" + veragrid_phase + "_Bus 1_pu",
            True,
        ))
        signals.append(build_direct_signal(
            "02_source_currents",
            "Source current phase " + phase_name,
            "p.u.",
            simulink_frame,
            veragrid_frame,
            simulink_time,
            veragrid_time,
            common_time,
            "Iac_bus0_" + simulink_suffix + "_pu",
            "i_" + veragrid_phase + "_gen@Bus 1_pu",
            True,
        ))
        signals.append(build_direct_signal(
            "03_receiving_bus_voltages",
            "Receiving-bus voltage phase " + phase_name,
            "p.u.",
            simulink_frame,
            veragrid_frame,
            simulink_time,
            veragrid_time,
            common_time,
            "Vac_bus1_" + simulink_suffix + "_pu",
            "v_" + veragrid_phase + "_Bus 0_pu",
            True,
        ))
        signals.append(build_direct_signal(
            "04_load_currents",
            "Load injection current phase " + phase_name,
            "p.u.",
            simulink_frame,
            veragrid_frame,
            simulink_time,
            veragrid_time,
            common_time,
            "Iac_bus1_" + simulink_suffix + "_pu",
            "i_" + veragrid_phase + "_Load@Bus 0_pu",
            True,
        ))

    # Reconstruct the controlled three-phase Thevenin voltage from the exported
    # Simulink magnitude and phase signals for comparison with VeraGrid e_abc.
    simulink_magnitude: np.ndarray = interpolate_column(
        simulink_frame,
        simulink_time,
        common_time,
        "Vac_grid_pu",
    )
    veragrid_theta: np.ndarray = interpolate_column(
        veragrid_frame,
        veragrid_time,
        common_time,
        "theta_gen@Bus 1_pu",
    )
    phase_offsets_pu: tuple[float, ...] = (0.0, -1.0 / 3.0, 1.0 / 3.0)

    for phase_index in range(3):
        phase_name = phase_names[phase_index]
        simulink_suffix = simulink_phase_suffixes[phase_index]
        veragrid_phase = veragrid_phase_names[phase_index]
        simulink_phase: np.ndarray = interpolate_column(
            simulink_frame,
            simulink_time,
            common_time,
            "phase_" + simulink_suffix + "_pu",
        )
        simulink_internal_voltage: np.ndarray = simulink_magnitude * np.sin(
            2.0 * np.pi * simulink_phase
        )
        veragrid_internal_voltage: np.ndarray = interpolate_column(
            veragrid_frame,
            veragrid_time,
            common_time,
            "e_" + veragrid_phase + "_gen@Bus 1_pu",
        )
        signals.append(build_derived_signal(
            "05_internal_source_voltages",
            "Internal source voltage phase " + phase_name,
            "p.u.",
            "Vac_grid_pu*sin(2*pi*phase_" + simulink_suffix + "_pu)",
            "e_" + veragrid_phase + "_gen@Bus 1_pu",
            common_time,
            simulink_internal_voltage,
            veragrid_internal_voltage,
            True,
        ))
        signals.append(build_derived_signal(
            "06_source_angle_and_frequency",
            "Source phase " + phase_name,
            "revolutions",
            "phase_" + simulink_suffix + "_pu",
            "theta_gen@Bus 1_pu + phase offset",
            common_time,
            simulink_phase,
            veragrid_theta + phase_offsets_pu[phase_index],
            False,
        ))

    # The exported VeraGrid angle is in electrical revolutions. Its derivative
    # divided by 50 Hz therefore gives the frequency directly in per unit.
    veragrid_frequency_pu: np.ndarray = np.gradient(veragrid_theta, common_time) / 50.0
    simulink_frequency_pu: np.ndarray = interpolate_column(
        simulink_frame,
        simulink_time,
        common_time,
        "omega_grid_pu",
    )
    signals.append(build_derived_signal(
        "06_source_angle_and_frequency",
        "Source frequency",
        "p.u.",
        "omega_grid_pu",
        "gradient(theta_gen@Bus 1_pu)/50",
        common_time,
        simulink_frequency_pu,
        veragrid_frequency_pu,
        False,
    ))

    # Active powers use the VeraGrid injection convention. Generator injection
    # is positive, load injection is negative, and their sum is network loss.
    sim_sending_voltage: np.ndarray = np.column_stack(tuple(
        interpolate_column(
            simulink_frame,
            simulink_time,
            common_time,
            "Vac_bus0_" + simulink_suffix + "_pu",
        )
        for simulink_suffix in simulink_phase_suffixes
    ))
    sim_source_current_sensor: np.ndarray = np.column_stack(tuple(
        interpolate_column(
            simulink_frame,
            simulink_time,
            common_time,
            "Iac_bus0_" + simulink_suffix + "_pu",
        )
        for simulink_suffix in simulink_phase_suffixes
    ))
    sim_receiving_voltage: np.ndarray = np.column_stack(tuple(
        interpolate_column(
            simulink_frame,
            simulink_time,
            common_time,
            "Vac_bus1_" + simulink_suffix + "_pu",
        )
        for simulink_suffix in simulink_phase_suffixes
    ))
    sim_load_injection_current: np.ndarray = np.column_stack(tuple(
        interpolate_column(
            simulink_frame,
            simulink_time,
            common_time,
            "Iac_bus1_" + simulink_suffix + "_pu",
        )
        for simulink_suffix in simulink_phase_suffixes
    ))
    vg_receiving_voltage: np.ndarray = np.column_stack(tuple(
        interpolate_column(
            veragrid_frame,
            veragrid_time,
            common_time,
            "v_" + veragrid_phase + "_Bus 0_pu",
        )
        for veragrid_phase in veragrid_phase_names
    ))
    vg_load_injection_current: np.ndarray = np.column_stack(tuple(
        interpolate_column(
            veragrid_frame,
            veragrid_time,
            common_time,
            "i_" + veragrid_phase + "_Load@Bus 0_pu",
        )
        for veragrid_phase in veragrid_phase_names
    ))
    sim_generator_injection: np.ndarray = -np.sum(
        sim_sending_voltage * sim_source_current_sensor,
        axis=1,
    )
    vg_generator_injection: np.ndarray = interpolate_column(
        veragrid_frame,
        veragrid_time,
        common_time,
        "Pe_gen@Bus 1_pu",
    )
    sim_load_injection: np.ndarray = np.sum(
        sim_receiving_voltage * sim_load_injection_current,
        axis=1,
    )
    vg_load_injection: np.ndarray = np.sum(
        vg_receiving_voltage * vg_load_injection_current,
        axis=1,
    )
    sim_losses: np.ndarray = sim_generator_injection + sim_load_injection
    vg_losses: np.ndarray = vg_generator_injection + vg_load_injection
    signals.append(build_derived_signal(
        "07_active_powers",
        "Generator active-power injection",
        "p.u.",
        "-sum(Vac_bus0_abc_pu*Iac_bus0_abc_pu)",
        "Pe_gen@Bus 1_pu",
        common_time,
        sim_generator_injection,
        vg_generator_injection,
        False,
    ))
    signals.append(build_derived_signal(
        "07_active_powers",
        "Load active-power injection",
        "p.u.",
        "sum(Vac_bus1_abc_pu*Iac_bus1_abc_pu)",
        "sum(v_abc_Bus 0_pu*i_abc_Load@Bus 0_pu)",
        common_time,
        sim_load_injection,
        vg_load_injection,
        False,
    ))
    signals.append(build_derived_signal(
        "07_active_powers",
        "Network active-power losses",
        "p.u.",
        "P_generator_injection + P_load_injection",
        "P_generator_injection + P_load_injection",
        common_time,
        sim_losses,
        vg_losses,
        False,
    ))

    # The terminal currents Iac_bus0 and Iac_bus1 already represent the source
    # and load interfaces. The extra measurements below are used only for the
    # distinct internal PI-line series-current states, so terminal currents are
    # not compared a second time under another name.
    line_series_columns: tuple[str, ...] = (
        "Iac_ser_line_a_pu",
        "Iac_ser_line_b_pu",
        "Iac_ser_line_c_pu",
    )
    for phase_index in range(3):
        phase_name = phase_names[phase_index]
        veragrid_phase = veragrid_phase_names[phase_index]
        signals.append(build_direct_signal(
            "08_line_series_currents",
            "PI-line series current phase " + phase_name,
            "p.u.",
            simulink_frame,
            veragrid_frame,
            simulink_time,
            veragrid_time,
            common_time,
            line_series_columns[phase_index],
            "i_ser_" + veragrid_phase + "_Line 1_pu",
            True,
        ))

    # VeraGrid stores capacitor charge as a state, q=C*v. Reconstructing the
    # same quantity from the measured bus voltage validates those six states
    # without asking Simulink to export redundant charge signals.
    line_half_capacitance: float = 0.03 / (2.0 * 2.0 * np.pi * 50.0)
    sim_charge_from: np.ndarray = line_half_capacitance * sim_sending_voltage
    sim_charge_to: np.ndarray = line_half_capacitance * sim_receiving_voltage
    vg_charge_from: np.ndarray = np.column_stack(tuple(
        interpolate_column(
            veragrid_frame,
            veragrid_time,
            common_time,
            "q_f_" + veragrid_phase + "_Line 1_pu",
        )
        for veragrid_phase in veragrid_phase_names
    ))
    vg_charge_to: np.ndarray = np.column_stack(tuple(
        interpolate_column(
            veragrid_frame,
            veragrid_time,
            common_time,
            "q_t_" + veragrid_phase + "_Line 1_pu",
        )
        for veragrid_phase in veragrid_phase_names
    ))

    for phase_index in range(3):
        phase_name = phase_names[phase_index]
        veragrid_phase = veragrid_phase_names[phase_index]
        signals.append(build_derived_signal(
            "09_capacitor_charges",
            "Sending-end capacitor charge phase " + phase_name,
            "p.u.-equivalent charge",
            "(C_line/2)*Vac_bus0_" + simulink_phase_suffixes[phase_index] + "_pu",
            "q_f_" + veragrid_phase + "_Line 1_pu",
            common_time,
            sim_charge_from[:, phase_index],
            vg_charge_from[:, phase_index],
            True,
        ))
        signals.append(build_derived_signal(
            "09_capacitor_charges",
            "Receiving-end capacitor charge phase " + phase_name,
            "p.u.-equivalent charge",
            "(C_line/2)*Vac_bus1_" + simulink_phase_suffixes[phase_index] + "_pu",
            "q_t_" + veragrid_phase + "_Line 1_pu",
            common_time,
            sim_charge_to[:, phase_index],
            vg_charge_to[:, phase_index],
            True,
        ))

    # Direct capacitor-current measurements avoid the numerical noise that
    # would be introduced by differentiating the reconstructed capacitor charge.
    capacitor_from_columns: tuple[str, ...] = (
        "Iac_cap_from_line_a_pu",
        "Iac_cap_from_line_b_pu",
        "Iac_cap_from_line_c_pu",
    )
    capacitor_to_columns: tuple[str, ...] = (
        "Iac_cap_to_line_a_pu",
        "Iac_cap_to_line_b_pu",
        "Iac_cap_to_line_c_pu",
    )

    for phase_index in range(3):
        phase_name = phase_names[phase_index]
        veragrid_phase = veragrid_phase_names[phase_index]
        signals.append(build_direct_signal(
            "10_capacitor_currents",
            "Sending-end capacitor current phase " + phase_name,
            "p.u.",
            simulink_frame,
            veragrid_frame,
            simulink_time,
            veragrid_time,
            common_time,
            capacitor_from_columns[phase_index],
            "i_cap_f_" + veragrid_phase + "_Line 1_pu",
            True,
        ))
        signals.append(build_direct_signal(
            "10_capacitor_currents",
            "Receiving-end capacitor current phase " + phase_name,
            "p.u.",
            simulink_frame,
            veragrid_frame,
            simulink_time,
            veragrid_time,
            common_time,
            capacitor_to_columns[phase_index],
            "i_cap_t_" + veragrid_phase + "_Line 1_pu",
            True,
        ))

    # Reactive power is derived from the bus voltage and the sign-corrected
    # source injection current, using the same abc convention as VeraGrid.
    sim_source_injection_current: np.ndarray = -sim_source_current_sensor
    sim_generator_reactive_power: np.ndarray = calculate_instantaneous_reactive_power(
        sim_sending_voltage,
        sim_source_injection_current,
    )
    vg_generator_reactive_power: np.ndarray = interpolate_column(
        veragrid_frame,
        veragrid_time,
        common_time,
        "Qe_gen@Bus 1_pu",
    )
    signals.append(build_derived_signal(
        "11_generator_reactive_power",
        "Generator reactive-power injection",
        "p.u.",
        "q_abc(Vac_bus0_abc_pu,-Iac_bus0_abc_pu)",
        "Qe_gen@Bus 1_pu",
        common_time,
        sim_generator_reactive_power,
        vg_generator_reactive_power,
        False,
    ))

    return signals


def plot_signal_group(time_s: np.ndarray,
                      group_signals: list[ComparisonSignal],
                      output_path: Path) -> None:
    """Save full-duration and final-40-ms overlays for one signal group.

    :param time_s: Common comparison time in seconds.
    :param group_signals: Signals belonging to one output figure.
    :param output_path: Destination PNG path.
    :return: None.
    """
    signal_count: int = len(group_signals)
    figure: plt.Figure
    axes: np.ndarray
    figure, axes = plt.subplots(
        signal_count,
        2,
        figsize=(15.0, max(3.2 * signal_count, 5.5)),
        squeeze=False,
        sharex="col",
    )
    maximum_full_points: int = 25000
    full_stride: int = max(1, int(np.ceil(time_s.size / maximum_full_points)))
    zoom_start_s: float = max(float(time_s[0]), float(time_s[-1]) - 0.04)
    zoom_mask: np.ndarray = time_s >= zoom_start_s
    signal_index: int

    # A full trace reveals startup behaviour while the final two 50 Hz cycles
    # make amplitude and phase differences visible without manual zooming.
    for signal_index in range(signal_count):
        signal: ComparisonSignal = group_signals[signal_index]
        simulink_values: np.ndarray = signal.get_simulink_values()
        veragrid_values: np.ndarray = signal.get_veragrid_values()
        left_axis: plt.Axes = axes[signal_index, 0]
        right_axis: plt.Axes = axes[signal_index, 1]
        sign_label: str = "Simulink mapped"

        if signal.get_simulink_multiplier() < 0.0:
            sign_label = "Simulink mapped (sign reversed)"
        else:
            pass

        left_axis.plot(
            time_s[::full_stride],
            veragrid_values[::full_stride],
            color="#1f77b4",
            linewidth=1.2,
            label="VeraGrid",
        )
        left_axis.plot(
            time_s[::full_stride],
            simulink_values[::full_stride],
            color="#d62728",
            linewidth=1.0,
            linestyle="--",
            label=sign_label,
        )
        right_axis.plot(
            time_s[zoom_mask],
            veragrid_values[zoom_mask],
            color="#1f77b4",
            linewidth=1.4,
            label="VeraGrid",
        )
        right_axis.plot(
            time_s[zoom_mask],
            simulink_values[zoom_mask],
            color="#d62728",
            linewidth=1.1,
            linestyle="--",
            label=sign_label,
        )
        left_axis.set_ylabel(signal.get_name() + " [" + signal.get_unit() + "]")
        left_axis.grid(True, alpha=0.3)
        right_axis.grid(True, alpha=0.3)

        if signal_index == 0:
            left_axis.set_title("Full simulation")
            right_axis.set_title("Final 40 ms")
            left_axis.legend(loc="best")
            right_axis.legend(loc="best")
        else:
            pass

    axes[signal_count - 1, 0].set_xlabel("Time [s]")
    axes[signal_count - 1, 1].set_xlabel("Time [s]")
    figure_title: str = "Simulink vs VeraGrid - " + output_path.stem.replace("_", " ").title()
    figure.suptitle(figure_title, fontsize=16, fontweight="bold")
    figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.965))
    figure.savefig(output_path, dpi=170, bbox_inches="tight")
    plt.close(figure)


def write_summary(signals: list[ComparisonSignal], output_path: Path) -> None:
    """Write mapping, polarity and numerical error metrics to CSV.

    :param signals: Completed comparison signals.
    :param output_path: Destination summary CSV path.
    :return: None.
    """
    rows: list[tuple[str, str, str, str, str, float, int, float, float, float, float, float]] = list()
    signal: ComparisonSignal

    for signal in signals:
        simulink_values: np.ndarray = signal.get_simulink_values()
        veragrid_values: np.ndarray = signal.get_veragrid_values()
        error: np.ndarray = simulink_values - veragrid_values
        reference_rms: float = float(np.sqrt(np.mean(veragrid_values ** 2)))
        rmse: float = float(np.sqrt(np.mean(error ** 2)))

        if reference_rms > 1.0e-15:
            normalized_rmse: float = rmse / reference_rms
        else:
            normalized_rmse = float("nan")

        rows.append((
            signal.get_group_name(),
            signal.get_name(),
            signal.get_unit(),
            signal.get_simulink_reference(),
            signal.get_veragrid_reference(),
            signal.get_simulink_multiplier(),
            int(error.size),
            float(np.mean(np.abs(error))),
            rmse,
            normalized_rmse,
            float(np.max(np.abs(error))),
            signal.get_phase_offset_deg(),
        ))

    summary_columns: list[str] = list()
    summary_columns.extend((
        "plot_group",
        "signal",
        "unit",
        "simulink_reference",
        "veragrid_reference",
        "simulink_multiplier_to_veragrid",
        "points",
        "mae",
        "rmse",
        "normalized_rmse",
        "max_abs_error",
        "phase_simulink_minus_veragrid_deg",
    ))
    summary_frame: pd.DataFrame = pd.DataFrame(rows, columns=summary_columns)
    summary_frame.to_csv(output_path, index=False)


def write_unmapped_columns(simulink_frame: pd.DataFrame,
                           veragrid_frame: pd.DataFrame,
                           output_path: Path) -> None:
    """Record model-variable coverage and genuinely missing Simulink signals.

    :param simulink_frame: Loaded Simulink CSV.
    :param veragrid_frame: Loaded VeraGrid CSV.
    :param output_path: Destination text file.
    :return: None.
    """
    used_simulink_columns: set[str] = set((
        "time_s", "Vac_grid_pu", "omega_grid_pu",
        "phase_a_pu", "phase_b_pu", "phase_c_pu",
        "Vac_bus0_a_pu", "Vac_bus0_b_pu", "Vac_bus0_c_pu",
        "Iac_bus0_a_pu", "Iac_bus0_b_pu", "Iac_bus0_c_pu",
        "Iac_ser_line_a_pu", "Iac_ser_line_b_pu", "Iac_ser_line_c_pu",
        "Iac_cap_from_line_a_pu", "Iac_cap_from_line_b_pu", "Iac_cap_from_line_c_pu",
        "Vac_bus1_a_pu", "Vac_bus1_b_pu", "Vac_bus1_c_pu",
        "Iac_bus1_a_pu", "Iac_bus1_b_pu", "Iac_bus1_c_pu",
        "Iac_cap_to_line_a_pu", "Iac_cap_to_line_b_pu", "Iac_cap_to_line_c_pu",
    ))
    used_veragrid_columns: set[str] = set((
        "time_s", "theta_gen@Bus 1_pu", "Pe_gen@Bus 1_pu", "Qe_gen@Bus 1_pu",
        "e_A_gen@Bus 1_pu", "e_B_gen@Bus 1_pu", "e_C_gen@Bus 1_pu",
        "i_A_gen@Bus 1_pu", "i_B_gen@Bus 1_pu", "i_C_gen@Bus 1_pu",
        "i_A_Load@Bus 0_pu", "i_B_Load@Bus 0_pu", "i_C_Load@Bus 0_pu",
        "v_A_Bus 0_pu", "v_B_Bus 0_pu", "v_C_Bus 0_pu",
        "v_A_Bus 1_pu", "v_B_Bus 1_pu", "v_C_Bus 1_pu",
        "q_f_A_Line 1_pu", "q_f_B_Line 1_pu", "q_f_C_Line 1_pu",
        "q_t_A_Line 1_pu", "q_t_B_Line 1_pu", "q_t_C_Line 1_pu",
        "i_cap_f_A_Line 1_pu", "i_cap_f_B_Line 1_pu", "i_cap_f_C_Line 1_pu",
        "i_cap_t_A_Line 1_pu", "i_cap_t_B_Line 1_pu", "i_cap_t_C_Line 1_pu",
        "if_A_Line 1_pu", "if_B_Line 1_pu", "if_C_Line 1_pu",
        "it_A_Line 1_pu", "it_B_Line 1_pu", "it_C_Line 1_pu",
    ))
    used_veragrid_columns.update((
        "i_ser_A_Line 1_pu",
        "i_ser_B_Line 1_pu",
        "i_ser_C_Line 1_pu",
    ))

    simulink_unmapped: list[str] = sorted(set(simulink_frame.columns) - used_simulink_columns)
    veragrid_unmapped: list[str] = sorted(set(veragrid_frame.columns) - used_veragrid_columns)
    output_lines: list[str] = list()
    column_name: str

    output_lines.append("IMPORTANT VERAGRID VARIABLES STILL MISSING IN SIMULINK")
    for column_name in veragrid_unmapped:
        output_lines.append(column_name)
    output_lines.append("")
    output_lines.append("DIRECT SIMULINK CURRENT CHANNELS USED")
    output_lines.extend((
        "Iac_ser_line_abc_pu <-> i_ser_abc_Line 1_pu",
        "Iac_cap_from_line_abc_pu <-> i_cap_f_abc_Line 1_pu",
        "Iac_cap_to_line_abc_pu <-> i_cap_t_abc_Line 1_pu",
    ))
    output_lines.append("")
    output_lines.append("VERAGRID VARIABLES DERIVED FROM EXISTING SIMULINK CHANNELS")
    output_lines.extend((
        "Qe_gen@Bus 1_pu <- abc reactive power at Simulink bus0",
        "q_f_abc_Line 1_pu <- (C_line/2)*Vac_bus0_abc_pu",
        "q_t_abc_Line 1_pu <- (C_line/2)*Vac_bus1_abc_pu",
    ))
    output_lines.append("")
    output_lines.append("VERAGRID ALGEBRAIC ALIASES ALREADY COVERED")
    output_lines.extend((
        "if_abc_Line 1_pu == i_abc_gen@Bus 1_pu in this two-bus case",
        "it_abc_Line 1_pu == i_abc_Load@Bus 0_pu in this two-bus case",
    ))
    output_lines.append("")
    output_lines.append("SIMULINK COLUMNS WITHOUT A SEPARATE VERAGRID COMPARISON")
    for column_name in simulink_unmapped:
        output_lines.append(column_name)

    output_path.write_text("\n".join(output_lines) + "\n", encoding="utf-8")


def main() -> int:
    """Run the case-specific Simulink-to-VeraGrid CSV comparison.

    Both input files are expected beside this script. Plots and the numerical
    mapping summary are written to ``comparison_plots`` in the same directory.

    :return: Process exit code, zero when the comparison succeeds.
    """
    case_directory: Path = Path(__file__).resolve().parent
    simulink_path: Path = case_directory / "simulink_results_thev_line_Rload_pu.csv"
    veragrid_path: Path = case_directory / "veragrid_results_thev_line_Rload_pu.csv"
    output_directory: Path = case_directory / "comparison_plots"

    if simulink_path.is_file() and veragrid_path.is_file():
        pass
    else:
        print("Input CSV files were not found beside the comparison script.")
        return 1

    # Loading the two case files once is faster and more consistent than
    # repeating partial reads for every plot and derived power calculation.
    simulink_frame: pd.DataFrame = pd.read_csv(simulink_path)
    veragrid_frame: pd.DataFrame = pd.read_csv(veragrid_path)
    required_simulink_columns: tuple[str, ...] = (
        "time_s", "Vac_grid_pu", "omega_grid_pu",
        "phase_a_pu", "phase_b_pu", "phase_c_pu",
        "Vac_bus0_a_pu", "Vac_bus0_b_pu", "Vac_bus0_c_pu",
        "Iac_bus0_a_pu", "Iac_bus0_b_pu", "Iac_bus0_c_pu",
        "Iac_ser_line_a_pu", "Iac_ser_line_b_pu", "Iac_ser_line_c_pu",
        "Iac_cap_from_line_a_pu", "Iac_cap_from_line_b_pu", "Iac_cap_from_line_c_pu",
        "Vac_bus1_a_pu", "Vac_bus1_b_pu", "Vac_bus1_c_pu",
        "Iac_bus1_a_pu", "Iac_bus1_b_pu", "Iac_bus1_c_pu",
        "Iac_cap_to_line_a_pu", "Iac_cap_to_line_b_pu", "Iac_cap_to_line_c_pu",
    )
    required_veragrid_columns: tuple[str, ...] = (
        "time_s", "theta_gen@Bus 1_pu", "Pe_gen@Bus 1_pu", "Qe_gen@Bus 1_pu",
        "e_A_gen@Bus 1_pu", "e_B_gen@Bus 1_pu", "e_C_gen@Bus 1_pu",
        "i_A_gen@Bus 1_pu", "i_B_gen@Bus 1_pu", "i_C_gen@Bus 1_pu",
        "i_A_Load@Bus 0_pu", "i_B_Load@Bus 0_pu", "i_C_Load@Bus 0_pu",
        "v_A_Bus 0_pu", "v_B_Bus 0_pu", "v_C_Bus 0_pu",
        "v_A_Bus 1_pu", "v_B_Bus 1_pu", "v_C_Bus 1_pu",
        "q_f_A_Line 1_pu", "q_f_B_Line 1_pu", "q_f_C_Line 1_pu",
        "q_t_A_Line 1_pu", "q_t_B_Line 1_pu", "q_t_C_Line 1_pu",
        "i_cap_f_A_Line 1_pu", "i_cap_f_B_Line 1_pu", "i_cap_f_C_Line 1_pu",
        "i_cap_t_A_Line 1_pu", "i_cap_t_B_Line 1_pu", "i_cap_t_C_Line 1_pu",
    )
    valid_simulink: bool = validate_columns(
        simulink_frame,
        required_simulink_columns,
        simulink_path.name,
    )
    valid_veragrid: bool = validate_columns(
        veragrid_frame,
        required_veragrid_columns,
        veragrid_path.name,
    )

    if valid_simulink and valid_veragrid:
        pass
    else:
        return 1

    simulink_time: np.ndarray = simulink_frame["time_s"].to_numpy(dtype=float)
    veragrid_time: np.ndarray = veragrid_frame["time_s"].to_numpy(dtype=float)
    overlap_start_s: float = max(float(simulink_time[0]), float(veragrid_time[0]))
    overlap_end_s: float = min(float(simulink_time[-1]), float(veragrid_time[-1]))
    overlap_mask: np.ndarray = (simulink_time >= overlap_start_s) & (simulink_time <= overlap_end_s)
    common_time: np.ndarray = simulink_time[overlap_mask]

    if common_time.size >= 2:
        pass
    else:
        print("The two CSV files do not have a usable overlapping time interval.")
        return 1

    signals: list[ComparisonSignal] = create_comparison_signals(
        simulink_frame,
        veragrid_frame,
        simulink_time,
        veragrid_time,
        common_time,
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    group_names: list[str] = sorted(set(signal.get_group_name() for signal in signals))
    group_name: str

    for group_name in group_names:
        group_signals: list[ComparisonSignal] = list()
        signal: ComparisonSignal
        for signal in signals:
            if signal.get_group_name() == group_name:
                group_signals.append(signal)
            else:
                pass
        plot_signal_group(
            common_time,
            group_signals,
            output_directory / (group_name + ".png"),
        )

    write_summary(signals, output_directory / "comparison_summary.csv")
    write_unmapped_columns(
        simulink_frame,
        veragrid_frame,
        output_directory / "unmapped_columns.txt",
    )
    print("Comparison plots and summaries written to: " + str(output_directory))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
else:
    pass
