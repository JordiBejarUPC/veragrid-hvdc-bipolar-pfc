# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Optional

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.template_definiton import TemplateDefinition, TemplateProp
from VeraGridEngine.Utils.Symbolic.block import Var
from VeraGridEngine.enumerations import DeviceType, VarPowerFlowReferenceType


class DcCurrentSourceEmtTemplate(TemplateDefinition):

    def __init__(self, vf):
        super().__init__(vf, params=[
            TemplateProp(name="source_current_value", units="", descr="Fixed injected DC current.", tpe=float),
            TemplateProp(name="name", units="", descr="Name of the emt model.", tpe=str),
        ])

    def eval(self) -> EmtModelTemplate:
        return get_dc_current_source_emt_template(
            self.vf,
            self.get_value("source_current_value"),
            self.get_value("name"),
        )


class ControlledDcCurrentSourceEmtTemplate(TemplateDefinition):

    def __init__(self, vf):
        super().__init__(vf, params=[
            TemplateProp(name="name", units="", descr="Name of the emt model.", tpe=str),
        ])

    def eval(self) -> EmtModelTemplate:
        return get_controlled_dc_current_source_emt_template(self.vf, self.get_value("name"))


class DcVoltageSourceEmtTemplate(TemplateDefinition):

    def __init__(self, vf):
        super().__init__(vf, params=[
            TemplateProp(name="source_voltage_value", units="", descr="Fixed source voltage.", tpe=Optional[float]),
            TemplateProp(name="source_conductance_value", units="Siemens", descr="Norton conductance.", tpe=float),
            TemplateProp(name="name", units="", descr="Name of the emt model.", tpe=str),
        ])

    def eval(self) -> EmtModelTemplate:
        return get_dc_voltage_source_emt_template(
            self.vf,
            self.get_value("source_voltage_value"),
            self.get_value("source_conductance_value"),
            self.get_value("name"),
        )


class ControlledDcVoltageSourceEmtTemplate(TemplateDefinition):

    def __init__(self, vf):
        super().__init__(vf, params=[
            TemplateProp(name="source_conductance_value", units="Siemens", descr="Norton conductance.", tpe=float),
            TemplateProp(name="name", units="", descr="Name of the emt model.", tpe=str),
        ])

    def eval(self) -> EmtModelTemplate:
        return get_controlled_dc_voltage_source_emt_template(
            self.vf,
            self.get_value("source_conductance_value"),
            self.get_value("name"),
        )


def get_dc_current_source_emt_template(vf: VarFactory,
                                       source_current_value: float = 0.0,
                                       name: str = "dc_current_source_emt") -> EmtModelTemplate:
    """
    Build one EMT DC current source with fixed injected current.

    Positive DC current injects into the connected DC bus.

    :param vf: EMT variable factory.
    :param source_current_value: Fixed injected DC current.
    :param name: Symbolic model name.
    :return: Configured EMT template.
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.GeneratorDevice
    templ.name = name
    templ.block.name = name

    v_dc: Var = vf.add_var(name=f"v_dc_{name}", reference=VarPowerFlowReferenceType.Vdc)
    i_dc: Var = vf.add_var(name=f"i_dc_{name}", reference=VarPowerFlowReferenceType.Idc)
    i_src: Var = vf.add_var(name=f"I_src_{name}")
    templ.block.event_dict[i_src] = vf.add_const(float(source_current_value))

    templ.block.in_vars = [v_dc]
    templ.block.algebraic_vars = [i_dc]
    templ.block.algebraic_eqs = [i_dc - i_src]
    templ.block.out_vars = [i_dc]
    templ.block.external_mapping = {
        VarPowerFlowReferenceType.Vdc: v_dc,
        VarPowerFlowReferenceType.Idc: i_dc,
    }
    templ.block.init_eqs[i_dc] = i_src
    return templ


def get_controlled_dc_current_source_emt_template(vf: VarFactory,
                                                  name: str = "controlled_dc_current_source_emt") -> EmtModelTemplate:
    """
    Build one EMT DC current source driven by one command input.

    The command input is the injected DC current.

    :param vf: EMT variable factory.
    :param name: Symbolic model name.
    :return: Configured EMT template.
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.GeneratorDevice
    templ.name = name
    templ.block.name = name

    v_dc: Var = vf.add_var(name=f"v_dc_{name}", reference=VarPowerFlowReferenceType.Vdc)
    i_cmd: Var = vf.add_var(name=f"i_cmd_{name}")
    i_dc: Var = vf.add_var(name=f"i_dc_{name}", reference=VarPowerFlowReferenceType.Idc)

    templ.block.in_vars = [v_dc, i_cmd]
    templ.block.algebraic_vars = [i_dc]
    templ.block.algebraic_eqs = [i_dc - i_cmd]
    templ.block.out_vars = [i_dc]
    templ.block.external_mapping = {
        VarPowerFlowReferenceType.Vdc: v_dc,
        VarPowerFlowReferenceType.Idc: i_dc,
    }
    templ.block.init_eqs[i_dc] = i_cmd
    return templ


def get_dc_voltage_source_emt_template(vf: VarFactory,
                                       source_voltage_value: Optional[float] = 0.0,
                                       source_conductance_value: float = 100.0,
                                       name: str = "dc_voltage_source_emt") -> EmtModelTemplate:
    """
    Build one EMT DC voltage source using one Norton equivalent.

    The source injects ``i = g * (Vsrc - Vdc)``.

    :param vf: EMT variable factory.
    :param source_voltage_value: Fixed source voltage.
    :param source_conductance_value: Norton conductance.
    :param name: Symbolic model name.
    :return: Configured EMT template.
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.GeneratorDevice
    templ.name = name
    templ.block.name = name

    v_dc: Var = vf.add_var(name=f"v_dc_{name}", reference=VarPowerFlowReferenceType.Vdc)
    i_dc: Var = vf.add_var(name=f"i_dc_{name}", reference=VarPowerFlowReferenceType.Idc)
    v_src: Var = vf.add_var(name=f"V_src_{name}")
    g_src: Var = vf.add_var(name=f"g_src_{name}")
    templ.block.event_dict[v_src] = vf.add_const(
        None if source_voltage_value is None else float(source_voltage_value)
    )
    templ.block.event_dict[g_src] = vf.add_const(float(source_conductance_value))

    templ.block.in_vars = [v_dc]
    templ.block.algebraic_vars = [i_dc]
    templ.block.algebraic_eqs = [i_dc - g_src * (v_src - v_dc)]
    templ.block.out_vars = [i_dc]
    templ.block.external_mapping = {
        VarPowerFlowReferenceType.Vdc: v_dc,
        VarPowerFlowReferenceType.Idc: i_dc,
    }
    templ.block.init_eqs[i_dc] = g_src * (v_src - v_dc)
    templ.block.init_eqs[v_src] = v_dc + i_dc / g_src
    return templ


def get_controlled_dc_voltage_source_emt_template(vf: VarFactory,
                                                  source_conductance_value: float = 100.0,
                                                  name: str = "controlled_dc_voltage_source_emt") -> EmtModelTemplate:
    """
    Build one EMT DC voltage source driven by one command input.

    The command input is the internal source DC voltage used by the Norton
    equivalent ``i = g * (Vcmd - Vdc)``.

    :param vf: EMT variable factory.
    :param source_conductance_value: Norton conductance.
    :param name: Symbolic model name.
    :return: Configured EMT template.
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.GeneratorDevice
    templ.name = name
    templ.block.name = name

    v_dc: Var = vf.add_var(name=f"v_dc_{name}", reference=VarPowerFlowReferenceType.Vdc)
    v_cmd: Var = vf.add_var(name=f"v_cmd_{name}")
    i_dc: Var = vf.add_var(name=f"i_dc_{name}", reference=VarPowerFlowReferenceType.Idc)
    g_src: Var = vf.add_var(name=f"g_src_{name}")
    templ.block.event_dict[g_src] = vf.add_const(float(source_conductance_value))

    templ.block.in_vars = [v_dc, v_cmd]
    templ.block.algebraic_vars = [i_dc]
    templ.block.algebraic_eqs = [i_dc - g_src * (v_cmd - v_dc)]
    templ.block.out_vars = [i_dc]
    templ.block.external_mapping = {
        VarPowerFlowReferenceType.Vdc: v_dc,
        VarPowerFlowReferenceType.Idc: i_dc,
    }
    templ.block.init_eqs[i_dc] = g_src * (v_cmd - v_dc)
    return templ
