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
import scipy.sparse as sp
import scipy.sparse.linalg as spla
import numpy.linalg as la
from typing import Dict, List, Any, Set

from VeraGridEngine.Devices import MultiCircuit
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.Utils.Symbolic.symbolic import Var, piecewise
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import VarPowerFlowRefferenceType
from VeraGridEngine.basic_structures import ObjVec, BoolVec, Logger
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Templates.Emt.bergeron_line_emt_template import BergeronHistoryRuntime
from VeraGridEngine.Simulations.PowerFlow.power_flow_results_3ph import PowerFlowResults3Ph
from VeraGridEngine.Simulations.EMT.initialization_emt import init_explicit_emt

from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate


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


class EmtProblemDae(EmtProblemTemplate):
    """
    Electrical parser layer for the EMT DAE Problem.

    Responsibilities:
      - Traverses the MultiCircuit to extract electrical devices.
      - Constructs nodal KCL balances per phase.
      - Processes external piecewise events into the unified block.
      - Maintains mapping between physical devices and symbolic variables.
      - Delegates all mathematical and indexing plumbing to BaseProblem.
      - Initializes PF-based guesses AND evaluates mdl.init_eqs explicitly (Explicit init).
    """

    def __init__(self,
                 grid: MultiCircuit,
                 options: EmtOptions,
                 pf_results: PowerFlowResults3Ph | None):
        """
        Initializes the EMT Problem by parsing the grid and passing the
        resulting mathematical block to the BaseProblem constructor.
        :param grid:
        :param options:
        :param pf_results:
        """
        self.logger = Logger()
        self.grid = grid
        self.options = options
        self.power_flow_results = pf_results

        self._vars_info: Dict[ALL_DEV_TYPES, List[Var]] = dict()
        self._vars_glob_name2uid: Dict[str, int] = dict()
        self._vars2device: Dict[int, ALL_DEV_TYPES] = dict()
        self._temp_init_guess: Dict[int, float] = dict()

        # for init_explicit
        self._models_with_init_eqs: List[Block] = []
        self._models_with_diff_init_eqs: List[Block] = []

        sys_block = Block(children=[], in_vars=[])
        glob_time = Var(self.TIME_NAME)

        self.history_models = []
        self.step_counter = 0

        t_build = _tic()

        # build on local sys_block
        self._build_structure_and_collect(sys_block, grid, pf_results, glob_time)

        sys_block.unify_blocks()
        self._deduplicate_block_entities(sys_block)



        # initialize template with the complete block
        super().__init__(sys_block=sys_block, glob_time=glob_time)

        # 1) PF guesses
        self.init_guess.update(self._temp_init_guess)

        # 2) explicit init guesses initialization
        self._run_explicit_initialization()
        # self.diff_init_guess.update(self.diff_init_guess)


        t_done = _toc(t_build)

        if getattr(options, "verbose", 0) > 0:
            print(
                f"EMT electrical problem parsed in {t_done:.4f}s | "
                f"vars={self._n_vars} (state={self._n_state}, alg={self._n_alg}) | "
                f"eqs(state={len(self._state_eqs)}, alg={len(self._algebraic_eqs)})"
            )

    # ---------------------------------------------------------------------
    # NEW: init_eqs registration + explicit init execution
    # ---------------------------------------------------------------------
    def _register_init_model(self, mdl: Block):
        """
        Register a block for explicit initialization if it defines init_eqs.
        """
        try:
            init_eqs = getattr(mdl, "init_eqs", None)
            models_with_init_eqs_seen: Set[int] = set()
            if init_eqs is None or len(init_eqs) == 0:
                return
            mid = id(mdl)
            if mid in models_with_init_eqs_seen:
                return
            models_with_init_eqs_seen.add(mid)
            self._models_with_init_eqs.append(mdl)
        except Exception:
            pass

    def _register_diff_init_model(self, mdl: Block):
        """
        Register a block for explicit initialization of derivatives if it defines diff_init_eqs.
        """
        try:
            diff_init_eqs = getattr(mdl, "diff_init_eqs", None)
            models_with_diff_init_eqs_seen: Set[int] = set()
            if diff_init_eqs is None or len(diff_init_eqs) == 0:
                return
            mid = id(mdl)
            if mid in models_with_diff_init_eqs_seen:
                return
            models_with_diff_init_eqs_seen.add(mid)
            self._models_with_diff_init_eqs.append(mdl)

        except Exception:
            pass

    def _run_explicit_initialization(self):
        """
        Runs init_explicit for every block that defines init_eqs.

        - init_explicit expects sys_vars: Dict[int, Var] (it only uses len(sys_vars) but we comply)
        - init_explicit may MODIFY self._event_parameters_eqs (fill Const(None) -> Const(val)).
          BaseProblem builds event fn from a COPY; therefore we MUST rebuild runtime vectors after.
        """
        if len(self._models_with_init_eqs) == 0:
            return

        # sys_vars dict (uid -> Var), size = n_vars
        sys_vars: Dict[int, Var] = {v.uid: v for v in (self._state_vars + self._algebraic_vars)}
        sys_diff_vars: Dict[int, Var] = {dv.uid: dv for dv in self._diff_vars}

        for mdl in self._models_with_init_eqs:
            try:
                init_explicit_emt(
                    mdl=mdl,
                    sys_vars=sys_vars,
                    sys_diff_vars=sys_diff_vars,
                    variable_parameters=self._variable_parameters,
                    event_parameters_eqs=self._event_parameters_eqs,
                    constant_parameters=self._constant_parameters,
                    init_guess=self.init_guess,
                    diff_init_guess = self.diff_init_guess,
                    uid2idx_vars=self.uid2idx_vars,
                    uid2idx_diff = self.uid2idx_diff,
                    uid2idx_params=self.uid2idx_params,
                    uid2idx_event_params=self.uid2idx_event_params,
                    compiler_names_dict=self._compiler_names_dict,
                    alias_names_dict=self._alias_names_dict,
                    VARIABLE_PARAMS_NAME=self.VARIABLE_PARAMS_NAME,
                    TIME_NAME=self.TIME_NAME,
                    VARS_NAME=self.VARS_NAME,
                    DIFF_NAME=self.DIFF_NAME,
                    CONSTANT_PARAMS_NAME=self.CONSTANT_PARAMS_NAME
                )
            except Exception as e:
                if getattr(self.options, "verbose", 0) > 0:
                    print(f"[EMT][init_explicit] failed for block '{getattr(mdl, 'name', 'unknown')}'. Error: {e}")

        # for mdl in self._models_with_diff_init_eqs:
        #     try:
        #         init_explicit(
        #             mdl=mdl,
        #             sys_vars=sys_vars,
        #             variable_parameters=self._variable_parameters,
        #             event_parameters_eqs=self._event_parameters_eqs,
        #             constant_parameters=self._constant_parameters,
        #             init_guess=self.init_guess,
        #             uid2idx_vars=self.uid2idx_vars,
        #             uid2idx_params=self.uid2idx_params,
        #             uid2idx_event_params=self.uid2idx_event_params,
        #             compiler_names_dict=self._compiler_names_dict,
        #             alias_names_dict=self._alias_names_dict,
        #             VARIABLE_PARAMS_NAME=self.VARIABLE_PARAMS_NAME,
        #             TIME_NAME=self.TIME_NAME,
        #             VARS_NAME=self.VARS_NAME,
        #             DIFF_NAME=self.DIFF_NAME,
        #             CONSTANT_PARAMS_NAME=self.CONSTANT_PARAMS_NAME
        #         )
        #     except Exception as e:
        #         if getattr(self.options, "verbose", 0) > 0:
        #             print(f"[EMT][diff_init_explicit] failed for block '{getattr(mdl, 'name', 'unknown')}'. Error: {e}")

        self._build_runtime_param_vectors()

    # ---------------------------------------------------------------------
    # BUILD STRUCTURE
    # ---------------------------------------------------------------------
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



        c0 = grid.var_factory.add_const(0.0)



        # KCL accumulator per bus-phase
        I_kcl = {i: [c0, c0, c0, c0] for i in range(n_bus)}

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

            self._apply_piecewise_events_if_any(dev = bus, mdl =mdl, grid= grid, glob_time = glob_time)

            self._add_model_to_system_mappings(bus, mdl)
            sys_block.add(mdl)

            # register init_eqs blocks
            self._register_init_model(mdl)
            self._register_diff_init_model(mdl)

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

                # add its block (event params Ih_*)
                mdl = br.emt_model.model
                mdl.unify_blocks()

                self._apply_piecewise_events_if_any(dev = br, mdl = mdl, grid = grid, glob_time = glob_time)

                self._add_model_to_system_mappings(br, mdl)
                sys_block.add(mdl)

                # register init_eqs blocks (if any)
                self._register_init_model(mdl)
                self._register_diff_init_model(mdl)

                # Build voltage lists from bus blocks: [vN,vA,vB,vC], missing -> Const(0)
                v_f_vars = self._get_bus_v_list(br.bus_from.emt_model.model)
                v_t_vars = self._get_bus_v_list(br.bus_to.emt_model.model)

                # Create runtime companion that owns buffers + update_history
                rt = BergeronHistoryRuntime(line=br, line_block=mdl, h=h, sbase=Sbase, fbase=fbase)
                rt.bind_terminals(v_f_vars, v_t_vars)

                i_f_exprs, i_t_exprs = rt.get_nodal_injections()
                for ph in range(4):
                    I_kcl[f][ph] = I_kcl[f][ph] + i_f_exprs[ph]
                    I_kcl[t][ph] = I_kcl[t][ph] + i_t_exprs[ph]

                self.history_models.append(rt)
                continue

            # --- Non-Bergeron branches ---
            mdl = br.emt_model.model
            mdl.unify_blocks()

            self._apply_piecewise_events_if_any(dev = br, mdl = mdl, grid = grid, glob_time = glob_time)

            self._add_model_to_system_mappings(br, mdl)
            sys_block.add(mdl)

            # register init_eqs blocks
            self._register_init_model(mdl)
            self._register_diff_init_model(mdl)

            # Add terminal currents into KCL
            for ph in range(4):
                If_expr = mdl.E(br_if_keys[ph])
                It_expr = mdl.E(br_it_keys[ph])

                if If_expr is not None:
                    I_kcl[f][ph] = I_kcl[f][ph] + If_expr
                if It_expr is not None:
                    I_kcl[t][ph] = I_kcl[t][ph] + It_expr

            # PF init for branch internal variables (and if/it)
            if pf_results is not None:
                self._try_set_branch_pf_init(
                    mdl=mdl,
                    branch_index=branch_idx,
                    f_bus_idx=f,
                    t_bus_idx=t,
                    pf_results=pf_results,
                    sbase=getattr(grid, "Sbase", 1.0),
                )

        # -------------------------
        # 3) INJECTIONS
        # -------------------------
        for inj in grid.get_injection_devices_iter():
            mdl = inj.emt_model.model
            mdl.unify_blocks()

            self._apply_piecewise_events_if_any(dev = inj, mdl = mdl, grid = grid, glob_time = glob_time)

            self._add_model_to_system_mappings(inj, mdl)
            sys_block.add(mdl)

            # register init_eqs blocks
            self._register_init_model(mdl)
            self._register_diff_init_model(mdl)

            b = bus_dict[inj.bus]

            for ph in range(4):
                i_expr = mdl.E(inj_i_keys[ph])
                if i_expr is not None:
                    I_kcl[b][ph] = I_kcl[b][ph] - i_expr

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

            # EMT: bus equations must be KCL per existing phase.
            mdl.algebraic_eqs = []

            has_any_phase = False
            for ph_i, v_key in enumerate(ph_v_keys):
                if mdl.E(v_key) is None:
                    continue
                has_any_phase = True
                mdl.algebraic_eqs.append(I_kcl[bus_idx][ph_i])

            if not has_any_phase:
                self.logger.add_error("Bus has no phases (no voltage vars)", value=bus_idx)

    def _apply_piecewise_events_if_any(self, dev, mdl: Block, grid: MultiCircuit, glob_time):
        """

        :param dev: device object
        :param mdl: block
        :param grid: MultiCircuit
        :param glob_time: glob_time
        :return:
        """
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

    def _get_bus_v_list(self, grid:MultiCircuit,  bus_block: Block, ph_v_keys):
        out = []
        c0 = grid.var_factory.add_const(0.0)
        for k in ph_v_keys:
            vk = bus_block.E(k)
            out.append(vk if vk is not None else c0)
        return out

    # ---------------------------------------------------------------------
    # MAPPINGS
    # ---------------------------------------------------------------------
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

    # ---------------------------------------------------------------------
    # PF INIT
    # ---------------------------------------------------------------------
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

    def _try_set_branch_pf_init(
            self,
            mdl: Block,
            branch_index: int,
            f_bus_idx: int,
            t_bus_idx: int,
            pf_results: PowerFlowResults3Ph,
            sbase: float
    ):
        """
        Initialize branch variables from PF in a phase-agnostic way (any combo of N/A/B/C).

        Sets (if present in mdl.external_mapping -> mdl.E(key) is not None):
          - Sf_*, St_* (complex per-phase powers) for phases that exist in PF (A/B/C today)
          - Pf/Qf/Pt/Qt (aggregated over available Sf/St phases)
          - if_*, it_* (instantaneous terminal currents at t=0)

        Special:
          - PF typically has no Sf_N/St_N. If the model has if_N/it_N, set them to 0.0.
        :param mdl: Block
        :param branch_index:  int
        :param f_bus_idx: int
        :param t_bus_idx: int
        :param pf_results: PowerFlowResults3Ph
        :param sbase: float
        :return:
        """

        try:
            def set_if_exists(key, value):
                if (key is not None) and (mdl.E(key) is not None):
                    self.set_init_guess(mdl, key, float(value))

            phases = ["N", "A", "B", "C"]

            Sf_key = {
                "N": getattr(VarPowerFlowRefferenceType, "Sf_N", None),
                "A": VarPowerFlowRefferenceType.Sf_A,
                "B": VarPowerFlowRefferenceType.Sf_B,
                "C": VarPowerFlowRefferenceType.Sf_C,
            }
            St_key = {
                "N": getattr(VarPowerFlowRefferenceType, "St_N", None),
                "A": VarPowerFlowRefferenceType.St_A,
                "B": VarPowerFlowRefferenceType.St_B,
                "C": VarPowerFlowRefferenceType.St_C,
            }

            if_key = {
                "N": VarPowerFlowRefferenceType.if_N,
                "A": VarPowerFlowRefferenceType.if_A,
                "B": VarPowerFlowRefferenceType.if_B,
                "C": VarPowerFlowRefferenceType.if_C,
            }
            it_key = {
                "N": VarPowerFlowRefferenceType.it_N,
                "A": VarPowerFlowRefferenceType.it_A,
                "B": VarPowerFlowRefferenceType.it_B,
                "C": VarPowerFlowRefferenceType.it_C,
            }

            V_arr = {
                "N": getattr(pf_results, "voltage_N", None),
                "A": pf_results.voltage_A,
                "B": pf_results.voltage_B,
                "C": pf_results.voltage_C,
            }

            Sf_arr = {
                "N": getattr(pf_results, "Sf_N", None),
                "A": pf_results.Sf_A,
                "B": pf_results.Sf_B,
                "C": pf_results.Sf_C,
            }
            St_arr = {
                "N": getattr(pf_results, "St_N", None),
                "A": pf_results.St_A,
                "B": pf_results.St_B,
                "C": pf_results.St_C,
            }

            # 1) Per-phase Sf/St + totals
            Sf_sum = 0.0 + 0.0j
            St_sum = 0.0 + 0.0j

            for ph in phases:
                kSf = Sf_key[ph]
                kSt = St_key[ph]

                if (kSf is not None) and (mdl.E(kSf) is not None) and (Sf_arr[ph] is not None):
                    Sf_ph = Sf_arr[ph][branch_index] / sbase
                    set_if_exists(kSf, Sf_ph)
                    Sf_sum += Sf_ph

                if (kSt is not None) and (mdl.E(kSt) is not None) and (St_arr[ph] is not None):
                    St_ph = St_arr[ph][branch_index] / sbase
                    set_if_exists(kSt, St_ph)
                    St_sum += St_ph



            # 2) Terminal currents if_/it_
            for ph in phases:
                uses_curr = (mdl.E(if_key[ph]) is not None) or (mdl.E(it_key[ph]) is not None)
                if not uses_curr:
                    continue

                # PF doesn't have Sf_N/St_N -> set N currents to 0 if needed
                if (Sf_arr[ph] is None) or (St_arr[ph] is None) or (V_arr[ph] is None):
                    set_if_exists(if_key[ph], 0.0)
                    set_if_exists(it_key[ph], 0.0)
                    continue

                Sf_ph = Sf_arr[ph][branch_index] / sbase
                St_ph = St_arr[ph][branch_index] / sbase

                Vf_ph = V_arr[ph][f_bus_idx]
                Vt_ph = V_arr[ph][t_bus_idx]

                I_f = 0.0 + 0.0j if Vf_ph == 0 else np.conj(Sf_ph / Vf_ph)
                I_t = 0.0 + 0.0j if Vt_ph == 0 else np.conj(St_ph / Vt_ph)

                i_f0 = np.sqrt(2.0) * np.abs(I_f) * np.cos(np.angle(I_f))
                i_t0 = np.sqrt(2.0) * np.abs(I_t) * np.cos(np.angle(I_t))

                set_if_exists(if_key[ph], float(i_f0))
                set_if_exists(it_key[ph], float(i_t0))

            set_if_exists(VarPowerFlowRefferenceType.Pf, float(np.real(Sf_sum)))
            set_if_exists(VarPowerFlowRefferenceType.Qf, float(np.imag(Sf_sum)))
            set_if_exists(VarPowerFlowRefferenceType.Pt, float(np.real(St_sum)))
            set_if_exists(VarPowerFlowRefferenceType.Qt, float(np.imag(St_sum)))

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

                if (mdl.E(i_key) is None) and (mdl.E(P_key) is None) and (mdl.E(Q_key) is None):
                    continue

                S = S_arr[bus_index] / sbase
                V = V_arr[bus_index]

                if V == 0:
                    I = 0.0 + 0.0j
                else:
                    I = np.conj(S / V)

                I_rms = np.abs(I)
                I_ang = np.angle(I)

                i0 = np.sqrt(2.0) * I_rms * np.cos(I_ang)

                set_if_exists(i_key, float(i0))
                set_if_exists(P_key, float(np.real(S)))
                set_if_exists(Q_key, float(np.imag(S)))

                Sbus_total += S

            if mdl.E(VarPowerFlowRefferenceType.theta) is not None:
                VA = pf_results.voltage_A[bus_index]
                VB = pf_results.voltage_B[bus_index]
                VC = pf_results.voltage_C[bus_index]

                a = np.exp(1j * 2 * np.pi / 3)
                V1 = (1 / 3) * (VA + a * VB + (a * a) * VC)
                theta = np.angle(V1)


                self.set_init_guess(mdl, VarPowerFlowRefferenceType.theta, float(theta))
                # Prueba sumando o restando pi/2 si el modelo es Park estándar
                self.set_init_guess(mdl, VarPowerFlowRefferenceType.theta, float(theta) - np.pi / 2)

            set_if_exists(VarPowerFlowRefferenceType.P, float(np.real(Sbus_total)))
            set_if_exists(VarPowerFlowRefferenceType.Q, float(np.imag(Sbus_total)))

        except Exception:
            pass

    # ---------------------------------------------------------------------
    # UTILS
    # ---------------------------------------------------------------------
    def _deduplicate_block_entities(self, block: Block):
        """
        Removes duplicated symbolic objects within the block by UID
        while preserving their first appearance order.
        """


        block.state_vars = self._unique_keep_order(block.state_vars)
        block.algebraic_vars = self._unique_keep_order(block.algebraic_vars)
        block.diff_vars = self._unique_keep_order(block.diff_vars)

    def _unique_keep_order(self, seq: List):
        seen = set()
        out = []
        for x in seq:
            if x.uid not in seen:
                seen.add(x.uid)
                out.append(x)
        return out

    def add_device_var(self, dev: ALL_DEV_TYPES, var: Var):
        """
        Registers a variable belonging to a specific device.
        """
        var_list = self._vars_info.get(dev, None)
        if var_list is None:
            self._vars_info[dev] = [var]
        else:
            var_list.append(var)

    def set_init_guess(self, mdl: Block, reference_powerflow: Any, val: float):
        """
        Sets the temporary initial guess for a given variable during the parsing phase.
        (PF guesses go to _temp_init_guess; then copied into self.init_guess after super().__init__.)
        """
        if not hasattr(mdl, "external_mapping") or mdl.external_mapping is None:
            return
        if reference_powerflow in mdl.external_mapping:
            var = mdl.external_mapping[reference_powerflow]
            if var is None:
                return
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

    def emt_boundary_update(self,
                            t_curr: float,
                            x_prev: np.ndarray,
                            full_params: np.ndarray):
        """
        Updates boundary functions for devices with history.
        """
        for rt in self.history_models:
            rt.update_history(self.step_counter, x_prev, full_params)
        self.step_counter += 1

    def get_floquet_ak_stack(self, trajectory: np.ndarray, h: float, jac_evaluator=None, static_params=None) -> \
    Optional[np.ndarray]:
        """
        HPC Implementation: Calculates the A_k stack using exact Kron Reduction
        optimized with Scipy Sparse Solvers. Evaluates the non-linear Jacobian
        at each step of the limit cycle trajectory.
        """
        if jac_evaluator is None:
            self.logger.add_warning(
                "No jac_evaluator provided to get_floquet_ak_stack. Falling back to LU-cached path.")
            return None

        n = self.get_states_number()
        steps = len(trajectory) - 1

        if steps <= 0:
            return None

        stack = np.zeros((steps, n, n), order='C')

        for i in range(steps):
            x_k = trajectory[i]

            try:
                J = jac_evaluator(x_k, static_params, x_k, None, h, None)
            except Exception as e:
                self.logger.add_warning(f"Failed to evaluate Jacobian for Ak stack: {e}")
                return None

            J11 = J[:n, :n]
            J12 = J[:n, n:]
            J21 = J[n:, :n]
            J22 = J[n:, n:]

            J22_inv_J21 = spla.spsolve(J22, J21)

            J_red = (J11 - J12 @ J22_inv_J21)

            if sp.issparse(J_red):
                J_red = J_red.toarray()

            stack[i] = la.inv(h * J_red)

        return stack

    def get_init_guess_table(self,
                             include_all_vars: bool = True,
                             only_in_init_guess: bool = False,
                             tol_zero: float = 1e-12) -> pd.DataFrame:
        """
        Return a table with uid, alias/name and initial value for each variable.

        include_all_vars:
            - True: include all state+algebraic vars, even if not in init_guess (value=0).
            - False: include only uids present in init_guess (or only_in_init_guess=True).

        only_in_init_guess:
            - True: filter to only those explicitly initialized (uid in init_guess).
            - False: keep everything (depending on include_all_vars).

        tol_zero:
            threshold to flag values close to zero.
        """
        # Build x0 and dx0 from current guesses
        x0 = self.get_x0()
        dx0 = self.get_dx0()

        uid2idx_vars = self.uid2idx_vars
        uid2idx_diff = self.uid2idx_diff

        # Define the sets we want to process: (Variables, Guess_Source, Index_Map, Vector, Label)
        data_sets = [
            (list(self.get_state_vars()) + list(self.get_algebraic_vars()), self.init_guess, uid2idx_vars, x0, "Var"),
            (list(self.get_diff_vars()), self.diff_init_guess, uid2idx_diff, dx0, "DiffVar")
        ]

        rows = []
        for vars_list, guess_dict, idx_map, vector, var_type in data_sets:
            for v in vars_list:
                uid = v.uid
                idx = idx_map.get(uid, None)
                val = float(vector[idx]) if idx is not None else 0.0

                in_guess = uid in guess_dict

                # Filters
                if only_in_init_guess and (not in_guess):
                    continue
                if (not include_all_vars) and (not in_guess):
                    continue

                alias = self._alias_names_dict.get(uid, None) if hasattr(self, "_alias_names_dict") else None

                rows.append({
                    "uid": uid,
                    "type": var_type, # NEW: Distinguishes between Var and DiffVar
                    "alias": alias,
                    "name": getattr(v, "name", None),
                    "value": val,
                    "in_init_guess": in_guess,
                    "is_zero": abs(val) <= tol_zero,
                })

        df = pd.DataFrame(rows)

        # Nice ordering: Group by type, then initialization status
        if not df.empty:
            sort_cols = ["type", "in_init_guess", "is_zero", "name"]
            df = df.sort_values(sort_cols, ascending=[False, False, True, True]).reset_index(drop=True)

        return df