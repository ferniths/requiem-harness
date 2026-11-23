"""Unified provider request and response models.

All providers normalize into these types.  The rest of the application
(agent engine, TUI) never touches provider-specific wire formats.
"""

from __future__ import annotations

import enum
from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ToolDefinition(BaseModel):
    """A tool that the model may call."""

    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict, description="JSON Schema for the tool's input.")


class ToolCallRequest(BaseModel):
    """A tool invocation requested by the model."""

    id: str
    name: str
    arguments: dict[str, Any]


class ChatMessage(BaseModel):
    """A single message in the conversation."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""
    tool_calls: list[ToolCallRequest] = Field(default_factory=list)
    tool_call_id: str | None = None  # set when role == "tool"

    def to_provider_dict(self) -> dict[str, Any]:
        """Convert to provider-agnostic dict for serialization."""
        d: dict[str, Any] = {"role": self.role}
        if self.content:
            d["content"] = self.content
        if self.tool_calls:
            d["tool_calls"] = [
                {"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": _json(tc.arguments)}}
                for tc in self.tool_calls
            ]
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        return d


def _json(obj: Any) -> str:
    import json

    return json.dumps(obj)


class ProviderRequest(BaseModel):
    """Normalized request sent to any provider."""

    model: str
    messages: list[ChatMessage] = Field(default_factory=list)
    tools: list[ToolDefinition] = Field(default_factory=list)
    temperature: float | None = None
    max_tokens: int | None = None
    stop: list[str] | None = None
    stream: bool = False
    # Provider-specific passthrough (e.g. OpenRouter provider routing, 9Router extras)
    metadata: dict[str, Any] = Field(default_factory=dict)
    # OpenAI-compatible: tool_choice
    tool_choice: str | dict[str, Any] | None = None

    @property
    def system_instructions(self) -> str:
        return self.messages[0].content if self.messages and self.messages[0].role == "system" else ""


class TokenUsage(BaseModel):
    """Token accounting for a single request."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0
    provider: str = ""
    model: str = ""
    # Optional cost tracking
    input_cost: float | None = None
    output_cost: float | None = None
    total_cost: float | None = None

    @property
    def has_cost(self) -> bool:
        return self.input_cost is not None or self.output_cost is not None


class FinishReason(enum.Enum):
    STOP = "stop"
    LENGTH = "length"
    TOOL_CALLS = "tool_calls"
    CONTENT_FILTER = "content_filter"
    ERROR = "error"
    UNKNOWN = "unknown"

    @classmethod
    def from_provider(cls, value: str | None) -> FinishReason:
        if not value:
            return cls.UNKNOWN
        mapping: dict[str, FinishReason] = {
            "stop": cls.STOP,
            "end_turn": cls.STOP,  # Anthropic
            "length": cls.LENGTH,
            "tool_calls": cls.TOOL_CALLS,
            "tool_use": cls.TOOL_CALLS,  # Anthropic
            "content_filter": cls.CONTENT_FILTER,
        }
        return mapping.get(value, cls.UNKNOWN)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class ProviderResponse(BaseModel):
    """Normalized response from any provider."""

    content: str = ""
    tool_calls: list[ToolCallRequest] = Field(default_factory=list)
    finish_reason: FinishReason = FinishReason.UNKNOWN
    usage: TokenUsage = Field(default_factory=TokenUsage)
    provider: str = ""
    model: str = ""
    request_id: str = ""
    error: str | None = None

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0

    @property
    def is_error(self) -> bool:
        return self.error is not None


# ---------------------------------------------------------------------------
# Streaming events
# ---------------------------------------------------------------------------

class StreamEvent(BaseModel):
    """A single normalized streaming event.

    The TUI and agent engine consume these; they never see
    provider-specific SSE chunk formats.
    """

    type: Literal[
        "content_delta",  # incremental text
        "tool_call_delta",  # incremental tool call arguments
        "usage",  # final token usage
        "finish",  # stream complete
        "error",  # stream error
    ]
    content: str = ""
    tool_call: ToolCallRequest | None = None
    usage: TokenUsage | None = None
    finish_reason: FinishReason | None = None
    error: str | None = None
    # For tool_call_delta: which tool call index this delta belongs to
    tool_call_index: int = 0


class ProviderCapabilities(BaseModel):
    """What a provider can do."""

    streaming: bool = True
    tool_calls: bool = False
    model_discovery: bool = False
    max_context_tokens: int | None = None
    temperature: bool = True
    stop_sequences: bool = True
