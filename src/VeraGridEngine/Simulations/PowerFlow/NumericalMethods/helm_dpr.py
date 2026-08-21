# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import time

import numpy as np
from scipy.sparse import csc_matrix, coo_matrix, diags
from scipy.sparse import hstack as hs, vstack as vs
from scipy.sparse.linalg import factorized

from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
import VeraGridEngine.Simulations.PowerFlow.NumericalMethods.common_functions as cf
import VeraGridEngine.Simulations.PowerFlow.NumericalMethods.helm_power_flow as helm_power_flow
from VeraGridEngine.basic_structures import Logger, CscMat, CxVec, IntVec


class DprSegmentResult:
    """
    Result of one dynamic-power-restart HELM segment.

    The segment starts from one voltage germ and computes a short embedded
    correction towards the requested power state.

    :param U: Voltage series coefficients for the reduced non-slack system.
    :param X: Inverse-conjugate voltage series coefficients.
    :param Q: PV reactive-power correction coefficients.
    :param V: Best accepted full voltage vector found in this segment.
    :param iterations: Number of coefficients computed in the segment.
    :param norm_f: Best power mismatch found in this segment.
    :param converged: True when the requested tolerance was reached.
    :param improved: True when the segment found an admissible lower mismatch.
    """

    __slots__ = ("U", "X", "Q", "V", "iterations", "norm_f", "converged", "improved")

    def __init__(self,
                 U: np.ndarray,
                 X: np.ndarray,
                 Q: np.ndarray,
                 V: np.ndarray,
                 iterations: int,
                 norm_f: float,
                 converged: bool,
                 improved: bool) -> None:
        """
        Build the segment result container.

        :param U: Voltage series coefficients for the reduced non-slack system.
        :param X: Inverse-conjugate voltage series coefficients.
        :param Q: PV reactive-power correction coefficients.
        :param V: Best accepted full voltage vector found in this segment.
        :param iterations: Number of coefficients computed in the segment.
        :param norm_f: Best power mismatch found in this segment.
        :param converged: True when the requested tolerance was reached.
        :param improved: True when the segment found an admissible lower mismatch.
        :return: None.
        """

        self.U: np.ndarray = U
        self.X: np.ndarray = X
        self.Q: np.ndarray = Q
        self.V: np.ndarray = V
        self.iterations: int = iterations
        self.norm_f: float = norm_f
        self.converged: bool = converged
        self.improved: bool = improved


def _reduced_bus_indices(nbus: int, pq: IntVec, pv: IntVec, sl: IntVec) -> tuple[IntVec, IntVec, IntVec]:
    """
    Convert original bus indices into the reduced no-slack indexing used by HELM.

    :param nbus: Number of buses in the full system.
    :param pq: Original PQ bus indices.
    :param pv: Original PV bus indices.
    :param sl: Original slack bus indices.
    :return: Reduced PQ, reduced PV and original sorted PQ/PV bus indices.
    """

    nsl_counted: IntVec = np.zeros(nbus, dtype=int)
    slack_count: int = 0

    # Count how many slack buses appear before each original bus index.  Removing
    # slack buses shifts all following indices in the reduced matrix.
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


def _power_mismatch(Ybus: CscMat, V: CxVec, S0: CxVec, no_slack: IntVec, pq: IntVec) -> float:
    """
    Compute the standard VeraGrid power-flow mismatch norm.

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


def _angle_guard(V: CxVec, sl: IntVec, no_slack: IntVec) -> bool:
    """
    Check the DPRHEM physical-branch guard using the slack-angle reference.

    :param V: Full voltage vector to test.
    :param sl: Slack bus indices.
    :param no_slack: Non-slack bus indices.
    :return: True when every non-slack voltage angle remains within +/- 90 degrees.
    """

    if len(sl) > 0:
        slack_angle: float = float(np.angle(V[sl[0]], deg=True))
    else:
        slack_angle = 0.0

    angle_diff: np.ndarray = np.angle(V[no_slack], deg=True) - slack_angle
    angle_diff = (angle_diff + 180.0) % 360.0 - 180.0
    allowed: bool = bool(np.all(angle_diff < 90.0) and np.all(angle_diff > -90.0))

    return allowed


def _safe_voltage_germ(V: CxVec, no_slack: IntVec) -> CxVec:
    """
    Replace zero non-slack germ voltages by a neutral value.

    :param V: Candidate full voltage germ.
    :param no_slack: Original non-slack bus indices.
    :return: Full voltage germ with non-zero non-slack entries.
    """

    Vgerm: CxVec = V.copy()
    voltage_abs: np.ndarray = np.abs(Vgerm[no_slack])
    bad: np.ndarray = voltage_abs < 1e-10

    if np.any(bad):
        Vgerm[no_slack[bad]] = 1.0 + 0.0j
    else:
        Vgerm = Vgerm

    return Vgerm


def _known_inverse_voltage_coefficient(U: np.ndarray, X: np.ndarray, order: int) -> np.ndarray:
    """
    Compute the known part of X[order] before U[order] is solved.

    The inverse-voltage relation is conj(U(s)) * X(s) = 1.  At a given order,
    the term containing U[order] is unknown and is therefore left for the
    segment matrix.  This function returns only the lower-order convolution.

    :param U: Voltage series coefficients.
    :param X: Inverse-conjugate voltage coefficients.
    :param order: Coefficient order currently being solved.
    :return: Known part of the inverse-conjugate voltage coefficient.
    """

    known: np.ndarray = np.zeros(U.shape[1], dtype=complex)

    for coeff_idx in range(1, order):
        known += np.conj(U[coeff_idx, :]) * X[order - coeff_idx, :]

    if order > 1:
        known = -known / np.conj(U[0, :])
    else:
        known = known

    return known


def _build_dpr_matrix(Yred: CscMat,
                      Ysh: CxVec,
                      U0: CxVec,
                      Sbase_rhs: CxVec,
                      pv: IntVec,
                      npv: int,
                      npqpv: int) -> CscMat:
    """
    Build the real sparse linear system for one DPRHEM segment.

    :param Yred: Reduced series admittance matrix.
    :param Ysh: Reduced shunt admittance vector.
    :param U0: Segment voltage germ in reduced coordinates.
    :param Sbase_rhs: Conjugated initial-state complex powers in reduced coordinates.
    :param pv: Reduced PV bus indices.
    :param npv: Number of PV buses.
    :param npqpv: Number of non-slack buses.
    :return: Sparse CSC coefficient matrix.
    """

    # DPRHEM restarts from a physical voltage germ instead of the classical
    # no-load germ.  The reduced physical equation is:
    #
    #     (Yred + diag(Ysh)) U(s) = Yslack Vslack + conj(S(s)) X(s)
    #
    # The slack term is constant after order zero, so the n >= 1 system is:
    #
    #     A U[n] = conj(Sini) X[n] + conj(Sdir) X[n-1]
    #
    # Since X[n] contains -conj(U[n]) / conj(U[0])**2, the restarted system
    # needs the extra diagonal term below.  This is the actual system change
    # versus the base HELM derivation.
    network_matrix: CscMat = (Yred + diags(Ysh, offsets=0, format="csc")).tocsc()
    gamma: CxVec = Sbase_rhs / (np.conj(U0) * np.conj(U0))
    gamma_re: CscMat = diags(gamma.real, offsets=0, format="csc")
    gamma_im: CscMat = diags(gamma.imag, offsets=0, format="csc")

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


def _solve_dpr_segment(Ybus: CscMat,
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
    Solve one low-order dynamic-power-restart HELM segment.

    :param Ybus: Complete admittance matrix.
    :param Yseries: Series-only admittance matrix.
    :param Vgerm: Full voltage germ used as the segment initial state.
    :param Vset: Voltage set-point vector used for PV magnitudes and slack voltages.
    :param S0: Specified complex bus powers.
    :param Ysh0: Bus shunt admittance vector.
    :param pq: Original PQ bus indices.
    :param pv: Original PV bus indices.
    :param sl: Original slack bus indices.
    :param no_slack: Original non-slack bus indices.
    :param pq_reduced: Reduced PQ bus indices.
    :param pv_reduced: Reduced PV bus indices.
    :param pqpv_original: Original sorted PQ/PV bus indices.
    :param tolerance: Target mismatch tolerance.
    :param max_order: Maximum coefficient order for this segment.
    :param current_norm: Mismatch norm at the segment germ.
    :return: Segment result with the best accepted voltage state.
    """

    npqpv: int = len(pqpv_original)
    npv: int = len(pv_reduced)

    Yred: CscMat = Yseries[np.ix_(pqpv_original, pqpv_original)]
    Ysh: CxVec = Ysh0[pqpv_original]
    U0: CxVec = Vgerm[pqpv_original].copy()
    U0_abs: np.ndarray = np.abs(U0)
    bad_u0: np.ndarray = U0_abs < 1e-10

    if np.any(bad_u0):
        U0[bad_u0] = 1.0 + 0.0j
    else:
        U0 = U0

    Sbase: CxVec = cf.compute_power(Ybus, Vgerm)
    Sbase_rhs: CxVec = np.conj(Sbase[pqpv_original])
    Sdir_pq_rhs: CxVec = np.conj(S0[pq] - Sbase[pq])
    Pdir_pv: np.ndarray = S0.real[pv] - Sbase.real[pv]
    vec_W: np.ndarray = np.abs(Vset[pqpv_original]) * np.abs(Vset[pqpv_original])

    U: np.ndarray = np.zeros((max_order + 1, npqpv), dtype=complex)
    X: np.ndarray = np.zeros((max_order + 1, npqpv), dtype=complex)
    Q: np.ndarray = np.zeros((max_order + 1, npqpv), dtype=complex)

    U[0, :] = U0
    X[0, :] = 1.0 / np.conj(U0)

    try:
        mat_factorized = factorized(_build_dpr_matrix(Yred, Ysh, U0, Sbase_rhs, pv_reduced, npv, npqpv))
        factorized_ok: bool = True
    except RuntimeError:
        factorized_ok = False

    if factorized_ok:
        Vbest: CxVec = Vgerm.copy()
        best_norm: float = current_norm
        best_order: int = 0
        converged: bool = current_norm <= tolerance
        improved: bool = False
        order: int = 1
        keep_solving: bool = not converged
        dval: CxVec = np.zeros(npqpv, dtype=complex)

        while order <= max_order and keep_solving:
            X_known: CxVec = _known_inverse_voltage_coefficient(U, X, order)

            # PQ buses have fixed active and reactive target powers.  The
            # right-hand side is the known part of conj(Sini) X[n] plus the
            # embedded direction term conj(Starget - Sini) X[n - 1].
            dval[pq_reduced] = (Sbase_rhs[pq_reduced] * X_known[pq_reduced]
                                + Sdir_pq_rhs * X[order - 1, pq_reduced])

            # PV buses use the same initial physical state, but only active
            # power has a specified target.  The reactive direction is solved
            # through Q while the voltage-magnitude row enforces the PV setpoint.
            dval[pv_reduced] = (Sbase_rhs[pv_reduced] * X_known[pv_reduced]
                                + Pdir_pv * X[order - 1, pv_reduced]
                                - 1j * helm_power_flow.conv2(X, Q, order, pv_reduced))

            if order == 1:
                voltage_rhs: np.ndarray = vec_W[pv_reduced] - (np.abs(U[0, pv_reduced]) ** 2.0)
            else:
                voltage_rhs = -helm_power_flow.conv3(U, U, order, pv_reduced).real

            RHS: np.ndarray = np.r_[dval.real, dval.imag, voltage_rhs]
            LHS: np.ndarray = mat_factorized(RHS)

            U[order, :] = LHS[:npqpv] + 1j * LHS[npqpv:2 * npqpv]
            Q[order - 1, pv_reduced] = LHS[2 * npqpv:]
            X[order, :] = -helm_power_flow.conv1(U, X, order) / np.conj(U[0, :])

            Vcandidate: CxVec = Vgerm.copy()
            Vcandidate[sl] = Vset[sl]
            Vcandidate[pqpv_original] = U[:order + 1, :].sum(axis=0)

            candidate_norm: float = _power_mismatch(Ybus, Vcandidate, S0, no_slack, pq)
            candidate_ok: bool = bool(np.isfinite(candidate_norm) and _angle_guard(Vcandidate, sl, no_slack))

            if candidate_ok:
                if candidate_norm < best_norm:
                    Vbest = Vcandidate
                    best_norm = candidate_norm
                    best_order = order
                    improved = True
                else:
                    Vbest = Vbest
            else:
                Vbest = Vbest

            if best_norm <= tolerance:
                converged = True
                keep_solving = False
            else:
                keep_solving = True

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


def helm_coefficients_dpr(Ybus: CscMat, Yseries: CscMat, V0: CxVec, S0: CxVec, Ysh0: CxVec,
                          pq: IntVec, pv: IntVec, sl: IntVec, no_slack: IntVec,
                          tolerance: float = 1e-6, max_coeff: int = 30,
                          restart_order: int = 6, max_restarts: int = 20,
                          verbose: bool = False, logger: Logger = None) -> tuple[np.ndarray, np.ndarray, np.ndarray,
                                                                                  CxVec, int, bool]:
    """
    Compute DPRHEM coefficients and the final voltage state.

    :param Ybus: Complete admittance matrix.
    :param Yseries: Series-only admittance matrix.
    :param V0: Initial voltage germ and voltage set-point vector.
    :param S0: Specified complex bus powers.
    :param Ysh0: Bus shunt admittance vector.
    :param pq: Original PQ bus indices.
    :param pv: Original PV bus indices.
    :param sl: Original slack bus indices.
    :param no_slack: Original non-slack bus indices.
    :param tolerance: Target mismatch tolerance.
    :param max_coeff: Total coefficient budget across all restarts.
    :param restart_order: Maximum order computed before forcing a restart.
    :param max_restarts: Maximum number of dynamic power restarts.
    :param verbose: Store debug information in the logger.
    :param logger: Logger object.
    :return: Last segment coefficients, voltage vector, total iterations and convergence flag.
    """

    nbus: int = Yseries.shape[0]
    npqpv: int = len(no_slack)
    order_budget: int = max_coeff

    Ulast: np.ndarray = np.zeros((1, npqpv), dtype=complex)
    Xlast: np.ndarray = np.zeros((1, npqpv), dtype=complex)
    Qlast: np.ndarray = np.zeros((1, npqpv), dtype=complex)

    if nbus < 2:
        converged: bool = False
        iterations: int = 0
        Vbest: CxVec = V0.copy()
    else:
        pq_reduced, pv_reduced, pqpv_original = _reduced_bus_indices(nbus, pq, pv, sl)
        Vbest = _safe_voltage_germ(V0, no_slack)
        Vbest[sl] = V0[sl]
        current_norm: float = _power_mismatch(Ybus, Vbest, S0, no_slack, pq)
        converged = current_norm <= tolerance
        iterations = 0
        restart_count: int = 0
        can_continue: bool = True

        if restart_order > 0:
            local_restart_order: int = restart_order
        else:
            local_restart_order = max_coeff

        while can_continue and not converged:
            remaining_order: int = order_budget - iterations

            if remaining_order > 0:
                segment_order: int = min(local_restart_order, remaining_order)
            else:
                segment_order = 0

            if segment_order > 0 and restart_count <= max_restarts:
                segment: DprSegmentResult = _solve_dpr_segment(Ybus=Ybus,
                                                               Yseries=Yseries,
                                                               Vgerm=Vbest,
                                                               Vset=V0,
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


def helm_dpr(nc: NumericalCircuit,
             Ybus: CscMat, Yf: CscMat, Yt: CscMat, Yshunt_bus: CxVec,
             Yseries: CscMat, V0: CxVec, S0: CxVec, Ysh0: CxVec,
             pq: IntVec, pv: IntVec, vd: IntVec, no_slack: IntVec,
             tolerance: float = 1e-6, max_coefficients: int = 30, use_pade: bool = True,
             restart_order: int = 6, max_restarts: int = 20,
             verbose: int = 0, logger: Logger = None) -> NumericPowerFlowResults:
    """
    Solve the power flow with a dynamic-power-restart HELM variant.

    :param nc: Numerical circuit.
    :param Ybus: Complete admittance matrix.
    :param Yf: Branch-from admittance matrix.
    :param Yt: Branch-to admittance matrix.
    :param Yshunt_bus: Bus shunt admittance vector.
    :param Yseries: Series-only admittance matrix.
    :param V0: Initial voltage germ and voltage set-point vector.
    :param S0: Specified complex bus powers.
    :param Ysh0: Bus shunt admittance vector including branch shunt legs.
    :param pq: PQ bus indices.
    :param pv: PV bus indices.
    :param vd: Slack bus indices.
    :param no_slack: Sorted PQ/PV bus indices.
    :param tolerance: Target mismatch tolerance.
    :param max_coefficients: Total coefficient budget across all restarts.
    :param use_pade: Kept for interface compatibility; DPRHEM uses restart summation.
    :param restart_order: Maximum order computed before forcing a restart.
    :param max_restarts: Maximum number of dynamic power restarts.
    :param verbose: Verbosity flag.
    :param logger: Logger object.
    :return: Numeric power-flow results.
    """

    start_time: float = time.time()

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
                                                             verbose=bool(verbose),
                                                             logger=logger)

        # Pade across restart boundaries is not meaningful because each segment
        # has a different germ.  The flag remains accepted for drop-in use.
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
