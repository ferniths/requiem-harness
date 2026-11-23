"""Streaming utility — wraps provider stream generators for the TUI.

The TUI consumes these generators and renders content_delta events as
they arrive, updating the live message in place.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from requiem.providers.models import FinishReason, ProviderResponse, StreamEvent, TokenUsage

logger = logging.getLogger("requiem.providers.streaming")


async def collect_stream(events: AsyncIterator[StreamEvent]) -> ProviderResponse:
    """Consume a stream and assemble a complete ProviderResponse.

    Used by the agent engine (which needs the full response to decide
    on tool calls) and as a test helper.
    """
    content_parts: list[str] = []
    tool_calls: list[StreamEvent] = []
    usage: TokenUsage | None = None
    finish_reason: FinishReason | None = None
    error: str | None = None
    provider = ""
    _model = ""

    async for event in events:
        if event.type == "content_delta":
            content_parts.append(event.content)
        elif event.type == "tool_call_delta":
            tool_calls.append(event)
        elif event.type == "usage":
            usage = event.usage
        elif event.type == "finish":
            finish_reason = event.finish_reason
            provider = provider  # will be set by caller
        elif event.type == "error":
            error = event.error

    from requiem.providers.models import ToolCallRequest

    # Assemble tool calls from deltas
    tc_map: dict[int, ToolCallRequest] = {}
    for tc_event in tool_calls:
        if tc_event.tool_call is None:
            continue
        idx = tc_event.tool_call_index
        if idx not in tc_map:
            tc_map[idx] = tc_event.tool_call
        # For argument streaming, the last event for a given index has the full args
        # (providers send full args in the final chunk)

    tool_call_list = list(tc_map.values()) if tc_map else []

    return ProviderResponse(
        content="".join(content_parts),
        tool_calls=tool_call_list,
        finish_reason=finish_reason or FinishReason.UNKNOWN,
        usage=usage or TokenUsage(),
        error=error,
    )


async def stream_to_log(events: AsyncIterator[StreamEvent]) -> ProviderResponse:
    """Debug helper: log each event as it arrives, then collect."""
    import time

    start = time.monotonic()
    event_count = 0

    collected = []

    async for event in events:
        event_count += 1
        if event.type == "content_delta":
            logger.debug("STREAM[%d] content_delta: %r", event_count, event.content[:80])
        elif event.type == "tool_call_delta":
            logger.debug("STREAM[%d] tool_call_delta: %s", event_count, event.tool_call)
        elif event.type == "usage":
            logger.debug("STREAM[%d] usage: %s", event_count, event.usage)
        elif event.type == "finish":
            logger.debug("STREAM[%d] finish: %s", event_count, event.finish_reason)
        elif event.type == "error":
            logger.warning("STREAM error: %s", event.error)

        collected.append(event)
    elapsed = time.monotonic() - start
    logger.debug("STREAM completed %d events in %.3fs", event_count, elapsed)

    # Now collect from the collected events
    content_parts: list[str] = []
    tool_calls = []
    usage = None
    finish_reason = None
    error = None

    for event in collected:
        if event.type == "content_delta":
            content_parts.append(event.content)
        elif event.type == "tool_call_delta":
            tool_calls.append(event)
        elif event.type == "usage":
            usage = event.usage
        elif event.type == "finish":
            finish_reason = event.finish_reason
        elif event.type == "error":
            error = event.error

    from requiem.providers.models import TokenUsage, ToolCallRequest

    tc_map: dict[int, ToolCallRequest] = {}
    for tc_event in tool_calls:
        if tc_event.tool_call is None:
            continue
        idx = tc_event.tool_call_index
        tc_map[idx] = tc_event.tool_call

    return ProviderResponse(
        content="".join(content_parts),
        tool_calls=list(tc_map.values()),
        finish_reason=finish_reason or FinishReason.UNKNOWN,
        usage=usage or TokenUsage(),
        error=error,
    )
