# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import math

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.BasicBlockCatalog.Functions.typ_124__st_1_st_enable import build_typ_124__st_1_st_enable_template
from VeraGridEngine.Templates.BasicBlockCatalog.Functions.typ_138__1_1_st import build_typ_138__1_1_st_template
from VeraGridEngine.Templates.BasicBlockCatalog.Functions.typ_151__k_1_st import build_typ_151__k_1_st_template
from VeraGridEngine.Templates.BasicBlockCatalog.Functions.typ_169__multiply_k import build_typ_169__multiply_k_template
from VeraGridEngine.Templates.BasicBlockCatalog.Functions.typ_179__multiply_k import build_typ_179__multiply_k_template
from VeraGridEngine.Templates.BasicBlockCatalog.Functions.typ_200__1_1_s_2_x_zeta_wc_ss_wc_x_wc import build_typ_200__1_1_s_2_x_zeta_wc_ss_wc_x_wc_template
from VeraGridEngine.Templates.BasicBlockCatalog.Functions.typ_214__1_s import build_typ_214__1_s_template
from VeraGridEngine.Templates.BasicBlockCatalog.Functions.typ_298__1_stb_1_sta import build_typ_298__1_stb_1_sta_template
from VeraGridEngine.Templates.BasicBlockCatalog.Functions.typ_452__kp_1_ti_s_s_s_rst_variant import build_typ_452__kp_1_ti_s_s_s_rst_variant_template
from VeraGridEngine.Templates.BasicBlockCatalog.Functions.typ_465__kp_1_ti_s_s_s_rst_sig_hold import build_typ_465__kp_1_ti_s_s_s_rst_sig_hold_template
from VeraGridEngine.Templates.BasicBlockCatalog.Functions.typ_75__lim import build_typ_75__lim_template
from VeraGridEngine.Templates.BasicBlockCatalog.Functions.typ_76__lim_const import build_typ_76__lim_const_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import CmpOp
from VeraGridEngine.Utils.Symbolic.symbolic import Comparison
from VeraGridEngine.Utils.Symbolic.symbolic import Const
from VeraGridEngine.Utils.Symbolic.symbolic import Expr
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.enumerations import DeviceType


def build_scalar_gain_runtime_template(vf: VarFactory, gain_value: float, name: str) -> EmtModelTemplate:
    """
    Build one scalar gain template using the BasicBlockCatalog primitives.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param gain_value: Scalar gain value.
    :type gain_value: float
    :param name: Runtime template name.
    :type name: str
    :return: Materialized gain template.
    :rtype: EmtModelTemplate
    """
    template_obj: EmtModelTemplate

    if float(gain_value) >= 0.0:
        template_obj = build_typ_179__multiply_k_template(vf=vf, name=name)
        template_obj.block.set_parameter_in_model('Multiply K__K_' + name, float(gain_value))
    else:
        template_obj = build_typ_169__multiply_k_template(vf=vf, name=name)
        template_obj.block.set_parameter_in_model('Multiply (-K)__K_' + name, abs(float(gain_value)))

    return template_obj


def _build_zero_output_runtime_template(vf: VarFactory, name: str) -> EmtModelTemplate:
    """
    Build one zero-valued source block with no external inputs.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param name: Runtime template name.
    :type name: str
    :return: Materialized zero-output template.
    :rtype: EmtModelTemplate
    """
    zero_output: Var = vf.add_var('zero_output_' + name)
    algebraic_equations: list[Expr] = list()
    algebraic_variables: list[Var] = list()
    output_template: EmtModelTemplate = EmtModelTemplate()
    root_block: Block = Block(name=name)

    # Materialize the constant source explicitly so it can be wired into reset pins.
    algebraic_equations.append(zero_output - Const(0.0))
    algebraic_variables.append(zero_output)
    root_block.algebraic_vars = algebraic_variables
    root_block.algebraic_eqs = algebraic_equations
    root_block.out_vars = list([zero_output])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_gain_then_first_order_runtime_template(
        vf: VarFactory,
        gain_value: float,
        time_constant: float,
        name: str,
) -> EmtModelTemplate:
    """
    Build one `gain -> first-order` chain from BasicBlockCatalog primitives.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param gain_value: Scalar gain value.
    :type gain_value: float
    :param time_constant: First-order time constant.
    :type time_constant: float
    :param name: Runtime template name.
    :type name: str
    :return: Materialized chained template.
    :rtype: EmtModelTemplate
    """
    gain_template: EmtModelTemplate = build_scalar_gain_runtime_template(vf=vf, gain_value=gain_value, name=name + '_gain')
    first_order_template: EmtModelTemplate = build_typ_138__1_1_st_template(vf=vf, name=name + '_first_order')
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()

    first_order_template.block.set_parameter_in_model('1/(1+sT)__T_' + name + '_first_order', float(time_constant))
    first_order_template.block.connect([first_order_template.block.in_vars[0]], [gain_template.block.out_vars[0]])
    root_block.merge_incoming_block(gain_template.block)
    root_block.merge_incoming_block(first_order_template.block)
    root_block.in_vars = list([gain_template.block.in_vars[0]])
    root_block.out_vars = list([first_order_template.block.out_vars[0]])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_gain_then_second_order_runtime_template(
        vf: VarFactory,
        gain_value: float,
        wc_value: float,
        zeta_value: float,
        name: str,
) -> EmtModelTemplate:
    """
    Build one `gain -> second-order low-pass` chain from BasicBlockCatalog primitives.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param gain_value: Scalar input gain value.
    :type gain_value: float
    :param wc_value: Natural frequency parameter.
    :type wc_value: float
    :param zeta_value: Damping ratio parameter.
    :type zeta_value: float
    :param name: Runtime template name.
    :type name: str
    :return: Materialized chained template.
    :rtype: EmtModelTemplate
    """
    second_order_template: EmtModelTemplate = build_typ_200__1_1_s_2_x_zeta_wc_ss_wc_x_wc_template(vf=vf, name=name + '_second_order')
    output_template: EmtModelTemplate = EmtModelTemplate()
    root_block: Block = Block(name=name)

    # Configure the recovered second-order low-pass parameters first.
    second_order_template.block.set_parameter_in_model('1/(1+s(2 x zeta)/wc+ ss/(wc x wc))__wc_' + name + '_second_order', float(wc_value))
    second_order_template.block.set_parameter_in_model('1/(1+s(2 x zeta)/wc+ ss/(wc x wc))__zeta_' + name + '_second_order', float(zeta_value))

    if math.isclose(float(gain_value), 1.0, rel_tol=1.0e-9, abs_tol=1.0e-9):
        root_block.merge_incoming_block(second_order_template.block)
        root_block.in_vars = list([second_order_template.block.in_vars[0]])
        root_block.out_vars = list([second_order_template.block.out_vars[0]])
    else:
        gain_template: EmtModelTemplate = build_scalar_gain_runtime_template(vf=vf, gain_value=gain_value, name=name + '_gain')
        second_order_template.block.connect([second_order_template.block.in_vars[0]], [gain_template.block.out_vars[0]])
        root_block.merge_incoming_block(gain_template.block)
        root_block.merge_incoming_block(second_order_template.block)
        root_block.in_vars = list([gain_template.block.in_vars[0]])
        root_block.out_vars = list([second_order_template.block.out_vars[0]])

    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_lead_lag_then_first_order_cascade_runtime_template(
        vf: VarFactory,
        tb_value: float,
        ta_value: float,
        stage_time_constants: tuple[float, ...],
        name: str,
) -> EmtModelTemplate:
    """
    Build one `lead-lag -> first-order cascade` chain from catalog primitives.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param tb_value: Lead-lag numerator time constant.
    :type tb_value: float
    :param ta_value: Lead-lag denominator time constant.
    :type ta_value: float
    :param stage_time_constants: Ordered first-order stage time constants.
    :type stage_time_constants: tuple[float, ...]
    :param name: Runtime template name.
    :type name: str
    :return: Materialized chained template.
    :rtype: EmtModelTemplate
    """
    lead_lag_template: EmtModelTemplate = build_typ_298__1_stb_1_sta_template(vf=vf, name=name + '_lead_lag')
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()
    previous_output: Var
    stage_index: int
    stage_time_constant: float
    stage_template: EmtModelTemplate

    # Configure the leading transfer function and then append each lag stage in order.
    lead_lag_template.block.set_parameter_in_model('(1+sTb)/(1+sTa)__Tb_' + name + '_lead_lag', float(tb_value))
    lead_lag_template.block.set_parameter_in_model('(1+sTb)/(1+sTa)__Ta_' + name + '_lead_lag', float(ta_value))
    root_block.merge_incoming_block(lead_lag_template.block)
    previous_output = lead_lag_template.block.out_vars[0]

    for stage_index, stage_time_constant in enumerate(stage_time_constants, start=1):
        stage_template = build_typ_138__1_1_st_template(vf=vf, name=name + '_cascade_' + str(stage_index))
        stage_template.block.set_parameter_in_model('1/(1+sT)__T_' + name + '_cascade_' + str(stage_index), float(stage_time_constant))
        stage_template.block.connect([stage_template.block.in_vars[0]], [previous_output])
        root_block.merge_incoming_block(stage_template.block)
        previous_output = stage_template.block.out_vars[0]

    root_block.in_vars = list([lead_lag_template.block.in_vars[0]])
    root_block.out_vars = list([previous_output])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_lead_lag_chain_runtime_template(
        vf: VarFactory,
        tb_values: tuple[float, ...],
        ta_values: tuple[float, ...],
        name: str,
) -> EmtModelTemplate:
    """
    Build one sequential lead-lag chain from catalog primitives.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param tb_values: Ordered numerator time constants.
    :type tb_values: tuple[float, ...]
    :param ta_values: Ordered denominator time constants.
    :type ta_values: tuple[float, ...]
    :param name: Runtime template name.
    :type name: str
    :return: Materialized chained template.
    :rtype: EmtModelTemplate
    """
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()
    stage_index: int
    tb_value: float
    ta_value: float
    stage_template: EmtModelTemplate
    previous_output: Var | None = None
    first_input: Var | None = None

    for stage_index, tb_value in enumerate(tb_values, start=1):
        ta_value = ta_values[stage_index - 1]
        stage_template = build_typ_298__1_stb_1_sta_template(vf=vf, name=name + '_lead_lag_' + str(stage_index))
        stage_template.block.set_parameter_in_model('(1+sTb)/(1+sTa)__Tb_' + name + '_lead_lag_' + str(stage_index), float(tb_value))
        stage_template.block.set_parameter_in_model('(1+sTb)/(1+sTa)__Ta_' + name + '_lead_lag_' + str(stage_index), float(ta_value))

        if previous_output is None:
            first_input = stage_template.block.in_vars[0]
        else:
            stage_template.block.connect([stage_template.block.in_vars[0]], [previous_output])

        root_block.merge_incoming_block(stage_template.block)
        previous_output = stage_template.block.out_vars[0]

    if first_input is None or previous_output is None:
        pass
    else:
        root_block.in_vars = list([first_input])
        root_block.out_vars = list([previous_output])

    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_gain_then_lead_lag_runtime_template(
        vf: VarFactory,
        gain_value: float,
        tb_value: float,
        ta_value: float,
        name: str,
) -> EmtModelTemplate:
    """
    Build one `gain -> lead-lag` chain from catalog primitives.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param gain_value: Scalar input gain value.
    :type gain_value: float
    :param tb_value: Lead-lag numerator time constant.
    :type tb_value: float
    :param ta_value: Lead-lag denominator time constant.
    :type ta_value: float
    :param name: Runtime template name.
    :type name: str
    :return: Materialized chained template.
    :rtype: EmtModelTemplate
    """
    gain_template: EmtModelTemplate = build_scalar_gain_runtime_template(vf=vf, gain_value=gain_value, name=name + '_gain')
    lead_lag_template: EmtModelTemplate = build_typ_298__1_stb_1_sta_template(vf=vf, name=name + '_lead_lag')
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()

    lead_lag_template.block.set_parameter_in_model('(1+sTb)/(1+sTa)__Tb_' + name + '_lead_lag', float(tb_value))
    lead_lag_template.block.set_parameter_in_model('(1+sTb)/(1+sTa)__Ta_' + name + '_lead_lag', float(ta_value))
    lead_lag_template.block.connect([lead_lag_template.block.in_vars[0]], [gain_template.block.out_vars[0]])
    root_block.merge_incoming_block(gain_template.block)
    root_block.merge_incoming_block(lead_lag_template.block)
    root_block.in_vars = list([gain_template.block.in_vars[0]])
    root_block.out_vars = list([lead_lag_template.block.out_vars[0]])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_gain_then_washout_runtime_template(
        vf: VarFactory,
        gain_value: float,
        time_constant: float,
        name: str,
) -> EmtModelTemplate:
    """
    Build one `gain -> washout` chain from catalog primitives.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param gain_value: Scalar input gain value.
    :type gain_value: float
    :param time_constant: Washout time constant.
    :type time_constant: float
    :param name: Runtime template name.
    :type name: str
    :return: Materialized chained template.
    :rtype: EmtModelTemplate
    """
    gain_template: EmtModelTemplate = build_scalar_gain_runtime_template(vf=vf, gain_value=gain_value, name=name + '_gain')
    washout_template: EmtModelTemplate = build_typ_124__st_1_st_enable_template(vf=vf, name=name + '_washout')
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()

    washout_template.block.set_parameter_in_model('sT/(1+sT) _enable__T_' + name + '_washout', float(time_constant))
    washout_template.block.connect([washout_template.block.in_vars[0]], [gain_template.block.out_vars[0]])
    root_block.merge_incoming_block(gain_template.block)
    root_block.merge_incoming_block(washout_template.block)
    root_block.in_vars = list([gain_template.block.in_vars[0]])
    root_block.out_vars = list([washout_template.block.out_vars[0]])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_washout_then_first_order_runtime_template(
        vf: VarFactory,
        washout_time_constant: float,
        first_order_time_constant: float,
        name: str,
) -> EmtModelTemplate:
    """
    Build one `washout -> first-order` chain from catalog primitives.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param washout_time_constant: Washout time constant.
    :type washout_time_constant: float
    :param first_order_time_constant: First-order time constant.
    :type first_order_time_constant: float
    :param name: Runtime template name.
    :type name: str
    :return: Materialized chained template.
    :rtype: EmtModelTemplate
    """
    washout_template: EmtModelTemplate = build_typ_124__st_1_st_enable_template(vf=vf, name=name + '_washout')
    first_order_template: EmtModelTemplate = build_typ_138__1_1_st_template(vf=vf, name=name + '_first_order')
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()

    washout_template.block.set_parameter_in_model('sT/(1+sT) _enable__T_' + name + '_washout', float(washout_time_constant))
    first_order_template.block.set_parameter_in_model('1/(1+sT)__T_' + name + '_first_order', float(first_order_time_constant))
    first_order_template.block.connect([first_order_template.block.in_vars[0]], [washout_template.block.out_vars[0]])
    root_block.merge_incoming_block(washout_template.block)
    root_block.merge_incoming_block(first_order_template.block)
    root_block.in_vars = list([washout_template.block.in_vars[0]])
    root_block.out_vars = list([first_order_template.block.out_vars[0]])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_washout_chain_then_first_order_runtime_template(
        vf: VarFactory,
        washout_time_constants: tuple[float, ...],
        first_order_time_constant: float,
        name: str,
) -> EmtModelTemplate:
    """
    Build one `washout chain -> first-order` composite from catalog primitives.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param washout_time_constants: Ordered washout stage time constants.
    :type washout_time_constants: tuple[float, ...]
    :param first_order_time_constant: First-order time constant.
    :type first_order_time_constant: float
    :param name: Runtime template name.
    :type name: str
    :return: Materialized chained template.
    :rtype: EmtModelTemplate
    """
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()
    previous_output: Var | None = None
    first_input: Var | None = None
    stage_index: int
    washout_time_constant: float
    washout_template: EmtModelTemplate
    first_order_template: EmtModelTemplate

    for stage_index, washout_time_constant in enumerate(washout_time_constants, start=1):
        washout_template = build_typ_124__st_1_st_enable_template(vf=vf, name=name + '_washout_' + str(stage_index))
        washout_template.block.set_parameter_in_model('sT/(1+sT) _enable__T_' + name + '_washout_' + str(stage_index), float(washout_time_constant))

        if previous_output is None:
            first_input = washout_template.block.in_vars[0]
        else:
            washout_template.block.connect([washout_template.block.in_vars[0]], [previous_output])

        root_block.merge_incoming_block(washout_template.block)
        previous_output = washout_template.block.out_vars[0]

    first_order_template = build_typ_138__1_1_st_template(vf=vf, name=name + '_first_order')
    first_order_template.block.set_parameter_in_model('1/(1+sT)__T_' + name + '_first_order', float(first_order_time_constant))
    if previous_output is None:
        pass
    else:
        first_order_template.block.connect([first_order_template.block.in_vars[0]], [previous_output])
    root_block.merge_incoming_block(first_order_template.block)

    if first_input is None:
        pass
    else:
        root_block.in_vars = list([first_input])
        root_block.out_vars = list([first_order_template.block.out_vars[0]])

    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_pi_then_first_order_runtime_template(
        vf: VarFactory,
        kp_value: float,
        ti_value: float,
        kaw_value: float,
        y_max_value: float,
        y_min_value: float,
        first_order_time_constant: float,
        name: str,
) -> EmtModelTemplate:
    """
    Build one `PI -> first-order` composite from catalog primitives.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param kp_value: PI proportional gain.
    :type kp_value: float
    :param ti_value: PI integral time constant.
    :type ti_value: float
    :param kaw_value: PI anti-windup gain.
    :type kaw_value: float
    :param y_max_value: PI upper limit.
    :type y_max_value: float
    :param y_min_value: PI lower limit.
    :type y_min_value: float
    :param first_order_time_constant: Downstream first-order time constant.
    :type first_order_time_constant: float
    :param name: Runtime template name.
    :type name: str
    :return: Materialized chained template.
    :rtype: EmtModelTemplate
    """
    pi_template: EmtModelTemplate = build_limited_pi_antiwindup_runtime_template(
        vf=vf,
        kp_value=kp_value,
        ti_value=ti_value,
        kaw_value=kaw_value,
        y_max_value=y_max_value,
        y_min_value=y_min_value,
        name=name + '_pi',
    )
    first_order_template: EmtModelTemplate = build_typ_138__1_1_st_template(vf=vf, name=name + '_first_order')
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()

    first_order_template.block.set_parameter_in_model('1/(1+sT)__T_' + name + '_first_order', float(first_order_time_constant))
    first_order_template.block.connect([first_order_template.block.in_vars[0]], [pi_template.block.out_vars[0]])
    root_block.merge_incoming_block(pi_template.block)
    root_block.merge_incoming_block(first_order_template.block)
    root_block.in_vars = list([pi_template.block.in_vars[0]])
    root_block.out_vars = list([first_order_template.block.out_vars[0]])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_pi_hold_then_lead_lag_runtime_template(
        vf: VarFactory,
        kp_value: float,
        ti_value: float,
        tt_value: float,
        y_max_value: float,
        y_min_value: float,
        tb_value: float,
        ta_value: float,
        name: str,
) -> EmtModelTemplate:
    """
    Build one `PI_HOLD -> lead-lag` composite from catalog primitives.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param kp_value: Held-PI proportional gain.
    :type kp_value: float
    :param ti_value: Held-PI integral time constant.
    :type ti_value: float
    :param tt_value: Held-PI tracking time constant.
    :type tt_value: float
    :param y_max_value: Held-PI upper limit.
    :type y_max_value: float
    :param y_min_value: Held-PI lower limit.
    :type y_min_value: float
    :param tb_value: Lead-lag numerator time constant.
    :type tb_value: float
    :param ta_value: Lead-lag denominator time constant.
    :type ta_value: float
    :param name: Runtime template name.
    :type name: str
    :return: Materialized chained template.
    :rtype: EmtModelTemplate
    """
    pi_hold_template: EmtModelTemplate = build_limited_pi_antiwindup_hold_runtime_template(
        vf=vf,
        kp_value=kp_value,
        ti_value=ti_value,
        tt_value=tt_value,
        y_max_value=y_max_value,
        y_min_value=y_min_value,
        name=name + '_pi_hold',
    )
    lead_lag_template: EmtModelTemplate = build_typ_298__1_stb_1_sta_template(vf=vf, name=name + '_lead_lag')
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()

    lead_lag_template.block.set_parameter_in_model('(1+sTb)/(1+sTa)__Tb_' + name + '_lead_lag', float(tb_value))
    lead_lag_template.block.set_parameter_in_model('(1+sTb)/(1+sTa)__Ta_' + name + '_lead_lag', float(ta_value))
    lead_lag_template.block.connect([lead_lag_template.block.in_vars[0]], [pi_hold_template.block.out_vars[0]])
    root_block.merge_incoming_block(pi_hold_template.block)
    root_block.merge_incoming_block(lead_lag_template.block)
    root_block.in_vars = list([pi_hold_template.block.in_vars[0], pi_hold_template.block.in_vars[1]])
    root_block.out_vars = list([lead_lag_template.block.out_vars[0]])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_gain_then_washout_then_lead_lag_chain_runtime_template(
        vf: VarFactory,
        gain_value: float,
        washout_time_constant: float,
        tb_values: tuple[float, ...],
        ta_values: tuple[float, ...],
        name: str,
) -> EmtModelTemplate:
    """
    Build one `gain -> washout -> lead-lag chain` composite from catalog primitives.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param gain_value: Scalar input gain value.
    :type gain_value: float
    :param washout_time_constant: Washout time constant.
    :type washout_time_constant: float
    :param tb_values: Ordered lead-lag numerator time constants.
    :type tb_values: tuple[float, ...]
    :param ta_values: Ordered lead-lag denominator time constants.
    :type ta_values: tuple[float, ...]
    :param name: Runtime template name.
    :type name: str
    :return: Materialized chained template.
    :rtype: EmtModelTemplate
    """
    gain_washout_template: EmtModelTemplate = build_gain_then_washout_runtime_template(
        vf=vf,
        gain_value=gain_value,
        time_constant=washout_time_constant,
        name=name + '_gain_washout',
    )
    lead_lag_chain_template: EmtModelTemplate = build_lead_lag_chain_runtime_template(
        vf=vf,
        tb_values=tb_values,
        ta_values=ta_values,
        name=name + '_lead_lag_chain',
    )
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()

    lead_lag_chain_template.block.connect([lead_lag_chain_template.block.in_vars[0]], [gain_washout_template.block.out_vars[0]])
    root_block.merge_incoming_block(gain_washout_template.block)
    root_block.merge_incoming_block(lead_lag_chain_template.block)
    root_block.in_vars = list([gain_washout_template.block.in_vars[0]])
    root_block.out_vars = list([lead_lag_chain_template.block.out_vars[0]])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_first_order_then_gain_washout_lead_lag_chain_runtime_template(
        vf: VarFactory,
        first_order_time_constant: float,
        gain_value: float,
        washout_time_constant: float,
        tb_values: tuple[float, ...],
        ta_values: tuple[float, ...],
        name: str,
) -> EmtModelTemplate:
    """
    Build one `first-order -> gain -> washout -> lead-lag chain` composite.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param first_order_time_constant: Upstream first-order time constant.
    :type first_order_time_constant: float
    :param gain_value: Scalar gain value.
    :type gain_value: float
    :param washout_time_constant: Washout time constant.
    :type washout_time_constant: float
    :param tb_values: Ordered lead-lag numerator time constants.
    :type tb_values: tuple[float, ...]
    :param ta_values: Ordered lead-lag denominator time constants.
    :type ta_values: tuple[float, ...]
    :param name: Runtime template name.
    :type name: str
    :return: Materialized chained template.
    :rtype: EmtModelTemplate
    """
    first_order_template: EmtModelTemplate = build_typ_138__1_1_st_template(vf=vf, name=name + '_first_order')
    downstream_template: EmtModelTemplate = build_gain_then_washout_then_lead_lag_chain_runtime_template(
        vf=vf,
        gain_value=gain_value,
        washout_time_constant=washout_time_constant,
        tb_values=tb_values,
        ta_values=ta_values,
        name=name + '_downstream',
    )
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()

    first_order_template.block.set_parameter_in_model('1/(1+sT)__T_' + name + '_first_order', float(first_order_time_constant))
    downstream_template.block.connect([downstream_template.block.in_vars[0]], [first_order_template.block.out_vars[0]])
    root_block.merge_incoming_block(first_order_template.block)
    root_block.merge_incoming_block(downstream_template.block)
    root_block.in_vars = list([first_order_template.block.in_vars[0]])
    root_block.out_vars = list([downstream_template.block.out_vars[0]])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_limited_lead_lag_runtime_template(
        vf: VarFactory,
        gain_value: float,
        lead_time_constant: float,
        lag_time_constant: float,
        y_max_value: float,
        y_min_value: float,
        name: str,
) -> EmtModelTemplate:
    """
    Build one limited-lead-lag wrapper from catalog primitives plus one explicit subtractor.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param gain_value: Wrapper gain ``K``.
    :type gain_value: float
    :param lead_time_constant: Lead time constant ``t1``.
    :type lead_time_constant: float
    :param lag_time_constant: Lag time constant ``t2``.
    :type lag_time_constant: float
    :param y_max_value: Upper output limit.
    :type y_max_value: float
    :param y_min_value: Lower output limit.
    :type y_min_value: float
    :param name: Runtime template name.
    :type name: str
    :return: Materialized limited-lead-lag template.
    :rtype: EmtModelTemplate
    """
    first_order_template: EmtModelTemplate = build_typ_151__k_1_st_template(vf=vf, name=name + '_first_order')
    gain_template: EmtModelTemplate = build_scalar_gain_runtime_template(vf=vf, gain_value=gain_value, name=name + '_gain')
    limiter_template: EmtModelTemplate = build_typ_76__lim_const_template(vf=vf, name=name + '_limiter')
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()
    input_var: Var = vf.add_var('yi_' + name)
    feedback_var: Var = vf.add_var('feedback_' + name)
    denominator_value: float
    first_order_gain_value: float

    # Recover the internal first-order gain from the OpenModelica parameter identities.
    denominator_value = float(lead_time_constant) * float(gain_value)
    if math.isclose(denominator_value, 0.0, rel_tol=1.0e-9, abs_tol=1.0e-12):
        first_order_gain_value = 0.0
    else:
        first_order_gain_value = (float(lead_time_constant) - float(lag_time_constant)) / denominator_value

    first_order_template.block.set_parameter_in_model('K/(1+sT)__K_' + name + '_first_order', float(first_order_gain_value))
    first_order_template.block.set_parameter_in_model('K/(1+sT)__T_' + name + '_first_order', float(lead_time_constant))
    limiter_template.block.set_parameter_in_model('lim_const__y_max_' + name + '_limiter', float(y_max_value))
    limiter_template.block.set_parameter_in_model('lim_const__y_min_' + name + '_limiter', float(y_min_value))

    # Close the feedback loop y -> first-order -> subtract -> gain -> limiter -> y.
    first_order_template.block.connect([first_order_template.block.in_vars[0]], [limiter_template.block.out_vars[0]])
    root_block.merge_incoming_block(first_order_template.block)
    root_block.algebraic_vars.append(feedback_var)
    root_block.algebraic_eqs.append(feedback_var - (input_var - first_order_template.block.out_vars[0]))
    gain_template.block.connect([gain_template.block.in_vars[0]], [feedback_var])
    limiter_template.block.connect([limiter_template.block.in_vars[0]], [gain_template.block.out_vars[0]])
    root_block.merge_incoming_block(gain_template.block)
    root_block.merge_incoming_block(limiter_template.block)
    root_block.in_vars = list([input_var])
    root_block.out_vars = list([limiter_template.block.out_vars[0]])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_limited_first_order_runtime_template(
        vf: VarFactory,
        gk_value: float,
        g_value: float,
        integrator_gain_value: float,
        y_max_value: float,
        y_min_value: float,
        name: str,
) -> EmtModelTemplate:
    """
    Build one limited-first-order wrapper from catalog primitives plus explicit gating algebra.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param gk_value: Upstream input gain applied before feedback subtraction.
    :type gk_value: float
    :param g_value: Feedback gain applied before the limited integrator.
    :type g_value: float
    :param integrator_gain_value: Integrator gain.
    :type integrator_gain_value: float
    :param y_max_value: Upper output limit.
    :type y_max_value: float
    :param y_min_value: Lower output limit.
    :type y_min_value: float
    :param name: Runtime template name.
    :type name: str
    :return: Materialized limited-first-order template.
    :rtype: EmtModelTemplate
    """
    input_gain_template: EmtModelTemplate = build_scalar_gain_runtime_template(vf=vf, gain_value=gk_value, name=name + '_gk')
    feedback_gain_template: EmtModelTemplate = build_scalar_gain_runtime_template(vf=vf, gain_value=g_value, name=name + '_g')
    integrator_template: EmtModelTemplate = build_gain_then_integrator_runtime_template(vf=vf, gain_value=integrator_gain_value, name=name + '_integrator')
    limiter_template: EmtModelTemplate = build_typ_76__lim_const_template(vf=vf, name=name + '_limiter')
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()
    feedback_var: Var = vf.add_var('feedback_' + name)
    gated_input_var: Var = vf.add_var('gated_input_' + name)
    upper_block_expr: Expr
    lower_block_expr: Expr
    limiter_input_var: Var = integrator_template.block.out_vars[0]
    limited_output_var: Var = limiter_template.block.out_vars[0]
    feedback_drive_var: Var = feedback_gain_template.block.out_vars[0]

    limiter_template.block.set_parameter_in_model('lim_const__y_max_' + name + '_limiter', float(y_max_value))
    limiter_template.block.set_parameter_in_model('lim_const__y_min_' + name + '_limiter', float(y_min_value))

    limiter_template.block.connect([limiter_template.block.in_vars[0]], [limiter_input_var])

    # The limited-first-order wrapper subtracts the saturated output from the scaled input.
    root_block.algebraic_vars.append(feedback_var)
    root_block.algebraic_eqs.append(feedback_var - (input_gain_template.block.out_vars[0] - limited_output_var))

    # Apply the internal wiring before merging the child blocks so the merged
    # equations reference the connected variables rather than the original
    # standalone child inputs.
    feedback_gain_template.block.connect([feedback_gain_template.block.in_vars[0]], [feedback_var])

    # Freeze the integrator when the drive pushes further into an active saturation boundary.
    upper_block_expr = Comparison(lhs=feedback_drive_var, op=CmpOp.GT, rhs=0.0).to_expression() * Comparison(lhs=limiter_input_var, op=CmpOp.GE, rhs=Const(float(y_max_value))).to_expression()
    lower_block_expr = Comparison(lhs=feedback_drive_var, op=CmpOp.LT, rhs=0.0).to_expression() * Comparison(lhs=limiter_input_var, op=CmpOp.LE, rhs=Const(float(y_min_value))).to_expression()
    root_block.algebraic_vars.append(gated_input_var)
    root_block.algebraic_eqs.append(gated_input_var - ((Const(1.0) - upper_block_expr - lower_block_expr) * feedback_drive_var))
    integrator_template.block.connect([integrator_template.block.in_vars[0]], [gated_input_var])

    root_block.merge_incoming_block(input_gain_template.block)
    root_block.merge_incoming_block(feedback_gain_template.block)
    root_block.merge_incoming_block(integrator_template.block)
    root_block.merge_incoming_block(limiter_template.block)

    root_block.in_vars = list([input_gain_template.block.in_vars[0]])
    root_block.out_vars = list([limited_output_var])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_rate_limited_first_order_freeze_runtime_template(
        vf: VarFactory,
        gain_value: float,
        time_constant: float,
        dy_max_value: float,
        dy_min_value: float,
        name: str,
        include_freeze_input: bool,
) -> EmtModelTemplate:
    """
    Build one rate-limited first-order-with-freeze wrapper.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param gain_value: Input gain ``k``.
    :type gain_value: float
    :param time_constant: Wrapper time constant ``T``.
    :type time_constant: float
    :param dy_max_value: Upper derivative limit.
    :type dy_max_value: float
    :param dy_min_value: Lower derivative limit.
    :type dy_min_value: float
    :param name: Runtime template name.
    :type name: str
    :param include_freeze_input: Whether to expose one explicit freeze input.
    :type include_freeze_input: bool
    :return: Materialized wrapper.
    :rtype: EmtModelTemplate
    """
    gain_template: EmtModelTemplate = build_scalar_gain_runtime_template(vf=vf, gain_value=gain_value, name=name + '_gain')
    rate_limiter_template: EmtModelTemplate = build_typ_76__lim_const_template(vf=vf, name=name + '_rate_limit')
    integrator_template: EmtModelTemplate = build_typ_214__1_s_template(vf=vf, name=name + '_integrator')
    zero_template: EmtModelTemplate | None = None
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()
    feedback_error_var: Var = vf.add_var('feedback_error_' + name)
    scaled_rate_var: Var = vf.add_var('scaled_rate_' + name)
    gated_rate_var: Var = vf.add_var('gated_rate_' + name)
    freeze_var: Var
    freeze_expr: Expr

    rate_limiter_template.block.set_parameter_in_model('lim_const__y_max_' + name + '_rate_limit', float(dy_max_value))
    rate_limiter_template.block.set_parameter_in_model('lim_const__y_min_' + name + '_rate_limit', float(dy_min_value))

    if include_freeze_input:
        freeze_var = vf.add_var('freeze_' + name)
        freeze_expr = freeze_var
        root_block.in_vars = list([gain_template.block.in_vars[0], freeze_var])
    else:
        zero_template = _build_zero_output_runtime_template(vf=vf, name=name + '_freeze_zero')
        freeze_expr = zero_template.block.out_vars[0]
        root_block.in_vars = list([gain_template.block.in_vars[0]])

    # Compute the first-order drive `k*u - y`, scale by `1/T`, then clamp the derivative.
    root_block.algebraic_vars.append(feedback_error_var)
    root_block.algebraic_eqs.append(feedback_error_var - (gain_template.block.out_vars[0] - integrator_template.block.out_vars[0]))
    root_block.algebraic_vars.append(scaled_rate_var)
    root_block.algebraic_eqs.append(scaled_rate_var - (feedback_error_var / Const(float(time_constant))))
    rate_limiter_template.block.connect([rate_limiter_template.block.in_vars[0]], [scaled_rate_var])

    # Freeze the state derivative whenever the external freeze signal is active.
    root_block.algebraic_vars.append(gated_rate_var)
    root_block.algebraic_eqs.append(gated_rate_var - ((Const(1.0) - freeze_expr) * rate_limiter_template.block.out_vars[0]))
    integrator_template.block.connect([integrator_template.block.in_vars[0]], [gated_rate_var])

    root_block.merge_incoming_block(gain_template.block)
    root_block.merge_incoming_block(rate_limiter_template.block)
    root_block.merge_incoming_block(integrator_template.block)
    if zero_template is None:
        pass
    else:
        root_block.merge_incoming_block(zero_template.block)
    root_block.out_vars = list([integrator_template.block.out_vars[0]])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_limited_lead_lag_chain_runtime_template(
        vf: VarFactory,
        gain_values: tuple[float, ...],
        lead_time_constants: tuple[float, ...],
        lag_time_constants: tuple[float, ...],
        y_max_values: tuple[float, ...],
        y_min_values: tuple[float, ...],
        name: str,
) -> EmtModelTemplate:
    """
    Build one sequential limited-lead-lag chain from composite limited-lead-lag stages.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param gain_values: Ordered wrapper gains.
    :type gain_values: tuple[float, ...]
    :param lead_time_constants: Ordered lead time constants.
    :type lead_time_constants: tuple[float, ...]
    :param lag_time_constants: Ordered lag time constants.
    :type lag_time_constants: tuple[float, ...]
    :param y_max_values: Ordered upper output limits.
    :type y_max_values: tuple[float, ...]
    :param y_min_values: Ordered lower output limits.
    :type y_min_values: tuple[float, ...]
    :param name: Runtime template name.
    :type name: str
    :return: Materialized chained template.
    :rtype: EmtModelTemplate
    """
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()
    previous_output: Var | None = None
    first_input: Var | None = None
    stage_index: int
    gain_value: float
    stage_template: EmtModelTemplate

    for stage_index, gain_value in enumerate(gain_values, start=1):
        stage_template = build_limited_lead_lag_runtime_template(
            vf=vf,
            gain_value=float(gain_value),
            lead_time_constant=float(lead_time_constants[stage_index - 1]),
            lag_time_constant=float(lag_time_constants[stage_index - 1]),
            y_max_value=float(y_max_values[stage_index - 1]),
            y_min_value=float(y_min_values[stage_index - 1]),
            name=name + '_limited_lead_lag_' + str(stage_index),
        )

        if previous_output is None:
            first_input = stage_template.block.in_vars[0]
        else:
            stage_template.block.connect([stage_template.block.in_vars[0]], [previous_output])

        root_block.merge_incoming_block(stage_template.block)
        previous_output = stage_template.block.out_vars[0]

    if first_input is None or previous_output is None:
        pass
    else:
        root_block.in_vars = list([first_input])
        root_block.out_vars = list([previous_output])

    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_gain_then_lead_lag_chain_runtime_template(
        vf: VarFactory,
        gain_value: float,
        tb_values: tuple[float, ...],
        ta_values: tuple[float, ...],
        name: str,
) -> EmtModelTemplate:
    """
    Build one `gain -> lead-lag chain` composite from catalog primitives.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param gain_value: Scalar input gain value.
    :type gain_value: float
    :param tb_values: Ordered numerator time constants.
    :type tb_values: tuple[float, ...]
    :param ta_values: Ordered denominator time constants.
    :type ta_values: tuple[float, ...]
    :param name: Runtime template name.
    :type name: str
    :return: Materialized chained template.
    :rtype: EmtModelTemplate
    """
    gain_template: EmtModelTemplate = build_scalar_gain_runtime_template(vf=vf, gain_value=gain_value, name=name + '_gain')
    chain_template: EmtModelTemplate = build_lead_lag_chain_runtime_template(vf=vf, tb_values=tb_values, ta_values=ta_values, name=name + '_lead_lag_chain')
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()

    chain_template.block.connect([chain_template.block.in_vars[0]], [gain_template.block.out_vars[0]])
    root_block.merge_incoming_block(gain_template.block)
    root_block.merge_incoming_block(chain_template.block)
    root_block.in_vars = list([gain_template.block.in_vars[0]])
    root_block.out_vars = list([chain_template.block.out_vars[0]])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_gain_then_integrator_runtime_template(vf: VarFactory, gain_value: float, name: str) -> EmtModelTemplate:
    """
    Build one `gain -> integrator` chain from BasicBlockCatalog primitives.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param gain_value: Scalar gain value.
    :type gain_value: float
    :param name: Runtime template name.
    :type name: str
    :return: Materialized chained template.
    :rtype: EmtModelTemplate
    """
    gain_template: EmtModelTemplate = build_scalar_gain_runtime_template(vf=vf, gain_value=gain_value, name=name + '_gain')
    integrator_template: EmtModelTemplate = build_typ_214__1_s_template(vf=vf, name=name + '_integrator')
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()

    integrator_template.block.connect([integrator_template.block.in_vars[0]], [gain_template.block.out_vars[0]])
    root_block.merge_incoming_block(gain_template.block)
    root_block.merge_incoming_block(integrator_template.block)
    root_block.in_vars = list([gain_template.block.in_vars[0]])
    root_block.out_vars = list([integrator_template.block.out_vars[0]])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_gain_then_limiter_runtime_template(
        vf: VarFactory,
        gain_value: float,
        y_max_value: float,
        y_min_value: float,
        name: str,
) -> EmtModelTemplate:
    """
    Build one `gain -> limiter` chain from BasicBlockCatalog primitives.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param gain_value: Scalar gain value.
    :type gain_value: float
    :param y_max_value: Upper saturation limit.
    :type y_max_value: float
    :param y_min_value: Lower saturation limit.
    :type y_min_value: float
    :param name: Runtime template name.
    :type name: str
    :return: Materialized chained template.
    :rtype: EmtModelTemplate
    """
    gain_template: EmtModelTemplate = build_scalar_gain_runtime_template(vf=vf, gain_value=gain_value, name=name + '_gain')
    limiter_template: EmtModelTemplate = build_typ_76__lim_const_template(vf=vf, name=name + '_limiter')
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()

    limiter_template.block.set_parameter_in_model('lim_const__y_max_' + name + '_limiter', float(y_max_value))
    limiter_template.block.set_parameter_in_model('lim_const__y_min_' + name + '_limiter', float(y_min_value))
    limiter_template.block.connect([limiter_template.block.in_vars[0]], [gain_template.block.out_vars[0]])
    root_block.merge_incoming_block(gain_template.block)
    root_block.merge_incoming_block(limiter_template.block)
    root_block.in_vars = list([gain_template.block.in_vars[0]])
    root_block.out_vars = list([limiter_template.block.out_vars[0]])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_limited_pi_antiwindup_runtime_template(
        vf: VarFactory,
        kp_value: float,
        ti_value: float,
        kaw_value: float,
        y_max_value: float,
        y_min_value: float,
        name: str,
) -> EmtModelTemplate:
    """
    Build one limited PI-with-antiwindup block using the shipped catalog primitive.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param kp_value: Proportional gain.
    :type kp_value: float
    :param ti_value: Integral time constant.
    :type ti_value: float
    :param kaw_value: Anti-windup back-calculation gain.
    :type kaw_value: float
    :param y_max_value: Upper output limit.
    :type y_max_value: float
    :param y_min_value: Lower output limit.
    :type y_min_value: float
    :param name: Runtime template name.
    :type name: str
    :return: Materialized PI template.
    :rtype: EmtModelTemplate
    """
    pi_template: EmtModelTemplate = build_typ_452__kp_1_ti_s_s_s_rst_variant_template(vf=vf, name=name + '_pi')
    zero_template: EmtModelTemplate = _build_zero_output_runtime_template(vf=vf, name=name + '_zero')
    output_template: EmtModelTemplate = EmtModelTemplate()
    root_block: Block = Block(name=name)

    # Configure the catalog PI block with the recovered scalar parameters.
    pi_template.block.set_parameter_in_model('Kp(1/Ti+s)/s (s) _rst (variant)__Kp_' + name + '_pi', float(kp_value))
    pi_template.block.set_parameter_in_model('Kp(1/Ti+s)/s (s) _rst (variant)__Ti_' + name + '_pi', float(ti_value))
    pi_template.block.set_parameter_in_model('Kp(1/Ti+s)/s (s) _rst (variant)__Kaw_' + name + '_pi', float(kaw_value))
    pi_template.block.set_parameter_in_model('Kp(1/Ti+s)/s (s) _rst (variant)__y_max_' + name + '_pi', float(y_max_value))
    pi_template.block.set_parameter_in_model('Kp(1/Ti+s)/s (s) _rst (variant)__y_min_' + name + '_pi', float(y_min_value))

    # Tie the reset port to zero because the imported LimPID cases do not expose reset publicly.
    pi_template.block.connect([pi_template.block.in_vars[1]], [zero_template.block.out_vars[0]])
    root_block.merge_incoming_block(zero_template.block)
    root_block.merge_incoming_block(pi_template.block)
    root_block.in_vars = list([pi_template.block.in_vars[0]])
    root_block.out_vars = list([pi_template.block.out_vars[0]])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_limited_pi_antiwindup_hold_runtime_template(
        vf: VarFactory,
        kp_value: float,
        ti_value: float,
        tt_value: float,
        y_max_value: float,
        y_min_value: float,
        name: str,
) -> EmtModelTemplate:
    """
    Build one held PI-with-antiwindup chain with an external limiter feedback path.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param kp_value: Proportional gain.
    :type kp_value: float
    :param ti_value: Integral time constant.
    :type ti_value: float
    :param tt_value: Back-calculation tracking time constant.
    :type tt_value: float
    :param y_max_value: Upper output limit.
    :type y_max_value: float
    :param y_min_value: Lower output limit.
    :type y_min_value: float
    :param name: Runtime template name.
    :type name: str
    :return: Materialized PI-hold template.
    :rtype: EmtModelTemplate
    """
    pi_template: EmtModelTemplate = build_typ_465__kp_1_ti_s_s_s_rst_sig_hold_template(vf=vf, name=name + '_pi_hold')
    limiter_template: EmtModelTemplate = build_typ_76__lim_const_template(vf=vf, name=name + '_limiter')
    zero_template: EmtModelTemplate = _build_zero_output_runtime_template(vf=vf, name=name + '_zero')
    output_template: EmtModelTemplate = EmtModelTemplate()
    root_block: Block = Block(name=name)

    # Configure the PI-hold primitive with the recovered controller constants.
    pi_template.block.set_parameter_in_model('Kp(1/Ti+s)/s (s) _rst_sig_hold__Kp_' + name + '_pi_hold', float(kp_value))
    pi_template.block.set_parameter_in_model('Kp(1/Ti+s)/s (s) _rst_sig_hold__Ti_' + name + '_pi_hold', float(ti_value))
    pi_template.block.set_parameter_in_model('Kp(1/Ti+s)/s (s) _rst_sig_hold__Tt_' + name + '_pi_hold', float(tt_value))
    limiter_template.block.set_parameter_in_model('lim_const__y_max_' + name + '_limiter', float(y_max_value))
    limiter_template.block.set_parameter_in_model('lim_const__y_min_' + name + '_limiter', float(y_min_value))

    # Close the anti-windup loop through the limiter and ground the unused reset pins.
    pi_template.block.connect([pi_template.block.in_vars[2]], [zero_template.block.out_vars[0]])
    pi_template.block.connect([pi_template.block.in_vars[4]], [zero_template.block.out_vars[0]])
    limiter_template.block.connect([limiter_template.block.in_vars[0]], [pi_template.block.out_vars[0]])
    pi_template.block.connect([pi_template.block.in_vars[3]], [limiter_template.block.out_vars[0]])
    root_block.merge_incoming_block(zero_template.block)
    root_block.merge_incoming_block(pi_template.block)
    root_block.merge_incoming_block(limiter_template.block)
    root_block.in_vars = list([pi_template.block.in_vars[0], pi_template.block.in_vars[1]])
    root_block.out_vars = list([limiter_template.block.out_vars[0]])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_limited_pi_antiwindup_hold_variable_limit_runtime_template(
        vf: VarFactory,
        kp_value: float,
        ti_value: float,
        tt_value: float,
        name: str,
) -> EmtModelTemplate:
    """
    Build one held PI-with-antiwindup chain with variable limiter bounds.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param kp_value: Proportional gain.
    :type kp_value: float
    :param ti_value: Integral time constant.
    :type ti_value: float
    :param tt_value: Back-calculation tracking time constant.
    :type tt_value: float
    :param name: Runtime template name.
    :type name: str
    :return: Materialized PI-hold template.
    :rtype: EmtModelTemplate
    """
    pi_template: EmtModelTemplate = build_typ_465__kp_1_ti_s_s_s_rst_sig_hold_template(vf=vf, name=name + '_pi_hold')
    limiter_template: EmtModelTemplate = build_typ_75__lim_template(vf=vf, name=name + '_limiter_var')
    zero_template: EmtModelTemplate = _build_zero_output_runtime_template(vf=vf, name=name + '_zero')
    output_template: EmtModelTemplate = EmtModelTemplate()
    root_block: Block = Block(name=name)

    # Configure the held PI primitive with the recovered scalar controller constants.
    pi_template.block.set_parameter_in_model('Kp(1/Ti+s)/s (s) _rst_sig_hold__Kp_' + name + '_pi_hold', float(kp_value))
    pi_template.block.set_parameter_in_model('Kp(1/Ti+s)/s (s) _rst_sig_hold__Ti_' + name + '_pi_hold', float(ti_value))
    pi_template.block.set_parameter_in_model('Kp(1/Ti+s)/s (s) _rst_sig_hold__Tt_' + name + '_pi_hold', float(tt_value))

    # Close the anti-windup loop and expose the variable limiter bounds as public inputs.
    pi_template.block.connect([pi_template.block.in_vars[2]], [zero_template.block.out_vars[0]])
    pi_template.block.connect([pi_template.block.in_vars[4]], [zero_template.block.out_vars[0]])
    limiter_template.block.connect([limiter_template.block.in_vars[0]], [pi_template.block.out_vars[0]])
    pi_template.block.connect([pi_template.block.in_vars[3]], [limiter_template.block.out_vars[0]])
    root_block.merge_incoming_block(zero_template.block)
    root_block.merge_incoming_block(pi_template.block)
    root_block.merge_incoming_block(limiter_template.block)
    root_block.in_vars = list([
        pi_template.block.in_vars[0],
        pi_template.block.in_vars[1],
        limiter_template.block.in_vars[1],
        limiter_template.block.in_vars[2],
    ])
    root_block.out_vars = list([limiter_template.block.out_vars[0]])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template
