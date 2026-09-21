# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import numpy as np
from VeraGridEngine.basic_structures import Logger
import VeraGridEngine.api as gce
from VeraGridEngine.Devices.Events.dynamic_plot_entry import compare_dynamic_plots
from VeraGridEngine.Utils.Symbolic import Block
from VeraGridEngine.Utils.Symbolic.symbolic_io import compare_blocks


def test_load_save_load() -> None:
    """
    This test checks if the saving and load process is correct

    The test consists in:
    - loading grids in different gridcal variations (grid1)
    - saving the grid with a different name
    - loading the saved grid (grid2)
    - comparing that grid1 == grid2

    """
    folder = os.path.join('data', 'dynamic_versions')

    if not os.path.exists(os.path.join("data", "output")):
        os.makedirs(os.path.join("data", "output"))

    # for name in ['kundur_rms_6_0_22.veragrid',
    #              'kundur_from_gui_6_0_22.veragrid',]:

    for name in [
        'kundor_6_4_2_from_gui.veragrid',
        'kundur_6_1_3_from_gui.veragrid',
        'kundur_6_1_3_rms.veragrid',
        'kundur_6_1_3_static.veragrid',
        'kundur_6_2_0_from_gui.veragrid',
        'kundur_6_2_0_rms.veragrid',
        'kundur_6_2_0_static.veragrid',
        'kundur_6_2_3_from_gui.veragrid',
        'kundur_6_2_3_rms.veragrid',
        'kundur_6_2_3_static.veragrid',
        'kundur_6_3_2_from_gui.veragrid',
        'kundur_6_3_2_rms.veragrid',
        'kundur_6_3_2_static.veragrid',
        'kundur_6_3_8_from_gui.veragrid',
        'kundur_6_3_8_rms.veragrid',
        'kundur_6_3_8_static.veragrid',
        'kundur_6_4_2_rms.veragrid',
        'kundur_6_4_2_static.veragrid',
        'kundur_6_5_17_from_gui.veragrid',
        'kundur_6_5_17_rms.veragrid',
        'kundur_6_5_17_static.veragrid',
        'kundur_6_5_29_from_gui.veragrid',
        'kundur_6_5_29_rms.veragrid',
        'kundur_6_5_29_static.veragrid',
        'kundur_rms_6_0_22.veragrid',
        'kundur_rms_6_1_4.veragrid',
        'kundur_rms_6_2_11.veragrid',
        'kundur_rms_6_2_4.veragrid',
        'kundur_rms_6_3_4.veragrid',
        'kundur_rms_6_4_0.veragrid',
        'kundur_rms_6_5_0.veragrid',
        'kundur_rms_6_5_22.veragrid',
        'kundur_rms_from_gui_6_0_22.veragrid',
        'kundur_rms_from_gui_6_1_4.veragrid',
        'kundur_rms_from_gui_6_2_11.veragrid',
        'kundur_rms_from_gui_6_2_4.veragrid',
        'kundur_rms_from_gui_6_3_4.veragrid',
        'kundur_rms_from_gui_6_4_0.veragrid',
        'kundur_rms_from_gui_6_5_0.veragrid',
        'kundur_rms_from_gui_6_5_22.veragrid',
        'kundur_static_6_0_22.veragrid',
        'kundur_static_6_1_4.veragrid',
        'kundur_static_6_2_11.veragrid',
        'kundur_static_6_2_4.veragrid',
        'kundur_static_6_3_4.veragrid',
        'kundur_static_6_4_0.veragrid',
        'kundur_static_6_5_0.veragrid',
        'kundur_static_6_5_22.veragrid',
    ]:

        fname = os.path.join(folder, name)

        # open the main grid
        grid1 = gce.open_file(fname)

        name, ext = os.path.splitext(os.path.basename(fname))

        fname2 = os.path.join("data", "output", name + '_to_save.veragrid')

        gce.save_file(grid=grid1, filename=fname2)

        # open the main grid again
        grid2 = gce.open_file(fname2)

        # compare the original grid with the saved one to check that they are equal
        equal, logger = grid1.compare_circuits(grid2, detailed_profile_comparison=True)

        if not equal:
            logger.print()

        # asset for failing
        assert equal

        # if all ok, we can delete the test file
        os.remove(fname2)

