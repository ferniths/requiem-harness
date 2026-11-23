"""Provider tests using mocked HTTP responses.

All tests use respx to mock httpx calls — no real API calls are made.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from requiem.providers.implementations.openai import OpenAIProvider
from requiem.providers.implementations.openrouter import OpenRouterProvider
from requiem.providers.implementations.router9 import Router9Provider
from requiem.providers.models import (
    ChatMessage,
    FinishReason,
    ProviderRequest,
    StreamEvent,
    ToolCallRequest,
    ToolDefinition,
)
from requiem.providers.registry import SUPPORTED_KINDS, create_provider


def _make_request(model: str = "gpt-4o-mini", content: str = "Hello") -> ProviderRequest:
    return ProviderRequest(
        model=model,
        messages=[
            ChatMessage(role="user", content=content),
        ],
        temperature=0.7,
        max_tokens=100,
    )


def _ok_response(
    content: str = "Hi there",
    model: str = "gpt-4o-mini",
    finish_reason: str = "stop",
    usage: dict | None = None,
) -> dict:
    data: dict[str, Any] = {
        "id": "chatcmpl-test",
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": finish_reason,
            }
        ],
    }
    if usage:
        data["usage"] = usage
    return data


class TestProviderRegistry:
    def test_supported_kinds(self):
        assert "openai" in SUPPORTED_KINDS
        assert "anthropic" in SUPPORTED_KINDS
        assert "openrouter" in SUPPORTED_KINDS
        assert "router9" in SUPPORTED_KINDS
        assert "custom" in SUPPORTED_KINDS

    def test_create_openai_provider(self):
        p = create_provider("openai", api_key="sk-test")
        assert p.name == "openai"
        assert p.display_name == "OpenAI / ChatGPT"

    def test_create_router9_provider(self):
        p = create_provider("router9", base_url="http://localhost:8080/v1", api_key="key")
        assert isinstance(p, Router9Provider)
        assert p.name == "router9"

    def test_create_openrouter_provider(self):
        p = create_provider("openrouter", api_key="sk-or-test")
        assert isinstance(p, OpenRouterProvider)
        assert p.name == "openrouter"

    def test_create_custom_provider(self):
        p = create_provider("custom", base_url="http://localhost:11434/v1", api_key="key")
        assert p.name == "openai"  # Falls back to OpenAICompatibleProvider

    def test_unknown_kind_raises(self):
        with pytest.raises(ValueError, match="Unknown provider kind"):
            create_provider("nonexistent")

    def test_custom_requires_base_url(self):
        with pytest.raises(ValueError, match="base_url"):
            create_provider("custom")


class TestOpenAIProvider:
    @respx.mock
    async def test_complete_success(self):
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=_ok_response())
        )
        provider = OpenAIProvider(api_key="sk-test")
        request = _make_request()
        resp = await provider.complete(request)
        assert resp.content == "Hi there"
        assert resp.finish_reason == FinishReason.STOP
        assert resp.provider == "openai"
        await provider.close()

    @respx.mock
    async def test_complete_auth_failure(self):
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(401, json={"error": "Invalid API key"})
        )
        provider = OpenAIProvider(api_key="sk-bad")
        from requiem.core.exceptions import ProviderAuthError

        with pytest.raises(ProviderAuthError):
            await provider.complete(_make_request())
        await provider.close()

    @respx.mock
    async def test_complete_rate_limit(self):
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(429, headers={"retry-after": "30"}, json={"error": "Rate limit"})
        )
        provider = OpenAIProvider(api_key="sk-test")
        from requiem.core.exceptions import ProviderRateLimitError

        with pytest.raises(ProviderRateLimitError):
            await provider.complete(_make_request())
        await provider.close()

    @respx.mock
    async def test_complete_with_usage(self):
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json=_ok_response(usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}),
            )
        )
        provider = OpenAIProvider(api_key="sk-test")
        resp = await provider.complete(_make_request())
        assert resp.usage.input_tokens == 10
        assert resp.usage.output_tokens == 20
        assert resp.usage.total_tokens == 30
        await provider.close()

    @respx.mock
    async def test_list_models(self):
        respx.get("https://api.openai.com/v1/models").mock(
            return_value=httpx.Response(
                200, json={"data": [{"id": "gpt-4o"}, {"id": "gpt-4o-mini"}]}
            )
        )
        provider = OpenAIProvider(api_key="sk-test")
        models = await provider.list_models()
        assert models == ["gpt-4o", "gpt-4o-mini"]
        await provider.close()

    @respx.mock
    async def test_validate_connection_ok(self):
        respx.get("https://api.openai.com/v1/models").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        provider = OpenAIProvider(api_key="sk-test")
        ok, msg = await provider.validate_connection()
        assert ok is True
        await provider.close()

    @respx.mock
    async def test_validate_connection_auth_fail(self):
        respx.get("https://api.openai.com/v1/models").mock(
            return_value=httpx.Response(401, json={"error": "Bad key"})
        )
        provider = OpenAIProvider(api_key="sk-bad")
        ok, msg = await provider.validate_connection()
        assert ok is False
        assert "Authentication" in msg or "Check" in msg
        await provider.close()


class TestRouter9Provider:
    @respx.mock
    async def test_router9_with_custom_base_url(self):
        respx.post("http://my-router9.local:8080/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=_ok_response(content="Router9 response"))
        )
        provider = Router9Provider(base_url="http://my-router9.local:8080/v1", api_key="r9-key")
        resp = await provider.complete(_make_request())
        assert resp.content == "Router9 response"
        assert resp.provider == "router9"
        await provider.close()

    @respx.mock
    async def test_router9_custom_headers(self):
        # Capture the request to verify custom headers are sent
        captured = {}

        def capture_request(request: httpx.Request) -> httpx.Response:
            captured["headers"] = dict(request.headers)
            return httpx.Response(200, json=_ok_response())

        respx.post("http://my-router9.local/v1/chat/completions").mock(side_effect=capture_request)
        provider = Router9Provider(
            base_url="http://my-router9.local/v1",
            api_key="key",
            custom_headers={"X-Instance": "requiem"},
        )
        await provider.complete(_make_request())
        # httpx may lowercase header names in the dict conversion
        hdrs = {k.lower(): v for k, v in captured["headers"].items()}
        assert hdrs.get("x-instance") == "requiem"
        assert hdrs.get("authorization") is not None
        await provider.close()

    @respx.mock
    async def test_router9_list_models_explicit(self):
        provider = Router9Provider(
            base_url="http://localhost:8080/v1",
            api_key="key",
            model_list=["gpt-4o", "claude-sonnet-4"],
        )
        models = await provider.list_models()
        assert models == ["gpt-4o", "claude-sonnet-4"]
        await provider.close()

    @respx.mock
    async def test_router9_list_models_fallback_when_endpoint_missing(self):
        # /models returns 404 → fall back to explicit list or None
        respx.get("http://localhost:8080/v1/models").mock(return_value=httpx.Response(404))
        provider = Router9Provider(
            base_url="http://localhost:8080/v1",
            api_key="key",
            model_list=["my-model"],
        )
        models = await provider.list_models()
        assert models == ["my-model"]
        await provider.close()

    @respx.mock
    async def test_router9_validate_by_probe(self):
        # /models returns 404, so validation falls back to a completion probe
        respx.get("http://localhost:8080/v1/models").mock(return_value=httpx.Response(404))
        respx.post("http://localhost:8080/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=_ok_response(content="ok"))
        )
        provider = Router9Provider(base_url="http://localhost:8080/v1", api_key="key")
        ok, msg = await provider.validate_connection(model="gpt-4o-mini")
        assert ok is True
        assert "probe" in msg.lower() or "OK" in msg
        await provider.close()


class TestOpenRouterProvider:
    @respx.mock
    async def test_openrouter_complete(self):
        respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=_ok_response(content="OpenRouter works", model="openai/gpt-4o-mini"))
        )
        provider = OpenRouterProvider(api_key="sk-or-test")
        resp = await provider.complete(_make_request(model="openai/gpt-4o-mini"))
        assert resp.content == "OpenRouter works"
        assert resp.provider == "openrouter"
        await provider.close()

    @respx.mock
    async def test_openrouter_headers(self):
        captured = {}

        def capture(request: httpx.Request) -> httpx.Response:
            captured["headers"] = dict(request.headers)
            return httpx.Response(200, json=_ok_response())

        respx.post("https://openrouter.ai/api/v1/chat/completions").mock(side_effect=capture)
        provider = OpenRouterProvider(api_key="sk-or-test")
        await provider.complete(_make_request())
        hdrs = {k.lower(): v for k, v in captured["headers"].items()}
        assert hdrs.get("http-referer") == "https://github.com/requiem/requiem"
        assert hdrs.get("x-title") == "REQUIEM"
        await provider.close()


class TestProviderModels:
    def test_tool_definition(self):
        td = ToolDefinition(name="read_file", description="Read a file", parameters={"type": "object"})
        assert td.name == "read_file"
        assert td.parameters == {"type": "object"}

    def test_chat_message_to_provider_dict(self):
        msg = ChatMessage(role="user", content="Hello")
        d = msg.to_provider_dict()
        assert d["role"] == "user"
        assert d["content"] == "Hello"

    def test_tool_call_message(self):
        msg = ChatMessage(
            role="assistant",
            tool_calls=[ToolCallRequest(id="call-1", name="read_file", arguments={"path": "test.py"})],
        )
        d = msg.to_provider_dict()
        assert "tool_calls" in d
        assert d["tool_calls"][0]["function"]["name"] == "read_file"

    def test_stream_event_content_delta(self):
        event = StreamEvent(type="content_delta", content="Hello")
        assert event.content == "Hello"

    def test_finish_reason_mapping(self):
        assert FinishReason.from_provider("stop") == FinishReason.STOP
        assert FinishReason.from_provider("end_turn") == FinishReason.STOP  # Anthropic
        assert FinishReason.from_provider("tool_use") == FinishReason.TOOL_CALLS  # Anthropic
        assert FinishReason.from_provider("unknown_val") == FinishReason.UNKNOWN
        assert FinishReason.from_provider(None) == FinishReason.UNKNOWN
