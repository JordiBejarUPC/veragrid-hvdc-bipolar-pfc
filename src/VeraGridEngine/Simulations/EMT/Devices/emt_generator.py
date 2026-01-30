# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
from VeraGridEngine.basic_structures import Vec, IntVec, Logger
from VeraGridEngine.Devices.Injections.generator import Generator


class EmtGenerator:

    def __init__(self, n_elm: int):
        """

        :param n_elm:
        """
        self.n_elm = n_elm
        self.Gc_list = [None] * self.n_elm
        self.Rp: Vec = np.zeros(self.n_elm, dtype=float)


def initialize_emt_generator(ii: int,
                             dta: EmtGenerator,
                             h: float,
                             gen: Generator,
                             logger: Logger = Logger(),
                             verbose: int = 0):
    """
    Current Source Interface with High-Z Snubber (Corrección de Interfaz)
    """
    if gen.emt_model.empty():
        logger.add_error("No model added to the Generator ", gen.name)

        if verbose > 0:
            print(f"No model added to the Generator {gen.name}")
    else:
        phases = gen.bus.get_phases_array()
        idx4 = np.array(range(4))
        k4: IntVec = 4 * ii + idx4

        Ldpp = 0.245 #TODO: retrieve from the generator model
        N = 1.0
        dta.Rp[ii] = 2 * Ldpp / (N * h)

        Gc_val = 1.0 / dta.Rp[ii]

        if verbose > 0:
            print(f'Generator {gen.name}: '
                  f'Configured as Current Source with Snubber Rp={dta.Rp[ii]} p.u.')

        phases_idx = np.where(phases)[0]
        Gc: Vec = np.zeros((4, 4), dtype=float)

        Gc[np.ix_(phases_idx, phases_idx)] = np.eye(len(phases_idx)) * Gc_val

        dta.Gc_list[ii] = Gc

        if verbose > 0:
            print(f"Generator.Gc= {Gc}")

        return Gc