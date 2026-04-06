# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

"""
AI dialogue window for VeraGrid.

This module provides the GUI shell around the provider-agnostic backend.
The objective is to expose a VeraGrid-style chat window with explicit backend
configuration, live app-derived context and a visible transcript.
"""

import html
import json
import os
from enum import Enum
from typing import Any, Optional, TYPE_CHECKING

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from VeraGrid.Gui.AiAgent.ai_backend import ApprovalPolicy
from VeraGrid.Gui.AiAgent.ai_backend import ChatMessage
from VeraGrid.Gui.AiAgent.ai_backend import ConversationOrchestrator
from VeraGrid.Gui.AiAgent.ai_backend import ConversationRunResult
from VeraGrid.Gui.AiAgent.ai_backend import ModelListResult
from VeraGrid.Gui.AiAgent.ai_backend import PendingApproval
from VeraGrid.Gui.AiAgent.ai_backend import PromptFactory
from VeraGrid.Gui.AiAgent.ai_backend import ProviderConfig
from VeraGrid.Gui.AiAgent.ai_backend import ProviderType
from VeraGrid.Gui.AiAgent.ai_backend import ToolErrorCode
from VeraGrid.Gui.AiAgent.ai_backend import ToolRegistry
from VeraGrid.Gui.AiAgent.ai_backend import ToolExecutionResult
from VeraGrid.Gui.AiAgent.ai_backend import ToolRisk
from VeraGrid.Gui.AiAgent.ai_backend import ToolSpec
from VeraGrid.Gui.AiAgent.ai_backend import VeraGridContext
from VeraGrid.Gui.AiAgent.ai_backend import build_default_tool_registry
from VeraGrid.Gui.AiAgent.ai_backend import build_provider
from VeraGrid.Gui.AiAgent.ai_backend import list_provider_models
from VeraGrid.Gui.AiAgent.ai_chat_gui import Ui_AiChatDialog
from VeraGrid.Gui.Analysis.object_plot_analysis import GridErrorLog
from VeraGrid.Gui.Analysis.object_plot_analysis import grid_analysis
from VeraGrid.Gui.AiAgent.ai_retrieval import ProgramKnowledgeIndex
from VeraGrid.Gui.AiAgent.ai_retrieval import RuntimeKnowledgeSnapshot
from VeraGrid.Gui.AiAgent.ai_retrieval import build_default_knowledge_package_name
from VeraGrid.Gui.AiAgent.ai_retrieval import build_retrieved_context_text
from VeraGrid.Gui.AiAgent.ai_retrieval import build_runtime_knowledge_snapshot
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Simulations.PowerFlow.power_flow_ts_results import PowerFlowTimeSeriesResults
from VeraGridEngine.enumerations import SimulationTypes

if TYPE_CHECKING:
    from VeraGrid.Gui.Main.SubClasses.simulations import SimulationsMain


class SnapshotPayloadTool:
    """
    Read-only tool returning a fixed JSON payload.

    :param payload_json: JSON payload returned by the tool.
    """

    __slots__ = ("_payload_json",)

    def __init__(self, payload_json: str) -> None:
        """
        Store the fixed payload.

        :param payload_json: JSON payload returned by the tool.
        """
        self._payload_json: str = payload_json

    def execute(self, arguments: dict[str, object]) -> ToolExecutionResult:
        """
        Return the stored payload.

        :param arguments: Tool arguments.
        :returns: Tool execution result.
        """
        return ToolExecutionResult(
            success=True,
            error_code=ToolErrorCode.NONE,
            error_message="",
            payload_json=self._payload_json,
        )


class SnapshotBusListTool:
    """
    Read-only tool exposing a snapshotted bus list with filters.

    :param bus_records: Snapshotted bus records.
    :param selected_bus_idtags: Selected bus identifier set.
    """

    __slots__ = (
        "_bus_records",
        "_selected_bus_idtags",
    )

    def __init__(self, bus_records: list[dict[str, object]], selected_bus_idtags: set[str]) -> None:
        """
        Store the snapshotted bus data.

        :param bus_records: Snapshotted bus records.
        :param selected_bus_idtags: Selected bus identifier set.
        """
        self._bus_records: list[dict[str, object]] = bus_records
        self._selected_bus_idtags: set[str] = selected_bus_idtags

    def execute(self, arguments: dict[str, object]) -> ToolExecutionResult:
        """
        Return the bus snapshot filtered by the supplied arguments.

        :param arguments: Tool arguments.
        :returns: Tool execution result.
        """
        kv_min_obj: object = arguments.get("kv_min", None)
        limit_obj: object = arguments.get("limit", None)
        only_selected_obj: object = arguments.get("only_selected", None)
        kv_min: Optional[float] = None
        limit: int = 25
        only_selected: bool = False
        filtered_records: list[dict[str, object]] = list()
        index: int = 0

        if kv_min_obj is None:
            kv_min = None
        else:
            if isinstance(kv_min_obj, (int, float)):
                kv_min = float(kv_min_obj)
            else:
                return ToolExecutionResult(
                    success=False,
                    error_code=ToolErrorCode.EXECUTION_ERROR,
                    error_message="Invalid kv_min filter.",
                    payload_json="{}",
                )

        if limit_obj is None:
            limit = 25
        else:
            if isinstance(limit_obj, int) and (limit_obj > 0):
                limit = limit_obj
            else:
                return ToolExecutionResult(
                    success=False,
                    error_code=ToolErrorCode.EXECUTION_ERROR,
                    error_message="Invalid limit filter.",
                    payload_json="{}",
                )

        if only_selected_obj is None:
            only_selected = False
        else:
            if isinstance(only_selected_obj, bool):
                only_selected = only_selected_obj
            else:
                return ToolExecutionResult(
                    success=False,
                    error_code=ToolErrorCode.EXECUTION_ERROR,
                    error_message="Invalid only_selected flag.",
                    payload_json="{}",
                )

        while index < len(self._bus_records):
            record: dict[str, object] = self._bus_records[index]
            nominal_voltage_obj: object = record.get("nominal_voltage_kv", None)
            idtag_obj: object = record.get("idtag", None)
            include_record: bool = True

            if only_selected:
                if isinstance(idtag_obj, str) and (idtag_obj in self._selected_bus_idtags):
                    include_record = True
                else:
                    include_record = False
            else:
                pass

            if include_record and (kv_min is not None):
                if isinstance(nominal_voltage_obj, (int, float)):
                    include_record = float(nominal_voltage_obj) >= kv_min
                else:
                    include_record = False
            else:
                pass

            if include_record:
                filtered_records.append(record)
                if len(filtered_records) >= limit:
                    index = len(self._bus_records)
                else:
                    pass
            else:
                pass

            index += 1

        return ToolExecutionResult(
            success=True,
            error_code=ToolErrorCode.NONE,
            error_message="",
            payload_json=json.dumps(
                {
                    "count": len(filtered_records),
                    "items": filtered_records,
                },
                ensure_ascii=False,
            ),
        )


class SnapshotStudySummaryTool:
    """
    Read-only tool exposing snapshotted study summaries.

    :param active_study: Active study name.
    :param payload_by_study: Summary payloads by study name.
    """

    __slots__ = (
        "_active_study",
        "_payload_by_study",
    )

    def __init__(self, active_study: Optional[str], payload_by_study: dict[str, dict[str, object]]) -> None:
        """
        Store the snapshotted study summaries.

        :param active_study: Active study name.
        :param payload_by_study: Summary payloads by study name.
        """
        self._active_study: Optional[str] = active_study
        self._payload_by_study: dict[str, dict[str, object]] = payload_by_study

    def execute(self, arguments: dict[str, object]) -> ToolExecutionResult:
        """
        Return the requested or active study summary.

        :param arguments: Tool arguments.
        :returns: Tool execution result.
        """
        study_name_obj: object = arguments.get("study_name", None)
        study_name: Optional[str] = None
        payload: Optional[dict[str, object]] = None

        if study_name_obj is None:
            study_name = self._active_study
        else:
            if isinstance(study_name_obj, str):
                study_name = study_name_obj
            else:
                return ToolExecutionResult(
                    success=False,
                    error_code=ToolErrorCode.EXECUTION_ERROR,
                    error_message="Invalid study_name value.",
                    payload_json="{}",
                )

        if study_name is None:
            return ToolExecutionResult(
                success=False,
                error_code=ToolErrorCode.EXECUTION_ERROR,
                error_message="There is no active study selected.",
                payload_json="{}",
            )
        else:
            payload = self._payload_by_study.get(study_name, None)

        if payload is None:
            return ToolExecutionResult(
                success=False,
                error_code=ToolErrorCode.EXECUTION_ERROR,
                error_message=f"Study '{study_name}' is not available in the current session.",
                payload_json="{}",
            )
        else:
            return ToolExecutionResult(
                success=True,
                error_code=ToolErrorCode.NONE,
                error_message="",
                payload_json=json.dumps(payload, ensure_ascii=False),
            )


class RuntimeSnapshotSearchTool:
    """
    Read-only tool exposing lexical search over the live runtime snapshot.

    :param runtime_snapshot: Runtime snapshot.
    """

    __slots__ = ("_runtime_snapshot",)

    def __init__(self, runtime_snapshot: RuntimeKnowledgeSnapshot) -> None:
        """
        Store the runtime snapshot.

        :param runtime_snapshot: Runtime snapshot.
        """
        self._runtime_snapshot: RuntimeKnowledgeSnapshot = runtime_snapshot

    def execute(self, arguments: dict[str, object]) -> ToolExecutionResult:
        """
        Search the runtime snapshot.

        :param arguments: Tool arguments.
        :returns: Tool execution result.
        """
        query_obj: object = arguments.get("query", None)
        category_obj: object = arguments.get("category", None)
        limit_obj: object = arguments.get("limit", None)
        query_text: str
        category_text: Optional[str] = None
        limit_value: int = 6
        hits: list[object]
        items: list[dict[str, object]] = list()
        index: int = 0

        if isinstance(query_obj, str) and (len(query_obj.strip()) > 0):
            query_text = query_obj.strip()
        else:
            return ToolExecutionResult(
                success=False,
                error_code=ToolErrorCode.EXECUTION_ERROR,
                error_message="The query argument must be a non-empty string.",
                payload_json="{}",
            )

        if isinstance(category_obj, str) and (len(category_obj.strip()) > 0):
            category_text = category_obj.strip()
        else:
            category_text = None

        if isinstance(limit_obj, int) and (limit_obj > 0):
            limit_value = min(limit_obj, 12)
        else:
            pass

        hits = self._runtime_snapshot.search(
            query=query_text,
            top_k=limit_value,
            category=category_text,
        )

        while index < len(hits):
            hit = hits[index]
            items.append(
                {
                    "title": hit.record.title,
                    "category": hit.record.category,
                    "score": hit.score,
                    "excerpt": hit.excerpt,
                    "content": hit.record.content,
                }
            )
            index += 1

        return ToolExecutionResult(
            success=True,
            error_code=ToolErrorCode.NONE,
            error_message="",
            payload_json=json.dumps(
                {
                    "query": query_text,
                    "category": category_text,
                    "count": len(items),
                    "items": items,
                },
                ensure_ascii=False,
            ),
        )


class RuntimeSnapshotRecordTool:
    """
    Read-only tool exposing exact runtime records by title.

    :param runtime_snapshot: Runtime snapshot.
    """

    __slots__ = ("_runtime_snapshot",)

    def __init__(self, runtime_snapshot: RuntimeKnowledgeSnapshot) -> None:
        """
        Store the runtime snapshot.

        :param runtime_snapshot: Runtime snapshot.
        """
        self._runtime_snapshot: RuntimeKnowledgeSnapshot = runtime_snapshot

    def execute(self, arguments: dict[str, object]) -> ToolExecutionResult:
        """
        Return one runtime record by exact title.

        :param arguments: Tool arguments.
        :returns: Tool execution result.
        """
        title_obj: object = arguments.get("title", None)
        record = None

        if isinstance(title_obj, str) and (len(title_obj.strip()) > 0):
            record = self._runtime_snapshot.find_record_by_title(title_obj.strip())
        else:
            return ToolExecutionResult(
                success=False,
                error_code=ToolErrorCode.EXECUTION_ERROR,
                error_message="The title argument must be a non-empty string.",
                payload_json="{}",
            )

        if record is None:
            return ToolExecutionResult(
                success=False,
                error_code=ToolErrorCode.EXECUTION_ERROR,
                error_message=f"Runtime record '{title_obj}' was not found.",
                payload_json="{}",
            )
        else:
            return ToolExecutionResult(
                success=True,
                error_code=ToolErrorCode.NONE,
                error_message="",
                payload_json=json.dumps(
                    {
                        "title": record.title,
                        "category": record.category,
                        "content": record.content,
                    },
                    ensure_ascii=False,
                ),
            )


def build_default_grid_analysis_parameters() -> dict[str, object]:
    """
    Build the default grid-analysis parameters used by the AI diagnostics tool.

    :returns: Grid-analysis parameter dictionary.
    """
    parameters: dict[str, object] = dict()

    parameters["analyze_ts"] = True
    parameters["imbalance_threshold"] = 0.02
    parameters["v_low"] = 0.95
    parameters["v_high"] = 1.05
    parameters["tap_min"] = 0.95
    parameters["tap_max"] = 1.05
    parameters["transformer_virtual_tap_tolerance"] = 0.1
    parameters["branch_connection_voltage_tolerance"] = 0.1
    parameters["min_vcc"] = 8.0
    parameters["max_vcc"] = 18.0
    parameters["branch_x_threshold"] = 1e-4
    parameters["condition_number_threshold"] = 1e-4
    parameters["eps_max"] = 1e20
    parameters["eps_min"] = 1e-20

    return parameters


def build_grid_error_log_entries(error_log: GridErrorLog) -> list[dict[str, object]]:
    """
    Convert a ``GridErrorLog`` into a JSON-safe list of issue entries.

    :param error_log: Grid error log.
    :returns: Issue-entry list.
    """
    entries: list[dict[str, object]] = list()

    for message_text, message_entries in error_log.logs.items():
        message_index: int = 0

        while message_index < len(message_entries):
            entry: list[object] = message_entries[message_index]
            severity_text: str = str(entry[3].value) if hasattr(entry[3], "value") else str(entry[3])
            entries.append(
                {
                    "message": str(message_text),
                    "object_type": str(entry[0]),
                    "element_name": str(entry[1]),
                    "element_index": int(entry[2]),
                    "severity": severity_text,
                    "property_name": str(entry[4]),
                    "lower": str(entry[5]),
                    "value": str(entry[6]),
                    "upper": str(entry[7]),
                }
            )
            message_index += 1

    return entries


def build_grid_analysis_payload_from_app(
    app: "SimulationsMain",
    analyze_time_series: bool,
    max_issue_count: int,
) -> dict[str, object]:
    """
    Run VeraGrid structural diagnostics and return a JSON-safe payload.

    :param app: VeraGrid main window.
    :param analyze_time_series: Whether to analyze time-series consistency.
    :param max_issue_count: Maximum issue entries to include in the payload.
    :returns: Grid-diagnostic payload.
    """
    parameters: dict[str, object] = build_default_grid_analysis_parameters()
    error_log: GridErrorLog = GridErrorLog()
    fixable_errors: list[object]
    issue_entries: list[dict[str, object]]
    severity_counts: dict[str, int] = dict()
    message_counts: dict[str, int] = dict()
    limited_issue_entries: list[dict[str, object]] = list()
    index: int = 0
    payload: dict[str, object] = dict()

    parameters["analyze_ts"] = analyze_time_series
    parameters["logger"] = error_log
    fixable_errors = grid_analysis(
        circuit=app.circuit,
        analyze_ts=bool(parameters["analyze_ts"]),
        imbalance_threshold=float(parameters["imbalance_threshold"]),
        v_low=float(parameters["v_low"]),
        v_high=float(parameters["v_high"]),
        tap_min=float(parameters["tap_min"]),
        tap_max=float(parameters["tap_max"]),
        transformer_virtual_tap_tolerance=float(parameters["transformer_virtual_tap_tolerance"]),
        branch_connection_voltage_tolerance=float(parameters["branch_connection_voltage_tolerance"]),
        min_vcc=float(parameters["min_vcc"]),
        max_vcc=float(parameters["max_vcc"]),
        logger=error_log,
        branch_x_threshold=float(parameters["branch_x_threshold"]),
        condition_number_threshold=float(parameters["condition_number_threshold"]),
        eps_max=float(parameters["eps_max"]),
        eps_min=float(parameters["eps_min"]),
    )
    issue_entries = build_grid_error_log_entries(error_log)

    while index < len(issue_entries):
        severity_text: str = str(issue_entries[index]["severity"])
        message_text: str = str(issue_entries[index]["message"])

        if severity_text in severity_counts:
            severity_counts[severity_text] += 1
        else:
            severity_counts[severity_text] = 1

        if message_text in message_counts:
            message_counts[message_text] += 1
        else:
            message_counts[message_text] = 1

        if len(limited_issue_entries) < max_issue_count:
            limited_issue_entries.append(issue_entries[index])
        else:
            pass

        index += 1

    payload["project_name"] = get_current_project_name_from_app(app)
    payload["issue_count"] = len(issue_entries)
    payload["fixable_issue_count"] = len(fixable_errors)
    payload["severity_counts"] = severity_counts
    payload["top_messages"] = [
        {
            "message": message_text,
            "count": count_value,
        }
        for message_text, count_value in sort_message_count_items(message_counts)[:12]
    ]
    payload["issues"] = limited_issue_entries
    payload["analyze_time_series"] = analyze_time_series

    return payload


def sort_message_count_items(message_counts: dict[str, int]) -> list[tuple[str, int]]:
    """
    Sort message-count pairs by descending count and ascending message text.

    :param message_counts: Message-count dictionary.
    :returns: Sorted message-count items.
    """
    items: list[tuple[str, int]] = list(message_counts.items())
    items.sort(key=sort_message_count_item)
    return items


def sort_message_count_item(item: tuple[str, int]) -> tuple[int, str]:
    """
    Build the sorting key for a message-count item.

    :param item: Message-count item.
    :returns: Sorting key.
    """
    return (-item[1], item[0])


def build_grid_diagnostic_summary_text(payload: dict[str, object]) -> str:
    """
    Build a concise assistant-facing summary from a grid-diagnostic payload.

    :param payload: Grid-diagnostic payload.
    :returns: Summary text.
    """
    issue_count_obj: object = payload.get("issue_count", 0)
    fixable_issue_count_obj: object = payload.get("fixable_issue_count", 0)
    top_messages_obj: object = payload.get("top_messages", list())
    lines: list[str] = list()
    index: int = 0

    lines.append(
        f"Detected {issue_count_obj} grid issues, with {fixable_issue_count_obj} marked as fixable."
    )

    if isinstance(top_messages_obj, list) and (len(top_messages_obj) > 0):
        lines.append("Most relevant issues:")

        while index < min(len(top_messages_obj), 5):
            item: object = top_messages_obj[index]
            if isinstance(item, dict):
                lines.append(f"- {item.get('message', '')} ({item.get('count', 0)})")
            else:
                pass
            index += 1
    else:
        lines.append("No structural issues were reported by the grid analysis.")

    return "\n".join(lines)


def is_direct_grid_diagnostics_request(message_text: str) -> bool:
    """
    Check whether the user explicitly asked for grid diagnostics.

    :param message_text: User message text.
    :returns: True when the request clearly targets diagnostic analysis.
    """
    normalized_text: str = normalize_simulation_request_text(message_text)
    diagnosis_phrases: list[str] = list()
    index: int = 0

    diagnosis_phrases.append("what is wrong with the grid")
    diagnosis_phrases.append("what's wrong with the grid")
    diagnosis_phrases.append("what is wrong with this grid")
    diagnosis_phrases.append("what's wrong with this grid")
    diagnosis_phrases.append("problems with the grid")
    diagnosis_phrases.append("issues with the grid")
    diagnosis_phrases.append("diagnose the grid")
    diagnosis_phrases.append("analyze the grid")
    diagnosis_phrases.append("grid diagnostics")
    diagnosis_phrases.append("grid diagnosis")

    while index < len(diagnosis_phrases):
        if diagnosis_phrases[index] in normalized_text:
            return True
        else:
            pass
        index += 1

    return False


class MainThreadGridDiagnosticsRunner(QtCore.QObject):
    """
    Main-thread bridge used to run VeraGrid grid diagnostics safely from the AI worker.

    :param app: VeraGrid main window.
    """

    request_run = QtCore.Signal(object, object)

    __slots__ = (
        "_app",
        "_pending_result",
    )

    def __init__(self, app: "SimulationsMain") -> None:
        """
        Build the main-thread diagnostics bridge.

        :param app: VeraGrid main window.
        """
        QtCore.QObject.__init__(self)
        self._app: SimulationsMain = app
        self._pending_result: ToolExecutionResult = ToolExecutionResult(
            success=False,
            error_code=ToolErrorCode.EXECUTION_ERROR,
            error_message="The grid diagnostics tool did not run.",
            payload_json="{}",
        )
        self.request_run.connect(
            self._execute_grid_diagnostics,
            QtCore.Qt.ConnectionType.BlockingQueuedConnection,
        )

    def run_diagnostics(self, analyze_time_series: bool, max_issue_count: int) -> ToolExecutionResult:
        """
        Launch VeraGrid grid diagnostics on the GUI thread.

        :param analyze_time_series: Whether to analyze time-series consistency.
        :param max_issue_count: Maximum issue count to include in the payload.
        :returns: Tool execution result.
        """
        self.request_run.emit(analyze_time_series, max_issue_count)
        return self._pending_result

    @QtCore.Slot(object, object)
    def _execute_grid_diagnostics(
        self,
        analyze_time_series_obj: object,
        max_issue_count_obj: object,
    ) -> None:
        """
        Execute the grid diagnostics action on the GUI thread.

        :param analyze_time_series_obj: Analyze-time-series flag.
        :param max_issue_count_obj: Maximum issue count.
        :returns: Nothing.
        """
        analyze_time_series: bool = bool(analyze_time_series_obj)
        max_issue_count: int = int(max_issue_count_obj) if isinstance(max_issue_count_obj, int) else 20
        payload: dict[str, object] = build_grid_analysis_payload_from_app(
            app=self._app,
            analyze_time_series=analyze_time_series,
            max_issue_count=max_issue_count,
        )

        self._pending_result = ToolExecutionResult(
            success=True,
            error_code=ToolErrorCode.NONE,
            error_message="",
            payload_json=json.dumps(payload, ensure_ascii=False),
        )


class LiveGridDiagnosticsTool:
    """
    Live VeraGrid tool that runs the structural grid diagnostics.

    :param app: VeraGrid main window.
    """

    __slots__ = ("_runner",)

    def __init__(self, app: "SimulationsMain") -> None:
        """
        Build the live grid-diagnostics tool.

        :param app: VeraGrid main window.
        """
        self._runner: MainThreadGridDiagnosticsRunner = MainThreadGridDiagnosticsRunner(app)

    def execute(self, arguments: dict[str, object]) -> ToolExecutionResult:
        """
        Execute the live grid-diagnostics tool.

        :param arguments: Tool arguments.
        :returns: Tool execution result.
        """
        analyze_time_series_obj: object = arguments.get("analyze_time_series", True)
        max_issue_count_obj: object = arguments.get("max_issue_count", 20)
        analyze_time_series: bool = True
        max_issue_count: int = 20

        if isinstance(analyze_time_series_obj, bool):
            analyze_time_series = analyze_time_series_obj
        else:
            pass

        if isinstance(max_issue_count_obj, int) and (max_issue_count_obj > 0):
            max_issue_count = min(max_issue_count_obj, 100)
        else:
            pass

        return self._runner.run_diagnostics(
            analyze_time_series=analyze_time_series,
            max_issue_count=max_issue_count,
        )


class AiSimulationCommand(Enum):
    """
    Simulation commands exposed to the AI layer.

    The values are stable identifiers used by the tool schema and the
    deterministic direct-command parser.
    """
    POWER_FLOW = "power_flow"
    POWER_FLOW_3PH = "power_flow_3ph"
    SHORT_CIRCUIT = "short_circuit"
    CONTINUATION_POWER_FLOW = "continuation_power_flow"
    POWER_FLOW_TIME_SERIES = "power_flow_time_series"
    STOCHASTIC_POWER_FLOW = "stochastic_power_flow"
    STATE_ESTIMATION = "state_estimation"
    OPTIMAL_POWER_FLOW = "optimal_power_flow"
    OPTIMAL_POWER_FLOW_TIME_SERIES = "optimal_power_flow_time_series"
    OPTIMAL_NET_TRANSFER_CAPACITY = "optimal_net_transfer_capacity"
    OPTIMAL_NET_TRANSFER_CAPACITY_TIME_SERIES = "optimal_net_transfer_capacity_time_series"
    INPUTS_ANALYSIS = "inputs_analysis"
    LINEAR_ANALYSIS = "linear_analysis"
    LINEAR_ANALYSIS_TIME_SERIES = "linear_analysis_time_series"
    CONTINGENCY_ANALYSIS = "contingency_analysis"
    CONTINGENCY_ANALYSIS_TIME_SERIES = "contingency_analysis_time_series"
    AVAILABLE_TRANSFER_CAPACITY = "available_transfer_capacity"
    AVAILABLE_TRANSFER_CAPACITY_TIME_SERIES = "available_transfer_capacity_time_series"
    CLUSTERING_ANALYSIS = "clustering_analysis"
    SIGMA_ANALYSIS = "sigma_analysis"
    NODE_GROUPS = "node_groups"
    INVESTMENTS_EVALUATION = "investments_evaluation"
    RELIABILITY_STUDY = "reliability_study"
    RMS_DYNAMIC = "rms_dynamic"
    RMS_SMALL_SIGNAL = "rms_small_signal"
    EMT_DYNAMIC = "emt_dynamic"
    EMT_SMALL_SIGNAL = "emt_small_signal"
    NODAL_CAPACITY = "nodal_capacity"


class SimulationCommandDefinition:
    """
    Explicit definition for one VeraGrid simulation command.

    :param command: Stable AI command identifier.
    :param display_name: User-facing simulation name.
    :param aliases: Direct-command aliases expected in user prompts.
    :param running_simulation_tpe: Simulation type tracked by the session, if any.
    :param assistant_message: Default assistant acknowledgement message.
    :param optimistic_success: Whether the action should be considered executed
        even when the session does not expose a running driver afterwards.
    """

    __slots__ = (
        "command",
        "display_name",
        "aliases",
        "running_simulation_tpe",
        "assistant_message",
        "optimistic_success",
    )

    def __init__(
        self,
        command: AiSimulationCommand,
        display_name: str,
        aliases: list[str],
        running_simulation_tpe: Optional[SimulationTypes],
        assistant_message: str,
        optimistic_success: bool,
    ) -> None:
        """
        Store one explicit simulation command definition.

        :param command: Stable AI command identifier.
        :param display_name: User-facing simulation name.
        :param aliases: Direct-command aliases expected in user prompts.
        :param running_simulation_tpe: Simulation type tracked by the session, if any.
        :param assistant_message: Default assistant acknowledgement message.
        :param optimistic_success: Whether the action should be considered
            executed even when the session does not expose a running driver afterwards.
        """
        self.command: AiSimulationCommand = command
        self.display_name: str = display_name
        self.aliases: list[str] = aliases
        self.running_simulation_tpe: Optional[SimulationTypes] = running_simulation_tpe
        self.assistant_message: str = assistant_message
        self.optimistic_success: bool = optimistic_success


def build_simulation_command_definitions() -> list[SimulationCommandDefinition]:
    """
    Build the explicit VeraGrid simulation command definitions.

    The order is intentional: more specific aliases come first so the direct
    parser does not accidentally match a generic phrase such as "power flow"
    before "optimal power flow" or "power flow time series".

    :returns: Ordered simulation command definitions.
    """
    definitions: list[SimulationCommandDefinition] = list()

    definitions.append(
        SimulationCommandDefinition(
            command=AiSimulationCommand.OPTIMAL_NET_TRANSFER_CAPACITY_TIME_SERIES,
            display_name="Optimal net transfer capacity time series",
            aliases=["optimal net transfer capacity time series", "opf ntc time series", "ntc opf time series"],
            running_simulation_tpe=SimulationTypes.OPF_NTC_TS_run,
            assistant_message="Started the optimal net transfer capacity time series study.",
            optimistic_success=False,
        )
    )
    definitions.append(
        SimulationCommandDefinition(
            command=AiSimulationCommand.OPTIMAL_NET_TRANSFER_CAPACITY,
            display_name="Optimal net transfer capacity",
            aliases=["optimal net transfer capacity", "opf ntc", "ntc opf"],
            running_simulation_tpe=SimulationTypes.OPF_NTC_run,
            assistant_message="Started the optimal net transfer capacity study.",
            optimistic_success=False,
        )
    )
    definitions.append(
        SimulationCommandDefinition(
            command=AiSimulationCommand.OPTIMAL_POWER_FLOW_TIME_SERIES,
            display_name="Optimal power flow time series",
            aliases=["optimal power flow time series", "opf time series"],
            running_simulation_tpe=SimulationTypes.OPFTimeSeries_run,
            assistant_message="Started the optimal power flow time series study.",
            optimistic_success=False,
        )
    )
    definitions.append(
        SimulationCommandDefinition(
            command=AiSimulationCommand.OPTIMAL_POWER_FLOW,
            display_name="Optimal power flow",
            aliases=["optimal power flow", "opf"],
            running_simulation_tpe=SimulationTypes.OPF_run,
            assistant_message="Started the optimal power flow study.",
            optimistic_success=False,
        )
    )
    definitions.append(
        SimulationCommandDefinition(
            command=AiSimulationCommand.AVAILABLE_TRANSFER_CAPACITY_TIME_SERIES,
            display_name="Available transfer capacity time series",
            aliases=["available transfer capacity time series", "atc time series"],
            running_simulation_tpe=SimulationTypes.NetTransferCapacityTS_run,
            assistant_message="Started the available transfer capacity time series study.",
            optimistic_success=False,
        )
    )
    definitions.append(
        SimulationCommandDefinition(
            command=AiSimulationCommand.AVAILABLE_TRANSFER_CAPACITY,
            display_name="Available transfer capacity",
            aliases=["available transfer capacity", "atc"],
            running_simulation_tpe=SimulationTypes.NetTransferCapacity_run,
            assistant_message="Started the available transfer capacity study.",
            optimistic_success=False,
        )
    )
    definitions.append(
        SimulationCommandDefinition(
            command=AiSimulationCommand.CONTINGENCY_ANALYSIS_TIME_SERIES,
            display_name="Contingency analysis time series",
            aliases=["contingency analysis time series", "otdf time series", "contingency time series"],
            running_simulation_tpe=SimulationTypes.ContingencyAnalysisTS_run,
            assistant_message="Started the contingency analysis time series study.",
            optimistic_success=False,
        )
    )
    definitions.append(
        SimulationCommandDefinition(
            command=AiSimulationCommand.CONTINGENCY_ANALYSIS,
            display_name="Contingency analysis",
            aliases=["contingency analysis", "contingencies", "otdf"],
            running_simulation_tpe=SimulationTypes.ContingencyAnalysis_run,
            assistant_message="Started the contingency analysis study.",
            optimistic_success=False,
        )
    )
    definitions.append(
        SimulationCommandDefinition(
            command=AiSimulationCommand.LINEAR_ANALYSIS_TIME_SERIES,
            display_name="Linear analysis time series",
            aliases=["linear analysis time series", "ptdf time series"],
            running_simulation_tpe=SimulationTypes.LinearAnalysis_TS_run,
            assistant_message="Started the linear analysis time series study.",
            optimistic_success=False,
        )
    )
    definitions.append(
        SimulationCommandDefinition(
            command=AiSimulationCommand.LINEAR_ANALYSIS,
            display_name="Linear analysis",
            aliases=["linear analysis", "linear power flow", "ptdf"],
            running_simulation_tpe=SimulationTypes.LinearAnalysis_run,
            assistant_message="Started the linear analysis study.",
            optimistic_success=False,
        )
    )
    definitions.append(
        SimulationCommandDefinition(
            command=AiSimulationCommand.CONTINUATION_POWER_FLOW,
            display_name="Continuation power flow",
            aliases=["continuation power flow", "voltage stability"],
            running_simulation_tpe=SimulationTypes.ContinuationPowerFlow_run,
            assistant_message="Started the continuation power flow study.",
            optimistic_success=False,
        )
    )
    definitions.append(
        SimulationCommandDefinition(
            command=AiSimulationCommand.POWER_FLOW_TIME_SERIES,
            display_name="Power flow time series",
            aliases=["power flow time series", "time series power flow"],
            running_simulation_tpe=SimulationTypes.PowerFlowTimeSeries_run,
            assistant_message="Started the power flow time series study.",
            optimistic_success=False,
        )
    )
    definitions.append(
        SimulationCommandDefinition(
            command=AiSimulationCommand.POWER_FLOW_3PH,
            display_name="3-phase power flow",
            aliases=["three phase power flow", "three-phase power flow", "3 phase power flow", "3-phase power flow"],
            running_simulation_tpe=SimulationTypes.PowerFlow3ph_run,
            assistant_message="Started the 3-phase power flow study.",
            optimistic_success=False,
        )
    )
    definitions.append(
        SimulationCommandDefinition(
            command=AiSimulationCommand.POWER_FLOW,
            display_name="Power flow",
            aliases=["power flow", "load flow"],
            running_simulation_tpe=SimulationTypes.PowerFlow_run,
            assistant_message="Started the standard power flow study.",
            optimistic_success=False,
        )
    )
    definitions.append(
        SimulationCommandDefinition(
            command=AiSimulationCommand.STOCHASTIC_POWER_FLOW,
            display_name="Stochastic power flow",
            aliases=["stochastic power flow", "monte carlo power flow", "latin hypercube power flow"],
            running_simulation_tpe=SimulationTypes.StochasticPowerFlow,
            assistant_message="Started the stochastic power flow study.",
            optimistic_success=False,
        )
    )
    definitions.append(
        SimulationCommandDefinition(
            command=AiSimulationCommand.SHORT_CIRCUIT,
            display_name="Short circuit",
            aliases=["short circuit", "short-circuit"],
            running_simulation_tpe=SimulationTypes.ShortCircuit_run,
            assistant_message="Started the short-circuit study.",
            optimistic_success=False,
        )
    )
    definitions.append(
        SimulationCommandDefinition(
            command=AiSimulationCommand.STATE_ESTIMATION,
            display_name="State estimation",
            aliases=["state estimation"],
            running_simulation_tpe=SimulationTypes.StateEstimation_run,
            assistant_message="Started the state estimation study.",
            optimistic_success=False,
        )
    )
    definitions.append(
        SimulationCommandDefinition(
            command=AiSimulationCommand.INPUTS_ANALYSIS,
            display_name="Inputs analysis",
            aliases=["inputs analysis"],
            running_simulation_tpe=SimulationTypes.InputsAnalysis_run,
            assistant_message="Started the inputs analysis study.",
            optimistic_success=False,
        )
    )
    definitions.append(
        SimulationCommandDefinition(
            command=AiSimulationCommand.CLUSTERING_ANALYSIS,
            display_name="Clustering analysis",
            aliases=["clustering analysis", "clustering"],
            running_simulation_tpe=SimulationTypes.ClusteringAnalysis_run,
            assistant_message="Started the clustering analysis.",
            optimistic_success=False,
        )
    )
    definitions.append(
        SimulationCommandDefinition(
            command=AiSimulationCommand.SIGMA_ANALYSIS,
            display_name="Sigma analysis",
            aliases=["sigma analysis"],
            running_simulation_tpe=SimulationTypes.SigmaAnalysis_run,
            assistant_message="Executed the sigma analysis command. Review the sigma window or VeraGrid messages for details.",
            optimistic_success=True,
        )
    )
    definitions.append(
        SimulationCommandDefinition(
            command=AiSimulationCommand.NODE_GROUPS,
            display_name="Node groups",
            aliases=["find node groups", "node groups"],
            running_simulation_tpe=SimulationTypes.NodeGrouping_run,
            assistant_message="Executed the node-groups command. Review VeraGrid for PTDF prerequisites or resulting markers.",
            optimistic_success=True,
        )
    )
    definitions.append(
        SimulationCommandDefinition(
            command=AiSimulationCommand.INVESTMENTS_EVALUATION,
            display_name="Investments evaluation",
            aliases=["investments evaluation", "investment evaluation"],
            running_simulation_tpe=SimulationTypes.InvestmentsEvaluation_run,
            assistant_message="Started the investments evaluation study.",
            optimistic_success=False,
        )
    )
    definitions.append(
        SimulationCommandDefinition(
            command=AiSimulationCommand.NODAL_CAPACITY,
            display_name="Nodal capacity",
            aliases=["nodal capacity", "hosting capacity"],
            running_simulation_tpe=SimulationTypes.NodalCapacityTimeSeries_run,
            assistant_message="Started the nodal capacity study.",
            optimistic_success=False,
        )
    )
    definitions.append(
        SimulationCommandDefinition(
            command=AiSimulationCommand.RELIABILITY_STUDY,
            display_name="Reliability study",
            aliases=["reliability study", "reliability"],
            running_simulation_tpe=SimulationTypes.Reliability_run,
            assistant_message="Started the reliability study.",
            optimistic_success=False,
        )
    )
    definitions.append(
        SimulationCommandDefinition(
            command=AiSimulationCommand.RMS_SMALL_SIGNAL,
            display_name="RMS small-signal stability",
            aliases=["rms small signal", "rms small-signal", "small signal rms", "small-signal rms"],
            running_simulation_tpe=SimulationTypes.RmsSmallSignal_run,
            assistant_message="Started the RMS small-signal stability study.",
            optimistic_success=False,
        )
    )
    definitions.append(
        SimulationCommandDefinition(
            command=AiSimulationCommand.EMT_SMALL_SIGNAL,
            display_name="EMT small-signal stability",
            aliases=["emt small signal", "emt small-signal", "small signal emt", "small-signal emt"],
            running_simulation_tpe=SimulationTypes.EmtSmallSignal_run,
            assistant_message="Started the EMT small-signal stability study.",
            optimistic_success=False,
        )
    )
    definitions.append(
        SimulationCommandDefinition(
            command=AiSimulationCommand.RMS_DYNAMIC,
            display_name="Dynamic RMS simulation",
            aliases=["dynamic rms simulation", "rms dynamic simulation", "rms simulation"],
            running_simulation_tpe=SimulationTypes.RmsDynamic_run,
            assistant_message="Started the dynamic RMS simulation.",
            optimistic_success=False,
        )
    )
    definitions.append(
        SimulationCommandDefinition(
            command=AiSimulationCommand.EMT_DYNAMIC,
            display_name="Dynamic EMT simulation",
            aliases=["dynamic emt simulation", "emt dynamic simulation", "emt simulation"],
            running_simulation_tpe=SimulationTypes.EmtDynamic_run,
            assistant_message="Started the dynamic EMT simulation.",
            optimistic_success=False,
        )
    )

    return definitions


def find_simulation_command_definition(
    command: AiSimulationCommand,
) -> Optional[SimulationCommandDefinition]:
    """
    Find the explicit definition for a simulation command.

    :param command: Simulation command identifier.
    :returns: Matching command definition or None.
    """
    definitions: list[SimulationCommandDefinition] = build_simulation_command_definitions()
    index: int = 0

    while index < len(definitions):
        if definitions[index].command == command:
            return definitions[index]
        else:
            pass
        index += 1

    return None


def parse_ai_simulation_command(
    value: str,
) -> tuple[bool, Optional[AiSimulationCommand], str]:
    """
    Parse a simulation command value from the tool payload.

    :param value: Raw command value.
    :returns: Tuple with success flag, parsed command and error message.
    """
    definitions: list[SimulationCommandDefinition] = build_simulation_command_definitions()
    index: int = 0

    while index < len(definitions):
        if definitions[index].command.value == value:
            return True, definitions[index].command, ""
        else:
            pass
        index += 1

    return False, None, f"Unsupported simulation_name '{value}'."


def normalize_simulation_request_text(message_text: str) -> str:
    """
    Normalize a user request before alias matching.

    :param message_text: Raw user message.
    :returns: Normalized text.
    """
    normalized_text: str = message_text.lower().replace("-", " ").replace("_", " ")
    return normalized_text


def is_explicit_run_request(message_text: str) -> bool:
    """
    Check whether the message explicitly asks to launch an action.

    :param message_text: User message text.
    :returns: True when the request clearly targets execution.
    """
    normalized_text: str = normalize_simulation_request_text(message_text)
    run_verbs: list[str] = [
        "run",
        "execute",
        "start",
        "launch",
        "solve",
        "calculate",
        "perform",
    ]
    index: int = 0

    while index < len(run_verbs):
        if run_verbs[index] in normalized_text:
            return True
        else:
            pass
        index += 1

    return False


def detect_direct_simulation_command(message_text: str) -> Optional[AiSimulationCommand]:
    """
    Detect an explicit simulation command from a user request.

    :param message_text: User message text.
    :returns: Matching simulation command or None.
    """
    definitions: list[SimulationCommandDefinition] = build_simulation_command_definitions()
    normalized_text: str = normalize_simulation_request_text(message_text)
    definition_index: int = 0

    if not is_explicit_run_request(normalized_text):
        return None
    else:
        pass

    while definition_index < len(definitions):
        alias_index: int = 0
        aliases: list[str] = definitions[definition_index].aliases

        while alias_index < len(aliases):
            if aliases[alias_index] in normalized_text:
                return definitions[definition_index].command
            else:
                pass
            alias_index += 1

        definition_index += 1

    return None


def build_run_simulation_schema_json() -> str:
    """
    Build the JSON schema for the generic simulation tool.

    :returns: JSON schema string.
    """
    definitions: list[SimulationCommandDefinition] = build_simulation_command_definitions()
    command_values: list[str] = list()
    description_lines: list[str] = list()
    index: int = 0

    while index < len(definitions):
        command_values.append(definitions[index].command.value)
        description_lines.append(
            f"{definitions[index].command.value}: {definitions[index].display_name}"
        )
        index += 1

    return json.dumps(
        {
            "type": "object",
            "properties": {
                "simulation_name": {
                    "type": "string",
                    "enum": command_values,
                    "description": "Supported simulations: " + "; ".join(description_lines),
                }
            },
            "required": ["simulation_name"],
            "additionalProperties": False,
        }
    )


def build_run_simulation_tool_description() -> str:
    """
    Build the generic simulation-tool description.

    :returns: Tool description.
    """
    return (
        "Run a VeraGrid simulation or analysis on the active project using the current GUI options. "
        "Choose the exact simulation_name enum value that matches the requested study."
    )


def build_simulation_tool_result(
    definition: SimulationCommandDefinition,
    started: bool,
    used_optimistic_success: bool,
) -> ToolExecutionResult:
    """
    Build the successful simulation tool response payload.

    :param definition: Simulation command definition.
    :param started: Whether VeraGrid exposed a started background study.
    :param used_optimistic_success: Whether the success was inferred for an immediate GUI action.
    :returns: Tool execution result.
    """
    payload: dict[str, object] = dict()
    payload["simulation_name"] = definition.command.value
    payload["display_name"] = definition.display_name
    payload["study_name"] = (
        None
        if definition.running_simulation_tpe is None
        else definition.running_simulation_tpe.value
    )
    payload["started"] = started
    payload["optimistic_success"] = used_optimistic_success
    payload["message"] = definition.assistant_message

    return ToolExecutionResult(
        success=True,
        error_code=ToolErrorCode.NONE,
        error_message="",
        payload_json=json.dumps(payload, ensure_ascii=False),
    )


def execute_ai_simulation_command(app: "SimulationsMain", command: AiSimulationCommand) -> None:
    """
    Execute one explicit VeraGrid simulation command on the GUI thread.

    :param app: VeraGrid main window.
    :param command: Simulation command to execute.
    :returns: Nothing.
    """
    if command == AiSimulationCommand.POWER_FLOW:
        app.power_flow_dispatcher()
    else:
        if command == AiSimulationCommand.POWER_FLOW_3PH:
            app.power_flow_3ph_dispatcher()
        else:
            if command == AiSimulationCommand.SHORT_CIRCUIT:
                app.run_short_circuit()
            else:
                if command == AiSimulationCommand.CONTINUATION_POWER_FLOW:
                    app.run_continuation_power_flow()
                else:
                    if command == AiSimulationCommand.POWER_FLOW_TIME_SERIES:
                        app.run_power_flow_time_series()
                    else:
                        if command == AiSimulationCommand.STOCHASTIC_POWER_FLOW:
                            app.run_stochastic()
                        else:
                            if command == AiSimulationCommand.STATE_ESTIMATION:
                                app.run_state_estimation()
                            else:
                                if command == AiSimulationCommand.OPTIMAL_POWER_FLOW:
                                    app.optimal_power_flow_dispatcher()
                                else:
                                    if command == AiSimulationCommand.OPTIMAL_POWER_FLOW_TIME_SERIES:
                                        app.run_opf_time_series()
                                    else:
                                        if command == AiSimulationCommand.OPTIMAL_NET_TRANSFER_CAPACITY:
                                            app.run_opf_ntc()
                                        else:
                                            if command == AiSimulationCommand.OPTIMAL_NET_TRANSFER_CAPACITY_TIME_SERIES:
                                                app.run_opf_ntc_ts()
                                            else:
                                                if command == AiSimulationCommand.INPUTS_ANALYSIS:
                                                    app.run_inputs_analysis()
                                                else:
                                                    if command == AiSimulationCommand.LINEAR_ANALYSIS:
                                                        app.linear_pf_dispatcher()
                                                    else:
                                                        if command == AiSimulationCommand.LINEAR_ANALYSIS_TIME_SERIES:
                                                            app.run_linear_analysis_ts()
                                                        else:
                                                            if command == AiSimulationCommand.CONTINGENCY_ANALYSIS:
                                                                app.contingencies_dispatcher()
                                                            else:
                                                                if command == AiSimulationCommand.CONTINGENCY_ANALYSIS_TIME_SERIES:
                                                                    app.run_contingency_analysis_ts()
                                                                else:
                                                                    if command == AiSimulationCommand.AVAILABLE_TRANSFER_CAPACITY:
                                                                        app.atc_dispatcher()
                                                                    else:
                                                                        if command == AiSimulationCommand.AVAILABLE_TRANSFER_CAPACITY_TIME_SERIES:
                                                                            app.run_available_transfer_capacity_ts()
                                                                        else:
                                                                            if command == AiSimulationCommand.CLUSTERING_ANALYSIS:
                                                                                app.run_clustering()
                                                                            else:
                                                                                if command == AiSimulationCommand.SIGMA_ANALYSIS:
                                                                                    app.run_sigma_analysis()
                                                                                else:
                                                                                    if command == AiSimulationCommand.NODE_GROUPS:
                                                                                        app.ui.actionFind_node_groups.setChecked(True)
                                                                                        app.run_find_node_groups()
                                                                                    else:
                                                                                        if command == AiSimulationCommand.INVESTMENTS_EVALUATION:
                                                                                            app.run_investments_evaluation()
                                                                                        else:
                                                                                            if command == AiSimulationCommand.RELIABILITY_STUDY:
                                                                                                app.reliability_dispatcher()
                                                                                            else:
                                                                                                if command == AiSimulationCommand.RMS_DYNAMIC:
                                                                                                    app.rms_dispatcher()
                                                                                                else:
                                                                                                    if command == AiSimulationCommand.RMS_SMALL_SIGNAL:
                                                                                                        app.rms_small_signal_dispatcher()
                                                                                                    else:
                                                                                                        if command == AiSimulationCommand.EMT_DYNAMIC:
                                                                                                            app.emt_dispatcher()
                                                                                                        else:
                                                                                                            if command == AiSimulationCommand.EMT_SMALL_SIGNAL:
                                                                                                                app.emt_small_signal_dispatcher()
                                                                                                            else:
                                                                                                                if command == AiSimulationCommand.NODAL_CAPACITY:
                                                                                                                    app.run_nodal_capacity()
                                                                                                                else:
                                                                                                                    raise ValueError(
                                                                                                                        f"Unsupported AI simulation command: {command.value}"
                                                                                                                    )


def execute_live_simulation_from_app(
    app: "SimulationsMain",
    command: AiSimulationCommand,
) -> ToolExecutionResult:
    """
    Execute a VeraGrid simulation from the live application.

    :param app: VeraGrid main window.
    :param command: Simulation command to execute.
    :returns: Tool execution result.
    """
    definition: Optional[SimulationCommandDefinition] = find_simulation_command_definition(command)
    before_remote_job_count: int = len(app._remote_jobs)
    running_simulation_tpe: Optional[SimulationTypes]
    started: bool = False

    if definition is None:
        return ToolExecutionResult(
            success=False,
            error_code=ToolErrorCode.EXECUTION_ERROR,
            error_message=f"Unsupported simulation command '{command.value}'.",
            payload_json="{}",
        )
    else:
        running_simulation_tpe = definition.running_simulation_tpe

    if running_simulation_tpe is None:
        pass
    else:
        if app.session.is_this_running(running_simulation_tpe):
            return ToolExecutionResult(
                success=False,
                error_code=ToolErrorCode.EXECUTION_ERROR,
                error_message=f"{definition.display_name} is already running.",
                payload_json="{}",
            )
        else:
            pass

    # Execute the explicit VeraGrid GUI action on the main thread.
    execute_ai_simulation_command(app, command)

    if running_simulation_tpe is None:
        started = definition.optimistic_success
    else:
        if app.session.is_this_running(running_simulation_tpe):
            started = True
        else:
            if running_simulation_tpe in app.stuff_running_now:
                started = True
            else:
                if len(app._remote_jobs) > before_remote_job_count:
                    started = True
                else:
                    started = False

    if started:
        return build_simulation_tool_result(
            definition=definition,
            started=started,
            used_optimistic_success=(definition.optimistic_success and (running_simulation_tpe is None)),
        )
    else:
        return ToolExecutionResult(
            success=False,
            error_code=ToolErrorCode.EXECUTION_ERROR,
            error_message=(
                f"VeraGrid did not report that {definition.display_name} started. "
                f"Check the GUI for prerequisite or validation messages."
            ),
            payload_json="{}",
        )


def extract_assistant_message_from_tool_result(result: ToolExecutionResult) -> str:
    """
    Extract the assistant-facing acknowledgement message from a tool result.

    :param result: Tool execution result.
    :returns: Assistant message text.
    """
    payload_obj: Any

    if not result.success:
        return result.error_message
    else:
        pass

    try:
        payload_obj = json.loads(result.payload_json)
    except json.JSONDecodeError:
        payload_obj = dict()

    if isinstance(payload_obj, dict):
        message_obj: object = payload_obj.get("message", "")
        if isinstance(message_obj, str) and (len(message_obj) > 0):
            return message_obj
        else:
            pass
    else:
        pass

    return "Executed the requested VeraGrid simulation command."


class MainThreadSimulationRunner(QtCore.QObject):
    """
    Main-thread bridge used to launch VeraGrid simulations safely from the AI worker.

    :param app: VeraGrid main window.
    """

    request_run = QtCore.Signal(object)

    __slots__ = (
        "_app",
        "_pending_result",
    )

    def __init__(self, app: "SimulationsMain") -> None:
        """
        Build the main-thread simulation bridge.

        :param app: VeraGrid main window.
        """
        QtCore.QObject.__init__(self)
        self._app: SimulationsMain = app
        self._pending_result: ToolExecutionResult = ToolExecutionResult(
            success=False,
            error_code=ToolErrorCode.EXECUTION_ERROR,
            error_message="The simulation tool did not run.",
            payload_json="{}",
        )
        self.request_run.connect(
            self._execute_requested_simulation,
            QtCore.Qt.ConnectionType.BlockingQueuedConnection,
        )

    def run_simulation(self, command: AiSimulationCommand) -> ToolExecutionResult:
        """
        Launch the requested VeraGrid simulation on the GUI thread.

        :param command: Simulation command to execute.
        :returns: Tool execution result.
        """
        self.request_run.emit(command)
        return self._pending_result

    @QtCore.Slot(object)
    def _execute_requested_simulation(self, command_obj: object) -> None:
        """
        Execute the requested simulation action on the GUI thread.

        :param command_obj: Simulation command object.
        :returns: Nothing.
        """
        if isinstance(command_obj, AiSimulationCommand):
            self._pending_result = execute_live_simulation_from_app(self._app, command_obj)
        else:
            self._pending_result = ToolExecutionResult(
                success=False,
                error_code=ToolErrorCode.EXECUTION_ERROR,
                error_message="Invalid simulation command.",
                payload_json="{}",
            )


class LiveRunSimulationTool:
    """
    Live VeraGrid tool that launches the selected simulation command.

    :param app: VeraGrid main window.
    """

    __slots__ = (
        "_runner",
    )

    def __init__(self, app: "SimulationsMain") -> None:
        """
        Build the live simulation tool.

        :param app: VeraGrid main window.
        """
        self._runner: MainThreadSimulationRunner = MainThreadSimulationRunner(app)

    def execute(self, arguments: dict[str, object]) -> ToolExecutionResult:
        """
        Execute the live simulation tool.

        :param arguments: Tool arguments.
        :returns: Tool execution result.
        """
        simulation_name_obj: object = arguments.get("simulation_name", None)
        ok_command: bool
        command: Optional[AiSimulationCommand]
        error_message: str

        if isinstance(simulation_name_obj, str):
            ok_command, command, error_message = parse_ai_simulation_command(simulation_name_obj)
            if ok_command and (command is not None):
                return self._runner.run_simulation(command)
            else:
                return ToolExecutionResult(
                    success=False,
                    error_code=ToolErrorCode.EXECUTION_ERROR,
                    error_message=error_message,
                    payload_json="{}",
                )
        else:
            return ToolExecutionResult(
                success=False,
                error_code=ToolErrorCode.EXECUTION_ERROR,
                error_message="The simulation_name argument must be a string.",
                payload_json="{}",
            )


class AiTurnExecutionRequest:
    """
    Input bundle for one background AI turn.

    :param provider_config: Provider configuration.
    :param system_prompt: System prompt.
    :param tool_registry: Snapshotted tool registry.
    :param base_history: Transcript before the current user turn.
    :param user_message: User message.
    :param approved_tool_name: Approved tool name if any.
    :param approved_arguments_json: Approved tool arguments if any.
    """

    __slots__ = (
        "provider_config",
        "system_prompt",
        "grounding_context_text",
        "tool_registry",
        "base_history",
        "user_message",
        "approved_tool_name",
        "approved_arguments_json",
    )

    def __init__(
        self,
        provider_config: ProviderConfig,
        system_prompt: str,
        grounding_context_text: str,
        tool_registry: ToolRegistry,
        base_history: list[ChatMessage],
        user_message: str,
        approved_tool_name: Optional[str],
        approved_arguments_json: Optional[str],
    ) -> None:
        """
        Store one background AI turn request.

        :param provider_config: Provider configuration.
        :param system_prompt: System prompt.
        :param grounding_context_text: Deterministic grounding context for the current turn.
        :param tool_registry: Snapshotted tool registry.
        :param base_history: Transcript before the current user turn.
        :param user_message: User message.
        :param approved_tool_name: Approved tool name if any.
        :param approved_arguments_json: Approved tool arguments if any.
        """
        self.provider_config: ProviderConfig = provider_config
        self.system_prompt: str = system_prompt
        self.grounding_context_text: str = grounding_context_text
        self.tool_registry: ToolRegistry = tool_registry
        self.base_history: list[ChatMessage] = base_history
        self.user_message: str = user_message
        self.approved_tool_name: Optional[str] = approved_tool_name
        self.approved_arguments_json: Optional[str] = approved_arguments_json


class AiTurnExecutionResponse:
    """
    Output bundle returned by the background AI worker.

    :param success: Execution success flag.
    :param request: Original execution request.
    :param result: Conversation run result.
    :param error_message: Fatal worker error message.
    """

    __slots__ = (
        "success",
        "request",
        "result",
        "error_message",
    )

    def __init__(
        self,
        success: bool,
        request: AiTurnExecutionRequest,
        result: ConversationRunResult,
        error_message: str,
    ) -> None:
        """
        Store one background AI turn response.

        :param success: Execution success flag.
        :param request: Original execution request.
        :param result: Conversation run result.
        :param error_message: Fatal worker error message.
        """
        self.success: bool = success
        self.request: AiTurnExecutionRequest = request
        self.result: ConversationRunResult = result
        self.error_message: str = error_message


class AiTurnWorker(QtCore.QObject):
    """
    Background worker that executes AI turns in a dedicated QThread.
    """

    completed = QtCore.Signal(object)

    __slots__ = (
        "_cached_provider",
        "_cached_provider_signature",
    )

    def __init__(self) -> None:
        """
        Build the worker state.
        """
        QtCore.QObject.__init__(self)
        self._cached_provider: Any = None
        self._cached_provider_signature: Optional[tuple[str, str, str, str, float]] = None

    def _build_provider_signature(self, config: ProviderConfig) -> tuple[str, str, str, str, float]:
        """
        Build the provider cache signature.

        :param config: Provider configuration.
        :returns: Cache signature tuple.
        """
        api_key_value: str = "" if config.api_key is None else config.api_key
        base_url_value: str = "" if config.base_url is None else config.base_url

        return (
            config.provider_tpe.value,
            config.model_name,
            api_key_value,
            base_url_value,
            config.timeout_s,
        )

    def _get_or_create_provider(self, config: ProviderConfig) -> Any:
        """
        Reuse or create the provider in the worker thread.

        :param config: Provider configuration.
        :returns: Provider instance.
        """
        provider_signature: tuple[str, str, str, str, float] = self._build_provider_signature(config)

        if self._cached_provider_signature == provider_signature:
            if self._cached_provider is None:
                self._cached_provider = build_provider(config)
            else:
                pass
        else:
            self._cached_provider = build_provider(config)
            self._cached_provider_signature = provider_signature

        return self._cached_provider

    @QtCore.Slot(object)
    def run_request(self, request: AiTurnExecutionRequest) -> None:
        """
        Execute one AI turn in the worker thread.

        :param request: Execution request.
        :returns: Nothing.
        """
        try:
            provider: Any = self._get_or_create_provider(request.provider_config)
            orchestrator: ConversationOrchestrator = ConversationOrchestrator(
                provider=provider,
                tool_registry=request.tool_registry,
                max_rounds=4,
            )
            result: ConversationRunResult = orchestrator.run(
                system_prompt=request.system_prompt,
                user_message=request.user_message,
                grounding_context_text=request.grounding_context_text,
                history=request.base_history,
                approved_tool_name=request.approved_tool_name,
                approved_arguments_json=request.approved_arguments_json,
            )
            self.completed.emit(
                AiTurnExecutionResponse(
                    success=True,
                    request=request,
                    result=result,
                    error_message="",
                )
            )
        except Exception as exc:
            failure_result: ConversationRunResult = build_turn_failure_result(request, str(exc))
            self.completed.emit(
                AiTurnExecutionResponse(
                    success=False,
                    request=request,
                    result=failure_result,
                    error_message=str(exc),
                )
            )


class ProviderPreset:
    """
    Provider preset used to seed the dialogue controls.

    :param provider_tpe: Backend provider type.
    :param display_name: User-facing provider name.
    :param typical_model_names: Suggested model identifiers.
    :param default_base_url: Suggested API base URL.
    """

    __slots__ = (
        "provider_tpe",
        "display_name",
        "typical_model_names",
        "default_base_url",
    )

    def __init__(
        self,
        provider_tpe: ProviderType,
        display_name: str,
        typical_model_names: list[str],
        default_base_url: str,
    ) -> None:
        """
        Build one provider preset.

        :param provider_tpe: Backend provider type.
        :param display_name: User-facing provider name.
        :param typical_model_names: Suggested model identifiers.
        :param default_base_url: Suggested API base URL.
        """
        self.provider_tpe: ProviderType = provider_tpe
        self.display_name: str = display_name
        self.typical_model_names: list[str] = typical_model_names
        self.default_base_url: str = default_base_url


class PendingConversationState:
    """
    Snapshot of a conversation waiting for tool approval.

    :param base_history: Transcript before the current user turn.
    :param user_message: User message being processed.
    :param approval: Pending approval request.
    """

    __slots__ = (
        "base_history",
        "user_message",
        "approval",
    )

    def __init__(
        self,
        base_history: list[ChatMessage],
        user_message: str,
        approval: PendingApproval,
    ) -> None:
        """
        Store the approval snapshot.

        :param base_history: Transcript before the current user turn.
        :param user_message: User message being processed.
        :param approval: Pending approval request.
        """
        self.base_history: list[ChatMessage] = base_history
        self.user_message: str = user_message
        self.approval: PendingApproval = approval


class AiBackendState:
    """
    Persistable backend-state snapshot for the AI dialogue.

    :param provider_tpe: Selected provider type.
    :param model_name: Selected model name.
    :param base_url: Provider base URL or local model path.
    :param api_key: Optional API key.
    :param timeout_s: Request timeout in seconds.
    """

    __slots__ = (
        "provider_tpe",
        "model_name",
        "base_url",
        "api_key",
        "timeout_s",
    )

    def __init__(
        self,
        provider_tpe: ProviderType,
        model_name: str,
        base_url: str,
        api_key: Optional[str],
        timeout_s: float,
    ) -> None:
        """
        Build one backend-state snapshot.

        :param provider_tpe: Selected provider type.
        :param model_name: Selected model name.
        :param base_url: Provider base URL or local model path.
        :param api_key: Optional API key.
        :param timeout_s: Request timeout in seconds.
        """
        self.provider_tpe: ProviderType = provider_tpe
        self.model_name: str = model_name
        self.base_url: str = base_url
        self.api_key: Optional[str] = api_key
        self.timeout_s: float = timeout_s


def build_provider_presets() -> list[ProviderPreset]:
    """
    Build the default provider presets displayed in the GUI.

    :returns: Ordered preset list.
    """
    presets: list[ProviderPreset] = list()

    # Local llama.cpp is the default mode because VeraGrid should work offline first.
    presets.append(
        ProviderPreset(
            provider_tpe=ProviderType.LOCAL_LLAMA_CPP,
            display_name="Local llama.cpp",
            typical_model_names=list(),
            default_base_url="",
        )
    )

    # OpenAI uses the Responses API, so the default points at the v1 root.
    presets.append(
        ProviderPreset(
            provider_tpe=ProviderType.OPENAI,
            display_name="Codex / OpenAI",
            typical_model_names=list(),
            default_base_url="https://api.openai.com/v1",
        )
    )
    presets[-1].typical_model_names.append("gpt-5.2")
    presets[-1].typical_model_names.append("gpt-5")
    presets[-1].typical_model_names.append("gpt-5-mini")
    presets[-1].typical_model_names.append("gpt-5-nano")
    presets[-1].typical_model_names.append("gpt-4.1")
    presets[-1].typical_model_names.append("gpt-4.1-mini")
    presets[-1].typical_model_names.append("gpt-4o")
    presets[-1].typical_model_names.append("gpt-4o-mini")

    # Anthropic uses its messages endpoint under the same versioned root.
    presets.append(
        ProviderPreset(
            provider_tpe=ProviderType.ANTHROPIC,
            display_name="Claude / Anthropic",
            typical_model_names=list(),
            default_base_url="https://api.anthropic.com/v1",
        )
    )
    presets[-1].typical_model_names.append("claude-opus-4-1-20250805")
    presets[-1].typical_model_names.append("claude-opus-4-20250514")
    presets[-1].typical_model_names.append("claude-sonnet-4-20250514")
    presets[-1].typical_model_names.append("claude-3-7-sonnet-latest")
    presets[-1].typical_model_names.append("claude-3-5-sonnet-latest")
    presets[-1].typical_model_names.append("claude-3-5-haiku-latest")

    # OpenAI-compatible backends usually expose a local REST endpoint.
    presets.append(
        ProviderPreset(
            provider_tpe=ProviderType.OPENAI_COMPATIBLE,
            display_name="OpenAI-compatible",
            typical_model_names=list(),
            default_base_url="http://localhost:11434/v1",
        )
    )
    presets[-1].typical_model_names.append("llama3.1")
    presets[-1].typical_model_names.append("llama3.2")
    presets[-1].typical_model_names.append("qwen2.5")
    presets[-1].typical_model_names.append("mistral-small")

    return presets


def copy_chat_history(messages: list[ChatMessage]) -> list[ChatMessage]:
    """
    Copy a transcript into a detached list.

    :param messages: Source transcript.
    :returns: Deep-enough copy for re-running a user turn.
    """
    copied_messages: list[ChatMessage] = list()
    index: int = 0

    # Copy each message explicitly so approval replays use a stable snapshot.
    while index < len(messages):
        message: ChatMessage = messages[index]
        copied_messages.append(
            ChatMessage(
                role=message.role,
                content=message.content,
                name=message.name,
            )
        )
        index += 1

    return copied_messages


def collect_non_empty_lines(text: str) -> list[str]:
    """
    Collect stripped non-empty lines from a multiline field.

    :param text: Raw multiline text.
    :returns: Filtered line list.
    """
    lines: list[str] = list()
    raw_lines: list[str] = text.splitlines()
    index: int = 0

    # The GUI stores list-like context as one item per line.
    while index < len(raw_lines):
        stripped_line: str = raw_lines[index].strip()
        if len(stripped_line) > 0:
            lines.append(stripped_line)
        else:
            pass
        index += 1

    return lines


def build_turn_failure_result(
    request: AiTurnExecutionRequest,
    error_message: str,
) -> ConversationRunResult:
    """
    Build a fallback result for worker-level failures.

    :param request: Execution request.
    :param error_message: Fatal worker error message.
    :returns: Failure run result.
    """
    transcript: list[ChatMessage] = copy_chat_history(request.base_history)
    transcript.append(ChatMessage(role="user", content=request.user_message, name=None))
    transcript.append(ChatMessage(role="assistant", content=error_message, name=None))

    return ConversationRunResult(
        final_text=error_message,
        pending_approval=None,
        transcript=transcript,
    )


def sanitize_runtime_json_value(value: object) -> object:
    """
    Convert runtime values into JSON-safe payload values.

    :param value: Runtime value.
    :returns: JSON-safe value.
    """
    if value is None:
        return None
    else:
        pass

    if isinstance(value, (str, int, float, bool)):
        return value
    else:
        pass

    if isinstance(value, np.ndarray):
        flat_value: np.ndarray = value.reshape(-1)
        sample_count: int = min(int(flat_value.shape[0]), 8)
        sample_values: list[object] = list()
        index: int = 0

        while index < sample_count:
            sample_values.append(sanitize_runtime_json_value(flat_value[index].item()))
            index += 1

        return {
            "kind": "ndarray",
            "shape": list(value.shape),
            "dtype": str(value.dtype),
            "sample": sample_values,
        }
    else:
        pass

    if isinstance(value, list):
        items: list[object] = list()
        sample_count = min(len(value), 12)
        index = 0

        while index < sample_count:
            items.append(sanitize_runtime_json_value(value[index]))
            index += 1

        return items
    else:
        pass

    if isinstance(value, tuple):
        return sanitize_runtime_json_value(list(value))
    else:
        pass

    if isinstance(value, dict):
        sanitized_dict: dict[str, object] = dict()
        for key_obj, item_value in value.items():
            sanitized_dict[str(key_obj)] = sanitize_runtime_json_value(item_value)
        return sanitized_dict
    else:
        pass

    serialized_text: str = str(value)
    if " object at 0x" in serialized_text:
        return value.__class__.__name__
    else:
        if len(serialized_text) > 160:
            return serialized_text[:160].rstrip() + "..."
        else:
            return serialized_text


def build_object_save_record(device: Any) -> dict[str, object]:
    """
    Build a JSON-safe object record from ``get_save_data()``.

    :param device: VeraGrid editable device.
    :returns: Object record.
    """
    headers: list[str] = list(device.get_headers())
    values: list[object] = list(device.get_save_data())
    record: dict[str, object] = dict()
    index: int = 0
    item_count: int = min(len(headers), len(values))

    while index < item_count:
        record[str(headers[index])] = sanitize_runtime_json_value(values[index])
        index += 1

    record["idtag"] = device.idtag
    record["name"] = device.name
    record["code"] = device.code
    record["type_name"] = device.type_name

    return record


def build_selected_element_labels_from_app(app: "SimulationsMain") -> list[str]:
    """
    Build selected-element labels from the concrete VeraGrid app.

    :param app: VeraGrid main window.
    :returns: Selected-element labels.
    """
    selected_devices: list[Any] = app.get_selected_devices()
    selected_buses: list[tuple[int, Any, object | None]] = app.get_diagram_selected_buses()
    labels: list[str] = list()
    index: int = 0

    if len(selected_devices) > 0:
        while index < len(selected_devices):
            labels.append(f"{selected_devices[index].type_name}: {selected_devices[index].name}")
            index += 1
    else:
        while index < len(selected_buses):
            _, bus, _ = selected_buses[index]
            labels.append(f"{bus.type_name}: {bus.name}")
            index += 1

    return labels


def get_current_project_name_from_app(app: "SimulationsMain") -> Optional[str]:
    """
    Read the current project name from the concrete VeraGrid app.

    :param app: VeraGrid main window.
    :returns: Project name or None.
    """
    project_name_text: str = app.circuit.name.strip()

    if len(project_name_text) == 0:
        project_name_text = app.ui.grid_name_line_edit.text().strip()
    else:
        pass

    if len(project_name_text) > 0:
        return project_name_text
    else:
        return None


def get_current_study_name_from_app(app: "SimulationsMain") -> Optional[str]:
    """
    Read the current study name from the concrete VeraGrid app.

    :param app: VeraGrid main window.
    :returns: Study name or None.
    """
    study_name_text: str = app.ui.available_results_to_color_comboBox.currentText().strip()

    if len(study_name_text) > 0:
        return study_name_text
    else:
        return None


def get_current_solver_name_from_app(app: "SimulationsMain") -> Optional[str]:
    """
    Read the current solver name from the concrete VeraGrid app.

    :param app: VeraGrid main window.
    :returns: Solver name or None.
    """
    solver_name_text: str = app.ui.engineComboBox.currentText().strip()

    if len(solver_name_text) > 0:
        return solver_name_text
    else:
        return None


def summarize_power_flow_results(results: PowerFlowResults) -> dict[str, float | bool]:
    """
    Summarize one steady-state power-flow result set.

    :param results: Power-flow results instance.
    :returns: Numeric summary dictionary.
    """
    voltage_abs: np.ndarray = np.abs(results.voltage)
    loading_abs: np.ndarray = np.abs(results.loading) * 100.0

    return {
        "converged": bool(results.converged),
        "min_voltage_pu": float(np.min(voltage_abs)),
        "max_voltage_pu": float(np.max(voltage_abs)),
        "max_branch_loading_pct": float(np.max(loading_abs)),
        "iterations": float(results.iterations),
        "elapsed_s": float(results.elapsed),
    }


def summarize_power_flow_time_series_results(
    results: PowerFlowTimeSeriesResults,
) -> dict[str, float | int]:
    """
    Summarize one power-flow time-series result set.

    :param results: Time-series power-flow results instance.
    :returns: Numeric summary dictionary.
    """
    voltage_abs: np.ndarray = np.abs(results.voltage)
    loading_abs: np.ndarray = np.abs(results.loading) * 100.0

    return {
        "time_steps": int(results.voltage.shape[0]),
        "min_voltage_pu": float(np.min(voltage_abs)),
        "max_voltage_pu": float(np.max(voltage_abs)),
        "max_branch_loading_pct": float(np.max(loading_abs)),
    }


def build_logger_summary_payload(logger_obj: object | None) -> dict[str, object]:
    """
    Build a compact logger payload from a VeraGrid driver logger.

    :param logger_obj: Logger object or None.
    :returns: Logger payload.
    """
    payload: dict[str, object] = dict()

    if logger_obj is None:
        payload["has_logger"] = False
    else:
        payload["has_logger"] = True
        payload["info_count"] = int(logger_obj.info_count())
        payload["warning_count"] = int(logger_obj.warning_count())
        payload["error_count"] = int(logger_obj.error_count())

    return payload


def build_results_payload(results_obj: object | None) -> dict[str, object]:
    """
    Build a compact payload for one VeraGrid results object.

    :param results_obj: Results object or None.
    :returns: Results payload.
    """
    payload: dict[str, object] = dict()
    available_result_tree_obj: object
    result_type_dict_obj: object
    data_variables_obj: object
    result_dict_obj: object
    result_keys: list[str] = list()
    variable_names: list[str] = list()
    index: int = 0

    if results_obj is None:
        payload["has_results"] = False
        return payload
    else:
        payload["has_results"] = True
        payload["result_class"] = results_obj.__class__.__name__

    try:
        available_result_tree_obj = results_obj.get_name_tree()
    except Exception:
        available_result_tree_obj = dict()

    try:
        result_type_dict_obj = results_obj.get_name_to_results_type_dict()
    except Exception:
        result_type_dict_obj = dict()

    payload["available_result_tree"] = sanitize_runtime_json_value(available_result_tree_obj)
    payload["available_result_types"] = sanitize_runtime_json_value(result_type_dict_obj)

    data_variables_obj = getattr(results_obj, "data_variables", None)
    if isinstance(data_variables_obj, dict):
        variable_names = list(data_variables_obj.keys())
        payload["data_variable_names"] = variable_names
        payload["data_variable_preview"] = dict()

        while index < min(len(variable_names), 8):
            variable_name: str = variable_names[index]
            try:
                variable_value: object = object.__getattribute__(results_obj, variable_name)
            except AttributeError:
                variable_value = None

            payload["data_variable_preview"][variable_name] = sanitize_runtime_json_value(variable_value)
            index += 1
    else:
        pass

    try:
        result_dict_obj = results_obj.get_dict()
    except Exception:
        result_dict_obj = dict()

    if isinstance(result_dict_obj, dict):
        result_keys = list(result_dict_obj.keys())
        payload["result_data_keys"] = result_keys
    else:
        payload["result_data_keys"] = list()

    return payload


def build_driver_payload(app: "SimulationsMain", driver: Any) -> dict[str, object]:
    """
    Build a compact payload for one session driver.

    :param app: VeraGrid main window.
    :param driver: Session driver.
    :returns: Driver payload.
    """
    payload: dict[str, object] = dict()

    payload["driver_name"] = driver.name
    payload["driver_type"] = driver.tpe.value
    payload["driver_class"] = driver.__class__.__name__
    payload["is_running"] = bool(app.session.is_this_running(driver.tpe))
    payload["elapsed_s"] = sanitize_runtime_json_value(driver.elapsed)
    payload["engine"] = sanitize_runtime_json_value(driver.engine)
    payload["logger"] = build_logger_summary_payload(driver.logger)
    payload["results"] = build_results_payload(driver.results)

    return payload


def build_study_summary_payload_from_app(
    app: "SimulationsMain",
    requested_study_name: Optional[str],
) -> tuple[bool, dict[str, object], str]:
    """
    Build a study-summary payload from the concrete VeraGrid app.

    :param app: VeraGrid main window.
    :param requested_study_name: Requested study name or None.
    :returns: Success flag, payload and error message.
    """
    study_name: Optional[str] = requested_study_name
    payload: dict[str, object] = dict()

    if study_name is None:
        study_name = get_current_study_name_from_app(app)
    else:
        pass

    if study_name is None:
        return False, dict(), "There is no active study selected."
    else:
        if study_name == SimulationTypes.DesignView.value:
            return False, dict(), "The active study is Design View, which has no simulation results."
        else:
            driver: Any = app.session.get_driver_by_name(study_name=study_name)

    if driver is None:
        return False, dict(), f"Study '{study_name}' is not available in the current session."
    else:
        if driver.results is None:
            return False, dict(), f"Study '{study_name}' does not have results loaded yet."
        else:
            pass

    payload["study_name"] = study_name
    payload["driver"] = build_driver_payload(app, driver)
    payload["driver_name"] = driver.name
    payload["driver_type"] = str(driver.tpe.value)
    payload["available_result_tree"] = driver.results.get_name_tree()
    payload["results"] = build_results_payload(driver.results)

    if driver.tpe == SimulationTypes.PowerFlow_run:
        _, results = app.session.power_flow
        if results is None:
            payload["summary"] = dict()
        else:
            payload["summary"] = summarize_power_flow_results(results)
    else:
        if driver.tpe == SimulationTypes.PowerFlowTimeSeries_run:
            _, results = app.session.power_flow_ts
            if results is None:
                payload["summary"] = dict()
            else:
                payload["summary"] = summarize_power_flow_time_series_results(results)
        else:
            payload["summary"] = dict()

    return True, payload, ""


def build_live_tool_registry_from_app(app: "SimulationsMain") -> ToolRegistry:
    """
    Build a snapshot-backed tool registry from the concrete VeraGrid app.

    :param app: VeraGrid main window.
    :returns: Tool registry.
    """
    approval_policy: ApprovalPolicy = ApprovalPolicy(
        require_mutating=False,
        require_destructive=False,
    )
    registry: ToolRegistry = ToolRegistry(approval_policy=approval_policy)
    selected_devices: list[Any] = app.get_selected_devices()
    selected_bus_tuples: list[tuple[int, Any, object | None]] = app.get_diagram_selected_buses()
    selected_device_records: list[dict[str, object]] = list()
    selected_bus_records: list[dict[str, object]] = list()
    selected_bus_idtags: set[str] = set()
    bus_records: list[dict[str, object]] = list()
    available_studies: list[str] = list()
    study_payload_by_name: dict[str, dict[str, object]] = dict()
    run_simulation_schema_json: str = build_run_simulation_schema_json()
    runtime_snapshot: RuntimeKnowledgeSnapshot = build_runtime_knowledge_snapshot(app)
    runtime_category_names: list[str] = runtime_snapshot.list_categories()
    runtime_record_titles: list[str] = runtime_snapshot.list_titles(32)
    index: int = 0

    while index < len(selected_devices):
        selected_device_records.append(build_object_save_record(selected_devices[index]))
        index += 1

    index = 0
    while index < len(selected_bus_tuples):
        _, bus, _ = selected_bus_tuples[index]
        selected_bus_records.append(build_object_save_record(bus))
        selected_bus_idtags.add(bus.idtag)
        index += 1

    index = 0
    while index < len(app.circuit.buses):
        bus: Any = app.circuit.buses[index]
        record: dict[str, object] = build_object_save_record(bus)
        record["nominal_voltage_kv"] = float(bus.Vnom)
        bus_records.append(record)
        index += 1

    model_summary_payload: dict[str, object] = {
        "project_name": get_current_project_name_from_app(app),
        "active_study": get_current_study_name_from_app(app),
        "solver_name": get_current_solver_name_from_app(app),
        "selected_diagram": None if app.get_selected_diagram_widget() is None else str(app.get_selected_diagram_widget().__class__.__name__),
        "bus_count": int(app.circuit.get_bus_number()),
        "branch_count": int(app.circuit.get_branch_number(add_hvdc=False, add_vsc=False, add_switch=True)),
        "load_count": int(app.circuit.get_loads_number()),
        "generator_count": int(app.circuit.get_generators_number()),
        "selected_device_count": len(selected_devices),
        "selected_bus_count": len(selected_bus_tuples),
    }

    index = 0
    while index < len(app.session.get_available_drivers()):
        driver: Any = app.session.get_available_drivers()[index]
        study_name: str = str(driver.tpe.value)
        available_studies.append(study_name)
        ok_summary: bool
        payload: dict[str, object]
        error_message: str
        ok_summary, payload, error_message = build_study_summary_payload_from_app(app, study_name)
        if ok_summary:
            study_payload_by_name[study_name] = payload
        else:
            study_payload_by_name[study_name] = {
                "study_name": study_name,
                "error": error_message,
            }
        index += 1

    model_summary_payload["available_studies"] = available_studies
    model_summary_payload["session_driver_count"] = len(app.session.get_available_drivers())
    model_summary_payload["runtime_category_names"] = runtime_category_names
    model_summary_payload["runtime_record_title_preview"] = runtime_record_titles

    registry.register(
        ToolSpec(
            name="run_simulation",
            description=build_run_simulation_tool_description(),
            input_schema_json=run_simulation_schema_json,
            risk=ToolRisk.COMPUTE,
            handler=LiveRunSimulationTool(app),
        )
    )
    registry.register(
        ToolSpec(
            name="get_model_summary",
            description="Get a summary of the loaded VeraGrid project, active study and selection.",
            input_schema_json=json.dumps({"type": "object", "properties": dict(), "additionalProperties": False}),
            risk=ToolRisk.READ_ONLY,
            handler=SnapshotPayloadTool(json.dumps(model_summary_payload, ensure_ascii=False)),
        )
    )
    registry.register(
        ToolSpec(
            name="get_selected_elements",
            description="Get the devices and buses selected in the current VeraGrid diagram.",
            input_schema_json=json.dumps({"type": "object", "properties": dict(), "additionalProperties": False}),
            risk=ToolRisk.READ_ONLY,
            handler=SnapshotPayloadTool(
                json.dumps(
                    {
                        "selected_devices": selected_device_records,
                        "selected_buses": selected_bus_records,
                    },
                    ensure_ascii=False,
                )
            ),
        )
    )
    registry.register(
        ToolSpec(
            name="list_buses",
            description="List buses from the loaded VeraGrid model with optional voltage and selection filters.",
            input_schema_json=json.dumps(
                {
                    "type": "object",
                    "properties": {
                        "kv_min": {"type": "number"},
                        "limit": {"type": "integer"},
                        "only_selected": {"type": "boolean"},
                    },
                    "additionalProperties": False,
                }
            ),
            risk=ToolRisk.READ_ONLY,
            handler=SnapshotBusListTool(bus_records=bus_records, selected_bus_idtags=selected_bus_idtags),
        )
    )
    registry.register(
        ToolSpec(
            name="list_available_studies",
            description="List the VeraGrid studies currently available in the session.",
            input_schema_json=json.dumps({"type": "object", "properties": dict(), "additionalProperties": False}),
            risk=ToolRisk.READ_ONLY,
            handler=SnapshotPayloadTool(
                json.dumps(
                    {
                        "active_study": get_current_study_name_from_app(app),
                        "items": [
                            {
                                "study_name": study_name,
                                "driver_type": study_name,
                                "is_running": bool(app.session.is_this_running(app.session.get_driver_by_name(study_name).tpe)),
                                "has_results": bool(
                                    app.session.get_driver_by_name(study_name) is not None
                                    and app.session.get_driver_by_name(study_name).results is not None
                                ),
                            }
                            for study_name in available_studies
                        ],
                    },
                    ensure_ascii=False,
                )
            ),
        )
    )
    registry.register(
        ToolSpec(
            name="get_study_summary",
            description="Summarize a VeraGrid study from the current session, defaulting to the active study.",
            input_schema_json=json.dumps(
                {
                    "type": "object",
                    "properties": {"study_name": {"type": "string"}},
                    "additionalProperties": False,
                }
            ),
            risk=ToolRisk.READ_ONLY,
            handler=SnapshotStudySummaryTool(
                active_study=get_current_study_name_from_app(app),
                payload_by_study=study_payload_by_name,
            ),
        )
    )
    registry.register(
        ToolSpec(
            name="search_runtime_records",
            description=(
                "Search live VeraGrid runtime records built from app.circuit, app.session, "
                "session drivers, and loaded results."
            ),
            input_schema_json=json.dumps(
                {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "category": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                }
            ),
            risk=ToolRisk.READ_ONLY,
            handler=RuntimeSnapshotSearchTool(runtime_snapshot=runtime_snapshot),
        )
    )
    registry.register(
        ToolSpec(
            name="get_runtime_record",
            description=(
                "Get one exact live VeraGrid runtime record by title. "
                "Use this after search_runtime_records when you need the full content."
            ),
            input_schema_json=json.dumps(
                {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                    },
                    "required": ["title"],
                    "additionalProperties": False,
                }
            ),
            risk=ToolRisk.READ_ONLY,
            handler=RuntimeSnapshotRecordTool(runtime_snapshot=runtime_snapshot),
        )
    )
    registry.register(
        ToolSpec(
            name="analyze_grid_issues",
            description=(
                "Run VeraGrid structural diagnostics over the current grid and report what is wrong, "
                "including imbalance, invalid ranges, connection issues, and numerical-stability warnings."
            ),
            input_schema_json=json.dumps(
                {
                    "type": "object",
                    "properties": {
                        "analyze_time_series": {"type": "boolean"},
                        "max_issue_count": {"type": "integer"},
                    },
                    "additionalProperties": False,
                }
            ),
            risk=ToolRisk.READ_ONLY,
            handler=LiveGridDiagnosticsTool(app),
        )
    )

    return registry


def build_live_context_from_app(app: "SimulationsMain") -> VeraGridContext:
    """
    Build a live VeraGrid context directly from the concrete app.

    :param app: VeraGrid main window.
    :returns: Current context.
    """
    notes: list[str] = list()
    selected_diagram_widget: object | None = app.get_selected_diagram_widget()
    available_studies: list[str] = list()
    driver_index: int = 0
    drivers: list[Any] = app.session.get_available_drivers()

    notes.append(f"Bus count: {app.circuit.get_bus_number()}")
    notes.append(
        "Branch count: "
        f"{app.circuit.get_branch_number(add_hvdc=False, add_vsc=False, add_switch=True)}"
    )
    notes.append(f"Load count: {app.circuit.get_loads_number()}")
    notes.append(f"Generator count: {app.circuit.get_generators_number()}")

    if selected_diagram_widget is None:
        pass
    else:
        notes.append(f"Selected diagram widget: {selected_diagram_widget.__class__.__name__}")

    while driver_index < len(drivers):
        available_studies.append(str(drivers[driver_index].tpe.value))
        driver_index += 1

    if len(available_studies) > 0:
        notes.append("Available studies: " + ", ".join(available_studies[:8]))
    else:
        notes.append("Available studies: none")

    return VeraGridContext(
        project_name=get_current_project_name_from_app(app),
        active_study=get_current_study_name_from_app(app),
        solver_name=get_current_solver_name_from_app(app),
        selected_elements=build_selected_element_labels_from_app(app),
        notes=notes,
    )


def convert_markdown_to_html(text: str) -> str:
    """
    Convert markdown text into HTML using Qt's document engine.

    :param text: Markdown text.
    :returns: HTML fragment.
    """
    document: QtGui.QTextDocument = QtGui.QTextDocument()
    html_text: str
    body_start: int
    body_end: int
    body_content_start: int

    document.setMarkdown(text)
    html_text = document.toHtml()
    body_start = html_text.find("<body")
    body_end = html_text.rfind("</body>")

    if (body_start > -1) and (body_end > body_start):
        body_content_start = html_text.find(">", body_start)
        if body_content_start > -1:
            return html_text[(body_content_start + 1):body_end]
        else:
            return html.escape(text).replace("\n", "<br/>")
    else:
        return html.escape(text).replace("\n", "<br/>")


class AiChatDialogue(QtWidgets.QDialog):
    """
    VeraGrid AI dialogue window.

    :param parent: Optional Qt parent widget.
    """

    turn_execution_requested = QtCore.Signal(object)
    dialogue_visibility_changed = QtCore.Signal(bool)

    __slots__ = (
        "ui",
        "_provider_presets",
        "_backend_mode_button_group",
        "_program_knowledge_index",
        "_history",
        "_prompt_factory",
        "_tool_registry",
        "_pending_state",
        "_app",
        "_embedded_mode",
        "_turn_thread",
        "_turn_worker",
        "_turn_running",
        "_path_scan_timer",
        "_waiting_animation_timer",
        "_waiting_animation_index",
        "_waiting_status_base_text",
        "_allow_window_close",
    )

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        app: Optional["SimulationsMain"] = None,
    ) -> None:
        """
        Build the dialogue and connect the explicit UI workflow.

        :param parent: Optional Qt parent widget.
        :param app: Optional concrete VeraGrid main window.
        """
        QtWidgets.QDialog.__init__(self, parent)

        # Build the static designer-driven widget tree first.
        self.ui: Ui_AiChatDialog = Ui_AiChatDialog()
        self.ui.setupUi(self)
        self.setWindowTitle("VeraGrid AI dialogue")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, False)
        if self.ui.local_model_combo_box.lineEdit() is not None:
            self.ui.local_model_combo_box.lineEdit().setPlaceholderText("Pick or type a GGUF file name")
        else:
            pass
        if self.ui.api_model_combo_box.lineEdit() is not None:
            self.ui.api_model_combo_box.lineEdit().setPlaceholderText("Provider model name")
        else:
            pass
        self._configure_transcript_browser()

        # Create explicit controller state used by future user turns.
        self._provider_presets: list[ProviderPreset] = build_provider_presets()
        self._backend_mode_button_group: QtWidgets.QButtonGroup = QtWidgets.QButtonGroup(self)
        self._backend_mode_button_group.addButton(self.ui.local_ai_radioButton)
        self._backend_mode_button_group.addButton(self.ui.api_ai_radioButton)
        self._backend_mode_button_group.setExclusive(True)
        self.ui.local_ai_radioButton.setChecked(True)
        self._program_knowledge_index: ProgramKnowledgeIndex = ProgramKnowledgeIndex(
            build_default_knowledge_package_name()
        )
        self._history: list[ChatMessage] = list()
        self._prompt_factory: PromptFactory = PromptFactory()
        self._app: Optional[SimulationsMain] = app
        if self._app is None:
            self._tool_registry = build_default_tool_registry()
        else:
            self._tool_registry = build_live_tool_registry_from_app(self._app)
        self._pending_state: Optional[PendingConversationState] = None
        self._embedded_mode: bool = False
        self._turn_thread: QtCore.QThread = QtCore.QThread(self)
        self._turn_worker: AiTurnWorker = AiTurnWorker()
        self._turn_running: bool = False
        self._turn_worker.moveToThread(self._turn_thread)
        self.turn_execution_requested.connect(self._turn_worker.run_request)
        self._turn_worker.completed.connect(self._handle_turn_execution_response)
        self._turn_thread.start()
        self._path_scan_timer: QtCore.QTimer = QtCore.QTimer(self)
        self._path_scan_timer.setSingleShot(True)
        self._waiting_animation_timer: QtCore.QTimer = QtCore.QTimer(self)
        self._waiting_animation_index: int = 0
        self._waiting_status_base_text: str = ""
        self._allow_window_close: bool = False
        self._waiting_animation_timer.setInterval(140)
        self._waiting_animation_timer.timeout.connect(self._advance_waiting_animation)
        self._path_scan_timer.timeout.connect(self._scan_local_model_path_if_directory)
        qt_application: Optional[QtWidgets.QApplication] = QtWidgets.QApplication.instance()
        if qt_application is None:
            pass
        else:
            qt_application.aboutToQuit.connect(self.shutdown_turn_thread)

        # Initialize the controls before any signal starts reacting to changes.
        self._populate_provider_combo_box()
        self._connect_signals()
        self._apply_provider_preset(self.ui.api_provider_combo_box.currentIndex())
        self._hide_context_controls()
        self._hide_approval_controls()
        self.refresh_context_from_app()
        self._refresh_pending_approval_widgets()
        self._render_transcript()

    def _configure_transcript_browser(self) -> None:
        """
        Configure the transcript browser colors for readable selection and contrast.

        :returns: Nothing.
        """
        self.ui.conversation_text_browser.setStyleSheet(
            """
            QTextBrowser {
                background-color: #f7f7f8;
                color: #1f2937;
                selection-background-color: #c9defe;
                selection-color: #111827;
                border: none;
                padding: 0px;
            }
            QTextBrowser a {
                color: #2563eb;
            }
            """
        )

    def _hide_approval_controls(self) -> None:
        """
        Keep compatibility with the previous UI, which no longer exposes approval widgets.

        :returns: Nothing.
        """
        pass

    def _is_api_mode_selected(self) -> bool:
        """
        Check whether the API mode is currently selected.

        :returns: True when API mode is selected.
        """
        return self.ui.api_ai_radioButton.isChecked()

    def _get_local_provider_preset(self) -> ProviderPreset:
        """
        Return the fixed local provider preset.

        :returns: Local llama.cpp preset.
        """
        index: int = 0

        while index < len(self._provider_presets):
            if self._provider_presets[index].provider_tpe == ProviderType.LOCAL_LLAMA_CPP:
                return self._provider_presets[index]
            else:
                pass
            index += 1

        return self._provider_presets[0]

    def _get_api_provider_presets(self) -> list[ProviderPreset]:
        """
        Return the API-facing provider presets.

        :returns: API preset list.
        """
        visible_presets: list[ProviderPreset] = list()
        index: int = 0

        while index < len(self._provider_presets):
            preset: ProviderPreset = self._provider_presets[index]
            if preset.provider_tpe == ProviderType.LOCAL_LLAMA_CPP:
                pass
            else:
                visible_presets.append(preset)
            index += 1

        return visible_presets

    def _get_visible_provider_presets(self) -> list[ProviderPreset]:
        """
        Return the provider presets visible for the selected backend mode.

        :returns: Visible provider presets.
        """
        if self._is_api_mode_selected():
            return self._get_api_provider_presets()
        else:
            return [self._get_local_provider_preset()]

    def set_embedded_mode(self, enabled: bool) -> None:
        """
        Configure whether the dialogue is embedded inside the main VeraGrid window.

        :param enabled: Embedded-mode flag.
        :returns: Nothing.
        """
        self._embedded_mode = enabled

        if enabled:
            self.setWindowTitle("VeraGrid AI")
        else:
            self.setWindowTitle("VeraGrid AI dialogue")

    def _hide_context_controls(self) -> None:
        """
        Keep compatibility with the previous UI, which no longer exposes manual context widgets.

        :returns: Nothing.
        """
        pass

    def refresh_context_from_app(self) -> None:
        """
        Refresh any cached app-derived context.

        :returns: Nothing.
        """
        pass

    def _build_retrieved_context_text(self, user_query: str) -> str:
        """
        Build the deterministic retrieval block for the current question.

        :param user_query: User query text.
        :returns: Retrieved-context block.
        """
        runtime_snapshot = None

        if self._app is None:
            runtime_snapshot = None
        else:
            # The runtime snapshot is built in the GUI thread because it touches live app state.
            runtime_snapshot = build_runtime_knowledge_snapshot(self._app)

        return build_retrieved_context_text(
            query=user_query,
            program_index=self._program_knowledge_index,
            runtime_snapshot=runtime_snapshot,
        )

    def _populate_provider_combo_box(self) -> None:
        """
        Fill the provider combo box from the explicit preset list.

        :returns: Nothing.
        """
        visible_presets: list[ProviderPreset] = self._get_api_provider_presets()
        index: int = 0

        self.ui.api_provider_combo_box.clear()

        # The combo box order must match the filtered preset array order for lookup.
        while index < len(visible_presets):
            preset = visible_presets[index]
            self.ui.api_provider_combo_box.addItem(preset.display_name)
            index += 1

    def _connect_signals(self) -> None:
        """
        Connect the dialogue widgets to their controller methods.

        :returns: Nothing.
        """
        self.ui.local_ai_radioButton.toggled.connect(self._handle_backend_mode_changed)
        self.ui.api_ai_radioButton.toggled.connect(self._handle_backend_mode_changed)

        # Provider selection loads the matching endpoint defaults.
        self.ui.api_provider_combo_box.currentIndexChanged.connect(self._apply_provider_preset)
        self.ui.local_model_path_line_edit.textChanged.connect(self._handle_model_path_text_changed)

        # Utility actions are limited to model discovery and transcript control.
        self.ui.local_refresh_models_button.clicked.connect(self.refresh_available_models)
        self.ui.api_refresh_models_button.clicked.connect(self.refresh_available_models)
        self.ui.clear_chat_button.clicked.connect(self.clear_chat)

        # The main action path is explicit: send a turn.
        self.ui.send_button.clicked.connect(self.send_message)

    def _handle_backend_mode_changed(self, checked: bool) -> None:
        """
        Reconfigure the active backend when the radio-button selection changes.

        :param checked: Radio-button checked state.
        :returns: Nothing.
        """
        if checked:
            self._apply_provider_preset(self.ui.api_provider_combo_box.currentIndex())
        else:
            pass

    def _handle_model_path_text_changed(self, text: str) -> None:
        """
        Debounce a local model scan when the model-path text becomes a folder.

        :param text: Current model-path text.
        :returns: Nothing.
        """
        expanded_text: str = os.path.expanduser(text.strip())

        if os.path.isdir(expanded_text):
            self._path_scan_timer.start(350)
        else:
            self._path_scan_timer.stop()

    def _scan_local_model_path_if_directory(self) -> None:
        """
        Trigger a local model scan when the current model-path text is a folder.

        :returns: Nothing.
        """
        current_text: str = os.path.expanduser(self.ui.local_model_path_line_edit.text().strip())

        if self._is_local_provider_selected() and os.path.isdir(current_text):
            self.refresh_available_models()
        else:
            pass

    def _get_provider_preset_at(self, index: int) -> ProviderPreset:
        """
        Return the preset at a combo-box index.

        :param index: Combo-box index.
        :returns: Matching provider preset.
        """
        preset: ProviderPreset

        if self._is_api_mode_selected():
            visible_presets: list[ProviderPreset] = self._get_api_provider_presets()
            if (index >= 0) and (index < len(visible_presets)):
                preset = visible_presets[index]
            else:
                preset = visible_presets[0]
        else:
            preset = self._get_local_provider_preset()

        return preset

    def _find_provider_index(self, provider_tpe: ProviderType) -> int:
        """
        Find the combo-box index for a provider type.

        :param provider_tpe: Provider type to look up.
        :returns: Matching combo-box index or zero.
        """
        index: int = 0
        visible_presets: list[ProviderPreset] = self._get_api_provider_presets()

        while index < len(visible_presets):
            if visible_presets[index].provider_tpe == provider_tpe:
                return index
            else:
                pass
            index += 1

        return 0

    def _configure_provider_inputs(self, preset: ProviderPreset) -> None:
        """
        Adjust the backend form for the selected provider kind.

        :param preset: Active provider preset.
        :returns: Nothing.
        """
        if preset.provider_tpe == ProviderType.LOCAL_LLAMA_CPP:
            self.ui.groupBox.setEnabled(True)
            self.ui.groupBox_2.setEnabled(True)
            self.ui.local_model_label.setEnabled(True)
            self.ui.local_model_combo_box.setEnabled(True)
            self.ui.local_model_path_label.setEnabled(True)
            self.ui.local_model_path_line_edit.setEnabled(True)
            self.ui.local_refresh_models_button.setEnabled(True)
            self.ui.local_timeout_label.setEnabled(True)
            self.ui.local_timeout_double_spin_box.setEnabled(True)
            self.ui.api_provider_label.setEnabled(False)
            self.ui.api_provider_combo_box.setEnabled(False)
            self.ui.api_base_url_label.setEnabled(False)
            self.ui.api_base_url_line_edit.setEnabled(False)
            self.ui.api_api_key_label.setEnabled(False)
            self.ui.api_api_key_line_edit.setEnabled(False)
            self.ui.api_model_label.setEnabled(False)
            self.ui.api_model_combo_box.setEnabled(False)
            self.ui.api_refresh_models_button.setEnabled(False)
            self.ui.api_timeout_label.setEnabled(False)
            self.ui.api_timeout_double_spin_box.setEnabled(False)
            self.ui.local_refresh_models_button.setToolTip("Scan the configured path for GGUF files.")
            if self.ui.local_model_combo_box.lineEdit() is None:
                pass
            else:
                self.ui.local_model_combo_box.lineEdit().setPlaceholderText("Pick or type a GGUF file name")
        else:
            self.ui.groupBox.setEnabled(True)
            self.ui.groupBox_2.setEnabled(True)
            self.ui.local_model_label.setEnabled(False)
            self.ui.local_model_combo_box.setEnabled(False)
            self.ui.local_model_path_label.setEnabled(False)
            self.ui.local_model_path_line_edit.setEnabled(False)
            self.ui.local_refresh_models_button.setEnabled(False)
            self.ui.local_timeout_label.setEnabled(False)
            self.ui.local_timeout_double_spin_box.setEnabled(False)
            self.ui.api_provider_label.setEnabled(True)
            self.ui.api_provider_combo_box.setEnabled(True)
            self.ui.api_base_url_label.setEnabled(True)
            self.ui.api_base_url_line_edit.setEnabled(True)
            self.ui.api_api_key_label.setEnabled(True)
            self.ui.api_api_key_line_edit.setEnabled(True)
            self.ui.api_model_label.setEnabled(True)
            self.ui.api_model_combo_box.setEnabled(True)
            self.ui.api_refresh_models_button.setEnabled(True)
            self.ui.api_timeout_label.setEnabled(True)
            self.ui.api_timeout_double_spin_box.setEnabled(True)
            self.ui.api_api_key_line_edit.setPlaceholderText(
                "Leave empty for unauthenticated endpoints"
            )
            self.ui.api_refresh_models_button.setToolTip("Query the configured backend for models.")
            if self.ui.api_model_combo_box.lineEdit() is None:
                pass
            else:
                self.ui.api_model_combo_box.lineEdit().setPlaceholderText("Provider model name")

    def _is_local_provider_selected(self) -> bool:
        """
        Check whether the local llama.cpp mode is currently selected.

        :returns: True when the current preset is the local provider.
        """
        return not self._is_api_mode_selected()

    def _apply_provider_preset(self, index: int) -> None:
        """
        Apply the preset values for the selected provider.

        :param index: Combo-box index.
        :returns: Nothing.
        """
        preset: ProviderPreset = self._get_provider_preset_at(index)

        # Provider selection should make the required fields immediately usable.
        self._configure_provider_inputs(preset)
        self._set_model_choices(preset.typical_model_names)

        if preset.provider_tpe == ProviderType.LOCAL_LLAMA_CPP:
            pass
        else:
            self.ui.api_base_url_line_edit.setText(preset.default_base_url)

        # Keep the status area informative so the user sees what changed.
        if preset.provider_tpe == ProviderType.LOCAL_LLAMA_CPP:
            self._set_status_message(
                "Choose a GGUF file or directory, click Scan, then start chatting."
            )
        else:
            self._set_status_message(f"Loaded defaults for {preset.display_name}.")

        if len(self._history) == 0:
            self._render_transcript()
        else:
            pass

    def _set_model_choices(self, model_names: list[str]) -> None:
        """
        Replace the editable model combo-box choices.

        :param model_names: Ordered model identifiers to display.
        :returns: Nothing.
        """
        combo_box: QtWidgets.QComboBox
        index: int = 0

        if self._is_local_provider_selected():
            combo_box = self.ui.local_model_combo_box
        else:
            combo_box = self.ui.api_model_combo_box

        current_text: str = combo_box.currentText().strip()

        # Reset the combo box so provider changes do not leave stale models behind.
        combo_box.clear()

        while index < len(model_names):
            combo_box.addItem(model_names[index])
            index += 1

        if len(model_names) > 0:
            combo_box.setCurrentText(model_names[0])
        else:
            combo_box.setCurrentText("")

        if len(current_text) > 0:
            if combo_box.findText(current_text) > -1:
                combo_box.setCurrentText(current_text)
            else:
                pass
        else:
            pass

    def _get_selected_model_name(self) -> str:
        """
        Read the current model identifier from the editable combo box.

        :returns: Selected model name.
        """
        model_name: str

        if self._is_local_provider_selected():
            model_name = self.ui.local_model_combo_box.currentText().strip()
        else:
            model_name = self.ui.api_model_combo_box.currentText().strip()
        return model_name

    def get_backend_state(self) -> AiBackendState:
        """
        Read the current backend form into a persistable state object.

        :returns: Backend-state snapshot.
        """
        provider_tpe: ProviderType = self._get_provider_preset_at(
            self.ui.api_provider_combo_box.currentIndex()
        ).provider_tpe
        model_name: str = self._get_selected_model_name()
        base_url: str
        api_key_text: str
        api_key: Optional[str]

        if provider_tpe == ProviderType.LOCAL_LLAMA_CPP:
            base_url = self.ui.local_model_path_line_edit.text().strip()
            api_key_text = ""
        else:
            base_url = self.ui.api_base_url_line_edit.text().strip()
            api_key_text = self.ui.api_api_key_line_edit.text().strip()

        if len(api_key_text) > 0:
            api_key = api_key_text
        else:
            api_key = None

        return AiBackendState(
            provider_tpe=provider_tpe,
            model_name=model_name,
            base_url=base_url,
            api_key=api_key,
            timeout_s=(
                float(self.ui.local_timeout_double_spin_box.value())
                if provider_tpe == ProviderType.LOCAL_LLAMA_CPP
                else float(self.ui.api_timeout_double_spin_box.value())
            ),
        )

    def apply_backend_state(self, state: AiBackendState) -> None:
        """
        Apply a backend-state snapshot to the visible form.

        :param state: Backend-state snapshot.
        :returns: Nothing.
        """
        provider_index: int = self._find_provider_index(state.provider_tpe)
        current_index: int = self.ui.api_provider_combo_box.currentIndex()

        if state.provider_tpe == ProviderType.LOCAL_LLAMA_CPP:
            if not self.ui.local_ai_radioButton.isChecked():
                self.ui.local_ai_radioButton.setChecked(True)
            else:
                self._apply_provider_preset(0)

            self.ui.local_model_path_line_edit.setText(state.base_url)
            self.ui.local_model_combo_box.setCurrentText(state.model_name)
            self.ui.local_timeout_double_spin_box.setValue(state.timeout_s)
        else:
            if not self.ui.api_ai_radioButton.isChecked():
                self.ui.api_ai_radioButton.setChecked(True)
            else:
                pass

            if current_index != provider_index:
                self.ui.api_provider_combo_box.setCurrentIndex(provider_index)
            else:
                self._apply_provider_preset(provider_index)

            self.ui.api_base_url_line_edit.setText(state.base_url)
            self.ui.api_model_combo_box.setCurrentText(state.model_name)

            if state.api_key is None:
                self.ui.api_api_key_line_edit.clear()
            else:
                self.ui.api_api_key_line_edit.setText(state.api_key)

            self.ui.api_timeout_double_spin_box.setValue(state.timeout_s)

    def apply_local_model_defaults(
        self,
        model_path: str,
        model_name: str,
        timeout_s: float,
    ) -> None:
        """
        Apply local-model defaults from the host main window.

        :param model_path: GGUF file path or model directory.
        :param model_name: Selected GGUF file name.
        :param timeout_s: Request timeout in seconds.
        :returns: Nothing.
        """
        self.apply_backend_state(
            AiBackendState(
                provider_tpe=ProviderType.LOCAL_LLAMA_CPP,
                model_name=model_name,
                base_url=model_path,
                api_key=None,
                timeout_s=timeout_s,
            )
        )

    def _build_provider_config(self, require_model_name: bool = True) -> Optional[ProviderConfig]:
        """
        Build a backend provider configuration from the form.

        :param require_model_name: Whether an explicit model is required.
        :returns: Provider configuration or None if the form is incomplete.
        """
        model_name: str = self._get_selected_model_name()
        base_url_text: str
        api_key_text: str
        timeout_s: float
        provider_tpe: ProviderType = self._get_provider_preset_at(
            self.ui.api_provider_combo_box.currentIndex()
        ).provider_tpe
        config: Optional[ProviderConfig]
        requires_model_name: bool = require_model_name

        if provider_tpe == ProviderType.LOCAL_LLAMA_CPP:
            base_url_text = self.ui.local_model_path_line_edit.text().strip()
            api_key_text = ""
            timeout_s = float(self.ui.local_timeout_double_spin_box.value())
        else:
            base_url_text = self.ui.api_base_url_line_edit.text().strip()
            api_key_text = self.ui.api_api_key_line_edit.text().strip()
            timeout_s = float(self.ui.api_timeout_double_spin_box.value())

        # Local single-file configurations can derive the model from a manual scan later.
        if provider_tpe == ProviderType.LOCAL_LLAMA_CPP:
            requires_model_name = require_model_name
        else:
            pass

        # Chat completions require an explicit model, while model discovery does not.
        if requires_model_name and (len(model_name) == 0):
            self._set_status_message("The model field is empty.")
            config = None
        else:
            # The backend also requires a base URL because it does not infer endpoints.
            if len(base_url_text) == 0:
                if provider_tpe == ProviderType.LOCAL_LLAMA_CPP:
                    self._set_status_message("The model path field is empty.")
                else:
                    self._set_status_message("The base URL field is empty.")
                config = None
            else:
                api_key: Optional[str]
                if provider_tpe == ProviderType.LOCAL_LLAMA_CPP:
                    api_key = None
                else:
                    if len(api_key_text) > 0:
                        api_key = api_key_text
                    else:
                        api_key = None

                config = ProviderConfig(
                    provider_tpe=provider_tpe,
                    model_name=model_name,
                    api_key=api_key,
                    base_url=base_url_text,
                    timeout_s=timeout_s,
                )

        return config

    def refresh_available_models(self) -> None:
        """
        Query the configured backend for the available models and update the combo box.

        :returns: Nothing.
        """
        config: Optional[ProviderConfig] = self._build_provider_config(require_model_name=False)

        # The query can only run when the current backend form is already valid.
        if config is None:
            pass
        else:
            if config.provider_tpe == ProviderType.LOCAL_LLAMA_CPP:
                self._set_status_message("Scanning the configured model path...")
            else:
                self._set_status_message("Refreshing models from the configured backend...")
            result: ModelListResult = list_provider_models(config)

            if result.success:
                self._set_model_choices(result.model_names)
                if config.provider_tpe == ProviderType.LOCAL_LLAMA_CPP:
                    self._set_status_message(
                        f"Found {len(result.model_names)} local GGUF models in the configured path."
                    )
                else:
                    self._set_status_message(
                        f"Loaded {len(result.model_names)} models from the backend."
                    )
            else:
                if config.provider_tpe == ProviderType.LOCAL_LLAMA_CPP:
                    self._set_status_message(f"Could not scan local models: {result.error_message}")
                else:
                    self._set_status_message(f"Could not refresh models: {result.error_message}")

    def build_context_from_ui(self) -> VeraGridContext:
        """
        Build a VeraGrid context object from the live app state.

        :returns: Current dialogue context.
        """
        if self._app is None:
            return VeraGridContext(
                project_name=None,
                active_study=None,
                solver_name=None,
                selected_elements=list(),
                notes=list(),
            )
        else:
            return build_live_context_from_app(self._app)

    def set_context(self, context: VeraGridContext, include_notes: bool = True) -> None:
        """
        Retained for compatibility after removing the visible context controls.

        :param context: Context to display in the dialogue.
        :param include_notes: Whether to replace the manual notes field.
        :returns: Nothing.
        """
        pass

    def send_message(self) -> None:
        """
        Send the current user message through the configured backend.

        :returns: Nothing.
        """
        message_text: str = self.ui.message_plain_text_edit.toPlainText().strip()

        # Always refresh the runtime context right before preparing a new user turn.
        self.refresh_context_from_app()

        # Do not mix a new turn into a transcript that is awaiting approval.
        if self._pending_state is None:
            if len(message_text) > 0:
                if self._try_handle_direct_app_command(message_text):
                    self.ui.message_plain_text_edit.clear()
                else:
                    base_history: list[ChatMessage] = copy_chat_history(self._history)
                    self._run_turn(
                        base_history=base_history,
                        user_message=message_text,
                        approved_tool_name=None,
                        approved_arguments_json=None,
                    )
            else:
                self._set_status_message("Type a message before sending.")
        else:
            self._set_status_message("Resolve the pending tool approval or clear the chat first.")

    def _try_handle_direct_app_command(self, message_text: str) -> bool:
        """
        Execute explicit simulation commands without relying on LLM tool-calling.

        :param message_text: User message text.
        :returns: True when the command was handled directly.
        """
        command: Optional[AiSimulationCommand]
        result: ToolExecutionResult
        assistant_text: str

        if self._app is None:
            return False
        else:
            pass

        if is_direct_grid_diagnostics_request(message_text):
            result = LiveGridDiagnosticsTool(self._app).execute(
                {
                    "analyze_time_series": True,
                    "max_issue_count": 20,
                }
            )

            self._history.append(ChatMessage(role="user", content=message_text, name=None))

            if result.success:
                payload_obj: object

                try:
                    payload_obj = json.loads(result.payload_json)
                except json.JSONDecodeError:
                    payload_obj = dict()

                if isinstance(payload_obj, dict):
                    assistant_text = build_grid_diagnostic_summary_text(payload_obj)
                else:
                    assistant_text = "Finished the grid diagnostics."

                self._set_status_message("Finished the grid diagnostics.")
            else:
                assistant_text = result.error_message
                self._set_status_message(result.error_message)

            self._history.append(ChatMessage(role="assistant", content=assistant_text, name=None))
            self._render_transcript()
            return True
        else:
            pass

        command = detect_direct_simulation_command(message_text)

        if command is None:
            return False
        else:
            result = execute_live_simulation_from_app(self._app, command)
            self._history.append(ChatMessage(role="user", content=message_text, name=None))

            if result.success:
                assistant_text = extract_assistant_message_from_tool_result(result)
                self._set_status_message(assistant_text)
            else:
                assistant_text = result.error_message
                self._set_status_message(result.error_message)

            self._history.append(ChatMessage(role="assistant", content=assistant_text, name=None))
            self._render_transcript()
            return True

    def approve_pending_tool_call(self) -> None:
        """
        Re-run the pending user turn with an approved tool call.

        :returns: Nothing.
        """
        pending_state: Optional[PendingConversationState] = self._pending_state

        # Refresh the runtime fields before replaying the approved tool call.
        self.refresh_context_from_app()

        # Approval is only valid when there is a stored snapshot to replay.
        if pending_state is None:
            self._set_status_message("There is no pending tool call to approve.")
        else:
            approval: PendingApproval = pending_state.approval
            self._run_turn(
                base_history=copy_chat_history(pending_state.base_history),
                user_message=pending_state.user_message,
                approved_tool_name=approval.tool_name,
                approved_arguments_json=approval.arguments_json,
            )

    def _run_turn(
        self,
        base_history: list[ChatMessage],
        user_message: str,
        approved_tool_name: Optional[str],
        approved_arguments_json: Optional[str],
    ) -> None:
        """
        Execute one user turn with optional tool approval.

        :param base_history: Transcript before the current user turn.
        :param user_message: User message to process.
        :param approved_tool_name: Approved tool name if any.
        :param approved_arguments_json: Approved tool arguments if any.
        :returns: Nothing.
        """
        config: Optional[ProviderConfig] = self._build_provider_config()

        if self._turn_running:
            self._set_status_message("Wait for the current AI turn to finish.")
        else:
            pass

        # Abort early when the backend form is incomplete.
        if self._turn_running:
            pass
        else:
            if config is None:
                pass
            else:
                if approved_tool_name is None:
                    self.ui.message_plain_text_edit.clear()
                else:
                    pass

                context: VeraGridContext = self.build_context_from_ui()
                retrieved_context_text: str = self._build_retrieved_context_text(user_message)
                system_prompt: str = self._prompt_factory.build_system_prompt(
                    context,
                    retrieved_context_text=retrieved_context_text,
                )
                tool_registry: ToolRegistry

                if self._app is None:
                    tool_registry = self._tool_registry
                else:
                    tool_registry = build_live_tool_registry_from_app(self._app)
                    self._tool_registry = tool_registry

                request: AiTurnExecutionRequest = AiTurnExecutionRequest(
                    provider_config=config,
                    system_prompt=system_prompt,
                    grounding_context_text=retrieved_context_text,
                    tool_registry=tool_registry,
                    base_history=copy_chat_history(base_history),
                    user_message=user_message,
                    approved_tool_name=approved_tool_name,
                    approved_arguments_json=approved_arguments_json,
                )
                self._set_turn_running(True)
                self._set_status_message("Running AI turn...")
                self.turn_execution_requested.emit(request)

    def _set_turn_running(self, running: bool) -> None:
        """
        Update the dialogue widgets according to the background-turn state.

        :param running: Running flag.
        :returns: Nothing.
        """
        self._turn_running = running
        self.ui.send_button.setEnabled(not running)
        self.ui.clear_chat_button.setEnabled(not running)

        if running:
            self._waiting_status_base_text = "Running AI turn"
            self._waiting_animation_index = 0
            self._waiting_animation_timer.start()
        else:
            self._waiting_animation_timer.stop()
            self.ui.send_button.setText("Send")
            self._refresh_pending_approval_widgets()

    def _advance_waiting_animation(self) -> None:
        """
        Advance the waiting animation while the AI worker is running.

        :returns: Nothing.
        """
        frames: list[str] = ["|", "/", "-", "\\"]
        frame_text: str = frames[self._waiting_animation_index % len(frames)]

        self.ui.status_label.setText(f"{self._waiting_status_base_text} {frame_text}")
        self.ui.send_button.setText(f"Wait {frame_text}")
        self._waiting_animation_index += 1

    @QtCore.Slot(object)
    def _handle_turn_execution_response(self, response: AiTurnExecutionResponse) -> None:
        """
        Collect the background-turn callback and update the GUI state.

        :param response: Worker response.
        :returns: Nothing.
        """
        result: ConversationRunResult = response.result

        self._set_turn_running(False)
        self._history = result.transcript

        if result.pending_approval is None:
            self._pending_state = None
            if response.success:
                self._set_status_message("Turn completed.")
            else:
                self._set_status_message(f"AI turn failed: {response.error_message}")
        else:
            self._pending_state = PendingConversationState(
                base_history=copy_chat_history(response.request.base_history),
                user_message=response.request.user_message,
                approval=result.pending_approval,
            )
            self._set_status_message("The backend requested tool approval, but approval UI is disabled.")

        self._refresh_pending_approval_widgets()
        self._render_transcript()

    def shutdown_turn_thread(self) -> None:
        """
        Stop the background AI worker thread.

        :returns: Nothing.
        """
        if self._turn_thread.isRunning():
            self._turn_thread.quit()
            self._turn_thread.wait(2000)
        else:
            pass

    def prepare_for_shutdown(self) -> None:
        """
        Allow the dialogue window to close permanently during application shutdown.

        :returns: Nothing.
        """
        self._allow_window_close = True

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        """
        Refresh the live context when the dialogue becomes visible.

        :param event: Qt show event.
        :returns: Nothing.
        """
        # Re-synchronize the visible context every time the user reopens the dialogue.
        self.refresh_context_from_app()
        QtWidgets.QDialog.showEvent(self, event)
        self.dialogue_visibility_changed.emit(True)

    def hideEvent(self, event: QtGui.QHideEvent) -> None:
        """
        Synchronize external UI state whenever the dialogue becomes hidden.

        :param event: Qt hide event.
        :returns: Nothing.
        """
        QtWidgets.QDialog.hideEvent(self, event)
        self.dialogue_visibility_changed.emit(False)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """
        Keep the dialogue instance alive when the user closes the floating window.

        :param event: Qt close event.
        :returns: Nothing.
        """
        if self._allow_window_close:
            QtWidgets.QDialog.closeEvent(self, event)
        else:
            event.ignore()
            self.hide()

    def reject(self) -> None:
        """
        Hide the dialogue for escape-key closure instead of destroying the instance.

        :returns: Nothing.
        """
        if self._allow_window_close:
            QtWidgets.QDialog.reject(self)
        else:
            self.hide()

    def clear_chat(self) -> None:
        """
        Clear the transcript and reset pending approval state.

        :returns: Nothing.
        """
        # Reset both visible transcript data and hidden approval replay state.
        self._history = list()
        self._pending_state = None
        self.ui.message_plain_text_edit.clear()
        self._render_transcript()
        self._set_status_message("Chat cleared.")

    def _refresh_pending_approval_widgets(self) -> None:
        """
        Synchronize the approval widgets with the pending state.

        :returns: Nothing.
        """
        pending_state: Optional[PendingConversationState] = self._pending_state

        # The current UI does not expose approval widgets, so only internal state is kept.
        if pending_state is None:
            pass
        else:
            pass

    def _set_status_message(self, text: str) -> None:
        """
        Update the status label.

        :param text: Status message text.
        :returns: Nothing.
        """
        self.ui.status_label.setText(text)

    def _render_transcript(self) -> None:
        """
        Render the current transcript into the chat browser.

        :returns: Nothing.
        """
        html_parts: list[str] = list()
        index: int = 0
        wrapper_html: str

        # Render an initial help state when there is still no conversation content.
        if len(self._history) == 0:
            html_parts.append(self._build_empty_state_html())
        else:
            while index < len(self._history):
                html_parts.append(self._format_message_html(self._history[index]))
                index += 1

        wrapper_html = (
            "<html><body style='margin:0;background-color:#f7f7f8;'>"
            "<div style='max-width:880px;margin:0 auto;padding:24px 20px 40px 20px;"
            "font-family:\"Segoe UI\", \"Noto Sans\", sans-serif;font-size:11pt;"
            "line-height:1.6;color:#1f2937;'>"
            + "".join(html_parts)
            + "</div></body></html>"
        )

        self.ui.conversation_text_browser.setHtml(wrapper_html)
        self.ui.conversation_text_browser.moveCursor(QtGui.QTextCursor.MoveOperation.End)

    def _build_empty_state_html(self) -> str:
        """
        Build the transcript HTML for the empty state.

        :returns: Empty-state HTML.
        """
        if self._is_local_provider_selected():
            return (
                "<div style='padding:32px 12px 12px 12px;'>"
                "<div style='max-width:700px;margin:0 auto;text-align:left;'>"
                "<div style='font-size:20pt;font-weight:600;color:#111827;margin-bottom:10px;'>"
                "How can VeraGrid help?"
                "</div>"
                "<div style='font-size:10pt;color:#6b7280;margin-bottom:18px;'>"
                "Select a GGUF file or model directory in Settings, scan it, choose a local model, "
                "then start a conversation with the current VeraGrid session."
                "</div>"
                "<div style='background-color:#ffffff;border:1px solid #e5e7eb;border-radius:16px;"
                "padding:16px 18px;'>"
                "<div style='font-size:9pt;font-weight:600;letter-spacing:0.04em;"
                "text-transform:uppercase;color:#9ca3af;margin-bottom:10px;'>"
                "Try asking"
                "</div>"
                "<ul>"
                "<li>List the high-voltage buses in the current project.</li>"
                "<li>Summarize the active study context before I run a solver.</li>"
                "<li>Explain which VeraGrid tool you would use next and why.</li>"
                "</ul>"
                "</div>"
                "</div>"
                "</div>"
            )
        else:
            return (
                "<div style='padding:32px 12px 12px 12px;'>"
                "<div style='max-width:700px;margin:0 auto;text-align:left;'>"
                "<div style='font-size:20pt;font-weight:600;color:#111827;margin-bottom:10px;'>"
                "How can VeraGrid help?"
                "</div>"
                "<div style='font-size:10pt;color:#6b7280;margin-bottom:18px;'>"
                "Choose an API backend in Settings. The VeraGrid context is taken directly from the main app."
                "</div>"
                "<div style='background-color:#ffffff;border:1px solid #e5e7eb;border-radius:16px;"
                "padding:16px 18px;'>"
                "<div style='font-size:9pt;font-weight:600;letter-spacing:0.04em;"
                "text-transform:uppercase;color:#9ca3af;margin-bottom:10px;'>"
                "Try asking"
                "</div>"
                "<ul>"
                "<li>List the high-voltage buses in the current project.</li>"
                "<li>Summarize the active study context before I run a solver.</li>"
                "<li>Explain which VeraGrid tool you would use next and why.</li>"
                "</ul>"
                "</div>"
                "</div>"
                "</div>"
            )

    def _build_pending_banner_html(self, approval: PendingApproval) -> str:
        """
        Build the HTML banner for a pending approval request.

        :param approval: Pending approval request.
        :returns: Banner HTML.
        """
        escaped_tool_name: str = html.escape(approval.tool_name)
        escaped_arguments: str = html.escape(approval.arguments_json)
        escaped_reason: str = html.escape(approval.reason)

        return (
            "<div style='margin-top:12px;padding:10px;border:1px solid #e1a63b;"
            "background-color:#fff4d8;border-radius:6px;'>"
            f"<b>Approval required</b><br/>Tool: <code>{escaped_tool_name}</code><br/>"
            f"Arguments: <code>{escaped_arguments}</code><br/>"
            f"Reason: {escaped_reason}"
            "</div>"
        )

    def _format_message_html(self, message: ChatMessage) -> str:
        """
        Format one transcript message as HTML.

        :param message: Transcript message.
        :returns: Message HTML block.
        """
        role_label: str = self._get_role_label(message.role)
        background_color: str = self._get_role_background_color(message.role)
        border_color: str = self._get_role_border_color(message.role)
        content_color: str = self._get_role_content_color(message.role)
        role_color: str = self._get_role_label_color(message.role)
        row_alignment: str = self._get_role_row_alignment(message.role)
        message_width: str = self._get_role_message_width(message.role)
        content_text: str = convert_markdown_to_html(message.content)

        return (
            f"<div style='display:flex;justify-content:{row_alignment};margin-bottom:20px;'>"
            f"<div style='width:{message_width};'>"
            f"<div style='font-size:8.5pt;font-weight:600;letter-spacing:0.03em;"
            f"text-transform:uppercase;color:{role_color};margin-bottom:6px;'>"
            f"{html.escape(role_label)}</div>"
            "<div style='padding:14px 16px;border-radius:18px;"
            f"background-color:{background_color};border:1px solid {border_color};"
            f"color:{content_color};box-shadow:0 1px 2px rgba(15, 23, 42, 0.04);'>"
            f"{content_text}</div>"
            "</div>"
            "</div>"
        )

    def _get_role_label(self, role: str) -> str:
        """
        Map backend message roles into user-facing labels.

        :param role: Backend role name.
        :returns: Display label.
        """
        label: str

        if role == "user":
            label = "You"
        else:
            if role == "assistant":
                label = "VeraGrid AI"
            else:
                if role == "tool":
                    label = "Tool"
                else:
                    label = role.capitalize()

        return label

    def _get_role_background_color(self, role: str) -> str:
        """
        Map backend message roles into transcript background colors.

        :param role: Backend role name.
        :returns: CSS color value.
        """
        background_color: str

        if role == "user":
            background_color = "#dbeafe"
        else:
            if role == "assistant":
                background_color = "#ffffff"
            else:
                if role == "tool":
                    background_color = "#f3f4f6"
                else:
                    background_color = "#fff7ed"

        return background_color

    def _get_role_border_color(self, role: str) -> str:
        """
        Map backend message roles into transcript border colors.

        :param role: Backend role name.
        :returns: CSS color value.
        """
        border_color: str

        if role == "user":
            border_color = "#bfdbfe"
        else:
            if role == "assistant":
                border_color = "#e5e7eb"
            else:
                if role == "tool":
                    border_color = "#d1d5db"
                else:
                    border_color = "#fed7aa"

        return border_color

    def _get_role_content_color(self, role: str) -> str:
        """
        Map backend message roles into transcript text colors.

        :param role: Backend role name.
        :returns: CSS color value.
        """
        content_color: str

        if role == "user":
            content_color = "#0f172a"
        else:
            if role == "assistant":
                content_color = "#1f2937"
            else:
                if role == "tool":
                    content_color = "#374151"
                else:
                    content_color = "#7c2d12"

        return content_color

    def _get_role_label_color(self, role: str) -> str:
        """
        Map backend message roles into small heading colors.

        :param role: Backend role name.
        :returns: CSS color value.
        """
        label_color: str

        if role == "user":
            label_color = "#2563eb"
        else:
            if role == "assistant":
                label_color = "#6b7280"
            else:
                if role == "tool":
                    label_color = "#4b5563"
                else:
                    label_color = "#c2410c"

        return label_color

    def _get_role_row_alignment(self, role: str) -> str:
        """
        Map backend message roles into horizontal alignment for the transcript row.

        :param role: Backend role name.
        :returns: CSS flex alignment value.
        """
        row_alignment: str

        if role == "user":
            row_alignment = "flex-end"
        else:
            row_alignment = "flex-start"

        return row_alignment

    def _get_role_message_width(self, role: str) -> str:
        """
        Map backend message roles into width hints for the transcript bubble.

        :param role: Backend role name.
        :returns: CSS width expression.
        """
        message_width: str

        if role == "user":
            message_width = "min(78%, 620px)"
        else:
            if role == "assistant":
                message_width = "min(92%, 760px)"
            else:
                message_width = "min(86%, 700px)"

        return message_width


def run_ai_chat_dialogue() -> int:
    """
    Run the AI chat dialogue as a standalone Qt application.

    :returns: Qt application exit code.
    """
    app: QtWidgets.QApplication
    existing_app: Optional[QtWidgets.QApplication] = QtWidgets.QApplication.instance()

    # Reuse an existing QApplication when launched from an interactive session.
    if existing_app is None:
        app = QtWidgets.QApplication(list())
    else:
        app = existing_app

    # Create and show the dialogue as the main standalone window.
    dialogue: AiChatDialogue = AiChatDialogue()
    dialogue.show()

    if existing_app is None:
        return app.exec()
    else:
        return 0


if __name__ == "__main__":
    raise SystemExit(run_ai_chat_dialogue())
else:
    pass
