"""Core event bus for intra-app communication.

Provides a lightweight pub/sub mechanism so subsystems can communicate
without direct imports.  The TUI subscribes to provider and workflow
events; the workflow engine emits them; the agent layer emits
lifecycle events.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger("requiem.core.events")


class Event:
    """A single application event."""

    def __init__(self, type_: str, data: dict[str, Any] | None = None, source: str = "") -> None:
        self.type = type_
        self.data = data or {}
        self.source = source

    def __repr__(self) -> str:
        return f"Event({self.type!r}, source={self.source!r})"


# Event type constants
class EventType:
    PROVIDER_REQUEST = "provider.request"
    PROVIDER_RESPONSE = "provider.response"
    PROVIDER_ERROR = "provider.error"
    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_FAILED = "workflow.failed"
    WORKFLOW_CANCELLED = "workflow.cancelled"
    TASK_STATUS_CHANGED = "task.status_changed"
    AGENT_STARTED = "agent.started"
    AGENT_COMPLETED = "agent.completed"
    AGENT_FAILED = "agent.failed"
    AGENT_OUTPUT = "agent.output"
    TOOL_EXECUTED = "tool.executed"
    TOOL_APPROVAL_REQUIRED = "tool.approval_required"
    APPROVAL_GRANTED = "approval.granted"
    APPROVAL_DENIED = "approval.denied"
    LOG_ENTRY = "log.entry"
    CHECKPOINT_SAVED = "checkpoint.saved"
    THEME_CHANGED = "theme.changed"


EventCallback = Callable[[Event], None]
AsyncEventCallback = Callable[[Event], Awaitable[None]]


class EventBus:
    """Simple async-capable event bus.

    Subscribers can be sync or async callables.  Sync callbacks are
    invoked directly; async callbacks are scheduled as tasks.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventCallback | AsyncEventCallback]] = defaultdict(list)
        self._global_subscribers: list[EventCallback | AsyncEventCallback] = []

    def subscribe(self, event_type: str, callback: EventCallback | AsyncEventCallback) -> None:
        """Subscribe to a specific event type."""
        self._subscribers[event_type].append(callback)

    def subscribe_all(self, callback: EventCallback | AsyncEventCallback) -> None:
        """Subscribe to every event (wildcard)."""
        self._global_subscribers.append(callback)

    def unsubscribe(self, event_type: str, callback: EventCallback | AsyncEventCallback) -> None:
        subs = self._subscribers.get(event_type, [])
        if callback in subs:
            subs.remove(callback)

    def emit(self, event: Event) -> None:
        """Emit an event to all subscribers.

        Sync callbacks are called immediately.  Async callbacks are
        scheduled as fire-and-forget tasks on the running loop.
        """
        callbacks = list(self._subscribers.get(event.type, [])) + list(self._global_subscribers)
        for cb in callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    asyncio.ensure_future(cb(event))
                else:
                    cb(event)
            except Exception:
                logger.exception("Event callback error for %s", event.type)

    def emit_nowait(self, event: Event) -> None:
        """Alias for emit (kept for clarity at call sites)."""
        self.emit(event)
