# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Module providing the EmtProblemDae class, which acts as the electrical
parser for the generic BaseProblem layer. It translates electrical components
(buses, branches, injections) into the unified DAE mathematical structure.
"""

from __future__ import annotations

import time
import numpy as np
import pandas as pd
from typing import Dict, List, Any

from VeraGridEngine.Devices import MultiCircuit
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.Utils.Symbolic.symbolic import Var, piecewise, Const
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import VarPowerFlowRefferenceType
from VeraGridEngine.basic_structures import Vec, ObjVec, BoolVec, Logger
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_results_3ph import PowerFlowResults3Ph

# Assuming BaseProblem is accessible in your generic problems folder
from VeraGridEngine.Simulations.EMT.problems.base_problem import BaseProblem


def _tic() -> float:
    """
    Returns the current performance counter time.
    """
    return time.perf_counter()


def _toc(t0: float) -> float:
    """
    Returns the elapsed time since t0.
    """
    return time.perf_counter() - t0


def set_p(p: ObjVec, p_used: BoolVec, k: int, val: object):
    """
    Accumulates real power equations for a specific node.
    """
    if not p_used[k]:
        p[k] = val
        p_used[k] = True
    else:
        p[k] += val


def set_q(q: ObjVec, q_used: BoolVec, k: int, val: object):
    """
    Accumulates reactive power equations for a specific node.
    """
    if not q_used[k]:
        q[k] = val
        q_used[k] = True
    else:
        q[k] += val


class EmtProblemDae(BaseProblem):
    """
    Electrical parser layer for the EMT DAE Problem.

    Responsibilities:
      - Traverses the MultiCircuit to extract electrical devices.
      - Constructs nodal power balances.
      - Processes external piecewise events into the unified block.
      - Maintains mapping between physical devices and symbolic variables.
      - Delegates all mathematical and indexing plumbing to BaseProblem.
    """

    def __init__(
            self,
            grid: MultiCircuit,
            options: EmtOptions,
            pf_results: PowerFlowResults3Ph | None,
    ):
        """
        Initializes the EMT Problem by parsing the grid and passing the
        resulting mathematical block to the BaseProblem constructor.
        """
        self.logger = Logger()
        self.grid = grid
        self.options = options
        self.power_flow_results = pf_results

        self._vars_info: Dict[ALL_DEV_TYPES, List[Var]] = dict()
        self._vars_glob_name2uid: Dict[str, int] = dict()
        self._vars2device: Dict[int, ALL_DEV_TYPES] = dict()
        self._temp_init_guess: Dict[int, float] = dict()

        sys_block = Block(children=[], in_vars=[])
        glob_time = Var(self.TIME_NAME)

        self.history_models = []  # list of models with history components
        self.step_counter = 0

        t_build = _tic()

        self._build_structure_and_collect(sys_block, grid, pf_results, glob_time)

        sys_block.unify_blocks()
        self._deduplicate_block_entities(sys_block)

        super().__init__(sys_block=sys_block, glob_time=glob_time)

        self.init_guess.update(self._temp_init_guess)

        t_done = _toc(t_build)

        if options.verbose > 0:
            print(
                f"EMT electrical problem parsed in {t_done:.4f}s | "
                f"vars={self._n_vars} (state={self._n_state}, alg={self._n_alg}) | "
                f"eqs(state={len(self._state_eqs)}, alg={len(self._algebraic_eqs)})"
            )

    def _build_structure_and_collect(
            self,
            sys_block: Block,
            grid: MultiCircuit,
            pf_results: PowerFlowResults3Ph | None,
            glob_time: Var
    ):
        """
        EMT (abc) assembly: nodal KCL per phase.
        - Unknowns: bus phase voltages (v_N,v_A,v_B,v_C as available)
        - Algebraic equations: KCL per bus-phase: sum(i_phase) = 0
        """

        bus_dict: Dict[Any, int] = dict()
        n_bus = len(grid.buses)

        # --- helpers ---
        ph_v_keys = [
            VarPowerFlowRefferenceType.v_N,
            VarPowerFlowRefferenceType.v_A,
            VarPowerFlowRefferenceType.v_B,
            VarPowerFlowRefferenceType.v_C,
        ]
        inj_i_keys = [
            VarPowerFlowRefferenceType.i_N,
            VarPowerFlowRefferenceType.i_A,
            VarPowerFlowRefferenceType.i_B,
            VarPowerFlowRefferenceType.i_C,
        ]

        # These MUST exist in VarPowerFlowRefferenceType for non-Bergeron branches:
        # current leaving FROM bus into the branch:
        br_if_keys = [
            VarPowerFlowRefferenceType.if_N,
            VarPowerFlowRefferenceType.if_A,
            VarPowerFlowRefferenceType.if_B,
            VarPowerFlowRefferenceType.if_C,
        ]
        # current leaving TO bus into the branch:
        br_it_keys = [
            VarPowerFlowRefferenceType.it_N,
            VarPowerFlowRefferenceType.it_A,
            VarPowerFlowRefferenceType.it_B,
            VarPowerFlowRefferenceType.it_C,
        ]

        def _apply_piecewise_events_if_any(dev, mdl: Block):
            """Apply scheduled events to ANY device that defines event_dict."""
            emt_events = getattr(grid, "emt_events", None)
            if emt_events is None:
                emt_events = getattr(grid, "rms_events", [])

            if mdl.event_dict is None or len(mdl.event_dict) == 0:
                return

            collect_events = {key: {"times": [], "values": []} for key in mdl.event_dict.keys()}
            dev_events = [evt for evt in emt_events if evt.device_idtag == dev.idtag]

            for evt in dev_events:
                if evt.parameter in collect_events:
                    collect_events[evt.parameter]["times"].append(evt.time)
                    collect_events[evt.parameter]["values"].append(evt.value)

            for param, info in collect_events.items():
                if len(info["times"]) == 0:
                    continue
                default_value = mdl.event_dict[param]
                mdl.event_dict[param] = piecewise(
                    time_var=glob_time,
                    t_events=np.array(info["times"], dtype=np.float64),
                    new_values=np.array(info["values"], dtype=np.float64),
                    default_value=default_value,
                )

        def _get_bus_v_list(bus_block: Block):
            """Return [vN,vA,vB,vC] as Vars if present else Const(0)."""
            out = []
            for k in ph_v_keys:
                vk = bus_block.E(k)
                out.append(vk if vk is not None else grid.var_factory.add_const(0.0))
            return out

        # KCL accumulator per bus-phase (symbolic)
        I_kcl = {i: [grid.var_factory.add_const(0.0) for _ in range(4)] for i in range(n_bus)}

        # Bases (for Bergeron constructor)
        h = getattr(self.options, "time_step", 1e-4)
        Sbase = getattr(grid, "Sbase", 1.0)
        fbase = getattr(grid, "fBase", 50.0)

        # -------------------------
        # 1) BUSES
        # -------------------------
        for bus_idx, bus in enumerate(grid.buses):
            bus_dict[bus] = bus_idx
            mdl = bus.emt_model.model
            mdl.unify_blocks()

            _apply_piecewise_events_if_any(bus, mdl)

            self._add_model_to_system_mappings(bus, mdl)
            sys_block.add(mdl)

            if pf_results is not None:
                self._try_set_bus_pf_init(mdl=mdl, bus_index=bus_idx, pf_results=pf_results)

        # -------------------------
        # 2) BRANCHES
        # -------------------------
        for branch_idx, br in enumerate(grid.get_branches_iter(add_vsc=True, add_hvdc=True, add_switch=True)):
            f = bus_dict[br.bus_from]
            t = bus_dict[br.bus_to]

            # --- Bergeron special-case: current injections + history params ---
            is_bergeron = (
                    getattr(br, "emt_model_type", None) is not None
                    and getattr(br.emt_model_type, "value", None) == "Bergeron"
            )

            if is_bergeron:

                line_tpl = br.emt_model.model

                # add its block (event params Ih_*)
                mdl = line_tpl.block
                mdl.unify_blocks()

                _apply_piecewise_events_if_any(br, mdl)

                self._add_model_to_system_mappings(br, mdl)
                sys_block.add(mdl)

                # store for boundary update
                self.history_models.append(line_tpl)

                # build voltage lists from bus blocks
                v_f_vars = _get_bus_v_list(br.bus_from.emt_model.model)
                v_t_vars = _get_bus_v_list(br.bus_to.emt_model.model)

                # symbolic Norton injections
                i_f_exprs, i_t_exprs = line_tpl.get_nodal_injections(v_f_vars, v_t_vars)

                for ph in range(4):
                    I_kcl[f][ph] = I_kcl[f][ph] + i_f_exprs[ph]
                    I_kcl[t][ph] = I_kcl[t][ph] + i_t_exprs[ph]

                continue

            # --- All other branches must contribute terminal currents (If_*, It_*) ---
            mdl = br.emt_model.model
            mdl.unify_blocks()

            _apply_piecewise_events_if_any(br, mdl)

            self._add_model_to_system_mappings(br, mdl)
            sys_block.add(mdl)

            # Add terminal currents into KCL
            for ph in range(4):
                If_expr = mdl.E(br_if_keys[ph])
                It_expr = mdl.E(br_it_keys[ph])

                if If_expr is not None:
                    I_kcl[f][ph] = I_kcl[f][ph] + If_expr
                if It_expr is not None:
                    I_kcl[t][ph] = I_kcl[t][ph] + It_expr

            # PF init for branch internal variables (optional, keep if meaningful)
            if pf_results is not None:
                self._try_set_branch_pf_init(
                    mdl=mdl,
                    branch_index=branch_idx,
                    pf_results=pf_results,
                    sbase=getattr(grid, "Sbase", 1.0),
                )

        # -------------------------
        # 3) INJECTIONS
        # -------------------------
        for inj in grid.get_injection_devices_iter():
            mdl = inj.emt_model.model
            mdl.unify_blocks()

            _apply_piecewise_events_if_any(inj, mdl)

            self._add_model_to_system_mappings(inj, mdl)
            sys_block.add(mdl)

            b = bus_dict[inj.bus]

            # Add injection currents into KCL
            for ph in range(4):
                i_expr = mdl.E(inj_i_keys[ph])
                if i_expr is not None:
                    I_kcl[b][ph] = I_kcl[b][ph] + i_expr

            # PF init for injection internal vars (keep)
            if pf_results is not None:
                self._try_set_inj_pf_init(
                    mdl=mdl,
                    bus_index=b,
                    pf_results=pf_results,
                    sbase=getattr(grid, "Sbase", 1.0),
                )

        # -------------------------
        # 4) FINAL: stamp KCL equations into each bus model (per existing phase)
        # -------------------------
        for bus_idx, bus in enumerate(grid.buses):
            mdl = bus.emt_model.model

            # Ensure we don't accidentally keep RMS equations in EMT
            # (you may prefer to enforce mdl.algebraic_eqs == 0 here)
            if len(mdl.algebraic_eqs) != 0:
                # If bus templates already add equations (e.g., slack constraints), keep them,
                # but still append KCL for phases that exist unless the bus already has KCL.
                pass

            has_any_phase = False
            has_any_kcl_term = False

            for ph_i, v_key in enumerate(ph_v_keys):
                if mdl.E(v_key) is None:
                    continue
                has_any_phase = True

                # stamp KCL residual for this phase
                mdl.algebraic_eqs.append(I_kcl[bus_idx][ph_i])

                # detect if KCL is non-trivial (optional diagnostics)
                has_any_kcl_term = True

            if not has_any_phase:
                self.logger.add_error("Bus has no phases (no voltage vars)", value=bus_idx)
            else:
                # If everything is zero and no devices contributed, it's isolated.
                # (You can refine detection by tracking connectivity.)
                if all(isinstance(I_kcl[bus_idx][ph], Const) and getattr(I_kcl[bus_idx][ph], "value", None) == 0.0
                       for ph in range(4)):
                    self.logger.add_error("Isolated bus (no KCL contributions)", value=bus_idx)



    def _add_model_to_system_mappings(self, elm: ALL_DEV_TYPES, mdl: Block):
        """
        Populates tracking dictionaries to maintain the relationship between
        electrical devices and their corresponding symbolic variables.
        """
        for v in mdl.state_vars:
            self.add_device_var(dev=elm, var=v)
            self._vars_glob_name2uid[v.name + elm.name] = v.uid
            self._vars2device[v.uid] = elm

        for v in mdl.algebraic_vars:
            self.add_device_var(dev=elm, var=v)
            self._vars_glob_name2uid[v.name + elm.name] = v.uid
            self._vars2device[v.uid] = elm

        for dv in mdl.diff_vars:
            self.add_device_var(dev=elm, var=dv)
            self._vars_glob_name2uid[dv.name + elm.name] = dv.uid
            self._vars2device[dv.uid] = elm

    def _try_set_bus_pf_init(self, mdl: Block, bus_index: int, pf_results: PowerFlowResults3Ph):
        """
        Attempts to initialize bus variables based on PowerFlow3ph results.
        Phasor results are transformed into instantaneous in the abc domain.

        All buses have VarPowerFlowRefferenceType.v_N, v_A, v_B, v_C in their external mapping.
        Voltages can be None if the bus hasn't that phase.
        """

        try:
            if mdl.E(VarPowerFlowRefferenceType.v_N) is not None:
                V_N_rms, V_N_angle = np.abs(pf_results.voltage_N[bus_index]), np.angle(pf_results.voltage_N[bus_index])
                v_N = np.sqrt(2) * V_N_rms * np.cos(V_N_angle)
                self.set_init_guess(mdl, VarPowerFlowRefferenceType.v_N, v_N)

            if mdl.E(VarPowerFlowRefferenceType.v_A) is not None:
                V_A_rms, V_A_angle = np.abs(pf_results.voltage_A[bus_index]), np.angle(pf_results.voltage_A[bus_index])
                v_A = np.sqrt(2) * V_A_rms * np.cos(V_A_angle)
                self.set_init_guess(mdl, VarPowerFlowRefferenceType.v_A, v_A)

            if mdl.E(VarPowerFlowRefferenceType.v_B) is not None:
                V_B_rms, V_B_angle = np.abs(pf_results.voltage_B[bus_index]), np.angle(pf_results.voltage_B[bus_index])
                v_B = np.sqrt(2) * V_B_rms * np.cos(V_B_angle)
                self.set_init_guess(mdl, VarPowerFlowRefferenceType.v_B, v_B)

            if mdl.E(VarPowerFlowRefferenceType.v_C) is not None:
                V_C_rms, V_C_angle = np.abs(pf_results.voltage_C[bus_index]), np.angle(pf_results.voltage_C[bus_index])
                v_C = np.sqrt(2) * V_C_rms * np.cos(V_C_angle)
                self.set_init_guess(mdl, VarPowerFlowRefferenceType.v_C, v_C)

        except Exception:
            pass

    def _try_set_branch_pf_init(self, mdl: Block, branch_index: int, pf_results: PowerFlowResults3Ph, sbase: float):
        """
        Attempts to initialize branch variables based on PowerFlow results.
        """

        try:
            Sf = 0.0
            St = 0.0

            if mdl.E(VarPowerFlowRefferenceType.Sf_A) is not None:
                Sf_A = pf_results.Sf_A[branch_index] / sbase
                self.set_init_guess(mdl, VarPowerFlowRefferenceType.Sf_A, float(Sf_A))
                Sf += Sf_A
            if mdl.E(VarPowerFlowRefferenceType.Sf_B) is not None:
                Sf_B = pf_results.Sf_B[branch_index] / sbase
                self.set_init_guess(mdl, VarPowerFlowRefferenceType.Sf_B, float(Sf_B))
                Sf += Sf_B
            if mdl.E(VarPowerFlowRefferenceType.Sf_C) is not None:
                Sf_C = pf_results.Sf_C[branch_index] / sbase
                self.set_init_guess(mdl, VarPowerFlowRefferenceType.Sf_C, float(Sf_C))
                Sf += Sf_C
            if mdl.E(VarPowerFlowRefferenceType.St_A) is not None:
                St_A = pf_results.St_A[branch_index] / sbase
                self.set_init_guess(mdl, VarPowerFlowRefferenceType.St_A, float(St_A))
                St += St_A
            if mdl.E(VarPowerFlowRefferenceType.St_B) is not None:
                St_B = pf_results.St_B[branch_index] / sbase
                self.set_init_guess(mdl, VarPowerFlowRefferenceType.St_B, float(St_B))
                St += St_B
            if mdl.E(VarPowerFlowRefferenceType.St_C) is not None:
                St_C = pf_results.St_C[branch_index] / sbase
                self.set_init_guess(mdl, VarPowerFlowRefferenceType.St_C, float(St_C))
                St += St_C

            Pf = np.real(Sf)
            Qf = np.imag(Sf)
            Pt = np.real(St)
            Qt = np.imag(St)

            self.set_init_guess(mdl, VarPowerFlowRefferenceType.Pf, Pf)
            self.set_init_guess(mdl, VarPowerFlowRefferenceType.Qf, Qf)
            self.set_init_guess(mdl, VarPowerFlowRefferenceType.Pt, Pt)
            self.set_init_guess(mdl, VarPowerFlowRefferenceType.Qt, Qt)

        except Exception:
            pass

    def _try_set_inj_pf_init(self, mdl: Block, bus_index: int, pf_results: PowerFlowResults3Ph, sbase: float):
        """
        Attempts to initialize injection variables based on PowerFlow results.
        Initialize any present (not-None) injection variables from PF results.
        Works per-phase and only computes each phase once if needed.
        """
        try:
            def set_if_exists(key, value):
                if mdl.E(key) is not None:
                    self.set_init_guess(mdl, key, value)

            Sbus_total = 0.0 + 0.0j

            # (phase_name, Sbus_array, V_array, i_key, P_key, Q_key)
            phase_specs = [
                ("N", pf_results.Sbus_N, pf_results.voltage_N,
                 VarPowerFlowRefferenceType.i_N, VarPowerFlowRefferenceType.P_N, VarPowerFlowRefferenceType.Q_N),

                ("A", pf_results.Sbus_A, pf_results.voltage_A,
                 VarPowerFlowRefferenceType.i_A, VarPowerFlowRefferenceType.P_A, VarPowerFlowRefferenceType.Q_A),

                ("B", pf_results.Sbus_B, pf_results.voltage_B,
                 VarPowerFlowRefferenceType.i_B, VarPowerFlowRefferenceType.P_B, VarPowerFlowRefferenceType.Q_B),

                ("C", pf_results.Sbus_C, pf_results.voltage_C,
                 VarPowerFlowRefferenceType.i_C, VarPowerFlowRefferenceType.P_C, VarPowerFlowRefferenceType.Q_C),
            ]

            for _, S_arr, V_arr, i_key, P_key, Q_key in phase_specs:

                # If this model doesn't use anything from this phase, skip it. todo: do it differently?
                if (mdl.E(i_key) is None) and (mdl.E(P_key) is None) and (mdl.E(Q_key) is None):
                    continue

                S = S_arr[bus_index] / sbase
                V = V_arr[bus_index]

                # Avoid divide-by-zero
                if V == 0:
                    I = 0.0 + 0.0j
                else:
                    I = np.conj(S / V)

                I_rms = np.abs(I)
                I_ang = np.angle(I)

                # Instantaneous init at t=0 (your convention)
                i0 = np.sqrt(2.0) * I_rms * np.cos(I_ang)

                set_if_exists(i_key, float(i0))
                set_if_exists(P_key, float(np.real(S)))
                set_if_exists(Q_key, float(np.imag(S)))

                Sbus_total += S

            # theta (only if model has it)
            if mdl.E(VarPowerFlowRefferenceType.theta) is not None:
                VA = pf_results.voltage_A[bus_index]
                VB = pf_results.voltage_B[bus_index]
                VC = pf_results.voltage_C[bus_index]

                a = np.exp(1j * 2 * np.pi / 3)
                V1 = (1 / 3) * (VA + a * VB + (a * a) * VC)
                theta = np.angle(V1)

                self.set_init_guess(mdl, VarPowerFlowRefferenceType.theta, float(theta))

            # Total P/Q only if the model has them
            set_if_exists(VarPowerFlowRefferenceType.P, float(np.real(Sbus_total)))
            set_if_exists(VarPowerFlowRefferenceType.Q, float(np.imag(Sbus_total)))

        except Exception:
            pass

        # try:
        #     Sbus = 0.0 + 0.0j
        #     if mdl.E(VarPowerFlowRefferenceType.P_N) is not None:
        #         Sbus_N = pf_results.Sbus_N[bus_index] / sbase
        #         V_N = pf_results.voltage_N[bus_index]
        #         I_N = np.conj(Sbus_N / V_N)
        #         I_N_rms, I_N_angle = np.abs(I_N), np.angle(I_N)
        #         i_N = np.sqrt(2) * I_N_rms * np.cos(I_N_angle)
        #
        #         self.set_init_guess(mdl, VarPowerFlowRefferenceType.i_N, i_N)
        #         self.set_init_guess(mdl, VarPowerFlowRefferenceType.P_N, float(np.real(Sbus_N)))
        #         self.set_init_guess(mdl, VarPowerFlowRefferenceType.Q_N, float(np.imag(Sbus_N)))
        #         Sbus += Sbus_N
        #
        #     if mdl.E(VarPowerFlowRefferenceType.P_A) is not None:
        #         Sbus_A = pf_results.Sbus_A[bus_index] / sbase
        #         V_A = pf_results.voltage_A[bus_index]
        #         I_A = np.conj(Sbus_A / V_A)
        #         I_A_rms, I_A_angle = np.abs(I_A), np.angle(I_A)
        #         i_A = np.sqrt(2) * I_A_rms * np.cos(I_A_angle)
        #
        #         self.set_init_guess(mdl, VarPowerFlowRefferenceType.i_A, i_A)
        #         self.set_init_guess(mdl, VarPowerFlowRefferenceType.P_A, float(np.real(Sbus_A)))
        #         self.set_init_guess(mdl, VarPowerFlowRefferenceType.Q_A, float(np.imag(Sbus_A)))
        #         Sbus += Sbus_A
        #
        #     if mdl.E(VarPowerFlowRefferenceType.P_B) is not None:
        #         Sbus_B = pf_results.Sbus_B[bus_index] / sbase
        #         V_B = pf_results.voltage_B[bus_index]
        #         I_B = np.conj(Sbus_B / V_B)
        #         I_B_rms, I_B_angle = np.abs(I_B), np.angle(I_B)
        #         i_B = np.sqrt(2) * I_B_rms * np.cos(I_B_angle)
        #
        #         self.set_init_guess(mdl, VarPowerFlowRefferenceType.i_B, i_B)
        #         self.set_init_guess(mdl, VarPowerFlowRefferenceType.P_B, float(np.real(Sbus_B)))
        #         self.set_init_guess(mdl, VarPowerFlowRefferenceType.Q_B, float(np.imag(Sbus_B)))
        #         Sbus += Sbus_B
        #
        #     if mdl.E(VarPowerFlowRefferenceType.P_C) is not None:
        #         Sbus_C = pf_results.Sbus_C[bus_index] / sbase
        #         V_C = pf_results.voltage_C[bus_index]
        #         I_C = np.conj(Sbus_C / V_C)
        #         I_C_rms, I_C_angle = np.abs(I_C), np.angle(I_C)
        #         i_C = np.sqrt(2) * I_C_rms * np.cos(I_C_angle)
        #
        #         self.set_init_guess(mdl, VarPowerFlowRefferenceType.i_C, i_C)
        #         self.set_init_guess(mdl, VarPowerFlowRefferenceType.P_C, float(np.real(Sbus_C)))
        #         self.set_init_guess(mdl, VarPowerFlowRefferenceType.Q_C, float(np.imag(Sbus_C)))
        #         Sbus += Sbus_C
        #
        #     if mdl.E(VarPowerFlowRefferenceType.theta) is not None:
        #         V_A = pf_results.voltage_A[bus_index]
        #         V_B = pf_results.voltage_B[bus_index]
        #         V_C = pf_results.voltage_C[bus_index]
        #
        #         # find theta from the positive sequence voltage for the synchronous generator
        #         a = np.exp(1j * 2 * np.pi / 3)
        #         V1 = (1 / 3) * (V_A + a * V_B + a * a * V_C)  # positive sequence voltage for the synchronous generator
        #         theta = np.angle(V1)
        #         self.set_init_guess(mdl, VarPowerFlowRefferenceType.theta, float(theta))
        #
        #     self.set_init_guess(mdl, VarPowerFlowRefferenceType.P, float(np.real(Sbus)))
        #     self.set_init_guess(mdl, VarPowerFlowRefferenceType.Q, float(np.imag(Sbus)))
        #
        # except Exception:
        #     pass

    def _deduplicate_block_entities(self, block: Block):
        """
        Removes duplicated symbolic objects within the block by UID
        while preserving their first appearance order.
        """

        def _unique_keep_order(seq):
            seen = set()
            out = []
            for x in seq:
                if x.uid not in seen:
                    seen.add(x.uid)
                    out.append(x)
            return out

        block.state_vars = _unique_keep_order(block.state_vars)
        block.algebraic_vars = _unique_keep_order(block.algebraic_vars)
        block.diff_vars = _unique_keep_order(block.diff_vars)

    def add_device_var(self, dev: ALL_DEV_TYPES, var: Var):
        """
        Registers a variable belonging to a specific device.
        """
        var_list = self._vars_info.get(dev, None)
        if var_list is None:
            self._vars_info[dev] = [var]
        else:
            var_list.append(var)

    def set_init_guess(self, mdl: Block, reference_powerflow: VarPowerFlowRefferenceType, val: float):
        """
        Sets the temporary initial guess for a given variable during the parsing phase.
        """
        if not hasattr(mdl, "external_mapping") or mdl.external_mapping is None:
            return
        if reference_powerflow in mdl.external_mapping:
            var = mdl.external_mapping[reference_powerflow]
            self._temp_init_guess[var.uid] = float(val)

    def get_init_guess_info(self) -> pd.DataFrame:
        """
        Returns a DataFrame containing all initialized guesses for variables.
        """
        rows = []
        all_vars = {v.uid: v for v in (self._state_vars + self._algebraic_vars)}
        for uid, value in self.init_guess.items():
            if uid in all_vars:
                rows.append((uid, all_vars[uid].name, value))
        return pd.DataFrame(rows, columns=["uid", "var_name", "value"])

    def get_device_vars_dict(self) -> Dict[ALL_DEV_TYPES, List[Var]]:
        """
        Returns the dictionary mapping electrical devices to their variables.
        """
        return self._vars_info

    @property
    def vars_glob_name2uid(self) -> Dict[str, int]:
        """
        Returns the dictionary mapping global variable names to UIDs.
        """
        return self._vars_glob_name2uid