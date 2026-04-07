# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Dict
import numpy as np

from VeraGridEngine import EmtLineTypes
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.enumerations import DeviceType, VarPowerFlowRefferenceType
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Var, Expr

def get_pi_line_emt_template(
        grid: MultiCircuit,
        line: Line,
        name: str = EmtLineTypes.PI) -> EmtModelTemplate:
    """
    :param grid: Multicircuit
    :param line: Line object to apply the template
    :param name: string to identify the line and model
    :return: EmtModelTemplate
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.LineDevice
    templ.name = name

    templ.block.name = EmtLineTypes.PI

    vf: VarFactory = grid.var_factory
    fbase: float = grid.fBase
    sbase: float = grid.Sbase

    c0 = vf.add_const(0.0)

    # -----------------------------
    # Phase mask from the line itself [N,A,B,C]
    # -----------------------------
    ph_mask = np.array([
        bool(line.ys.phN),
        bool(line.ys.phA),
        bool(line.ys.phB),
        bool(line.ys.phC),
    ], dtype=bool)

    ph_labels = ["N", "A", "B", "C"]
    idx_global = np.where(ph_mask)[0]  # indices in global NABC convention
    active_ph = [ph_labels[i] for i in idx_global]
    m = len(active_ph)

    if m == 0:
        raise ValueError(f"PI line '{name}' has no enabled phases in line.ys")

    # -----------------------------
    # Create ONLY active terminal voltage input vars
    #    (Connection to buses is done by the assembler, not here.)
    # -----------------------------
    # vf_vars = [vf.add_var(f"vf_{ph}_{name}") for ph in active_ph]
    # vt_vars = [vf.add_var(f"vt_{ph}_{name}") for ph in active_ph]

    v_N_f = vf.add_var(name=f"vf_N_{name}", reference=VarPowerFlowRefferenceType.vf_N) if ph_mask[0] else None
    v_A_f = vf.add_var(name=f"vf_A_{name}", reference=VarPowerFlowRefferenceType.vf_A) if ph_mask[1] else None
    v_B_f = vf.add_var(name=f"vf_B_{name}", reference=VarPowerFlowRefferenceType.vf_B) if ph_mask[2] else None
    v_C_f = vf.add_var(name=f"vf_C_{name}", reference=VarPowerFlowRefferenceType.vf_C) if ph_mask[3] else None

    v_N_t = vf.add_var(name=f"vt_N_{name}", reference=VarPowerFlowRefferenceType.vt_N) if ph_mask[0] else None
    v_A_t = vf.add_var(name=f"vt_A_{name}", reference=VarPowerFlowRefferenceType.vt_A) if ph_mask[1] else None
    v_B_t = vf.add_var(name=f"vt_B_{name}", reference=VarPowerFlowRefferenceType.vt_B) if ph_mask[2] else None
    v_C_t = vf.add_var(name=f"vt_C_{name}", reference=VarPowerFlowRefferenceType.vt_C) if ph_mask[3] else None

    vf_vars = [v for v in (v_N_f, v_A_f, v_B_f, v_C_f) if v is not None]
    vt_vars = [v for v in (v_N_t, v_A_t, v_B_t, v_C_t) if v is not None]

    # diff vars used for initialization
    d_vf_vars = [vf.add_diff_var(name=f"d_vf_{ph}_{name}", base_var=v_base) for ph, v_base in
                 zip(active_ph, vf_vars)]
    d_vt_vars = [vf.add_diff_var(name=f"d_vt_{ph}_{name}", base_var=v_base) for ph, v_base in
                 zip(active_ph, vt_vars)]

    for d_var in d_vf_vars:
        templ.block.event_dict[d_var] = vf.add_const(None)
    for d_var in d_vt_vars:
        templ.block.event_dict[d_var] = vf.add_const(None)

    # -----------------------------
    # Compute continuous parameters in pu (R, L, G_end, C) in ACTIVE subspace
    # -----------------------------
    w0 = 2.0 * np.pi * float(fbase)

    Vbase = line.bus_from.Vnom * 1e3
    S = float(sbase) * 1e6
    Zbase = (Vbase * Vbase) / S
    Ybase = 1.0 / Zbase

    Z_phys = line.template.z_nabc * line.length
    Y_phys = line.template.y_nabc * line.length

    # pu conversion
    Z_pu = Z_phys / Zbase
    Y_pu = Y_phys / Ybase

    R_full = np.real(Z_pu)
    X_full = np.imag(Z_pu)
    L_full = X_full / (w0 + 1e-20)

    Gsh_full = np.real(Y_pu)
    Bsh_full = np.imag(Y_pu)
    C_full = Bsh_full / (w0 + 1e-20)

    G_end_full = 0.5 * Gsh_full
    C_end_full = 0.5 * C_full

    n_mat = R_full.shape[0]

    if R_full.shape[0] != R_full.shape[1]:
        raise ValueError(
            f"Line '{name}' has a non-square Z matrix with shape {R_full.shape}."
        )

    if L_full.shape != R_full.shape or C_end_full.shape != R_full.shape:
        raise ValueError(
            f"Line '{name}' has inconsistent matrix shapes: "
            f"R={R_full.shape}, L={L_full.shape}, C_end={C_end_full.shape}."
        )

    if n_mat == 3:
        # Matrices are stored in compact ABC order
        if 0 in idx_global:
            raise ValueError(
                f"Line '{name}' has N phase enabled but template matrices are 3x3 (ABC)."
            )
        idx_mat = idx_global - 1  # A->0, B->1, C->2

    elif n_mat == 4:
        # Matrices are stored in full NABC order
        idx_mat = idx_global

    else:
        raise ValueError(
            f"Unsupported template matrix size {R_full.shape} for line '{name}' "
            f"(expected 3x3 or 4x4)."
        )

    idx_mat = np.array(idx_mat, dtype=int)

    R = R_full[np.ix_(idx_mat, idx_mat)]
    L = L_full[np.ix_(idx_mat, idx_mat)]
    C = C_end_full[np.ix_(idx_mat, idx_mat)]
    # -----------------------------
    # Create model vars
    # -----------------------------
    i_ser = [vf.add_var(f"i_ser_{name}_{k}") for k in range(m)]
    q_f = [vf.add_var(f"q_f_{name}_{k}") for k in range(m)]
    q_t = [vf.add_var(f"q_t_{name}_{k}") for k in range(m)]

    di_ser = [vf.add_diff_var(name=f"di_ser_{name}_{k}", base_var=i_ser[k]) for k in range(m)]
    dq_f = [vf.add_diff_var(name=f"dq_f_{name}_{k}", base_var=q_f[k]) for k in range(m)]
    dq_t = [vf.add_diff_var(name=f"dq_t_{name}_{k}", base_var=q_t[k]) for k in range(m)]

    i_cap_f = [vf.add_var(f"i_cap_f_{name}_{k}") for k in range(m)]
    i_cap_t = [vf.add_var(f"i_cap_t_{name}_{k}") for k in range(m)]
    if_act = [vf.add_var(f"if_{name}_{k}") for k in range(m)]
    it_act = [vf.add_var(f"it_{name}_{k}") for k in range(m)]

    # -----------------------------
    # Build block
    # -----------------------------
    templ.block.in_vars = vf_vars + vt_vars
    templ.block.state_vars = i_ser + q_f + q_t
    templ.block.diff_vars = di_ser + dq_f + dq_t
    templ.block.algebraic_vars = i_cap_f + i_cap_t + if_act + it_act

    # -----------------------------
    # State equations
    # -----------------------------
    state_eqs = []
    #  L * di_ser + R * i_ser - (vf - vt) = 0
    # di_ser = L^-1 * [(vf - vt) - R * i_ser]
    L_inv = np.linalg.inv(L)

    #Equations for the series branch currents (i_ser)
    for a in range(m):
        expr_rhs = c0
        for b in range(m):
            Linv_ab = float(L_inv[a, b])
            if Linv_ab != 0.0:
                # term_b = (vf_b - vt_b) - sum_k R[b,k]*i_ser[k]
                term_b = (vf_vars[b] - vt_vars[b])
                for k in range(m):
                    R_bk = float(R[b, k])
                    if R_bk != 0.0:
                        term_b = term_b - R_bk * i_ser[k]
                expr_rhs = expr_rhs + Linv_ab * term_b
        state_eqs.append(expr_rhs)

    # Equations for the charge of the 'from' side capacitor (q_f)
    # Capacitor charge dynamics:
    #   dq_f = i_cap_f
    #   dq_t = i_cap_t
    for a in range(m):
        state_eqs.append(i_cap_f[a])
    for a in range(m):
        state_eqs.append(i_cap_t[a])

    templ.block.state_eqs = state_eqs

    # -----------------------------
    # Algebraic equations
    # -----------------------------
    alg_eqs = []

    for a in range(m):
        rhs_q = c0
        for b in range(m):
            Cab = float(C[a, b])
            if Cab != 0.0:
                rhs_q = rhs_q + Cab * vf_vars[b]
        alg_eqs.append(q_f[a] - rhs_q)

    for a in range(m):
        rhs_q = c0
        for b in range(m):
            Cab = float(C[a, b])
            if Cab != 0.0:
                rhs_q = rhs_q + Cab * vt_vars[b]
        alg_eqs.append(q_t[a] - rhs_q)

    # small numerical damping to clean up high freq oscillations
    G_damp = 1e-5

    for a in range(m):
        # Terminal current at from-bus: if = i_ser + i_cap_f + G_damp*v
        alg_eqs.append(if_act[a] - (i_ser[a] + i_cap_f[a] + G_damp * vf_vars[a]))
        # Terminal current at to-bus: it = -i_ser + i_cap_t + G_damp*v
        alg_eqs.append(it_act[a] - (-i_ser[a] + i_cap_t[a] + G_damp * vt_vars[a]))

    templ.block.algebraic_eqs = alg_eqs

    # outputs
    templ.block.out_vars = if_act + it_act

    # -----------------------------
    # external mapping for KCL stamping in EmtProblemDae
    # -----------------------------
    if_keys = {
        "N": VarPowerFlowRefferenceType.if_N,
        "A": VarPowerFlowRefferenceType.if_A,
        "B": VarPowerFlowRefferenceType.if_B,
        "C": VarPowerFlowRefferenceType.if_C,
    }
    it_keys = {
        "N": VarPowerFlowRefferenceType.it_N,
        "A": VarPowerFlowRefferenceType.it_A,
        "B": VarPowerFlowRefferenceType.it_B,
        "C": VarPowerFlowRefferenceType.it_C,
    }
    vf_keys = {
        "N": VarPowerFlowRefferenceType.vf_N,
        "A": VarPowerFlowRefferenceType.vf_A,
        "B": VarPowerFlowRefferenceType.vf_B,
        "C": VarPowerFlowRefferenceType.vf_C,
    }
    vt_keys = {
        "N": VarPowerFlowRefferenceType.vt_N,
        "A": VarPowerFlowRefferenceType.vt_A,
        "B": VarPowerFlowRefferenceType.vt_B,
        "C": VarPowerFlowRefferenceType.vt_C,
    }
    Sf_keys = {
        "A": VarPowerFlowRefferenceType.Sf_A,
        "B": VarPowerFlowRefferenceType.Sf_B,
        "C": VarPowerFlowRefferenceType.Sf_C,
    }
    St_keys = {
        "A": VarPowerFlowRefferenceType.St_A,
        "B": VarPowerFlowRefferenceType.St_B,
        "C": VarPowerFlowRefferenceType.St_C,
    }
    d_vf_keys = {
        "N": VarPowerFlowRefferenceType.d_v_N_f,
        "A": VarPowerFlowRefferenceType.d_v_A_f,
        "B": VarPowerFlowRefferenceType.d_v_B_f,
        "C": VarPowerFlowRefferenceType.d_v_C_f,
    }
    d_vt_keys = {
        "N": VarPowerFlowRefferenceType.d_v_N_t,
        "A": VarPowerFlowRefferenceType.d_v_A_t,
        "B": VarPowerFlowRefferenceType.d_v_B_t,
        "C": VarPowerFlowRefferenceType.d_v_C_t,
    }

    # Start with all phases present as None
    mapping: Dict[VarPowerFlowRefferenceType, Var | None] = {
        if_keys["N"]: None, if_keys["A"]: None, if_keys["B"]: None, if_keys["C"]: None,
        it_keys["N"]: None, it_keys["A"]: None, it_keys["B"]: None, it_keys["C"]: None,
        vf_keys["N"]: None, vf_keys["A"]: None, vf_keys["B"]: None, vf_keys["C"]: None,
        vt_keys["N"]: None, vt_keys["A"]: None, vt_keys["B"]: None, vt_keys["C"]: None,
        Sf_keys["A"]: None, Sf_keys["B"]: None, Sf_keys["C"]: None,
        St_keys["A"]: None, St_keys["B"]: None, St_keys["C"]: None,
        d_vf_keys["N"]: None, d_vf_keys["A"]: None, d_vf_keys["B"]: None, d_vf_keys["C"]: None,
        d_vt_keys["N"]: None, d_vt_keys["A"]: None, d_vt_keys["B"]: None, d_vt_keys["C"]: None,
    }

    # Fill only active phases
    for k, ph in enumerate(active_ph):
        mapping[vf_keys[ph]] = vf_vars[k]
        mapping[vt_keys[ph]] = vt_vars[k]
        mapping[if_keys[ph]] = if_act[k]
        mapping[it_keys[ph]] = it_act[k]
        mapping[d_vf_keys[ph]] = d_vf_vars[k]
        mapping[d_vt_keys[ph]] = d_vt_vars[k]

    templ.block.external_mapping = mapping

    # -----------------------------
    # init equations (ALL internal vars)
    # -----------------------------
    init_eqs: Dict[Var, Expr] = {}

    # q = C * v (inicialización de carga)
    for a in range(m):
        rhs_f = c0
        rhs_t = c0
        for b in range(m):
            Cab = float(C[a, b])
            if Cab != 0.0:
                rhs_f += Cab * vf_vars[b]
                rhs_t += Cab * vt_vars[b]
        init_eqs[q_f[a]] = rhs_f
        init_eqs[q_t[a]] = rhs_t

    # i_cap seeds
    for a in range(m):
        init_eqs[i_cap_f[a]] = c0
        init_eqs[i_cap_t[a]] = c0

    # i_ser seed using KLC i_ser = if - i_cap_f
    for a in range(m):
        init_eqs[i_ser[a]] = if_act[a] - i_cap_f[a]

    templ.block.init_eqs = init_eqs

    # -----------------------------
    # Derivative initialization (diff_init_eqs)
    # -----------------------------
    diff_init_eqs: Dict[Var, Expr] = {}
    Linv_numeric = np.linalg.inv(L)

    for a in range(m):
        di_expression = c0
        for b in range(m):
            term_b = (vf_vars[b] - vt_vars[b])
            for k in range(m):
                R_bk = float(R[b, k])
                if R_bk != 0.0:
                    term_b = term_b - R_bk * i_ser[k]
            coeff = float(Linv_numeric[a, b])
            if abs(coeff) > 1e-15:
                di_expression = di_expression + coeff * term_b

        diff_init_eqs[di_ser[a]] = di_expression

    for a in range(m):
        diff_init_eqs[dq_f[a]] = i_cap_f[a]
        diff_init_eqs[dq_t[a]] = i_cap_t[a]

    for a in range(m):
        rhs_icap_f = c0
        rhs_icap_t = c0
        for b in range(m):
            Cab = float(C[a, b])
            if Cab != 0.0:
                rhs_icap_f += Cab * d_vf_vars[b]  # Usamos la dV/dt del PF
                rhs_icap_t += Cab * d_vt_vars[b]

        init_eqs[i_cap_f[a]] = rhs_icap_f
        init_eqs[i_cap_t[a]] = rhs_icap_t

    templ.block.diff_init_eqs = diff_init_eqs


    return templ

# def get_pi_line_emt_template(vf: VarFactory,
#                              name: str = "pi_line_emt_template") -> EmtModelTemplate:
#     """
#     :param vf: VarFactory. Stores the variables and parameters of the system
#     :param name: string to identify the line and model
#     :return: EmtModelTemplate
#     """
#     templ = EmtModelTemplate()
#     templ.tpe = DeviceType.LineDevice
#     templ.name = name
#
#     c0 = vf.add_const(0.0)
#
#     # -----------------------------
#     # Explicit Enum Mappings (No getattr, strictly Enums as keys)
#     # -----------------------------
#     ph_enums = [
#         ParamPowerFlowRefferenceType.phN, ParamPowerFlowRefferenceType.phA,
#         ParamPowerFlowRefferenceType.phB, ParamPowerFlowRefferenceType.phC
#     ]
#     r_enums = [
#         [ParamPowerFlowRefferenceType.Rnn, ParamPowerFlowRefferenceType.Rna, ParamPowerFlowRefferenceType.Rnb, ParamPowerFlowRefferenceType.Rnc],
#         [ParamPowerFlowRefferenceType.Ran, ParamPowerFlowRefferenceType.Raa, ParamPowerFlowRefferenceType.Rab, ParamPowerFlowRefferenceType.Rac],
#         [ParamPowerFlowRefferenceType.Rbn, ParamPowerFlowRefferenceType.Rba, ParamPowerFlowRefferenceType.Rbb, ParamPowerFlowRefferenceType.Rbc],
#         [ParamPowerFlowRefferenceType.Rcn, ParamPowerFlowRefferenceType.Rca, ParamPowerFlowRefferenceType.Rcb, ParamPowerFlowRefferenceType.Rcc]
#     ]
#     linv_enums = [
#         [ParamPowerFlowRefferenceType.Linv_nn, ParamPowerFlowRefferenceType.Linv_na, ParamPowerFlowRefferenceType.Linv_nb, ParamPowerFlowRefferenceType.Linv_nc],
#         [ParamPowerFlowRefferenceType.Linv_an, ParamPowerFlowRefferenceType.Linv_aa, ParamPowerFlowRefferenceType.Linv_ab, ParamPowerFlowRefferenceType.Linv_ac],
#         [ParamPowerFlowRefferenceType.Linv_bn, ParamPowerFlowRefferenceType.Linv_ba, ParamPowerFlowRefferenceType.Linv_bb, ParamPowerFlowRefferenceType.Linv_bc],
#         [ParamPowerFlowRefferenceType.Linv_cn, ParamPowerFlowRefferenceType.Linv_ca, ParamPowerFlowRefferenceType.Linv_cb, ParamPowerFlowRefferenceType.Linv_cc]
#     ]
#     c_enums = [
#         [ParamPowerFlowRefferenceType.Cnn, ParamPowerFlowRefferenceType.Cna, ParamPowerFlowRefferenceType.Cnb, ParamPowerFlowRefferenceType.Cnc],
#         [ParamPowerFlowRefferenceType.Can, ParamPowerFlowRefferenceType.Caa, ParamPowerFlowRefferenceType.Cab, ParamPowerFlowRefferenceType.Cac],
#         [ParamPowerFlowRefferenceType.Cbn, ParamPowerFlowRefferenceType.Cba, ParamPowerFlowRefferenceType.Cbb, ParamPowerFlowRefferenceType.Cbc],
#         [ParamPowerFlowRefferenceType.Ccn, ParamPowerFlowRefferenceType.Cca, ParamPowerFlowRefferenceType.Ccb, ParamPowerFlowRefferenceType.Ccc]
#     ]
#
#     # -----------------------------
#     # Compute continuous parameters in pu (R, L, G_end, C) in ACTIVE subspace
#     # -----------------------------
#     phases = ["n", "a", "b", "c"]
#     ph_flags_str = ["phN", "phA", "phB", "phC"]
#
#     # init empty vars matrices with type hints to avoid IDE warnings
#     R: list[list[Any]] = [[None] * 4 for _ in range(4)]
#     L_inv: list[list[Any]] = [[None] * 4 for _ in range(4)]
#     C: list[list[Any]] = [[None] * 4 for _ in range(4)]
#     ph: list[Any] = [None] * 4
#
#     # 2. create and organize params vars using numeric indices
#     for i in range(4):
#         # phase vars
#         var_ph = vf.add_var(f"{ph_flags_str[i]}_{name}")
#         ph[i] = var_ph
#         # Mapping using ENUM as key
#         templ.block.api_obj_mapping[ph_enums[i]] = var_ph
#
#         for j in range(4):
#             # --- R ---
#             var_r = vf.add_var(f"R{phases[i]}{phases[j]}_{name}")
#             R[i][j] = var_r
#             templ.block.api_obj_mapping[r_enums[i][j]] = var_r
#
#             # --- Linv ---
#             var_l = vf.add_var(f"Linv_{phases[i]}{phases[j]}_{name}")
#             L_inv[i][j] = var_l
#             templ.block.api_obj_mapping[linv_enums[i][j]] = var_l
#
#             # --- C ---
#             var_c = vf.add_var(f"C{phases[i]}{phases[j]}_{name}")
#             C[i][j] = var_c
#             templ.block.api_obj_mapping[c_enums[i][j]] = var_c
#
#     # 1. Define the status of each phase
#     ph_values = [ph[0], ph[1], ph[2], ph[3]]
#
#     # -----------------------------
#     # Phase mask from the line itself [N,A,B,C]
#     # -----------------------------
#     ph_mask = np.array([
#         bool(ph_values[0]), bool(ph_values[1]), bool(ph_values[2]), bool(ph_values[3])
#     ], dtype=bool)
#
#     ph_labels = ["N", "A", "B", "C"]
#     idx_global = np.where(ph_mask)[0]  # indices in global NABC convention
#     active_ph = [ph_labels[i] for i in idx_global]
#     m = len(active_ph)
#
#     # 3. Perform the matrix reduction using integer indices
#     R_red = [[R[i][j] for j in idx_global] for i in idx_global]
#     Linv_red = [[L_inv[i][j] for j in idx_global] for i in idx_global]
#     C_red = [[C[i][j] for j in idx_global] for i in idx_global]
#
#     if m == 0:
#         raise ValueError(f"PI line '{name}' has no enabled phases in line.ys")
#
#     # -----------------------------
#     # Create ONLY active terminal voltage input vars
#     # -----------------------------
#     vf_vars = [vf.add_var(f"vf_{ph_label}_{name}") for ph_label in active_ph]
#     vt_vars = [vf.add_var(f"vt_{ph_label}_{name}") for ph_label in active_ph]
#
#     d_vf_vars = [vf.add_diff_var(name=f"d_vf_{ph_label}_{name}", base_var=v_base) for ph_label, v_base in zip(active_ph, vf_vars)]
#     d_vt_vars = [vf.add_diff_var(name=f"d_vt_{ph_label}_{name}", base_var=v_base) for ph_label, v_base in zip(active_ph, vt_vars)]
#
#
#     # -----------------------------
#     # Create model vars
#     # -----------------------------
#     i_ser = [vf.add_var(f"i_ser_{name}_{k}") for k in range(m)]
#     q_f = [vf.add_var(f"q_f_{name}_{k}") for k in range(m)]
#     q_t = [vf.add_var(f"q_t_{name}_{k}") for k in range(m)]
#
#     di_ser = [vf.add_diff_var(name=f"di_ser_{name}_{k}", base_var=i_ser[k]) for k in range(m)]
#     dq_f = [vf.add_diff_var(name=f"dq_f_{name}_{k}", base_var=q_f[k]) for k in range(m)]
#     dq_t = [vf.add_diff_var(name=f"dq_t_{name}_{k}", base_var=q_t[k]) for k in range(m)]
#
#     i_cap_f = [vf.add_var(f"i_cap_f_{name}_{k}") for k in range(m)]
#     i_cap_t = [vf.add_var(f"i_cap_t_{name}_{k}") for k in range(m)]
#     if_act = [vf.add_var(f"if_{name}_{k}") for k in range(m)]
#     it_act = [vf.add_var(f"it_{name}_{k}") for k in range(m)]
#
#     # -----------------------------
#     # Build block
#     # -----------------------------
#     templ.block.in_vars = vf_vars + vt_vars
#     templ.block.state_vars = i_ser + q_f + q_t
#     templ.block.diff_vars = di_ser + dq_f + dq_t
#     templ.block.algebraic_vars = i_cap_f + i_cap_t + if_act + it_act
#
#     # -----------------------------
#     # State equations
#     # -----------------------------
#     state_eqs = []
#
#     for a in range(m):
#         expr_rhs = c0
#         for b in range(m):
#             L_inv_ab = Linv_red[a][b]
#             term_b = (vf_vars[b] - vt_vars[b])
#             for k in range(m):
#                 R_bk = R_red[b][k]
#                 term_b = term_b - R_bk * i_ser[k]
#             expr_rhs = expr_rhs + L_inv_ab * term_b
#         state_eqs.append(expr_rhs)
#
#     for a in range(m):
#         state_eqs.append(i_cap_f[a])
#     for a in range(m):
#         state_eqs.append(i_cap_t[a])
#
#     templ.block.state_eqs = state_eqs
#
#     # -----------------------------
#     # Algebraic equations
#     # -----------------------------
#     alg_eqs = []
#
#     for a in range(m):
#         rhs_q = c0
#         for b in range(m):
#             C_ab = C_red[a][b]
#             rhs_q = rhs_q + C_ab * vf_vars[b]
#         alg_eqs.append(q_f[a] - rhs_q)
#
#     for a in range(m):
#         rhs_q = c0
#         for b in range(m):
#             C_ab = C_red[a][b]
#             rhs_q = rhs_q + C_ab * vt_vars[b]
#         alg_eqs.append(q_t[a] - rhs_q)
#
#     G_damp = 1e-5
#     for a in range(m):
#         alg_eqs.append(if_act[a] - (i_ser[a] + i_cap_f[a] + G_damp * vf_vars[a]))
#         alg_eqs.append(it_act[a] - (-i_ser[a] + i_cap_t[a] + G_damp * vt_vars[a]))
#
#     templ.block.algebraic_eqs = alg_eqs
#     templ.block.out_vars = if_act + it_act
#
#     # -----------------------------
#     # External mapping
#     # -----------------------------
#     if_keys = {"N": VarPowerFlowRefferenceType.if_N, "A": VarPowerFlowRefferenceType.if_A, "B": VarPowerFlowRefferenceType.if_B, "C": VarPowerFlowRefferenceType.if_C}
#     it_keys = {"N": VarPowerFlowRefferenceType.it_N, "A": VarPowerFlowRefferenceType.it_A, "B": VarPowerFlowRefferenceType.it_B, "C": VarPowerFlowRefferenceType.it_C}
#     Sf_keys = {"A": VarPowerFlowRefferenceType.Sf_A, "B": VarPowerFlowRefferenceType.Sf_B, "C": VarPowerFlowRefferenceType.Sf_C}
#     St_keys = {"A": VarPowerFlowRefferenceType.St_A, "B": VarPowerFlowRefferenceType.St_B, "C": VarPowerFlowRefferenceType.St_C}
#     d_vf_keys = {"N": VarPowerFlowRefferenceType.d_v_N_f, "A": VarPowerFlowRefferenceType.d_v_A_f, "B": VarPowerFlowRefferenceType.d_v_B_f, "C": VarPowerFlowRefferenceType.d_v_C_f}
#     d_vt_keys = {"N": VarPowerFlowRefferenceType.d_v_N_t, "A": VarPowerFlowRefferenceType.d_v_A_t, "B": VarPowerFlowRefferenceType.d_v_B_t, "C": VarPowerFlowRefferenceType.d_v_C_t}
#
#     mapping: Dict[VarPowerFlowRefferenceType, Var | None] = {
#         if_keys["N"]: None, if_keys["A"]: None, if_keys["B"]: None, if_keys["C"]: None,
#         it_keys["N"]: None, it_keys["A"]: None, it_keys["B"]: None, it_keys["C"]: None,
#         Sf_keys["A"]: None, Sf_keys["B"]: None, Sf_keys["C"]: None,
#         St_keys["A"]: None, St_keys["B"]: None, St_keys["C"]: None,
#         d_vf_keys["N"]: None, d_vf_keys["A"]: None, d_vf_keys["B"]: None, d_vf_keys["C"]: None,
#         d_vt_keys["N"]: None, d_vt_keys["A"]: None, d_vt_keys["B"]: None, d_vt_keys["C"]: None,
#     }
#
#     for k, phase_label in enumerate(active_ph):
#         mapping[if_keys[phase_label]] = if_act[k]
#         mapping[it_keys[phase_label]] = it_act[k]
#         mapping[d_vf_keys[phase_label]] = d_vf_vars[k]
#         mapping[d_vt_keys[phase_label]] = d_vt_vars[k]
#
#     templ.block.external_mapping = mapping
#
#     # -----------------------------
#     # Init equations
#     # -----------------------------
#     init_eqs: Dict[Var, Expr] = {}
#
#     for a in range(m):
#         rhs_f = c0
#         rhs_t = c0
#         for b in range(m):
#             C_ab = C_red[a][b]
#             rhs_f += C_ab * vf_vars[b]
#             rhs_t += C_ab * vt_vars[b]
#         init_eqs[q_f[a]] = rhs_f
#         init_eqs[q_t[a]] = rhs_t
#
#     for a in range(m):
#         init_eqs[i_ser[a]] = if_act[a] - i_cap_f[a]
#
#     templ.block.init_eqs = init_eqs
#
#     # -----------------------------
#     # Derivative initialization
#     # -----------------------------
#     diff_init_eqs: Dict[Var, Expr] = {}
#
#     for a in range(m):
#         di_expression = c0
#         for b in range(m):
#             term_b = (vf_vars[b] - vt_vars[b])
#             for k in range(m):
#                 R_bk = R_red[b][k]
#                 term_b = term_b - R_bk * i_ser[k]
#             coeff = Linv_red[a][b]
#             di_expression = di_expression + coeff * term_b
#         diff_init_eqs[di_ser[a]] = di_expression
#
#     for a in range(m):
#         diff_init_eqs[dq_f[a]] = i_cap_f[a]
#         diff_init_eqs[dq_t[a]] = i_cap_t[a]
#
#     for a in range(m):
#         rhs_icap_f = c0
#         rhs_icap_t = c0
#         for b in range(m):
#             C_ab = C_red[a][b]
#             rhs_icap_f += C_ab * d_vf_vars[b]
#             rhs_icap_t += C_ab * d_vt_vars[b]
#         init_eqs[i_cap_f[a]] = rhs_icap_f
#         init_eqs[i_cap_t[a]] = rhs_icap_t
#
#     templ.block.diff_init_eqs = diff_init_eqs
#
#     return templ