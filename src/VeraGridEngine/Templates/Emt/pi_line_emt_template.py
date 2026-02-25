# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np

from typing import Dict
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType, VarPowerFlowRefferenceType
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Utils.Symbolic.block import Var

class PiLineEmtTemplate(EmtModelTemplate):
    """
    Continuous-time PI line model in abc (matrix-coupled), no internal discretization.

    Inputs (in_vars) - ONLY active phases:
      vf_{ph}_{line.name}, vt_{ph}_{line.name}  (instantaneous terminal voltages in pu)

    States (active dimension m):
      i_ser[k]   series current
      q_f[k]     shunt charge at from end
      q_t[k]     shunt charge at to end

    Diff vars:
      di_ser[k], dq_f[k], dq_t[k]

    Algebraic vars:
      i_cap_f[k], i_cap_t[k]  capacitor currents
      If[k], It[k]            terminal currents (to stamp KCL)

    DAEs (active subspace):
      (1) L di_ser + R i_ser = vf - vt
      (2) dq_f = i_cap_f
      (3) dq_t = i_cap_t
      (4) q_f = C_end vf
      (5) q_t = C_end vt
      (6) If = i_ser + G_end vf + i_cap_f
      (7) It = -i_ser + G_end vt + i_cap_t
    """

    def __init__(self,
                 vf:VarFactory,
                 line: Line,
                 sbase: float,
                 fbase: float,
                 name: str = ""):
        super().__init__(name=name or f"emt_pi_{line.name}")
        self.tpe = DeviceType.LineDevice
        self.name = name

        c0 = vf.add_const(0.0)

        # -----------------------------
        # 0) Phase mask from the line itself [N,A,B,C]
        # -----------------------------
        ph_mask = np.array([
            bool(line.ys.phN),
            bool(line.ys.phA),
            bool(line.ys.phB),
            bool(line.ys.phC),
        ], dtype=bool)

        ph_labels = ["N", "A", "B", "C"]
        idx = np.where(ph_mask)[0]              # indices in [0..3]
        active_ph = [ph_labels[i] for i in idx] # names in canonical order
        m = len(active_ph)

        if m == 0:
            raise ValueError(f"PI line '{line.name}' has no enabled phases in line.ys")

        # -----------------------------
        # 1) Create ONLY active terminal voltage input vars
        #    (Connection to buses is done by the assembler, not here.)
        # -----------------------------
        vf_vars = [vf.add_var(f"vf_{ph}_{line.name}") for ph in active_ph]
        vt_vars = [vf.add_var(f"vt_{ph}_{line.name}") for ph in active_ph]

        # These are the "active" voltage vectors
        vf_act = vf_vars
        vt_act = vt_vars

        # -----------------------------
        # 2) Compute continuous parameters in pu (R, L, G_end, C_end) in ACTIVE subspace
        # -----------------------------
        w0 = 2.0 * np.pi * float(fbase)

        Vbase = line.bus_from.Vnom * 1e3
        S = float(sbase) * 1e6
        Zbase = (Vbase * Vbase) / S
        Ybase = 1.0 / Zbase

        # per-meter matrices (assumed in ohm/km and S/km -> /1e3 to per meter)
        Z_phys_m = line.template.z_nabc / 1e3
        Y_phys_m = line.template.y_nabc / 1e3

        # lumped over length
        Z_phys = Z_phys_m * line.length
        Y_phys = Y_phys_m * line.length

        # pu
        Z_pu = Z_phys / Zbase
        Y_pu = Y_phys / Ybase

        R_full = np.real(Z_pu)
        X_full = np.imag(Z_pu)
        L_full = X_full / (w0 + 1e-20)      # X = wL  => L = X/w

        Gsh_full = np.real(Y_pu)
        Bsh_full = np.imag(Y_pu)
        C_full = Bsh_full / (w0 + 1e-20)    # B = wC  => C = B/w

        # split shunt into two ends
        G_end_full = 0.5 * Gsh_full
        C_end_full = 0.5 * C_full

        # reduce to active subspace using idx
        R = R_full[np.ix_(idx, idx)]
        L = L_full[np.ix_(idx, idx)]
        G_end = G_end_full[np.ix_(idx, idx)]
        C_end = C_end_full[np.ix_(idx, idx)]

        # -----------------------------
        # 3) Create model vars (ACTIVE dimension only)
        # -----------------------------
        # States
        i_ser = [vf.add_var(f"i_ser_{line.name}_{k}") for k in range(m)]
        q_f   = [vf.add_var(f"q_f_{line.name}_{k}")   for k in range(m)]
        q_t   = [vf.add_var(f"q_t_{line.name}_{k}")   for k in range(m)]

        # Diff vars (aligned with state_vars)
        di_ser = [vf.add_var(f"di_ser_{line.name}_{k}") for k in range(m)]
        dq_f   = [vf.add_var(f"dq_f_{line.name}_{k}")   for k in range(m)]
        dq_t   = [vf.add_var(f"dq_t_{line.name}_{k}")   for k in range(m)]

        # Algebraic vars
        i_cap_f = [vf.add_var(f"i_cap_f_{line.name}_{k}") for k in range(m)]
        i_cap_t = [vf.add_var(f"i_cap_t_{line.name}_{k}") for k in range(m)]
        If_act  = [vf.add_var(f"If_{line.name}_{k}")      for k in range(m)]
        It_act  = [vf.add_var(f"It_{line.name}_{k}")      for k in range(m)]

        # -----------------------------
        # 4) Build block
        # -----------------------------
        self._block = Block(name=f"PiLine_{line.name}")

        # inputs: only active phases
        self._block.in_vars = vf_vars + vt_vars

        # declare vars
        self._block.state_vars = i_ser + q_f + q_t
        self._block.diff_vars = di_ser + dq_f + dq_t
        self._block.algebraic_vars = i_cap_f + i_cap_t + If_act + It_act

        # -----------------------------
        # 5) State equations
        # -----------------------------
        state_eqs = []

        # (1) L di_ser + R i_ser - (vf - vt) = 0
        for a in range(m):
            expr = c0
            for b in range(m):
                Lab = float(L[a, b])
                Rab = float(R[a, b])
                if Lab != 0.0:
                    expr = expr + Lab * di_ser[b]
                if Rab != 0.0:
                    expr = expr + Rab * i_ser[b]
            expr = expr - (vf_act[a] - vt_act[a])
            state_eqs.append(expr)

        # (2) dq_f - i_cap_f = 0
        for a in range(m):
            state_eqs.append(dq_f[a] - i_cap_f[a])

        # (3) dq_t - i_cap_t = 0
        for a in range(m):
            state_eqs.append(dq_t[a] - i_cap_t[a])

        self._block.state_eqs = state_eqs

        # -----------------------------
        # 6) Algebraic equations
        # -----------------------------
        alg_eqs = []

        # (4) q_f - C_end * vf = 0
        for a in range(m):
            rhs = c0
            for b in range(m):
                Cab = float(C_end[a, b])
                if Cab != 0.0:
                    rhs = rhs + Cab * vf_act[b]
            alg_eqs.append(q_f[a] - rhs)

        # (5) q_t - C_end * vt = 0
        for a in range(m):
            rhs = c0
            for b in range(m):
                Cab = float(C_end[a, b])
                if Cab != 0.0:
                    rhs = rhs + Cab * vt_act[b]
            alg_eqs.append(q_t[a] - rhs)

        # (6) If - (i_ser + G_end*vf + i_cap_f) = 0
        for a in range(m):
            gv = c0
            for b in range(m):
                Gab = float(G_end[a, b])
                if Gab != 0.0:
                    gv = gv + Gab * vf_act[b]
            alg_eqs.append(If_act[a] - (i_ser[a] + gv + i_cap_f[a]))

        # (7) It - (-i_ser + G_end*vt + i_cap_t) = 0
        for a in range(m):
            gv = c0
            for b in range(m):
                Gab = float(G_end[a, b])
                if Gab != 0.0:
                    gv = gv + Gab * vt_act[b]
            alg_eqs.append(It_act[a] - (-i_ser[a] + gv + i_cap_t[a]))

        self._block.algebraic_eqs = alg_eqs

        # outputs (optional)
        self._block.out_vars = If_act + It_act

        # -----------------------------
        # 7) external mapping for KCL stamping in EmtProblemDae
        # -----------------------------
        If_keys = {
            "N": VarPowerFlowRefferenceType.if_N,
            "A": VarPowerFlowRefferenceType.if_A,
            "B": VarPowerFlowRefferenceType.if_B,
            "C": VarPowerFlowRefferenceType.if_C,
        }
        It_keys = {
            "N": VarPowerFlowRefferenceType.it_N,
            "A": VarPowerFlowRefferenceType.it_A,
            "B": VarPowerFlowRefferenceType.it_B,
            "C": VarPowerFlowRefferenceType.it_C,
        }

        # Start with all phases present as None
        mapping: Dict[VarPowerFlowRefferenceType, Var|None] = {
            If_keys["N"]: None, If_keys["A"]: None, If_keys["B"]: None, If_keys["C"]: None,
            It_keys["N"]: None, It_keys["A"]: None, It_keys["B"]: None, It_keys["C"]: None,
        }

        # Fill only active phases
        for k, ph in enumerate(active_ph):
            mapping[If_keys[ph]] = If_act[k]
            mapping[It_keys[ph]] = It_act[k]

        self._block.external_mapping = mapping

def get_pi_line_emt_template(grid: MultiCircuit,
                             line: Line,
                             name: str = "") -> EmtModelTemplate:

    templ = PiLineEmtTemplate(vf = grid.var_factory,
                              line= line,
                              sbase = grid.Sbase,
                              fbase = grid.fBase,
                              name = name)

    return templ
