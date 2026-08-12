

from __future__ import annotations

import cProfile as profile
import time

import numpy as np

from matplotlib import pyplot as plt
from typing import Any
from pathlib import Path

from VeraGridEngine import SmallSignalStabilityRmsResults
from VeraGridEngine.enumerations import VarPowerFlowReferenceType, DynamicIntegrationMethod, RmsInitializationMethod

from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Branches.line import Line

from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model

from VeraGridEngine.Templates.Rms.genrow1_rms_template import get_genrow1_rms_template
from VeraGridEngine.Templates.Rms.genrow2_rms_template import get_genrow2_rms_template
from VeraGridEngine.Templates.Rms.genrow3_rms_template import get_genrow3_rms_template
from VeraGridEngine.Templates.Rms.genrow4_rms_template import get_genrow4_rms_template

from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template

from VeraGridEngine.Simulations.SmallSignalStabilityRms.small_signal_driver import SmallSignalStabilityRmsDriver
from VeraGridEngine.Simulations.SmallSignalStabilityRms.small_signal_options import RmsSmallSignalStabilityOptions

from VeraGridEngine.Utils.Symbolic import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
import VeraGridEngine.api as gce
from trunk.dynamics.small_signal.veragrid_small_signal_benchmark_timing import benchmark_veragrid_isolated_numerical_phases
from trunk.dynamics.small_signal.small_signal_benchmark_timing import elapsed_seconds
from trunk.dynamics.small_signal.small_signal_benchmark_timing import save_benchmark_timings
from VeraGridEngine.Utils.Symbolic.symbolic_io import block_deep_copy

pr = profile.Profile()
pr.disable()


def find_name_in_block(name: str, block: Block) -> Var | None:
    """Find one named symbolic variable recursively in a block hierarchy.

    :param name: Variable name to find.
    :param block: Root symbolic block.
    :return: Matching variable or ``None``.
    """
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()):
        if name == var.name:
            return var
        else:
            pass

    for mdl in block.children:
        res = find_name_in_block(name, mdl)
        if res is not None:
            return res
        else:
            pass
    return None


def plot_s_domain_eigenvalues(eigenvalues: np.ndarray) -> None:
    """
    Plot the RMS eigenvalues in the s-domain.

    :param eigenvalues: Complex eigenvalue vector.
    :return: None.
    """
    values: np.ndarray = np.asarray(eigenvalues, dtype=complex).ravel()

    if values.size == 0:
        return
    else:
        pass

    real_part: np.ndarray = values.real
    imag_part: np.ndarray = values.imag
    slope: float = 1.0 / 0.05
    x_min_ref: float = min(float(np.min(real_part)), -1e-6)
    x_z: np.ndarray = np.linspace(x_min_ref * 1.05, 0.0, 400)
    y_z: np.ndarray = slope * x_z

    plt.figure(figsize=(9, 7))
    plt.plot(x_z, y_z, '--', color='grey', label='zeta = 5%')
    plt.plot(x_z, -y_z, '--', color='grey')
    plt.scatter(real_part, imag_part, marker='x', color='blue', label='Eigenvalues')
    plt.xlabel('Re')
    plt.ylabel('Im [rad/s]')
    plt.title('RMS small-signal eigenvalues')

    real_span: float = float(np.max(real_part) - np.min(real_part))
    imag_span: float = float(np.max(imag_part) - np.min(imag_part))
    margin_x: float = 0.1 * real_span if real_span > 0.0 else 1.0
    margin_y: float = 0.1 * imag_span if imag_span > 0.0 else 1.0

    plt.xlim(float(np.min(real_part)) - margin_x, float(np.max(real_part)) + margin_x)
    plt.ylim(float(np.min(imag_part)) - margin_y, float(np.max(imag_part)) + margin_y)
    plt.axhline(0.0, color='black', linewidth=1.0)
    plt.axvline(0.0, color='black', linewidth=1.0)
    plt.legend(loc='upper left')
    plt.tight_layout()


def plot_participation_factors(participation_factors: np.ndarray) -> None:
    """
    Plot the participation-factor matrix as one heatmap.

    :param participation_factors: Participation-factor matrix.
    :return: None.
    """
    values: np.ndarray = np.asarray(participation_factors, dtype=float)

    if values.ndim != 2:
        return
    else:
        if values.size == 0:
            return
        else:
            pass

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
    plt.title('Participation factors')
    plt.tight_layout()

def _get_state_matrix_labels(results: Any) -> list[str]:
    """
    Return labels aligned with the state-matrix dimension.

    :param results: Small-signal RMS results object.
    :return: Matrix labels.
    """
    matrix = np.asarray(results.state_matrix)
    n_rows = int(matrix.shape[0])

    state_labels = list(np.asarray(results.stat_vars_array).astype(str))
    algebraic_labels = list(np.asarray(results.algebraic_vars_array).astype(str))

    if len(state_labels) == n_rows:
        return state_labels
    else:
        pass

    combined = state_labels + algebraic_labels

    if len(combined) == n_rows:
        return combined
    else:
        pass

    return [f"Variable {idx + 1}" for idx in range(n_rows)]

def _format_complex(value: complex, decimals: int = 12) -> str:
    """
    Return one complex number in a CSV-friendly representation.

    :param value: Complex value.
    :param decimals: Number of decimal places.
    :return: Formatted complex value.
    """
    val = complex(value)
    return f"{val.real:.{decimals}e}{val.imag:+.{decimals}e}j"


def _get_participation_row_labels(results: Any) -> list[str]:
    """
    Return row labels aligned with the participation-factor matrix.

    :param results: Small-signal RMS results object.
    :return: Row labels.
    """
    n_rows = int(results.participation_factors.shape[0])

    state_labels = list(np.asarray(results.stat_vars_array).astype(str))
    algebraic_labels = list(np.asarray(results.algebraic_vars_array).astype(str))

    if len(state_labels) == n_rows:
        return state_labels
    else:
        pass

    combined = state_labels + algebraic_labels

    if len(combined) == n_rows:
        return combined
    else:
        pass

    return [f"State {idx + 1}" for idx in range(n_rows)]

def save_small_signal_results_to_csv(
    results: SmallSignalStabilityRmsResults,
    pf_results: PowerFlowResults,
    output_dir: Path,
    benchmark_state_labels: list[str] | None = None,
) -> None:
    """
    Save the power-flow and RMS small-signal results to CSV files.

    Files written:
      - power_flow_buses.csv
      - power_flow_branches.csv
      - modes.csv
      - participation_factors.csv
      - state_matrix.csv

    :param results: Small-signal RMS results object.
    :param pf_results: Power-flow results object.
    :param output_dir: Destination directory.
    :param benchmark_state_labels: Optional physical labels shared with the
                                   external benchmark model.
    :return: None.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Power-flow operating point used by the linearization.
    pf_results.get_bus_df().to_csv(
        output_dir / "power_flow_buses.csv",
        index=True,
    )
    pf_results.get_branch_df().to_csv(
        output_dir / "power_flow_branches.csv",
        index=True,
    )

    eigenvalues = np.asarray(results.eigenvalues, dtype=complex).ravel()
    damping_ratios = np.asarray(results.damping_ratios, dtype=float).ravel()
    frequencies_hz = np.asarray(results.conjugate_frequencies, dtype=float).ravel()

    modes_data = np.column_stack(
        (
            np.arange(1, eigenvalues.size + 1, dtype=int),
            eigenvalues.real,
            eigenvalues.imag,
            damping_ratios,
            frequencies_hz,
        )
    )

    np.savetxt(
        output_dir / "modes.csv",
        modes_data,
        delimiter=",",
        header="mode,real_rad_per_s,imag_rad_per_s,damping_ratio,oscillation_frequency_hz",
        comments="",
        fmt=["%d", "%.12e", "%.12e", "%.12e", "%.12e"],
    )

    participation = np.asarray(results.participation_factors, dtype=float)
    if benchmark_state_labels is None:
        participation_labels: list[str] = _get_participation_row_labels(results)
    else:
        participation_labels = list(benchmark_state_labels)
        if len(participation_labels) == participation.shape[0]:
            pass
        else:
            raise ValueError(
                f"Received {len(participation_labels)} benchmark labels for "
                f"{participation.shape[0]} participation-factor rows."
            )
    mode_labels = [f"Mode {idx + 1}" for idx in range(participation.shape[1])]

    with (output_dir / "participation_factors.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as csv_file:
        csv_file.write("state," + ",".join(mode_labels) + "\n")
        for row_label, row in zip(participation_labels, participation):
            row_values = ",".join(f"{float(value):.12e}" for value in row)
            csv_file.write(f"{row_label},{row_values}\n")

    state_matrix = np.asarray(results.state_matrix)
    if benchmark_state_labels is None:
        state_matrix_labels: list[str] = _get_state_matrix_labels(results)
    else:
        state_matrix_labels = list(benchmark_state_labels)
        if len(state_matrix_labels) == state_matrix.shape[0]:
            pass
        else:
            raise ValueError(
                f"Received {len(state_matrix_labels)} benchmark labels for "
                f"a {state_matrix.shape[0]}-row state matrix."
            )

    with (output_dir / "state_matrix.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as csv_file:
        csv_file.write("equation," + ",".join(state_matrix_labels) + "\n")
        for row_idx, row in enumerate(state_matrix):
            row_label = (
                state_matrix_labels[row_idx]
                if row_idx < len(state_matrix_labels)
                else f"Equation {row_idx + 1}"
            )
            row_values = ",".join(_format_complex(value) for value in row)
            csv_file.write(f"{row_label},{row_values}\n")

    print(f"\nCSV results saved in: {output_dir.resolve()}")
    for filename in (
        "power_flow_buses.csv",
        "power_flow_branches.csv",
        "modes.csv",
        "participation_factors.csv",
        "state_matrix.csv",
    ):
        print(f"  - {filename}")

def rms_kundur_small_signal() -> None:
    """Build and run the VeraGrid Kundur RMS small-signal benchmark.

    :return: None.
    """
    total_start: float = time.perf_counter()
    model_start: float = time.perf_counter()
    timings: dict[str, float] = dict()
    ###########################################################################################################################
    # Build VeraGrid object
    ###########################################################################################################################

    grid = gce.MultiCircuit()

    # Buses
    bus1 = Bus(name="Bus1", Vnom=20)
    bus2 = Bus(name="Bus2", Vnom=20)
    bus3 = Bus(name="Bus3", Vnom=20, is_slack=True)
    bus4 = Bus(name="Bus4", Vnom=20)
    bus5 = Bus(name="Bus5", Vnom=230)
    bus6 = Bus(name="Bus6", Vnom=230)
    bus7 = Bus(name="Bus7", Vnom=230)
    bus8 = Bus(name="Bus8", Vnom=230)
    bus9 = Bus(name="Bus9", Vnom=230)
    bus10 = Bus(name="Bus10", Vnom=230)
    bus11 = Bus(name="Bus11", Vnom=230)

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

    for bus in grid.buses:
        initialize_bus_rms(bus, vf=grid.var_factory)

    # Line

    line0 = gce.Line(name="line 5-6-1", bus_from=bus5, bus_to=bus6,
                     r=0.00500, x=0.05000, b=0.02187, rate=750.0)

    line1 = gce.Line(name="line 5-6-2", bus_from=bus5, bus_to=bus6,
                     r=0.00500, x=0.05000, b=0.02187, rate=750.0)

    line2 = gce.Line(name="line 6-7-1", bus_from=bus6, bus_to=bus7,
                     r=0.00300, x=0.03000, b=0.00583, rate=700.0)

    line3 = gce.Line(name="line 6-7-2", bus_from=bus6, bus_to=bus7,
                     r=0.00300, x=0.03000, b=0.00583, rate=700.0)

    line4 = gce.Line(name="line 6-7-3", bus_from=bus6, bus_to=bus7,
                     r=0.00300, x=0.03000, b=0.00583, rate=700.0)

    line5 = gce.Line(name="line 7-8-1", bus_from=bus7, bus_to=bus8,
                     r=0.01100, x=0.11000, b=0.19250, rate=400.0)

    line6 = gce.Line(name="line 7-8-2", bus_from=bus7, bus_to=bus8,
                     r=0.01100, x=0.11000, b=0.19250, rate=400.0)

    line7 = gce.Line(name="line 8-9-1", bus_from=bus8, bus_to=bus9,
                     r=0.01100, x=0.11000, b=0.19250, rate=400.0)

    line8 = gce.Line(name="line 8-9-2", bus_from=bus8, bus_to=bus9,
                     r=0.01100, x=0.11000, b=0.19250, rate=400.0)

    line9 = gce.Line(name="line 9-10-1", bus_from=bus9, bus_to=bus10,
                     r=0.00300, x=0.03000, b=0.00583, rate=700.0)

    line10 = gce.Line(name="line 9-10-2", bus_from=bus9, bus_to=bus10,
                      r=0.00300, x=0.03000, b=0.00583, rate=700.0)

    line11 = gce.Line(name="line 9-10-3", bus_from=bus9, bus_to=bus10,
                      r=0.00300, x=0.03000, b=0.00583, rate=700.0)

    line12 = gce.Line(name="line 10-11-1", bus_from=bus10, bus_to=bus11,
                      r=0.00500, x=0.05000, b=0.02187, rate=750.0)

    line13 = gce.Line(name="line 10-11-2", bus_from=bus10, bus_to=bus11,
                      r=0.00500, x=0.05000, b=0.02187, rate=750.0)

    # Transformers
    xt1 = 0.15 * (100.0 / 900.0)
    trafo_G1 = Line(name="trafo 5-1", bus_from=bus5, bus_to=bus1,
                    r=0.00000, x=0.15 * (100.0 / 900.0), b=0.0, rate=900.0)

    trafo_G2 = gce.Line(name="trafo 6-2", bus_from=bus6, bus_to=bus2,
                        r=0.00000, x=0.15 * (100.0 / 900.0), b=0.0, rate=900.0)

    trafo_G3 = gce.Line(name="trafo 11-3", bus_from=bus11, bus_to=bus3,
                        r=0.00000, x=0.15 * (100.0 / 900.0), b=0.0, rate=900.0)

    trafo_G4 = gce.Line(name="trafo 10-4", bus_from=bus10, bus_to=bus4,
                        r=0.00000, x=0.15 * (100.0 / 900.0), b=0.0, rate=900.0)

    # load
    load1 = gce.Load(name="load1", P=967.0, Q=100.0)

    load2 = gce.Load(name="load2", P=1767.0, Q=100.0)

    # Generators
    fn_1 = 60.0
    M_1 = 13.0 * 9.0
    D_1 = 10.0 * 9.0
    ra_1 = 0.0
    xd_1 = 0.3 * 100.0 / 900.0
    omega_ref_1 = 1.0
    Kp_1 = 0.0
    Ki_1 = 0.0

    fn_2 = 60.0
    M_2 = 13.0 * 9.0
    D_2 = 10.0 * 9.0
    ra_2 = 0.0
    xd_2 = 0.3 * 100.0 / 900.0
    omega_ref_2 = 1.0
    Kp_2 = 0.0
    Ki_2 = 0.0

    fn_3 = 60.0
    M_3 = 12.35 * 9.0
    D_3 = 10.0 * 9.0
    ra_3 = 0.0
    xd_3 = 0.3 * 100.0 / 900.0
    omega_ref_3 = 1.0
    Kp_3 = 0.0
    Ki_3 = 0.0

    fn_4 = 60.0
    M_4 = 12.35 * 9.0
    D_4 = 10.0 * 9.0
    ra_4 = 0.0
    xd_4 = 0.3 * 100.0 / 900.0
    omega_ref_4 = 1.0
    Kp_4 = 0.0
    Ki_4 = 0.0

    # Generators
    gen1 = Generator(
        name="Gen1", P=700.0, vset=1.03, Snom=900.0,
        x1=xd_1, r1=ra_1, freq=fn_1,
    )

    gen2 = Generator(
        name="Gen2", P=700.0, vset=1.01, Snom=900.0,
        x1=xd_2, r1=ra_2, freq=fn_2,
    )

    gen3 = Generator(
        name="Gen3", P=719.091, vset=1.03, Snom=900.0,
        x1=xd_3, r1=ra_3, freq=fn_3,
    )

    gen4 = Generator(
        name="Gen4", P=700.0, vset=1.01, Snom=900.0,
        x1=xd_4, r1=ra_4, freq=fn_4,
    )

    ######################################################################################################
    # Build Rms models
    ######################################################################################################

    # Build rms models from template
    # generators
    genrow_mdl1 = get_genrow1_rms_template(grid.var_factory).block
    genrow_mdl2 = get_genrow2_rms_template(grid.var_factory).block
    genrow_mdl3 = get_genrow3_rms_template(grid.var_factory).block
    genrow_mdl4 = get_genrow4_rms_template(grid.var_factory).block

    # lines
    line0_mdl = get_line_rms_template(grid.var_factory).block
    line1_mdl = get_line_rms_template(grid.var_factory).block
    line2_mdl = get_line_rms_template(grid.var_factory).block
    line3_mdl = get_line_rms_template(grid.var_factory).block
    line4_mdl = get_line_rms_template(grid.var_factory).block
    line5_mdl = get_line_rms_template(grid.var_factory).block
    line6_mdl = get_line_rms_template(grid.var_factory).block
    line7_mdl = get_line_rms_template(grid.var_factory).block
    line8_mdl = get_line_rms_template(grid.var_factory).block
    line9_mdl = get_line_rms_template(grid.var_factory).block
    line10_mdl = get_line_rms_template(grid.var_factory).block
    line11_mdl = get_line_rms_template(grid.var_factory).block
    line12_mdl = get_line_rms_template(grid.var_factory).block
    line13_mdl = get_line_rms_template(grid.var_factory).block

    # trafos
    trafo1_mdl = get_line_rms_template(grid.var_factory).block
    trafo2_mdl = get_line_rms_template(grid.var_factory).block
    trafo3_mdl = get_line_rms_template(grid.var_factory).block
    trafo4_mdl = get_line_rms_template(grid.var_factory).block

    # loads
    load1_mdl = get_load_rms_template(grid.var_factory).block
    load2_mdl = get_load_rms_template(grid.var_factory).block

    # set models parameters
    load1_mdl.set_parameter_in_model(var_name="Pl0", new_value=-9.670000000007317)
    load1_mdl.set_parameter_in_model(var_name="Ql0", new_value=-0.9999999999967969)

    load2_mdl.set_parameter_in_model(var_name="Pl0", new_value=-17.6699999999199)
    load2_mdl.set_parameter_in_model(var_name="Ql0", new_value=-0.999999999989467)

    # connection with buses

    grid.var_factory.add_connections([genrow_mdl1.in_vars[0]], [bus1.rms_model.out_vars[0]])
    grid.var_factory.add_connections([genrow_mdl1.in_vars[1]], [bus1.rms_model.out_vars[1]])

    grid.var_factory.add_connections([genrow_mdl2.in_vars[0]], [bus2.rms_model.out_vars[0]])
    grid.var_factory.add_connections([genrow_mdl2.in_vars[1]], [bus2.rms_model.out_vars[1]])

    grid.var_factory.add_connections([genrow_mdl3.in_vars[0]], [bus3.rms_model.out_vars[0]])
    grid.var_factory.add_connections([genrow_mdl3.in_vars[1]], [bus3.rms_model.out_vars[1]])

    grid.var_factory.add_connections([genrow_mdl4.in_vars[0]], [bus4.rms_model.out_vars[0]])
    grid.var_factory.add_connections([genrow_mdl4.in_vars[1]], [bus4.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line0_mdl.in_vars[0]], [bus5.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line0_mdl.in_vars[1]], [bus5.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line0_mdl.in_vars[2]], [bus6.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line0_mdl.in_vars[3]], [bus6.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line1_mdl.in_vars[0]], [bus5.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line1_mdl.in_vars[1]], [bus5.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line1_mdl.in_vars[2]], [bus6.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line1_mdl.in_vars[3]], [bus6.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line2_mdl.in_vars[0]], [bus6.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line2_mdl.in_vars[1]], [bus6.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line2_mdl.in_vars[2]], [bus7.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line2_mdl.in_vars[3]], [bus7.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line3_mdl.in_vars[0]], [bus6.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line3_mdl.in_vars[1]], [bus6.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line3_mdl.in_vars[2]], [bus7.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line3_mdl.in_vars[3]], [bus7.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line4_mdl.in_vars[0]], [bus6.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line4_mdl.in_vars[1]], [bus6.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line4_mdl.in_vars[2]], [bus7.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line4_mdl.in_vars[3]], [bus7.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line5_mdl.in_vars[0]], [bus7.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line5_mdl.in_vars[1]], [bus7.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line5_mdl.in_vars[2]], [bus8.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line5_mdl.in_vars[3]], [bus8.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line6_mdl.in_vars[0]], [bus7.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line6_mdl.in_vars[1]], [bus7.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line6_mdl.in_vars[2]], [bus8.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line6_mdl.in_vars[3]], [bus8.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line7_mdl.in_vars[0]], [bus8.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line7_mdl.in_vars[1]], [bus8.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line7_mdl.in_vars[2]], [bus9.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line7_mdl.in_vars[3]], [bus9.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line8_mdl.in_vars[0]], [bus8.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line8_mdl.in_vars[1]], [bus8.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line8_mdl.in_vars[2]], [bus9.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line8_mdl.in_vars[3]], [bus9.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line9_mdl.in_vars[0]], [bus9.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line9_mdl.in_vars[1]], [bus9.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line9_mdl.in_vars[2]], [bus10.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line9_mdl.in_vars[3]], [bus10.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line10_mdl.in_vars[0]], [bus9.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line10_mdl.in_vars[1]], [bus9.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line10_mdl.in_vars[2]], [bus10.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line10_mdl.in_vars[3]], [bus10.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line11_mdl.in_vars[0]], [bus9.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line11_mdl.in_vars[1]], [bus9.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line11_mdl.in_vars[2]], [bus10.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line11_mdl.in_vars[3]], [bus10.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line12_mdl.in_vars[0]], [bus10.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line12_mdl.in_vars[1]], [bus10.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line12_mdl.in_vars[2]], [bus11.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line12_mdl.in_vars[3]], [bus11.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line13_mdl.in_vars[0]], [bus10.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line13_mdl.in_vars[1]], [bus10.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line13_mdl.in_vars[2]], [bus11.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line13_mdl.in_vars[3]], [bus11.rms_model.out_vars[1]])

    grid.var_factory.add_connections([trafo1_mdl.in_vars[0]], [bus5.rms_model.out_vars[0]])
    grid.var_factory.add_connections([trafo1_mdl.in_vars[1]], [bus5.rms_model.out_vars[1]])

    grid.var_factory.add_connections([trafo1_mdl.in_vars[2]], [bus1.rms_model.out_vars[0]])
    grid.var_factory.add_connections([trafo1_mdl.in_vars[3]], [bus1.rms_model.out_vars[1]])

    grid.var_factory.add_connections([trafo2_mdl.in_vars[0]], [bus6.rms_model.out_vars[0]])
    grid.var_factory.add_connections([trafo2_mdl.in_vars[1]], [bus6.rms_model.out_vars[1]])

    grid.var_factory.add_connections([trafo2_mdl.in_vars[2]], [bus2.rms_model.out_vars[0]])
    grid.var_factory.add_connections([trafo2_mdl.in_vars[3]], [bus2.rms_model.out_vars[1]])

    grid.var_factory.add_connections([trafo3_mdl.in_vars[0]], [bus11.rms_model.out_vars[0]])
    grid.var_factory.add_connections([trafo3_mdl.in_vars[1]], [bus11.rms_model.out_vars[1]])

    grid.var_factory.add_connections([trafo3_mdl.in_vars[2]], [bus3.rms_model.out_vars[0]])
    grid.var_factory.add_connections([trafo3_mdl.in_vars[3]], [bus3.rms_model.out_vars[1]])

    grid.var_factory.add_connections([trafo4_mdl.in_vars[0]], [bus10.rms_model.out_vars[0]])
    grid.var_factory.add_connections([trafo4_mdl.in_vars[1]], [bus10.rms_model.out_vars[1]])

    grid.var_factory.add_connections([trafo4_mdl.in_vars[2]], [bus4.rms_model.out_vars[0]])
    grid.var_factory.add_connections([trafo4_mdl.in_vars[3]], [bus4.rms_model.out_vars[1]])

    grid.var_factory.add_connections([load1_mdl.in_vars[0]], [bus7.rms_model.out_vars[0]])
    grid.var_factory.add_connections([load1_mdl.in_vars[1]], [bus7.rms_model.out_vars[1]])

    grid.var_factory.add_connections([load2_mdl.in_vars[0]], [bus9.rms_model.out_vars[0]])
    grid.var_factory.add_connections([load2_mdl.in_vars[1]], [bus9.rms_model.out_vars[1]])

    # external mapping

    big_gen1 = Block(children=[genrow_mdl1])
    big_gen2 = Block(children=[genrow_mdl2])
    big_gen3 = Block(children=[genrow_mdl3])
    big_gen4 = Block(children=[genrow_mdl4])

    big_gen1.external_mapping.update({VarPowerFlowReferenceType.P: genrow_mdl1.out_vars[0]})
    big_gen1.external_mapping.update({VarPowerFlowReferenceType.Q: genrow_mdl1.out_vars[1]})

    big_gen2.external_mapping.update({VarPowerFlowReferenceType.P: genrow_mdl2.out_vars[0]})
    big_gen2.external_mapping.update({VarPowerFlowReferenceType.Q: genrow_mdl2.out_vars[1]})

    big_gen3.external_mapping.update({VarPowerFlowReferenceType.P: genrow_mdl3.out_vars[0]})
    big_gen3.external_mapping.update({VarPowerFlowReferenceType.Q: genrow_mdl3.out_vars[1]})

    big_gen4.external_mapping.update({VarPowerFlowReferenceType.P: genrow_mdl4.out_vars[0]})
    big_gen4.external_mapping.update({VarPowerFlowReferenceType.Q: genrow_mdl4.out_vars[1]})

    # add models to opi objects

    gen1.rms_model = big_gen1
    gen2.rms_model = big_gen2
    gen3.rms_model = big_gen3
    gen4.rms_model = big_gen4

    line0.rms_model = line0_mdl
    line1.rms_model = line1_mdl
    line2.rms_model = line2_mdl
    line3.rms_model = line3_mdl
    line4.rms_model = line4_mdl
    line5.rms_model = line5_mdl
    line6.rms_model = line6_mdl
    line7.rms_model = line7_mdl
    line8.rms_model = line8_mdl
    line9.rms_model = line9_mdl
    line10.rms_model = line10_mdl
    line11.rms_model = line11_mdl
    line12.rms_model = line12_mdl
    line13.rms_model = line13_mdl

    trafo_G1.rms_model = trafo1_mdl
    trafo_G2.rms_model = trafo2_mdl
    trafo_G3.rms_model = trafo3_mdl
    trafo_G4.rms_model = trafo4_mdl

    load1.rms_model = load1_mdl
    load2.rms_model = load2_mdl

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

    grid.add_line(trafo_G1)
    grid.add_line(trafo_G2)
    grid.add_line(trafo_G3)
    grid.add_line(trafo_G4)

    grid.add_load(bus=bus7, api_obj=load1)
    grid.add_load(bus=bus9, api_obj=load2)

    grid.add_generator(bus=bus1, api_obj=gen1)
    grid.add_generator(bus=bus2, api_obj=gen2)
    grid.add_generator(bus=bus3, api_obj=gen3)
    grid.add_generator(bus=bus4, api_obj=gen4)



    timings["case_and_model_build"] = elapsed_seconds(model_start)
    pf_options = PowerFlowOptions(
        solver_type=gce.SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        initialize_with_existing_solution=True,
        tolerance=1e-6,
        max_iter=25,
        control_q=False,
        control_taps_modules=True,
        control_taps_phase=True,
        control_remote_voltage=True,
        orthogonalize_controls=True,
        apply_temperature_correction=True,
        branch_impedance_tolerance_mode=gce.BranchImpedanceMode.Specified,
        distributed_slack=False,
        ignore_single_node_islands=False,
        trust_radius=1.0,
        backtracking_parameter=0.05,
        use_stored_guess=False,
        initialize_angles=False,
        generate_report=False,
    )
    power_flow = PowerFlowDriver(grid, pf_options)
    power_flow_start: float = time.perf_counter()
    power_flow.run()
    timings["power_flow"] = elapsed_seconds(power_flow_start)
    res = power_flow.results

    pr.enable()

    rms_options = RmsOptions(time_step=0.001,
                             simulation_time=10,
                             tolerance=1e-6,
                             integration_method=DynamicIntegrationMethod.DaeBackEuler,
                             initialization_method=RmsInitializationMethod.Explicit,
                             use_init_values=False,
                             max_iter=1000,
                             verbose=0)

    sss_options = RmsSmallSignalStabilityOptions(k=0,
                                                ss_assessment_time=0,
                                                verbose=1)


    compilation_start: float = time.perf_counter()
    small_signal_driver = SmallSignalStabilityRmsDriver(grid=grid,
                                                        rms_options=rms_options,
                                                        sss_options=sss_options,
                                                        pf_results=res)
    timings["symbolic_to_numeric"] = elapsed_seconds(compilation_start)
    small_signal_start: float = time.perf_counter()
    small_signal_driver.run()
    timings["small_signal_total"] = elapsed_seconds(small_signal_start)
    timings.update(benchmark_veragrid_isolated_numerical_phases(small_signal_driver))

    eigenvalues = small_signal_driver.results.eigenvalues
    PFactors = small_signal_driver.results.participation_factors
    damping_ratios = small_signal_driver.results.damping_ratios

    print(f"eigenvalues = {eigenvalues}")
    print(f"PFactors = {PFactors}")
    print(f"damping_ratios = {damping_ratios}")

    results_directory: Path = Path(__file__).resolve().parent / "kundur_small_signal_rms_results_VeraGrid"
    export_start: float = time.perf_counter()
    save_small_signal_results_to_csv(
        results=small_signal_driver.results,
        pf_results=res,
        output_dir=results_directory,
    )
    timings["result_export"] = elapsed_seconds(export_start)
    timings["end_to_end"] = elapsed_seconds(total_start) - (
        timings["state_matrix_isolated_repeat"]
        + timings["eigenanalysis_isolated_repeat"]
    )
    save_benchmark_timings(
        output_directory=results_directory,
        engine_label="VeraGrid",
        case_label="KUNDUR_no_shunt",
        timings=timings,
        state_count=int(small_signal_driver.results.state_matrix.shape[0]),
        mode_count=int(small_signal_driver.results.eigenvalues.size),
    )

    plot_s_domain_eigenvalues(eigenvalues=eigenvalues)
    plot_participation_factors(participation_factors=PFactors)
    plt.show()



if __name__ == '__main__':
    rms_kundur_small_signal()
else:
    pass
