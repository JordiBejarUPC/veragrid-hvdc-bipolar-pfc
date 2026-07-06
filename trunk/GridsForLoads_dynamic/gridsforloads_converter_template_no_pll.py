# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Utils.Symbolic.symbolic import cos, sin, Expr
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import hard_saturation, sampled_value
from VeraGridEngine.enumerations import VarPowerFlowReferenceType, DeviceType


def _wrap_angle_expr(angle: Expr) -> Expr:
    """Wrap one angle expression to ``[-pi, pi]``.

    :param angle: Input angle expression in radians.
    :return: Wrapped angle expression in radians.
    """
    return sym.atan2(sin(angle), cos(angle))


def get_trafo_grid_connection_G4L(vf: VarFactory, name: str = "G4L_transformer") -> EmtModelTemplate:
    """
    Equivalent transformer where the load is connected.
    """

    templ = EmtModelTemplate()
    templ.tpe = DeviceType.LineDevice
    templ.name = name
    templ.block.name = name

    c0 = vf.add_const(0.0)

    eps = vf.add_const(1e-9)

    # Follow the built-in EMT template pattern: fixed coefficients used only by
    # this custom branch are embedded as symbolic constants inside the equations
    # instead of introducing extra parameter vars that must be registered in the
    # compiler maps.
    omega_base = 2 * np.pi * 50.0
    # R_ser = vf.add_const(0.1 / 10.0)
    # X_ser = vf.add_const(1.0 / 10.0)
    # Linv = vf.add_const(omega_base / (1.0 / 10.0))
    # C_sh = vf.add_const((2.0 / 15.0) / (2.0 * omega_base))
    # R_sh = vf.add_const(0.05)
    PU_Z_TO_EMT = 3.0
    PU_Y_TO_EMT = 1.0 / 3.0

    R_ser_pu = PU_Z_TO_EMT * (0.1 / 10.0)  # 0.03
    X_ser_pu = PU_Z_TO_EMT * (1.0 / 10.0)  # 0.30

    R_ser = vf.add_const(R_ser_pu)
    X_ser = vf.add_const(X_ser_pu)
    Linv = vf.add_const(omega_base / X_ser_pu)

    # Simulink C_f gives standard susceptance B = 1/15 pu.
    # In VeraGrid EMT phase/current signal base, admittance is 1/3 of standard pu.
    C_sh = vf.add_const((PU_Y_TO_EMT * (1.0 / 15.0)) / omega_base)  # 1/(45*omega)

    # Simulink R_Cf = 0.05*Zbase; in the EMT signal impedance base it is 3x.
    R_sh = vf.add_const(PU_Z_TO_EMT * 0.05)  # 0.15

    # grid connection voltages
    v_f_A = vf.add_var(name=f"v_f_A_{name}", reference=VarPowerFlowReferenceType.vf_A)
    v_f_B = vf.add_var(name=f"v_f_B_{name}", reference=VarPowerFlowReferenceType.vf_B)
    v_f_C = vf.add_var(name=f"v_f_C_{name}", reference=VarPowerFlowReferenceType.vf_C)

    # VSC connection voltages
    v_t_A = vf.add_var(name=f"v_t_A_{name}", reference=VarPowerFlowReferenceType.vt_A)
    v_t_B = vf.add_var(name=f"v_t_B_{name}", reference=VarPowerFlowReferenceType.vt_B)
    v_t_C = vf.add_var(name=f"v_t_C_{name}", reference=VarPowerFlowReferenceType.vt_C)

    inputs = [v_f_A, v_f_B, v_f_C, v_t_A, v_t_B, v_t_C]

    # from and to currents
    i_f_A = vf.add_var(name=f"i_f_A_{name}", reference=VarPowerFlowReferenceType.if_A)
    i_f_B = vf.add_var(name=f"i_f_B_{name}", reference=VarPowerFlowReferenceType.if_B)
    i_f_C = vf.add_var(name=f"i_f_C_{name}", reference=VarPowerFlowReferenceType.if_C)
    i_t_A = vf.add_var(name=f"i_t_A_{name}", reference=VarPowerFlowReferenceType.it_A)
    i_t_B = vf.add_var(name=f"i_t_B_{name}", reference=VarPowerFlowReferenceType.it_B)
    i_t_C = vf.add_var(name=f"i_t_C_{name}", reference=VarPowerFlowReferenceType.it_C)

    # series current and derivative
    i_ser_A = vf.add_var(name=f"i_ser_A_{name}")
    i_ser_B = vf.add_var(name=f"i_ser_B_{name}")
    i_ser_C = vf.add_var(name=f"i_ser_C_{name}")
    di_ser_A = vf.add_diff_var(name=f"di_ser_A_{name}", base_var=i_ser_A)
    di_ser_B = vf.add_diff_var(name=f"di_ser_B_{name}", base_var=i_ser_B)
    di_ser_C = vf.add_diff_var(name=f"di_ser_C_{name}", base_var=i_ser_C)

    # shunt series RC branch on the converter side
    i_cap_t_A = vf.add_var(name=f"i_cap_t_A_{name}")
    i_cap_t_B = vf.add_var(name=f"i_cap_t_B_{name}")
    i_cap_t_C = vf.add_var(name=f"i_cap_t_C_{name}")
    q_t_A = vf.add_var(name=f"q_t_A_{name}")
    q_t_B = vf.add_var(name=f"q_t_B_{name}")
    q_t_C = vf.add_var(name=f"q_t_C_{name}")
    dq_t_A = vf.add_diff_var(name=f"dq_t_A_{name}", base_var=q_t_A)
    dq_t_B = vf.add_diff_var(name=f"dq_t_B_{name}", base_var=q_t_B)
    dq_t_C = vf.add_diff_var(name=f"dq_t_C_{name}", base_var=q_t_C)

    # P and Q ac
    Pac = vf.add_var(name=f"Pac_{name}")
    Qac = vf.add_var(name=f"Qac_{name}")

    templ.block = Block(
        # --------------------------------------------------------------------------------------
        # STATE EQUATIONS (seconds + pu)
        # --------------------------------------------------------------------------------------
        state_eqs=[
            Linv * (v_f_A - v_t_A - R_ser * i_ser_A),
            Linv * (v_f_B - v_t_B - R_ser * i_ser_B),
            Linv * (v_f_C - v_t_C - R_ser * i_ser_C),
            i_cap_t_A,
            i_cap_t_B,
            i_cap_t_C,
        ],
        state_vars=[i_ser_A, i_ser_B, i_ser_C, q_t_A, q_t_B, q_t_C],
        diff_vars = [di_ser_A, di_ser_B, di_ser_C, dq_t_A, dq_t_B, dq_t_C],

        # --------------------------------------------------------------------------------------
        # ALGEBRAIC EQUATIONS
        # --------------------------------------------------------------------------------------
        algebraic_eqs=[
            # shunt RC equations
            q_t_A - C_sh * (v_t_A - R_sh * i_cap_t_A),
            q_t_B - C_sh * (v_t_B - R_sh * i_cap_t_B),
            q_t_C - C_sh * (v_t_C - R_sh * i_cap_t_C),
            # current balance in the "from" node
            i_f_A - i_ser_A,
            i_f_B - i_ser_B,
            i_f_C - i_ser_C,
            # current balance in the "to" node
            i_t_A - (-i_ser_A + i_cap_t_A),
            i_t_B - (-i_ser_B + i_cap_t_B),
            i_t_C - (-i_ser_C + i_cap_t_C),
            Pac - (v_t_A*i_t_A + v_t_B*i_t_B + v_t_C*i_t_C),
            Qac - (1 / np.sqrt(3)) * ((v_t_A - v_t_B) * i_t_C +
                                     (v_t_B - v_t_C) * i_t_A +
                                     (v_t_C - v_t_A) * i_t_B),
        ],
        algebraic_vars=[i_cap_t_A, i_cap_t_B, i_cap_t_C, i_f_A, i_f_B, i_f_C, i_t_A, i_t_B, i_t_C, Pac, Qac],
        in_vars=inputs,
        out_vars=[i_f_A, i_f_B, i_f_C, i_t_A, i_t_B, i_t_C],
        init_eqs={
            i_ser_A: i_f_A,
            i_ser_B: i_f_B,
            i_ser_C: i_f_C,
            i_cap_t_A: C_sh * omega_base * (v_t_C - v_t_B) / np.sqrt(3),
            i_cap_t_B: C_sh * omega_base * (v_t_A - v_t_C) / np.sqrt(3),
            i_cap_t_C: C_sh * omega_base * (v_t_B - v_t_A) / np.sqrt(3),
            q_t_A: C_sh * (v_t_A - R_sh * i_cap_t_A),
            q_t_B: C_sh * (v_t_B - R_sh * i_cap_t_B),
            q_t_C: C_sh * (v_t_C - R_sh * i_cap_t_C),
            Pac: v_t_A*i_t_A + v_t_B*i_t_B + v_t_C*i_t_C,
            Qac: (1 / np.sqrt(3)) * ((v_t_A - v_t_B) * i_t_C +
                                     (v_t_B - v_t_C) * i_t_A +
                                     (v_t_C - v_t_A) * i_t_B),
        },
        diff_init_eqs={
            di_ser_A: Linv * (v_f_A - v_t_A - R_ser * i_ser_A),
            di_ser_B: Linv * (v_f_B - v_t_B - R_ser * i_ser_B),
            di_ser_C: Linv * (v_f_C - v_t_C - R_ser * i_ser_C),
            dq_t_A: i_cap_t_A,
            dq_t_B: i_cap_t_B,
            dq_t_C: i_cap_t_C,
        },
    )

    templ.block.external_mapping = {
        VarPowerFlowReferenceType.vf_N: None,
        VarPowerFlowReferenceType.vf_A: v_f_A,
        VarPowerFlowReferenceType.vf_B: v_f_B,
        VarPowerFlowReferenceType.vf_C: v_f_C,
        VarPowerFlowReferenceType.vt_N: None,
        VarPowerFlowReferenceType.vt_A: v_t_A,
        VarPowerFlowReferenceType.vt_B: v_t_B,
        VarPowerFlowReferenceType.vt_C: v_t_C,
        VarPowerFlowReferenceType.if_N: None,
        VarPowerFlowReferenceType.if_A: i_f_A,
        VarPowerFlowReferenceType.if_B: i_f_B,
        VarPowerFlowReferenceType.if_C: i_f_C,
        VarPowerFlowReferenceType.it_N: None,
        VarPowerFlowReferenceType.it_A: i_t_A,
        VarPowerFlowReferenceType.it_B: i_t_B,
        VarPowerFlowReferenceType.it_C: i_t_C,
        VarPowerFlowReferenceType.Pt: Pac,
        VarPowerFlowReferenceType.Qt: Qac,
    }

    return templ


def get_grid_side_converter_GFL(vf: VarFactory, name: str = "G4L_grid_side_converter") -> EmtModelTemplate:
    """
    VSC average model

    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.VscDevice
    templ.name = name

    templ.block.name = name

    c0 = vf.add_const(0.0)
    eps = vf.add_const(1e-9)

    PU_Z_TO_EMT = 3.0

    R_f_pu = PU_Z_TO_EMT * (0.1 / 10.0)  # 0.03
    X_f_pu = PU_Z_TO_EMT * (1.0 / 10.0)  # 0.30
    omega_base = 2 * np.pi * 50
    R_f = vf.add_const(R_f_pu)
    Linv_f = vf.add_const(omega_base / X_f_pu)

    v_A = vf.add_var(name=f"v_A_{name}", reference=VarPowerFlowReferenceType.v_A)
    v_B = vf.add_var(name=f"v_B_{name}", reference=VarPowerFlowReferenceType.v_B)
    v_C = vf.add_var(name=f"v_C_{name}", reference=VarPowerFlowReferenceType.v_C)
    v_dc = vf.add_var(name=f"v_dc_{name}", reference=VarPowerFlowReferenceType.Vdc)
    v_con_A = vf.add_var(name=f"v_con_A_{name}")
    v_con_B = vf.add_var(name=f"v_con_B_{name}")
    v_con_C = vf.add_var(name=f"v_con_C_{name}")

    inputs = [v_A, v_B, v_C, v_dc, v_con_A, v_con_B, v_con_C]

    i_A = vf.add_var(name=f"i_f_A_{name}", reference=VarPowerFlowReferenceType.i_A)
    i_B = vf.add_var(name=f"i_f_B_{name}", reference=VarPowerFlowReferenceType.i_B)
    i_C = vf.add_var(name=f"i_f_C_{name}", reference=VarPowerFlowReferenceType.i_C)
    i_dc = vf.add_var(name=f"i_dc_{name}", reference=VarPowerFlowReferenceType.Idc)

    i_ser_A = vf.add_var(name=f"i_ser_A_{name}")
    i_ser_B = vf.add_var(name=f"i_ser_B_{name}")
    i_ser_C = vf.add_var(name=f"i_ser_C_{name}")
    di_ser_A = vf.add_diff_var(name=f"di_ser_A_{name}", base_var=i_ser_A)
    di_ser_B = vf.add_diff_var(name=f"di_ser_B_{name}", base_var=i_ser_B)
    di_ser_C = vf.add_diff_var(name=f"di_ser_C_{name}", base_var=i_ser_C)

    Pac_bus =  vf.add_var(name=f"Pac_bus_{name}")
    Pac = vf.add_var(name=f"Pac_{name}")
    i_dc_mode = vf.add_var(name=f"i_dc_mode_{name}")

    templ.block = Block(
        state_eqs=[
            Linv_f * (v_con_A - v_A - R_f * i_ser_A),
            Linv_f * (v_con_B - v_B - R_f * i_ser_B),
            Linv_f * (v_con_C - v_C - R_f * i_ser_C),
        ],
        state_vars=[i_ser_A, i_ser_B, i_ser_C],
        diff_vars=[di_ser_A, di_ser_B, di_ser_C],
        algebraic_eqs=[
            i_A - i_ser_A,
            i_B - i_ser_B,
            i_C - i_ser_C,
            Pac - (v_con_A * i_A + v_con_B * i_B + v_con_C * i_C),
            i_dc - i_dc_mode,
            Pac_bus - (v_A * i_A + v_B * i_B + v_C * i_C),
        ],
        algebraic_vars=[i_A, i_B, i_C, Pac, i_dc, Pac_bus],
        in_vars=inputs,
        out_vars=[i_A, i_B, i_C, i_dc, Pac_bus, Pac],
        init_eqs={
            i_ser_A: i_A,
            i_ser_B: i_B,
            i_ser_C: i_C,
            Pac_bus: v_A * i_A + v_B * i_B + v_C * i_C,
            Pac: v_con_A * i_A + v_con_B * i_B + v_con_C * i_C,
            i_dc: -Pac / sym.max(v_dc, eps),
        },
        diff_init_eqs={
            di_ser_A: Linv_f * (v_con_A - v_A - R_f * i_ser_A),
            di_ser_B: Linv_f * (v_con_B - v_B - R_f * i_ser_B),
            di_ser_C: Linv_f * (v_con_C - v_C - R_f * i_ser_C),
        },
        mode_dict={
            i_dc_mode: i_dc,
        },
        procedural_logic=[
            sampled_value(
                output=i_dc_mode,
                source=-Pac / sym.max(v_dc, eps),
                name=f"i_dc_sample_{name}",
            ),
        ],
    )

    templ.block.external_mapping = {
        VarPowerFlowReferenceType.v_A: v_A,
        VarPowerFlowReferenceType.v_B: v_B,
        VarPowerFlowReferenceType.v_C: v_C,
        VarPowerFlowReferenceType.i_A: i_A,
        VarPowerFlowReferenceType.i_B: i_B,
        VarPowerFlowReferenceType.i_C: i_C,
    }

    return templ


def get_load_side_converter_GFL(vf: VarFactory, name: str = "G4L_load_side_converter") -> EmtModelTemplate:
    """
    Load side converter: load current source + DC capacitor
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.LoadDevice
    templ.name = name

    templ.block.name = name

    c0 = vf.add_const(0.0)
    eps = vf.add_const(1e-9)

    Cdc = vf.add_var(name=f"Cdc_{name}")
    event_dict = {
        Cdc: vf.add_const(0.04),
    }

    v_dc = vf.add_var(name=f"v_dc_{name}", reference=VarPowerFlowReferenceType.Vdc)
    i_dc_L = vf.add_var(name=f"i_dc_L_{name}")
    i_dc_vsc = vf.add_var(name=f"i_dc_vsc_{name}")

    inputs = [i_dc_vsc, i_dc_L]

    i_cap_dc = vf.add_var(name=f"i_cap_dc_{name}")
    q_cap = vf.add_var(name=f"q_cap_{name}")
    dq_cap = vf.add_diff_var(name=f"dq_cap_{name}", base_var=q_cap)


    templ.block = Block(
        state_eqs=[
            i_cap_dc,
        ],
        state_vars=[q_cap],
        diff_vars=[dq_cap],
        algebraic_eqs=[
            q_cap - Cdc * v_dc,
            i_dc_vsc - i_dc_L - i_cap_dc,
        ],
        algebraic_vars=[i_cap_dc, v_dc],
        in_vars=inputs,
        out_vars=[v_dc],
        init_eqs={
            i_cap_dc: i_dc_vsc - i_dc_L,
            q_cap: Cdc * vf.add_const(1.0),
            v_dc: vf.add_const(1.0),
        },
        diff_init_eqs={
            dq_cap:i_cap_dc,
        },
        event_dict=event_dict,
    )

    return templ


def get_load_side_converter_control_GFL(vf: VarFactory, name: str = "G4L_load_side_converter_control") -> EmtModelTemplate:
    """
    Load side converter control (PI)
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    templ.block.name = name

    c0 = vf.add_const(0.0)
    eps = vf.add_const(1e-9)

    v_dc_ref = vf.add_var(name=f"v_dc_ref_{name}")

    C_DC = 0.04
    chi_E = 0.707
    tau_E = 0.1
    w_E: float = 4 / (chi_E * tau_E)
    Kp_E = vf.add_var(name=f"Kp_E_{name}")
    Ki_E = vf.add_var(name=f"Ki_E_{name}")
    event_dict = {
        v_dc_ref: vf.add_const(1.0),
        Kp_E: vf.add_const(C_DC * chi_E * w_E),
        Ki_E: vf.add_const((C_DC / 2) * w_E * w_E),
    }


    v_dc = vf.add_var(name=f"v_dc_{name}", reference=VarPowerFlowReferenceType.Vdc)
    Pac = vf.add_var(name=f"Pac_{name}")
    i_dc_L = vf.add_var(name=f"i_dc_L_{name}")

    inputs = [v_dc, Pac]

    p_dc = vf.add_var(name=f"p_dc_{name}")
    i_dc_L_mode = vf.add_var(name=f"i_dc_L_mode_{name}")
    err = vf.add_var(name=f"err_{name}")
    x_e = vf.add_var(name=f"x_e_{name}")
    dx_e = vf.add_diff_var(name=f"dx_e_{name}", base_var=x_e)

    templ.block = Block(
        state_eqs=[
            Ki_E * err,
        ],
        state_vars=[x_e],
        diff_vars=[dx_e],
        algebraic_eqs=[
            err - (v_dc_ref*v_dc_ref - v_dc*v_dc),
            p_dc -(Kp_E*err + x_e),
            i_dc_L - i_dc_L_mode,
        ],
        algebraic_vars=[err, p_dc, i_dc_L],
        in_vars=inputs,
        out_vars=[i_dc_L],
        init_eqs={
            p_dc: Pac,
            i_dc_L: -p_dc / sym.max(v_dc, eps),
            err: c0,
            x_e: p_dc,
        },
        diff_init_eqs={
            dx_e: err,
        },
        event_dict=event_dict,
        mode_dict={
            i_dc_L_mode: i_dc_L,
        },
        procedural_logic=[
            sampled_value(
                output=i_dc_L_mode,
                source= -p_dc / sym.max(v_dc, eps),
                name=f"i_dc_L_sample_{name}",
            ),
        ],
    )

    return templ


def get_grid_side_converter_control_GFL(vf: VarFactory, name: str = "G4L_grid_side_converter_control") -> EmtModelTemplate:
    """
    This function connects all converter controls:
    - Clark-park transform
    - VSM with constant synchronous speed
    - Virtual admittance - current limitation - current loop
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name
    templ.block.name = name


    clark_park_transforms_mdl = get_clark_park_transforms_qd_GFL(vf=vf).block
    PLL_mdl = get_PLL_GFL(vf=vf).block
    VA_mdl = get_virtual_admittance_GFL(vf=vf).block
    current_limiter_mdl = get_current_limiter_GFL(vf=vf).block
    current_loop_mdl = get_current_loop_GFL(vf=vf).block

    templ.block.in_vars = [clark_park_transforms_mdl.in_vars[0],
                           clark_park_transforms_mdl.in_vars[1],
                           clark_park_transforms_mdl.in_vars[2],
                           clark_park_transforms_mdl.in_vars[3],
                           clark_park_transforms_mdl.in_vars[4],
                           clark_park_transforms_mdl.in_vars[5],
                           PLL_mdl.in_vars[6],
                           ]
    templ.block.out_vars = [current_loop_mdl.out_vars[0],
                            current_loop_mdl.out_vars[1],
                            current_loop_mdl.out_vars[2],
                            current_loop_mdl.out_vars[3],
                            current_loop_mdl.out_vars[4],
                            current_loop_mdl.out_vars[5],
                            ]

    vf.add_connection(clark_park_transforms_mdl.in_vars[6], PLL_mdl.out_vars[0])
    vf.add_connection(current_loop_mdl.in_vars[4], PLL_mdl.out_vars[0])
    vf.add_connection(PLL_mdl.in_vars[0], clark_park_transforms_mdl.in_vars[0])
    vf.add_connection(PLL_mdl.in_vars[1], clark_park_transforms_mdl.in_vars[1])
    vf.add_connection(PLL_mdl.in_vars[2], clark_park_transforms_mdl.in_vars[2])
    vf.add_connection(PLL_mdl.in_vars[3], clark_park_transforms_mdl.in_vars[3])
    vf.add_connection(PLL_mdl.in_vars[4], clark_park_transforms_mdl.in_vars[4])
    vf.add_connection(PLL_mdl.in_vars[5], clark_park_transforms_mdl.in_vars[5])
    vf.add_connection(current_loop_mdl.in_vars[5], PLL_mdl.out_vars[1])
    vf.add_connection(VA_mdl.in_vars[0], clark_park_transforms_mdl.out_vars[0])
    vf.add_connection(current_loop_mdl.in_vars[0], clark_park_transforms_mdl.out_vars[0])
    vf.add_connection(VA_mdl.in_vars[1], clark_park_transforms_mdl.out_vars[1])
    vf.add_connection(current_loop_mdl.in_vars[1], clark_park_transforms_mdl.out_vars[1])
    vf.add_connection(current_loop_mdl.in_vars[2], clark_park_transforms_mdl.out_vars[2])
    vf.add_connection(current_loop_mdl.in_vars[3], clark_park_transforms_mdl.out_vars[3])
    vf.add_connection(current_limiter_mdl.in_vars[0], VA_mdl.out_vars[0])
    vf.add_connection(current_limiter_mdl.in_vars[1], VA_mdl.out_vars[1])
    vf.add_connection(current_loop_mdl.in_vars[6], current_limiter_mdl.out_vars[0])
    vf.add_connection(current_loop_mdl.in_vars[7], current_limiter_mdl.out_vars[1])

    templ.block.children.append(clark_park_transforms_mdl)
    templ.block.children.append(PLL_mdl)
    templ.block.children.append(VA_mdl)
    templ.block.children.append(current_limiter_mdl)
    templ.block.children.append(current_loop_mdl)

    templ.block.external_mapping = {
        VarPowerFlowReferenceType.v_A: clark_park_transforms_mdl.in_vars[0],
        VarPowerFlowReferenceType.v_B: clark_park_transforms_mdl.in_vars[1],
        VarPowerFlowReferenceType.v_C: clark_park_transforms_mdl.in_vars[2],
        VarPowerFlowReferenceType.i_A: clark_park_transforms_mdl.in_vars[3],
        VarPowerFlowReferenceType.i_B: clark_park_transforms_mdl.in_vars[4],
        VarPowerFlowReferenceType.i_C: clark_park_transforms_mdl.in_vars[5],
    }

    return templ


def get_clark_park_transforms_qd_GFL(vf: VarFactory, name: str = "G4L_clark_park_transforms_qd") -> EmtModelTemplate:
    """
    clark - park transforms to qd axis
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    templ.block.name = name

    c0 = vf.add_const(0.0)
    eps = vf.add_const(1e-9)

    v_A = vf.add_var(name=f"v_A_{name}", reference=VarPowerFlowReferenceType.v_A)
    v_B = vf.add_var(name=f"v_B_{name}", reference=VarPowerFlowReferenceType.v_B)
    v_C = vf.add_var(name=f"v_C_{name}", reference=VarPowerFlowReferenceType.v_C)
    i_A = vf.add_var(name=f"i_f_A_{name}", reference=VarPowerFlowReferenceType.i_A)
    i_B = vf.add_var(name=f"i_f_B_{name}", reference=VarPowerFlowReferenceType.i_B)
    i_C = vf.add_var(name=f"i_f_C_{name}", reference=VarPowerFlowReferenceType.i_C)
    phase_pll = vf.add_var(name=f"phase_pll_{name}")

    inputs = [v_A, v_B, v_C, i_A, i_B, i_C, phase_pll]

    alpha_v = vf.add_var(name=f"alpha_v_{name}")
    beta_v = vf.add_var(name=f"beta_v_{name}")
    v_d = vf.add_var(name=f"v_d_{name}")
    v_q = vf.add_var(name=f"v_q_{name}")
    alpha_i = vf.add_var(name=f"alpha_i_{name}")
    beta_i = vf.add_var(name=f"beta_i_{name}")
    i_d = vf.add_var(name=f"i_d_{name}")
    i_q = vf.add_var(name=f"i_q_{name}")

    templ.block = Block(
        state_eqs=[],
        state_vars=[],
        diff_vars=[],
        algebraic_eqs=[
            alpha_v - ((1 / 3) * (2 * v_A - v_B - v_C)),
            beta_v - ((1 / 3) * (-np.sqrt(3) * v_B + np.sqrt(3) * v_C)),
            v_q - (alpha_v * cos(phase_pll) - beta_v * sin(phase_pll)),
            v_d - (alpha_v * sin(phase_pll) + beta_v * cos(phase_pll)),
            alpha_i - ((1 / 3) * (2 * i_A - i_B - i_C)),
            beta_i - ((1 / 3) * (-np.sqrt(3) * i_B + np.sqrt(3) * i_C)),
            i_q - (alpha_i * cos(phase_pll) - beta_i * sin(phase_pll)),
            i_d - (alpha_i * sin(phase_pll) + beta_i * cos(phase_pll)),
        ],
        algebraic_vars=[alpha_v, beta_v, v_q, v_d,
                        alpha_i, beta_i, i_q, i_d,],
        in_vars=inputs,
        out_vars=[v_q, v_d, i_q, i_d],
        init_eqs={
            alpha_v: (1 / 3) * (2 * v_A - v_B - v_C),
            beta_v: (1 / 3) * (-np.sqrt(3) * v_B + np.sqrt(3) * v_C),
            alpha_i: (1 / 3) * (2 * i_A - i_B - i_C),
            beta_i: (1 / 3) * (-np.sqrt(3) * i_B + np.sqrt(3) * i_C),
            v_q: alpha_v * cos(phase_pll) - beta_v * sin(phase_pll),
            v_d: alpha_v * sin(phase_pll) + beta_v * cos(phase_pll),
            i_q: alpha_i * cos(phase_pll) - beta_i * sin(phase_pll),
            i_d: alpha_i * sin(phase_pll) + beta_i * cos(phase_pll),
        },
    )

    templ.block.external_mapping = {
        VarPowerFlowReferenceType.v_A: v_A,
        VarPowerFlowReferenceType.v_B: v_B,
        VarPowerFlowReferenceType.v_C: v_C,
        VarPowerFlowReferenceType.i_A: i_A,
        VarPowerFlowReferenceType.i_B: i_B,
        VarPowerFlowReferenceType.i_C: i_C,
    }

    return templ


def get_PLL_GFL(vf: VarFactory, name: str = "G4L_PLL") -> EmtModelTemplate:
    """
    VSM-only angle generator with constant synchronous speed.
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    templ.block.name = name

    c0 = vf.add_const(0.0)
    eps = vf.add_const(1e-9)

    v_A = vf.add_var(name=f"v_A_{name}", reference=VarPowerFlowReferenceType.v_A)
    v_B = vf.add_var(name=f"v_B_{name}", reference=VarPowerFlowReferenceType.v_B)
    v_C = vf.add_var(name=f"v_C_{name}", reference=VarPowerFlowReferenceType.v_C)
    i_A = vf.add_var(name=f"i_A_{name}", reference=VarPowerFlowReferenceType.i_A)
    i_B = vf.add_var(name=f"i_B_{name}", reference=VarPowerFlowReferenceType.i_B)
    i_C = vf.add_var(name=f"i_C_{name}", reference=VarPowerFlowReferenceType.i_C)
    Pac = vf.add_var(name=f"Pac_{name}")
    P_ref = vf.add_var(name=f"P_ref_{name}")

    inputs =[v_A, v_B, v_C, i_A, i_B, i_C, Pac]

    phase_pll = vf.add_var(name=f"phase_pll_{name}")
    omega_pll = vf.add_var(name=f"omega_pll_{name}")
    d_phase_pll = vf.add_diff_var(name=f"d_phase_pll_{name}", base_var=phase_pll)

    Sb_va = 2000000.0
    omega_expr = 2 * np.pi * 50
    Vdc_ref_si = 1200.0
    C_DC_si = Sb_va * 0.02 * 2 / (Vdc_ref_si * Vdc_ref_si)
    C_pu = C_DC_si * Vdc_ref_si * Vdc_ref_si / Sb_va
    Sb_expr = 1.0
    Zaparent = 0.5
    chi = 0.8
    kH = (1.935 / 2 / 50) / (1 - (665 * 665 / (Vdc_ref_si * Vdc_ref_si)))
    kP = chi * 2 * np.sqrt(kH * (1 / Zaparent) * omega_expr * 2 / C_pu) / (kH * (1 / Zaparent) * omega_expr)

    k_d = vf.add_var(name=f"k_d_{name}")
    omega_ref = vf.add_var(name=f"omega_ref_{name}")
    H = vf.add_var(name=f"H_{name}")
    Sb = vf.add_var(name=f"Sb_{name}")
    k_p = vf.add_var(name=f"k_p_{name}")

    w_pll = vf.add_var(name=f"w_pll_{name}")

    event_dict = {
        P_ref: vf.add_const(-0.8),
        k_d: vf.add_const(kP * (C_pu / 2 * (1 / Zaparent) * omega_expr)),
        omega_ref: vf.add_const(omega_expr),
        H: vf.add_const(C_pu / (kH * 4)),
        Sb: vf.add_const(Sb_expr),
        k_p: vf.add_const(20),
        w_pll: omega_ref,
    }

    alpha = vf.add_var(name=f"alpha_{name}")
    beta =  vf.add_var(name=f"beta_{name}")
    x = vf.add_var(name=f"x_{name}")
    y = vf.add_var(name=f"y_{name}")
    dy = vf.add_diff_var(name=f"dy_{name}", base_var=y)

    theta_v = sym.atan2(-beta, alpha)
    alpha_i = (1 / 3) * (2 * i_A - i_B - i_C)
    beta_i = (1 / 3) * (-np.sqrt(3) * i_B + np.sqrt(3) * i_C)
    i_q0 = alpha_i * cos(theta_v) - beta_i * sin(theta_v)
    i_d0 = alpha_i * sin(theta_v) + beta_i * cos(theta_v)
    v_mag = sym.sqrt(alpha * alpha + beta * beta)

    v_q_ref_init = vf.add_const(np.sqrt(2))
    v_d_ref_init = vf.add_const(0.0)
    z_virtual = 1.0
    r_l_virtual = 0.1
    lv_expr = z_virtual / omega_expr
    rv_expr = z_virtual * r_l_virtual
    Xv = vf.add_const(lv_expr * omega_expr)
    Rv = vf.add_const(rv_expr)
    D = sym.max(Rv * Rv + Xv * Xv, eps)
    c0_q = (Rv * v_q_ref_init - Xv * v_d_ref_init) / D
    c0_d = (Xv * v_q_ref_init + Rv * v_d_ref_init) / D
    c1_q = Rv * v_mag / D
    c1_d = Xv * v_mag / D
    a_q = c0_q - i_q0
    a_d = c0_d - i_d0
    delta_raw = sym.atan2(a_d, a_q) - sym.atan2(c1_d, c1_q)
    delta_vsm0 = _wrap_angle_expr(delta_raw)

    templ.block = Block(
        state_eqs=[
            ((1 - y) * k_p + P_ref - Pac + x) / (2 * sym.max(H, eps)),
            omega_pll,
        ],
        state_vars=[y, phase_pll],
        diff_vars=[dy, d_phase_pll],
        algebraic_eqs=[
            alpha - ((1/3) * (2*v_A - v_B - v_C)),
            beta - ((1/3) * (-np.sqrt(3)*v_B + np.sqrt(3)*v_C)),
            x - ((w_pll / sym.max(omega_ref, eps)) - y) * k_d,
            omega_pll - (y * omega_ref),

        ],
        algebraic_vars=[alpha, beta, x, omega_pll],
        in_vars=inputs,
        out_vars=[phase_pll, omega_pll],
        init_eqs={
            alpha: (1/3) * (2*v_A - v_B - v_C),
            beta: (1/3) * (-np.sqrt(3)*v_B + np.sqrt(3)*v_C),
            x: c0,
            y: vf.add_const(1.0),
            phase_pll: theta_v + delta_vsm0,
            omega_pll: omega_ref,

        },
        diff_init_eqs={
            dy: c0,
            d_phase_pll: omega_ref,
        },
        event_dict=event_dict,
    )

    templ.block.external_mapping = {
        VarPowerFlowReferenceType.v_A: v_A,
        VarPowerFlowReferenceType.v_B: v_B,
        VarPowerFlowReferenceType.v_C: v_C,
        VarPowerFlowReferenceType.i_A: i_A,
        VarPowerFlowReferenceType.i_B: i_B,
        VarPowerFlowReferenceType.i_C: i_C,
    }

    return templ


def get_virtual_admittance_GFL(vf: VarFactory, name: str = "G4L_Virtual_admittance") -> EmtModelTemplate:
    """
    Virtual admittance block
    """

    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    templ.block.name = name

    c0 = vf.add_const(0.0)
    eps = vf.add_const(1e-9)

    v_q = vf.add_var(name=f"v_q_{name}")
    v_d = vf.add_var(name=f"v_d_{name}")
    inputs = [v_q, v_d]

    v_q_ref = vf.add_var(name=f"v_q_ref_{name}")
    v_d_ref = vf.add_var(name=f"v_d_ref_{name}")
    event_dict = {
        v_q_ref: vf.add_const(np.sqrt(2)),
        v_d_ref: vf.add_const(0.0),
    }

    Vac_expr = np.sqrt(2 / 3)
    omega_ref_expr = 2 * np.pi * 50
    Zvirtual = 0.6
    R_L = 0.1
    Lv = vf.add_const(Zvirtual / omega_ref_expr)
    Rv = vf.add_const(Zvirtual * R_L)
    omega_ref = vf.add_const(omega_ref_expr)

    i_d_out_VA = vf.add_var(name=f"i_d_out_VA_{name}")
    i_q_out_VA = vf.add_var(name=f"i_q_out_VA_{name}")
    err_q = vf.add_var(name=f"err_q_{name}")
    err_d =  vf.add_var(name=f"err_d_{name}")
    y1 = vf.add_var(name=f"y1_{name}")
    y2 = vf.add_var(name=f"y2_{name}")
    y3 = vf.add_var(name=f"y3_{name}")
    y4 = vf.add_var(name=f"y4_{name}")
    x1_1 = vf.add_var(name=f"x1_1_{name}")
    x2_1 = vf.add_var(name=f"x2_1_{name}")
    dx1_1 = vf.add_diff_var(name=f"dx1_1_{name}", base_var=x1_1)
    dx2_1 = vf.add_diff_var(name=f"dx2_1_{name}", base_var=x2_1)
    x1_2 = vf.add_var(name=f"x1_2_{name}")
    x2_2 = vf.add_var(name=f"x2_2_{name}")
    dx1_2 = vf.add_diff_var(name=f"dx1_2_{name}", base_var=x1_2)
    dx2_2 = vf.add_diff_var(name=f"dx2_2_{name}", base_var=x2_2)
    x1_3 = vf.add_var(name=f"x1_3_{name}")
    x2_3 = vf.add_var(name=f"x2_3_{name}")
    dx1_3 = vf.add_diff_var(name=f"dx1_3_{name}", base_var=x1_3)
    dx2_3 = vf.add_diff_var(name=f"dx2_3_{name}", base_var=x2_3)
    x1_4 = vf.add_var(name=f"x1_4_{name}")
    x2_4 = vf.add_var(name=f"x2_4_{name}")
    dx1_4 = vf.add_diff_var(name=f"dx1_4_{name}", base_var=x1_4)
    dx2_4 = vf.add_diff_var(name=f"dx2_4_{name}", base_var=x2_4)


    n1_0 = Lv
    n0_0 = Rv
    n0_1 = Lv * omega_ref
    d2 = Lv * Lv
    d1 = 2 * Lv * Rv
    d0 = sym.max(Lv * Lv * omega_ref * omega_ref + Rv * Rv, eps)

    templ.block = Block(
        state_eqs=[
            x2_1,
            (err_q - d1 * x2_1 - d0 * x1_1)/sym.max(d2, eps),
            x2_2,
            (err_d - d1 * x2_2 - d0 * x1_2) / sym.max(d2, eps),
            x2_3,
            (err_q - d1 * x2_3 - d0 * x1_3) / sym.max(d2, eps),
            x2_4,
            (err_d - d1 * x2_4 - d0 * x1_4) / sym.max(d2, eps),
        ],
        state_vars=[x1_1, x2_1, x1_2, x2_2, x1_3, x2_3, x1_4, x2_4],
        diff_vars=[dx1_1, dx2_1, dx1_2, dx2_2, dx1_3, dx2_3, dx1_4, dx2_4],
        algebraic_eqs=[
            err_q - (v_q_ref - v_q),
            err_d - (v_d_ref - v_d),
            y1 - (n1_0 * x2_1 + n0_0 * x1_1),
            y2 - (n0_1 * x1_2),
            y3 - (n0_1 * x1_3),
            y4 - (n1_0 * x2_4 + n0_0 * x1_4),
            i_q_out_VA - (y1 - y2) ,
            i_d_out_VA - (y3 + y4) ,
        ],
        algebraic_vars=[err_q, err_d, y1, y2, y3, y4, i_q_out_VA, i_d_out_VA],
        in_vars=inputs,
        out_vars=[i_q_out_VA, i_d_out_VA],
        init_eqs={
            err_q: v_q_ref - v_q,
            err_d: v_d_ref - v_d,
            x1_1: err_q / d0,
            x1_2: err_d / d0,
            x1_3: err_q / d0,
            x1_4: err_d / d0,
            x2_1: c0,
            x2_2: c0,
            x2_3: c0,
            x2_4: c0,
            y1: n1_0 * x2_1 + n0_0 * x1_1,
            y2: n0_1 * x1_2,
            y3: n0_1 * x1_3,
            y4: n1_0 * x2_4 + n0_0 * x1_4,
            i_q_out_VA: (y1 - y2),
            i_d_out_VA: (y3 + y4),
        },
        diff_init_eqs={
            dx1_1: x2_1,
            dx1_2: x2_2,
            dx1_3: x2_3,
            dx1_4: x2_4,
            dx2_1: (err_q - d1*x2_1 - d0*x1_1)/sym.max(d2, eps),
            dx2_2: (err_d - d1*x2_2 - d0*x1_2)/sym.max(d2, eps),
            dx2_3: (err_q - d1*x2_3 - d0*x1_3)/sym.max(d2, eps),
            dx2_4: (err_d - d1*x2_4 - d0*x1_4)/sym.max(d2, eps),
        },
        event_dict=event_dict,
    )

    return templ


def get_current_limiter_GFL(vf: VarFactory, name: str = "G4L_current_limiter") -> EmtModelTemplate:
    """
    Current limiter equivalent to the Simulink block.

    Simulink:
        A = i_d
        B = i_q

    Priority:
        i_d is limited first.
        i_q receives the remaining current capability.
    """

    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name
    templ.block.name = name

    c0 = vf.add_const(0.0)

    i_q = vf.add_var(name=f"i_q_{name}")
    i_d = vf.add_var(name=f"i_d_{name}")
    inputs = [i_q, i_d]
    i_q_lim = vf.add_var(name=f"i_q_lim_{name}")
    i_d_lim = vf.add_var(name=f"i_d_lim_{name}")
    i_q_lim_mode = vf.add_var(name=f"i_q_lim_mode_{name}")
    i_d_lim_mode = vf.add_var(name=f"i_d_lim_mode_{name}")
    Imax = vf.add_const(1.1 * np.sqrt(2.0) / 3.0)
    i_mag_expr = sym.sqrt(i_q * i_q + i_d * i_d)
    i_q_cap_expr = sym.sqrt(sym.max(Imax * Imax - i_d_lim_mode * i_d_lim_mode, c0))
    i_q_cap_signed = (
        i_q_cap_expr * sym.heaviside(i_q)
        - i_q_cap_expr * sym.heaviside(-i_q)
    )
    i_q_lim_expr = (
        i_q * sym.heaviside(Imax - i_mag_expr)
        + i_q_cap_signed * sym.heaviside(i_mag_expr - Imax)
    )

    templ.block = Block(
        state_eqs=[],
        state_vars=[],
        diff_vars=[],
        algebraic_eqs=[
            i_q_lim - i_q_lim_mode,
            i_d_lim - i_d_lim_mode,
        ],
        algebraic_vars=[i_q_lim, i_d_lim],
        in_vars=inputs,
        out_vars=[i_q_lim, i_d_lim],
        init_eqs={
            i_q_lim: i_q,
            i_d_lim: i_d,
        },
        mode_dict={
            i_q_lim_mode: i_q,
            i_d_lim_mode: i_d,
        },
        procedural_logic=[
            hard_saturation(
                output=i_d_lim_mode,
                u=i_d,
                u_min=-Imax,
                u_max=Imax,
                name=f"i_d_lim_sat_{name}",
            ),
            sampled_value(
                output=i_q_lim_mode,
                source=i_q_lim_expr,
                name=f"i_q_lim_sample_{name}",
            ),
        ],
    )

    return templ


def get_current_loop_GFL(vf: VarFactory, name: str = "G4L_current_loop") -> EmtModelTemplate:
    """
    Current controller + inverse clark park transforms
    """

    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    templ.block.name = name

    c0 = vf.add_const(0.0)

    v_d = vf.add_var(name=f"v_d_{name}")
    v_q = vf.add_var(name=f"v_q_{name}")
    i_d = vf.add_var(name=f"i_d_{name}")
    i_q = vf.add_var(name=f"i_q_{name}")
    phase_pll = vf.add_var(name=f"phase_pll_{name}")
    omega_pll = vf.add_var(name=f"omega_pll_{name}")
    phase_cmd = phase_pll
    c_sqrt3 = vf.add_const(np.sqrt(3.0))

    v_con_A = vf.add_var(name=f"v_con_A_{name}")
    v_con_B = vf.add_var(name=f"v_con_B_{name}")
    v_con_C = vf.add_var(name=f"v_con_C_{name}")
    v_con_A_mode = vf.add_var(name=f"v_con_A_mode_{name}")
    v_con_B_mode = vf.add_var(name=f"v_con_B_mode_{name}")
    v_con_C_mode = vf.add_var(name=f"v_con_C_mode_{name}")

    v_con_q = vf.add_var(name=f"v_con_q_{name}")
    v_con_d = vf.add_var(name=f"v_con_d_{name}")

    i_d_lim = vf.add_var(name=f"i_d_lim_{name}")
    i_q_lim = vf.add_var(name=f"i_q_lim_{name}")

    inputs = [v_q, v_d, i_q, i_d, phase_pll, omega_pll, i_q_lim, i_d_lim]

    v_ffw_q = vf.add_var(name=f"v_ffw_q_{name}")
    v_ffw_d = vf.add_var(name=f"v_ffw_d_{name}")
    dv_ffw_q = vf.add_diff_var(name=f"dv_ffw_q_{name}", base_var=v_ffw_q)
    dv_ffw_d = vf.add_diff_var(name=f"dv_ffw_d_{name}", base_var=v_ffw_d)
    T_ffw = vf.add_const(0.0005)

    tau_cc = 0.001
    omega_ref_expr = 2 * np.pi * 50
    PU_Z_TO_EMT = 3.0

    R_f_pu = PU_Z_TO_EMT * (0.1 / 10.0)
    X_f_pu = PU_Z_TO_EMT * (1.0 / 10.0)
    L_f_expr = X_f_pu / omega_ref_expr
    Kp_cc = vf.add_const(L_f_expr / tau_cc)
    Ki_cc = vf.add_const(R_f_pu / tau_cc)
    L_f = vf.add_const(L_f_expr)
    err_q = vf.add_var(name=f"err_q_{name}")
    err_d = vf.add_var(name=f"err_d_{name}")
    x_e_q = vf.add_var(name=f"x_e_q_{name}")
    dx_e_q = vf.add_diff_var(name=f"dx_e_q_{name}", base_var=x_e_q)
    x_e_d = vf.add_var(name=f"x_e_d_{name}")
    dx_e_d = vf.add_diff_var(name=f"dx_e_d_{name}", base_var=x_e_d)
    y_q = vf.add_var(name=f"y_q_{name}")
    y_d = vf.add_var(name=f"y_d_{name}")
    alpha = vf.add_var(name=f"alpha_{name}")
    beta = vf.add_var(name=f"beta_{name}")

    templ.block = Block(
        state_eqs=[
            (v_q - v_ffw_q) / T_ffw,
            (v_d - v_ffw_d) / T_ffw,
            Ki_cc * err_q,
            Ki_cc * err_d,
        ],
        state_vars=[v_ffw_q, v_ffw_d, x_e_q, x_e_d],
        diff_vars=[dv_ffw_q, dv_ffw_d, dx_e_q, dx_e_d],
        algebraic_eqs=[
            err_q - (i_q_lim - i_q),
            err_d - (i_d_lim - i_d),
            y_q - (err_q * Kp_cc + x_e_q),
            y_d - (err_d * Kp_cc + x_e_d),
            v_con_q - (v_ffw_q + y_q + omega_pll * L_f * i_d),
            v_con_d - (v_ffw_d + y_d - omega_pll * L_f * i_q),
            alpha - (v_con_q * cos(phase_cmd) + v_con_d * sin(phase_cmd)),
            beta - (-v_con_q * sin(phase_cmd) + v_con_d * cos(phase_cmd)),
            v_con_A - 0.5 * (2 * alpha),
            v_con_B - 0.5 * (-alpha - np.sqrt(3) * beta),
            v_con_C - 0.5 * (-alpha + np.sqrt(3) * beta),

        ],
        algebraic_vars=[err_q, err_d, y_q, y_d, v_con_q, v_con_d, alpha, beta, v_con_A, v_con_B, v_con_C],
        in_vars=inputs,
        out_vars=[v_con_A_mode, v_con_B_mode, v_con_C_mode, v_con_A, v_con_B, v_con_C],
        init_eqs={
            v_ffw_q: v_q,
            v_ffw_d: v_d,
            err_q: i_q_lim - i_q,
            err_d: i_d_lim - i_d,
            v_con_q: v_q + R_f_pu * i_q + omega_pll * L_f * i_d,
            v_con_d: v_d + R_f_pu * i_d - omega_pll * L_f * i_q,
            y_q: v_con_q - v_ffw_q - omega_pll * L_f * i_d,
            y_d: v_con_d - v_ffw_d + omega_pll * L_f * i_q,
            x_e_q: y_q - Kp_cc * err_q,
            x_e_d: y_d - Kp_cc * err_d,
            alpha: v_con_q * cos(phase_cmd) + v_con_d * sin(phase_cmd),
            beta: -v_con_q * sin(phase_cmd) + v_con_d * cos(phase_cmd),
            v_con_A: alpha,
            v_con_B: 0.5 * (-alpha - c_sqrt3 * beta),
            v_con_C: 0.5 * (-alpha + c_sqrt3 * beta),
        },
        diff_init_eqs={
            dv_ffw_q: c0,
            dv_ffw_d: c0,
            dx_e_q: c0,
            dx_e_d: c0,
        },
        mode_dict={
            v_con_A_mode: v_con_A,
            v_con_B_mode: v_con_B,
            v_con_C_mode: v_con_C,
        },
        procedural_logic=[
            sampled_value(output=v_con_A_mode, source=v_con_A, name=f"v_con_A_sample_{name}"),
            sampled_value(output=v_con_B_mode, source=v_con_B, name=f"v_con_B_sample_{name}"),
            sampled_value(output=v_con_C_mode, source=v_con_C, name=f"v_con_C_sample_{name}"),
        ]
    )

    return templ


def get_complete_load_template_G4L(vf: VarFactory, name: str = "G4L_complete_load") -> EmtModelTemplate:
    """
    Complete GFL load composed by:
    - grid side converter
    - load side converter
    - grid side converter control:
        - clark park transforms
        - VSM only
        - Virtual Admittance
        - Current Limitation
        - Current control
    - Load side converter control
    """

    templ = EmtModelTemplate()
    templ.tpe = DeviceType.LoadDevice
    templ.name = name

    templ.block.name = name

    grid_side_vsc_mdl = get_grid_side_converter_GFL(vf=vf).block
    load_side_vsc_mdl = get_load_side_converter_GFL(vf=vf).block
    grid_side_ctrl_mdl = get_grid_side_converter_control_GFL(vf=vf).block
    load_side_ctrl_mdl = get_load_side_converter_control_GFL(vf=vf).block

    templ.block.in_vars = [grid_side_vsc_mdl.in_vars[0],
                           grid_side_vsc_mdl.in_vars[1],
                           grid_side_vsc_mdl.in_vars[2],
                           ]

    templ.block.out_vars = [grid_side_vsc_mdl.out_vars[0],
                            grid_side_vsc_mdl.out_vars[1],
                            grid_side_vsc_mdl.out_vars[2],
                            ]

    vf.add_connection(load_side_vsc_mdl.in_vars[0], grid_side_vsc_mdl.out_vars[3])
    vf.add_connection(grid_side_vsc_mdl.in_vars[3], load_side_vsc_mdl.out_vars[0])
    vf.add_connection(load_side_ctrl_mdl.in_vars[0], load_side_vsc_mdl.out_vars[0])
    vf.add_connection(load_side_vsc_mdl.in_vars[1], load_side_ctrl_mdl.out_vars[0])
    vf.add_connection(grid_side_vsc_mdl.in_vars[4], grid_side_ctrl_mdl.out_vars[3])
    vf.add_connection(grid_side_vsc_mdl.in_vars[5], grid_side_ctrl_mdl.out_vars[4])
    vf.add_connection(grid_side_vsc_mdl.in_vars[6], grid_side_ctrl_mdl.out_vars[5])
    vf.add_connection(grid_side_ctrl_mdl.in_vars[0], grid_side_vsc_mdl.in_vars[0])
    vf.add_connection(grid_side_ctrl_mdl.in_vars[1], grid_side_vsc_mdl.in_vars[1])
    vf.add_connection(grid_side_ctrl_mdl.in_vars[2], grid_side_vsc_mdl.in_vars[2])
    vf.add_connection(grid_side_ctrl_mdl.in_vars[3], grid_side_vsc_mdl.out_vars[0])
    vf.add_connection(grid_side_ctrl_mdl.in_vars[4], grid_side_vsc_mdl.out_vars[1])
    vf.add_connection(grid_side_ctrl_mdl.in_vars[5], grid_side_vsc_mdl.out_vars[2])
    vf.add_connection(grid_side_ctrl_mdl.in_vars[6], grid_side_vsc_mdl.out_vars[4])
    vf.add_connection(load_side_ctrl_mdl.in_vars[1], grid_side_vsc_mdl.out_vars[5])

    templ.block.children.append(grid_side_vsc_mdl)
    templ.block.children.append(load_side_vsc_mdl)
    templ.block.children.append(grid_side_ctrl_mdl)
    templ.block.children.append(load_side_ctrl_mdl)

    templ.block.external_mapping = {
        VarPowerFlowReferenceType.v_A: grid_side_vsc_mdl.in_vars[0],
        VarPowerFlowReferenceType.v_B: grid_side_vsc_mdl.in_vars[1],
        VarPowerFlowReferenceType.v_C: grid_side_vsc_mdl.in_vars[2],
        VarPowerFlowReferenceType.i_A: grid_side_vsc_mdl.out_vars[0],
        VarPowerFlowReferenceType.i_B: grid_side_vsc_mdl.out_vars[1],
        VarPowerFlowReferenceType.i_C: grid_side_vsc_mdl.out_vars[2],
        VarPowerFlowReferenceType.P: grid_side_vsc_mdl.out_vars[4],
    }


    return templ
