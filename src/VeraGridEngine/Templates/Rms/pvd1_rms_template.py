# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.enumerations import DeviceType, VarPowerFlowRefferenceType
from VeraGridEngine.Utils.Symbolic.block import Block
import VeraGridEngine.Utils.Symbolic.symbolic as sym


def get_pvd1_rms_template(vfactory: VarFactory, name: str = "PVD1 RMS template") -> RmsModelTemplate:
    """
    WECC/ANDES PVD1-inspired RMS PV model.

    This implementation focuses on the core current-command behavior needed for
    RMS studies in VeraGrid:
    - P/Q references to current commands
    - Q(V) droop outside [v0, v1]
    - active/reactive current hard limits with P/Q priority
    - simplified V/f tripping multipliers
    - first-order lag on output currents (tip, tiq)
    """
    templ = RmsModelTemplate(name=name)
    templ.tpe = DeviceType.GeneratorDevice

    vm = vfactory.add_var(f"Vm_{name}", VarPowerFlowRefferenceType.Vm)
    va = vfactory.add_var(f"Va_{name}", VarPowerFlowRefferenceType.Va)
    inputs = [vm, va]

    p = vfactory.add_var("P_pvd1")
    q = vfactory.add_var("Q_pvd1")
    ip_cmd = vfactory.add_var("Ip_cmd")
    iq_cmd = vfactory.add_var("Iq_cmd")
    ip_max = vfactory.add_var("Ip_max")
    iq_max = vfactory.add_var("Iq_max")
    p_sum = vfactory.add_var("P_sum")
    q_sum = vfactory.add_var("Q_sum")
    q_droop = vfactory.add_var("Q_droop")
    f_trip = vfactory.add_var("F_trip")
    v_trip = vfactory.add_var("V_trip")

    ipout = vfactory.add_var("Ipout_y")
    iqout = vfactory.add_var("Iqout_y")

    pref0 = vfactory.add_var("pref0")
    qref0 = vfactory.add_var("qref0")
    pext0 = vfactory.add_var("pext0")
    qmx = vfactory.add_var("qmx")
    qmn = vfactory.add_var("qmn")
    pmx = vfactory.add_var("pmx")
    v0 = vfactory.add_var("v0")
    v1 = vfactory.add_var("v1")
    dqdv = vfactory.add_var("dqdv")
    ialim = vfactory.add_var("ialim")
    pqflag = vfactory.add_var("pqflag")
    tip = vfactory.add_var("tip")
    tiq = vfactory.add_var("tiq")
    recflag = vfactory.add_var("recflag")

    ft0 = vfactory.add_var("ft0")
    ft1 = vfactory.add_var("ft1")
    ft2 = vfactory.add_var("ft2")
    ft3 = vfactory.add_var("ft3")
    f_hz = vfactory.add_var("f_hz")

    vt0 = vfactory.add_var("vt0")
    vt1 = vfactory.add_var("vt1")
    vt2 = vfactory.add_var("vt2")
    vt3 = vfactory.add_var("vt3")

    one = vfactory.add_const(1.0)
    zero = vfactory.add_const(0.0)
    eps_v = vfactory.add_const(0.01)
    eps_i = vfactory.add_const(1e-8)

    vm_eff = sym.max(vm, eps_v)
    under_v_db = sym.heaviside(v0 - vm)
    over_v_db = sym.heaviside(vm - v1)

    q_droop_expr = dqdv * (vm - v0) * under_v_db + dqdv * (vm - v1) * over_v_db

    p_sum_expr = sym.hard_sat(pref0 + pext0, -pmx, pmx)
    q_sum_expr = sym.hard_sat(qref0 + q_droop_expr, qmn, qmx)

    ip_unlimited = p_sum_expr / vm_eff
    iq_unlimited = q_sum_expr / vm_eff

    ip_cap_q = sym.sqrt(sym.max(ialim ** 2 - iq_unlimited ** 2, eps_i))
    iq_cap_p = sym.sqrt(sym.max(ialim ** 2 - ip_unlimited ** 2, eps_i))

    ip_max_expr = pqflag * ialim + (one - pqflag) * ip_cap_q
    iq_max_expr = (one - pqflag) * ialim + pqflag * iq_cap_p

    f_low = sym.hard_sat((f_hz - ft0) / (ft1 - ft0), zero, one)
    f_high = sym.hard_sat((ft3 - f_hz) / (ft3 - ft2), zero, one)
    f_trip_expr = f_low * f_high

    v_low = sym.hard_sat((vm - vt0) / (vt1 - vt0), zero, one)
    v_high = sym.hard_sat((vt3 - vm) / (vt3 - vt2), zero, one)
    v_trip_expr = v_low * v_high

    trip_gain = one - recflag + recflag * f_trip_expr * v_trip_expr

    ip_cmd_expr = sym.hard_sat(ip_unlimited, -ip_max_expr, ip_max_expr) * trip_gain
    iq_cmd_expr = sym.hard_sat(iq_unlimited, -iq_max_expr, iq_max_expr) * trip_gain

    block = Block(
        algebraic_eqs=[
            p - vm * ipout,
            q - vm * iqout,
            q_droop - q_droop_expr,
            p_sum - p_sum_expr,
            q_sum - q_sum_expr,
            ip_max - ip_max_expr,
            iq_max - iq_max_expr,
            f_trip - f_trip_expr,
            v_trip - v_trip_expr,
            ip_cmd - ip_cmd_expr,
            iq_cmd - iq_cmd_expr,
        ],
        algebraic_vars=[p, q, q_droop, p_sum, q_sum, ip_max, iq_max, f_trip, v_trip, ip_cmd, iq_cmd],
        state_eqs=[
            (ip_cmd - ipout) / tip,
            (iq_cmd - iqout) / tiq,
        ],
        state_vars=[ipout, iqout],
        in_vars=inputs,
        init_eqs={
            pref0: p,
            qref0: q,
            pext0: zero,
            f_hz: vfactory.add_const(60.0),
            q_droop: q_droop_expr,
            p_sum: p_sum_expr,
            q_sum: q_sum_expr,
            ip_max: ip_max_expr,
            iq_max: iq_max_expr,
            f_trip: f_trip_expr,
            v_trip: v_trip_expr,
            ip_cmd: ip_cmd_expr,
            iq_cmd: iq_cmd_expr,
            ipout: ip_cmd_expr,
            iqout: iq_cmd_expr,
        },
        event_dict={
            pref0: vfactory.add_const(None),
            qref0: vfactory.add_const(None),
            pext0: vfactory.add_const(0.0),
            qmx: vfactory.add_const(1.0),
            qmn: vfactory.add_const(-1.0),
            pmx: vfactory.add_const(9.999),
            v0: vfactory.add_const(0.8),
            v1: vfactory.add_const(1.1),
            dqdv: vfactory.add_const(-1.0),
            ialim: vfactory.add_const(1.3),
            pqflag: vfactory.add_const(1.0),
            tip: vfactory.add_const(0.02),
            tiq: vfactory.add_const(0.02),
            recflag: vfactory.add_const(1.0),
            ft0: vfactory.add_const(59.5),
            ft1: vfactory.add_const(59.7),
            ft2: vfactory.add_const(60.3),
            ft3: vfactory.add_const(60.5),
            vt0: vfactory.add_const(0.88),
            vt1: vfactory.add_const(0.9),
            vt2: vfactory.add_const(1.1),
            vt3: vfactory.add_const(1.2),
            f_hz: vfactory.add_const(60.0),
        },
    )

    block.name = name
    block.external_mapping = {
        VarPowerFlowRefferenceType.Vm: vm,
        VarPowerFlowRefferenceType.Va: va,
        VarPowerFlowRefferenceType.P: p,
        VarPowerFlowRefferenceType.Q: q,
    }
    block.out_vars = [p, q, ipout, iqout, q_droop, p_sum, q_sum, f_trip, v_trip]

    templ.block = block
    return templ
