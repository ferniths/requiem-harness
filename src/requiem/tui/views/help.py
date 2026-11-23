"""Help view with keyboard shortcuts and CLI reference."""

from __future__ import annotations

from typing import Any, cast
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

HELP_LINES = [
    ("Key Bindings", "header"),
    ("  Ctrl+P         Command palette", "key"),
    ("  Ctrl+Q         Quit", "key"),
    ("  Ctrl+C         Cancel current operation", "key"),
    ("  Ctrl+Enter     Submit chat message", "key"),
    ("  Shift+Enter    Newline in composer", "key"),
    ("  Esc            Close dialog / go back", "key"),
    ("  F1–F7          Navigate main sections", "key"),
    ("  Tab / Shift+Tab  Cycle focusable controls", "key"),
    ("", ""),
    ("Sections", "header"),
    ("  Chat            Primary conversation workspace", "desc"),
    ("  Agents          Agent monitoring dashboard", "desc"),
    ("  Workflows       Workflow definitions and execution", "desc"),
    ("  Providers       Connection and credential management", "desc"),
    ("  Logs            Live operational log viewer", "desc"),
    ("  Settings        Interactive configuration", "desc"),
    ("  Appearance      Theme selection and preview", "desc"),
    ("", ""),
    ("CLI Commands", "header"),
    ("  requiem check         Verify installation", "desc"),
    ("  requiem init          Create project structure", "desc"),
    ("  requiem list-providers  Show configured providers", "desc"),
    ("  requiem test <id>     Test a provider connection", "desc"),
    ("  requiem run <path>    Run a workflow headlessly", "desc"),
    ("", ""),
    ("Configuration", "header"),
    ("  Config file:  ~/.config/requiem/requiem/config.toml", "desc"),
    ("  Credentials:  OS keyring (Windows/macOS/Linux)", "desc"),
    ("  Project:      .requiem/ in your project root", "desc"),
]


class HelpView(Vertical):
    """Help and reference view."""

    view_id = "help"
    view_label = "Help"
    view_group = "Management"

    def compose(self) -> ComposeResult:
        with Vertical(id="req-help-layout"):
            yield Static("Help", classes="req-section-title")
            yield Static("", id="req-help-content")

    def on_mount(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        from rich.text import Text

        p: Any = cast(Any, getattr(self.app, "_theme_mgr", None)).palette
        gold = p.secondary_accent
        muted = p.muted_ash

        lines: list[Text] = []
        for text, role in HELP_LINES:
            if not text:
                lines.append(Text(""))
            elif role == "header":
                lines.append(Text(text, style=f"bold {gold}"))
            elif role == "key":
                lines.append(Text(text, style=muted))
            else:
                lines.append(Text(text, style=muted))

        content = self.query_one("#req-help-content")
        content.mount(Static("\n".join(str(t) for t in lines)))
