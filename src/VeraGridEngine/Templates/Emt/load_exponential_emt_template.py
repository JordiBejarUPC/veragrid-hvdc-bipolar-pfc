# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""EMT exponential load template."""

from typing import Dict

import numpy as np

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic.symbolic import Expr, Var
from VeraGridEngine.enumerations import DeviceType, ParamPowerFlowRefferenceType, VarPowerFlowRefferenceType


def get_exponential_load_3ph_emt(vf: VarFactory, name: str = "exp_Load_EMT_3ph") -> EmtModelTemplate:
    """
    Build the three-phase EMT exponential load template.

    The template uses the same EMT current-injection convention as the ZIP load:
    positive ``Pl0`` and ``Ql0`` values in the API object represent power
    consumption, while the injected bus powers and currents are negative.

    P(V) = P0 * (V / V0)^a
    Q(V) = Q0 * (V / V0)^b

    Typical interpretation:
    constant power load: a = 0, b = 0
    constant current-like load: a = 1, b = 1
    constant impedance-like load: a = 2, b = 2
    Physical Interpretation

    If voltage drops and a > 0, active power decreases.
    If voltage drops and b > 0, reactive power decreases.
    If a = b = 2, the load behaves like an impedance.
    If a = b = 0, the load tries to keep power constant, which requires higher current during voltage dips.

    :param vf: EMT variable factory.
    :param name: Symbolic block name.
    :return: Configured EMT model template.
    """
    templ: EmtModelTemplate = EmtModelTemplate()
    templ.tpe = DeviceType.LoadDevice
    templ.name = name
    templ.block.name = name

    c2: Expr = vf.add_const(2.0)
    c05: Expr = vf.add_const(0.5)

    # The EMT network provides instantaneous abc voltages at the device terminal.
    v_a: Var = vf.add_var(name=f"v_A_{name}", reference=VarPowerFlowRefferenceType.v_A)
    v_b: Var = vf.add_var(name=f"v_B_{name}", reference=VarPowerFlowRefferenceType.v_B)
    v_c: Var = vf.add_var(name=f"v_C_{name}", reference=VarPowerFlowRefferenceType.v_C)
    templ.block.in_vars = [v_a, v_b, v_c]

    # The terminal voltage derivatives are runtime parameters injected from the PF
    # projection. They are needed to seed the SOGI quadrature states explicitly.
    d_v_a: Var = vf.add_var(name=f"d_v_A_{name}")
    d_v_b: Var = vf.add_var(name=f"d_v_B_{name}")
    d_v_c: Var = vf.add_var(name=f"d_v_C_{name}")

    p0_a: Var = vf.add_var(f"P0_A_{name}")
    q0_a: Var = vf.add_var(f"Q0_A_{name}")
    p0_b: Var = vf.add_var(f"P0_B_{name}")
    q0_b: Var = vf.add_var(f"Q0_B_{name}")
    p0_c: Var = vf.add_var(f"P0_C_{name}")
    q0_c: Var = vf.add_var(f"Q0_C_{name}")
    v0: Var = vf.add_var(f"V0_{name}")
    alpha_p: Var = vf.add_var(f"a_{name}")
    alpha_q: Var = vf.add_var(f"b_{name}")
    k_sogi: Var = vf.add_var(f"k_sogi_{name}")
    eps: Var = vf.add_var(f"eps_{name}")
    omega: Var = vf.add_var(f"omega_{name}")

    # Event parameters remain runtime-accessible so the template can be perturbed by
    # EMT events without changing the symbolic structure.
    templ.block.event_dict[p0_a] = vf.add_const(0.1 / 3.0)
    templ.block.event_dict[q0_a] = vf.add_const(0.01 / 3.0)
    templ.block.event_dict[p0_b] = vf.add_const(0.1 / 3.0)
    templ.block.event_dict[q0_b] = vf.add_const(0.01 / 3.0)
    templ.block.event_dict[p0_c] = vf.add_const(0.1 / 3.0)
    templ.block.event_dict[q0_c] = vf.add_const(0.01 / 3.0)
    templ.block.event_dict[v0] = vf.add_const(np.sqrt(2.0))
    templ.block.event_dict[alpha_p] = vf.add_const(2.0)
    templ.block.event_dict[alpha_q] = vf.add_const(2.0)
    templ.block.event_dict[k_sogi] = vf.add_const(np.sqrt(2.0))
    templ.block.event_dict[eps] = vf.add_const(1e-12)
    templ.block.event_dict[omega] = vf.add_const(2.0 * np.pi * 50.0)
    templ.block.event_dict[d_v_a] = vf.add_const(None)
    templ.block.event_dict[d_v_b] = vf.add_const(None)
    templ.block.event_dict[d_v_c] = vf.add_const(None)

    # The SOGI states reconstruct a filtered in-phase and quadrature voltage pair.
    u_a: Var = vf.add_var(f"u_A_{name}")
    q_a: Var = vf.add_var(f"q_A_{name}")
    u_b: Var = vf.add_var(f"u_B_{name}")
    q_b: Var = vf.add_var(f"q_B_{name}")
    u_c: Var = vf.add_var(f"u_C_{name}")
    q_c: Var = vf.add_var(f"q_C_{name}")
    d_u_a: Var = vf.add_diff_var(f"d_u_A_{name}", base_var=u_a)
    d_q_a: Var = vf.add_diff_var(f"d_q_A_{name}", base_var=q_a)
    d_u_b: Var = vf.add_diff_var(f"d_u_B_{name}", base_var=u_b)
    d_q_b: Var = vf.add_diff_var(f"d_q_B_{name}", base_var=q_b)
    d_u_c: Var = vf.add_diff_var(f"d_u_C_{name}", base_var=u_c)
    d_q_c: Var = vf.add_diff_var(f"d_q_C_{name}", base_var=q_c)

    templ.block.state_vars = [u_a, q_a, u_b, q_b, u_c, q_c]
    templ.block.diff_vars = [d_u_a, d_q_a, d_u_b, d_q_b, d_u_c, d_q_c]

    # The solver owns the derivative variables, so state equations provide only the
    # right-hand side evaluated from the current terminal voltage snapshot.
    templ.block.state_eqs = [
        k_sogi * omega * (v_a - u_a) - omega * q_a,
        omega * u_a,
        k_sogi * omega * (v_b - u_b) - omega * q_b,
        omega * u_b,
        k_sogi * omega * (v_c - u_c) - omega * q_c,
        omega * u_c,
    ]

    # These algebraic variables keep every intermediate available for explicit
    # initialization and for post-processing in diagnostics and plots.
    va2: Var = vf.add_var(f"VA2_{name}")
    vb2: Var = vf.add_var(f"VB2_{name}")
    vc2: Var = vf.add_var(f"VC2_{name}")
    vm_a: Var = vf.add_var(f"VmA_{name}")
    vm_b: Var = vf.add_var(f"VmB_{name}")
    vm_c: Var = vf.add_var(f"VmC_{name}")
    r_a: Var = vf.add_var(f"rA_{name}")
    r_b: Var = vf.add_var(f"rB_{name}")
    r_c: Var = vf.add_var(f"rC_{name}")
    p_a: Var = vf.add_var(f"P_A_{name}")
    q_load_a: Var = vf.add_var(f"Q_A_{name}")
    p_b: Var = vf.add_var(f"P_B_{name}")
    q_load_b: Var = vf.add_var(f"Q_B_{name}")
    p_c: Var = vf.add_var(f"P_C_{name}")
    q_load_c: Var = vf.add_var(f"Q_C_{name}")
    i_a: Var = vf.add_var(f"i_A_{name}")
    i_b: Var = vf.add_var(f"i_B_{name}")
    i_c: Var = vf.add_var(f"i_C_{name}")

    templ.block.algebraic_vars = [
        va2, vb2, vc2,
        vm_a, vm_b, vm_c,
        r_a, r_b, r_c,
        p_a, q_load_a, p_b, q_load_b, p_c, q_load_c,
        i_a, i_b, i_c,
    ]

    templ.block.algebraic_eqs = [
        va2 - (u_a * u_a + q_a * q_a),
        vb2 - (u_b * u_b + q_b * q_b),
        vc2 - (u_c * u_c + q_c * q_c),
        vm_a - ((va2 + eps) ** c05),
        vm_b - ((vb2 + eps) ** c05),
        vm_c - ((vc2 + eps) ** c05),
        r_a - (vm_a / v0),
        r_b - (vm_b / v0),
        r_c - (vm_c / v0),
        p_a + (p0_a * (r_a ** alpha_p)),
        q_load_a + (q0_a * (r_a ** alpha_q)),
        p_b + (p0_b * (r_b ** alpha_p)),
        q_load_b + (q0_b * (r_b ** alpha_q)),
        p_c + (p0_c * (r_c ** alpha_p)),
        q_load_c + (q0_c * (r_c ** alpha_q)),
        i_a - (c2 * (u_a * p_a + q_a * q_load_a) / (va2 + eps)),
        i_b - (c2 * (u_b * p_b + q_b * q_load_b) / (vb2 + eps)),
        i_c - (c2 * (u_c * p_c + q_c * q_load_c) / (vc2 + eps)),
    ]

    init_eqs: Dict[Var, Expr] = dict()

    # The SOGI is seeded from the instantaneous bus voltage and its derivative so the
    # explicit initialization produces the steady sinusoidal operating point directly.
    init_eqs[u_a] = v_a
    init_eqs[u_b] = v_b
    init_eqs[u_c] = v_c
    init_eqs[q_a] = -d_v_a / omega
    init_eqs[q_b] = -d_v_b / omega
    init_eqs[q_c] = -d_v_c / omega

    # These algebraic seeds make explicit initialization complete, so the reduced
    # initialization workflow is not required just to evaluate the load template.
    init_eqs[va2] = u_a * u_a + q_a * q_a
    init_eqs[vb2] = u_b * u_b + q_b * q_b
    init_eqs[vc2] = u_c * u_c + q_c * q_c
    init_eqs[vm_a] = (va2 + eps) ** c05
    init_eqs[vm_b] = (vb2 + eps) ** c05
    init_eqs[vm_c] = (vc2 + eps) ** c05
    init_eqs[r_a] = vm_a / v0
    init_eqs[r_b] = vm_b / v0
    init_eqs[r_c] = vm_c / v0
    init_eqs[p_a] = -(p0_a * (r_a ** alpha_p))
    init_eqs[q_load_a] = -(q0_a * (r_a ** alpha_q))
    init_eqs[p_b] = -(p0_b * (r_b ** alpha_p))
    init_eqs[q_load_b] = -(q0_b * (r_b ** alpha_q))
    init_eqs[p_c] = -(p0_c * (r_c ** alpha_p))
    init_eqs[q_load_c] = -(q0_c * (r_c ** alpha_q))
    init_eqs[i_a] = c2 * (u_a * p_a + q_a * q_load_a) / (va2 + eps)
    init_eqs[i_b] = c2 * (u_b * p_b + q_b * q_load_b) / (vb2 + eps)
    init_eqs[i_c] = c2 * (u_c * p_c + q_c * q_load_c) / (vc2 + eps)
    templ.block.init_eqs = init_eqs

    diff_init_eqs: Dict[Var, Expr] = dict()

    # Differential seeds must match the state equations at the operating point so the
    # solver starts from a consistent EMT derivative vector.
    diff_init_eqs[d_u_a] = d_v_a
    diff_init_eqs[d_q_a] = omega * u_a
    diff_init_eqs[d_u_b] = d_v_b
    diff_init_eqs[d_q_b] = omega * u_b
    diff_init_eqs[d_u_c] = d_v_c
    diff_init_eqs[d_q_c] = omega * u_c
    templ.block.diff_init_eqs = diff_init_eqs

    templ.block.external_mapping = {
        VarPowerFlowRefferenceType.v_N: None,
        VarPowerFlowRefferenceType.v_A: v_a,
        VarPowerFlowRefferenceType.v_B: v_b,
        VarPowerFlowRefferenceType.v_C: v_c,
        VarPowerFlowRefferenceType.P: None,
        VarPowerFlowRefferenceType.Q: None,
        VarPowerFlowRefferenceType.P_N: None,
        VarPowerFlowRefferenceType.Q_N: None,
        VarPowerFlowRefferenceType.P_A: p_a,
        VarPowerFlowRefferenceType.Q_A: q_load_a,
        VarPowerFlowRefferenceType.P_B: p_b,
        VarPowerFlowRefferenceType.Q_B: q_load_b,
        VarPowerFlowRefferenceType.P_C: p_c,
        VarPowerFlowRefferenceType.Q_C: q_load_c,
        VarPowerFlowRefferenceType.i_N: None,
        VarPowerFlowRefferenceType.i_A: i_a,
        VarPowerFlowRefferenceType.i_B: i_b,
        VarPowerFlowRefferenceType.i_C: i_c,
        VarPowerFlowRefferenceType.phi_v: None,
        VarPowerFlowRefferenceType.phi: None,
        VarPowerFlowRefferenceType.Vpk: None,
        VarPowerFlowRefferenceType.Ipk: None,
        VarPowerFlowRefferenceType.d_v_N: None,
        VarPowerFlowRefferenceType.d_v_A: d_v_a,
        VarPowerFlowRefferenceType.d_v_B: d_v_b,
        VarPowerFlowRefferenceType.d_v_C: d_v_c,
    }

    templ.block.api_obj_mapping = {
        ParamPowerFlowRefferenceType.omega_base: omega,
        ParamPowerFlowRefferenceType.Pl0_A: p0_a,
        ParamPowerFlowRefferenceType.Ql0_A: q0_a,
        ParamPowerFlowRefferenceType.Pl0_B: p0_b,
        ParamPowerFlowRefferenceType.Ql0_B: q0_b,
        ParamPowerFlowRefferenceType.Pl0_C: p0_c,
        ParamPowerFlowRefferenceType.Ql0_C: q0_c,
    }

    return templ
