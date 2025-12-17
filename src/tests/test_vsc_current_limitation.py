# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import os
import numpy as np
import VeraGridEngine.api as vge
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from VeraGridEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions
from VeraGridEngine.enumerations import ConverterControlType

def test_vsc_current_limitation() -> None:
    """
    Full AC/DC Power Flow simulation with converter's current limitation and negative poles
    """
    fname = os.path.join('data', 'grids', 'vsc_current_limitation.veragrid')

    grid = vge.open_file(fname)

    options = PowerFlowOptions(solver_type=SolverType.NR,
                               retry_with_other_methods=False,
                               limit_i_vsc=True)

    driver = PowerFlowDriver(grid=grid, options=options)
    driver.run()
    solution = driver.results

    if not solution.converged:
        driver.logger.print("")

    assert solution.converged

    # Checks if the voltage magnitude and angle are correct.
    assert np.allclose(0.9287489355489488, abs(solution.voltage[9]), atol=1e-4)
    assert np.allclose(-11.373895194717075, np.angle(solution.voltage[9], deg=True), atol=1e-4)

    # Checks if the converter's current limitation is well implemented, controlling Imax instead of Qac,
    # which originally was 5 MVAr.
    assert np.allclose(4.99999615809046, solution.St[27].real, atol=1e-4)
    assert np.allclose(2.628707079131246, solution.St[27].imag, atol=1e-4)
    assert np.allclose(1+0j, solution.voltage[21], atol=1e-4)