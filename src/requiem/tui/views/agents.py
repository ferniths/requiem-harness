"""Agent dashboard view.

Displays agent status from the backend. Since no agents package exists yet,
this view shows an honest empty state with a link to Workflows.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

logger = logging.getLogger("requiem.tui.views.agents")


class AgentsView(Vertical):
    """Agent monitoring dashboard.

    Currently shows the honest empty state since the multi-agent backend
    is not yet implemented. When agents are running, this view will display
    live agent cards with status, task, tokens, and recent activity.
    """

    view_id = "agents"
    view_label = "Agents"
    view_group = "Workspace"

    def compose(self) -> ComposeResult:
        with Vertical(id="req-agents-layout"):
            yield Static("Agent Dashboard", classes="req-section-title")
            yield Static("", id="req-agents-content")

    def on_mount(self) -> None:
        self._render_state()

    def _render_state(self) -> None:
        content: Any = self.query_one("#req-agents-content")
        content.remove_children("*")

        p: Any = cast(Any, getattr(self.app, "_theme_mgr", None)).palette
        accent = p.primary_accent
        gold = p.secondary_accent
        muted = p.muted_ash

        from rich.panel import Panel
        from rich.text import Text

        lines = [
            Text("AGENT STATUS", style=f"bold {gold}"),
            Text(""),
            Text("  Running       0", style=muted),
            Text("  Waiting       0", style=muted),
            Text("  Completed     0", style=muted),
            Text("  Failed        0", style=muted),
            Text(""),
            Text("No active agents.", style=f"bold {accent}"),
            Text("Agents appear when a workflow is running.", style=muted),
            Text(""),
            Text("→ Press F3 to open Workflow Center", style=accent),
        ]

        content.mount(Static(Panel("\n".join(str(t) for t in lines), border_style=accent, padding=(1, 2))))
