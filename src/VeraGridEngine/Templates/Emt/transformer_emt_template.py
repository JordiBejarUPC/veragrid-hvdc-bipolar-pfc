# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can see it at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0



from typing import Dict, Any
import numpy as np

from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.enumerations import DeviceType, VarPowerFlowRefferenceType
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Branches.transformer import Transformer2W
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Var, Expr

"""
EMT Transformer template.

Models a two-winding transformer as a series RL branch with an ideal transformer
ratio. The model includes:
- Series resistance (R) and inductance (L) referred to the primary side
- Magnetizing branch (optional): represented as Gm (iron losses) and Bm (magnetizing susceptance)
- Ideal transformer turns ratio: n = V1/V2

For a simple transformer model, we use:
- Lumped parameters referred to the "from" bus side
- Magnetizing branch neglected (Gm = Bm = 0) for simplicity
"""

def get_transformer_emt_template(
    grid: MultiCircuit,
    trafo: Transformer2W,
    name: str = "transformer_emt_template"
) -> EmtModelTemplate:
    """
    Build an EMT transformer model.

    The transformer is modeled as:
    - Series RL branch between from and to terminals
    - Magnetizing branch (Gm, Bm) at the from terminal
    - Ideal transformer ratio n

    Args:
        grid: Multicircuit
        trafo: Transformer2W device
        name: Name for the model

    Returns:
        EmtModelTemplate with the transformer block
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.TransformerTypeDevice
    templ.name = name

    vf: VarFactory = grid.emt_var_factory
    fbase: float = grid.fBase

    c0 = vf.add_const(0.0)

    # ============================================================
    # Parameters from the transformer device
    # ============================================================
    R = trafo.R  # p.u.
    X = trafo.X  # p.u.
    L = X / (2.0 * np.pi * float(fbase))  # H (converted from p.u.)
    G = trafo.G  # p.u. (magnetizing conductance)
    B = trafo.B  # p.u. (magnetizing susceptance)

    # Ideal transformer turns ratio
    n = trafo.tap_module if trafo.tap_module != 0.0 else 1.0

    # ============================================================
    # Terminal voltage inputs (from bus and to bus)
    # ============================================================
    v_A_f = vf.add_var(name=f"vf_A_{name}", ref=VarPowerFlowRefferenceType.v_A_f)
    v_B_f = vf.add_var(name=f"vf_B_{name}", ref=VarPowerFlowRefferenceType.v_B_f)
    v_C_f = vf.add_var(name=f"vf_C_{name}", ref=VarPowerFlowRefferenceType.v_C_f)

    v_A_t = vf.add_var(name=f"vt_A_{name}", ref=VarPowerFlowRefferenceType.v_A_t)
    v_B_t = vf.add_var(name=f"vt_B_{name}", ref=VarPowerFlowRefferenceType.v_B_t)
    v_C_t = vf.add_var(name=f"vt_C_{name}", ref=VarPowerFlowRefferenceType.v_C_t)

    vf_vars = [v_A_f, v_B_f, v_C_f]
    vt_vars = [v_A_t, v_B_t, v_C_t]

    # ============================================================
    # State variables: series currents (one per phase)
    # ============================================================
    i_ser_A = vf.add_var(name=f"i_ser_A_{name}")
    i_ser_B = vf.add_var(name=f"i_ser_B_{name}")
    i_ser_C = vf.add_var(name=f"i_ser_C_{name}")
    i_ser = [i_ser_A, i_ser_B, i_ser_C]

    # Differential variables for series currents
    di_ser_A = vf.add_diff_var(name=f"di_ser_A_{name}", base_var=i_ser_A)
    di_ser_B = vf.add_diff_var(name=f"di_ser_B_{name}", base_var=i_ser_B)
    di_ser_C = vf.add_diff_var(name=f"di_ser_C_{name}", base_var=i_ser_C)
    di_ser = [di_ser_A, di_ser_B, di_ser_C]

    # ============================================================
    # Algebraic variables: terminal currents
    # ============================================================
    if_A = vf.add_var(name=f"if_{name}_A")
    if_B = vf.add_var(name=f"if_{name}_B")
    if_C = vf.add_var(name=f"if_{name}_C")
    if_act = [if_A, if_B, if_C]

    it_A = vf.add_var(name=f"it_{name}_A")
    it_B = vf.add_var(name=f"it_{name}_B")
    it_C = vf.add_var(name=f"it_{name}_C")
    it_act = [it_A, it_B, it_C]

    # ============================================================
    # Build block structure
    # ============================================================
    templ.block.in_vars = vf_vars + vt_vars
    templ.block.state_vars = i_ser
    templ.block.diff_vars = di_ser
    templ.block.algebraic_vars = if_act + it_act

    # ============================================================
    # State equations: L * di_ser/dt + R * i_ser = (vf - n*vt)
    # ============================================================
    state_eqs = []
    for k in range(3):
        # Voltage drop across series impedance: R*i_ser + L*di_ser/dt
        # At the from side: vf = n*vt + R*i_ser + L*di_ser/dt
        # At the to side: n*vt = vf - R*i_ser - L*di_ser/dt
        # For transformer: di_ser/dt = (vf - n*vt - R*i_ser) / L
        state_eqs.append((vf_vars[k] - n * vt_vars[k] - R * i_ser[k]) / L)
    templ.block.state_eqs = state_eqs

    # ============================================================
    # Algebraic equations: KCL at each terminal
    # ============================================================
    alg_eqs = []

    # From side: if = i_ser + G*vf (magnetizing current)
    for k in range(3):
        alg_eqs.append(if_act[k] - (i_ser[k] + G * vf_vars[k]))

    # To side: it = -i_ser + G*n*vf_t (magnetizing current at to side)
    for k in range(3):
        alg_eqs.append(it_act[k] - (-i_ser[k] + G * n * vt_vars[k]))

    templ.block.algebraic_eqs = alg_eqs

    # ============================================================
    # Output variables
    # ============================================================
    templ.block.out_vars = if_act + it_act

    # ============================================================
    # External mapping for KCL stamping in EmtProblemDae
    # ============================================================
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
    sf_keys = {
        "A": VarPowerFlowRefferenceType.Sf_A,
        "B": VarPowerFlowRefferenceType.Sf_B,
        "C": VarPowerFlowRefferenceType.Sf_C,
    }
    st_keys = {
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

    mapping: Dict[VarPowerFlowRefferenceType, Var | None] = {
        if_keys["N"]: None, if_keys["A"]: if_A, if_keys["B"]: if_B, if_keys["C"]: if_C,
        it_keys["N"]: None, it_keys["A"]: it_A, it_keys["B"]: it_B, it_keys["C"]: it_C,
        sf_keys["A"]: None, sf_keys["B"]: None, sf_keys["C"]: None,
        st_keys["A"]: None, st_keys["B"]: None, st_keys["C"]: None,
        d_vf_keys["N"]: None, d_vf_keys["A"]: None, d_vf_keys["B"]: None, d_vf_keys["C"]: None,
        d_vt_keys["N"]: None, d_vt_keys["A"]: None, d_vt_keys["B"]: None, d_vt_keys["C"]: None,
    }

    templ.block.external_mapping = mapping

    # ============================================================
    # Initialization equations
    # ============================================================
    init_eqs: Dict[Var, Expr] = {}

    # Initialize series currents to zero
    init_eqs[i_ser_A] = if_A
    init_eqs[i_ser_B] = if_B
    init_eqs[i_ser_C] = if_C

    templ.block.init_eqs = init_eqs

    # ============================================================
    # Derivative initialization
    # ============================================================
    diff_init_eqs: Dict[Var, Expr] = {}

    # Initialize di_ser from steady-state: di_ser/dt = (vf - n*vt - R*i_ser) / L
    for k in range(3):
        diff_init_eqs[di_ser[k]] = (vf_vars[k] - n * vt_vars[k] - R * i_ser[k]) / L

    templ.block.diff_init_eqs = diff_init_eqs

    return templ
