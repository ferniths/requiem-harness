"""Approval gate and audit log for security-sensitive operations."""

from __future__ import annotations

import asyncio
import enum
import logging
import time
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger("requiem.security.audit")


class ApprovalDecision(enum.Enum):
    GRANTED = "granted"
    DENIED = "denied"
    TIMEOUT = "timeout"


@dataclass
class ApprovalRequest:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    tool: str = ""
    description: str = ""
    arguments: dict[str, object] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    _event: asyncio.Event = field(default_factory=asyncio.Event, repr=False)
    decision: ApprovalDecision | None = None

    @property
    def is_resolved(self) -> bool:
        return self.decision is not None

    def resolve(self, decision: ApprovalDecision) -> None:
        self.decision = decision
        self._event.set()

    async def wait(self, timeout_s: float = 300.0) -> ApprovalDecision:
        """Await a decision with an optional timeout.

        Returns TIMEOUT if no decision is made within *timeout_s*.
        """
        try:
            await asyncio.wait_for(self._event.wait(), timeout=timeout_s)
        except TimeoutError:
            self.resolve(ApprovalDecision.TIMEOUT)
        return self.decision or ApprovalDecision.TIMEOUT


class ApprovalGate:
    """Manages pending approval requests.

    The TUI registers a callback that displays the approval prompt and
    calls `resolve()` when the user responds.
    """

    def __init__(self) -> None:
        self._pending: dict[str, ApprovalRequest] = {}
        self._history: list[ApprovalRequest] = []
        self._timeout_s: float = 300.0

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def pending_requests(self) -> list[ApprovalRequest]:
        return list(self._pending.values())

    @property
    def history(self) -> list[ApprovalRequest]:
        return list(self._history)

    def set_timeout(self, seconds: float) -> None:
        self._timeout_s = seconds

    def request(self, tool: str, description: str, arguments: dict[str, object]) -> ApprovalRequest:
        req = ApprovalRequest(tool=tool, description=description, arguments=arguments)
        self._pending[req.id] = req
        logger.info("Approval requested: [%s] %s (%s)", req.id, tool, description)
        return req

    def resolve(self, request_id: str, decision: ApprovalDecision) -> None:
        req = self._pending.pop(request_id, None)
        if req is None:
            logger.warning("resolve: unknown approval request %s", request_id)
            return
        req.resolve(decision)
        self._history.append(req)
        logger.info("Approval [%s] %s: %s", request_id, req.tool, decision.value)

    def cancel_all(self) -> None:
        """Cancel all pending approvals (called on workflow cancellation)."""
        for req in list(self._pending.values()):
            req.resolve(ApprovalDecision.DENIED)
        self._pending.clear()

    async def request_and_wait(
        self,
        tool: str,
        description: str,
        arguments: dict[str, object],
    ) -> ApprovalDecision:
        """Create an approval request and await its decision."""
        req = self.request(tool, description, arguments)
        decision = await req.wait(timeout_s=self._timeout_s)
        self.resolve(req.id, decision)
        return decision


class AuditLog:
    """Append-only audit trail for security-sensitive tool operations.

    Each entry records: who (agent), what (tool), when, and outcome.
    Entries are written to a structured log file.
    """

    def __init__(self, logger_name: str = "requiem.audit") -> None:
        self._logger = logging.getLogger(logger_name)

    def record(
        self,
        agent: str,
        tool: str,
        arguments: dict[str, object],
        outcome: str,
        *,
        permission: str = "",
        approval_id: str = "",
    ) -> None:
        self._logger.info(
            "AUDIT agent=%s tool=%s outcome=%s permission=%s approval=%s args=%r",
            agent,
            tool,
            outcome,
            permission,
            approval_id,
            arguments,
        )
