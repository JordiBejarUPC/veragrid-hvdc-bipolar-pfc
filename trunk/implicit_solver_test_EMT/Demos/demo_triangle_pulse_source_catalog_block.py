# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Dict
from pathlib import Path

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.BasicBlockCatalog.Functions.typ_481__pulse import build_typ_481__pulse_template
from VeraGridEngine.Templates.BasicBlockCatalog.Functions.typ_489__triangle_wave_generator import (
    build_typ_489__triangle_wave_generator_template,
)
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const

from trunk.implicit_solver_test_EMT.Demos.catalog_signal_demo_support import bind_internal_time_vars
from trunk.implicit_solver_test_EMT.Demos.catalog_signal_demo_support import get_demo_plot_directory
from trunk.implicit_solver_test_EMT.Demos.catalog_signal_demo_support import plot_named_traces
from trunk.implicit_solver_test_EMT.Demos.catalog_signal_demo_support import run_demo_simulation
from trunk.implicit_solver_test_EMT.Demos.catalog_signal_demo_support import set_event_parameter_by_name


def run_triangle_pulse_source_demo(enable_plots: bool = True) -> Dict[str, object]:
    """
    Simulate one triangle-wave source driving the native pulse block.

    :param enable_plots: If True, show the resulting trace plots.
    :return: Trace dictionary.
    """
    output_dir: Path = get_demo_plot_directory("triangle_pulse_source_catalog_block")
    png_path: Path = output_dir / "triangle_pulse_source_catalog_block.png"

    vf = VarFactory()
    glob_time = vf.add_var("glob_time_triangle_pulse_demo")
    time_state = vf.add_var("time_state_triangle_pulse_demo")
    dtime_state = vf.add_diff_var(name="dtime_state_triangle_pulse_demo", base_var=time_state)
    triangle_template = build_typ_489__triangle_wave_generator_template(vf=vf, name="triangle_source_demo")
    pulse_template = build_typ_481__pulse_template(vf=vf, name="pulse_from_triangle_demo")

    bind_internal_time_vars(triangle_template.block, time_state)
    set_event_parameter_by_name(triangle_template.block, "f", 1.0)
    set_event_parameter_by_name(pulse_template.block, "K", 0.75)
    set_event_parameter_by_name(pulse_template.block, "T1", 0.08)
    pulse_template.block.connect([pulse_template.block.in_vars[0]], [triangle_template.block.out_vars[0]])

    x_state = vf.add_var("x_triangle_pulse_demo")
    dx_state = vf.add_diff_var(name="dx_triangle_pulse_demo", base_var=x_state)
    root_block = Block(
        name="TrianglePulseSourceCatalogDemo",
        children=list([triangle_template.block, pulse_template.block]),
        state_vars=list([time_state, x_state]),
        diff_vars=list([dtime_state, dx_state]),
        state_eqs=list([Const(1.0), Const(20.0) * (pulse_template.block.out_vars[0] - x_state)]),
        init_eqs=dict({time_state: Const(0.0), x_state: Const(0.0)}),
    )

    traces = run_demo_simulation(
        root_block=root_block,
        glob_time_var=glob_time,
        tracked_names=("yo_triangle_source_demo", "yo_pulse_from_triangle_demo", "x_triangle_pulse_demo"),
        t_end=4.0,
        dt=1.0e-3,
    )

    if enable_plots:
        plot_named_traces(
            traces=traces,
            title="Triangle Source Plus Pulse Catalog Demo",
            y_labels=("yo_triangle_source_demo", "yo_pulse_from_triangle_demo", "x_triangle_pulse_demo"),
            file_path=png_path,
        )
    else:
        plot_named_traces(
            traces=traces,
            title="Triangle Source Plus Pulse Catalog Demo",
            y_labels=("yo_triangle_source_demo", "yo_pulse_from_triangle_demo", "x_triangle_pulse_demo"),
            file_path=png_path,
        )

    result = dict(traces)
    result["png_path"] = str(png_path)
    return result


if __name__ == "__main__":
    run_triangle_pulse_source_demo(enable_plots=True)
