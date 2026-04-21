# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import List
import numpy as np
import scipy as sp
from VeraGridEngine.basic_structures import Mat, Vec, IntVec
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.enumerations import EmtLineTypes


class EmtLine:
    __slots__ = (
        'nelm',
        'tau',
        'n_delay',
        'H',
        'Gc',
        'emt_model_type',
        'pi_indices',
        'bergeron_indices',
        'j_marti_indices',
    )

    def __init__(self, n_elm: int):
        self.nelm: int = n_elm

        self.tau: Vec = np.zeros(self.nelm, dtype=float)
        self.n_delay: IntVec = np.zeros(self.nelm, dtype=int)
        self.H: Mat = np.zeros((self.nelm * 4, 4))
        self.Gc: Mat = np.zeros((self.nelm * 4, 4))
        # self.Gff: Mat = np.zeros((self.nelm * 4, 4))
        # self.Gft: Mat = np.zeros((self.nelm * 4, 4))
        # self.Gtf: Mat = np.zeros((self.nelm * 4, 4))
        # self.Gtt: Mat = np.zeros((self.nelm * 4, 4))
        self.emt_model_type: List[EmtLineTypes] = [EmtLineTypes.Bergeron] * self.nelm

        self.pi_indices: List[int] = list()
        self.bergeron_indices: List[int] = list()
        self.j_marti_indices: List[int] = list()

    def set_emt_model_type(self, ii: int, tpe: EmtLineTypes):
        self.emt_model_type[ii] = tpe

        if tpe == EmtLineTypes.PI:
            self.pi_indices.append(ii)
        elif tpe == EmtLineTypes.Bergeron:
            self.bergeron_indices.append(ii)
        elif tpe == EmtLineTypes.J_Marti:
            self.j_marti_indices.append(ii)
        else:
            raise NotImplementedError(f"{tpe} is not implemented")


def initialize_emt_line(ii: int,
                        line: Line,
                        dta: EmtLine,
                        h: float,
                        Sbase: float,
                        fbase: float,
                        verbose: int = 0):
    """
    Compile Line EMT parameters
    Here we fill the line with index ii in the structure EmtLine

    :param ii: line index
    :param line: Line object to use for initialization
    :param dta: EmtLine structure
    :param h: float, time step of the EMT simulation
    :param Sbase: base power of the grid
    :param fbase: base frequency of the grid
    :param verbose: verbosity level

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

    dta.set_emt_model_type(ii=ii, tpe=line.emt_model_type)

    idx4 = np.array(range(4))
    k4 = 4 * ii + idx4

    w = 2 * np.pi * fbase
    Sbase = Sbase  # MVA
    Vbase = line.bus_from.Vnom  # kV
    V = Vbase * 1e3  # V
    S = Sbase * 1e6  # VA
    Zbase = V * V / S  # ohm

    if verbose > 0:
        print('Zbase calculated at line.py [ohm] = ', Zbase)
    Ybase = 1 / Zbase

    if line.length <= 0.0:
        raise ValueError(f"Line {line.name}: length must be defined for EMT simulations.")

    if line.template is None:
        raise ValueError("Line template must be present to be able to obtain 4x4 impedance matrices")

    phases = line.bus_from.get_phases_array()

    # Physical Parameters from Carson's
    # TODO: consider using line.ys and line.ysh instead
    Z = line.template.z_nabc  # from Carson ohm/km
    Y = line.template.y_nabc  # from Carson ohm/km

    if verbose:
        print('Z tower [ohm/km] =', Z)  # ohm/km
        print('Y tower [S/km] =', Y)  # S/km

    Z_phys_m = Z / 1e3  # ohm/m
    Y_phys_m = Y / 1e3  # S/m

    # line time delay (tau) (only relevant for Bergeron and JMartí)
    dta.tau[ii] = line.get_tau(w=w)  # s
    dta.n_delay[ii] = max(1, int(round(dta.tau[ii] / h)))  # int

    # Per Unit parameters
    Z_pu = Z_phys_m / Zbase  # p.u./m
    Y_pu = Y_phys_m / Ybase  # p.u./m

    R = np.real(Z_pu) * line.length  # p.u. Total
    L = np.imag(Z_pu) * line.length  # p.u. Total  (total inductive reactance)
    C = np.imag(Y_pu) * line.length  # p.u. Total  (total capacitive susceptance)

    if verbose > 0:
        print(f'R line= {R}[p.u.]')
        print(f'L line= {L}[p.u.]')
        print(f'C line= {C}[p.u.]')

    # Gc y H (n x n) matrices calculation
    try:
        Zc = sp.linalg.sqrtm(L @ np.linalg.inv(C))
    except:
        Zc = np.eye(4) * np.sqrt(L[0, 0] / C[0, 0])

    if verbose > 0:
        print(f'Zc line= {Zc}[p.u.]')
        print("type Zc=", type(Zc))

    if line.emt_model_type == EmtLineTypes.PI:

        if verbose > 0:
            print("  > Configuring Matrices for PI Model (Hybrid: Trapezoidal RL + BackEuler C)...")

        # trapezoidal series (RL)
        factor_L = 2.0 / (w * h)
        Z_series = R + L * factor_L
        Gc_series = np.linalg.inv(Z_series)

        # shunt branch (C) with backward euler
        # (The Backward Euler method damps numerical oscillations in voltage nodes)
        factor_C = 1.0 / (w * h)
        Gc_shunt = C * factor_C

        # matrix assignation

        # Gc: only series part (calculate series history in driver)
        Gc = Gc_series
        H = np.zeros_like(Gc)

        # G_shunt: stored temporally to map
        G_shunt = Gc_shunt
    else:

        if verbose > 0:
            print("  > Configuring Matrices for BERGERON/JMARTI Model...")

        # Bergeron Model: Z = Zc + R/4
        Z_eq = np.real(Zc) + R / 4
        Gc = np.linalg.inv(Z_eq)
        H = (np.real(Zc) - R / 4) @ Gc

        if verbose > 0:
            print(f'Z line= {Z_eq}[p.u.]')
            print(f'Gc line= {Gc}[p.u.]')
            print(f'H line= {H}[p.u.]')

        G_shunt = np.zeros_like(Gc)  # Bergeron doesn't have explicit shunt in G

    all_phases = ['n', 'a', 'b', 'c']
    # convert Gc to a 4x4 matrix with 0 in the rows and cols of nonexistent phases
    loc_index = {ph: i for i, ph in enumerate(phases)}

    Gc4: Mat = np.zeros((4, 4), dtype=float)
    H4: Mat = np.zeros((4, 4), dtype=float)
    G_shunt4: Mat = np.zeros((4, 4), dtype=float)  # Necesario para Pi

    phase_idx = np.where(phases)[0]
    Gc4[np.ix_(phase_idx, phase_idx)] = Gc
    H4[np.ix_(phase_idx, phase_idx)] = H

    if line.emt_model_type == EmtLineTypes.PI:
        G_shunt4[np.ix_(phase_idx, phase_idx)] = G_shunt

    # for i, phi in enumerate(all_phases):
    #     if phi in phases:
    #         i_small = loc_index[phi]
    #         for j, phj in enumerate(all_phases):
    #             if phj in phases:
    #                 j_small = loc_index[phj]
    #                 Gc4[i, j] = Gc[i_small, j_small]
    #                 H4[i, j] = H[i_small, j_small]
    #                 if line.emt_model_type == EmtLineTypes.PI:
    #                     G_shunt4[i, j] = G_shunt[i_small, j_small]

    dta.H[k4, :] = H4  # NxN H has no units
    dta.Gc[k4, :] = Gc4  # Device conductance (Serie en Pi, Característica en Bergeron)

    # nodal matrix (Gff, Gtt, Gft, Gtf)
    if line.emt_model_type == EmtLineTypes.PI:
        # For Pi, Gff = G_serie + G_shunt
        # dta.Gff[k4, :] = Gc4 + G_shunt4  # TODO: should this be G_shunt4 / 2 ?
        # dta.Gtt[k4, :] = Gc4 + G_shunt4  # TODO: should this be G_shunt4 / 2 ?

        # In the π model, the nodes are COUPLED. Gft = -G_serie
        # dta.Gft[k4, :] = -1.0 * Gc4
        # dta.Gtf[k4, :] = -1.0 * Gc4

        # In the π model,  Ndelay=1, τ=0 are enforced to prevent the driver from accessing distant buffers
        dta.tau[ii] = 0.0
        dta.n_delay[ii] = 1

        Gff = Gc4 + G_shunt4
        Gft = -Gc4

        # Gff, Gft, Gtf, Gtt
        return Gff, Gft, Gft, Gff

    elif line.emt_model_type == EmtLineTypes.Bergeron:

        # Bergeron, Gff = Gc (Self components)
        # dta.Gff[k4, :] = Gc4
        # dta.Gtt[k4, :] = Gc4

        # Bergeron, nodes are uncoupled  en t (Gft=0)
        # NOTE: No need since it is already zeroed
        # dta.Gft[k4, :] = np.zeros((4, 4), dtype=float)
        # dta.Gtf[k4, :] = np.zeros((4, 4), dtype=float)

        Gff = Gc4
        Gft = np.zeros((4, 4), dtype=float)

        # Gff, Gft, Gtf, Gtt
        return Gff, Gft, Gft, Gff

    elif line.emt_model_type == EmtLineTypes.J_Marti:

        # En Bergeron, Gff = Gc (Self components)
        # dta.Gff[k4, :] = Gc4
        # dta.Gtt[k4, :] = Gc4

        # En Bergeron, nodes are uncoupled  en t (Gft=0)
        # NOTE: No need since it is already zeroed
        # dta.Gft[k4, :] = np.zeros((4, 4), dtype=float)
        # dta.Gtf[k4, :] = np.zeros((4, 4), dtype=float)

        Gff = Gc4
        Gft = np.zeros((4, 4), dtype=float)

        # Gff, Gft, Gtf, Gtt
        return Gff, Gft, Gft, Gff

    else:
        raise ValueError(f"Emt model type not implemented {line.emt_model_type.value}")
