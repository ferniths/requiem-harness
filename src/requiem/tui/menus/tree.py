"""Sub-menu tree — two-column hierarchy with expandable children.

A left/right tree where each node can expand to reveal children,
indented by 2 spaces per depth. Used for "File → Export → PDF"
style hierarchies. Supports lazy children and "no sub-items" leaves
that are directly selectable.

Keys:
    Up/Down  move highlight within the visible (expanded) path
    Enter    select a leaf, or toggle-expand a branch
    → / o    open (expand) a branch's children
    Esc      close / go back one level
"""

from __future__ import annotations

import logging
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Static

from requiem.tui.menus.base import MenuBase, Selected
from requiem.tui.menus.commands import SubMenuNode
from requiem.tui.menus.styles import MenuStyle

logger = logging.getLogger("requiem.tui.menus.tree")


class SubMenu(Vertical, MenuBase):
    """Two-column expandable tree menu.

    Compose into an app and call :meth:`set_nodes` to populate.
    Selection is tracked on the *flattened visible* list, so Up/Down
    only moves within currently-expanded nodes.
    """

    CSS = """
    SubMenu {
        height: auto;
        max-height: 18;
        background: $requiem-bg-recessed;
        border: solid $requiem-border;
        padding: 1 0;
    }
    .sm-row {
        height: 1;
        padding: 0 2;
        color: $requiem-text-muted;
    }
    .sm-row.selected {
        background: $requiem-bg-elevated;
        color: $requiem-text;
    }
    .sm-branch {
        color: $requiem-accent;
        text-style: bold;
    }
    .sm-leaf {
        color: $requiem-text;
    }
    .sm-empty {
        color: $requiem-text-muted;
        padding: 0 4;
        text-style: italic;
    }
    """

    BINDINGS = [
        Binding("up", "move_up", "Up", show=False),
        Binding("down", "move_down", "Down", show=False),
        Binding("enter", "activate", "Select"),
        Binding("right", "expand", "Open", show=False),
        Binding("o", "expand", "Open", show=False),
        Binding("g", "jump_first", "Top", show=False),
        Binding("G", "jump_last", "Bottom", show=False),
        Binding("escape", "collapse", "Back", show=False),
    ]

    def __init__(self, style: MenuStyle | None = None) -> None:
        MenuBase.__init__(self, id="submenu-tree")
        Vertical.__init__(self)
        self._style = style or MenuStyle.for_theme()
        self._roots: list[SubMenuNode] = []
        #: Set of node ids currently expanded.
        self._expanded: set[str] = set()

    @property
    def style(self) -> MenuStyle:
        return self._style

    def set_nodes(self, roots: list[SubMenuNode]) -> None:
        """Populate the tree with a fresh root list."""
        self._roots = list(roots)
        self._expanded = set()
        self._sel_idx = 0
        self._invalidate()

    # ── visible-flattened data source ────────────────────────────────

    def _visible_nodes(self) -> list[tuple[SubMenuNode, int]]:
        """Return the flattened (node, depth) list honoring _expanded."""
        out: list[tuple[SubMenuNode, int]] = []

        def walk(nodes: list[SubMenuNode], depth: int) -> None:
            for node in nodes:
                out.append((node, depth))
                if node.children and node.id in self._expanded:
                    walk(node.children, depth + 1)

        walk(self._roots, 0)
        return out

    def _items(self) -> list[SubMenuNode]:
        return [n for n, _d in self._visible_nodes()]

    # ── compose / render ─────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Vertical(id="sm-list")

    def on_mount(self) -> None:
        self._invalidate()

    def _invalidate(self) -> None:
        if not self.is_mounted:
            # Not mounted yet (e.g. set_nodes called in parent's on_mount
            # before this widget is composed). on_mount will render.
            return
        self._bump_frame()
        box = self.query_one("#sm-list", Vertical)
        box.remove_children()

        visible = self._visible_nodes()
        if not visible:
            box.mount(Static("  No items.", classes="sm-empty"))
            return

        for i, (node, depth) in enumerate(visible):
            indent = "    " * depth
            is_branch = bool(node.children)
            cls = "sm-row selected" if i == self._sel_idx else "sm-row"
            marker = ""
            if is_branch:
                marker = "▾ " if node.id in self._expanded else "▸ "
            prefix = f"{marker} {node.icon} " if marker or node.icon else "   "
            row_cls = "sm-branch" if is_branch else "sm-leaf"
            box.mount(
                Static(
                    f"{indent}{prefix}{node.label}",
                    classes=f"{cls} {row_cls}",
                ),
            )

    # ── navigation ───────────────────────────────────────────────────

    def _clamp(self) -> None:
        items = self._items()
        if not items:
            self._sel_idx = 0
            return
        self._sel_idx = max(0, min(self._sel_idx, len(items) - 1))

    def action_move_up(self) -> None:
        self._typeahead_reset()
        self._sel_idx = max(0, self._sel_idx - 1)
        self._invalidate()

    def action_move_down(self) -> None:
        self._typeahead_reset()
        items = self._items()
        if items:
            self._sel_idx = min(len(items) - 1, self._sel_idx + 1)
        self._invalidate()

    def action_expand(self) -> None:
        """Expand the branch under the cursor (or select a leaf)."""
        items = self._items()
        if not items:
            return
        node = items[self._sel_idx]
        if node.children:
            self._expanded.add(node.id)
            self._invalidate()
        else:
            self.action_activate()

    def action_collapse(self) -> None:
        """Collapse the topmost expanded ancestor of the cursor."""
        items = self._items()
        if not items:
            return
        node = items[self._sel_idx]
        visible = self._visible_nodes()
        node_depth = next((d for n, d in visible if n.id == node.id), 0)
        if node.children:
            self._expanded.discard(node.id)
        else:
            for j in range(self._sel_idx - 1, -1, -1):
                parent, parent_depth = visible[j]
                if parent_depth < node_depth and parent.children:
                    self._expanded.discard(parent.id)
                    break
        self._invalidate()

    def action_activate(self) -> None:
        """Select a leaf (or toggle a branch)."""
        items = self._items()
        if not items:
            return
        node = items[self._sel_idx]
        if not node.enabled:
            return
        if node.children:
            # Toggle
            if node.id in self._expanded:
                self._expanded.discard(node.id)
            else:
                self._expanded.add(node.id)
            self._invalidate()
            return

        # Leaf: fire action
        fn = node.action
        if callable(fn):
            try:
                fn()
            except Exception:
                logger.exception("Tree action for %r failed", node.id)
        elif isinstance(fn, str):
            # String command names are resolved by the parent's registry;
            # we just post the selection and let the app handle it.
            pass
        self.post_message(Selected(node.id, self))

    def on_key(self, event: Any) -> None:
        if event.is_printable and not event.character.isspace():
            self._typeahead_feed(event.character)
            event.stop()

    # ── public API ───────────────────────────────────────────────────

    def open(self) -> None:
        self._invalidate()

    def close(self) -> None:
        self._expanded = set()
        self._sel_idx = 0
        self._invalidate()
