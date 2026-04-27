# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Dict

from trunk.implicit_solver_test_EMT.Demos.demo_lookup_table_catalog_block import run_lookup_table_catalog_demo
from trunk.implicit_solver_test_EMT.Demos.demo_triangle_pulse_source_catalog_block import run_triangle_pulse_source_demo


def run_lookup_table_case(enable_plots: bool = True) -> Dict[str, object]:
    """
    Run the catalog lookup-table demo from the `dynamics_emt` scripting surface.

    :param enable_plots: If True, show the resulting plots.
    :return: Trace dictionary.
    """
    return run_lookup_table_catalog_demo(enable_plots=enable_plots)


def run_triangle_pulse_case(enable_plots: bool = True) -> Dict[str, object]:
    """
    Run the triangle-source plus pulse demo from the `dynamics_emt` scripting surface.

    :param enable_plots: If True, show the resulting plots.
    :return: Trace dictionary.
    """
    return run_triangle_pulse_source_demo(enable_plots=enable_plots)


if __name__ == "__main__":
    run_lookup_table_case(enable_plots=True)
    run_triangle_pulse_case(enable_plots=True)
