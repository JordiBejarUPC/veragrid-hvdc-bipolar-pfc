# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import sys
from typing import Any, Optional

from VeraGrid.AI.mcp_protocol import (
    chat_message_from_json,
    llm_response_to_json,
    model_list_result_to_json,
    provider_config_from_json,
    read_mcp_message,
    tool_spec_from_json,
    write_mcp_message,
)
from VeraGrid.AI.providers import build_provider
from VeraGrid.AI.providers import list_provider_models
from VeraGrid.AI.types_and_tools import (
    ChatMessage,
    LLMResponse,
    ModelListResult,
    ProviderConfig,
    ToolSpec,
)


class VeraGridAiMcpServer:
    """
    Minimal MCP stdio server for VeraGrid AI completions.
    """

    __slots__ = (
        "_cached_provider",
        "_cached_signature",
    )

    def __init__(self) -> None:
        """
        Build the server with no loaded model/provider.
        """
        self._cached_provider: Any = None
        self._cached_signature: str = ""

    def _build_provider_signature(self, config: ProviderConfig) -> str:
        """
        Build a cache key for provider reuse.

        :param config: Provider configuration.
        :returns: Cache signature.
        """
        api_key_text: str = "" if config.api_key is None else config.api_key
        base_url_text: str = "" if config.base_url is None else config.base_url
        return (
            f"{config.provider_tpe.value}|{config.model_name}|{api_key_text}|"
            f"{base_url_text}|{config.timeout_s}"
        )

    def _get_provider(self, config: ProviderConfig) -> Any:
        """
        Reuse the provider for repeated calls with the same backend settings.

        :param config: Provider configuration.
        :returns: Provider instance.
        """
        signature: str = self._build_provider_signature(config)

        # Provider creation stays lazy so VeraGrid startup only starts a cheap idle process.
        if self._cached_signature == signature:
            if self._cached_provider is None:
                self._cached_provider = build_provider(config)
            else:
                pass
        else:
            self._cached_provider = build_provider(config)
            self._cached_signature = signature

        return self._cached_provider

    def handle_request(self, request: dict[str, Any]) -> Optional[dict[str, Any]]:
        """
        Handle one JSON-RPC request.

        :param request: JSON-RPC request object.
        :returns: JSON-RPC response object, or None for notifications.
        """
        request_id: object = request.get("id", None)
        method_obj: object = request.get("method", "")
        params_obj: object = request.get("params", dict())

        if request_id is None:
            return None
        else:
            pass

        if isinstance(method_obj, str):
            method: str = method_obj
        else:
            method = ""

        if isinstance(params_obj, dict):
            params: dict[str, Any] = params_obj
        else:
            params = dict()

        try:
            result: Any = self.dispatch_method(method=method, params=params)
            return self.build_result_response(request_id=request_id, result=result)
        except Exception as exc:
            return self.build_error_response(request_id=request_id, message=str(exc))

    def dispatch_method(self, method: str, params: dict[str, Any]) -> Any:
        """
        Dispatch a supported MCP/JSON-RPC method.

        :param method: Method name.
        :param params: Request parameters.
        :returns: Method result.
        """
        if method == "initialize":
            return self.handle_initialize()
        else:
            if method == "tools/list":
                return self.handle_tools_list()
            else:
                if method == "llm/complete":
                    return self.handle_llm_complete(params)
                else:
                    if method == "llm/list_models":
                        return self.handle_llm_list_models(params)
                    else:
                        if method == "shutdown":
                            return dict()
                        else:
                            raise ValueError(f"Unsupported MCP method: {method}")

    def handle_initialize(self) -> dict[str, Any]:
        """
        Return the MCP initialize payload.

        :returns: Initialize result.
        """
        server_info: dict[str, Any] = dict()
        capabilities: dict[str, Any] = dict()
        tools: dict[str, Any] = dict()
        result: dict[str, Any] = dict()

        server_info["name"] = "veragrid-ai"
        server_info["version"] = "0.1"
        capabilities["tools"] = tools
        result["protocolVersion"] = "2024-11-05"
        result["serverInfo"] = server_info
        result["capabilities"] = capabilities
        return result

    def handle_tools_list(self) -> dict[str, Any]:
        """
        Return an empty MCP tool list because VeraGrid executes live tools in-process.

        :returns: MCP tools/list result.
        """
        result: dict[str, Any] = dict()
        result["tools"] = list()
        return result

    def handle_llm_complete(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Run one provider completion.

        :param params: Completion parameters.
        :returns: Serialized LLM response.
        """
        config_obj: object = params.get("provider_config", dict())
        messages_obj: object = params.get("messages", list())
        tools_obj: object = params.get("tool_specs", list())
        messages: list[ChatMessage] = list()
        tool_specs: list[ToolSpec] = list()
        index: int = 0

        if isinstance(config_obj, dict):
            config: ProviderConfig = provider_config_from_json(config_obj)
        else:
            config = provider_config_from_json(dict())

        if isinstance(messages_obj, list):
            while index < len(messages_obj):
                message_obj: object = messages_obj[index]
                if isinstance(message_obj, dict):
                    messages.append(chat_message_from_json(message_obj))
                else:
                    pass
                index += 1
        else:
            pass

        if isinstance(tools_obj, list):
            index = 0
            while index < len(tools_obj):
                tool_obj: object = tools_obj[index]
                if isinstance(tool_obj, dict):
                    tool_specs.append(tool_spec_from_json(tool_obj))
                else:
                    pass
                index += 1
        else:
            pass

        provider: Any = self._get_provider(config)
        response: LLMResponse = provider.complete(
            system_prompt=str(params.get("system_prompt", "")),
            messages=messages,
            tool_specs=tool_specs,
        )
        return llm_response_to_json(response)

    def handle_llm_list_models(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Query models through the selected provider.

        :param params: Model-list parameters.
        :returns: Serialized model-list result.
        """
        config_obj: object = params.get("provider_config", dict())

        if isinstance(config_obj, dict):
            config: ProviderConfig = provider_config_from_json(config_obj)
        else:
            config = provider_config_from_json(dict())

        result: ModelListResult = list_provider_models(config)
        return model_list_result_to_json(result)

    def build_result_response(self, request_id: object, result: Any) -> dict[str, Any]:
        """
        Build a successful JSON-RPC response.

        :param request_id: JSON-RPC request id.
        :param result: Method result.
        :returns: JSON-RPC response.
        """
        response: dict[str, Any] = dict()
        response["jsonrpc"] = "2.0"
        response["id"] = request_id
        response["result"] = result
        return response

    def build_error_response(self, request_id: object, message: str) -> dict[str, Any]:
        """
        Build an error JSON-RPC response.

        :param request_id: JSON-RPC request id.
        :param message: Error message.
        :returns: JSON-RPC response.
        """
        error_obj: dict[str, Any] = dict()
        response: dict[str, Any] = dict()
        error_obj["code"] = -32000
        error_obj["message"] = message
        response["jsonrpc"] = "2.0"
        response["id"] = request_id
        response["error"] = error_obj
        return response

    def serve(self) -> int:
        """
        Serve MCP requests until stdin closes.

        :returns: Process exit code.
        """
        while True:
            request: Optional[dict[str, Any]] = read_mcp_message(sys.stdin.buffer)
            if request is None:
                return 0
            else:
                response: Optional[dict[str, Any]] = self.handle_request(request)
                if response is None:
                    pass
                else:
                    write_mcp_message(sys.stdout.buffer, response)


def run_server() -> int:
    """
    Run the VeraGrid AI MCP server.

    :returns: Process exit code.
    """
    server: VeraGridAiMcpServer = VeraGridAiMcpServer()
    return server.serve()


if __name__ == "__main__":
    raise SystemExit(run_server())
