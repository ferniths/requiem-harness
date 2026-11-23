"""Command Palette modal — searchable action list."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Input, Label, Static


class CommandPalette(ModalScreen[None]):
    """Searchable command palette. Type to filter, Enter to execute."""

    CSS = """
    CommandPalette {
        content-align: center middle;
        background: rgba(12, 10, 11, 0.92);
    }
    #palette-box {
        width: 60%;
        height: 50%;
        border: solid #C02645;
        background: $surface;
        padding: 1;
    }
    #palette-input {
        height: 2;
        border: solid #2A242D;
        background: $panel;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("enter", "execute", "Execute"),
    ]

    # (label, action_key, keywords)
    _COMMANDS: list[tuple[str, str, str]] = [
        ("Agent Dashboard", "show_agents", "agents dashboard F2"),
        ("Workflow Runner", "show_workflows", "workflows F3"),
        ("Logs", "show_logs", "logs F4"),
        ("Provider Manager", "show_providers", "providers F5 9router openai anthropic"),
        ("Settings", "show_settings", "settings F6"),
        ("Theme Manager", "show_themes", "themes F7 classic blue purple"),
        ("Help", "show_help", "help F1"),
        ("Quit", "quit", "quit exit close"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._filtered: list[tuple[str, str, str]] = []

    def compose(self) -> ComposeResult:
        self._filtered = list(self._COMMANDS)
        with Vertical(id="palette-box"):
            yield Label("Command Palette")
            yield Input(placeholder="Type a command…", id="palette-input")
            yield VerticalScroll(id="palette-list")

    def on_mount(self) -> None:
        self._mount_commands()

    def _mount_commands(self) -> None:
        """Re-mount the command list (called after filtering)."""
        box = self.query_one("#palette-list")
        # Remove all children
        box.remove_children("*")
        for label, action, _ in self._filtered:
            box.mount(Static(f"  {label}", id=f"cmd-{action}"))

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "palette-input":
            return
        query = event.value.strip().lower()
        if not query:
            self._filtered = list(self._COMMANDS)
        else:
            self._filtered = [
                (label, action, kw)
                for label, action, kw in self._COMMANDS
                if query in label.lower() or query in kw
            ]
        self._mount_commands()

    def action_execute(self) -> None:
        """Execute the first visible command."""
        if not self._filtered:
            self.dismiss()
            return
        action = self._filtered[0][1]
        self.dismiss()
        # Trigger the app action after dismissing
        app = self.app
        getattr(app, f"action_{action}", lambda: None)()

    def action_close(self) -> None:
        self.dismiss()
