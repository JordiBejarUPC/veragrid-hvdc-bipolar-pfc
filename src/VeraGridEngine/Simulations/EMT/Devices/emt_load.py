# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
from VeraGridEngine.basic_structures import Mat
from VeraGridEngine.Devices.Injections.load import Load


class EmtLoad:

    def __init__(self):
        self.Gc: Mat = np.zeros((0, 0))
        self.G: Mat = np.zeros((0, 0))

    def initialize_emt(self, h: float, Sbase: float, load: Load):
        """

        :param h:
        :param Sbase:
        :param load:
        :return:
        """
        # todo: consider LC from the load
        # Zc = 0.0
        # if self.R > 0:
        #     Zc = self.R
        # if self.L > 0:
        #     Zc += 2 * self.L / h
        # if self.C > 0:
        #     Zc += h / 2 * self.C
        # G = 1.0 / Zc

        Vbase = load.bus.Vnom  # kV
        # Sbase in MVA
        V = Vbase * 1e3  # kV
        S = Sbase * 1e6  # VA
        Zbase = (V * V) / S
        print(f"Zbase calculated at load.py = {Zbase}[ohm]")
        #
        # all_phases = ['n', 'a', 'b', 'c']
        # phases = [p for p in all_phases if getattr(self.bus, f"ph_{p}")]

        # Gc_val = 1.0 / self.R
        # todo: si té L o C canviar Z a voltage source!
        P = load.Pa * 1e6
        R = (V * V / 3) / P  # ohm

        print(f"Rload [ohm] = {R}")
        R = R / Zbase  # p.u.
        Gc_val = 1.0 / R

        # CORRECT IMPLEMENTATION!!
        Gc4 = np.eye(4) * Gc_val
        Gc4[0, 0] = 0.0
        self.Gc = Gc4
        print(f"Rload [p.u.] = {R}")

        # cutre fix to check lines with matched Zc todo: TEMPORARY!
        # Zc_line = np.array([[4.213e2, 1.174e2, 8.758e1], [1.142e2, 4.217e2, 1.142e2],
        #                     [8.758e1, 1.174e2, 4.213e2]])
        # Zc_inv = np.linalg.inv(Zc_line)
        # Zc_inv_4x4 = np.zeros((4, 4))
        # Zc_inv_4x4[1:, 1:] = Zc_inv
        # self.Gc = Zc_inv_4x4

        # short-circuited
        # Zc_line = np.array([[0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0],
        #                     [0.0, 0.0, 0.0, 0.0]])
        # self.Gc = Zc_line

        # open-circuited
        # Zc_line = np.array([[1e30, 0.0, 0.0], [0.0, 1e30, 0.0],
        #                     [0.0, 0.0, 1e30]])
        # Zc_inv = np.linalg.inv(Zc_line)
        # Zc_inv_4x4 = np.zeros((4, 4))
        # Zc_inv_4x4[1:, 1:] = Zc_inv
        # self.Gc = Zc_inv_4x4

        print('load.Gc = ', self.Gc)  # p.u.
