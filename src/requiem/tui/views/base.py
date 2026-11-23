"""Base class for REQUIEM workspace views."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static


class BaseView(Vertical):
    """Abstract base for workspace views.

    Each view occupies the full workspace area. The application shell
    swaps views by mounting/unmounting inside the workspace container.
    """

    #: Stable identifier used by the navigation rail.
    view_id: str = ""

    #: Label shown in the navigation rail.
    view_label: str = ""

    #: Optional group label shown above the nav item.
    view_group: str = ""

    def __init__(self) -> None:
        super().__init__(id=self.view_id)

    @property
    def title(self) -> str:
        """Short title shown in the header subtitle."""
        return self.view_label

    def compose(self) -> ComposeResult:
        yield from self._compose_content()

    def _compose_content(self) -> ComposeResult:
        """Override to build view-specific content."""
        yield Static("")

    # -- shared helpers ------------------------------------------------

    def _section_header(self, text: str) -> Static:
        return Static(text, classes="req-section-title")

    def _empty_state(self, title: str, description: str, action_label: str = "") -> Vertical:
        box = Vertical(id=f"empty-{self.view_id}")
        box._add_children(
            Static(title, classes="req-empty-state-title"),
            Static(description, classes="req-empty-state"),
        )
        if action_label:
            box._add_children(Static(action_label, classes="req-empty-state-action"))
        return box
