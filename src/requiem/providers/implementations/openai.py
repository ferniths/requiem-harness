"""OpenAI-compatible provider (also used as base for OpenRouter and 9Router).

This implementation speaks the OpenAI Chat Completions wire format.
Subclasses override `default_base_url`, `display_name`, and
`_build_headers` for provider-specific behavior.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from requiem.providers.base import BaseProvider
from requiem.providers.errors import (
    classify_connect_error,
    classify_http_error,
    classify_read_error,
    classify_timeout,
)
from requiem.providers.models import (
    FinishReason,
    ProviderCapabilities,
    ProviderRequest,
    ProviderResponse,
    StreamEvent,
    TokenUsage,
    ToolCallRequest,
)
from requiem.providers.sse import parse_sse_stream

logger = logging.getLogger("requiem.providers.openai")


class OpenAICompatibleProvider(BaseProvider):
    """Base class for all OpenAI-compatible endpoints."""

    def __init__(
        self,
        *,
        base_url: str = "https://api.openai.com/v1",
        api_key: str = "",
        timeout_s: float = 60.0,
        custom_headers: dict[str, str] | None = None,
        compat: dict[str, str] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout_s
        self._custom_headers = custom_headers or {}
        self._compat = compat or {}
        self._client: httpx.AsyncClient | None = None

    # -- BaseProvider overrides ---------------------------------------------

    @property
    def name(self) -> str:
        return "openai"

    @property
    def display_name(self) -> str:
        return "OpenAI / ChatGPT"

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            streaming=True,
            tool_calls=True,
            model_discovery=True,
            temperature=True,
            stop_sequences=True,
        )

    # -- HTTP client lifecycle ------------------------------------------------

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._timeout),
                headers=self._build_headers(),
            )
        return self._client

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            **self._custom_headers,
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # -- Provider interface ----------------------------------------------------

    async def complete(
        self,
        request: ProviderRequest,
        *,
        api_key: str | None = None,
    ) -> ProviderResponse:
        if api_key:
            self._api_key = api_key
        client = await self._get_client()
        payload = self._build_payload(request)
        try:
            resp = await client.post("/chat/completions", json=payload)
        except httpx.ConnectError as e:
            raise classify_connect_error(e, provider=self.name) from e
        except httpx.ReadError as e:
            raise classify_read_error(e, provider=self.name) from e
        except httpx.TimeoutException as e:
            raise classify_timeout(self._timeout) from e

        if resp.status_code >= 400:
            raise classify_http_error(
                resp.status_code, resp.text, provider=self.name, headers=dict(resp.headers)
            )

        data = resp.json()
        return self._parse_response(data, request)

    async def stream(
        self,
        request: ProviderRequest,
        *,
        api_key: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        if api_key:
            self._api_key = api_key
        client = await self._get_client()
        payload = self._build_payload(request, stream=True)
        try:
            async with client.stream("POST", "/chat/completions", json=payload) as resp:
                if resp.status_code >= 400:
                    body = await resp.aread()
                    raise classify_http_error(
                        resp.status_code, body.decode(errors="replace"), provider=self.name
                    )
                async for event in self._parse_sse(resp, request, request.model):
                    yield event
        except httpx.ConnectError as e:
            raise classify_connect_error(e, provider=self.name) from e
        except httpx.ReadError as e:
            raise classify_read_error(e, provider=self.name) from e
        except httpx.TimeoutException:
            raise classify_timeout(self._timeout) from None

    async def list_models(
        self,
        *,
        api_key: str | None = None,
    ) -> list[str] | None:
        if api_key:
            self._api_key = api_key
        client = await self._get_client()
        try:
            resp = await client.get("/models")
            if resp.status_code >= 400:
                return None
            data = resp.json()
            return [m.get("id", "") for m in data.get("data", []) if m.get("id")]
        except Exception:
            logger.debug("Model discovery failed for %s", self.name, exc_info=True)
            return None

    async def validate_connection(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
    ) -> tuple[bool, str]:
        if api_key:
            self._api_key = api_key
        client = await self._get_client()
        try:
            resp = await client.get("/models")
            if resp.status_code in (401, 403):
                return False, "Authentication failed. Check your API key."
            if resp.status_code >= 400:
                return False, f"Endpoint returned HTTP {resp.status_code}"
            # Endpoint reachable and authenticated
            if model:
                models = await self.list_models()
                if models and model not in models:
                    return True, f"Connected. Model '{model}' not found in provider's model list."
            return True, "Connection OK"
        except httpx.ConnectError:
            return False, f"Cannot reach {self._base_url}. Check the URL and your network."
        except httpx.TimeoutException:
            return False, f"Connection timed out after {self._timeout}s"

    # -- Internal helpers ------------------------------------------------------

    def _build_payload(self, request: ProviderRequest, *, stream: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": [m.to_provider_dict() for m in request.messages],
            "stream": stream,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.stop:
            payload["stop"] = request.stop
        if request.tools:
            payload["tools"] = [
                {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
                for t in request.tools
            ]
            if request.tool_choice:
                payload["tool_choice"] = request.tool_choice
        # Provider-specific metadata passthrough
        payload.update(request.metadata)
        return payload

    def _parse_response(self, data: dict[str, Any], request: ProviderRequest) -> ProviderResponse:
        choice = data.get("choices", [{}])[0]
        msg = choice.get("message", {})
        usage_data = data.get("usage")

        tool_calls: list[ToolCallRequest] = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function", {})
            args_str = fn.get("arguments", "{}")
            try:
                args = json.loads(args_str) if isinstance(args_str, str) else args_str
            except json.JSONDecodeError:
                args = {"raw": args_str}
            tool_calls.append(ToolCallRequest(id=tc.get("id", ""), name=fn.get("name", ""), arguments=args))

        usage = TokenUsage(
            input_tokens=usage_data.get("prompt_tokens", 0) if usage_data else 0,
            output_tokens=usage_data.get("completion_tokens", 0) if usage_data else 0,
            total_tokens=usage_data.get("total_tokens", 0) if usage_data else 0,
            cached_tokens=(usage_data.get("prompt_tokens_details") or {}).get(
                "cached_tokens", 0
            )
            if usage_data
            else 0,
            provider=self.name,
            model=data.get("model", request.model),
        )

        return ProviderResponse(
            content=msg.get("content") or "",
            tool_calls=tool_calls,
            finish_reason=FinishReason.from_provider(choice.get("finish_reason")),
            usage=usage,
            provider=self.name,
            model=data.get("model", request.model),
            request_id=data.get("id", ""),
        )

    async def _parse_sse(
        self,
        resp: httpx.Response,
        request: ProviderRequest,
        model: str,
    ) -> AsyncIterator[StreamEvent]:
        """Parse an OpenAI SSE stream, yielding normalized StreamEvents."""
        async for event in parse_sse_stream(resp, model=model, provider=self.name):
            yield event


# ------------------------------------------------------------------
# OpenAI-specific subclass
# ------------------------------------------------------------------

class OpenAIProvider(OpenAICompatibleProvider):
    @property
    def name(self) -> str:
        return "openai"

    @property
    def display_name(self) -> str:
        return "OpenAI / ChatGPT"
