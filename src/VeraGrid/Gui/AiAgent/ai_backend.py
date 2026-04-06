from __future__ import annotations

"""
Provider-agnostic LLM integration layers for VeraGrid.

This module implements the following components:

- Provider selection through enums
- Typed request/response wrapper classes
- OpenAI provider
- Anthropic provider
- OpenAI-compatible provider for Ollama / LM Studio
- Local llama.cpp provider for GGUF models loaded in-process
- Tool registry
- Approval gate for mutating tools
- Conversation orchestrator
- VeraGrid context builder

The module is intentionally written in a conservative style so it can be
integrated into VeraGrid with minimal hidden behaviour.
"""

from enum import Enum
import json
import os
from typing import Any, Optional, Protocol

import requests


class ProviderType(Enum):
    """Supported LLM provider types."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OPENAI_COMPATIBLE = "openai_compatible"
    LOCAL_LLAMA_CPP = "local_llama_cpp"


class ToolRisk(Enum):
    """Risk classes for tool execution."""

    READ_ONLY = "read_only"
    COMPUTE = "compute"
    MUTATING = "mutating"
    DESTRUCTIVE = "destructive"


class ProviderErrorCode(Enum):
    """Error categories for provider execution."""

    NONE = "none"
    HTTP_ERROR = "http_error"
    PARSE_ERROR = "parse_error"
    INVALID_CONFIGURATION = "invalid_configuration"


class ToolErrorCode(Enum):
    """Error categories for tool execution."""

    NONE = "none"
    UNKNOWN_TOOL = "unknown_tool"
    APPROVAL_REQUIRED = "approval_required"
    EXECUTION_ERROR = "execution_error"


class ProviderConfig:
    """
    Provider configuration.

    :param provider_tpe: Selected provider type.
    :param model_name: Model identifier.
    :param api_key: API key if required.
    :param base_url: Base URL for the provider endpoint.
    :param timeout_s: HTTP timeout in seconds.
    """

    __slots__ = (
        "provider_tpe",
        "model_name",
        "api_key",
        "base_url",
        "timeout_s",
    )

    def __init__(
        self,
        provider_tpe: ProviderType,
        model_name: str,
        api_key: Optional[str],
        base_url: Optional[str],
        timeout_s: float,
    ) -> None:
        self.provider_tpe: ProviderType = provider_tpe
        self.model_name: str = model_name
        self.api_key: Optional[str] = api_key
        self.base_url: Optional[str] = base_url
        self.timeout_s: float = timeout_s


class ChatMessage:
    """
    Conversation message.

    :param role: Message role.
    :param content: Message text.
    :param name: Optional message name.
    """

    __slots__ = (
        "role",
        "content",
        "name",
    )

    def __init__(self, role: str, content: str, name: Optional[str] = None) -> None:
        self.role: str = role
        self.content: str = content
        self.name: Optional[str] = name


class ToolCall:
    """
    Tool call returned by a model.

    :param call_id: Tool call identifier.
    :param tool_name: Tool name.
    :param arguments_json: Raw arguments encoded as JSON.
    """

    __slots__ = (
        "call_id",
        "tool_name",
        "arguments_json",
    )

    def __init__(self, call_id: str, tool_name: str, arguments_json: str) -> None:
        self.call_id: str = call_id
        self.tool_name: str = tool_name
        self.arguments_json: str = arguments_json

    def parse_arguments(self) -> tuple[bool, dict[str, Any], str]:
        """
        Parse the tool arguments.

        :returns: Tuple with success flag, parsed arguments and error message.
        """
        parsed_args: dict[str, Any] = dict()
        error_msg: str = ""
        is_ok: bool = False

        try:
            parsed_obj: Any = json.loads(self.arguments_json)
            if isinstance(parsed_obj, dict):
                parsed_args = parsed_obj
                error_msg = ""
                is_ok = True
            else:
                parsed_args = dict()
                error_msg = "Tool arguments are not a JSON object."
                is_ok = False
        except json.JSONDecodeError:
            parsed_args = dict()
            error_msg = "Could not decode tool arguments JSON."
            is_ok = False

        return is_ok, parsed_args, error_msg


class LLMResponse:
    """
    Provider response wrapper.

    :param text: Assistant text.
    :param tool_calls: Parsed tool calls.
    :param error_code: Provider error code.
    :param error_message: Provider error description.
    """

    __slots__ = (
        "text",
        "tool_calls",
        "error_code",
        "error_message",
    )

    def __init__(
        self,
        text: str,
        tool_calls: list[ToolCall],
        error_code: ProviderErrorCode,
        error_message: str,
    ) -> None:
        self.text: str = text
        self.tool_calls: list[ToolCall] = tool_calls
        self.error_code: ProviderErrorCode = error_code
        self.error_message: str = error_message


class ModelListResult:
    """
    Result wrapper for provider model discovery.

    :param success: Discovery success flag.
    :param model_names: Ordered list of discovered model identifiers.
    :param error_message: Error description when discovery fails.
    """

    __slots__ = (
        "success",
        "model_names",
        "error_message",
    )

    def __init__(
        self,
        success: bool,
        model_names: list[str],
        error_message: str,
    ) -> None:
        self.success: bool = success
        self.model_names: list[str] = model_names
        self.error_message: str = error_message


class ToolExecutionResult:
    """
    Result wrapper for tool execution.

    :param success: Execution success flag.
    :param error_code: Tool error code.
    :param error_message: Error message.
    :param payload_json: Tool result encoded as JSON.
    """

    __slots__ = (
        "success",
        "error_code",
        "error_message",
        "payload_json",
    )

    def __init__(
        self,
        success: bool,
        error_code: ToolErrorCode,
        error_message: str,
        payload_json: str,
    ) -> None:
        self.success: bool = success
        self.error_code: ToolErrorCode = error_code
        self.error_message: str = error_message
        self.payload_json: str = payload_json


class PendingApproval:
    """
    Approval request for a pending tool call.

    :param tool_name: Tool name.
    :param arguments_json: Arguments encoded as JSON.
    :param reason: Approval reason.
    """

    __slots__ = (
        "tool_name",
        "arguments_json",
        "reason",
    )

    def __init__(self, tool_name: str, arguments_json: str, reason: str) -> None:
        self.tool_name: str = tool_name
        self.arguments_json: str = arguments_json
        self.reason: str = reason


class ToolSpec:
    """
    Tool specification wrapper.

    :param name: Tool name.
    :param description: Tool description.
    :param input_schema_json: JSON schema as string.
    :param risk: Tool risk class.
    :param handler: Object implementing the tool behaviour.
    """

    __slots__ = (
        "name",
        "description",
        "input_schema_json",
        "risk",
        "handler",
    )

    def __init__(
        self,
        name: str,
        description: str,
        input_schema_json: str,
        risk: ToolRisk,
        handler: "ToolHandlerProtocol",
    ) -> None:
        self.name: str = name
        self.description: str = description
        self.input_schema_json: str = input_schema_json
        self.risk: ToolRisk = risk
        self.handler: ToolHandlerProtocol = handler

    def build_openai_tool(self) -> dict[str, Any]:
        """
        Build the OpenAI/OpenAI-compatible tool schema.

        :returns: Tool schema dictionary.
        """
        params_obj: Any = json.loads(self.input_schema_json)
        tool_obj: dict[str, Any] = dict()
        function_obj: dict[str, Any] = dict()
        tool_obj["type"] = "function"
        function_obj["name"] = self.name
        function_obj["description"] = self.description
        function_obj["parameters"] = params_obj
        tool_obj["function"] = function_obj
        return tool_obj

    def build_anthropic_tool(self) -> dict[str, Any]:
        """
        Build the Anthropic tool schema.

        :returns: Tool schema dictionary.
        """
        params_obj: Any = json.loads(self.input_schema_json)
        tool_obj: dict[str, Any] = dict()
        tool_obj["name"] = self.name
        tool_obj["description"] = self.description
        tool_obj["input_schema"] = params_obj
        return tool_obj


class ToolHandlerProtocol(Protocol):
    """Protocol for explicit tool handler objects."""

    def execute(self, arguments: dict[str, Any]) -> ToolExecutionResult:
        """Execute the tool with explicit arguments."""


class ApprovalPolicy:
    """
    Approval policy for tool execution.

    :param require_mutating: Whether mutating tools require approval.
    :param require_destructive: Whether destructive tools require approval.
    """

    __slots__ = (
        "require_mutating",
        "require_destructive",
    )

    def __init__(self, require_mutating: bool, require_destructive: bool) -> None:
        self.require_mutating: bool = require_mutating
        self.require_destructive: bool = require_destructive

    def requires_approval(self, tool_spec: ToolSpec) -> bool:
        """
        Check whether the tool requires approval.

        :param tool_spec: Tool specification.
        :returns: Approval requirement flag.
        """
        requires_flag: bool = False

        if tool_spec.risk == ToolRisk.MUTATING:
            requires_flag = self.require_mutating
        else:
            if tool_spec.risk == ToolRisk.DESTRUCTIVE:
                requires_flag = self.require_destructive
            else:
                requires_flag = False

        return requires_flag


class ToolRegistry:
    """
    Registry of available tools.

    :param approval_policy: Tool approval policy.
    """

    __slots__ = (
        "_approval_policy",
        "_tools_by_name",
        "_tool_order",
    )

    def __init__(self, approval_policy: ApprovalPolicy) -> None:
        self._approval_policy: ApprovalPolicy = approval_policy
        self._tools_by_name: dict[str, ToolSpec] = dict()
        self._tool_order: list[str] = list()

    def register(self, tool_spec: ToolSpec) -> bool:
        """
        Register a tool.

        :param tool_spec: Tool specification.
        :returns: True if the tool was added, False if it already existed.
        """
        was_added: bool = False

        if tool_spec.name in self._tools_by_name:
            was_added = False
        else:
            self._tools_by_name[tool_spec.name] = tool_spec
            self._tool_order.append(tool_spec.name)
            was_added = True

        return was_added

    def get_tool(self, tool_name: str) -> Optional[ToolSpec]:
        """
        Get a tool by name.

        :param tool_name: Tool name.
        :returns: Tool specification or None.
        """
        tool_spec: Optional[ToolSpec] = self._tools_by_name.get(tool_name, None)
        return tool_spec

    def list_tools(self) -> list[ToolSpec]:
        """
        Return the registered tools in insertion order.

        :returns: List of tool specifications.
        """
        tool_specs: list[ToolSpec] = list()
        index: int = 0
        tool_count: int = len(self._tool_order)

        while index < tool_count:
            tool_name: str = self._tool_order[index]
            tool_spec: ToolSpec = self._tools_by_name[tool_name]
            tool_specs.append(tool_spec)
            index += 1

        return tool_specs

    def execute(
        self,
        tool_name: str,
        arguments_json: str,
        is_approved: bool,
    ) -> ToolExecutionResult:
        """
        Execute a registered tool.

        :param tool_name: Tool name.
        :param arguments_json: Tool arguments JSON.
        :param is_approved: Approval flag.
        :returns: Tool execution result.
        """
        tool_spec: Optional[ToolSpec] = self.get_tool(tool_name)
        result: ToolExecutionResult

        if tool_spec is None:
            result = ToolExecutionResult(
                success=False,
                error_code=ToolErrorCode.UNKNOWN_TOOL,
                error_message=f"Unknown tool: {tool_name}",
                payload_json="{}",
            )
        else:
            if self._approval_policy.requires_approval(tool_spec) and (not is_approved):
                result = ToolExecutionResult(
                    success=False,
                    error_code=ToolErrorCode.APPROVAL_REQUIRED,
                    error_message=f"Tool '{tool_name}' requires approval.",
                    payload_json="{}",
                )
            else:
                parsed_ok: bool
                parsed_args: dict[str, Any]
                parse_error: str
                parser: ToolCall = ToolCall("", tool_name, arguments_json)
                parsed_ok, parsed_args, parse_error = parser.parse_arguments()

                if parsed_ok:
                    result = tool_spec.handler.execute(parsed_args)
                else:
                    result = ToolExecutionResult(
                        success=False,
                        error_code=ToolErrorCode.EXECUTION_ERROR,
                        error_message=parse_error,
                        payload_json="{}",
                    )

        return result


class LLMProviderProtocol(Protocol):
    """Protocol for LLM providers."""

    def complete(
        self,
        system_prompt: str,
        messages: list[ChatMessage],
        tool_specs: list[ToolSpec],
    ) -> LLMResponse:
        """Run one provider completion."""


class HTTPClient:
    """
    Simple explicit HTTP client wrapper.

    :param config: Provider configuration.
    """

    __slots__ = ("_config",)

    def __init__(self, config: ProviderConfig) -> None:
        self._config: ProviderConfig = config

    def build_headers(self) -> dict[str, str]:
        """
        Build the request headers.

        :returns: HTTP headers.
        """
        headers: dict[str, str] = dict()
        headers["Content-Type"] = "application/json"

        if self._config.provider_tpe == ProviderType.ANTHROPIC:
            headers["anthropic-version"] = "2023-06-01"
        else:
            headers["Content-Type"] = "application/json"

        if self._config.api_key is None:
            headers_result: dict[str, str] = headers
        else:
            if self._config.provider_tpe == ProviderType.ANTHROPIC:
                headers["x-api-key"] = self._config.api_key
                headers_result = headers
            else:
                headers["Authorization"] = f"Bearer {self._config.api_key}"
                headers_result = headers

        return headers_result

    def post_json(self, url: str, payload: dict[str, Any]) -> tuple[bool, dict[str, Any], str]:
        """
        Execute a POST request and decode the JSON response.

        :param url: Endpoint URL.
        :param payload: JSON payload.
        :returns: Tuple with success flag, decoded payload and error message.
        """
        response_obj: requests.Response
        result_obj: dict[str, Any] = dict()
        error_msg: str = ""
        is_ok: bool = False

        try:
            response_obj = requests.post(
                url,
                headers=self.build_headers(),
                json=payload,
                timeout=self._config.timeout_s,
            )
            if response_obj.status_code >= 400:
                result_obj = dict()
                error_msg = f"HTTP {response_obj.status_code}: {response_obj.text}"
                is_ok = False
            else:
                try:
                    decoded_obj: Any = response_obj.json()
                    if isinstance(decoded_obj, dict):
                        result_obj = decoded_obj
                        error_msg = ""
                        is_ok = True
                    else:
                        result_obj = dict()
                        error_msg = "Provider returned a non-object JSON payload."
                        is_ok = False
                except ValueError:
                    result_obj = dict()
                    error_msg = "Provider returned invalid JSON."
                    is_ok = False
        except requests.RequestException as exc:
            result_obj = dict()
            error_msg = str(exc)
            is_ok = False

        return is_ok, result_obj, error_msg

    def get_json(self, url: str) -> tuple[bool, dict[str, Any], str]:
        """
        Execute a GET request and decode the JSON response.

        :param url: Endpoint URL.
        :returns: Tuple with success flag, decoded payload and error message.
        """
        response_obj: requests.Response
        result_obj: dict[str, Any] = dict()
        error_msg: str = ""
        is_ok: bool = False

        try:
            response_obj = requests.get(
                url,
                headers=self.build_headers(),
                timeout=self._config.timeout_s,
            )
            if response_obj.status_code >= 400:
                result_obj = dict()
                error_msg = f"HTTP {response_obj.status_code}: {response_obj.text}"
                is_ok = False
            else:
                try:
                    decoded_obj: Any = response_obj.json()
                    if isinstance(decoded_obj, dict):
                        result_obj = decoded_obj
                        error_msg = ""
                        is_ok = True
                    else:
                        result_obj = dict()
                        error_msg = "Provider returned a non-object JSON payload."
                        is_ok = False
                except ValueError:
                    result_obj = dict()
                    error_msg = "Provider returned invalid JSON."
                    is_ok = False
        except requests.RequestException as exc:
            result_obj = dict()
            error_msg = str(exc)
            is_ok = False

        return is_ok, result_obj, error_msg


class OpenAIProvider:
    """
    OpenAI Responses API provider.

    :param config: Provider configuration.
    """

    __slots__ = (
        "_config",
        "_http_client",
    )

    def __init__(self, config: ProviderConfig) -> None:
        self._config: ProviderConfig = config
        self._http_client: HTTPClient = HTTPClient(config)

    def complete(
        self,
        system_prompt: str,
        messages: list[ChatMessage],
        tool_specs: list[ToolSpec],
    ) -> LLMResponse:
        """
        Execute one OpenAI completion.

        :param system_prompt: System prompt.
        :param messages: Conversation messages.
        :param tool_specs: Available tools.
        :returns: Provider response.
        """
        base_url: Optional[str] = self._config.base_url
        message_count: int = len(messages)
        input_items: list[dict[str, Any]] = list()
        tool_items: list[dict[str, Any]] = list()
        index: int = 0

        if base_url is None:
            return LLMResponse(
                text="",
                tool_calls=list(),
                error_code=ProviderErrorCode.INVALID_CONFIGURATION,
                error_message="OpenAI base URL is not configured.",
            )
        else:
            while index < message_count:
                message_obj: ChatMessage = messages[index]
                input_item: dict[str, Any] = dict()
                content_item: dict[str, Any] = dict()
                content_items: list[dict[str, Any]] = list()
                input_item["role"] = message_obj.role
                content_item["type"] = "input_text"
                content_item["text"] = message_obj.content
                content_items.append(content_item)
                input_item["content"] = content_items
                input_items.append(input_item)
                index += 1

            index = 0
            while index < len(tool_specs):
                tool_items.append(tool_specs[index].build_openai_tool())
                index += 1

            payload: dict[str, Any] = dict()
            payload["model"] = self._config.model_name
            payload["instructions"] = system_prompt
            payload["input"] = input_items
            payload["tools"] = tool_items

            url: str = f"{base_url.rstrip('/')}/responses"
            ok_http: bool
            response_obj: dict[str, Any]
            http_error: str
            ok_http, response_obj, http_error = self._http_client.post_json(url, payload)

            if ok_http:
                return parse_openai_responses_payload(response_obj)
            else:
                return LLMResponse(
                    text="",
                    tool_calls=list(),
                    error_code=ProviderErrorCode.HTTP_ERROR,
                    error_message=http_error,
                )


class AnthropicProvider:
    """
    Anthropic Messages API provider.

    :param config: Provider configuration.
    """

    __slots__ = (
        "_config",
        "_http_client",
    )

    def __init__(self, config: ProviderConfig) -> None:
        self._config: ProviderConfig = config
        self._http_client: HTTPClient = HTTPClient(config)

    def complete(
        self,
        system_prompt: str,
        messages: list[ChatMessage],
        tool_specs: list[ToolSpec],
    ) -> LLMResponse:
        """
        Execute one Anthropic completion.

        :param system_prompt: System prompt.
        :param messages: Conversation messages.
        :param tool_specs: Available tools.
        :returns: Provider response.
        """
        base_url: Optional[str] = self._config.base_url
        payload_messages: list[dict[str, Any]] = list()
        tool_items: list[dict[str, Any]] = list()
        index: int = 0

        if base_url is None:
            return LLMResponse(
                text="",
                tool_calls=list(),
                error_code=ProviderErrorCode.INVALID_CONFIGURATION,
                error_message="Anthropic base URL is not configured.",
            )
        else:
            while index < len(messages):
                message_obj: ChatMessage = messages[index]
                item: dict[str, Any] = dict()
                item["role"] = message_obj.role
                item["content"] = message_obj.content
                payload_messages.append(item)
                index += 1

            index = 0
            while index < len(tool_specs):
                tool_items.append(tool_specs[index].build_anthropic_tool())
                index += 1

            payload: dict[str, Any] = dict()
            payload["model"] = self._config.model_name
            payload["system"] = system_prompt
            payload["messages"] = payload_messages
            payload["tools"] = tool_items
            payload["max_tokens"] = 2048

            url: str = f"{base_url.rstrip('/')}/messages"
            ok_http: bool
            response_obj: dict[str, Any]
            http_error: str
            ok_http, response_obj, http_error = self._http_client.post_json(url, payload)

            if ok_http:
                return parse_anthropic_payload(response_obj)
            else:
                return LLMResponse(
                    text="",
                    tool_calls=list(),
                    error_code=ProviderErrorCode.HTTP_ERROR,
                    error_message=http_error,
                )


class OpenAICompatibleProvider:
    """
    OpenAI-compatible provider for Ollama / LM Studio.

    :param config: Provider configuration.
    """

    __slots__ = (
        "_config",
        "_http_client",
    )

    def __init__(self, config: ProviderConfig) -> None:
        self._config: ProviderConfig = config
        self._http_client: HTTPClient = HTTPClient(config)

    def complete(
        self,
        system_prompt: str,
        messages: list[ChatMessage],
        tool_specs: list[ToolSpec],
    ) -> LLMResponse:
        """
        Execute one OpenAI-compatible chat completion.

        :param system_prompt: System prompt.
        :param messages: Conversation messages.
        :param tool_specs: Available tools.
        :returns: Provider response.
        """
        base_url: Optional[str] = self._config.base_url
        payload_messages: list[dict[str, Any]]
        tool_items: list[dict[str, Any]] = list()
        index: int = 0

        if base_url is None:
            return LLMResponse(
                text="",
                tool_calls=list(),
                error_code=ProviderErrorCode.INVALID_CONFIGURATION,
                error_message="OpenAI-compatible base URL is not configured.",
            )
        else:
            payload_messages = build_openai_compatible_messages(system_prompt, messages)

            index = 0
            while index < len(tool_specs):
                tool_items.append(tool_specs[index].build_openai_tool())
                index += 1

            payload: dict[str, Any] = dict()
            payload["model"] = self._config.model_name
            payload["messages"] = payload_messages
            payload["tools"] = tool_items
            payload["tool_choice"] = "auto"
            payload["max_tokens"] = 2048

            url: str = f"{base_url.rstrip('/')}/chat/completions"
            ok_http: bool
            response_obj: dict[str, Any]
            http_error: str
            ok_http, response_obj, http_error = self._http_client.post_json(url, payload)

            if ok_http:
                return parse_openai_compatible_payload(response_obj)
            else:
                return LLMResponse(
                    text="",
                    tool_calls=list(),
                    error_code=ProviderErrorCode.HTTP_ERROR,
                    error_message=http_error,
                )


def build_openai_compatible_messages(
    system_prompt: str,
    messages: list[ChatMessage],
) -> list[dict[str, Any]]:
    """
    Build an OpenAI-compatible message array.

    :param system_prompt: System prompt.
    :param messages: Conversation messages.
    :returns: OpenAI-compatible message array.
    """
    payload_messages: list[dict[str, Any]] = list()
    system_item: dict[str, Any] = dict()
    index: int = 0

    # Keep the system message explicit and first so all backends see the same context.
    system_item["role"] = "system"
    system_item["content"] = system_prompt
    payload_messages.append(system_item)

    # Convert the internal transcript into the shape expected by OpenAI-style APIs.
    while index < len(messages):
        message_obj: ChatMessage = messages[index]
        item: dict[str, Any] = dict()
        item["role"] = message_obj.role
        item["content"] = message_obj.content

        # Tool messages may carry the tool name and some local providers can use it.
        if message_obj.name is None:
            pass
        else:
            item["name"] = message_obj.name

        payload_messages.append(item)
        index += 1

    return payload_messages


def resolve_local_llama_model_path(config: ProviderConfig) -> tuple[bool, str, str]:
    """
    Resolve a local GGUF model path from the provider configuration.

    :param config: Provider configuration.
    :returns: Tuple with success flag, resolved model path and error message.
    """
    base_path_raw: Optional[str] = config.base_url
    model_name_raw: str = config.model_name.strip()
    base_path: str
    candidate_path: str
    alternate_path: str

    if base_path_raw is None:
        return False, "", "Local llama.cpp requires a model path or model directory."
    else:
        base_path = os.path.expanduser(base_path_raw.strip())

    if len(base_path) == 0:
        return False, "", "Local llama.cpp requires a model path or model directory."
    else:
        if os.path.isfile(base_path):
            return True, base_path, ""
        else:
            if os.path.isdir(base_path):
                if len(model_name_raw) == 0:
                    return False, "", "Select a model or type a GGUF file name for the chosen directory."
                else:
                    candidate_path = os.path.join(base_path, model_name_raw)
                    if os.path.isfile(candidate_path):
                        return True, candidate_path, ""
                    else:
                        if model_name_raw.endswith(".gguf"):
                            return False, "", f"Model file does not exist: {candidate_path}"
                        else:
                            alternate_path = os.path.join(base_path, f"{model_name_raw}.gguf")
                            if os.path.isfile(alternate_path):
                                return True, alternate_path, ""
                            else:
                                return False, "", f"Model file does not exist: {candidate_path}"
            else:
                return False, "", f"Configured local path does not exist: {base_path}"


def list_local_llama_models(config: ProviderConfig) -> ModelListResult:
    """
    List local GGUF models from a configured path.

    :param config: Provider configuration.
    :returns: Model discovery result.
    """
    base_path_raw: Optional[str] = config.base_url
    base_path: str
    entry_names: list[str]
    model_names: list[str]
    index: int

    if base_path_raw is None:
        return ModelListResult(
            success=False,
            model_names=list(),
            error_message="Local llama.cpp requires a model path or model directory.",
        )
    else:
        base_path = os.path.expanduser(base_path_raw.strip())

    if len(base_path) == 0:
        return ModelListResult(
            success=False,
            model_names=list(),
            error_message="Local llama.cpp requires a model path or model directory.",
        )
    else:
        if os.path.isfile(base_path):
            return ModelListResult(
                success=True,
                model_names=[os.path.basename(base_path)],
                error_message="",
            )
        else:
            if os.path.isdir(base_path):
                try:
                    entry_names = os.listdir(base_path)
                except OSError as exc:
                    return ModelListResult(
                        success=False,
                        model_names=list(),
                        error_message=str(exc),
                    )

                model_names = list()
                index = 0

                # Surface only GGUF files because llama.cpp loads those directly.
                while index < len(entry_names):
                    entry_name: str = entry_names[index]
                    entry_path: str = os.path.join(base_path, entry_name)
                    if os.path.isfile(entry_path) and entry_name.lower().endswith(".gguf"):
                        model_names.append(entry_name)
                    else:
                        pass
                    index += 1

                model_names.sort()

                if len(model_names) > 0:
                    return ModelListResult(
                        success=True,
                        model_names=model_names,
                        error_message="",
                    )
                else:
                    return ModelListResult(
                        success=False,
                        model_names=list(),
                        error_message="No GGUF files were found in the configured directory.",
                    )
            else:
                return ModelListResult(
                    success=False,
                    model_names=list(),
                    error_message=f"Configured local path does not exist: {base_path}",
                )


def import_llama_cpp_llama() -> tuple[bool, Any, str]:
    """
    Import the llama.cpp Python binding lazily.

    :returns: Tuple with success flag, imported Llama class and error message.
    """
    llama_class: Any = None

    # The local provider is optional, so the import stays lazy and recoverable.
    try:
        from llama_cpp import Llama

        llama_class = Llama
        return True, llama_class, ""
    except ImportError:
        return False, None, "llama-cpp-python is not installed."


class LocalLlamaCppProvider:
    """
    Local in-process provider backed by llama-cpp-python.

    :param config: Provider configuration.
    """

    __slots__ = (
        "_config",
        "_model_instance",
        "_loaded_model_path",
    )

    def __init__(self, config: ProviderConfig) -> None:
        self._config: ProviderConfig = config
        self._model_instance: Optional[Any] = None
        self._loaded_model_path: Optional[str] = None

    def _ensure_model(self) -> tuple[bool, str]:
        """
        Load the GGUF model lazily if required.

        :returns: Tuple with success flag and error message.
        """
        ok_import: bool
        llama_class: Any
        import_error: str
        ok_path: bool
        model_path: str
        path_error: str

        ok_path, model_path, path_error = resolve_local_llama_model_path(self._config)
        if ok_path:
            pass
        else:
            return False, path_error

        if (self._model_instance is not None) and (self._loaded_model_path == model_path):
            return True, ""
        else:
            ok_import, llama_class, import_error = import_llama_cpp_llama()
            if ok_import:
                pass
            else:
                return False, f"{import_error} Install it and configure a GGUF model path."

            try:
                # Keep the defaults explicit and conservative for desktop usage.
                self._model_instance = llama_class(
                    model_path=model_path,
                    n_ctx=4096,
                    n_gpu_layers=33,
                    verbose=False,
                )
                self._loaded_model_path = model_path
                return True, ""
            except Exception as exc:
                self._model_instance = None
                self._loaded_model_path = None
                return False, str(exc)

    def complete(
        self,
        system_prompt: str,
        messages: list[ChatMessage],
        tool_specs: list[ToolSpec],
    ) -> LLMResponse:
        """
        Execute one in-process llama.cpp chat completion.

        :param system_prompt: System prompt.
        :param messages: Conversation messages.
        :param tool_specs: Available tools.
        :returns: Provider response.
        """
        ok_model: bool
        model_error: str
        payload_messages: list[dict[str, Any]]
        tool_items: list[dict[str, Any]]
        payload: dict[str, Any]
        response_obj: Any
        index: int

        ok_model, model_error = self._ensure_model()
        if ok_model:
            pass
        else:
            return LLMResponse(
                text="",
                tool_calls=list(),
                error_code=ProviderErrorCode.INVALID_CONFIGURATION,
                error_message=model_error,
            )

        payload_messages = build_openai_compatible_messages(system_prompt, messages)
        tool_items = list()
        index = 0

        # Reuse the OpenAI-style tool schema so the local provider stays aligned with the rest.
        while index < len(tool_specs):
            tool_items.append(tool_specs[index].build_openai_tool())
            index += 1

        payload = dict()
        payload["messages"] = payload_messages
        payload["max_tokens"] = 2048

        if len(self._config.model_name.strip()) > 0:
            payload["model"] = self._config.model_name.strip()
        else:
            pass

        if len(tool_items) > 0:
            payload["tools"] = tool_items
            payload["tool_choice"] = "auto"
        else:
            pass

        try:
            if self._model_instance is None:
                return LLMResponse(
                    text="",
                    tool_calls=list(),
                    error_code=ProviderErrorCode.INVALID_CONFIGURATION,
                    error_message="Local llama.cpp model is not loaded.",
                )
            else:
                response_obj = self._model_instance.create_chat_completion(**payload)
        except Exception as exc:
            return LLMResponse(
                text="",
                tool_calls=list(),
                error_code=ProviderErrorCode.HTTP_ERROR,
                error_message=str(exc),
            )

        if isinstance(response_obj, dict):
            return parse_openai_compatible_payload(response_obj)
        else:
            return LLMResponse(
                text="",
                tool_calls=list(),
                error_code=ProviderErrorCode.PARSE_ERROR,
                error_message="Local llama.cpp provider returned an invalid response object.",
            )


class VeraGridContext:
    """
    Context made available to the assistant.

    :param project_name: Project name.
    :param active_study: Active study name.
    :param solver_name: Solver name.
    :param selected_elements: Selected elements.
    :param notes: Additional notes.
    """

    __slots__ = (
        "project_name",
        "active_study",
        "solver_name",
        "selected_elements",
        "notes",
    )

    def __init__(
        self,
        project_name: Optional[str],
        active_study: Optional[str],
        solver_name: Optional[str],
        selected_elements: list[str],
        notes: list[str],
    ) -> None:
        self.project_name: Optional[str] = project_name
        self.active_study: Optional[str] = active_study
        self.solver_name: Optional[str] = solver_name
        self.selected_elements: list[str] = selected_elements
        self.notes: list[str] = notes


class ConversationRunResult:
    """
    Result of one orchestrated run.

    :param final_text: Assistant final text.
    :param pending_approval: Pending approval request if any.
    :param transcript: Final transcript.
    """

    __slots__ = (
        "final_text",
        "pending_approval",
        "transcript",
    )

    def __init__(
        self,
        final_text: str,
        pending_approval: Optional[PendingApproval],
        transcript: list[ChatMessage],
    ) -> None:
        self.final_text: str = final_text
        self.pending_approval: Optional[PendingApproval] = pending_approval
        self.transcript: list[ChatMessage] = transcript


class ConversationOrchestrator:
    """
    Orchestrates assistant completions and tool calls.

    :param provider: Selected provider.
    :param tool_registry: Tool registry.
    :param max_rounds: Maximum tool-calling rounds.
    """

    __slots__ = (
        "_provider",
        "_tool_registry",
        "_max_rounds",
    )

    def __init__(
        self,
        provider: LLMProviderProtocol,
        tool_registry: ToolRegistry,
        max_rounds: int,
    ) -> None:
        self._provider: LLMProviderProtocol = provider
        self._tool_registry: ToolRegistry = tool_registry
        self._max_rounds: int = max_rounds

    def run(
        self,
        system_prompt: str,
        user_message: str,
        grounding_context_text: str,
        history: list[ChatMessage],
        approved_tool_name: Optional[str],
        approved_arguments_json: Optional[str],
    ) -> ConversationRunResult:
        """
        Execute the orchestration loop.

        :param system_prompt: System prompt.
        :param user_message: User input.
        :param grounding_context_text: Deterministic grounding context for the current turn.
        :param history: Existing conversation history.
        :param approved_tool_name: Approved tool name if any.
        :param approved_arguments_json: Approved tool arguments if any.
        :returns: Run result.
        """
        transcript: list[ChatMessage] = list()
        llm_transcript: list[ChatMessage] = list()
        round_index: int = 0
        message_index: int = 0
        final_text: str = ""
        pending_approval: Optional[PendingApproval] = None
        effective_user_message: str = user_message

        while message_index < len(history):
            transcript.append(history[message_index])
            llm_transcript.append(history[message_index])
            message_index += 1

        if len(grounding_context_text.strip()) > 0:
            effective_user_message = (
                "Authoritative VeraGrid grounding context for this request:\n"
                f"{grounding_context_text}\n\n"
                "User request:\n"
                f"{user_message}\n\n"
                "Treat references like 'this grid', 'given grid', or 'current grid' as the active VeraGrid session above. "
                "Answer from that grounding context first. If the answer still requires more project data, use tools."
            )
        else:
            pass

        transcript.append(ChatMessage(role="user", content=user_message, name=None))
        llm_transcript.append(ChatMessage(role="user", content=effective_user_message, name=None))

        while round_index < self._max_rounds:
            provider_response: LLMResponse = self._provider.complete(
                system_prompt=system_prompt,
                messages=llm_transcript,
                tool_specs=self._tool_registry.list_tools(),
            )

            if provider_response.error_code == ProviderErrorCode.NONE:
                final_text = provider_response.text
            else:
                final_text = provider_response.error_message

            if len(provider_response.text) > 0:
                assistant_message: ChatMessage = ChatMessage(
                    role="assistant",
                    content=provider_response.text,
                    name=None,
                )
            else:
                assistant_message = ChatMessage(role="assistant", content=final_text, name=None)

            transcript.append(assistant_message)
            llm_transcript.append(assistant_message)

            if len(provider_response.tool_calls) == 0:
                pending_approval = None
                round_index = self._max_rounds
            else:
                tool_index: int = 0
                stop_loop: bool = False

                while tool_index < len(provider_response.tool_calls) and (not stop_loop):
                    tool_call: ToolCall = provider_response.tool_calls[tool_index]
                    is_approved: bool = False

                    if approved_tool_name is None:
                        is_approved = False
                    else:
                        if approved_arguments_json is None:
                            is_approved = False
                        else:
                            if (tool_call.tool_name == approved_tool_name) and (
                                tool_call.arguments_json == approved_arguments_json
                            ):
                                is_approved = True
                            else:
                                is_approved = False

                    tool_result: ToolExecutionResult = self._tool_registry.execute(
                        tool_name=tool_call.tool_name,
                        arguments_json=tool_call.arguments_json,
                        is_approved=is_approved,
                    )

                    if tool_result.error_code == ToolErrorCode.APPROVAL_REQUIRED:
                        pending_approval = PendingApproval(
                            tool_name=tool_call.tool_name,
                            arguments_json=tool_call.arguments_json,
                            reason=tool_result.error_message,
                        )
                        stop_loop = True
                    else:
                        tool_message_text: str = tool_result.payload_json
                        tool_message: ChatMessage = ChatMessage(
                            role="tool",
                            content=tool_message_text,
                            name=tool_call.tool_name,
                        )
                        transcript.append(tool_message)
                        llm_transcript.append(tool_message)
                        pending_approval = None

                    tool_index += 1

                if stop_loop:
                    round_index = self._max_rounds
                else:
                    round_index += 1

        return ConversationRunResult(
            final_text=final_text,
            pending_approval=pending_approval,
            transcript=transcript,
        )


class PromptFactory:
    """Factory for system prompt construction."""

    __slots__ = ()

    def build_system_prompt(
        self,
        context: VeraGridContext,
        retrieved_context_text: str = "",
    ) -> str:
        """
        Build the system prompt from the current VeraGrid context.

        :param context: VeraGrid context.
        :param retrieved_context_text: Retrieved grounding references.
        :returns: Prompt text.
        """
        context_obj: dict[str, Any] = dict()
        context_obj["project_name"] = context.project_name
        context_obj["active_study"] = context.active_study
        context_obj["solver_name"] = context.solver_name
        context_obj["selected_elements"] = context.selected_elements
        context_obj["notes"] = context.notes

        prompt_text: str = (
            "You are the VeraGrid engineering assistant. "
            "Use tools when authoritative project data is required. "
            "For questions about the currently loaded model, session, studies, drivers, or results, "
            "query the live runtime tools instead of guessing. "
            "Prefer search_runtime_records, get_runtime_record, get_model_summary, "
            "get_selected_elements, list_available_studies, and get_study_summary when they are available. "
            "If the user asks what is wrong with the grid, to diagnose the model, or to explain structural issues, "
            "use analyze_grid_issues when it is available. "
            "When the user asks you to run, execute, launch, solve, or calculate an analysis "
            "and a matching tool exists, call the tool instead of only describing the action. "
            "Do not invent study results. "
            "Treat phrases such as 'this grid', 'given grid', 'current grid', and 'loaded grid' "
            "as references to the active VeraGrid project context below. "
            "If a project-changing action is requested, require approval before executing it.\n\n"
            "Current VeraGrid context:\n"
            f"{json.dumps(context_obj, indent=2, ensure_ascii=False)}"
        )

        if len(retrieved_context_text.strip()) > 0:
            prompt_text += (
                "\n\nRetrieved authoritative VeraGrid references:\n"
                f"{retrieved_context_text}"
            )
        else:
            pass

        return prompt_text


class RunPowerFlowTool:
    """Example power-flow tool."""

    __slots__ = ()

    def execute(self, arguments: dict[str, Any]) -> ToolExecutionResult:
        """
        Execute the power-flow tool.

        :param arguments: Tool arguments.
        :returns: Tool result.
        """
        case_id: Any = arguments.get("case_id", None)
        result_obj: dict[str, Any] = dict()

        if isinstance(case_id, str):
            result_obj["case_id"] = case_id
            result_obj["status"] = "converged"
            result_obj["min_voltage_pu"] = 0.95
            result_obj["max_voltage_pu"] = 1.01
            result_obj["max_branch_loading_pct"] = 91.2
            return ToolExecutionResult(
                success=True,
                error_code=ToolErrorCode.NONE,
                error_message="",
                payload_json=json.dumps(result_obj, ensure_ascii=False),
            )
        else:
            return ToolExecutionResult(
                success=False,
                error_code=ToolErrorCode.EXECUTION_ERROR,
                error_message="Invalid or missing case_id.",
                payload_json="{}",
            )


class ListBusesTool:
    """Example bus-listing tool."""

    __slots__ = ()

    def execute(self, arguments: dict[str, Any]) -> ToolExecutionResult:
        """
        Execute the bus-listing tool.

        :param arguments: Tool arguments.
        :returns: Tool result.
        """
        kv_min_obj: Any = arguments.get("kv_min", None)
        items: list[dict[str, Any]] = list()
        result_obj: dict[str, Any] = dict()

        items.append({"id": "Bus1", "kv": 400.0, "vm_pu": 1.01})
        items.append({"id": "Bus2", "kv": 220.0, "vm_pu": 0.97})
        items.append({"id": "Bus3", "kv": 132.0, "vm_pu": 0.95})

        if kv_min_obj is None:
            filtered_items: list[dict[str, Any]] = items
        else:
            if isinstance(kv_min_obj, (int, float)):
                filtered_items = list()
                index: int = 0
                while index < len(items):
                    item: dict[str, Any] = items[index]
                    item_kv: Any = item.get("kv", None)
                    if isinstance(item_kv, (int, float)) and (item_kv >= float(kv_min_obj)):
                        filtered_items.append(item)
                    else:
                        pass
                    index += 1
            else:
                return ToolExecutionResult(
                    success=False,
                    error_code=ToolErrorCode.EXECUTION_ERROR,
                    error_message="Invalid kv_min.",
                    payload_json="{}",
                )

        result_obj["count"] = len(filtered_items)
        result_obj["items"] = filtered_items
        return ToolExecutionResult(
            success=True,
            error_code=ToolErrorCode.NONE,
            error_message="",
            payload_json=json.dumps(result_obj, ensure_ascii=False),
        )


class ApplyParameterPatchTool:
    """Example mutating patch tool."""

    __slots__ = ()

    def execute(self, arguments: dict[str, Any]) -> ToolExecutionResult:
        """
        Execute the patch tool.

        :param arguments: Tool arguments.
        :returns: Tool result.
        """
        element_id: Any = arguments.get("element_id", None)
        patch_obj: Any = arguments.get("patch", None)
        result_obj: dict[str, Any] = dict()

        if isinstance(element_id, str):
            if isinstance(patch_obj, dict):
                result_obj["status"] = "updated"
                result_obj["element_id"] = element_id
                result_obj["applied_patch"] = patch_obj
                return ToolExecutionResult(
                    success=True,
                    error_code=ToolErrorCode.NONE,
                    error_message="",
                    payload_json=json.dumps(result_obj, ensure_ascii=False),
                )
            else:
                return ToolExecutionResult(
                    success=False,
                    error_code=ToolErrorCode.EXECUTION_ERROR,
                    error_message="Invalid patch object.",
                    payload_json="{}",
                )
        else:
            return ToolExecutionResult(
                success=False,
                error_code=ToolErrorCode.EXECUTION_ERROR,
                error_message="Invalid element_id.",
                payload_json="{}",
            )


def parse_openai_responses_payload(payload: dict[str, Any]) -> LLMResponse:
    """
    Parse an OpenAI Responses payload.

    :param payload: Provider payload.
    :returns: Parsed response.
    """
    output_obj: Any = payload.get("output", None)
    text_parts: list[str] = list()
    tool_calls: list[ToolCall] = list()

    if isinstance(output_obj, list):
        index: int = 0
        while index < len(output_obj):
            item: Any = output_obj[index]
            if isinstance(item, dict):
                item_tpe: Any = item.get("type", None)
                if item_tpe == "message":
                    content_obj: Any = item.get("content", None)
                    if isinstance(content_obj, list):
                        content_index: int = 0
                        while content_index < len(content_obj):
                            content_item: Any = content_obj[content_index]
                            if isinstance(content_item, dict):
                                content_tpe: Any = content_item.get("type", None)
                                text_obj: Any = content_item.get("text", None)
                                if (content_tpe in ("output_text", "text")) and isinstance(text_obj, str):
                                    text_parts.append(text_obj)
                                else:
                                    pass
                            else:
                                pass
                            content_index += 1
                    else:
                        pass
                else:
                    if item_tpe == "function_call":
                        tool_id_obj: Any = item.get("call_id", None)
                        tool_name_obj: Any = item.get("name", None)
                        tool_args_obj: Any = item.get("arguments", None)
                        if isinstance(tool_id_obj, str) and isinstance(tool_name_obj, str):
                            if isinstance(tool_args_obj, str):
                                tool_calls.append(
                                    ToolCall(
                                        call_id=tool_id_obj,
                                        tool_name=tool_name_obj,
                                        arguments_json=tool_args_obj,
                                    )
                                )
                            else:
                                tool_calls.append(
                                    ToolCall(
                                        call_id=tool_id_obj,
                                        tool_name=tool_name_obj,
                                        arguments_json="{}",
                                    )
                                )
                        else:
                            pass
                    else:
                        pass
            else:
                pass
            index += 1

        return LLMResponse(
            text="\n".join(text_parts).strip(),
            tool_calls=tool_calls,
            error_code=ProviderErrorCode.NONE,
            error_message="",
        )
    else:
        return LLMResponse(
            text="",
            tool_calls=list(),
            error_code=ProviderErrorCode.PARSE_ERROR,
            error_message="OpenAI response payload does not contain a valid output list.",
        )



def parse_anthropic_payload(payload: dict[str, Any]) -> LLMResponse:
    """
    Parse an Anthropic Messages payload.

    :param payload: Provider payload.
    :returns: Parsed response.
    """
    content_obj: Any = payload.get("content", None)
    text_parts: list[str] = list()
    tool_calls: list[ToolCall] = list()

    if isinstance(content_obj, list):
        index: int = 0
        while index < len(content_obj):
            item: Any = content_obj[index]
            if isinstance(item, dict):
                item_tpe: Any = item.get("type", None)
                if item_tpe == "text":
                    text_obj: Any = item.get("text", None)
                    if isinstance(text_obj, str):
                        text_parts.append(text_obj)
                    else:
                        pass
                else:
                    if item_tpe == "tool_use":
                        tool_id_obj: Any = item.get("id", None)
                        tool_name_obj: Any = item.get("name", None)
                        tool_input_obj: Any = item.get("input", None)
                        if isinstance(tool_id_obj, str) and isinstance(tool_name_obj, str):
                            if isinstance(tool_input_obj, dict):
                                tool_calls.append(
                                    ToolCall(
                                        call_id=tool_id_obj,
                                        tool_name=tool_name_obj,
                                        arguments_json=json.dumps(tool_input_obj, ensure_ascii=False),
                                    )
                                )
                            else:
                                tool_calls.append(
                                    ToolCall(
                                        call_id=tool_id_obj,
                                        tool_name=tool_name_obj,
                                        arguments_json="{}",
                                    )
                                )
                        else:
                            pass
                    else:
                        pass
            else:
                pass
            index += 1

        return LLMResponse(
            text="\n".join(text_parts).strip(),
            tool_calls=tool_calls,
            error_code=ProviderErrorCode.NONE,
            error_message="",
        )
    else:
        return LLMResponse(
            text="",
            tool_calls=list(),
            error_code=ProviderErrorCode.PARSE_ERROR,
            error_message="Anthropic response payload does not contain a valid content list.",
        )



def parse_openai_compatible_payload(payload: dict[str, Any]) -> LLMResponse:
    """
    Parse an OpenAI-compatible chat-completions payload.

    :param payload: Provider payload.
    :returns: Parsed response.
    """
    choices_obj: Any = payload.get("choices", None)

    if isinstance(choices_obj, list) and (len(choices_obj) > 0):
        first_choice: Any = choices_obj[0]
        if isinstance(first_choice, dict):
            message_obj: Any = first_choice.get("message", None)
            if isinstance(message_obj, dict):
                content_obj: Any = message_obj.get("content", None)
                tool_calls_obj: Any = message_obj.get("tool_calls", None)
                assistant_text: str = ""
                parsed_tool_calls: list[ToolCall] = list()

                if isinstance(content_obj, str):
                    assistant_text = content_obj
                else:
                    assistant_text = ""

                if isinstance(tool_calls_obj, list):
                    index: int = 0
                    while index < len(tool_calls_obj):
                        tool_item: Any = tool_calls_obj[index]
                        if isinstance(tool_item, dict):
                            tool_id_obj: Any = tool_item.get("id", None)
                            function_obj: Any = tool_item.get("function", None)
                            if isinstance(tool_id_obj, str) and isinstance(function_obj, dict):
                                tool_name_obj: Any = function_obj.get("name", None)
                                tool_args_obj: Any = function_obj.get("arguments", None)
                                if isinstance(tool_name_obj, str):
                                    if isinstance(tool_args_obj, str):
                                        parsed_tool_calls.append(
                                            ToolCall(
                                                call_id=tool_id_obj,
                                                tool_name=tool_name_obj,
                                                arguments_json=tool_args_obj,
                                            )
                                        )
                                    else:
                                        parsed_tool_calls.append(
                                            ToolCall(
                                                call_id=tool_id_obj,
                                                tool_name=tool_name_obj,
                                                arguments_json="{}",
                                            )
                                        )
                                else:
                                    pass
                            else:
                                pass
                        else:
                            pass
                        index += 1

                return LLMResponse(
                    text=assistant_text,
                    tool_calls=parsed_tool_calls,
                    error_code=ProviderErrorCode.NONE,
                    error_message="",
                )
            else:
                return LLMResponse(
                    text="",
                    tool_calls=list(),
                    error_code=ProviderErrorCode.PARSE_ERROR,
                    error_message="OpenAI-compatible payload does not contain a valid message object.",
                )
        else:
            return LLMResponse(
                text="",
                tool_calls=list(),
                error_code=ProviderErrorCode.PARSE_ERROR,
                error_message="OpenAI-compatible payload first choice is invalid.",
            )
    else:
        return LLMResponse(
            text="",
            tool_calls=list(),
            error_code=ProviderErrorCode.PARSE_ERROR,
            error_message="OpenAI-compatible payload does not contain valid choices.",
        )



def parse_model_list_payload(payload: dict[str, Any]) -> ModelListResult:
    """
    Parse a provider model-list payload.

    :param payload: Provider payload.
    :returns: Parsed model-list result.
    """
    data_obj: Any = payload.get("data", None)
    model_names: list[str] = list()

    if isinstance(data_obj, list):
        index: int = 0

        # Extract model identifiers in provider order to keep the UI list stable.
        while index < len(data_obj):
            item_obj: Any = data_obj[index]
            if isinstance(item_obj, dict):
                model_id_obj: Any = item_obj.get("id", None)
                if isinstance(model_id_obj, str):
                    model_names.append(model_id_obj)
                else:
                    pass
            else:
                pass
            index += 1

        if len(model_names) > 0:
            return ModelListResult(
                success=True,
                model_names=model_names,
                error_message="",
            )
        else:
            return ModelListResult(
                success=False,
                model_names=list(),
                error_message="Provider returned a model list without string identifiers.",
            )
    else:
        return ModelListResult(
            success=False,
            model_names=list(),
            error_message="Provider model-list payload does not contain a valid data list.",
        )


def list_provider_models(config: ProviderConfig) -> ModelListResult:
    """
    Query the configured provider for the list of available models.

    :param config: Provider configuration.
    :returns: Model discovery result.
    """
    base_url: Optional[str] = config.base_url

    if config.provider_tpe == ProviderType.LOCAL_LLAMA_CPP:
        return list_local_llama_models(config)
    else:
        if base_url is None:
            return ModelListResult(
                success=False,
                model_names=list(),
                error_message="Provider base URL is not configured.",
            )
        else:
            http_client: HTTPClient = HTTPClient(config)
            url: str = f"{base_url.rstrip('/')}/models"
            ok_http: bool
            response_obj: dict[str, Any]
            http_error: str
            ok_http, response_obj, http_error = http_client.get_json(url)

            if ok_http:
                return parse_model_list_payload(response_obj)
            else:
                return ModelListResult(
                    success=False,
                    model_names=list(),
                    error_message=http_error,
                )


def build_provider(config: ProviderConfig) -> LLMProviderProtocol:
    """
    Build the selected provider.

    :param config: Provider configuration.
    :returns: Provider instance.
    """
    provider: LLMProviderProtocol

    if config.provider_tpe == ProviderType.OPENAI:
        provider = OpenAIProvider(config)
    else:
        if config.provider_tpe == ProviderType.ANTHROPIC:
            provider = AnthropicProvider(config)
        else:
            if config.provider_tpe == ProviderType.OPENAI_COMPATIBLE:
                provider = OpenAICompatibleProvider(config)
            else:
                if config.provider_tpe == ProviderType.LOCAL_LLAMA_CPP:
                    provider = LocalLlamaCppProvider(config)
                else:
                    provider = OpenAICompatibleProvider(config)

    return provider



def build_default_tool_registry() -> ToolRegistry:
    """
    Build a default registry with demo tools.

    :returns: Tool registry.
    """
    approval_policy: ApprovalPolicy = ApprovalPolicy(
        require_mutating=False,
        require_destructive=False,
    )
    registry: ToolRegistry = ToolRegistry(approval_policy=approval_policy)

    run_pf_schema: str = json.dumps(
        {
            "type": "object",
            "properties": {
                "case_id": {"type": "string"},
            },
            "required": ["case_id"],
            "additionalProperties": False,
        }
    )
    list_buses_schema: str = json.dumps(
        {
            "type": "object",
            "properties": {
                "kv_min": {"type": "number"},
            },
            "additionalProperties": False,
        }
    )
    patch_schema: str = json.dumps(
        {
            "type": "object",
            "properties": {
                "element_id": {"type": "string"},
                "patch": {"type": "object"},
            },
            "required": ["element_id", "patch"],
            "additionalProperties": False,
        }
    )

    registry.register(
        ToolSpec(
            name="run_power_flow",
            description="Run a power flow for a selected study case.",
            input_schema_json=run_pf_schema,
            risk=ToolRisk.COMPUTE,
            handler=RunPowerFlowTool(),
        )
    )
    registry.register(
        ToolSpec(
            name="list_buses",
            description="List buses, optionally filtered by minimum nominal voltage.",
            input_schema_json=list_buses_schema,
            risk=ToolRisk.READ_ONLY,
            handler=ListBusesTool(),
        )
    )
    registry.register(
        ToolSpec(
            name="apply_parameter_patch",
            description="Apply a parameter patch to a project element.",
            input_schema_json=patch_schema,
            risk=ToolRisk.MUTATING,
            handler=ApplyParameterPatchTool(),
        )
    )

    return registry
