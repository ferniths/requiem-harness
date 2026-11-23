"""Menu demo application — exercises every menu widget in one TUI.

Run with::

    python -m requiem.tui.menus.app_demo

Layout:
    Left rail  — SubMenu tree (File / Edit / View)
    Center     — a list of "files" that right-clicks into a ContextMenu
    Right rail — a SelectorMenu (theme) and a CheckMenu (filters)
    Modal      — Ctrl+P opens a ModalMenuScreen launcher

Every action is a registry-resolved callable that logs to a status panel,
so you can watch each menu fire without a backend.
"""

from __future__ import annotations

import logging
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Static

from requiem.tui.menus.commands import MenuCommand, MenuRegistry, SubMenuNode
from requiem.tui.menus.context import ContextMenu
from requiem.tui.menus.screen import ModalMenuScreen
from requiem.tui.menus.selector import CheckMenu, CheckToggled, RadioSelected, SelectorMenu
from requiem.tui.menus.styles import MenuStyle
from requiem.tui.menus.tree import SubMenu

logger = logging.getLogger("requiem.tui.menus.demo")


def _make_commands() -> list[MenuCommand]:
    return [
        MenuCommand(id="save", label="Save", hint="Ctrl+S", category="File", icon="◈"),
        MenuCommand(id="open", label="Open…", hint="Ctrl+O", category="File", icon="⊕"),
        MenuCommand(id="export", label="Export", hint="Ctrl+E", category="File", icon="⇱"),
        MenuCommand(id="undo", label="Undo", hint="Ctrl+Z", category="Edit", icon="↶"),
        MenuCommand(id="redo", label="Redo", hint="Ctrl+Y", category="Edit", icon="↷"),
        MenuCommand(id="find", label="Find…", hint="Ctrl+F", category="Edit", icon="◎"),
        MenuCommand(id="theme", label="Cycle theme", hint="F7", category="View", icon="◍"),
        MenuCommand(id="quit", label="Quit", hint="Ctrl+Q", category="File", icon="✕"),
    ]


def _make_tree() -> list[SubMenuNode]:
    return [
        SubMenuNode(
            id="file", label="File", icon="◈",
            children=[
                SubMenuNode(id="file-new", label="New", action="save"),
                SubMenuNode(id="file-open", label="Open…", action="open"),
                SubMenuNode(
                    id="file-export", label="Export",
                    children=[
                        SubMenuNode(id="export-pdf", label="PDF…", action="export"),
                        SubMenuNode(id="export-md", label="Markdown", action="export"),
                    ],
                ),
            ],
        ),
        SubMenuNode(
            id="edit", label="Edit", icon="✎",
            children=[
                SubMenuNode(id="edit-undo", label="Undo", action="undo"),
                SubMenuNode(id="edit-redo", label="Redo", action="redo"),
            ],
        ),
        SubMenuNode(
            id="view", label="View", icon="◧",
            children=[
                SubMenuNode(id="view-theme", label="Cycle theme", action="theme"),
            ],
        ),
    ]


def _make_context_items() -> list[MenuCommand]:
    return [
        MenuCommand(id="ctx-open", label="Open", icon="⊕"),
        MenuCommand(id="ctx-copy", label="Copy path", icon="⧉"),
        MenuCommand(id="ctx-rename", label="Rename…", icon="✎"),
        MenuCommand(id="ctx-delete", label="Delete", icon="✕"),
    ]


_FILE_NAMES = ["main.py", "cli.py", "config.toml", "README.md", "pyproject.toml"]


class MenuDemoApp(App[None]):
    """Demo shell wiring together every menu widget."""

    TITLE = "REQUIEM Menu Demo"
    CSS = """
    MenuDemoApp {
        background: $requiem-bg;
        color: $requiem-text;
    }
    #demo-body {
        height: 1fr;
    }
    #demo-rail {
        width: 34;
        height: 1fr;
        background: $requiem-bg-recessed;
        border-right: solid $requiem-border;
    }
    #demo-center {
        width: 1fr;
        height: 1fr;
        padding: 1;
    }
    #demo-right {
        width: 34;
        height: 1fr;
        background: $requiem-bg-recessed;
        border-left: solid $requiem-border;
    }
    #demo-log {
        height: 3;
        background: $requiem-bg-recessed;
        border-top: solid $requiem-border;
        padding: 0 2;
        color: $requiem-text-muted;
    }
    .rail-header {
        color: $requiem-text;
        text-style: bold;
        padding: 1 2 0 2;
    }
    .file-row {
        height: 1;
        padding: 0 2;
        color: $requiem-text;
    }
    """

    BINDINGS = [
        Binding("ctrl+p", "open_launcher", "Launcher"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def get_css_variables(self) -> dict[str, str]:
        base = super().get_css_variables()
        base.update(MenuStyle.for_theme().css_variables())
        return base

    def __init__(self) -> None:
        super().__init__()
        self._menu_registry = MenuRegistry()
        self._log_buf: list[str] = []
        self._ctx_menu: ContextMenu | None = None
        self._theme_menu: SelectorMenu | None = None
        self._filter_menu: CheckMenu | None = None
        self._tree: SubMenu | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="demo-body"):
            with Vertical(id="demo-rail"):
                yield Static("MENU TREE", classes="rail-header")
                # Tree is mounted in on_mount after registry setup
                yield Static("(tree loads on mount)")
                yield Static("")
                yield Static("Right-click a file\nin the center pane\nfor context menu.",
                             classes="rail-header")
            with VerticalScroll(id="demo-center"):
                yield Static("Files — right-click a row", classes="rail-header")
                for name in _FILE_NAMES:
                    yield Static(
                        f"  ◈  {name}",
                        id=f"file-{name.replace('.', '_')}",
                        classes="file-row",
                    )
            with Vertical(id="demo-right"):
                yield Static("THEME (radio)", classes="rail-header")
                yield Static("FILTERS (checkbox)", classes="rail-header")
        yield Static("", id="demo-log")

    def on_mount(self) -> None:
        self._menu_registry.register("save", self._action_save, "Save state")
        self._menu_registry.register("open", self._action_open, "Open a file")
        self._menu_registry.register("export", self._action_export, "Export")
        self._menu_registry.register("undo", self._action_undo, "Undo")
        self._menu_registry.register("redo", self._action_redo, "Redo")
        self._menu_registry.register("theme", self._action_theme, "Cycle theme")
        self._menu_registry.register("quit", self._action_quit, "Quit")
        self._menu_registry.register("ctx-open", self._action_ctx_open, "Ctx open")
        self._menu_registry.register("ctx-copy", self._action_ctx_copy, "Ctx copy")
        self._menu_registry.register("ctx-rename", self._action_ctx_rename, "Ctx rename")
        self._menu_registry.register("ctx-delete", self._action_ctx_delete, "Ctx delete")

        # Replace placeholder tree with real one
        rail = self.query_one("#demo-rail", Vertical)
        for child in list(rail.children):
            if isinstance(child, Static) and "(tree loads on mount)" in str(child.render()):
                rail.remove_children([child])
                break
        tree = SubMenu(style=MenuStyle.for_theme())
        tree.set_nodes(_make_tree())
        self._tree = tree
        rail.mount(tree)

        # Right rail menus
        right = self.query_one("#demo-right", Vertical)
        self._theme_menu = SelectorMenu(
            [
                MenuCommand(id="classic", label="Classic"),
                MenuCommand(id="blue", label="Blue"),
                MenuCommand(id="purple", label="Purple"),
                MenuCommand(id="magenta", label="Magenta"),
                MenuCommand(id="grey", label="Grey"),
            ],
            selected="classic",
        )
        self._filter_menu = CheckMenu(
            [
                MenuCommand(id="debug", label="Debug logs"),
                MenuCommand(id="info", label="Info logs"),
                MenuCommand(id="warn", label="Warnings"),
                MenuCommand(id="error", label="Errors", enabled=False),
            ],
            checked=["info", "warn"],
        )
        right.mount(self._theme_menu)
        right.mount(self._filter_menu)

        # Context menu as overlay
        self._ctx_menu = ContextMenu()
        self._ctx_menu.set_items(_make_context_items(), self._menu_registry)
        self.mount(self._ctx_menu)

        self._status("menu demo ready — press Ctrl+P for launcher")

    # ── message handlers ──────────────────────────────────────────────

    def on_radio_selected(self, msg: RadioSelected) -> None:
        self._status(f"theme → {msg.command_id}")

    def on_check_toggled(self, msg: CheckToggled) -> None:
        self._status(f"filter {msg.command_id} {'on' if msg.checked else 'off'}")

    def on_mouse_down(self, msg: Any) -> None:
        """Right-click on a file row opens the context menu anchored at the cursor."""
        if getattr(msg, "button", 0) != 3:
            return
        sender = msg.widget
        sender_id = getattr(sender, "id", "")
        if sender_id.startswith("file-") and self._ctx_menu is not None:
            x = getattr(msg, "x", 40)
            y = getattr(msg, "y", 10)
            self._ctx_menu.show(x, y, viewport_w=self.size.width, viewport_h=self.size.height)

    # ── modal launcher ────────────────────────────────────────────────

    def action_open_launcher(self) -> None:
        self.push_screen(
            ModalMenuScreen(
                commands=_make_commands(),
                registry=self._menu_registry,
                title="Commands",
            ),
            callback=self._on_launcher_closed,
        )

    def _on_launcher_closed(self, selected: str | None) -> None:
        self._status(f"launcher → {selected or '(closed)'}")

    # ── registered actions ────────────────────────────────────────────

    def _status(self, text: str) -> None:
        self._log_buf.append(text)
        line = "   ".join(self._log_buf[-3:])
        try:
            widget = self.query_one("#demo-log", Static)
            widget.update(line)
        except Exception:
            pass

    def _action_save(self) -> None:
        self._status("action: save")

    def _action_open(self) -> None:
        self._status("action: open")

    def _action_export(self) -> None:
        self._status("action: export")

    def _action_undo(self) -> None:
        self._status("action: undo")

    def _action_redo(self) -> None:
        self._status("action: redo")

    def _action_theme(self) -> None:
        if self._theme_menu is not None:
            menu = self._theme_menu
            names = [c.id for c in menu._commands]
            cur = names.index(menu.selected) if menu.selected in names else 0
            menu.selected = names[(cur + 1) % len(names)]
            self._status(f"action: theme → {menu.selected}")

    def _action_quit(self) -> None:
        self._status("action: quit")
        self.exit()

    def _action_ctx_open(self) -> None:
        self._status("ctx: open")

    def _action_ctx_copy(self) -> None:
        self._status("ctx: copy path")

    def _action_ctx_rename(self) -> None:
        self._status("ctx: rename")

    def _action_ctx_delete(self) -> None:
        self._status("ctx: delete")


def run() -> None:
    MenuDemoApp().run()


if __name__ == "__main__":
    run()
