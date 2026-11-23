"""Context menu — opens anchored at the cursor on right-click.

Shows 3-4 context-sensitive actions. Clamps its position to stay
fully on-screen when the anchor is near the bottom or right edge.

Use as an overlay widget: on a list widget's ``on_mouse_down`` with
``button == 3`` (right-click), compute the anchor and call
``menu.show(anchor_x, anchor_y)``. The widget positions itself in
``absolute`` coordinate space within its parent.

Keys:
    Up/Down  move highlight
    Enter    select the action
    Esc      close
"""

from __future__ import annotations

import logging
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Static

from requiem.tui.menus.base import MenuBase, Selected
from requiem.tui.menus.commands import MenuCommand, MenuRegistry
from requiem.tui.menus.styles import MenuStyle

logger = logging.getLogger("requiem.tui.menus.context")


class ContextMenu(Vertical, MenuBase):
    """Anchored right-click context menu.

    Compose it into a screen (it's an overlay). Position it with
    :meth:`show` which sets its ``offset`` and makes it visible.
    """

    CSS = """
    ContextMenu {
        display: none;
        height: auto;
        background: $requiem-bg-recessed;
        border: solid $requiem-accent;
        padding: 1 0;
        box-shadow: 2 2 0 #0C0A0B;
    }
    .cm-item {
        height: 1;
        padding: 0 2;
        color: $requiem-text-muted;
    }
    .cm-item.selected {
        background: $requiem-bg-elevated;
        color: $requiem-text;
    }
    .cm-disabled {
        color: $requiem-text-muted;
        text-style: italic;
    }
    """

    BINDINGS = [
        Binding("up", "move_up", "Up", show=False),
        Binding("down", "move_down", "Down", show=False),
        Binding("enter", "activate", "Select"),
        Binding("g", "jump_first", "Top", show=False),
        Binding("G", "jump_last", "Bottom", show=False),
        Binding("escape", "hide", "Close"),
    ]

    def __init__(self, style: MenuStyle | None = None) -> None:
        MenuBase.__init__(self, id="context-menu")
        Vertical.__init__(self)
        self._style = style or MenuStyle.for_theme()
        self._cmds: list[MenuCommand] = []
        self._registry: MenuRegistry | None = None

    @property
    def style(self) -> MenuStyle:
        return self._style

    def set_items(self, items: list[MenuCommand], registry: MenuRegistry | None = None) -> None:
        """Repopulate the context menu without rebuilding."""
        self._cmds = list(items)
        self._registry = registry
        self._sel_idx = 0
        self._invalidate()

    def _items(self) -> list[MenuCommand]:
        return self._cmds

    def compose(self) -> ComposeResult:
        yield Vertical(id="cm-list")

    def on_mount(self) -> None:
        self._invalidate()

    # ── show / hide / position ────────────────────────────────────────

    def show(self, anchor_x: int, anchor_y: int, viewport_w: int = 80, viewport_h: int = 24) -> None:
        """Position the menu at (anchor_x, anchor_y) in terminal cells.

        Clamps so the menu stays fully on-screen: if the anchor would
        push the menu off the right edge, shift left; off the bottom,
        shift up.
        """
        self._sel_idx = 0
        self._invalidate()
        # Estimate menu size: width ~ max label length + hint + padding,
        # height ~ item count + 2 (borders).
        menu_h = len(self._cmds) + 2
        menu_w = 30  # conservative; caller can override

        x = anchor_x
        y = anchor_y
        if x + menu_w > viewport_w:
            x = max(0, viewport_w - menu_w)
        if y + menu_h > viewport_h:
            y = max(0, viewport_h - menu_h)

        self.styles.offset = (x, y)
        self.styles.display = "block"
        self._bump_frame()

    def hide(self) -> None:
        self.styles.display = "none"

    def open(self) -> None:
        self.styles.display = "block"

    def close(self) -> None:
        self.hide()

    # ── render ────────────────────────────────────────────────────────

    def _invalidate(self) -> None:
        if not self.is_mounted:
            return
        self._bump_frame()
        box = self.query_one("#cm-list", Vertical)
        box.remove_children()
        for i, cmd in enumerate(self._cmds):
            cls = "cm-item selected" if i == self._sel_idx else "cm-item"
            if not cmd.enabled:
                cls += " cm-disabled"
            icon = f"{cmd.icon}  " if cmd.icon else "   "
            hint = f"  {cmd.hint}" if cmd.hint else ""
            text = f"{icon}{cmd.label}{hint}"
            box.mount(Static(text, classes=cls))

    # ── navigation ───────────────────────────────────────────────────

    def action_move_up(self) -> None:
        self._typeahead_reset()
        if self._cmds:
            self._sel_idx = max(0, self._sel_idx - 1)
            self._invalidate()

    def action_move_down(self) -> None:
        self._typeahead_reset()
        if self._cmds:
            self._sel_idx = min(len(self._cmds) - 1, self._sel_idx + 1)
            self._invalidate()

    def action_activate(self) -> None:
        if not self._cmds:
            return
        cmd = self._cmds[self._sel_idx]
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
                logger.exception("Context action %r failed", cmd.id)
        self.hide()
        self.post_message(Selected(cmd.id, self))

    def on_key(self, event: Any) -> None:
        if event.is_printable and not event.character.isspace():
            self._typeahead_feed(event.character)
            event.stop()
