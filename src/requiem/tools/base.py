"""Tool base classes — shared types for the tool registry and all tool implementations.

Every tool exposes:
- A JSON-schema-like input schema (dict)
- A structured ToolResult (not arbitrary untyped output)
- A permission level requirement
- An async execution handler
"""

from __future__ import annotations

import abc
import enum
from dataclasses import dataclass, field
from typing import Any


class ToolStatus(enum.Enum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    DENIED = "denied"
    CANCELLED = "cancelled"


@dataclass
class ToolResult:
    """Structured result returned by every tool execution."""

    status: ToolStatus
    data: Any = None
    error: str | None = None
    duration_s: float = 0.0
    truncated: bool = False

    @property
    def ok(self) -> bool:
        return self.status == ToolStatus.SUCCESS

    def to_dict(self) -> dict[str, Any]:
        """Serialize for agent context or audit log."""
        d: dict[str, Any] = {"status": self.status.value, "duration_s": round(self.duration_s, 3)}
        if self.data is not None:
            d["data"] = self.data
        if self.error:
            d["error"] = self.error
        if self.truncated:
            d["truncated"] = True
        return d


class Tool(abc.ABC):
    """Abstract base for all tool implementations.

    Subclasses set:
        name: str
        description: str
        input_schema: dict
        permission_level: PermissionLevel (from security.permissions)
        timeout_s: float
    """

    name: str = ""
    description: str = ""
    input_schema: dict[str, Any] = {}
    permission_level: Any = None  # set by registry
    timeout_s: float = 30.0

    @abc.abstractmethod
    async def execute(self, arguments: dict[str, Any], *, context: ToolContext) -> ToolResult:
        """Execute the tool with validated arguments.

        context provides workspace paths, audit log, etc.
        """
        ...


@dataclass
class ToolContext:
    """Execution context passed to every tool invocation.

    Provides:
    - workspace_root: the project directory all filesystem ops are relative to
    - audit_log: append-only audit trail for security-sensitive operations
    - cancel_event: asyncio.Event set when the user cancels the workflow
    - extra: provider-specific or agent-specific context
    """

    workspace_root: str = "."
    audit_log: Any = None  # AuditLog instance
    cancel_event: Any = None  # asyncio.Event | None
    extra: dict[str, Any] = field(default_factory=dict)
