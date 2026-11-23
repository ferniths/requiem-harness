"""Help screen — keyboard shortcuts, commands, and usage info."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, Static

HELP_TEXT = """
  REQUIEM — Keyboard Shortcuts

  Ctrl+P      Command palette
  Ctrl+Q      Quit application
  Ctrl+C      Cancel active operation
  Ctrl+Enter  Submit message

  F1          Help (this screen)
  F2          Agent dashboard
  F3          Workflow runner
  F4          Logs
  F5          Provider manager
  F6          Settings
  F7          Theme manager
  Esc         Close modal / go back
  Tab         Move focus

  Configuration

  User config:  platformdirs/requiem/config.toml
  Project:      .requiem/ in your project root

  CLI Commands

  requiem            Launch TUI
  requiem check      Verify installation
  requiem init       Create .requiem/
  requiem list-providers
  requiem test <id>  Test a provider connection
  requiem run <wf>   Run a workflow headlessly
"""


class HelpScreen(ModalScreen[None]):
    """Modal help overlay."""

    CSS = """
    HelpScreen {
        content-align: center middle;
        background: rgba(12, 10, 11, 0.92);
    }
    #help-box {
        width: 70%;
        height: 80%;
        border: solid #2A242D;
        background: $surface;
        padding: 2;
    }
    """

    BINDINGS = [("escape", "close", "Close")]

    def compose(self) -> ComposeResult:
        with Vertical(id="help-box"):
            yield Label("REQUIEM — Help", id="help-title")
            yield Static(HELP_TEXT)

    def action_close(self) -> None:
        self.dismiss()
