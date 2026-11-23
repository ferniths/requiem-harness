"""Menu command registry and data model.

Menus in the REQUIEM TUI are data-driven: each menu is built from a
``list[MenuCommand]`` rather than hand-written rows. A ``MenuRegistry``
lets other code register named callables so a menu item can reference
``"save"`` by name instead of holding a bound method.

This module is the shared foundation for every menu widget: the launcher,
the sub-menu tree, the context menu, and the selector / check menus all
render ``MenuCommand`` instances.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("requiem.tui.menus.commands")


@dataclass(frozen=True)
class MenuCommand:
    """A single selectable menu item.

    Attributes:
        id: Unique stable identifier used as the selection key.
        label: Human-readable text shown in the row.
        hint: Right-aligned shortcut hint, e.g. ``"F1"`` or ``"Ctrl+P"``.
        category: Grouping label; rows are rendered under a section header
            when their category changes. Empty string means no header.
        enabled: If False the row is rendered dimmed and is not selectable.
        icon: Leading 1-2 char glyph shown before the label.
        action: A callable to invoke on selection, or a string command
            name resolved against a :class:`MenuRegistry`, or ``None``.
    """

    id: str
    label: str
    hint: str = ""
    category: str = ""
    enabled: bool = True
    icon: str = ""
    action: Callable[..., Any] | str | None = None


@dataclass
class _RegisteredAction:
    """Internal wrapper for a registry entry."""

    fn: Callable[..., Any]
    name: str


class MenuRegistry:
    """Resolves string command names to callables.

    Usage::

        registry = MenuRegistry()
        registry.register("save", do_save, "Save the current state")
        # ...
        cmd = MenuCommand(id="save", label="Save", action="save")
        cmd.action  # -> still "save" (string)
        registry.resolve(cmd)  # -> the bound do_save callable
    """

    def __init__(self) -> None:
        self._actions: dict[str, _RegisteredAction] = {}

    def register(self, name: str, fn: Callable[..., Any], description: str = "") -> None:
        """Register a named action. Idempotent: re-registering replaces."""
        self._actions[name] = _RegisteredAction(fn=fn, name=name)
        logger.debug("Registered menu action %r", name)

    def is_registered(self, name: str) -> bool:
        """Return True if *name* is a known action id."""
        return name in self._actions

    def get(self, name: str) -> Callable[..., Any] | None:
        """Return the registered callable, or None."""
        entry = self._actions.get(name)
        return entry.fn if entry else None

    def resolve(self, command: MenuCommand) -> Callable[..., Any] | None:
        """Resolve a command's action to a callable.

        If ``command.action`` is already a callable, return it as-is.
        If it is a string, look it up in this registry. Return ``None``
        when the string is not registered (caller treats it as disabled).
        """
        act = command.action
        if act is None:
            return None
        if callable(act):
            return act
        if isinstance(act, str):
            return self.get(act)
        # act is neither None, callable, nor str — treat as disabled.
        return None  # type: ignore[unreachable]

    @property
    def names(self) -> list[str]:
        return sorted(self._actions.keys())


class SubMenuNode:
    """A node in a :class:`~requiem.tui.menus.tree.SubMenu` tree.

    Attributes:
        id: Stable node identifier.
        label: Row text.
        children: Lazy list of child nodes. An empty list means leaf.
        action: Callable or command-name string fired when this leaf is
            selected (ignored if children exist).
        enabled: Selectable state.
        icon: Leading glyph.
    """

    __slots__ = ("id", "label", "children", "action", "enabled", "icon")

    def __init__(
        self,
        id: str,
        label: str,
        children: list["SubMenuNode"] | None = None,
        action: Callable[..., Any] | str | None = None,
        enabled: bool = True,
        icon: str = "",
    ) -> None:
        self.id = id
        self.label = label
        self.children: list[SubMenuNode] = children if children is not None else []
        self.action = action
        self.enabled = enabled
        self.icon = icon
