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
from VeraGrid.Gui.AiAgent.ai_retrieval import ProgramKnowledgeIndex
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


def execute_live_power_flow_from_app(app: "SimulationsMain") -> ToolExecutionResult:
    """
    Execute the standard VeraGrid power flow directly from the live application.

    :param app: VeraGrid main window.
    :returns: Tool execution result.
    """
    if app.circuit.valid_for_simulation():
        if app.session.is_this_running(SimulationTypes.PowerFlow_run):
            return ToolExecutionResult(
                success=False,
                error_code=ToolErrorCode.EXECUTION_ERROR,
                error_message="A power flow simulation is already running.",
                payload_json="{}",
            )
        else:
            app.run_power_flow()
            return ToolExecutionResult(
                success=True,
                error_code=ToolErrorCode.NONE,
                error_message="",
                payload_json=json.dumps(
                    {
                        "started": True,
                        "study_name": SimulationTypes.PowerFlow_run.value,
                        "message": (
                            "Started the standard VeraGrid power flow simulation "
                            "for the active project and current GUI options."
                        ),
                    },
                    ensure_ascii=False,
                ),
            )
    else:
        return ToolExecutionResult(
            success=False,
            error_code=ToolErrorCode.EXECUTION_ERROR,
            error_message="The current circuit is not valid for simulation.",
            payload_json="{}",
        )


def is_direct_power_flow_request(message_text: str) -> bool:
    """
    Check whether the user explicitly asked to run a standard power flow.

    :param message_text: User message text.
    :returns: True when the request clearly targets a power-flow run.
    """
    normalized_text: str = message_text.lower()
    run_verbs: list[str] = list()
    index: int = 0

    run_verbs.append("run")
    run_verbs.append("execute")
    run_verbs.append("start")
    run_verbs.append("launch")
    run_verbs.append("solve")
    run_verbs.append("calculate")

    if "power flow" in normalized_text:
        while index < len(run_verbs):
            if run_verbs[index] in normalized_text:
                return True
            else:
                pass
            index += 1
    else:
        pass

    return False


class MainThreadPowerFlowRunner(QtCore.QObject):
    """
    Main-thread bridge used to launch a VeraGrid power flow safely from the AI worker.

    :param app: VeraGrid main window.
    """

    request_run = QtCore.Signal()

    __slots__ = (
        "_app",
        "_pending_result",
    )

    def __init__(self, app: "SimulationsMain") -> None:
        """
        Build the main-thread power-flow bridge.

        :param app: VeraGrid main window.
        """
        QtCore.QObject.__init__(self)
        self._app: SimulationsMain = app
        self._pending_result: ToolExecutionResult = ToolExecutionResult(
            success=False,
            error_code=ToolErrorCode.EXECUTION_ERROR,
            error_message="The power flow tool did not run.",
            payload_json="{}",
        )
        self.request_run.connect(
            self._execute_run_power_flow,
            QtCore.Qt.ConnectionType.BlockingQueuedConnection,
        )

    def run_power_flow(self) -> ToolExecutionResult:
        """
        Launch the current VeraGrid power flow on the GUI thread.

        :returns: Tool execution result.
        """
        self.request_run.emit()
        return self._pending_result

    @QtCore.Slot()
    def _execute_run_power_flow(self) -> None:
        """
        Execute the standard power-flow action on the GUI thread.

        :returns: Nothing.
        """
        self._pending_result = execute_live_power_flow_from_app(self._app)


class LiveRunPowerFlowTool:
    """
    Live VeraGrid tool that launches the standard power flow.

    :param app: VeraGrid main window.
    """

    __slots__ = (
        "_runner",
    )

    def __init__(self, app: "SimulationsMain") -> None:
        """
        Build the live power-flow tool.

        :param app: VeraGrid main window.
        """
        self._runner: MainThreadPowerFlowRunner = MainThreadPowerFlowRunner(app)

    def execute(self, arguments: dict[str, object]) -> ToolExecutionResult:
        """
        Execute the live power-flow tool.

        :param arguments: Tool arguments.
        :returns: Tool execution result.
        """
        del arguments
        return self._runner.run_power_flow()


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
        record[str(headers[index])] = values[index]
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
    payload["driver_name"] = driver.name
    payload["driver_type"] = str(driver.tpe.value)
    payload["available_result_tree"] = driver.results.get_name_tree()

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
    run_power_flow_schema: str = json.dumps(
        {
            "type": "object",
            "properties": dict(),
            "additionalProperties": False,
        }
    )
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

    registry.register(
        ToolSpec(
            name="run_power_flow",
            description=(
                "Start the standard VeraGrid power flow simulation for the active project "
                "using the current GUI options."
            ),
            input_schema_json=run_power_flow_schema,
            risk=ToolRisk.COMPUTE,
            handler=LiveRunPowerFlowTool(app),
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
        Execute simple explicit app commands without relying on LLM tool-calling.

        :param message_text: User message text.
        :returns: True when the command was handled directly.
        """
        if self._app is None:
            return False
        else:
            pass

        if is_direct_power_flow_request(message_text):
            result: ToolExecutionResult = execute_live_power_flow_from_app(self._app)
            assistant_text: str

            self._history.append(ChatMessage(role="user", content=message_text, name=None))

            if result.success:
                assistant_text = (
                    "Started the standard VeraGrid power flow using the current GUI options. "
                    "The results will appear in VeraGrid when the simulation finishes."
                )
                self._set_status_message("Started the power flow simulation.")
            else:
                assistant_text = result.error_message
                self._set_status_message(result.error_message)

            self._history.append(ChatMessage(role="assistant", content=assistant_text, name=None))
            self._render_transcript()
            return True
        else:
            return False

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
