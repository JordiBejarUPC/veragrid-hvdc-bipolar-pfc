# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, List, Tuple


def configure_repo_python_path() -> None:
    """
    Add repository source folders to ``sys.path`` before local imports.

    :return: None.
    """
    current_file: Path = Path(__file__).resolve()
    repo_root: Path = current_file.parent.parent.parent
    src_root: Path = repo_root / "src"
    repo_root_text: str = str(repo_root)
    src_root_text: str = str(src_root)

    # The script may be executed as a loose file, so the repository roots must
    # be available before importing any local package.
    if src_root_text in sys.path:
        pass
    else:
        sys.path.insert(0, src_root_text)

    if repo_root_text in sys.path:
        pass
    else:
        sys.path.insert(0, repo_root_text)


configure_repo_python_path()

import numpy as np

from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Templates.Emt.generator_emt_type_template import get_complete_generator_template_emt
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_r_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from trunk.dynamics_emt.scripting_2gens_same_bus_slack import (
    assert_close,
    build_emt_problem,
    build_two_bus_grid_with_two_slack_generators,
    compute_expected_balanced_phase_current,
    extract_three_phase_matrix,
    get_external_init_value,
    get_state_series,
    run_balanced_power_flow,
    run_short_emt_simulation,
    save_line_internal_currents_plot,
    save_phase_a_split_plot,
    save_two_panel_three_phase_plot,
)


def attach_emt_models(
        grid: MultiCircuit,
        line: Line,
        generator_1: Generator,
        generator_2: Generator,
        load: Load,
) -> Tuple[Block, Block, Block, Block]:
    """
    Attach EMT templates to all devices of the complete-generator test case.

    :param grid: Grid model.
    :param line: Transmission line.
    :param generator_1: First generator.
    :param generator_2: Second generator.
    :param load: Remote load.
    :return: Line, the two generator and the load EMT blocks.
    """
    bus: Bus

    # The network shell stays identical to the other same-bus scripts so the
    # comparison isolates the generator-model behavior only.
    line_block: Block = get_pi_line_emt_template(
        vf=grid.var_factory,
        phN=False,
        phA=True,
        phB=True,
        phC=True,
        name="Line01_Pi",
    ).block

    # Each slack generator receives the complete generator model so the EMT
    # initialization and dynamic run exercise the governor/exciter path too.
    generator_1_block: Block = get_complete_generator_template_emt(
        vf=grid.var_factory,
        name="SlackGen1_CompleteEmt",
    ).block
    generator_2_block: Block = get_complete_generator_template_emt(
        vf=grid.var_factory,
        name="SlackGen2_CompleteEmt",
    ).block

    load_block: Block = get_shunt_r_emt_template(
        vf=grid.var_factory,
        phA=True,
        phB=True,
        phC=True,
    ).block

    # Every bus still needs the standard EMT bus shell before branch and
    # injection templates can bind their external voltage/current variables.
    for bus in grid.buses:
        get_bus_emt_template(grid, bus)

    set_emt_model(device=line, model=line_block, var_factory=grid.var_factory)
    set_emt_model(device=generator_1, model=generator_1_block, var_factory=grid.var_factory)
    set_emt_model(device=generator_2, model=generator_2_block, var_factory=grid.var_factory)
    set_emt_model(device=load, model=load_block, var_factory=grid.var_factory)

    return line.emt_model, generator_1.emt_model, generator_2.emt_model, load.emt_model


def export_plots_two_slack_generators_same_bus(
        problem,
        time_values: np.ndarray,
        y_values: np.ndarray,
        bus0: Bus,
        bus1: Bus,
        line_block: Block,
        generator_1_block: Block,
        generator_2_block: Block,
        load_block: Block,
) -> List[Path]:
    """
    Export diagnostic plots for the complete-generator same-bus example.

    :param problem: EMT problem.
    :param time_values: Time vector.
    :param y_values: EMT state trajectory matrix.
    :param bus0: Slack bus.
    :param bus1: Remote bus.
    :param line_block: Line EMT block.
    :param generator_1_block: First generator EMT block.
    :param generator_2_block: Second generator EMT block.
    :param load_block: Load EMT block.
    :return: Saved plot paths.
    """
    output_directory: Path = Path(__file__).resolve().parent / "plot_results" / "emt_two_slack_generators_complete_same_bus_balanced"
    paths: List[Path] = list()

    # The plots mirror the other same-bus scripts so the model-dependent current
    # split can be compared visually with the same diagnostics.
    bus0_voltages: np.ndarray = extract_three_phase_matrix(problem, y_values, tuple(bus0.emt_model.out_vars[:3]))
    bus1_voltages: np.ndarray = extract_three_phase_matrix(problem, y_values, tuple(bus1.emt_model.out_vars[:3]))

    generator_1_currents: np.ndarray = extract_three_phase_matrix(problem, y_values, tuple(generator_1_block.out_vars[:3]))
    generator_2_currents: np.ndarray = extract_three_phase_matrix(problem, y_values, tuple(generator_2_block.out_vars[:3]))
    total_generator_currents: np.ndarray = generator_1_currents + generator_2_currents

    load_currents: np.ndarray = -np.column_stack((
        get_state_series(problem, load_block, "i_A", y_values),
        get_state_series(problem, load_block, "i_B", y_values),
        get_state_series(problem, load_block, "i_C", y_values),
    ))

    line_series_currents: np.ndarray = np.column_stack((
        get_state_series(problem, line_block, "i_ser_Line01_Pi_A", y_values),
        get_state_series(problem, line_block, "i_ser_Line01_Pi_B", y_values),
        get_state_series(problem, line_block, "i_ser_Line01_Pi_C", y_values),
    ))
    line_from_shunt_currents: np.ndarray = np.column_stack((
        get_state_series(problem, line_block, "i_cap_f_Line01_Pi_A", y_values),
        get_state_series(problem, line_block, "i_cap_f_Line01_Pi_B", y_values),
        get_state_series(problem, line_block, "i_cap_f_Line01_Pi_C", y_values),
    ))
    line_to_shunt_currents: np.ndarray = np.column_stack((
        get_state_series(problem, line_block, "i_cap_t_Line01_Pi_A", y_values),
        get_state_series(problem, line_block, "i_cap_t_Line01_Pi_B", y_values),
        get_state_series(problem, line_block, "i_cap_t_Line01_Pi_C", y_values),
    ))

    output_directory.mkdir(parents=True, exist_ok=True)

    paths.append(
        save_two_panel_three_phase_plot(
            file_path=output_directory / "bus_voltages.png",
            time_values=time_values,
            top_triplet=(bus0_voltages[:, 0], bus0_voltages[:, 1], bus0_voltages[:, 2]),
            top_title="Bus 0 Voltages",
            top_ylabel="Voltage [pu]",
            top_legend_prefix="Bus0",
            bottom_triplet=(bus1_voltages[:, 0], bus1_voltages[:, 1], bus1_voltages[:, 2]),
            bottom_title="Bus 1 Voltages",
            bottom_ylabel="Voltage [pu]",
            bottom_legend_prefix="Bus1",
        )
    )

    paths.append(
        save_two_panel_three_phase_plot(
            file_path=output_directory / "source_load_currents.png",
            time_values=time_values,
            top_triplet=(total_generator_currents[:, 0], total_generator_currents[:, 1], total_generator_currents[:, 2]),
            top_title="Total Slack-Generator Currents (Gen1 + Gen2)",
            top_ylabel="Current [pu]",
            top_legend_prefix="Gen",
            bottom_triplet=(load_currents[:, 0], load_currents[:, 1], load_currents[:, 2]),
            bottom_title="Remote Load Currents",
            bottom_ylabel="Current [pu]",
            bottom_legend_prefix="Load",
        )
    )

    paths.append(
        save_line_internal_currents_plot(
            file_path=output_directory / "line_internal_currents.png",
            time_values=time_values,
            series_currents=line_series_currents,
            from_shunt_currents=line_from_shunt_currents,
            to_shunt_currents=line_to_shunt_currents,
        )
    )

    paths.append(
        save_phase_a_split_plot(
            file_path=output_directory / "duplicated_slack_generators_phase_a_split.png",
            time_values=time_values,
            first_current=generator_1_currents[:, 0],
            second_current=generator_2_currents[:, 0],
            first_label="Gen1 i_A",
            second_label="Gen2 i_A",
            total_label="Gen1 + Gen2 i_A",
            title="Duplicated Complete Generators on Bus 0: Phase-A Currents",
        )
    )

    return paths


def main() -> None:
    """
    Execute the complete-generator EMT example with two generators on one slack bus.

    :return: None.
    """
    grid: MultiCircuit
    bus0: Bus
    bus1: Bus
    line: Line
    generator_1: Generator
    generator_2: Generator
    load: Load
    line_block: Block
    generator_1_block: Block
    generator_2_block: Block
    load_block: Block
    power_flow_results: Any
    problem: Any
    slack_bus_power: complex
    slack_phase_power_total: complex
    slack_phase_power_1: complex
    slack_phase_power_2: complex
    bus_voltage_a: complex
    expected_current_1_a: float
    expected_current_2_a: float
    initialized_current_1_a: float
    initialized_current_2_a: float
    time_values: np.ndarray
    y_values: np.ndarray
    plot_paths: List[Path]

    grid, bus0, bus1, line, generator_1, generator_2, load = build_two_bus_grid_with_two_slack_generators()
    line_block, generator_1_block, generator_2_block, load_block = attach_emt_models(grid, line, generator_1, generator_2, load)

    power_flow_results = run_balanced_power_flow(grid)
    print("Converged balanced power flow:", power_flow_results.converged)
    print(power_flow_results.get_bus_df())
    print(power_flow_results.get_branch_df())

    problem = build_emt_problem(grid, power_flow_results)

    # The balanced PF gives one total slack-bus power. The EMT builder must seed
    # each complete generator with its own current share according to ``Snom``.
    slack_bus_power = complex(power_flow_results.Sbus[0] / grid.Sbase)
    slack_phase_power_total = slack_bus_power / 3.0
    slack_phase_power_1 = slack_phase_power_total * (float(generator_1.Snom) / (float(generator_1.Snom) + float(generator_2.Snom)))
    slack_phase_power_2 = slack_phase_power_total * (float(generator_2.Snom) / (float(generator_1.Snom) + float(generator_2.Snom)))

    bus_voltage_a = complex(power_flow_results.voltage[0])
    expected_current_1_a = compute_expected_balanced_phase_current(slack_phase_power_1, bus_voltage_a)
    expected_current_2_a = compute_expected_balanced_phase_current(slack_phase_power_2, bus_voltage_a)

    initialized_current_1_a = get_external_init_value(
        problem,
        generator_1_block,
        "i_A_SlackGen1_CompleteEmt_gen",
    )
    initialized_current_2_a = get_external_init_value(
        problem,
        generator_2_block,
        "i_A_SlackGen2_CompleteEmt_gen",
    )

    assert_close(
        label="Complete generator 1 phase-A EMT initialization",
        value=initialized_current_1_a,
        expected=expected_current_1_a,
        tolerance=1.0e-8,
    )
    assert_close(
        label="Complete generator 2 phase-A EMT initialization",
        value=initialized_current_2_a,
        expected=expected_current_2_a,
        tolerance=1.0e-8,
    )
    assert_close(
        label="Total complete-generator phase-A current",
        value=initialized_current_1_a + initialized_current_2_a,
        expected=expected_current_1_a + expected_current_2_a,
        tolerance=1.0e-8,
    )
    assert_close(
        label="Complete-generator current sharing ratio",
        value=initialized_current_2_a / initialized_current_1_a,
        expected=float(generator_2.Snom) / float(generator_1.Snom),
        tolerance=1.0e-8,
    )

    time_values, y_values = run_short_emt_simulation(problem)
    plot_paths = export_plots_two_slack_generators_same_bus(
        problem=problem,
        time_values=time_values,
        y_values=y_values,
        bus0=bus0,
        bus1=bus1,
        line_block=line_block,
        generator_1_block=generator_1_block,
        generator_2_block=generator_2_block,
        load_block=load_block,
    )
    print("Generated plots:")
    for plot_path in plot_paths:
        print(f"  {plot_path}")


if __name__ == "__main__":
    main()
