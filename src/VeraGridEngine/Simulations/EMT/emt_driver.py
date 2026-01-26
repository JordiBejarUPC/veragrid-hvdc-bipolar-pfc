# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import pandas as pd
from typing import Dict, List
import scipy.sparse as sp

import VeraGridEngine.Devices as dev
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.types import INJECTION_DEVICE_TYPES
from VeraGridEngine.Simulations.driver_template import DriverTemplate
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.emt_results import EmtResults
from VeraGridEngine.enumerations import EngineType, SimulationTypes
from VeraGridEngine.Simulations.EMT.initialization_emt import initialize_emt
from VeraGridEngine.Simulations.PowerFlow.power_flow_results_3ph import PowerFlowResults3Ph

from VeraGridEngine.Utils.Symbolic.block_solver import BlockSolver
from VeraGridEngine.Utils.Symbolic.block import Block, Var, Const

from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.Devices.Substation.bus import Bus

from VeraGridEngine.basic_structures import Vec, IntVec, Mat, Vector, BoolVec

from scipy.sparse.linalg import factorized


class EmtSolverProperties:

    def __init__(
            self,
            bus: dev.Bus,
            bus_index: int,
            syst_blocks: Dict[dev.bus, Block],
            bus_regions_dict: Dict[dev.Bus, Dict[DeviceType, List[INJECTION_DEVICE_TYPES]]],
            alter_params_mappings: Dict[dev.Bus, Dict[int, Const]],
            init_guesses: List[Dict[int, float]],
            t: Var,
            steps: int,
    ):
        """
        Container for all EMT symbolic and solver-related properties
        associated with a single bus.
        :param bus : Bus object.
        :param bus_index: Float.
        :param devices : Any injections attached to the bus
        :param region_block : Block. Symbolic region block of the bus + injections of that bus
        :param params0 : 1D array. Initial parameter values
        :param alter_params0 : 1D array. Alternative initial parameter values
        :param x0 : 1D array. Initial variables vector
        :param dx0 : 1D array.  Initial state derivative variables vector
        :params0 x : (steps , len(x0)) array. Solution container with the variables solution at each timestep.
        :param dx : 1D array. Solution container with the State derivative variables solution at each timestep.
        :param blocksolver : BlockSolver/DiffBlockSolver    Block solver instance.
        """

        self.bus = bus
        self.name = bus.name
        self.index = bus_index

        # Symbolic structure
        self.devices: Dict[DeviceType, List[INJECTION_DEVICE_TYPES]] | None = None
        # Default initialisation (bus without region block)
        self.region_block: Block | None = None
        self.blocksolver: BlockSolver | None = None
        self.params0: Vec | None = None
        self.alter_params0: Vec | None = None
        self.x0: Vec | None = None
        self.dx0: Vec | None = None
        self.x: Mat | None = None
        self.dx: Mat | None = None

        self.devices = bus_regions_dict[bus]
        self.region_block = syst_blocks[bus]

        if len(self.region_block.children) >= 2:  # there's a block apart from the bus block

            # Solver
            self.blocksolver = BlockSolver(block_system=self.region_block, glob_time=t)

            # Parameters
            params_mapping = {}
            self.params0 = self.blocksolver.build_init_params_vector(params_mapping)

            # alter parameters
            alter_params_mapping = alter_params_mappings[bus]
            self.alter_params0 = (self.blocksolver.build_init_alter_params_vector(alter_params_mapping))

            # Initial states
            self.x0 = self.blocksolver.build_init_vars_vector_from_uid(init_guesses[bus_index])

            print(f"init guess Bus region {bus_index} = {init_guesses[bus_index]}")

            self.dx0 = np.zeros(self.blocksolver.n_diff)
            # self.dx0[4] = 1.0

            self.x = np.zeros((steps, self.blocksolver.n_vars))
            self.dx = np.zeros((steps, self.blocksolver.n_diff))

    def set_alter_params0(self, alter_params0: Vec):
        """Attach or replace the alter params."""
        self.alter_params0 = alter_params0


class EmtSimulationDriver(DriverTemplate):
    name = 'EMT Simulation'
    tpe = SimulationTypes.EmtDynamic_run

    """
    Dynamic wrapper to use with Qt
    """

    def __init__(self, grid: MultiCircuit,
                 options: EmtOptions,
                 pf_results: PowerFlowResults3Ph | None,
                 engine: EngineType = EngineType.VeraGrid):

        """
        DynamicDriver class constructor
        :param grid: MultiCircuit instance
        :param options: RmsOptions instance (optional)
        :param pf_results: PowerFlowResults
        :param engine: EngineType (i.e., EngineType.VeraGrid) (optional)
        """

        DriverTemplate.__init__(self, grid=grid, engine=engine)

        self.grid = grid

        self.pf_results: PowerFlowResults3Ph | None = pf_results

        self.options = options

        self.results = EmtResults(values=np.empty(0),
                                  time_array=pd.DatetimeIndex(pd.to_datetime(np.empty(0))),
                                  uid2idx=dict(),
                                  vars_glob_name2uid=dict(),
                                  devices=[])

        self.line_states = {}

    def run(self):
        """
        Main function to initialize and run the system simulation.

        This function sets up logging, starts the dynamic simulation, and
        logs the outcome. It handles and logs any exceptions raised during execution.
        :return:
        """
        # Run the dynamic simulation
        return self.run_time_simulation()

    def run_time_simulation(self):
        """
        Performs the EMTP loop using the MNA.
        :return:
        """
        self.tic()

        nc = compile_numerical_circuit_at(
            circuit=self.grid,
            fill_three_phase=True
        )

        (t, syst_blocks, init_guesses, h, N_delay, G0,
         binary_bus_mask, branch_lookup, bus_idx_lookup,
         alter_params_mappings, uid2idx_alterparams) = initialize_emt(
            grid=self.grid,
            emt_options=self.options,
            pf_results=self.pf_results,
            nc=nc)

        # Inicializar estados internos para líneas
        for branch in self.grid.get_branches_iter():
            if branch.device_type.value == 'Line':
                self.line_states[branch.name] = {
                    'i_prev': None,  # Para modelo Pi
                    'x_states': None  # Para modelo J-Marti
                }

        # simulate
        t, V, hist, Ibranches, hist_branches, Is, x, dx = self.simulate_emt(
            t=t,
            simulation_time=self.options.simulation_time,
            grid=self.grid,
            nc=nc,
            syst_blocks=syst_blocks,
            init_guesses=init_guesses,
            time_step=h,
            N_delay=N_delay,
            G0=G0,
            binary_bus_mask=binary_bus_mask,
            branch_lookup=branch_lookup,
            bus_idx_lookup=bus_idx_lookup,
            alter_params_mappings=alter_params_mappings,
            uid2idx_alterparams=uid2idx_alterparams
        )

        # self.results = EmtResults(values=y,
        #                           time_array=pd.DatetimeIndex(pd.to_datetime(t)),
        #                           uid2idx=slv.uid2idx_vars,
        #                           vars_glob_name2uid=slv.v_glob_name2uid,
        #                           devices = devices)

        self.toc()

        return t, V, hist, Ibranches, hist_branches, Is, x, dx

    def simulate_emt(
            self,
            t: Var,
            simulation_time: float,
            grid: MultiCircuit,
            nc: NumericalCircuit,
            syst_blocks: Dict,
            init_guesses: List,
            time_step: float,
            N_delay: int,
            G0: sp.csc_matrix,
            binary_bus_mask: BoolVec,
            branch_lookup: IntVec,
            bus_idx_lookup: IntVec,
            alter_params_mappings: Dict[Bus, Dict[int, Const]],
            uid2idx_alterparams: Dict[int, int]
            # newton_tol: float = 1e-8,
            # newton_max_iter: int = 1000,
    ):  # -> Tuple[np.ndarray, np.ndarray]:
        """
        Main MNA loop that simulates the system over time.
        :param simulation_time: float, total time
        :param grid: (MultiCircuit)
        :param nc: (NumericalCircuit)
        :param syst_block: system block
        :param init_guess: dict, initial guess
        :param time_step: float
        :param N_delay: int, number of steps according to t-tau for the longest line in the system
        :param G0: initial conductance matrix
        :param binary_bus_mask: List with True or False for each conductor existent or nonexistent in the network.
        :param branch_lookup:
        :param bus_idx_lookup:
        :return: 1D time array, 2D array of simulated variables
        """

        # simulation params
        h = time_step
        steps = int(np.ceil(simulation_time / h))

        # bus_dict = nc.bus_dict
        Nnodes = sum(binary_bus_mask)

        # branch_lookup = np.asarray(branch_lookup)
        Nbranches_masked = int(np.sum(branch_lookup >= 0))
        total_branch_currents = 2 * Nbranches_masked

        branch_from_lookup = np.full_like(branch_lookup, -1)
        branch_to_lookup = np.full_like(branch_lookup, -1)

        for r, base in enumerate(branch_lookup):
            if base >= 0:
                branch_from_lookup[r] = 2 * base
                branch_to_lookup[r] = 2 * base + 1

        # initialize results vectors
        temp = np.zeros((steps, 1))  # time
        V = np.zeros((steps, Nnodes))  # bus voltages vector
        Is = np.zeros((steps, Nnodes))  # currents from current sources vector
        hist = np.zeros((steps, Nnodes))  # I_history currents vector

        Ibranches = np.zeros((steps, total_branch_currents))
        hist_branches = np.zeros((steps, total_branch_currents))
        V_hist_buffer = np.zeros((N_delay + 1, Nnodes))
        I_hist_buffer = np.zeros((N_delay + 1, total_branch_currents))

        # DEFINITION OF EACH CONTAINER
        # temp: contains the time
        # V: voltages at each bus: [Va1, Vb1, Vc1, Va2, Vb2, Vc2...] instantaneous voltage
        # Is: current from current sources at each bus: [Isa1, Isb1, Isc1, Isa2, Isb2, Isc2...]
        # hist: history current term at each bus: [hist_a1, hist_b1, hist_c1, hist_a2, hist_b2, hist_c2...]
        # Ibranches: current at each branch termination: [I_from_aline1, I_to_aline1, I_from_bline1, I_to_bline1, I_from_cline1, I_to_cline1, I_from_aline2, I_to_aline2, I_from_bline2, I_to_bline2, I_from_cline2, I_to_cline2...]
        # hist_branches: history term of each branch termination: [hist_from_aline1, hist_to_aline1, hist_from_bline1, hist_to_bline1, hist_from_cline1, hist_to_cline1, hist_from_aline2, hist_to_aline2, hist_from_bline2, hist_to_bline2, hist_from_cline2, hist_to_cline2...]
        # V_hist_buffer: voltage t-tau steps before: [Va1(t-tau), Vb1(t-tau), Vc1(t-tau), Va2(t-tau), Vb2(t-tau), Vc2(t-tau)...]
        # I_hist_buffer: currents at each branch termination t-tau steps before: [I_from_aline1(t-tau), I_to_aline1(t-tau), I_from_bline1(t-tau), I_to_bline1(t-tau), I_from_cline1(t-tau), I_to_cline1(t-tau), I_from_aline2(t-tau), I_to_aline2(t-tau), I_from_bline2(t-tau), I_to_bline2(t-tau), I_from_cline2(t-tau), I_to_cline2(t-tau)...]

        # Initialize history buffers with steady state AC solution
        if self.pf_results is not None:
            omega = 2 * np.pi * grid.fBase
            res = self.pf_results

            print("Initializing EMT history buffers with steady-state AC values.")

            nbus4 = 4 * nc.bus_data.nbus
            sqrt2 = np.sqrt(2)

            # --- PF voltages (RMS p.u. phasors) ---
            V_mag_N = np.abs(res.voltage_N) if hasattr(res, 'voltage_N') else np.zeros(nc.bus_data.nbus)
            V_ang_N = np.angle(res.voltage_N) if hasattr(res, 'voltage_N') else np.zeros(nc.bus_data.nbus)
            V_mag_A = np.abs(res.voltage_A)
            V_ang_A = np.angle(res.voltage_A)
            V_mag_B = np.abs(res.voltage_B)
            V_ang_B = np.angle(res.voltage_B)
            V_mag_C = np.abs(res.voltage_C)
            V_ang_C = np.angle(res.voltage_C)

            # --- PF branch currents (RMS p.u. phasors) ---
            m = nc.passive_branch_data.nelm

            If_N = getattr(res, 'If_N', np.zeros(m, dtype=complex))
            If_A = getattr(res, 'If_A', np.zeros(m, dtype=complex))
            If_B = getattr(res, 'If_B', np.zeros(m, dtype=complex))
            If_C = getattr(res, 'If_C', np.zeros(m, dtype=complex))

            It_N = getattr(res, 'It_N', np.zeros(m, dtype=complex))
            It_A = getattr(res, 'It_A', np.zeros(m, dtype=complex))
            It_B = getattr(res, 'It_B', np.zeros(m, dtype=complex))
            It_C = getattr(res, 'It_C', np.zeros(m, dtype=complex))

            I_mag_f_N, I_ang_f_N = np.abs(If_N), np.angle(If_N)
            I_mag_f_A, I_ang_f_A = np.abs(If_A), np.angle(If_A)
            I_mag_f_B, I_ang_f_B = np.abs(If_B), np.angle(If_B)
            I_mag_f_C, I_ang_f_C = np.abs(If_C), np.angle(If_C)

            I_mag_t_N, I_ang_t_N = np.abs(It_N), np.angle(It_N)
            I_mag_t_A, I_ang_t_A = np.abs(It_A), np.angle(It_A)
            I_mag_t_B, I_ang_t_B = np.abs(It_B), np.angle(It_B)
            I_mag_t_C, I_ang_t_C = np.abs(It_C), np.angle(It_C)

            idx4 = np.array([0, 1, 2, 3], dtype=int)  # N,A,B,C

            # ---- fill buffers for negative times: t = -h, -2h, ... -N_delay*h ----
            for kdelay in range(1, N_delay + 1):
                t_val = -kdelay * h
                idx_buf = (-kdelay) % (N_delay + 1)

                # ---------- VOLTAGES (peak p.u.) ----------
                V_inst_all = np.zeros(nbus4, dtype=float)
                V_inst_all[0::4] = sqrt2 * V_mag_N * np.cos(omega * t_val + V_ang_N)
                V_inst_all[1::4] = sqrt2 * V_mag_A * np.cos(omega * t_val + V_ang_A)
                V_inst_all[2::4] = sqrt2 * V_mag_B * np.cos(omega * t_val + V_ang_B)
                V_inst_all[3::4] = sqrt2 * V_mag_C * np.cos(omega * t_val + V_ang_C)

                V_hist_buffer[idx_buf, :] = V_inst_all[binary_bus_mask]

                # ---------- HISTORY CURRENTS h(t) = i(t) - Gc*v(t) ----------
                # Initialize buffer row to zero first (optional but recommended)
                # I_hist_buffer[idx_buf, :] = 0.0

                for br_k, branch in enumerate(grid.get_branches_iter()):
                    if branch.device_type.value != 'Line':
                        continue

                    fro = nc.passive_branch_data.F[br_k]
                    to = nc.passive_branch_data.T[br_k]

                    f4 = 4 * fro + idx4
                    t4 = 4 * to + idx4

                    idx_from_red = bus_idx_lookup[f4]
                    idx_to_red = bus_idx_lookup[t4]

                    # Keep only active phases
                    mask_from = idx_from_red >= 0
                    mask_to = idx_to_red >= 0
                    mask = mask_from & mask_to  # phases active on both ends

                    if not np.any(mask):
                        continue

                    idx_from = idx_from_red[mask]
                    idx_to = idx_to_red[mask]

                    row_base = 4 * br_k + idx4
                    idx_hist_f = branch_from_lookup[row_base][mask]
                    idx_hist_t = branch_to_lookup[row_base][mask]

                    if np.any(idx_hist_f < 0) or np.any(idx_hist_t < 0):
                        raise RuntimeError(
                            f"Invalid history index after masking for branch {branch.name}"
                        )
                    Np = np.sum(mask)  # number of active phases

                    # voltages at ends (peak p.u.)
                    v_f = V_hist_buffer[idx_buf, idx_from]
                    v_t = V_hist_buffer[idx_buf, idx_to]

                    # currents at ends from PF (peak p.u.)
                    i_f_full = np.zeros(4, dtype=float)
                    i_t_full = np.zeros(4, dtype=float)

                    i_f_full[0] = sqrt2 * I_mag_f_N[br_k] * np.cos(omega * t_val + I_ang_f_N[br_k])
                    i_f_full[1] = sqrt2 * I_mag_f_A[br_k] * np.cos(omega * t_val + I_ang_f_A[br_k])
                    i_f_full[2] = sqrt2 * I_mag_f_B[br_k] * np.cos(omega * t_val + I_ang_f_B[br_k])
                    i_f_full[3] = sqrt2 * I_mag_f_C[br_k] * np.cos(omega * t_val + I_ang_f_C[br_k])

                    i_t_full[0] = sqrt2 * I_mag_t_N[br_k] * np.cos(omega * t_val + I_ang_t_N[br_k])
                    i_t_full[1] = sqrt2 * I_mag_t_A[br_k] * np.cos(omega * t_val + I_ang_t_A[br_k])
                    i_t_full[2] = sqrt2 * I_mag_t_B[br_k] * np.cos(omega * t_val + I_ang_t_B[br_k])
                    i_t_full[3] = sqrt2 * I_mag_t_C[br_k] * np.cos(omega * t_val + I_ang_t_C[br_k])

                    i_ft = i_f_full[mask]
                    i_tf = i_t_full[mask]

                    # Gc reduced
                    # Gc_full = np.asarray(branch.Gc, dtype=float)
                    # Gc = Gc_full[np.ix_(mask, mask)]
                    #
                    # # Bergeron history
                    # h_f = i_f - (Gc @ v_f)
                    # h_t = i_t - (Gc @ v_t)
                    #
                    # I_hist_buffer[idx_buf, idx_hist_f] = h_f
                    # I_hist_buffer[idx_buf, idx_hist_t] = h_t

                    I_hist_buffer[idx_buf, idx_hist_f] = i_ft
                    I_hist_buffer[idx_buf, idx_hist_t] = i_tf

        # Symbolic EmtSolverProperties association
        emt_vec = Vector(grid.get_bus_number())
        bus_regions_dict = grid.get_injection_devices_grouped_by_bus()  # dict with only injections (no bus blocks)
        for i, bus in enumerate(grid.get_buses()):
            emt_vec[i] = EmtSolverProperties(
                bus=bus,
                bus_index=i,
                syst_blocks=syst_blocks,
                bus_regions_dict=bus_regions_dict,
                alter_params_mappings=alter_params_mappings,
                init_guesses=init_guesses,
                t=t,
                steps=steps,
            )

            # Voltage initialisation from power flow ---------------------------------------------------------------
            V0 = set_V0_bus(alter_params_mapping=alter_params_mappings[bus],
                            uid2idx_alterparams=uid2idx_alterparams,
                            bus=bus,
                            i=i,
                            nc=nc,
                            binary_bus_mask=binary_bus_mask)
            V[0, :] += V0

            if emt_vec[i].blocksolver is not None:  # else, it's 0
                # Assign step 0 variables and derivatives
                emt: EmtSolverProperties = emt_vec[i]
                emt.x[0, :] = emt.x0
                emt.dx[0, :] = emt.dx0
                # Assign step 0 currents from injections ---------------------------------------------------------------
                Is_0 = set_I0_bus(emt_vec_bus=emt_vec[i],
                                  i=i,
                                  nc=nc,
                                  init_guesses=init_guesses,
                                  binary_bus_mask=binary_bus_mask,
                                  bus_idx_lookup=bus_idx_lookup,
                                  V=V[0, :])

                Is[0, :] += Is_0

        hist[0, :] = update_Hist(nc=nc,
                                 step=0,
                                 V_hist_buffer=V_hist_buffer,
                                 I_hist_buffer=I_hist_buffer,
                                 hist_branches=hist_branches[0, :],
                                 grid=grid,
                                 N_delay=N_delay,
                                 h=h,
                                 branch_from_lookup=branch_from_lookup,
                                 branch_to_lookup=branch_to_lookup,
                                 bus_idx_lookup=bus_idx_lookup,
                                 line_states=self.line_states)
        # update Ibranches for the step 0
        Ibranches[0, :] = update_Ibranches(nc=nc,
                                           V=V[0, :],
                                           hist_branches=hist_branches[0, :],
                                           grid=grid,
                                           step=0,
                                           h=h,
                                           N_delay=N_delay,
                                           bus_idx_lookup=bus_idx_lookup,
                                           branch_from_lookup=branch_from_lookup,
                                           branch_to_lookup=branch_to_lookup,
                                           total_branch_currents=I_hist_buffer.shape[1],
                                           line_states=self.line_states)
        kbuf = 0 % (N_delay + 1)
        V_hist_buffer[kbuf, :] = V[0, :]
        I_hist_buffer[kbuf, :] = hist_branches[0, :]

        print(f"Voltages[0] = {V[0, :]}")
        print(f"Isource[0] = {Is[0, :]}")
        print(f"hist[0] = {hist[0, :]}")
        print(f"Ibranches[0] = {Ibranches[0, :]}")

        V0 = V[0, :]  # shape (N_nodes,)
        Is0 = Is[0, :]  # shape (N_nodes,)
        hist0 = hist[0, :]  # shape (N_nodes,)

        Itotal0 = (Is0 - hist0).reshape(-1, 1)

        # --- MNA residual ---
        r = G0 @ V0 - Itotal0

        # --- diagnostics ---
        r_inf = np.linalg.norm(r, ord=np.inf)
        r_l2 = np.linalg.norm(r)

        print("MNA residual check at t = 0")
        print(f"||r||_inf = {r_inf:.3e}")
        print(f"||r||_2   = {r_l2:.3e}")

        print(f"step 0 completed, starting the loop...")

        G = factorized(G0)
        # ---------- MAIN LOOP ----------
        for step in range(1, steps):
            # for step in range(steps): # -----------
            # actualize time variable
            temp[step] = step * h
            print("sim time = ", temp[step])

            # check events that change G TODO

            # calculate current sources i_s: from active elements
            Is[step, :] = predict_Is(emt_simulation_driver=self,
                                     Vprev=V[step - 1, :],
                                     nc=nc,
                                     step=step,
                                     grid=grid,
                                     h=h,
                                     binary_bus_mask=binary_bus_mask,
                                     bus_idx_lookup=bus_idx_lookup,
                                     emt_vec=emt_vec)

            # update i history
            hist[step, :] = update_Hist(nc=nc,
                                        step=step,
                                        V_hist_buffer=V_hist_buffer,
                                        I_hist_buffer=I_hist_buffer,
                                        hist_branches=hist_branches[step, :],
                                        grid=grid,
                                        N_delay=N_delay,
                                        h=h,
                                        branch_from_lookup=branch_from_lookup,
                                        branch_to_lookup=branch_to_lookup,
                                        bus_idx_lookup=bus_idx_lookup,
                                        line_states=self.line_states)

            # Create right hand side vector Itotal for the MNA
            Itotal = (Is[step, :] - hist[step, :]).reshape(-1, 1)  # column vector

            # solve MNA
            sol = G(Itotal)
            V[step, :] = sol[:, 0]

            # -----------------------------------------------
            Is[step, :] = update_Is(emt_simulation_driver=self,
                                    Vsol=V[step, :],
                                    nc=nc,
                                    step=step,
                                    grid=grid,
                                    h=h,
                                    binary_bus_mask=binary_bus_mask,
                                    bus_idx_lookup=bus_idx_lookup,
                                    emt_vec=emt_vec)

            # Itotal = (Is[step, :] - hist[step, :]).reshape(-1, 1)  # column vector
            #
            # # solve MNA
            # sol = G(Itotal)
            # V[step, :] = sol[:, 0]
            # print(f"step {step} sol = {sol[:, 0]}")

            # solve current equations
            Ibranches[step, :] = update_Ibranches(nc=nc,
                                                  V=V[step, :],
                                                  hist_branches=hist_branches[step, :],
                                                  grid=grid,
                                                  step=step,
                                                  h=h,
                                                  N_delay=N_delay,
                                                  bus_idx_lookup=bus_idx_lookup,
                                                  branch_from_lookup=branch_from_lookup,
                                                  branch_to_lookup=branch_to_lookup,
                                                  total_branch_currents=I_hist_buffer.shape[1],
                                                  line_states=self.line_states)
            # kbuf = step % (N_delay + 1)
            kbuf = step % (1 + 1)
            V_hist_buffer[kbuf, :] = V[step, :]
            # I_hist_buffer[kbuf, :] = hist_branches[step, :]  # <-- guarda h(t) MALAMENT
            I_hist_buffer[kbuf, :] = Ibranches[step, :]  # <-- guarda i(t)

        # save symbolic results to x, dx
        # y = x[:, 1:]
        x = None
        dx = None
        # dx = np.zeros((steps, 0))
        for i, bus in enumerate(grid.get_buses()):
            emt: EmtSolverProperties = emt_vec[i]
            x_bus = emt.x
            dx_bus = emt.dx
            if x_bus is not None:
                if x is None:
                    x = x_bus
                    dx = dx_bus
                else:
                    x = np.concatenate((x, x_bus), axis=1)
                    dx = np.concatenate((dx, dx_bus), axis=1)

        return temp, V, hist, Ibranches, hist_branches, Is, x, dx


def predict_Is(emt_simulation_driver: EmtSimulationDriver,
               Vprev: np.ndarray,
               nc: NumericalCircuit,
               step: int,
               grid: MultiCircuit,
               h: float,
               binary_bus_mask: BoolVec,
               bus_idx_lookup: IntVec,
               emt_vec: Vector):
    """
    Predict the current sources vector Is for arbitrary phase configurations.
    :param emt_simulation_driver: EmtSimulationDriver
    :param Vprev: np.ndarray. voltage solution at previous timestep V[step-1, :]
    :param nc: NumericalCircuit
    :param step: int
    :param grid: MultiCircuit
    :param h: float. time-step
    :param binary_bus_mask: BoolVec
    :param bus_idx_lookup : IntVec
    :param init_guesses: List[Dict[int, float]]
    :param emt_vec: Vector
    :return Is_step: np array
    """
    n = nc.bus_data.nbus
    Is_step = np.zeros(n * 4, dtype=float)

    for i, bus in enumerate(
            grid.get_buses()):  # solve 1 step of the symbolic blocs in each bus (only if the bus has a symbolic block)
        emt: EmtSolverProperties = emt_vec[i]
        if emt.blocksolver is not None:  # only if there are injections in the bus
            # update x0, dx0 with x, dx from the previous state if it's not the first iter
            x0 = emt.x[step - 1, :]
            dx0 = emt.dx[step - 1, :]
            emt.x0 = x0
            emt.dx0 = dx0

            # update v_abc in alter_params0
            idx = 4 * i + np.array([0, 1, 2, 3])
            net_idx = np.asarray(bus_idx_lookup)[idx]
            v_n, v_a, v_b, v_c = [Vprev[i] if i >= 0 else 0.0 for i in net_idx]

            alter_params0 = np.array([v_n, v_a, v_b, v_c], dtype=float)
            alter_params0 = alter_params0[binary_bus_mask[idx]]
            print(f"step{step} previous voltages bus {i}: v_a = {v_a}, v_b = {v_b}, v_c = {v_c}")

            emt.set_alter_params0(alter_params0)

            # simulate just 1 timestep
            slv = emt.blocksolver

            _, y, dx, _ = slv.simulate(
                t0=(step - 1) * h,
                t_end=step * h + 1e-10,  # h + 1e-10,  # just one timestep simulation
                # t0=0,
                # t_end=h + 1e-10,  # just one timestep simulation
                h=h,
                x0=emt.x0,
                dx0=emt.dx0,
                params0=emt.params0,  # not used
                alter_params0=emt.alter_params0,
                method=emt_simulation_driver.options.integration_method,
                newton_tol=emt_simulation_driver.options.tolerance,
                newton_max_iter=1000,
                followed_vars=None,
                initialized=False,
                verbose=False,
            )
            print(f"step{step} prediction: y = {y[1, :]}")
            print(f"step{step} prediction: dx = {dx[1, :]}")
            # paste results to the EmtSolverProperties
            emt.x[step, :] = y[1, :]
            emt.dx[step, :] = dx[1, :]

            # paste current results to the Is array
            for dev_type, dev_list in emt.devices.items():
                for elm in dev_list:
                    i_s_bus = np.zeros(4, dtype=float)
                    for var in elm.emt_model.model.out_vars:
                        if str(var) == 'i_n':
                            i_n_idx = slv.uid2idx_vars[var.uid]
                            i_s_bus[0] = y[1, i_n_idx]
                        elif str(var) == 'i_a':
                            i_a_idx = slv.uid2idx_vars[var.uid]
                            i_s_bus[1] = y[1, i_a_idx]
                        elif str(var) == 'i_b':
                            i_b_idx = slv.uid2idx_vars[var.uid]
                            i_s_bus[2] = y[1, i_b_idx]
                        elif str(var) == 'i_c':
                            i_c_idx = slv.uid2idx_vars[var.uid]
                            i_s_bus[3] = y[1, i_c_idx]

                    Is_step[idx] += i_s_bus
                    if dev_type.name == 'GeneratorDevice':
                        # plus the generator history component due to the interfacing resistor v(t-dt)/ Rp
                        # Gp = (1 / elm.Rp) * np.eye(4)
                        # Is_step[idx] += np.array([v_n, v_a, v_b, v_c], dtype=float) @ Gp
                        # Is_step[idx] += elm.Gc @ np.array([v_n, v_a, v_b, v_c], dtype=float)

                        Is_step[idx] += elm.Gc @ np.array([v_n, v_a, v_b, v_c], dtype=float)

    Is_step = Is_step[binary_bus_mask]

    return Is_step


# ----------------------------------------------------------------------------------------------------------------------
#     # GENERATOR AS VOLTAGE SOURCE (INITIAL IMPLEMENTATION)
#     n = nc.bus_data.nbus
#     Is_step = np.zeros(n*4, dtype=float)
#
#     # Balanced 3-phase reference angles (if needed)
#     phase_angles = {
#         'n': 0.0,  # not needed
#         'a': 0.0,
#         'b': -2.0 * np.pi / 3.0,
#         'c': 2.0 * np.pi / 3.0,
#     }
#
#     # generators #todo: adapt to all injections!
#     idx4 = np.array([0, 1, 2, 3])
#     Gc_gen = 0.0
#     Gc_line = 0.0
#     Gc_trafo = 0.0
#     for elm in grid.get_generators():
#         bus = elm.bus
#         bus_idx = nc.bus_dict[bus]
#
#         Gc_gen = elm.Gc
#
#         for line in grid.get_lines():
#             Gc_line = line.Gc
#         for trafo in grid.get_transformers2w():
#             Gc_trafo = trafo.Gc
#
#         Gc = Gc_gen + Gc_line + Gc_trafo
#
#         # Build local source voltage vector v_src
#         v_src = np.zeros((4,), dtype=float)
#
#         phases = ['n', 'a', 'b', 'c']
#         for i, ph in enumerate(phases):
#
#             if ph == 'n':
#                 # neutral usually at 0 V internally
#                 v_src[i] = 0.0
#                 continue
#
#             angle = phase_angles[ph]
#             # Basic sinusoidal source
#             t = step * h
#             Vpeak = np.sqrt(2)
#             v_src[i] = Vpeak * np.sin(2 * np.pi * elm.freq * t + angle) #todo: working as voltage source.
#
#         i_s_bus = Gc @ v_src
#         idx = 4 * bus_idx + idx4
#         Is_step[idx] += i_s_bus
#
#     Is_step = Is_step[binary_bus_mask]
#
#     return Is_step


def update_Hist(nc: NumericalCircuit,
                step: int,
                V_hist_buffer: np.ndarray,
                I_hist_buffer: np.ndarray,
                hist_branches: np.ndarray,
                grid: MultiCircuit,
                N_delay: int,
                h: float,
                branch_from_lookup: IntVec,
                branch_to_lookup: IntVec,
                bus_idx_lookup: IntVec,
                line_states: Dict):
    """
    Update history currents for lines (Bergeron) in a multi-phase setting.

    :param nc: NumericalCircuit
    :param step: current time step index
    :param V_hist_buffer: (N_delay+1, total_cond)
    :param I_hist_buffer: (N_delay+1, 2*max_phases_line*nl)
    :param hist_branches: 1D array with current history for all line ends at this step
    :param grid: MultiCircuit
    :param N_delay: max delay in steps (for the longest line)
    :param h: time step (not used here but kept for future extensions)
    :param branch_from_lookup:
    :param branch_to_lookup:
    :param bus_idx_lookup:
    :return: hist_step (1 x total_cond)
    """
    n = nc.bus_data.nbus
    bus_idx_lookup = np.asarray(bus_idx_lookup, dtype=int)
    Nnodes = np.sum(bus_idx_lookup >= 0)
    hist_step = np.zeros(Nnodes, dtype=float)

    idx4 = np.array([0, 1, 2, 3])

    for k, branch in enumerate(grid.get_branches_iter()):

        # Full bus indices
        fro = nc.passive_branch_data.F[k]  # indices of the from buses
        to = nc.passive_branch_data.T[k]  # indices of the to buses

        # Full-node indices (N,A,B,C)
        f4 = 4 * fro + idx4
        t4 = 4 * to + idx4

        # Reduce using bus_idx_lookup
        idx_from_reduced = bus_idx_lookup[f4]
        idx_to_reduced = bus_idx_lookup[t4]

        # Keep only active phases
        mask_from = idx_from_reduced >= 0
        mask_to = idx_to_reduced >= 0
        mask = mask_from & mask_to  # phases active on both ends

        if not np.any(mask):
            continue

        idx_from = idx_from_reduced[mask]
        idx_to = idx_to_reduced[mask]

        # Retrieve history currents segment for this line
        row_base = 4 * k + np.array([0, 1, 2, 3])

        idx_hist_f_full = branch_from_lookup[row_base]
        idx_hist_t_full = branch_to_lookup[row_base]
        idx_hist_f = idx_hist_f_full[mask]
        idx_hist_t = idx_hist_t_full[mask]

        if np.any(idx_hist_f < 0) or np.any(idx_hist_t < 0):
            raise RuntimeError(
                f"Invalid history index after masking for branch {branch.name}"
            )

        Np = np.sum(mask)  # number of active phases

        # ---- lines history components ----
        if branch.device_type.value == 'Line':  # DeviceType.LineDevice:

            model = getattr(branch, 'model_type', 'Bergeron')

            if model == "Bergeron":
                delay = branch.Ndelay

                k_delay = (step - delay) % (N_delay + 1)

                v_delay_f = V_hist_buffer[k_delay, idx_from]
                v_delay_t = V_hist_buffer[k_delay, idx_to]

                i_delay_ft = I_hist_buffer[k_delay, idx_hist_f]
                i_delay_tf = I_hist_buffer[k_delay, idx_hist_t]

                # Bergeron matrices
                Gc_full = np.asarray(branch.Gc, dtype=float)  # 4x4
                H_full = np.asarray(branch.H, dtype=float)

                Gc = Gc_full[np.ix_(mask, mask)]
                H = H_full[np.ix_(mask, mask)]
                I = np.eye(Np)

                X_f = - (Gc @ v_delay_t) - i_delay_tf
                Y_f = - (Gc @ v_delay_f) - i_delay_ft

                X_t = - (Gc @ v_delay_f) - i_delay_ft
                Y_t = - (Gc @ v_delay_t) - i_delay_tf

                # Bergeron updates
                I_hist_f = 0.5 * ((I + H) @ X_f + (I - H) @ Y_f)
                I_hist_t = 0.5 * ((I + H) @ X_t + (I - H) @ Y_t)

                hist_branches[idx_hist_f] = I_hist_f
                hist_branches[idx_hist_t] = I_hist_t

                # add history components from the trafo to the history vector at the current timestep
                hist_step[idx_from] += I_hist_f
                hist_step[idx_to] += I_hist_t

            elif model == 'Pi':
                # --- MODELO PI HÍBRIDO (Correcto Físicamente) ---
                # Serie RL: Trapecio (I_h = G_ser*v_diff_old + i_ser_old)
                # Shunt C:  Backward Euler (I_h = -G_sh * v_old)

                k_prev = (step - 1) % (N_delay + 1)

                # 1. Recuperar estados previos
                vf_prev = V_hist_buffer[k_prev, idx_from]
                vt_prev = V_hist_buffer[k_prev, idx_to]
                i_ser_prev = I_hist_buffer[k_prev, idx_hist_f]

                # 2. Recuperar Conductancias
                # branch.Gc es G_serie (lo definimos así en line.py)
                Gc_ser_full = np.asarray(branch.Gc, dtype=float)
                Gc_ser = Gc_ser_full[np.ix_(mask, mask)]

                # branch.Gff contiene (G_serie + G_shunt).
                # Por tanto: G_shunt = Gff - Gc
                Gff_full = np.asarray(branch.Gff, dtype=float)
                Gff = Gff_full[np.ix_(mask, mask)]
                G_sh = Gff - Gc_ser  # Extraemos la G del condensador

                # 3. CÁLCULO DE HISTORIA SERIE (RL - Trapecio)
                v_diff_prev = vf_prev - vt_prev
                I_h_ser = (Gc_ser @ v_diff_prev) + i_ser_prev

                # 4. CÁLCULO DE HISTORIA SHUNT (C - Backward Euler)
                # MNA: G*v(t) = i(t) + G*v(t-h)
                # El término RHS (historia) es +G*v(t-h).
                # Como el driver hace 'Is - hist', 'hist' debe ser -G*v(t-h).
                I_h_sh_f = -1.0 * (G_sh @ vf_prev)
                I_h_sh_t = -1.0 * (G_sh @ vt_prev)

                # 5. Guardar historia de RAMA (Solo parte serie para el buffer I_branches)
                # Esto es importante para que update_Ibranches funcione bien luego
                hist_branches[idx_hist_f] = I_h_ser
                hist_branches[idx_hist_t] = -I_h_ser

                # 6. Acumular en Vector Nodal (INCLUYENDO SHUNT)
                # Nodo From: Sale corriente serie, entra inyección shunt from
                # hist_step se resta en el solver (Is - hist).
                # Queremos inyectar (I_h_ser + I_h_sh_f).
                # Entonces hist += I_h_ser + I_h_sh_f
                hist_step[idx_from] += (I_h_ser + I_h_sh_f)

                # Nodo To: Entra corriente serie (-I_h_ser), entra inyección shunt to
                hist_step[idx_to] += (-I_h_ser + I_h_sh_t)

            elif model == 'JMarti':
                # --- J-MARTI (Frequency Dependent) ---
                # Recuperar parámetros de ajuste (Vector Fitting)
                # Se asume que 'branch' tiene estos atributos cargados
                yc_poles = getattr(branch, 'Yc_poles', np.array([]))
                yc_res = getattr(branch, 'Yc_residues', np.array([]))
                h_poles = getattr(branch, 'H_poles', np.array([]))
                h_res = getattr(branch, 'H_residues', np.array([]))

                # Estado actual de la memoria recursiva
                st = line_states[branch.name]['x_states']

                # Inicialización "lazy" si no se hizo antes
                if st is None:
                    n_yc, n_h = len(yc_poles), len(h_poles)
                    st = {
                        'yc_f': np.zeros((n_yc, Np), dtype=complex),
                        'yc_t': np.zeros((n_yc, Np), dtype=complex),
                        'h_f': np.zeros((n_h, Np), dtype=complex),
                        'h_t': np.zeros((n_h, Np), dtype=complex)
                    }
                    line_states[branch.name]['x_states'] = st

                # 1. Historia Local (Yc)
                k_prev = (step - 1) % (N_delay + 1)
                vf_prev = V_hist_buffer[k_prev, idx_from]
                vt_prev = V_hist_buffer[k_prev, idx_to]

                Ih_yc_f = np.zeros(Np, dtype=complex)
                Ih_yc_t = np.zeros(Np, dtype=complex)

                # Convolución Yc (Nodo From)
                for i, p in enumerate(yc_poles):
                    c = yc_res[i]
                    denom = 2.0 - p * h
                    alpha = (2.0 + p * h) / denom
                    beta = (c * h) / denom

                    # h_term = alpha * x(t-h) + beta * v(t-h)
                    h_term = alpha * st['yc_f'][i] + beta * vf_prev
                    Ih_yc_f += h_term

                # Convolución Yc (Nodo To)
                for i, p in enumerate(yc_poles):
                    c = yc_res[i]
                    denom = 2.0 + p * h
                    alpha = (2.0 - p * h) / denom
                    beta = (c * h) / denom

                    h_term = alpha * st['yc_t'][i] + beta * vt_prev
                    Ih_yc_t += h_term

                # 2. Historia Propagación (H)
                delay = branch.Ndelay
                k_tau = (step - delay) % (N_delay + 1)

                vf_tau, vt_tau = V_hist_buffer[k_tau, idx_from], V_hist_buffer[k_tau, idx_to]
                if_tau, it_tau = I_hist_buffer[k_tau, idx_hist_f], I_hist_buffer[k_tau, idx_hist_t]

                # Impedancia característica aprox (inversa de Gc)
                Gc = np.asarray(branch.Gc, dtype=float)[np.ix_(mask, mask)]
                Zc_inf = np.linalg.inv(Gc)

                # Ondas viajeras incidentes
                f_inc_to_from = vt_tau + Zc_inf @ it_tau  # De T a F
                f_inc_from_to = vf_tau + Zc_inf @ if_tau  # De F a T

                Ih_prop_f = np.zeros(Np, dtype=complex)
                Ih_prop_t = np.zeros(Np, dtype=complex)

                if len(h_poles) == 0:
                    # Fallback Bergeron
                    Ih_prop_f = -0.5 * (Gc @ f_inc_to_from)
                    Ih_prop_t = -0.5 * (Gc @ f_inc_from_to)
                else:
                    # Convolución H
                    for i, p in enumerate(h_poles):
                        c = h_res[i]
                        denom = 2.0 + p * h
                        alpha = (2.0 - p * h) / denom
                        beta = (c * h) / denom

                        # Onda llegando a F
                        prev_state = st['h_f'][i]
                        u_curr = f_inc_to_from
                        new_state = alpha * prev_state + beta * u_curr
                        st['h_f'][i] = new_state
                        Ih_prop_f += new_state

                    # Onda llegando a T
                    for i, p in enumerate(h_poles):
                        c = h_res[i]
                        denom = 2.0 + p * h
                        alpha = (2.0 - p * h) / denom
                        beta = (c * h) / denom

                        prev_state = st['h_t'][i]
                        u_curr = f_inc_from_to
                        new_state = alpha * prev_state + beta * u_curr
                        st['h_t'][i] = new_state
                        Ih_prop_t += new_state

                # Total History para MNA: Is - I_hist = G V
                I_hist_f_val = 2 * Ih_prop_f - Ih_yc_f
                I_hist_t_val = 2 * Ih_prop_t - Ih_yc_t

                hist_branches[idx_hist_f] = I_hist_f_val.real  # Tomamos parte real por seguridad numérica
                hist_branches[idx_hist_t] = I_hist_t_val.real

                hist_step[idx_from] += I_hist_f_val.real
                hist_step[idx_to] += I_hist_t_val.real

        # ---- transformers history components ----
        elif branch.device_type.value == 'Transformer':  # Transformer2WDevice = 'Transformer'
            # k_delay = (step - 1)% (1 + 1)
            k_delay = (step - 1) % (N_delay + 1)

            v_delay_f = V_hist_buffer[k_delay, idx_from]
            v_delay_t = V_hist_buffer[k_delay, idx_to]

            i_delay_ft = I_hist_buffer[k_delay, idx_hist_f]
            i_delay_tf = I_hist_buffer[k_delay, idx_hist_t]

            Vfrom = branch.bus_from.Vnom
            Vto = branch.bus_to.Vnom
            hv = max(Vfrom, Vto)

            # find bus high
            if hv == Vfrom:  # bus "from" is the primary
                v_delay_h = v_delay_f
                v_delay_l = v_delay_t

                i_delay_h = i_delay_ft
                i_delay_l = i_delay_tf

            else:  # bus "to" is the primary
                v_delay_h = v_delay_t
                v_delay_l = v_delay_f

                i_delay_h = i_delay_tf
                i_delay_l = i_delay_ft

            L_hh = branch.L_hh
            L_ll = branch.L_ll
            L_hl = branch.L_hl

            D = L_hh * L_ll - L_hl * L_hl
            if abs(D) < 1e-18:
                raise RuntimeError(f"Ill-conditioned transformer inductance matrix: D={D}")

            I_hist_h = i_delay_h + (h / (2 * (L_hh * L_ll - L_hl * L_hl))) * (L_ll - L_hl) * v_delay_h + (
                    h * L_hl / (2 * (L_hh * L_ll - L_hl * L_hl))) * (v_delay_h - v_delay_l)
            I_hist_l = i_delay_l + (h / (2 * (L_hh * L_ll - L_hl * L_hl))) * (L_hh - L_hl) * v_delay_l + (
                    h * L_hl / (2 * (L_hh * L_ll - L_hl * L_hl))) * (v_delay_l - v_delay_h)

            # add history components from the trafo to the history vector at the current timestep
            if hv == Vfrom:
                hist_step[idx_from] += I_hist_h
                hist_step[idx_to] += I_hist_l
            else:
                hist_step[idx_from] += I_hist_l
                hist_step[idx_to] += I_hist_h

        # todo: consider LC from the load

    return hist_step


def check_Vini(nc: NumericalCircuit,
               step: int,
               grid: MultiCircuit,
               Vsol: np.ndarray, ):
    """
    Paste Vfrom=Vto to bos_to when t<tau for each line
    :param nc: NumericalCircuit
    :return Is_step: np array
    """

    V_correct = np.copy(Vsol)

    return V_correct


def update_Is(emt_simulation_driver: EmtSimulationDriver,
              Vsol: np.ndarray,
              nc: NumericalCircuit,
              step: int,
              grid: MultiCircuit,
              h: float,
              binary_bus_mask: BoolVec,
              bus_idx_lookup: IntVec,
              emt_vec: Vector):
    """
    Update the current sources vector Is for arbitrary phase configurations.
    :param emt_simulation_driver: EmtSimulationDriver
    :param Vprev: np.ndarray. voltage solution at previous timestep V[step-1, :]
    :param nc: NumericalCircuit
    :param step: int
    :param grid: MultiCircuit
    :param h: float. time-step
    :param binary_bus_mask: BoolVec
    :param bus_idx_lookup : IntVec
    :param emt_vec: Vector
    :return Is_step: np array
    """
    n = nc.bus_data.nbus
    Is_step = np.zeros(n * 4, dtype=float)

    for i, bus in enumerate(
            grid.get_buses()):  # solve 1 step of the symbolic blocs in each bus (only if the bus has a symbolic block)
        emt: EmtSolverProperties = emt_vec[i]
        if emt.blocksolver is not None:  # only if there are injections in the bus

            # update v_abc in alter_params0 with the V solution from the MNA
            idx = 4 * i + np.array([0, 1, 2, 3])
            net_idx = np.asarray(bus_idx_lookup)[idx]
            v_n, v_a, v_b, v_c = [Vsol[i] if i >= 0 else 0.0 for i in net_idx]

            alter_params0 = np.array([v_n, v_a, v_b, v_c], dtype=float)
            alter_params0 = alter_params0[binary_bus_mask[idx]]
            print(f"step{step} predicted voltages bus {i}: v_a = {v_a}, v_b = {v_b}, v_c = {v_c}")

            emt.set_alter_params0(alter_params0)

            # simulate just 1 timestep
            slv = emt.blocksolver

            _, y, dx, _ = slv.simulate(
                t0=(step - 1) * h,
                t_end=step * h + 1e-10,  # h + 1e-10,  # just one timestep simulation
                # t0=0,
                # t_end=h + 1e-10,  # just one timestep simulation
                h=h,
                x0=emt.x0,
                dx0=emt.dx0,
                params0=emt.params0,  # not used
                alter_params0=emt.alter_params0,
                method=emt_simulation_driver.options.integration_method,
                newton_tol=emt_simulation_driver.options.tolerance,
                newton_max_iter=1000,
                followed_vars=None,
                initialized=False,
                verbose=False,
            )
            print(f"step{step} solution: y = {y[1, :]}")
            print(f"step{step} solution: dx = {dx[1, :]}")
            # paste results to the EmtSolverProperties
            emt.x[step, :] = y[1, :]
            emt.dx[step, :] = dx[1, :]

            # paste current results to the Is array
            for dev_type, dev_list in emt.devices.items():
                for elm in dev_list:
                    i_s_bus = np.zeros(4, dtype=float)
                    for var in elm.emt_model.model.out_vars:
                        if str(var) == 'i_n':
                            i_n_idx = slv.uid2idx_vars[var.uid]
                            i_s_bus[0] = y[1, i_n_idx]
                        elif str(var) == 'i_a':
                            i_a_idx = slv.uid2idx_vars[var.uid]
                            i_s_bus[1] = y[1, i_a_idx]
                        elif str(var) == 'i_b':
                            i_b_idx = slv.uid2idx_vars[var.uid]
                            i_s_bus[2] = y[1, i_b_idx]
                        elif str(var) == 'i_c':
                            i_c_idx = slv.uid2idx_vars[var.uid]
                            i_s_bus[3] = y[1, i_c_idx]

                    Is_step[idx] += i_s_bus
                    if dev_type.name == 'GeneratorDevice':
                        # plus the generator history component due to the interfacing resistor v(t-dt)/ Rp
                        # Gp = (1 / elm.Rp) * np.eye(4)
                        # Is_step[idx] += np.array([v_n, v_a, v_b, v_c], dtype=float) @ Gp
                        # Is_step[idx] += elm.Gc @ np.array([v_n, v_a, v_b, v_c], dtype=float)
                        #
                        Is_step[idx] += elm.Gc @ np.array([v_n, v_a, v_b, v_c], dtype=float)

    Is_step = Is_step[binary_bus_mask]

    return Is_step


def update_Ibranches(nc: NumericalCircuit,
                     V: np.ndarray,
                     hist_branches: np.ndarray,
                     grid: MultiCircuit,
                     step: int,
                     h: float,
                     N_delay: int,
                     bus_idx_lookup: IntVec,
                     branch_from_lookup: IntVec,
                     branch_to_lookup: IntVec,
                     total_branch_currents: int,
                     line_states: Dict):
    """
    Compute instantaneous line currents for multi-phase lines.
    :param nc: NumericalCircuit
    :param V: 1D array (N_active_nodes,) reduced nodal voltages
    :param hist_branches: 1D array (total_branch_currents,) history currents for each branch row (this step)
    :param V_hist_buffer: (N_delay+1, N_active_nodes)
    :param I_hist_buffer: (N_delay+1, total_branch_currents)
    :param grid: MultiCircuit
    :param step: current timestep index
    :param N_delay: max delay in steps
    :param bus_idx_lookup: length 4*nbus, from full (4*bus) index → reduced node index (or -1)
    :param branch_from_lookup: length 4*nl, from full branch-row index → reduced line-current index (or -1)
    :param branch_to_lookup: length 4*nl, from full branch-row index → reduced line-current index (or -1)
    :return: Ibranches_step (1 x n_line_cond) where n_line_cond = I_hist_buffer.shape[1]
    """
    bus_idx_lookup = np.asarray(bus_idx_lookup, dtype=int)
    Ibranches_step = np.zeros(total_branch_currents, dtype=float)

    idx4 = np.array([0, 1, 2, 3], dtype=int)  # N, A, B, C

    # Iterate through branches
    for k, branch in enumerate(grid.get_branches_iter()):
        f = nc.passive_branch_data.F[k]
        t = nc.passive_branch_data.T[k]

        f4 = 4 * f + idx4
        t4 = 4 * t + idx4

        idx_from_red = bus_idx_lookup[f4]  # shape (4,)
        idx_to_red = bus_idx_lookup[t4]  # shape (4,)

        phase_mask = (idx_from_red >= 0) & (idx_to_red >= 0)
        mask = phase_mask
        if not np.any(phase_mask):
            # No active phases for this line
            continue

        idx_from = idx_from_red[phase_mask]
        idx_to = idx_to_red[phase_mask]
        Np = len(idx_from)

        row_base = 4 * k + idx4

        idx_hist_f = branch_from_lookup[row_base][phase_mask]
        idx_hist_t = branch_to_lookup[row_base][phase_mask]

        if len(idx_hist_f) != Np or len(idx_hist_t) != Np:
            raise RuntimeError(
                f"Inconsistent indexing in update_Ibranches for line {branch.name}: "
                f"Np={Np}, len(idx_hist_f)={len(idx_hist_f)}, len(idx_hist_t)={len(idx_hist_t)}"
            )

        # ---- lines currents ----
        if branch.device_type.value == 'Line':  # DeviceType.LineDevice:

            model = getattr(branch, 'model_type', 'Bergeron')

            V_f = V[idx_from]
            V_t = V[idx_to]
            hist_f = hist_branches[idx_hist_f]
            hist_t = hist_branches[idx_hist_t]

            Gc_full = np.asarray(branch.Gc, dtype=float)
            Gc = Gc_full[np.ix_(phase_mask, phase_mask)]

            if model == 'Pi':
                # Modelo Pi: I_series(t) = Gc * (Vf - Vt) + I_hist
                # Nota: Gc en Pi es inv(R + 2L/h)
                I_ser = Gc @ (V_f - V_t) + hist_f

                Ibranches_step[idx_hist_f] = I_ser
                Ibranches_step[idx_hist_t] = -I_ser  # La corriente en el otro extremo es opuesta

            elif model == 'Bergeron':
                I_ft = Gc @ V_f + hist_f
                I_tf = Gc @ V_t + hist_t

                Ibranches_step[idx_hist_f] = I_ft
                Ibranches_step[idx_hist_t] = I_tf

                # Update history buffers for the next time shift (t - τ) for lines
                # delay = branch.Ndelay #todo: RECENTLY CHANGED!
                # kbuf = step % (N_delay + 1)
                # V_hist_buffer[kbuf, :] = V
                # I_hist_buffer[kbuf, idx_hist_f] = Ibranches_step[idx_hist_f]
                # I_hist_buffer[kbuf, idx_hist_t] = Ibranches_step[idx_hist_t]

                # delay = branch.Ndelay
                # kbuf = step % (delay + 1)
                # V_hist_buffer[kbuf, :] = V
                # I_hist_buffer[kbuf, :] = Ibranches_step

            elif model == 'JMarti':
                # 1. Calcular corriente instantánea
                # I_branch(t) = Gc * V(t) + I_hist_branch
                # (I_hist_branch ya fue calculado en update_Hist y pasado aquí en hist_branches)

                Gc = np.asarray(branch.Gc, dtype=float)[np.ix_(mask, mask)]
                I_ft = Gc @ V_f + hist_f
                I_tf = Gc @ V_t + hist_t

                Ibranches_step[idx_hist_f] = I_ft
                Ibranches_step[idx_hist_t] = I_tf

                # 2. ACTUALIZAR ESTADOS Yc (CRÍTICO)
                # x(t) = alpha * x(t-h) + beta * (v(t) + v(t-h))

                st = line_states[branch.name]['x_states']
                if st is not None:
                    yc_poles = getattr(branch, 'Yc_poles', np.array([]))
                    yc_res = getattr(branch, 'Yc_residues', np.array([]))

                    k_prev = (step - 1) % (N_delay + 1)
                    vf_prev = V_hist_buffer[k_prev, idx_from]
                    vt_prev = V_hist_buffer[k_prev, idx_to]

                    # Actualizar estados Nodo F
                    for i, p in enumerate(yc_poles):
                        c = yc_res[i]
                        denom = 2.0 + p * h
                        alpha = (2.0 - p * h) / denom
                        beta = (c * h) / denom

                        x_prev = st['yc_f'][i]
                        # Ecuación de estado recursiva completa
                        st['yc_f'][i] = alpha * x_prev + beta * (V_f + vf_prev)

                    # Actualizar estados Nodo T
                    for i, p in enumerate(yc_poles):
                        c = yc_res[i]
                        denom = 2.0 + p * h
                        alpha = (2.0 - p * h) / denom
                        beta = (c * h) / denom

                        x_prev = st['yc_t'][i]
                        st['yc_t'][i] = alpha * x_prev + beta * (V_t + vt_prev)


        elif branch.device_type.value == 'Transformer':  # Transformer2WDevice = 'Transformer'

            hist_f = hist_branches[idx_hist_f]
            hist_t = hist_branches[idx_hist_t]

            k_delay = step - 1

            Vfrom = branch.bus_from.Vnom
            Vto = branch.bus_to.Vnom
            hv = max(Vfrom, Vto)

            V_f = V[idx_from]
            V_t = V[idx_to]

            # find bus high
            if hv == Vfrom:  # bus "from" is the primary
                I_hist_h = hist_f
                I_hist_l = hist_t

                v_h = V_f
                v_l = V_t

            else:  # bus "to" is the primary
                I_hist_h = hist_t
                I_hist_l = hist_f

                v_h = V_t
                v_l = V_f

            L_hh = branch.L_hh
            L_ll = branch.L_ll
            L_hl = branch.L_hl

            i_h = I_hist_h + (h / (2 * (L_hh * L_ll - L_hl * L_hl))) * (L_ll - L_hl) * v_h + (
                    h * L_hl / (2 * (L_hh * L_ll - L_hl * L_hl))) * (v_h - v_l)
            i_l = I_hist_l + (h / (2 * (L_hh * L_ll - L_hl * L_hl))) * (L_hh - L_hl) * v_l + (
                    h * L_hl / (2 * (L_hh * L_ll - L_hl * L_hl))) * (v_l - v_h)

            if hv == Vfrom:  # bus "from" is the primary
                Ibranches_step[idx_hist_f] = i_h
                Ibranches_step[idx_hist_t] = i_l

            else:  # bus "to" is the primary
                Ibranches_step[idx_hist_f] = i_l
                Ibranches_step[idx_hist_t] = i_h

            # Update history buffers for the next time shift (t - h) for transformers
            # TODO: wrong implementation, it overwrites lines and trafos!!!!
            # kbuf = step % (1 + 1)
            # V_hist_buffer[kbuf, :] = V
            # I_hist_buffer[kbuf, idx_hist_f] = Ibranches_step[idx_hist_f]
            # I_hist_buffer[kbuf, idx_hist_t] = Ibranches_step[idx_hist_t]

        # kbuf = step % (N_delay + 1)
        # V_hist_buffer[kbuf, :] = V
        # I_hist_buffer[kbuf, :] = Ibranches_step

    return Ibranches_step


def set_V0_bus(alter_params_mapping: Dict[int, Const],
               uid2idx_alterparams: Dict[int, int],
               bus: dev.Bus,
               i: int,
               nc: NumericalCircuit,
               binary_bus_mask: BoolVec):
    """
    Set init guess solution to the first step in the simulation
    :param emt_vec_bus: EmtSolverProperties
    :param i: int. Bus index
    :param nc: NumericalCircuit
    :return :
    """
    v_n = v_a = v_b = v_c = 0.0
    alter_params = bus.emt_model.model.alter_params

    for uid, const in alter_params_mapping.items():
        idx = uid2idx_alterparams[uid]
        var = alter_params[idx]
        val = const.value

        if var.name == "v_n":
            v_n = val
        elif var.name == "v_a":
            v_a = val
        elif var.name == "v_b":
            v_b = val
        elif var.name == "v_c":
            v_c = val

    V0 = np.zeros((1, 4 * len(nc.bus_dict)))
    V0[0, 4 * i + 0] = v_n
    V0[0, 4 * i + 1] = v_a
    V0[0, 4 * i + 2] = v_b
    V0[0, 4 * i + 3] = v_c

    V0 = V0[0, binary_bus_mask]

    # v_n = v_a = v_b = v_c = 0.0
    # if emt_vec_bus.alter_params0 is not None:
    #     uid2idx_alterparams = emt_vec_bus.blocksolver.uid2idx_alterparams
    #     alter_params = emt_vec_bus.blocksolver.alter_params
    #     alter_params0 = emt_vec_bus.alter_params0
    #
    #     for uid, idx in uid2idx_alterparams.items():
    #         var = alter_params[idx]
    #         val = alter_params0[idx]
    #
    #         if var.name == "v_n":
    #             v_n = val
    #         elif var.name == "v_a":
    #             v_a = val
    #         elif var.name == "v_b":
    #             v_b = val
    #         elif var.name == "v_c":
    #             v_c = val
    #
    # V0 = np.zeros((1, 4 * len(nc.bus_dict)))
    # V0[0, 4 * i + 0] = v_n
    # V0[0, 4 * i + 1] = v_a
    # V0[0, 4 * i + 2] = v_b
    # V0[0, 4 * i + 3] = v_c
    #
    # V0 = V0[0, binary_bus_mask]

    return V0


def set_I0_bus(emt_vec_bus: EmtSolverProperties,
               i: int,
               nc: NumericalCircuit,
               init_guesses: List[Dict[int, float]],
               binary_bus_mask: BoolVec,
               bus_idx_lookup: IntVec,
               V: np.ndarray):
    uid2idx_vars = emt_vec_bus.blocksolver.uid2idx_vars
    vars_all = (
            emt_vec_bus.blocksolver.state_vars +
            emt_vec_bus.blocksolver.algebraic_vars
    )
    init_guess = init_guesses[i]
    i_n = i_a = i_b = i_c = 0.0
    for uid, val in init_guess.items():
        index = uid2idx_vars.get(uid)
        if index is None:
            raise ValueError(f"Missing variable uid {uid} in uid2idx_vars")
        var = vars_all[index]
        if var.name == "i_n":
            i_n = val
        elif var.name == "i_a":
            i_a = val
        elif var.name == "i_b":
            i_b = val
        elif var.name == "i_c":
            i_c = val

    Is0 = np.zeros((1, 4 * len(nc.bus_dict)))
    Is0[0, 4 * i + 0] += i_n
    Is0[0, 4 * i + 1] += i_a
    Is0[0, 4 * i + 2] += i_b
    Is0[0, 4 * i + 3] += i_c

    if emt_vec_bus.blocksolver is not None:
        idx = 4 * i + np.array([0, 1, 2, 3])
        net_idx = np.asarray(bus_idx_lookup)[idx]
        v_n, v_a, v_b, v_c = [V[i] if i >= 0 else 0.0 for i in net_idx]
        for dev_type, dev_list in emt_vec_bus.devices.items():
            for elm in dev_list:
                if dev_type.name == 'GeneratorDevice':
                    # Is0[idx] += np.array([v_n, v_a, v_b, v_c], dtype=float) @ elm.Gc
                    Ir0 = elm.Gc @ np.array([v_n, v_a, v_b, v_c], dtype=float)
                    # Is0[idx] +=Ir0.reshape(-1, 1)
                    Is0[0, idx] = Ir0

    Is0 = Is0[0, binary_bus_mask]

    return Is0
