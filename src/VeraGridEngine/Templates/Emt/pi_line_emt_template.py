# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Dict
import numpy as np
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType, VarPowerFlowRefferenceType
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Utils.Symbolic.block import Var, Expr

def get_pi_line_emt_template(grid: MultiCircuit,
                             line: Line,
                             name: str = "") -> EmtModelTemplate:
    """

    :param grid: Multicircuit
    :param line: Line object to apply the template
    :param name: string to identify the line and model
    :return: EmtModelTemplate
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.LineDevice
    templ.name = name

    vf: VarFactory = grid.rms_var_factory
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
    idx = np.where(ph_mask)[0]  # indices in [0..3]
    active_ph = [ph_labels[i] for i in idx]  # names in canonical order
    m = len(active_ph)

    if m == 0:
        raise ValueError(f"PI line '{line.name}' has no enabled phases in line.ys")

    # -----------------------------
    # Create ONLY active terminal voltage input vars
    #    (Connection to buses is done by the assembler, not here.)
    # -----------------------------
    vf_vars = [vf.add_var(f"vf_{ph}_{line.name}") for ph in active_ph]
    vt_vars = [vf.add_var(f"vt_{ph}_{line.name}") for ph in active_ph]
    d_vf_vars = [vf.add_diff_var(name=f"d_vf_{ph}_{line.name}", base_var=v_base) for ph, v_base in
                 zip(active_ph, vf_vars)]
    d_vt_vars = [vf.add_diff_var(name=f"d_vt_{ph}_{line.name}", base_var=v_base) for ph, v_base in
                 zip(active_ph, vt_vars)]

    # -----------------------------
    # Compute continuous parameters in pu (R, L, G_end, C_end) in ACTIVE subspace
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

    idx_global = idx
    n_mat = R_full.shape[0]

    if n_mat == 3:
        # Matrices are ABC only
        if 0 in idx_global:
            raise ValueError(
                f"Line '{line.name}' has N phase enabled but template matrices are 3x3 (ABC)."
            )
        idx_mat = idx_global - 1  # A->0, B->1, C->2
    elif n_mat == 4:
        # Matrices are NABC
        idx_mat = idx_global
    else:
        raise ValueError(
            f"Unsupported template matrix size {n_mat} for line '{line.name}' (expected 3 or 4)."
        )

    R = R_full[np.ix_(idx_mat, idx_mat)]
    L = L_full[np.ix_(idx_mat, idx_mat)]
    C_end = C_end_full[np.ix_(idx_mat, idx_mat)]

    # -----------------------------
    # Create model vars
    # -----------------------------
    i_ser = [vf.add_var(f"i_ser_{line.name}_{k}") for k in range(m)]
    q_f = [vf.add_var(f"q_f_{line.name}_{k}") for k in range(m)]
    q_t = [vf.add_var(f"q_t_{line.name}_{k}") for k in range(m)]

    di_ser = [vf.add_diff_var(name=f"di_ser_{line.name}_{k}", base_var=i_ser[k]) for k in range(m)]
    dq_f = [vf.add_diff_var(name=f"dq_f_{line.name}_{k}", base_var=q_f[k]) for k in range(m)]
    dq_t = [vf.add_diff_var(name=f"dq_t_{line.name}_{k}", base_var=q_t[k]) for k in range(m)]

    i_cap_f = [vf.add_var(f"i_cap_f_{line.name}_{k}") for k in range(m)]
    i_cap_t = [vf.add_var(f"i_cap_t_{line.name}_{k}") for k in range(m)]
    if_act = [vf.add_var(f"if_{line.name}_{k}") for k in range(m)]
    it_act = [vf.add_var(f"it_{line.name}_{k}") for k in range(m)]

    # -----------------------------
    # Build block
    # -----------------------------
    templ.block.in_vars = vf_vars + vt_vars + d_vf_vars + d_vt_vars
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
    #i_cap_f - C_end * d_vf = 0
    for a in range(m):
        rhs = c0
        for b in range(m):
            Cab = float(C_end[a, b])
            if Cab != 0.0:
                rhs = rhs + Cab * d_vf_vars[b]
        alg_eqs.append(i_cap_f[a] - rhs)
    # i_cap_t - C_end * d_vt = 0
    for a in range(m):
        rhs = c0
        for b in range(m):
            Cab = float(C_end[a, b])
            if Cab != 0.0:
                rhs = rhs + Cab * d_vt_vars[b]
        alg_eqs.append(i_cap_t[a] - rhs)

    # Terminal current at from-bus:
    # if = i_ser + i_cap_f
    for a in range(m):
        gv = c0
        alg_eqs.append(if_act[a] - (i_ser[a] + gv + i_cap_f[a]))

    # Terminal current at to-bus:
    # it = -i_ser + i_cap_t
    for a in range(m):
        gv = c0
        alg_eqs.append(it_act[a] - (-i_ser[a] + gv + i_cap_t[a]))

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

    # Start with all phases present as None
    mapping: Dict[VarPowerFlowRefferenceType, Var | None] = {
        if_keys["N"]: None, if_keys["A"]: None, if_keys["B"]: None, if_keys["C"]: None,
        it_keys["N"]: None, it_keys["A"]: None, it_keys["B"]: None, it_keys["C"]: None,
        Sf_keys["A"]: None, Sf_keys["B"]: None, Sf_keys["C"]: None,
        St_keys["A"]: None, St_keys["B"]: None, St_keys["C"]: None,
    }

    # Fill only active phases
    for k, ph in enumerate(active_ph):
        mapping[if_keys[ph]] = if_act[k]
        mapping[it_keys[ph]] = it_act[k]

    templ.block.external_mapping = mapping

    # -----------------------------
    # init equations (ALL internal vars)
    # -----------------------------
    init_eqs: Dict[Var, Expr] = {}

    # q_f = C_end * vf
    for a in range(m):
        rhs = c0
        for b in range(m):
            Cab = float(C_end[a, b])
            if Cab != 0.0:
                rhs = rhs + Cab * vf_vars[b]
        init_eqs[q_f[a]] = rhs

    # q_t = C_end * vt
    for a in range(m):
        rhs = c0
        for b in range(m):
            Cab = float(C_end[a, b])
            if Cab != 0.0:
                rhs = rhs + Cab * vt_vars[b]
        init_eqs[q_t[a]] = rhs

    # i_cap seeds
    for a in range(m):
        init_eqs[i_cap_f[a]] = c0
        init_eqs[i_cap_t[a]] = c0

    # i_ser seed using KLC
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

    templ.block.diff_init_eqs = diff_init_eqs


    return templ