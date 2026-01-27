# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
from VeraGridEngine.basic_structures import Mat, IntVec, Vec, BoolVec
from VeraGridEngine.Devices.Branches.transformer import Transformer2W


class EmtTransformer:

    def __init__(self, n_elm: int):
        self.n_elm = n_elm

        self.L_hh: Vec = np.zeros(self.n_elm, dtype=float)
        self.L_ll: Vec = np.zeros(self.n_elm, dtype=float)
        self.L_hl: Vec = np.zeros(self.n_elm, dtype=float)

        self.Gff: Mat = np.zeros((4 * self.n_elm, 4), dtype=float)
        self.Gft: Mat = np.zeros((4 * self.n_elm, 4), dtype=float)
        self.Gtf: Mat = np.zeros((4 * self.n_elm, 4), dtype=float)
        self.Gtt: Mat = np.zeros((4 * self.n_elm, 4), dtype=float)


def initialize_emt_transformer(ii: int,
                               dta: EmtTransformer,
                               h: float,
                               tr: Transformer2W):
    """

    :param ii:
    :param dta:
    :param h:
    :param tr:
    :return:
    """
    idx4 = np.array(range(4))
    k4: IntVec = 4 * ii + idx4

    # for now the ideal transformer won't have a symbolic block, just numeric solver in emt_driver.
    # here the needed params L11 L12 L21 L22 are calculated
    v_from = tr.bus_from.Vnom
    v_to = tr.bus_to.Vnom
    v_h = max(v_from, v_to)
    # v_l = min(v_from, v_to)

    X_leack = tr.X # p.u.
    X_magn = 1 / tr.B # p.u.
    # R_cooper = tr.R
    # R_iron = 1 / tr.G

    L1 = X_leack / 2.0
    L2 = L1
    L12 = X_magn - L1
    L11 = L1 + L12
    L22 = L2 + L12

    dta.L_hh = L11
    dta.L_ll = L22
    dta.L_hl = L12

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

    binary_bus_mask: BoolVec = np.zeros(4, dtype=bool)
    binary_bus_mask[0] = bool(tr.bus_from.ph_n)
    binary_bus_mask[1] = bool(tr.bus_from.ph_a)
    binary_bus_mask[2] = bool(tr.bus_from.ph_b)
    binary_bus_mask[3] = bool(tr.bus_from.ph_c)

    dta.Gff[k4, :] = Gff[binary_bus_mask, binary_bus_mask]
    dta.Gft[k4, :] = Gft[binary_bus_mask, binary_bus_mask]
    dta.Gtf[k4, :] = Gtf[binary_bus_mask, binary_bus_mask]
    dta.Gtt[k4, :] = Gtt[binary_bus_mask, binary_bus_mask]
