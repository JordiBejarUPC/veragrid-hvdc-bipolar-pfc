# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Maintainable international-standard module for 'TGov3'.

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
from VeraGridEngine.Templates.BasicBlockCatalog.lookup_array_runtime_templates import build_lookup_array_linear_runtime_template
from VeraGridEngine.Templates.BasicBlockCatalog.lookup_array_runtime_templates import build_lookup_array_spline_runtime_template
from VeraGridEngine.Templates.BasicBlockCatalog.Functions.typ_138__1_1_st import build_typ_138__1_1_st_template
from VeraGridEngine.Templates.BasicBlockCatalog.Functions.typ_214__1_s import build_typ_214__1_s_template
from VeraGridEngine.Templates.international_standards.runtime_helpers import build_gain_then_first_order_runtime_template
from VeraGridEngine.Templates.international_standards.runtime_helpers import build_gain_then_integrator_runtime_template
from VeraGridEngine.Templates.international_standards.runtime_helpers import build_scalar_gain_runtime_template
from VeraGridEngine.Templates.BasicBlockCatalog.Functions.typ_298__1_stb_1_sta import build_typ_298__1_stb_1_sta_template
from VeraGridEngine.Templates.BasicBlockCatalog.Functions.typ_76__lim_const import build_typ_76__lim_const_template
from VeraGridEngine.Templates.international_standards.runtime_helpers import build_gain_then_limiter_runtime_template

TEMPLATE_KEY: str = 'tgov3'
DISPLAY_NAME: str = 'TGov3'
SOURCE_XML_NAME: str = 'TGov3.xml'
WARNING_MESSAGES: tuple[str, ...] = ('Skipped 1 when-equation blocks during conversion', 'Applied canonical public TGov3 valve flow curve assuming unit linear valve characteristic')
INPUT_NAMES: tuple[str, ...] = ()
OUTPUT_NAMES: tuple[str, ...] = ()

RECOVERED_RUNTIME_FAMILY_NAMES: tuple[str, ...] = ('lookup_table', 'first_order', 'lead_lag', 'gain', 'limiter')

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    """
    Materialize the international-standard EMT template.

    :param vf: Variable factory used to allocate the symbolic surface.
    :param name: Optional explicit runtime template name.
    :returns: Materialized EMT template.
    """
    template_name: str
    if name is None:
        template_name: str = 'TGov3'
    else:
        template_name: str = name

    # Allocate the template container before building the symbolic surface.
    template: EmtModelTemplate = EmtModelTemplate()
    template.tpe = DeviceType.NoDevice
    template.name = template_name

    # Declare every variable explicitly before the equations reference it.
    # Declare the runtime parameter variables used by the template.
    gov_FValveTableName: Var = vf.add_var('gov.FValveTableName_' + template_name)
    gov_K: Var = vf.add_var('gov.K_' + template_name)
    gov_K1: Var = vf.add_var('gov.K1_' + template_name)
    gov_K2: Var = vf.add_var('gov.K2_' + template_name)
    gov_K3: Var = vf.add_var('gov.K3_' + template_name)
    gov_PMaxPu: Var = vf.add_var('gov.PMaxPu_' + template_name)
    gov_PMinPu: Var = vf.add_var('gov.PMinPu_' + template_name)
    gov_Pm0Pu: Var = vf.add_var('gov.Pm0Pu_' + template_name)
    gov_Pr0Pu: Var = vf.add_var('gov.Pr0Pu_' + template_name)
    gov_PrMaxPu: Var = vf.add_var('gov.PrMaxPu_' + template_name)
    gov_TablesFile: Var = vf.add_var('gov.TablesFile_' + template_name)
    gov_Uc: Var = vf.add_var('gov.Uc_' + template_name)
    gov_Uo: Var = vf.add_var('gov.Uo_' + template_name)
    gov_add_k1: Var = vf.add_var('gov.add.k1_' + template_name)
    gov_add_k2: Var = vf.add_var('gov.add.k2_' + template_name)
    gov_add1_k1: Var = vf.add_var('gov.add1.k1_' + template_name)
    gov_add1_k2: Var = vf.add_var('gov.add1.k2_' + template_name)
    gov_add3_k1: Var = vf.add_var('gov.add3.k1_' + template_name)
    gov_add3_k2: Var = vf.add_var('gov.add3.k2_' + template_name)
    gov_add3_k3: Var = vf.add_var('gov.add3.k3_' + template_name)
    gov_combiTable1Ds_columns_1: Var = vf.add_var('gov.combiTable1Ds.columns[1]_' + template_name)
    gov_combiTable1Ds_extrapolation: Var = vf.add_var('gov.combiTable1Ds.extrapolation_' + template_name)
    gov_combiTable1Ds_fileName: Var = vf.add_var('gov.combiTable1Ds.fileName_' + template_name)
    gov_combiTable1Ds_nout: Var = vf.add_var('gov.combiTable1Ds.nout_' + template_name)
    gov_combiTable1Ds_smoothness: Var = vf.add_var('gov.combiTable1Ds.smoothness_' + template_name)
    gov_combiTable1Ds_tableID: Var = vf.add_var('gov.combiTable1Ds.tableID_' + template_name)
    gov_combiTable1Ds_tableName: Var = vf.add_var('gov.combiTable1Ds.tableName_' + template_name)
    gov_combiTable1Ds_tableOnFile: Var = vf.add_var('gov.combiTable1Ds.tableOnFile_' + template_name)
    gov_combiTable1Ds_u_max: Var = vf.add_var('gov.combiTable1Ds.u_max_' + template_name)
    gov_combiTable1Ds_u_min: Var = vf.add_var('gov.combiTable1Ds.u_min_' + template_name)
    gov_combiTable1Ds_verboseExtrapolation: Var = vf.add_var('gov.combiTable1Ds.verboseExtrapolation_' + template_name)
    gov_combiTable1Ds_verboseRead: Var = vf.add_var('gov.combiTable1Ds.verboseRead_' + template_name)
    gov_combiTable1Ds1_columns_1: Var = vf.add_var('gov.combiTable1Ds1.columns[1]_' + template_name)
    gov_combiTable1Ds1_extrapolation: Var = vf.add_var('gov.combiTable1Ds1.extrapolation_' + template_name)
    gov_combiTable1Ds1_fileName: Var = vf.add_var('gov.combiTable1Ds1.fileName_' + template_name)
    gov_combiTable1Ds1_nout: Var = vf.add_var('gov.combiTable1Ds1.nout_' + template_name)
    gov_combiTable1Ds1_smoothness: Var = vf.add_var('gov.combiTable1Ds1.smoothness_' + template_name)
    gov_combiTable1Ds1_tableID: Var = vf.add_var('gov.combiTable1Ds1.tableID_' + template_name)
    gov_combiTable1Ds1_tableName: Var = vf.add_var('gov.combiTable1Ds1.tableName_' + template_name)
    gov_combiTable1Ds1_tableOnFile: Var = vf.add_var('gov.combiTable1Ds1.tableOnFile_' + template_name)
    gov_combiTable1Ds1_table_1_1: Var = vf.add_var('gov.combiTable1Ds1.table[1,1]_' + template_name)
    gov_combiTable1Ds1_table_1_2: Var = vf.add_var('gov.combiTable1Ds1.table[1,2]_' + template_name)
    gov_combiTable1Ds1_table_2_1: Var = vf.add_var('gov.combiTable1Ds1.table[2,1]_' + template_name)
    gov_combiTable1Ds1_table_2_2: Var = vf.add_var('gov.combiTable1Ds1.table[2,2]_' + template_name)
    gov_combiTable1Ds1_table_3_1: Var = vf.add_var('gov.combiTable1Ds1.table[3,1]_' + template_name)
    gov_combiTable1Ds1_table_3_2: Var = vf.add_var('gov.combiTable1Ds1.table[3,2]_' + template_name)
    gov_combiTable1Ds1_table_4_1: Var = vf.add_var('gov.combiTable1Ds1.table[4,1]_' + template_name)
    gov_combiTable1Ds1_table_4_2: Var = vf.add_var('gov.combiTable1Ds1.table[4,2]_' + template_name)
    gov_combiTable1Ds1_table_5_1: Var = vf.add_var('gov.combiTable1Ds1.table[5,1]_' + template_name)
    gov_combiTable1Ds1_table_5_2: Var = vf.add_var('gov.combiTable1Ds1.table[5,2]_' + template_name)
    gov_combiTable1Ds1_u_max: Var = vf.add_var('gov.combiTable1Ds1.u_max_' + template_name)
    gov_combiTable1Ds1_u_min: Var = vf.add_var('gov.combiTable1Ds1.u_min_' + template_name)
    gov_combiTable1Ds1_verboseExtrapolation: Var = vf.add_var('gov.combiTable1Ds1.verboseExtrapolation_' + template_name)
    gov_combiTable1Ds1_verboseRead: Var = vf.add_var('gov.combiTable1Ds1.verboseRead_' + template_name)
    gov_firstOrder_T: Var = vf.add_var('gov.firstOrder.T_' + template_name)
    gov_firstOrder_initType: Var = vf.add_var('gov.firstOrder.initType_' + template_name)
    gov_firstOrder_k: Var = vf.add_var('gov.firstOrder.k_' + template_name)
    gov_firstOrder_y_start: Var = vf.add_var('gov.firstOrder.y_start_' + template_name)
    gov_firstOrder1_T: Var = vf.add_var('gov.firstOrder1.T_' + template_name)
    gov_firstOrder1_initType: Var = vf.add_var('gov.firstOrder1.initType_' + template_name)
    gov_firstOrder1_k: Var = vf.add_var('gov.firstOrder1.k_' + template_name)
    gov_firstOrder1_y_start: Var = vf.add_var('gov.firstOrder1.y_start_' + template_name)
    gov_gain_k: Var = vf.add_var('gov.gain.k_' + template_name)
    gov_integrator_initType: Var = vf.add_var('gov.integrator.initType_' + template_name)
    gov_integrator_k: Var = vf.add_var('gov.integrator.k_' + template_name)
    gov_integrator_use_reset: Var = vf.add_var('gov.integrator.use_reset_' + template_name)
    gov_integrator_use_set: Var = vf.add_var('gov.integrator.use_set_' + template_name)
    gov_integrator_y_start: Var = vf.add_var('gov.integrator.y_start_' + template_name)
    gov_limIntegrator_initType: Var = vf.add_var('gov.limIntegrator.initType_' + template_name)
    gov_limIntegrator_k: Var = vf.add_var('gov.limIntegrator.k_' + template_name)
    gov_limIntegrator_limitsAtInit: Var = vf.add_var('gov.limIntegrator.limitsAtInit_' + template_name)
    gov_limIntegrator_outMax: Var = vf.add_var('gov.limIntegrator.outMax_' + template_name)
    gov_limIntegrator_outMin: Var = vf.add_var('gov.limIntegrator.outMin_' + template_name)
    gov_limIntegrator_strict: Var = vf.add_var('gov.limIntegrator.strict_' + template_name)
    gov_limIntegrator_use_reset: Var = vf.add_var('gov.limIntegrator.use_reset_' + template_name)
    gov_limIntegrator_use_set: Var = vf.add_var('gov.limIntegrator.use_set_' + template_name)
    gov_limIntegrator_y_start: Var = vf.add_var('gov.limIntegrator.y_start_' + template_name)
    gov_limiter_homotopyType: Var = vf.add_var('gov.limiter.homotopyType_' + template_name)
    gov_limiter_limitsAtInit: Var = vf.add_var('gov.limiter.limitsAtInit_' + template_name)
    gov_limiter_strict: Var = vf.add_var('gov.limiter.strict_' + template_name)
    gov_limiter_uMax: Var = vf.add_var('gov.limiter.uMax_' + template_name)
    gov_limiter_uMin: Var = vf.add_var('gov.limiter.uMin_' + template_name)
    gov_limiter1_homotopyType: Var = vf.add_var('gov.limiter1.homotopyType_' + template_name)
    gov_limiter1_limitsAtInit: Var = vf.add_var('gov.limiter1.limitsAtInit_' + template_name)
    gov_limiter1_strict: Var = vf.add_var('gov.limiter1.strict_' + template_name)
    gov_limiter1_uMax: Var = vf.add_var('gov.limiter1.uMax_' + template_name)
    gov_limiter1_uMin: Var = vf.add_var('gov.limiter1.uMin_' + template_name)
    gov_t1: Var = vf.add_var('gov.t1_' + template_name)
    gov_t2: Var = vf.add_var('gov.t2_' + template_name)
    gov_t3: Var = vf.add_var('gov.t3_' + template_name)
    gov_t4: Var = vf.add_var('gov.t4_' + template_name)
    gov_t5: Var = vf.add_var('gov.t5_' + template_name)
    gov_t6: Var = vf.add_var('gov.t6_' + template_name)
    gov_tA: Var = vf.add_var('gov.tA_' + template_name)
    gov_tB: Var = vf.add_var('gov.tB_' + template_name)
    gov_tC: Var = vf.add_var('gov.tC_' + template_name)
    gov_transferFunction_a_1: Var = vf.add_var('gov.transferFunction.a[1]_' + template_name)
    gov_transferFunction_a_2: Var = vf.add_var('gov.transferFunction.a[2]_' + template_name)
    gov_transferFunction_a_end: Var = vf.add_var('gov.transferFunction.a_end_' + template_name)
    gov_transferFunction_b_1: Var = vf.add_var('gov.transferFunction.b[1]_' + template_name)
    gov_transferFunction_b_2: Var = vf.add_var('gov.transferFunction.b[2]_' + template_name)
    gov_transferFunction_bb_1: Var = vf.add_var('gov.transferFunction.bb[1]_' + template_name)
    gov_transferFunction_bb_2: Var = vf.add_var('gov.transferFunction.bb[2]_' + template_name)
    gov_transferFunction_d: Var = vf.add_var('gov.transferFunction.d_' + template_name)
    gov_transferFunction_na: Var = vf.add_var('gov.transferFunction.na_' + template_name)
    gov_transferFunction_nb: Var = vf.add_var('gov.transferFunction.nb_' + template_name)
    gov_transferFunction_nx: Var = vf.add_var('gov.transferFunction.nx_' + template_name)
    gov_transferFunction_x_start_1: Var = vf.add_var('gov.transferFunction.x_start[1]_' + template_name)
    gov_transferFunction_y_start: Var = vf.add_var('gov.transferFunction.y_start_' + template_name)
    # Declare the state variables used by the template.
    gov_firstOrder_y: Var = vf.add_var('gov.firstOrder.y_' + template_name)
    gov_firstOrder1_y: Var = vf.add_var('gov.firstOrder1.y_' + template_name)
    gov_integrator_y: Var = vf.add_var('gov.integrator.y_' + template_name)
    gov_limIntegrator_y: Var = vf.add_var('gov.limIntegrator.y_' + template_name)
    gov_transferFunction_x_scaled_1: Var = vf.add_var('gov.transferFunction.x_scaled[1]_' + template_name)
    # Declare the algebraic/shared variables used by the template.
    PRE_gov_timer_entryTime: Var = vf.add_var('$PRE.gov.timer.entryTime_' + template_name)
    START_gov_firstOrder_y: Var = vf.add_var('$START.gov.firstOrder.y_' + template_name)
    START_gov_firstOrder1_y: Var = vf.add_var('$START.gov.firstOrder1.y_' + template_name)
    START_gov_transferFunction_x_scaled_1: Var = vf.add_var('$START.gov.transferFunction.x_scaled[1]_' + template_name)
    gov_PmPu: Var = vf.add_var('gov.PmPu_' + template_name)
    gov_PmRefPu: Var = vf.add_var('gov.PmRefPu_' + template_name)
    gov_add_y: Var = vf.add_var('gov.add.y_' + template_name)
    gov_add1_y: Var = vf.add_var('gov.add1.y_' + template_name)
    gov_combiTable1Ds_y_1: Var = vf.add_var('gov.combiTable1Ds.y[1]_' + template_name)
    gov_combiTable1Ds1_y_1: Var = vf.add_var('gov.combiTable1Ds1.y[1]_' + template_name)
    gov_fastValving: Var = vf.add_var('gov.fastValving_' + template_name)
    gov_feedback_y: Var = vf.add_var('gov.feedback.y_' + template_name)
    gov_feedback1_y: Var = vf.add_var('gov.feedback1.y_' + template_name)
    gov_gain_y: Var = vf.add_var('gov.gain.y_' + template_name)
    gov_integrator_local_reset: Var = vf.add_var('gov.integrator.local_reset_' + template_name)
    gov_integrator_local_set: Var = vf.add_var('gov.integrator.local_set_' + template_name)
    gov_limIntegrator_local_reset: Var = vf.add_var('gov.limIntegrator.local_reset_' + template_name)
    gov_limIntegrator_local_set: Var = vf.add_var('gov.limIntegrator.local_set_' + template_name)
    gov_limiter_simplifiedExpr: Var = vf.add_var('gov.limiter.simplifiedExpr_' + template_name)
    gov_limiter_y: Var = vf.add_var('gov.limiter.y_' + template_name)
    gov_limiter1_simplifiedExpr: Var = vf.add_var('gov.limiter1.simplifiedExpr_' + template_name)
    gov_limiter1_y: Var = vf.add_var('gov.limiter1.y_' + template_name)
    gov_omegaPu: Var = vf.add_var('gov.omegaPu_' + template_name)
    gov_omegaRefPu: Var = vf.add_var('gov.omegaRefPu_' + template_name)
    gov_product_y: Var = vf.add_var('gov.product.y_' + template_name)
    gov_timer_entryTime: Var = vf.add_var('gov.timer.entryTime_' + template_name)
    gov_timer_y: Var = vf.add_var('gov.timer.y_' + template_name)
    gov_transferFunction_x_1: Var = vf.add_var('gov.transferFunction.x[1]_' + template_name)
    gov_transferFunction_y: Var = vf.add_var('gov.transferFunction.y_' + template_name)
    # Declare the differential variables used by the template.
    d_gov_firstOrder_y: Var = vf.add_diff_var('d_gov.firstOrder.y_' + template_name, base_var=gov_firstOrder_y)
    d_gov_firstOrder1_y: Var = vf.add_diff_var('d_gov.firstOrder1.y_' + template_name, base_var=gov_firstOrder1_y)
    d_gov_integrator_y: Var = vf.add_diff_var('d_gov.integrator.y_' + template_name, base_var=gov_integrator_y)
    d_gov_limIntegrator_y: Var = vf.add_diff_var('d_gov.limIntegrator.y_' + template_name, base_var=gov_limIntegrator_y)
    d_gov_transferFunction_x_scaled_1: Var = vf.add_diff_var('d_gov.transferFunction.x_scaled[1]_' + template_name, base_var=gov_transferFunction_x_scaled_1)

    # Build explicit typed collections so the symbolic surface is easy to inspect.
    state_equations: list[Expr] = list()
    state_equations.append((((gov_firstOrder1_k * gov_combiTable1Ds_y_1) - gov_firstOrder1_y) / gov_firstOrder1_T))
    state_equations.append((((gov_firstOrder_k * gov_limiter1_y) - gov_firstOrder_y) / gov_firstOrder_T))
    state_equations.append((((gov_transferFunction_a_end * gov_add_y) - (gov_transferFunction_a_2 * gov_transferFunction_x_scaled_1)) / gov_transferFunction_a_1))
    state_equations.append((((sym.Const(1.0) - ((sym.Const(1.0) - ((sym.heaviside(((gov_limIntegrator_outMin - gov_limIntegrator_y) - sym.Const(1e-06))) * sym.heaviside(((gov_limIntegrator_outMin - gov_limIntegrator_y) - sym.Const(1e-06)))) * sym.heaviside(((sym.Const(0.0) - (gov_limIntegrator_k * gov_feedback1_y)) - sym.Const(1e-06))))) * (sym.Const(1.0) - ((((((sym.heaviside(((gov_limIntegrator_outMin - gov_limIntegrator_y) - sym.Const(1e-06))) * sym.heaviside(((sym.Const(0.0) - (gov_limIntegrator_k * gov_feedback1_y)) - sym.Const(1e-06)))) * sym.heaviside(((gov_limIntegrator_y - gov_limIntegrator_outMax) - sym.Const(1e-06)))) * sym.heaviside(((gov_limIntegrator_outMin - gov_limIntegrator_y) - sym.Const(1e-06)))) * sym.heaviside(((sym.Const(0.0) - (gov_limIntegrator_k * gov_feedback1_y)) - sym.Const(1e-06)))) * sym.heaviside(((gov_limIntegrator_y - gov_limIntegrator_outMax) - sym.Const(1e-06)))) * sym.heaviside((((gov_limIntegrator_k * gov_feedback1_y) - sym.Const(0.0)) - sym.Const(1e-06))))))) * sym.Const(0.0)) + ((sym.Const(1.0) - (sym.Const(1.0) - ((sym.Const(1.0) - ((sym.heaviside(((gov_limIntegrator_outMin - gov_limIntegrator_y) - sym.Const(1e-06))) * sym.heaviside(((gov_limIntegrator_outMin - gov_limIntegrator_y) - sym.Const(1e-06)))) * sym.heaviside(((sym.Const(0.0) - (gov_limIntegrator_k * gov_feedback1_y)) - sym.Const(1e-06))))) * (sym.Const(1.0) - ((((((sym.heaviside(((gov_limIntegrator_outMin - gov_limIntegrator_y) - sym.Const(1e-06))) * sym.heaviside(((sym.Const(0.0) - (gov_limIntegrator_k * gov_feedback1_y)) - sym.Const(1e-06)))) * sym.heaviside(((gov_limIntegrator_y - gov_limIntegrator_outMax) - sym.Const(1e-06)))) * sym.heaviside(((gov_limIntegrator_outMin - gov_limIntegrator_y) - sym.Const(1e-06)))) * sym.heaviside(((sym.Const(0.0) - (gov_limIntegrator_k * gov_feedback1_y)) - sym.Const(1e-06)))) * sym.heaviside(((gov_limIntegrator_y - gov_limIntegrator_outMax) - sym.Const(1e-06)))) * sym.heaviside((((gov_limIntegrator_k * gov_feedback1_y) - sym.Const(0.0)) - sym.Const(1e-06)))))))) * (gov_limIntegrator_k * gov_feedback1_y))))
    state_equations.append((gov_integrator_k * gov_limiter_y))
    state_variables: list[Var] = list()
    state_variables.append(gov_firstOrder1_y)
    state_variables.append(gov_firstOrder_y)
    state_variables.append(gov_transferFunction_x_scaled_1)
    state_variables.append(gov_limIntegrator_y)
    state_variables.append(gov_integrator_y)
    algebraic_equations: list[Expr] = list()
    algebraic_equations.append((gov_product_y - (gov_combiTable1Ds1_y_1 * gov_limIntegrator_y)))
    algebraic_equations.append((gov_combiTable1Ds_y_1 - (((((((sym.Const(0.0) * sym.heaviside(((sym.Const(0.0) - gov_product_y) - sym.Const(1e-06)))) + ((((((sym.Const(0.25) - sym.Const(0.0)) / (sym.Const(0.25) - sym.Const(0.0))) * gov_product_y) + (sym.Const(0.0) - (((sym.Const(0.25) - sym.Const(0.0)) / (sym.Const(0.25) - sym.Const(0.0))) * sym.Const(0.0)))) * sym.heaviside(((gov_product_y - sym.Const(0.0)) + sym.Const(1e-06)))) * sym.heaviside(((sym.Const(0.25) - gov_product_y) - sym.Const(1e-06))))) + ((((((sym.Const(0.5) - sym.Const(0.25)) / (sym.Const(0.5) - sym.Const(0.25))) * gov_product_y) + (sym.Const(0.25) - (((sym.Const(0.5) - sym.Const(0.25)) / (sym.Const(0.5) - sym.Const(0.25))) * sym.Const(0.25)))) * sym.heaviside(((gov_product_y - sym.Const(0.25)) + sym.Const(1e-06)))) * sym.heaviside(((sym.Const(0.5) - gov_product_y) - sym.Const(1e-06))))) + ((((((sym.Const(0.75) - sym.Const(0.5)) / (sym.Const(0.75) - sym.Const(0.5))) * gov_product_y) + (sym.Const(0.5) - (((sym.Const(0.75) - sym.Const(0.5)) / (sym.Const(0.75) - sym.Const(0.5))) * sym.Const(0.5)))) * sym.heaviside(((gov_product_y - sym.Const(0.5)) + sym.Const(1e-06)))) * sym.heaviside(((sym.Const(0.75) - gov_product_y) - sym.Const(1e-06))))) + ((((((sym.Const(1.0) - sym.Const(0.75)) / (sym.Const(1.0) - sym.Const(0.75))) * gov_product_y) + (sym.Const(0.75) - (((sym.Const(1.0) - sym.Const(0.75)) / (sym.Const(1.0) - sym.Const(0.75))) * sym.Const(0.75)))) * sym.heaviside(((gov_product_y - sym.Const(0.75)) + sym.Const(1e-06)))) * sym.heaviside(((sym.Const(1.0) - gov_product_y) - sym.Const(1e-06))))) + ((((((sym.Const(1.25) - sym.Const(1.0)) / (sym.Const(1.25) - sym.Const(1.0))) * gov_product_y) + (sym.Const(1.0) - (((sym.Const(1.25) - sym.Const(1.0)) / (sym.Const(1.25) - sym.Const(1.0))) * sym.Const(1.0)))) * sym.heaviside(((gov_product_y - sym.Const(1.0)) + sym.Const(1e-06)))) * sym.heaviside(((sym.Const(1.25) - gov_product_y) - sym.Const(1e-06))))) + (sym.Const(1.25) * sym.heaviside(((gov_product_y - sym.Const(1.25)) + sym.Const(1e-06)))))))
    algebraic_equations.append((gov_PmPu - ((gov_add3_k1 * gov_firstOrder_y) + ((gov_add3_k2 * gov_combiTable1Ds_y_1) + (gov_add3_k3 * gov_firstOrder1_y)))))
    algebraic_equations.append((gov_limiter1_y - ((sym.heaviside(((gov_integrator_y - gov_limiter1_uMax) - sym.Const(1e-06))) * gov_limiter1_uMax) + ((sym.Const(1.0) - sym.heaviside(((gov_integrator_y - gov_limiter1_uMax) - sym.Const(1e-06)))) * ((sym.heaviside(((gov_limiter1_uMin - gov_integrator_y) - sym.Const(1e-06))) * gov_limiter1_uMin) + ((sym.Const(1.0) - sym.heaviside(((gov_limiter1_uMin - gov_integrator_y) - sym.Const(1e-06)))) * gov_integrator_y))))))
    algebraic_equations.append((gov_transferFunction_x_1 - (gov_transferFunction_x_scaled_1 / gov_transferFunction_a_end)))
    algebraic_equations.append((gov_transferFunction_y - (((gov_transferFunction_bb_2 - (gov_transferFunction_d * gov_transferFunction_a_2)) * gov_transferFunction_x_1) + (gov_transferFunction_d * gov_add_y))))
    algebraic_equations.append((gov_add1_y - ((gov_add1_k1 * gov_PmRefPu) + (gov_add1_k2 * gov_transferFunction_y))))
    algebraic_equations.append((gov_feedback1_y - (gov_firstOrder_y - gov_combiTable1Ds_y_1)))
    algebraic_equations.append((gov_feedback_y - (gov_add1_y - gov_limiter1_y)))
    algebraic_equations.append((gov_gain_y - (gov_gain_k * gov_feedback_y)))
    algebraic_equations.append((gov_limiter_y - ((sym.heaviside(((gov_gain_y - gov_limiter_uMax) - sym.Const(1e-06))) * gov_limiter_uMax) + ((sym.Const(1.0) - sym.heaviside(((gov_gain_y - gov_limiter_uMax) - sym.Const(1e-06)))) * ((sym.heaviside(((gov_limiter_uMin - gov_gain_y) - sym.Const(1e-06))) * gov_limiter_uMin) + ((sym.Const(1.0) - sym.heaviside(((gov_limiter_uMin - gov_gain_y) - sym.Const(1e-06)))) * gov_gain_y))))))
    algebraic_variables: list[Var] = list()
    algebraic_variables.append(gov_product_y)
    algebraic_variables.append(gov_combiTable1Ds_y_1)
    algebraic_variables.append(gov_PmPu)
    algebraic_variables.append(gov_limiter1_y)
    algebraic_variables.append(gov_transferFunction_x_1)
    algebraic_variables.append(gov_transferFunction_y)
    algebraic_variables.append(gov_add1_y)
    algebraic_variables.append(gov_feedback1_y)
    algebraic_variables.append(gov_feedback_y)
    algebraic_variables.append(gov_gain_y)
    algebraic_variables.append(gov_limiter_y)
    algebraic_variables.append(gov_combiTable1Ds1_y_1)
    algebraic_variables.append(gov_add_y)
    algebraic_variables.append(gov_PmRefPu)
    algebraic_variables.append(gov_omegaPu)
    algebraic_variables.append(gov_omegaRefPu)
    algebraic_variables.append(gov_fastValving)
    algebraic_variables.append(gov_limiter_simplifiedExpr)
    algebraic_variables.append(gov_integrator_local_reset)
    algebraic_variables.append(gov_integrator_local_set)
    algebraic_variables.append(gov_limiter1_simplifiedExpr)
    algebraic_variables.append(gov_limIntegrator_local_reset)
    algebraic_variables.append(gov_limIntegrator_local_set)
    algebraic_variables.append(START_gov_transferFunction_x_scaled_1)
    algebraic_variables.append(START_gov_firstOrder_y)
    algebraic_variables.append(START_gov_firstOrder1_y)
    algebraic_variables.append(gov_timer_y)
    algebraic_variables.append(PRE_gov_timer_entryTime)
    algebraic_variables.append(gov_timer_entryTime)
    differential_variables: list[Var] = list()
    differential_variables.append(d_gov_firstOrder1_y)
    differential_variables.append(d_gov_firstOrder_y)
    differential_variables.append(d_gov_transferFunction_x_scaled_1)
    differential_variables.append(d_gov_limIntegrator_y)
    differential_variables.append(d_gov_integrator_y)
    input_variables: list[Var] = list()
    output_variables: list[Var] = list()
    event_parameters: dict[Var, Expr | Const] = dict()
    event_parameters[gov_K] = vf.add_const(25.0, name='')
    event_parameters[gov_K1] = vf.add_const(0.2, name='')
    event_parameters[gov_K2] = vf.add_const(0.0, name='')
    event_parameters[gov_K3] = vf.add_const(0.8, name='')
    event_parameters[gov_PMaxPu] = vf.add_const(1.0, name='')
    event_parameters[gov_PMinPu] = vf.add_const(0.0, name='')
    event_parameters[gov_Pm0Pu] = vf.add_const(0.8, name='')
    event_parameters[gov_Pr0Pu] = vf.add_const(1.0, name='')
    event_parameters[gov_PrMaxPu] = vf.add_const(1.2, name='')
    event_parameters[gov_Uc] = vf.add_const(-10.0, name='')
    event_parameters[gov_Uo] = vf.add_const(1.0, name='')
    event_parameters[gov_add_k1] = vf.add_const(1.0, name='')
    event_parameters[gov_add_k2] = vf.add_const(-1.0, name='')
    event_parameters[gov_add1_k1] = vf.add_const(1.0, name='')
    event_parameters[gov_add1_k2] = (-gov_K)
    event_parameters[gov_add3_k1] = gov_K1
    event_parameters[gov_add3_k2] = gov_K2
    event_parameters[gov_add3_k3] = gov_K3
    event_parameters[gov_combiTable1Ds_u_max] = vf.add_const(1.25, name='')
    event_parameters[gov_combiTable1Ds_u_min] = vf.add_const(0.0, name='')
    event_parameters[gov_combiTable1Ds1_table_1_1] = vf.add_const(0.0, name='')
    event_parameters[gov_combiTable1Ds1_table_1_2] = vf.add_const(1.0, name='')
    event_parameters[gov_combiTable1Ds1_table_2_1] = gov_tA
    event_parameters[gov_combiTable1Ds1_table_2_2] = vf.add_const(0.0, name='')
    event_parameters[gov_combiTable1Ds1_table_3_1] = gov_tB
    event_parameters[gov_combiTable1Ds1_table_3_2] = vf.add_const(0.0, name='')
    event_parameters[gov_combiTable1Ds1_table_4_1] = gov_tC
    event_parameters[gov_combiTable1Ds1_table_4_2] = vf.add_const(1.0, name='')
    event_parameters[gov_combiTable1Ds1_table_5_1] = (sym.Const(2.0) * gov_tC)
    event_parameters[gov_combiTable1Ds1_table_5_2] = vf.add_const(1.0, name='')
    event_parameters[gov_combiTable1Ds1_u_max] = vf.add_const(2.0, name='')
    event_parameters[gov_combiTable1Ds1_u_min] = vf.add_const(0.0, name='')
    event_parameters[gov_firstOrder_T] = gov_t4
    event_parameters[gov_firstOrder_k] = vf.add_const(1.0, name='')
    event_parameters[gov_firstOrder_y_start] = gov_Pm0Pu
    event_parameters[gov_firstOrder1_T] = gov_t6
    event_parameters[gov_firstOrder1_k] = vf.add_const(1.0, name='')
    event_parameters[gov_firstOrder1_y_start] = gov_Pm0Pu
    event_parameters[gov_gain_k] = (sym.Const(1.0) / gov_t3)
    event_parameters[gov_integrator_k] = vf.add_const(1.0, name='')
    event_parameters[gov_integrator_y_start] = gov_Pm0Pu
    event_parameters[gov_limIntegrator_k] = (sym.Const(1.0) / gov_t5)
    event_parameters[gov_limIntegrator_outMax] = gov_PrMaxPu
    event_parameters[gov_limIntegrator_outMin] = vf.add_const(-999.0, name='')
    event_parameters[gov_limIntegrator_y_start] = gov_Pr0Pu
    event_parameters[gov_limiter_uMax] = gov_Uo
    event_parameters[gov_limiter_uMin] = gov_Uc
    event_parameters[gov_limiter1_uMax] = gov_PMaxPu
    event_parameters[gov_limiter1_uMin] = gov_PMinPu
    event_parameters[gov_t1] = vf.add_const(1e-06, name='')
    event_parameters[gov_t2] = vf.add_const(1e-06, name='')
    event_parameters[gov_t3] = vf.add_const(0.1, name='')
    event_parameters[gov_t4] = vf.add_const(0.3, name='')
    event_parameters[gov_t5] = vf.add_const(5.0, name='')
    event_parameters[gov_t6] = vf.add_const(0.5, name='')
    event_parameters[gov_tA] = vf.add_const(0.1, name='')
    event_parameters[gov_tB] = vf.add_const(0.5, name='')
    event_parameters[gov_tC] = vf.add_const(1.0, name='')
    event_parameters[gov_transferFunction_a_1] = gov_t1
    event_parameters[gov_transferFunction_a_2] = vf.add_const(1.0, name='')
    event_parameters[gov_transferFunction_a_end] = ((sym.heaviside(((gov_transferFunction_a_2 - (sym.Const(2.220446049250313e-14) * sym.sqrt(((gov_transferFunction_a_1 ** sym.Const(2.0)) + (gov_transferFunction_a_2 ** sym.Const(2.0)))))) - sym.Const(1e-06))) * gov_transferFunction_a_2) + ((sym.Const(1.0) - sym.heaviside(((gov_transferFunction_a_2 - (sym.Const(2.220446049250313e-14) * sym.sqrt(((gov_transferFunction_a_1 ** sym.Const(2.0)) + (gov_transferFunction_a_2 ** sym.Const(2.0)))))) - sym.Const(1e-06)))) * sym.Const(1.0)))
    event_parameters[gov_transferFunction_b_1] = gov_t2
    event_parameters[gov_transferFunction_b_2] = vf.add_const(1.0, name='')
    event_parameters[gov_transferFunction_bb_1] = gov_transferFunction_b_1
    event_parameters[gov_transferFunction_bb_2] = gov_transferFunction_b_2
    event_parameters[gov_transferFunction_d] = (gov_transferFunction_bb_1 / gov_transferFunction_a_1)
    event_parameters[gov_transferFunction_x_start_1] = vf.add_const(0.0, name='')
    event_parameters[gov_transferFunction_y_start] = vf.add_const(0.0, name='')
    event_parameters[gov_combiTable1Ds_columns_1] = vf.add_const(2.0, name='')
    event_parameters[gov_combiTable1Ds_extrapolation] = vf.add_const(2.0, name='')
    event_parameters[gov_combiTable1Ds_nout] = vf.add_const(1.0, name='')
    event_parameters[gov_combiTable1Ds_smoothness] = vf.add_const(1.0, name='')
    event_parameters[gov_combiTable1Ds1_columns_1] = vf.add_const(2.0, name='')
    event_parameters[gov_combiTable1Ds1_extrapolation] = vf.add_const(2.0, name='')
    event_parameters[gov_combiTable1Ds1_nout] = vf.add_const(1.0, name='')
    event_parameters[gov_combiTable1Ds1_smoothness] = vf.add_const(1.0, name='')
    event_parameters[gov_firstOrder_initType] = vf.add_const(1.0, name='')
    event_parameters[gov_firstOrder1_initType] = vf.add_const(1.0, name='')
    event_parameters[gov_integrator_initType] = vf.add_const(3.0, name='')
    event_parameters[gov_limIntegrator_initType] = vf.add_const(3.0, name='')
    event_parameters[gov_limiter_homotopyType] = vf.add_const(1.0, name='')
    event_parameters[gov_limiter1_homotopyType] = vf.add_const(1.0, name='')
    event_parameters[gov_transferFunction_na] = vf.add_const(2.0, name='')
    event_parameters[gov_transferFunction_nb] = vf.add_const(2.0, name='')
    event_parameters[gov_transferFunction_nx] = vf.add_const(1.0, name='')
    event_parameters[gov_combiTable1Ds_tableOnFile] = vf.add_const(1.0, name='')
    event_parameters[gov_combiTable1Ds_verboseExtrapolation] = vf.add_const(0.0, name='')
    event_parameters[gov_combiTable1Ds_verboseRead] = vf.add_const(1.0, name='')
    event_parameters[gov_combiTable1Ds1_tableOnFile] = vf.add_const(0.0, name='')
    event_parameters[gov_combiTable1Ds1_verboseExtrapolation] = vf.add_const(0.0, name='')
    event_parameters[gov_combiTable1Ds1_verboseRead] = vf.add_const(1.0, name='')
    event_parameters[gov_integrator_use_reset] = vf.add_const(0.0, name='')
    event_parameters[gov_integrator_use_set] = vf.add_const(0.0, name='')
    event_parameters[gov_limIntegrator_limitsAtInit] = vf.add_const(1.0, name='')
    event_parameters[gov_limIntegrator_strict] = vf.add_const(0.0, name='')
    event_parameters[gov_limIntegrator_use_reset] = vf.add_const(0.0, name='')
    event_parameters[gov_limIntegrator_use_set] = vf.add_const(0.0, name='')
    event_parameters[gov_limiter_limitsAtInit] = vf.add_const(1.0, name='')
    event_parameters[gov_limiter_strict] = vf.add_const(0.0, name='')
    event_parameters[gov_limiter1_limitsAtInit] = vf.add_const(1.0, name='')
    event_parameters[gov_limiter1_strict] = vf.add_const(0.0, name='')
    event_parameters[gov_FValveTableName] = vf.add_const(0.0, name='')
    event_parameters[gov_TablesFile] = vf.add_const(0.0, name='')
    event_parameters[gov_combiTable1Ds_fileName] = gov_TablesFile
    event_parameters[gov_combiTable1Ds_tableName] = gov_FValveTableName
    event_parameters[gov_combiTable1Ds1_fileName] = vf.add_const(0.0, name='')
    event_parameters[gov_combiTable1Ds1_tableName] = vf.add_const(0.0, name='')
    event_parameters[gov_combiTable1Ds_tableID] = vf.add_const(0.0, name='')
    event_parameters[gov_combiTable1Ds1_tableID] = vf.add_const(0.0, name='')
    mode_parameters: dict[Var, Expr | Const] = dict()
    initial_equations: dict[Var, Expr | Const] = dict()
    initial_equations[gov_firstOrder_y] = gov_firstOrder_y_start
    initial_equations[gov_firstOrder1_y] = gov_firstOrder1_y_start
    initial_equations[gov_integrator_y] = gov_integrator_y_start
    initial_equations[gov_limIntegrator_y] = gov_limIntegrator_y_start
    initial_equations[gov_transferFunction_x_scaled_1] = (gov_transferFunction_a_end * gov_transferFunction_x_start_1)
    initial_equations[gov_PmPu] = vf.add_const(0.8, name='')
    initial_equations[gov_PmRefPu] = vf.add_const(0.8, name='')
    initial_equations[gov_omegaPu] = vf.add_const(1.0, name='')
    initial_equations[gov_omegaRefPu] = vf.add_const(1.0, name='')
    initial_equations[gov_transferFunction_x_1] = gov_transferFunction_x_start_1
    initial_equations[gov_transferFunction_y] = gov_transferFunction_y_start
    initial_equations[gov_fastValving] = vf.add_const(0.0, name='')
    initial_equations[gov_limiter_simplifiedExpr] = vf.add_const(0.0, name='')
    initial_equations[gov_integrator_local_reset] = vf.add_const(0.0, name='')
    initial_equations[gov_integrator_local_set] = vf.add_const(0.0, name='')
    initial_equations[gov_limiter1_simplifiedExpr] = vf.add_const(0.0, name='')
    initial_equations[gov_limIntegrator_local_reset] = vf.add_const(0.0, name='')
    initial_equations[gov_limIntegrator_local_set] = vf.add_const(0.0, name='')
    initial_equations[gov_combiTable1Ds1_y_1] = ((((((sym.Const(1.0) * sym.heaviside(((sym.Const(0.0) - sym.Const(0.0)) - sym.Const(1e-06)))) + ((((((sym.Const(0.0) - sym.Const(1.0)) / (sym.Const(0.1) - sym.Const(0.0))) * sym.Const(0.0)) + (sym.Const(1.0) - (((sym.Const(0.0) - sym.Const(1.0)) / (sym.Const(0.1) - sym.Const(0.0))) * sym.Const(0.0)))) * sym.heaviside(((sym.Const(0.0) - sym.Const(0.0)) + sym.Const(1e-06)))) * sym.heaviside(((sym.Const(0.1) - sym.Const(0.0)) - sym.Const(1e-06))))) + ((((((sym.Const(0.0) - sym.Const(0.0)) / (sym.Const(0.5) - sym.Const(0.1))) * sym.Const(0.0)) + (sym.Const(0.0) - (((sym.Const(0.0) - sym.Const(0.0)) / (sym.Const(0.5) - sym.Const(0.1))) * sym.Const(0.1)))) * sym.heaviside(((sym.Const(0.0) - sym.Const(0.1)) + sym.Const(1e-06)))) * sym.heaviside(((sym.Const(0.5) - sym.Const(0.0)) - sym.Const(1e-06))))) + ((((((sym.Const(1.0) - sym.Const(0.0)) / (sym.Const(1.0) - sym.Const(0.5))) * sym.Const(0.0)) + (sym.Const(0.0) - (((sym.Const(1.0) - sym.Const(0.0)) / (sym.Const(1.0) - sym.Const(0.5))) * sym.Const(0.5)))) * sym.heaviside(((sym.Const(0.0) - sym.Const(0.5)) + sym.Const(1e-06)))) * sym.heaviside(((sym.Const(1.0) - sym.Const(0.0)) - sym.Const(1e-06))))) + ((((((sym.Const(1.0) - sym.Const(1.0)) / (sym.Const(2.0) - sym.Const(1.0))) * sym.Const(0.0)) + (sym.Const(1.0) - (((sym.Const(1.0) - sym.Const(1.0)) / (sym.Const(2.0) - sym.Const(1.0))) * sym.Const(1.0)))) * sym.heaviside(((sym.Const(0.0) - sym.Const(1.0)) + sym.Const(1e-06)))) * sym.heaviside(((sym.Const(2.0) - sym.Const(0.0)) - sym.Const(1e-06))))) + (sym.Const(1.0) * sym.heaviside(((sym.Const(0.0) - sym.Const(2.0)) + sym.Const(1e-06)))))
    initial_equations[gov_add_y] = (gov_add_k1 + gov_add_k2)
    initial_equations[gov_timer_y] = vf.add_const(0.0, name='')
    initial_equations[PRE_gov_timer_entryTime] = vf.add_const(0.0, name='')
    initial_equations[gov_timer_entryTime] = PRE_gov_timer_entryTime
    initial_equations[gov_add1_y] = ((gov_add1_k1 * gov_PmRefPu) + (gov_add1_k2 * gov_transferFunction_y))
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
    templates.extend(build_lookup_runtime_templates(vf=vf, name_prefix=name_prefix))
    templates.extend(build_first_order_runtime_templates(vf=vf, name_prefix=name_prefix))
    templates.extend(build_lead_lag_runtime_templates(vf=vf, name_prefix=name_prefix))
    templates.extend(build_gain_runtime_templates(vf=vf, name_prefix=name_prefix))
    templates.extend(build_limiter_runtime_templates(vf=vf, name_prefix=name_prefix))
    return tuple(templates)

def build_lookup_runtime_templates(vf: VarFactory, name_prefix: str | None = None) -> tuple[EmtModelTemplate, ...]:
    """
    Materialize the recovered lookup tables through BasicBlockCatalog builders.

    :param vf: Variable factory shared by the generated lookup templates.
    :param name_prefix: Optional template-name prefix for emitted lookup helpers.
    :returns: Tuple of lookup-table EMT templates.
    """
    template_prefix: str
    lookup_templates: list[EmtModelTemplate] = list()
    lookup_index: int = 0
    symbol_name: str
    lookup_kind: str
    source_function: str
    x_points: tuple[float, ...]
    y_points: tuple[float, ...]

    if name_prefix is None:
        template_prefix = TEMPLATE_KEY
    else:
        template_prefix = name_prefix

    for symbol_name, lookup_kind, source_function, x_points, y_points in LOOKUP_TABLE_SPECS:
        if source_function:
            pass
        else:
            pass
        if lookup_kind == 'linear_clipped':
            lookup_templates.append(
                build_lookup_array_linear_runtime_template(
                    vf=vf,
                    x_points=x_points,
                    y_points=y_points,
                    clip=True,
                    name=f'{template_prefix}_lookup_{lookup_index + 1}',
                )
            )
        else:
            if lookup_kind == 'linear_unclipped':
                lookup_templates.append(
                    build_lookup_array_linear_runtime_template(
                        vf=vf,
                        x_points=x_points,
                        y_points=y_points,
                        clip=False,
                        name=f'{template_prefix}_lookup_{lookup_index + 1}',
                    )
                )
            else:
                if lookup_kind == 'spline':
                    lookup_templates.append(
                        build_lookup_array_spline_runtime_template(
                            vf=vf,
                            x_points=x_points,
                            y_points=y_points,
                            name=f'{template_prefix}_lookup_{lookup_index + 1}',
                        )
                    )
                else:
                    pass
        lookup_index += 1

    return tuple(lookup_templates)

def build_gain_runtime_templates(vf: VarFactory, name_prefix: str | None = None) -> tuple[EmtModelTemplate, ...]:
    """
    Materialize directly mappable scalar gain primitives.

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
    symbol_name: str
    input_name: str
    gain_name: str | None
    gain_value: float | None

    if name_prefix is None:
        template_prefix = TEMPLATE_KEY
    else:
        template_prefix = name_prefix

    for symbol_name, input_name, gain_name, gain_value in GAIN_SPECS:
        if gain_value is None:
            pass
        else:
            template_name: str = f'{template_prefix}_gain_{spec_index + 1}'
            template_obj: EmtModelTemplate = build_scalar_gain_runtime_template(vf=vf, gain_value=float(gain_value), name=template_name)
            templates.append(template_obj)
        spec_index += 1

    return tuple(templates)

def build_first_order_runtime_templates(vf: VarFactory, name_prefix: str | None = None) -> tuple[EmtModelTemplate, ...]:
    """
    Materialize directly mappable first-order and integrator primitives.

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
    state_name: str
    kind: str
    input_name: str
    t_name: str | None
    t_value: float | None
    gain_name: str | None
    gain_value: float | None

    if name_prefix is None:
        template_prefix = TEMPLATE_KEY
    else:
        template_prefix = name_prefix

    for state_name, kind, input_name, t_name, t_value, gain_name, gain_value in FIRST_ORDER_SPECS:
        if kind == 'first_order_unity' and t_value is not None:
            template_name: str = f'{template_prefix}_first_order_{spec_index + 1}'
            template_obj: EmtModelTemplate = build_typ_138__1_1_st_template(vf=vf, name=template_name)
            template_obj.block.set_parameter_in_model('1/(1+sT)__T_' + template_name, float(t_value))
            templates.append(template_obj)
        else:
            if kind == 'first_order_gain' and t_value is not None and gain_value is not None:
                template_name: str = f'{template_prefix}_first_order_{spec_index + 1}'
                template_obj: EmtModelTemplate = build_gain_then_first_order_runtime_template(vf=vf, gain_value=float(gain_value), time_constant=float(t_value), name=template_name)
                templates.append(template_obj)
            else:
                if kind == 'integrator_unity':
                    template_name: str = f'{template_prefix}_integrator_{spec_index + 1}'
                    template_obj: EmtModelTemplate = build_typ_214__1_s_template(vf=vf, name=template_name)
                    templates.append(template_obj)
                else:
                    if kind == 'integrator_gain' and gain_value is not None:
                        template_name: str = f'{template_prefix}_integrator_{spec_index + 1}'
                        template_obj: EmtModelTemplate = build_gain_then_integrator_runtime_template(vf=vf, gain_value=float(gain_value), name=template_name)
                        templates.append(template_obj)
                    else:
                        pass
        spec_index += 1

    return tuple(templates)

def build_lead_lag_runtime_templates(vf: VarFactory, name_prefix: str | None = None) -> tuple[EmtModelTemplate, ...]:
    """
    Materialize directly mappable unit-gain lead-lag primitives.

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
    symbol_name: str
    input_name: str
    tb_name: str | None
    tb_value: float | None
    ta_name: str | None
    ta_value: float | None

    if name_prefix is None:
        template_prefix = TEMPLATE_KEY
    else:
        template_prefix = name_prefix

    for symbol_name, input_name, tb_name, tb_value, ta_name, ta_value in LEAD_LAG_SPECS:
        if tb_value is not None and ta_value is not None:
            template_name: str = f'{template_prefix}_lead_lag_{spec_index + 1}'
            template_obj: EmtModelTemplate = build_typ_298__1_stb_1_sta_template(vf=vf, name=template_name)
            template_obj.block.set_parameter_in_model('(1+sTb)/(1+sTa)__Tb_' + template_name, float(tb_value))
            template_obj.block.set_parameter_in_model('(1+sTb)/(1+sTa)__Ta_' + template_name, float(ta_value))
            templates.append(template_obj)
        else:
            pass
        spec_index += 1

    return tuple(templates)

def build_limiter_runtime_templates(vf: VarFactory, name_prefix: str | None = None) -> tuple[EmtModelTemplate, ...]:
    """
    Materialize directly mappable constant limiter primitives.

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
    symbol_name: str
    source_expr: str
    input_name: str | None
    gain_name: str | None
    gain_value: float | None
    y_max_name: str | None
    y_max_value: float | None
    y_min_name: str | None
    y_min_value: float | None

    if name_prefix is None:
        template_prefix = TEMPLATE_KEY
    else:
        template_prefix = name_prefix

    for symbol_name, source_expr, input_name, gain_name, gain_value, y_max_name, y_max_value, y_min_name, y_min_value in LIMITER_SPECS:
        if y_max_value is not None and y_min_value is not None:
            template_name: str = f'{template_prefix}_limiter_{spec_index + 1}'
            if gain_value is not None:
                template_obj: EmtModelTemplate = build_gain_then_limiter_runtime_template(vf=vf, gain_value=float(gain_value), y_max_value=float(y_max_value), y_min_value=float(y_min_value), name=template_name)
            else:
                template_obj: EmtModelTemplate = build_typ_76__lim_const_template(vf=vf, name=template_name)
                template_obj.block.set_parameter_in_model('lim_const__y_max_' + template_name, float(y_max_value))
                template_obj.block.set_parameter_in_model('lim_const__y_min_' + template_name, float(y_min_value))
            templates.append(template_obj)
        else:
            pass
        spec_index += 1

    return tuple(templates)

# Recovered spec payloads kept for regeneration and inspection

LOOKUP_TABLE_SPECS: tuple[tuple[str, str, str, tuple[float, ...], tuple[float, ...]], ...] = (
    ('gov.combiTable1Ds.column[2]', 'linear_clipped', 'getTable1DValue', (0.0, 0.25, 0.5, 0.75, 1.0, 1.25), (0.0, 0.25, 0.5, 0.75, 1.0, 1.25)),
    ('gov.combiTable1Ds1.column[2]', 'linear_clipped', 'getTable1DValue', (0.0, 0.1, 0.5, 1.0, 2.0), (1.0, 0.0, 0.0, 1.0, 1.0)),
)

FIRST_ORDER_SPECS: tuple[tuple[str, str, str, str | None, float | None, str | None, float | None], ...] = (
    ('gov.firstOrder1.y', 'first_order_gain', 'gov.combiTable1Ds.y[1]', 'gov.firstOrder1.T', 0.5, 'gov.firstOrder1.k', 1.0),
    ('gov.firstOrder.y', 'first_order_gain', 'gov.limiter1.y', 'gov.firstOrder.T', 0.3, 'gov.firstOrder.k', 1.0),
    ('gov.integrator.y', 'integrator_gain', 'gov.limiter.y', None, None, 'gov.integrator.k', 1.0),
)

LEAD_LAG_SPECS: tuple[tuple[str, str, str | None, float | None, str | None, float | None], ...] = (
    ('gov.transferFunction.y', 'gov.add.y', 'gov.transferFunction.b[1]', 0.0, 'gov.transferFunction.a[1]', 0.0),
)

GAIN_SPECS: tuple[tuple[str, str, str | None, float | None], ...] = (
    ('gov.gain.y', 'gov.feedback.y', 'gov.gain.k', 10.0),
)

LIMITER_SPECS: tuple[tuple[str, str, str | None, str | None, float | None, str | None, float | None, str | None, float | None], ...] = (
    ('gov.limiter1.y', '((heaviside(((gov.integrator.y - gov.limiter1.uMax) - 1e-06)) * gov.limiter1.uMax) + ((1.0 - heaviside(((gov.integrator.y - gov.limiter1.uMax) - 1e-06))) * ((heaviside(((gov.limiter1.uMin - gov.integrator.y) - 1e-06)) * gov.limiter1.uMin) + ((1.0 - heaviside(((gov.limiter1.uMin - gov.integrator.y) - 1e-06))) * gov.integrator.y))))', 'gov.integrator.y', None, None, 'gov.limiter1.uMax', 1.0, 'gov.limiter1.uMin', 0.0),
    ('gov.limiter.y', '((heaviside(((gov.gain.y - gov.limiter.uMax) - 1e-06)) * gov.limiter.uMax) + ((1.0 - heaviside(((gov.gain.y - gov.limiter.uMax) - 1e-06))) * ((heaviside(((gov.limiter.uMin - gov.gain.y) - 1e-06)) * gov.limiter.uMin) + ((1.0 - heaviside(((gov.limiter.uMin - gov.gain.y) - 1e-06))) * gov.gain.y))))', 'gov.gain.y', None, None, 'gov.limiter.uMax', 1.0, 'gov.limiter.uMin', -10.0),
)
