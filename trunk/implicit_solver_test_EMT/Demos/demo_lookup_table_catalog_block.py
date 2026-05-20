# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Dict
from pathlib import Path

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.BasicBlockCatalog.Functions.typ_489__triangle_wave_generator import (
    build_typ_489__triangle_wave_generator_template,
)
from VeraGridEngine.Templates.BasicBlockCatalog.lookup_array_runtime_templates import (
    build_lookup_array_spline_runtime_template,
)
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var

from trunk.implicit_solver_test_EMT.Demos.catalog_signal_demo_support import bind_internal_time_vars
from trunk.implicit_solver_test_EMT.Demos.catalog_signal_demo_support import get_demo_plot_directory
from trunk.implicit_solver_test_EMT.Demos.catalog_signal_demo_support import plot_named_traces
from trunk.implicit_solver_test_EMT.Demos.catalog_signal_demo_support import run_demo_simulation
from trunk.implicit_solver_test_EMT.Demos.catalog_signal_demo_support import set_event_parameter_by_name


def run_lookup_table_catalog_demo(enable_plots: bool = True) -> Dict[str, object]:
    """
    Simulate one triangle-source plus lookup-table signal chain.

    :param enable_plots: If True, show the resulting trace plots.
    :return: Trace dictionary.
    """
    output_dir: Path = get_demo_plot_directory("lookup_table_catalog_block")
    png_path: Path = output_dir / "lookup_table_catalog_block.png"

    vf = VarFactory()
    glob_time = vf.add_var("glob_time_lookup_demo")
    time_state = vf.add_var("time_state_lookup_demo")
    dtime_state = vf.add_diff_var(name="dtime_state_lookup_demo", base_var=time_state)
    triangle_template = build_typ_489__triangle_wave_generator_template(vf=vf, name="triangle_source_demo")
    lookup_template = build_lookup_array_spline_runtime_template(
        vf=vf,
        x_points=(0.0, 0.20, 0.50, 0.80, 1.00),
        y_points=(0.0, 0.10, 1.00, 0.10, 0.0),
        name="lookup_spline_demo",
    )

    bind_internal_time_vars(triangle_template.block, time_state)
    set_event_parameter_by_name(triangle_template.block, "f", 0.5)
    grid.var_factory.add_connections([lookup_template.block.in_vars[0]], [triangle_template.block.out_vars[0]])

    x_state = vf.add_var("x_lookup_demo")
    dx_state = vf.add_diff_var(name="dx_lookup_demo", base_var=x_state)
    lag_gain = Const(12.0)
    root_block = Block(
        name="LookupTableCatalogDemo",
        children=list([triangle_template.block, lookup_template.block]),
        state_vars=list([time_state, x_state]),
        diff_vars=list([dtime_state, dx_state]),
        state_eqs=list([Const(1.0), lag_gain * (lookup_template.block.out_vars[0] - x_state)]),
        init_eqs=dict({time_state: Const(0.0), x_state: Const(0.0)}),
    )

    traces = run_demo_simulation(
        root_block=root_block,
        glob_time_var=glob_time,
        tracked_names=("yo_triangle_source_demo", "yo_lookup_spline_demo", "x_lookup_demo"),
        t_end=6.0,
        dt=2.0e-3,
    )

    if enable_plots:
        plot_named_traces(
            traces=traces,
            title="Lookup Table Catalog Block Demo",
            y_labels=("yo_triangle_source_demo", "yo_lookup_spline_demo", "x_lookup_demo"),
            file_path=png_path,
        )
    else:
        plot_named_traces(
            traces=traces,
            title="Lookup Table Catalog Block Demo",
            y_labels=("yo_triangle_source_demo", "yo_lookup_spline_demo", "x_lookup_demo"),
            file_path=png_path,
        )

    result = dict(traces)
    result["png_path"] = str(png_path)
    return result


if __name__ == "__main__":
    run_lookup_table_catalog_demo(enable_plots=True)
