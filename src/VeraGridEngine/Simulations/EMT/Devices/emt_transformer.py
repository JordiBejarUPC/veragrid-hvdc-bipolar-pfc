# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
from VeraGridEngine.basic_structures import Mat
from VeraGridEngine.Devices.Branches.transformer import Transformer2W


class EmtTransformer:

    def __init__(self):
        self.X_leack: float = 0.0
        self.X_magn: float = 0.0
        self.L_hh: float = 0.0
        self.L_ll: float = 0.0
        self.L_hl: float = 0.0
        self.Gc: Mat = np.zeros((0, 0))
        self.Gff: Mat = np.zeros((0, 0))
        self.Gft: Mat = np.zeros((0, 0))
        self.Gtf: Mat = np.zeros((0, 0))
        self.Gtt: Mat = np.zeros((0, 0))

    def initialize_emt(self, h: float, tr: Transformer2W):
        """

        :param h:
        :param tr:
        :return:
        """
        # for now the ideal transformer won't have a symbolic block, just numeric solver in emt_driver.
        # here the needed params L11 L12 L21 L22 are calculated
        v_from = tr.bus_from.Vnom
        v_to = tr.bus_to.Vnom
        v_h = max(v_from, v_to)
        v_l = min(v_from, v_to)
        a = v_h / v_l  # in p.u. a is 1

        L1 = self.X_leack / 2
        L2 = L1
        L12 = self.X_magn - L1
        L11 = L1 + L12
        L22 = L2 + L12

        self.L_hh = L11
        self.L_ll = L22
        self.L_hl = L12

        det = L11 * L22 - L12 * L12

        # single phase
        Gc = (h / (2 * det)) * np.array([[L22, -L12], [-L12, L11]])

        if v_h == v_from:  # bus "from" is the primary
            Gff = Gc[0, 0]
            Gft = Gc[0, 1]
            Gtf = Gc[1, 0]
            Gtt = Gc[1, 1]

        else:  # bus "to" is the primary
            Gff = Gc[1, 1]
            Gft = Gc[1, 0]
            Gtf = Gc[0, 1]
            Gtt = Gc[0, 0]

        # assuming no coupling between phases
        Gff = np.eye(4, 4) * Gff
        Gft = np.eye(4, 4) * Gft
        Gtf = np.eye(4, 4) * Gtf
        Gtt = np.eye(4, 4) * Gtt

        binary_bus_mask = np.zeros(4, dtype=bool)
        binary_bus_mask[0] = bool(tr.bus_from.ph_n)
        binary_bus_mask[1] = bool(tr.bus_from.ph_a)
        binary_bus_mask[2] = bool(tr.bus_from.ph_b)
        binary_bus_mask[3] = bool(tr.bus_from.ph_c)
        self.Gc = Gff  # ???

        self.Gff = Gff[binary_bus_mask, binary_bus_mask]
        self.Gft = Gft[binary_bus_mask, binary_bus_mask]
        self.Gtf = Gtf[binary_bus_mask, binary_bus_mask]
        self.Gtt = Gtt[binary_bus_mask, binary_bus_mask]
