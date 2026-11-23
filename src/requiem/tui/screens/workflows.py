"""Workflow Runner modal screen."""

from __future__ import annotations

import pathlib

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Label, Static


class WorkflowsScreen(ModalScreen[None]):
    """Shows available workflow files and active workflow status."""

    CSS = """
    WorkflowsScreen {
        content-align: center middle;
        background: rgba(12, 10, 11, 0.92);
    }
    #wf-box {
        width: 70%;
        height: 80%;
        border: solid #2A242D;
        background: $surface;
        padding: 2;
    }
    """

    BINDINGS = [("escape", "close", "Close")]

    def compose(self) -> ComposeResult:
        with Vertical(id="wf-box"):
            yield Label("Workflow Runner")
            yield Static("Status: No active workflow", id="wf-status")

            # List workflow files
            wf_dir = pathlib.Path(".requiem/workflows")
            if wf_dir.is_dir():
                files = sorted(f.name for f in wf_dir.iterdir() if f.suffix in (".toml", ".yaml", ".yml", ".json"))
                if files:
                    with VerticalScroll():
                        for fname in files:
                            yield Static(f"  {fname}")
                else:
                    yield Static("  No workflow files found in .requiem/workflows/")
            else:
                yield Static("  No .requiem/workflows/ directory found. Run `requiem init` to create it.")

            yield Static("\nRun a workflow: requiem run <path-to-workflow>")
            yield Static("Esc  Close")

    def action_close(self) -> None:
        self.dismiss()
