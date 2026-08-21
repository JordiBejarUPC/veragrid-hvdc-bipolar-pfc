# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

# AUTHORS: Josep Fanals Batllori and Santiago Peñate Vera
# CONTACT:  u1946589@campus.udg.edu and santiago.penate.vera@gmail.com
# thanks to Llorenç Fanals Batllori for his help at coding
import pandas as pd
import numpy as np
import numba as nb
import time
from warnings import warn
from scipy.sparse import csc_matrix, coo_matrix
from scipy.sparse import hstack as hs, vstack as vs
from scipy.sparse.linalg import spsolve, factorized

from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
import VeraGridEngine.Simulations.PowerFlow.NumericalMethods.common_functions as cf
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.discrete_controls import (control_q_inside_method,
                                                                                     compute_slack_distribution)
from VeraGridEngine.basic_structures import Logger, CscMat, CxVec, IntVec, Vec


def epsilon(Sn, n, E):
    """
    Fast recursive Wynn's epsilon algorithm from:
        NONLINEAR SEQUENCE TRANSFORMATIONS FOR THE ACCELERATION OF CONVERGENCE
        AND THE SUMMATION OF DIVERGENT SERIES

        by Ernst Joachim Weniger
    Args:
        Sn: sum of coefficients
        n: order
        E: Coefficients structure copy that is modified in this algorithm

    Returns:

    """
    Zero = complex(0)
    One = complex(1)
    Tiny = np.finfo(complex).tiny  # np.finfo(complex).min
    Huge = np.finfo(complex).max

    E[n] = Sn

    if n == 0:
        estim = Sn
    else:
        AUX2 = Zero

        for j in range(n, 0, -1):  # range from n to 1 (both included)
            AUX1 = AUX2
            AUX2 = E[j - 1]
            DIFF = E[j] - AUX2

            if abs(DIFF) <= Tiny:
                E[j - 1] = Huge
            else:
                if DIFF == 0:
                    DIFF = Tiny
                E[j - 1] = AUX1 + One / DIFF

        if np.mod(n, 2) == 0:
            estim = E[0]
        else:
            estim = E[1]

    return estim, E


# @nb.njit("(c16[:])(i8, c16[:, :], f8)")
def pade4all(order, coeff_mat, s=1.0):
    """
    Computes the "order" Padè approximant of the coefficients at the approximation point s

    Arguments:
        coeff_mat: coefficient matrix (order, buses)
        order:  order of the series
        s: point of approximation (at 1 you get the voltage)

    Returns:
        Padè approximation at s for all the series
    """
    nbus = coeff_mat.shape[1]

    # complex_type = nb.complex128
    complex_type = np.complex128

    voltages = np.zeros(nbus, dtype=complex_type)

    nn = int(order / 2)
    L = nn
    M = nn

    for d in range(nbus):

        # formation of the linear system right hand side
        rhs = coeff_mat[L + 1:L + M + 1, d]

        # formation of the coefficients matrix
        C = np.zeros((L, M), dtype=complex_type)
        for i in range(L):
            k = i + 1
            C[i, :] = coeff_mat[L - M + k:L + k, d]

        # Obtaining of the b coefficients for orders greater than 0
        b = np.zeros(rhs.shape[0] + 1, dtype=complex_type)
        x = np.linalg.solve(C, -rhs)  # bn to b1
        b[0] = 1
        b[1:] = x[::-1]

        # Obtaining of the coefficients 'a'
        a = np.zeros(L + 1, dtype=complex_type)
        a[0] = coeff_mat[0, d]
        for i in range(L):
            val = complex_type(0)
            k = i + 1
            for j in range(k + 1):
                val += coeff_mat[k - j, d] * b[j]
            a[i + 1] = val

        # evaluation of the function for the value 's'
        p = complex_type(0)
        q = complex_type(0)
        for i in range(L + 1):
            p += a[i] * s ** i
            q += b[i] * s ** i

        voltages[d] = p / q

    return voltages


# @nb.njit("(c16[:])(c16[:, :], c16[:, :], i8, c16[:])")
@nb.njit(cache=True)
def sigma_function(coeff_matU, coeff_matX, order, V_slack):
    """

    :param coeff_matU: array with voltage coefficients
    :param coeff_matX: array with inverse conjugated voltage coefficients
    :param order: should be prof - 1
    :param V_slack: slack bus voltage vector. Must contain only 1 slack bus
    :return: sigma complex value
    """
    if len(V_slack) > 1:
        print('Sigma values may not be correct')
    V0 = V_slack[0]
    coeff_matU = coeff_matU / V0
    coeff_matX = coeff_matX / V0
    nbus = coeff_matU.shape[1]
    complex_type = nb.complex128
    # complex_type = complex
    sigmas = np.zeros(nbus, dtype=complex_type)

    if order % 2 == 0:
        M = int(order / 2) - 1
    else:
        M = int(order / 2)

    for d in range(nbus):
        a = coeff_matU[1:2 * M + 2, d]
        b = coeff_matX[0:2 * M + 1, d]
        C = np.zeros((2 * M + 1, 2 * M + 1), dtype=complex_type)

        for i in range(2 * M + 1):
            if i < M:
                C[1 + i:, i] = a[:2 * M - i]
            else:
                C[i - M:, i] = - b[:3 * M - i + 1]

        lhs = np.linalg.solve(C, -a)

        sigmas[d] = np.sum(lhs[M:]) / (np.sum(lhs[:M]) + 1)

    return sigmas


# @nb.njit("(c16[:])(c16[:, :], c16[:, :], i8, i8[:])")
@nb.njit(cache=True)
def conv1_old(A, B, c, indices):
    """
    Performs the convolution of A* and B
    :param A: Coefficients matrix 1 (orders, buses)
    :param B: Coefficients matrix 2 (orders, buses)
    :param c: order of the coefficients
    :param indices: bus indices array
    :return: Array with the convolution for the buses given by "indices"
    """
    suma = np.zeros(len(indices), dtype=nb.complex128)
    for k in range(1, c + 1):
        for i, d in enumerate(indices):
            suma[i] += np.conj(A[k, d]) * B[c - k, d]
    return suma


# @nb.njit("(c16[:])(c16[:, :], c16[:, :], i8)")
@nb.njit(cache=True)
def conv1(A, B, c):
    """
    Performs the convolution of A* and B
    :param A: Coefficients matrix 1 (orders, buses)
    :param B: Coefficients matrix 2 (orders, buses)
    :param c: order of the coefficients
    :return: Array with the convolution for the buses given by "indices"
    """
    suma = np.zeros(A.shape[1], dtype=nb.complex128)
    for k in range(1, c + 1):
        for i in range(A.shape[1]):
            suma[i] += np.conj(A[k, i]) * B[c - k, i]
    return suma


# @nb.njit("(c16[:])(c16[:, :], c16[:, :], i8, i8[:])")
@nb.njit(cache=True)
def conv2(A, B, c, indices):
    """
    Performs the convolution of A and B
    :param A: Coefficients matrix 1 (orders, buses)
    :param B: Coefficients matrix 2 (orders, buses)
    :param c: order of the coefficients
    :param indices: bus indices array
    :return: Array with the convolution for the buses given by "indices"
    """
    suma = np.zeros(len(indices), dtype=nb.complex128)
    for k in range(1, c):
        for i, d in enumerate(indices):
            suma[i] += A[k, d] * B[c - 1 - k, d]
    return suma


# @nb.njit("(c16[:])(c16[:, :], c16[:, :], i8, i8[:])")
@nb.njit(cache=True)
def conv3(A, B, c, indices):
    """
    Performs the convolution of A and B*
    :param A: Coefficients matrix 1 (orders, buses)
    :param B: Coefficients matrix 2 (orders, buses)
    :param c: order of the coefficients
    :param indices: bus indices array
    :return: Array with the convolution for the buses given by "indices"
    """
    suma = np.zeros(len(indices), dtype=nb.complex128)
    for k in range(1, c):
        for i, d in enumerate(indices):
            suma[i] += A[k, d] * np.conj(B[c - k, d])
    return suma


def helm_coefficients_josep(Ybus: CscMat, Yseries: CscMat, V0: CxVec, S0: CxVec, Ysh0: CxVec,
                            pq: IntVec, pv: IntVec, sl: IntVec, no_slack: IntVec,
                            tolerance=1e-6, max_coeff=30, verbose=False, stop_if_too_bad=False,
                            logger: Logger = None):
    """
    Holomorphic Embedding LoadFlow Method as formulated by Josep Fanals Batllori in 2020
    This function just returns the coefficients for further usage in other routines
    :param Ybus: Admittance matrix
    :param Yseries: Admittance matrix of the series elements
    :param V0: vector of specified voltages
    :param S0: vector of specified power
    :param Ysh0: vector of shunt admittances (including the shunts of the Branches)
    :param pq: list of pq nodes
    :param pv: list of pv nodes
    :param sl: list of slack nodes
    :param no_slack: sorted list of pq and pv nodes
    :param tolerance: target error (or tolerance)
    :param max_coeff: maximum number of coefficients
    :param verbose: print intermediate information
    :param stop_if_too_bad: stop when things go wrong
    :param logger: Logger object to store the debug info
    :return: U, X, Q, V, iterations
    """

    n_no_slack = len(no_slack)
    npv = len(pv)
    nsl = len(sl)
    n = Yseries.shape[0]

    # --------------------------- PREPARING IMPLEMENTATION -------------------------------------------------------------
    U = np.zeros((max_coeff + 1, n_no_slack), dtype=complex)  # voltages
    X = np.zeros((max_coeff + 1, n_no_slack), dtype=complex)  # compute X=1/conj(U)
    Q = np.zeros((max_coeff + 1, n_no_slack), dtype=complex)  # unknown reactive powers

    if n < 2:
        # U, X, Q, V, iter_, converged
        return U, X, Q, V0, 0, False

    if verbose:
        logger.add_debug('Yseries', Yseries.toarray())

        df = pd.DataFrame(data=np.c_[Ysh0.imag, S0.real, S0.imag, np.abs(V0)],
                          columns=['Ysh', 'P0', 'Q0', 'V0'])
        logger.add_debug(df.to_string())

    # build the reduced system
    Yred = Yseries[np.ix_(no_slack, no_slack)]  # admittance matrix without slack buses
    Yslack = -Yseries[np.ix_(no_slack, sl)]  # yes, it is the negative of this
    G = Yred.real.copy()  # real parts of Yij
    B = Yred.imag.copy()  # imaginary parts of Yij
    vec_P = S0.real[no_slack]
    vec_Q = S0.imag[no_slack]
    Vslack = V0[sl]
    Ysh = Ysh0[no_slack]
    Vm0 = np.abs(V0[no_slack])
    vec_W = Vm0 * Vm0

    # indices 0 based in the internal scheme
    nsl_counted = np.zeros(n, dtype=int)
    compt = 0
    for i in range(n):
        if i in sl:
            compt += 1
        nsl_counted[i] = compt

    pq_ = pq - nsl_counted[pq]
    pv_ = pv - nsl_counted[pv]

    # .......................CALCULATION OF TERMS [0] ------------------------------------------------------------------

    if nsl > 1:
        U[0, :] = spsolve(Yred, Yslack.sum(axis=1))
    else:
        U[0, :] = spsolve(Yred, Yslack)

    # if U[0, :].real != 0.0 and U[0, :].imag != 0.0:
    X[0, :] = 1 / np.conj(U[0, :])

    # .......................CALCULATION OF TERMS [1] ------------------------------------------------------------------
    valor = np.zeros(n_no_slack, dtype=complex)

    # get the current Injections that appear due to the slack buses reduction
    # `@ Vslack` can leave a column-shaped result; ravel() makes it a plain 1-D vector for `valor[...]`.
    I_inj_slack_pq = np.asarray(Yslack[pq_, :] @ Vslack).ravel()
    I_inj_slack_pv = np.asarray(Yslack[pv_, :] @ Vslack).ravel()

    valor[pq_] = (I_inj_slack_pq
                  - Yslack[pq_].sum(axis=1).A1
                  + (vec_P[pq_] - vec_Q[pq_] * 1j) * X[0, pq_]
                  - U[0, pq_] * Ysh[pq_])

    valor[pv_] = (I_inj_slack_pv
                  - Yslack[pv_].sum(axis=1).A1
                  + (vec_P[pv_]) * X[0, pv_]
                  - U[0, pv_] * Ysh[pv_])

    # compose the right-hand side vector
    RHS = np.r_[
        valor.real,
        valor.imag,
        vec_W[pv_] - (U[0, pv_] * U[0, pv_]).real  # vec_W[pv_] - 1.0
    ]

    # Form the system matrix (MAT)
    Upv = U[0, pv_]
    Xpv = X[0, pv_]
    VRE = coo_matrix((2 * Upv.real, (np.arange(npv), pv_)), shape=(npv, n_no_slack)).tocsc()
    VIM = coo_matrix((2 * Upv.imag, (np.arange(npv), pv_)), shape=(npv, n_no_slack)).tocsc()
    XIM = coo_matrix((-Xpv.imag, (pv_, np.arange(npv))), shape=(n_no_slack, npv)).tocsc()
    XRE = coo_matrix((Xpv.real, (pv_, np.arange(npv))), shape=(n_no_slack, npv)).tocsc()
    EMPTY = csc_matrix((npv, npv))

    MAT = vs(
        (hs((G, -B, XIM)),
         hs((B, G, XRE)),
         hs((VRE, VIM, EMPTY))),
        format='csc'
    )

    if verbose:
        logger.add_debug("MAT", MAT.toarray())

    # factorize (only once)
    # MAT_LU = factorized(MAT.tocsc())

    # solve
    try:
        mat_factorized = factorized(MAT)
    except RuntimeError:
        warn("Unable to factorize HELM coefficients matrix :/")
        return U, X, Q, V0, 0, False

    LHS = mat_factorized(RHS)
    # LHS = spsolve(MAT, RHS)

    # update coefficients
    U[1, :] = LHS[:n_no_slack] + 1j * LHS[n_no_slack:2 * n_no_slack]
    Q[0, pv_] = LHS[2 * n_no_slack:]
    X[1, :] = -X[0, :] * np.conj(U[1, :]) / np.conj(U[0, :])

    # .......................CALCULATION OF TERMS [>=2] ----------------------------------------------------------------
    iter_ = 1
    c = 2
    norm_f_prev = 1e20
    converged = False
    V = np.empty(n, dtype=complex)
    V[sl] = V0[sl]
    V[no_slack] = U[:c, :].sum(axis=0)

    a = n_no_slack
    b = 2 * n_no_slack

    while c <= max_coeff and not converged:  # c defines the current depth

        valor[pq_] = (vec_P[pq_] - vec_Q[pq_] * 1j) * X[c - 1, pq_] - U[c - 1, pq_] * Ysh[pq_]
        valor[pv_] = -1j * conv2(X, Q, c, pv_) - U[c - 1, pv_] * Ysh[pv_] + X[c - 1, pv_] * vec_P[pv_]

        RHS = np.r_[
            valor.real,
            valor.imag,
            -conv3(U, U, c, pv_).real
        ]

        # LHS = spsolve(MAT, RHS)
        LHS = mat_factorized(RHS)

        # update voltage coefficients
        U[c, :] = LHS[:a] + 1j * LHS[a:b]

        # update reactive power
        Q[c - 1, pv_] = LHS[b:]

        # update voltage inverse coefficients
        X[c, :] = -conv1(U, X, c) / np.conj(U[0, :])

        # compute power mismatch
        V[no_slack] += U[c, :]

        if stop_if_too_bad:
            # usually we want to go this route for power flows
            if V.real.max() < 10:
                Scalc = cf.compute_power(Ybus, V)
                norm_f = cf.compute_fx_error(cf.compute_fx(Scalc, S0, no_slack, pq))
                converged = (norm_f <= tolerance) and (c % 2)  # we want an odd amount of coefficients

                if norm_f > norm_f_prev:
                    return U[c - 1, :], X[c - 1, :], Q[c - 1, :], V, iter_ - 1, converged

                norm_f_prev = norm_f
            else:
                # completely erroneous
                return U[c - 1, :], X[c - 1, :], Q[c - 1, :], V, iter_ - 1, converged
        else:
            # usually we want to go this route for sigma analysis
            Scalc = cf.compute_power(Ybus, V)
            norm_f = cf.compute_fx_error(cf.compute_fx(Scalc, S0, no_slack, pq))
            converged = (norm_f <= tolerance) and (c % 2)  # we want an odd amount of coefficients

        iter_ += 1
        c += 1

    return U, X, Q, V, iter_, converged


class HelmPreparation:
    """
    HelmPreparation
    """

    def __init__(self, sys_mat_factorization, Uini, Xini, Yslack, Vslack,
                 vec_P, vec_Q, Ysh, vec_W, pq, pv, pqpv, sl,
                 npqpv, nbus, pqpv_original, pq_original):
        """

        :param sys_mat_factorization:
        :param Uini:
        :param Xini:
        :param Yslack:
        :param Vslack:
        :param vec_P:
        :param vec_Q:
        :param Ysh:
        :param vec_W:
        :param pq:
        :param pv:
        :param pqpv:
        :param sl:
        :param npqpv:
        :param nbus:
        :param pqpv_original:
        """
        self.sys_mat_factorization = sys_mat_factorization
        self.Uini = Uini
        self.Xini = Xini
        self.Yslack = Yslack
        self.Vslack = Vslack
        self.vec_P = vec_P
        self.vec_Q = vec_Q
        self.Ysh = Ysh
        self.vec_W = vec_W
        self.pq = pq
        self.pv = pv
        self.sl = sl
        self.pqpv = pqpv
        self.npqpv = npqpv
        self.nbus = nbus
        self.pqpv_original = pqpv_original
        self.pq_original = pq_original


def helm_preparation_dY(Yseries, V0, S0, Ysh0, pq, pv, sl, pqpv, verbose: int = 0,
                        logger: Logger = None) -> HelmPreparation:
    """
    This function returns the constant objects to run many HELM simulations

    Based on the paper: Novel AC Distribution Factor for Efficient Outage Analysis
                        Rui Yao, Senior Member, IEEE, and Feng Qiu, Senior Member, IEEE

    :param Yseries: Admittance matrix of the series elements
    :param V0: vector of specified voltages
    :param S0: vector of specified power
    :param Ysh0: vector of shunt admittances (including the shunts of the Branches)
    :param pq: list of pq nodes
    :param pv: list of pv nodes
    :param sl: list of slack nodes
    :param pqpv: sorted list of pq and pv nodes
    :param verbose: print intermediate information
    :param logger: Logger object to store the debug info
    :return: U, X, Q, V, iterations
    """

    npqpv = len(pqpv)
    npv = len(pv)
    nsl = len(sl)
    nbus = Yseries.shape[0]

    # --------------------------- PREPARING IMPLEMENTATION -------------------------------------------------------------

    # build the reduced system
    Yred = Yseries[np.ix_(pqpv, pqpv)]  # admittance matrix without slack buses
    Yslack = -Yseries[np.ix_(pqpv, sl)]  # yes, it is the negative of this
    G = Yred.real.copy()  # real parts of Yij
    B = Yred.imag.copy()  # imaginary parts of Yij
    vec_P = S0.real[pqpv]
    vec_Q = S0.imag[pqpv]
    Vslack = V0[sl]
    Ysh = Ysh0[pqpv]
    Vm0 = np.abs(V0[pqpv])
    vec_W = Vm0 * Vm0

    # indices 0 based in the internal scheme
    nsl_counted = np.zeros(nbus, dtype=int)
    compt = 0
    for i in range(nbus):
        if i in sl:
            compt += 1
        nsl_counted[i] = compt

    pqpv_original = np.sort(np.r_[pq, pv])
    pq_original = np.sort(np.r_[pq])

    pq_ = pq - nsl_counted[pq]
    pv_ = pv - nsl_counted[pv]
    pqpv_ = np.sort(np.r_[pq_, pv_])

    # .......................CALCULATION OF TERMS [0] ------------------------------------------------------------------
    if nsl > 1:
        Uini = spsolve(Yred, Yslack.sum(axis=1))
    else:
        Uini = spsolve(Yred, Yslack)

    Xini = 1 / Uini

    # .......................CALCULATION OF THE MATRIX -----------------------------------------------------------------
    Upv = Uini[pv_]
    Xpv = Xini[pv_]
    VRE = coo_matrix((2 * Upv.real, (np.arange(npv), pv_)), shape=(npv, npqpv)).tocsc()
    VIM = coo_matrix((2 * Upv.imag, (np.arange(npv), pv_)), shape=(npv, npqpv)).tocsc()
    XIM = coo_matrix((-Xpv.imag, (pv_, np.arange(npv))), shape=(npqpv, npv)).tocsc()
    XRE = coo_matrix((Xpv.real, (pv_, np.arange(npv))), shape=(npqpv, npv)).tocsc()
    EMPTY = csc_matrix((npv, npv))

    MAT = vs((hs((G, -B, XIM)),
              hs((B, G, XRE)),
              hs((VRE, VIM, EMPTY))), format='csc')

    if verbose:
        logger.add_debug("MAT", MAT.toarray())

    # solve
    mat_factorized = factorized(MAT)

    return HelmPreparation(mat_factorized, Uini, Xini, Yslack, Vslack, vec_P, vec_Q, Ysh, vec_W,
                           pq_, pv_, pqpv_, sl, npqpv, nbus, pqpv_original, pq_original)


def helm_coefficients_dY(dY, sys_mat_factorization, Uini, Xini,
                         Yslack, Ysh, Ybus, vec_P, vec_Q, S0,
                         vec_W, V0, Vslack, pq, pv, pqpv, npqpv, nbus, sl, 
                         pqpv_original, pq_original, 
                         tolerance=1e-6, max_coeff=10):
    """
    Holomorphic Embedding LoadFlow Method as formulated by Josep Fanals Batllori in 2020
    This function just returns the coefficients for further usage in other routines

    Based on the paper: Novel AC Distribution Factor for Efficient Outage Analysis
                        Rui Yao, Senior Member, IEEE, and Feng Qiu, Senior Member, IEEE

    :param dY:
    :param sys_mat_factorization: factorized HELM system matrix
    :param Uini:
    :param Xini:
    :param Yslack:
    :param Ysh:
    :param Ybus:
    :param vec_P:
    :param vec_Q:
    :param S0: vector of specified power
    :param vec_W:
    :param V0: vector of specified voltages
    :param Vslack:
    :param pq: reduced scheme list of pq nodes
    :param pv: reduced scheme list of pv nodes
    :param pqpv: reduced scheme list of pq|pv nodes
    :param npqpv: number of pq and pv nodes
    :param nbus: number of nodes
    :param pqpv: sorted list of pq and pv nodes
    :param pq:list of pq nodes
    :param sl: list of slack nodes
    :param pqpv_original: sorted list of pq and pv nodes in the original order, considering slack
    :param pq_original: list of pq nodes in the original order, considering slack
    :param tolerance: target error (or tolerance)
    :param max_coeff: maximum number of coefficients
    :return: U, V, iter_, norm_f
    """

    AYred = dY[np.ix_(pqpv_original, pqpv_original)]  # difference admittance matrix without slack buses
    AYsl = dY[np.ix_(pqpv_original, sl)]  # difference admittance matrix involving slack buses

    # --------------------------- PREPARING IMPLEMENTATION -------------------------------------------------------------
    U = np.zeros((max_coeff + 1, npqpv), dtype=complex)  # voltages
    X = np.zeros((max_coeff + 1, npqpv), dtype=complex)  # compute X=1/conj(U)
    Q = np.zeros((max_coeff + 1, npqpv), dtype=complex)  # unknown reactive powers

    # .......................CALCULATION OF TERMS [0] ------------------------------------------------------------------
    U[0, :] = Uini
    X[0, :] = Xini

    # .......................CALCULATION OF TERMS [1] ------------------------------------------------------------------
    dval = np.zeros(npqpv, dtype=complex)

    # get the current Injections that appear due to the slack buses reduction
    I_inj_slack = Yslack[pqpv, :] * Vslack
    AI_inj_slack = AYsl[pqpv, :] * Vslack

    Ysl_sum = Yslack.sum(axis=1).A1
    AYsl_sum = AYsl.sum(axis=1).A1

    AIred = AYred @ U[0, :]

    dval[pq] = I_inj_slack[pq] + 1.0 * AI_inj_slack[pq] - Ysl_sum[pq] + (vec_P[pq] - vec_Q[pq] * 1j) * X[0, pq] - U[0, pq] * Ysh[pq] + 1.0 * AIred[pq]
    dval[pv] = I_inj_slack[pv] + 1.0 * AI_inj_slack[pv] - Ysl_sum[pv] + (vec_P[pv]) * X[0, pv] - U[0, pv] * Ysh[pv] + 1.0 * AIred[pv]

    # compose the right-hand side vector
    RHS = np.r_[dval.real, dval.imag, vec_W[pv] - (U[0, pv] * U[0, pv]).real]  # vec_W[pv_] - 1.0

    LHS = sys_mat_factorization(RHS)

    # update coefficients
    U[1, :] = LHS[:npqpv] + 1j * LHS[npqpv:2 * npqpv]
    Q[0, pv] = LHS[2 * npqpv:]
    X[1, :] = -X[0, :] * np.conj(U[1, :]) / np.conj(U[0, :])

    # .......................CALCULATION OF TERMS [>=2] ----------------------------------------------------------------
    iter_ = 1
    c = 2
    converged = False
    # V = np.empty(nbus, dtype=complex)
    # V[sl] = V0[sl]
    # V[pqpv] = U[:c, :].sum(axis=0)

    # Need the rebuild the voltage vector, as the passed pqpv indices are already reduced    
    V = np.zeros(nbus, dtype=complex)
    V[sl] = V0[sl]
    V[pqpv_original] = U[:c, :].sum(axis=0)

    norm_f = 0.0

    while c <= max_coeff and not converged:  # c defines the current depth

        AIred = AYred @ U[c - 1, :]

        dval[pq] = (vec_P[pq] - vec_Q[pq] * 1j) * X[c - 1, pq] - U[c - 1, pq] * Ysh[pq] + 1.0 * AIred[pq]
        dval[pv] = -1j * conv2(X, Q, c, pv) - U[c - 1, pv] * Ysh[pv] + X[c - 1, pv] * vec_P[pv] + 1.0 * AIred[pv]

        RHS = np.r_[dval.real, dval.imag, -conv3(U, U, c, pv).real]

        # LHS = spsolve(MAT, RHS)
        LHS = sys_mat_factorization(RHS)

        # update 
        U[c, :] = LHS[:npqpv] + 1j * LHS[npqpv:2 * npqpv]
        Q[c - 1, pv] = LHS[2 * npqpv:]
        X[c, :] = -conv1(U, X, c) / np.conj(U[0, :])

        # compute power mismatch
        V[pqpv_original] += U[c, :]

        if V.real.max() < 10:
            Scalc = cf.compute_power(Ybus - dY, V)
            norm_f = cf.compute_fx_error(cf.compute_fx(Scalc, S0, pqpv_original, pq_original))
            converged = (norm_f <= tolerance) and (c % 2)  # we want an odd amount of coefficients
        else:
            # completely erroneous
            break

        iter_ += 1
        c += 1

    return U, V, iter_, norm_f


def helm_josep(nc: NumericalCircuit,
               Ybus: CscMat, Yf: CscMat, Yt: CscMat, Yshunt_bus: CxVec,
               Yseries: CscMat, V0: CxVec, S0: CxVec, Ysh0: CxVec,
               pq: IntVec, pv: IntVec, vd: IntVec, no_slack: IntVec,
               tolerance: float = 1e-6, max_coefficients: int = 30, use_pade: bool = True,
               verbose: int = 0, logger: Logger = None) -> NumericPowerFlowResults:
    """
    Holomorphic Embedding LoadFlow Method as formulated by Josep Fanals Batllori in 2020
    :param nc: NumericalCircuit
    :param Ybus: Complete admittance matrix
    :param Yf: admittance from matrix
    :param Yt: admittance to matrix
    :param Yseries: Admittance matrix of the series elements
    :param V0: vector of specified voltages
    :param S0: vector of specified power
    :param Ysh0: vector of shunt admittances (including the shunt "legs" of the pi Branches)
    :param pq: list of pq nodes
    :param pv: list of pv nodes
    :param vd: list of slack nodes
    :param no_slack: sorted list of pq and pv nodes
    :param tolerance: target error (or tolerance)
    :param max_coefficients: maximum number of coefficients
    :param use_pade: Use the Padè approximation? otherwise, a simple summation is done
    :param verbose: print intermediate information
    :param logger: Logger object to store the debug info
    :return: V, converged, norm_f, Scalc, iter_, elapsed
    """

    start_time = time.time()

    if nc.bus_data.nbus < 2:
        return NumericPowerFlowResults(V=V0,
                                       Scalc=S0,
                                       m=np.ones(nc.nbr, dtype=float),
                                       tau=np.zeros(nc.nbr, dtype=float),
                                       Sf=np.zeros(nc.nbr, dtype=complex),
                                       St=np.zeros(nc.nbr, dtype=complex),
                                       If=np.zeros(nc.nbr, dtype=complex),
                                       It=np.zeros(nc.nbr, dtype=complex),
                                       loading=np.zeros(nc.nbr, dtype=complex),
                                       losses=np.zeros(nc.nbr, dtype=complex),
                                       Pfp_vsc=np.zeros(nc.nvsc, dtype=float),
                                       Pfn_vsc=np.zeros(nc.nvsc, dtype=float),
                                       St_vsc=np.zeros(nc.nvsc, dtype=complex),
                                       If_vsc=np.zeros(nc.nvsc, dtype=float),
                                       It_vsc=np.zeros(nc.nvsc, dtype=complex),
                                       losses_vsc=np.zeros(nc.nvsc, dtype=float),
                                       loading_vsc=np.zeros(nc.nvsc, dtype=float),
                                       Sf_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                       St_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                       losses_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                       loading_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                       norm_f=0.0,
                                       converged=False,
                                       iterations=0,
                                       elapsed=0.0)

    # compute the series of coefficients
    U, X, Q, V, iter_, converged = helm_coefficients_josep(Ybus=Ybus,
                                                           Yseries=Yseries,
                                                           V0=V0,
                                                           S0=S0,
                                                           Ysh0=Ysh0,
                                                           pq=pq,
                                                           pv=pv,
                                                           sl=vd,
                                                           no_slack=no_slack,
                                                           tolerance=tolerance,
                                                           max_coeff=max_coefficients,
                                                           verbose=bool(verbose),
                                                           stop_if_too_bad=True,
                                                           logger=logger)

    # --------------------------- RESULTS COMPOSITION ------------------------------------------------------------------
    if verbose:
        logger.add_debug('V coefficients\n', U)

    # compute the final voltage vector
    if use_pade:
        V = V0.copy()
        try:
            V[no_slack] = pade4all(max_coefficients - 1, U, 1)
        except RuntimeError:
            warn('Padè failed :(, using coefficients summation')
            V[no_slack] = U.sum(axis=0)

    # compute power mismatch
    Scalc = cf.compute_power(Ybus, V)
    norm_f = cf.compute_fx_error(cf.compute_fx(Scalc, S0, no_slack, pq))

    # check convergence
    converged = norm_f < tolerance

    elapsed = time.time() - start_time

    # Compute the Branches power and the slack buses power
    Sf, St, If, It, Vbranch, loading, losses, Sbus = cf.power_flow_post_process_nonlinear(
        Sbus=Scalc,
        V=V,
        F=nc.passive_branch_data.F,
        T=nc.passive_branch_data.T,
        pv=pv,
        vd=vd,
        Ybus=Ybus,
        Yf=Yf,
        Yt=Yt,
        Yshunt_bus=Yshunt_bus,
        branch_rates=nc.passive_branch_data.rates,
        Sbase=nc.Sbase
    )

    return NumericPowerFlowResults(
        V=V,
        Scalc=Scalc * nc.Sbase,
        m=np.ones(nc.nbr, dtype=float),
        tau=np.zeros(nc.nbr, dtype=float),
        Sf=Sf,
        St=St,
        If=If,
        It=It,
        loading=loading,
        losses=losses,
        Pfp_vsc=np.zeros(nc.nvsc, dtype=float),
        Pfn_vsc=np.zeros(nc.nvsc, dtype=float),
        St_vsc=np.zeros(nc.nvsc, dtype=complex),
        If_vsc=np.zeros(nc.nvsc, dtype=float),
        It_vsc=np.zeros(nc.nvsc, dtype=complex),
        losses_vsc=np.zeros(nc.nvsc, dtype=float),
        loading_vsc=np.zeros(nc.nvsc, dtype=float),
        Sf_hvdc=np.zeros(nc.nhvdc, dtype=complex),
        St_hvdc=np.zeros(nc.nhvdc, dtype=complex),
        losses_hvdc=np.zeros(nc.nhvdc, dtype=complex),
        loading_hvdc=np.zeros(nc.nhvdc, dtype=complex),
        norm_f=norm_f,
        converged=converged,
        iterations=iter_,
        elapsed=elapsed
    )


# =====================================================================================================================
# Dynamic Power Restart HELM (DPRHEM)
#
# This section intentionally lives in the same module as a full copy of the base HELM implementation.  The copied base
# functions above make it easy to compare each modified DPRHEM step against Josep's original coefficient recursion.
# =====================================================================================================================
from scipy.sparse import diags as dpr_diags


class DprSegmentResult:
    """
    Result of one DPRHEM segment.

    :param U: Voltage coefficients in reduced no-slack coordinates.
    :param X: Reciprocal-conjugate voltage coefficients in reduced no-slack coordinates.
    :param Q: PV reactive power coefficients in reduced no-slack coordinates.
    :param V: Full voltage vector selected as the segment output.
    :param iterations: Number of computed/accepted coefficient orders.
    :param norm_f: Power-flow mismatch norm of ``V``.
    :param converged: True if ``norm_f`` satisfies the requested tolerance.
    :param improved: True if the segment found a better voltage than its input germ.
    """

    __slots__ = ("U", "X", "Q", "V", "iterations", "norm_f", "converged", "improved")

    def __init__(self,
                 U: np.ndarray,
                 X: np.ndarray,
                 Q: np.ndarray,
                 V: CxVec,
                 iterations: int,
                 norm_f: float,
                 converged: bool,
                 improved: bool) -> None:
        """
        Build the DPRHEM segment result.

        :param U: Voltage coefficients in reduced no-slack coordinates.
        :param X: Reciprocal-conjugate voltage coefficients in reduced no-slack coordinates.
        :param Q: PV reactive power coefficients in reduced no-slack coordinates.
        :param V: Full voltage vector selected as the segment output.
        :param iterations: Number of computed/accepted coefficient orders.
        :param norm_f: Power-flow mismatch norm of ``V``.
        :param converged: True if ``norm_f`` satisfies the requested tolerance.
        :param improved: True if the segment found a better voltage than its input germ.
        :return: None.
        """

        self.U: np.ndarray = U
        self.X: np.ndarray = X
        self.Q: np.ndarray = Q
        self.V: CxVec = V
        self.iterations: int = iterations
        self.norm_f: float = norm_f
        self.converged: bool = converged
        self.improved: bool = improved


def dpr_reduced_bus_indices(nbus: int, pq: IntVec, pv: IntVec, sl: IntVec) -> tuple[IntVec, IntVec, IntVec]:
    """
    Convert original bus indices into the reduced no-slack indexing used by HELM.

    :param nbus: Number of buses in the full island.
    :param pq: Original PQ bus indices.
    :param pv: Original PV bus indices.
    :param sl: Original slack bus indices.
    :return: Reduced PQ indices, reduced PV indices and original sorted non-slack indices.
    """

    nsl_counted: IntVec = np.zeros(nbus, dtype=int)
    slack_count: int = 0

    # Removing slack buses shifts every following original index in the reduced matrix.
    for bus_idx in range(nbus):
        if bus_idx in sl:
            slack_count += 1
        else:
            slack_count = slack_count

        nsl_counted[bus_idx] = slack_count

    pq_reduced: IntVec = pq - nsl_counted[pq]
    pv_reduced: IntVec = pv - nsl_counted[pv]
    pqpv_original: IntVec = np.sort(np.r_[pq, pv])

    return pq_reduced, pv_reduced, pqpv_original


def dpr_power_mismatch(Ybus: CscMat, V: CxVec, S0: CxVec, no_slack: IntVec, pq: IntVec) -> float:
    """
    Compute the VeraGrid power-flow mismatch norm.

    :param Ybus: Complete admittance matrix.
    :param V: Full voltage vector.
    :param S0: Specified complex bus powers.
    :param no_slack: Original non-slack bus indices.
    :param pq: Original PQ bus indices.
    :return: Power-flow mismatch norm.
    """

    Scalc: CxVec = cf.compute_power(Ybus, V)
    fx: np.ndarray = cf.compute_fx(Scalc, S0, no_slack, pq)
    norm_f: float = float(cf.compute_fx_error(fx))

    return norm_f


def dpr_angle_guard(V: CxVec, sl: IntVec, no_slack: IntVec) -> bool:
    """
    Apply the DPRHEM voltage-angle physical-branch guard.

    :param V: Full voltage vector to test.
    :param sl: Slack bus indices.
    :param no_slack: Non-slack bus indices.
    :return: True if all non-slack voltage angles are within +/- 90 degrees of the slack angle.
    """

    if len(sl) > 0:
        slack_angle: float = float(np.angle(V[sl[0]], deg=True))
    else:
        slack_angle = 0.0

    angle_diff: np.ndarray = np.angle(V[no_slack], deg=True) - slack_angle
    angle_diff = (angle_diff + 180.0) % 360.0 - 180.0
    allowed: bool = bool(np.all(angle_diff < 90.0) and np.all(angle_diff > -90.0))

    return allowed


def dpr_safe_voltage_germ(V: CxVec, no_slack: IntVec) -> CxVec:
    """
    Make a voltage germ safe for reciprocal-voltage calculations.

    :param V: Full voltage vector candidate.
    :param no_slack: Original non-slack bus indices.
    :return: Full voltage vector with non-zero non-slack entries.
    """

    Vgerm: CxVec = V.copy()
    voltage_abs: np.ndarray = np.abs(Vgerm[no_slack])
    bad: np.ndarray = voltage_abs < 1e-10

    if np.any(bad):
        Vgerm[no_slack[bad]] = 1.0 + 0.0j
    else:
        Vgerm = Vgerm

    return Vgerm


def dpr_classical_no_load_germ(Yseries: CscMat, Vset: CxVec, sl: IntVec, no_slack: IntVec, pv: IntVec) -> CxVec:
    """Paper-style classical germ: flat 1 p.u., with slack angle and PV magnitudes fixed."""

    Vgerm: CxVec = np.ones_like(Vset, dtype=complex)
    Vgerm[sl] = Vset[sl]

    return dpr_safe_voltage_germ(Vgerm, no_slack)


def dpr_known_inverse_voltage_coefficient(U: np.ndarray, X: np.ndarray, order: int) -> np.ndarray:
    """
    Compute the known part of ``X[order]`` before ``U[order]`` is solved.

    The copied base HELM formulation uses ``X(s) = 1 / conj(U(s))``.  At a given order, the part containing
    ``conj(U[order])`` is moved to the left-hand side of the DPRHEM matrix.  This function returns the remaining
    lower-order convolution.

    :param U: Voltage coefficients.
    :param X: Reciprocal-conjugate voltage coefficients.
    :param order: Coefficient order being solved.
    :return: Known lower-order contribution to ``X[order]``.
    """

    known: np.ndarray = np.zeros(U.shape[1], dtype=complex)

    # Accumulate only lower-order terms; the current-order unknown is kept in the matrix.
    for coeff_idx in range(1, order):
        known += np.conj(U[coeff_idx, :]) * X[order - coeff_idx, :]

    if order > 1:
        known = -known / np.conj(U[0, :])
    else:
        known = known

    return known


def dpr_residual_ratio(previous_norm: float, candidate_norm: float, tolerance: float) -> float:
    """
    Compute the residual-ratio indicator used by the DPRHEM restart rule.

    :param previous_norm: Previous order mismatch norm.
    :param candidate_norm: Current order mismatch norm.
    :param tolerance: Target mismatch tolerance.
    :return: Residual-ratio value.
    """

    denominator: float = previous_norm - tolerance

    if abs(denominator) > 1e-30:
        ratio: float = (previous_norm - candidate_norm) / denominator
    else:
        ratio = 0.0

    return ratio


def dpr_build_matrix(Yred: CscMat,
                     Ysh: CxVec,
                     U0: CxVec,
                     Sini_rhs: CxVec,
                     pv: IntVec,
                     npv: int,
                     npqpv: int) -> CscMat:
    """
    Build the real sparse DPRHEM segment matrix.

    The copied base HELM matrix is modified according to the paper's shifted-germ model: the initial physical power
    state ``Sini`` introduces a diagonal term multiplying ``conj(U[n])``.  The right-hand side then carries only
    lower-order terms and the direction power ``S_target - Sini``.

    :param Yred: Reduced series admittance matrix.
    :param Ysh: Reduced shunt admittance vector.
    :param U0: Segment voltage germ in reduced coordinates.
    :param Sini_rhs: Conjugated initial complex power in reduced coordinates.
    :param pv: Reduced PV bus indices.
    :param npv: Number of PV buses.
    :param npqpv: Number of non-slack buses.
    :return: Real sparse CSC matrix.
    """

    network_matrix: CscMat = (Yred + dpr_diags(Ysh, offsets=0, format="csc")).tocsc()
    gamma: CxVec = Sini_rhs / (np.conj(U0) * np.conj(U0))
    gamma_re: CscMat = dpr_diags(gamma.real, offsets=0, format="csc")
    gamma_im: CscMat = dpr_diags(gamma.imag, offsets=0, format="csc")

    # Real form of A*U + gamma*conj(U), with unknown vector [U.real, U.imag, Qpv].
    upper_left: CscMat = network_matrix.real + gamma_re
    upper_right: CscMat = -network_matrix.imag + gamma_im
    lower_left: CscMat = network_matrix.imag + gamma_im
    lower_right: CscMat = network_matrix.real - gamma_re

    X0: CxVec = 1.0 / np.conj(U0)
    XIM: CscMat = coo_matrix((-X0[pv].imag, (pv, np.arange(npv))), shape=(npqpv, npv)).tocsc()
    XRE: CscMat = coo_matrix((X0[pv].real, (pv, np.arange(npv))), shape=(npqpv, npv)).tocsc()
    VRE: CscMat = coo_matrix((2.0 * U0[pv].real, (np.arange(npv), pv)), shape=(npv, npqpv)).tocsc()
    VIM: CscMat = coo_matrix((2.0 * U0[pv].imag, (np.arange(npv), pv)), shape=(npv, npqpv)).tocsc()
    EMPTY: CscMat = csc_matrix((npv, npv))

    MAT: CscMat = vs(
        (hs((upper_left, upper_right, XIM)),
         hs((lower_left, lower_right, XRE)),
         hs((VRE, VIM, EMPTY))),
        format="csc"
    )

    return MAT


def dpr_select_candidate(Ybus: CscMat,
                         Vgerm: CxVec,
                         Vset: CxVec,
                         U: np.ndarray,
                         order: int,
                         sl: IntVec,
                         no_slack: IntVec,
                         pqpv_original: IntVec,
                         S0: CxVec,
                         pq: IntVec) -> tuple[CxVec, float, bool]:
    """
    Select the best valid truncated segment voltage.

    The paper evaluates at ``s = 1``.  The extra smaller scales are a guarded fallback for VeraGrid's very large
    PEGASE cases where the local segment radius is visibly below one; the selected state is still restarted through
    the same paper power-space update.

    :param Ybus: Complete admittance matrix.
    :param Vgerm: Full segment voltage germ.
    :param Vset: Full voltage set-point vector.
    :param U: Voltage coefficients.
    :param order: Highest available coefficient order.
    :param sl: Slack bus indices.
    :param no_slack: Non-slack bus indices.
    :param pqpv_original: Original sorted non-slack bus indices.
    :param S0: Specified power target.
    :param pq: Original PQ bus indices.
    :return: Candidate voltage, mismatch norm and validity flag.
    """

    Vcandidate: CxVec = Vgerm.copy()
    candidate_norm: float = np.inf
    candidate_ok: bool = False
    candidate_scales: np.ndarray = np.array([1.0, 0.5, 0.25, 0.1, 0.05, 0.01, 0.001], dtype=float)

    # Evaluate a few points on the same analytic segment and restart from the best physical one.
    for scale in candidate_scales:
        Uscaled: CxVec = U[0, :].copy()

        for scale_order in range(1, order + 1):
            Uscaled += U[scale_order, :] * scale ** scale_order

        candidates: list[CxVec] = [Uscaled]

        if scale == 1.0 and order >= 4 and order % 2 == 0:
            try:
                candidates.append(pade4all(order, U[:order + 1, :], s=scale))
            except Exception:
                candidates = candidates

        for Ucandidate in candidates:
            Vscaled: CxVec = Vgerm.copy()
            Vscaled[sl] = Vset[sl]
            Vscaled[pqpv_original] = Ucandidate

            scaled_norm: float = dpr_power_mismatch(Ybus, Vscaled, S0, no_slack, pq)
            scaled_ok: bool = bool(np.isfinite(scaled_norm) and dpr_angle_guard(Vscaled, sl, no_slack))

            if scaled_ok and scaled_norm < candidate_norm:
                Vcandidate = Vscaled
                candidate_norm = scaled_norm
                candidate_ok = True
            else:
                Vcandidate = Vcandidate

    return Vcandidate, candidate_norm, candidate_ok


def dpr_solve_segment(Ybus: CscMat,
                      Yseries: CscMat,
                      Vgerm: CxVec,
                      Vset: CxVec,
                      S0: CxVec,
                      Ysh0: CxVec,
                      pq: IntVec,
                      pv: IntVec,
                      sl: IntVec,
                      no_slack: IntVec,
                      pq_reduced: IntVec,
                      pv_reduced: IntVec,
                      pqpv_original: IntVec,
                      tolerance: float,
                      max_order: int,
                      current_norm: float) -> DprSegmentResult:
    """
    Solve one DPRHEM shifted-germ segment.

    :param Ybus: Complete admittance matrix.
    :param Yseries: Series-only admittance matrix.
    :param Vgerm: Full voltage germ for this segment.
    :param Vset: Voltage set-point vector.
    :param S0: Specified complex target powers.
    :param Ysh0: Bus shunt admittance vector.
    :param pq: Original PQ bus indices.
    :param pv: Original PV bus indices.
    :param sl: Slack bus indices.
    :param no_slack: Original non-slack bus indices.
    :param pq_reduced: Reduced PQ bus indices.
    :param pv_reduced: Reduced PV bus indices.
    :param pqpv_original: Original sorted non-slack bus indices.
    :param tolerance: Target mismatch tolerance.
    :param max_order: Maximum coefficient order for this segment.
    :param current_norm: Mismatch norm at the germ.
    :return: Segment result.
    """

    npqpv: int = len(pqpv_original)
    npv: int = len(pv_reduced)
    Yred: CscMat = Yseries[np.ix_(pqpv_original, pqpv_original)]
    Ysh: CxVec = Ysh0[pqpv_original]
    U0: CxVec = Vgerm[pqpv_original].copy()
    bad_u0: np.ndarray = np.abs(U0) < 1e-10

    if np.any(bad_u0):
        U0[bad_u0] = 1.0 + 0.0j
    else:
        U0 = U0

    # Paper Eq. (2): initial state power is recomputed from the current voltage germ.
    Sini: CxVec = cf.compute_power(Ybus, Vgerm)
    Sini_rhs: CxVec = np.conj(Sini[pqpv_original])
    Sdir_pq_rhs: CxVec = np.conj(S0[pq] - Sini[pq])
    Pdir_pv: np.ndarray = S0.real[pv] - Sini.real[pv]
    vec_W: np.ndarray = np.abs(Vset[pqpv_original]) * np.abs(Vset[pqpv_original])

    U: np.ndarray = np.zeros((max_order + 1, npqpv), dtype=complex)
    X: np.ndarray = np.zeros((max_order + 1, npqpv), dtype=complex)
    Q: np.ndarray = np.zeros((max_order + 1, npqpv), dtype=complex)
    U[0, :] = U0
    X[0, :] = 1.0 / np.conj(U0)

    try:
        mat_factorized = factorized(dpr_build_matrix(Yred=Yred,
                                                     Ysh=Ysh,
                                                     U0=U0,
                                                     Sini_rhs=Sini_rhs,
                                                     pv=pv_reduced,
                                                     npv=npv,
                                                     npqpv=npqpv))
        factorized_ok: bool = True
    except RuntimeError:
        factorized_ok = False

    if factorized_ok:
        Vbest: CxVec = Vgerm.copy()
        best_norm: float = current_norm
        best_order: int = 0
        previous_norm: float = current_norm
        norm_order_1: float = current_norm
        baseline_ratio: float = np.inf
        converged: bool = current_norm <= tolerance
        improved: bool = False
        order: int = 1
        keep_solving: bool = not converged
        dval: CxVec = np.zeros(npqpv, dtype=complex)

        while order <= max_order and keep_solving:
            X_known: CxVec = dpr_known_inverse_voltage_coefficient(U, X, order)

            # Paper Eq. (14): PQ bus shifted-power recurrence.
            dval[pq_reduced] = (Sini_rhs[pq_reduced] * X_known[pq_reduced]
                                + Sdir_pq_rhs * X[order - 1, pq_reduced])

            # Paper Eq. (17): PV bus active-power direction and unknown reactive-power recurrence.
            dval[pv_reduced] = (Sini_rhs[pv_reduced] * X_known[pv_reduced]
                                + Pdir_pv * X[order - 1, pv_reduced]
                                - 1j * conv2(X, Q, order, pv_reduced))

            if order == 1:
                voltage_rhs: np.ndarray = vec_W[pv_reduced] - (np.abs(U[0, pv_reduced]) ** 2.0)
            else:
                voltage_rhs = -conv3(U, U, order, pv_reduced).real

            RHS: np.ndarray = np.r_[dval.real, dval.imag, voltage_rhs]
            LHS: np.ndarray = mat_factorized(RHS)
            U[order, :] = LHS[:npqpv] + 1j * LHS[npqpv:2 * npqpv]
            Q[order - 1, pv_reduced] = LHS[2 * npqpv:]
            X[order, :] = -conv1(U, X, order) / np.conj(U[0, :])

            Vcandidate, candidate_norm, candidate_ok = dpr_select_candidate(Ybus=Ybus,
                                                                            Vgerm=Vgerm,
                                                                            Vset=Vset,
                                                                            U=U,
                                                                            order=order,
                                                                            sl=sl,
                                                                            no_slack=no_slack,
                                                                            pqpv_original=pqpv_original,
                                                                            S0=S0,
                                                                            pq=pq)

            if candidate_ok:
                if candidate_norm < best_norm:
                    Vbest = Vcandidate
                    best_norm = candidate_norm
                    best_order = order
                    improved = True
                else:
                    Vbest = Vbest

                if candidate_norm <= tolerance:
                    converged = True
                    keep_solving = False
                elif order == 1:
                    norm_order_1 = candidate_norm
                    keep_solving = True
                elif order == 2:
                    baseline_ratio = dpr_residual_ratio(previous_norm=norm_order_1,
                                                        candidate_norm=candidate_norm,
                                                        tolerance=tolerance)
                    keep_solving = True
                else:
                    ratio: float = dpr_residual_ratio(previous_norm=previous_norm,
                                                      candidate_norm=candidate_norm,
                                                      tolerance=tolerance)
                    slow_restart: bool = bool(baseline_ratio >= ratio > 0.0)
                    divergence_restart: bool = bool(ratio < 0.0)
                    restart_now: bool = bool((slow_restart or divergence_restart) and candidate_norm < current_norm)

                    if restart_now:
                        Vbest = Vcandidate
                        best_norm = candidate_norm
                        best_order = order
                        improved = True
                        keep_solving = False
                    else:
                        keep_solving = True
            else:
                keep_solving = True

            previous_norm = candidate_norm
            order += 1

        result: DprSegmentResult = DprSegmentResult(U=U,
                                                    X=X,
                                                    Q=Q,
                                                    V=Vbest,
                                                    iterations=best_order,
                                                    norm_f=best_norm,
                                                    converged=converged,
                                                    improved=improved)
    else:
        result = DprSegmentResult(U=U,
                                  X=X,
                                  Q=Q,
                                  V=Vgerm,
                                  iterations=0,
                                  norm_f=current_norm,
                                  converged=False,
                                  improved=False)

    return result


def helm_coefficients_dpr(Ybus: CscMat, Yseries: CscMat, V0: CxVec | None, Vset: CxVec, S0: CxVec, Ysh0: CxVec,
                          pq: IntVec, pv: IntVec, sl: IntVec, no_slack: IntVec,
                          tolerance: float = 1e-6, max_coeff: int = 30,
                          restart_order: int = 6, max_restarts: int = 20,
                          use_classical_germ: bool = False,
                          verbose: bool = False, logger: Logger = None) -> tuple[np.ndarray, np.ndarray, np.ndarray,
                                                                                  CxVec, int, bool]:
    """
    Compute DPRHEM coefficients and final voltage state.

    :param Ybus: Complete admittance matrix.
    :param Yseries: Series-only admittance matrix.
    :param V0: Voltage estimate/set-point vector.
    :param S0: Specified complex bus powers.
    :param Ysh0: Bus shunt admittance vector.
    :param pq: Original PQ bus indices.
    :param pv: Original PV bus indices.
    :param sl: Slack bus indices.
    :param no_slack: Original non-slack bus indices.
    :param tolerance: Target mismatch tolerance.
    :param max_coeff: Total coefficient budget across restarts.
    :param restart_order: Maximum coefficient order per segment.
    :param max_restarts: Maximum number of DPRHEM restarts.
    :param use_classical_germ: Use the classical no-load germ instead of the supplied voltage estimate.
    :param verbose: Store debug information.
    :param logger: Logger object.
    :return: Last segment U, X, Q, final voltage, total iterations and convergence flag.
    """

    nbus: int = Yseries.shape[0]
    npqpv: int = len(no_slack)
    Ulast: np.ndarray = np.zeros((1, npqpv), dtype=complex)
    Xlast: np.ndarray = np.zeros((1, npqpv), dtype=complex)
    Qlast: np.ndarray = np.zeros((1, npqpv), dtype=complex)

    if nbus < 2:
        Vbest: CxVec = V0.copy()
        iterations: int = 0
        converged: bool = False
    else:
        pq_reduced, pv_reduced, pqpv_original = dpr_reduced_bus_indices(nbus, pq, pv, sl)

        Vtarget: CxVec = Vset if V0 is None else V0

        if use_classical_germ:
            Vbest = dpr_classical_no_load_germ(Yseries=Yseries, Vset=Vtarget, sl=sl, no_slack=no_slack, pv=pv)
        else:
            Vbest = dpr_safe_voltage_germ(Vtarget, no_slack)

        Vbest[sl] = Vtarget[sl]
        current_norm: float = dpr_power_mismatch(Ybus, Vbest, S0, no_slack, pq)
        converged = current_norm <= tolerance
        iterations = 0
        restart_count: int = 0
        can_continue: bool = True
        local_restart_order: int = restart_order if restart_order > 0 else max_coeff

        while can_continue and not converged:
            remaining_order: int = max_coeff - iterations
            segment_order: int = min(local_restart_order, remaining_order) if remaining_order > 0 else 0

            if segment_order > 0 and restart_count <= max_restarts:
                segment: DprSegmentResult = dpr_solve_segment(Ybus=Ybus,
                                                              Yseries=Yseries,
                                                              Vgerm=Vbest,
                                                              Vset=Vset,
                                                              S0=S0,
                                                              Ysh0=Ysh0,
                                                              pq=pq,
                                                              pv=pv,
                                                              sl=sl,
                                                              no_slack=no_slack,
                                                              pq_reduced=pq_reduced,
                                                              pv_reduced=pv_reduced,
                                                              pqpv_original=pqpv_original,
                                                              tolerance=tolerance,
                                                              max_order=segment_order,
                                                              current_norm=current_norm)
                Ulast = segment.U
                Xlast = segment.X
                Qlast = segment.Q
                iterations += max(1, segment.iterations)

                if segment.improved:
                    Vbest = segment.V
                    current_norm = segment.norm_f
                    converged = segment.converged
                    restart_count += 1
                else:
                    can_continue = False

                if verbose:
                    if logger is not None:
                        logger.add_debug("DPRHEM restart", restart_count)
                        logger.add_debug("DPRHEM norm", current_norm)
                    else:
                        verbose = verbose
                else:
                    verbose = verbose
            else:
                can_continue = False

    return Ulast, Xlast, Qlast, Vbest, iterations, converged


def helm_dpr_fixed_model(nc: NumericalCircuit,
                         Ybus: CscMat, Yf: CscMat, Yt: CscMat, Yshunt_bus: CxVec,
                         Yseries: CscMat, V0: CxVec | None, S0: CxVec, Ysh0: CxVec,
                         pq: IntVec, pv: IntVec, vd: IntVec, no_slack: IntVec,
                         tolerance: float = 1e-6, max_coefficients: int = 30, use_pade: bool = True,
                         restart_order: int = 6, max_restarts: int = 20,
                         use_classical_germ: bool = False,
                         verbose: int = 0, logger: Logger = None) -> NumericPowerFlowResults:
    """
    Solve one fixed-control power flow model with the DPRHEM variant in this module.

    :param nc: Numerical circuit island.
    :param Ybus: Complete admittance matrix.
    :param Yf: Branch-from admittance matrix.
    :param Yt: Branch-to admittance matrix.
    :param Yshunt_bus: Bus shunt admittance vector.
    :param Yseries: Series-only admittance matrix.
    :param V0: Voltage estimate/set-point vector.
    :param S0: Specified complex bus powers.
    :param Ysh0: Bus shunt admittance vector including branch shunt legs.
    :param pq: PQ bus indices.
    :param pv: PV bus indices.
    :param vd: Slack bus indices.
    :param no_slack: Sorted PQ/PV bus indices.
    :param tolerance: Target mismatch tolerance.
    :param max_coefficients: Total coefficient budget.
    :param use_pade: Kept for interface compatibility; restarts use direct summation.
    :param restart_order: Maximum coefficient order per segment.
    :param max_restarts: Maximum restart count.
    :param use_classical_germ: Use the classical no-load germ instead of the supplied voltage estimate.
    :param verbose: Verbosity flag.
    :param logger: Logger object.
    :return: Numeric power-flow results for the fixed model.
    """

    start_time: float = time.time()
    Vset: CxVec = nc.bus_data.Vbus

    if nc.bus_data.nbus < 2:
        results: NumericPowerFlowResults = NumericPowerFlowResults(
            V=V0,
            Scalc=S0,
            m=np.ones(nc.nbr, dtype=float),
            tau=np.zeros(nc.nbr, dtype=float),
            Sf=np.zeros(nc.nbr, dtype=complex),
            St=np.zeros(nc.nbr, dtype=complex),
            If=np.zeros(nc.nbr, dtype=complex),
            It=np.zeros(nc.nbr, dtype=complex),
            loading=np.zeros(nc.nbr, dtype=complex),
            losses=np.zeros(nc.nbr, dtype=complex),
            Pfp_vsc=np.zeros(nc.nvsc, dtype=float),
            Pfn_vsc=np.zeros(nc.nvsc, dtype=float),
            St_vsc=np.zeros(nc.nvsc, dtype=complex),
            If_vsc=np.zeros(nc.nvsc, dtype=float),
            It_vsc=np.zeros(nc.nvsc, dtype=complex),
            losses_vsc=np.zeros(nc.nvsc, dtype=float),
            loading_vsc=np.zeros(nc.nvsc, dtype=float),
            Sf_hvdc=np.zeros(nc.nhvdc, dtype=complex),
            St_hvdc=np.zeros(nc.nhvdc, dtype=complex),
            losses_hvdc=np.zeros(nc.nhvdc, dtype=complex),
            loading_hvdc=np.zeros(nc.nhvdc, dtype=complex),
            norm_f=0.0,
            converged=False,
            iterations=0,
            elapsed=0.0
        )
    else:
        U: np.ndarray
        X: np.ndarray
        Q: np.ndarray
        V: CxVec
        iter_: int
        converged: bool

        U, X, Q, V, iter_, converged = helm_coefficients_dpr(Ybus=Ybus,
                                                             Yseries=Yseries,
                                                             V0=V0,
                                                             Vset=Vset,
                                                             S0=S0,
                                                             Ysh0=Ysh0,
                                                             pq=pq,
                                                             pv=pv,
                                                             sl=vd,
                                                             no_slack=no_slack,
                                                             tolerance=tolerance,
                                                             max_coeff=max_coefficients,
                                                             restart_order=restart_order,
                                                             max_restarts=max_restarts,
                                                             use_classical_germ=use_classical_germ,
                                                             verbose=bool(verbose),
                                                             logger=logger)

        # Pade across restart boundaries is not meaningful because each segment has its own germ.
        if use_pade:
            use_pade = use_pade
        else:
            use_pade = use_pade

        Scalc: CxVec = cf.compute_power(Ybus, V)
        norm_f: float = float(cf.compute_fx_error(cf.compute_fx(Scalc, S0, no_slack, pq)))
        converged = norm_f < tolerance
        elapsed: float = time.time() - start_time

        if verbose:
            if logger is not None:
                logger.add_debug("DPRHEM V coefficients\n", U)
                logger.add_debug("DPRHEM X coefficients\n", X)
                logger.add_debug("DPRHEM Q coefficients\n", Q)
            else:
                verbose = verbose
        else:
            verbose = verbose

        Sf, St, If, It, Vbranch, loading, losses, Sbus = cf.power_flow_post_process_nonlinear(
            Sbus=Scalc,
            V=V,
            F=nc.passive_branch_data.F,
            T=nc.passive_branch_data.T,
            pv=pv,
            vd=vd,
            Ybus=Ybus,
            Yf=Yf,
            Yt=Yt,
            Yshunt_bus=Yshunt_bus,
            branch_rates=nc.passive_branch_data.rates,
            Sbase=nc.Sbase
        )

        results = NumericPowerFlowResults(
            V=V,
            Scalc=Scalc * nc.Sbase,
            m=np.ones(nc.nbr, dtype=float),
            tau=np.zeros(nc.nbr, dtype=float),
            Sf=Sf,
            St=St,
            If=If,
            It=It,
            loading=loading,
            losses=losses,
            Pfp_vsc=np.zeros(nc.nvsc, dtype=float),
            Pfn_vsc=np.zeros(nc.nvsc, dtype=float),
            St_vsc=np.zeros(nc.nvsc, dtype=complex),
            If_vsc=np.zeros(nc.nvsc, dtype=float),
            It_vsc=np.zeros(nc.nvsc, dtype=complex),
            losses_vsc=np.zeros(nc.nvsc, dtype=float),
            loading_vsc=np.zeros(nc.nvsc, dtype=float),
            Sf_hvdc=np.zeros(nc.nhvdc, dtype=complex),
            St_hvdc=np.zeros(nc.nhvdc, dtype=complex),
            losses_hvdc=np.zeros(nc.nhvdc, dtype=complex),
            loading_hvdc=np.zeros(nc.nhvdc, dtype=complex),
            norm_f=norm_f,
            converged=converged,
            iterations=iter_,
            elapsed=elapsed
        )

    return results


def helm_dpr(nc: NumericalCircuit,
             Ybus: CscMat, Yf: CscMat, Yt: CscMat, Yshunt_bus: CxVec,
             Yseries: CscMat, V0: CxVec | None, S0: CxVec, Ysh0: CxVec,
             pq: IntVec, pv: IntVec, vd: IntVec, no_slack: IntVec,
             tolerance: float = 1e-6, max_coefficients: int = 30, use_pade: bool = True,
             restart_order: int = 6, max_restarts: int = 20,
             use_classical_germ: bool = False,
             control_q: bool = False, pqv: IntVec | None = None, p: IntVec | None = None,
             Qmin: Vec | None = None, Qmax: Vec | None = None,
             distributed_slack: bool = False, bus_installed_power: Vec | None = None,
             controls_tol: float = 1e-3, max_control_restarts: int = 3,
             verbose: int = 0, logger: Logger = None) -> NumericPowerFlowResults:
    """
    Solve power flow with DPRHEM and apply discrete controls at DPR restart boundaries.

    :param nc: Numerical circuit island.
    :param Ybus: Complete admittance matrix.
    :param Yf: Branch-from admittance matrix.
    :param Yt: Branch-to admittance matrix.
    :param Yshunt_bus: Bus shunt admittance vector.
    :param Yseries: Series-only admittance matrix.
    :param V0: Voltage estimate/set-point vector.
    :param S0: Specified complex bus powers in p.u.
    :param Ysh0: Bus shunt admittance vector including branch shunt legs.
    :param pq: PQ bus indices.
    :param pv: PV bus indices.
    :param vd: Slack bus indices.
    :param no_slack: Sorted PQ/PV bus indices.
    :param tolerance: Target mismatch tolerance.
    :param max_coefficients: Total coefficient budget for each fixed-control DPR solve.
    :param use_pade: Kept for interface compatibility; restarts use direct summation.
    :param restart_order: Maximum coefficient order per DPR segment.
    :param max_restarts: Maximum DPR restart count for each fixed-control solve.
    :param use_classical_germ: Use the classical flat germ instead of the supplied voltage estimate.
    :param control_q: Apply PV-to-PQ reactive limit control at accepted DPR states.
    :param pqv: PQV bus indices used by the Q-limit control.
    :param p: P bus indices used by the Q-limit control.
    :param Qmin: Minimum reactive power limits in p.u.
    :param Qmax: Maximum reactive power limits in p.u.
    :param distributed_slack: Apply one distributed slack correction at an accepted DPR state.
    :param bus_installed_power: Installed power per bus for distributed slack participation.
    :param controls_tol: Residual threshold below which discrete controls are trusted.
    :param max_control_restarts: Maximum outer restarts caused by controls.
    :param verbose: Verbosity flag.
    :param logger: Logger object.
    :return: Numeric power-flow results.
    """

    start_time: float = time.time()
    active_S0: CxVec = S0.copy()
    active_V0: CxVec | None = None if V0 is None else V0.copy()
    active_pq: IntVec = pq.copy()
    active_pv: IntVec = pv.copy()
    active_pqv: IntVec = np.zeros(0, dtype=int) if pqv is None else pqv.copy()
    active_p: IntVec = np.zeros(0, dtype=int) if p is None else p.copy()
    active_use_classical_germ: bool = use_classical_germ
    control_restart: int = 0
    total_iterations: int = 0
    controls_pending: bool = True
    slack_distributed: bool = False
    solution: NumericPowerFlowResults = helm_dpr_fixed_model(
        nc=nc,
        Ybus=Ybus,
        Yf=Yf,
        Yt=Yt,
        Yshunt_bus=Yshunt_bus,
        Yseries=Yseries,
        V0=active_V0,
        S0=active_S0,
        Ysh0=Ysh0,
        pq=active_pq,
        pv=active_pv,
        vd=vd,
        no_slack=no_slack,
        tolerance=tolerance,
        max_coefficients=max_coefficients,
        use_pade=use_pade,
        restart_order=restart_order,
        max_restarts=max_restarts,
        use_classical_germ=active_use_classical_germ,
        verbose=verbose,
        logger=logger
    )

    while controls_pending and control_restart < max_control_restarts:
        controls_pending = False

        # Controls use physical powers, so only trust them once DPR is close enough to the current fixed model.
        if solution.norm_f < controls_tol:
            if control_q and Qmin is not None and Qmax is not None and (len(active_pv) + len(active_p)) > 0:
                Scalc_pu: CxVec = cf.compute_power(Ybus, solution.V)
                changed, active_pv, active_pq, active_pqv, active_p = control_q_inside_method(
                    Scalc=Scalc_pu,
                    S0=active_S0,
                    pv=active_pv,
                    pq=active_pq,
                    pqv=active_pqv,
                    p=active_p,
                    Qmin=Qmin,
                    Qmax=Qmax
                )
                if len(changed) > 0:
                    controls_pending = True
                else:
                    controls_pending = controls_pending
            else:
                controls_pending = controls_pending

            if distributed_slack and not slack_distributed and bus_installed_power is not None:
                Scalc_pu = cf.compute_power(Ybus, solution.V)
                ok, delta = compute_slack_distribution(
                    Scalc=Scalc_pu,
                    vd=vd,
                    bus_installed_power=bus_installed_power
                )
                if ok:
                    active_S0 += delta
                    slack_distributed = True
                    controls_pending = True
                else:
                    controls_pending = controls_pending
            else:
                controls_pending = controls_pending
        else:
            controls_pending = False

        if controls_pending:
            control_restart += 1
            total_iterations += solution.iterations
            active_V0 = solution.V
            active_use_classical_germ = False
            solution = helm_dpr_fixed_model(
                nc=nc,
                Ybus=Ybus,
                Yf=Yf,
                Yt=Yt,
                Yshunt_bus=Yshunt_bus,
                Yseries=Yseries,
                V0=active_V0,
                S0=active_S0,
                Ysh0=Ysh0,
                pq=active_pq,
                pv=active_pv,
                vd=vd,
                no_slack=no_slack,
                tolerance=tolerance,
                max_coefficients=max_coefficients,
                use_pade=use_pade,
                restart_order=restart_order,
                max_restarts=max_restarts,
                use_classical_germ=active_use_classical_germ,
                verbose=verbose,
                logger=logger
            )
        else:
            controls_pending = controls_pending

    total_iterations += solution.iterations

    solution.iterations = total_iterations
    solution.elapsed = time.time() - start_time

    return solution
