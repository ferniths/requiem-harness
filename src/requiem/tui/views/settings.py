"""Interactive settings view.

Replaces the read-only settings dump with a proper settings workspace
grouped by category. Writes back via save_config().
"""

from __future__ import annotations

import contextlib
import logging
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Input, Select, Static

logger = logging.getLogger("requiem.tui.views.settings")


class SettingsView(Vertical):
    """Interactive settings workspace."""

    view_id = "settings"
    view_label = "Settings"
    view_group = "Management"

    def __init__(self) -> None:
        super().__init__(id="req-settings-view")
        self._config: Any = None
        self._dirty = False

    def compose(self) -> ComposeResult:
        with Vertical(id="req-settings-layout"):
            yield Static("Settings", classes="req-section-title")
            with Vertical(id="req-settings-content"):
                yield Static("Loading settings…", classes="req-empty-state")

    def on_mount(self) -> None:
        self._load()

    def _load(self) -> None:
        from requiem.config.loader import load_config

        try:
            self._config = load_config()
        except Exception as e:
            self._config = None
            content: Any = self.query_one("#req-settings-content")
            content.update(
                Static(f"Failed to load config: {e}", classes="req-empty-state")
            )
            return

        self._refresh()

    def _refresh(self) -> None:
        content = self.query_one("#req-settings-content")
        content.remove_children()


        cfg = self._config
        if cfg is None:
            content.mount(Static("No configuration found.", classes="req-empty-state"))
            return

        # ── General ──────────────────────────────────────────────────────
        content.mount(Static("GENERAL", classes="req-section-title"))
        content.mount(Static(f"  Default Provider: {cfg.default_provider or '(none)'}", classes="req-setting-label"))

        # ── Theme ────────────────────────────────────────────────────────
        content.mount(Static("APPEARANCE", classes="req-section-title"))
        theme_select = Select(options=[
            ("Classic REQUIEM", "classic"),
            ("Blue", "blue"),
            ("Purple", "purple"),
            ("Magenta", "magenta"),
            ("Grey", "grey"),
        ], value=cfg.theme.active, id="req-settings-theme")
        content.mount(theme_select)
        content.mount(Static("  Theme", classes="req-setting-label"))

        # ── Execution ───────────────────────────────────────────────────
        content.mount(Static("EXECUTION", classes="req-section-title"))
        exec_input = Input(
            value=str(cfg.execution.max_concurrent_agents),
            id="req-settings-max-agents",
        )
        content.mount(Static("  Max Concurrent Agents", classes="req-setting-label"))
        content.mount(exec_input)
        retry_input = Input(
            value=str(cfg.execution.max_retry_attempts),
            id="req-settings-max-retries",
        )
        content.mount(Static("  Max Retry Attempts", classes="req-setting-label"))
        content.mount(retry_input)

        # ── Logging ──────────────────────────────────────────────────────
        content.mount(Static("LOGGING", classes="req-section-title"))
        log_select = Select(
            options=[
                ("Debug", "DEBUG"),
                ("Info", "INFO"),
                ("Warning", "WARNING"),
                ("Error", "ERROR"),
            ],
            value=cfg.logging.level,
            id="req-settings-log-level",
        )
        content.mount(log_select)
        content.mount(Static("  Log Level", classes="req-setting-label"))
        content.mount(Horizontal(
            Static("  Save  ", classes="req-button", id="act-save-settings"),
            Static("  Reset  ", classes="req-button", id="act-reset-settings"),
        ))


    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "req-settings-theme":
            self._config.theme.active = str(event.value)
        elif event.select.id == "req-settings-log-level":
            self._config.logging.level = str(event.value)
        self._dirty = True

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "req-settings-max-agents":
            with contextlib.suppress(ValueError):
                self._config.execution.max_concurrent_agents = int(event.value)
        elif event.input.id == "req-settings-max-retries":
            with contextlib.suppress(ValueError):
                self._config.execution.max_retry_attempts = int(event.value)
        self._dirty = True

    def _save(self) -> None:
        from requiem.config.loader import save_config
        from requiem.config.paths import user_config_file

        if self._config is None:
            return
        try:
            save_config(self._config, user_config_file())
            content = self.query_one("#req-settings-content")
            content.mount(Static("Settings saved.", classes="req-tool-done"))
            self._dirty = False
            if hasattr(self._config, "theme"):
                theme_name = self._config.theme.active
                mgr: Any = getattr(self.app, "_theme_mgr", None)
                if theme_name != mgr.name:
                    mgr.set_theme(theme_name)
                    self.app.theme = theme_name
        except Exception as e:
            content = self.query_one("#req-settings-content")
            content.mount(Static(f"Save failed: {e}", classes="req-tool-error"))
