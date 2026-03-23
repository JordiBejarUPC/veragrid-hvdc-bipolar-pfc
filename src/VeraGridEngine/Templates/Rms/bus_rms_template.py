# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import Tuple, Optional

from typing import TYPE_CHECKING
from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory

from VeraGridEngine.Utils.Symbolic.block import Block, VarPowerFlowRefferenceType
from VeraGridEngine.Utils.Symbolic.symbolic import Var

if TYPE_CHECKING:
    from VeraGridEngine.Devices.Substation.bus import Bus


class BusRmsTemplate(RmsModelTemplate):

    def __init__(self, vf: VarFactory, is_dc:bool=False, name: str = "rms_bus_template"):
        """
        Created the RMS Template of a Bus
        :param vf: VarFactory
        :param name: Name of the RMS Model
        """
        super().__init__(name=name)

        self.tpe: DeviceType = DeviceType.BusDevice
        if is_dc:
            Vdc = vf.add_var("Vdc")
            P = vf.add_var("P")
            Q = vf.add_var("Q")

            self._block = Block(
                algebraic_vars=[Vdc],
                out_vars = [Vdc])

            self._block.external_mapping = {
                VarPowerFlowRefferenceType.Vdc: Vdc,
                VarPowerFlowRefferenceType.P: P,
                VarPowerFlowRefferenceType.Q: Q
            }

        else:
            self.Vm = vf.add_var("Vm", VarPowerFlowRefferenceType.Vm)
            self.Va = vf.add_var("Va", VarPowerFlowRefferenceType.Va)

            algebraic_eqs = []
            event_dict = {}
            init_eqs = {}

            if is_slack:
                vm_ref = vf.add_var("Vm_ref")
                va_ref = vf.add_var("Va_ref")
                algebraic_eqs = [
                    self.Vm - vm_ref,
                    self.Va - va_ref,
                ]
                event_dict = {
                    vm_ref: vf.add_const(1.0),
                    va_ref: vf.add_const(0.0),
                }
                init_eqs = {
                    self.Vm: vm_ref,
                    self.Va: va_ref,
                }

            self._block = Block(
                algebraic_vars=[self.Vm, self.Va],
                algebraic_eqs=algebraic_eqs,
                event_dict=event_dict,
                init_eqs=init_eqs,
                out_vars=[self.Vm, self.Va]
            )
    
            self._block.external_mapping = {
                VarPowerFlowRefferenceType.Vm: self.Vm,
                VarPowerFlowRefferenceType.Va: self.Va,
            }


def initialize_bus_rms(bus: Bus, vf: VarFactory):
    """

    :param bus:
    :param vf:
    :return:
    """
    bus.rms_model = BusRmsTemplate(vf=vf, is_dc=bus.is_dc).block

# def get_bus_rms_algebraic_vars(bus_rms_model: Block) -> Tuple[Var, Var]:
#     """
#     Initializes rms model if not initialized
#     :return: Vm, Va rms vars
#     """
#
#     return bus_rms_model.algebraic_vars[0], bus_rms_model.algebraic_vars[1]


def get_bus_rms_algebraic_vars(bus_rms_model: Block) -> Tuple[Var, Optional[Var]]:
    """
    Return the RMS bus algebraic voltage variables.

    For AC buses:
        returns (Vm, Va)

    For DC buses:
        returns (Vdc, None)

    :param bus_rms_model: RMS bus block
    :return: Tuple with two positions to preserve the project API
    """
    mapping = bus_rms_model.external_mapping

    vdc = mapping.get(VarPowerFlowRefferenceType.Vdc, None)
    if vdc is not None:
        return vdc, None

    vm = mapping.get(VarPowerFlowRefferenceType.Vm, None)
    va = mapping.get(VarPowerFlowRefferenceType.Va, None)

    if vm is None or va is None:
        raise ValueError("Invalid RMS bus model: expected either (Vdc) or (Vm, Va)")

    return vm, va


