"""Selector and check menus.

SelectorMenu — radio buttons: exactly one active item, shown as
"●"/"○". CheckMenu — checkboxes: multiple persist across navigation,
shown as "☑"/"☐".

Both expose:
    .selected: str | None          (SelectorMenu: the single id)
    .selected_ids: list[str]       (CheckMenu: the active ids)
    .on_selected / .on_check_toggle message handlers
"""

from __future__ import annotations

import logging
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Static

from requiem.tui.menus.base import MenuBase
from requiem.tui.menus.commands import MenuCommand
from requiem.tui.menus.styles import MenuStyle

logger = logging.getLogger("requiem.tui.menus.selector")


class CheckToggled(Message):
    """Posted by CheckMenu when the user toggles a checkbox."""

    def __init__(self, command_id: str, checked: bool, source: Any) -> None:
        self.command_id = command_id
        self.checked = checked
        self.source = source
        super().__init__()


class RadioSelected(Message):
    """Posted by SelectorMenu when the user confirms a radio choice."""

    def __init__(self, command_id: str, source: Any) -> None:
        self.command_id = command_id
        self.source = source
        super().__init__()


class _SelectorBase(Vertical, MenuBase):
    """Shared base for radio and check menus."""

    CSS = """
    _SelectorBase {
        height: auto;
        background: $requiem-bg-recessed;
        border: solid $requiem-border;
        padding: 1 0;
    }
    .sl-item {
        height: 1;
        padding: 0 2;
        color: $requiem-text-muted;
    }
    .sl-item.selected {
        background: $requiem-bg-elevated;
        color: $requiem-text;
    }
    .sl-marker {
        color: $requiem-accent;
        text-style: bold;
    }
    """

    BINDINGS = [
        Binding("up", "move_up", "Up", show=False),
        Binding("down", "move_down", "Down", show=False),
        Binding("enter", "activate", "Select"),
        Binding("g", "jump_first", "Top", show=False),
        Binding("G", "jump_last", "Bottom", show=False),
        Binding("escape", "close", "Close", show=False),
    ]

    def __init__(self, commands: list[MenuCommand] | None = None, style: MenuStyle | None = None) -> None:
        MenuBase.__init__(self)
        Vertical.__init__(self)
        self._style = style or MenuStyle.for_theme()
        self._commands = list(commands or [])

    @property
    def style(self) -> MenuStyle:
        return self._style

    def set_commands(self, commands: list[MenuCommand]) -> None:
        self._commands = list(commands)
        self._sel_idx = 0
        self._invalidate()

    def _items(self) -> list[MenuCommand]:
        return self._commands

    def compose(self) -> ComposeResult:
        yield Vertical(id="sl-list")

    def on_mount(self) -> None:
        self._invalidate()

    def _invalidate(self) -> None:
        if not self.is_mounted:
            return
        self._bump_frame()
        box = self.query_one("#sl-list", Vertical)
        box.remove_children()
        if not self._commands:
            box.mount(Static("  No options.", classes="sl-item"))
            return
        for i, cmd in enumerate(self._commands):
            marker = self._marker_for(cmd, i)
            is_sel = i == self._sel_idx
            cls = "sl-item selected" if is_sel else "sl-item"
            icon = f"{cmd.icon}  " if cmd.icon else "   "
            box.mount(
                Static(
                    f"{marker}  {icon}{cmd.label}  {cmd.hint}".rstrip(),
                    classes=cls,
                ),
            )

    def _marker_for(self, cmd: MenuCommand, idx: int) -> str:
        raise NotImplementedError

    # ── shared navigation ────────────────────────────────────────────

    def action_move_up(self) -> None:
        self._typeahead_reset()
        if self._commands:
            self._sel_idx = max(0, self._sel_idx - 1)
            self._invalidate()

    def action_move_down(self) -> None:
        self._typeahead_reset()
        if self._commands:
            self._sel_idx = min(len(self._commands) - 1, self._sel_idx + 1)
            self._invalidate()

    def action_close(self) -> None:
        pass

    def on_key(self, event: Any) -> None:
        if event.is_printable and not event.character.isspace():
            self._typeahead_feed(event.character)
            event.stop()

    def open(self) -> None:
        self._invalidate()

    def close(self) -> None:
        pass


class SelectorMenu(_SelectorBase):
    """Radio-button selector: exactly one active item."""

    def __init__(
        self,
        commands: list[MenuCommand] | None = None,
        selected: str | None = None,
        style: MenuStyle | None = None,
    ) -> None:
        super().__init__(commands=commands, style=style)
        self._selected: str | None = selected

    @property
    def selected(self) -> str | None:
        return self._selected

    @selected.setter
    def selected(self, value: str | None) -> None:
        self._selected = value
        if value is not None and self._commands:
            for i, cmd in enumerate(self._commands):
                if cmd.id == value:
                    self._sel_idx = i
                    break
        self._invalidate()

    def _marker_for(self, cmd: MenuCommand, idx: int) -> str:
        return "●" if cmd.id == self._selected else "○"

    def action_activate(self) -> None:
        if not self._commands:
            return
        cmd = self._commands[self._sel_idx]
        if not cmd.enabled:
            return
        self._selected = cmd.id
        self._invalidate()
        self.post_message(RadioSelected(cmd.id, self))

    def open(self) -> None:
        self._invalidate()

    def close(self) -> None:
        pass


class CheckMenu(_SelectorBase):
    """Checkbox multi-select: any number of active items persist."""

    def __init__(
        self,
        commands: list[MenuCommand] | None = None,
        checked: list[str] | None = None,
        style: MenuStyle | None = None,
    ) -> None:
        super().__init__(commands=commands, style=style)
        self._checked: set[str] = set(checked or [])

    @property
    def selected_ids(self) -> list[str]:
        """Return the active checkbox ids, in menu order."""
        return [c.id for c in self._commands if c.id in self._checked]

    @selected_ids.setter
    def selected_ids(self, ids: list[str]) -> None:
        self._checked = set(ids)
        self._invalidate()

    def _marker_for(self, cmd: MenuCommand, idx: int) -> str:
        return "☑" if cmd.id in self._checked else "☐"

    def action_activate(self) -> None:
        if not self._commands:
            return
        cmd = self._commands[self._sel_idx]
        if not cmd.enabled:
            return
        # Toggle
        if cmd.id in self._checked:
            self._checked.discard(cmd.id)
            checked = False
        else:
            self._checked.add(cmd.id)
            checked = True
        self._invalidate()
        self.post_message(CheckToggled(cmd.id, checked, self))

    def open(self) -> None:
        self._invalidate()

    def close(self) -> None:
        pass
