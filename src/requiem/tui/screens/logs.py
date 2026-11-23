"""Application Logs modal screen."""

from __future__ import annotations

import logging

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Label, Static


class _RingBufferHandler(logging.Handler):
    """A logging handler that keeps the last N log records in memory."""

    def __init__(self, capacity: int = 200) -> None:
        super().__init__()
        self._capacity = capacity
        self._records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self._records.append(record)
        if len(self._records) > self._capacity:
            self._records = self._records[-self._capacity:]

    def get_records(self, level: int = logging.INFO) -> list[str]:
        fmt = "%(asctime)s  %(levelname)-8s  %(name)-28s  %(message)s"
        out = []
        for rec in reversed(self._records):
            if rec.levelno >= level:
                out.append(fmt % rec.__dict__)
        return out[-50:]



_ring_buffer = _RingBufferHandler()


def install_log_handler() -> None:
    """Install the ring buffer handler on the requiem logger (call once at startup)."""
    req_logger = logging.getLogger("requiem")
    if not any(isinstance(h, _RingBufferHandler) for h in req_logger.handlers):
        req_logger.addHandler(_ring_buffer)
        req_logger.setLevel(logging.DEBUG)


class LogsScreen(ModalScreen[None]):
    """Shows recent application log entries."""

    CSS = """
    LogsScreen {
        content-align: center middle;
        background: rgba(12, 10, 11, 0.92);
    }
    #logs-box {
        width: 80%;
        height: 85%;
        border: solid #2A242D;
        background: $surface;
        padding: 1;
    }
    """

    BINDINGS = [("escape", "close", "Close")]

    def compose(self) -> ComposeResult:
        install_log_handler()
        with Vertical(id="logs-box"):
            yield Label("Application Logs")
            yield Static("Filter: all | INFO | WARNING | ERROR   (display only)", id="log-filter-hint")
            with VerticalScroll():
                lines = _ring_buffer.get_records()
                if lines:
                    for line in lines:
                        yield Static(line)
                else:
                    yield Static("No log entries recorded yet.")

    def action_close(self) -> None:
        self.dismiss()
