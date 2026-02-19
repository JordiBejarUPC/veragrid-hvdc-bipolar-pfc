# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import numba as nb
from matplotlib import pyplot as plt
import scipy.linalg as la
import scipy.sparse.linalg as spla
import math
import time
import scipy.sparse as sp

from typing import Union
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.driver_template import DriverTemplate
from VeraGridEngine.Simulations.SmallSignalStability.small_signal_options import SmallSignalStabilityOptions
from VeraGridEngine.Simulations.SmallSignalStability.small_signal_results import SmallSignalStabilityResults
from VeraGridEngine.enumerations import EngineType, SimulationTypes
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.basic_structures import Vec
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration


# def compute_state_matrix(slv: BlockSolver, x: Vec, time: float, ):
def compute_state_matrix(problem, x: Vec, dx: Vec, dense: bool = True):
    """
    Small Signal Stability analysis core matrix computation.
    """
    h = problem.get_dt_value()

    fx = problem.get_j11(x, dx, h)  # ∂f/∂x
    fy = problem.get_j12(x, dx, h)  # ∂f/∂y
    gx = problem.get_j21(x, dx, h)  # ∂g/∂x
    gy = problem.get_j22(x, dx, h)  # ∂g/∂y

    gy_lu = spla.splu(gy)

    if dense:
        gy_inv_gx = gy_lu.solve(gx.toarray())
        A = fx.toarray() - fy.toarray() @ gy_inv_gx

        A_bal, scale_factors = la.matrix_balance(A, separate=False)

        return A_bal, A
    else:
        n_states = fx.shape[0]

        def matvec(v):
            return fx @ v - fy @ gy_lu.solve(gx @ v)

        def rmatvec(v):
            return fx.T @ v - gx.T @ gy_lu.solve(fy.T @ v, trans='T')

        A_op = spla.LinearOperator((n_states, n_states), matvec=matvec, rmatvec=rmatvec)
        return A_op, None


@nb.njit(cache=True)
def compute_participation_factors(v, w):
    """
    Calculates normalized participation factors correctly for both dense and sparse.
    Compatible with strict Numba (without keep dims).
    :param v: right eigenvectors (columns)
    :param w: left eigenvectors (columns)
    """
    n_rows = v.shape[0]
    k = v.shape[1]

    for i in range(k):
        norm_factor = 0j
        for j in range(n_rows):
            norm_factor += w[j, i] * v[j, i]

        if np.abs(norm_factor) > 1e-15:
            for j in range(n_rows):
                w[j, i] = w[j, i] / norm_factor

    PF = np.empty_like(v, dtype=np.float64)
    for i in range(k):
        for j in range(n_rows):
            PF[j, i] = np.abs(w[j, i] * v[j, i])

    PF_norm = np.empty_like(PF)
    for i in range(k):
        col_sum = np.sum(PF[:, i])
        if col_sum > 1e-15:
            for j in range(n_rows):
                PF_norm[j, i] = PF[j, i] / col_sum
        else:
            for j in range(n_rows):
                PF_norm[j, i] = PF[j, i]

    return PF_norm

# @nb.njit(cache=True)
def select_eigs_without_conjugates(eigenvalues):
    """
    :param eigenvalues: row np array with modes
    :return: row np array with only the positive complex conjugate modes
    """
    eig_no_conjugates = np.array([])
    seen = set()
    tol = 1e-12
    for z in eigenvalues:
        if np.isreal(z):
            seen.add(z)
        elif z.imag > tol:
            if z not in seen and np.conj(z) not in seen:
                seen.add(z)
                eig_no_conjugates =np.append(eig_no_conjugates,z)
        elif z.imag < tol:
            continue
    return eig_no_conjugates

@nb.njit(cache=True)
def compute_damping_ratios_and_frequencies(eigenvalues, eig_no_conjugates):
    """
    :param eigenvalues: row np array with modes
    :param eig_no_conjugates: row np array with only the positive complex conjugate modes
    :return: damping_ratios: list with damping ratios for the positive complex conjugate modes. Nan for other modes
    :return: conjugate_frequencies: list with oscillation frequencies for the positive complex conjugate modes. Nan for other modes
    """
    damping_ratios = np.full(eigenvalues.shape[0], np.nan, dtype=np.float64)
    conjugate_frequencies = np.full(eigenvalues.shape[0], np.nan, dtype=np.float64)
    tol = 1e-12
    match_tol = 1e-8

    for i in range(eigenvalues.shape[0]):
        mode = eigenvalues[i]
        found = False
        for j in range(eig_no_conjugates.shape[0]):
            if np.abs(mode - eig_no_conjugates[j]) <= match_tol:
                found = True
                break
        if found:
            re = mode.real
            im = mode.imag
            conjugate_frequencies[i] = im / (2.0 * np.pi)
            modz = np.abs(mode)
            if modz < tol:
                damping_ratios[i] = 0.0
            else:
                damping_ratios[i] = -re / modz
        else:
            damping_ratios[i] = np.nan
            conjugate_frequencies[i] = np.nan

    return damping_ratios, conjugate_frequencies

def plot_stability(eigenvalues, plot_units = "rad/s" ):
    """
        :param eigenvalues: row np array with modes
        :param plot_units: string with the imaginary units "rad/s" or "Hz"
        :return: plot S-domain modes
    """
    x = eigenvalues.real
    y = eigenvalues.imag
    slope = 1 / 0.05
    x_z = np.linspace(-200, 0, 400)
    y_z = slope * x_z

    x_label = "Re"
    y_label = "Im [rad/s]"

    if plot_units == "Hz":
        y = y / (2 * math.pi)
        y_z = y_z / (2 * math.pi)
        y_label = "Im [Hz]"

    # plot 5% damping ratio lines
    plt.plot(x_z, y_z, '--', color='grey', label='ζ = 5%')
    plt.plot(x_z, -y_z, '--', color='grey')
    # Plot the two lines (positive and negative imaginary axis)
    plt.axhline(0, color='black', linewidth=1)
    plt.axvline(0, color='black', linewidth=1)
    # plot modes
    plt.scatter(x, y, marker='x', color='blue')
    plt.xlabel(x_label)
    plt.ylabel(y_label)
    plt.title("Stability plot")

    margin_x = (x.max() - x.min()) * 0.1
    margin_y = (y.max() - y.min()) * 0.1
    x_min = x.min() - margin_x
    x_max = x.max() + margin_x
    y_min = y.min() - margin_y
    y_max = y.max() + margin_y
    plt.xlim([x_min, x_max])
    plt.ylim([y_min, y_max])

    plt.tight_layout()
    plt.show()


def run_dense_small_signal_stability(problem, x: Vec, dx: Vec, verbose: int = 0):
    # We obtain the balanced matrix
    A_bal, A_orig = compute_state_matrix(problem=problem, x=x, dx=dx, dense=True)

    # Scipy returns w such that w^TA = lambda w^H. We must conjugate it to W^TA = lambda W^T.
    eigenvalues, w_raw, v = la.eig(A_bal, left=True, right=True)
    w = w_raw.conj()

    participation_factors = compute_participation_factors(v=v, w=w)

    eig_no_conjugates = select_eigs_without_conjugates(eigenvalues)
    damping_ratios, conjugate_freq = compute_damping_ratios_and_frequencies(eigenvalues, eig_no_conjugates)

    if verbose:
        print("Eigenvalues:", eigenvalues)

    return eigenvalues, participation_factors, damping_ratios, conjugate_freq, A_orig


def run_sparse_small_signal_stability(problem, x: Vec, dx: Vec, k: int, verbose: int = 0):
    t0 = time.perf_counter()
    h = problem.get_dt_value()

    # Obtain sparse submatrices
    fx = problem.get_j11(x, dx, h)
    fy = problem.get_j12(x, dx, h)
    gx = problem.get_j21(x, dx, h)
    gy = problem.get_j22(x, dx, h)

    n_states = fx.shape[0]

    #1. BUILD THE ENHANCED JACOBIAN (Sparse)
    J_top = sp.hstack([fx, fy])
    J_bot = sp.hstack([gx, gy])
    J_aug = sp.vstack([J_top, J_bot], format='csc')

    #2. SUPER-LU FACTORIZATION OF THE ENTIRE SYSTEM
    J_aug_lu = spla.splu(J_aug)

    #3. CREATE THE SHIFT-AND-INVERT OPERATOR (A^-1 * v)
    def matvec_inv(b):
        rhs = np.zeros(J_aug.shape[0], dtype=np.float64)
        rhs[:n_states] = b
        sol = J_aug_lu.solve(rhs)
        return sol[:n_states]

    def rmatvec_inv(b):
        rhs = np.zeros(J_aug.shape[0], dtype=np.float64)
        rhs[:n_states] = b
        sol = J_aug_lu.solve(rhs, trans='T')
        return sol[:n_states]

    Inv_A_op = spla.LinearOperator((n_states, n_states), matvec=matvec_inv, rmatvec=rmatvec_inv)

    # 4. MODAL EXTRACTION
    # In small systems, k_search cannot exceed the dimension of the operator.
    k_search = min(k + 6, n_states - 2)
    if k_search <= 0:
        k_search = k

    mu_R, v_raw = spla.eigs(Inv_A_op, k=k_search, which="LM", tol=1e-10)
    mu_L, w_raw = spla.eigs(Inv_A_op.T, k=k_search, which="LM", tol=1e-10)

    # Tolerance for filtering algebraic noise (mu -> 0 means lambda -> inf)
    tol_mu = 1e-8

    # --- Rights Filtering ---
    valid_mask_R = np.abs(mu_R) > tol_mu
    mu_R_valid = mu_R[valid_mask_R]
    v_valid = v_raw[:, valid_mask_R]
    eigenvalues_R = 1.0 / mu_R_valid

    # --- Left Filtering ---
    valid_mask_L = np.abs(mu_L) > tol_mu
    mu_L_valid = mu_L[valid_mask_L]
    w_valid = w_raw[:, valid_mask_L]
    eigenvalues_L = 1.0 / mu_L_valid

    # 5. STRICT MATCHING
    # To avoid Arnoldi asymmetries, we use a metric that combines Re and Im.
    # We sort from lowest to highest natural frequency.
    order_R = np.argsort(np.abs(eigenvalues_R.imag) + np.abs(eigenvalues_R.real))
    order_L = np.argsort(np.abs(eigenvalues_L.imag) + np.abs(eigenvalues_L.real))

    eigenvalues_R = eigenvalues_R[order_R]

    v_valid = v_valid[:, order_R]
    w_valid = w_valid[:, order_L]

    # We strictly truncate to the requested k modes.
    if len(eigenvalues_R) > k:
        eigenvalues_R = eigenvalues_R[:k]
        v_valid = v_valid[:, :k]

    # We use w_valid shape for validate the size of L_eigen
    if w_valid.shape[1] > k:
        w_valid = w_valid[:, :k]

    eigenvalues = eigenvalues_R

    #6. PARTICIPATION
    participation_factors = compute_participation_factors(v=v_valid, w=w_valid)

    eig_no_conjugates = select_eigs_without_conjugates(eigenvalues)
    damping_ratios, conjugate_freq = compute_damping_ratios_and_frequencies(eigenvalues, eig_no_conjugates)

    if verbose:
        print(f"Sparse SSS Math Time: {(time.perf_counter() - t0) * 1000:.2f} ms")

    return eigenvalues, participation_factors, damping_ratios, conjugate_freq, None, None

class SmallSignalStabilityDriver(DriverTemplate):
    """
    SmallSignal_Stability_Driver
    """
    name = 'Small Signal Stability Simulation'
    tpe = SimulationTypes.SmallSignal_run

    def __init__(self,
                 grid: MultiCircuit,
                 problem: RmsProblemDae,
                 rms_options: Union[RmsOptions, None] = None,
                 ss_options: Union[SmallSignalStabilityOptions, None] = None,
                 engine: EngineType = EngineType.VeraGrid):

        """
        DynamicDriver class constructor
        :param grid: MultiCircuit instance
        :param options: SmallSignalOptions instance
        :param pf_results: PowerFlowResults
        :param engine: EngineType (i.e., EngineType.VeraGrid) (optional)
        """

        DriverTemplate.__init__(self, grid=grid, engine=engine)

        # self.grid = grid

        # self.pf_results: Union[PowerFlowResults, None] = pf_results

        self.problem = problem

        self.ss_options: SmallSignalStabilityOptions = SmallSignalStabilityOptions() if ss_options is None else ss_options
        self.assessment_time = self.ss_options.ss_assessment_time

        self.k = self.ss_options.k if self.ss_options.k is not None else self.problem.get_states_number()


        self.rms_options: RmsOptions = RmsOptions() if rms_options is None else rms_options

        self.results: SmallSignalStabilityResults = SmallSignalStabilityResults(eigenvalues=np.empty(0),
                                                                                participation_factors=np.empty(0),
                                                                                damping_ratios=np.empty(0),
                                                                                conjugate_frequencies=np.empty(0),
                                                                                state_matrix =np.empty(0),
                                                                                stat_vars=[])

        self.__cancel__ = False

    def run(self):
        """
        Main function to initialize and run the system simulation.

        This function sets up logging, starts the dynamic simulation, and
        logs the outcome. It handles and logs any exceptions raised during execution.
        :return:
        """
        # Run the dynamic simulation
        self.run_small_signal_stability()

    def run_small_signal_stability(self):
        """
        Performs the numerical integration using the chosen method.
        :return:
        """
        self.tic()

        # time, ss, init_guess = initialize_rms(self.grid, self.pf_results)
        # slv = BlockSolver(ss, time)


        # x0 = slv.build_init_vars_vector_from_uid(init_guess)
        x = self.problem.get_x0()
        print(f"x = {x}")
        dx = np.zeros_like(x)

        if not self.assessment_time == 0:
            # Get integration method

            # TODO: assign a solver directly depending on the options.integration_method (without if)
            if self.rms_options.integration_method == DynamicIntegrationMethod.Trapezoid:
                NotImplementedError(f"Rms integration method {DynamicIntegrationMethod.Trapezoid} not implemented")

            elif self.rms_options.integration_method == DynamicIntegrationMethod.BackEuler:
                solver = BackEulerImplicitIntegration(
                    problem=self.problem,
                    t0=0,
                    t_end=self.assessment_time,
                    h=self.rms_options.time_step,
                    max_iter=self.rms_options.max_iter
                )

                t, y, well_initialized, converged = solver.simulate()
                i = int(self.assessment_time / self.rms_options.time_step)
                x = y[i]

            else:
                raise ValueError(f"integrator not implemented :( {self.rms_options.integration_method}")


        n = self.problem.get_states_number()
        print(f"type n = {type(n)}")
        print(f"type self.k = {type(self.k)}")
        if self.k >= n-1:

            reduced_state_matrix = None
            (eigenvalues,
             participation_factors,
             damping_ratios,
             conjugate_frequencies,
             state_matrix) = run_dense_small_signal_stability(problem=self.problem,
                                                              x=x,
                                                              dx=dx,
                                                              verbose= self.ss_options.verbose)

        else:
            (eigenvalues,
             participation_factors,
             damping_ratios,
             conjugate_frequencies,
             state_matrix, reduced_state_matrix) = run_sparse_small_signal_stability(problem=self.problem,
                                                                                     x=x, dx=dx,
                                                                                     k = self.k,
                                                                                     verbose= self.ss_options.verbose)


        state_vars = self.problem.get_state_vars
        self.results: SmallSignalStabilityResults = SmallSignalStabilityResults(
            eigenvalues = eigenvalues,
            participation_factors = participation_factors,
            damping_ratios = damping_ratios,
            conjugate_frequencies = conjugate_frequencies,
            state_matrix = state_matrix,
            reduced_state_matrix = reduced_state_matrix,
            stat_vars = state_vars,
        )

        self.toc()
