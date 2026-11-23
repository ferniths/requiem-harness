"""Log viewer with real filtering and live tail.

Replaces the snapshot-only logs screen with an interactive log viewer
that supports level filtering, text search, and pause/resume.
"""

from __future__ import annotations

import logging
import time
from collections import deque

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Input, Label, Static

logger = logging.getLogger("requiem.tui.views.logs")

_LEVELS = ["ALL", "DEBUG", "INFO", "WARNING", "ERROR"]


class _LogBufferHandler(logging.Handler):
    """Ring buffer log handler for the log viewer."""

    def __init__(self, maxlen: int = 500) -> None:
        super().__init__()
        self._buf: deque[logging.LogRecord] = deque(maxlen=maxlen)

    def emit(self, record: logging.LogRecord) -> None:
        self._buf.append(record)

    def records(self, *, level: str = "ALL", search: str = "") -> list[str]:
        """Return formatted log lines filtered by level and search."""
        lines = []
        for rec in reversed(self._buf):
            if level != "ALL" and rec.levelname != level:
                continue
            formatted = (
                f"{time.strftime('%H:%M:%S', time.localtime(rec.created))}"
                f"  {rec.levelname:<8}"
                f"  {rec.name:<24}"
                f"  {rec.getMessage()}"
            )
            if search and search.lower() not in formatted.lower():
                continue
            lines.append(formatted)
            if len(lines) >= 200:
                break
        return lines


_log_handler = _LogBufferHandler()


def install_log_handler() -> None:
    """Attach the ring buffer handler to the requiem logger (idempotent)."""
    root = logging.getLogger("requiem")
    for h in root.handlers:
        if isinstance(h, _LogBufferHandler):
            return
    root.addHandler(_log_handler)
    root.setLevel(logging.DEBUG)


class LogsView(Vertical):
    """Interactive log viewer."""

    view_id = "logs"
    view_label = "Logs"
    view_group = "Management"

    filter_level: reactive[str] = reactive("ALL")
    search_text: reactive[str] = reactive("")
    is_paused: reactive[bool] = reactive(False)

    def __init__(self) -> None:
        super().__init__(id="req-logs-view")

    def compose(self) -> ComposeResult:
        with Vertical(id="req-logs-layout"):
            yield Static("Logs", classes="req-section-title")
            # Filter row
            with Vertical(id="req-logs-filters"):
                yield Label("", id="req-logs-filter-label")
                yield Input(placeholder="Search logs…", id="req-logs-search")
            # Log content
            yield VerticalScroll(id="req-logs-content")
            # Controls
            with Vertical(id="req-logs-controls"):
                yield Label("", id="req-logs-controls-label")

    def on_mount(self) -> None:
        install_log_handler()
        self._refresh_filters()
        self._refresh()
        # Auto-refresh every 2 seconds
        self.set_interval(2.0, self._refresh)

    def _refresh_filters(self) -> None:
        label = self.query_one("#req-logs-filter-label", Label)
        label.update(f"Filter: {self.filter_level}   ·   {'Paused' if self.is_paused else 'Live'}")

    def _refresh(self) -> None:
        if self.is_paused:
            return
        content = self.query_one("#req-logs-content")
        content.remove_children("*")
        lines = _log_handler.records(level=self.filter_level, search=self.search_text)
        if not lines:
            content.mount(Static("No log entries match the current filter.", classes="req-empty-state"))
            return
        for line in lines:
            content.mount(Static(line, classes="req-log-row"))
        content.scroll_end()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "req-logs-search":
            self.search_text = event.value.strip()
            self._refresh()

    def action_cycle_level(self) -> None:
        """Cycle through filter levels: ALL → DEBUG → INFO → WARNING → ERROR → ALL."""
        idx = _LEVELS.index(self.filter_level)
        self.filter_level = _LEVELS[(idx + 1) % len(_LEVELS)]
        self._refresh_filters()
        self._refresh()

    def action_toggle_pause(self) -> None:
        self.is_paused = not self.is_paused
        self._refresh_filters()

    def action_clear_view(self) -> None:
        """Clear the displayed view without touching the persistent buffer."""
        content = self.query_one("#req-logs-content")
        content.remove_children("*")
        content.mount(Static("(View cleared — logs still accumulating in background)", classes="req-empty-state"))
