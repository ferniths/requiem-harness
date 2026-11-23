"""Launcher menu — the command palette.

A single-line search box with a filtered command list below it. Each
row shows a leading glyph, the label, and a right-aligned shortcut
hint. Selecting a row fires its bound action (via ``MenuRegistry``)
and posts a :class:`~requiem.tui.menus.base.Selected` message.

Usage::

    launcher = LauncherMenu()
    launcher.set_commands(
        [
            MenuCommand(id="save",  label="Save",        hint="Ctrl+S", action="save"),
            MenuCommand(id="open",  label="Open file",  hint="Ctrl+O", action="open"),
            MenuCommand(id="quit",  label="Quit",        hint="Ctrl+Q", action="quit"),
        ],
        registry=my_registry,
    )
    app.compose_result_yield(launcher)
"""

from __future__ import annotations

import logging
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Input, Static

from requiem.tui.menus.base import MenuBase, Selected
from requiem.tui.menus.commands import MenuCommand, MenuRegistry
from requiem.tui.menus.styles import MenuStyle

logger = logging.getLogger("requiem.tui.menus.launcher")


class LauncherMenu(Vertical, MenuBase):
    """Command-palette widget. Compose it into an app or screen."""

    CSS = """
    LauncherMenu {
        height: auto;
        max-height: 15;
        background: $requiem-bg-recessed;
        border: solid $requiem-border;
        padding: 1 0;
    }
    .lm-input {
        height: 1;
        background: $requiem-bg-elevated;
        border: solid $requiem-border;
        padding: 0 1;
        margin: 0 1;
    }
    .lm-input:focus {
        border: solid $requiem-accent;
    }
    .lm-item {
        height: 1;
        padding: 0 2;
        color: $requiem-text-muted;
    }
    .lm-item.selected {
        background: $requiem-bg-elevated;
        color: $requiem-text;
    }
    .lm-header {
        color: $requiem-text-muted;
        text-style: italic;
        padding: 0 2;
        height: 1;
    }
    """

    BINDINGS = [
        Binding("up", "move_up", "Up", show=False),
        Binding("down", "move_down", "Down", show=False),
        Binding("g", "jump_first", "Top"),
        Binding("G", "jump_last", "Bottom"),
        Binding("escape", "close", "Close"),
    ]

    def __init__(self, style: MenuStyle | None = None) -> None:
        MenuBase.__init__(self, id="launcher-menu")
        Vertical.__init__(self)
        self._style = style or MenuStyle.for_theme()
        self._commands: list[MenuCommand] = []
        self._registry: MenuRegistry | None = None
        self._filtered: list[MenuCommand] = []
        self._sel_widget: Static | None = None

    @property
    def style(self) -> MenuStyle:
        return self._style

    def set_commands(
        self,
        commands: list[MenuCommand],
        registry: MenuRegistry | None = None,
    ) -> None:
        """Repopulate the launcher without rebuilding the widget."""
        self._commands = list(commands)
        self._registry = registry
        self._sel_idx = 0
        self._filtered = list(commands)
        self._invalidate()

    # ── data source ──────────────────────────────────────────────────

    def _items(self) -> list[MenuCommand]:
        return self._filtered

    # ── compose ───────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Type a command…", id="lm-input", classes="lm-input")
        yield VerticalScroll(id="lm-list")

    def on_mount(self) -> None:
        self._rebuild_rows()
        self.query_one("#lm-input").focus()

    # ── render ────────────────────────────────────────────────────────

    def _rebuild_rows(self) -> None:
        self._bump_frame()
        box = self.query_one("#lm-list", VerticalScroll)
        box.remove_children()
        self._sel_widget = None

        if not self._filtered:
            box.mount(Static("  No matching commands.", classes="lm-header"))
            return

        prev_cat = ""
        for i, cmd in enumerate(self._filtered):
            if cmd.category and cmd.category != prev_cat:
                box.mount(Static(f"  {cmd.category.upper()}", classes="lm-header"))
                prev_cat = cmd.category
            is_sel = i == self._sel_idx
            cls = "lm-item selected" if is_sel else "lm-item"
            icon = f"{cmd.icon}  " if cmd.icon else "   "
            hint = f"  {cmd.hint}" if cmd.hint else ""
            text = f"{icon}{cmd.label}{hint}"
            if not cmd.enabled:
                text = f"{text}  (disabled)"
            row = Static(text, classes=cls)
            box.mount(row)
            if is_sel:
                self._sel_widget = row

    def _invalidate(self) -> None:
        if not self.is_mounted:
            return
        self._rebuild_rows()
        # Scroll the selected row into view
        if self._sel_widget is not None:
            self.query_one("#lm-list", VerticalScroll).scroll_to_widget(self._sel_widget)

    # ── keyboard ──────────────────────────────────────────────────────

    def action_move_up(self) -> None:
        self._typeahead_reset()
        if self._filtered:
            self._sel_idx = max(0, self._sel_idx - 1)
            self._invalidate()

    def action_move_down(self) -> None:
        self._typeahead_reset()
        if self._filtered:
            self._sel_idx = min(len(self._filtered) - 1, self._sel_idx + 1)
            self._invalidate()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "lm-input":
            return
        query = event.value.strip().lower()
        if not query:
            self._filtered = list(self._commands)
        else:
            self._filtered = [
                c for c in self._commands
                if query in c.label.lower()
                or query in (c.hint or "").lower()
                or query in (c.category or "").lower()
            ]
        self._sel_idx = 0
        self._invalidate()

    def on_key(self, event: Any) -> None:
        # Forward printable keys to type-ahead when not in the input
        if event.is_printable and not event.character.isspace():
            self._typeahead_feed(event.character)
            event.stop()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "lm-input":
            self.action_execute()

    # ── selection ─────────────────────────────────────────────────────

    def action_execute(self) -> None:
        """Run the currently selected command's action."""
        items = self._filtered
        if not items:
            self.action_close()
            return
        cmd = items[self._sel_idx]
        if not cmd.enabled:
            return
        fn = None
        if self._registry is not None:
            fn = self._registry.resolve(cmd)
        elif callable(cmd.action):
            fn = cmd.action
        if fn is not None:
            try:
                result = fn()
                if hasattr(result, "__await__"):
                    import asyncio
                    asyncio.ensure_future(result)
            except Exception:
                logger.exception("Launcher action %r failed", cmd.id)
        self.post_message(Selected(cmd.id, self))

    def action_close(self) -> None:
        """Post a Selected with empty id to signal close."""
        self.post_message(Selected("", self))

    def open(self) -> None:
        self.query_one("#lm-input").focus()

    def close(self) -> None:
        self.post_message(Selected("", self))
