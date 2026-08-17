# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Maintainable international-standard module for 'pss1aPgen'.

This is the runtime implementation shipped by VeraGrid.
It exposes the imported public interface, explicit symbolic equations, and
recovered BasicBlockCatalog structures for incremental maintenance.
"""

from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic.block import Block
import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.Utils.Symbolic.symbolic import Expr
from VeraGridEngine.Utils.Symbolic.symbolic import Const
from VeraGridEngine.Utils.Symbolic.symbolic import BinOp
from VeraGridEngine.Templates.international_standards.runtime_helpers import build_first_order_then_gain_washout_lead_lag_chain_runtime_template

TEMPLATE_KEY: str = 'pss1apgen'
DISPLAY_NAME: str = 'pss1aPgen'
SOURCE_XML_NAME: str = 'pss1aPgen.xml'
WARNING_MESSAGES: tuple[str, ...] = ()
INPUT_NAMES: tuple[str, ...] = ()
OUTPUT_NAMES: tuple[str, ...] = ()

RECOVERED_RUNTIME_FAMILY_NAMES: tuple[str, ...] = ('first_order_gain_washout_lead_lag_chain')

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    """
    Materialize the international-standard EMT template.

    :param vf: Variable factory used to allocate the symbolic surface.
    :param name: Optional explicit runtime template name.
    :returns: Materialized EMT template.
    """
    template_name: str
    if name is None:
        template_name: str = 'pss1aPgen'
    else:
        template_name: str = name

    # Allocate the template container before building the symbolic surface.
    template: EmtModelTemplate = EmtModelTemplate()
    template.tpe = DeviceType.NoDevice
    template.name = template_name

    # Declare every variable explicitly before the equations reference it.
    # Declare the runtime parameter variables used by the template.
    pss_A1: Var = vf.add_var('pss.A1_' + template_name)
    pss_A2: Var = vf.add_var('pss.A2_' + template_name)
    pss_Ks: Var = vf.add_var('pss.Ks_' + template_name)
    pss_PGen0Pu: Var = vf.add_var('pss.PGen0Pu_' + template_name)
    pss_SNom: Var = vf.add_var('pss.SNom_' + template_name)
    pss_VPssMaxPu: Var = vf.add_var('pss.VPssMaxPu_' + template_name)
    pss_VPssMinPu: Var = vf.add_var('pss.VPssMinPu_' + template_name)
    pss_firstOrder_T: Var = vf.add_var('pss.firstOrder.T_' + template_name)
    pss_firstOrder_initType: Var = vf.add_var('pss.firstOrder.initType_' + template_name)
    pss_firstOrder_k: Var = vf.add_var('pss.firstOrder.k_' + template_name)
    pss_firstOrder_y_start: Var = vf.add_var('pss.firstOrder.y_start_' + template_name)
    pss_gain_k: Var = vf.add_var('pss.gain.k_' + template_name)
    pss_gain1_k: Var = vf.add_var('pss.gain1.k_' + template_name)
    pss_limiter_homotopyType: Var = vf.add_var('pss.limiter.homotopyType_' + template_name)
    pss_limiter_limitsAtInit: Var = vf.add_var('pss.limiter.limitsAtInit_' + template_name)
    pss_limiter_strict: Var = vf.add_var('pss.limiter.strict_' + template_name)
    pss_limiter_uMax: Var = vf.add_var('pss.limiter.uMax_' + template_name)
    pss_limiter_uMin: Var = vf.add_var('pss.limiter.uMin_' + template_name)
    pss_secondOrder_A1: Var = vf.add_var('pss.secondOrder.A1_' + template_name)
    pss_secondOrder_A2: Var = vf.add_var('pss.secondOrder.A2_' + template_name)
    pss_secondOrder_D: Var = vf.add_var('pss.secondOrder.D_' + template_name)
    pss_secondOrder_K: Var = vf.add_var('pss.secondOrder.K_' + template_name)
    pss_secondOrder_Y0: Var = vf.add_var('pss.secondOrder.Y0_' + template_name)
    pss_secondOrder_Yd0: Var = vf.add_var('pss.secondOrder.Yd0_' + template_name)
    pss_secondOrder_firstOrder_T: Var = vf.add_var('pss.secondOrder.firstOrder.T_' + template_name)
    pss_secondOrder_firstOrder_initType: Var = vf.add_var('pss.secondOrder.firstOrder.initType_' + template_name)
    pss_secondOrder_firstOrder_k: Var = vf.add_var('pss.secondOrder.firstOrder.k_' + template_name)
    pss_secondOrder_firstOrder_y_start: Var = vf.add_var('pss.secondOrder.firstOrder.y_start_' + template_name)
    pss_secondOrder_gain_k: Var = vf.add_var('pss.secondOrder.gain.k_' + template_name)
    pss_secondOrder_secondOrder_D: Var = vf.add_var('pss.secondOrder.secondOrder.D_' + template_name)
    pss_secondOrder_secondOrder_initType: Var = vf.add_var('pss.secondOrder.secondOrder.initType_' + template_name)
    pss_secondOrder_secondOrder_k: Var = vf.add_var('pss.secondOrder.secondOrder.k_' + template_name)
    pss_secondOrder_secondOrder_w: Var = vf.add_var('pss.secondOrder.secondOrder.w_' + template_name)
    pss_secondOrder_secondOrder_y_start: Var = vf.add_var('pss.secondOrder.secondOrder.y_start_' + template_name)
    pss_secondOrder_secondOrder_yd_start: Var = vf.add_var('pss.secondOrder.secondOrder.yd_start_' + template_name)
    pss_secondOrder_tFo: Var = vf.add_var('pss.secondOrder.tFo_' + template_name)
    pss_secondOrder_w: Var = vf.add_var('pss.secondOrder.w_' + template_name)
    pss_t1: Var = vf.add_var('pss.t1_' + template_name)
    pss_t2: Var = vf.add_var('pss.t2_' + template_name)
    pss_t3: Var = vf.add_var('pss.t3_' + template_name)
    pss_t4: Var = vf.add_var('pss.t4_' + template_name)
    pss_t5: Var = vf.add_var('pss.t5_' + template_name)
    pss_t6: Var = vf.add_var('pss.t6_' + template_name)
    pss_transferFunction_a_1: Var = vf.add_var('pss.transferFunction.a[1]_' + template_name)
    pss_transferFunction_a_2: Var = vf.add_var('pss.transferFunction.a[2]_' + template_name)
    pss_transferFunction_a_end: Var = vf.add_var('pss.transferFunction.a_end_' + template_name)
    pss_transferFunction_b_1: Var = vf.add_var('pss.transferFunction.b[1]_' + template_name)
    pss_transferFunction_b_2: Var = vf.add_var('pss.transferFunction.b[2]_' + template_name)
    pss_transferFunction_bb_1: Var = vf.add_var('pss.transferFunction.bb[1]_' + template_name)
    pss_transferFunction_bb_2: Var = vf.add_var('pss.transferFunction.bb[2]_' + template_name)
    pss_transferFunction_d: Var = vf.add_var('pss.transferFunction.d_' + template_name)
    pss_transferFunction_na: Var = vf.add_var('pss.transferFunction.na_' + template_name)
    pss_transferFunction_nb: Var = vf.add_var('pss.transferFunction.nb_' + template_name)
    pss_transferFunction_nx: Var = vf.add_var('pss.transferFunction.nx_' + template_name)
    pss_transferFunction_x_start_1: Var = vf.add_var('pss.transferFunction.x_start[1]_' + template_name)
    pss_transferFunction_y_start: Var = vf.add_var('pss.transferFunction.y_start_' + template_name)
    pss_transferFunction1_a_1: Var = vf.add_var('pss.transferFunction1.a[1]_' + template_name)
    pss_transferFunction1_a_2: Var = vf.add_var('pss.transferFunction1.a[2]_' + template_name)
    pss_transferFunction1_a_end: Var = vf.add_var('pss.transferFunction1.a_end_' + template_name)
    pss_transferFunction1_b_1: Var = vf.add_var('pss.transferFunction1.b[1]_' + template_name)
    pss_transferFunction1_b_2: Var = vf.add_var('pss.transferFunction1.b[2]_' + template_name)
    pss_transferFunction1_bb_1: Var = vf.add_var('pss.transferFunction1.bb[1]_' + template_name)
    pss_transferFunction1_bb_2: Var = vf.add_var('pss.transferFunction1.bb[2]_' + template_name)
    pss_transferFunction1_d: Var = vf.add_var('pss.transferFunction1.d_' + template_name)
    pss_transferFunction1_na: Var = vf.add_var('pss.transferFunction1.na_' + template_name)
    pss_transferFunction1_nb: Var = vf.add_var('pss.transferFunction1.nb_' + template_name)
    pss_transferFunction1_nx: Var = vf.add_var('pss.transferFunction1.nx_' + template_name)
    pss_transferFunction1_x_start_1: Var = vf.add_var('pss.transferFunction1.x_start[1]_' + template_name)
    pss_transferFunction1_y_start: Var = vf.add_var('pss.transferFunction1.y_start_' + template_name)
    pss_washout_U0: Var = vf.add_var('pss.washout.U0_' + template_name)
    pss_washout_derivative_T: Var = vf.add_var('pss.washout.derivative.T_' + template_name)
    pss_washout_derivative_initType: Var = vf.add_var('pss.washout.derivative.initType_' + template_name)
    pss_washout_derivative_k: Var = vf.add_var('pss.washout.derivative.k_' + template_name)
    pss_washout_derivative_x_start: Var = vf.add_var('pss.washout.derivative.x_start_' + template_name)
    pss_washout_derivative_y_start: Var = vf.add_var('pss.washout.derivative.y_start_' + template_name)
    pss_washout_derivative_zeroGain: Var = vf.add_var('pss.washout.derivative.zeroGain_' + template_name)
    pss_washout_tW: Var = vf.add_var('pss.washout.tW_' + template_name)
    # Declare the state variables used by the template.
    pss_firstOrder_y: Var = vf.add_var('pss.firstOrder.y_' + template_name)
    pss_secondOrder_firstOrder_y: Var = vf.add_var('pss.secondOrder.firstOrder.y_' + template_name)
    pss_secondOrder_secondOrder_y: Var = vf.add_var('pss.secondOrder.secondOrder.y_' + template_name)
    pss_secondOrder_secondOrder_yd: Var = vf.add_var('pss.secondOrder.secondOrder.yd_' + template_name)
    pss_transferFunction_x_scaled_1: Var = vf.add_var('pss.transferFunction.x_scaled[1]_' + template_name)
    pss_transferFunction1_x_scaled_1: Var = vf.add_var('pss.transferFunction1.x_scaled[1]_' + template_name)
    pss_washout_derivative_x: Var = vf.add_var('pss.washout.derivative.x_' + template_name)
    # Declare the algebraic/shared variables used by the template.
    pss_PGenPu: Var = vf.add_var('pss.PGenPu_' + template_name)
    pss_VPssPu: Var = vf.add_var('pss.VPssPu_' + template_name)
    pss_gain_y: Var = vf.add_var('pss.gain.y_' + template_name)
    pss_secondOrder_y: Var = vf.add_var('pss.secondOrder.y_' + template_name)
    pss_transferFunction_x_1: Var = vf.add_var('pss.transferFunction.x[1]_' + template_name)
    pss_transferFunction_y: Var = vf.add_var('pss.transferFunction.y_' + template_name)
    pss_transferFunction1_x_1: Var = vf.add_var('pss.transferFunction1.x[1]_' + template_name)
    pss_transferFunction1_y: Var = vf.add_var('pss.transferFunction1.y_' + template_name)
    pss_washout_y: Var = vf.add_var('pss.washout.y_' + template_name)
    # Declare the differential variables used by the template.
    d_pss_firstOrder_y: Var = vf.add_diff_var('d_pss.firstOrder.y_' + template_name, base_var=pss_firstOrder_y)
    d_pss_secondOrder_firstOrder_y: Var = vf.add_diff_var('d_pss.secondOrder.firstOrder.y_' + template_name, base_var=pss_secondOrder_firstOrder_y)
    d_pss_secondOrder_secondOrder_y: Var = vf.add_diff_var('d_pss.secondOrder.secondOrder.y_' + template_name, base_var=pss_secondOrder_secondOrder_y)
    d_pss_secondOrder_secondOrder_yd: Var = vf.add_diff_var('d_pss.secondOrder.secondOrder.yd_' + template_name, base_var=pss_secondOrder_secondOrder_yd)
    d_pss_transferFunction_x_scaled_1: Var = vf.add_diff_var('d_pss.transferFunction.x_scaled[1]_' + template_name, base_var=pss_transferFunction_x_scaled_1)
    d_pss_transferFunction1_x_scaled_1: Var = vf.add_diff_var('d_pss.transferFunction1.x_scaled[1]_' + template_name, base_var=pss_transferFunction1_x_scaled_1)
    d_pss_washout_derivative_x: Var = vf.add_diff_var('d_pss.washout.derivative.x_' + template_name, base_var=pss_washout_derivative_x)

    # Build explicit typed collections so the symbolic surface is easy to inspect.
    state_equations: list[Expr] = list()
    state_equations.append(pss_secondOrder_secondOrder_yd)
    state_equations.append((((pss_transferFunction_a_end * pss_transferFunction1_y) - (pss_transferFunction_a_2 * pss_transferFunction_x_scaled_1)) / pss_transferFunction_a_1))
    state_equations.append((((pss_transferFunction1_a_end * pss_secondOrder_y) - (pss_transferFunction1_a_2 * pss_transferFunction1_x_scaled_1)) / pss_transferFunction1_a_1))
    state_equations.append((sym.Const(99999.99999999999) * ((pss_secondOrder_firstOrder_k * pss_washout_y) - pss_secondOrder_firstOrder_y)))
    state_equations.append(((pss_secondOrder_secondOrder_k * pss_washout_y) - pss_secondOrder_secondOrder_y))
    state_equations.append(((pss_washout_derivative_zeroGain * sym.Const(0.0)) + ((sym.Const(1.0) - pss_washout_derivative_zeroGain) * ((pss_gain_y - pss_washout_derivative_x) / pss_washout_derivative_T))))
    state_equations.append(((((pss_firstOrder_k * pss_gain1_k) * pss_PGenPu) - pss_firstOrder_y) / pss_firstOrder_T))
    state_variables: list[Var] = list()
    state_variables.append(pss_secondOrder_secondOrder_y)
    state_variables.append(pss_transferFunction_x_scaled_1)
    state_variables.append(pss_transferFunction1_x_scaled_1)
    state_variables.append(pss_secondOrder_firstOrder_y)
    state_variables.append(pss_secondOrder_secondOrder_yd)
    state_variables.append(pss_washout_derivative_x)
    state_variables.append(pss_firstOrder_y)
    algebraic_equations: list[Expr] = list()
    algebraic_equations.append((pss_transferFunction_x_1 - (pss_transferFunction_x_scaled_1 / pss_transferFunction_a_end)))
    algebraic_equations.append((pss_transferFunction1_x_1 - (pss_transferFunction1_x_scaled_1 / pss_transferFunction1_a_end)))
    algebraic_equations.append((pss_gain_y - (pss_gain_k * pss_firstOrder_y)))
    algebraic_equations.append((pss_washout_y - ((pss_washout_derivative_zeroGain * sym.Const(0.0)) + ((sym.Const(1.0) - pss_washout_derivative_zeroGain) * ((pss_washout_derivative_k / pss_washout_derivative_T) * (pss_gain_y - pss_washout_derivative_x))))))
    algebraic_equations.append((pss_secondOrder_y - (pss_secondOrder_gain_k * pss_washout_y)))
    algebraic_equations.append((pss_transferFunction1_y - (((pss_transferFunction1_bb_2 - (pss_transferFunction1_d * pss_transferFunction1_a_2)) * pss_transferFunction1_x_1) + (pss_transferFunction1_d * pss_secondOrder_y))))
    algebraic_equations.append((pss_transferFunction_y - (((pss_transferFunction_bb_2 - (pss_transferFunction_d * pss_transferFunction_a_2)) * pss_transferFunction_x_1) + (pss_transferFunction_d * pss_transferFunction1_y))))
    algebraic_equations.append((pss_VPssPu - ((sym.heaviside(((pss_transferFunction_y - pss_limiter_uMax) - sym.Const(1e-06))) * pss_limiter_uMax) + ((sym.Const(1.0) - sym.heaviside(((pss_transferFunction_y - pss_limiter_uMax) - sym.Const(1e-06)))) * ((sym.heaviside(((pss_limiter_uMin - pss_transferFunction_y) - sym.Const(1e-06))) * pss_limiter_uMin) + ((sym.Const(1.0) - sym.heaviside(((pss_limiter_uMin - pss_transferFunction_y) - sym.Const(1e-06)))) * pss_transferFunction_y))))))
    algebraic_variables: list[Var] = list()
    algebraic_variables.append(pss_transferFunction_x_1)
    algebraic_variables.append(pss_transferFunction1_x_1)
    algebraic_variables.append(pss_gain_y)
    algebraic_variables.append(pss_washout_y)
    algebraic_variables.append(pss_secondOrder_y)
    algebraic_variables.append(pss_transferFunction1_y)
    algebraic_variables.append(pss_transferFunction_y)
    algebraic_variables.append(pss_VPssPu)
    algebraic_variables.append(pss_PGenPu)
    differential_variables: list[Var] = list()
    differential_variables.append(d_pss_secondOrder_secondOrder_y)
    differential_variables.append(d_pss_transferFunction_x_scaled_1)
    differential_variables.append(d_pss_transferFunction1_x_scaled_1)
    differential_variables.append(d_pss_secondOrder_firstOrder_y)
    differential_variables.append(d_pss_secondOrder_secondOrder_yd)
    differential_variables.append(d_pss_washout_derivative_x)
    differential_variables.append(d_pss_firstOrder_y)
    input_variables: list[Var] = list()
    input_variables.append(pss_PGenPu)
    output_variables: list[Var] = list()
    output_variables.append(pss_VPssPu)
    event_parameters: dict[Var, Expr | Const] = dict()
    event_parameters[pss_A1] = vf.add_const(0.0, name='')
    event_parameters[pss_A2] = vf.add_const(0.0, name='')
    event_parameters[pss_Ks] = vf.add_const(10.0, name='')
    event_parameters[pss_PGen0Pu] = vf.add_const(0.8, name='')
    event_parameters[pss_SNom] = vf.add_const(100.0, name='')
    event_parameters[pss_VPssMaxPu] = vf.add_const(0.1, name='')
    event_parameters[pss_VPssMinPu] = vf.add_const(-0.1, name='')
    event_parameters[pss_firstOrder_T] = pss_t6
    event_parameters[pss_firstOrder_k] = vf.add_const(1.0, name='')
    event_parameters[pss_firstOrder_y_start] = (sym.Const(100.0) * (pss_PGen0Pu / pss_SNom))
    event_parameters[pss_gain_k] = pss_Ks
    event_parameters[pss_gain1_k] = (sym.Const(100.0) / pss_SNom)
    event_parameters[pss_limiter_uMax] = pss_VPssMaxPu
    event_parameters[pss_limiter_uMin] = pss_VPssMinPu
    event_parameters[pss_secondOrder_A1] = vf.add_const(0.0, name='')
    event_parameters[pss_secondOrder_A2] = vf.add_const(0.0, name='')
    event_parameters[pss_secondOrder_D] = vf.add_const(0.0, name='')
    event_parameters[pss_secondOrder_K] = vf.add_const(1.0, name='')
    event_parameters[pss_secondOrder_Y0] = vf.add_const(0.0, name='')
    event_parameters[pss_secondOrder_Yd0] = vf.add_const(0.0, name='')
    event_parameters[pss_secondOrder_firstOrder_T] = vf.add_const(1e-05, name='')
    event_parameters[pss_secondOrder_firstOrder_k] = pss_secondOrder_K
    event_parameters[pss_secondOrder_firstOrder_y_start] = pss_secondOrder_Y0
    event_parameters[pss_secondOrder_gain_k] = pss_secondOrder_K
    event_parameters[pss_secondOrder_secondOrder_D] = vf.add_const(0.0, name='')
    event_parameters[pss_secondOrder_secondOrder_k] = pss_secondOrder_K
    event_parameters[pss_secondOrder_secondOrder_w] = vf.add_const(1.0, name='')
    event_parameters[pss_secondOrder_secondOrder_y_start] = pss_secondOrder_Y0
    event_parameters[pss_secondOrder_secondOrder_yd_start] = pss_secondOrder_Yd0
    event_parameters[pss_secondOrder_tFo] = vf.add_const(1e-05, name='')
    event_parameters[pss_secondOrder_w] = vf.add_const(1.0, name='')
    event_parameters[pss_t1] = vf.add_const(0.1, name='')
    event_parameters[pss_t2] = vf.add_const(0.05, name='')
    event_parameters[pss_t3] = vf.add_const(0.1, name='')
    event_parameters[pss_t4] = vf.add_const(0.05, name='')
    event_parameters[pss_t5] = vf.add_const(10.0, name='')
    event_parameters[pss_t6] = vf.add_const(0.02, name='')
    event_parameters[pss_transferFunction_a_1] = pss_t4
    event_parameters[pss_transferFunction_a_2] = vf.add_const(1.0, name='')
    event_parameters[pss_transferFunction_a_end] = ((sym.heaviside(((pss_transferFunction_a_2 - (sym.Const(2.220446049250313e-14) * sym.sqrt(((pss_transferFunction_a_1 ** sym.Const(2.0)) + (pss_transferFunction_a_2 ** sym.Const(2.0)))))) - sym.Const(1e-06))) * pss_transferFunction_a_2) + ((sym.Const(1.0) - sym.heaviside(((pss_transferFunction_a_2 - (sym.Const(2.220446049250313e-14) * sym.sqrt(((pss_transferFunction_a_1 ** sym.Const(2.0)) + (pss_transferFunction_a_2 ** sym.Const(2.0)))))) - sym.Const(1e-06)))) * sym.Const(1.0)))
    event_parameters[pss_transferFunction_b_1] = pss_t3
    event_parameters[pss_transferFunction_b_2] = vf.add_const(1.0, name='')
    event_parameters[pss_transferFunction_bb_1] = pss_transferFunction_b_1
    event_parameters[pss_transferFunction_bb_2] = pss_transferFunction_b_2
    event_parameters[pss_transferFunction_d] = (pss_transferFunction_bb_1 / pss_transferFunction_a_1)
    event_parameters[pss_transferFunction_x_start_1] = vf.add_const(0.0, name='')
    event_parameters[pss_transferFunction_y_start] = vf.add_const(0.0, name='')
    event_parameters[pss_transferFunction1_a_1] = pss_t2
    event_parameters[pss_transferFunction1_a_2] = vf.add_const(1.0, name='')
    event_parameters[pss_transferFunction1_a_end] = ((sym.heaviside(((pss_transferFunction1_a_2 - (sym.Const(2.220446049250313e-14) * sym.sqrt(((pss_transferFunction1_a_1 ** sym.Const(2.0)) + (pss_transferFunction1_a_2 ** sym.Const(2.0)))))) - sym.Const(1e-06))) * pss_transferFunction1_a_2) + ((sym.Const(1.0) - sym.heaviside(((pss_transferFunction1_a_2 - (sym.Const(2.220446049250313e-14) * sym.sqrt(((pss_transferFunction1_a_1 ** sym.Const(2.0)) + (pss_transferFunction1_a_2 ** sym.Const(2.0)))))) - sym.Const(1e-06)))) * sym.Const(1.0)))
    event_parameters[pss_transferFunction1_b_1] = pss_t1
    event_parameters[pss_transferFunction1_b_2] = vf.add_const(1.0, name='')
    event_parameters[pss_transferFunction1_bb_1] = pss_transferFunction1_b_1
    event_parameters[pss_transferFunction1_bb_2] = pss_transferFunction1_b_2
    event_parameters[pss_transferFunction1_d] = (pss_transferFunction1_bb_1 / pss_transferFunction1_a_1)
    event_parameters[pss_transferFunction1_x_start_1] = vf.add_const(0.0, name='')
    event_parameters[pss_transferFunction1_y_start] = vf.add_const(0.0, name='')
    event_parameters[pss_washout_U0] = (sym.Const(100.0) * (pss_Ks * (pss_PGen0Pu / pss_SNom)))
    event_parameters[pss_washout_derivative_T] = vf.add_const(10.0, name='')
    event_parameters[pss_washout_derivative_k] = vf.add_const(10.0, name='')
    event_parameters[pss_washout_derivative_x_start] = pss_washout_U0
    event_parameters[pss_washout_derivative_y_start] = vf.add_const(0.0, name='')
    event_parameters[pss_washout_tW] = vf.add_const(10.0, name='')
    event_parameters[pss_firstOrder_initType] = vf.add_const(1.0, name='')
    event_parameters[pss_limiter_homotopyType] = vf.add_const(1.0, name='')
    event_parameters[pss_secondOrder_firstOrder_initType] = vf.add_const(1.0, name='')
    event_parameters[pss_secondOrder_secondOrder_initType] = vf.add_const(1.0, name='')
    event_parameters[pss_transferFunction_na] = vf.add_const(2.0, name='')
    event_parameters[pss_transferFunction_nb] = vf.add_const(2.0, name='')
    event_parameters[pss_transferFunction_nx] = vf.add_const(1.0, name='')
    event_parameters[pss_transferFunction1_na] = vf.add_const(2.0, name='')
    event_parameters[pss_transferFunction1_nb] = vf.add_const(2.0, name='')
    event_parameters[pss_transferFunction1_nx] = vf.add_const(1.0, name='')
    event_parameters[pss_washout_derivative_initType] = vf.add_const(1.0, name='')
    event_parameters[pss_limiter_limitsAtInit] = vf.add_const(1.0, name='')
    event_parameters[pss_limiter_strict] = vf.add_const(0.0, name='')
    event_parameters[pss_washout_derivative_zeroGain] = sym.heaviside(((sym.Const(2.220446049250313e-16) - sym.abs(pss_washout_derivative_k)) - sym.Const(1e-06)))
    mode_parameters: dict[Var, Expr | Const] = dict()
    initial_equations: dict[Var, Expr | Const] = dict()
    initial_equations[pss_secondOrder_secondOrder_y] = pss_secondOrder_Y0
    initial_equations[pss_transferFunction_x_scaled_1] = (pss_transferFunction_a_end * pss_transferFunction_x_start_1)
    initial_equations[pss_transferFunction1_x_scaled_1] = (pss_transferFunction1_a_end * pss_transferFunction1_x_start_1)
    initial_equations[pss_secondOrder_firstOrder_y] = pss_secondOrder_firstOrder_y_start
    initial_equations[pss_secondOrder_secondOrder_yd] = pss_secondOrder_Yd0
    initial_equations[pss_washout_derivative_x] = (pss_gain_k * ((pss_firstOrder_k * pss_gain1_k) * pss_PGenPu))
    initial_equations[pss_firstOrder_y] = ((pss_firstOrder_k * pss_gain1_k) * pss_PGenPu)
    initial_equations[pss_VPssPu] = vf.add_const(0.0, name='')
    initial_equations[pss_gain_y] = (pss_gain_k * ((pss_firstOrder_k * pss_gain1_k) * pss_PGenPu))
    initial_equations[pss_secondOrder_y] = pss_secondOrder_Y0
    initial_equations[pss_transferFunction_x_1] = pss_transferFunction_x_start_1
    initial_equations[pss_transferFunction_y] = pss_transferFunction_y_start
    initial_equations[pss_transferFunction1_x_1] = pss_transferFunction1_x_start_1
    initial_equations[pss_transferFunction1_y] = pss_transferFunction1_y_start
    initial_equations[pss_washout_y] = vf.add_const(0.0, name='')
    initial_equations[pss_PGenPu] = vf.add_const(1.0, name='')
    differential_initial_equations: dict[Var, Expr | Const] = dict()
    procedural_logic_entries: list[object] = list()

    # Assemble the final block from the explicit typed collections above.
    template.block = Block(
        state_vars=state_variables,
        state_eqs=state_equations,
        algebraic_vars=algebraic_variables,
        algebraic_eqs=algebraic_equations,
        diff_vars=differential_variables,
        init_eqs=initial_equations,
        diff_init_eqs=differential_initial_equations,
        in_vars=input_variables,
        out_vars=output_variables,
        event_dict=event_parameters,
        mode_dict=mode_parameters,
        procedural_logic=procedural_logic_entries,
        name=template_name,
    )

    return template

def build_recovered_runtime_templates(vf: VarFactory, name_prefix: str | None = None) -> tuple[EmtModelTemplate, ...]:
    """
    Materialize the recovered native-block companions in one ordered list.

    This is the human entry point that most closely resembles an explicit
    EMT/RMS controller composition: each non-empty recovered family is
    instantiated in module order and appended into one tuple.

    :param vf: Variable factory used to allocate the symbolic variables.
    :type vf: VarFactory
    :param name_prefix: Optional prefix for the recovered companion templates.
    :type name_prefix: str | None
    :return: Materialized result produced by this builder.
    :rtype: tuple[EmtModelTemplate, ...]
"""
    templates: list[EmtModelTemplate] = list()
    templates.extend(build_first_order_gain_washout_lead_lag_chain_runtime_templates(vf=vf, name_prefix=name_prefix))
    return tuple(templates)

def build_first_order_gain_washout_lead_lag_chain_runtime_templates(vf: VarFactory, name_prefix: str | None = None) -> tuple[EmtModelTemplate, ...]:
    """
    Materialize directly mappable first-order-gain-washout-lead-lag-chain composites.

    :param vf: Variable factory used to allocate the symbolic variables.
    :type vf: VarFactory
    :param name_prefix: Optional prefix for the recovered companion templates.
    :type name_prefix: str | None
    :return: Materialized result produced by this builder.
    :rtype: tuple[EmtModelTemplate, ...]
"""
    template_prefix: str
    templates: list[EmtModelTemplate] = list()
    spec_index: int = 0
    first_order_symbol_name: str
    gain_symbol_name: str
    washout_symbol_name: str
    stage_symbol_names: tuple[str, ...]
    input_name: str
    first_order_t_name: str | None
    first_order_t_value: float | None
    gain_name: str | None
    gain_value: float | None
    washout_t_name: str | None
    washout_t_value: float | None
    tb_names: tuple[str, ...]
    tb_values: tuple[float, ...]
    ta_names: tuple[str, ...]
    ta_values: tuple[float, ...]

    if name_prefix is None:
        template_prefix = TEMPLATE_KEY
    else:
        template_prefix = name_prefix

    for first_order_symbol_name, gain_symbol_name, washout_symbol_name, stage_symbol_names, input_name, first_order_t_name, first_order_t_value, gain_name, gain_value, washout_t_name, washout_t_value, tb_names, tb_values, ta_names, ta_values in FIRST_ORDER_GAIN_WASHOUT_LEAD_LAG_CHAIN_SPECS:
        if first_order_t_value is None or gain_value is None or washout_t_value is None or len(tb_values) == 0 or len(tb_values) != len(ta_values):
            pass
        else:
            template_name: str = f'{template_prefix}_first_order_gain_washout_lead_lag_chain_{spec_index + 1}'
            template_obj: EmtModelTemplate = build_first_order_then_gain_washout_lead_lag_chain_runtime_template(vf=vf, first_order_time_constant=float(first_order_t_value), gain_value=float(gain_value), washout_time_constant=float(washout_t_value), tb_values=tuple(tb_values), ta_values=tuple(ta_values), name=template_name)
            templates.append(template_obj)
        spec_index += 1

    return tuple(templates)

# Recovered spec payloads kept for regeneration and inspection

FIRST_ORDER_GAIN_WASHOUT_LEAD_LAG_CHAIN_SPECS: tuple[tuple[str, str, str, tuple[str, ...], str, str | None, float | None, str | None, float | None, str | None, float | None, tuple[str, ...], tuple[float, ...], tuple[str, ...], tuple[float, ...]], ...] = (
    ('pss.firstOrder.y', 'pss.gain.y', 'pss.washout.y', ('pss.transferFunction1.y', 'pss.transferFunction.y'), 'pss.transferFunction.y', 'pss.firstOrder.T', 0.02, 'pss.gain.k', 10.0, 'pss.washout.derivative.T', 10.0, ('pss.transferFunction1.b[1]', 'pss.transferFunction.b[1]'), (0.1, 0.1), ('pss.transferFunction1.a[1]', 'pss.transferFunction.a[1]'), (0.05, 0.05)),
)
