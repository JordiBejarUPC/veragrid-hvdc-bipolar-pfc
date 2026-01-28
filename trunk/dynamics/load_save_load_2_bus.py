# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import numpy as np
from typing import List
import VeraGridEngine.api as gce
from VeraGridEngine.Utils.Symbolic import Block, compare_blocks_dict


def load_save_load_rms() -> None:

    """
        This test checks if the saving and load process is correct when the grid contains rms models

        The test consists in:
        - loading grids in different veragrid variations (grid1)
        - saving the grid with a different name
        - loading the saved grid (grid2)
        - comparing that grid1 == grid2

        """

    # folder = os.path.join('data', 'grids')
    #
    if not os.path.exists("output"):
        os.makedirs("output")
    #
    # for name in ['2bus_gen_load.veragrid']:
    fname ='2bus_gen_load_2.veragrid'

    # open the main grid
    grid1 = gce.open_file(fname)
    grid1.rms_models = list()

    name, ext = os.path.splitext(os.path.basename(fname))

    fname2 = os.path.join("output", name + '_to_save.veragrid')

    gce.save_file(grid=grid1, filename=fname2)

    # open the main grid again
    grid2 = gce.open_file(fname2)

    # compare the original grid with the saved one to check that they are equal
    equal, logger = grid1.compare_circuits(grid2, detailed_profile_comparison=True)
    if not equal:
        logger.print()
    # asset for failing
    assert equal

    # compare the rms models inside the elements of the grid
    grid1_rms_system_dict = grid1.compose_bus_blocks()
    grid2_rms_system_dict = grid2.compose_bus_blocks()

    blocks_grid1: List[Block] = list()

    blocks_grid2: List[Block] = list()

    for bus, block in grid1_rms_system_dict.items():
        blocks_grid1.extend(block.children)

    for bus, block in grid2_rms_system_dict.items():
        blocks_grid2.extend(block.children)

    for block1, block2 in zip(blocks_grid1, blocks_grid2):
        # compare the blocks
        equal, logger = compare_blocks_dict(block1.to_dict(), block2.to_dict())

        if not equal:
            logger.print()

    # asset for failing
    assert equal

    # if all ok, we can delete the test file
    os.remove(fname2)

load_save_load_rms()