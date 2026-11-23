"""Modal menu screen.

Wraps a :class:`~requiem.tui.menus.launcher.LauncherMenu` in a
:class:`ModalScreen` so it can overlay any active screen. The
selected command's action fires when the user confirms.

Usage::

    app.push_screen(ModalMenuScreen(commands=[...], registry=my_reg))
    # later, on dismissal:
    result = screen.dismissed
    if result:  # a command was selected
        ...

The screen returns the selected command id (or None if dismissed).
"""

from __future__ import annotations

import logging
from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from requiem.tui.menus.commands import MenuCommand, MenuRegistry
from requiem.tui.menus.launcher import LauncherMenu
from requiem.tui.menus.styles import MenuStyle

logger = logging.getLogger("requiem.tui.menus.screen")


class ModalMenuScreen(ModalScreen[str | None]):
    """Modal launcher. Dismisses with the selected command id (or None)."""

    CSS = """
    ModalMenuScreen {
        content-align: center middle;
        background: $requiem-bg-recessed;
    }
    #modal-menu-wrap {
        width: 55%;
        height: auto;
        max-height: 50%;
        border: solid $requiem-accent;
        background: $requiem-bg-elevated;
        padding: 1;
    }
    """

    def __init__(
        self,
        commands: list[MenuCommand],
        registry: MenuRegistry | None = None,
        title: str = "Commands",
        style: MenuStyle | None = None,
    ) -> None:
        super().__init__()
        self._commands = commands
        self._registry = registry
        self._title = title
        self._style = style or MenuStyle.for_theme()
        self._selected: str | None = None
        self._launcher: LauncherMenu | None = None

    @property
    def selected(self) -> str | None:
        """The command id the user picked, or None if closed without selecting."""
        return self._selected

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-menu-wrap"):
            yield Static(f"  {self._title}", classes="lm-header")
            yield LauncherMenu(style=self._style)

    def on_mount(self) -> None:
        launcher = self.query_one("#modal-menu-wrap", Vertical).query_one(LauncherMenu)
        launcher.set_commands(self._commands, self._registry)
        launcher.focus()
        self._launcher = launcher

    def on_selected(self, msg: Any) -> None:
        """Handle a Selection from the launcher."""
        from requiem.tui.menus.base import Selected

        if not isinstance(msg, Selected):
            return
        # Empty id means "close" — dismiss with None
        self._selected = msg.selected_id or None
        if not msg.selected_id:
            self.dismiss(None)
            return
        # Fire the action
        if self._launcher is not None and self._registry is not None:
            for cmd in self._commands:
                if cmd.id == msg.selected_id:
                    fn = self._registry.resolve(cmd)
                    if fn is not None:
                        try:
                            result = fn()
                            if hasattr(result, "__await__"):
                                import asyncio
                                asyncio.ensure_future(result)
                        except Exception:
                            logger.exception("Modal menu action %r failed", msg.selected_id)
                    break
        self.dismiss(self._selected)
