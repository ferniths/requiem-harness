"""Tests for the REQUIEM menu kit.

Covers the command registry (resolve, idempotent register, disabled) and one
pilot-driven test per menu type (launcher, sub-menu tree, context menu,
radio selector, check menu) plus the modal launcher screen.

The menus reference ``$requiem-*`` CSS variables, so every test App uses
:class:`_MenuTestApp`, which supplies them from ``MenuStyle``.
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Vertical

from requiem.tui.menus import (
    CheckMenu,
    CheckToggled,
    ContextMenu,
    LauncherMenu,
    MenuCommand,
    MenuRegistry,
    ModalMenuScreen,
    RadioSelected,
    SelectorMenu,
    SubMenu,
    SubMenuNode,
)
from requiem.tui.menus.base import Selected
from requiem.tui.menus.styles import MenuStyle


class _MenuTestApp(App[None]):
    """Test App that defines the ``$requiem-*`` CSS variables the menus need."""



    def get_css_variables(self) -> dict[str, str]:
        base = super().get_css_variables()
        base.update(MenuStyle.for_theme().css_variables())
        return base


def _cmds() -> list[MenuCommand]:
    return [
        MenuCommand(id="save", label="Save", hint="Ctrl+S"),
        MenuCommand(id="open", label="Open", hint="Ctrl+O"),
        MenuCommand(id="quit", label="Quit", hint="Ctrl+Q", enabled=False),
    ]


# ── registry unit tests ──────────────────────────────────────────────


def test_registry_register_and_get():
    reg = MenuRegistry()
    called: list[str] = []
    reg.register("save", lambda: called.append("save"), "Save")
    fn = reg.get("save")
    assert fn is not None
    fn()
    assert called == ["save"]
    assert reg.is_registered("save")
    assert reg.names == ["save"]


def test_registry_register_is_idempotent_replaces():
    reg = MenuRegistry()
    reg.register("x", lambda: "a", "First")
    reg.register("x", lambda: "b", "Second")
    assert reg.get("x")() == "b"
    assert reg.names == ["x"]


def test_registry_resolve_unknown_string_returns_none():
    reg = MenuRegistry()
    cmd = MenuCommand(id="nope", label="Nope", action="unregistered")
    assert reg.resolve(cmd) is None


def test_registry_resolve_call_action_passthrough():
    def do_save() -> None:
        return None

    cmd = MenuCommand(id="save", label="Save", action=do_save)
    assert MenuRegistry().resolve(cmd) is do_save


def test_registry_resolve_string_action():
    reg = MenuRegistry()
    fired: list[str] = []
    reg.register("go", lambda: fired.append("go"), "Go")
    cmd = MenuCommand(id="go", label="Go", action="go")
    fn = reg.resolve(cmd)
    assert fn is not None
    fn()
    assert fired == ["go"]


def test_registry_resolve_none_action_returns_none():
    cmd = MenuCommand(id="x", label="X", action=None)
    assert MenuRegistry().resolve(cmd) is None


def test_registry_empty_names():
    assert MenuRegistry().names == []


def test_registry_get_unknown_returns_none():
    assert MenuRegistry().get("nothing") is None


# ── launcher menu ────────────────────────────────────────────────────


async def test_launcher_renders_commands():
    class _App(_MenuTestApp):
        def compose(self) -> ComposeResult:
            yield LauncherMenu()

    app = _App()
    async with app.run_test(size=(80, 30)) as pilot:
        lm = app.query_one(LauncherMenu)
        lm.set_commands(_cmds())
        await pilot.pause()
        assert len(lm.query(".lm-item")) == 3


async def test_launcher_filters_on_input():
    from textual.widgets import Input

    class _App(_MenuTestApp):
        def compose(self) -> ComposeResult:
            yield LauncherMenu()

    app = _App()
    async with app.run_test(size=(80, 30)) as pilot:
        lm = app.query_one(LauncherMenu)
        lm.set_commands(_cmds())
        await pilot.pause()
        assert len(lm._filtered) == 3
        app.query_one("#lm-input", Input).value = "op"
        await pilot.pause()
        assert [c.id for c in lm._filtered] == ["open"]


async def test_launcher_empty_filter_shows_placeholder():
    from textual.widgets import Input

    class _App(_MenuTestApp):
        def compose(self) -> ComposeResult:
            yield LauncherMenu()

    app = _App()
    async with app.run_test(size=(80, 30)) as pilot:
        lm = app.query_one(LauncherMenu)
        lm.set_commands(_cmds())
        await pilot.pause()
        app.query_one("#lm-input", Input).value = "zzz-nomatch"
        await pilot.pause()
        assert lm._filtered == []
        assert "No matching commands" in str(lm.query_one(".lm-header").render())


async def test_launcher_no_commands_shows_placeholder():
    class _App(_MenuTestApp):
        def compose(self) -> ComposeResult:
            yield LauncherMenu()

    app = _App()
    async with app.run_test(size=(80, 30)) as pilot:
        lm = app.query_one(LauncherMenu)
        lm.set_commands([])
        await pilot.pause()
        assert "No matching commands" in str(lm.query_one(".lm-header").render())


async def test_launcher_select_posts_message():
    captured: list[Selected] = []

    class _App(_MenuTestApp):
        def compose(self) -> ComposeResult:
            yield LauncherMenu()

        def on_selected(self, event: Selected) -> None:
            captured.append(event)

    app = _App()
    async with app.run_test(size=(80, 30)) as pilot:
        lm = app.query_one(LauncherMenu)
        lm.set_commands(_cmds())
        await pilot.pause()
        lm.action_move_down()
        lm.action_execute()
        await pilot.pause()
        assert captured and captured[0].selected_id == "open"


# ── sub-menu tree ─────────────────────────────────────────────────────


def _tree() -> list[SubMenuNode]:
    return [
        SubMenuNode(
            id="file",
            label="File",
            children=[
                SubMenuNode(id="new", label="New", action="new"),
                SubMenuNode(id="open", label="Open", action="open"),
            ],
        ),
        SubMenuNode(id="help", label="Help", action="help"),
    ]


async def test_tree_expand_and_collapse():
    class _App(_MenuTestApp):
        def compose(self) -> ComposeResult:
            yield SubMenu()

    app = _App()
    async with app.run_test(size=(80, 30)) as pilot:
        sm = app.query_one(SubMenu)
        sm.set_nodes(_tree())
        await pilot.pause()
        assert [n.id for n in sm._items()] == ["file", "help"]
        sm.action_expand()
        assert [n.id for n in sm._items()] == ["file", "new", "open", "help"]
        sm.action_collapse()
        assert [n.id for n in sm._items()] == ["file", "help"]


async def test_tree_moves_selection():
    class _App(_MenuTestApp):
        def compose(self) -> ComposeResult:
            yield SubMenu()

    app = _App()
    async with app.run_test(size=(80, 30)) as pilot:
        sm = app.query_one(SubMenu)
        sm.set_nodes(_tree())
        await pilot.pause()
        assert sm.selected == "file"
        sm.action_move_down()
        assert sm.selected == "help"
        sm.action_move_up()
        assert sm.selected == "file"


# ── context menu ─────────────────────────────────────────────────────


async def test_context_menu_show_and_hide():
    class _App(_MenuTestApp):
        def compose(self) -> ComposeResult:
            with Vertical():
                yield ContextMenu()

    app = _App()
    async with app.run_test(size=(80, 30)) as pilot:
        cm = app.query_one(ContextMenu)
        cm.set_items(_cmds())
        await pilot.pause()
        cm.show(10, 5, 80, 30)
        await pilot.pause()
        assert cm.styles.display == "block"
        cm.hide()
        await pilot.pause()
        assert cm.styles.display == "none"


async def test_context_menu_clamps_to_viewport():
    class _App(_MenuTestApp):
        def compose(self) -> ComposeResult:
            with Vertical():
                yield ContextMenu()

    app = _App()
    async with app.run_test(size=(80, 30)) as pilot:
        cm = app.query_one(ContextMenu)
        cm.set_items(_cmds())
        await pilot.pause()
        cm.show(200, 200, 80, 30)
        await pilot.pause()
        off = cm.styles.offset
        assert off.x.value < 80
        assert off.y.value < 30


# ── radio selector ────────────────────────────────────────────────────


async def test_radio_selector_moves_and_selects():
    captured: list[RadioSelected] = []

    class _App(_MenuTestApp):
        def compose(self) -> ComposeResult:
            yield SelectorMenu(_cmds(), selected="save")

        def on_radio_selected(self, event: RadioSelected) -> None:
            captured.append(event)

    app = _App()
    async with app.run_test(size=(80, 30)) as pilot:
        sm = app.query_one(SelectorMenu)
        await pilot.pause()
        assert sm.selected == "save"
        sm.action_move_down()
        sm.action_activate()
        await pilot.pause()
        assert sm.selected == "open"
        assert captured and captured[0].command_id == "open"


# ── check menu ────────────────────────────────────────────────────────


async def test_check_menu_toggles():
    captured: list[CheckToggled] = []

    class _App(_MenuTestApp):
        def compose(self) -> ComposeResult:
            yield CheckMenu(_cmds(), checked=["save"])

        def on_check_toggled(self, event: CheckToggled) -> None:
            captured.append(event)

    app = _App()
    async with app.run_test(size=(80, 30)) as pilot:
        cm = app.query_one(CheckMenu)
        await pilot.pause()
        assert cm.selected_ids == ["save"]
        cm.action_move_down()
        cm.action_activate()
        await pilot.pause()
        assert "open" in cm.selected_ids
        assert captured


# ── modal menu screen ────────────────────────────────────────────────


async def test_modal_menu_screen_dismisses_with_selection():
    class _App(_MenuTestApp):
        def compose(self) -> ComposeResult:
            yield Vertical()

    registry = MenuRegistry()
    fired: list[str] = []
    registry.register("save", lambda: fired.append("save"), "Save")

    app = _App()
    async with app.run_test(size=(80, 30)) as pilot:
        screen = ModalMenuScreen(commands=_cmds(), registry=registry)
        await app.push_screen(screen)
        await pilot.pause()
        assert isinstance(app.screen_stack[-1], ModalMenuScreen)
        screen._launcher.action_move_down()
        screen._launcher.action_execute()
        await pilot.pause()
        assert screen.selected == "open"


async def test_modal_menu_screen_escape_dismisses_with_none():
    class _App(_MenuTestApp):
        def compose(self) -> ComposeResult:
            yield Vertical()

    app = _App()
    async with app.run_test(size=(80, 30)) as pilot:
        screen = ModalMenuScreen(commands=_cmds(), registry=MenuRegistry())
        await app.push_screen(screen)
        await pilot.pause()
        screen._launcher.action_close()
        await pilot.pause()
        assert screen.selected is None
