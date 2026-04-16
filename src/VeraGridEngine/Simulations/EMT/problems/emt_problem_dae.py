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
from VeraGridEngine.Devices.Branches.transformer import Transformer2W
from VeraGridEngine.Simulations.driver_template import DummySignal
from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.Utils.Symbolic.symbolic import Var, piecewise, Const
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import (
    VarPowerFlowRefferenceType,
    ParamPowerFlowRefferenceType,
    DeviceType,
    EmtLineTypes,
    ConverterControlType,
    WindingType,
)
from VeraGridEngine.basic_structures import Logger, CxVec
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Templates.Emt.bergeron_line_emt_template import BergeronHistoryRuntime
from VeraGridEngine.Simulations.PowerFlow.power_flow_results_3ph import PowerFlowResults3Ph
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Simulations.EMT.initialization_emt import EmtInitializationReport, run_emt_native_initialization
from VeraGridEngine.Utils.Symbolic.explicit_initialization_symbolic import init_explicit_common, build_symbolic_vector_single_equation_compiler
from VeraGridEngine.Utils.Symbolic.compiled_functions import get_compiled_functions_cache_stats
from VeraGridEngine.Templates.Emt.bus_emt_template import get_bus_emt_algebraic_vars
from VeraGridEngine.IO.fmu.importer import (
    finalize_emt_fmu_cs_devices,
    finalize_emt_fmu_me_devices,
    queue_emt_fmu_cs_device,
    queue_emt_fmu_me_device,
)

from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import (
    EmtBoundaryUpdateProtocol,
    EmtProblemTemplate,
)


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


def _xfmr_connection_matrix(winding_tpe: WindingType) -> np.ndarray:
    """
    Return the 3x3 winding connection matrix used by the XFMR EMT template.

    :param winding_tpe: Transformer winding connection type.
    :return: 3x3 connection matrix in winding coordinates.
    """
    if winding_tpe in (WindingType.GroundedStar, WindingType.NeutralStar, WindingType.FloatingStar):
        return np.eye(3, dtype=float)
    else:
        if winding_tpe == WindingType.Delta:
            return np.array([
                [1.0, 0.0, -1.0],
                [-1.0, 1.0, 0.0],
                [0.0, -1.0, 1.0],
            ], dtype=float) / np.sqrt(3.0)
        else:
            return np.eye(3, dtype=float)


def _xfmr_phase_permutation_matrix(clock: int) -> np.ndarray:
    """
    Return the phase permutation matrix implied by the transformer vector group.

    :param clock: Transformer vector group clock number.
    :return: 3x3 phase permutation matrix.
    """
    shift: int = (int(clock) // 4) % 3
    if shift == 0:
        return np.eye(3, dtype=float)
    else:
        if shift == 1:
            return np.array([
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
                [1.0, 0.0, 0.0],
            ], dtype=float)
        else:
            return np.array([
                [0.0, 0.0, 1.0],
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
            ], dtype=float)


class EmtTopologyError(Exception):
    """
    Exception raised when EMT topology validation fails.
    This includes orphaned in_vars/out_vars and floating bus phases.
    """

    def __init__(self, message: str):
        """
        :param message: Descriptive error message indicating the topology issue.
        """
        self.message = message
        super().__init__(self.message)


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
    return bool(abs(t_curr - event_time) <= time_tol)

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

    return grid.emt_events

def _get_bus_v_list(
        grid: MultiCircuit,
        bus_block: Block,
        ph_v_keys: List[VarPowerFlowRefferenceType]
) -> List[Any]:
    """
    Return the ordered list of bus phase voltages, using None for missing phases.

    :param grid: MultiCircuit instance.
    :param bus_block: Bus symbolic block.
    :param ph_v_keys: Ordered list of phase voltage keys.
    :return: Ordered list of bus phase voltage expressions or None.
    """
    out: List[Any] = list()

    for key in ph_v_keys:
        vk = bus_block.E(key)

        if vk is None:
            out.append(None)
        else:
            out.append(vk)

    return out

def _get_external_mapping(mdl: Block) -> Optional[Dict[Any, Var]]:
    external_mapping: Optional[Dict[Any, Var]] = mdl.external_mapping
    if external_mapping is None:
        return None
    else:
        return external_mapping

# USE AS REFERENCE TO VALIDATE THAT ALL MODELS HAVE THE SAME NUMBER OF PHASES THAN THE STATIC DEVICES!
# def _get_expected_pi_line_terminal_refs(ph_mask: List[bool]) -> List[VarPowerFlowRefferenceType]:
#     """
#     Build the ordered terminal-voltage references for the active pi-line phases.
#
#     :param ph_mask: Physical line phase mask in NABC order.
#     :return: Ordered ``vf_*`` and ``vt_*`` references for the active phases only.
#     """
#     vf_refs: List[VarPowerFlowRefferenceType] = list([
#         VarPowerFlowRefferenceType.vf_N,
#         VarPowerFlowRefferenceType.vf_A,
#         VarPowerFlowRefferenceType.vf_B,
#         VarPowerFlowRefferenceType.vf_C,
#     ])
#     vt_refs: List[VarPowerFlowRefferenceType] = list([
#         VarPowerFlowRefferenceType.vt_N,
#         VarPowerFlowRefferenceType.vt_A,
#         VarPowerFlowRefferenceType.vt_B,
#         VarPowerFlowRefferenceType.vt_C,
#     ])
#
#     ordered_refs: List[VarPowerFlowRefferenceType] = list()
#
#     for idx, is_active in enumerate(ph_mask):
#         if is_active:
#             ordered_refs.append(vf_refs[idx])
#         else:
#             pass
#
#     for idx, is_active in enumerate(ph_mask):
#         if is_active:
#             ordered_refs.append(vt_refs[idx])
#         else:
#             pass
#
#     return ordered_refs
#
#
# def _normalize_pi_line_phase_layout(branch: Any, grid: MultiCircuit) -> None:
#     """
#     Rebuild the standard pi-line template when its symbolic phase layout does not
#     match the physical branch connection mask.
#
#     The EMT parameter mapper writes reduced branch matrices into the fixed NABC
#     API map using ``branch.ys``. After the recent API change, callers can create
#     a pi-line template with a phase mask that does not match ``branch.ys``. When
#     that happens, the symbolic block keeps terminal inputs for non-existent bus
#     phases and later substitutions introduce ``None`` or unresolved UIDs.
#
#     This helper keeps the public explicit-mask API in place, but re-aligns the
#     standard pi-line block with the physical branch mask right before the EMT
#     problem flattens the device into the global system.
#
#     :param branch: Grid branch device.
#     :param grid: Parent circuit, used for the shared variable factory.
#     :return: None.
#     """
#     mdl: Any = branch.emt_model
#     api_obj_mapping: Any = mdl.api_obj_mapping
#
#     if not isinstance(api_obj_mapping, dict):
#         return
#     else:
#         pass
#
#     if ParamPowerFlowRefferenceType.Rnn not in api_obj_mapping:
#         return
#     else:
#         pass
#
#     ph_mask: List[bool] = list([
#         bool(branch.ys.phN),
#         bool(branch.ys.phA),
#         bool(branch.ys.phB),
#         bool(branch.ys.phC),
#     ])
#     expected_refs: List[VarPowerFlowRefferenceType] = _get_expected_pi_line_terminal_refs(ph_mask)
#     tracked_refs: Set[VarPowerFlowRefferenceType] = set([
#         VarPowerFlowRefferenceType.vf_N,
#         VarPowerFlowRefferenceType.vf_A,
#         VarPowerFlowRefferenceType.vf_B,
#         VarPowerFlowRefferenceType.vf_C,
#         VarPowerFlowRefferenceType.vt_N,
#         VarPowerFlowRefferenceType.vt_A,
#         VarPowerFlowRefferenceType.vt_B,
#         VarPowerFlowRefferenceType.vt_C,
#     ])
#     current_refs: List[VarPowerFlowRefferenceType] = list()
#
#     for in_var in mdl.in_vars:
#         if in_var.ref in tracked_refs:
#             current_refs.append(in_var.ref)
#         else:
#             pass
#
#     if current_refs != expected_refs:
#         branch.emt_model = get_pi_line_emt_template(
#             vf=grid.var_factory,
#             phN=ph_mask[0],
#             phA=ph_mask[1],
#             phB=ph_mask[2],
#             phC=ph_mask[3],
#             name=mdl.name,
#         ).block
#     else:
#         pass


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
                 pf_results_3ph: PowerFlowResults3Ph | None = None,
                 pf_results: PowerFlowResults | None = None,
                 progress_signal: DummySignal | None = None,
                 progress_text: DummySignal | None = None, )-> None:
        """
        Initializes the EMT Problem by parsing the grid and passing the
        resulting mathematical block to the BaseProblem constructor.
        :param grid:
        :param options:
        :param pf_results_3ph:
        :param pf_results:
        """
        self.logger = Logger()
        self.grid = grid
        self.options = options
        self.power_flow_results_3ph = pf_results_3ph
        self.power_flow_results = pf_results

        self._vars_info: Dict[ALL_DEV_TYPES, List[Var]] = dict()
        self._vars_glob_name2uid: Dict[str, int] = dict()
        self._vars2device: Dict[int, ALL_DEV_TYPES] = dict()
        self._temp_init_guess: Dict[int, float] = dict()
        self._temp_diff_init_guess: Dict[int, float] = dict()
        self.initialization_report: EmtInitializationReport | None = None
        self.build_report: Dict[str, float] = dict()

        self._scheduled_mode_events: Dict[int, List[Tuple[float, float, bool]]] = dict()
        self._mode_event_cursor: Dict[int, int] = dict()
        self._runtime_parameter_eqs0: List[Any] = list()
        self._event_parameter_device_idtags: Dict[int, str] = dict()
        self._continuous_event_parameter_uids: Set[int] = set()
        self._discrete_event_parameter_uids: Set[int] = set()
        self._active_events_group: EmtEventsGroup | None = None

        # for init_explicit
        self._models_with_init_eqs: List[Block] = []
        self._models_with_diff_init_eqs: List[Block] = []
        self._models_with_init_eqs_seen: Set[int] = set()
        self._models_with_diff_init_eqs_seen: Set[int] = set()

        sys_block = Block(children=[], in_vars=[])
        glob_time = Var(self.TIME_NAME)

        self.history_models: List[BergeronHistoryRuntime] = list()
        self.step_counter: int = 0
        self._fmu_cs_adapters: List[Any] = list()
        self._pending_fmu_cs_devices: List[Tuple[Any, Block]] = list()
        self._fmu_me_adapters: List[Any] = list()
        self._pending_fmu_me_devices: List[Tuple[Any, Block]] = list()

        t_build = _tic()
        t_phase_start: float = t_build
        cache_stats_before: Dict[str, float] = get_compiled_functions_cache_stats()

        validate_models_s: float = _toc(t_phase_start)
        t_phase_start = _tic()

        # build on local sys_block
        self._build_structure_and_collect(sys_block, grid, glob_time)
        structure_collect_s: float = _toc(t_phase_start)
        t_phase_start = _tic()

        sys_block.unify_blocks()
        _deduplicate_block_entities(sys_block)
        unify_blocks_s: float = _toc(t_phase_start)
        t_phase_start = _tic()

        self._validate_connections()
        validate_connections_s: float = _toc(t_phase_start)
        t_phase_start = _tic()

        # initialize template with the complete block
        super().__init__(sys_block=sys_block, glob_time=glob_time, progress_signal=progress_signal,
                         progress_text=progress_text)
        template_init_s: float = _toc(t_phase_start)
        t_phase_start = _tic()

        # Mark retained runtime parameters:
        #   - scheduled mode parameters
        #   - Bergeron history parameters
        mode_parameters: List[Var] = self._collect_runtime_mode_parameters()
        if len(mode_parameters) > 0:
            self.set_runtime_mode_parameters(mode_parameters)
        else:
            pass

        # Runtime parameter indices may have changed after repartitioning,
        # so Bergeron runtimes must bind their parameter indices afterwards.
        for rt in self.history_models:
            rt.setup_indices(
                uid2idx_vars=self.uid2idx_vars,
                uid2idx_event_params=self.uid2idx_event_params,
                params_offset=0,
            )

        self._runtime_parameter_eqs0 = list(self._runtime_all_eqs_source)
        finalize_emt_fmu_cs_devices(self)
        finalize_emt_fmu_me_devices(self)

        if len(self._runtime_mode_parameters) > 0:
            self._initialize_mode_event_state()
        else:
            pass
        runtime_partition_s: float = _toc(t_phase_start)
        t_phase_start = _tic()

        # 1) PF guesses update
        self.init_guess.update(self._temp_init_guess)
        self.diff_init_guess.update(self._temp_diff_init_guess)
        if self.progress_signal is not None:
            self.progress_signal.emit(10)

        # 2) explicit init guesses initialization
        self._run_explicit_initialization()
        explicit_init_s: float = _toc(t_phase_start)
        t_phase_start = _tic()
        self.initialization_report = run_emt_native_initialization(problem=self, options=self.options)
        native_init_s: float = _toc(t_phase_start)
        t_phase_start = _tic()

        if self.progress_signal is not None:
            self.progress_signal.emit(20)

        # EMT event groups are activated only after the initialization stage.
        # Some runtime parameters start as Const(None) placeholders and are
        # resolved during explicit/native initialization. Wrapping them in
        # piecewise expressions before that would preserve the undefined default
        # and break the initial runtime-parameter evaluation.
        self.set_events_group(None)
        events_group_finalize_s: float = _toc(t_phase_start)

        t_done = _toc(t_build)
        cache_stats_after: Dict[str, float] = get_compiled_functions_cache_stats()
        compiled_function_cache_delta: float = cache_stats_after.get("entry_count", 0.0) - cache_stats_before.get("entry_count", 0.0)
        native_structural_cold_s: float = 0.0
        native_numeric_refresh_s: float = 0.0

        if self.initialization_report is None:
            native_structural_cold_s = 0.0
            native_numeric_refresh_s = 0.0
        else:
            native_structural_cold_s = float(self.initialization_report.reduced_system_build_s)
            native_numeric_refresh_s = (
                float(self.initialization_report.runtime_param_build_s)
                + float(self.initialization_report.constant_param_build_s)
                + float(self.initialization_report.initial_residual_eval_s)
                + float(self.initialization_report.newton_elapsed_s)
                + float(self.initialization_report.pseudo_transient_elapsed_s)
                + float(self.initialization_report.dx0_completion_s)
            )

        structural_cold_s: float = (
            validate_models_s
            + structure_collect_s
            + unify_blocks_s
            + validate_connections_s
            + template_init_s
            + runtime_partition_s
            + explicit_init_s
            + native_structural_cold_s
        )
        numeric_refresh_s: float = native_numeric_refresh_s + events_group_finalize_s

        self.build_report = dict(
            validate_models_s=validate_models_s,
            structure_collect_s=structure_collect_s,
            unify_blocks_s=unify_blocks_s,
            validate_connections_s=validate_connections_s,
            template_init_s=template_init_s,
            runtime_partition_s=runtime_partition_s,
            explicit_init_s=explicit_init_s,
            native_init_s=native_init_s,
            events_group_finalize_s=events_group_finalize_s,
            structural_cold_s=structural_cold_s,
            numeric_refresh_s=numeric_refresh_s,
            native_structural_cold_s=native_structural_cold_s,
            native_numeric_refresh_s=native_numeric_refresh_s,
            compiled_function_cache_delta=compiled_function_cache_delta,
            persistent_init_cache_hit=1.0 if (self.initialization_report is not None and self.initialization_report.persistent_cache_hit) else 0.0,
            persistent_init_cache_load_s=0.0 if self.initialization_report is None else float(self.initialization_report.persistent_cache_load_s),
            persistent_init_cache_store_s=0.0 if self.initialization_report is None else float(self.initialization_report.persistent_cache_store_s),
            total_s=t_done,
        )

        if options.verbose > 0:
            self.logger.add_debug(f"init guess = {self.init_guess}")
            self.logger.add_debug(f"diff init guess = {self.diff_init_guess}")
            if self.initialization_report is None:
                pass
            else:
                self.logger.add_debug(
                    f"EMT initialization used {self.initialization_report.method_used} | "
                    f"status={self.initialization_report.status.name} | "
                    f"res0={self.initialization_report.initial_residual_inf:.3e} | "
                    f"resf={self.initialization_report.final_residual_inf:.3e} | "
                    f"newton={self.initialization_report.newton_iterations} | "
                    f"ptc={self.initialization_report.pseudo_transient_steps} | "
                    f"auto_dx0={self.initialization_report.automatic_dx0_count}"
                )
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

    def get_build_report(self) -> Dict[str, float]:
        """
        Return the EMT problem build timing report.

        :return: Build timing report.
        :rtype: Dict[str, float]
        """
        return dict(self.build_report)

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


        :return: None
        """

        if len(self._models_with_init_eqs) == 0 and len(self._models_with_diff_init_eqs) == 0:
            return

        # sys_vars dict (uid -> Var), size = n_vars
        sys_vars: Dict[int, Var] = {v.uid: v for v in (self._state_vars + self._algebraic_vars)}
        sys_diff_vars: Dict[int, Var] = {dv.uid: dv for dv in self._diff_vars}
        compile_single_equation = build_symbolic_vector_single_equation_compiler(
            compiler_names_dict=self._compiler_names_dict,
            alias_names_dict=self._alias_names_dict,
            vars_name=self.VARS_NAME,
            diff_name=self.DIFF_NAME,
            event_params_name=self.VARIABLE_PARAMS_NAME,
            params_name=self.CONSTANT_PARAMS_NAME,
        )

        seen_blocks: set[int] = set()

        for mdl in chain(self._models_with_init_eqs, self._models_with_diff_init_eqs):
            mdl_id = id(mdl)

            if mdl_id not in seen_blocks:
                seen_blocks.add(mdl_id)

                try:
                    params_array: np.ndarray = np.zeros(len(self._constant_parameters))

                    for param, const in mdl.parameters.items():
                        param_idx: int | None = self.uid2idx_params.get(param.uid, None)

                        if param_idx is None:
                            params_array = params_array
                        else:
                            params_array[param_idx] = const.value

                    self.init_guess, self.diff_init_guess = init_explicit_common(
                        mdl=mdl,
                        sys_vars=sys_vars,
                        sys_diff_vars=sys_diff_vars,
                        variable_parameters=self._variable_parameters,
                        event_parameters_eqs=self._event_parameters_eqs,
                        constant_parameters=self._constant_parameters,
                        init_guess=self.init_guess,
                        diff_init_guess=self.diff_init_guess,
                        uid2idx_vars=self.uid2idx_vars,
                        uid2idx_diff=self.uid2idx_diff,
                        uid2idx_params=self.uid2idx_params,
                        uid2idx_event_params=self.uid2idx_event_params,
                        params_array=params_array,
                        compile_single_equation=compile_single_equation,
                        verbose=bool(self.options.verbose > 0),
                    )


                    for event_var in mdl.event_dict.keys():
                        event_idx: int | None = self.uid2idx_event_params.get(event_var.uid, None)

                        if event_idx is None:
                            mdl.event_dict[event_var] = mdl.event_dict[event_var]
                        else:
                            mdl.event_dict[event_var] = self._event_parameters_eqs[event_idx]
                            self._runtime_parameter_eqs0[event_idx] = self._event_parameters_eqs[event_idx]
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
                            f"[EMT][init_explicit] failed for block '{block_name}'. Error: {error_detail}"
                        )

                        print(
                            f"EMT explicit initialization failed for block {block_name}. "
                            f"Error detail: {error_detail}"
                        )


        self._build_runtime_param_vectors()

    def _validate_connections(self) -> None:
        """
        Validate EMT topology connectivity.

        Checks that each phase exposed by a bus must be connected to at least 2 elements
        (branches or injections). A floating phase indicates an open circuit.

        The phase connection mapping is:
        - Branch in_vars with ref vf_N/A/B/C connect to bus_from's v_N/A/B/C
        - Branch in_vars with ref vt_N/A/B/C connect to bus_to's v_N/A/B/C
        - Injection device in_vars with ref v_N/A/B/C connect to their bus's v_N/A/B/C

        :raises EmtTopologyError: If topology inconsistencies are found.
        """
        phase_ref_to_bus_phase = {
            VarPowerFlowRefferenceType.vf_N: VarPowerFlowRefferenceType.v_N,
            VarPowerFlowRefferenceType.vf_A: VarPowerFlowRefferenceType.v_A,
            VarPowerFlowRefferenceType.vf_B: VarPowerFlowRefferenceType.v_B,
            VarPowerFlowRefferenceType.vf_C: VarPowerFlowRefferenceType.v_C,
            VarPowerFlowRefferenceType.vt_N: VarPowerFlowRefferenceType.v_N,
            VarPowerFlowRefferenceType.vt_A: VarPowerFlowRefferenceType.v_A,
            VarPowerFlowRefferenceType.vt_B: VarPowerFlowRefferenceType.v_B,
            VarPowerFlowRefferenceType.vt_C: VarPowerFlowRefferenceType.v_C,
        }

        branch_phase_refs = {
            VarPowerFlowRefferenceType.vf_N,
            VarPowerFlowRefferenceType.vf_A,
            VarPowerFlowRefferenceType.vf_B,
            VarPowerFlowRefferenceType.vf_C,
            VarPowerFlowRefferenceType.vt_N,
            VarPowerFlowRefferenceType.vt_A,
            VarPowerFlowRefferenceType.vt_B,
            VarPowerFlowRefferenceType.vt_C,
        }

        ac_phases = [
            VarPowerFlowRefferenceType.v_N,
            VarPowerFlowRefferenceType.v_A,
            VarPowerFlowRefferenceType.v_B,
            VarPowerFlowRefferenceType.v_C,
        ]

        bus_phase_connections: Dict[Tuple[Any, VarPowerFlowRefferenceType], Set[str]] = dict()
        for bus in self.grid.buses:
            for phase in ac_phases:
                bus_phase_connections[(bus, phase)] = set()

        vsc_ac_phase_refs = {
            VarPowerFlowRefferenceType.v_A,
            VarPowerFlowRefferenceType.v_B,
            VarPowerFlowRefferenceType.v_C,
        }

        for br in self.grid.get_branches_iter(add_vsc=True, add_hvdc=True, add_switch=True):
            try:
                br_emt_model = br.emt_model
            except AttributeError:
                br_emt_model = None

            if br_emt_model is not None:
                try:
                    br_bus_from = br.bus_from
                    br_bus_to = br.bus_to
                except AttributeError:
                    pass
                else:
                    is_bergeron = br_emt_model.name == EmtLineTypes.Bergeron.value

                    if is_bergeron:
                        try:
                            br_ys = br.ys
                        except AttributeError:
                            br_ys = None

                        if br_ys is not None:
                            if br_ys.phN:
                                bus_phase_connections[(br_bus_from, VarPowerFlowRefferenceType.v_N)].add(f"branch_from:{br.name}")
                                bus_phase_connections[(br_bus_to, VarPowerFlowRefferenceType.v_N)].add(f"branch_to:{br.name}")
                            else:
                                pass

                            if br_ys.phA:
                                bus_phase_connections[(br_bus_from, VarPowerFlowRefferenceType.v_A)].add(f"branch_from:{br.name}")
                                bus_phase_connections[(br_bus_to, VarPowerFlowRefferenceType.v_A)].add(f"branch_to:{br.name}")
                            else:
                                pass

                            if br_ys.phB:
                                bus_phase_connections[(br_bus_from, VarPowerFlowRefferenceType.v_B)].add(f"branch_from:{br.name}")
                                bus_phase_connections[(br_bus_to, VarPowerFlowRefferenceType.v_B)].add(f"branch_to:{br.name}")
                            else:
                                pass

                            if br_ys.phC:
                                bus_phase_connections[(br_bus_from, VarPowerFlowRefferenceType.v_C)].add(f"branch_from:{br.name}")
                                bus_phase_connections[(br_bus_to, VarPowerFlowRefferenceType.v_C)].add(f"branch_to:{br.name}")
                            else:
                                pass
                        else:
                            pass
                    else:
                        for in_var in br_emt_model.in_vars:
                            if in_var.ref in branch_phase_refs:
                                bus_phase = phase_ref_to_bus_phase[in_var.ref]

                                if in_var.ref in {
                                    VarPowerFlowRefferenceType.vf_N,
                                    VarPowerFlowRefferenceType.vf_A,
                                    VarPowerFlowRefferenceType.vf_B,
                                    VarPowerFlowRefferenceType.vf_C,
                                }:
                                    bus_phase_connections[(br_bus_from, bus_phase)].add(f"branch_from:{br.name}")
                                elif in_var.ref in {
                                    VarPowerFlowRefferenceType.vt_N,
                                    VarPowerFlowRefferenceType.vt_A,
                                    VarPowerFlowRefferenceType.vt_B,
                                    VarPowerFlowRefferenceType.vt_C,
                                }:
                                    bus_phase_connections[(br_bus_to, bus_phase)].add(f"branch_to:{br.name}")
                                else:
                                    pass
                            elif in_var.ref in vsc_ac_phase_refs:
                                if br_bus_to.is_dc:
                                    bus_phase_connections[(br_bus_from, in_var.ref)].add(f"branch_from:{br.name}")
                                else:
                                    bus_phase_connections[(br_bus_to, in_var.ref)].add(f"branch_to:{br.name}")
                            else:
                                pass
            else:
                pass

        for inj in self.grid.get_injection_devices_iter():
            try:
                inj_emt_model = inj.emt_model
            except AttributeError:
                inj_emt_model = None

            if inj_emt_model is not None:
                try:
                    inj_bus = inj.bus
                except AttributeError:
                    pass
                else:
                    for in_var in inj_emt_model.in_vars:
                        if in_var.ref in ac_phases:
                            bus_phase_connections[(inj_bus, in_var.ref)].add(f"injection:{inj.name}")
                        else:
                            pass
            else:
                pass

        floating_phases: List[str] = list()
        for bus in self.grid.buses:
            if not bus.is_dc:
                bus_out_refs = {v.ref for v in bus.emt_model.out_vars}
                for phase in ac_phases:
                    connections = bus_phase_connections.get((bus, phase), set())
                    if phase in bus_out_refs and len(connections) < 2:
                        floating_phases.append(
                            f"  - Bus '{bus.name}' phase '{phase.value}' is floating "
                            f"(connected to {len(connections)} element(s): {connections})"
                        )
                    else:
                        pass
            else:
                pass

        if floating_phases:
            error_msg = (
                "TopologyError: Floating bus phases detected "
                "(each phase must be connected to at least 2 elements):\n"
            )
            error_msg += "\n".join(floating_phases)
            raise EmtTopologyError(error_msg)
        else:
            pass

    def _process_device_model(self, dev: Any, sys_block: Block, grid: MultiCircuit, glob_time: Var) -> Block:
        """
        Register a device EMT model into the global system block.

        The device model is flattened before being attached to the system block.
        Some wrapper-style models store ``api_obj_mapping`` in nested child blocks,
        while ``unify_blocks()`` does not propagate that metadata to the top-level
        block. For that reason, the mapping is rebuilt first and restored on the
        device block before flattening.

        :param dev: Device object from the grid.
        :param sys_block: Main DAE system block.
        :param grid: MultiCircuit instance.
        :param glob_time: Global time variable.
        :return: Unified device block.
        """
        mdl: Block = dev.emt_model

        resolved_api_mapping: Dict[ParamPowerFlowRefferenceType, Any] = self._collect_api_obj_mapping(mdl)
        if len(resolved_api_mapping) > 0:
            mdl.api_obj_mapping = resolved_api_mapping
        else:
            pass

        mdl.unify_blocks()

        self._register_runtime_event_parameters(dev=dev, mdl=mdl)
        self._add_model_to_system_mappings(dev, mdl)
        queue_emt_fmu_cs_device(self, dev, mdl)
        queue_emt_fmu_me_device(self, dev, mdl)
        sys_block.add(mdl)

        self._register_init_model(mdl)
        self._register_diff_init_model(mdl)

        return mdl

    def _collect_api_obj_mapping(self, mdl: Block) -> Dict[ParamPowerFlowRefferenceType, Any]:
        """
        Collect the API object mapping from a block hierarchy.

        Wrapper models may keep the parameter mapping in nested child blocks.
        This method traverses the hierarchy and merges the first occurrence
        of each mapping key so the top-level block preserves the metadata
        required by PF-derived parameter assignment.

        :param mdl: Root block to inspect.
        :return: Flattened API object mapping.
        """
        mapping: Dict[ParamPowerFlowRefferenceType, Any] = dict()
        stack: List[Block] = list([mdl])
        visited: Set[int] = set()

        while len(stack) > 0:
            block: Block = stack.pop()
            block_id: int = id(block)

            if block_id not in visited:
                visited.add(block_id)

                local_mapping: Any = block.api_obj_mapping
                if isinstance(local_mapping, dict):
                    for key, val in local_mapping.items():
                        if key not in mapping:
                            mapping[key] = val
                        else:
                            pass
                else:
                    pass

                for child in block.children:
                    stack.append(child)
            else:
                pass

        return mapping

    def _to_const(self, value: Any) -> Const:
        """
        Convert a numeric value into a ``Const`` symbolic expression.

        :param value: Numeric or already-constant value.
        :return: Constant symbolic expression.
        """
        if isinstance(value, Const):
            return value
        else:
            return Const(float(value))

    def _assign_api_obj_param_if_present(
            self,
            mdl: Block,
            key: ParamPowerFlowRefferenceType,
            value: Any
    ) -> None:
        """
        Assign a mapped model parameter when the mapping key exists.

        Some device models do not expose every optional API mapping entry.
        This method performs a defensive assignment and keeps the original
        semantics of silently skipping unavailable parameters.

        :param mdl: Device symbolic block.
        :param key: Parameter mapping key.
        :param value: Value to assign.
        :return: None.
        """
        api_obj_mapping: Any = mdl.api_obj_mapping

        if isinstance(api_obj_mapping, dict):
            target: Any | None = api_obj_mapping.get(key, None)

            if target is not None:
                mdl.parameters[target] = self._to_const(value)
            else:
                pass
        else:
            pass
    # ---------------------------------------------------------------------
    # BUILD STRUCTURE
    # ---------------------------------------------------------------------
    def _build_structure_and_collect(
            self,
            sys_block: Block,
            grid: MultiCircuit,
            glob_time: Var
    ) -> None:
        """
        Build the EMT system structure and collect all algebraic KCL equations.

        This routine assembles the EMT nodal equations in abc coordinates.
        The unknowns are the bus phase voltages and the algebraic equations
        are the KCL balances at each bus-phase.

        The function preserves the original sign conventions:
        - Branch currents are defined as leaving the bus, therefore they are
          subtracted from the KCL accumulator.
        - Injection currents are defined as entering the bus, therefore they are
          added to the KCL accumulator.

        :param sys_block: Block containing the full system DAE.
        :param grid: Network model to assemble.
        :param glob_time: Global simulation time variable.
        :return: None.
        """
        # Stage 1: prepare the shared nodal assembly context used by every device loop.
        (
            bus_dict,
            I_kcl,
            ph_v_keys,
            inj_i_keys,
            br_if_keys,
            br_it_keys,
            br_vf_keys,
            br_vt_keys,
            h,
            sbase,
            fbase,
            vsc_idx_dict,
        ) = self._prepare_structure_collect_context(grid=grid)

        # Stage 2: branches define network couplings first, including Bergeron history runtimes.
        for branch_idx, br in enumerate(grid.get_branches_iter(add_vsc=True, add_hvdc=True, add_switch=True)):
            self._process_structure_branch(
                branch_idx=branch_idx,
                br=br,
                sys_block=sys_block,
                grid=grid,
                glob_time=glob_time,
                bus_dict=bus_dict,
                I_kcl=I_kcl,
                ph_v_keys=ph_v_keys,
                inj_i_keys=inj_i_keys,
                br_if_keys=br_if_keys,
                br_it_keys=br_it_keys,
                br_vf_keys=br_vf_keys,
                br_vt_keys=br_vt_keys,
                h=h,
                sbase=sbase,
                fbase=fbase,
                vsc_idx_dict=vsc_idx_dict,
            )

        # Stage 3: injections contribute source currents and receive bus-voltage substitutions.
        for inj in grid.get_injection_devices_iter():
            self._process_structure_injection(
                inj=inj,
                sys_block=sys_block,
                grid=grid,
                glob_time=glob_time,
                bus_dict=bus_dict,
                I_kcl=I_kcl,
                ph_v_keys=ph_v_keys,
                inj_i_keys=inj_i_keys,
            )

        # Stage 4: bus models are registered last so their PF initialization sees the assembled network.
        for bus_idx, bus in enumerate(grid.buses):
            self._process_structure_bus(
                bus_idx=bus_idx,
                bus=bus,
                sys_block=sys_block,
                grid=grid,
                glob_time=glob_time,
            )
            # Stage 5: materialize the final bus algebraic equations from the accumulated KCL expressions.
            mdl: Block = bus.emt_model
            mdl.algebraic_eqs = list()

            # Rebuild each bus algebraic block from the shared KCL accumulator so
            # buses expose one equation per available EMT voltage variable.
            if bus.is_dc:
                v_dc_expr: Any | None = mdl.E(VarPowerFlowRefferenceType.Vdc)
                if v_dc_expr is not None:
                    mdl.algebraic_eqs.append(I_kcl[bus_idx][0])
                else:
                    pass
            else:
                for ph_idx, v_key in enumerate(ph_v_keys):
                    v_expr: Any | None = mdl.E(v_key)
                    if v_expr is not None:
                        mdl.algebraic_eqs.append(I_kcl[bus_idx][ph_idx])
                    else:
                        pass

            if len(mdl.algebraic_eqs) == 0:
                self.logger.add_error(
                    "Bus has no phases (no voltage vars)",
                    value=str(bus_idx),
                )
            else:
                pass


    def _prepare_structure_collect_context(
            self,
            grid: MultiCircuit,
    ) -> Tuple[
        Dict[Any, int],
        Dict[int, List[Any]],
        List[VarPowerFlowRefferenceType],
        List[VarPowerFlowRefferenceType],
        List[VarPowerFlowRefferenceType],
        List[VarPowerFlowRefferenceType],
        List[VarPowerFlowRefferenceType],
        List[VarPowerFlowRefferenceType],
        float,
        float,
        float,
        Dict[str, int],
    ]:
        """
        Prepare the shared data used by EMT structure collection.

        This stage sets the stable bus ordering, creates the per-bus KCL
        accumulators, defines the ordered phase reference lists, and caches the
        runtime constants and VSC lookup table consumed by later device loops.

        :param grid: Network model to assemble.
        :return: Tuple with bus indices, KCL accumulators, phase-key lists,
            runtime constants, and VSC lookup table.
        """
        bus_dict: Dict[Any, int] = dict()

        # Keep the original phase ordering because every downstream EMT mapping
        # and KCL contribution assumes this exact NABC convention.
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
        br_if_keys: List[VarPowerFlowRefferenceType] = list([
            VarPowerFlowRefferenceType.if_N,
            VarPowerFlowRefferenceType.if_A,
            VarPowerFlowRefferenceType.if_B,
            VarPowerFlowRefferenceType.if_C,
        ])
        br_it_keys: List[VarPowerFlowRefferenceType] = list([
            VarPowerFlowRefferenceType.it_N,
            VarPowerFlowRefferenceType.it_A,
            VarPowerFlowRefferenceType.it_B,
            VarPowerFlowRefferenceType.it_C,
        ])
        br_vf_keys: List[VarPowerFlowRefferenceType] = list([
            VarPowerFlowRefferenceType.vf_N,
            VarPowerFlowRefferenceType.vf_A,
            VarPowerFlowRefferenceType.vf_B,
            VarPowerFlowRefferenceType.vf_C,
        ])
        br_vt_keys: List[VarPowerFlowRefferenceType] = list([
            VarPowerFlowRefferenceType.vt_N,
            VarPowerFlowRefferenceType.vt_A,
            VarPowerFlowRefferenceType.vt_B,
            VarPowerFlowRefferenceType.vt_C,
        ])

        c0: Any = grid.var_factory.add_const(0.0)

        # Create one KCL accumulator vector per bus before device traversal so
        # branches and injections can update the exact same shared expressions.
        I_kcl: Dict[int, List[Any]] = dict()
        for bus_idx, bus in enumerate(grid.buses):
            if bus.is_dc:
                I_kcl[bus_idx] = list([c0])
            else:
                I_kcl[bus_idx] = list([c0, c0, c0, c0])

            bus_dict[bus] = int(bus_idx)

        h: float = float(self.options.time_step)
        sbase: float = float(grid.Sbase)
        fbase: float = float(grid.fBase)

        # VSC branches need their PF index during branch traversal, so cache the
        # lookup once up front instead of recomputing it inside the loop.
        vsc_idx_dict: Dict[str, int] = dict()
        for vsc_idx, vsc in enumerate(grid.vsc_devices):
            vsc_idx_dict[vsc.idtag] = vsc_idx

        return (
            bus_dict,
            I_kcl,
            ph_v_keys,
            inj_i_keys,
            br_if_keys,
            br_it_keys,
            br_vf_keys,
            br_vt_keys,
            h,
            sbase,
            fbase,
            vsc_idx_dict,
        )

    def _process_structure_branch(
            self,
            branch_idx: int,
            br: Any,
            sys_block: Block,
            grid: MultiCircuit,
            glob_time: Var,
            bus_dict: Dict[Any, int],
            I_kcl: Dict[int, List[Any]],
            ph_v_keys: List[VarPowerFlowRefferenceType],
            inj_i_keys: List[VarPowerFlowRefferenceType],
            br_if_keys: List[VarPowerFlowRefferenceType],
            br_it_keys: List[VarPowerFlowRefferenceType],
            br_vf_keys: List[VarPowerFlowRefferenceType],
            br_vt_keys: List[VarPowerFlowRefferenceType],
            h: float,
            sbase: float,
            fbase: float,
            vsc_idx_dict: Dict[str, int],
    ) -> None:
        """
        Register one branch model and apply its EMT nodal contributions.

        Branches are processed before injections and buses because they define
        the network coupling, terminal substitutions, and Bergeron runtimes that
        later stages depend on.

        :param branch_idx: Branch index in the traversed grid order.
        :param br: Grid branch device.
        :param sys_block: Global EMT system block.
        :param grid: Network model to assemble.
        :param glob_time: Global simulation time variable.
        :param bus_dict: Mapping from bus object to bus index.
        :param I_kcl: Shared KCL accumulators.
        :param ph_v_keys: Ordered bus voltage reference keys.
        :param inj_i_keys: Ordered injection current reference keys.
        :param br_if_keys: Ordered from-side branch current reference keys.
        :param br_it_keys: Ordered to-side branch current reference keys.
        :param br_vf_keys: Ordered from-side branch voltage reference keys.
        :param br_vt_keys: Ordered to-side branch voltage reference keys.
        :param h: EMT time step.
        :param sbase: Floating-point system base power.
        :param fbase: Floating-point system base frequency.
        :param vsc_idx_dict: Mapping from VSC idtag to PF result index.
        :return: None.
        """
        f: int = bus_dict[br.bus_from]
        t: int = bus_dict[br.bus_to]
        mdl: Block = self._process_device_model(br, sys_block, grid, glob_time)

        is_bergeron: bool = br.emt_model.name == EmtLineTypes.Bergeron.value
        is_vsc: bool = br.device_type == DeviceType.VscDevice
        vsc_index: int = vsc_idx_dict.get(br.idtag, -1)

        # Preserve the original API mapping assignment point before any branch-
        # specific runtime setup, substitutions, or PF initialization.
        self._assign_api_obj_mapping_branch(br=br, is_vsc=is_vsc, vsc_index=vsc_index)

        if is_bergeron:
            self._process_structure_bergeron_branch(
                branch_idx=branch_idx,
                br=br,
                mdl=mdl,
                grid=grid,
                f=f,
                t=t,
                I_kcl=I_kcl,
                ph_v_keys=ph_v_keys,
                h=h,
                sbase=sbase,
                fbase=fbase,
            )
        else:
            self._process_structure_standard_branch(
                branch_idx=branch_idx,
                br=br,
                mdl=mdl,
                grid=grid,
                f=f,
                t=t,
                I_kcl=I_kcl,
                inj_i_keys=inj_i_keys,
                br_if_keys=br_if_keys,
                br_it_keys=br_it_keys,
                br_vf_keys=br_vf_keys,
                br_vt_keys=br_vt_keys,
                is_vsc=is_vsc,
                vsc_index=vsc_index,
                sbase=sbase,
            )

    def _process_structure_bergeron_branch(
            self,
            branch_idx: int,
            br: Any,
            mdl: Block,
            grid: MultiCircuit,
            f: int,
            t: int,
            I_kcl: Dict[int, List[Any]],
            ph_v_keys: List[VarPowerFlowRefferenceType],
            h: float,
            sbase: float,
            fbase: float,
    ) -> None:
        """
        Process the Bergeron-specific branch path during EMT structure collection.

        Bergeron lines create a runtime history object, bind terminal voltages,
        optionally initialize from PF results, and finally inject their nodal
        currents into the shared KCL accumulators.

        :param branch_idx: Branch index in the traversed grid order.
        :param br: Grid branch device.
        :param mdl: Unified symbolic block for the branch.
        :param grid: Network model to assemble.
        :param f: From-bus index.
        :param t: To-bus index.
        :param I_kcl: Shared KCL accumulators.
        :param ph_v_keys: Ordered bus voltage reference keys.
        :param h: EMT time step.
        :param sbase: Floating-point system base power.
        :param fbase: Floating-point system base frequency.
        :return: None.
        """
        # Bergeron runtimes work on explicit terminal voltages, so collect the
        # bus expressions before runtime creation and binding.
        v_f_vars: List[Any] = _get_bus_v_list(
            grid=grid,
            bus_block=br.bus_from.emt_model,
            ph_v_keys=ph_v_keys,
        )
        v_t_vars: List[Any] = _get_bus_v_list(
            grid=grid,
            bus_block=br.bus_to.emt_model,
            ph_v_keys=ph_v_keys,
        )

        rt: BergeronHistoryRuntime = BergeronHistoryRuntime(
            line=br,
            line_block=mdl,
            h=h,
            sbase=sbase,
            fbase=fbase,
        )
        rt.bind_terminals(v_f_vars, v_t_vars)

        # Preserve the original PF-init dispatch so Bergeron history variables
        # receive the exact same 3ph, balanced, or no-PF initialization behavior.
        if self.power_flow_results_3ph is not None:
            self._try_set_bergeron_pf_init(
                mdl=mdl,
                rt=rt,
                branch_index=branch_idx,
                f_bus_idx=f,
                t_bus_idx=t,
                sbase=grid.Sbase,
            )
        elif self.power_flow_results is not None:
            if self.options.verbose:
                print("Initializing bergeron line variables assuming a balanced power flow")
            else:
                pass

            self._try_set_bergeron_pf_init_balanced(
                mdl=mdl,
                rt=rt,
                branch_index=branch_idx,
                f_bus_idx=f,
                t_bus_idx=t,
                sbase=grid.Sbase,
            )
        else:
            if self.options.verbose:
                print("No Power Flow results given.")
            else:
                pass

        i_f_exprs: List[Any]
        i_t_exprs: List[Any]
        i_f_exprs, i_t_exprs = rt.get_nodal_injections()

        # Bergeron nodal injections follow the same sign convention as the old
        # implementation: branch currents leave the bus and subtract from KCL.
        for ph in range(4):
            if i_f_exprs[ph] is not None:
                I_kcl[f][ph] = I_kcl[f][ph] - i_f_exprs[ph]
            else:
                pass

            if i_t_exprs[ph] is not None:
                I_kcl[t][ph] = I_kcl[t][ph] - i_t_exprs[ph]
            else:
                pass

        self.history_models.append(rt)

    def _process_structure_standard_branch(
            self,
            branch_idx: int,
            br: Any,
            mdl: Block,
            grid: MultiCircuit,
            f: int,
            t: int,
            I_kcl: Dict[int, List[Any]],
            inj_i_keys: List[VarPowerFlowRefferenceType],
            br_if_keys: List[VarPowerFlowRefferenceType],
            br_it_keys: List[VarPowerFlowRefferenceType],
            br_vf_keys: List[VarPowerFlowRefferenceType],
            br_vt_keys: List[VarPowerFlowRefferenceType],
            is_vsc: bool,
            vsc_index: int,
            sbase: float,
    ) -> None:
        """
        Process the non-Bergeron branch path during EMT structure collection.

        Standard branch models contribute terminal currents directly, receive bus
        voltage substitutions through their external mapping, and then follow the
        existing PF initialization dispatch.

        :param branch_idx: Branch index in the traversed grid order.
        :param br: Grid branch device.
        :param mdl: Unified symbolic block for the branch.
        :param grid: Network model to assemble.
        :param f: From-bus index.
        :param t: To-bus index.
        :param I_kcl: Shared KCL accumulators.
        :param inj_i_keys: Ordered injection current reference keys.
        :param br_if_keys: Ordered from-side branch current reference keys.
        :param br_it_keys: Ordered to-side branch current reference keys.
        :param br_vf_keys: Ordered from-side branch voltage reference keys.
        :param br_vt_keys: Ordered to-side branch voltage reference keys.
        :param is_vsc: Whether the branch is a VSC device.
        :param vsc_index: PF result index for the VSC branch.
        :param sbase: Floating-point system base power.
        :return: None.
        """
        # First accumulate branch currents into the bus KCL balances using the
        # existing sign convention where branch currents leave the bus.
        side_bus_indices: List[int] = list([f, t])
        side_buses: List[Any] = list([br.bus_from, br.bus_to])
        side_current_keys: List[List[VarPowerFlowRefferenceType]] = list([br_if_keys, br_it_keys])

        for side_idx in range(2):
            side_bus_idx: int = side_bus_indices[side_idx]
            side_bus: Any = side_buses[side_idx]
            current_keys: List[VarPowerFlowRefferenceType] = side_current_keys[side_idx]

            if side_bus.is_dc:
                side_dc_expr: Any | None = mdl.E(VarPowerFlowRefferenceType.Idc)
                if side_dc_expr is not None:
                    I_kcl[side_bus_idx][0] = I_kcl[side_bus_idx][0] - side_dc_expr
                else:
                    pass
            else:
                for ph in range(4):
                    if is_vsc:
                        side_expr: Any | None = mdl.E(inj_i_keys[ph])
                    else:
                        side_expr = mdl.E(current_keys[ph])

                    if side_expr is not None:
                        I_kcl[side_bus_idx][ph] = I_kcl[side_bus_idx][ph] - side_expr
                    else:
                        pass

        # Then wire the branch external mapping to the already-created bus
        # voltage algebraics so templates see the same substituted terminals.
        terminal_buses: List[Any] = list([br.bus_from, br.bus_to])
        terminal_voltage_keys: List[List[VarPowerFlowRefferenceType]] = list([br_vf_keys, br_vt_keys])

        for term_idx in range(2):
            terminal_bus: Any = terminal_buses[term_idx]
            terminal_keys: List[VarPowerFlowRefferenceType] = terminal_voltage_keys[term_idx]
            external_mapping: Optional[Dict[Any, Var]] = _get_external_mapping(br.emt_model)

            if terminal_bus.is_dc:
                v_dc, _, _, _ = get_bus_emt_algebraic_vars(terminal_bus.emt_model)

                if external_mapping is not None:
                    mapped_var: Optional[Var] = external_mapping.get(VarPowerFlowRefferenceType.Vdc, None)
                    if mapped_var is not None:
                        br.emt_model.update_model(mapped_var, v_dc)
                    else:
                        pass
                else:
                    pass
            else:
                v_n, v_a, v_b, v_c = get_bus_emt_algebraic_vars(terminal_bus.emt_model)
                terminal_voltage_vars: List[Any] = list([v_n, v_a, v_b, v_c])

                if external_mapping is not None:
                    for ph in range(4):
                        mapped_var = external_mapping.get(terminal_keys[ph], None)
                        terminal_voltage_var = terminal_voltage_vars[ph]

                        if mapped_var is not None and terminal_voltage_var is not None:
                            br.emt_model.update_model(mapped_var, terminal_voltage_var)
                        else:
                            pass
                else:
                    pass

        # Finally, preserve the exact PF-init branch dispatch including the VSC-
        # specific 3ph path and the balanced fallback behavior.
        if self.power_flow_results_3ph is not None:
            if is_vsc and vsc_index >= 0:
                self._try_set_vsc_branch_pf_init(
                    mdl=mdl,
                    f_bus_idx=f,
                    t_bus_idx=t,
                    sbase=sbase,
                    vsc_index=vsc_index,
                )
            else:
                self._try_set_branch_pf_init(
                    mdl=mdl,
                    branch_index=branch_idx,
                    f_bus_idx=f,
                    t_bus_idx=t,
                    sbase=grid.Sbase,
                    is_vsc=is_vsc,
                    vsc_index=vsc_index,
                )
        else:
            if self.power_flow_results is not None:
                if self.options.verbose:
                    print("Initializing branch variables assuming a balanced power flow")
                else:
                    pass

                self._try_set_branch_pf_init_balanced(
                    mdl=mdl,
                    branch_index=branch_idx,
                    f_bus_idx=f,
                    t_bus_idx=t,
                    sbase=grid.Sbase,
                    is_vsc=is_vsc,
                    vsc_index=vsc_index,
                )
            else:
                if self.options.verbose:
                    print("No Power Flow results given.")
                else:
                    pass

    def _process_structure_injection(
            self,
            inj: Any,
            sys_block: Block,
            grid: MultiCircuit,
            glob_time: Var,
            bus_dict: Dict[Any, int],
            I_kcl: Dict[int, List[Any]],
            ph_v_keys: List[VarPowerFlowRefferenceType],
            inj_i_keys: List[VarPowerFlowRefferenceType],
    ) -> None:
        """
        Register one injection model and apply its EMT nodal contributions.

        Injection models add currents into the bus KCL balance, update their
        external bus-voltage mappings, and keep the existing PF initialization
        dispatch unchanged.

        :param inj: Grid injection device.
        :param sys_block: Global EMT system block.
        :param grid: Network model to assemble.
        :param glob_time: Global simulation time variable.
        :param bus_dict: Mapping from bus object to bus index.
        :param I_kcl: Shared KCL accumulators.
        :param ph_v_keys: Ordered bus voltage reference keys.
        :param inj_i_keys: Ordered injection current reference keys.
        :return: None.
        """
        mdl: Block = self._process_device_model(inj, sys_block, grid, glob_time)
        b: int = bus_dict[inj.bus]

        # Keep the original device-type-specific API mapping assignments before
        # any current accumulation or voltage substitution takes place.
        if inj.device_type == DeviceType.LoadDevice:
            self._assign_api_obj_mapping_load(inj)
        else:
            if inj.device_type == DeviceType.GeneratorDevice:
                self._assign_api_obj_mapping_generator(inj)
            else:
                pass

        # Injections enter the bus and therefore add to the shared KCL balance.
        if inj.bus.is_dc:
            i_dc_expr: Any | None = mdl.E(VarPowerFlowRefferenceType.Idc)
            if i_dc_expr is not None:
                I_kcl[b][0] = I_kcl[b][0] + i_dc_expr
            else:
                pass
        else:
            for ph in range(4):
                i_expr: Any | None = mdl.E(inj_i_keys[ph])
                if i_expr is not None:
                    I_kcl[b][ph] = I_kcl[b][ph] + i_expr
                else:
                    pass

        # Substitute the bus voltage algebraics into the injection external map
        # so the device sees the same bus-terminal variables as before.
        inj_external_mapping: Optional[Dict[Any, Var]] = _get_external_mapping(inj.emt_model)

        if inj.bus.is_dc:
            v_dc, _, _, _ = get_bus_emt_algebraic_vars(inj.bus.emt_model)

            if inj_external_mapping is not None:
                mapped_var = inj_external_mapping.get(VarPowerFlowRefferenceType.Vdc, None)
                if mapped_var is not None:
                    inj.emt_model.update_model(mapped_var, v_dc)
                else:
                    pass
            else:
                pass
        else:
            v_n, v_a, v_b, v_c = get_bus_emt_algebraic_vars(inj.bus.emt_model)
            inj_bus_voltage_vars: List[Any] = list([v_n, v_a, v_b, v_c])

            if inj_external_mapping is not None:
                for ph in range(4):
                    mapped_var = inj_external_mapping.get(ph_v_keys[ph], None)
                    inj_bus_voltage_var = inj_bus_voltage_vars[ph]

                    if mapped_var is not None and inj_bus_voltage_var is not None:
                        inj.emt_model.update_model(mapped_var, inj_bus_voltage_var)
                    else:
                        pass
            else:
                pass

        # Preserve the original 3ph, balanced, and no-PF initialization paths.
        if self.power_flow_results_3ph is not None:
            self._try_set_inj_pf_init(
                inj=inj,
                mdl=mdl,
                bus_index=b,
                sbase=grid.Sbase,
            )
        else:
            if self.power_flow_results is not None:
                if self.options.verbose:
                    print("Initializing injection variables assuming a balanced power flow")
                else:
                    pass

                self._try_set_inj_pf_init_balanced(
                    inj=inj,
                    mdl=mdl,
                    bus_index=b,
                    sbase=grid.Sbase,
                )
            else:
                if self.options.verbose:
                    print("No Power Flow results given.")
                else:
                    pass

    def _process_structure_bus(
            self,
            bus_idx: int,
            bus: Any,
            sys_block: Block,
            grid: MultiCircuit,
            glob_time: Var,
    ) -> None:
        """
        Register one bus model and apply its PF initialization stage.

        Bus processing is intentionally kept separate from branch and injection
        traversal so the top-level EMT assembly reads as a clear pipeline.

        :param bus_idx: Bus index in the traversed grid order.
        :param bus: Grid bus device.
        :param sys_block: Global EMT system block.
        :param grid: Network model to assemble.
        :param glob_time: Global simulation time variable.
        :return: None.
        """
        mdl: Block = self._process_device_model(bus, sys_block, grid, glob_time)

        # Bus models do not alter KCL accumulation here; they only register their
        # symbolic block and keep the original PF-init dispatch behavior.
        if self.power_flow_results_3ph is not None:
            self._try_set_bus_pf_init(
                bus=bus,
                mdl=mdl,
                bus_index=bus_idx,
            )
        elif self.power_flow_results is not None:
            if self.options.verbose:
                print("Initializing bus variables assuming a balanced power flow.")
            else:
                pass

            self._try_set_bus_pf_init_balanced(
                bus=bus,
                mdl=mdl,
                bus_index=bus_idx,
            )
        else:
            if self.options.verbose:
                print("No Power Flow results given.")
            else:
                pass


    def _register_runtime_event_parameters(self, dev: Any, mdl: Block) -> None:
        """
        Register runtime-updatable EMT parameters declared by the device block.

        EMT runtime events are no longer baked into the symbolic model during the
        parsing phase. Instead, the problem stores the event-capable parameters and
        later activates the selected EMT event group through ``set_events_group()``.

        :param dev: Device object from the grid.
        :param mdl: Device symbolic block containing ``event_dict`` and ``mode_dict``.
        :return: None
        """
        if not mdl.event_dict and not mdl.mode_dict:
            return

        for parameter in mdl.event_dict.keys():
            self._event_parameter_device_idtags[parameter.uid] = dev.idtag
            self._continuous_event_parameter_uids.add(parameter.uid)

        for parameter in mdl.mode_dict.keys():
            self._event_parameter_device_idtags[parameter.uid] = dev.idtag
            self._discrete_event_parameter_uids.add(parameter.uid)

    def _get_emt_events_for_group(self, emt_events_group: EmtEventsGroup | None) -> List[Any]:
        """
        Return the EMT events that belong to the selected group.

        ``None`` means that all EMT events registered in the grid remain active,
        which preserves the previous default behavior.
        """
        emt_events: List[Any] = _get_grid_runtime_events(self.grid)

        if emt_events_group is None:
            return emt_events

        filtered_events: List[Any] = list()

        for evt in emt_events:
            try:
                group_idtag = evt.group.idtag
            except AttributeError:
                group_idtag = None

            if group_idtag == emt_events_group.idtag:
                filtered_events.append(evt)
            else:
                pass

        return filtered_events

    def _event_targets_registered_parameter(self, evt: Any, parameter_uid: int) -> bool:
        """
        Return whether the EMT event targets a runtime parameter registered in the problem.
        """
        registered_device_idtag: str | None = self._event_parameter_device_idtags.get(parameter_uid, None)

        try:
            event_device_idtag: str = str(evt.device_idtag)
        except AttributeError:
            event_device_idtag = ""

        if registered_device_idtag is None:
            return False

        if event_device_idtag == "":
            return True

        return registered_device_idtag == event_device_idtag

    def set_events_group(self, emt_events_group: EmtEventsGroup | None) -> None:
        """
        Activate the selected EMT events group inside the problem runtime layer.

        Continuous EMT events are mapped to runtime ``piecewise(time)`` expressions.
        Discrete EMT mode events are stored as scheduled updates consumed by the
        boundary update hook used by the EMT solvers.

        :param emt_events_group: EMT events group to activate. ``None`` keeps all EMT events active.
        :return: None
        """
        same_group_requested: bool

        if self._active_events_group is None:
            same_group_requested = emt_events_group is None and len(self._scheduled_mode_events) > 0
        elif emt_events_group is None:
            same_group_requested = False
        else:
            same_group_requested = self._active_events_group.idtag == emt_events_group.idtag

        if same_group_requested:
            return
        else:
            pass

        active_runtime_eqs: List[Any] = list(self._runtime_parameter_eqs0)
        scheduled_mode_events: Dict[int, List[Tuple[float, float, bool]]] = dict()
        continuous_events: Dict[int, Dict[str, List[float]]] = {
            parameter.uid: {"times": list(), "values": list()}
            for parameter in self.get_runtime_continuous_parameters()
            if parameter.uid in self._continuous_event_parameter_uids
        }

        emt_events: List[Any] = self._get_emt_events_for_group(emt_events_group)

        for evt in emt_events:
            if isinstance(evt.parameter, Var):
                parameter_uid: int = evt.parameter.uid

                if self._event_targets_registered_parameter(evt, parameter_uid):
                    if parameter_uid in self._discrete_event_parameter_uids:
                        event_list: List[Tuple[float, float, bool]] = scheduled_mode_events.setdefault(
                            parameter_uid,
                            list(),
                        )

                        try:
                            force_step_alignment = bool(evt.force_step_alignment)
                        except AttributeError:
                            force_step_alignment = False

                        event_list.append(
                            (
                                float(evt.time),
                                float(evt.value),
                                force_step_alignment,
                            )
                        )
                    else:
                        if parameter_uid in continuous_events:
                            continuous_events[parameter_uid]["times"].append(float(evt.time))
                            continuous_events[parameter_uid]["values"].append(float(evt.value))
                        else:
                            pass
                else:
                    pass
            else:
                pass

        for parameter_uid, info in continuous_events.items():
            if len(info["times"]) != 0:
                runtime_idx: int = self.uid2idx_event_params[parameter_uid]
                sort_idx: np.ndarray = np.argsort(np.asarray(info["times"], dtype=np.float64), kind="stable")
                t_events: np.ndarray = np.asarray(info["times"], dtype=np.float64)[sort_idx]
                new_values: np.ndarray = np.asarray(info["values"], dtype=np.float64)[sort_idx]

                active_runtime_eqs[runtime_idx] = piecewise(
                    time_var=self._glob_time,
                    t_events=t_events,
                    new_values=new_values,
                    default_value=active_runtime_eqs[runtime_idx],
                )
            else:
                pass

        self._active_events_group = emt_events_group
        self._runtime_all_eqs_source = active_runtime_eqs
        self._scheduled_mode_events = scheduled_mode_events

        # Event-group activation only changes the runtime equations and scheduled
        # updates; it does not change the parameter ordering. Reusing the existing
        # partition avoids rebuilding constant parameter buffers and repeated list
        # reconstruction during every event-group switch.
        self._runtime_continuous_eqs = list()
        self._runtime_mode_eqs = list()

        n_source: int = len(self._runtime_all_parameters_source)
        i: int = 0
        while i < n_source:
            parameter: Var = self._runtime_all_parameters_source[i]
            equation: Any = active_runtime_eqs[i]

            if parameter.uid in self._runtime_mode_uids:
                self._runtime_mode_eqs.append(equation)
            else:
                self._runtime_continuous_eqs.append(equation)

            i += 1

        self._event_parameters_eqs = list()

        for equation in self._runtime_continuous_eqs:
            self._event_parameters_eqs.append(equation)

        for equation in self._runtime_mode_eqs:
            self._event_parameters_eqs.append(equation)

        self._mode_event_cursor = dict()
        self._initialize_mode_event_state()

        if self.get_variable_parameter_number() > 0:
            self._event_params_values = self._initialize_runtime_parameter_values(0.0)
            self._event_params_values = self.def_event_params_fn(self._event_params_values, 0.0)
        else:
            self._event_params_values = np.zeros(0, dtype=np.float64)

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
    def _get_pf_omega_base(self) -> float:
        """
        Return the EMT electrical base angular frequency.

        :return: Base angular frequency in rad/s.
        """
        return float(2.0 * np.pi * self.grid.fBase)

    def _phasor_to_instantaneous_initial_value(self, phasor: complex) -> float:
        """
        Convert one phasor into the EMT instantaneous value at ``t = 0``.

        :param phasor: Complex phasor quantity.
        :return: Instantaneous EMT value.
        """
        return float(np.sqrt(2.0) * np.imag(phasor))

    def _phasor_to_instantaneous_derivative_value(self, phasor: complex) -> float:
        """
        Convert one voltage phasor into the EMT derivative value at ``t = 0``.

        :param phasor: Complex voltage phasor.
        :return: Instantaneous EMT derivative value.
        """
        return float(self._get_pf_omega_base() * np.sqrt(2.0) * np.real(phasor))

    def _phasor_current_from_power_voltage(self, power: complex, voltage: complex) -> complex:
        """
        Return the current phasor implied by complex power and terminal voltage.

        :param power: Complex power in per unit.
        :param voltage: Complex terminal voltage in per unit.
        :return: Complex current phasor.
        """
        if abs(voltage) <= 1e-12:
            return 0.0 + 0.0j
        else:
            return np.conj(power / voltage)

    def _get_zero_phase_phasor_dict(self) -> Dict[str, complex]:
        """
        Return a zero-valued NABC phase dictionary.

        :return: Zero phasor dictionary for phases ``N``, ``A``, ``B`` and ``C``.
        """
        phase_dict: Dict[str, complex] = dict()
        phase_dict["N"] = 0.0 + 0.0j
        phase_dict["A"] = 0.0 + 0.0j
        phase_dict["B"] = 0.0 + 0.0j
        phase_dict["C"] = 0.0 + 0.0j
        return phase_dict

    def _get_ac_phase_voltages_from_3ph_pf(self, bus_index: int) -> Dict[str, complex]:
        """
        Return the NABC bus-voltage phasors from the unbalanced three-phase PF.

        :param bus_index: Bus index in the three-phase PF results.
        :return: Phase-voltage phasor dictionary.
        """
        if self.power_flow_results_3ph is not None:
            phase_voltages: Dict[str, complex] = dict()
            phase_voltages["N"] = complex(self.power_flow_results_3ph.voltage_N[bus_index])
            phase_voltages["A"] = complex(self.power_flow_results_3ph.voltage_A[bus_index])
            phase_voltages["B"] = complex(self.power_flow_results_3ph.voltage_B[bus_index])
            phase_voltages["C"] = complex(self.power_flow_results_3ph.voltage_C[bus_index])
            return phase_voltages
        else:
            raise ValueError("Three-phase EMT initialization requires three-phase power-flow results.")

    def _get_ac_phase_voltages_from_balanced_pf(self, bus_index: int) -> Dict[str, complex]:
        """
        Reconstruct balanced NABC bus-voltage phasors from the positive-sequence PF.

        :param bus_index: Bus index in the balanced PF results.
        :return: Phase-voltage phasor dictionary.
        """
        if self.power_flow_results is not None:
            alpha: float = 2.0 * np.pi / 3.0
            v_bus: CxVec = self.power_flow_results.voltage[bus_index]
            phase_voltages: Dict[str, complex] = dict()
            phase_voltages["N"] = 0.0 + 0.0j
            phase_voltages["A"] = complex(v_bus)
            phase_voltages["B"] = complex(v_bus * np.exp(-1j * alpha))
            phase_voltages["C"] = complex(v_bus * np.exp(+1j * alpha))
            return phase_voltages
        else:
            raise ValueError("Balanced EMT initialization requires the balanced PowerFlow to be calculated.")

    def _set_dc_bus_pf_voltage_initialization(self, mdl: Block, bus_index: int) -> None:
        """
        Initialize one DC bus voltage from balanced PF results.

        :param mdl: Bus symbolic block.
        :param bus_index: Bus index in the balanced PF results.
        :return: None.
        """
        if self.power_flow_results is not None:
            self.set_init_guess(
                mdl,
                VarPowerFlowRefferenceType.Vdc,
                float(np.abs(self.power_flow_results.voltage[bus_index])),
            )
        else:
            raise ValueError(
                "EMT simulation with DC branches requires the non unbalanced PowerFlow to be calculated."
            )

    def _set_ac_bus_pf_voltage_initialization(self, mdl: Block, phase_voltages: Dict[str, complex]) -> None:
        """
        Initialize AC bus voltage states and derivatives from phase phasors.

        :param mdl: Bus symbolic block.
        :param phase_voltages: NABC voltage phasor dictionary.
        :return: None.
        """
        voltage_keys: Dict[str, VarPowerFlowRefferenceType] = dict()
        voltage_keys["N"] = VarPowerFlowRefferenceType.v_N
        voltage_keys["A"] = VarPowerFlowRefferenceType.v_A
        voltage_keys["B"] = VarPowerFlowRefferenceType.v_B
        voltage_keys["C"] = VarPowerFlowRefferenceType.v_C

        derivative_keys: Dict[str, VarPowerFlowRefferenceType] = dict()
        derivative_keys["N"] = VarPowerFlowRefferenceType.d_v_N
        derivative_keys["A"] = VarPowerFlowRefferenceType.d_v_A
        derivative_keys["B"] = VarPowerFlowRefferenceType.d_v_B
        derivative_keys["C"] = VarPowerFlowRefferenceType.d_v_C

        for phase_name in list(["N", "A", "B", "C"]):
            voltage_key: VarPowerFlowRefferenceType = voltage_keys[phase_name]
            derivative_key: VarPowerFlowRefferenceType = derivative_keys[phase_name]

            if mdl.E(voltage_key) is not None:
                phase_voltage: complex = phase_voltages[phase_name]
                self.set_init_guess(
                    mdl,
                    voltage_key,
                    self._phasor_to_instantaneous_initial_value(phase_voltage),
                )
                self.set_diff_init_guess(
                    mdl,
                    derivative_key,
                    self._phasor_to_instantaneous_derivative_value(phase_voltage),
                )
            else:
                pass

    def _set_ac_voltage_derivative_external_params(
            self,
            mdl: Block,
            phase_voltages: Dict[str, complex],
            derivative_keys: Dict[str, VarPowerFlowRefferenceType],
    ) -> None:
        """
        Write PF-derived AC voltage derivative values into external mappings.

        :param mdl: Symbolic block receiving PF-derived parameters.
        :param phase_voltages: NABC voltage phasor dictionary.
        :param derivative_keys: Mapping from phase label to derivative reference.
        :return: None.
        """
        for phase_name in list(["N", "A", "B", "C"]):
            derivative_key: VarPowerFlowRefferenceType = derivative_keys[phase_name]
            if mdl.E(derivative_key) is not None:
                self.set_external_param(
                    mdl,
                    derivative_key,
                    self._phasor_to_instantaneous_derivative_value(phase_voltages[phase_name]),
                )
            else:
                pass

    def _set_pf_positive_sequence_external_params(
            self,
            mdl: Block,
            phase_voltages: Dict[str, complex],
            phase_currents: Dict[str, complex],
    ) -> None:
        """
        Write positive-sequence PF-derived quantities when the model exposes them.

        :param mdl: Symbolic block receiving PF-derived parameters.
        :param phase_voltages: NABC voltage phasor dictionary.
        :param phase_currents: NABC current phasor dictionary.
        :return: None.
        """
        external_mapping: Optional[Dict[Any, Var]] = _get_external_mapping(mdl)

        if external_mapping is not None:
            a: complex = np.exp(1j * 2.0 * np.pi / 3.0)
            v_a: complex = phase_voltages["A"]
            v_b: complex = phase_voltages["B"]
            v_c: complex = phase_voltages["C"]
            i_a: complex = phase_currents["A"]
            i_b: complex = phase_currents["B"]
            i_c: complex = phase_currents["C"]

            v1: complex = (v_a + a * v_b + (a * a) * v_c) / 3.0
            i1: complex = (i_a + a * i_b + (a * a) * i_c) / 3.0

            phi_v: float = float(np.angle(v1))
            phi_i: float = float(np.angle(i1))
            ang: float = phi_i - phi_v
            phi: float = float(np.arctan2(np.sin(ang), np.cos(ang)))

            if VarPowerFlowRefferenceType.phi_v in external_mapping:
                self.set_external_param(mdl, VarPowerFlowRefferenceType.phi_v, phi_v)
            else:
                pass

            if VarPowerFlowRefferenceType.phi in external_mapping:
                self.set_external_param(mdl, VarPowerFlowRefferenceType.phi, phi)
            else:
                pass

            if VarPowerFlowRefferenceType.Vpk in external_mapping:
                self.set_external_param(mdl, VarPowerFlowRefferenceType.Vpk, float(np.sqrt(2.0) * np.abs(v1)))
            else:
                pass

            if VarPowerFlowRefferenceType.Ipk in external_mapping:
                self.set_external_param(mdl, VarPowerFlowRefferenceType.Ipk, float(np.sqrt(2.0) * np.abs(i1)))
            else:
                pass
        else:
            pass

    def _apply_injection_ac_pf_initialization(
            self,
            mdl: Block,
            phase_voltages: Dict[str, complex],
            phase_powers: Dict[str, complex],
    ) -> None:
        """
        Apply AC injection PF initialization from explicit phase phasors.

        :param mdl: Injection symbolic block.
        :param phase_voltages: NABC voltage phasor dictionary.
        :param phase_powers: NABC complex-power dictionary.
        :return: None.
        """
        current_keys: Dict[str, VarPowerFlowRefferenceType] = dict()
        current_keys["N"] = VarPowerFlowRefferenceType.i_N
        current_keys["A"] = VarPowerFlowRefferenceType.i_A
        current_keys["B"] = VarPowerFlowRefferenceType.i_B
        current_keys["C"] = VarPowerFlowRefferenceType.i_C

        active_power_keys: Dict[str, VarPowerFlowRefferenceType] = dict()
        active_power_keys["N"] = VarPowerFlowRefferenceType.P_N
        active_power_keys["A"] = VarPowerFlowRefferenceType.P_A
        active_power_keys["B"] = VarPowerFlowRefferenceType.P_B
        active_power_keys["C"] = VarPowerFlowRefferenceType.P_C

        reactive_power_keys: Dict[str, VarPowerFlowRefferenceType] = dict()
        reactive_power_keys["N"] = VarPowerFlowRefferenceType.Q_N
        reactive_power_keys["A"] = VarPowerFlowRefferenceType.Q_A
        reactive_power_keys["B"] = VarPowerFlowRefferenceType.Q_B
        reactive_power_keys["C"] = VarPowerFlowRefferenceType.Q_C

        derivative_keys: Dict[str, VarPowerFlowRefferenceType] = dict()
        derivative_keys["N"] = VarPowerFlowRefferenceType.d_v_N
        derivative_keys["A"] = VarPowerFlowRefferenceType.d_v_A
        derivative_keys["B"] = VarPowerFlowRefferenceType.d_v_B
        derivative_keys["C"] = VarPowerFlowRefferenceType.d_v_C

        phase_currents: Dict[str, complex] = dict()
        for phase_name in list(["N", "A", "B", "C"]):
            phase_currents[phase_name] = self._phasor_current_from_power_voltage(
                phase_powers[phase_name],
                phase_voltages[phase_name],
            )

            current_key: VarPowerFlowRefferenceType = current_keys[phase_name]
            active_power_key: VarPowerFlowRefferenceType = active_power_keys[phase_name]
            reactive_power_key: VarPowerFlowRefferenceType = reactive_power_keys[phase_name]

            uses_any: bool = (
                (mdl.E(current_key) is not None)
                or (mdl.E(active_power_key) is not None)
                or (mdl.E(reactive_power_key) is not None)
            )

            if uses_any:
                phase_current: complex = phase_currents[phase_name]
                phase_power: complex = phase_powers[phase_name]
                self.set_if_exists(
                    mdl=mdl,
                    key=current_key,
                    value=self._phasor_to_instantaneous_initial_value(phase_current),
                )
                self.set_if_exists(mdl=mdl, key=active_power_key, value=float(np.real(phase_power)))
                self.set_if_exists(mdl=mdl, key=reactive_power_key, value=float(np.imag(phase_power)))
            else:
                pass

        if mdl.E(VarPowerFlowRefferenceType.phi) is not None:
            self._set_pf_positive_sequence_external_params(
                mdl=mdl,
                phase_voltages=phase_voltages,
                phase_currents=phase_currents,
            )
        else:
            pass

        self._set_ac_voltage_derivative_external_params(
            mdl=mdl,
            phase_voltages=phase_voltages,
            derivative_keys=derivative_keys,
        )

    def _apply_branch_pf_phase_initialization(
            self,
            mdl: Block,
            phase_voltages_from: Dict[str, complex],
            phase_voltages_to: Dict[str, complex],
            phase_powers_from: Dict[str, complex],
            phase_powers_to: Dict[str, complex],
            aggregate_power_from: complex,
            aggregate_power_to: complex,
    ) -> None:
        """
        Apply generic branch PF initialization from explicit terminal phase data.

        :param mdl: Branch symbolic block.
        :param phase_voltages_from: From-side NABC voltage phasors.
        :param phase_voltages_to: To-side NABC voltage phasors.
        :param phase_powers_from: From-side NABC complex powers.
        :param phase_powers_to: To-side NABC complex powers.
        :param aggregate_power_from: Total from-side complex power.
        :param aggregate_power_to: Total to-side complex power.
        :return: None.
        """
        sf_keys: Dict[str, Optional[VarPowerFlowRefferenceType]] = dict()
        sf_keys["N"] = None
        sf_keys["A"] = VarPowerFlowRefferenceType.Sf_A
        sf_keys["B"] = VarPowerFlowRefferenceType.Sf_B
        sf_keys["C"] = VarPowerFlowRefferenceType.Sf_C

        st_keys: Dict[str, Optional[VarPowerFlowRefferenceType]] = dict()
        st_keys["N"] = None
        st_keys["A"] = VarPowerFlowRefferenceType.St_A
        st_keys["B"] = VarPowerFlowRefferenceType.St_B
        st_keys["C"] = VarPowerFlowRefferenceType.St_C

        if_keys: Dict[str, VarPowerFlowRefferenceType] = dict()
        if_keys["N"] = VarPowerFlowRefferenceType.if_N
        if_keys["A"] = VarPowerFlowRefferenceType.if_A
        if_keys["B"] = VarPowerFlowRefferenceType.if_B
        if_keys["C"] = VarPowerFlowRefferenceType.if_C

        it_keys: Dict[str, VarPowerFlowRefferenceType] = dict()
        it_keys["N"] = VarPowerFlowRefferenceType.it_N
        it_keys["A"] = VarPowerFlowRefferenceType.it_A
        it_keys["B"] = VarPowerFlowRefferenceType.it_B
        it_keys["C"] = VarPowerFlowRefferenceType.it_C

        d_vf_keys: Dict[str, VarPowerFlowRefferenceType] = dict()
        d_vf_keys["N"] = VarPowerFlowRefferenceType.d_v_N_f
        d_vf_keys["A"] = VarPowerFlowRefferenceType.d_v_A_f
        d_vf_keys["B"] = VarPowerFlowRefferenceType.d_v_B_f
        d_vf_keys["C"] = VarPowerFlowRefferenceType.d_v_C_f

        d_vt_keys: Dict[str, VarPowerFlowRefferenceType] = dict()
        d_vt_keys["N"] = VarPowerFlowRefferenceType.d_v_N_t
        d_vt_keys["A"] = VarPowerFlowRefferenceType.d_v_A_t
        d_vt_keys["B"] = VarPowerFlowRefferenceType.d_v_B_t
        d_vt_keys["C"] = VarPowerFlowRefferenceType.d_v_C_t

        for phase_name in list(["N", "A", "B", "C"]):
            sf_key: Optional[VarPowerFlowRefferenceType] = sf_keys[phase_name]
            st_key: Optional[VarPowerFlowRefferenceType] = st_keys[phase_name]

            if sf_key is not None:
                if mdl.E(sf_key) is not None:
                    self.set_if_exists(mdl=mdl, key=sf_key, value=float(np.real(phase_powers_from[phase_name])))
                else:
                    pass
            else:
                pass

            if st_key is not None:
                if mdl.E(st_key) is not None:
                    self.set_if_exists(mdl=mdl, key=st_key, value=float(np.real(phase_powers_to[phase_name])))
                else:
                    pass
            else:
                pass

            if_key: VarPowerFlowRefferenceType = if_keys[phase_name]
            it_key: VarPowerFlowRefferenceType = it_keys[phase_name]
            uses_currents: bool = (mdl.E(if_key) is not None) or (mdl.E(it_key) is not None)

            if uses_currents:
                i_from: complex = self._phasor_current_from_power_voltage(
                    phase_powers_from[phase_name],
                    phase_voltages_from[phase_name],
                )
                i_to: complex = self._phasor_current_from_power_voltage(
                    phase_powers_to[phase_name],
                    phase_voltages_to[phase_name],
                )
                self.set_if_exists(
                    mdl=mdl,
                    key=if_key,
                    value=self._phasor_to_instantaneous_initial_value(i_from),
                )
                self.set_if_exists(
                    mdl=mdl,
                    key=it_key,
                    value=self._phasor_to_instantaneous_initial_value(i_to),
                )
            else:
                pass

        self._set_ac_voltage_derivative_external_params(
            mdl=mdl,
            phase_voltages=phase_voltages_from,
            derivative_keys=d_vf_keys,
        )
        self._set_ac_voltage_derivative_external_params(
            mdl=mdl,
            phase_voltages=phase_voltages_to,
            derivative_keys=d_vt_keys,
        )

        self.set_if_exists(mdl=mdl, key=VarPowerFlowRefferenceType.Pf, value=float(np.real(aggregate_power_from)))
        self.set_if_exists(mdl=mdl, key=VarPowerFlowRefferenceType.Qf, value=float(np.imag(aggregate_power_from)))
        self.set_if_exists(mdl=mdl, key=VarPowerFlowRefferenceType.Pt, value=float(np.real(aggregate_power_to)))
        self.set_if_exists(mdl=mdl, key=VarPowerFlowRefferenceType.Qt, value=float(np.imag(aggregate_power_to)))

    def _set_vsc_ac_terminal_pf_initialization(
            self,
            mdl: Block,
            phase_voltages: Dict[str, complex],
            phase_currents: Dict[str, complex],
    ) -> None:
        """
        Initialize the AC-terminal voltage and current variables exposed by a VSC.

        :param mdl: VSC symbolic block.
        :param phase_voltages: NABC AC-terminal voltage phasors.
        :param phase_currents: NABC AC-terminal current phasors.
        :return: None.
        """
        voltage_keys: Dict[str, VarPowerFlowRefferenceType] = dict()
        voltage_keys["N"] = VarPowerFlowRefferenceType.v_N
        voltage_keys["A"] = VarPowerFlowRefferenceType.v_A
        voltage_keys["B"] = VarPowerFlowRefferenceType.v_B
        voltage_keys["C"] = VarPowerFlowRefferenceType.v_C

        current_keys: Dict[str, VarPowerFlowRefferenceType] = dict()
        current_keys["N"] = VarPowerFlowRefferenceType.i_N
        current_keys["A"] = VarPowerFlowRefferenceType.i_A
        current_keys["B"] = VarPowerFlowRefferenceType.i_B
        current_keys["C"] = VarPowerFlowRefferenceType.i_C

        for phase_name in list(["N", "A", "B", "C"]):
            self.set_if_exists(
                mdl=mdl,
                key=voltage_keys[phase_name],
                value=self._phasor_to_instantaneous_initial_value(phase_voltages[phase_name]),
            )
            self.set_if_exists(
                mdl=mdl,
                key=current_keys[phase_name],
                value=self._phasor_to_instantaneous_initial_value(phase_currents[phase_name]),
            )

    def _apply_vsc_branch_pf_initialization(
            self,
            mdl: Block,
            ac_is_from: bool,
            dc_bus_idx: int,
            phase_voltages_ac: Dict[str, complex],
            phase_powers_ac: Dict[str, complex],
            aggregate_power_ac: complex,
            aggregate_power_dc: complex,
    ) -> None:
        """
        Apply VSC-specific PF initialization from explicit AC/DC phase data.

        :param mdl: VSC symbolic block.
        :param ac_is_from: Whether the AC side is connected to the branch from-side.
        :param dc_bus_idx: DC bus index in the balanced PF results.
        :param phase_voltages_ac: NABC AC-side voltage phasors.
        :param phase_powers_ac: NABC AC-side complex powers.
        :param aggregate_power_ac: Total AC-side complex power.
        :param aggregate_power_dc: Total DC-side complex power.
        :return: None.
        """
        phase_currents_ac: Dict[str, complex] = dict()
        for phase_name in list(["N", "A", "B", "C"]):
            phase_currents_ac[phase_name] = self._phasor_current_from_power_voltage(
                phase_powers_ac[phase_name],
                phase_voltages_ac[phase_name],
            )

        self._set_vsc_ac_terminal_pf_initialization(
            mdl=mdl,
            phase_voltages=phase_voltages_ac,
            phase_currents=phase_currents_ac,
        )

        zero_phases: Dict[str, complex] = self._get_zero_phase_phasor_dict()
        if ac_is_from:
            phase_voltages_from: Dict[str, complex] = phase_voltages_ac
            phase_voltages_to: Dict[str, complex] = zero_phases
            phase_powers_from: Dict[str, complex] = phase_powers_ac
            phase_powers_to: Dict[str, complex] = zero_phases
            aggregate_power_from: complex = aggregate_power_ac
            aggregate_power_to: complex = aggregate_power_dc
        else:
            phase_voltages_from = zero_phases
            phase_voltages_to = phase_voltages_ac
            phase_powers_from = zero_phases
            phase_powers_to = phase_powers_ac
            aggregate_power_from = aggregate_power_dc
            aggregate_power_to = aggregate_power_ac

        self._apply_branch_pf_phase_initialization(
            mdl=mdl,
            phase_voltages_from=phase_voltages_from,
            phase_voltages_to=phase_voltages_to,
            phase_powers_from=phase_powers_from,
            phase_powers_to=phase_powers_to,
            aggregate_power_from=aggregate_power_from,
            aggregate_power_to=aggregate_power_to,
        )
        self._set_pf_positive_sequence_external_params(
            mdl=mdl,
            phase_voltages=phase_voltages_ac,
            phase_currents=phase_currents_ac,
        )

        if self.power_flow_results is not None:
            v_dc: float = float(np.abs(self.power_flow_results.voltage[dc_bus_idx]))
            self.set_if_exists(mdl=mdl, key=VarPowerFlowRefferenceType.Vdc, value=v_dc)

            if abs(v_dc) > 1e-12:
                self.set_if_exists(
                    mdl=mdl,
                    key=VarPowerFlowRefferenceType.Idc,
                    value=float(np.real(aggregate_power_dc) / v_dc),
                )
            else:
                self.set_if_exists(mdl=mdl, key=VarPowerFlowRefferenceType.Idc, value=0.0)
        else:
            pass

        self.set_if_exists(mdl=mdl, key=VarPowerFlowRefferenceType.P, value=float(np.real(aggregate_power_ac)))
        self.set_if_exists(mdl=mdl, key=VarPowerFlowRefferenceType.Q, value=float(np.imag(aggregate_power_ac)))

    def _try_set_bus_pf_init(self, bus: Any, mdl: Block, bus_index: int) -> None:
        """
        Initialize one bus from the unbalanced three-phase PF results.

        :param bus: Bus device.
        :param mdl: Bus symbolic block.
        :param bus_index: Bus index in the PF results.
        :return: None.
        """
        if bus.is_dc:
            self._set_dc_bus_pf_voltage_initialization(mdl=mdl, bus_index=bus_index)
        else:
            phase_voltages: Dict[str, complex] = self._get_ac_phase_voltages_from_3ph_pf(bus_index=bus_index)
            self._set_ac_bus_pf_voltage_initialization(mdl=mdl, phase_voltages=phase_voltages)

    def _try_set_bus_pf_init_balanced(self, bus: Any, mdl: Block, bus_index: int) -> None:
        """
        Initialize one bus from the balanced PF results.

        :param bus: Bus device.
        :param mdl: Bus symbolic block.
        :param bus_index: Bus index in the PF results.
        :return: None.
        """
        if bus.is_dc:
            self._set_dc_bus_pf_voltage_initialization(mdl=mdl, bus_index=bus_index)
        else:
            phase_voltages: Dict[str, complex] = self._get_ac_phase_voltages_from_balanced_pf(bus_index=bus_index)
            self._set_ac_bus_pf_voltage_initialization(mdl=mdl, phase_voltages=phase_voltages)

    def _get_vsc_terminal_indices(self,
                                  f_bus_idx: int,
                                  t_bus_idx: int) -> Tuple[int, int, bool]:
        """
        Return ``(ac_bus_idx, dc_bus_idx, ac_is_from)`` for a VSC branch.

        The preferred detection rule is based on bus types. If the branch does
        not present the expected AC/DC split, fall back to the legacy VSC
        orientation assumption used by the PF results: from side is DC and to
        side is AC.

        :param f_bus_idx: From-bus index.
        :param t_bus_idx: To-bus index.
        :return: AC bus index, DC bus index, and AC-side orientation flag.
        """
        f_bus = self.grid.buses[f_bus_idx]
        t_bus = self.grid.buses[t_bus_idx]

        if not f_bus.is_dc and t_bus.is_dc:
            return f_bus_idx, t_bus_idx, True
        else:
            if f_bus.is_dc and not t_bus.is_dc:
                return t_bus_idx, f_bus_idx, False
            else:
                return t_bus_idx, f_bus_idx, False

    def _try_set_vsc_branch_pf_init(self,
                                    mdl: Block,
                                    f_bus_idx: int,
                                    t_bus_idx: int,
                                    sbase: float,
                                    vsc_index: int) -> None:
        """
        Initialize a VSC branch from three-phase PF results.

        :param mdl: VSC symbolic block.
        :param f_bus_idx: From-bus index.
        :param t_bus_idx: To-bus index.
        :param sbase: Base power.
        :param vsc_index: VSC index in PF results.
        :return: None.
        """
        pf_results_3ph: PowerFlowResults3Ph | None = self.power_flow_results_3ph
        if pf_results_3ph is not None:
            ac_bus_idx, dc_bus_idx, ac_is_from = self._get_vsc_terminal_indices(
                f_bus_idx=f_bus_idx,
                t_bus_idx=t_bus_idx,
            )

            phase_voltages_ac: Dict[str, complex] = dict()
            phase_voltages_ac["N"] = 0.0 + 0.0j
            phase_voltages_ac["A"] = complex(pf_results_3ph.voltage_A[ac_bus_idx])
            phase_voltages_ac["B"] = complex(pf_results_3ph.voltage_B[ac_bus_idx])
            phase_voltages_ac["C"] = complex(pf_results_3ph.voltage_C[ac_bus_idx])

            phase_powers_ac: Dict[str, complex] = dict()
            phase_powers_ac["N"] = 0.0 + 0.0j
            phase_powers_ac["A"] = complex(pf_results_3ph.St_vsc_A[vsc_index] / sbase)
            phase_powers_ac["B"] = complex(pf_results_3ph.St_vsc_B[vsc_index] / sbase)
            phase_powers_ac["C"] = complex(pf_results_3ph.St_vsc_C[vsc_index] / sbase)

            try:
                pf_results_3ph_pfn_vsc = pf_results_3ph.Pfn_vsc[vsc_index]
            except AttributeError:
                pf_results_3ph_pfn_vsc = 0.0

            aggregate_power_ac: complex = (
                phase_powers_ac["A"] + phase_powers_ac["B"] + phase_powers_ac["C"]
            )
            aggregate_power_dc: complex = complex(
                (pf_results_3ph.Pfp_vsc[vsc_index] + pf_results_3ph_pfn_vsc) / sbase,
                0.0,
            )

            self._apply_vsc_branch_pf_initialization(
                mdl=mdl,
                ac_is_from=ac_is_from,
                dc_bus_idx=dc_bus_idx,
                phase_voltages_ac=phase_voltages_ac,
                phase_powers_ac=phase_powers_ac,
                aggregate_power_ac=aggregate_power_ac,
                aggregate_power_dc=aggregate_power_dc,
            )
        else:
            pass

    def _try_set_vsc_branch_pf_init_balanced(self,
                                             mdl: Block,
                                             f_bus_idx: int,
                                             t_bus_idx: int,
                                             sbase: float,
                                             vsc_index: int) -> None:
        """
        Initialize a VSC branch from balanced PF results.

        :param mdl: VSC symbolic block.
        :param f_bus_idx: From-bus index.
        :param t_bus_idx: To-bus index.
        :param sbase: Base power.
        :param vsc_index: VSC index in PF results.
        :return: None.
        """
        pf_results: PowerFlowResults | None = self.power_flow_results
        if pf_results is not None:
            ac_bus_idx, dc_bus_idx, ac_is_from = self._get_vsc_terminal_indices(
                f_bus_idx=f_bus_idx,
                t_bus_idx=t_bus_idx,
            )

            phase_voltages_ac: Dict[str, complex] = self._get_ac_phase_voltages_from_balanced_pf(bus_index=ac_bus_idx)

            try:
                pf_results_pfn_vsc = pf_results.Pfn_vsc[vsc_index]
            except AttributeError:
                pf_results_pfn_vsc = 0.0

            aggregate_power_ac: complex = complex(pf_results.St_vsc[vsc_index] / sbase)
            aggregate_power_dc: complex = complex(
                (pf_results.Pfp_vsc[vsc_index] + pf_results_pfn_vsc) / sbase,
                0.0,
            )
            phase_power_value: complex = aggregate_power_ac / 3.0

            phase_powers_ac: Dict[str, complex] = dict()
            phase_powers_ac["N"] = 0.0 + 0.0j
            phase_powers_ac["A"] = phase_power_value
            phase_powers_ac["B"] = phase_power_value
            phase_powers_ac["C"] = phase_power_value

            self._apply_vsc_branch_pf_initialization(
                mdl=mdl,
                ac_is_from=ac_is_from,
                dc_bus_idx=dc_bus_idx,
                phase_voltages_ac=phase_voltages_ac,
                phase_powers_ac=phase_powers_ac,
                aggregate_power_ac=aggregate_power_ac,
                aggregate_power_dc=aggregate_power_dc,
            )
        else:
            pass

    def _try_set_branch_pf_init(
            self,
            mdl: Block,
            branch_index: int,
            f_bus_idx: int,
            t_bus_idx: int,
            sbase: float,
            is_vsc: bool = False,
            vsc_index: int = -1
    ) -> None:
        """
        Initialize branch variables from three-phase power-flow results.

        :param mdl: Branch symbolic block.
        :param branch_index: Branch index in the PF results.
        :param f_bus_idx: From-bus index.
        :param t_bus_idx: To-bus index.
        :param sbase: Base power.
        :param is_vsc: Whether the branch is a VSC.
        :param vsc_index: VSC index in PF results.
        :return: None.
        """
        if is_vsc and vsc_index >= 0:
            self._try_set_vsc_branch_pf_init(
                mdl=mdl,
                f_bus_idx=f_bus_idx,
                t_bus_idx=t_bus_idx,
                sbase=sbase,
                vsc_index=vsc_index,
            )
        else:
            pf_results_3ph: PowerFlowResults3Ph | None = self.power_flow_results_3ph
            if pf_results_3ph is not None:
                phase_voltages_from: Dict[str, complex] = self._get_ac_phase_voltages_from_3ph_pf(bus_index=f_bus_idx)
                phase_voltages_to: Dict[str, complex] = self._get_ac_phase_voltages_from_3ph_pf(bus_index=t_bus_idx)

                phase_powers_from: Dict[str, complex] = dict()
                phase_powers_from["N"] = 0.0 + 0.0j
                phase_powers_from["A"] = complex(pf_results_3ph.Sf_A[branch_index] / sbase)
                phase_powers_from["B"] = complex(pf_results_3ph.Sf_B[branch_index] / sbase)
                phase_powers_from["C"] = complex(pf_results_3ph.Sf_C[branch_index] / sbase)

                phase_powers_to: Dict[str, complex] = dict()
                phase_powers_to["N"] = 0.0 + 0.0j
                phase_powers_to["A"] = complex(pf_results_3ph.St_A[branch_index] / sbase)
                phase_powers_to["B"] = complex(pf_results_3ph.St_B[branch_index] / sbase)
                phase_powers_to["C"] = complex(pf_results_3ph.St_C[branch_index] / sbase)

                aggregate_power_from: complex = (
                    phase_powers_from["A"] + phase_powers_from["B"] + phase_powers_from["C"]
                )
                aggregate_power_to: complex = (
                    phase_powers_to["A"] + phase_powers_to["B"] + phase_powers_to["C"]
                )

                self._apply_branch_pf_phase_initialization(
                    mdl=mdl,
                    phase_voltages_from=phase_voltages_from,
                    phase_voltages_to=phase_voltages_to,
                    phase_powers_from=phase_powers_from,
                    phase_powers_to=phase_powers_to,
                    aggregate_power_from=aggregate_power_from,
                    aggregate_power_to=aggregate_power_to,
                )
            else:
                pass

    def _try_set_branch_pf_init_balanced(
            self,
            mdl: Block,
            branch_index: int,
            f_bus_idx: int,
            t_bus_idx: int,
            sbase: float,
            is_vsc: bool = False,
            vsc_index: int = -1
    ) -> None:
        """
        Initialize branch variables from balanced power-flow results.

        :param mdl: Branch symbolic block.
        :param branch_index: Branch index in the PF results.
        :param f_bus_idx: From-bus index.
        :param t_bus_idx: To-bus index.
        :param sbase: Base power.
        :param is_vsc: Whether the branch is a VSC.
        :param vsc_index: VSC index in PF results.
        :return: None.
        """
        if is_vsc and vsc_index >= 0:
            self._try_set_vsc_branch_pf_init_balanced(
                mdl=mdl,
                f_bus_idx=f_bus_idx,
                t_bus_idx=t_bus_idx,
                sbase=sbase,
                vsc_index=vsc_index,
            )
        else:
            pf_results: PowerFlowResults | None = self.power_flow_results
            if pf_results is not None:
                phase_voltages_from: Dict[str, complex] = self._get_ac_phase_voltages_from_balanced_pf(bus_index=f_bus_idx)
                phase_voltages_to: Dict[str, complex] = self._get_ac_phase_voltages_from_balanced_pf(bus_index=t_bus_idx)

                aggregate_power_from: complex = complex(pf_results.Sf[branch_index] / sbase)
                aggregate_power_to: complex = complex(pf_results.St[branch_index] / sbase)
                phase_power_from_value: complex = aggregate_power_from / 3.0
                phase_power_to_value: complex = aggregate_power_to / 3.0

                phase_powers_from: Dict[str, complex] = dict()
                phase_powers_from["N"] = 0.0 + 0.0j
                phase_powers_from["A"] = phase_power_from_value
                phase_powers_from["B"] = phase_power_from_value
                phase_powers_from["C"] = phase_power_from_value

                phase_powers_to: Dict[str, complex] = dict()
                phase_powers_to["N"] = 0.0 + 0.0j
                phase_powers_to["A"] = phase_power_to_value
                phase_powers_to["B"] = phase_power_to_value
                phase_powers_to["C"] = phase_power_to_value

                self._apply_branch_pf_phase_initialization(
                    mdl=mdl,
                    phase_voltages_from=phase_voltages_from,
                    phase_voltages_to=phase_voltages_to,
                    phase_powers_from=phase_powers_from,
                    phase_powers_to=phase_powers_to,
                    aggregate_power_from=aggregate_power_from,
                    aggregate_power_to=aggregate_power_to,
                )
            else:
                pass

    def _try_set_inj_pf_init(self,
                             inj: Any,
                             mdl: Block,
                             bus_index: int,
                             sbase: float) -> None:
        """
        Initialize injection variables from three-phase power-flow results.

        :param inj: Injection device.
        :param mdl: Injection symbolic block.
        :param bus_index: Bus index in the PF results.
        :param sbase: Base power.
        :return: None.
        """
        if inj.bus.is_dc:
            p_dc = float(np.real(self.power_flow_results.Sbus[bus_index]))
            v_dc = float(np.abs(self.power_flow_results.voltage[bus_index]))
            self.set_init_guess(mdl=mdl, reference_powerflow=VarPowerFlowRefferenceType.P, val=p_dc)

            if v_dc != 0.0:
                self.set_if_exists(mdl=mdl, key=VarPowerFlowRefferenceType.Idc, value=p_dc / v_dc)
            else:
                self.set_if_exists(mdl=mdl, key=VarPowerFlowRefferenceType.Idc, value=0.0)
        else:
            phase_voltages: Dict[str, complex] = self._get_ac_phase_voltages_from_3ph_pf(bus_index=bus_index)
            phase_powers: Dict[str, complex] = dict()
            phase_powers["N"] = complex(self.power_flow_results_3ph.Sbus_N[bus_index] / sbase)
            phase_powers["A"] = complex(self.power_flow_results_3ph.Sbus_A[bus_index] / sbase)
            phase_powers["B"] = complex(self.power_flow_results_3ph.Sbus_B[bus_index] / sbase)
            phase_powers["C"] = complex(self.power_flow_results_3ph.Sbus_C[bus_index] / sbase)
            self._apply_injection_ac_pf_initialization(
                mdl=mdl,
                phase_voltages=phase_voltages,
                phase_powers=phase_powers,
            )

    def _try_set_inj_pf_init_balanced(self,
                                      inj: Any,
                                      mdl: Block,
                                      bus_index: int,
                                      sbase: float) -> None:
        """
        Initialize injection variables from balanced power-flow results.

        :param inj: Injection device.
        :param mdl: Injection symbolic block.
        :param bus_index: Bus index in the PF results.
        :param sbase: Base power.
        :return: None.
        """
        if inj.bus.is_dc:
            p_dc = float(np.real(self.power_flow_results.Sbus[bus_index]))
            v_dc = float(np.abs(self.power_flow_results.voltage[bus_index]))
            self.set_init_guess(mdl=mdl, reference_powerflow=VarPowerFlowRefferenceType.P, val=p_dc)

            if abs(v_dc) > 1e-12:
                self.set_if_exists(mdl=mdl, key=VarPowerFlowRefferenceType.Idc, value=p_dc / v_dc)
            else:
                self.set_if_exists(mdl=mdl, key=VarPowerFlowRefferenceType.Idc, value=0.0)
        else:
            phase_voltages: Dict[str, complex] = self._get_ac_phase_voltages_from_balanced_pf(bus_index=bus_index)
            phase_power_value: complex = complex(self.power_flow_results.Sbus[bus_index] / sbase) / 3.0
            phase_powers: Dict[str, complex] = dict()
            phase_powers["N"] = 0.0 + 0.0j
            phase_powers["A"] = phase_power_value
            phase_powers["B"] = phase_power_value
            phase_powers["C"] = phase_power_value
            self._apply_injection_ac_pf_initialization(
                mdl=mdl,
                phase_voltages=phase_voltages,
                phase_powers=phase_powers,
            )

    def _try_set_bergeron_pf_init(
            self,
            mdl: Block,
            rt: BergeronHistoryRuntime,
            branch_index: int,
            f_bus_idx: int,
            t_bus_idx: int,
            sbase: float
    ) -> None:
        """
        Initialize Bergeron history terms from three-phase power-flow results.

        The history sources are initialized so that, at t = 0:
            i_f(0) = Gc * v_f(0) + Ih_f(0)
            i_t(0) = Gc * v_t(0) + Ih_t(0)

        Hence:
            Ih_f(0) = i_f(0) - Gc * v_f(0)
            Ih_t(0) = i_t(0) - Gc * v_t(0)

        Only active phases in the Bergeron runtime are considered.
        """
        voltage_dict: Dict[str, Optional[np.ndarray]] = {
            "N": self.power_flow_results_3ph.voltage_N,
            "A": self.power_flow_results_3ph.voltage_A,
            "B": self.power_flow_results_3ph.voltage_B,
            "C": self.power_flow_results_3ph.voltage_C,
        }

        sf_array_dict: Dict[str, Optional[np.ndarray]] = {
            "N": None,
            "A": self.power_flow_results_3ph.Sf_A,
            "B": self.power_flow_results_3ph.Sf_B,
            "C": self.power_flow_results_3ph.Sf_C,
        }

        st_array_dict: Dict[str, Optional[np.ndarray]] = {
            "N": None,
            "A": self.power_flow_results_3ph.St_A,
            "B": self.power_flow_results_3ph.St_B,
            "C": self.power_flow_results_3ph.St_C,
        }

        v_f0_red = np.zeros(rt.m, dtype=np.float64)
        v_t0_red = np.zeros(rt.m, dtype=np.float64)
        i_f0_red = np.zeros(rt.m, dtype=np.float64)
        i_t0_red = np.zeros(rt.m, dtype=np.float64)

        for k, ph in enumerate(rt.active_ph):
            voltage_array = voltage_dict[ph]

            if voltage_array is None:
                vf_ph = 0.0 + 0.0j
                vt_ph = 0.0 + 0.0j
            else:
                vf_ph = voltage_array[f_bus_idx]
                vt_ph = voltage_array[t_bus_idx]

            # Instantaneous voltage at t = 0 with your EMT convention
            v_f0_red[k] = float(np.sqrt(2.0) * np.imag(vf_ph))
            v_t0_red[k] = float(np.sqrt(2.0) * np.imag(vt_ph))

            sf_array = sf_array_dict[ph]
            st_array = st_array_dict[ph]

            if sf_array is None or abs(vf_ph) <= 1e-12:
                i_f = 0.0 + 0.0j
            else:
                sf_ph = sf_array[branch_index] / sbase
                i_f = np.conj(sf_ph / vf_ph)

            if st_array is None or abs(vt_ph) <= 1e-12:
                i_t = 0.0 + 0.0j
            else:
                st_ph = st_array[branch_index] / sbase
                i_t = np.conj(st_ph / vt_ph)

            # Instantaneous current at t = 0 with your EMT convention
            i_f0_red[k] = float(np.sqrt(2.0) * np.imag(i_f))
            i_t0_red[k] = float(np.sqrt(2.0) * np.imag(i_t))

        Ih_f0_red = i_f0_red - rt.Gc_red @ v_f0_red
        Ih_t0_red = i_t0_red - rt.Gc_red @ v_t0_red

        for k in range(rt.m):
            mdl.event_dict[rt.Ih_f[k]] = self.grid.var_factory.add_const(float(Ih_f0_red[k]))
            mdl.event_dict[rt.Ih_t[k]] = self.grid.var_factory.add_const(float(Ih_t0_red[k]))

        rt.initialize_buffers_from_initial_point(
            v_f0_red=v_f0_red,
            v_t0_red=v_t0_red,
            i_f0_red=i_f0_red,
            i_t0_red=i_t0_red,
        )

    def _try_set_bergeron_pf_init_balanced(
            self,
            mdl: Block,
            rt: BergeronHistoryRuntime,
            branch_index: int,
            f_bus_idx: int,
            t_bus_idx: int,
            sbase: float
    ) -> None:
        """
        Initialize Bergeron history terms from balanced power-flow results.

        Assumptions
        -----------
        - self.power_flow_results.voltage contains one complex bus-voltage phasor per bus
          (balanced positive-sequence representation).
        - self.power_flow_results.Sf and self.power_flow_results.St contain the total
          three-phase complex power at each branch end.
        - The balanced abc phase voltages are reconstructed from the bus phasor as:
                V_A = V1
                V_B = V1 * exp(-j*2*pi/3)
                V_C = V1 * exp(+j*2*pi/3)
        - Per-phase power is:
                S_phase = S_3ph / 3
        - Per-phase current is:
                I_phase = conj(S_phase / V_phase)

        EMT initialization convention kept identical to the existing 3-phase version:
                x(0) = sqrt(2) * imag(X_phasor)

        Neutral phase, if present, is initialized to zero.
        """
        pf_results = self.power_flow_results

        alpha = 2.0 * np.pi / 3.0

        v_f_bus = pf_results.voltage[f_bus_idx]
        v_t_bus = pf_results.voltage[t_bus_idx]

        s_f_3ph = pf_results.Sf[branch_index] / sbase
        s_t_3ph = pf_results.St[branch_index] / sbase

        s_f_phase = s_f_3ph / 3.0
        s_t_phase = s_t_3ph / 3.0

        v_f0_red = np.zeros(rt.m, dtype=np.float64)
        v_t0_red = np.zeros(rt.m, dtype=np.float64)
        i_f0_red = np.zeros(rt.m, dtype=np.float64)
        i_t0_red = np.zeros(rt.m, dtype=np.float64)

        for k, ph in enumerate(rt.active_ph):

            if ph == "N":
                vf_ph = 0.0 + 0.0j
                vt_ph = 0.0 + 0.0j
                i_f = 0.0 + 0.0j
                i_t = 0.0 + 0.0j

            elif ph == "A":
                vf_ph = v_f_bus
                vt_ph = v_t_bus

                if abs(vf_ph) <= 1e-12:
                    i_f = 0.0 + 0.0j
                else:
                    i_f = np.conj(s_f_phase / vf_ph)

                if abs(vt_ph) <= 1e-12:
                    i_t = 0.0 + 0.0j
                else:
                    i_t = np.conj(s_t_phase / vt_ph)

            elif ph == "B":
                vf_ph = v_f_bus * np.exp(-1j * alpha)
                vt_ph = v_t_bus * np.exp(-1j * alpha)

                if abs(vf_ph) <= 1e-12:
                    i_f = 0.0 + 0.0j
                else:
                    i_f = np.conj(s_f_phase / vf_ph)

                if abs(vt_ph) <= 1e-12:
                    i_t = 0.0 + 0.0j
                else:
                    i_t = np.conj(s_t_phase / vt_ph)

            elif ph == "C":
                vf_ph = v_f_bus * np.exp(+1j * alpha)
                vt_ph = v_t_bus * np.exp(+1j * alpha)

                if abs(vf_ph) <= 1e-12:
                    i_f = 0.0 + 0.0j
                else:
                    i_f = np.conj(s_f_phase / vf_ph)

                if abs(vt_ph) <= 1e-12:
                    i_t = 0.0 + 0.0j
                else:
                    i_t = np.conj(s_t_phase / vt_ph)

            else:
                raise ValueError(f"Unsupported phase label in Bergeron runtime: {ph}")

            # Instantaneous values at t = 0 using the same EMT convention as the original code
            v_f0_red[k] = float(np.sqrt(2.0) * np.imag(vf_ph))
            v_t0_red[k] = float(np.sqrt(2.0) * np.imag(vt_ph))
            i_f0_red[k] = float(np.sqrt(2.0) * np.imag(i_f))
            i_t0_red[k] = float(np.sqrt(2.0) * np.imag(i_t))

        Ih_f0_red = i_f0_red - rt.Gc_red @ v_f0_red
        Ih_t0_red = i_t0_red - rt.Gc_red @ v_t0_red

        for k in range(rt.m):
            mdl.event_dict[rt.Ih_f[k]] = self.grid.var_factory.add_const(float(Ih_f0_red[k]))
            mdl.event_dict[rt.Ih_t[k]] = self.grid.var_factory.add_const(float(Ih_t0_red[k]))

        rt.initialize_buffers_from_initial_point(
            v_f0_red=v_f0_red,
            v_t0_red=v_t0_red,
            i_f0_red=i_f0_red,
            i_t0_red=i_t0_red,
        )


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
                if mapped_var in mdl.event_dict:
                    mdl.event_dict[mapped_var] = self.grid.var_factory.add_const(float(value))
                else:
                    self._temp_init_guess[mapped_var.uid] = float(value)

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
                is_time_aligned: bool = _is_time_aligned(t_curr, event_time)

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

    def _collect_runtime_mode_parameters(self) -> List[Var]:
        """
        Collect runtime parameters that must be retained between steps.

        This includes:
          - scheduled discrete mode parameters,
          - Bergeron line history parameters, which are updated explicitly by the runtime.
        """
        mode_parameters: List[Var] = list()
        seen: Set[int] = set()

        # 1) Scheduled mode parameters already registered through mode_dict
        for parameter in self.get_runtime_mode_parameters():
            if parameter.uid not in seen:
                seen.add(parameter.uid)
                mode_parameters.append(parameter)

        # 2) Bergeron history parameters must also be retained
        for rt in self.history_models:
            for parameter in rt.Ih_f:
                if parameter.uid not in seen:
                    seen.add(parameter.uid)
                    mode_parameters.append(parameter)

            for parameter in rt.Ih_t:
                if parameter.uid not in seen:
                    seen.add(parameter.uid)
                    mode_parameters.append(parameter)

        return mode_parameters

    def add_device_var(self, dev: ALL_DEV_TYPES, var: Var)->None:
        """
        Registers a variable belonging to a specific device.
        """
        var_list = self._vars_info.get(dev, None)
        if var_list is None:
            self._vars_info[dev] = [var]
        else:
            if var not in var_list:
                self._vars_info[dev].append(var)



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

    def set_external_param(self, mdl: Block, key: VarPowerFlowRefferenceType, value: float) -> None:
        """
        Set a PF-derived value either as an event parameter if the mapped variable belongs to mdl.event_dict.
        """
        var = mdl.E(key)

        if var is None:
            return

        if var in mdl.event_dict:
            mdl.event_dict[var] = self.grid.var_factory.add_const(float(value))
        else:
            pass

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

    @property
    def boundary_update(self) -> EmtBoundaryUpdateProtocol | None:
        """
        Return the endogenous EMT boundary updater consumed by the EMT solvers.
        """
        if len(self._scheduled_mode_events) == 0 and len(self.history_models) == 0:
            return None

        return self

    def reset_boundary_update_state(self, t0: float = 0.0) -> None:
        """
        Reset the EMT boundary update state before a new solver run starts.

        :param t0: Initial simulation time.
        :return: None
        """
        super().reset_boundary_update_state(t0)
        self.step_counter = 0
        self._mode_event_cursor = dict()
        self._initialize_mode_event_state()

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

        # Persist the updated runtime parameters so the next step sees them
        n_runtime: int = self.get_variable_parameter_number()
        self._event_params_values[:] = full_params[:n_runtime]

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

    def _assign_api_obj_value_if_present(self, mdl: Block, key: ParamPowerFlowRefferenceType, value: Any) -> None:
        """
        Assign one mapped constant into either ``event_dict`` or ``parameters``.

        Some EMT templates expose retained parameters through ``event_dict`` while
        others keep them in the plain parameter table. This helper preserves the
        existing semantics by writing into the location already owned by the mapped
        symbolic variable.

        :param mdl: Device symbolic block.
        :param key: API mapping key.
        :param value: Numeric value to assign.
        :return: None.
        """
        api_obj_mapping_local: Any = mdl.api_obj_mapping
        if isinstance(api_obj_mapping_local, dict):
            target_local: Any | None = api_obj_mapping_local.get(key, None)
            if target_local is not None:
                if target_local in mdl.event_dict:
                    mdl.event_dict[target_local] = self._to_const(value)
                else:
                    mdl.parameters[target_local] = self._to_const(value)
            else:
                pass
        else:
            pass

    def _has_api_obj_mapping_keys(
            self,
            api_obj_mapping: Dict[ParamPowerFlowRefferenceType, Any],
            keys: List[ParamPowerFlowRefferenceType],
    ) -> bool:
        """
        Return whether an API mapping exposes all required keys.

        :param api_obj_mapping: Device API mapping dictionary.
        :param keys: Required mapping keys.
        :return: True when every key is present.
        """
        return bool(all(key in api_obj_mapping for key in keys))

    def _assign_api_obj_mapping_vsc(self, vsc: Any, vsc_index: int) -> None:
        """
        Assign PF-derived VSC control and loss parameters into the EMT mapping.

        :param vsc: VSC device.
        :param vsc_index: VSC index in PF results.
        :return: None.
        """
        p_loss0: float = 0.0
        p0_vsc: float = 0.0
        if self.power_flow_results is not None:
            try:
                p_loss0 = float(self.power_flow_results.losses_vsc[vsc_index])
            except (AttributeError, IndexError, TypeError, ValueError):
                p_loss0 = 0.0

            try:
                p0_vsc = float(np.real(self.power_flow_results.St_vsc[vsc_index]))
            except (AttributeError, IndexError, TypeError, ValueError):
                p0_vsc = 0.0
        else:
            pass

        control_code_dict: Dict[ConverterControlType | None, float] = dict()
        control_code_dict[None] = 0.0
        control_code_dict[ConverterControlType.Vm_dc] = 1.0
        control_code_dict[ConverterControlType.Vm_ac] = 2.0
        control_code_dict[ConverterControlType.Va_ac] = 3.0
        control_code_dict[ConverterControlType.Qac] = 4.0
        control_code_dict[ConverterControlType.Pdc] = 5.0
        control_code_dict[ConverterControlType.Pac] = 6.0
        control_code_dict[ConverterControlType.Pdc_angle_droop] = 7.0
        control_code_dict[ConverterControlType.Imax] = 8.0

        self._assign_api_obj_value_if_present(vsc.emt_model, ParamPowerFlowRefferenceType.Sbase, self.grid.Sbase)
        self._assign_api_obj_value_if_present(
            vsc.emt_model,
            ParamPowerFlowRefferenceType.omega_base,
            2.0 * np.pi * self.grid.fBase,
        )
        self._assign_api_obj_value_if_present(vsc.emt_model, ParamPowerFlowRefferenceType.P0, p0_vsc)
        self._assign_api_obj_value_if_present(
            vsc.emt_model,
            ParamPowerFlowRefferenceType.converter_loss_power_0,
            p_loss0,
        )
        self._assign_api_obj_value_if_present(
            vsc.emt_model,
            ParamPowerFlowRefferenceType.converter_control_mode_1,
            control_code_dict[vsc.control1],
        )
        self._assign_api_obj_value_if_present(
            vsc.emt_model,
            ParamPowerFlowRefferenceType.converter_control_mode_2,
            control_code_dict[vsc.control2],
        )
        self._assign_api_obj_value_if_present(
            vsc.emt_model,
            ParamPowerFlowRefferenceType.converter_control_target_1,
            vsc.control1_val,
        )
        self._assign_api_obj_value_if_present(
            vsc.emt_model,
            ParamPowerFlowRefferenceType.converter_control_target_2,
            vsc.control2_val,
        )

    def _assign_api_obj_mapping_transformer_report(self, br: Any, api_obj_mapping: Dict[ParamPowerFlowRefferenceType, Any]) -> bool:
        """
        Assign test-report-based transformer parameters when that mapping is present.

        :param br: Branch device.
        :param api_obj_mapping: Branch API mapping dictionary.
        :return: True when the branch was handled by this mapping path.
        """
        transformer_report_keys: List[ParamPowerFlowRefferenceType] = list([
            ParamPowerFlowRefferenceType.transformer_rated_power_mva,
            ParamPowerFlowRefferenceType.transformer_short_circuit_voltage_pct,
            ParamPowerFlowRefferenceType.transformer_short_circuit_resistance_pct,
            ParamPowerFlowRefferenceType.transformer_open_circuit_current_pct,
            ParamPowerFlowRefferenceType.transformer_open_circuit_loss_kw,
            ParamPowerFlowRefferenceType.transformer_tap_ratio,
            ParamPowerFlowRefferenceType.transformer_terminal_capacitance_pu_s,
            ParamPowerFlowRefferenceType.transformer_from_connection_aa,
            ParamPowerFlowRefferenceType.transformer_to_connection_aa,
        ])
        has_transformer_report_mapping: bool = self._has_api_obj_mapping_keys(api_obj_mapping, transformer_report_keys)

        if has_transformer_report_mapping:
            if isinstance(br, Transformer2W):
                w0: float = 2.0 * np.pi * float(self.grid.fBase)
                eps_value: float = 1e-12

                sn_value: float = max(float(br.Sn), 1e-9)
                winding1_voltage_value: float = float(br.HV) if br.HV is not None else 1.0
                winding2_voltage_value: float = float(br.LV) if br.LV is not None else 1.0
                short_circuit_voltage_pct_value: float
                short_circuit_loss_kw_value: float = max(float(br.Pcu), 0.0)
                open_circuit_loss_kw_value: float = max(float(br.Pfe), 0.0)
                open_circuit_current_pct_value: float = max(float(br.I0), 0.0)
                tap_ratio_value: float = float(br.tap_module) if abs(float(br.tap_module)) > eps_value else 1.0

                if float(br.Vsc) > 0.0:
                    short_circuit_voltage_pct_value = float(br.Vsc)
                else:
                    short_circuit_voltage_pct_value = 100.0 * np.sqrt(
                        max(float(br.R) * float(br.R) + float(br.X) * float(br.X), 0.0)
                    )

                short_circuit_resistance_pct_value: float
                if short_circuit_loss_kw_value > 0.0:
                    short_circuit_resistance_pct_value = short_circuit_loss_kw_value / (10.0 * sn_value)
                else:
                    short_circuit_resistance_pct_value = 100.0 * max(float(br.R), 0.0)

                terminal_capacitance_value: float
                if sn_value > eps_value and abs(float(br.B)) > eps_value:
                    terminal_capacitance_value = 0.5 * max(abs(float(br.B)) / (w0 + eps_value), 0.0)
                else:
                    terminal_capacitance_value = 0.0

                open_circuit_loss_pu_value: float = open_circuit_loss_kw_value / (1000.0 * sn_value)
                open_circuit_current_pu_value: float = open_circuit_current_pct_value / 100.0
                magnetizing_current_pu_value: float = np.sqrt(
                    max(
                        open_circuit_current_pu_value * open_circuit_current_pu_value
                        - open_circuit_loss_pu_value * open_circuit_loss_pu_value,
                        0.0,
                    )
                )
                if magnetizing_current_pu_value > eps_value:
                    linear_core_inductance_value: float = 1.0 / magnetizing_current_pu_value
                else:
                    linear_core_inductance_value = 1e6

                connection_from_matrix: np.ndarray = _xfmr_connection_matrix(br.conn_f)
                connection_to_matrix: np.ndarray = _xfmr_connection_matrix(br.conn_t)
                phase_permutation_matrix: np.ndarray = _xfmr_phase_permutation_matrix(int(br.vector_group_number))
                connection_to_effective_matrix: np.ndarray = phase_permutation_matrix @ connection_to_matrix

                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.omega_base, w0)
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_rated_power_mva, sn_value)
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_winding1_rated_voltage_ll_kv, winding1_voltage_value)
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_winding2_rated_voltage_ll_kv, winding2_voltage_value)
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_connection_clock, float(br.vector_group_number))
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_open_circuit_current_pct, open_circuit_current_pct_value)
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_open_circuit_loss_kw, open_circuit_loss_kw_value)
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_short_circuit_voltage_pct, short_circuit_voltage_pct_value)
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_short_circuit_resistance_pct, short_circuit_resistance_pct_value)
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_short_circuit_loss_kw, short_circuit_loss_kw_value)
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_tap_ratio, tap_ratio_value)
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_terminal_capacitance_pu_s, terminal_capacitance_value)
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_linear_core_inductance_pu_s, linear_core_inductance_value)
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_core_curve_a_prime, linear_core_inductance_value)
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_core_curve_b_prime, 0.0)
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_use_linear_core, 1.0)

                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_from_connection_aa, float(connection_from_matrix[0, 0]))
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_from_connection_ab, float(connection_from_matrix[0, 1]))
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_from_connection_ac, float(connection_from_matrix[0, 2]))
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_from_connection_ba, float(connection_from_matrix[1, 0]))
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_from_connection_bb, float(connection_from_matrix[1, 1]))
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_from_connection_bc, float(connection_from_matrix[1, 2]))
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_from_connection_ca, float(connection_from_matrix[2, 0]))
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_from_connection_cb, float(connection_from_matrix[2, 1]))
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_from_connection_cc, float(connection_from_matrix[2, 2]))

                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_to_connection_aa, float(connection_to_effective_matrix[0, 0]))
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_to_connection_ab, float(connection_to_effective_matrix[0, 1]))
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_to_connection_ac, float(connection_to_effective_matrix[0, 2]))
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_to_connection_ba, float(connection_to_effective_matrix[1, 0]))
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_to_connection_bb, float(connection_to_effective_matrix[1, 1]))
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_to_connection_bc, float(connection_to_effective_matrix[1, 2]))
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_to_connection_ca, float(connection_to_effective_matrix[2, 0]))
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_to_connection_cb, float(connection_to_effective_matrix[2, 1]))
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_to_connection_cc, float(connection_to_effective_matrix[2, 2]))
                return True
            else:
                return True
        else:
            return False

    def _assign_api_obj_mapping_transformer_coupled(self, br: Any, api_obj_mapping: Dict[ParamPowerFlowRefferenceType, Any]) -> bool:
        """
        Assign coupled-winding transformer parameters when that mapping is present.

        :param br: Branch device.
        :param api_obj_mapping: Branch API mapping dictionary.
        :return: True when the branch was handled by this mapping path.
        """
        transformer_coupled_keys: List[ParamPowerFlowRefferenceType] = list([
            ParamPowerFlowRefferenceType.transformer_winding1_resistance_pu,
            ParamPowerFlowRefferenceType.transformer_winding2_resistance_pu,
            ParamPowerFlowRefferenceType.transformer_winding1_inductance_pu_s,
            ParamPowerFlowRefferenceType.transformer_winding2_inductance_pu_s,
            ParamPowerFlowRefferenceType.transformer_mutual_inductance_pu_s,
            ParamPowerFlowRefferenceType.transformer_magnetizing_conductance_pu,
        ])
        has_transformer_coupled_mapping: bool = self._has_api_obj_mapping_keys(api_obj_mapping, transformer_coupled_keys)

        if has_transformer_coupled_mapping:
            if isinstance(br, Transformer2W):
                fbase: float = float(self.grid.fBase)
                w0: float = 2.0 * np.pi * fbase
                eps_value: float = 1e-12

                tap_ratio: float = float(br.tap_module)
                effective_tap_ratio: float
                if abs(tap_ratio) > eps_value:
                    effective_tap_ratio = tap_ratio
                else:
                    effective_tap_ratio = 1.0

                tap_ratio_sq: float = effective_tap_ratio * effective_tap_ratio
                r_total: float = float(br.R)
                x_total: float = float(br.X)
                g_core: float = float(br.G)
                b_magnetizing: float = float(br.B)

                leakage_inductance_winding1: float = 0.5 * x_total / (w0 + eps_value)
                leakage_inductance_winding2: float = leakage_inductance_winding1 / (tap_ratio_sq + eps_value)

                magnetizing_reactance: float
                if abs(b_magnetizing) > eps_value:
                    magnetizing_reactance = 1.0 / abs(b_magnetizing)
                else:
                    magnetizing_reactance = max(abs(x_total), 1.0) * 1e6

                magnetizing_inductance_winding1: float = magnetizing_reactance / (w0 + eps_value)
                magnetizing_inductance_winding2: float = magnetizing_inductance_winding1 / (tap_ratio_sq + eps_value)
                mutual_inductance: float = magnetizing_inductance_winding1 / (
                    effective_tap_ratio + np.sign(effective_tap_ratio) * eps_value
                )

                winding1_resistance_value: float = 0.5 * r_total
                winding2_resistance_value: float = 0.5 * r_total / (tap_ratio_sq + eps_value)
                winding1_inductance_value: float = leakage_inductance_winding1 + magnetizing_inductance_winding1
                winding2_inductance_value: float = leakage_inductance_winding2 + magnetizing_inductance_winding2
                determinant_value: float = (
                    winding1_inductance_value * winding2_inductance_value - mutual_inductance * mutual_inductance
                )

                if determinant_value <= eps_value:
                    raise ValueError(
                        f"Transformer '{br.name}' has a non-physical inductance matrix determinant {determinant_value}."
                    )
                else:
                    pass

                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_winding1_resistance_pu, winding1_resistance_value)
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_winding2_resistance_pu, winding2_resistance_value)
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_winding1_inductance_pu_s, winding1_inductance_value)
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_winding2_inductance_pu_s, winding2_inductance_value)
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_mutual_inductance_pu_s, mutual_inductance)
                self._assign_api_obj_param_if_present(br.emt_model, ParamPowerFlowRefferenceType.transformer_magnetizing_conductance_pu, g_core)
                return True
            else:
                return True
        else:
            return False

    def _assign_api_obj_mapping_branch(self,
                                       br: Any,
                                       is_vsc: bool,
                                       vsc_index: int) -> None:
        """
        Assign branch EMT mapped parameters into the API object mapping.

        The routine supports the historical pi-line mapping contract and the
        classical transformer coupled-winding contract. Each template exposes a
        fixed symbolic parameter interface, and this stage injects the numerical
        values derived from the corresponding static API object.

        :param br: Branch device whose EMT model receives the mapped values.
        :return: None.
        :raises ValueError: If the reduced physical matrices are inconsistent.
        """
        if is_vsc:
            vsc = br
            if 0 <= vsc_index < len(self.grid.vsc_devices):
                vsc = self.grid.vsc_devices[vsc_index]
            else:
                pass

            self._assign_api_obj_mapping_vsc(vsc=vsc, vsc_index=vsc_index)
            return
        else:
            pass

        api_obj_mapping: Any = br.emt_model.api_obj_mapping
        if not isinstance(api_obj_mapping, dict):
            return

        # -----------------------------
        # 1. Handle the XFMR EMT transformer mapping before the classical
        # transformer path and before the line path.
        # -----------------------------
        if self._assign_api_obj_mapping_transformer_report(br=br, api_obj_mapping=api_obj_mapping):
            return
        else:
            pass

        # -----------------------------
        # 2. Handle the classical transformer mapping before the line path.
        # The transformer block now exposes only symbolic winding parameters,
        # so the EMT assembler must derive and assign the numerical values here.
        # -----------------------------
        if self._assign_api_obj_mapping_transformer_coupled(br=br, api_obj_mapping=api_obj_mapping):
            return
        else:
            pass

        if ParamPowerFlowRefferenceType.Rnn not in api_obj_mapping:
            return
        else:
            pass

        # -----------------------------
        # 3. Resolve the physical phase layout from the line connection.
        # This selects the reduced subspace that exists in the physical line,
        # which is the basis for placing values into the global 4x4 NABC map.
        # -----------------------------
        ph_mask: list[bool] = list([
            bool(br.ys.phN),
            bool(br.ys.phA),
            bool(br.ys.phB),
            bool(br.ys.phC),
        ])
        idx_global: list[int] = list(i for i, is_active in enumerate(ph_mask) if is_active)
        n_active: int = len(idx_global)

        # -----------------------------
        # 4. Convert the physical line matrices into the EMT per-unit form.
        # The EMT template is parameterized in per-unit R, L^-1 and C values,
        # so this stage preserves the existing numerical pipeline exactly.
        # -----------------------------
        fbase: float = self.grid.fBase
        w0: float = 2.0 * np.pi * fbase
        v_base: float = br.bus_from.Vnom * 1e3
        s_base_mva: float = self.grid.Sbase
        s_base_va: float = s_base_mva * 1e6
        z_base: float = (v_base * v_base) / s_base_va
        y_base: float = 1.0 / z_base

        # z_phys: np.ndarray = br.template.z_nabc * br.length
        # y_phys: np.ndarray = br.template.y_nabc * br.length
        #
        # z_pu: np.ndarray = z_phys / z_base
        # y_pu: np.ndarray = y_phys / y_base
        #
        # r_full: np.ndarray = np.real(z_pu)
        # x_full: np.ndarray = np.imag(z_pu)
        # l_full: np.ndarray = x_full / (w0 + 1e-20)
        # bsh_full: np.ndarray = np.imag(y_pu)
        # c_full: np.ndarray = (bsh_full / (w0 + 1e-20)) / 2.0

        try:
            # if a tower is set to the branch it has the full matrix
            z_phys: np.ndarray = br.template.z_nabc * br.length
            y_phys: np.ndarray = br.template.y_nabc * br.length

            z_pu: np.ndarray = z_phys / z_base
            y_pu: np.ndarray = y_phys / y_base

            r_full: np.ndarray = np.real(z_pu)
            x_full: np.ndarray = np.imag(z_pu)
            l_full: np.ndarray = x_full / (w0 + 1e-20)
            bsh_full: np.ndarray = np.imag(y_pu)
            c_full: np.ndarray = (bsh_full / (w0 + 1e-20)) / 2.0
        except:
            # if the result is running from balanced powerflow the user can not set a tower template to the line, then the line becomes uncoupled
            R: int = br.R
            X: int = br.B
            B: int = br.X

            r_full: np.ndarray = np.array([[R, 0.0, 0.0],[0.0, R, 0.0],[0.0, 0.0, R]])
            x_full: np.ndarray = np.array([[X, 0.0, 0.0],[0.0, X, 0.0],[0.0, 0.0, X]])
            l_full: np.ndarray = x_full / (w0 + 1e-20)
            bsh_full: np.ndarray = np.array([[B, 0.0, 0.0],[0.0, B, 0.0],[0.0, 0.0, B]])
            c_full: np.ndarray = (bsh_full / (w0 + 1e-20)) / 2.0


        # -----------------------------
        # 5. Validate the reduced matrices before mapping them.
        # These checks keep bad topology or singular data from silently
        # corrupting the full API mapping used by the EMT assembly.
        # -----------------------------
        expected_shape: tuple[int, int] = (n_active, n_active)

        if r_full.shape != expected_shape:
            raise ValueError(
            f"Line '{br.name}' must have a {n_active}x{n_active} Z matrix based on active phases. "
            f"Got {r_full.shape}."
        )
        if l_full.shape != expected_shape or c_full.shape != expected_shape:
            raise ValueError(
                f"Line '{br.name}' has inconsistent matrix shapes: "
                f"R={r_full.shape}, L={l_full.shape}, C={c_full.shape}."
            )

        try:
            l_inv_full: np.ndarray = np.linalg.inv(l_full)
        except np.linalg.LinAlgError as exc:
            raise ValueError(
                f"Inductance matrix L for line '{br.name}' is singular and cannot be inverted."
            ) from exc

        # -----------------------------
        # 6. Define the fixed global NABC mapping contract.
        # Both the EMT initializer and the EMT template rely on the same enum
        # layout so that active reduced matrices land in deterministic slots.
        # -----------------------------
        r_enums: list[list[ParamPowerFlowRefferenceType]] = list([
            list([
                ParamPowerFlowRefferenceType.Rnn,
                ParamPowerFlowRefferenceType.Rna,
                ParamPowerFlowRefferenceType.Rnb,
                ParamPowerFlowRefferenceType.Rnc,
            ]),
            list([
                ParamPowerFlowRefferenceType.Ran,
                ParamPowerFlowRefferenceType.Raa,
                ParamPowerFlowRefferenceType.Rab,
                ParamPowerFlowRefferenceType.Rac,
            ]),
            list([
                ParamPowerFlowRefferenceType.Rbn,
                ParamPowerFlowRefferenceType.Rba,
                ParamPowerFlowRefferenceType.Rbb,
                ParamPowerFlowRefferenceType.Rbc,
            ]),
            list([
                ParamPowerFlowRefferenceType.Rcn,
                ParamPowerFlowRefferenceType.Rca,
                ParamPowerFlowRefferenceType.Rcb,
                ParamPowerFlowRefferenceType.Rcc,
            ]),
        ])
        linv_enums: list[list[ParamPowerFlowRefferenceType]] = list([
            list([
                ParamPowerFlowRefferenceType.Linv_nn,
                ParamPowerFlowRefferenceType.Linv_na,
                ParamPowerFlowRefferenceType.Linv_nb,
                ParamPowerFlowRefferenceType.Linv_nc,
            ]),
            list([
                ParamPowerFlowRefferenceType.Linv_an,
                ParamPowerFlowRefferenceType.Linv_aa,
                ParamPowerFlowRefferenceType.Linv_ab,
                ParamPowerFlowRefferenceType.Linv_ac,
            ]),
            list([
                ParamPowerFlowRefferenceType.Linv_bn,
                ParamPowerFlowRefferenceType.Linv_ba,
                ParamPowerFlowRefferenceType.Linv_bb,
                ParamPowerFlowRefferenceType.Linv_bc,
            ]),
            list([
                ParamPowerFlowRefferenceType.Linv_cn,
                ParamPowerFlowRefferenceType.Linv_ca,
                ParamPowerFlowRefferenceType.Linv_cb,
                ParamPowerFlowRefferenceType.Linv_cc,
            ]),
        ])
        c_enums: list[list[ParamPowerFlowRefferenceType]] = list([
            list([
                ParamPowerFlowRefferenceType.Cnn,
                ParamPowerFlowRefferenceType.Cna,
                ParamPowerFlowRefferenceType.Cnb,
                ParamPowerFlowRefferenceType.Cnc,
            ]),
            list([
                ParamPowerFlowRefferenceType.Can,
                ParamPowerFlowRefferenceType.Caa,
                ParamPowerFlowRefferenceType.Cab,
                ParamPowerFlowRefferenceType.Cac,
            ]),
            list([
                ParamPowerFlowRefferenceType.Cbn,
                ParamPowerFlowRefferenceType.Cba,
                ParamPowerFlowRefferenceType.Cbb,
                ParamPowerFlowRefferenceType.Cbc,
            ]),
            list([
                ParamPowerFlowRefferenceType.Ccn,
                ParamPowerFlowRefferenceType.Cca,
                ParamPowerFlowRefferenceType.Ccb,
                ParamPowerFlowRefferenceType.Ccc,
            ]),
        ])
        # -----------------------------
        # 6. Reset the full 4x4 map and then write the active reduced values.
        # Zeroing all entries preserves the previous semantics for inactive
        # rows and columns, which the template later reduces with line.ys.
        # -----------------------------
        for i_glob in range(4):
            for j_glob in range(4):
                self._assign_api_obj_param_if_present(br.emt_model, r_enums[i_glob][j_glob], 0.0)
                self._assign_api_obj_param_if_present(br.emt_model, linv_enums[i_glob][j_glob], 0.0)
                self._assign_api_obj_param_if_present(br.emt_model, c_enums[i_glob][j_glob], 0.0)

        for i_red, i_glob in enumerate(idx_global):
            for j_red, j_glob in enumerate(idx_global):
                self._assign_api_obj_param_if_present(br.emt_model, r_enums[i_glob][j_glob],
                                                      float(r_full[i_red, j_red]))
                self._assign_api_obj_param_if_present(
                    br.emt_model,
                    linv_enums[i_glob][j_glob],
                    float(l_inv_full[i_red, j_red])
                )
                self._assign_api_obj_param_if_present(br.emt_model, c_enums[i_glob][j_glob],
                                                      float(c_full[i_red, j_red]))

    def _assign_api_obj_mapping_load(self, load) -> None:
        """
        Assign PF-derived static load parameters into the EMT model API mapping.
        :param load: Load device.
        :return: None.
        """
        fbase: float = self.grid.fBase
        sbase: float = self.grid.Sbase
        w0: float = 2.0 * np.pi * fbase

        p_values: List[float] = list([
            load.Pa / sbase,
            load.Pb / sbase,
            load.Pc / sbase,
        ])
        q_values: List[float] = list([
            load.Qa / sbase,
            load.Qb / sbase,
            load.Qc / sbase,
        ])
        p_keys: List[ParamPowerFlowRefferenceType] = list([
            ParamPowerFlowRefferenceType.Pl0_A,
            ParamPowerFlowRefferenceType.Pl0_B,
            ParamPowerFlowRefferenceType.Pl0_C,
        ])
        q_keys: List[ParamPowerFlowRefferenceType] = list([
            ParamPowerFlowRefferenceType.Ql0_A,
            ParamPowerFlowRefferenceType.Ql0_B,
            ParamPowerFlowRefferenceType.Ql0_C,
        ])

        if not load.bus.is_dc:
            for idx in range(3):
                self._assign_api_obj_param_if_present(load.emt_model, p_keys[idx], p_values[idx])
                self._assign_api_obj_param_if_present(load.emt_model, q_keys[idx], q_values[idx])

            self._assign_api_obj_param_if_present(load.emt_model, ParamPowerFlowRefferenceType.omega_base, w0)
        else:
            dc_p_value: float = load.P / sbase
            dc_g_value: float = load.G / sbase

            if dc_g_value == 0.0:
                dc_p_value = 0.0
                dc_g_value = load.P / sbase
            else:
                pass

            self._assign_api_obj_param_if_present(load.emt_model, ParamPowerFlowRefferenceType.Pl0, dc_p_value)
            self._assign_api_obj_param_if_present(load.emt_model, ParamPowerFlowRefferenceType.g, dc_g_value)

    def _assign_api_obj_mapping_generator(self, gen) -> None:
        """
        Assign PF-derived static generator parameters into the EMT model API mapping.

        :param gen: Generator device.
        :return: None.
        """
        fbase: float = self.grid.fBase
        w0: float = 2.0 * np.pi * fbase

        self._assign_api_obj_param_if_present(gen.emt_model, ParamPowerFlowRefferenceType.omega_base, w0)
        self._assign_api_obj_param_if_present(gen.emt_model, ParamPowerFlowRefferenceType.R1, gen.R1)
        self._assign_api_obj_param_if_present(gen.emt_model, ParamPowerFlowRefferenceType.X1, gen.X1)
        self._assign_api_obj_param_if_present(gen.emt_model, ParamPowerFlowRefferenceType.X0, gen.X0)


