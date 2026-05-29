# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Dict, List
import numpy as np
import scipy.sparse as sp
import copy

import VeraGridEngine.Devices as dev
from VeraGridEngine.Devices.Parents.physical_device import PhysicalDevice
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.basic_structures import Logger, Mat, BoolVec
from VeraGridEngine.Utils.Symbolic.symbolic import piecewise
from VeraGridEngine.enumerations import EmtLineTypes
from VeraGridEngine.Simulations.PowerFlow.Formulations.pf_basic_formulation_3ph import lookup_from_mask
from VeraGridEngine.enumerations import VarPowerFlowReferenceType
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_results_3ph import PowerFlowResults3Ph
from VeraGridEngine.Utils.Symbolic.block import Block
from trunk.dynamics_emt.emt_models_and_circuits.emt_transformer import initialize_emt_transformer
from trunk.dynamics_emt.emt_models_and_circuits.emt_line import EmtLine, initialize_emt_line
from trunk.dynamics_emt.emt_models_and_circuits.emt_load import initialize_emt_load
from trunk.dynamics_emt.emt_models_and_circuits.emt_generator import initialize_emt_generator
from trunk.dynamics_emt.emt_models_and_circuits.emt_circuit import EmtCircuit


def adapt_h(freq: float,
            lines: List[dev.Line],
            dta: EmtLine,
            emt_options: EmtOptions,
            logger: Logger = Logger(),
            verbose: int = 0):
    """
    Find the simulation step such that it is a multiple of the largest line tau
    :param freq:
    :param lines:
    :param dta:
    :param emt_options:
    :param logger:
    :param verbose:
    :return:
    """
    # choose N_delay according to the tau of the longest line
    n_delay = 1
    dt = emt_options.time_step
    max_length = 0  # init counter
    w = 2 * np.pi * freq
    for ii, line in enumerate(lines):

        # If model is Pi, tau is 0. We must skip the N_delay check
        # because Pi models don't impose travel time constraints.

        if line.emt_model_type != EmtLineTypes.PI and line.length > max_length:

            max_length = line.length
            dta.tau[ii] = line.get_tau(w=w)

            n_delay = int(round(dta.tau[ii] / dt))

            if verbose > 0:
                print(f"tau = {dta.tau[ii] * 1e3}ms")

            if n_delay != 0:
                emt_options.time_step = dta.tau[ii] / n_delay
                logger.add_error("time step adapted to", value=emt_options.time_step)

                if verbose > 0:
                    print(f"time step adapted to {emt_options.time_step}s")

    if n_delay == 0:
        logger.add_error("EMT simulation cannot be initialized due to: Time step too large. Reduce it.",
                         value=emt_options.time_step)

        if verbose > 0:
            print(f"EMT simulation cannot be initialized due to: Time step too large. Reduce it. ")

    return emt_options.time_step, n_delay


def compile_emt(grid: MultiCircuit,
                emt_options: EmtOptions,
                res_pf: PowerFlowResults3Ph,
                logger: Logger) -> EmtCircuit:
    """
     Initialize all EMT models
    :param grid: (MultiCircuit)
    :param emt_options:
    :param res_pf: PowerFlowResults3Ph instance
    :param logger:
    :return: EmtCircuit
    """

    dta = EmtCircuit(
        n_bus=grid.get_bus_number(),
        n_line=grid.get_lines_number(),
        n_transformer=grid.get_transformers2w_number(),
        n_gen=grid.get_generators_number(),
        n_load=grid.get_loads_number()
    )

    nbr_real = grid.get_branch_number(add_vsc=False, add_hvdc=False, add_switch=True)
    if nbr_real != dta.n_br:
        raise ValueError(f"Grid branch number {nbr_real} "
                         f"different from supported emt branch number {dta.n_br}")

    # instantiate vars2device  and vars_glob_name2uid dicts
    vars2device: Dict[int, PhysicalDevice] = dict()
    vars_glob_name2uid: Dict[str, int] = dict()

    # TODO: find events
    rms_events = grid.rms_events

    # adapt time step, cannot be avoided because I need a final h for the EMT initialization
    dta.h, dta.n_delay = adapt_h(freq=grid.fBase,
                                 lines=grid.lines,
                                 dta=dta.line_emt_data,
                                 emt_options=emt_options,
                                 logger=logger,
                                 verbose=emt_options.verbose)

    bus_dict = grid.get_bus_index_dict()

    idx4 = np.array([0, 1, 2, 3])  # array that we use to generate the 3-phase indices

    n = dta.n_bus
    m = dta.n_br
    Cf: sp.lil_matrix = sp.lil_matrix((4 * m, 4 * n), dtype=int)
    Ct: sp.lil_matrix = sp.lil_matrix((4 * m, 4 * n), dtype=int)
    Gf: sp.lil_matrix = sp.lil_matrix((4 * m, 4 * n), dtype=float)
    Gt: sp.lil_matrix = sp.lil_matrix((4 * m, 4 * n), dtype=float)

    G_inj: Mat = np.zeros((4 * n, 4 * n), float)

    R: BoolVec = np.zeros(4 * m, dtype=bool)

    # ------------------------------------------------------------------------------------------------------------------
    # Buses
    # ------------------------------------------------------------------------------------------------------------------

    for ii, bus in enumerate(grid.buses):
        bus_block = Block(children=[], in_vars=[])

        bus_block.vars_glob_name2uid = vars_glob_name2uid

        # add bus block
        bus_block.add(bus.emt_model)

        # store and initialize the block solver
        dta.set_bus_block(i=ii, block=bus_block)

    # ------------------------------------------------------------------------------------------------------------------
    # Lines
    # ------------------------------------------------------------------------------------------------------------------
    for k, elm in enumerate(grid.lines):
        Gff, Gft, Gtf, Gtt = initialize_emt_line(ii=k,
                                                 line=elm,
                                                 dta=dta.line_emt_data,
                                                 h=dta.h,
                                                 Sbase=grid.Sbase,
                                                 fbase=grid.fBase,
                                                 verbose=emt_options.verbose)

        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]

        f4 = 4 * f + idx4
        t4 = 4 * t + idx4
        k4 = 4 * k + idx4

        Gf[np.ix_(k4, f4)] = Gff
        Gf[np.ix_(k4, t4)] = Gft
        Gt[np.ix_(k4, f4)] = Gtf
        Gt[np.ix_(k4, t4)] = Gtt

        R[4 * k + 0] = elm.ys.phN
        R[4 * k + 1] = elm.ys.phA
        R[4 * k + 2] = elm.ys.phB
        R[4 * k + 3] = elm.ys.phC

        Cf[k4, f4] = 1
        Ct[k4, t4] = 1

    # ------------------------------------------------------------------------------------------------------------------
    # Transformers
    # ------------------------------------------------------------------------------------------------------------------

    for k, elm in enumerate(grid.transformers2w):
        Gff, Gft, Gtf, Gtt = initialize_emt_transformer(ii=k,
                                                        h=dta.h,
                                                        tr=elm,
                                                        dta=dta.transformer_emt_data)

        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]

        f4 = 4 * f + idx4
        t4 = 4 * t + idx4
        k4 = 4 * k + idx4

        Gf[np.ix_(k4, f4)] = Gff
        Gf[np.ix_(k4, t4)] = Gft
        Gt[np.ix_(k4, f4)] = Gtf
        Gt[np.ix_(k4, t4)] = Gtt

        (R[4 * k + 0],
         R[4 * k + 1],
         R[4 * k + 2],
         R[4 * k + 3]) = elm.transformer_phases(logger=logger)

        Cf[k4, f4] = 1
        Ct[k4, t4] = 1

    # ------------------------------------------------------------------------------------------------------------------
    # Mask stuff
    # ------------------------------------------------------------------------------------------------------------------
    zero_mask = (R == 0)
    Cfcopy = Cf.copy()
    Ctcopy = Ct.copy()

    Cfcopy[zero_mask, :] = 0
    Ctcopy[zero_mask, :] = 0

    Ctot = Cfcopy + Ctcopy
    col_sums = np.array(Ctot.sum(axis=0))[0, :]
    binary_bus_mask = (col_sums > 0).astype(bool)

    bus_has_neutral = np.ones(4 * n, dtype=bool)  # por defecto el neutro del bus está activo

    # TODO This must happen at the branches loop
    # for bus_idx in range(n):
    #     connected = np.where((F == bus_idx) | (T == bus_idx))[0]
    #     if connected.size == 0:
    #         continue
    #
    #     grounded_here = False
    #     for k in connected:
    #         # Si este bus es el 'from' de la rama k y ese lado es Yg -> neutro a 0
    #         if F[k] == bus_idx and is_yg(nc.passive_branch_data.conn_f[k]):
    #             grounded_here = True
    #             break
    #         # Si este bus es el 'to' de la rama k y ese lado es Yg -> neutro a 0
    #         if T[k] == bus_idx and is_yg(nc.passive_branch_data.conn_t[k]):
    #             grounded_here = True
    #             break
    #
    #     if grounded_here:
    #         bus_has_neutral[4 * bus_idx + 0] = False  # desactiva el nodo de neutro del bus

    # aplica la prioridad: si algún trafo aterra el neutro del bus, el neutro se elimina del solver
    binary_bus_mask[0::4] = binary_bus_mask[0::4] & bus_has_neutral[0::4]

    bus_idx_lookup = lookup_from_mask(binary_bus_mask)
    branch_lookup = lookup_from_mask(R)

    # ------------------------------------------------------------------------------------------------------------------
    # Loads
    # ------------------------------------------------------------------------------------------------------------------
    for ii, elm in enumerate(grid.loads):
        Gc = initialize_emt_load(ii=ii,
                                 dta=dta.load_emt_data,
                                 sbase=grid.Sbase,
                                 load=elm,
                                 verbose=emt_options.verbose)

        bus_idx = bus_dict[elm.bus]

        # Always stamp full 4×4 block (N, A, B, C)
        idx = 4 * bus_idx + idx4

        # Stamp the 4×4 matrix
        G_inj[np.ix_(idx, idx)] += Gc  # elm.Gc is now 4x4

        # record block into the bus block
        if not elm.emt_model.check_empty():
            dta.set_bus_block(i=bus_idx, block=elm.emt_model)

    # ------------------------------------------------------------------------------------------------------------------
    # Generators
    # ------------------------------------------------------------------------------------------------------------------
    for ii, elm in enumerate(grid.generators):
        Gc = initialize_emt_generator(ii=ii,
                                      h=dta.h,
                                      gen=elm,
                                      dta=dta.gen_emt_data,
                                      logger=logger)

        bus_idx = bus_dict[elm.bus]

        # Always stamp full 4×4 block (N, A, B, C)
        idx = 4 * bus_idx + idx4

        # Stamp the 4×4 matrix
        G_inj[np.ix_(idx, idx)] += Gc  # elm.Gc is now 4x4

        if elm.emt_model.event_dict is not None:
            collect_events = {
                key: {"times": [], "values": []}
                for key in elm.emt_model.event_dict.keys()
            }
            # TODO: find events
            # find out if there are events affecting the device parameters
            rms_evts = [rms_evt for rms_evt in rms_events if rms_evt.device_idtag == elm.idtag]
            if len(rms_evts) != 0:
                for rms_evt in rms_evts:
                    collect_events[rms_evt.parameter]["times"].append(rms_evt.time)
                    collect_events[rms_evt.parameter]["values"].append(rms_evt.value)
                    # TODO: implement the function in block: apply_event
                for param, events_info in collect_events.items():
                    default_value = copy.deepcopy(elm.emt_model.event_dict[param])
                    elm.emt_model.event_dict[param] = piecewise(dta.tme,
                                                                      np.array(events_info["times"]),
                                                                      np.array(events_info["values"]), default_value)
            for state_var in elm.emt_model.state_vars:
                vars2device[state_var.uid] = elm
                vars_glob_name2uid[state_var.name + elm.name] = state_var.uid
            for algeb_var in elm.emt_model.algebraic_vars:
                vars2device[algeb_var.uid] = elm
                vars_glob_name2uid[algeb_var.name + elm.name] = algeb_var.uid

            # record block into the bus block
            dta.set_bus_block(i=bus_idx, block=elm.emt_model)

            # initialize generator variables ---------------------------------------------------------------------------
            init_guess: Dict[int, float] = dict()

            S_a = res_pf.Sbus_A[bus_idx]  # MVA
            S_b = res_pf.Sbus_B[bus_idx]  # MVA
            S_c = res_pf.Sbus_C[bus_idx]  # MVA

            S_a = S_a / grid.Sbase  # p.u.
            S_b = S_b / grid.Sbase  # p.u.
            S_c = S_c / grid.Sbase  # p.u.

            V_a = res_pf.voltage_A[bus_idx]  # p.u.
            V_b = res_pf.voltage_B[bus_idx]  # p.u.
            V_c = res_pf.voltage_C[bus_idx]  # p.u.

            S = S_a + S_b + S_c  # MVA

            P = np.real(S)  # p.u.
            Q = np.imag(S)  # p.u.

            dta.add_guess(bus_idx, VarPowerFlowReferenceType.P, float(P))
            dta.add_guess(bus_idx, VarPowerFlowReferenceType.Q, float(Q))

            print(f"initial P = {P}")
            print(f"initial Q = {Q}")

            I_a = np.conj(S_a / V_a)
            I_b = np.conj(S_b / V_b)
            I_c = np.conj(S_c / V_c)

            Ia_rms, Ia_angle = np.abs(I_a), np.angle(I_a)
            Ib_rms, Ib_angle = np.abs(I_b), np.angle(I_b)
            Ic_rms, Ic_angle = np.abs(I_c), np.angle(I_c)

            i_a = np.sqrt(2) * Ia_rms * np.cos(Ia_angle)
            i_b = np.sqrt(2) * Ib_rms * np.cos(Ib_angle)
            i_c = np.sqrt(2) * Ic_rms * np.cos(Ic_angle)

            dta.add_guess(bus_idx, VarPowerFlowReferenceType.Ia, i_a)
            dta.add_guess(bus_idx, VarPowerFlowReferenceType.Ib, i_b)
            dta.add_guess(bus_idx, VarPowerFlowReferenceType.Ic, i_c)

            if emt_options.verbose > 0:
                print(f"initial i_a = {i_a}")
                print(f"initial i_b = {i_b}")
                print(f"initial i_c = {i_c}")

            a = np.exp(1j * 2 * np.pi / 3)
            V1 = (1.0 / 3.0) * (V_a + a * V_b + a * a * V_c)  # positive sequence voltage for the synchronous generator
            theta: float = np.angle(V1)

            if emt_options.verbose > 0:
                print(f"theta initialization generator = {theta}")
            # --------------------------------
            # theta = 0.0
            # --------------------------------
            dta.add_guess(bus_idx, VarPowerFlowReferenceType.theta, theta)

            if emt_options.verbose > 0:
                print(f"sanity check!")
                # print(f"va*ia+vb*ib+vc*ic = {va0 * i_a + vb0 * i_b + vc0 * i_c}")
                print(f"P from power flow = {P} [p.u.]")

    # ------------------------------------------------------------------------------------------------------------------
    # Initialize per-bus solvers
    # ------------------------------------------------------------------------------------------------------------------

    for ii, bus in enumerate(grid.buses):
        # store and initialize the block solver
        dta.init_solver(i=ii)

    # ------------------------------------------------------------------------------------------------------------------
    # Conductance Assembly
    # ------------------------------------------------------------------------------------------------------------------

    G_full = (Cf.T @ Gf + Ct.T @ Gt) + sp.csc_matrix(G_inj)

    # Slice per phase
    dta.G0 = sp.csc_matrix(G_full[binary_bus_mask, :][:, binary_bus_mask])

    return dta
