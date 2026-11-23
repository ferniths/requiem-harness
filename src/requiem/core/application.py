"""Core application lifecycle and state management."""

from __future__ import annotations

import enum
import logging
from typing import Any

logger = logging.getLogger("requiem.core")


class AppState(enum.Enum):
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    SHUTTING_DOWN = "shutting_down"
    STOPPED = "stopped"


class ApplicationState:
    """Holds cross-cutting application state.

    This is the single source of truth for application lifecycle state.
    Individual subsystems (providers, workflow engine, TUI) receive
    references to this object rather than maintaining their own copies.
    """

    def __init__(self) -> None:
        self._state = AppState.STARTING
        self._active_workflow_id: str | None = None
        self._active_agents: dict[str, Any] = {}
        self._last_error: Exception | None = None

    @property
    def state(self) -> AppState:
        return self._state

    def transition_to(self, new_state: AppState) -> None:
        old = self._state
        self._state = new_state
        logger.debug("App state: %s -> %s", old, new_state)

    @property
    def active_workflow_id(self) -> str | None:
        return self._active_workflow_id

    def set_active_workflow(self, workflow_id: str | None) -> None:
        self._active_workflow_id = workflow_id

    @property
    def active_agents(self) -> dict[str, Any]:
        return self._active_agents

    @property
    def last_error(self) -> Exception | None:
        return self._last_error

    def set_last_error(self, error: Exception | None) -> None:
        self._last_error = error

    def start(self) -> None:
        self.transition_to(AppState.RUNNING)

    def pause(self) -> None:
        self.transition_to(AppState.PAUSED)

    def resume(self) -> None:
        self.transition_to(AppState.RUNNING)

    def shutdown(self) -> None:
        self.transition_to(AppState.SHUTTING_DOWN)

    def stopped(self) -> None:
        self.transition_to(AppState.STOPPED)
