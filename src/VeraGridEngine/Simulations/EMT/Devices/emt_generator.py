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

        self.Gc: Vec = np.zeros(4 * self.n_elm, dtype=float)
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

        # --- CORRECCIÓN ---
        # Ldpp = 0.245  # TODO: retrieve from emt_model
        # Gc_val = h / (2 * Ldpp)
        # AHORA: Usamos un Snubber de alta impedancia.

        # Valor alto en p.u. (ej. 10,000 p.u).
        # Esto actúa casi como circuito abierto para la física,
        # pero evita matrices singulares numéricamente.
        # self.Rp = 10000.0
        Ldpp = 0.245
        N = 1.0
        dta.Rp[ii] = 2 * Ldpp / (N * h)
        # self.Rp = 0.02
        # self.Rp = 1000000000000
        # Rp=123808.42921715266 p.u.

        # Si tu matriz Ybus trabaja en p.u., usa 1/Rp.
        # Si trabaja en Siemens reales, divide por Zbase (asumiendo que Sbase/Vbase están disponibles).
        # Por seguridad, definimos Gc_val como una conductancia muy pequeña.
        Gc_val = 1.0 / dta.Rp[ii]

        if verbose > 0:
            print(f'Generator {gen.name}: '
                  f'Configured as Current Source with Snubber Rp={dta.Rp[ii]} p.u.')

        for i, ph in enumerate(phases):
            if ph:
                dta.Gc[k4[i]] = Gc_val  # TODO, check this is ok

        if verbose > 0:
            print(f"Generator.Gc= {dta.Gc[k4]}")
