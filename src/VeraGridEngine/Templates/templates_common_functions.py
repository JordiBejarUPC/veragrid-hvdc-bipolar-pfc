# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
#
from typing import Any
#
from VeraGridEngine.enumerations import VarPowerFlowRefferenceType
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory

from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.Templates.Rms.bus_rms_template import initialize_bus_rms


def connect_line_rms_from(mdl1: Block, mdl2: Block):
    """
    This function substitutes input variables for output variables to connect two rms models
    :param mdl1:
    :param mdl2:
    :return:
    """
    # connect Vm
    pairs = [
        (outp, inpt)
        for outp in mdl1.out_vars
        for inpt in mdl2.in_vars
        if outp.ref == VarPowerFlowRefferenceType.Vm and inpt.ref == VarPowerFlowRefferenceType.Vmf
    ]
    for outp, inpt in pairs:
        mdl2.connect([inpt], [outp])

    # connect Va
    pairs = [
        (outp, inpt)
        for outp in mdl1.out_vars
        for inpt in mdl2.in_vars
        if outp.ref == VarPowerFlowRefferenceType.Va and inpt.ref == VarPowerFlowRefferenceType.Vaf
    ]
    for outp, inpt in pairs:
        mdl2.connect([inpt], [outp])

def connect_models_power_flow(mdl1: Block, mdl2: Block):
    """
    This function substitutes input variables for output variables to connect two rms models
    :param mdl1:
    :param mdl2:
    :return:

    """
    # connect inputs mdl2 with outputs mdl1
    pairs = [
        (outp, inpt)
        for outp in mdl1.out_vars
        for inpt in mdl2.in_vars
        if outp.ref == inpt.ref
    ]
    for pair in pairs:
        mdl2.connect([pair[1]], [pair[0]])


def connect_line_rms_to(mdl1: Block, mdl2: Block):
    """
    This function substitutes input variables for output variables to connect two rms models
    :param mdl1:
    :param mdl2:
    :return:
    """
    # connect Vm
    pairs = [
        (outp, inpt)
        for outp in mdl1.out_vars
        for inpt in mdl2.in_vars
        if outp.ref == VarPowerFlowRefferenceType.Vm and inpt.ref == VarPowerFlowRefferenceType.Vmt
    ]
    for outp, inpt in pairs:
        mdl2.connect([inpt], [outp])

    # connect Va
    pairs = [
        (outp, inpt)
        for outp in mdl1.out_vars
        for inpt in mdl2.in_vars
        if outp.ref == VarPowerFlowRefferenceType.Va and inpt.ref == VarPowerFlowRefferenceType.Vat
    ]
    for outp, inpt in pairs:
        mdl2.connect([inpt], [outp])


def connect_line_phasor_rms_from(mdl1: Block, mdl2: Block):
    """
    Connect phasor RMS models for the 'from' end of a line.
    Connects Vr, Vi from bus to line inputs.
    """
    # connect Vr
    pairs = [
        (outp, inpt)
        for outp in mdl1.out_vars
        for inpt in mdl2.in_vars
        if outp.ref == VarPowerFlowRefferenceType.Vr and inpt.ref == VarPowerFlowRefferenceType.Vrf
    ]
    for outp, inpt in pairs:
        mdl2.connect([inpt], [outp])

    # connect Vi
    pairs = [
        (outp, inpt)
        for outp in mdl1.out_vars
        for inpt in mdl2.in_vars
        if outp.ref == VarPowerFlowRefferenceType.Vi and inpt.ref == VarPowerFlowRefferenceType.Vif
    ]
    for outp, inpt in pairs:
        mdl2.connect([inpt], [outp])


def connect_line_phasor_rms_to(mdl1: Block, mdl2: Block):
    """
    Connect phasor RMS models for the 'to' end of a line.
    Connects Vr, Vi from bus to line inputs.
    """
    # connect Vr
    pairs = [
        (outp, inpt)
        for outp in mdl1.out_vars
        for inpt in mdl2.in_vars
        if outp.ref == VarPowerFlowRefferenceType.Vr and inpt.ref == VarPowerFlowRefferenceType.Vrt
    ]
    for outp, inpt in pairs:
        mdl2.connect([inpt], [outp])

    # connect Vi
    pairs = [
        (outp, inpt)
        for outp in mdl1.out_vars
        for inpt in mdl2.in_vars
        if outp.ref == VarPowerFlowRefferenceType.Vi and inpt.ref == VarPowerFlowRefferenceType.Vit
    ]
    for outp, inpt in pairs:
        mdl2.connect([inpt], [outp])


def connect_models(mdl1: Block, mdl2: Block):
    """
    This function substitutes input variables for output variables to connect two rms models
    :param mdl1:
    :param mdl2:
    :return:
    """
    # connect inputs mdl2 with outputs mdl1
    pairs = [
        (outp, inpt)
        for outp in mdl1.out_vars
        for inpt in mdl2.in_vars
        if outp.ref == inpt.shared_ref and outp.shared_ref is not None and inpt.shared_ref is not None
    ]

    for outp, inpt in pairs:
        mdl2.connect([inpt], [outp])

    # connect inputs mdl1 with outputs mdl2
    pairs = [
        (outp, inpt)
        for outp in mdl2.out_vars
        for inpt in mdl1.in_vars
        if outp.shared_ref == inpt.shared_ref and outp.shared_ref is not None and inpt.shared_ref is not None
    ]

    for outp, inpt in pairs:
        mdl1.connect([inpt], [outp])

    # # connect inputs mdl1 with inputs mdl2
    # pairs = [
    #     (inpt1, inpt2)
    #     for inpt2 in mdl2.in_vars
    #     for inpt1 in mdl1.in_vars
    #     if inpt1.power_flow_reference is not None and inpt2.power_flow_reference is not None and inpt1.power_flow_reference == inpt2.power_flow_reference
    #
    # ]
    # for pair in pairs:
    #     if pair[0].network_conn:
    #         mdl1.connect([pair[1]], [pair[0]])
    #     else:
    #         mdl1.connect([pair[0]], [pair[1]])




    #print("")
def connect_bus_variables(device: Any, model:Block, var_factory: VarFactory):
    """
    connect the bus variables of the model with the api_object bus variables
    :param device:
    :type device:
    :param model:
    :type model:
    :param var_factory:
    :type var_factory:
    :return:
    :rtype:
    """

    if device.device_type in [DeviceType.BranchDevice, DeviceType.LineDevice, DeviceType.Transformer2WDevice, DeviceType.Transformer3WDevice]:
        # Check if using phasor or polar coordinates by looking at bus model outputs
        bus_model = device.bus_from.rms_model
        if bus_model.empty():
            initialize_bus_rms(device.bus_from, var_factory)

        # Check if bus has Vr/Vi (phasor) or Vm/Va (polar) outputs
        has_phasor = any(v.ref == VarPowerFlowRefferenceType.Vr for v in bus_model.out_vars)
        if has_phasor:
            connect_line_phasor_rms_from(device.bus_from.rms_model, model)
        else:
            connect_line_rms_from(device.bus_from.rms_model, model)


        bus_model = device.bus_to.rms_model
        if bus_model.empty():
            initialize_bus_rms(device.bus_to, var_factory)
        # Check if bus has Vr/Vi (phasor) or Vm/Va (polar) outputs
        has_phasor = any(v.ref == VarPowerFlowRefferenceType.Vr for v in bus_model.out_vars)
        if has_phasor:
            connect_line_phasor_rms_to(device.bus_to.rms_model, model)
        else:
            connect_line_rms_to(device.bus_to.rms_model, model)


    else:
        if device.bus.rms_model.empty():
            initialize_bus_rms(device.bus, var_factory)
            connect_models_power_flow(device.bus.rms_model, model)

        else:
            raise ValueError(f"Connection Bus RMS model cannot be empty, initialize {device.bus.name} RMS model")



def set_rms_model(device: Any, model:Block, var_factory: VarFactory):
    """
    Set the RMS model
    :return:
    :rtype:
    """
    # connect bus variables

    if device.device_type in [DeviceType.BranchDevice, DeviceType.LineDevice, DeviceType.Transformer2WDevice, DeviceType.Transformer3WDevice]:
        # Check if using phasor or polar coordinates by looking at bus model outputs
        bus_model = device.bus_from.rms_model
        if not bus_model.empty():
            # Check if bus has Vr/Vi (phasor) or Vm/Va (polar) outputs
            has_phasor = any(v.ref == VarPowerFlowRefferenceType.Vr for v in bus_model.out_vars)
            if has_phasor:
                connect_line_phasor_rms_from(device.bus_from.rms_model, model)
            else:
                connect_line_rms_from(device.bus_from.rms_model, model)
        else:
            raise ValueError(f"Connection Bus RMS model cannot be empty, initialize {device.bus_from.name} RMS model")

        bus_model = device.bus_to.rms_model
        if not bus_model.empty():
            # Check if bus has Vr/Vi (phasor) or Vm/Va (polar) outputs
            has_phasor = any(v.ref == VarPowerFlowRefferenceType.Vr for v in bus_model.out_vars)
            if has_phasor:
                connect_line_phasor_rms_to(device.bus_to.rms_model, model)
            else:
                connect_line_rms_to(device.bus_to.rms_model, model)
        else:
            raise ValueError(f"Connection Bus RMS model cannot be empty, initialize {device.bus_to.name} RMS model")

    else:
        if not device.bus.rms_model.empty():
            connect_models_power_flow(device.bus.rms_model, model)

        else:
            raise ValueError(f"Connection Bus RMS model cannot be empty, initialize {device.bus.name} RMS model")

    # fill var factoru dict[Dev, List[Var]] with model variables
    model.unify_blocks()
    for vr in model.algebraic_vars:
        var_factory.register_var(device, vr)
    for vr in model.state_vars:
        var_factory.register_var(device, vr)

    # set the model to the device
    device.rms_model = model


def connect_line_emt_from(mdl1: Block, mdl2: Block):
    """
    Connects the bus voltages (mdl1) to the "from" side of the line (mdl2)
    for simulations with explicit phases (e.g., EMT).
    It only connects the phases present in both models (any NABC combination).

    :param mdl1: Bus model (Block)
    :param mdl2: Line model (Block)
    :return: None
    """
    # Create a dictionary to map the bus output variable
    # to the corresponding line input variable ("from" side)
    phase_map = {
        VarPowerFlowRefferenceType.v_N: VarPowerFlowRefferenceType.vf_N,
        VarPowerFlowRefferenceType.v_A: VarPowerFlowRefferenceType.vf_A,
        VarPowerFlowRefferenceType.v_B: VarPowerFlowRefferenceType.vf_B,
        VarPowerFlowRefferenceType.v_C: VarPowerFlowRefferenceType.vf_C,
        VarPowerFlowRefferenceType.Vdc: VarPowerFlowRefferenceType.Vf_dc,
    }

    # Find the variable pairs that match our mapping
    pairs = [
        (outp, inpt)
        for outp in mdl1.out_vars
        for inpt in mdl2.in_vars
        if outp.ref in phase_map and phase_map[outp.ref] == inpt.ref
    ]

    # Connect all found pairs
    for outp, inpt in pairs:
        mdl2.connect([inpt], [outp])

def connect_line_emt_to(mdl1: Block, mdl2: Block):
    """
    Connects the bus voltages (mdl1) to the "to" side of the line (mdl2)
    for simulations with explicit phases (e.g., EMT).
    It only connects the phases present in both models (any NABC combination).

    :param mdl1: Bus model (Block)
    :param mdl2: Line model (Block)
    :return: None
    """
    # Create a dictionary to map the bus output variable
    # to the corresponding line input variable ("to" side)
    phase_map = {
        VarPowerFlowRefferenceType.v_N: VarPowerFlowRefferenceType.vt_N,
        VarPowerFlowRefferenceType.v_A: VarPowerFlowRefferenceType.vt_A,
        VarPowerFlowRefferenceType.v_B: VarPowerFlowRefferenceType.vt_B,
        VarPowerFlowRefferenceType.v_C: VarPowerFlowRefferenceType.vt_C,
        VarPowerFlowRefferenceType.Vdc: VarPowerFlowRefferenceType.Vt_dc,
    }

    # Find the variable pairs that match our mapping
    pairs = [
        (outp, inpt)
        for outp in mdl1.out_vars
        for inpt in mdl2.in_vars
        if outp.ref in phase_map and phase_map[outp.ref] == inpt.ref
    ]

    # Connect all found pairs
    for outp, inpt in pairs:
        mdl2.connect([inpt], [outp])


def connect_vsc_emt_from(mdl1: Block, mdl2: Block, is_dc_bus: bool = False):
    """
    Connects the bus voltages to the "from" side of the VSC model.
    For DC buses, connects Vdc. For AC buses, connects abc voltages.

    :param mdl1: Bus model (Block)
    :param mdl2: VSC model (Block)
    :param is_dc_bus: True if bus_from is DC
    :return: None
    """
    if is_dc_bus:
        # DC bus: connect Vdc
        dc_map = {
            VarPowerFlowRefferenceType.Vdc: VarPowerFlowRefferenceType.Vdc
        }
        pairs = [
            (outp, inpt)
            for outp in mdl1.out_vars
            for inpt in mdl2.in_vars
            if outp.ref in dc_map and dc_map[outp.ref] == inpt.ref
        ]
    else:
        # AC bus: connect abc voltages
        phase_map = {
            VarPowerFlowRefferenceType.v_A: VarPowerFlowRefferenceType.v_A,
            VarPowerFlowRefferenceType.v_B: VarPowerFlowRefferenceType.v_B,
            VarPowerFlowRefferenceType.v_C: VarPowerFlowRefferenceType.v_C
        }
        pairs = [
            (outp, inpt)
            for outp in mdl1.out_vars
            for inpt in mdl2.in_vars
            if outp.ref in phase_map and phase_map[outp.ref] == inpt.ref
        ]

    for outp, inpt in pairs:
        mdl2.connect([inpt], [outp])


def connect_vsc_emt_to(mdl1: Block, mdl2: Block, is_dc_bus: bool = False):
    """
    Connects the bus voltages to the "to" side of the VSC model.
    For DC buses, connects Vdc. For AC buses, connects abc voltages.

    :param mdl1: Bus model (Block)
    :param mdl2: VSC model (Block)
    :param is_dc_bus: True if bus_to is DC
    :return: None
    """
    if is_dc_bus:
        # DC bus: connect Vdc
        dc_map = {
            VarPowerFlowRefferenceType.Vdc: VarPowerFlowRefferenceType.Vdc
        }
        pairs = [
            (outp, inpt)
            for outp in mdl1.out_vars
            for inpt in mdl2.in_vars
            if outp.ref in dc_map and dc_map[outp.ref] == inpt.ref
        ]
    else:
        # AC bus: connect abc voltages
        phase_map = {
            VarPowerFlowRefferenceType.v_A: VarPowerFlowRefferenceType.v_A,
            VarPowerFlowRefferenceType.v_B: VarPowerFlowRefferenceType.v_B,
            VarPowerFlowRefferenceType.v_C: VarPowerFlowRefferenceType.v_C
        }
        pairs = [
            (outp, inpt)
            for outp in mdl1.out_vars
            for inpt in mdl2.in_vars
            if outp.ref in phase_map and phase_map[outp.ref] == inpt.ref
        ]

    for outp, inpt in pairs:
        mdl2.connect([inpt], [outp])


def set_emt_model(device: Any, model: Block, var_factory: VarFactory):
    """
    Sets the EMT model for a given device, connects it to the bus(es),
    and registers all its variables in the VarFactory.

    :param device: The power system device (Line, Transformer, Generator, etc.)
    :param model: The mathematical block model of the device
    :param var_factory: Factory to register simulation variables
    :return: None
    """
    # 1. Connect bus variables depending on the device type
    if device.device_type in [DeviceType.BranchDevice,
                              DeviceType.LineDevice,
                              DeviceType.DCLineDevice,
                              DeviceType.HVDCLineDevice,
                              DeviceType.SwitchDevice,
                              DeviceType.SeriesReactanceDevice,
                              DeviceType.UpfcDevice,
                              DeviceType.Transformer2WDevice,
                              DeviceType.Transformer3WDevice]:

        # Bus FROM connection
        bus_from_model = device.bus_from.emt_model
        if not bus_from_model.empty():
            connect_line_emt_from(bus_from_model, model)
        else:
            raise ValueError(f"Connection Bus EMT model cannot be empty, initialize {device.bus_from.name} EMT model")

        # Bus TO connection
        bus_to_model = device.bus_to.emt_model
        if not bus_to_model.empty():
            connect_line_emt_to(bus_to_model, model)
        else:
            raise ValueError(f"Connection Bus EMT model cannot be empty, initialize {device.bus_to.name} EMT model")

    elif device.device_type == DeviceType.VscDevice:

        # VSC: bus_from is DC, bus_to is AC
        bus_from_model = device.bus_from.emt_model
        if not bus_from_model.empty():
            connect_vsc_emt_from(bus_from_model, model, is_dc_bus=device.bus_from.is_dc)
        else:
            raise ValueError(f"Connection Bus EMT model cannot be empty, initialize {device.bus_from.name} EMT model")

        bus_to_model = device.bus_to.emt_model
        if not bus_to_model.empty():
            connect_vsc_emt_to(bus_to_model, model, is_dc_bus=device.bus_to.is_dc)
        else:
            raise ValueError(f"Connection Bus EMT model cannot be empty, initialize {device.bus_to.name} EMT model")

    else:
        # Generic device connection (e.g., Loads, Generators connected to a single bus)
        if not device.bus.emt_model.empty():
            connect_models(device.bus.emt_model, model)
        else:
            raise ValueError(f"Connection Bus EMT model cannot be empty, initialize {device.bus.name} EMT model")

    # 2. Unify blocks and register all variables in the VarFactory
    model.unify_blocks()

    for vr in model.algebraic_vars:
        var_factory.register_var(device, vr)

    for vr in model.state_vars:
        var_factory.register_var(device, vr)

    # Added diff_vars for EMT simulations
    for vr in model.diff_vars:
        var_factory.register_var(device, vr)

    # 3. Assign the configured model to the device
    device.emt_model = model
