# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Utils.Symbolic.symbolic import Var, cos, sin
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import sampled_value
from VeraGridEngine.enumerations import VarPowerFlowReferenceType, DeviceType


def _connect_with_shared_reference(vf: VarFactory,
                                   target_var: Var,
                                   source_var: Var,
                                   shared_name: str) -> None:
    """
    Connect two symbolic ports and expose their relationship to the block editor.

    The variable factory owns the runtime alias used by the DAE model, while
    the shared reference is the explicit semantic tag used by the dynamic
    editor to discover and draw the corresponding inter-block wire.

    :param vf: Variable factory shared by the complete converter model.
    :param target_var: Input variable whose runtime identity is substituted.
    :param source_var: Output or root-interface variable driving the target.
    :param shared_name: Stable semantic name shared by every endpoint of the signal.
    :return: None.
    """
    # Fan-out signals call this helper once per target. Avoid registering the
    # same variable repeatedly when it already owns the requested reference.
    if source_var.shared_ref is None or source_var.shared_ref.name != shared_name:
        vf.add_shared_ref_to_var(source_var, shared_name)
    else:
        pass

    if target_var.shared_ref is None or target_var.shared_ref.name != shared_name:
        vf.add_shared_ref_to_var(target_var, shared_name)
    else:
        pass

    vf.add_connection(var_to_subs=target_var, incoming_var=source_var)


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

    PU_Z_TO_EMT = 3.0
    PU_Y_TO_EMT = 1.0 / 3.0

    R_ser_pu = PU_Z_TO_EMT * (0.1 / 10.0)  # 0.03
    X_ser_pu = PU_Z_TO_EMT * (1.0 / 10.0)  # 0.30

    # R_ser = vf.add_const(R_ser_pu)
    R_ser = vf.add_var(name=f"R_ser_{name}")
    X_ser = vf.add_var(name=f"X_ser_{name}")
    Linv = vf.add_var(name=f"Linv_{name}")

    # Simulink C_f gives standard susceptance B = 1/15 pu.
    # In VeraGrid EMT phase/current signal base, admittance is 1/3 of standard pu.
    C_sh = vf.add_var(name=f"C_sh_{name}")

    # Simulink R_Cf = 0.05*Zbase; in the EMT signal impedance base it is 3x.
    R_sh = vf.add_var(name=f"R_sh_{name}")  # 0.15

    event_dict={
        R_ser: vf.add_const(R_ser_pu),
        Linv: vf.add_const(omega_base / X_ser_pu),
        C_sh: vf.add_const((PU_Y_TO_EMT * (1.0 / 15.0)) / omega_base),
        R_sh: vf.add_const(PU_Z_TO_EMT * 0.05),
    }

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

    # Keep the template root as a pure hierarchical container.  The physical
    # line equations live in one named child so the Dynamic Editor presents the
    # branch as one block that can be opened to inspect its internals.
    line_block: Block = Block(
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
            # Simulink starts the branch inductors and shunt capacitors from
            # zero energy.  Reusing the power-flow current or a sinusoidal
            # capacitor charge gives VeraGrid a different physical startup.
            i_ser_A: c0,
            i_ser_B: c0,
            i_ser_C: c0,
            i_cap_t_A: c0,
            i_cap_t_B: c0,
            i_cap_t_C: c0,
            q_t_A: c0,
            q_t_B: c0,
            q_t_C: c0,
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
        event_dict=event_dict,
        name=f"{name}_line",
    )

    line_block.external_mapping = {
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

    # Publish the physical line as the only child and mirror its external
    # contract on the root.  EMT compilation still flattens the child, while
    # serialization preserves this hierarchy for the GUI.
    templ.block.children.append(line_block)
    templ.block.external_mapping = line_block.external_mapping
    templ.block.api_obj_mapping = line_block.api_obj_mapping
    templ.block.parameters = line_block.parameters
    templ.block.in_vars = line_block.in_vars
    templ.block.out_vars = line_block.out_vars

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

    # Follow the working converter/filter templates: fixed internal filter
    # coefficients are embedded directly in the equations instead of being
    # introduced as separate symbolic parameter vars.
    # R_f_pu = 0.1 / 10.0
    # X_f_pu = 1.0 / 10.0
    PU_Z_TO_EMT = 3.0

    R_f_pu = PU_Z_TO_EMT * (0.1 / 10.0)  # 0.03
    X_f_pu = PU_Z_TO_EMT * (1.0 / 10.0)  # 0.30
    omega_base = 2 * np.pi * 50
    R_f = vf.add_var(name=f"R_f_{name}")
    Linv_f = vf.add_var(name=f"Linv_f_{name}")

    event_dict = {
        Linv_f: vf.add_const(omega_base / X_f_pu),
        R_f: vf.add_const(R_f_pu),
    }

    # grid connection voltages
    v_A = vf.add_var(name=f"v_A_{name}", reference=VarPowerFlowReferenceType.v_A)
    v_B = vf.add_var(name=f"v_B_{name}", reference=VarPowerFlowReferenceType.v_B)
    v_C = vf.add_var(name=f"v_C_{name}", reference=VarPowerFlowReferenceType.v_C)

    # DC connection voltages
    v_dc = vf.add_var(name=f"v_dc_{name}", reference=VarPowerFlowReferenceType.Vdc)

    # AC voltage reference from the controller -> VOLTAGE SOURCE VOLTAGES
    v_con_A = vf.add_var(name=f"v_con_A_{name}")
    v_con_B = vf.add_var(name=f"v_con_B_{name}")
    v_con_C = vf.add_var(name=f"v_con_C_{name}")

    inputs = [v_A, v_B, v_C, v_dc, v_con_A, v_con_B, v_con_C]

    # AC and DC currents
    i_A = vf.add_var(name=f"i_f_A_{name}", reference=VarPowerFlowReferenceType.i_A)
    i_B = vf.add_var(name=f"i_f_B_{name}", reference=VarPowerFlowReferenceType.i_B)
    i_C = vf.add_var(name=f"i_f_C_{name}", reference=VarPowerFlowReferenceType.i_C)
    i_dc = vf.add_var(name=f"i_dc_{name}", reference=VarPowerFlowReferenceType.Idc)

    # series current and derivative
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
        # --------------------------------------------------------------------------------------
        # STATE EQUATIONS (seconds + pu)
        # --------------------------------------------------------------------------------------
        state_eqs=[
            # AC RL branch + AC voltage source
            # Linv_f * (v_A - v_con_A - R_f * i_ser_A),
            # Linv_f * (v_B - v_con_B - R_f * i_ser_B),
            # Linv_f * (v_C - v_con_C - R_f * i_ser_C),
            Linv_f * (v_con_A - v_A - R_f * i_ser_A),
            Linv_f * (v_con_B - v_B - R_f * i_ser_B),
            Linv_f * (v_con_C - v_C - R_f * i_ser_C),
        ],
        state_vars=[i_ser_A, i_ser_B, i_ser_C],
        diff_vars=[di_ser_A, di_ser_B, di_ser_C],

        # --------------------------------------------------------------------------------------
        # ALGEBRAIC EQUATIONS
        # --------------------------------------------------------------------------------------
        algebraic_eqs=[
            # AC currents
            i_A - i_ser_A,
            i_B - i_ser_B,
            i_C - i_ser_C,

            # power in the AC voltage source of the converter NEG
            Pac - (v_con_A * i_A + v_con_B * i_B + v_con_C * i_C),
            # DC current injection
            i_dc - i_dc_mode,
            # power in the point of connection of the VSC (bus)
            Pac_bus - (v_A * i_A + v_B * i_B + v_C * i_C),
        ],
        algebraic_vars=[i_A, i_B, i_C, Pac, i_dc, Pac_bus],
        in_vars=inputs,
        out_vars=[i_A, i_B, i_C, i_dc, Pac_bus, Pac],
        init_eqs={
            # The Simulink converter filter inductors use zero initial current.
            i_ser_A: c0,
            i_ser_B: c0,
            i_ser_C: c0,
            Pac_bus: v_A * i_A + v_B * i_B + v_C * i_C,
            # Pac: Pac_bus,
            Pac: v_con_A * i_A + v_con_B * i_B + v_con_C * i_C,
            i_dc: -Pac / sym.max(v_dc, eps),
        },
        diff_init_eqs={
            # di_ser_A: Linv_f * (v_A - v_con_A - R_f * i_ser_A),
            # di_ser_B: Linv_f * (v_B - v_con_B - R_f * i_ser_B),
            # di_ser_C: Linv_f * (v_C - v_con_C - R_f * i_ser_C),
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
        event_dict=event_dict,
    )

    templ.block.external_mapping = {
        VarPowerFlowReferenceType.v_A: v_A,
        VarPowerFlowReferenceType.v_B: v_B,
        VarPowerFlowReferenceType.v_C: v_C,
        VarPowerFlowReferenceType.i_A: i_A,
        VarPowerFlowReferenceType.i_B: i_B,
        VarPowerFlowReferenceType.i_C: i_C,
        # VarPowerFlowReferenceType.P: Pac_bus,
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

    # Reuse the standard EMT branch parameter API slots so the model can be
    # initialized through VeraGrid's existing static-parameter mapping.
    Cdc = vf.add_var(name=f"Cdc_{name}")
    event_dict = {
        Cdc: vf.add_const(0.04),
    }

    # DC connection voltages
    v_dc = vf.add_var(name=f"v_dc_{name}", reference=VarPowerFlowReferenceType.Vdc)

    # DC load current
    i_dc_L = vf.add_var(name=f"i_dc_L_{name}")

    # i_dc from VSC
    i_dc_vsc = vf.add_var(name=f"i_dc_vsc_{name}")

    inputs = [i_dc_vsc, i_dc_L]

    # cap current and charge
    i_cap_dc = vf.add_var(name=f"i_cap_dc_{name}")
    q_cap = vf.add_var(name=f"q_cap_{name}")
    dq_cap = vf.add_diff_var(name=f"dq_cap_{name}", base_var=q_cap)


    templ.block = Block(
        # --------------------------------------------------------------------------------------
        # STATE EQUATIONS (seconds + pu)
        # --------------------------------------------------------------------------------------
        state_eqs=[
            i_cap_dc,
        ],
        state_vars=[q_cap],
        diff_vars=[dq_cap],
        # --------------------------------------------------------------------------------------
        # ALGEBRAIC EQUATIONS
        # --------------------------------------------------------------------------------------
        algebraic_eqs=[
            q_cap - Cdc * v_dc,
            # Both converter currents are defined positive into the DC link.
            # This matches Simulink: a positive sampled i_dc_L raises v_dc at
            # startup, while its negative steady-state value draws DC power.
            i_dc_vsc + i_dc_L - i_cap_dc,
        ],
        algebraic_vars=[i_cap_dc, v_dc],
        in_vars=inputs,
        out_vars=[v_dc],
        init_eqs={
            i_cap_dc: i_dc_vsc + i_dc_L,
            q_cap: Cdc * vf.add_const(1.0),
            v_dc: vf.add_const(1.0),
        },
        diff_init_eqs={
            dq_cap:i_cap_dc,
        },
        event_dict=event_dict,
    )

    return templ

def get_load_side_converter_control_GFL(
        vf: VarFactory,
        name: str = "G4L_load_side_converter_control",
) -> EmtModelTemplate:
    """
    Build the continuous load-side DC-voltage PI controller.

    The EMT solver applies the selected integration kernel to the symbolic PI
    state, keeping the controller independent of the numerical time step.

    :param vf: EMT variable factory.
    :param name: Symbolic block name.
    :return: Configured load-side controller template.
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    templ.block.name = name

    c0 = vf.add_const(0.0)
    eps = vf.add_const(1e-9)

    # Vdc reference
    v_dc_ref = vf.add_var(name=f"v_dc_ref_{name}")

    C_DC = 0.04
    chi_E = 0.707
    tau_E = 0.1
    w_E: float = 4 / (chi_E * tau_E)
    # PI
    Kp_E = vf.add_var(name=f"Kp_E_{name}")
    Ki_E = vf.add_var(name=f"Ki_E_{name}")
    event_dict = {
        v_dc_ref: vf.add_const(1.0),
        Kp_E: vf.add_const(C_DC * chi_E * w_E),
        Ki_E: vf.add_const((C_DC / 2) * w_E * w_E),
    }


    # DC connection voltages
    v_dc = vf.add_var(name=f"v_dc_{name}", reference=VarPowerFlowReferenceType.Vdc)
    Pac = vf.add_var(name=f"Pac_{name}")

    # DC load current
    i_dc_L = vf.add_var(name=f"i_dc_L_{name}")

    inputs = [v_dc, Pac]

    # DC current and power
    p_dc = vf.add_var(name=f"p_dc_{name}")
    i_dc_L_mode = vf.add_var(name=f"i_dc_L_mode_{name}")

    # error
    err = vf.add_var(name=f"err_{name}")
    # integral state of I (PI)
    x_e = vf.add_var(name=f"x_e_{name}")
    dx_e = vf.add_diff_var(name=f"dx_e_{name}", base_var=x_e)
    p_dc_initial = vf.add_const(0.8)
    templ.block = Block(
        # --------------------------------------------------------------------------------------
        # STATE EQUATIONS (seconds + pu)
        # --------------------------------------------------------------------------------------
        state_eqs=[Ki_E * err],
        state_vars=[x_e],
        diff_vars=[dx_e],
        # --------------------------------------------------------------------------------------
        # ALGEBRAIC EQUATIONS
        # --------------------------------------------------------------------------------------
        algebraic_eqs=[
            err - (v_dc_ref*v_dc_ref - v_dc*v_dc),
            p_dc -(Kp_E*err + x_e), # PI output
            i_dc_L - i_dc_L_mode,
        ],
        algebraic_vars=[err, p_dc, i_dc_L],
        in_vars=inputs,
        out_vars=[i_dc_L],
        init_eqs={
            # Simulink initializes the DC PI output at the requested 0.8 pu
            # load power, but the sampled DC current remains zero at t = 0.
            # The first sampled update then applies p_dc / v_dc = 0.8 pu.
            i_dc_L: c0,
            err: v_dc_ref*v_dc_ref - v_dc*v_dc,
            x_e: p_dc_initial,
            p_dc: Kp_E*err + x_e,
        },
        diff_init_eqs={
            dx_e: Ki_E * err,
        },
        event_dict=event_dict,
        mode_dict={
            i_dc_L_mode: c0,
        },
        procedural_logic=[
            sampled_value(
                output=i_dc_L_mode,
                source=p_dc / sym.max(v_dc, eps),
                name=f"i_dc_L_sample_{name}",
            ),
        ],
    )

    return templ

def get_grid_side_converter_control_GFL(
        vf: VarFactory,
        name: str = "G4L_grid_side_converter_control",
) -> EmtModelTemplate:
    """
    This function connects all converter controls:
    - Clark-park transform
    - PLL with VSM
    - Virtual admittance - current limitation - current loop
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name
    templ.block.name = name


    clark_park_transforms_mdl = get_clark_park_transforms_qd_GFL(vf=vf).block
    PLL_mdl = get_PLL_GFL(vf=vf).block
    VSM_mdl = get_VSM_GFL(vf=vf).block
    VA_mdl = get_virtual_admittance_GFL(vf=vf).block
    current_limiter_mdl = get_current_limiter_GFL(vf=vf).block
    current_loop_mdl = get_current_loop_GFL(vf=vf).block

    # IN VARS: v_A, v_B, v_C, i_A, i_B, i_C
    templ.block.in_vars = [clark_park_transforms_mdl.in_vars[0], # v_A
                           clark_park_transforms_mdl.in_vars[1], # v_B
                           clark_park_transforms_mdl.in_vars[2], # v_C
                           clark_park_transforms_mdl.in_vars[3], # i_A
                           clark_park_transforms_mdl.in_vars[4], # i_B
                           clark_park_transforms_mdl.in_vars[5], # i_C
                           VSM_mdl.in_vars[2], # Pac
                           ]
    # OUT VARS:  v_con_A, v_con_B, v_con_C,
    templ.block.out_vars = [current_loop_mdl.out_vars[0],  # v_con_A
                            current_loop_mdl.out_vars[1],  # v_con_B
                            current_loop_mdl.out_vars[2],  # v_con_C
                            ]

    # CONNECT VARIABLES BETWEEN CHILDREN
    # phase_vsm
    _connect_with_shared_reference(vf=vf,
                                   target_var=clark_park_transforms_mdl.in_vars[6],
                                   source_var=VSM_mdl.out_vars[0],
                                   shared_name=f"{name}_phase_vsm")
    _connect_with_shared_reference(vf=vf,
                                   target_var=current_loop_mdl.in_vars[4],
                                   source_var=VSM_mdl.out_vars[0],
                                   shared_name=f"{name}_phase_vsm")
    # bus voltages into PLL
    _connect_with_shared_reference(vf=vf,
                                   target_var=PLL_mdl.in_vars[0],
                                   source_var=clark_park_transforms_mdl.in_vars[0],
                                   shared_name=f"{name}_v_A")
    _connect_with_shared_reference(vf=vf,
                                   target_var=PLL_mdl.in_vars[1],
                                   source_var=clark_park_transforms_mdl.in_vars[1],
                                   shared_name=f"{name}_v_B")
    _connect_with_shared_reference(vf=vf,
                                   target_var=PLL_mdl.in_vars[2],
                                   source_var=clark_park_transforms_mdl.in_vars[2],
                                   shared_name=f"{name}_v_C")
    # bus voltages into VSM for steady-state phase offset initialization
    _connect_with_shared_reference(vf=vf,
                                   target_var=VSM_mdl.in_vars[3],
                                   source_var=clark_park_transforms_mdl.in_vars[0],
                                   shared_name=f"{name}_v_A")
    _connect_with_shared_reference(vf=vf,
                                   target_var=VSM_mdl.in_vars[4],
                                   source_var=clark_park_transforms_mdl.in_vars[1],
                                   shared_name=f"{name}_v_B")
    _connect_with_shared_reference(vf=vf,
                                   target_var=VSM_mdl.in_vars[5],
                                   source_var=clark_park_transforms_mdl.in_vars[2],
                                   shared_name=f"{name}_v_C")
    # measured currents into VSM for steady-state phase offset initialization
    _connect_with_shared_reference(vf=vf,
                                   target_var=VSM_mdl.in_vars[6],
                                   source_var=clark_park_transforms_mdl.in_vars[3],
                                   shared_name=f"{name}_i_A")
    _connect_with_shared_reference(vf=vf,
                                   target_var=VSM_mdl.in_vars[7],
                                   source_var=clark_park_transforms_mdl.in_vars[4],
                                   shared_name=f"{name}_i_B")
    _connect_with_shared_reference(vf=vf,
                                   target_var=VSM_mdl.in_vars[8],
                                   source_var=clark_park_transforms_mdl.in_vars[5],
                                   shared_name=f"{name}_i_C")
    # omega VSM
    _connect_with_shared_reference(vf=vf,
                                   target_var=current_loop_mdl.in_vars[5],
                                   source_var=VSM_mdl.out_vars[1],
                                   shared_name=f"{name}_omega_vsm")
    # theta pll
    _connect_with_shared_reference(vf=vf,
                                   target_var=VSM_mdl.in_vars[0],
                                   source_var=PLL_mdl.out_vars[0],
                                   shared_name=f"{name}_theta_pll")
    # omega pll
    _connect_with_shared_reference(vf=vf,
                                   target_var=VSM_mdl.in_vars[1],
                                   source_var=PLL_mdl.out_vars[1],
                                   shared_name=f"{name}_omega_pll")
    # v_q
    _connect_with_shared_reference(vf=vf,
                                   target_var=VA_mdl.in_vars[0],
                                   source_var=clark_park_transforms_mdl.out_vars[0],
                                   shared_name=f"{name}_v_q")
    _connect_with_shared_reference(vf=vf,
                                   target_var=current_loop_mdl.in_vars[0],
                                   source_var=clark_park_transforms_mdl.out_vars[0],
                                   shared_name=f"{name}_v_q")
    # v_d
    _connect_with_shared_reference(vf=vf,
                                   target_var=VA_mdl.in_vars[1],
                                   source_var=clark_park_transforms_mdl.out_vars[1],
                                   shared_name=f"{name}_v_d")
    _connect_with_shared_reference(vf=vf,
                                   target_var=current_loop_mdl.in_vars[1],
                                   source_var=clark_park_transforms_mdl.out_vars[1],
                                   shared_name=f"{name}_v_d")
    # i_q
    _connect_with_shared_reference(vf=vf,
                                   target_var=current_loop_mdl.in_vars[2],
                                   source_var=clark_park_transforms_mdl.out_vars[2],
                                   shared_name=f"{name}_i_q")
    # i_d
    _connect_with_shared_reference(vf=vf,
                                   target_var=current_loop_mdl.in_vars[3],
                                   source_var=clark_park_transforms_mdl.out_vars[3],
                                   shared_name=f"{name}_i_d")
    # i_q out VA
    _connect_with_shared_reference(vf=vf,
                                   target_var=current_limiter_mdl.in_vars[0],
                                   source_var=VA_mdl.out_vars[0],
                                   shared_name=f"{name}_i_q_va")
    # i_d out VA
    _connect_with_shared_reference(vf=vf,
                                   target_var=current_limiter_mdl.in_vars[1],
                                   source_var=VA_mdl.out_vars[1],
                                   shared_name=f"{name}_i_d_va")
    # i_q_lim
    _connect_with_shared_reference(vf=vf,
                                   target_var=current_loop_mdl.in_vars[6],
                                   source_var=current_limiter_mdl.out_vars[0],
                                   shared_name=f"{name}_i_q_lim")
    # i_d_lim
    _connect_with_shared_reference(vf=vf,
                                   target_var=current_loop_mdl.in_vars[7],
                                   source_var=current_limiter_mdl.out_vars[1],
                                   shared_name=f"{name}_i_d_lim")

    # APPEND CHILDREN
    templ.block.children.append(clark_park_transforms_mdl)
    templ.block.children.append(PLL_mdl)
    templ.block.children.append(VSM_mdl)
    templ.block.children.append(VA_mdl)
    templ.block.children.append(current_limiter_mdl)
    templ.block.children.append(current_loop_mdl)

    # EXTERNAL MAPPING
    templ.block.external_mapping = {
        VarPowerFlowReferenceType.v_A: clark_park_transforms_mdl.in_vars[0],
        VarPowerFlowReferenceType.v_B: clark_park_transforms_mdl.in_vars[1],
        VarPowerFlowReferenceType.v_C: clark_park_transforms_mdl.in_vars[2],
        VarPowerFlowReferenceType.i_A: clark_park_transforms_mdl.in_vars[3],
        VarPowerFlowReferenceType.i_B: clark_park_transforms_mdl.in_vars[4],
        VarPowerFlowReferenceType.i_C: clark_park_transforms_mdl.in_vars[5],
        VarPowerFlowReferenceType.P: VSM_mdl.in_vars[2],
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

    # grid connection voltages
    v_A = vf.add_var(name=f"v_A_{name}", reference=VarPowerFlowReferenceType.v_A)
    v_B = vf.add_var(name=f"v_B_{name}", reference=VarPowerFlowReferenceType.v_B)
    v_C = vf.add_var(name=f"v_C_{name}", reference=VarPowerFlowReferenceType.v_C)

    # AC currents
    i_A = vf.add_var(name=f"i_f_A_{name}", reference=VarPowerFlowReferenceType.i_A)
    i_B = vf.add_var(name=f"i_f_B_{name}", reference=VarPowerFlowReferenceType.i_B)
    i_C = vf.add_var(name=f"i_f_C_{name}", reference=VarPowerFlowReferenceType.i_C)


    # theta pll
    phase_pll = vf.add_var(name=f"phase_pll_{name}")

    inputs = [v_A, v_B, v_C, i_A, i_B, i_C, phase_pll]

    # clark park voltage
    alpha_v = vf.add_var(name=f"alpha_v_{name}")
    beta_v = vf.add_var(name=f"beta_v_{name}")
    v_d = vf.add_var(name=f"v_d_{name}")
    v_q = vf.add_var(name=f"v_q_{name}")
    # clark park current
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
    Build the continuous symbolic PLL.

    The PI integrator and electrical angle remain DAE states.  The selected EMT
    integration method supplies their numerical kernel.  Only the explicit
    one-sample angle delay remains procedural because it is a genuine digital
    block in the Simulink model.

    :param vf: EMT variable factory.
    :param name: Symbolic block name.
    :return: Configured continuous PLL template.
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name
    templ.block.name = name

    v_A = vf.add_var(name=f"v_A_{name}", reference=VarPowerFlowReferenceType.v_A)
    v_B = vf.add_var(name=f"v_B_{name}", reference=VarPowerFlowReferenceType.v_B)
    v_C = vf.add_var(name=f"v_C_{name}", reference=VarPowerFlowReferenceType.v_C)
    inputs = [v_A, v_B, v_C]

    tau_pll: float = 0.01
    xi_pll: float = 0.707
    vac_peak_pu: float = np.sqrt(2.0)
    kp_pll_value: float = 4.0 * xi_pll * xi_pll / (tau_pll * vac_peak_pu)
    ki_pll_value: float = kp_pll_value / tau_pll
    Kp_pll = vf.add_var(name=f"Kp_pll_{name}")
    Ki_pll = vf.add_var(name=f"Ki_pll_{name}")

    alpha = vf.add_var(name=f"alpha_{name}")
    beta = vf.add_var(name=f"beta_{name}")
    v_q = vf.add_var(name=f"v_q_{name}")
    v_d = vf.add_var(name=f"v_d_{name}")

    x_e_pll = vf.add_var(name=f"x_e_pll_{name}")
    dx_e_pll = vf.add_diff_var(name=f"dx_e_pll_{name}", base_var=x_e_pll)
    theta_pll = vf.add_var(name=f"theta_pll_{name}")
    d_theta_pll = vf.add_diff_var(name=f"d_theta_pll_{name}", base_var=theta_pll)
    w_pll = vf.add_var(name=f"w_pll_{name}")
    theta_pll_mode = vf.add_var(name=f"theta_pll_mode_{name}")

    omega_init: float = 2.0 * np.pi * 50.0
    theta_init = vf.add_const(-np.pi / 2.0)

    templ.block = Block(
        state_eqs=[
            Ki_pll * (-v_d),
            w_pll,
        ],
        state_vars=[x_e_pll, theta_pll],
        diff_vars=[dx_e_pll, d_theta_pll],
        algebraic_eqs=[
            alpha - (1.0 / 3.0) * (2.0 * v_A - v_B - v_C),
            beta - (1.0 / 3.0) * (-np.sqrt(3.0) * v_B + np.sqrt(3.0) * v_C),
            v_q - (alpha * cos(theta_pll_mode) - beta * sin(theta_pll_mode)),
            v_d - (alpha * sin(theta_pll_mode) + beta * cos(theta_pll_mode)),
            w_pll - (-v_d * Kp_pll + x_e_pll),
        ],
        algebraic_vars=[alpha, beta, v_q, v_d, w_pll],
        in_vars=inputs,
        out_vars=[theta_pll, w_pll],
        init_eqs={
            x_e_pll: vf.add_const(omega_init),
            theta_pll: theta_init,
            alpha: (1.0 / 3.0) * (2.0 * v_A - v_B - v_C),
            beta: (1.0 / 3.0) * (-np.sqrt(3.0) * v_B + np.sqrt(3.0) * v_C),
            v_q: alpha * cos(theta_pll_mode) - beta * sin(theta_pll_mode),
            v_d: alpha * sin(theta_pll_mode) + beta * cos(theta_pll_mode),
            w_pll: -v_d * Kp_pll + x_e_pll,
        },
        diff_init_eqs={
            dx_e_pll: Ki_pll * (-v_d),
            d_theta_pll: w_pll,
        },
        event_dict={
            Kp_pll: vf.add_const(kp_pll_value),
            Ki_pll: vf.add_const(ki_pll_value),
        },
        mode_dict={
            theta_pll_mode: theta_init,
        },
        procedural_logic=[
            sampled_value(
                output=theta_pll_mode,
                source=theta_pll,
                name=f"theta_pll_sample_{name}",
            ),
        ],
    )

    templ.block.external_mapping = {
        VarPowerFlowReferenceType.v_A: v_A,
        VarPowerFlowReferenceType.v_B: v_B,
        VarPowerFlowReferenceType.v_C: v_C,
    }

    return templ


def get_VSM_GFL(vf: VarFactory, name: str = "G4L_VSM") -> EmtModelTemplate:
    """
    Build the continuous symbolic virtual synchronous machine.

    :param vf: EMT variable factory.
    :param name: Symbolic block name.
    :return: Configured continuous VSM template.
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name
    templ.block.name = name

    eps = vf.add_const(1.0e-9)

    Pac = vf.add_var(name=f"Pac_{name}")
    w_pll = vf.add_var(name=f"w_pll_{name}")
    theta_pll = vf.add_var(name=f"theta_pll_{name}")
    v_A = vf.add_var(name=f"v_A_{name}", reference=VarPowerFlowReferenceType.v_A)
    v_B = vf.add_var(name=f"v_B_{name}", reference=VarPowerFlowReferenceType.v_B)
    v_C = vf.add_var(name=f"v_C_{name}", reference=VarPowerFlowReferenceType.v_C)
    i_A = vf.add_var(name=f"i_A_{name}", reference=VarPowerFlowReferenceType.i_A)
    i_B = vf.add_var(name=f"i_B_{name}", reference=VarPowerFlowReferenceType.i_B)
    i_C = vf.add_var(name=f"i_C_{name}", reference=VarPowerFlowReferenceType.i_C)
    inputs = [theta_pll, w_pll, Pac, v_A, v_B, v_C, i_A, i_B, i_C]

    P_ref = vf.add_var(name=f"P_ref_{name}")
    k_d = vf.add_var(name=f"k_d_{name}")
    omega_ref = vf.add_var(name=f"omega_ref_{name}")
    H = vf.add_var(name=f"H_{name}")
    Sb = vf.add_var(name=f"Sb_{name}")
    k_p = vf.add_var(name=f"k_p_{name}")

    sb_va: float = 2000000.0
    omega_value: float = 2.0 * np.pi * 50.0
    vdc_ref_si: float = 1200.0
    c_dc_si: float = sb_va * 0.02 * 2.0 / (vdc_ref_si * vdc_ref_si)
    c_pu: float = c_dc_si * vdc_ref_si * vdc_ref_si / sb_va
    z_apparent: float = 0.5
    chi: float = 0.8
    k_h: float = (1.935 / 2.0 / 50.0) / (1.0 - 665.0 * 665.0 / (vdc_ref_si * vdc_ref_si))
    k_p_damping: float = (
        chi * 2.0 * np.sqrt(k_h * (1.0 / z_apparent) * omega_value * 2.0 / c_pu)
        / (k_h * (1.0 / z_apparent) * omega_value)
    )

    x = vf.add_var(name=f"x_{name}")
    y = vf.add_var(name=f"y_{name}")
    dy = vf.add_diff_var(name=f"dy_{name}", base_var=y)
    phase_vsm = vf.add_var(name=f"phase_vsm_{name}")
    d_phase_vsm = vf.add_diff_var(name=f"d_phase_vsm_{name}", base_var=phase_vsm)
    omega_vsm = vf.add_var(name=f"omega_vsm_{name}")

    y_rate_expr = ((1.0 - y) * k_p + P_ref - Pac + x) / (2.0 * sym.max(H, eps))
    phase_init = vf.add_const(-np.pi / 2.0 - 0.4)

    templ.block = Block(
        state_eqs=[
            y_rate_expr,
            omega_vsm,
        ],
        state_vars=[y, phase_vsm],
        diff_vars=[dy, d_phase_vsm],
        algebraic_eqs=[
            x - ((w_pll / sym.max(omega_ref, eps)) - y) * k_d,
            omega_vsm - y * omega_ref,
        ],
        algebraic_vars=[x, omega_vsm],
        in_vars=inputs,
        out_vars=[phase_vsm, omega_vsm],
        init_eqs={
            y: vf.add_const(1.0),
            phase_vsm: phase_init,
            x: ((w_pll / sym.max(omega_ref, eps)) - y) * k_d,
            omega_vsm: y * omega_ref,
        },
        diff_init_eqs={
            dy: y_rate_expr,
            d_phase_vsm: omega_vsm,
        },
        event_dict={
            P_ref: vf.add_const(-0.8),
            k_d: vf.add_const(k_p_damping * (c_pu / 2.0 * (1.0 / z_apparent) * omega_value)),
            omega_ref: vf.add_const(omega_value),
            H: vf.add_const(c_pu / (k_h * 4.0)),
            Sb: vf.add_const(1.0),
            k_p: vf.add_const(20.0),
        },
    )

    templ.block.external_mapping = {
        VarPowerFlowReferenceType.P: Pac,
        VarPowerFlowReferenceType.v_A: v_A,
        VarPowerFlowReferenceType.v_B: v_B,
        VarPowerFlowReferenceType.v_C: v_C,
        VarPowerFlowReferenceType.i_A: i_A,
        VarPowerFlowReferenceType.i_B: i_B,
        VarPowerFlowReferenceType.i_C: i_C,
    }

    return templ


def get_virtual_admittance_GFL(
        vf: VarFactory,
        name: str = "G4L_Virtual_admittance",
) -> EmtModelTemplate:
    """
    Build the continuous symbolic virtual-admittance controller.

    Each transfer-function path is expressed as a second-order state-space
    realization.  The EMT solver discretizes these states with its selected
    integration method.

    :param vf: EMT variable factory.
    :param name: Symbolic block name.
    :return: Configured continuous virtual-admittance template.
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name
    templ.block.name = name

    c0 = vf.add_const(0.0)
    eps = vf.add_const(1.0e-12)

    v_q = vf.add_var(name=f"v_q_{name}")
    v_d = vf.add_var(name=f"v_d_{name}")
    inputs = [v_q, v_d]

    v_q_ref = vf.add_var(name=f"v_q_ref_{name}")
    v_d_ref = vf.add_var(name=f"v_d_ref_{name}")

    omega_value: float = 2.0 * np.pi * 50.0
    pu_z_to_emt: float = 3.0
    zvirtual_emt: float = pu_z_to_emt * 0.6
    r_l_ratio: float = 0.1
    Lv = vf.add_const(zvirtual_emt / omega_value)
    Rv = vf.add_const(zvirtual_emt * r_l_ratio)
    omega_ref = vf.add_const(omega_value)

    err_q = vf.add_var(name=f"err_q_{name}")
    err_d = vf.add_var(name=f"err_d_{name}")
    y1 = vf.add_var(name=f"y1_{name}")
    y2 = vf.add_var(name=f"y2_{name}")
    y3 = vf.add_var(name=f"y3_{name}")
    y4 = vf.add_var(name=f"y4_{name}")
    i_q_out_VA = vf.add_var(name=f"i_q_out_VA_{name}")
    i_d_out_VA = vf.add_var(name=f"i_d_out_VA_{name}")

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

    n1_main = Lv
    n0_main = Rv
    n0_cross = Lv * omega_ref
    d2 = Lv * Lv
    d1 = 2.0 * Lv * Rv
    d0 = Lv * Lv * omega_ref * omega_ref + Rv * Rv

    x2_dot_1 = (err_q - d1 * x2_1 - d0 * x1_1) / sym.max(d2, eps)
    x2_dot_2 = (err_d - d1 * x2_2 - d0 * x1_2) / sym.max(d2, eps)
    x2_dot_3 = (err_q - d1 * x2_3 - d0 * x1_3) / sym.max(d2, eps)
    x2_dot_4 = (err_d - d1 * x2_4 - d0 * x1_4) / sym.max(d2, eps)

    templ.block = Block(
        state_eqs=[
            x2_1,
            x2_dot_1,
            x2_2,
            x2_dot_2,
            x2_3,
            x2_dot_3,
            x2_4,
            x2_dot_4,
        ],
        state_vars=[x1_1, x2_1, x1_2, x2_2, x1_3, x2_3, x1_4, x2_4],
        diff_vars=[dx1_1, dx2_1, dx1_2, dx2_2, dx1_3, dx2_3, dx1_4, dx2_4],
        algebraic_eqs=[
            err_q - (v_q_ref - v_q),
            err_d - (v_d_ref - v_d),
            y1 - (n1_main * x2_1 + n0_main * x1_1),
            y2 - n0_cross * x1_2,
            y3 - n0_cross * x1_3,
            y4 - (n1_main * x2_4 + n0_main * x1_4),
            i_q_out_VA - (y1 - y2),
            i_d_out_VA - (y3 + y4),
        ],
        algebraic_vars=[err_q, err_d, y1, y2, y3, y4, i_q_out_VA, i_d_out_VA],
        in_vars=inputs,
        out_vars=[i_q_out_VA, i_d_out_VA],
        init_eqs={
            x1_1: c0,
            x2_1: c0,
            x1_2: c0,
            x2_2: c0,
            x1_3: c0,
            x2_3: c0,
            x1_4: c0,
            x2_4: c0,
            err_q: v_q_ref - v_q,
            err_d: v_d_ref - v_d,
            y1: n1_main * x2_1 + n0_main * x1_1,
            y2: n0_cross * x1_2,
            y3: n0_cross * x1_3,
            y4: n1_main * x2_4 + n0_main * x1_4,
            i_q_out_VA: y1 - y2,
            i_d_out_VA: y3 + y4,
        },
        diff_init_eqs={
            dx1_1: x2_1,
            dx2_1: x2_dot_1,
            dx1_2: x2_2,
            dx2_2: x2_dot_2,
            dx1_3: x2_3,
            dx2_3: x2_dot_3,
            dx1_4: x2_4,
            dx2_4: x2_dot_4,
        },
        event_dict={
            v_q_ref: vf.add_const(np.sqrt(2.0)),
            v_d_ref: vf.add_const(0.0),
        },
    )

    return templ


def get_current_limiter_GFL(vf: VarFactory, name: str = "G4L_current_limiter") -> EmtModelTemplate:
    """
    Build the combinational d-priority limiter used by Simulink.

    :param vf: EMT variable factory.
    :param name: Symbolic block name.
    :return: Configured current-limiter template.
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

    Imax = vf.add_const(1.1 * np.sqrt(2.0) / 3.0)
    i_d_lim_expr = sym.max(-Imax, sym.min(i_d, Imax))
    i_q_cap_expr = sym.sqrt(sym.max(Imax * Imax - i_d_lim_expr * i_d_lim_expr, c0))
    i_q_lim_expr = sym.max(-i_q_cap_expr, sym.min(i_q, i_q_cap_expr))

    templ.block = Block(
        state_eqs=[],
        state_vars=[],
        diff_vars=[],
        algebraic_eqs=[
            i_q_lim - i_q_lim_expr,
            i_d_lim - i_d_lim_expr,
        ],
        algebraic_vars=[i_q_lim, i_d_lim],
        in_vars=inputs,
        out_vars=[i_q_lim, i_d_lim],
        init_eqs={
            i_q_lim: i_q_lim_expr,
            i_d_lim: i_d_lim_expr,
        },
    )

    return templ

def get_current_loop_GFL(vf: VarFactory, name: str = "G4L_current_loop") -> EmtModelTemplate:
    """
    Build the continuous current controller and inverse qd/abc transform.

    The feed-forward filters and both PI integrators are symbolic DAE states.
    Their numerical discretization is delegated to the EMT solver.

    :param vf: EMT variable factory.
    :param name: Symbolic block name.
    :return: Configured continuous current-loop template.
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name
    templ.block.name = name

    c0 = vf.add_const(0.0)
    c_sqrt3 = vf.add_const(np.sqrt(3.0))

    v_d = vf.add_var(name=f"v_d_{name}")
    v_q = vf.add_var(name=f"v_q_{name}")
    i_d = vf.add_var(name=f"i_d_{name}")
    i_q = vf.add_var(name=f"i_q_{name}")
    phase_pll = vf.add_var(name=f"phase_pll_{name}")
    omega_pll = vf.add_var(name=f"omega_pll_{name}")
    i_q_lim = vf.add_var(name=f"i_q_lim_{name}")
    i_d_lim = vf.add_var(name=f"i_d_lim_{name}")
    inputs = [v_q, v_d, i_q, i_d, phase_pll, omega_pll, i_q_lim, i_d_lim]

    v_ffw_q = vf.add_var(name=f"v_ffw_q_{name}")
    v_ffw_d = vf.add_var(name=f"v_ffw_d_{name}")
    dv_ffw_q = vf.add_diff_var(name=f"dv_ffw_q_{name}", base_var=v_ffw_q)
    dv_ffw_d = vf.add_diff_var(name=f"dv_ffw_d_{name}", base_var=v_ffw_d)
    tau_ffw = vf.add_const(0.0005)

    tau_cc: float = 0.001
    omega_value: float = 2.0 * np.pi * 50.0
    pu_z_to_emt: float = 3.0
    r_f_pu: float = pu_z_to_emt * (0.1 / 10.0)
    x_f_pu: float = pu_z_to_emt * (1.0 / 10.0)
    l_f_value: float = x_f_pu / omega_value
    Kp_cc = vf.add_const(l_f_value / tau_cc)
    Ki_cc = vf.add_const(r_f_pu / tau_cc)
    L_f = vf.add_const(l_f_value)

    err_q = vf.add_var(name=f"err_q_{name}")
    err_d = vf.add_var(name=f"err_d_{name}")
    x_e_q = vf.add_var(name=f"x_e_q_{name}")
    dx_e_q = vf.add_diff_var(name=f"dx_e_q_{name}", base_var=x_e_q)
    x_e_d = vf.add_var(name=f"x_e_d_{name}")
    dx_e_d = vf.add_diff_var(name=f"dx_e_d_{name}", base_var=x_e_d)
    y_q = vf.add_var(name=f"y_q_{name}")
    y_d = vf.add_var(name=f"y_d_{name}")

    v_con_q = vf.add_var(name=f"v_con_q_{name}")
    v_con_d = vf.add_var(name=f"v_con_d_{name}")
    alpha = vf.add_var(name=f"alpha_{name}")
    beta = vf.add_var(name=f"beta_{name}")
    v_con_A = vf.add_var(name=f"v_con_A_{name}")
    v_con_B = vf.add_var(name=f"v_con_B_{name}")
    v_con_C = vf.add_var(name=f"v_con_C_{name}")

    v_ffw_q_dot = (v_q - v_ffw_q) / tau_ffw
    v_ffw_d_dot = (v_d - v_ffw_d) / tau_ffw
    x_e_q_dot = Ki_cc * err_q
    x_e_d_dot = Ki_cc * err_d

    templ.block = Block(
        state_eqs=[
            v_ffw_q_dot,
            v_ffw_d_dot,
            x_e_q_dot,
            x_e_d_dot,
        ],
        state_vars=[v_ffw_q, v_ffw_d, x_e_q, x_e_d],
        diff_vars=[dv_ffw_q, dv_ffw_d, dx_e_q, dx_e_d],
        algebraic_eqs=[
            err_q - (i_q_lim - i_q),
            err_d - (i_d_lim - i_d),
            y_q - (Kp_cc * err_q + x_e_q),
            y_d - (Kp_cc * err_d + x_e_d),
            # Current and PI signs are reversed with respect to Simulink.  The
            # q-axis cross-coupling is therefore positive in VeraGrid.
            v_con_q - (v_ffw_q + y_q + omega_pll * L_f * i_d),
            v_con_d - (v_ffw_d + y_d - omega_pll * L_f * i_q),
            alpha - (v_con_q * cos(phase_pll) + v_con_d * sin(phase_pll)),
            beta - (-v_con_q * sin(phase_pll) + v_con_d * cos(phase_pll)),
            v_con_A - alpha,
            v_con_B - 0.5 * (-alpha - c_sqrt3 * beta),
            v_con_C - 0.5 * (-alpha + c_sqrt3 * beta),
        ],
        algebraic_vars=[
            err_q,
            err_d,
            y_q,
            y_d,
            v_con_q,
            v_con_d,
            alpha,
            beta,
            v_con_A,
            v_con_B,
            v_con_C,
        ],
        in_vars=inputs,
        # Each physical controller voltage is one output. Repeating the same
        # Var objects produced six indistinguishable GUI ports without adding
        # any mathematical degree of freedom.
        out_vars=[v_con_A, v_con_B, v_con_C],
        init_eqs={
            v_ffw_q: c0,
            v_ffw_d: c0,
            x_e_q: c0,
            x_e_d: c0,
            err_q: i_q_lim - i_q,
            err_d: i_d_lim - i_d,
            y_q: Kp_cc * err_q + x_e_q,
            y_d: Kp_cc * err_d + x_e_d,
            v_con_q: v_ffw_q + y_q + omega_pll * L_f * i_d,
            v_con_d: v_ffw_d + y_d - omega_pll * L_f * i_q,
            alpha: v_con_q * cos(phase_pll) + v_con_d * sin(phase_pll),
            beta: -v_con_q * sin(phase_pll) + v_con_d * cos(phase_pll),
            v_con_A: alpha,
            v_con_B: 0.5 * (-alpha - c_sqrt3 * beta),
            v_con_C: 0.5 * (-alpha + c_sqrt3 * beta),
        },
        diff_init_eqs={
            dv_ffw_q: v_ffw_q_dot,
            dv_ffw_d: v_ffw_d_dot,
            dx_e_q: x_e_q_dot,
            dx_e_d: x_e_d_dot,
        },
    )

    return templ


def get_complete_load_template_G4L(
        vf: VarFactory,
        name: str = "G4L_complete_load",
) -> EmtModelTemplate:
    """
    Complete GFL load composed by:
    - grid side converter
    - load side converter
    - grid side converter control:
        - clark park transforms
        - PLL + VSM
        - Virtual Admittance
        - Current Limitation
        - Current control
    - Load side converter control

    :param vf: EMT variable factory.
    :param name: Symbolic block name.
    :return: Configured complete GFL load template.
    """

    templ = EmtModelTemplate()
    templ.tpe = DeviceType.LoadDevice
    templ.name = name

    templ.block.name = name

    grid_side_vsc_mdl = get_grid_side_converter_GFL(vf=vf).block
    load_side_vsc_mdl = get_load_side_converter_GFL(vf=vf).block
    grid_side_ctrl_mdl = get_grid_side_converter_control_GFL(vf=vf).block
    load_side_ctrl_mdl = get_load_side_converter_control_GFL(vf=vf).block

    templ.block.in_vars = [grid_side_vsc_mdl.in_vars[0],  # v_A
                           grid_side_vsc_mdl.in_vars[1],  # v_B
                           grid_side_vsc_mdl.in_vars[2],  # v_C
                           ]

    templ.block.out_vars = [grid_side_vsc_mdl.out_vars[0],  # i_A
                            grid_side_vsc_mdl.out_vars[1],  # i_B
                            grid_side_vsc_mdl.out_vars[2],  # i_C
                            ]

    _connect_with_shared_reference(vf=vf,
                                   target_var=load_side_vsc_mdl.in_vars[0],
                                   source_var=grid_side_vsc_mdl.out_vars[3],
                                   shared_name=f"{name}_i_dc_grid")
    _connect_with_shared_reference(vf=vf,
                                   target_var=grid_side_vsc_mdl.in_vars[3],
                                   source_var=load_side_vsc_mdl.out_vars[0],
                                   shared_name=f"{name}_v_dc")
    _connect_with_shared_reference(vf=vf,
                                   target_var=load_side_ctrl_mdl.in_vars[0],
                                   source_var=load_side_vsc_mdl.out_vars[0],
                                   shared_name=f"{name}_v_dc")
    _connect_with_shared_reference(vf=vf,
                                   target_var=load_side_vsc_mdl.in_vars[1],
                                   source_var=load_side_ctrl_mdl.out_vars[0],
                                   shared_name=f"{name}_i_dc_load")
    _connect_with_shared_reference(vf=vf,
                                   target_var=grid_side_vsc_mdl.in_vars[4],
                                   source_var=grid_side_ctrl_mdl.out_vars[0],
                                   shared_name=f"{name}_v_con_A")
    _connect_with_shared_reference(vf=vf,
                                   target_var=grid_side_vsc_mdl.in_vars[5],
                                   source_var=grid_side_ctrl_mdl.out_vars[1],
                                   shared_name=f"{name}_v_con_B")
    _connect_with_shared_reference(vf=vf,
                                   target_var=grid_side_vsc_mdl.in_vars[6],
                                   source_var=grid_side_ctrl_mdl.out_vars[2],
                                   shared_name=f"{name}_v_con_C")
    _connect_with_shared_reference(vf=vf,
                                   target_var=grid_side_ctrl_mdl.in_vars[0],
                                   source_var=grid_side_vsc_mdl.in_vars[0],
                                   shared_name=f"{grid_side_ctrl_mdl.name}_v_A")
    _connect_with_shared_reference(vf=vf,
                                   target_var=grid_side_ctrl_mdl.in_vars[1],
                                   source_var=grid_side_vsc_mdl.in_vars[1],
                                   shared_name=f"{grid_side_ctrl_mdl.name}_v_B")
    _connect_with_shared_reference(vf=vf,
                                   target_var=grid_side_ctrl_mdl.in_vars[2],
                                   source_var=grid_side_vsc_mdl.in_vars[2],
                                   shared_name=f"{grid_side_ctrl_mdl.name}_v_C")
    _connect_with_shared_reference(vf=vf,
                                   target_var=grid_side_ctrl_mdl.in_vars[3],
                                   source_var=grid_side_vsc_mdl.out_vars[0],
                                   shared_name=f"{grid_side_ctrl_mdl.name}_i_A")
    _connect_with_shared_reference(vf=vf,
                                   target_var=grid_side_ctrl_mdl.in_vars[4],
                                   source_var=grid_side_vsc_mdl.out_vars[1],
                                   shared_name=f"{grid_side_ctrl_mdl.name}_i_B")
    _connect_with_shared_reference(vf=vf,
                                   target_var=grid_side_ctrl_mdl.in_vars[5],
                                   source_var=grid_side_vsc_mdl.out_vars[2],
                                   shared_name=f"{grid_side_ctrl_mdl.name}_i_C")
    _connect_with_shared_reference(vf=vf,
                                   target_var=grid_side_ctrl_mdl.in_vars[6],
                                   source_var=grid_side_vsc_mdl.out_vars[4],
                                   shared_name=f"{name}_Pac_bus")
    _connect_with_shared_reference(vf=vf,
                                   target_var=load_side_ctrl_mdl.in_vars[1],
                                   source_var=grid_side_vsc_mdl.out_vars[5],
                                   shared_name=f"{name}_Pac_grid")

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
