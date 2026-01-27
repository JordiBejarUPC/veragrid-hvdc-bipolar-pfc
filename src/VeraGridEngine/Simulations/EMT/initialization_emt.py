# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Dict, List, Any
import numpy as np
import scipy.sparse as sp
import copy

from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.Devices.Parents.physical_device import PhysicalDevice
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.types import INJECTION_DEVICE_TYPES
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Simulations.Rms.initialization import _compile_equation, _compile_parameters_equations
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const, piecewise
from VeraGridEngine.Simulations.PowerFlow.Formulations.pf_basic_formulation_3ph import compute_masks
from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.Simulations.PowerFlow.Formulations.pf_basic_formulation_3ph import lookup_from_mask
from VeraGridEngine.Devices.Substation.bus import Bus
import VeraGridEngine.Devices as dev
from VeraGridEngine.enumerations import VarPowerFlowRefferenceType
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_results_3ph import PowerFlowResults3Ph
from VeraGridEngine.Simulations.EMT.Devices.emt_load import EmtLoad, initialize_emt_load
from VeraGridEngine.Simulations.EMT.Devices.emt_generator import EmtGenerator, initialize_emt_generator
from VeraGridEngine.Simulations.EMT.Devices.emt_line import EmtLine, initialize_emt_line
from VeraGridEngine.Simulations.EMT.Devices.emt_transformer import EmtTransformer, initialize_emt_transformer
from VeraGridEngine.Utils.Symbolic.block import Block


def compose_bus_blocks_emt(grid: MultiCircuit) -> Dict[dev.bus, Block]:
    """
    this function returns a dictionary with keys, the device bus and values, a block containing all the emt models
    of the elements connected to that bus and the bus block itself
    (If there's no injection blocks, it returns the bus block).
    :return syst_blocks: Dict[dev.bus, Block]
    -------

    """
    syst_blocks: Dict[dev.bus, Block] = dict()

    bus_regions_dict = grid.get_injection_devices_grouped_by_bus()

    for bus, region in bus_regions_dict.items():
        bus_block = Block(children=[], in_vars=[])
        # add bus block
        bus_mdl = bus.emt_model.model
        bus_block.add(bus_mdl)
        # add injection in the bus blocks

        for dev_type, dev_list in region.items():
            for elm in dev_list:
                if not elm.emt_model.empty():
                    elm_mdl = elm.emt_model.model
                    bus_block.add(elm_mdl)

        # if len(bus_block.children) >=2: #minimum the bus model + 1 injection = 2 blocks
        syst_blocks[bus] = bus_block

    return syst_blocks


def initialize_emt(grid: MultiCircuit,
                   emt_options: EmtOptions,
                   pf_results: PowerFlowResults3Ph,
                   nc: NumericalCircuit,
                   logger: Logger):
    """
     Initialize all EMT models
    :param grid: (MultiCircuit)
    :param emt_options:
    :param pf_results:
    :param nc:
    :param logger:
    :return:
    """

    time = Var("time")

    # instantiate vars2device  and vars_glob_name2uid dicts
    vars2device: Dict[int, PhysicalDevice] = dict()
    vars_glob_name2uid: Dict[str, int] = dict()

    # find events todo!!
    rms_events = grid.rms_events

    # adapt time step
    h, N_delay = adapt_h(grid=grid, emt_options=emt_options)
    # print("Ndelay = ", N_delay)

    bus_dict = grid.get_bus_index_dict()

    binary_bus_mask, bus_idx_lookup, branch_lookup = compute_masks(nc)

    if grid.get_lines_number() == 0:  # if just 1 bus in the network

        binary_bus_mask = np.zeros(4 * nc.bus_data.nbus, dtype=bool)
        for n, bus in enumerate(grid.get_buses()):
            binary_bus_mask[4 * n + 0] = bool(bus.ph_n)
            binary_bus_mask[4 * n + 1] = bool(bus.ph_a)
            binary_bus_mask[4 * n + 2] = bool(bus.ph_b)
            binary_bus_mask[4 * n + 3] = bool(bus.ph_c)
        binary_bus_mask.astype(bool)
        bus_idx_lookup = lookup_from_mask(binary_bus_mask)

    idx4 = np.array([0, 1, 2, 3])  # array that we use to generate the 3-phase indices

    n = nc.bus_data.nbus
    m = nc.passive_branch_data.nelm
    Cf = sp.lil_matrix((4 * m, 4 * n), dtype=int)
    Ct = sp.lil_matrix((4 * m, 4 * n), dtype=int)
    Gf = sp.lil_matrix((4 * m, 4 * n), dtype=float)
    Gt = sp.lil_matrix((4 * m, 4 * n), dtype=float)

    F = np.array(nc.passive_branch_data.F, dtype=int)
    T = np.array(nc.passive_branch_data.T, dtype=int)

    G_inj = np.zeros((4 * n, 4 * n), float)

    for elm in grid.loads:
        emt_elm = EmtLoad()
        initialize_emt_load(h=h, Sbase=grid.Sbase, load=elm)

        bus_idx = bus_dict[elm.bus]

        # Always stamp full 4×4 block (N, A, B, C)
        idx = 4 * bus_idx + idx4

        # Stamp the 4×4 matrix
        G_inj[np.ix_(idx, idx)] += emt_elm.Gc  # elm.Gc is now 4x4

    for elm in grid.generators:
        emt_elm = EmtGenerator()
        initialize_emt_generator(h=h, gen=elm, logger=logger)

        bus_idx = bus_dict[elm.bus]

        # Always stamp full 4×4 block (N, A, B, C)
        idx = 4 * bus_idx + idx4

        # Stamp the 4×4 matrix
        G_inj[np.ix_(idx, idx)] += emt_elm.Gc  # elm.Gc is now 4x4

        if elm.emt_model.model.event_dict is not None:
            collect_events = {
                key: {"times": [], "values": []}
                for key in elm.emt_model.model.event_dict.keys()
            }
            # find out if there are events affecting the device parameters
            rms_evts = [rms_evt for rms_evt in rms_events if rms_evt.device_idtag == elm.idtag]
            if len(rms_evts) != 0:
                for rms_evt in rms_evts:
                    collect_events[rms_evt.parameter]["times"].append(rms_evt.time)
                    collect_events[rms_evt.parameter]["values"].append(rms_evt.value)
                    # TODO: implement the function in block: apply_event
                for param, events_info in collect_events.items():
                    default_value = copy.deepcopy(elm.emt_model.model.event_dict[param])
                    elm.emt_model.model.event_dict[param] = piecewise(time, np.array(events_info["times"]),
                                                                      np.array(events_info["values"]), default_value)
            for state_var in elm.emt_model.model.state_vars:
                vars2device[state_var.uid] = elm
                vars_glob_name2uid[state_var.name + elm.name] = state_var.uid
            for algeb_var in elm.emt_model.model.algebraic_vars:
                vars2device[algeb_var.uid] = elm
                vars_glob_name2uid[algeb_var.name + elm.name] = algeb_var.uid

    for k, elm in enumerate(grid.get_branches_iter(add_vsc=False, add_hvdc=False, add_switch=True)):

        if elm.device_type == DeviceType.LineDevice:
            emt_elm = EmtLine()
            initialize_emt_line(line=elm, h=h, Sbase=grid.Sbase, fbase=grid.fBase)

        elif elm.device_type == DeviceType.Transformer2WDevice:
            emt_elm = EmtTransformer()
            initialize_emt_transformer(h=h, tr=elm)

        else:
            raise NotImplementedError(f"The branch type is not implemented in EMT {elm.device_type}")

        f = F[k]  # idx of the 'from' buses
        t = T[k]  # idx of the 'to' buses

        f4 = 4 * f + idx4
        t4 = 4 * t + idx4
        k4 = 4 * k + idx4

        Gf[np.ix_(k4, f4)] = emt_elm.Gff
        Gf[np.ix_(k4, t4)] = emt_elm.Gft
        Gt[np.ix_(k4, f4)] = emt_elm.Gtf
        Gt[np.ix_(k4, t4)] = emt_elm.Gtt

        Cf[k4, f4] = 1
        Ct[k4, t4] = 1

    # Assemble the final conductance matrix
    G_full = (Cf.T @ Gf + Ct.T @ Gt) + sp.csc_matrix(G_inj)

    # Slice per phase
    G0 = sp.csc_matrix(G_full[binary_bus_mask, :][:, binary_bus_mask])

    # NOW SYSTEM BLOCKS HAS ALSO A BLOCK WITH ONLY A BUS IF THERE'S NO BLOCK CONNECTED
    syst_blocks = compose_bus_blocks_emt(grid)

    (time, init_guesses,
     alter_params_mappings,
     uid2idx_alterparams) = initialize_bus_blocks(nc=nc,
                                                  time=time,
                                                  syst_blocks=syst_blocks,
                                                  grid=grid,
                                                  power_flow_results=pf_results,
                                                  vars2device=vars2device,
                                                  vars_glob_name2uid=vars_glob_name2uid)

    return (time, syst_blocks, init_guesses, h, N_delay, G0,
            binary_bus_mask, branch_lookup, bus_idx_lookup,
            alter_params_mappings, uid2idx_alterparams)


def adapt_h(grid: MultiCircuit,
            emt_options: EmtOptions,
            logger: Logger = Logger()):
    """
    :param grid: (MultiCircuit)
    :param emt_options:
    :param logger:
    :return emt_options.time_step:
    :return N_delay:
    """
    # choose N_delay according to the tau of the longest line
    N_delay = 1
    dt = emt_options.time_step
    max_length = 0  # init counter
    minimum_N = 10

    if len(grid.get_lines()) > 0:
        for line in grid.get_lines():
            initialize_emt_line(emt_options.time_step, grid.Sbase, grid.fBase)

            # If model is Pi, tau is 0. We must skip the N_delay check
            # because Pi models don't impose travel time constraints.
            model_type = line.emt_model_type
            if model_type == 'Pi':
                continue

            if line.length > max_length:
                max_length = line.length
                N_delay = int(round(line.tau / dt))
                print(f"tau = {line.tau * 1e3}ms")
                if N_delay != 0:
                    emt_options.time_step = line.tau / N_delay
                    logger.add_error("time step adapted to", value=emt_options.time_step)
                    print(f"time step adapted to {emt_options.time_step}s")

        if N_delay == 0:
            logger.add_error("EMT simulation cannot be initialized due to: Time step too large. Reduce it.",
                             value=emt_options.time_step)
            print(f"EMT simulation cannot be initialized due to: Time step too large. Reduce it. ")
            exit()
        # elif N_delay < minimum_N:  # recommend to set a smaller dt to get more accurate results
        # logger.add_warning("Time step too large. It is recommended to reduce it to improve results accuracy.", value=emt_options.time_step)
        # print(f"Time step too large. It is recommended to reduce it to improve results accuracy.")

    return emt_options.time_step, N_delay


def initialize_bus_blocks(nc: NumericalCircuit,
                          time: Var,
                          syst_blocks: Dict, grid: MultiCircuit,
                          power_flow_results: PowerFlowResults3Ph,
                          vars2device: Dict[int, PhysicalDevice],
                          vars_glob_name2uid: Dict[str, int]) -> tuple[
    Var | Any, list[dict[int, float]], dict[Bus, dict[int, Const]], dict[
        int, int]]:  # tuple[{uid}, list[Any], dict[int, int]]
    """
    :param syst_blocks: Dict with the region block for each bus. (region = bus + all injections in that block)
    :param grid:
    :param power_flow_results:
    :param vars2device: dictionary relating uid of vars with the device they belong to
    :param vars_glob_name2uid: dictionary relating global name of the variable and uid (used when showing results)
    :return time:
    :return System block:
    :return  initial guess: Dict
    """
    # already computed grid power flow
    res = power_flow_results
    init_guesses: List[Dict[int, float]] = list()  # list with all init guesses from all system blocks (one per bus)
    alter_params_mappings: Dict[
        Bus, Dict[int, Const]] = dict()  # list with all init guesses ALTER PARAMS from all system blocks (one per bus)
    bus_regions_dict = grid.get_injection_devices_grouped_by_bus()
    uid2idx_alterparams: Dict[int, int] = dict()

    for bus, region_block in syst_blocks.items():
        region_block.vars2device = vars2device
        region_block.vars_glob_name2uid = vars_glob_name2uid

        # initialize containers
        init_guess: Dict[int, float] = dict()
        sys_vars: list[int] = list()
        seen_vars: set[int] = set()

        uid2sym_vars: Dict[int, str] = dict()
        uid2idx_vars: Dict[int, int] = dict()
        uid2sym_t: Dict[int, str] = dict()
        uid2idx_t: Dict[int, int] = dict()

        # fill uid2sym_t and uid2idx_t dicts
        array_index_t = 0
        uid2sym_t[time.uid] = f"glob_time"
        uid2idx_t[time.uid] = array_index_t

        # alternating parameters to assign values to vars from outside
        alter_params_mapping: Dict[int, Const] = dict()

        region = bus_regions_dict[bus]
        init_explicit_regions(grid=grid,
                              nc=nc,
                              bus=bus,
                              region=region,
                              res_pf=res,
                              init_guess=init_guess,
                              seen_vars=seen_vars,
                              sys_vars=sys_vars,
                              uid2sym_vars=uid2sym_vars,
                              uid2idx_vars=uid2idx_vars,
                              uid2sym_t=uid2sym_t,
                              alter_params_mapping=alter_params_mapping,
                              uid2idx_alterparams_global=uid2idx_alterparams)

        init_guesses.append(init_guess)
        alter_params_mappings[bus] = alter_params_mapping

    return time, init_guesses, alter_params_mappings, uid2idx_alterparams


def init_explicit_regions(grid: MultiCircuit,
                          nc: NumericalCircuit,
                          bus: dev.Bus,
                          region: Dict[DeviceType, Dict[DeviceType, List[INJECTION_DEVICE_TYPES]]],
                          res_pf: PowerFlowResults3Ph,
                          init_guess: Dict[int, float],
                          seen_vars: set[int],
                          sys_vars: list[int],
                          uid2sym_vars: Dict[int, str],
                          uid2idx_vars: Dict[int, int],
                          uid2sym_t: Dict[int, str],
                          alter_params_mapping: Dict[int, Const],
                          uid2idx_alterparams_global: Dict[int, int]):
    """
    initialize equations for the injection devices in a specific bus.
    :param region: Dict with the region for each bus. (region = bus + all injections in that block)
    """
    uid2sym_params: Dict[int, str] = {}
    uid2idx_params: Dict[int, int] = {}

    uid2sym_alterparams: Dict[int, str] = dict()
    uid2idx_alterparams: Dict[int, int] = dict()

    # bus: only has alter_params to initialize.
    mdl = bus.emt_model.model
    alterparam_array_index = 0
    for i in range(len(mdl.alter_params)):
        altparam = mdl.alter_params[i]
        uid = altparam.uid
        if uid not in seen_vars:
            seen_vars.add(uid)

        if altparam.uid not in uid2sym_alterparams:
            uid2sym_alterparams[altparam.uid] = f"alter[{alterparam_array_index}]"
            uid2idx_alterparams[altparam.uid] = alterparam_array_index
            uid2idx_alterparams_global[altparam.uid] = alterparam_array_index
            alterparam_array_index += 1

    # assign already known power_flow bus voltages to alternating parameters (bus voltages)
    # TODO: see what happens with the res_pf.voltage !!!
    altparams_array = np.zeros(4)
    bus_idx = bus_dict[bus]
    for altparam in mdl.alter_params:
        if altparam.name == 'v_n':
            Vn_rms, Vn_angle = np.abs(res_pf.voltage_N[bus_idx]), np.angle(res_pf.voltage_N[bus_idx])
            vn0 = np.sqrt(2) * Vn_rms * np.cos(Vn_angle)
            alter_params_mapping[altparam.uid] = Const(vn0)
            altparams_array[0] = vn0

            # if bus_idx == 0: # TEMPORARY
            #     alter_params_mapping[altparam.uid] = Const(0.0)  # TEMPORARY
            #     altparams_array[0] = 0.0 # TEMPORARY

        if altparam.name == 'v_a':
            Va_rms, Va_angle = np.abs(res_pf.voltage_A[bus_idx]), np.angle(res_pf.voltage_A[bus_idx])  # p.u. rms
            va0 = np.sqrt(2) * Va_rms * np.cos(Va_angle)
            alter_params_mapping[altparam.uid] = Const(va0)
            altparams_array[1] = va0

            # if bus_idx == 0: # TEMPORARY
            # #     #good init values for generator only
            # #     # rload = 1/0.3833
            # #     # alter_params_mapping[altparam.uid] = Const(0.7722782435188278) # TEMPORARY
            # #     # altparams_array[1] = 0.7722782435188278 # TEMPORARY
            # #
            # #     # rload = 3.0 p.u.
            # #     alter_params_mapping[altparam.uid] = Const(0.6973992259905542)  # TEMPORARY
            # #     altparams_array[1] = 0.6973992259905542  # TEMPORARY
            # #
            #     # init values for gen + line
            #     alter_params_mapping[altparam.uid] = Const(0.003946205123095523)  # TEMPORARY
            #     altparams_array[1] = 0.003946205123095523 # TEMPORARY

        if altparam.name == 'v_b':
            Vb_rms, Vb_angle = np.abs(res_pf.voltage_B[bus_idx]), np.angle(res_pf.voltage_B[bus_idx])
            vb0 = np.sqrt(2) * Vb_rms * np.cos(Vb_angle)
            alter_params_mapping[altparam.uid] = Const(vb0)
            altparams_array[2] = vb0

            # if bus_idx == 0: # TEMPORARY
            # #     #good init values for generator only
            # #     # rload = 1/0.3833
            # #     # alter_params_mapping[altparam.uid] = Const(-1.4121458156657476) # TEMPORARY
            # #     # altparams_array[2] = -1.4121458156657476 # TEMPORARY
            # #
            # #     # rload = 3.0 p.u.
            # #     alter_params_mapping[altparam.uid] = Const(-1.4141693402474556)  # TEMPORARY
            # #     altparams_array[2] = -1.4141693402474556  # TEMPORARY
            # #
            # #     # init values for gen + line
            #     alter_params_mapping[altparam.uid] = Const(-1.2267131513535872)  # TEMPORARY
            #     altparams_array[2] = -1.2267131513535872  # TEMPORARY

        if altparam.name == 'v_c':
            Vc_rms, Vc_angle = np.abs(res_pf.voltage_C[bus_idx]), np.angle(res_pf.voltage_C[bus_idx])
            vc0 = np.sqrt(2) * Vc_rms * np.cos(Vc_angle)
            alter_params_mapping[altparam.uid] = Const(vc0)
            altparams_array[3] = vc0

            # if bus_idx == 0: # TEMPORARY
            # #     #good init values for generator only
            # #     # rload = 1/0.3833
            # #     # alter_params_mapping[altparam.uid] = Const(0.6398675721469198) # TEMPORARY
            # #     # altparams_array[3] = 0.6398675721469198 # TEMPORARY
            # #     # rload = 3.0 p.u.
            # #     alter_params_mapping[altparam.uid] = Const(0.7167701142569014)  # TEMPORARY
            # #     altparams_array[3] = 0.7167701142569014  # TEMPORARY
            # #
            #     # init values for gen + line
            #     alter_params_mapping[altparam.uid] = Const(1.2227670553957843)  # TEMPORARY
            #     altparams_array[3] = 1.2227670553957843  # TEMPORARY

    binary_bus_mask, bus_idx_lookup, branch_lookup = compute_masks(nc)
    idx = 4 * nc.bus_dict[bus] + np.array([0, 1, 2, 3])

    if grid.get_lines_number() == 0:  # if just 1 bus in the network

        binary_bus_mask = np.zeros(4 * nc.bus_data.nbus, dtype=bool)
        for n, bus in enumerate(grid.get_buses()):
            binary_bus_mask[4 * n + 0] = bool(bus.ph_n)
            binary_bus_mask[4 * n + 1] = bool(bus.ph_a)
            binary_bus_mask[4 * n + 2] = bool(bus.ph_b)
            binary_bus_mask[4 * n + 3] = bool(bus.ph_c)

        bus_idx_lookup = lookup_from_mask(binary_bus_mask)

    altparams_array = altparams_array[binary_bus_mask[idx]]

    array_index = 0

    for dev_type, dev_list in region.items():
        for elm in dev_list:
            mdl = elm.emt_model.model
            # mdl.unify_blocks()
            # mdl_vars = mdl.state_vars + mdl.algebraic_vars + mdl.diff_vars

            # add vars and params to uid indices
            for lst in [mdl.state_vars, mdl.algebraic_vars, mdl.diff_vars]:
                for var in lst:
                    uid = var.uid
                    if uid not in seen_vars:
                        sys_vars.append(uid)
                        seen_vars.add(uid)

                    if var.uid not in uid2sym_vars:
                        uid2sym_vars[var.uid] = f"vars[{array_index}]"
                        uid2idx_vars[var.uid] = array_index
                        array_index += 1

            params_array_index = 0
            for param in mdl.event_dict.keys():
                if param.uid not in uid2sym_params:
                    uid2sym_params[param.uid] = f"params[{params_array_index}]"
                    uid2idx_params[param.uid] = params_array_index
                    params_array_index += 1

            # fill initial guesses that I already know
            if dev_type.name == 'GeneratorDevice':
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

                # trampilla per obtenir les vabc que teníem amb syst d'un generador!!!:---------------------
                # # todo:     temporary!!!
                # # rload = 1/0.3833
                # # P = 1.1498999999999997
                # # Q = -8.012344526598184e-18
                # #rload = 3.0
                # P = 0.9999965986510249
                # Q = -2.9044748908918416e-17
                # S = P + 1j * Q
                # S_a = S/3
                # S_b = S/3
                # S_c = S/3
                #
                # # rload = 1/0.3833
                # # va = 0.7722782435188278
                # # vb = -1.4121458156657476
                # # vc = 0.6398675721469198
                #
                # # rload = 3.0 p.u.
                # va = 0.6973992259905542
                # vb = -1.4141693402474556
                # vc = 0.7167701142569014
                #
                # vd = (2 / 3) * (va - 0.5 * vb - 0.5 * vc)
                # vq = (np.sqrt(3) / 3) * (vb - vc)
                # v0 = (va + vb + vc) / 3  # ~0 si equilibrat
                #
                # V_peak = np.sqrt(vd ** 2 + vq ** 2)
                # V_rms = V_peak / np.sqrt(2)
                #
                # theta_e = np.arctan2(vq, vd)
                #
                # V_a = V_rms * np.exp(1j * theta_e)
                # V_b = V_rms * np.exp(1j * (theta_e - 2 * np.pi / 3))
                # V_c = V_rms * np.exp(1j * (theta_e + 2 * np.pi / 3))

                # fi trampilla ---------------------------------------------------

                init_guess[mdl.external_mapping[VarPowerFlowRefferenceType.P].uid] = P
                init_guess[mdl.external_mapping[VarPowerFlowRefferenceType.Q].uid] = Q

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

                init_guess[mdl.external_mapping[VarPowerFlowRefferenceType.Ia].uid] = i_a
                init_guess[mdl.external_mapping[VarPowerFlowRefferenceType.Ib].uid] = i_b
                init_guess[mdl.external_mapping[VarPowerFlowRefferenceType.Ic].uid] = i_c

                print(f"initial i_a = {i_a}")
                print(f"initial i_b = {i_b}")
                print(f"initial i_c = {i_c}")

                a = np.exp(1j * 2 * np.pi / 3)
                V1 = (1 / 3) * (V_a + a * V_b + a * a * V_c)  # positive sequence voltage for the synchronous generator
                theta = np.angle(V1)

                print(f"theta initialization generator = {theta}")
                # --------------------------------
                # theta = 0.0
                # --------------------------------
                init_guess[mdl.external_mapping[VarPowerFlowRefferenceType.theta].uid] = theta

                print(f"sanity check!")
                print(f"va*ia+vb*ib+vc*ic = {va0 * i_a + vb0 * i_b + vc0 * i_c}")
                print(f"P from power flow = {P} [p.u.]")

            # initialize array for model variables
            x = np.zeros(len(sys_vars))

            # assign initial guesses for known variables
            for uid in sys_vars:
                if uid in init_guess:
                    x[uid2idx_vars[uid]] = init_guess[uid]

            # initialize array for model params
            params_array = np.zeros(len(mdl.event_dict.keys()))
            params_mapping: Dict[int, float] = dict()
            # compute and assign parameters value
            for param in mdl.event_dict.keys():
                eq = mdl.event_dict[param]
                eq_fn = _compile_parameters_equations([eq], uid2sym_t)
                param_val = float(eq_fn(0.0))
                params_array[uid2idx_params[param.uid]] = param_val
                params_mapping[param.uid] = param_val

            # compute and assign missing init_vars
            vars_initialized: set[int] = set()
            while len(vars_initialized) < len(mdl.init_eqs):
                progress = False
                vars_init_at_start = len(vars_initialized)
                for var, eq in mdl.init_eqs.items():
                    uid = var.uid
                    if uid in vars_initialized:
                        continue

                    deps = eq.get_vars()
                    calculate_now = True
                    for v_init in deps:
                        uid_deps = v_init.uid
                        if uid_deps in init_guess:  # it's a variable to be found (diff, state or algebraic)
                            continue
                        elif uid_deps in alter_params_mapping:  # it's an alter param to be found
                            continue
                        elif uid_deps in params_mapping:  # it's a parameter to be found
                            continue
                        else:
                            calculate_now = False
                            break
                    # if all((v.uid, v.name) in init_guess for v in deps):
                    if calculate_now:
                        var_now = var
                        eq_fn = _compile_equation([eq], uid2sym_vars, uid2sym_params, uid2sym_alterparams)
                        val = float(eq_fn(x, params_array, altparams_array))

                        init_guess[uid] = val
                        x[uid2idx_vars[var.uid]] = val
                        vars_initialized.add(uid)

                        if var.name == "psi_d":
                            print("psi_d = ", val)
                        elif var.name == "psi_q":
                            print("psi_q = ", val)
                        elif var.name == "psi_0":
                            print("psi_0 = ", val)
                        elif var.name == "v_f":
                            print("v_f = ", val)
                        elif var.name == "i_d":
                            print("i_d = ", val)
                        elif var.name == "i_q":
                            print("i_q = ", val)
                        elif var.name == "i_0":
                            print("i_0 = ", val)
                        elif var.name == "v_d":
                            print("v_d = ", val)
                        elif var.name == "v_q":
                            print("v_q = ", val)
                        elif var.name == "v_0":
                            print("v_0 = ", val)
                        elif var.name == "Pm":
                            print("Pm = ", val)
                            Pm = val
                        elif var.name == "Tm":
                            print("Tm = ", val)
                            Tm = val
                        elif var.name == "Te":
                            print("Te = ", val)
                        elif var.name == "i_f":
                            print("i_f = ", val)

                vars_init_at_end = len(vars_initialized)
                if vars_init_at_end > vars_init_at_start:
                    progress = True

                if not progress:
                    unresolved = [v.name for v in mdl.init_eqs if v.uid not in vars_initialized]
                    raise RuntimeError(f"Unresolvable init equations: {unresolved}")
                print("Second sanity check!!")
                print(f"P mec = {Pm}")
                print(f"tm*w = {Tm * 1.0}")

