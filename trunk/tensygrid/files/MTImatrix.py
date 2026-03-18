# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
MTI_Matrix: Multilinear Tensor Interpolation Matrix.
"""

import sys

class MTImatrix:
    """
    Multilinear Tensor Interpolation Matrix.
    """

    def __init__(self, problem):
        """
        :param problem: RMS phasor problem instance.
        """
        self.problem = problem


        print("Surto del programa")
        #sys.exit(1)

