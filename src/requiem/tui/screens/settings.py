"""Settings modal screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, Static

from requiem.config.loader import load_config


class SettingsScreen(ModalScreen[None]):
    """Shows current configuration values (read-only)."""

    CSS = """
    SettingsScreen {
        content-align: center middle;
        background: rgba(12, 10, 11, 0.92);
    }
    #settings-box {
        width: 60%;
        height: 70%;
        border: solid #2A242D;
        background: $surface;
        padding: 2;
    }
    """

    BINDINGS = [("escape", "close", "Close")]

    def compose(self) -> ComposeResult:
        cfg = load_config()

        with Vertical(id="settings-box"):
            yield Label("Settings")
            yield Static(f"  Theme:            {cfg.theme.active}")
            yield Static(f"  Default provider: {cfg.default_provider or '(none)'}")

            # Find default model
            default_model = "(not set)"
            if cfg.default_provider:
                for p in cfg.providers:
                    if p.id == cfg.default_provider and p.default_model:
                        default_model = p.default_model
                        break
            yield Static(f"  Default model:    {default_model}")
            yield Static(f"  Max concurrent:   {cfg.execution.max_concurrent_agents}")
            yield Static(f"  Max retries:      {cfg.execution.max_retry_attempts}")
            yield Static(f"  Log level:        {cfg.logging.level}")

            yield Static("")
            yield Static("Edit config file for full settings:")
            from requiem.config.paths import user_config_file
            yield Static(f"  {user_config_file()}")
            yield Static("\nEsc  Close")

    def action_close(self) -> None:
        self.dismiss()
