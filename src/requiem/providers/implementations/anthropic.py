import json
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


class AnthropicProvider(BaseProvider):
    """Anthropic Messages API provider."""

    def __init__(
        self,
        *,
        base_url: str = "https://api.anthropic.com",
        api_key: str = "",
        timeout_s: float = 60.0,
        model: str = "claude-sonnet-4-20250514",
        custom_headers: dict[str, str] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout_s
        self._model = model
        self._custom_headers = custom_headers or {}
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def display_name(self) -> str:
        return "Anthropic / Claude"

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            streaming=True,
            tool_calls=True,
            model_discovery=False,
            temperature=True,
            stop_sequences=True,
        )

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._timeout),
                headers=self._headers(),
            )
        return self._client

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {
            "x_api_key": self._api_key,
            "anthropic_version": "2023-06-01",
            "content_type": "application/json",
        }
        h.update(self._custom_headers)
        return h

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _build_payload(
        self, request: ProviderRequest, *, stream: bool = False
    ) -> dict[str, object]:
        system_parts = [m.content for m in request.messages if m.role == "system"]
        conv = [m for m in request.messages if m.role != "system"]
        messages: list[dict[str, object]] = []
        for m in conv:
            entry: dict[str, object] = {"role": m.role, "content": m.content}
            if m.role == "assistant" and m.tool_calls:
                entry["tool_calls"] = [
                    {
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    }
                    for tc in m.tool_calls
                ]
            if m.role == "tool":
                entry = {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": m.tool_call_id,
                            "content": m.content,
                        }
                    ],
                }
            messages.append(entry)
        payload: dict[str, object] = {
            "model": request.model or self._model,
            "messages": messages,
            "stream": stream,
        }
        if system_parts:
            payload["system"] = "".join(system_parts)
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens:
            payload["max_tokens"] = request.max_tokens
        elif request.max_tokens is None:
            payload["max_tokens"] = 4096
        if request.stop:
            payload["stop_sequences"] = request.stop
        if request.tools:
            payload["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.parameters,
                }
                for t in request.tools
            ]
        if request.tool_choice:
            payload["tool_choice"] = request.tool_choice
        if request.metadata:
            payload.update(request.metadata)
        return payload

    def _parse_response(
        self, data: dict[str, Any], request: ProviderRequest
    ) -> ProviderResponse:
        content: list[str] = []
        tool_calls: list[ToolCallRequest] = []
        content_data = data.get("content")
        for block in (content_data if isinstance(content_data, list) else []):
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                content.append(str(block.get("text", "")))
            elif block.get("type") == "tool_use":
                tool_calls.append(
                    ToolCallRequest(
                        id=str(block.get("id", "")),
                        name=str(block.get("name", "")),
                        arguments=(block.get("input") if isinstance(block.get("input"), dict) else {}) or {},
                    )
                )
        usage_data = data.get("usage")
        usage = usage_data if isinstance(usage_data, dict) else {}
        input_tokens = int(usage.get("input_tokens", 0))
        output_tokens = int(usage.get("output_tokens", 0))
        token_usage = TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            provider="anthropic",
            model=str(data.get("model", request.model)),
        )
        return ProviderResponse(
            content="".join(content),
            tool_calls=tool_calls,
            finish_reason=FinishReason.from_provider(
                str(data.get("stop_reason", ""))
            ),
            usage=token_usage,
            provider="anthropic",
            model=str(data.get("model", request.model)),
            request_id=str(data.get("id", "")),
        )

    async def complete(
        self, request: ProviderRequest, *, api_key: str | None = None
    ) -> ProviderResponse:
        if api_key:
            self._api_key = api_key
        client = await self._get_client()
        payload = self._build_payload(request)
        try:
            resp = await client.post("/v1/messages", json=payload)
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
        return self._parse_response(resp.json(), request)

    async def stream(
        self, request: ProviderRequest, *, api_key: str | None = None
    ) -> AsyncIterator[StreamEvent]:
        if api_key:
            self._api_key = api_key
        client = await self._get_client()
        payload = self._build_payload(request, stream=True)
        payload["stream"] = True
        try:
            async with client.stream(
                "POST", "/v1/messages", json=payload
            ) as resp:
                if resp.status_code >= 400:
                    body = await resp.aread()
                    raise classify_http_error(
                        resp.status_code, body.decode(errors="replace"), provider=self.name
                    )
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data:"):
                        continue
                    payload_s = line[5:].strip()
                    if not payload_s:
                        continue
                    try:
                        ev = json.loads(payload_s)
                    except json.JSONDecodeError:
                        continue
                    etype = ev.get("type")
                    if etype == "content_block_delta":
                        d = ev.get("delta") or {}
                        if isinstance(d, dict):
                            if d.get("type") == "text_delta":
                                yield StreamEvent(
                                    type="content_delta", content=str(d.get("text", ""))
                                )
                            elif d.get("type") == "input_json_delta":
                                yield StreamEvent(
                                    type="tool_call_delta",
                                    tool_call_index=0,
                                    content=str(d.get("partial_json", "")),
                                )
                    elif etype == "message_delta":
                        delta = ev.get("delta")
                        if isinstance(delta, dict) and delta.get("stop_reason"):
                            yield StreamEvent(
                                type="finish",
                                finish_reason=FinishReason.from_provider(
                                    str(delta["stop_reason"])
                                ),
                            )
                    elif etype == "error":
                        yield StreamEvent(type="error", error=str(ev.get("error")))
                        return
                    elif etype == "message_stop":
                        break
        except httpx.ConnectError as e:
            raise classify_connect_error(e, provider=self.name) from e
        except httpx.ReadError as e:
            raise classify_read_error(e, provider=self.name) from e
        except httpx.TimeoutException:
            raise classify_timeout(self._timeout) from None

    async def list_models(
        self, *, api_key: str | None = None
    ) -> list[str] | None:
        if api_key:
            self._api_key = api_key
        return None

    async def validate_connection(
        self, *, api_key: str | None = None, model: str | None = None
    ) -> tuple[bool, str]:
        if api_key:
            self._api_key = api_key
        client = await self._get_client()
        try:
            resp = await client.post(
                "/v1/messages",
                json={
                    "model": model or self._model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 8,
                },
            )
            if resp.status_code in (401, 403):
                return False, "Authentication failed. Check your API key."
            if resp.status_code >= 400:
                return False, f"Endpoint returned HTTP {resp.status_code}"
            return True, "Connection OK"
        except httpx.ConnectError:
            return False, f"Cannot reach {self._base_url}"
        except httpx.TimeoutException:
            return False, f"Connection timed out after {self._timeout}s"
