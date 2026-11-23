"""REQUIEM menu kit — data-driven menu widgets for the TUI.

Public API::

    from requiem.tui.menus import (
        MenuCommand, MenuRegistry, SubMenuNode,
        MenuStyle, LauncherMenu, SubMenu, ContextMenu,
        SelectorMenu, CheckMenu, ModalMenuScreen,
    )
"""

from __future__ import annotations

from requiem.tui.menus.base import MenuBase, Selected
from requiem.tui.menus.commands import MenuCommand, MenuRegistry, SubMenuNode
from requiem.tui.menus.context import ContextMenu
from requiem.tui.menus.launcher import LauncherMenu
from requiem.tui.menus.screen import ModalMenuScreen
from requiem.tui.menus.selector import CheckMenu, CheckToggled, RadioSelected, SelectorMenu
from requiem.tui.menus.styles import MenuStyle
from requiem.tui.menus.tree import SubMenu

__all__ = [
    "MenuBase",
    "Selected",
    "MenuCommand",
    "MenuRegistry",
    "SubMenuNode",
    "MenuStyle",
    "LauncherMenu",
    "SubMenu",
    "ContextMenu",
    "SelectorMenu",
    "CheckMenu",
    "CheckToggled",
    "RadioSelected",
    "ModalMenuScreen",
]
