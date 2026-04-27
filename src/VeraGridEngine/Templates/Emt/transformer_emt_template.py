# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Dict

from VeraGridEngine.enumerations import (
    DeviceType,
    ParamPowerFlowRefferenceType,
    VarPowerFlowRefferenceType,
    WindingType,
)
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Var, Expr




def get_transformer_emt_template(
    vf: VarFactory,
    conn_f: WindingType | None = None,
    conn_t: WindingType | None = None,
    name: str = "transformer_emt_template",
) -> EmtModelTemplate:
    """
    Build a linear two-winding transformer EMT template using coupled winding currents
    as state variables.

    This simplified version keeps only the series coupled-winding model and omits the
    primary shunt branch from the EMT equations. The total voltage ratio is exposed
    through api_obj_mapping and is used to initialize the primary winding current from
    the secondary-side port current in a way that is consistent with the external port
    convention.

    Assumptions:
    - `l1`, `l2`, and `m12` already represent the physical transformer model in the
      chosen winding coordinates.
    - branch currents are positive when leaving the connected bus.
    - `if_act` and `it_act` are externally initialized by the EMT framework from the
      power-flow solution through `external_mapping`.

    :param vf: EMT variable factory.
    :param conn_f: Optional from-side winding connection.
    :param conn_t: Optional to-side winding connection.
    :param name: Symbolic model name.
    :return: EMT transformer model template.
    """

    templ: EmtModelTemplate = EmtModelTemplate()
    templ.tpe = DeviceType.TransformerTypeDevice
    templ.name = name
    templ.block.name = name

    if conn_f in {WindingType.GroundedStar, WindingType.NeutralStar}:
        from_has_neutral_port: bool = True
    else:
        from_has_neutral_port = False

    if conn_t in {WindingType.GroundedStar, WindingType.NeutralStar}:
        to_has_neutral_port: bool = True
    else:
        to_has_neutral_port = False

    c_eps = vf.add_const(1e-12)

    # ------------------------------------------------------------------
    # Static parameters injected from the API object
    # ------------------------------------------------------------------
    r1: Var = vf.add_var(name=f"xfmr_r1_{name}")
    r2: Var = vf.add_var(name=f"xfmr_r2_{name}")
    l1: Var = vf.add_var(name=f"xfmr_l1_{name}")
    l2: Var = vf.add_var(name=f"xfmr_l2_{name}")
    m12: Var = vf.add_var(name=f"xfmr_m_{name}")
    gm: Var = vf.add_var(name=f"xfmr_gm_{name}")  # kept for compatibility, unused here
    total_voltage_ratio: Var = vf.add_var(name=f"tap_ratio_{name}")

    templ.block.api_obj_mapping[ParamPowerFlowRefferenceType.transformer_winding1_resistance_pu] = r1
    templ.block.api_obj_mapping[ParamPowerFlowRefferenceType.transformer_winding2_resistance_pu] = r2
    templ.block.api_obj_mapping[ParamPowerFlowRefferenceType.transformer_winding1_inductance_pu_s] = l1
    templ.block.api_obj_mapping[ParamPowerFlowRefferenceType.transformer_winding2_inductance_pu_s] = l2
    templ.block.api_obj_mapping[ParamPowerFlowRefferenceType.transformer_mutual_inductance_pu_s] = m12
    templ.block.api_obj_mapping[ParamPowerFlowRefferenceType.transformer_magnetizing_conductance_pu] = gm
    templ.block.api_obj_mapping[ParamPowerFlowRefferenceType.transformer_total_voltage_ratio] = total_voltage_ratio

    # ------------------------------------------------------------------
    # Terminal voltages
    # ------------------------------------------------------------------
    vf_n: Var | None = None
    vt_n: Var | None = None

    if from_has_neutral_port:
        vf_n = vf.add_var(name=f"vf_N_{name}", reference=VarPowerFlowRefferenceType.vf_N)
    else:
        pass

    if to_has_neutral_port:
        vt_n = vf.add_var(name=f"vt_N_{name}", reference=VarPowerFlowRefferenceType.vt_N)
    else:
        pass

    vf_vars: list[Var] = [
        vf.add_var(name=f"vf_A_{name}", reference=VarPowerFlowRefferenceType.vf_A),
        vf.add_var(name=f"vf_B_{name}", reference=VarPowerFlowRefferenceType.vf_B),
        vf.add_var(name=f"vf_C_{name}", reference=VarPowerFlowRefferenceType.vf_C),
    ]
    vt_vars: list[Var] = [
        vf.add_var(name=f"vt_A_{name}", reference=VarPowerFlowRefferenceType.vt_A),
        vf.add_var(name=f"vt_B_{name}", reference=VarPowerFlowRefferenceType.vt_B),
        vf.add_var(name=f"vt_C_{name}", reference=VarPowerFlowRefferenceType.vt_C),
    ]

    # ------------------------------------------------------------------
    # Internal winding-current states
    # ------------------------------------------------------------------
    i_f: list[Var] = [
        vf.add_var(name=f"i_f_A_{name}"),
        vf.add_var(name=f"i_f_B_{name}"),
        vf.add_var(name=f"i_f_C_{name}"),
    ]
    i_t: list[Var] = [
        vf.add_var(name=f"i_t_A_{name}"),
        vf.add_var(name=f"i_t_B_{name}"),
        vf.add_var(name=f"i_t_C_{name}"),
    ]

    di_f: list[Var] = [
        vf.add_diff_var(name=f"di_f_A_{name}", base_var=i_f[0]),
        vf.add_diff_var(name=f"di_f_B_{name}", base_var=i_f[1]),
        vf.add_diff_var(name=f"di_f_C_{name}", base_var=i_f[2]),
    ]
    di_t: list[Var] = [
        vf.add_diff_var(name=f"di_t_A_{name}", base_var=i_t[0]),
        vf.add_diff_var(name=f"di_t_B_{name}", base_var=i_t[1]),
        vf.add_diff_var(name=f"di_t_C_{name}", base_var=i_t[2]),
    ]

    # ------------------------------------------------------------------
    # External branch-port currents
    # ------------------------------------------------------------------
    if_act: list[Var] = [
        vf.add_var(name=f"if_{name}_A"),
        vf.add_var(name=f"if_{name}_B"),
        vf.add_var(name=f"if_{name}_C"),
    ]
    it_act: list[Var] = [
        vf.add_var(name=f"it_{name}_A"),
        vf.add_var(name=f"it_{name}_B"),
        vf.add_var(name=f"it_{name}_C"),
    ]
    if_n_act: Var | None = vf.add_var(name=f"if_{name}_N") if from_has_neutral_port else None
    it_n_act: Var | None = vf.add_var(name=f"it_{name}_N") if to_has_neutral_port else None

    input_vars: list[Var] = list()
    if vf_n is not None:
        input_vars.append(vf_n)
    else:
        pass

    input_vars.extend(vf_vars)

    if vt_n is not None:
        input_vars.append(vt_n)
    else:
        pass

    input_vars.extend(vt_vars)

    algebraic_vars: list[Var] = list(if_act + it_act)
    if if_n_act is not None:
        algebraic_vars.append(if_n_act)
    else:
        pass

    if it_n_act is not None:
        algebraic_vars.append(it_n_act)
    else:
        pass

    templ.block.in_vars = input_vars
    templ.block.state_vars = i_f + i_t
    templ.block.diff_vars = di_f + di_t
    templ.block.algebraic_vars = algebraic_vars

    v_f_term: list[Expr] = list()
    v_t_term: list[Expr] = list()
    idx: int
    for idx in range(3):
        if vf_n is not None:
            v_f_term.append(vf_vars[idx] - vf_n)
        else:
            v_f_term.append(vf_vars[idx])

        if vt_n is not None:
            v_t_term.append(vt_vars[idx] - vt_n)
        else:
            v_t_term.append(vt_vars[idx])

    # ------------------------------------------------------------------
    # Coupled winding dynamics
    #
    # [l1  m12] [di_f/dt] = [vf - r1*i_f]
    # [m12 l2 ] [di_t/dt]   [vt - r2*i_t]
    #
    # Inverting the inductance matrix gives negative signs in the cross terms.
    # ------------------------------------------------------------------
    state_eqs_f: list[Expr] = []
    state_eqs_t: list[Expr] = []
    det_l: Expr = l1 * l2 - m12 * m12

    for idx in range(3):
        primary_rhs: Expr = v_f_term[idx] - r1 * i_f[idx]
        secondary_rhs: Expr = v_t_term[idx] - r2 * i_t[idx]

        state_eqs_f.append((l2 * primary_rhs - m12 * secondary_rhs) / (det_l + c_eps))
        state_eqs_t.append((l1 * secondary_rhs - m12 * primary_rhs) / (det_l + c_eps))

    templ.block.state_eqs = state_eqs_f + state_eqs_t

    # ------------------------------------------------------------------
    # Port-current algebraic equations
    #
    # In this simplified EMT model, the port currents are exactly the series
    # winding currents. The primary-side shunt branch is intentionally omitted.
    # ------------------------------------------------------------------
    alg_eqs: list[Expr] = []
    for idx in range(3):
        alg_eqs.append(if_act[idx] - (i_f[idx] + gm * v_f_term[idx]))
        alg_eqs.append(it_act[idx] - i_t[idx])

    if if_n_act is not None:
        alg_eqs.append(if_n_act + if_act[0] + if_act[1] + if_act[2])
    else:
        pass

    if it_n_act is not None:
        alg_eqs.append(it_n_act + it_act[0] + it_act[1] + it_act[2])
    else:
        pass

    templ.block.algebraic_eqs = alg_eqs
    output_vars: list[Var] = list()
    if if_n_act is not None:
        output_vars.append(if_n_act)
    else:
        pass

    output_vars.extend(if_act)

    if it_n_act is not None:
        output_vars.append(it_n_act)
    else:
        pass

    output_vars.extend(it_act)
    templ.block.out_vars = output_vars

    # ------------------------------------------------------------------
    # External mapping for network stamping / PF seeding
    # ------------------------------------------------------------------
    templ.block.external_mapping = dict({
        VarPowerFlowRefferenceType.if_N: if_n_act,
        VarPowerFlowRefferenceType.if_A: if_act[0],
        VarPowerFlowRefferenceType.if_B: if_act[1],
        VarPowerFlowRefferenceType.if_C: if_act[2],
        VarPowerFlowRefferenceType.it_N: it_n_act,
        VarPowerFlowRefferenceType.it_A: it_act[0],
        VarPowerFlowRefferenceType.it_B: it_act[1],
        VarPowerFlowRefferenceType.it_C: it_act[2],
    })
    templ.block.external_mapping[VarPowerFlowRefferenceType.vf_N] = vf_n
    templ.block.external_mapping[VarPowerFlowRefferenceType.vt_N] = vt_n
    templ.block.external_mapping[VarPowerFlowRefferenceType.vf_A] = vf_vars[0]
    templ.block.external_mapping[VarPowerFlowRefferenceType.vf_B] = vf_vars[1]
    templ.block.external_mapping[VarPowerFlowRefferenceType.vf_C] = vf_vars[2]
    templ.block.external_mapping[VarPowerFlowRefferenceType.vt_A] = vt_vars[0]
    templ.block.external_mapping[VarPowerFlowRefferenceType.vt_B] = vt_vars[1]
    templ.block.external_mapping[VarPowerFlowRefferenceType.vt_C] = vt_vars[2]

    # ------------------------------------------------------------------
    # State initialization
    #
    # Since the EMT model omits the shunt branch, initialize the secondary
    # winding current directly from the secondary port current and initialize
    # the primary winding current from the secondary current referred through
    # the total voltage ratio.
    #
    # With branch currents positive when leaving the bus:
    #   primary series current ~= -(secondary port current) / total_voltage_ratio
    # ------------------------------------------------------------------
    init_eqs: Dict[Var, Expr] = dict()
    for idx in range(3):
        init_eqs[i_f[idx]] = if_act[idx] - gm * v_f_term[idx]
        init_eqs[i_t[idx]] = it_act[idx]

    templ.block.init_eqs = init_eqs

    # ------------------------------------------------------------------
    # Derivative initialization aligned with runtime dynamics
    # ------------------------------------------------------------------
    diff_init_eqs: Dict[Var, Expr] = dict()
    for idx in range(3):
        primary_rhs: Expr = v_f_term[idx] - r1 * i_f[idx]
        secondary_rhs: Expr = v_t_term[idx] - r2 * i_t[idx]

        diff_init_eqs[di_f[idx]] = (l2 * primary_rhs - m12 * secondary_rhs) / (det_l + c_eps)
        diff_init_eqs[di_t[idx]] = (l1 * secondary_rhs - m12 * primary_rhs) / (det_l + c_eps)

    templ.block.diff_init_eqs = diff_init_eqs

    return templ
