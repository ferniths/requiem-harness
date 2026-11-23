"""Command palette — searchable, keyboard-navigable action selector.

Opens with Ctrl+P. Filters commands by label and keywords.
Arrow keys move the selection cursor; Enter executes the selected command.
"""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Input, Static


class CommandPalette(ModalScreen[None]):
    """Searchable command palette with arrow-key navigation."""

    CSS = """
    CommandPalette {
        content-align: center middle;
        background: $requiem-bg-recessed;
    }
    #req-palette {
        width: 50%;
        height: auto;
        max-height: 50%;
        border: solid $requiem-accent;
        background: $requiem-bg-elevated;
        padding: 1;
    }
    #req-palette-input {
        height: 1;
        background: $requiem-bg-recessed;
        border: solid $requiem-border;
        padding: 0 1;
        margin-bottom: 1;
    }
    .req-palette-item {
        height: 1;
        padding: 0 2;
        color: $requiem-text-muted;
    }
    .req-palette-item.selected {
        background: $requiem-bg-elevated;
        color: $requiem-text;
    }
    .req-palette-key {
        color: $requiem-text-muted;
    }
    """

    BINDINGS = [
        ("escape", "close", "Close"),
        ("enter", "execute", "Run"),
        ("up", "move_up", ""),
        ("down", "move_down", ""),
    ]

    _COMMANDS: list[tuple[str, str, str, str]] = [
        # (label, action_method, keywords, description)
        ("Open Chat", "nav_chat", "chat workspace F1", "Switch to the chat workspace"),
        ("Agent Dashboard", "nav_agents", "agents F2", "View running agents"),
        ("Workflow Center", "nav_workflows", "workflows F3", "Manage workflow definitions"),
        ("Provider Manager", "nav_providers", "providers F5 9router openai anthropic", "Configure and test providers"),
        ("Logs", "nav_logs", "logs F4", "View operational logs"),
        ("Settings", "nav_settings", "settings F6", "Edit application configuration"),
        ("Change Theme", "nav_themes", "themes appearance F7 classic blue purple", "Switch the active theme"),
        ("Help", "nav_help", "help F1", "View keyboard shortcuts and CLI reference"),
        ("Run Onboarding", "run_onboarding", "onboarding first-run wizard", "Re-run the setup wizard"),
        ("Clear Conversation", "clear_conversation", "chat clear reset", "Start a fresh chat"),
        ("Quit REQUIEM", "quit", "exit close quit ctrl-q", "Exit the application"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._filtered: list[tuple[str, str, str, str]] = []
        self._selected_idx: int = 0

    def compose(self) -> ComposeResult:
        self._filtered = list(self._COMMANDS)
        with Vertical(id="req-palette"):
            yield Input(placeholder="Type a command…", id="req-palette-input")
            yield VerticalScroll(id="req-palette-list")

    def on_mount(self) -> None:
        self._mount_items()
        self.query_one("#req-palette-input", Input).focus()

    def _mount_items(self) -> None:
        """Render the filtered command list with selection highlighting."""
        box = self.query_one("#req-palette-list")
        # Remove all existing children synchronously
        box.remove_children("*")
        self._item_widgets: list[Static] = []
        if not self._filtered:
            box.mount(Static("  No matching commands.", classes="req-palette-item"))
            return
        for i, (label, _action, _kw, desc) in enumerate(self._filtered):
            cls = "req-palette-item selected" if i == self._selected_idx else "req-palette-item"
            hint = f"  —  {desc}" if desc else ""
            row = Static(f"  {label}{hint}", classes=cls)
            self._item_widgets.append(row)
            box.mount(row)
        # Keep the selected item visible
        if 0 <= self._selected_idx < len(self._item_widgets):
            box.scroll_to_widget(self._item_widgets[self._selected_idx])

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "req-palette-input":
            return
        query = event.value.strip().lower()
        if not query:
            self._filtered = list(self._COMMANDS)
        else:
            self._filtered = [
                (label, action, kw, desc)
                for label, action, kw, desc in self._COMMANDS
                if query in label.lower() or query in kw
            ]
        self._selected_idx = 0
        self._mount_items()

    def action_move_up(self) -> None:
        if self._filtered:
            self._selected_idx = max(0, self._selected_idx - 1)
            self._mount_items()

    def action_move_down(self) -> None:
        if self._filtered:
            self._selected_idx = min(len(self._filtered) - 1, self._selected_idx + 1)
            self._mount_items()

    def action_execute(self) -> None:
        """Execute the currently selected command."""
        if not self._filtered:
            self.dismiss()
            return
        label, action, _kw, _desc = self._filtered[self._selected_idx]
        self.dismiss()
        app: Any = self.app
        handler = getattr(app, f"action_{action}", None)
        if handler is not None:
            handler()
        elif action == "run_onboarding":
            from requiem.tui.screens.onboarding import OnboardingScreen
            app.push_screen(OnboardingScreen())
        elif action == "clear_conversation":
            view = app._get_view("chat")
            if view is not None:
                view.clear_conversation()

    def action_close(self) -> None:
        self.dismiss()
