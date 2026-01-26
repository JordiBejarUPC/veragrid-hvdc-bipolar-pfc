# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
import scipy as sp
from VeraGridEngine.basic_structures import Mat
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.enumerations import EmtLineTypes


class EmtLine:
    __slots__ = (
        'tau',
        'Ndelay',
        'H',
        'Gc',
        'Gff',
        'Gft',
        'Gtf',
        'Gtt',
    )

    def __init__(self):
        self.tau: float = 0
        self.Ndelay: int = 0
        self.H: Mat = np.zeros((0, 0))
        self.Gc: Mat = np.zeros((0, 0))
        self.Gff: Mat = np.zeros((0, 0))
        self.Gft: Mat = np.zeros((0, 0))
        self.Gtf: Mat = np.zeros((0, 0))
        self.Gtt: Mat = np.zeros((0, 0))

    def initialize_emt(self, line: Line, h: float, Sbase: float, fbase: float, verbose: int = 0):
        """
        Bergeron's line model / Pi Model
        :param line: Line object to use for initialization
        :param h: float, time step of the EMT simulation
        :param Sbase: base power of the grid
        :param fBase: base frequency of the grid

        initialize_emt computes the following parameters:
        l_: distributed line inductance [H/m]
        c_: distributed line capacitance [F/m]
        Zc: line characteristic impedance [ohm]
        v_wave: wave propagation speed [m/s]
        self.tau: time that takes the wave to travel the line [s]
        self.Ndelay: proportional constant tau/h
        self.H_abc: NxN matrix parameter used to compute the history current components
        self.Gc_abc: NxN matrix inverse of Z, being Z=Zc+R/4 (Bergeron) or inv(R+2L/h) (Pi)
        self.Gff_abc: from-from component of the line conductance matrix
        self.Gft_abc: from-to component of the line conductance matrix
        self.Gtf_abc: to-from component of the line conductance matrix
        self.Gtt_abc: to-to component of the line conductance matrix

        Includes ParaEMT Damping (Alvarado's Method)
        """

        if verbose > 0:
            print(f"--- Initializing Line: {line.name} ({line.emt_model_type}) ---")

        f = fbase
        w = 2 * np.pi * f
        # Sbase = Sbase #VA
        Sbase = Sbase  # MVA
        Vbase = line.bus_from.Vnom  # kV
        V = Vbase * 1e3  # V
        S = Sbase * 1e6  # VA
        Zbase = V * V / S  # ohm

        if verbose > 0:
            print('Zbase calculated at line.py [ohm] = ', Zbase)
        Ybase = 1 / Zbase
        # Lbase = Zbase / w  # H
        # Rbase = Zbase
        # Cbase = 1.0 / (w * Zbase)  # F

        if line.length <= 0.0:
            raise ValueError(f"Line {line.name}: length must be defined for EMT simulations.")

        phases = line.bus_from.get_phases_array()

        Ncond = len(phases)  # how many phases + neutral

        if Ncond == 0:
            # Open line
            self.Gc = np.zeros((0, 0))
            self.H = np.zeros((0, 0))
            self.Gff = self.Gc
            self.Gtt = self.Gc
            self.Gft = np.zeros_like(self.Gc)
            self.Gtf = np.zeros_like(self.Gc)
            self.tau = 0
            self.Ndelay = 0
            return

        # --- 1. PARAMETROS FÍSICOS (Physical Parameters) ---
        Z = line.template.z_nabc  # from Carson ohm/km
        Y = line.template.y_nabc  # from Carson ohm/km
        print('Z tower [ohm/km] =', Z)  # ohm/km
        print('Y tower [S/km] =', Y)  # S/km

        Z_phys_m = Z / 1e3  # ohm/m
        Y_phys_m = Y / 1e3  # S/m

        # Variables solicitadas en docstring para debug físico
        l_ = np.imag(Z_phys_m) / w  # H/m
        c_ = np.imag(Y_phys_m) / w  # F/m
        r_ = np.real(Z_phys_m)  # Ohm/m

        # Cálculo robusto de Zc físico y velocidad de onda
        # v_wave and tau from the travelling wave are taken only from the diagonal components
        L_w = l_[0, 0]
        C_w = c_[0, 0]
        v_wave = 1 / np.sqrt(L_w * C_w)

        # Tau físico (solo relevante para Bergeron/J-Marti, pero se calcula siempre)
        self.tau = line.length * 1e3 / v_wave  # s
        self.Ndelay = max(1, int(round(self.tau / h)))  # int

        if verbose > 0:
            print(f'l_ line= {l_[0, 0]:.3e}[H/m] (diag)')
            print(f'c_ line= {c_[0, 0]:.3e}[F/m] (diag)')
            print(f'v_wave= {v_wave:.2e}[m/s]')
            print(f'tau line= {self.tau}[s]')
            print(f'Ndelay line= {self.Ndelay}[-]')

        # --- 2. PARAMETROS EN P.U. (Per Unit Matrices) ---
        Z_pu = Z_phys_m / Zbase  # p.u./m
        Y_pu = Y_phys_m / Ybase  # p.u./m

        R = np.real(Z_pu) * line.length  # p.u. Total
        L = np.imag(Z_pu) * line.length  # p.u. Total (Reactancia inductiva total)
        C = np.imag(Y_pu) * line.length  # p.u. Total (Susceptancia capacitiva total)

        if verbose > 0:
            print(f'R line= {R}[p.u.]')
            print(f'L line= {L}[p.u.]')
            print(f'C line= {C}[p.u.]')

        # --- 3. CÁLCULO DE MATRICES Gc y H (n x n) SEGÚN MODELO ---

        # Pre-calculo de Zc para impresión (útil para Bergeron)
        try:
            Zc = sp.linalg.sqrtm(L @ np.linalg.inv(C))
        except:
            Zc = np.eye(Ncond) * np.sqrt(L[0, 0] / C[0, 0])

        if verbose > 0:
            print(f'Zc line= {Zc}[p.u.]')
            print("type Zc=", type(Zc))

        if line.emt_model_type == EmtLineTypes.PI:

            if verbose > 0:
                print("  > Configuring Matrices for PI Model (Hybrid: Trapezoidal RL + BackEuler C)...")

            # 1. RAMA SERIE (RL) -> Usamos TRAPECIO (Precisión)
            # Factor L = 2.0 / (w*h)
            factor_L = 2.0 / (w * h)
            Z_series = R + L * factor_L
            Gc_series = np.linalg.inv(Z_series)

            # 2. RAMA SHUNT (C) -> Usamos BACKWARD EULER (Estabilidad)
            # Factor C = 1.0 / (w*h).
            # (Backward Euler amortigua oscilaciones numéricas en nodos de voltaje)
            factor_C = 1.0 / (w * h)
            Gc_shunt = C * factor_C

            # 3. ASIGNACIÓN DE MATRICES

            # Gc: Solo la parte serie (para calcular historia serie en driver)
            Gc = Gc_series
            H = np.zeros_like(Gc)

            # G_shunt: Lo guardamos temporalmente para mapearlo
            G_shunt = Gc_shunt
        else:

            if verbose > 0:
                print("  > Configuring Matrices for BERGERON/JMARTI Model...")

            # Modelo Bergeron: Z = Zc + R/4
            Z_eq = np.real(Zc) + R / 4
            Gc = np.linalg.inv(Z_eq)
            # H = (Zc - R/4) * Gc
            H = (np.real(Zc) - R / 4) @ Gc

            if verbose > 0:
                print(f'Z line= {Z_eq}[p.u.]')
                print(f'Gc line= {Gc}[p.u.]')
                print(f'H line= {H}[p.u.]')

            G_shunt = np.zeros_like(Gc)  # Bergeron no tiene shunt explícito en G

        # --- 4. MAPEO A MATRICES 4x4 (Tu bucle original) ---
        all_phases = ['n', 'a', 'b', 'c']
        # convert Gc to a 4x4 matrix with 0 in the rows and cols of nonexistent phases
        loc_index = {ph: i for i, ph in enumerate(phases)}

        Gc4 = np.zeros((4, 4), dtype=float)
        H4 = np.zeros((4, 4), dtype=float)
        G_shunt4 = np.zeros((4, 4), dtype=float)  # Necesario para Pi

        for i, phi in enumerate(all_phases):
            if phi in phases:
                i_small = loc_index[phi]
                for j, phj in enumerate(all_phases):
                    if phj in phases:
                        j_small = loc_index[phj]
                        Gc4[i, j] = Gc[i_small, j_small]
                        H4[i, j] = H[i_small, j_small]
                        if line.emt_model_type == EmtLineTypes.PI:
                            G_shunt4[i, j] = G_shunt[i_small, j_small]

        # --- 5. ASIGNACIÓN FINAL (Con corrección para Pi) ---

        # Gc4 = Gc4 * Zbase # to p.u.
        self.H = H4  # NxN H has no units
        self.Gc = Gc4  # Esta es la conductancia "principal" (Serie en Pi, Característica en Bergeron)

        # Matriz Nodal (Gff, Gtt, Gft, Gtf)
        if line.emt_model_type == EmtLineTypes.PI:
            # En Pi, Gff = G_serie + G_shunt
            self.Gff = Gc4 + G_shunt4
            self.Gtt = Gc4 + G_shunt4

            # CRITICO: En Pi, los nodos están ACOPLADOS. Gft = -G_serie
            self.Gft = -1.0 * Gc4
            self.Gtf = -1.0 * Gc4

            # En Pi, forzamos Ndelay=1 y Tau=0 para que el driver no busque buffers lejanos
            self.tau = 0
            self.Ndelay = 1

        else:
            # En Bergeron, Gff = Gc (Resistencia equivalente a tierra)
            self.Gff = self.Gc
            self.Gtt = self.Gc

            # En Bergeron, los nodos están DESACOPLADOS en t (Gft=0)
            self.Gft = np.zeros_like(self.Gc)
            self.Gtf = np.zeros_like(self.Gc)
