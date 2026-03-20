# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Dict, Tuple
import math
import numpy as np

from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.enumerations import DeviceType, VarPowerFlowRefferenceType, WindingType, WindingsConnection
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Branches.transformer import Transformer2W
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Var, Expr
import VeraGridEngine.Utils.Symbolic.symbolic as sym


def _safe_positive(value: float | None, default: float, floor: float = 1e-9) -> float:
    if value is None or not math.isfinite(value) or value <= floor:
        return default
    return max(float(value), floor)


def _parse_connection(trafo: Transformer2W) -> Tuple[WindingType, WindingType]:
    if isinstance(trafo.conn_f, WindingType) and isinstance(trafo.conn_t, WindingType):
        return trafo.conn_f, trafo.conn_t

    conn = str(trafo.conn if isinstance(trafo.conn, WindingsConnection) else WindingsConnection.GG)
    lut = {
        "G": WindingType.GroundedStar,
        "S": WindingType.NeutralStar,
        "D": WindingType.Delta,
    }
    return lut[conn[0]], lut[conn[1]]


def _connection_matrix(winding_type: WindingType) -> np.ndarray:
    if winding_type in (WindingType.GroundedStar, WindingType.NeutralStar, WindingType.FloatingStar):
        return np.eye(3, dtype=float)

    if winding_type == WindingType.Delta:
        return np.array([
            [1.0, 0.0, -1.0],
            [-1.0, 1.0, 0.0],
            [0.0, -1.0, 1.0],
        ], dtype=float) / math.sqrt(3.0)

    raise NotImplementedError(f"XFMR EMT template does not support winding type {winding_type}")


def _phase_permutation_matrix(clock: int) -> np.ndarray:
    shift = (int(clock) // 4) % 3
    if shift == 0:
        return np.eye(3, dtype=float)
    if shift == 1:
        return np.array([
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [1.0, 0.0, 0.0],
        ], dtype=float)
    return np.array([
        [0.0, 0.0, 1.0],
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
    ], dtype=float)


def _estimate_core_loss_conductance_pu(trafo: Transformer2W) -> float:
    if abs(float(trafo.G)) > 1e-12:
        return max(float(trafo.G), 0.0)

    if float(trafo.Sn) > 1e-12 and float(trafo.Pfe) > 0.0:
        return max(float(trafo.Pfe) / (1000.0 * float(trafo.Sn)), 0.0)

    return 0.0


def _estimate_frolich_coefficients(trafo: Transformer2W) -> Tuple[float, float]:
    i0_pu = max(float(trafo.I0) / 100.0, 0.005)
    b_core = 0.5
    a_core = max(1.0 / i0_pu - b_core, 0.05)
    return a_core, b_core


def _estimate_terminal_capacitance_pu(trafo: Transformer2W, omega_base: float) -> float:
    if float(trafo.Sn) <= 1e-12:
        return 0.0

    if abs(float(trafo.B)) > 1e-12:
        return max(abs(float(trafo.B)) / omega_base, 0.0)

    return 0.0


def _frolich_current(lam: Expr, a_coeff: float, b_coeff: float, eps: Expr) -> Expr:
    return lam / (a_coeff + b_coeff * sym.abs(lam) + eps)


def _mat_vec_expr(mat: np.ndarray, vec: list[Expr], c0: Expr) -> list[Expr]:
    out: list[Expr] = []
    rows, cols = mat.shape
    for i in range(rows):
        rhs = c0
        for j in range(cols):
            coeff = float(mat[i, j])
            if abs(coeff) > 1e-15:
                rhs = rhs + coeff * vec[j]
        out.append(rhs)
    return out


def get_xfmr_emt_template(
    grid: MultiCircuit,
    trafo: Transformer2W,
    name: str = "xfmr_emt_template",
    core_topology: str = "three_legged",
) -> EmtModelTemplate:
    """
    Build an EMT transformer template inspired by ATPDraw's XFMR hybrid model.

    Implemented structure:
    - leakage branch represented in winding coordinates using connection matrices
    - topologically-aware nonlinear core model separated from leakage flux
    - split terminal capacitances connected at both winding ends
    - linear core-loss conductance at the energized winding side

    The available VeraGrid `Transformer2W` data is less detailed than ATP XFMR,
    so this block uses the same model structure but estimates missing parameters
    from the standard transformer fields when design/test-report data is absent.
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.TransformerTypeDevice
    templ.name = name

    vf: VarFactory = grid.emt_var_factory
    omega_base = 2.0 * math.pi * float(grid.fBase)

    c0 = vf.add_const(0.0)
    c_eps = vf.add_const(1e-9)
    c_omega = vf.add_const(omega_base)

    conn_f, conn_t = _parse_connection(trafo)
    c_f = _connection_matrix(conn_f)
    c_t = _connection_matrix(conn_t)
    p_t = _phase_permutation_matrix(int(getattr(trafo, "vector_group_number", 0)))
    c_t_eff = p_t @ c_t

    r_sigma = _safe_positive(float(trafo.R), default=1e-6)
    x_sigma = _safe_positive(float(trafo.X), default=0.1)
    l_sigma = _safe_positive(x_sigma / omega_base, default=1e-6)
    l_inv = 1.0 / l_sigma
    n_tap = float(trafo.tap_module) if abs(float(trafo.tap_module)) > 1e-12 else 1.0
    g_core = _estimate_core_loss_conductance_pu(trafo)
    c_term = 0.5 * _estimate_terminal_capacitance_pu(trafo, omega_base)

    a_core, b_core = _estimate_frolich_coefficients(trafo)

    if core_topology.lower() == "five_legged":
        a_yoke = 1.20 * a_core
        b_yoke = 0.60 * b_core
        five_legged = True
    else:
        a_yoke = 1.75 * a_core
        b_yoke = 1.20 * b_core
        five_legged = False

    v_f = [
        vf.add_var(name=f"vf_A_{name}", ref=VarPowerFlowRefferenceType.v_A_f),
        vf.add_var(name=f"vf_B_{name}", ref=VarPowerFlowRefferenceType.v_B_f),
        vf.add_var(name=f"vf_C_{name}", ref=VarPowerFlowRefferenceType.v_C_f),
    ]
    v_t = [
        vf.add_var(name=f"vt_A_{name}", ref=VarPowerFlowRefferenceType.v_A_t),
        vf.add_var(name=f"vt_B_{name}", ref=VarPowerFlowRefferenceType.v_B_t),
        vf.add_var(name=f"vt_C_{name}", ref=VarPowerFlowRefferenceType.v_C_t),
    ]
    d_v_f = [
        vf.add_var(name=f"d_vf_A_{name}", ref=VarPowerFlowRefferenceType.d_v_A_f),
        vf.add_var(name=f"d_vf_B_{name}", ref=VarPowerFlowRefferenceType.d_v_B_f),
        vf.add_var(name=f"d_vf_C_{name}", ref=VarPowerFlowRefferenceType.d_v_C_f),
    ]
    d_v_t = [
        vf.add_var(name=f"d_vt_A_{name}", ref=VarPowerFlowRefferenceType.d_v_A_t),
        vf.add_var(name=f"d_vt_B_{name}", ref=VarPowerFlowRefferenceType.d_v_B_t),
        vf.add_var(name=f"d_vt_C_{name}", ref=VarPowerFlowRefferenceType.d_v_C_t),
    ]

    for d_var in d_v_f:
        templ.block.event_dict[d_var] = vf.add_const(None)

    for d_var in d_v_t:
        templ.block.event_dict[d_var] = vf.add_const(None)

    i_leak = [vf.add_var(name=f"i_leak_{ph}_{name}") for ph in ("A", "B", "C")]
    lam_leg = [vf.add_var(name=f"lam_leg_{ph}_{name}") for ph in ("A", "B", "C")]
    q_f = [vf.add_var(name=f"qf_{ph}_{name}") for ph in ("A", "B", "C")]
    q_t = [vf.add_var(name=f"qt_{ph}_{name}") for ph in ("A", "B", "C")]

    di_leak = [vf.add_diff_var(name=f"di_leak_{ph}_{name}", base_var=i_leak[k]) for k, ph in enumerate(("A", "B", "C"))]
    dlam_leg = [vf.add_diff_var(name=f"dlam_leg_{ph}_{name}", base_var=lam_leg[k]) for k, ph in enumerate(("A", "B", "C"))]
    dq_f = [vf.add_diff_var(name=f"dqf_{ph}_{name}", base_var=q_f[k]) for k, ph in enumerate(("A", "B", "C"))]
    dq_t = [vf.add_diff_var(name=f"dqt_{ph}_{name}", base_var=q_t[k]) for k, ph in enumerate(("A", "B", "C"))]

    i_mag = [vf.add_var(name=f"i_mag_{ph}_{name}") for ph in ("A", "B", "C")]
    i_cap_f = [vf.add_var(name=f"i_cap_f_{ph}_{name}") for ph in ("A", "B", "C")]
    i_cap_t = [vf.add_var(name=f"i_cap_t_{ph}_{name}") for ph in ("A", "B", "C")]
    if_act = [vf.add_var(name=f"if_{ph}_{name}") for ph in ("A", "B", "C")]
    it_act = [vf.add_var(name=f"it_{ph}_{name}") for ph in ("A", "B", "C")]

    templ.block.in_vars = v_f + v_t + d_v_f + d_v_t
    templ.block.state_vars = i_leak + lam_leg + q_f + q_t
    templ.block.diff_vars = di_leak + dlam_leg + dq_f + dq_t
    templ.block.algebraic_vars = i_mag + i_cap_f + i_cap_t + if_act + it_act

    v_f_w = _mat_vec_expr(c_f.T, v_f, c0)
    v_t_perm = _mat_vec_expr(p_t, v_t, c0)
    d_v_f_w = _mat_vec_expr(c_f.T, d_v_f, c0)
    d_v_t_perm = _mat_vec_expr(p_t, d_v_t, c0)
    v_t_w = _mat_vec_expr(c_t.T, v_t_perm, c0)
    d_v_t_w = _mat_vec_expr(c_t.T, d_v_t_perm, c0)
    v_leak = [v_f_w[k] - n_tap * v_t_w[k] for k in range(3)]

    state_eqs: list[Expr] = []
    for k in range(3):
        state_eqs.append(l_inv * (v_leak[k] - r_sigma * i_leak[k]))
    for k in range(3):
        state_eqs.append(c_omega * v_f_w[k])
    for k in range(3):
        state_eqs.append(i_cap_f[k])
    for k in range(3):
        state_eqs.append(i_cap_t[k])
    templ.block.state_eqs = state_eqs

    lam_return = -(lam_leg[0] + lam_leg[1] + lam_leg[2])
    if five_legged:
        i_return = 2.0 * _frolich_current(0.5 * lam_return, a_yoke, b_yoke, c_eps)
    else:
        i_return = _frolich_current(lam_return, a_yoke, b_yoke, c_eps)

    i_series_from = _mat_vec_expr(c_f, i_leak, c0)
    i_series_to = _mat_vec_expr(c_t_eff, i_leak, c0)

    alg_eqs: list[Expr] = []
    for k in range(3):
        i_leg = _frolich_current(lam_leg[k], a_core, b_core, c_eps)
        alg_eqs.append(i_mag[k] - (i_leg - i_return))

    for k in range(3):
        alg_eqs.append(i_cap_f[k] - c_term * d_v_f[k])
        alg_eqs.append(i_cap_t[k] - c_term * d_v_t[k])

    for k in range(3):
        alg_eqs.append(q_f[k] - c_term * v_f[k])
        alg_eqs.append(q_t[k] - c_term * v_t[k])

    for k in range(3):
        alg_eqs.append(if_act[k] - (i_series_from[k] + i_mag[k] + g_core * v_f_w[k] + i_cap_f[k]))
        alg_eqs.append(it_act[k] - (-n_tap * i_series_to[k] + i_cap_t[k]))

    templ.block.algebraic_eqs = alg_eqs
    templ.block.out_vars = if_act + it_act + i_mag
    templ.block.name = name

    templ.block.external_mapping = {
        VarPowerFlowRefferenceType.if_N: None,
        VarPowerFlowRefferenceType.if_A: if_act[0],
        VarPowerFlowRefferenceType.if_B: if_act[1],
        VarPowerFlowRefferenceType.if_C: if_act[2],
        VarPowerFlowRefferenceType.it_N: None,
        VarPowerFlowRefferenceType.it_A: it_act[0],
        VarPowerFlowRefferenceType.it_B: it_act[1],
        VarPowerFlowRefferenceType.it_C: it_act[2],
        VarPowerFlowRefferenceType.Sf_A: None,
        VarPowerFlowRefferenceType.Sf_B: None,
        VarPowerFlowRefferenceType.Sf_C: None,
        VarPowerFlowRefferenceType.St_A: None,
        VarPowerFlowRefferenceType.St_B: None,
        VarPowerFlowRefferenceType.St_C: None,
        VarPowerFlowRefferenceType.d_v_N_f: None,
        VarPowerFlowRefferenceType.d_v_A_f: d_v_f[0],
        VarPowerFlowRefferenceType.d_v_B_f: d_v_f[1],
        VarPowerFlowRefferenceType.d_v_C_f: d_v_f[2],
        VarPowerFlowRefferenceType.d_v_N_t: None,
        VarPowerFlowRefferenceType.d_v_A_t: d_v_t[0],
        VarPowerFlowRefferenceType.d_v_B_t: d_v_t[1],
        VarPowerFlowRefferenceType.d_v_C_t: d_v_t[2],
    }

    init_eqs: Dict[Var, Expr] = {}
    for k in range(3):
        init_eqs[q_f[k]] = c_term * v_f[k]
        init_eqs[q_t[k]] = c_term * v_t[k]
        init_eqs[i_cap_f[k]] = c_term * d_v_f[k]
        init_eqs[i_cap_t[k]] = c_term * d_v_t[k]
        init_eqs[lam_leg[k]] = -d_v_f_w[k] / c_omega

    for k in range(3):
        i_leg = _frolich_current(lam_leg[k], a_core, b_core, c_eps)
        init_eqs[i_mag[k]] = i_leg - i_return

    series_seed = _mat_vec_expr(c_t_eff.T, [-it_act[0] / n_tap, -it_act[1] / n_tap, -it_act[2] / n_tap], c0)
    for k in range(3):
        init_eqs[i_leak[k]] = series_seed[k]
        init_eqs[if_act[k]] = i_series_from[k] + i_mag[k] + g_core * v_f_w[k] + i_cap_f[k]

    templ.block.init_eqs = init_eqs

    diff_init_eqs: Dict[Var, Expr] = {}
    for k in range(3):
        diff_init_eqs[di_leak[k]] = l_inv * (v_leak[k] - r_sigma * i_leak[k])
        diff_init_eqs[dlam_leg[k]] = c_omega * v_f_w[k]
        diff_init_eqs[dq_f[k]] = i_cap_f[k]
        diff_init_eqs[dq_t[k]] = i_cap_t[k]

    templ.block.diff_init_eqs = diff_init_eqs

    return templ
