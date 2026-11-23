"""Shared menu-base behaviour.

:class:`MenuBase` is a mixin (composed with ``Vertical`` or ``Widget``) that
provides the common machinery every menu widget needs:

- selection index tracking and ``selected`` accessors
- type-ahead (forward-jump on typed characters with a 500ms reset window)
- jump-to-first/last (``g`` / ``G``)
- a ``Selected`` message subclass for parent handlers
- frame-counter guard so stale animation updates are dropped after
  the widget unmounts or a newer frame supersedes an older one

Subclasses implement :meth:`_items` (the list of selectable rows) and
:meth:`_on_item_activated` (what to do when a row is confirmed).
"""

from __future__ import annotations

import logging
import time
from typing import Any, cast

from textual.message import Message
from textual.widget import Widget

logger = logging.getLogger("requiem.tui.menus.base")

#: Type-ahead buffer expiry in seconds.
_TYPEAHEAD_TTL = 0.5


class Selected(Message):
    """Posted by a menu when the user confirms a selection.

    Subclasses may carry extra fields; the handler name is derived from
    the class name (Textual convention: ``on_<snake_case_class_name>``).
    """

    def __init__(self, selected_id: str, source: Widget) -> None:
        self.selected_id = selected_id
        self.source = source
        super().__init__()


class MenuBase:
    """Mixin adding selection, type-ahead, and jump-to behavior.

    Compose with a Textual container, e.g.::

        class LauncherMenu(Vertical, MenuBase):
            ...
    """

    # Set in subclass __init__
    _sel_idx: int
    _typeahead_buf: str
    _typeahead_last: float
    _frame: int

    def __init__(self, **kwargs: Any) -> None:
        # MenuBase is a plain mixin; it does NOT call object.__init__.
        # Subclasses that mix it with a Textual container call the
        # container's __init__ separately, e.g.:
        #     MenuBase.__init__(self, id="x"); Vertical.__init__(self)
        self._sel_idx = 0
        self._typeahead_buf = ""
        self._typeahead_last = 0.0
        self._frame = 0

    # ── selection accessors ────────────────────────────────────────────

    @property
    def selected(self) -> str | None:
        """Return the id of the currently highlighted row, or None."""
        items = self._items()
        if not items:
            return None
        return cast("str | None", items[min(self._sel_idx, len(items) - 1)].id)

    @property
    def selected_item(self) -> Any | None:
        """Return the full row data object for the highlighted index."""
        items = self._items()
        if not items:
            return None
        return items[min(self._sel_idx, len(items) - 1)]

    # ── type-ahead ────────────────────────────────────────────────────

    def _typeahead_reset(self) -> None:
        self._typeahead_buf = ""

    def _typeahead_feed(self, char: str) -> None:
        """Feed a typed character into the type-ahead buffer and advance."""
        now = time.monotonic()
        if now - self._typeahead_last > _TYPEAHEAD_TTL:
            self._typeahead_buf = ""
        self._typeahead_buf += char.lower()
        self._typeahead_last = now
        self._jump_to_typeahead()

    def _jump_to_typeahead(self) -> None:
        items = self._items()
        if not items or not self._typeahead_buf:
            return
        buf = self._typeahead_buf
        for i, item in enumerate(items):
            if i == self._sel_idx:
                continue
            label = getattr(item, "label", "").lower()
            if label.startswith(buf):
                self._sel_idx = i
                self._invalidate()
                return

    # ── jump-to-first/last ────────────────────────────────────────────

    def action_jump_first(self) -> None:
        self._sel_idx = 0
        self._invalidate()

    def action_jump_last(self) -> None:
        items = self._items()
        if items:
            self._sel_idx = len(items) - 1
        self._invalidate()

    # ── frame guard ───────────────────────────────────────────────────

    def _bump_frame(self) -> int:
        self._frame += 1
        return self._frame

    def _frame_valid(self, frame: int) -> bool:
        """Return True if *frame* is the current frame (not superseded)."""
        return frame == self._frame

    # ── required subclass interface ────────────────────────────────────

    def _items(self) -> list[Any]:
        """Return the list of selectable row objects. Implemented by subclass."""
        raise NotImplementedError

    def _invalidate(self) -> None:
        """Re-render the rows after a selection change. Implemented by subclass."""
        raise NotImplementedError
