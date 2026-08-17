# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.enumerations import (
    DeviceType,
    ParamPowerFlowReferenceType,
    VarPowerFlowReferenceType,
)
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym


def VoltageSourceBuild(
    vfactory: VarFactory,
    name: str = "",
) -> RmsModelTemplate:
    """
    Build an ideal RMS voltage-source template.

    An external grid fixes voltage magnitude and angle while its active and
    reactive injections follow from the network balance. PowerFactory
    ``ElmXnet`` objects do not define generator P/Q capability limits, and the
    corresponding VeraGrid device has no such properties. Therefore this
    template must not introduce synthetic injection limits.

    :param vfactory: Symbolic variable factory shared by the circuit.
    :param name: Optional human-readable template name.
    :return: Ideal external-grid RMS template.
    """
    templ: RmsModelTemplate = RmsModelTemplate()
    templ.tpe = DeviceType.ExternalGridDevice

    Vm: Var = vfactory.add_var("Vm", VarPowerFlowReferenceType.Vm)
    Va: Var = vfactory.add_var("Va", VarPowerFlowReferenceType.Va)
    inputs: list[Var] = list([Vm, Va])

    P: Var = vfactory.add_var("P")
    Q: Var = vfactory.add_var("Q")

    Vg0: Var = vfactory.add_var("Vg0")
    Ag0: Var = vfactory.add_var("Ag0")

    event_dict: dict[Var, Const] = {
        Vg0: vfactory.add_const(None),
        Ag0: vfactory.add_const(None),
    }

    init_eqs: dict[Var, Var] = {
        Vg0: Vm,
        Ag0: Va,
    }

    # The two balance injections remain algebraic unknowns. The source itself
    # contributes only the ideal voltage constraints used by PowerFactory's
    # voltage-source external-network representation.
    templ.block = Block(
        algebraic_eqs=[
            Va - Ag0,
            Vm - Vg0,
        ],
        algebraic_vars=[P, Q],
        init_eqs=init_eqs,
        event_dict=event_dict,
    )

    templ.block.name = "Voltage Source"
    templ.block.external_mapping = {
        VarPowerFlowReferenceType.P: P,
        VarPowerFlowReferenceType.Q: Q,
        VarPowerFlowReferenceType.Vm: Vm,
        VarPowerFlowReferenceType.Va: Va,
    }
    templ.block.in_vars = inputs

    return templ


def build_thevenin_voltage_source(
        vfactory: VarFactory,
        resistance_pu: float,
        reactance_pu: float,
        name: str = "",
) -> RmsModelTemplate:
    """Build an RMS external-network source behind its DGS impedance.

    PowerFactory ``ElmXnet`` objects are ideal internal voltage sources behind
    the positive-sequence impedance derived from ``snss`` and ``rntxn``.  The
    terminal voltage therefore changes when the connected system exchanges
    power, even though the source's internal voltage remains constant.  This
    template retains that physical distinction and works with both the polar
    P/Q DAE and the rectangular-current phasor formulation.

    :param vfactory: Symbolic variable factory shared by the circuit.
    :param resistance_pu: Positive-sequence source resistance on system base.
    :param reactance_pu: Positive-sequence source reactance on system base.
    :param name: Optional human-readable template name.
    :return: External-network RMS template with a finite Thevenin impedance.
    """
    template: RmsModelTemplate = RmsModelTemplate(name=name)
    template.tpe = DeviceType.GeneratorDevice

    # Terminal voltage is supplied by the connected AC bus.  Power and current
    # are both retained so either supported RMS network formulation can stamp
    # the same physical source without rebuilding the template.
    voltage_magnitude: Var = vfactory.add_var(
        "Vm",
        VarPowerFlowReferenceType.Vm,
    )
    voltage_angle: Var = vfactory.add_var(
        "Va",
        VarPowerFlowReferenceType.Va,
    )
    active_power: Var = vfactory.add_var(
        "P",
        VarPowerFlowReferenceType.P,
    )
    reactive_power: Var = vfactory.add_var(
        "Q",
        VarPowerFlowReferenceType.Q,
    )
    current_real: Var = vfactory.add_var(
        "Ir",
        VarPowerFlowReferenceType.Ir,
    )
    current_imaginary: Var = vfactory.add_var(
        "Ii",
        VarPowerFlowReferenceType.Ii,
    )

    source_voltage: Var = vfactory.add_var("E_internal")
    source_angle: Var = vfactory.add_var("A_internal")
    resistance: Var = vfactory.add_var("R1")
    reactance: Var = vfactory.add_var("X1")

    terminal_voltage_real: Expr = voltage_magnitude * sym.cos(voltage_angle)
    terminal_voltage_imaginary: Expr = voltage_magnitude * sym.sin(voltage_angle)
    internal_voltage_real: Expr = (
        terminal_voltage_real
        + resistance * current_real
        - reactance * current_imaginary
    )
    internal_voltage_imaginary: Expr = (
        terminal_voltage_imaginary
        + reactance * current_real
        + resistance * current_imaginary
    )

    # The power/current identities use the injection sign convention
    # S = V * conj(I).  The last two equations impose E = V + Z*I, which is the
    # Thevenin source contract exported by ElmXnet.
    block: Block = Block(
        algebraic_vars=list([
            active_power,
            reactive_power,
            current_real,
            current_imaginary,
        ]),
        algebraic_eqs=list([
            active_power - voltage_magnitude * (
                sym.cos(voltage_angle) * current_real
                + sym.sin(voltage_angle) * current_imaginary
            ),
            reactive_power - voltage_magnitude * (
                sym.sin(voltage_angle) * current_real
                - sym.cos(voltage_angle) * current_imaginary
            ),
            source_voltage * sym.cos(source_angle) - internal_voltage_real,
            source_voltage * sym.sin(source_angle) - internal_voltage_imaginary,
        ]),
        parameters=dict({
            resistance: Const(float(resistance_pu)),
            reactance: Const(float(reactance_pu)),
        }),
        event_dict=dict({
            source_voltage: Const(None),
            source_angle: Const(None),
        }),
        init_eqs=dict({
            source_voltage: sym.sqrt(
                internal_voltage_real * internal_voltage_real
                + internal_voltage_imaginary * internal_voltage_imaginary
            ),
            source_angle: sym.atan2(
                internal_voltage_imaginary,
                internal_voltage_real,
            ),
        }),
        in_vars=list([voltage_magnitude, voltage_angle]),
        out_vars=list([
            active_power,
            reactive_power,
            current_real,
            current_imaginary,
        ]),
    )
    block.name = name if len(name) > 0 else "Thevenin Voltage Source"
    block.external_mapping = {
        VarPowerFlowReferenceType.P: active_power,
        VarPowerFlowReferenceType.Q: reactive_power,
        VarPowerFlowReferenceType.Ir: current_real,
        VarPowerFlowReferenceType.Ii: current_imaginary,
        VarPowerFlowReferenceType.Vm: voltage_magnitude,
        VarPowerFlowReferenceType.Va: voltage_angle,
    }
    block.api_obj_mapping = {
        ParamPowerFlowReferenceType.R1: resistance,
        ParamPowerFlowReferenceType.X1: reactance,
    }
    template.block = block
    return template
