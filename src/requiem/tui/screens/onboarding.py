"""First-run onboarding wizard.

Appears automatically when REQUIEM has not been configured.
Walks the user through:
1. Welcome
2. Theme selection (live preview)
3. Provider selection
4. Credential configuration
5. Model selection
6. Connection validation
7. Save and confirm
"""

from __future__ import annotations

import logging

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from requiem.config.loader import save_config
from requiem.config.models import ConfigModel, ProviderConfig, ProviderCredentials
from requiem.config.paths import user_config_file
from requiem.themes.emblem import emblem
from requiem.themes.palettes import ALL_THEMES, list_theme_names

logger = logging.getLogger("requiem.tui.onboarding")


class OnboardingScreen(ModalScreen[bool]):
    """First-run onboarding wizard. Returns True on completion, False on skip."""

    CSS = """
    OnboardingScreen {
        background: $requiem-bg-recessed;
    }
    #onboarding {
        width: 1fr;
        height: 1fr;
        padding: 2;
    }
    .ob-title {
        color: $requiem-accent-alt;
        text-style: bold;
        width: 100%;
    }
    .ob-body {
        color: $requiem-text;
        width: 100%;
    }
    .ob-hint {
        color: $requiem-text-muted;
        width: 100%;
    }
    .ob-step {
        border: solid #2A242D;
        background: $requiem-bg-elevated;
        padding: 1 2;
        width: 100%;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "skip", "Skip"),
        Binding("enter", "next", "Next"),
    ]

    # Provider kinds and their descriptions
    PROVIDER_INFO: list[tuple[str, str, str]] = [
        ("openai", "OpenAI / ChatGPT", "Requires OPENAI_API_KEY or a key entered here. Uses api.openai.com."),
        ("anthropic", "Anthropic / Claude", "Requires ANTHROPIC_API_KEY or a key entered here. Uses api.anthropic.com."),
        ("openrouter", "OpenRouter", "Aggregator for many providers. Requires OPENROUTER_API_KEY. Uses openrouter.ai."),
        ("router9", "9Router", "Self-hosted/configurable aggregator. Set your own base URL, API key, and model list."),
        ("custom", "Custom OpenAI-compatible", "Any OpenAI-compatible API endpoint. Set base URL and API key manually."),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._step = 0
        self._theme_choice: str = "classic"
        self._provider_choice: str = "openai"
        self._api_key: str = ""
        self._base_url: str = ""
        self._model: str = ""
        self._provider_name: str = ""

    def compose(self) -> ComposeResult:
        yield Vertical(id="onboarding")

    def on_mount(self) -> None:
        self._render_step()

    def _render_step(self) -> None:
        box = self.query_one("#onboarding", Vertical)
        box.remove_children("*")
        match self._step:
            case 0:
                self._step_welcome(box)
            case 1:
                self._step_theme(box)
            case 2:
                self._step_provider(box)
            case 3:
                self._step_credentials(box)
            case 4:
                self._step_model(box)
            case 5:
                self._step_save(box)
            case _:
                box.mount(Static("Onboarding complete."))

    def _step_welcome(self, box: Vertical) -> None:
        box.mount(Static("  ".join("REQUIEM"), classes="ob-title"))
        box.mount(Static("Multi-agent AI orchestration and development environment", classes="ob-hint"))
        box.mount(Static(""))
        for line in emblem(6):
            box.mount(Static(line, classes="ob-hint"))
        box.mount(Static(""))
        box.mount(
            Static(
                "This wizard will help you configure REQUIEM.\n"
                "  1. Choose a theme\n"
                "  2. Select an AI provider\n"
                "  3. Enter credentials\n"
                "  4. Choose a model\n"
                "\nPress Enter to begin, or Esc to skip and configure later.",
                classes="ob-body",
            )
        )

    def _step_theme(self, box: Vertical) -> None:
        box.mount(Static("Choose a theme", classes="ob-title"))
        box.mount(Static("", classes="ob-body"))
        for name in list_theme_names():
            marker = "★" if name == self._theme_choice else " "
            palette = ALL_THEMES[name]
            box.mount(
                Static(
                    f"{marker}  {name:<12s}  accent={palette.primary_accent}  bg={palette.obsidian}",
                    classes="ob-body",
                )
            )
        box.mount(Static("\nUse up/down arrows to select, Enter to confirm, Esc to skip.", classes="ob-hint"))

    def _step_provider(self, box: Vertical) -> None:
        box.mount(Static("Select an AI provider", classes="ob-title"))
        box.mount(Static("", classes="ob-body"))
        for kind, display, desc in self.PROVIDER_INFO:
            marker = "★" if kind == self._provider_choice else " "
            box.mount(Static(f"{marker}  {display}", classes="ob-body"))
            box.mount(Static(f"     {desc}", classes="ob-hint"))
            box.mount(Static("", classes="ob-hint"))
        box.mount(Static("Use up/down arrows to select, Enter to confirm.", classes="ob-hint"))

    def _step_credentials(self, box: Vertical) -> None:
        kind = self._provider_choice
        display = next((d for k, d, _ in self.PROVIDER_INFO if k == kind), kind)
        box.mount(Static(f"Configure {display}", classes="ob-title"))
        box.mount(Static("", classes="ob-body"))

        default_url = {
            "openai": "https://api.openai.com/v1",
            "anthropic": "https://api.anthropic.com",
            "openrouter": "https://openrouter.ai/api/v1",
            "router9": "https://api.router9.com/v1",
            "custom": "",
        }.get(kind, "")

        box.mount(Static(f"  Base URL: {default_url or '(required for custom)'}", classes="ob-body"))
        box.mount(Static("  API Key:  (enter in the input below)", classes="ob-body"))
        box.mount(Static("  Env var:  " + {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "openrouter": "OPENROUTER_API_KEY", "router9": "ROUTER9_API_KEY"}.get(kind, "(custom)"), classes="ob-hint"))
        box.mount(
            Static(
                "\nPress Enter to use the default (reads from env var if available).\n"
                "Type 'skip' and press Enter to skip credential entry.\n"
                "Esc to go back.",
                classes="ob-hint",
            )
        )

    def _step_model(self, box: Vertical) -> None:
        box.mount(Static("Select a model", classes="ob-title"))
        box.mount(Static("", classes="ob-body"))
        defaults = {
            "openai": "gpt-4o-mini",
            "anthropic": "claude-sonnet-4",
            "openrouter": "openai/gpt-4o-mini",
            "router9": "(enter your model ID)",
            "custom": "(enter your model ID)",
        }
        default_model = defaults.get(self._provider_choice, "")
        box.mount(Static(f"  Default: {default_model}", classes="ob-body"))
        box.mount(Static("  Type a model name and press Enter, or Esc to use the default.", classes="ob-hint"))

    def _step_save(self, box: Vertical) -> None:
        box.mount(Static("Configuration Summary", classes="ob-title"))
        box.mount(Static("", classes="ob-body"))
        kind = self._provider_choice
        display = next((d for k, d, _ in self.PROVIDER_INFO if k == kind), kind)
        box.mount(Static(f"  Theme:    {self._theme_choice}", classes="ob-body"))
        box.mount(Static(f"  Provider: {display} ({kind})", classes="ob-body"))
        key_status = "configured" if self._api_key else "not set (will use env var)"
        box.mount(Static(f"  API Key:  {key_status} (masked)", classes="ob-body"))
        box.mount(Static(f"  Model:    {self._model or '(default)'}", classes="ob-body"))
        box.mount(Static("", classes="ob-body"))
        box.mount(Static("Press Enter to save and launch REQUIEM. Esc to skip.", classes="ob-hint"))

    # -- Navigation -----------------------------------------------------------

    def action_next(self) -> None:
        """Advance to the next step."""
        if self._step < 5:
            self._step += 1
            self._render_step()
        else:
            self._save_and_close()

    def action_skip(self) -> None:
        """Skip onboarding without saving."""
        self.dismiss(False)

    def _save_and_close(self) -> None:
        """Persist the configuration and return to the main app."""
        kind = self._provider_choice
        default_url = {
            "openai": "https://api.openai.com/v1",
            "anthropic": "https://api.anthropic.com",
            "openrouter": "https://openrouter.ai/api/v1",
            "router9": "https://api.router9.com/v1",
            "custom": "",
        }.get(kind, "")

        cfg = ConfigModel()
        cfg.theme.active = self._theme_choice

        env_var = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "router9": "ROUTER9_API_KEY",
        }.get(kind, "CUSTOM_API_KEY")
        provider = ProviderConfig(
            id=f"{kind}-default",
            name=next((d for k, d, _ in self.PROVIDER_INFO if k == kind), kind),
            kind=kind,
            default_model=self._model or None,
            enabled=True,
            credentials=ProviderCredentials(
                api_key_ref=env_var,
                base_url=default_url or None,
                model=self._model or None,
            ),
        )

        cfg.providers.append(provider)
        cfg.default_provider = provider.id

        try:
            save_config(cfg, user_config_file())
            logger.info("Onboarding complete. Config saved to %s", user_config_file())
        except Exception:
            logger.exception("Failed to save onboarding config")

        self.dismiss(True)
