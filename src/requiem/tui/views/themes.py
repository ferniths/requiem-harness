"""Theme manager view with live preview and persistence.

Replaces the cycle-only themes modal with a proper theme selection
experience that previews immediately and persists to config.
"""

from __future__ import annotations

import logging
from typing import Any

import textual
import textual.events
from textual.containers import Vertical
from textual.app import ComposeResult
from textual.widgets import Label, Static

logger = logging.getLogger("requiem.tui.views.themes")


class ThemesView(Vertical):
    """Theme selection with live preview."""

    view_id = "themes"
    view_label = "Appearance"
    view_group = "Management"

    def __init__(self) -> None:
        super().__init__(id="req-themes-view")

    def compose(self) -> ComposeResult:
        with Vertical(id="req-themes-layout"):
            yield Static("Appearance", classes="req-section-title")
            yield Static("", id="req-themes-preview")
            yield Static("", id="req-themes-list")

    def on_mount(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        from rich.panel import Panel
        from rich.text import Text

        from requiem.themes.palettes import get_theme, list_theme_names

        mgr: Any = getattr(self.app, "_theme_mgr", None)
        active = mgr.name
        p = mgr.palette

        # Preview panel
        preview = self.query_one("#req-themes-preview")
        preview.remove_children("*")

        lines = [
            Text(f"Active theme: {active.upper()}", style=f"bold {p.secondary_accent}"),
            Text("", ),
            Text(f"  Background:  {p.obsidian}  (Obsidian)", style=p.muted_ash),
            Text(f"  Panel:       {p.dark_iron}  (Dark Iron)", style=p.muted_ash),
            Text(f"  Accent:      {p.primary_accent}", style=p.primary_accent),
            Text(f"  Gold:        {p.secondary_accent}", style=p.secondary_accent),
            Text(f"  Text:        {p.ash_white}", style=p.ash_white),
            Text(f"  Muted:       {p.muted_ash}", style=p.muted_ash),
            Text(f"  Border:      {p.iron_border}", style=p.iron_border),
        ]
        preview.mount(Static(Panel("\n".join(str(t) for t in lines), title="  Palette Preview  ", border_style=p.primary_accent)))

        # Theme list
        theme_list = self.query_one("#req-themes-list")
        theme_list.remove_children("*")
        theme_list.mount(Label("Available themes:", classes="req-section-title"))

        for name in list_theme_names():
            palette = get_theme(name)
            marker = "◈" if name == active else "◇"
            swatch = palette.primary_accent
            cls = "req-theme-item active" if name == active else "req-theme-item"
            row = Static(f"{marker}  {name:<12}  accent={swatch}  {palette.description}", id=f"theme-{name}", classes=cls)
            theme_list.mount(row)

        theme_list.mount(Static("", ))
        theme_list.mount(Static("Press Up/Down to preview · Enter to apply · Esc to close", classes="req-empty-state"))

    def action_apply_theme(self, name: str) -> None:
        """Apply and persist a theme."""
        from requiem.config.loader import load_config, save_config
        from requiem.config.paths import user_config_file

        mgr: Any = getattr(self.app, "_theme_mgr", None)
        if name == mgr.name:
            return

        mgr.set_theme(name)
        self.app.theme = name
        self._refresh()

        # Persist
        try:
            cfg = load_config()
            cfg.theme.active = name
            save_config(cfg, user_config_file())
        except Exception:
            logger.debug("Failed to persist theme", exc_info=True)

    def on_key(self, event: textual.events.Key) -> None:
        from requiem.themes.palettes import list_theme_names

        names = list_theme_names()
        mgr: Any = getattr(self.app, "_theme_mgr", None)
        active_idx = names.index(mgr.name) if mgr.name in names else 0

        if event.key == "down":
            target = names[(active_idx + 1) % len(names)]
            mgr.set_theme(target)
            self.app.theme = target
            self._refresh()
        elif event.key == "up":
            target = names[(active_idx - 1) % len(names)]
            mgr.set_theme(target)
            self.app.theme = target
            self._refresh()
        elif event.key == "enter":
            self.action_apply_theme(mgr.name)
