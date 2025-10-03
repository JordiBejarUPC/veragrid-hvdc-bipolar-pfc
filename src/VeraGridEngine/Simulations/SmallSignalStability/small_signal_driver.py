# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import numba as nb
from matplotlib import pyplot as plt
import scipy.linalg
from scipy.sparse import csr_matrix, csc_matrix, lil_matrix
from scipy.sparse.linalg import spsolve
import scipy.sparse as sp

from typing import Dict, Union
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Utils.Symbolic.block_solver import BlockSolver
from VeraGridEngine.Simulations.driver_template import DriverTemplate
from VeraGridEngine.Simulations.SmallSignalStability.small_signal_options import SmallSignalStabilityOptions
from VeraGridEngine.Simulations.SmallSignalStability.small_signal_results import SmallSignalStabilityResults
from VeraGridEngine.enumerations import EngineType, SimulationTypes
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowResults
from VeraGridEngine.Simulations.Rms.initialization import initialize_rms
from VeraGridEngine.basic_structures import Vec


@nb.njit(cache=True)
def compute_participation_factors(An, Am, v, w, n_eigenvalues, num_states):
    """

    :param A:
    :param v:
    :param w:
    :param n_eigenvalues:
    :param num_states:
    :return:
    """
    participation_factors = np.zeros((An, Am))
    for row in range(w.shape[0]):
        for column in range(w.shape[0]):
            participation_factors[row, column] = abs(w[row, column]) * abs(v[row, column])

    # normalize participation factors
    # pfact_abs = sp.csc_matrix(np.ones(num_states)) @ participation_factors
    pfact_abs = np.ones(num_states) @ participation_factors
    for i in range(n_eigenvalues):
        participation_factors[:, i] /= pfact_abs[i]

    return participation_factors


def run_small_signal_stability(slv: BlockSolver, x: Vec, params: Vec, plot=True, verbose: int = 0):
    """
    Small Signal Stability analysis
    :param slv: BlockSolver
    :param x: variables (1D numpy array)
    :param params: parameters (1D numpy array)
    :param plot: True(default) if S-domain eigenvalues plot wanted. Else: False
    :param verbose: verbosity level (0 for none)
    :return:
        stability: str
            "Unstable", "Marginally stable" or "Asymptotically stable"
        eigenvalues:  1D row numpy array
        participation factors: 2D array csc matrix.
            Participation factors of mode i stored in PF[:,i]
    """

    """
    Small Signal Stability analysis:
    1. Calculate the state matrix (A) from the state space model. From the DAE model:
        Tx'=f(x,y)
        0=g(x,y)
        the A matrix is computed as:
        A = T^-1(f_x - f_y * g_y^{-1} * g_x)   #T is implicit in the jacobian!

    2. Find eigenvalues and right(V) and left(W) eigenvectors

    3. Perform stability assessment

    4. Calculate normalized participation factors PF = W · V
    """

    fx = slv.j11(x, params)  # ∂f/∂x
    fy = slv.j12(x, params)  # ∂f/∂y
    gx = slv.j21(x, params)  # ∂g/∂x
    gy = slv.j22(x, params)  # ∂g/∂y

    gyx = spsolve(gy, gx)
    A = (fx - fy @ gyx)  # sparse state matrix csc matrix
    An = A.toarray()  # TODO: always use sparse algebra

    num_states = A.shape[0]

    # Note: The eigenvalue solution is dense in practice and apparently there is no sparse way around it
    eigenvalues, w, v = scipy.linalg.eig(An, left=True, right=True)

    # find participation factors
    participation_factors = compute_participation_factors(An=A.shape[0],
                                                          Am=A.shape[1],
                                                          v=v,
                                                          w=w,
                                                          n_eigenvalues=len(eigenvalues),
                                                          num_states=num_states)
    # for row in range(w.shape[0]):
    #     for column in range(w.shape[0]):
    #         participation_factors[row, column] = abs(w[row, column]) * abs(v[row, column])
    #
    # # normalize participation factors
    # pfact_abs = sp.csc_matrix(np.ones(num_states)) @ participation_factors
    # for i in range(len(eigenvalues)):
    #     participation_factors[:, i] /= pfact_abs[0, i]

    # damping ratios
    eig_no_conjugates = []
    seen = set()
    tol = 1e-12
    for z in eigenvalues:
        if np.isreal(z):
            seen.add(z)
            eig_no_conjugates.append(z)
        elif z.imag > tol:
            if z not in seen and np.conj(z) not in seen:
                seen.add(z)
                eig_no_conjugates.append(z)
        elif z.imag < tol:
            continue
    eig_no_conjugates = sp.lil_matrix(eig_no_conjugates)

    if verbose:
        print("eig no conjugates:", eig_no_conjugates)

    damping_ratios = lil_matrix(eig_no_conjugates.shape, dtype=float)
    conjugate_frequencies = lil_matrix(eig_no_conjugates.shape, dtype=float)
    for i in range(eig_no_conjugates.shape[1]):
        re = eig_no_conjugates[0, i].real
        im = eig_no_conjugates[0, i].imag
        conjugate_frequencies[0, i] = im / (2 * np.pi)
        modz = abs(eig_no_conjugates[0, i])
        if tol > modz:
            damping_ratios[0, i] = 0.0
        else:
            damping_ratios[0, i] = -re / modz

    # Stability: select positive and zero eigenvalues
    tol = 1e-6  # numerical tolerance for eigenvalues = 0
    unstable_eigs = eigenvalues[np.real(eigenvalues) > tol]
    zero_eigs = eigenvalues[abs(np.real(eigenvalues)) <= tol]

    # real_parts = eigenvalues.data.real
    # pos = real_parts > tol
    # unstable_eigs = eigenvalues.data[pos]

    if unstable_eigs.size == 0:
        if zero_eigs.size == 0:
            stability = "Asymptotically stable"  # TODO: always use Enums for known states
        else:
            stability = "Marginally stable"
    else:
        stability = "Unstable"

    if plot:
        x = eigenvalues.real
        y = eigenvalues.imag

        plt.scatter(x, y, marker='x', color='blue')
        plt.xlabel("Re [s -1]")
        plt.ylabel("Im [s -1]")
        plt.title("Stability plot")
        plt.axhline(0, color='black', linewidth=1)  # eje horizontal (y = 0)
        plt.axvline(0, color='black', linewidth=1)
        plt.tight_layout()
        plt.show()

    if verbose:
        print("all eigenvalues:", eigenvalues)
        print("complex conjugate eigenvalues:", eig_no_conjugates.toarray())
        print("daming ratios:", damping_ratios.toarray())
        print("conjugate_frequencies:", conjugate_frequencies.toarray())

    return stability, eigenvalues, participation_factors, damping_ratios, conjugate_frequencies


class SmallSignalStabilityDriver(DriverTemplate):
    """
    SmallSignal_Stability_Driver
    """
    name = 'Small Signal Stability Simulation'
    tpe = SimulationTypes.SmallSignal_run

    def __init__(self, grid: MultiCircuit,
                 options: Union[SmallSignalStabilityOptions, None] = None,
                 pf_results: Union[PowerFlowResults, None] = None,
                 engine: EngineType = EngineType.VeraGrid):

        """
        DynamicDriver class constructor
        :param grid: MultiCircuit instance
        :param options: SmallSignalOptions instance
        :param pf_results: PowerFlowResults
        :param engine: EngineType (i.e., EngineType.VeraGrid) (optional)
        """

        DriverTemplate.__init__(self, grid=grid, engine=engine)

        self.grid = grid

        self.pf_results: Union[PowerFlowResults, None] = pf_results

        self.options: SmallSignalStabilityOptions = SmallSignalStabilityOptions() if options is None else options

        self.results: SmallSignalStabilityResults = SmallSignalStabilityResults(stability="",
                                                                                Eigenvalues=np.empty(0),
                                                                                PF=np.empty(0),
                                                                                stat_vars=[],
                                                                                vars2device={})

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

        params_mapping: Dict = dict()

        ss, init_guess = initialize_rms(self.grid, self.pf_results)
        slv = BlockSolver(ss, self.grid.time)

        params0 = slv.build_init_params_vector(params_mapping)
        x0 = slv.build_init_vars_vector_from_uid(init_guess)

        if not self.options.ss_assessment_time == 0:
            # Get integration method
            if self.options.integration_method == "trapezoid":
                integrator = "trapezoid"
            elif self.options.integration_method == "implicit euler":
                integrator = "implicit_euler"
            else:
                raise ValueError(f"integrator not implemented :( {self.options.integration_method}")

            t, y = slv.simulate(
                t0=0,
                t_end=self.options.ss_assessment_time,
                h=self.options.time_step,
                x0=x0,
                params0=params0,
                method=integrator
            )

            i = int(self.options.ss_assessment_time / self.options.time_step)
            (stability,
             eigenvalues,
             participation_factors,
             damping_ratios,
             conjugate_frequencies) = run_small_signal_stability(slv=slv, x=y[i], params=params0, plot=False)

        else:

            (stability,
             eigenvalues,
             participation_factors,
             damping_ratios,
             conjugate_frequencies) = run_small_signal_stability(slv=slv, x=x0, params=params0, plot=False)

        self.results: SmallSignalStabilityResults = SmallSignalStabilityResults(
            stability=stability,
            Eigenvalues=eigenvalues,
            PF=participation_factors,
            stat_vars=slv.state_vars,
            vars2device=slv.vars2device
        )

        self.toc()
