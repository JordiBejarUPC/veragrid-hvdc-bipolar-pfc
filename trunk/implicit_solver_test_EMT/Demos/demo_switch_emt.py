# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Dict

from trunk.dynamics_emt.scripting_switch_emt import run_switch_emt_case


def run_demo(enable_plots: bool = True) -> Dict[str, object]:
    """
    Run the EMT switch demo from the implicit demo surface.

    :param enable_plots: If True, show the plot window.
    :return: Trace dictionary.
    """
    return run_switch_emt_case(enable_plots=enable_plots)


if __name__ == "__main__":
    run_demo(enable_plots=True)
