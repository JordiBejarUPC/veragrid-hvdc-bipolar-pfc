# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
from VeraGridEngine.basic_structures import Mat, IntVec
from VeraGridEngine.Devices.Injections.load import Load


class EmtLoad:

    def __init__(self, n_elm: int):
        """

        :param n_elm:
        """
        self.n_elm = n_elm
        # self.Gc: Mat = np.zeros((4 * self.n_elm, 4), dtype=float)
        # self.G: Mat = np.zeros((4 * self.n_elm, 4), dtype=float)


def initialize_emt_load(ii: int,
                        dta: EmtLoad,
                        sbase: float,
                        load: Load,
                        verbose: int = 0):
    """

    :param ii:
    :param dta:
    :param sbase:
    :param load:
    :param verbose:
    :return:
    """

    idx4 = np.array(range(4))
    k4: IntVec = 4 * ii + idx4

    # todo: consider LC from the load
    # Zc = 0.0
    # if self.R > 0:
    #     Zc = self.R
    # if self.L > 0:
    #     Zc += 2 * self.L / h
    # if self.C > 0:
    #     Zc += h / 2 * self.C
    # G = 1.0 / Zc

    vbase = load.bus.Vnom  # kV
    # Sbase in MVA
    V = vbase * 1e3  # kV
    S = sbase * 1e6  # VA
    Zbase = (V * V) / S

    if verbose:
        print(f"Zbase calculated at load.py = {Zbase}[ohm]")

    P = load.Pa * 1e6
    R = (V * V / 3) / P  # ohm

    if verbose:
        print(f"Rload [ohm] = {R}")

    R = R / Zbase  # p.u.
    Gc_val = 1.0 / R

    Gc: Mat = np.zeros((4, 4), dtype=float)
    Gc[np.ix_(k4[1:], k4[1:])] = Gc_val

    if verbose:
        print(f"Rload [p.u.] = {R}")

    # "cutre" fix to check lines with matched Zc TEMPORARY!
    # Zc_line = np.array([[4.213e2, 1.174e2, 8.758e1], [1.142e2, 4.217e2, 1.142e2],
    #                     [8.758e1, 1.174e2, 4.213e2]])
    # Zc_inv = np.linalg.inv(Zc_line)
    # Zc_inv_4x4 = np.zeros((4, 4))
    # Zc_inv_4x4[1:, 1:] = Zc_inv
    # self.Gc = Zc_inv_4x4

    if verbose:
        print('load.Gc = ', Gc_val)  # p.u.

    return Gc
