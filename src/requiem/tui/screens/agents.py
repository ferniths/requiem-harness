"""Agent Dashboard modal screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, Static


class AgentsScreen(ModalScreen[None]):
    """Shows active agents, their status, and current tasks."""

    CSS = """
    AgentsScreen {
        content-align: center middle;
        background: rgba(12, 10, 11, 0.92);
    }
    #agents-box {
        width: 70%;
        height: 80%;
        border: solid #2A242D;
        background: $surface;
        padding: 2;
    }
    """

    BINDINGS = [("escape", "close", "Close")]

    def compose(self) -> ComposeResult:
        with Vertical(id="agents-box"):
            yield Label("Agent Dashboard")
            yield Static(
                "No active agents. Start a workflow to see agent activity.\n"
                "  F3  Workflow Runner\n"
                "  Esc  Close",
                id="agents-empty",
            )

    def action_close(self) -> None:
        self.dismiss()
