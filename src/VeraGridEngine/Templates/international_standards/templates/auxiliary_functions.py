# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Maintainable equation builders for the direct REE catalogue models.

The public modules beside this file provide the stable catalogue surface.
This module only centralises equations shared by the synchronous machines,
induction machines, loads, and turbine governors.
"""

from __future__ import annotations

import math
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const
from VeraGridEngine.Utils.Symbolic.symbolic import Expr
from VeraGridEngine.Utils.Symbolic.symbolic import Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.enumerations import DeviceType, InductionMachineRole



def _build_diff_vars(vf: VarFactory, state_vars: list[Var]) -> list[Var]:
    """
    Allocate derivative variables for one ordered continuous-state collection.

    :param vf: Variable factory that owns the derivative variables.
    :type vf: VarFactory
    :param state_vars: Ordered continuous-state variables.
    :type state_vars: list[Var]
    :return: Derivative variables in the same order as ``state_vars``.
    :rtype: list[Var]
    """
    diff_vars: list[Var] = list()
    state_var: Var

    # Preserve state order because solver indexing couples each derivative to this exact position.
    for state_var in state_vars:
        diff_vars.append(vf.add_diff_var(name=f"d_{state_var.name}", base_var=state_var))

    return diff_vars


def _quadratic_saturation(
    value: Expr,
    s10: Expr,
    s12: Expr,
    vf: VarFactory,
) -> Expr:
    """
    Evaluate the standard two-point quadratic saturation ``SE(value)``.

    :param value: Flux-related quantity to saturate.
    :type value: Expr
    :param s10: Saturation value measured at 1.0 pu.
    :type s10: Expr
    :param s12: Saturation value measured at 1.2 pu.
    :type s12: Expr
    :param vf: Variable factory that owns the supporting constants.
    :type vf: VarFactory
    :return: Symbolic quadratic saturation expression.
    :rtype: Expr
    """
    # Recover the quadratic coefficients from the two published saturation
    # points while guarding degenerate parameter combinations numerically.
    zero: Const = vf.add_const(value=0.0)
    eps: Const = vf.add_const(value=1.0e-9)
    one: Const = vf.add_const(value=1.0)
    v12: Const = vf.add_const(value=1.2)
    root_10: Expr = sym.sqrt(sym.max(s10, zero))
    root_12: Expr = sym.sqrt(sym.max(s12, zero))
    slope: Expr = (root_12 - root_10) / (v12 - one)
    slope_safe: Expr = sym.max(slope, eps)
    intercept: Expr = one - root_10 / slope_safe
    enabled: Expr = sym.heaviside(s12 - eps) * sym.heaviside(slope - eps)
    return enabled * slope * slope * sym.max(value - intercept, zero) ** 2


def build_genrou(vf: VarFactory, name: str) -> EmtModelTemplate:
    """
    Build the six-state PSS/E GENROU round-rotor machine equations.

    :param vf: Variable factory that owns the machine symbols.
    :type vf: VarFactory
    :param name: Runtime machine name.
    :type name: str
    :return: Materialized GENROU dynamic template.
    :rtype: EmtModelTemplate
    """
    templ: EmtModelTemplate = EmtModelTemplate(name=name)
    templ.tpe = DeviceType.NoDevice
    id_pu: Var = vf.add_var(name=f"IdPu_{name}")
    iq_pu: Var = vf.add_var(name=f"IqPu_{name}")
    efd: Var = vf.add_var(name=f"EfdPu_{name}")
    pm: Var = vf.add_var(name=f"PmPu_{name}")

    delta: Var = vf.add_var(name=f"DeltaRad_{name}")
    omega: Var = vf.add_var(name=f"OmegaPu_{name}")
    epq: Var = vf.add_var(name=f"EpqPu_{name}")
    epd: Var = vf.add_var(name=f"EpdPu_{name}")
    psikd: Var = vf.add_var(name=f"PsiKdPu_{name}")
    psikq: Var = vf.add_var(name=f"PsiKqPu_{name}")
    states: list[Var] = list((delta, omega, epq, epd, psikd, psikq))

    psi_ppd: Var = vf.add_var(name=f"PsiPPdPu_{name}")
    psi_ppq: Var = vf.add_var(name=f"PsiPPqPu_{name}")
    psi_d: Var = vf.add_var(name=f"PsiDPu_{name}")
    psi_q: Var = vf.add_var(name=f"PsiQPu_{name}")
    psi_pp: Var = vf.add_var(name=f"PsiPPPu_{name}")
    xad_ifd: Var = vf.add_var(name=f"XadIfdPu_{name}")
    xaq_ilq: Var = vf.add_var(name=f"XaqIlqPu_{name}")
    te: Var = vf.add_var(name=f"TePu_{name}")
    ud: Var = vf.add_var(name=f"UdPu_{name}")
    uq: Var = vf.add_var(name=f"UqPu_{name}")
    pe: Var = vf.add_var(name=f"PePu_{name}")

    f_hz: Var = vf.add_var(name=f"FNomHz_{name}")
    h: Var = vf.add_var(name=f"H_{name}")
    damping: Var = vf.add_var(name=f"D_{name}")
    ra: Var = vf.add_var(name=f"RaPu_{name}")
    xd: Var = vf.add_var(name=f"XdPu_{name}")
    xq: Var = vf.add_var(name=f"XqPu_{name}")
    xpd: Var = vf.add_var(name=f"XpdPu_{name}")
    xpq: Var = vf.add_var(name=f"XpqPu_{name}")
    xppd: Var = vf.add_var(name=f"XppdPu_{name}")
    xppq: Var = vf.add_var(name=f"XppqPu_{name}")
    xl: Var = vf.add_var(name=f"XlPu_{name}")
    tpd0: Var = vf.add_var(name=f"Tpd0_{name}")
    tpq0: Var = vf.add_var(name=f"Tpq0_{name}")
    tppd0: Var = vf.add_var(name=f"Tppd0_{name}")
    tppq0: Var = vf.add_var(name=f"Tppq0_{name}")
    s10: Var = vf.add_var(name=f"S10_{name}")
    s12: Var = vf.add_var(name=f"S12_{name}")
    events: dict[Var, Expr | Const] = dict()
    events[f_hz] = vf.add_const(value=50.0)
    events[h] = vf.add_const(value=3.5)
    events[damping] = vf.add_const(value=0.0)
    events[ra] = vf.add_const(value=0.0025)
    events[xd] = vf.add_const(value=1.8)
    events[xq] = vf.add_const(value=1.7)
    events[xpd] = vf.add_const(value=0.30)
    events[xpq] = vf.add_const(value=0.55)
    events[xppd] = vf.add_const(value=0.25)
    events[xppq] = vf.add_const(value=0.25)
    events[xl] = vf.add_const(value=0.20)
    events[tpd0] = vf.add_const(value=8.0)
    events[tpq0] = vf.add_const(value=0.40)
    events[tppd0] = vf.add_const(value=0.03)
    events[tppq0] = vf.add_const(value=0.05)
    events[s10] = vf.add_const(value=0.0)
    events[s12] = vf.add_const(value=0.0)
    eps: Const = vf.add_const(value=1.0e-9)
    two: Const = vf.add_const(value=2.0)
    omega_b: Expr = two * vf.add_const(value=math.pi) * f_hz
    k1d: Expr = (xpd - xppd) * (xd - xpd) / sym.max((xpd - xl) ** 2, eps)
    k1q: Expr = (xpq - xppq) * (xq - xpq) / sym.max((xpq - xl) ** 2, eps)
    k3d: Expr = (xppd - xl) / sym.max(xpd - xl, eps)
    k4d: Expr = (xpd - xppd) / sym.max(xpd - xl, eps)
    k3q: Expr = (xppq - xl) / sym.max(xpq - xl, eps)
    k4q: Expr = (xpq - xppq) / sym.max(xpq - xl, eps)
    se: Expr = _quadratic_saturation(psi_pp, s10, s12, vf)

    psi_ppd_expr: Expr = epq * k3d + psikd * k4d
    psi_ppq_expr: Expr = epd * k3q + psikq * k4q
    psi_d_expr: Expr = psi_ppd - xppd * id_pu
    psi_q_expr: Expr = -psi_ppq - xppq * iq_pu
    psi_pp_expr: Expr = sym.sqrt(psi_ppd * psi_ppd + psi_ppq * psi_ppq)
    xad_expr: Expr = (
        k1d * (epq - psikd - (xpd - xl) * id_pu)
        + epq + (xd - xpd) * id_pu + se * psi_ppd
    )
    xaq_expr: Expr = (
        k1q * (epd - psikq + (xpq - xl) * iq_pu)
        + epd - (xq - xpq) * iq_pu
        + se * psi_ppq * (xq - xl) / sym.max(xd - xl, eps)
    )
    te_expr: Expr = psi_d * iq_pu - psi_q * id_pu
    ud_expr: Expr = -psi_q - ra * id_pu
    uq_expr: Expr = psi_d - ra * iq_pu
    pe_expr: Expr = ud * id_pu + uq * iq_pu

    templ.block = Block(
        state_vars=states,
        diff_vars=_build_diff_vars(vf=vf, state_vars=states),
        state_eqs=[
            omega_b * (omega - vf.add_const(value=1.0)),
            (pm - te - damping * (omega - vf.add_const(value=1.0))) / sym.max(two * h, eps),
            (efd - xad_ifd) / sym.max(tpd0, eps),
            -xaq_ilq / sym.max(tpq0, eps),
            (epq - psikd - (xpd - xl) * id_pu) / sym.max(tppd0, eps),
            (epd - psikq + (xpq - xl) * iq_pu) / sym.max(tppq0, eps),
        ],
        algebraic_vars=[psi_ppd, psi_ppq, psi_d, psi_q, psi_pp, xad_ifd, xaq_ilq, te, ud, uq, pe],
        algebraic_eqs=[
            psi_ppd - psi_ppd_expr, psi_ppq - psi_ppq_expr,
            psi_d - psi_d_expr, psi_q - psi_q_expr, psi_pp - psi_pp_expr,
            xad_ifd - xad_expr, xaq_ilq - xaq_expr, te - te_expr,
            ud - ud_expr, uq - uq_expr, pe - pe_expr,
        ],
        init_eqs={
            id_pu: vf.add_const(value=0.0), iq_pu: vf.add_const(value=0.0),
            efd: vf.add_const(value=1.0), pm: vf.add_const(value=0.0),
            delta: vf.add_const(value=0.0), omega: vf.add_const(value=1.0),
            epq: vf.add_const(value=1.0), epd: vf.add_const(value=0.0),
            psikd: vf.add_const(value=1.0), psikq: vf.add_const(value=0.0),
            psi_ppd: psi_ppd_expr, psi_ppq: psi_ppq_expr,
            psi_d: psi_d_expr, psi_q: psi_q_expr, psi_pp: psi_pp_expr,
            xad_ifd: xad_expr, xaq_ilq: xaq_expr, te: te_expr,
            ud: ud_expr, uq: uq_expr, pe: pe_expr,
        },
        event_dict=events,
        in_vars=[id_pu, iq_pu, efd, pm],
        out_vars=[ud, uq, pe, omega],
        name=name,
    )
    return templ


def build_gensal(vf: VarFactory, name: str) -> EmtModelTemplate:
    """
    Build the five-state PSS/E GENSAL salient-pole machine equations.

    :param vf: Variable factory that owns the machine symbols.
    :type vf: VarFactory
    :param name: Runtime machine name.
    :type name: str
    :return: Materialized GENSAL dynamic template.
    :rtype: EmtModelTemplate
    """
    templ: EmtModelTemplate = EmtModelTemplate(name=name)
    templ.tpe = DeviceType.NoDevice
    id_pu: Var = vf.add_var(name=f"IdPu_{name}")
    iq_pu: Var = vf.add_var(name=f"IqPu_{name}")
    efd: Var = vf.add_var(name=f"EfdPu_{name}")
    pm: Var = vf.add_var(name=f"PmPu_{name}")
    delta: Var = vf.add_var(name=f"DeltaRad_{name}")
    omega: Var = vf.add_var(name=f"OmegaPu_{name}")
    epq: Var = vf.add_var(name=f"EpqPu_{name}")
    psikd: Var = vf.add_var(name=f"PsiKdPu_{name}")
    psi_ppq: Var = vf.add_var(name=f"PsiPPqStatePu_{name}")
    states: list[Var] = list((delta, omega, epq, psikd, psi_ppq))

    psi_ppd: Var = vf.add_var(name=f"PsiPPdPu_{name}")
    psi_d: Var = vf.add_var(name=f"PsiDPu_{name}")
    psi_q: Var = vf.add_var(name=f"PsiQPu_{name}")
    xad_ifd: Var = vf.add_var(name=f"XadIfdPu_{name}")
    te: Var = vf.add_var(name=f"TePu_{name}")
    ud: Var = vf.add_var(name=f"UdPu_{name}")
    uq: Var = vf.add_var(name=f"UqPu_{name}")
    pe: Var = vf.add_var(name=f"PePu_{name}")

    f_hz: Var = vf.add_var(name=f"FNomHz_{name}")
    h: Var = vf.add_var(name=f"H_{name}")
    damping: Var = vf.add_var(name=f"D_{name}")
    ra: Var = vf.add_var(name=f"RaPu_{name}")
    xd: Var = vf.add_var(name=f"XdPu_{name}")
    xq: Var = vf.add_var(name=f"XqPu_{name}")
    xpd: Var = vf.add_var(name=f"XpdPu_{name}")
    xppd: Var = vf.add_var(name=f"XppdPu_{name}")
    xppq: Var = vf.add_var(name=f"XppqPu_{name}")
    xl: Var = vf.add_var(name=f"XlPu_{name}")
    tpd0: Var = vf.add_var(name=f"Tpd0_{name}")
    tppd0: Var = vf.add_var(name=f"Tppd0_{name}")
    tppq0: Var = vf.add_var(name=f"Tppq0_{name}")
    s10: Var = vf.add_var(name=f"S10_{name}")
    s12: Var = vf.add_var(name=f"S12_{name}")
    events: dict[Var, Expr | Const] = dict()
    events[f_hz] = vf.add_const(value=50.0)
    events[h] = vf.add_const(value=3.5)
    events[damping] = vf.add_const(value=0.0)
    events[ra] = vf.add_const(value=0.0025)
    events[xd] = vf.add_const(value=1.8)
    events[xq] = vf.add_const(value=1.7)
    events[xpd] = vf.add_const(value=0.30)
    events[xppd] = vf.add_const(value=0.25)
    events[xppq] = vf.add_const(value=0.25)
    events[xl] = vf.add_const(value=0.20)
    events[tpd0] = vf.add_const(value=8.0)
    events[tppd0] = vf.add_const(value=0.03)
    events[tppq0] = vf.add_const(value=0.05)
    events[s10] = vf.add_const(value=0.0)
    events[s12] = vf.add_const(value=0.0)
    eps: Const = vf.add_const(value=1.0e-9)
    one: Const = vf.add_const(value=1.0)
    two: Const = vf.add_const(value=2.0)
    omega_b: Expr = two * vf.add_const(value=math.pi) * f_hz
    k1d: Expr = (xpd - xppd) * (xd - xpd) / sym.max((xpd - xl) ** 2, eps)
    k3d: Expr = (xppd - xl) / sym.max(xpd - xl, eps)
    k4d: Expr = (xpd - xppd) / sym.max(xpd - xl, eps)
    se: Expr = _quadratic_saturation(epq, s10, s12, vf)
    psi_ppd_expr: Expr = epq * k3d + psikd * k4d
    psi_d_expr: Expr = psi_ppd - xppd * id_pu
    psi_q_expr: Expr = -psi_ppq - xppq * iq_pu
    xad_expr: Expr = (
        k1d * (epq - psikd - (xpd - xl) * id_pu)
        + (xd - xpd) * id_pu + (one + se) * epq
    )
    te_expr: Expr = psi_d * iq_pu - psi_q * id_pu
    ud_expr: Expr = -psi_q - ra * id_pu
    uq_expr: Expr = psi_d - ra * iq_pu
    pe_expr: Expr = ud * id_pu + uq * iq_pu
    templ.block = Block(
        state_vars=states,
        diff_vars=_build_diff_vars(vf=vf, state_vars=states),
        state_eqs=[
            omega_b * (omega - one),
            (pm - te - damping * (omega - one)) / sym.max(two * h, eps),
            (efd - xad_ifd) / sym.max(tpd0, eps),
            (epq - psikd - (xpd - xl) * id_pu) / sym.max(tppd0, eps),
            (-psi_ppq + (xq - xppq) * iq_pu) / sym.max(tppq0, eps),
        ],
        algebraic_vars=[psi_ppd, psi_d, psi_q, xad_ifd, te, ud, uq, pe],
        algebraic_eqs=[
            psi_ppd - psi_ppd_expr, psi_d - psi_d_expr,
            psi_q - psi_q_expr, xad_ifd - xad_expr, te - te_expr,
            ud - ud_expr, uq - uq_expr, pe - pe_expr,
        ],
        init_eqs={
            id_pu: vf.add_const(value=0.0), iq_pu: vf.add_const(value=0.0),
            efd: one, pm: vf.add_const(value=0.0), delta: vf.add_const(value=0.0),
            omega: one, epq: one, psikd: one, psi_ppq: vf.add_const(value=0.0),
            psi_ppd: psi_ppd_expr, psi_d: psi_d_expr, psi_q: psi_q_expr,
            xad_ifd: xad_expr, te: te_expr, ud: ud_expr, uq: uq_expr, pe: pe_expr,
        },
        event_dict=events,
        in_vars=[id_pu, iq_pu, efd, pm],
        out_vars=[ud, uq, pe, omega],
        name=name,
    )
    return templ


def build_induction_machine(
        vf: VarFactory,
        name: str,
        role: InductionMachineRole,
) -> EmtModelTemplate:
    """
    Build the shared fifth-order induction-machine equations.

    :param vf: Variable factory that owns the machine symbols.
    :type vf: VarFactory
    :param name: Runtime machine name.
    :type name: str
    :param role: Generator or motor sign and torque convention.
    :type role: InductionMachineRole
    :return: Materialized induction-machine template.
    :rtype: EmtModelTemplate
    """
    is_generator: bool = role == InductionMachineRole.GENERATOR
    templ: EmtModelTemplate = EmtModelTemplate(name=name)
    templ.tpe = DeviceType.NoDevice
    vd: Var = vf.add_var(name=f"VdPu_{name}")
    vq: Var = vf.add_var(name=f"VqPu_{name}")
    torque_input: Var = vf.add_var(name=f"{'TmPu' if is_generator else 'TLoad0Pu'}_{name}")
    epr: Var = vf.add_var(name=f"EprPu_{name}")
    epi: Var = vf.add_var(name=f"EpiPu_{name}")
    eppr: Var = vf.add_var(name=f"EpprPu_{name}")
    eppi: Var = vf.add_var(name=f"EppiPu_{name}")
    omega: Var = vf.add_var(name=f"OmegaPu_{name}")
    states: list[Var] = list((epr, epi, eppr, eppi, omega))
    ir: Var = vf.add_var(name=f"IrPu_{name}")
    ii: Var = vf.add_var(name=f"IiPu_{name}")
    te: Var = vf.add_var(name=f"TePu_{name}")
    torque: Var = vf.add_var(name=f"{'TeGeneratorPu' if is_generator else 'TLoadPu'}_{name}")
    p: Var = vf.add_var(name=f"{'PGenPu' if is_generator else 'PLoadPu'}_{name}")
    q: Var = vf.add_var(name=f"{'QGenPu' if is_generator else 'QLoadPu'}_{name}")

    f_hz: Var = vf.add_var(name=f"FNomHz_{name}")
    ra: Var = vf.add_var(name=f"RaPu_{name}")
    xs: Var = vf.add_var(name=f"XsPu_{name}")
    xp: Var = vf.add_var(name=f"XpPu_{name}")
    xpp: Var = vf.add_var(name=f"XppPu_{name}")
    tp0: Var = vf.add_var(name=f"Tp0_{name}")
    tpp0: Var = vf.add_var(name=f"Tpp0_{name}")
    h: Var = vf.add_var(name=f"H_{name}")
    damping: Var = vf.add_var(name=f"Damp_{name}")
    events: dict[Var, Expr | Const] = dict()
    events[f_hz] = vf.add_const(value=50.0)
    events[ra] = vf.add_const(value=0.015)
    events[xs] = vf.add_const(value=3.0)
    events[xp] = vf.add_const(value=0.30)
    events[xpp] = vf.add_const(value=0.20)
    events[tp0] = vf.add_const(value=0.60)
    events[tpp0] = vf.add_const(value=0.05)
    events[h] = vf.add_const(value=0.80)
    events[damping] = vf.add_const(value=0.0)
    eps: Const = vf.add_const(value=1.0e-9)
    one: Const = vf.add_const(value=1.0)
    two: Const = vf.add_const(value=2.0)
    wb: Expr = two * vf.add_const(value=math.pi) * f_hz
    slip: Expr = one - omega
    depr: Expr = wb * slip * epi - (epr + (xs - xp) * ii) / sym.max(tp0, eps)
    depi: Expr = -wb * slip * epr - (epi - (xs - xp) * ir) / sym.max(tp0, eps)
    deppr: Expr = (
        depr + wb * slip * (epi - eppi)
        - (eppr - epr + (xp - xpp) * ii) / sym.max(tpp0, eps)
    )
    deppi: Expr = (
        depi - wb * slip * (epr - eppr)
        - (eppi - epi - (xp - xpp) * ir) / sym.max(tpp0, eps)
    )
    te_motor: Expr = eppr * ir + eppi * ii
    p_motor: Expr = vd * ir + vq * ii
    q_motor: Expr = vq * ir - vd * ii
    x_sync: Expr = xs - two * xpp
    sync_den: Expr = ra * ra + x_sync * x_sync
    ir0: Expr = (-ra * vd + x_sync * vq) / sym.max(sync_den, eps)
    ii0: Expr = (-x_sync * vd - ra * vq) / sym.max(sync_den, eps)
    epr0: Expr = -(xs - xp) * ii0
    epi0: Expr = (xs - xp) * ir0
    eppr0: Expr = -(xs - xpp) * ii0
    eppi0: Expr = (xs - xpp) * ir0
    torque_expr: Expr
    p_expr: Expr
    q_expr: Expr
    domega: Expr
    if role == InductionMachineRole.GENERATOR:
        # The generator convention reports injected network power and balances
        # the mechanical input against the generated electrical torque.
        torque_expr = -te_motor
        p_expr = -p_motor
        q_expr = -q_motor
        domega = (torque_input - torque - damping * (omega - one)) / sym.max(two * h, eps)
    else:
        # Allocate motor-only coefficients inside the motor state so no optional
        # variables or impossible error state leak into the shared equations.
        a: Var = vf.add_var(name=f"A_{name}")
        b: Var = vf.add_var(name=f"B_{name}")
        d: Var = vf.add_var(name=f"D_{name}")
        exponent: Var = vf.add_var(name=f"E_{name}")
        events[a] = vf.add_const(value=0.0)
        events[b] = vf.add_const(value=0.0)
        events[d] = vf.add_const(value=0.0)
        events[exponent] = vf.add_const(value=1.0)
        c0: Expr = one - a - b - d
        torque_expr = torque_input * (a * omega ** 2 + b * omega + c0 + d * omega ** exponent)
        p_expr = p_motor
        q_expr = q_motor
        domega = (te - torque - damping * (omega - one)) / sym.max(two * h, eps)
    templ.block = Block(
        state_vars=states,
        diff_vars=_build_diff_vars(vf=vf, state_vars=states),
        state_eqs=[depr, depi, deppr, deppi, domega],
        algebraic_vars=[ir, ii, te, torque, p, q],
        algebraic_eqs=[
            vd - eppr + ra * ir - xpp * ii,
            vq - eppi + ra * ii + xpp * ir,
            te - te_motor, torque - torque_expr, p - p_expr, q - q_expr,
        ],
        init_eqs={
            vd: vf.add_const(value=0.0), vq: one,
            torque_input: vf.add_const(value=0.0),
            epr: epr0, epi: epi0, eppr: eppr0, eppi: eppi0, omega: one,
            ir: ir0, ii: ii0, te: te_motor, torque: torque_expr,
            p: p_expr, q: q_expr,
        },
        event_dict=events,
        in_vars=[vd, vq, torque_input],
        out_vars=[p, q, omega, te],
        name=name,
    )
    return templ


def build_ieel(vf: VarFactory, name: str) -> EmtModelTemplate:
    """
    Build the algebraic IEEE IEEL voltage/frequency load characteristic.

    :param vf: Variable factory that owns the load symbols.
    :type vf: VarFactory
    :param name: Runtime load name.
    :type name: str
    :return: Materialized IEEL dynamic template.
    :rtype: EmtModelTemplate
    """
    templ: EmtModelTemplate = EmtModelTemplate(name=name)
    templ.tpe = DeviceType.NoDevice
    voltage: Var = vf.add_var(name=f"VPu_{name}")
    frequency: Var = vf.add_var(name=f"FPu_{name}")
    p0: Var = vf.add_var(name=f"P0Pu_{name}")
    q0: Var = vf.add_var(name=f"Q0Pu_{name}")
    p: Var = vf.add_var(name=f"PLoadPu_{name}")
    q: Var = vf.add_var(name=f"QLoadPu_{name}")
    # These parameter vectors have fixed standard-defined sizes. Explicit
    # allocation makes each coefficient position directly inspectable.
    a_vars: list[Var] = list((
        vf.add_var(name=f"a1_{name}"),
        vf.add_var(name=f"a2_{name}"),
        vf.add_var(name=f"a3_{name}"),
        vf.add_var(name=f"a4_{name}"),
        vf.add_var(name=f"a5_{name}"),
        vf.add_var(name=f"a6_{name}"),
        vf.add_var(name=f"a7_{name}"),
        vf.add_var(name=f"a8_{name}"),
    ))
    n_vars: list[Var] = list((
        vf.add_var(name=f"N1_{name}"),
        vf.add_var(name=f"N2_{name}"),
        vf.add_var(name=f"N3_{name}"),
        vf.add_var(name=f"N4_{name}"),
        vf.add_var(name=f"N5_{name}"),
        vf.add_var(name=f"N6_{name}"),
    ))
    pf: Var = vf.add_var(name=f"Pf_{name}")
    events: dict[Var, Expr | Const] = dict()
    parameter_var: Var
    # Start every voltage and frequency coefficient from a neutral zero before
    # enabling the standard constant-power defaults below.
    for parameter_var in a_vars:
        events[parameter_var] = vf.add_const(value=0.0)
    for parameter_var in n_vars:
        events[parameter_var] = vf.add_const(value=0.0)
    events[a_vars[2]] = vf.add_const(value=1.0)
    events[a_vars[5]] = vf.add_const(value=1.0)
    events[pf] = vf.add_const(value=0.0)
    one: Const = vf.add_const(value=1.0)
    eps: Const = vf.add_const(value=1.0e-9)
    voltage_safe: Expr = sym.max(voltage, eps)
    p_voltage: Expr = (
        a_vars[0] * voltage_safe ** n_vars[0]
        + a_vars[1] * voltage_safe ** n_vars[1]
        + a_vars[2] * voltage_safe ** n_vars[2]
    )
    q_voltage: Expr = (
        a_vars[3] * voltage_safe ** n_vars[3]
        + a_vars[4] * voltage_safe ** n_vars[4]
        + a_vars[5] * voltage_safe ** n_vars[5]
    )
    pf_active: Expr = sym.heaviside(sym.abs(pf) - eps)
    pf_sign: Expr = sym.heaviside(pf) - sym.heaviside(-pf)
    pf_abs: Expr = sym.hard_sat(sym.abs(pf), eps, one)
    q_from_pf: Expr = pf_sign * p0 * sym.tan(sym.acos(pf_abs))
    q_reference: Expr = (one - pf_active) * q0 + pf_active * q_from_pf
    p_expr: Expr = p0 * p_voltage * (one + a_vars[6] * (frequency - one))
    q_expr: Expr = q_reference * q_voltage * (one + a_vars[7] * (frequency - one))
    templ.block = Block(
        algebraic_vars=[p, q],
        algebraic_eqs=[p - p_expr, q - q_expr],
        init_eqs={
            voltage: one, frequency: one, p0: one, q0: vf.add_const(value=0.2),
            p: p_expr, q: q_expr,
        },
        event_dict=events,
        in_vars=[voltage, frequency, p0, q0],
        out_vars=[p, q],
        name=name,
    )
    return templ


def build_tgov1(vf: VarFactory, name: str) -> EmtModelTemplate:
    """
    Build the two-state TGOV1 steam-turbine governor.

    :param vf: Variable factory that owns the governor symbols.
    :type vf: VarFactory
    :param name: Runtime governor name.
    :type name: str
    :return: Materialized TGOV1 dynamic template.
    :rtype: EmtModelTemplate
    """
    templ: EmtModelTemplate = EmtModelTemplate(name=name)
    templ.tpe = DeviceType.NoDevice
    omega: Var = vf.add_var(name=f"OmegaPu_{name}")
    pref: Var = vf.add_var(name=f"PRefPu_{name}")
    valve: Var = vf.add_var(name=f"ValvePu_{name}")
    lag: Var = vf.add_var(name=f"TurbineLagPu_{name}")
    speed_error: Var = vf.add_var(name=f"SpeedErrorPu_{name}")
    command: Var = vf.add_var(name=f"ValveCommandPu_{name}")
    pm: Var = vf.add_var(name=f"PmPu_{name}")
    r: Var = vf.add_var(name=f"R_{name}")
    t1: Var = vf.add_var(name=f"T1_{name}")
    vmax: Var = vf.add_var(name=f"Vmax_{name}")
    vmin: Var = vf.add_var(name=f"Vmin_{name}")
    t2: Var = vf.add_var(name=f"T2_{name}")
    t3: Var = vf.add_var(name=f"T3_{name}")
    dt: Var = vf.add_var(name=f"Dt_{name}")
    events: dict[Var, Expr | Const] = dict()
    events[r] = vf.add_const(value=0.05)
    events[t1] = vf.add_const(value=0.10)
    events[vmax] = vf.add_const(value=1.20)
    events[vmin] = vf.add_const(value=0.0)
    events[t2] = vf.add_const(value=0.20)
    events[t3] = vf.add_const(value=10.0)
    events[dt] = vf.add_const(value=0.0)
    eps: Const = vf.add_const(value=1.0e-9)
    one: Const = vf.add_const(value=1.0)
    speed_error_expr: Expr = omega - one
    command_expr: Expr = sym.hard_sat(pref - speed_error / sym.max(r, eps), vmin, vmax)
    lead_fraction: Expr = t2 / sym.max(t3, eps)
    pm_expr: Expr = lead_fraction * valve + (one - lead_fraction) * lag - dt * speed_error
    templ.block = Block(
        state_vars=[valve, lag],
        diff_vars=[
            vf.add_diff_var(name=f"d_{valve.name}", base_var=valve),
            vf.add_diff_var(name=f"d_{lag.name}", base_var=lag),
        ],
        state_eqs=[
            (command - valve) / sym.max(t1, eps),
            (valve - lag) / sym.max(t3, eps),
        ],
        algebraic_vars=[speed_error, command, pm],
        algebraic_eqs=[speed_error - speed_error_expr, command - command_expr, pm - pm_expr],
        init_eqs={
            omega: one, pref: vf.add_const(value=0.5), valve: vf.add_const(value=0.5),
            lag: vf.add_const(value=0.5), speed_error: vf.add_const(value=0.0),
            command: vf.add_const(value=0.5), pm: vf.add_const(value=0.5),
        },
        event_dict=events,
        in_vars=[omega, pref],
        out_vars=[pm, valve],
        name=name,
    )
    return templ


def build_hygov(vf: VarFactory, name: str) -> EmtModelTemplate:
    """
    Build the four-state HYGOV hydro governor and nonlinear water column.

    :param vf: Variable factory that owns the governor symbols.
    :type vf: VarFactory
    :param name: Runtime governor name.
    :type name: str
    :return: Materialized HYGOV dynamic template.
    :rtype: EmtModelTemplate
    """
    templ: EmtModelTemplate = EmtModelTemplate(name=name)
    templ.tpe = DeviceType.NoDevice
    omega: Var = vf.add_var(name=f"OmegaPu_{name}")
    pref: Var = vf.add_var(name=f"PRefPu_{name}")
    filtered_speed: Var = vf.add_var(name=f"FilterOutputPu_{name}")
    desired_gate: Var = vf.add_var(name=f"DesiredGatePu_{name}")
    gate: Var = vf.add_var(name=f"GatePu_{name}")
    flow: Var = vf.add_var(name=f"TurbineFlowPu_{name}")
    gate_demand: Var = vf.add_var(name=f"GateDemandPu_{name}")
    gate_rate: Var = vf.add_var(name=f"GateRatePuPerS_{name}")
    head: Var = vf.add_var(name=f"HeadPu_{name}")
    pm: Var = vf.add_var(name=f"PmPu_{name}")
    rperm: Var = vf.add_var(name=f"Rperm_{name}")
    rtemp: Var = vf.add_var(name=f"Rtemp_{name}")
    tr: Var = vf.add_var(name=f"Tr_{name}")
    tf: Var = vf.add_var(name=f"Tf_{name}")
    tg: Var = vf.add_var(name=f"Tg_{name}")
    velm: Var = vf.add_var(name=f"Velm_{name}")
    gmax: Var = vf.add_var(name=f"Gmax_{name}")
    gmin: Var = vf.add_var(name=f"Gmin_{name}")
    tw: Var = vf.add_var(name=f"Tw_{name}")
    at: Var = vf.add_var(name=f"At_{name}")
    dturb: Var = vf.add_var(name=f"Dturb_{name}")
    qnl: Var = vf.add_var(name=f"Qnl_{name}")
    events: dict[Var, Expr | Const] = dict()
    events[rperm] = vf.add_const(value=0.05)
    events[rtemp] = vf.add_const(value=0.30)
    events[tr] = vf.add_const(value=5.0)
    events[tf] = vf.add_const(value=0.05)
    events[tg] = vf.add_const(value=0.50)
    events[velm] = vf.add_const(value=0.20)
    events[gmax] = vf.add_const(value=1.0)
    events[gmin] = vf.add_const(value=0.0)
    events[tw] = vf.add_const(value=1.0)
    events[at] = vf.add_const(value=1.0)
    events[dturb] = vf.add_const(value=0.0)
    events[qnl] = vf.add_const(value=0.08)
    eps: Const = vf.add_const(value=1.0e-9)
    one: Const = vf.add_const(value=1.0)
    speed_deviation: Expr = omega - one
    demand_expr: Expr = sym.hard_sat(
        pref - filtered_speed / sym.max(rperm, eps) - rtemp * (gate - flow),
        gmin,
        gmax,
    )
    raw_rate: Expr = (desired_gate - gate) / sym.max(tg, eps)
    rate_expr: Expr = sym.hard_sat(raw_rate, -velm, velm)
    block_upper: Expr = sym.heaviside(gate - gmax + eps) * sym.heaviside(rate_expr)
    block_lower: Expr = sym.heaviside(gmin - gate + eps) * sym.heaviside(-rate_expr)
    limited_rate: Expr = (one - block_upper) * (one - block_lower) * rate_expr
    # HYGOV's rigid-water-column relation is h = (q / g)^2.  Keeping the
    # published direction of this ratio is essential: if flow exceeds gate
    # opening, head rises and the water-column derivative must become negative.
    head_expr: Expr = (flow / sym.max(gate, eps)) ** 2
    pm_expr: Expr = at * (flow - qnl) * head - dturb * gate * speed_deviation
    templ.block = Block(
        state_vars=[filtered_speed, desired_gate, gate, flow],
        diff_vars=_build_diff_vars(vf=vf, state_vars=[filtered_speed, desired_gate, gate, flow]),
        state_eqs=[
            (speed_deviation - filtered_speed) / sym.max(tf, eps),
            (gate_demand - desired_gate) / sym.max(tr, eps),
            limited_rate,
            (one - head) / sym.max(tw, eps),
        ],
        algebraic_vars=[gate_demand, gate_rate, head, pm],
        algebraic_eqs=[
            gate_demand - demand_expr, gate_rate - rate_expr,
            head - head_expr, pm - pm_expr,
        ],
        init_eqs={
            omega: one, pref: vf.add_const(value=0.5),
            filtered_speed: vf.add_const(value=0.0), desired_gate: vf.add_const(value=0.5),
            gate: vf.add_const(value=0.5), flow: vf.add_const(value=0.5),
            gate_demand: vf.add_const(value=0.5), gate_rate: vf.add_const(value=0.0),
            head: one, pm: vf.add_const(value=0.42),
        },
        event_dict=events,
        in_vars=[omega, pref],
        out_vars=[pm, gate, flow],
        name=name,
    )
    return templ


def build_ggov1(vf: VarFactory, name: str) -> EmtModelTemplate:
    """
    Build the documented continuous GGOV1 control paths and selectors.

    :param vf: Variable factory that owns the governor symbols.
    :type vf: VarFactory
    :param name: Runtime governor name.
    :type name: str
    :return: Materialized GGOV1 dynamic template.
    :rtype: EmtModelTemplate
    """
    templ: EmtModelTemplate = EmtModelTemplate(name=name)
    templ.tpe = DeviceType.NoDevice
    omega: Var = vf.add_var(name=f"OmegaPu_{name}")
    pe_input: Var = vf.add_var(name=f"PePu_{name}")
    pref: Var = vf.add_var(name=f"PRefPu_{name}")
    acceleration: Var = vf.add_var(name=f"AccelPuPerS_{name}")
    temp_input: Var = vf.add_var(name=f"TempLimitPu_{name}")
    pe_meas: Var = vf.add_var(name=f"PeMeasuredPu_{name}")
    derivative_state: Var = vf.add_var(name=f"DerivativeFilterPu_{name}")
    governor_integral: Var = vf.add_var(name=f"GovernorIntegralPu_{name}")
    actuator: Var = vf.add_var(name=f"ActuatorPu_{name}")
    turbine_lag: Var = vf.add_var(name=f"TurbineLagPu_{name}")
    load_filter: Var = vf.add_var(name=f"LoadFilterPu_{name}")
    load_integral: Var = vf.add_var(name=f"LoadIntegralPu_{name}")
    mw_integral: Var = vf.add_var(name=f"MwIntegralPu_{name}")
    accel_filter: Var = vf.add_var(name=f"AccelFilterPuPerS_{name}")
    temp_lag: Var = vf.add_var(name=f"TemperatureLagPu_{name}")
    states: list[Var] = list((
        pe_meas, derivative_state, governor_integral, actuator, turbine_lag,
        load_filter, load_integral, mw_integral, accel_filter, temp_lag,
    ))
    speed_error: Var = vf.add_var(name=f"SpeedErrorPu_{name}")
    derivative: Var = vf.add_var(name=f"DerivativePu_{name}")
    governor_demand: Var = vf.add_var(name=f"GovernorDemandPu_{name}")
    load_limit: Var = vf.add_var(name=f"LoadLimitPu_{name}")
    accel_limit: Var = vf.add_var(name=f"AccelLimitPu_{name}")
    temp_limit: Var = vf.add_var(name=f"TemperatureLimitPu_{name}")
    low_value: Var = vf.add_var(name=f"LowValueSelectPu_{name}")
    actuator_rate: Var = vf.add_var(name=f"ActuatorRatePuPerS_{name}")
    turbine_output: Var = vf.add_var(name=f"TurbineOutputPu_{name}")
    pm: Var = vf.add_var(name=f"PmPu_{name}")

    # GGOV1 exposes many named parameters that are repeatedly addressed by the
    # published equations. A dictionary is appropriate here solely as a lookup
    # table, and its construction remains explicit for auditability.
    names_defaults: dict[str, float] = dict()
    names_defaults["Rselect"] = 0.0
    names_defaults["Flag"] = 0.0
    names_defaults["R"] = 0.05
    names_defaults["Tpelec"] = 0.10
    names_defaults["Maxerr"] = 0.10
    names_defaults["Minerr"] = -0.10
    names_defaults["Kpgov"] = 10.0
    names_defaults["Kigov"] = 2.0
    names_defaults["Kdgov"] = 0.0
    names_defaults["Tdgov"] = 0.10
    names_defaults["Vmax"] = 1.0
    names_defaults["Vmin"] = 0.0
    names_defaults["Tact"] = 0.20
    names_defaults["Kturb"] = 1.0
    names_defaults["Wfnl"] = 0.0
    names_defaults["Tb"] = 0.50
    names_defaults["Tc"] = 0.0
    names_defaults["Teng"] = 0.0
    names_defaults["Tfload"] = 3.0
    names_defaults["Kpload"] = 0.0
    names_defaults["Kiload"] = 0.0
    names_defaults["Ldref"] = 1.0
    names_defaults["Dm"] = 0.0
    names_defaults["Ropen"] = 0.10
    names_defaults["Rclose"] = -0.10
    names_defaults["Kimw"] = 0.0
    names_defaults["Aset"] = 10.0
    names_defaults["Ka"] = 0.10
    names_defaults["Ta"] = 0.10
    names_defaults["Db"] = 0.0
    names_defaults["Tsa"] = 0.0
    names_defaults["Tsb"] = 1.0
    names_defaults["Rup"] = 99.0
    names_defaults["Rdown"] = -99.0
    params: dict[str, Var] = dict()
    events: dict[Var, Expr | Const] = dict()
    parameter_name: str
    default_value: float
    # Allocate every parameter and its default event together so the two lookup
    # tables cannot diverge while the standard parameter set is extended.
    for parameter_name, default_value in names_defaults.items():
        parameter_var: Var = vf.add_var(name=f"{parameter_name}_{name}")
        params[parameter_name] = parameter_var
        events[parameter_var] = vf.add_const(value=default_value)
    eps: Const = vf.add_const(value=1.0e-9)
    zero: Const = vf.add_const(value=0.0)
    one: Const = vf.add_const(value=1.0)
    speed_deviation: Expr = omega - one
    deadband_abs: Expr = sym.abs(speed_deviation)
    db_active: Expr = sym.heaviside(deadband_abs - params["Db"])
    speed_after_db: Expr = db_active * (
        speed_deviation
        - (sym.heaviside(speed_deviation) - sym.heaviside(-speed_deviation)) * params["Db"]
    )
    error_expr: Expr = sym.hard_sat(
        -speed_after_db - params["R"] * (pe_meas - pref),
        params["Minerr"], params["Maxerr"],
    )
    derivative_expr: Expr = (speed_error - derivative_state) / sym.max(params["Tdgov"], eps)
    governor_expr: Expr = (
        pref + params["Kpgov"] * speed_error + governor_integral
        + params["Kdgov"] * derivative + mw_integral
    )
    load_limit_expr: Expr = params["Kpload"] * (params["Ldref"] - load_filter) + load_integral
    accel_limit_expr: Expr = actuator + params["Ka"] * (params["Aset"] - accel_filter)
    temp_limit_expr: Expr = temp_lag + (params["Tsa"] / sym.max(params["Tsb"], eps)) * (temp_input - temp_lag)
    low_expr: Expr = sym.min(sym.min(governor_demand, load_limit), sym.min(accel_limit, temp_limit))
    raw_actuator_rate: Expr = (low_value - actuator) / sym.max(params["Tact"], eps)
    rate_expr: Expr = sym.hard_sat(raw_actuator_rate, params["Rclose"], params["Ropen"])
    block_upper: Expr = sym.heaviside(actuator - params["Vmax"] + eps) * sym.heaviside(rate_expr)
    block_lower: Expr = sym.heaviside(params["Vmin"] - actuator + eps) * sym.heaviside(-rate_expr)
    limited_actuator_rate: Expr = (one - block_upper) * (one - block_lower) * rate_expr
    turbine_output_expr: Expr = (
        turbine_lag + params["Tc"] / sym.max(params["Tb"], eps) * (actuator - turbine_lag)
    )
    pm_expr: Expr = params["Kturb"] * (turbine_output - params["Wfnl"]) - params["Dm"] * speed_deviation
    load_integral_rate: Expr = sym.hard_sat(
        params["Kiload"] * (params["Ldref"] - load_filter),
        params["Rdown"], params["Rup"],
    )
    templ.block = Block(
        state_vars=states,
        diff_vars=_build_diff_vars(vf=vf, state_vars=states),
        state_eqs=[
            (pe_input - pe_meas) / sym.max(params["Tpelec"], eps),
            derivative_expr,
            params["Kigov"] * speed_error,
            limited_actuator_rate,
            (actuator - turbine_lag) / sym.max(params["Tb"], eps),
            (pe_input - load_filter) / sym.max(params["Tfload"], eps),
            load_integral_rate,
            params["Kimw"] * (pref - pe_meas),
            (acceleration - accel_filter) / sym.max(params["Ta"], eps),
            (temp_input - temp_lag) / sym.max(params["Tsb"], eps),
        ],
        algebraic_vars=[
            speed_error, derivative, governor_demand, load_limit, accel_limit,
            temp_limit, low_value, actuator_rate, turbine_output, pm,
        ],
        algebraic_eqs=[
            speed_error - error_expr, derivative - derivative_expr,
            governor_demand - governor_expr, load_limit - load_limit_expr,
            accel_limit - accel_limit_expr, temp_limit - temp_limit_expr,
            low_value - low_expr, actuator_rate - rate_expr,
            turbine_output - turbine_output_expr, pm - pm_expr,
        ],
        init_eqs={
            omega: one, pe_input: vf.add_const(value=0.5), pref: vf.add_const(value=0.5),
            acceleration: zero, temp_input: one, pe_meas: vf.add_const(value=0.5),
            derivative_state: zero, governor_integral: zero,
            actuator: vf.add_const(value=0.5), turbine_lag: vf.add_const(value=0.5),
            load_filter: vf.add_const(value=0.5), load_integral: one,
            mw_integral: zero, accel_filter: zero, temp_lag: one,
            speed_error: zero, derivative: zero, governor_demand: vf.add_const(value=0.5),
            load_limit: one, accel_limit: vf.add_const(value=1.5), temp_limit: one,
            low_value: vf.add_const(value=0.5), actuator_rate: zero,
            turbine_output: vf.add_const(value=0.5), pm: vf.add_const(value=0.5),
        },
        event_dict=events,
        in_vars=[omega, pe_input, pref, acceleration, temp_input],
        out_vars=[pm, actuator, low_value],
        name=name,
    )
    return templ


def build_generator_band_trip_relay(
        vf: VarFactory,
        name: str,
        measurement_name: str,
        lower_name: str,
        upper_name: str,
        lower_default: float,
        upper_default: float,
) -> EmtModelTemplate:
    """
    Build pickup, breaker-delay, and retained-trip stages around one admissible band.

    :param vf: Variable factory that owns the relay symbols.
    :type vf: VarFactory
    :param name: Runtime relay name.
    :type name: str
    :param measurement_name: Public measurement input name.
    :type measurement_name: str
    :param lower_name: Lower-threshold parameter name.
    :type lower_name: str
    :param upper_name: Upper-threshold parameter name.
    :type upper_name: str
    :param lower_default: Default lower threshold.
    :type lower_default: float
    :param upper_default: Default upper threshold.
    :type upper_default: float
    :return: Materialized generator trip relay.
    :rtype: EmtModelTemplate
    """
    templ: EmtModelTemplate = EmtModelTemplate(name=name)
    templ.tpe = DeviceType.NoDevice

    # Allocate the public measurement and relay settings before composing timing logic.
    measurement: Var = vf.add_var(name=f"{measurement_name}_{name}")
    lower: Var = vf.add_var(name=f"{lower_name}_{name}")
    upper: Var = vf.add_var(name=f"{upper_name}_{name}")
    pickup_time: Var = vf.add_var(name=f"TP_{name}")
    breaker_time: Var = vf.add_var(name=f"TB_{name}")
    manual_reset: Var = vf.add_var(name=f"ManualReset_{name}")

    pickup_mode: Var = vf.add_var(name=f"PickupMode_{name}")
    breaker_mode: Var = vf.add_var(name=f"BreakerMode_{name}")
    trip_mode: Var = vf.add_var(name=f"TripMode_{name}")

    outside_band: Var = vf.add_var(name=f"OutsideBand_{name}")
    pickup_status: Var = vf.add_var(name=f"PickupStatus_{name}")
    breaker_status: Var = vf.add_var(name=f"BreakerStatus_{name}")
    trip: Var = vf.add_var(name=f"Trip_{name}")

    zero: Const = vf.add_const(value=0.0)
    half: Const = vf.add_const(value=0.5)
    outside_expr: Expr = bool_or(measurement < lower, measurement >= upper)

    # Settings remain runtime event parameters while timer states remain procedural modes.
    event_dict: dict[Var, Expr | Const] = dict({
        lower: vf.add_const(value=lower_default),
        upper: vf.add_const(value=upper_default),
        pickup_time: vf.add_const(value=0.00005),
        breaker_time: vf.add_const(value=0.083),
        manual_reset: zero,
    })
    mode_dict: dict[Var, Expr | Const] = dict({
        pickup_mode: zero,
        breaker_mode: zero,
        trip_mode: zero,
    })
    procedural_logic: list[ProceduralLogicBase] = list([
        pickup_dropoff(
            output=pickup_mode,
            boolexpr=outside_expr,
            Tpick=pickup_time,
            Tdrop=zero,
            name=f"pickup_timer_{name}",
        ),
        pickup_dropoff(
            output=breaker_mode,
            # Arm the breaker deadline from the original threshold crossing.
            # Chaining two independent timer objects would make the second
            # stage inherit the solver's previous accepted sample time and
            # could incorrectly overlap TP and TB at an exact forced event.
            boolexpr=outside_expr,
            Tpick=pickup_time + breaker_time,
            Tdrop=zero,
            name=f"breaker_timer_{name}",
        ),
        flipflop(
            boolset=breaker_mode > half,
            boolreset=manual_reset > half,
            output=trip_mode,
            name=f"trip_latch_{name}",
        ),
    ])

    templ.block = Block(
        algebraic_vars=[outside_band, pickup_status, breaker_status, trip],
        algebraic_eqs=[
            outside_band - outside_expr,
            pickup_status - pickup_mode,
            breaker_status - breaker_mode,
            trip - trip_mode,
        ],
        init_eqs={
            measurement: vf.add_const(value=(lower_default + upper_default) / 2.0),
            outside_band: zero,
            pickup_status: zero,
            breaker_status: zero,
            trip: zero,
        },
        event_dict=event_dict,
        mode_dict=mode_dict,
        procedural_logic=procedural_logic,
        in_vars=[measurement],
        out_vars=[trip],
        name=name,
    )
    return templ
