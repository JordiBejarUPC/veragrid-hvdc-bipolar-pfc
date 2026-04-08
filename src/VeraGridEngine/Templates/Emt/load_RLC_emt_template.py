# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.enumerations import VarPowerFlowRefferenceType, DeviceType, ParamPowerFlowRefferenceType
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate

# --------------------------------------------------------------------------------------
# 1) ABC primitives (phase-decoupled) as EMT DAE blocks using vars + diff_vars
#    - Shunt R: algebraic i = -v/R
#    - Shunt L: state is i, with di/dt = -(1/L) * v   (injected current convention)
#    - Shunt C: state is v_cap, with dv_cap/dt driven by bus voltage (v_cap = v_bus),
#               and injected current i = -C * dv_cap/dt
# --------------------------------------------------------------------------------------


def get_shunt_r_3ph_emt_template(vf: VarFactory, name: str = "Shunt_R_3ph") -> EmtModelTemplate:
    """
    3-phase shunt resistor (wye to ground), phase-decoupled.
    Inputs:  vA, vB, vC  (instantaneous phase-to-ground voltages)
    Outputs: i_A, i_B, i_C (injected currents into the bus; negative for consumption)
    """

    templ = EmtModelTemplate()
    templ.tpe = DeviceType.LoadDevice
    templ.name = name
    templ.block.name = name

    # Inputs (abc instantaneous voltages)
    v_A = vf.add_var(name=f"v_A_{name}", reference=VarPowerFlowRefferenceType.v_A)
    v_B = vf.add_var(name=f"v_B_{name}", reference=VarPowerFlowRefferenceType.v_B)
    v_C = vf.add_var(name=f"v_C_{name}", reference=VarPowerFlowRefferenceType.v_C)
    templ.block.in_vars = [v_A, v_B, v_C]

    # Parameters
    R_A = vf.add_var("R_A_" + name)
    R_B = vf.add_var("R_B_" + name)
    R_C = vf.add_var("R_C_" + name)
    templ.block.event_dict[R_A] = vf.add_const(None)
    templ.block.event_dict[R_B] = vf.add_const(None)
    templ.block.event_dict[R_C] = vf.add_const(None)

    Pl0_A = vf.add_var("Pl0_A_" + name)
    Pl0_B = vf.add_var("Pl0_B_" + name)
    Pl0_C = vf.add_var("Pl0_C_" + name)
    templ.block.parameters[Pl0_A] = vf.add_const(None)
    templ.block.parameters[Pl0_B] = vf.add_const(None)
    templ.block.parameters[Pl0_C] = vf.add_const(None)

    Vnom = vf.add_var("Vnom_" + name)
    templ.block.event_dict[Vnom] = vf.add_const(1.0)
    templ.block.event_dict[R_A] = Vnom ** 2 / Pl0_A
    templ.block.event_dict[R_B] = Vnom ** 2 / Pl0_B
    templ.block.event_dict[R_C] = Vnom ** 2 / Pl0_C


    # Algebraic injected currents
    i_A = vf.add_var(name=f"i_A_{name}", reference=VarPowerFlowRefferenceType.i_A)
    i_B = vf.add_var(name=f"i_B_{name}", reference=VarPowerFlowRefferenceType.i_B)
    i_C = vf.add_var(name=f"i_C_{name}", reference=VarPowerFlowRefferenceType.i_C)

    templ.block.algebraic_vars = [i_A, i_B, i_C]
    templ.block.algebraic_eqs = [
        i_A + v_A / R_A,   # i_inj = -v/R
        i_B + v_B / R_B,
        i_C + v_C / R_C,
    ]

    templ.block.external_mapping = {
        VarPowerFlowRefferenceType.v_N: None,
        VarPowerFlowRefferenceType.v_A: v_A,
        VarPowerFlowRefferenceType.v_B: v_B,
        VarPowerFlowRefferenceType.v_C: v_C,
        VarPowerFlowRefferenceType.P: None,
        VarPowerFlowRefferenceType.Q: None,
        VarPowerFlowRefferenceType.P_N: None,
        VarPowerFlowRefferenceType.Q_N: None,
        VarPowerFlowRefferenceType.P_A: None,
        VarPowerFlowRefferenceType.Q_A: None,
        VarPowerFlowRefferenceType.P_B: None,
        VarPowerFlowRefferenceType.Q_B: None,
        VarPowerFlowRefferenceType.P_C: None,
        VarPowerFlowRefferenceType.Q_C: None,
        VarPowerFlowRefferenceType.i_N: None,
        VarPowerFlowRefferenceType.i_A: i_A,
        VarPowerFlowRefferenceType.i_B: i_B,
        VarPowerFlowRefferenceType.i_C: i_C,
        VarPowerFlowRefferenceType.phi_v: None,
        VarPowerFlowRefferenceType.phi: None,
        VarPowerFlowRefferenceType.Vpk: None,
        VarPowerFlowRefferenceType.Ipk: None,
        VarPowerFlowRefferenceType.d_v_N: None,
        VarPowerFlowRefferenceType.d_v_A: None,
        VarPowerFlowRefferenceType.d_v_B: None,
        VarPowerFlowRefferenceType.d_v_C: None,
    }

    templ.block.api_obj_mapping = {
        ParamPowerFlowRefferenceType.omega_base: None,
        ParamPowerFlowRefferenceType.Pl0_A: Pl0_A,
        ParamPowerFlowRefferenceType.Pl0_B: Pl0_B,
        ParamPowerFlowRefferenceType.Pl0_C: Pl0_C,
        ParamPowerFlowRefferenceType.Ql0_A: None,
        ParamPowerFlowRefferenceType.Ql0_B: None,
        ParamPowerFlowRefferenceType.Ql0_C: None,
    }



    return templ

def get_shunt_r_1ph_emt_template(vf: VarFactory, name: str = "Shunt_R_1ph") -> EmtModelTemplate:
    """
    mono-phase shunt resistor
    Inputs:  vA, (instantaneous phase-to-ground voltages)
    Outputs: i_A(injected currents into the bus; negative for consumption)
    """

    templ = EmtModelTemplate()
    templ.tpe = DeviceType.LoadDevice
    templ.name = name
    templ.block.name = name

    # Inputs (abc instantaneous voltages)
    v_A = vf.add_var(name=f"v_A_{name}", reference=VarPowerFlowRefferenceType.v_A)
    templ.block.in_vars = [v_A]

    # Parameters
    R_A = vf.add_var("R_A_" + name)
    templ.block.event_dict[R_A] = vf.add_const(None)

    Pl0_A = vf.add_var("Pl0_A_" + name)
    templ.block.parameters[Pl0_A] = vf.add_const(None)

    Vnom = vf.add_var("Vnom_" + name)
    templ.block.event_dict[Vnom] = vf.add_const(1.0)
    templ.block.event_dict[R_A] = Vnom ** 2 / Pl0_A

    # Algebraic injected currents
    i_A = vf.add_var(name=f"i_A_{name}", reference=VarPowerFlowRefferenceType.i_A)

    templ.block.algebraic_vars = [i_A]
    templ.block.algebraic_eqs = [
        i_A + v_A / R_A,   # i_inj = -v/R
    ]

    templ.block.external_mapping = {
        VarPowerFlowRefferenceType.v_N: None,
        VarPowerFlowRefferenceType.v_A: v_A,
        VarPowerFlowRefferenceType.v_B: None,
        VarPowerFlowRefferenceType.v_C: None,
        VarPowerFlowRefferenceType.P: None,
        VarPowerFlowRefferenceType.Q: None,
        VarPowerFlowRefferenceType.P_N: None,
        VarPowerFlowRefferenceType.Q_N: None,
        VarPowerFlowRefferenceType.P_A: None,
        VarPowerFlowRefferenceType.Q_A: None,
        VarPowerFlowRefferenceType.P_B: None,
        VarPowerFlowRefferenceType.Q_B: None,
        VarPowerFlowRefferenceType.P_C: None,
        VarPowerFlowRefferenceType.Q_C: None,
        VarPowerFlowRefferenceType.i_N: None,
        VarPowerFlowRefferenceType.i_A: i_A,
        VarPowerFlowRefferenceType.i_B: None,
        VarPowerFlowRefferenceType.i_C: None,
        VarPowerFlowRefferenceType.phi_v: None,
        VarPowerFlowRefferenceType.phi: None,
        VarPowerFlowRefferenceType.Vpk: None,
        VarPowerFlowRefferenceType.Ipk: None,
        VarPowerFlowRefferenceType.d_v_N: None,
        VarPowerFlowRefferenceType.d_v_A: None,
        VarPowerFlowRefferenceType.d_v_B: None,
        VarPowerFlowRefferenceType.d_v_C: None,
    }

    templ.block.api_obj_mapping = {
        ParamPowerFlowRefferenceType.omega_base: None,
        ParamPowerFlowRefferenceType.Pl0_A: Pl0_A,
        ParamPowerFlowRefferenceType.Pl0_B: None,
        ParamPowerFlowRefferenceType.Pl0_C: None,
        ParamPowerFlowRefferenceType.Ql0_A: None,
        ParamPowerFlowRefferenceType.Ql0_B: None,
        ParamPowerFlowRefferenceType.Ql0_C: None,
    }



    return templ

def get_shunt_l_3ph_emt_template(vf: VarFactory, name: str = "Shunt_L_3ph") -> EmtModelTemplate:

    templ = EmtModelTemplate()
    templ.tpe = DeviceType.LoadDevice
    templ.name = name
    templ.block.name = name

    # Inputs and Parameters
    v_A = vf.add_var(name=f"v_A_{name}", reference=VarPowerFlowRefferenceType.v_A)
    v_B = vf.add_var(name=f"v_B_{name}", reference=VarPowerFlowRefferenceType.v_B)
    v_C = vf.add_var(name=f"v_C_{name}", reference=VarPowerFlowRefferenceType.v_C)
    templ.block.in_vars = [v_A, v_B, v_C]

    L_A, L_B, L_C = [vf.add_var(f"L_{p}_{name}") for p in ["A", "B", "C"]]
    Ql0_A, Ql0_B, Ql0_C = [vf.add_var(f"Ql0_{p}_{name}") for p in ["A", "B", "C"]]
    w_base = vf.add_var("w_base_" + name)
    Vnom = vf.add_var("Vnom_" + name)
    templ.block.event_dict[Vnom] = vf.add_const(1.0)
    # L = V^2 / (Q * w)
    templ.block.event_dict[L_A] = Vnom ** 2 / (Ql0_A * w_base)
    templ.block.event_dict[L_B] = Vnom ** 2 / (Ql0_A * w_base)
    templ.block.event_dict[L_C] = Vnom ** 2 / (Ql0_A * w_base)


    # State vars (injected currents)
    i_A, i_B, i_C = [vf.add_var(f"i_{p}_{name}") for p in ["A", "B", "C"]]
    d_i_A, d_i_B, d_i_C = [vf.add_diff_var(name =f"d_i_{p}_{name}", base_var=v)
                              for p, v in zip(["A", "B", "C"], [i_A, i_B, i_C])]

    templ.block.state_vars = [i_A, i_B, i_C]
    templ.block.diff_vars = [d_i_A, d_i_B, d_i_C]

    # Physics: di/dt = -v/L (for injected current)
    templ.block.state_eqs = [
        - v_A / L_A,
        - v_B / L_B,
        - v_C / L_C,
    ]

    templ.block.api_obj_mapping = {
        ParamPowerFlowRefferenceType.omega_base: w_base,
        ParamPowerFlowRefferenceType.Pl0_A: None,
        ParamPowerFlowRefferenceType.Pl0_B: None,
        ParamPowerFlowRefferenceType.Pl0_C: None,
        ParamPowerFlowRefferenceType.Ql0_A: Ql0_A,
        ParamPowerFlowRefferenceType.Ql0_B: Ql0_B,
        ParamPowerFlowRefferenceType.Ql0_C: Ql0_C,
    }



    templ.block.diff_init_eqs = {
        d_i_A: vf.add_const(0.0),
        d_i_B: vf.add_const(0.0),
        d_i_C: vf.add_const(0.0),
    }


    # Map injected currents to the bus
    templ.block.external_mapping = {
        VarPowerFlowRefferenceType.v_N: None,
        VarPowerFlowRefferenceType.v_A: v_A,
        VarPowerFlowRefferenceType.v_B: v_B,
        VarPowerFlowRefferenceType.v_C: v_C,
        VarPowerFlowRefferenceType.i_A: i_A,
        VarPowerFlowRefferenceType.i_B: i_B,
        VarPowerFlowRefferenceType.i_C: i_C,
    }

    return templ



def get_shunt_c_3ph_emt_template(vf: VarFactory, name: str = "Shunt_C_3ph") -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.LoadDevice
    templ.name = name
    templ.block.name = name

    v_A = vf.add_var(name=f"v_A_{name}", reference=VarPowerFlowRefferenceType.v_A)
    v_B = vf.add_var(name=f"v_B_{name}", reference=VarPowerFlowRefferenceType.v_B)
    v_C = vf.add_var(name=f"v_C_{name}", reference=VarPowerFlowRefferenceType.v_C)
    templ.block.in_vars = [v_A, v_B, v_C]

    C_A, C_B, C_C = [vf.add_var(f"C_{p}_{name}") for p in ["A", "B", "C"]]
    Ql0_A, Ql0_B, Ql0_C = [vf.add_var(f"Ql0_{p}_{name}") for p in ["A", "B", "C"]]
    w_base = vf.add_var("w_base_" + name)
    Vnom = vf.add_var("Vnom_" + name)
    templ.block.event_dict[Vnom] = vf.add_const(1.0)
    # C = Q / (V^2 * w)
    templ.block.event_dict[C_A] = Ql0_A / (Vnom ** 2 * w_base)
    templ.block.event_dict[C_B] = Ql0_B / (Vnom ** 2 * w_base)
    templ.block.event_dict[C_C] = Ql0_C / (Vnom ** 2 * w_base)

    i_A, i_B, i_C = [vf.add_var(f"i_{p}_{name}") for p in ["A", "B", "C"]]
    vCapA, vCapB, vCapC = [vf.add_var(f"vCap{p}_{name}") for p in ["A", "B", "C"]]
    dvCapA, dvCapB, dvCapC = [vf.add_diff_var(f"dvCap{p}_{name}", base_var=v)
                              for p, v in zip(["A", "B", "C"], [vCapA, vCapB, vCapC])]

    templ.block.state_vars = [vCapA, vCapB, vCapC]
    templ.block.diff_vars = [dvCapA, dvCapB, dvCapC]

    # In a pure capacitor model, the state equation is often redundant if
    # vCap is algebraically tied to vBus. We define the current algebraically:
    templ.block.algebraic_vars = [i_A, i_B, i_C]
    templ.block.algebraic_eqs = [
        vCapA - v_A,
        vCapB - v_B,
        vCapC - v_C,
        i_A + C_A * dvCapA,  # i_inj = -C * dv/dt
        i_B + C_B * dvCapB,
        i_C + C_C * dvCapC,
    ]

    templ.block.api_obj_mapping = {
        ParamPowerFlowRefferenceType.omega_base: w_base,
        ParamPowerFlowRefferenceType.Pl0_A: None,
        ParamPowerFlowRefferenceType.Pl0_B: None,
        ParamPowerFlowRefferenceType.Pl0_C: None,
        ParamPowerFlowRefferenceType.Ql0_A: Ql0_A,
        ParamPowerFlowRefferenceType.Ql0_B: Ql0_B,
        ParamPowerFlowRefferenceType.Ql0_C: Ql0_C,
    }



    templ.block.diff_init_eqs = {
        dvCapA: vf.add_const(0.0),
        dvCapB: vf.add_const(0.0),
        dvCapC: vf.add_const(0.0),
    }

    templ.block.external_mapping = {
        VarPowerFlowRefferenceType.v_N: None,
        VarPowerFlowRefferenceType.v_A: v_A,
        VarPowerFlowRefferenceType.v_B: v_B,
        VarPowerFlowRefferenceType.v_C: v_C,
        VarPowerFlowRefferenceType.i_A: i_A,
        VarPowerFlowRefferenceType.i_B: i_B,
        VarPowerFlowRefferenceType.i_C: i_C,
    }

    return templ
