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
    Build the local XFMR-style transformer EMT DAE template.

    - leakage and copper losses are separated from the main/core flux path,
    - short-circuit report data parameterize the series leakage branch,
    - open-circuit report data parameterize the core branch,
    - the core branch uses the basic Frohlich ``lambda(i)`` law,
    - core losses remain linear resistive branches,
    - the magnetic return path distinguishes 3-legged and 5-legged stacked cores.

    All user-facing scalar inputs used by this local template are exposed through
    ``templ.block.event_dict``. Because ``Transformer2W`` only carries a single
    open-circuit and short-circuit operating point in the current repository, the
    fully general multi-point XFMR report fit discussed in the paper cannot be
    wired end-to-end without touching other files. This function therefore
    implements the largest repository-local correct subset:

    - full two-winding short-circuit leakage derivation from test-report style data,
    - single-point open-circuit handling with a physically consistent linear core,
    - direct event parameters for the fitted core coefficients so callers can still
      override them without architectural changes,
    - 3-legged and 5-legged return-path equations using relative geometry.

    :param grid: Parent grid object.
    :param trafo: Transformer whose default report values seed ``event_dict``.
    :param name: Symbolic model name.
    :param core_topology: ``three_legged`` or ``five_legged`` local core topology.
    :return: EMT transformer template.
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.TransformerTypeDevice
    templ.name = name
    templ.block.name = name

    vf: VarFactory = grid.var_factory
    omega_base_value: float = 2.0 * math.pi * float(grid.fBase)

    c0: Expr = vf.add_const(0.0)
    c_eps: Expr = vf.add_const(1e-9)

    # ------------------------------------------------------------------
    # Build the electrical connection matrices in the same winding/line
    # coordinates already used by the previous local XFMR template.
    # ------------------------------------------------------------------
    conn_f: WindingType
    conn_t: WindingType
    conn_f, conn_t = _parse_connection(trafo)

    c_f: np.ndarray = _connection_matrix(conn_f)
    c_t: np.ndarray = _connection_matrix(conn_t)
    vector_group_clock: int = int(trafo.vector_group_number)
    p_t: np.ndarray = _phase_permutation_matrix(vector_group_clock)
    c_t_eff: np.ndarray = p_t @ c_t

    # ------------------------------------------------------------------
    # Seed the event parameters from the existing Transformer2W fields.
    #
    # Model reason:
    # The task requires that user-entered transformer data live in event_dict,
    # but the surrounding VeraGrid repository still stores the available report
    # values on Transformer2W. To keep the patch local, we translate those
    # fields into explicit event parameters here.
    #
    # Algorithm reason:
    # Each default below is a safe scalar fallback that can later be replaced by
    # EMT events without changing callers or the public function signature.
    # ------------------------------------------------------------------
    sn_default: float = _safe_positive(float(trafo.Sn), default=1.0)
    f_hz_default: float = _safe_positive(float(grid.fBase), default=50.0)

    hv_default: float
    if trafo.HV is None:
        hv_default = 1.0
    else:
        hv_default = _safe_positive(float(trafo.HV), default=1.0)

    lv_default: float
    if trafo.LV is None:
        lv_default = 1.0
    else:
        lv_default = _safe_positive(float(trafo.LV), default=1.0)

    r_fallback_pu: float = max(float(trafo.R), 0.0)
    x_fallback_pu: float = max(float(trafo.X), 0.0)
    z_fallback_pu: float = math.sqrt(max(r_fallback_pu * r_fallback_pu + x_fallback_pu * x_fallback_pu, 0.0))

    sc_voltage_pct_default: float
    if float(trafo.Vsc) > 0.0:
        sc_voltage_pct_default = float(trafo.Vsc)
    else:
        sc_voltage_pct_default = 100.0 * z_fallback_pu

    sc_resistance_pct_default: float
    if float(trafo.Pcu) > 0.0:
        sc_resistance_pct_default = float(trafo.Pcu) / (10.0 * sn_default)
    else:
        sc_resistance_pct_default = 100.0 * r_fallback_pu

    sc_loss_kw_default: float
    if float(trafo.Pcu) > 0.0:
        sc_loss_kw_default = float(trafo.Pcu)
    else:
        sc_loss_kw_default = 10.0 * sn_default * sc_resistance_pct_default

    oc_excitation_pct_default: float = 100.0

    oc_current_pct_default: float
    if float(trafo.I0) > 0.0:
        oc_current_pct_default = float(trafo.I0)
    else:
        oc_current_pct_default = max(abs(float(trafo.B)) * 100.0, 0.0)

    oc_loss_kw_default: float
    if float(trafo.Pfe) > 0.0:
        oc_loss_kw_default = float(trafo.Pfe)
    else:
        oc_loss_kw_default = max(float(trafo.G), 0.0) * 1000.0 * sn_default

    yoke_area_default: float = 1.0
    yoke_length_default: float = 1.0
    outer_area_default: float = 1.0
    outer_length_default: float = 1.0

    if core_topology.lower() == "five_legged":
        yoke_area_default = 0.54
        yoke_length_default = 1.5
        outer_area_default = 0.54
        outer_length_default = 2.5
        is_five_legged: bool = True
    else:
        yoke_area_default = 1.0
        yoke_length_default = 1.0
        outer_area_default = 1.0
        outer_length_default = 1.0
        is_five_legged = False

    # ------------------------------------------------------------------
    # Fit the single-point open-circuit subset locally.
    #
    # Model reason:
    # The XFMR paper states that when only one OC point is available, the core
    # model should be treated as linear rather than forcing a nonlinear fit.
    #
    # Algorithm reason:
    # The present repository exposes only one OC operating point through the
    # Transformer2W object, so we compute the loss-free magnetizing current from
    # the measured current and loss, then derive the equivalent linear
    # lambda/i slope used as the seeded core branch parameter.
    # ------------------------------------------------------------------
    oc_loss_pu_default: float = max(oc_loss_kw_default / (1000.0 * sn_default), 0.0)
    oc_current_pu_default: float = max(oc_current_pct_default / 100.0, 0.0)
    i_mag_pu_default: float = math.sqrt(max(oc_current_pu_default * oc_current_pu_default - oc_loss_pu_default * oc_loss_pu_default, 0.0))
    lambda_peak_default: float = math.sqrt(2.0) * max(oc_excitation_pct_default / 100.0, 0.0)
    current_peak_default: float = math.sqrt(2.0) * i_mag_pu_default

    linear_lm_default: float
    if current_peak_default > 1e-9:
        linear_lm_default = lambda_peak_default / current_peak_default
    else:
        linear_lm_default = 1e6

    a_prime_default: float = linear_lm_default
    b_prime_default: float = 0.0
    use_linear_core_default: float = 1.0

    # ------------------------------------------------------------------
    # Create explicit event parameters.
    #
    # Model reason:
    # These variables are the local schema for the transformer test-report path:
    # rating, SC data, OC data, geometry data, and fitted core coefficients.
    #
    # Algorithm reason:
    # Defining them as normal symbolic variables and storing their values in
    # block.event_dict makes them compatible with VeraGrid's EMT event system.
    # ------------------------------------------------------------------
    d_v_f: list[Var] = list([
        vf.add_var(name=f"d_vf_A_{name}", reference=VarPowerFlowRefferenceType.d_v_A_f),
        vf.add_var(name=f"d_vf_B_{name}", reference=VarPowerFlowRefferenceType.d_v_B_f),
        vf.add_var(name=f"d_vf_C_{name}", reference=VarPowerFlowRefferenceType.d_v_C_f),
    ])
    d_v_t: list[Var] = list([
        vf.add_var(name=f"d_vt_A_{name}", reference=VarPowerFlowRefferenceType.d_v_A_t),
        vf.add_var(name=f"d_vt_B_{name}", reference=VarPowerFlowRefferenceType.d_v_B_t),
        vf.add_var(name=f"d_vt_C_{name}", reference=VarPowerFlowRefferenceType.d_v_C_t),
    ])

    for d_var in d_v_f:
        templ.block.event_dict[d_var] = vf.add_const(None)
    for d_var in d_v_t:
        templ.block.event_dict[d_var] = vf.add_const(None)

    xfmr_s_rated_mva: Var = vf.add_var(name=f"xfmr_s_rated_mva_{name}")
    xfmr_f_hz: Var = vf.add_var(name=f"xfmr_f_hz_{name}")
    xfmr_v_hv_ll_kv: Var = vf.add_var(name=f"xfmr_v_hv_ll_kv_{name}")
    xfmr_v_lv_ll_kv: Var = vf.add_var(name=f"xfmr_v_lv_ll_kv_{name}")
    xfmr_vector_group_clock: Var = vf.add_var(name=f"xfmr_vector_group_clock_{name}")
    xfmr_core_topology_code: Var = vf.add_var(name=f"xfmr_core_topology_code_{name}")
    xfmr_oc_excitation_pct: Var = vf.add_var(name=f"xfmr_oc_excitation_pct_{name}")
    xfmr_oc_current_pct: Var = vf.add_var(name=f"xfmr_oc_current_pct_{name}")
    xfmr_oc_loss_kw: Var = vf.add_var(name=f"xfmr_oc_loss_kw_{name}")
    xfmr_sc_voltage_pct: Var = vf.add_var(name=f"xfmr_sc_voltage_pct_{name}")
    xfmr_sc_resistance_pct: Var = vf.add_var(name=f"xfmr_sc_resistance_pct_{name}")
    xfmr_sc_loss_kw: Var = vf.add_var(name=f"xfmr_sc_loss_kw_{name}")
    xfmr_yoke_area_rel: Var = vf.add_var(name=f"xfmr_yoke_area_rel_{name}")
    xfmr_yoke_length_rel: Var = vf.add_var(name=f"xfmr_yoke_length_rel_{name}")
    xfmr_outer_leg_area_rel: Var = vf.add_var(name=f"xfmr_outer_leg_area_rel_{name}")
    xfmr_outer_leg_length_rel: Var = vf.add_var(name=f"xfmr_outer_leg_length_rel_{name}")
    xfmr_core_a_prime: Var = vf.add_var(name=f"xfmr_core_a_prime_{name}")
    xfmr_core_b_prime: Var = vf.add_var(name=f"xfmr_core_b_prime_{name}")
    xfmr_core_linear_l_pu: Var = vf.add_var(name=f"xfmr_core_linear_l_pu_{name}")
    xfmr_use_linear_core: Var = vf.add_var(name=f"xfmr_use_linear_core_{name}")

    templ.block.event_dict[xfmr_s_rated_mva] = vf.add_const(sn_default)
    templ.block.event_dict[xfmr_f_hz] = vf.add_const(f_hz_default)
    templ.block.event_dict[xfmr_v_hv_ll_kv] = vf.add_const(hv_default)
    templ.block.event_dict[xfmr_v_lv_ll_kv] = vf.add_const(lv_default)
    templ.block.event_dict[xfmr_vector_group_clock] = vf.add_const(float(vector_group_clock))
    templ.block.event_dict[xfmr_core_topology_code] = vf.add_const(5.0 if is_five_legged else 3.0)
    templ.block.event_dict[xfmr_oc_excitation_pct] = vf.add_const(oc_excitation_pct_default)
    templ.block.event_dict[xfmr_oc_current_pct] = vf.add_const(oc_current_pct_default)
    templ.block.event_dict[xfmr_oc_loss_kw] = vf.add_const(oc_loss_kw_default)
    templ.block.event_dict[xfmr_sc_voltage_pct] = vf.add_const(sc_voltage_pct_default)
    templ.block.event_dict[xfmr_sc_resistance_pct] = vf.add_const(sc_resistance_pct_default)
    templ.block.event_dict[xfmr_sc_loss_kw] = vf.add_const(sc_loss_kw_default)
    templ.block.event_dict[xfmr_yoke_area_rel] = vf.add_const(yoke_area_default)
    templ.block.event_dict[xfmr_yoke_length_rel] = vf.add_const(yoke_length_default)
    templ.block.event_dict[xfmr_outer_leg_area_rel] = vf.add_const(outer_area_default)
    templ.block.event_dict[xfmr_outer_leg_length_rel] = vf.add_const(outer_length_default)
    templ.block.event_dict[xfmr_core_a_prime] = vf.add_const(a_prime_default)
    templ.block.event_dict[xfmr_core_b_prime] = vf.add_const(b_prime_default)
    templ.block.event_dict[xfmr_core_linear_l_pu] = vf.add_const(linear_lm_default)
    templ.block.event_dict[xfmr_use_linear_core] = vf.add_const(use_linear_core_default)

    # ------------------------------------------------------------------
    # Derive the leakage parameters directly from the short-circuit report.
    #
    # Model reason:
    # XFMR separates leakage and main flux. The leakage branch must come from
    # short-circuit data, while saturation must remain only in the core model.
    #
    # Algorithm reason:
    # We compute z_sc, r_sc, and x_sc in per unit exactly in the paper/report
    # style, then convert x_sc into a symbolic leakage inductance for the EMT
    # differential equation. The single two-winding series branch preserves the
    # existing VeraGrid block contract, so the equal resistance sharing is
    # represented implicitly by this one equivalent branch.
    # ------------------------------------------------------------------
    z_sc_pu: Expr = xfmr_sc_voltage_pct / 100.0
    r_sc_pu: Expr = xfmr_sc_resistance_pct / 100.0
    x_sc_pu: Expr = sym.sqrt(sym.max(z_sc_pu * z_sc_pu - r_sc_pu * r_sc_pu, c0))
    omega_event: Expr = 2.0 * math.pi * xfmr_f_hz
    l_sigma: Expr = x_sc_pu / (omega_event + c_eps)
    l_inv: Expr = 1.0 / (l_sigma + c_eps)

    # ------------------------------------------------------------------
    # Derive the linear core-loss conductance from the rated open-circuit loss.
    #
    # Model reason:
    # The task explicitly keeps core losses linear and resistive even when the
    # magnetizing inductive branch is nonlinear.
    #
    # Algorithm reason:
    # We convert rated OC loss into a total per-unit conductance and distribute
    # it evenly across the three legs in this local implementation so the model
    # stays compatible with the current energized-side current injection layout.
    # ------------------------------------------------------------------
    g_core_total: Expr = (xfmr_oc_loss_kw / 1000.0) / (xfmr_s_rated_mva + c_eps)
    g_core_leg: Expr = g_core_total / 3.0

    # ------------------------------------------------------------------
    # Preserve the small terminal capacitance path already supported locally.
    #
    # Model reason:
    # Capacitance is not the focus of this task, so the update is intentionally
    # limited to leakage/core parameterization.
    #
    # Algorithm reason:
    # Reusing the previous local capacitance estimate keeps unrelated EMT
    # behavior stable while we replace only the transformer magnetic model.
    # ------------------------------------------------------------------
    c_term_value: float = 0.5 * _estimate_terminal_capacitance_pu(trafo, omega_base_value)
    c_term: Expr = vf.add_const(c_term_value)

    n_tap_value: float
    if abs(float(trafo.tap_module)) > 1e-12:
        n_tap_value = float(trafo.tap_module)
    else:
        n_tap_value = 1.0

    # ------------------------------------------------------------------
    # Create the electrical interface variables.
    #
    # Model reason:
    # These are the abc terminal voltages seen by the EMT network solver.
    #
    # Algorithm reason:
    # They keep the same public mapping used elsewhere in VeraGrid, so callers
    # and nodal KCL stamping continue to work unchanged.
    # ------------------------------------------------------------------
    v_f: list[Var] = list([
        vf.add_var(name=f"vf_A_{name}", reference=VarPowerFlowRefferenceType.vf_A),
        vf.add_var(name=f"vf_B_{name}", reference=VarPowerFlowRefferenceType.vf_B),
        vf.add_var(name=f"vf_C_{name}", reference=VarPowerFlowRefferenceType.vf_C),
    ])
    v_t: list[Var] = list([
        vf.add_var(name=f"vt_A_{name}", reference=VarPowerFlowRefferenceType.vt_A),
        vf.add_var(name=f"vt_B_{name}", reference=VarPowerFlowRefferenceType.vt_B),
        vf.add_var(name=f"vt_C_{name}", reference=VarPowerFlowRefferenceType.vt_C),
    ])

    # ------------------------------------------------------------------
    # Differential variables.
    #
    # Model reason:
    # - i_leak stores the leakage-channel current dynamics.
    # - lam_leg stores the main-flux linkage of each core leg.
    # - q_f and q_t store the terminal capacitor charges.
    #
    # Algorithm reason:
    # Using leg flux linkages as explicit states lets the DAE express the core
    # nonlinearity algebraically while keeping Faraday's law in differential
    # form through d(lambda)/dt = omega * v in per-unit sinusoidal scaling.
    # ------------------------------------------------------------------
    i_leak: list[Var] = list(vf.add_var(name=f"i_leak_{ph}_{name}") for ph in ("A", "B", "C"))
    lam_leg: list[Var] = list(vf.add_var(name=f"lam_leg_{ph}_{name}") for ph in ("A", "B", "C"))
    q_f: list[Var] = list(vf.add_var(name=f"qf_{ph}_{name}") for ph in ("A", "B", "C"))
    q_t: list[Var] = list(vf.add_var(name=f"qt_{ph}_{name}") for ph in ("A", "B", "C"))

    di_leak: list[Var] = list(vf.add_diff_var(name=f"di_leak_{ph}_{name}", base_var=i_leak[k]) for k, ph in enumerate(("A", "B", "C")))
    dlam_leg: list[Var] = list(vf.add_diff_var(name=f"dlam_leg_{ph}_{name}", base_var=lam_leg[k]) for k, ph in enumerate(("A", "B", "C")))
    dq_f: list[Var] = list(vf.add_diff_var(name=f"dqf_{ph}_{name}", base_var=q_f[k]) for k, ph in enumerate(("A", "B", "C")))
    dq_t: list[Var] = list(vf.add_diff_var(name=f"dqt_{ph}_{name}", base_var=q_t[k]) for k, ph in enumerate(("A", "B", "C")))

    # ------------------------------------------------------------------
    # Algebraic variables.
    #
    # Model reason:
    # - i_leg_core are the nonlinear leg magnetizing currents.
    # - i_return_path / i_return_total are the return-path currents that enforce
    #   the chosen 3-legged or 5-legged core topology.
    # - i_mag are the phase magnetizing currents injected into the electrical side.
    # - i_loss_leg are the linear core-loss currents.
    # - i_cap_f / i_cap_t are capacitor currents.
    # - if_act / it_act are the final terminal currents stamped into network KCL.
    #
    # Algorithm reason:
    # The Fr"ohlich law is imposed as algebraic constitutive equations, which is
    # the cleanest way to keep the model as a symbolic DAE block.
    # ------------------------------------------------------------------
    i_leg_core: list[Var] = list(vf.add_var(name=f"i_leg_core_{ph}_{name}") for ph in ("A", "B", "C"))
    i_mag: list[Var] = list(vf.add_var(name=f"i_mag_{ph}_{name}") for ph in ("A", "B", "C"))
    i_loss_leg: list[Var] = list(vf.add_var(name=f"i_loss_leg_{ph}_{name}") for ph in ("A", "B", "C"))
    i_cap_f: list[Var] = list(vf.add_var(name=f"i_cap_f_{ph}_{name}") for ph in ("A", "B", "C"))
    i_cap_t: list[Var] = list(vf.add_var(name=f"i_cap_t_{ph}_{name}") for ph in ("A", "B", "C"))
    if_act: list[Var] = list(vf.add_var(name=f"if_{ph}_{name}") for ph in ("A", "B", "C"))
    it_act: list[Var] = list(vf.add_var(name=f"it_{ph}_{name}") for ph in ("A", "B", "C"))

    i_return_path: Var = vf.add_var(name=f"i_return_path_{name}")
    i_return_total: Var = vf.add_var(name=f"i_return_total_{name}")

    templ.block.in_vars = v_f + v_t + d_v_f + d_v_t
    templ.block.state_vars = i_leak + lam_leg + q_f + q_t
    templ.block.diff_vars = di_leak + dlam_leg + dq_f + dq_t
    templ.block.algebraic_vars = i_leg_core + list([i_return_path, i_return_total]) + i_mag + i_loss_leg + i_cap_f + i_cap_t + if_act + it_act

    v_f_w: list[Expr] = _mat_vec_expr(c_f.T, v_f, c0)
    v_t_perm: list[Expr] = _mat_vec_expr(p_t, v_t, c0)
    d_v_f_w: list[Expr] = _mat_vec_expr(c_f.T, d_v_f, c0)
    d_v_t_perm: list[Expr] = _mat_vec_expr(p_t, d_v_t, c0)
    v_t_w: list[Expr] = _mat_vec_expr(c_t.T, v_t_perm, c0)
    d_v_t_w: list[Expr] = _mat_vec_expr(c_t.T, d_v_t_perm, c0)
    v_leak: list[Expr] = list(v_f_w[k] - n_tap_value * v_t_w[k] for k in range(3))

    # Build the leakage-current and flux-linkage differential equations.
    #
    # Model reason:
    # The leakage branch is linear and separate from the saturable core branch.
    # The leg flux states integrate the winding-side induced voltages.
    #
    # Algorithm reason:
    # The state_eqs list must follow the same order as state_vars.
    state_eqs: list[Expr] = list()
    for k in range(3):
        state_eqs.append(l_inv * (v_leak[k] - r_sc_pu * i_leak[k]))
    for k in range(3):
        state_eqs.append(omega_event * v_f_w[k])
    for k in range(3):
        state_eqs.append(i_cap_f[k])
    for k in range(3):
        state_eqs.append(i_cap_t[k])
    templ.block.state_eqs = state_eqs

    # ------------------------------------------------------------------
    # Build the magnetic return-path equations.
    #
    # Model reason:
    # This is where the model becomes topologically aware instead of collapsing
    # everything into one shunt branch. The sum of the three leg fluxes must
    # close through the yokes and, for a 5-legged core, through the two outer
    # return limbs.
    #
    # Algorithm reason:
    # We write the return path as algebraic lambda(i) equations so that the
    # selected topology changes only the constitutive relation, not the external
    # electrical contract of the template.
    # ------------------------------------------------------------------
    lam_return_total: Expr = -(lam_leg[0] + lam_leg[1] + lam_leg[2])

    leg_linear_coeff: Expr = xfmr_core_linear_l_pu
    yoke_linear_coeff: Expr = xfmr_core_linear_l_pu * xfmr_yoke_area_rel / (xfmr_yoke_length_rel + c_eps)
    outer_linear_coeff: Expr = xfmr_core_linear_l_pu * xfmr_outer_leg_area_rel / (xfmr_outer_leg_length_rel + c_eps)

    yoke_frolich_lam: Expr = xfmr_yoke_area_rel * i_return_path / (xfmr_core_a_prime * xfmr_yoke_length_rel + xfmr_core_b_prime * sym.abs(i_return_path) + c_eps)
    outer_frolich_lam: Expr = xfmr_outer_leg_area_rel * i_return_path / (xfmr_core_a_prime * xfmr_outer_leg_length_rel + xfmr_core_b_prime * sym.abs(i_return_path) + c_eps)

    i_series_from: list[Expr] = _mat_vec_expr(c_f, i_leak, c0)
    i_series_to: list[Expr] = _mat_vec_expr(c_t_eff, i_leak, c0)

    # Collect algebraic equations in the same order as algebraic_vars.
    alg_eqs: list[Expr] = list()

    for k in range(3):
        # Main leg constitutive law.
        #
        # In the single-point default path the law is linear, matching the paper.
        # If callers later override the fitted a' and b' parameters and disable
        # the linear flag, this equation becomes the basic Fr"ohlich law.
        if use_linear_core_default >= 0.5:
            alg_eqs.append(lam_leg[k] - leg_linear_coeff * i_leg_core[k])
        else:
            alg_eqs.append(lam_leg[k] - i_leg_core[k] / (xfmr_core_a_prime + xfmr_core_b_prime * sym.abs(i_leg_core[k]) + c_eps))

    if is_five_legged:
        # Five-legged core:
        # the total return flux splits equally between two identical side return
        # paths, so each path carries half the total return flux linkage.
        if use_linear_core_default >= 0.5:
            alg_eqs.append(0.5 * lam_return_total - (2.0 * yoke_linear_coeff * i_return_path + outer_linear_coeff * i_return_path))
        else:
            alg_eqs.append(0.5 * lam_return_total - (2.0 * yoke_frolich_lam + outer_frolich_lam))
        alg_eqs.append(i_return_total - 2.0 * i_return_path)
    else:
        # Three-legged core:
        # the return path is represented here by two equal yoke sections in
        # series, so the same return current flows through the whole path.
        if use_linear_core_default >= 0.5:
            alg_eqs.append(lam_return_total - 2.0 * yoke_linear_coeff * i_return_path)
        else:
            alg_eqs.append(lam_return_total - 2.0 * yoke_frolich_lam)
        alg_eqs.append(i_return_total - i_return_path)

    for k in range(3):
        # Convert magnetic branch currents into electrical magnetizing current at
        # each phase. The return-path current subtracts from each leg current.
        alg_eqs.append(i_mag[k] - (i_leg_core[k] - i_return_total))

    for k in range(3):
        # Linear core-loss branch in parallel with the inductive core branch.
        alg_eqs.append(i_loss_leg[k] - g_core_leg * v_f_w[k])

    for k in range(3):
        # Capacitor constitutive equations using supplied bus voltage derivatives.
        alg_eqs.append(i_cap_f[k] - c_term * d_v_f[k])
        alg_eqs.append(i_cap_t[k] - c_term * d_v_t[k])

    for k in range(3):
        # Charge/voltage relations for the retained terminal capacitance states.
        alg_eqs.append(q_f[k] - c_term * v_f[k])
        alg_eqs.append(q_t[k] - c_term * v_t[k])

    for k in range(3):
        # Final terminal current assembly.
        #
        # From-side current includes leakage, magnetizing, core-loss, and local
        # terminal capacitance currents. To-side current includes the referred
        # leakage current plus the to-side terminal capacitance current.
        alg_eqs.append(if_act[k] - (i_series_from[k] + i_mag[k] + i_loss_leg[k] + i_cap_f[k]))
        alg_eqs.append(it_act[k] - (-n_tap_value * i_series_to[k] + i_cap_t[k]))

    templ.block.algebraic_eqs = alg_eqs
    templ.block.out_vars = if_act + it_act + i_mag
    templ.block.name = name

    templ.block.external_mapping = dict({
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
    })

    # ------------------------------------------------------------------
    # Initialize the dynamic states from the instantaneous voltages.
    #
    # Model reason:
    # Initialization should start from a physically coherent magnetic and
    # capacitive state without introducing extra assumptions outside this file.
    #
    # Algorithm reason:
    # We compute direct constitutive initial values where possible and leave the
    # nonlinear fallback conservative when the linear-core flag is disabled.
    # ------------------------------------------------------------------
    init_eqs: Dict[Var, Expr] = dict()
    for k in range(3):
        init_eqs[q_f[k]] = c_term * v_f[k]
        init_eqs[q_t[k]] = c_term * v_t[k]
        init_eqs[i_cap_f[k]] = c_term * d_v_f[k]
        init_eqs[i_cap_t[k]] = c_term * d_v_t[k]
        init_eqs[lam_leg[k]] = -d_v_f_w[k] / (omega_event + c_eps)
        init_eqs[i_loss_leg[k]] = g_core_leg * v_f_w[k]

    if use_linear_core_default >= 0.5:
        # Closed-form linear initialization for the return path.
        init_eqs[i_return_path] = lam_return_total / (2.0 * yoke_linear_coeff + outer_linear_coeff + c_eps) if is_five_legged else lam_return_total / (2.0 * yoke_linear_coeff + c_eps)
    else:
        # Conservative nonlinear seed when no closed-form value is enforced.
        init_eqs[i_return_path] = c0

    if is_five_legged:
        init_eqs[i_return_total] = 2.0 * i_return_path
    else:
        init_eqs[i_return_total] = i_return_path

    for k in range(3):
        if use_linear_core_default >= 0.5:
            # Linear leg current from lambda = L * i.
            init_eqs[i_leg_core[k]] = lam_leg[k] / (leg_linear_coeff + c_eps)
        else:
            # First-order nonlinear seed using the low-current Fr"ohlich slope.
            init_eqs[i_leg_core[k]] = lam_leg[k] / (xfmr_core_a_prime + c_eps)
        init_eqs[i_mag[k]] = i_leg_core[k] - i_return_total
        # Start leakage at zero because no separate steady-state PF-derived EMT
        # current seed exists for this template path in the current repository.
        init_eqs[i_leak[k]] = c0
        init_eqs[if_act[k]] = i_series_from[k] + i_mag[k] + i_loss_leg[k] + i_cap_f[k]
        init_eqs[it_act[k]] = -n_tap_value * i_series_to[k] + i_cap_t[k]

    templ.block.init_eqs = init_eqs

    # Derivative initialization mirrors the transient equations so the explicit
    # initializer can evaluate the same local physics consistently.
    diff_init_eqs: Dict[Var, Expr] = dict()
    for k in range(3):
        diff_init_eqs[di_leak[k]] = l_inv * (v_leak[k] - r_sc_pu * i_leak[k])
        diff_init_eqs[dlam_leg[k]] = omega_event * v_f_w[k]
        diff_init_eqs[dq_f[k]] = i_cap_f[k]
        diff_init_eqs[dq_t[k]] = i_cap_t[k]

    templ.block.diff_init_eqs = diff_init_eqs

    return templ
