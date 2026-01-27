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
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.Devices.Substation.bus import Bus

from VeraGridEngine.basic_structures import Vec, IntVec, Mat, Vector, BoolVec, CxVec
from VeraGridEngine.Simulations.EMT.emt_solver_properties import EmtSolverProperties
from VeraGridEngine.Simulations.EMT.Devices.emt_circuit import EmtCircuit

from scipy.sparse.linalg import factorized


def predict_Is(n: int,
               Vprev: np.ndarray,
               step: int,
               h: float,
               binary_bus_mask: BoolVec,
               bus_idx_lookup: IntVec,
               emt_vec: Vector,
               integration_method: DynamicIntegrationMethod,
               tolerance: float,
               verbose: int = 0
               ) -> Vec:
    """

    :param n:
    :param Vprev:
    :param step:
    :param h:
    :param binary_bus_mask:
    :param bus_idx_lookup:
    :param emt_vec:
    :param integration_method:
    :param tolerance:
    :param verbose:
    :return:
    """

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
    Is_step: Vec = np.zeros(n * 4, dtype=float)

    # solve 1 step of the symbolic blocs in each bus (only if the bus has a symbolic block)
    for i in range(n):

        emt: EmtSolverProperties = emt_vec[i]

        if emt.blocksolver is not None:  # only if there are injections in the bus
            # update x0, dx0 with x, dx from the previous state if it's not the first iter
            x0 = emt.x[step - 1, :]
            dx0 = emt.dx[step - 1, :]
            emt.x0 = x0
            emt.dx0 = dx0

            # update v_abc in alter_params0
            idx = 4 * i + np.array([0, 1, 2, 3])
            net_idx = bus_idx_lookup[idx]
            v_nabc: Vec = np.array([Vprev[i] if i >= 0 else 0.0 for i in net_idx], dtype=float)
            v_nabc = v_nabc[binary_bus_mask[idx]]

            if verbose:
                print(f"step{step} previous voltages bus {i}: "
                      f"v_a = {v_nabc[0]}, "
                      f"v_b = {v_nabc[1]}, "
                      f"v_c = {v_nabc[2]}")

            emt.set_alter_params0(v_nabc)

            # simulate just 1 timestep
            slv = emt.blocksolver

            _, y, dx, _ = slv.simulate(
                # t0=(step - 1) * h,
                # t_end=step * h + 1e-10,  # h + 1e-10,  # just one timestep simulation
                t0=0,
                t_end=h + 1e-10,  # just one timestep simulation
                h=h,
                x0=emt.x0,
                dx0=emt.dx0,
                params0=emt.params0,  # not used
                alter_params0=emt.alter_params0,
                method=integration_method,
                newton_tol=tolerance,
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

                    i_s_bus: Vec = np.zeros(4, dtype=float)

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
                        Is_step[idx] += elm.Gc @ v_nabc

    Is_step = Is_step[binary_bus_mask]

    return Is_step


def update_Hist(n_nodes: int,
                nc: NumericalCircuit,
                step: int,
                V_buffer: np.ndarray,
                I_lines_buffer: np.ndarray,
                I_magn_buffer: np.ndarray,
                hist_branches: np.ndarray,
                hist_magn_trafos: np.ndarray,
                grid: MultiCircuit,
                N_delay: int,
                h: float,
                branch_from_lookup: IntVec,
                branch_to_lookup: IntVec,
                bus_idx_lookup: IntVec,
                line_states: Dict):
    """

    :param n_nodes: number of nodes effective for simulation (np.sum(bus_idx_lookup >= 0))
    :param nc:
    :param step:
    :param V_buffer:
    :param I_lines_buffer:
    :param I_magn_buffer:
    :param hist_branches:
    :param hist_magn_trafos:
    :param grid:
    :param N_delay:
    :param h:
    :param branch_from_lookup:
    :param branch_to_lookup:
    :param bus_idx_lookup:
    :param line_states:
    :return:
    """
    """
    Update history currents for lines (Bergeron) in a multi-phase setting.

    :param nc: NumericalCircuit
    :param step: current time step index
    :param V_buffer: (N_delay+1, total_cond)
    :param I_lines_buffer: (N_delay+1, 2*max_phases_line*nl)
    :param hist_branches: 1D array with current history for all line ends at this step
    :param grid: MultiCircuit
    :param N_delay: max delay in steps (for the longest line)
    :param h: time step (not used here but kept for future extensions)
    :param branch_from_lookup:
    :param branch_to_lookup:
    :param bus_idx_lookup:
    :return: hist_step (1 x total_cond)
    """
    n = dta.n_bus

    hist_step = np.zeros(n_nodes, dtype=float)

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

            model = branch.emt_model_type

            if model == "Bergeron":
                delay = branch.Ndelay

                # k_delay = (step - delay) % (N_delay + 1)
                k_delay = 1
                print(f"k_delay en update_hist = {k_delay} step = {step}")

                v_delay_f = V_buffer[k_delay, idx_from]
                v_delay_t = V_buffer[k_delay, idx_to]

                i_delay_ft = I_lines_buffer[k_delay, idx_hist_f]
                i_delay_tf = I_lines_buffer[k_delay, idx_hist_t]

                print(
                    f"corriente linea en el step anterior from i_delay_ft= I_lines_buffer[k_delay, idx_hist_f] = {i_delay_ft} at step = {step}")
                print(
                    f"corriente linea en el step anterior to i_delay_tf = I_lines_buffer[k_delay, idx_hist_t] = {i_delay_tf} at step = {step}")
                print(
                    f"tensión buses en el step anterior from v_delay_f = V_buffer[k_delay, idx_from] = {v_delay_f} at step = {step}")
                print(
                    f"tensión buses en el step anterior from v_delay_t = V_buffer[k_delay, idx_to] = {v_delay_t} at step = {step}")

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
                vf_prev = V_buffer[k_prev, idx_from]
                vt_prev = V_buffer[k_prev, idx_to]
                i_ser_prev = I_lines_buffer[k_prev, idx_hist_f]

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
                vf_prev = V_buffer[k_prev, idx_from]
                vt_prev = V_buffer[k_prev, idx_to]

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

                vf_tau, vt_tau = V_buffer[k_tau, idx_from], V_buffer[k_tau, idx_to]
                if_tau, it_tau = I_lines_buffer[k_tau, idx_hist_f], I_lines_buffer[k_tau, idx_hist_t]

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
            k_delay = 1
            # k_delay = (step - 1) % (N_delay + 1)
            print(f"k_delay en update_hist = {k_delay} step = {step}")

            v_delay_f = V_buffer[k_delay, idx_from]
            v_delay_t = V_buffer[k_delay, idx_to]

            i_delay_ft = I_lines_buffer[k_delay, idx_hist_f]
            i_delay_tf = I_lines_buffer[k_delay, idx_hist_t]

            print(
                f"corriente trafo en el step anterior from i_delay_ft= I_lines_buffer[k_delay, idx_hist_f] = {i_delay_ft} at step = {step}")
            print(
                f"corriente trafo en el step anterior to i_delay_tf = I_lines_buffer[k_delay, idx_hist_t] = {i_delay_tf} at step = {step}")
            print(
                f"tensión buses en el step anterior from v_delay_f = V_buffer[k_delay, idx_from] = {v_delay_f} at step = {step}")
            print(
                f"tensión buses en el step anterior from v_delay_t = V_buffer[k_delay, idx_to] = {v_delay_t} at step = {step}")

            Vfrom = branch.bus_from.Vnom
            Vto = branch.bus_to.Vnom
            hv = max(Vfrom, Vto)
            lv = min(Vfrom, Vto)

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
            Llk = branch.X_leack
            Rlk = branch.R_leack
            Lm = branch.X_magn
            Rm = branch.R_magn

            D = L_hh * L_ll - L_hl * L_hl
            if abs(D) < 1e-18:
                raise RuntimeError(f"Ill-conditioned transformer inductance matrix: D={D}")

            k = h / (2.0 * D)

            I_hist_h = i_delay_h + k * (L_hl * v_delay_l - L_ll * v_delay_h)
            I_hist_l = i_delay_l + k * (L_hl * v_delay_h - L_hh * v_delay_l)
            # I_hist_h = i_delay_h #- k * (L_hl * v_delay_l - L_ll * v_delay_h)
            # I_hist_l =  i_delay_l #- k * (L_hl * v_delay_h - L_hh * v_delay_l)

            # I_hist_h = i_delay_h - (1/((2*D/(h * Lm))+Rm)) * (v_delay_h - v_delay_l) - (1/((2*D/(h * Llk/2))+ Rlk/2)) * v_delay_h
            # I_hist_l = i_delay_l - (1/((2*D/(h * Lm))+Rm)) * (v_delay_l - v_delay_h) - (1/((2*D/(h * Llk/2))+ Rlk/2)) * v_delay_l

            # print(f"término from  G*vprev= k * (L_ll * v_delay_h - L_hl * v_delay_l) = {k * (L_ll * v_delay_h - L_hl * v_delay_l)} at step = {step}")
            # print(f"término to  G*vprev= k * (L_hh * v_delay_l - L_hl * v_delay_h) = {k * (L_hh * v_delay_l - L_hl * v_delay_h)} at step = {step}")
            # print(f"history current que estoy construyendo from I_hist_f=  -( i_delay_h + k * (L_ll * v_delay_h - L_hl * v_delay_l))= {-I_hist_h} at step = {step}")
            # print(f"history current que estoy construyendo to I_hist_l=  -( i_delay_l + k * (L_hh * v_delay_l - L_hl * v_delay_h)))= {-I_hist_l} at step = {step}")

            print(f"I_hist_h transformer = {I_hist_h} at step{step}")
            print(f"I_hist_l transformer = {I_hist_l} at step{step}")

            # magnetizing current history calculation: ASSUMED IN THE PRIMARY BRANCH

            if hv == Vfrom:
                I_magn_delay = I_magn_buffer[k_delay, idx_from]
            else:
                I_magn_delay = I_magn_buffer[k_delay, idx_to]

            I_hist_magn = I_magn_delay + branch.Gm[1:, 1:] @ v_delay_h

            # add history components from the trafo to the history vector at the current timestep
            if hv == Vfrom:
                # history bus vector
                hist_step[idx_from] += I_hist_h + I_hist_magn
                hist_step[idx_to] += I_hist_l  ###############################
                # history of the branch itself
                hist_branches[idx_hist_f] = I_hist_h
                hist_branches[idx_hist_t] = I_hist_l
                # history of the magnetizing current in trafos
                hist_magn_trafos[idx_from] = I_hist_magn

            else:
                # history bus vector
                hist_step[idx_from] += I_hist_l  ##############################
                hist_step[idx_to] += I_hist_h + I_hist_magn
                # history of the branch itself
                hist_branches[idx_hist_f] = I_hist_l
                hist_branches[idx_hist_t] = I_hist_h
                # history of the magnetizing current in trafos
                hist_magn_trafos[idx_to] = I_hist_magn

        # todo: consider LC from the load

    return hist_step


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
    n = dta.n_bus
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
            # print(f"step{step} predicted voltages bus {i}: v_a = {v_a}, v_b = {v_b}, v_c = {v_c}")

            emt.set_alter_params0(alter_params0)

            # simulate just 1 timestep
            slv = emt.blocksolver

            _, y, dx, _ = slv.simulate(
                # t0=(step-1)*h,
                # t_end=step*h + 1e-10, #h + 1e-10,  # just one timestep simulation
                t0=0,
                t_end=h + 1e-10,  # just one timestep simulation
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
                     hist_magn_trafos: np.ndarray,
                     V_buffer: np.ndarray,
                     I_lines_buffer: np.ndarray,
                     I_magn_buffer: np.ndarray,
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
    :param V_buffer: (N_delay+1, N_active_nodes)
    :param I_lines_buffer: (N_delay+1, total_branch_currents)
    :param grid: MultiCircuit
    :param step: current timestep index
    :param N_delay: max delay in steps
    :param bus_idx_lookup: length 4*nbus, from full (4*bus) index → reduced node index (or -1)
    :param branch_from_lookup: length 4*nl, from full branch-row index → reduced line-current index (or -1)
    :param branch_to_lookup: length 4*nl, from full branch-row index → reduced line-current index (or -1)
    :return: Ibranches_step (1 x n_line_cond) where n_line_cond = I_lines_buffer.shape[1]
    """
    bus_idx_lookup = np.asarray(bus_idx_lookup, dtype=int)
    Nbranches_masked = int(total_branch_currents / 2)
    Ibranches_step = np.zeros(total_branch_currents, dtype=float)
    I_magn_step = np.zeros(Nbranches_masked, dtype=float)

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

            model = branch.emt_model_type

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
                    vf_prev = V_buffer[k_prev, idx_from]
                    vt_prev = V_buffer[k_prev, idx_to]

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

            # k_delay = (step - 1 )% (1 + 1)
            k_delay = 1

            Vfrom = branch.bus_from.Vnom
            Vto = branch.bus_to.Vnom
            hv = max(Vfrom, Vto)
            lv = min(Vfrom, Vto)

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
            Llk = branch.X_leack
            Rlk = branch.R_leack
            Lm = branch.X_magn
            Rm = branch.R_magn

            D = L_hh * L_ll - L_hl * L_hl
            k = h / (2.0 * D)

            i_h = I_hist_h + k * (L_ll * v_h - L_hl * v_l)
            i_l = I_hist_l + k * (L_hh * v_l - L_hl * v_h)
            # i_h = I_hist_h - k * (L_ll * v_h - L_hl * v_l)
            # i_l = I_hist_l - k * (L_hh * v_l - L_hl * v_h)

            # i_h = I_hist_h + (1/((2*D/(h * Lm))+Rm))* (v_h - v_l) + (1/((2*D/(h * Llk/2))+ Rlk/2)) * v_h
            # i_l = I_hist_l + (1/((2*D/(h * Lm))+Rm))* (v_l - v_h) + (1/((2*D/(h * Llk/2))+ Rlk/2)) * v_h

            print(f"history current from I_hist_h = {I_hist_h} at step = {step}")
            print(f"history current to I_hist_l = {I_hist_l} at step = {step}")
            print(f"G*v(t-dt) contribution at current trafo_primary = {k * (L_ll * v_h - L_hl * v_l)} at step = {step}")
            print(
                f"G*v(t-dt) contribution at current trafo_secondary = {k * (L_hh * v_l - L_hl * v_h)} at step = {step}")
            print(f"Current trafo from i_h = {i_h} at step = {step}")
            print(f"Current trafo to i_l = {i_l} at step = {step}")

            # transformer magnetizing current
            if hv == Vfrom:
                hist_magn = hist_magn_trafos[idx_from]
            else:
                hist_magn = hist_magn_trafos[idx_to]

            # I_magn = hist_magn + branch.Gm[1:,1:] @ v_h
            I_magn = hist_magn + branch.Gm[1:, 1:] @ (v_h - v_l)

            if hv == Vfrom:  # bus "from" is the primary
                Ibranches_step[idx_hist_f] = i_h
                Ibranches_step[idx_hist_t] = i_l
                # magnetizing current
                I_magn_step[idx_from] = I_magn

            else:  # bus "to" is the primary
                Ibranches_step[idx_hist_f] = i_l
                Ibranches_step[idx_hist_t] = i_h
                # magnetizing current
                I_magn_step[idx_to] = I_magn

    # kbuf = (step + 1) % (N_delay + 1)
    # kbuf = (step +1) % (1 + 1)
    kbuf = 1
    V_buffer[kbuf, :] = V
    # I_lines_buffer[kbuf, :] = hist_branches[step, :]  # <-- guarda h(t) MALAMENT
    I_lines_buffer[kbuf, :] = Ibranches_step  # <-- guarda i(t)
    I_magn_buffer[kbuf, :] = I_magn_step

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


def initialize_buffers(#nc: NumericalCircuit,
                       # grid: MultiCircuit,
                       dta: EmtCircuit,
                       pf_results: PowerFlowResults3Ph,
                       N_delay: int,
                       h: float,
                       V_buffer: np.ndarray,
                       I_lines_buffer: np.ndarray,
                       binary_bus_mask: BoolVec,
                       bus_idx_lookup: IntVec,
                       branch_from_lookup: IntVec,
                       branch_to_lookup: IntVec):
    """
    Initialize history buffers with steady state AC solution

    :param nc: NumericalCircuit
    :param grid: MultiCircuit
    :param N_delay: max delay in steps (for the longest line)
    :param h: time step
    :param V_buffer: array with voltage t-tau steps before (N_delay+1, total_cond)
    :param I_lines_buffer: array with currents at each branch termination t-tau steps before (N_delay+1, 2*max_phases_line*nl)
    :param binary_bus_mask: BoolVec
    :param bus_idx_lookup:  IntVec
    :param branch_from_lookup: IntVec
    :param branch_to_lookup: IntVec
    """
    # if pf_results is not None:
    omega = 2 * np.pi * grid.fBase
    res = pf_results

    print("Initializing EMT history buffers with steady-state AC values.")

    nbus4 = 4 * dta.n_bus
    sqrt2 = np.sqrt(2)

    # --- PF voltages (RMS p.u. phasors) ---
    V_mag_N = np.abs(res.voltage_N) if hasattr(res, 'voltage_N') else np.zeros(dta.n_bus)
    V_ang_N = np.angle(res.voltage_N) if hasattr(res, 'voltage_N') else np.zeros(dta.n_bus)
    V_mag_A = np.abs(res.voltage_A) if hasattr(res, 'voltage_A') else np.zeros(dta.n_bus)
    V_ang_A = np.angle(res.voltage_A) if hasattr(res, 'voltage_A') else np.zeros(dta.n_bus)
    V_mag_B = np.abs(res.voltage_B) if hasattr(res, 'voltage_B') else np.zeros(dta.n_bus)
    V_ang_B = np.angle(res.voltage_B) if hasattr(res, 'voltage_B') else np.zeros(dta.n_bus)
    V_mag_C = np.abs(res.voltage_C) if hasattr(res, 'voltage_C') else np.zeros(dta.n_bus)
    V_ang_C = np.angle(res.voltage_C) if hasattr(res, 'voltage_C') else np.zeros(dta.n_bus)


    # --- PF branch currents (RMS p.u. phasors) ---
    m = dta.n_br

    I_mag_f_N = np.abs(res.If_N) if hasattr(res, 'If_N') else np.zeros(dta.n_bus)
    I_ang_f_N = np.angle(res.If_N) if hasattr(res, 'If_N') else np.zeros(dta.n_bus)
    I_mag_f_A = np.abs(res.If_A) if hasattr(res, 'If_A') else np.zeros(dta.n_bus)
    I_ang_f_A = np.angle(res.If_A) if hasattr(res, 'If_A') else np.zeros(dta.n_bus)
    I_mag_f_B = np.abs(res.If_B) if hasattr(res, 'If_B') else np.zeros(dta.n_bus)
    I_ang_f_B = np.angle(res.If_B) if hasattr(res, 'If_B') else np.zeros(dta.n_bus)
    I_mag_f_C = np.abs(res.If_C) if hasattr(res, 'If_C') else np.zeros(dta.n_bus)
    I_ang_f_C = np.angle(res.If_C) if hasattr(res, 'If_C') else np.zeros(dta.n_bus)

    I_mag_t_N = np.abs(res.It_N) if hasattr(res, 'It_N') else np.zeros(dta.n_bus)
    I_ang_t_N = np.angle(res.It_N) if hasattr(res, 'It_N') else np.zeros(dta.n_bus)
    I_mag_t_A = np.abs(res.It_A) if hasattr(res, 'It_A') else np.zeros(dta.n_bus)
    I_ang_t_A = np.angle(res.It_A) if hasattr(res, 'It_A') else np.zeros(dta.n_bus)
    I_mag_t_B = np.abs(res.It_B) if hasattr(res, 'It_B') else np.zeros(dta.n_bus)
    I_ang_t_B = np.angle(res.It_B) if hasattr(res, 'It_B') else np.zeros(dta.n_bus)
    I_mag_t_C = np.abs(res.It_C) if hasattr(res, 'It_C') else np.zeros(dta.n_bus)
    I_ang_t_C = np.angle(res.It_C) if hasattr(res, 'It_C') else np.zeros(dta.n_bus)


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

        V_buffer[idx_buf, :] = V_inst_all[binary_bus_mask]

        # ---------- HISTORY CURRENTS h(t) = i(t) - Gc*v(t) ----------
        # Initialize buffer row to zero first (optional but recommended)
        # I_lines_buffer[idx_buf, :] = 0.0

        for br_k, branch in enumerate(grid.get_branches_iter()):

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

            I_lines_buffer[idx_buf, idx_hist_f] = i_ft
            I_lines_buffer[idx_buf, idx_hist_t] = i_tf


def simulate_emt(
        dta: EmtCircuit,
        # t: Var,
        simulation_time: float,
        # grid: MultiCircuit,
        # nc: NumericalCircuit,
        # syst_blocks: Dict,
        # init_guesses: List,
        # time_step: float,
        # N_delay: int,
        # G0: sp.csc_matrix,
        # binary_bus_mask: BoolVec,
        # branch_lookup: IntVec,
        # bus_idx_lookup: IntVec,
        # alter_params_mappings: Dict[Bus, Dict[int, Const]],
        # uid2idx_alterparams: Dict[int, int],
        # res: PowerFlowResults3Ph,
        integration_method: DynamicIntegrationMethod,
        tolerance: float,
        verbose: int = 0
):  # -> Tuple[np.ndarray, np.ndarray]:
    """
    Main MNA loop that simulates the system over time.
    :param t:
    :param simulation_time:
    :param grid:
    :param nc:
    :param syst_blocks:
    :param init_guesses:
    :param time_step:
    :param N_delay:
    :param G0:
    :param binary_bus_mask:
    :param branch_lookup:
    :param bus_idx_lookup:
    :param alter_params_mappings:
    :param uid2idx_alterparams:
    :return:
    """

    """
    
    :param simulation_time: 
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
    steps = int(np.ceil(simulation_time / dta.h))

    # branch_lookup = np.asarray(branch_lookup)
    Nbranches_masked = int(sum(dta.branch_lookup >= 0))
    total_branch_currents = 2 * Nbranches_masked

    branch_from_lookup = np.full_like(dta.branch_lookup, -1)
    branch_to_lookup = np.full_like(dta.branch_lookup, -1)

    for r, base in enumerate(dta.branch_lookup):
        if base >= 0:
            branch_from_lookup[r] = 2 * base
            branch_to_lookup[r] = 2 * base + 1

    # initialize results vectors
    n_nodes = sum(dta.binary_bus_mask)

    temp = np.zeros((steps, 1))  # time
    V = np.zeros((steps, n_nodes))  # bus voltages vector
    Is = np.zeros((steps, n_nodes))  # currents from current sources vector
    hist = np.zeros((steps, n_nodes))  # I_history currents vector

    Ibranches = np.zeros((steps, total_branch_currents))
    hist_branches = np.zeros((steps, total_branch_currents))
    hist_magn_trafos = np.zeros((steps, Nbranches_masked))
    V_buffer = np.zeros((dta.n_delay + 1, n_nodes))
    I_lines_buffer = np.zeros((dta.n_delay + 1, total_branch_currents))
    I_magn_buffer = np.zeros((dta.n_delay + 1, Nbranches_masked))
    print(f"Initial conditions are: V_buffer = {V_buffer}, I_lines_buffer = {I_lines_buffer}")

    initialize_buffers( #nc= nc,
                       #grid= grid,
                       pf_results= PowerFlowResults3Ph,
                       N_delay= dta.n_delay,
                       h= dta.h,
                       V_buffer= V_buffer,
                       I_lines_buffer= I_lines_buffer,
                       binary_bus_mask= dta.binary_bus_mask,
                       bus_idx_lookup= dta.bus_idx_lookup,
                       branch_from_lookup= IntVec,
                       branch_to_lookup= IntVec)

    # Symbolic EmtSolverProperties association
    emt_vec = Vector(dta.n_bus)
    bus_regions_dict = grid.get_injection_devices_grouped_by_bus()  # dict with only injections (no bus blocks)

    # TODO
    self.x = np.zeros((steps, self.blocksolver.n_vars))
    self.dx = np.zeros((steps, self.blocksolver.n_diff))

    for i, bus in enumerate(grid.get_buses()):
        emt_vec[i] = EmtSolverProperties(
            bus=bus,
            bus_index=i,
            syst_blocks=dta.syst_blocks,
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
                        binary_bus_mask=dta.binary_bus_mask)
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
    # --------------------------------------------------------------------------------------------------------------
    hist[0, :] = update_Hist(nc=nc,
                             step=0,
                             V_buffer=V_buffer,
                             I_lines_buffer=I_lines_buffer,
                             hist_branches=hist_branches[0, :],
                             grid=grid,
                             N_delay=N_delay,
                             h=h,
                             branch_from_lookup=branch_from_lookup,
                             branch_to_lookup=branch_to_lookup,
                             bus_idx_lookup=bus_idx_lookup,
                             line_states=line_states,
                             I_magn_buffer=I_magn_buffer,
                             hist_magn_trafos=hist_magn_trafos)

    # # update Ibranches for the step 0
    Ibranches[0, :] = update_Ibranches(nc=nc,
                                       V=V[0, :],
                                       V_buffer=V_buffer,
                                       I_lines_buffer=I_lines_buffer,
                                       I_magn_buffer=I_magn_buffer,
                                       hist_branches=hist_branches[0, :],
                                       hist_magn_trafos=hist_magn_trafos[0, :],
                                       grid=grid,
                                       step=0,
                                       h=h,
                                       N_delay=N_delay,
                                       bus_idx_lookup=bus_idx_lookup,
                                       branch_from_lookup=branch_from_lookup,
                                       branch_to_lookup=branch_to_lookup,
                                       total_branch_currents=I_lines_buffer.shape[1],
                                       line_states=line_states)
    kbuf = 0 % (N_delay + 1)
    V_buffer[kbuf, :] = V[0, :]
    I_lines_buffer[kbuf, :] = hist_branches[0, :]

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
        Is[step, :] = predict_Is(n=dta.n_bus,
                                 Vprev=V[step - 1, :],
                                 step=step,
                                 h=h,
                                 binary_bus_mask=binary_bus_mask,
                                 bus_idx_lookup=bus_idx_lookup,
                                 emt_vec=emt_vec,
                                 integration_method=integration_method,
                                 tolerance=tolerance,
                                 verbose=verbose
                                 )

        # update i history
        hist[step, :] = update_Hist(nc=nc,
                                    step=step,
                                    V_buffer=V_buffer,
                                    I_lines_buffer=I_lines_buffer,
                                    I_magn_buffer=I_magn_buffer,
                                    hist_branches=hist_branches[step, :],
                                    hist_magn_trafos=hist_magn_trafos[step, :],
                                    grid=grid,
                                    N_delay=N_delay,
                                    h=h,
                                    branch_from_lookup=branch_from_lookup,
                                    branch_to_lookup=branch_to_lookup,
                                    bus_idx_lookup=bus_idx_lookup,
                                    line_states=line_states)

        # Create right hand side vector Itotal for the MNA
        Itotal = (Is[step, :] - hist[step, :]).reshape(-1, 1)  # column vector
        print(f"Itotal = {Itotal}")
        print(f"Is[step,:] = {Is[step, :]}")
        print(f"hist[step, :] = {hist[step, :]}")

        # solve MNA
        sol = G(Itotal)
        V[step, :] = sol[:, 0]
        print(f"step {step} voltage sol = {sol[:, 0]}")

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

        # # solve MNA
        # sol = G(Itotal)
        # V[step, :] = sol[:, 0]
        # print(f"step {step} sol = {sol[:, 0]}")

        # solve current equations
        Ibranches[step, :] = update_Ibranches(nc=nc,
                                              V=V[step, :],
                                              hist_branches=hist_branches[step, :],
                                              hist_magn_trafos=hist_magn_trafos[step, :],
                                              V_buffer=V_buffer,
                                              I_lines_buffer=I_lines_buffer,
                                              I_magn_buffer=I_magn_buffer,
                                              grid=grid,
                                              step=step,
                                              h=h,
                                              N_delay=N_delay,
                                              bus_idx_lookup=bus_idx_lookup,
                                              branch_from_lookup=branch_from_lookup,
                                              branch_to_lookup=branch_to_lookup,
                                              total_branch_currents=I_lines_buffer.shape[1],
                                              line_states=line_states)

        print(f"transformer/line currents at current step = {Ibranches[step, :]}")

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
