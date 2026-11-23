"""Core exceptions for REQUIEM.

All exceptions in this hierarchy carry actionable metadata so the user
understands what failed, which component failed, and whether the
operation is retryable.
"""

from __future__ import annotations


class RequiemError(Exception):
    """Base exception for all REQUIEM errors."""

    def __init__(self, message: str, *, component: str = "unknown", retryable: bool = False) -> None:
        self.message = message
        self.component = component
        self.retryable = retryable
        super().__init__(message)


class ConfigError(RequiemError):
    """Configuration is missing, malformed, or fails validation."""

    def __init__(self, message: str, *, component: str = "config") -> None:
        super().__init__(message, component=component, retryable=False)


class CredentialError(RequiemError):
    """Credential retrieval, storage, or validation failure."""

    def __init__(self, message: str, *, component: str = "credentials") -> None:
        super().__init__(message, component=component, retryable=False)


class ProviderError(RequiemError):
    """A provider request or response failed."""

    def __init__(
        self,
        message: str,
        *,
        component: str = "provider",
        status_code: int | None = None,
        retryable: bool | None = None,
    ) -> None:
        self.status_code = status_code
        if retryable is None:
            retryable = status_code is not None and status_code >= 500
        super().__init__(message, component=component, retryable=retryable)

class ProviderAuthError(ProviderError):
    """Authentication failed (401/403). Not retryable."""

    def __init__(self, message: str, *, component: str = "provider") -> None:
        super().__init__(message, component=component, retryable=False)


class ProviderRateLimitError(ProviderError):
    """Rate limit exceeded (429). Retryable after delay."""

    def __init__(self, message: str, *, component: str = "provider", retry_after: float | None = None) -> None:
        self.retry_after = retry_after
        super().__init__(message, component=component, retryable=True)


class ProviderTimeoutError(ProviderError):
    """Request timed out. Retryable."""

    def __init__(self, message: str, *, component: str = "provider") -> None:
        super().__init__(message, component=component, retryable=True)


class WorkflowError(RequiemError):
    """Workflow definition, execution, or validation failure."""

    def __init__(self, message: str, *, component: str = "workflow", retryable: bool = False) -> None:
        super().__init__(message, component=component, retryable=retryable)


class WorkflowCycleError(WorkflowError):
    """The task graph contains a cycle."""

    def __init__(self, cycle: list[str]) -> None:
        self.cycle = cycle
        super().__init__(f"Task dependency cycle detected: {' -> '.join(cycle)}", component="workflow", retryable=False)


class PermissionError_(RequiemError):  # noqa: N801,N818
    """An operation was denied by the permission model."""

    def __init__(self, message: str, *, tool: str = "", permission: str = "") -> None:
        self.tool = tool
        self.permission = permission
        super().__init__(message, component="permissions", retryable=False)


class ToolError(RequiemError):
    """A tool execution failed."""

    def __init__(self, message: str, *, tool: str = "") -> None:
        self.tool_name = tool
        super().__init__(message, component=tool or "tool", retryable=False)


class AgentError(RequiemError):
    """An agent lifecycle failure."""

    def __init__(self, message: str, *, agent: str = "") -> None:
        self.agent_name = agent
        super().__init__(message, component=agent or "agent", retryable=False)


class ApprovalRequired(RequiemError):  # noqa: N818
    """The operation requires human approval before proceeding.

    This is not a failure — it is a control-flow signal.
    """

    def __init__(self, description: str, *, tool: str = "", arguments: dict[str, object] | None = None) -> None:
        self.description = description
        self.tool_name = tool
        self.arguments = arguments or {}
        super().__init__(f"Approval required: {description}", component="approval", retryable=False)
