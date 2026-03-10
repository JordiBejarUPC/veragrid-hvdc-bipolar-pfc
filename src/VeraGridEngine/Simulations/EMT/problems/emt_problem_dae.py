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
from typing import Dict, List, Any, Set, Optional, Tuple
from itertools import chain

from VeraGridEngine.Devices import MultiCircuit
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.Utils.Symbolic.symbolic import Var, piecewise
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import VarPowerFlowRefferenceType
from VeraGridEngine.basic_structures import Logger
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


def _unique_keep_order(seq: List[Var]) -> List[Var]:
    """
    Remove duplicated variables by UID while preserving the first appearance order.

    :param seq: Input variable sequence.
    :return: Deduplicated variable sequence.
    """
    seen: Set[int] = set()
    out: List[Var] = list()

    for item in seq:
        if item.uid in seen:
            pass
        else:
            seen.add(item.uid)
            out.append(item)

    return out

def _deduplicate_block_entities(block: Block)->None:
    """
    Removes duplicated symbolic objects within the block by UID
    while preserving their first appearance order.
    """


    block.state_vars = _unique_keep_order(block.state_vars)
    block.algebraic_vars = _unique_keep_order(block.algebraic_vars)
    block.diff_vars = _unique_keep_order(block.diff_vars)

def _get_mode_event_sort_key(event: Tuple[float, float, bool]) -> float:
    """
    Return the sorting key of a mode event.

    :param event: Mode event tuple (time, value, force_step_alignment).
    :return: Event time.
    """
    return event[0]

def _is_time_aligned(t_curr: float, event_time: float) -> bool:
    """
    Return whether the current solver time is aligned with the event time.

    :param t_curr: Current solver time.
    :param event_time: Scheduled event time.
    :return: True if the current time is aligned with the event time.
    """
    time_tol = 10.0 * np.finfo(np.float64).eps * max(1.0, abs(event_time))
    return abs(t_curr - event_time) <= time_tol

def _get_next_forced_mode_event_time(
        scheduled_mode_events: Dict[int, List[Tuple[float, float, bool]]],
        t_prev: float,
        t_target: float,
) -> Optional[float]:
    """
    Return the earliest forced-alignment mode event time in the interval
    (t_prev, t_target].

    :param t_prev: Previous solver time.
    :param t_target: Nominal target time.
    :return: Earliest forced event time or None.
    """
    next_time: Optional[float] = None

    for _, event_list in scheduled_mode_events.items():
        event_idx: int = 0

        while event_idx < len(event_list):
            event_time: float = event_list[event_idx][0]
            force_step_alignment: bool = event_list[event_idx][2]

            if force_step_alignment and (t_prev < event_time <= t_target):
                if next_time is None:
                    next_time = event_time
                else:
                    if event_time < next_time:
                        next_time = event_time
                    else:
                        pass
            else:
                pass

            event_idx += 1

    return next_time

def _get_block_name(mdl: Block) -> str:
    """
    Return the block name used for logging.

    :param mdl: Block to inspect.
    :return: Block name.
    """
    if mdl.name is None:
        return "unknown"
    else:
        return str(mdl.name)


def _get_grid_runtime_events(grid: MultiCircuit) -> List[Any]:
    """
    Return the list of scheduled runtime events available in the grid.

    :param grid: MultiCircuit instance.
    :return: List of scheduled runtime events.
    """
    rms_events = getattr(grid, "rms_events", None)

    if rms_events is not None:
        return list(rms_events)
    else:
        return list()

def _get_bus_v_list(
        grid: MultiCircuit,
        bus_block: Block,
        ph_v_keys: List[VarPowerFlowRefferenceType]
) -> List[Any]:
    """
    Return the ordered list of bus phase voltages, filling missing phases with zero.

    :param grid: MultiCircuit instance.
    :param bus_block: Bus symbolic block.
    :param ph_v_keys: Ordered list of phase voltage keys.
    :return: Ordered list of phase voltage expressions.
    """
    out: List[Any] = list()
    c0 = grid.var_factory.add_const(0.0)

    for key in ph_v_keys:
        vk = bus_block.E(key)

        if vk is None:
            out.append(c0)
        else:
            out.append(vk)

    return out

def _get_external_mapping(mdl: Block) -> Optional[Dict[Any, Var]]:
    external_mapping: Optional[Dict[Any, Var]] = mdl.external_mapping
    if external_mapping is None:
        return None
    else:
        return external_mapping


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
                 pf_results: PowerFlowResults3Ph | None)-> None:
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
        self._temp_diff_init_guess: Dict[int, float] = dict()

        self._scheduled_mode_events: Dict[int, List[Tuple[float, float, bool]]] = dict()
        self._mode_event_cursor: Dict[int, int] = dict()

        # for init_explicit
        self._models_with_init_eqs: List[Block] = []
        self._models_with_diff_init_eqs: List[Block] = []
        self._models_with_init_eqs_seen: Set[int] = set()
        self._models_with_diff_init_eqs_seen: Set[int] = set()

        sys_block = Block(children=[], in_vars=[])
        glob_time = Var(self.TIME_NAME)

        self.history_models: List[BergeronHistoryRuntime] = list()
        self.step_counter: int = 0

        t_build = _tic()

        # build on local sys_block
        self._build_structure_and_collect(sys_block, grid, pf_results, glob_time)

        sys_block.unify_blocks()
        _deduplicate_block_entities(sys_block)

        # initialize template with the complete block
        super().__init__(sys_block=sys_block, glob_time=glob_time)

        if len(self._runtime_mode_parameters) > 0:
            self._initialize_mode_event_state()

        # 1) PF guesses
        self.init_guess.update(self._temp_init_guess)
        self.diff_init_guess.update(self._temp_diff_init_guess)

        # 2) explicit init guesses initialization
        self._run_explicit_initialization()
        # self.diff_init_guess.update(self.diff_init_guess)

        t_done = _toc(t_build)

        if options.verbose > 0:
            self.logger.add_debug(f"init guess = {self.init_guess}")
            self.logger.add_debug(f"diff init guess = {self.diff_init_guess}")
            self.logger.add_debug(
                f"EMT electrical problem parsed in {t_done:.4f}s | "
                f"vars={self._n_vars} (state={self._n_state}, alg={self._n_alg}) | "
                f"eqs(state={len(self._state_eqs)}, alg={len(self._algebraic_eqs)})"
            )

    # ---------------------------------------------------------------------
    # init_eqs registration + explicit init execution
    # ---------------------------------------------------------------------
    def _register_init_model(self, mdl: Block) -> None:
        """
        Register a block for explicit initialization if it defines init_eqs.

        :param mdl: Block to inspect.
        :return: None
        """
        init_eqs = mdl.init_eqs

        if init_eqs is None or len(init_eqs) == 0:
            pass
        else:
            mid: int = id(mdl)

            if mid in self._models_with_init_eqs_seen:
                pass
            else:
                self._models_with_init_eqs_seen.add(mid)
                self._models_with_init_eqs.append(mdl)

    def _register_diff_init_model(self, mdl: Block) -> None:
        """
        Register a block for explicit differential initialization if it defines diff_init_eqs.

        :param mdl: Block to inspect.
        :return: None
        """
        diff_init_eqs = mdl.diff_init_eqs

        if diff_init_eqs is None or len(diff_init_eqs) == 0:
            pass
        else:
            mid: int = id(mdl)

            if mid in self._models_with_diff_init_eqs_seen:
                pass
            else:
                self._models_with_diff_init_eqs_seen.add(mid)
                self._models_with_diff_init_eqs.append(mdl)

    def _run_explicit_initialization(self)-> None:
        """
        Run explicit initialization for every block that defines initialization equations.

        The routine may modify runtime parameter expressions, so runtime parameter
        buffers are rebuilt afterwards.

        :return: None
        """

        if len(self._models_with_init_eqs) == 0 and len(self._models_with_diff_init_eqs) == 0:
            return

        # sys_vars dict (uid -> Var), size = n_vars
        sys_vars: Dict[int, Var] = {v.uid: v for v in (self._state_vars + self._algebraic_vars)}
        sys_diff_vars: Dict[int, Var] = {dv.uid: dv for dv in self._diff_vars}

        for mdl in chain(self._models_with_init_eqs, self._models_with_diff_init_eqs):
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
                block_name: str = _get_block_name(mdl)
                error_detail = f"{type(e).__name__}: {str(e)}"

                self.logger.add_warning(
                    msg="EMT explicit initialization failed for block.",
                    device=block_name,
                    value=error_detail,
                    expected_value="Successful explicit initialization",
                    device_class="EMT",
                    device_property="init_explicit"
                )

                if self.options.verbose > 0:
                    self.logger.add_debug(
                        f"[EMT][init_explicit] failed for block '{block_name}'. Error: {error_detail}")

        self._build_runtime_param_vectors()

    def _process_device_model(self, dev: Any, sys_block: Block, grid: MultiCircuit, glob_time: Var) -> Block:
        """
        Extracts, unifies, applies events, and registers a device's EMT model
        into the global system block.

        :param dev: Device object from the grid.
        :param sys_block: Main DAE system block.
        :param grid: MultiCircuit instance.
        :param glob_time: Global time variable.
        :return: The unified device block.
        """
        mdl = dev.emt_model.model
        mdl.unify_blocks()

        self._apply_piecewise_events_if_any(dev=dev, mdl=mdl, grid=grid, glob_time=glob_time)
        self._add_model_to_system_mappings(dev, mdl)
        sys_block.add(mdl)

        # register init_eqs blocks
        self._register_init_model(mdl)
        self._register_diff_init_model(mdl)

        return mdl

    # ---------------------------------------------------------------------
    # BUILD STRUCTURE
    # ---------------------------------------------------------------------
    def _build_structure_and_collect(
            self,
            sys_block: Block,
            grid: MultiCircuit,
            pf_results: PowerFlowResults3Ph | None,
            glob_time: Var
    ) -> None:
        """
        EMT (abc) assembly: nodal KCL per phase.
        - Unknowns: bus phase voltages (v_N,v_A,v_B,v_C as available)
        - Algebraic equations: KCL per bus-phase: sum(i_phase) = 0

        :param sys_block: Block with the system DAE
        :param grid: MultiCircuit
        :param pf_results: Power flow results in 3ph
        :param glob_time: Variable that stores the global time of the simulation
        :return: None
        """

        bus_dict: Dict[Any, int] = dict()
        n_bus: int = len(grid.buses)

        # --- helpers ---
        ph_v_keys: List[VarPowerFlowRefferenceType] = list([
            VarPowerFlowRefferenceType.v_N,
            VarPowerFlowRefferenceType.v_A,
            VarPowerFlowRefferenceType.v_B,
            VarPowerFlowRefferenceType.v_C,
        ])

        inj_i_keys: List[VarPowerFlowRefferenceType] = list([
            VarPowerFlowRefferenceType.i_N,
            VarPowerFlowRefferenceType.i_A,
            VarPowerFlowRefferenceType.i_B,
            VarPowerFlowRefferenceType.i_C,
        ])

        # These MUST exist in VarPowerFlowRefferenceType for non-Bergeron branches:
        # current leaving FROM bus into the branch:
        br_if_keys: List[VarPowerFlowRefferenceType] = list([
            VarPowerFlowRefferenceType.if_N,
            VarPowerFlowRefferenceType.if_A,
            VarPowerFlowRefferenceType.if_B,
            VarPowerFlowRefferenceType.if_C,
        ])

        # current leaving TO bus into the branch:
        br_it_keys: List[VarPowerFlowRefferenceType] = list([
            VarPowerFlowRefferenceType.it_N,
            VarPowerFlowRefferenceType.it_A,
            VarPowerFlowRefferenceType.it_B,
            VarPowerFlowRefferenceType.it_C,
        ])

        c0: Any = grid.var_factory.add_const(0.0)

        # KCL accumulator per bus-phase
        I_kcl: Dict[int, List[Any]] = dict()
        for i in range(n_bus):
            I_kcl[i] = list([c0, c0, c0, c0])

        # Bases (for Bergeron constructor)
        h: float = float(self.options.time_step)
        Sbase: float = float(grid.Sbase)
        fbase: float = float(grid.fBase)

        # -------------------------
        # 0) BUS DICT SETUP
        # -------------------------
        # Pre-allocate dictionary mapping to find buses quickly during branch/injection iteration
        for bus_idx, bus in enumerate(grid.buses):
            bus_dict[bus] = int(bus_idx)

        # -------------------------
        # 1) BRANCHES
        # -------------------------
        # Process all branches to extract their currents and map their internal models
        for branch_idx, br in enumerate(grid.get_branches_iter(add_vsc=True, add_hvdc=True, add_switch=True)):
            f: int = bus_dict[br.bus_from]
            t: int = bus_dict[br.bus_to]

            is_bergeron: bool = False
            if br.emt_model_type is not None:
                if br.emt_model_type.value == "Bergeron":
                    is_bergeron = True
                else:
                    pass
            else:
                pass

            # Process device model automatically to unify blocks and apply events
            mdl: Block = self._process_device_model(br, sys_block, grid, glob_time)

            if is_bergeron:
                # Build voltage lists from bus blocks: [vN,vA,vB,vC], missing -> Const(0)
                v_f_vars: List[Any] = _get_bus_v_list(grid=self.grid, bus_block=br.bus_from.emt_model.model,
                                                      ph_v_keys=ph_v_keys)
                v_t_vars: List[Any] = _get_bus_v_list(grid=self.grid, bus_block=br.bus_to.emt_model.model,
                                                      ph_v_keys=ph_v_keys)

                # Create runtime companion that owns buffers + update_history
                rt: BergeronHistoryRuntime = BergeronHistoryRuntime(line=br, line_block=mdl, h=h, sbase=Sbase,
                                                                    fbase=fbase)
                rt.bind_terminals(v_f_vars, v_t_vars)

                i_f_exprs: List[Any]
                i_t_exprs: List[Any]
                i_f_exprs, i_t_exprs = rt.get_nodal_injections()

                for ph in range(4):
                    # currents in branches are defined as going out of the bus (sign convention)
                    I_kcl[f][ph] = I_kcl[f][ph] - i_f_exprs[ph]
                    I_kcl[t][ph] = I_kcl[t][ph] - i_t_exprs[ph]

                self.history_models.append(rt)

            else:
                # --- Non-Bergeron branches ---
                # Add terminal currents into KCL
                for ph in range(4):
                    If_expr: Any | None = mdl.E(br_if_keys[ph])
                    It_expr: Any | None = mdl.E(br_it_keys[ph])

                    # currents in branches are defined as going out of the bus (sign convention)
                    if If_expr is not None:
                        I_kcl[f][ph] = I_kcl[f][ph] - If_expr
                    else:
                        pass

                    if It_expr is not None:
                        I_kcl[t][ph] = I_kcl[t][ph] - It_expr
                    else:
                        pass

                # PF init for branch internal variables (and if/it)
                if pf_results is not None:
                    self._try_set_branch_pf_init(
                        mdl=mdl,
                        branch_index=branch_idx,
                        f_bus_idx=f,
                        t_bus_idx=t,
                        pf_results=pf_results,
                        sbase=grid.Sbase
                    )
                else:
                    pass

        # -------------------------
        # 2) INJECTIONS
        # -------------------------
        # Process all injection devices to add their currents into the KCL accumulators
        for inj in grid.get_injection_devices_iter():
            mdl: Block = self._process_device_model(inj, sys_block, grid, glob_time)
            b: int = bus_dict[inj.bus]

            # currents in injections are defined as entering the bus (sign convention)
            for ph in range(4):
                i_expr: Any | None = mdl.E(inj_i_keys[ph])
                if i_expr is not None:
                    I_kcl[b][ph] = I_kcl[b][ph] + i_expr
                else:
                    pass

            if pf_results is not None:
                self._try_set_inj_pf_init(
                    mdl=mdl,
                    bus_index=b,
                    pf_results=pf_results,
                    sbase=grid.Sbase,
                )
            else:
                pass

        # -------------------------
        # 3) BUSES
        # -------------------------
        # Process the bus blocks themselves to prepare their models
        for bus_idx, bus in enumerate(grid.buses):
            mdl: Block = self._process_device_model(bus, sys_block, grid, glob_time)

            if pf_results is not None:
                self._try_set_bus_pf_init(mdl=mdl, bus_index=bus_idx, pf_results=pf_results)
            else:
                pass

        # -------------------------
        # 4) FINAL: stamp KCL equations into each bus model (per existing phase)
        # -------------------------
        # The accumulated KCL for each phase is assigned as the algebraic equation for the respective bus voltage
        for bus_idx, bus in enumerate(grid.buses):
            mdl: Block = bus.emt_model.model

            # EMT: bus equations must be KCL per existing phase.
            mdl.algebraic_eqs = list()
            for ph_i, v_key in enumerate(ph_v_keys):
                v_expr: Any | None = mdl.E(v_key)
                if v_expr is not None:
                    mdl.algebraic_eqs.append(I_kcl[bus_idx][ph_i])
                else:
                    pass

            if len(mdl.algebraic_eqs) == 0:
                self.logger.add_error("Bus has no phases (no voltage vars)", value=str(bus_idx))
            else:
                pass

    def _apply_piecewise_events_if_any(
            self,
            dev: Any,
            mdl: Block,
            grid: MultiCircuit,
            glob_time: Var
    ) -> None:
        """
        Apply scheduled runtime events to the model using explicit Block dictionaries.

        This function processes two types of events based on their registration in the Block:
        1. Continuous events (found in `mdl.event_dict`): Converted to `piecewise(time)` expressions.
        2. Discrete mode events (found in `mdl.mode_dict`): Stored as scheduled mode events to be
           applied dynamically by the EMT boundary update layer.

        :param dev: Device object from the grid.
        :param mdl: Device symbolic block containing `event_dict` and `mode_dict`.
        :param grid: MultiCircuit instance containing the scheduled events.
        :param glob_time: Global time symbolic variable.
        :return: None
        """
        runtime_events: List[Any] = _get_grid_runtime_events(grid)

        # Fast exit if the block defines no parameters that can be changed
        if not mdl.event_dict and not mdl.mode_dict:
            return
        else:
            pass

        # Prepare containers to collect time-value pairs for continuous parameters
        collect_events: Dict[Var, Dict[str, List[float]]] = dict()
        for key in mdl.event_dict.keys():
            collect_events[key] = {"times": list(), "values": list()}

        # Filter events belonging to this specific device
        dev_events: List[Any] = list()
        for evt in runtime_events:
            if getattr(evt, "device_idtag", None) == dev.idtag:
                dev_events.append(evt)
            else:
                pass

        # Classify and store events based on explicit Block dictionaries
        for evt in dev_events:
            parameter: Any = evt.parameter

            if parameter in mdl.mode_dict:
                # Process as a Discrete Mode event (breakers, faults, limits)
                if isinstance(parameter, Var):
                    uid: int = parameter.uid
                    event_list: Optional[List[Tuple[float, float, bool]]] = self._scheduled_mode_events.get(uid, None)

                    force_step_alignment: bool = bool(getattr(evt, "force_step_alignment", False))

                    if event_list is None:
                        self._scheduled_mode_events[uid] = [
                            (float(evt.time), float(evt.value), force_step_alignment)
                        ]
                    else:
                        event_list.append(
                            (float(evt.time), float(evt.value), force_step_alignment)
                        )
                else:
                    raise TypeError(
                        f"Mode runtime event parameter '{parameter}' must be a Var instance."
                    )

            elif parameter in mdl.event_dict:
                # Process as a Continuous Piecewise event (ramps, setpoints)
                collect_events[parameter]["times"].append(float(evt.time))
                collect_events[parameter]["values"].append(float(evt.value))

            else:
                # Parameter not registered in either dict; safely ignore
                pass

        # Construct piecewise functions for continuous parameters
        for param, info in collect_events.items():
            if len(info["times"]) != 0:
                default_value: Any = mdl.event_dict[param]
                mdl.event_dict[param] = piecewise(
                    time_var=glob_time,
                    t_events=np.array(info["times"], dtype=np.float64),
                    new_values=np.array(info["values"], dtype=np.float64),
                    default_value=default_value,
                )
            else:
                pass

    # ---------------------------------------------------------------------
    # MAPPINGS
    # ---------------------------------------------------------------------
    def _add_model_to_system_mappings(self, elm: ALL_DEV_TYPES, mdl: Block)->None:
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
    def _try_set_bus_pf_init(self, mdl: Block, bus_index: int, pf_results: PowerFlowResults3Ph) -> None:
        """
        Initialize bus voltage variables from three-phase power-flow results.

        Phasor results are transformed into instantaneous abc-domain values at t = 0.
        Only variables that exist in the model external mapping are initialized.

        :param mdl: Bus symbolic block.
        :param bus_index: Bus index in the power-flow results.
        :param pf_results: Three-phase power-flow results.
        :return: None
        """
        omega_base: float = 2.0 * np.pi * self.grid.fBase

        if mdl.E(VarPowerFlowRefferenceType.v_N) is not None:
            V_N = pf_results.voltage_N[bus_index]
            v_N: float = np.sqrt(2.0) * np.real(V_N)
            d_v_N: float = -omega_base * np.sqrt(2.0) * np.imag(V_N)

            self.set_init_guess(mdl, VarPowerFlowRefferenceType.v_N, v_N)
            self.set_diff_init_guess(mdl, VarPowerFlowRefferenceType.d_v_N, d_v_N)
        else:
            pass

        if mdl.E(VarPowerFlowRefferenceType.v_A) is not None:
            V_A = pf_results.voltage_A[bus_index]
            v_A: float = np.sqrt(2.0) * np.real(V_A)
            d_v_A: float = -omega_base * np.sqrt(2.0) * np.imag(V_A)

            self.set_init_guess(mdl, VarPowerFlowRefferenceType.v_A, v_A)
            self.set_diff_init_guess(mdl, VarPowerFlowRefferenceType.d_v_A, d_v_A)
        else:
            pass

        if mdl.E(VarPowerFlowRefferenceType.v_B) is not None:
            V_B = pf_results.voltage_B[bus_index]
            v_B: float = np.sqrt(2.0) * np.real(V_B)
            d_v_B: float = -omega_base * np.sqrt(2.0) * np.imag(V_B)

            self.set_init_guess(mdl, VarPowerFlowRefferenceType.v_B, v_B)
            self.set_diff_init_guess(mdl, VarPowerFlowRefferenceType.d_v_B, d_v_B)
        else:
            pass

        if mdl.E(VarPowerFlowRefferenceType.v_C) is not None:
            V_C = pf_results.voltage_C[bus_index]
            v_C: float = np.sqrt(2.0) * np.real(V_C)
            d_v_C: float = -omega_base * np.sqrt(2.0) * np.imag(V_C)

            self.set_init_guess(mdl, VarPowerFlowRefferenceType.v_C, v_C)
            self.set_diff_init_guess(mdl, VarPowerFlowRefferenceType.d_v_C, d_v_C)
        else:
            pass

    def _try_set_branch_pf_init(
            self,
            mdl: Block,
            branch_index: int,
            f_bus_idx: int,
            t_bus_idx: int,
            pf_results: PowerFlowResults3Ph,
            sbase: float
    ) -> None:
        """
        Initialize branch variables from three-phase power-flow results.

        The method initializes:
          - per-phase branch powers Sf_* and St_* when available,
          - aggregated terminal powers Pf/Qf/Pt/Qt,
          - per-phase instantaneous terminal currents if_* and it_* at t = 0.

        The neutral phase is initialized to zero for currents if the corresponding
        PF quantities are not available.

        :param mdl: Branch symbolic block.
        :param branch_index: Branch index in the power-flow results.
        :param f_bus_idx: From-bus index in the power-flow results.
        :param t_bus_idx: To-bus index in the power-flow results.
        :param pf_results: Three-phase power-flow results.
        :param sbase: Base power of the grid.
        :return: None
        """
        phases: List[str] = ["N", "A", "B", "C"]

        sf_key_dict: Dict[str, Optional[VarPowerFlowRefferenceType]] = {
            "N": None,
            "A": VarPowerFlowRefferenceType.Sf_A,
            "B": VarPowerFlowRefferenceType.Sf_B,
            "C": VarPowerFlowRefferenceType.Sf_C,
        }
        st_key_dict: Dict[str, Optional[VarPowerFlowRefferenceType]] = {
            "N": None,
            "A": VarPowerFlowRefferenceType.St_A,
            "B": VarPowerFlowRefferenceType.St_B,
            "C": VarPowerFlowRefferenceType.St_C,
        }

        if_key_dict: Dict[str, VarPowerFlowRefferenceType] = {
            "N": VarPowerFlowRefferenceType.if_N,
            "A": VarPowerFlowRefferenceType.if_A,
            "B": VarPowerFlowRefferenceType.if_B,
            "C": VarPowerFlowRefferenceType.if_C,
        }
        it_key_dict: Dict[str, VarPowerFlowRefferenceType] = {
            "N": VarPowerFlowRefferenceType.it_N,
            "A": VarPowerFlowRefferenceType.it_A,
            "B": VarPowerFlowRefferenceType.it_B,
            "C": VarPowerFlowRefferenceType.it_C,
        }

        voltage_dict: Dict[str, Optional[np.ndarray]] = {
            "N": pf_results.voltage_N,
            "A": pf_results.voltage_A,
            "B": pf_results.voltage_B,
            "C": pf_results.voltage_C,
        }

        sf_array_dict: Dict[str, Optional[np.ndarray]] = {
            "N": None,
            "A": pf_results.Sf_A,
            "B": pf_results.Sf_B,
            "C": pf_results.Sf_C,
        }
        st_array_dict: Dict[str, Optional[np.ndarray]] = {
            "N": None,
            "A": pf_results.St_A,
            "B": pf_results.St_B,
            "C": pf_results.St_C,
        }

        sf_sum: complex = 0.0 + 0.0j
        st_sum: complex = 0.0 + 0.0j

        for ph in phases:
            sf_key: Optional[VarPowerFlowRefferenceType] = sf_key_dict[ph]
            st_key: Optional[VarPowerFlowRefferenceType] = st_key_dict[ph]
            sf_array: Optional[np.ndarray] = sf_array_dict[ph]
            st_array: Optional[np.ndarray] = st_array_dict[ph]

            if sf_key is None:
                pass
            else:
                if mdl.E(sf_key) is not None and sf_array is not None:
                    sf_ph = sf_array[branch_index] / sbase
                    self.set_if_exists(mdl=mdl, key=sf_key, value=float(np.real(sf_ph)))
                    sf_sum += sf_ph
                else:
                    pass

            if st_key is None:
                pass
            else:
                if mdl.E(st_key) is not None and st_array is not None:
                    st_ph = st_array[branch_index] / sbase
                    self.set_if_exists(mdl=mdl, key=st_key, value=float(np.real(st_ph)))
                    st_sum += st_ph
                else:
                    pass

        for ph in phases:
            if_key: VarPowerFlowRefferenceType = if_key_dict[ph]
            it_key: VarPowerFlowRefferenceType = it_key_dict[ph]

            uses_currents: bool = (
                    (mdl.E(if_key) is not None)
                    or (mdl.E(it_key) is not None)
            )

            if uses_currents:
                sf_array = sf_array_dict[ph]
                st_array = st_array_dict[ph]
                voltage_array = voltage_dict[ph]

                if sf_array is None or st_array is None or voltage_array is None:
                    self.set_if_exists(mdl=mdl, key=if_key, value=0.0)
                    self.set_if_exists(mdl=mdl, key=it_key, value=0.0)
                else:
                    sf_ph = sf_array[branch_index] / sbase
                    st_ph = st_array[branch_index] / sbase

                    vf_ph = voltage_array[f_bus_idx]
                    vt_ph = voltage_array[t_bus_idx]

                    if vf_ph == 0:
                        i_f = 0.0 + 0.0j
                    else:
                        i_f = np.conj(sf_ph / vf_ph)

                    if vt_ph == 0:
                        i_t = 0.0 + 0.0j
                    else:
                        i_t = np.conj(st_ph / vt_ph)

                    i_f0: float = np.sqrt(2.0) * np.real(i_f)
                    i_t0: float = np.sqrt(2.0) * np.real(i_t)

                    self.set_if_exists(mdl=mdl, key=if_key, value=float(i_f0))
                    self.set_if_exists(mdl=mdl, key=it_key, value=float(i_t0))
            else:
                pass

        self.set_if_exists(mdl=mdl, key=VarPowerFlowRefferenceType.Pf, value=float(np.real(sf_sum)))
        self.set_if_exists(mdl=mdl, key=VarPowerFlowRefferenceType.Qf, value=float(np.imag(sf_sum)))
        self.set_if_exists(mdl=mdl, key=VarPowerFlowRefferenceType.Pt, value=float(np.real(st_sum)))
        self.set_if_exists(mdl=mdl, key=VarPowerFlowRefferenceType.Qt, value=float(np.imag(st_sum)))

    def _try_set_inj_pf_init(self, mdl: Block, bus_index: int, pf_results: PowerFlowResults3Ph, sbase: float) -> None:
        """
        Initialize injection variables from three-phase power-flow results.

        The method initializes any per-phase current and power variables that are
        present in the model external mapping. It also initializes the aggregated
        active and reactive powers and, if available, the positive-sequence angle.

        :param mdl: Injection symbolic block.
        :param bus_index: Bus index in the power-flow results.
        :param pf_results: Three-phase power-flow results.
        :param sbase: Base power of the grid.
        :return: None
        """
        Sbus_total: complex = 0.0 + 0.0j

        phase_specs: List[Tuple[
            str, Any, Any, VarPowerFlowRefferenceType, VarPowerFlowRefferenceType, VarPowerFlowRefferenceType]] = [
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
            uses_any: bool = (
                    (mdl.E(i_key) is not None)
                    or (mdl.E(P_key) is not None)
                    or (mdl.E(Q_key) is not None)
            )

            if uses_any:
                if S_arr is None or V_arr is None:
                    self.set_if_exists(mdl=mdl, key=i_key, value=0.0)
                    self.set_if_exists(mdl=mdl, key=P_key, value=0.0)
                    self.set_if_exists(mdl=mdl, key=Q_key, value=0.0)
                else:
                    S = S_arr[bus_index] / sbase
                    V = V_arr[bus_index]

                    if V == 0:
                        I = 0.0 + 0.0j
                    else:
                        I = np.conj(S / V)

                    i0: float = np.sqrt(2.0) * np.real(I)

                    self.set_if_exists(mdl=mdl, key=i_key, value=float(i0))
                    self.set_if_exists(mdl=mdl, key=P_key, value=float(np.real(S)))
                    self.set_if_exists(mdl=mdl, key=Q_key, value=float(np.imag(S)))

                    Sbus_total += S
            else:
                pass

        if mdl.E(VarPowerFlowRefferenceType.theta) is not None:
            VA = pf_results.voltage_A[bus_index]
            VB = pf_results.voltage_B[bus_index]
            VC = pf_results.voltage_C[bus_index]

            a = np.exp(1j * 2.0 * np.pi / 3.0)
            V1 = (1.0 / 3.0) * (VA + a * VB + (a * a) * VC)
            theta: float = np.angle(V1)

            self.set_init_guess(mdl, VarPowerFlowRefferenceType.theta, float(theta))
        else:
            pass

        self.set_if_exists(mdl=mdl, key=VarPowerFlowRefferenceType.P, value=float(np.real(Sbus_total)))
        self.set_if_exists(mdl=mdl, key=VarPowerFlowRefferenceType.Q, value=float(np.imag(Sbus_total)))
    # ---------------------------------------------------------------------
    # UTILS
    # ---------------------------------------------------------------------
    def set_if_exists(self,
                      mdl: Block,
                      key: VarPowerFlowRefferenceType,
                      value: float) -> None:
        """
        Set an initialization value only if the external mapping contains the key.

        :param mdl: Model block containing the external mapping.
        :param key: External mapping key.
        :param value: Initialization value.
        :return: None
        """
        external_mapping: Optional[Dict[Any, Var]] = _get_external_mapping(mdl)

        if external_mapping is None:
            pass
        else:
            mapped_var: Optional[Var] = external_mapping.get(key, None)

            if mapped_var is None:
                pass
            else:
                self._temp_init_guess[mapped_var.uid] = float(value)

    def _collect_runtime_mode_parameters(self) -> List[Var]:
        """
        Collect runtime parameters that should be classified as retained mode parameters.

        :return: List of retained mode runtime parameters.
        """
        mode_parameters: List[Var] = list()

        for parameter in self.get_variable_parameters():
            if _is_mode_runtime_parameter(parameter):
                mode_parameters.append(parameter)
            else:
                pass

        return mode_parameters

    def _initialize_mode_event_state(self) -> None:
        """
        Initialize the mode event cursor state.

        :return: None
        """
        for uid, event_list in self._scheduled_mode_events.items():
            event_list.sort(key=_get_mode_event_sort_key)
            self._mode_event_cursor[uid] = 0

    def _apply_scheduled_mode_events(self, t_curr: float, full_params: np.ndarray) -> None:
        """
        Apply scheduled retained mode events to the flat full parameter vector.

        :param t_curr: Current simulation time.
        :param full_params: Flat full parameter vector.
        :return: None
        """
        for uid, event_list in self._scheduled_mode_events.items():
            event_idx: int = self._mode_event_cursor.get(uid, 0)

            while event_idx < len(event_list) and t_curr >= event_list[event_idx][0]:
                event_time: float = event_list[event_idx][0]
                event_value: float = event_list[event_idx][1]
                force_step_alignment: bool = event_list[event_idx][2]

                runtime_idx: Optional[int] = self.uid2idx_event_params.get(uid, None)
                is_time_aligned: bool = self._is_time_aligned(t_curr, event_time)

                if force_step_alignment:
                    if is_time_aligned:
                        if runtime_idx is not None:
                            full_params[runtime_idx] = event_value
                        else:
                            pass
                    else:
                        raise RuntimeError(
                            f"Scheduled EMT mode event at t={event_time} requires exact step alignment, "
                            f"but current solver time is t={t_curr}. Adjust the EMT time step or enable step splitting."
                        )
                else:
                    if runtime_idx is not None:
                        full_params[runtime_idx] = event_value
                    else:
                        pass

                event_idx += 1

            self._mode_event_cursor[uid] = event_idx

    def add_device_var(self, dev: ALL_DEV_TYPES, var: Var)->None:
        """
        Registers a variable belonging to a specific device.
        """
        var_list = self._vars_info.get(dev, None)
        if var_list is None:
            self._vars_info[dev] = [var]
        else:
            var_list.append(var)

    def set_init_guess(self, mdl: Block, reference_powerflow: Any, val: float) -> None:
        """
        Set the temporary initial guess for a mapped variable during the parsing phase.

        :param mdl: Model block containing the external mapping.
        :param reference_powerflow: Reference key used to locate the mapped variable.
        :param val: Initialization value.
        :return: None
        """
        external_mapping: Optional[Dict[Any, Var]] = _get_external_mapping(mdl)

        if external_mapping is None:
            pass
        else:
            var: Optional[Var] = external_mapping.get(reference_powerflow, None)

            if var is None:
                pass
            else:
                self._temp_init_guess[var.uid] = float(val)

    def set_diff_init_guess(self, mdl: Block, reference_powerflow: Any, val: float) -> None:
        """
        Set the temporary initial guess for a mapped differential variable during the parsing phase.

        :param mdl: Model block containing the external mapping.
        :param reference_powerflow: Reference key used to locate the mapped differential variable.
        :param val: Initialization value.
        :return: None
        """
        external_mapping: Optional[Dict[Any, Var]] = _get_external_mapping(mdl)

        if external_mapping is None:
            pass
        else:
            diff_var: Optional[Var] = external_mapping.get(reference_powerflow, None)

            if diff_var is None:
                pass
            else:
                self._temp_diff_init_guess[diff_var.uid] = float(val)

    def get_init_guess_info(self) -> pd.DataFrame:
        """
        Return a table with the explicitly initialized variable guesses.

        :return: DataFrame with UID, variable name and initialization value.
        """
        rows: List[Dict[str, Any]] = list()
        all_vars: Dict[int, Var] = dict()

        for var in self._state_vars:
            all_vars[var.uid] = var

        for var in self._algebraic_vars:
            all_vars[var.uid] = var

        for uid, value in self.init_guess.items():
            if uid in all_vars:
                rows.append({
                    "uid": uid,
                    "var_name": all_vars[uid].name,
                    "value": value,
                })
            else:
                pass

        return pd.DataFrame(rows)

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

    def emt_boundary_update(
            self,
            t_curr: float,
            x_prev: np.ndarray,
            full_params: np.ndarray
    ) -> None:
        """
        Update runtime boundaries before the Newton step.

        Retained mode events are applied first. Afterwards, history-dependent EMT
        models update their internal boundary data.

        :param t_curr: Current simulation time.
        :param x_prev: Previous accepted state vector.
        :param full_params: Flat full parameter vector.
        :return: None
        """
        self._apply_scheduled_mode_events(t_curr, full_params)

        for rt in self.history_models:
            rt.update_history(self.step_counter, x_prev, full_params)

        self.step_counter += 1

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> Optional[float]:
        """
        Return the earliest forced-alignment event time in the interval
        (t_prev, t_target].

        :param t_prev: Previous solver time.
        :param t_target: Nominal target time.
        :return: Earliest forced event time or None.
        """
        return _get_next_forced_mode_event_time(self._scheduled_mode_events, t_prev, t_target)

    def update(self, t: float, x: np.ndarray, params: np.ndarray) -> None:
        """
        Boundary update entry point compatible with BoundaryUpdateWrapper.

        :param t: Current simulation time.
        :param x: Previous accepted state vector.
        :param params: Flat full parameter vector.
        :return: None
        """
        self.emt_boundary_update(t, x, params)

    def get_floquet_ak_stack(
            self,
            trajectory: np.ndarray,
            h: float,
            jac_evaluator: Optional[Any] = None,
            static_params: Optional[np.ndarray] = None
    ) -> Optional[np.ndarray]:
        """
        Return the stack of reduced transition matrices used for Floquet analysis.

        :param trajectory: State trajectory over one period.
        :param h: Time step.
        :param jac_evaluator: Optional Jacobian evaluator.
        :param static_params: Optional static parameter vector.
        :return: Stack of reduced transition matrices or None.
        """
        if jac_evaluator is None:
            self.logger.add_warning(
                msg="No Jacobian evaluator was provided for Floquet Ak stack computation.",
                device="EmtProblemDae",
                value="None",
                expected_value="Callable Jacobian evaluator",
                device_class="EMT",
                device_property="jac_evaluator"
            )
            return None
        else:
            pass

        n = self.get_states_number()
        steps = len(trajectory) - 1

        if steps <= 0:
            return None

        stack = np.zeros((steps, n, n), order='C')

        for i in range(steps):
            x_k = trajectory[i]

            J = jac_evaluator(x_k, static_params, x_k, None, h, None)

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

        rows: List[Dict[str, Any]] = list()
        for vars_list, guess_dict, idx_map, vector, var_type in data_sets:
            for v in vars_list:
                uid = v.uid
                idx = idx_map.get(uid, None)
                val = float(vector[idx]) if idx is not None else 0.0

                in_guess = uid in guess_dict

                keep_row = True
                if only_in_init_guess and (not in_guess):
                    keep_row = False
                if (not include_all_vars) and (not in_guess):
                    keep_row = False

                if keep_row:
                    alias: Optional[str] = self._alias_names_dict.get(uid, None)

                    rows.append({
                        "uid": uid,
                        "type": var_type,
                        "idx": idx,  # add this
                        "alias": alias,
                        "name": v.name,
                        "value": val,
                        "in_init_guess": in_guess,
                        "is_zero": abs(val) <= tol_zero,
                    })
                else:
                    pass

        df = pd.DataFrame(rows)

        # Nice ordering: Group by type, then initialization status
        if not df.empty:
            df = df.sort_values(["type", "idx"], ascending=[False, True])

        return df
