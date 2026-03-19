# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Utils.Symbolic.block import Block, VarPowerFlowRefferenceType

# depending on the number of phases of the bus a different model must be created.
class BusEmtTemplateNABC(EmtModelTemplate):

    def __init__(self,
                 vf: VarFactory,
                 mask: list[bool],
                 is_dc: bool = False,
                 name: str = "emt_bus_template"):
        """
        Created the EMT Template of a Bus
        :param vf: VarFactory
        :param mask: list[bool] with true if the phase exist and false if it doesn't in the order [N,A,B,C]
        :param name: Name of the EMT Model
        """

        super().__init__(name=name)

        self.tpe: DeviceType = DeviceType.BusDevice

        self.v_N = vf.add_var(name=f"v_N_{name}", ref = VarPowerFlowRefferenceType.v_N) if mask[0] else None
        self.v_A = vf.add_var(name=f"v_A_{name}", ref = VarPowerFlowRefferenceType.v_A) if mask[1] else None
        self.v_B = vf.add_var(name=f"v_B_{name}", ref = VarPowerFlowRefferenceType.v_B) if mask[2] else None
        self.v_C = vf.add_var(name=f"v_C_{name}", ref = VarPowerFlowRefferenceType.v_C) if mask[3] else None

        v_list = [v for v in (self.v_N, self.v_A, self.v_B, self.v_C) if v is not None]
        if not v_list:
            raise ValueError("Bus has no enabled phases")

        self._block = Block(
            algebraic_vars=v_list,
            out_vars = v_list
        )

        self._block.external_mapping = {
            VarPowerFlowRefferenceType.v_N: self.v_N,
            VarPowerFlowRefferenceType.v_A: self.v_A,
            VarPowerFlowRefferenceType.v_B: self.v_B,
            VarPowerFlowRefferenceType.v_C: self.v_C,
            VarPowerFlowRefferenceType.P: None,
            VarPowerFlowRefferenceType.Q: None
        }

    @property
    def block(self) -> Block:
        """
        block
        :return: Block
        """
        return self._block


class BusEmtTemplate(EmtModelTemplate):

    def __init__(self,
                 vf: VarFactory,
                 mask: list[bool],
                 is_dc: bool = False,
                 name: str = "emt_bus_template"):
        """
        Created the EMT Template of a Bus
        :param vf: VarFactory
        :param mask: list[bool] with true if the phase exist and false if it doesn't in the order [N,A,B,C]
        :param name: Name of the EMT Model
        """
        super().__init__(name=name)

        self.tpe: DeviceType = DeviceType.BusDevice
        if is_dc:
            # For a DC bus in EMT, we track the instantaneous DC voltage.
            self.v_DC = vf.add_var(name=f"v_DC_{name}", ref=VarPowerFlowRefferenceType.Vdc)

            self._block = Block(
                algebraic_vars=[self.v_DC],
                out_vars=[self.v_DC]
            )

            # Map the instantaneous DC voltage. P and Q are None because
            # EMT simulations compute power implicitly from v(t) and i(t).
            # Include v_N, v_A, v_B, v_C as None so that the loop in emt_problem_dae
            # can iterate over all phases without errors.
            self._block.external_mapping = {
                VarPowerFlowRefferenceType.Vdc: self.v_DC,
                VarPowerFlowRefferenceType.v_N: None,
                VarPowerFlowRefferenceType.v_A: None,
                VarPowerFlowRefferenceType.v_B: None,
                VarPowerFlowRefferenceType.v_C: None,
                VarPowerFlowRefferenceType.P: None,
                VarPowerFlowRefferenceType.Q: None
            }

        else:
            self.v_N = vf.add_var(name=f"v_N_{name}", ref=VarPowerFlowRefferenceType.v_N) if mask[0] else None
            self.v_A = vf.add_var(name=f"v_A_{name}", ref=VarPowerFlowRefferenceType.v_A) if mask[1] else None
            self.v_B = vf.add_var(name=f"v_B_{name}", ref=VarPowerFlowRefferenceType.v_B) if mask[2] else None
            self.v_C = vf.add_var(name=f"v_C_{name}", ref=VarPowerFlowRefferenceType.v_C) if mask[3] else None

            v_list = [v for v in (self.v_N, self.v_A, self.v_B, self.v_C) if v is not None]
            if not v_list:
                raise ValueError("Bus has no enabled phases")

            self._block = Block(
                algebraic_vars=v_list,
                out_vars=v_list
            )

            self._block.external_mapping = {
                VarPowerFlowRefferenceType.v_N: self.v_N,
                VarPowerFlowRefferenceType.v_A: self.v_A,
                VarPowerFlowRefferenceType.v_B: self.v_B,
                VarPowerFlowRefferenceType.v_C: self.v_C,
                VarPowerFlowRefferenceType.P: None,
                VarPowerFlowRefferenceType.Q: None
            }

    @property
    def block(self) -> Block:
        """
        block
        :return: Block
        """
        return self._block

def get_bus_emt_template(grid: MultiCircuit,
                         bus: Bus):
    """
    Initialize 3ph bus block
    A bus will have the phases of the branches connected to it
    :param grid: Multicircuit
    :param bus: Bus
    :param vf: VarFactory
    :param is_dc: Whether this is a DC bus
    :return:
    """

    vf = grid.emt_var_factory
    mask = [False,False,False,False] # [N, A, B, C]
    if not bus.is_dc:
        for branch in grid.get_branches_iter(add_vsc=True, add_switch= True, add_hvdc=True):
            if bus == branch.bus_from or bus == branch.bus_to:
                # Check if branch has ys attribute (Line, VSC, etc.)
                if hasattr(branch, 'ys') and branch.ys is not None:
                    mask[0] |= bool(branch.ys.phN)
                    mask[1] |= bool(branch.ys.phA)
                    mask[2] |= bool(branch.ys.phB)
                    mask[3] |= bool(branch.ys.phC)
                # Transformers are always 3-phase ABC
                elif hasattr(branch, 'R'):  # Transformer2W has R attribute
                    mask[1] = True  # Phase A
                    mask[2] = True  # Phase B
                    mask[3] = True  # Phase C
                else:
                    # Default: assume 3-phase for unknown branch types
                    mask[1] = True
                    mask[2] = True
                    mask[3] = True

    # choose template depending on the number of phases
    bus.emt_model = BusEmtTemplate(vf=vf, mask = mask, is_dc = bus.is_dc, name = f"{bus.name}_emt_template").block



