"""Workflow center view.

Lists available workflow files from .requiem/workflows/ and the config
project root. Shows workflow definitions without faking execution.
"""

from __future__ import annotations

import logging
import pathlib
from typing import Any, cast

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

logger = logging.getLogger("requiem.tui.views.workflows")

_WORKFLOW_EXTS = (".toml", ".yaml", ".yml", ".json")


class WorkflowsView(Vertical):
    """Workflow management center."""

    view_id = "workflows"
    view_label = "Workflows"
    view_group = "Workspace"

    def compose(self) -> ComposeResult:
        with Vertical(id="req-workflows-layout"):
            yield Static("Workflow Center", classes="req-section-title")
            yield Static("", id="req-workflows-content")

    def on_mount(self) -> None:
        self._refresh()

    def _find_workflow_dir(self) -> pathlib.Path | None:
        """Look for .requiem/workflows/ in CWD and parent directories."""
        search_root = pathlib.Path.cwd()
        while True:
            wf_dir = search_root / ".requiem" / "workflows"
            if wf_dir.is_dir():
                return wf_dir
            parent = search_root.parent
            if parent == search_root:
                break
            search_root = parent
        return None

    def _refresh(self) -> None:
        content = self.query_one("#req-workflows-content")
        content.remove_children("*")

        p: Any = cast(Any, getattr(self.app, "_theme_mgr", None)).palette
        accent = p.primary_accent
        muted = p.muted_ash

        wf_dir = self._find_workflow_dir()

        if wf_dir is None:
            from rich.text import Text
            lines = [
                Text("No workflow directory found.", style=f"bold {accent}"),
                Text("", ),
                Text("Run `requiem init` to create .requiem/workflows/.", style=muted),
                Text("Or create workflow definitions manually.", style=muted),
            ]
            content.mount(Static("\n".join(str(t) for t in lines)))
            return

        files = sorted(
            f for f in wf_dir.iterdir()
            if f.is_file() and f.suffix in _WORKFLOW_EXTS
        )

        if not files:
            from rich.text import Text
            lines = [
                Text("No workflows defined.", style=f"bold {accent}"),
                Text("", ),
                Text(f"Workflow directory: {wf_dir}", style=muted),
                Text("Create a .toml or .yaml file to define a workflow.", style=muted),
            ]
            content.mount(Static("\n".join(str(t) for t in lines)))
            return

        from rich.text import Text
        lines = []
        for f in files:
            lines.append(Text(f"◈ {f.stem}", style=f"bold {accent}"))
            lines.append(Text(f"  {f.name}", style=muted))
        lines.append(Text("", ))
        lines.append(Text("Workflow execution engine is not yet available.", style=muted))
        lines.append(Text("Press Ctrl+P to open the command palette.", style=muted))

        content.mount(Static("\n".join(str(t) for t in lines)))
