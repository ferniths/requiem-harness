"""REQUIEM main TUI application.

Architecture:
- The App itself is the main screen (chat).
- Other sections (agents, workflows, logs, etc.) are ModalScreens.
- The command palette is also a ModalScreen.
- Theme is managed via Textual's built-in Theme system with custom CSS variables.
"""

from __future__ import annotations

import asyncio
import logging

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.theme import Theme
from textual.widgets import Footer, Input, Static

from requiem.themes.manager import ThemeManager

logger = logging.getLogger("requiem.tui")


def _make_requiem_theme(name: str, palette: dict[str, str]) -> Theme:
    """Build a Textual Theme from a REQUIEM palette."""
    return Theme(
        name=name,
        primary=palette.get("primary_accent", "#C02645"),
        secondary=palette.get("secondary_accent", "#D4AF72"),
        foreground=palette.get("ash_white", "#E8E1E5"),
        background=palette.get("obsidian", "#0C0A0B"),
        surface=palette.get("dark_iron", "#171316"),
        panel=palette.get("elevated_iron", "#1B171F"),
        error=palette.get("primary_accent", "#C02645"),
        accent=palette.get("primary_accent", "#C02645"),
        dark=True,
        variables={
            "requiem-bg": palette.get("obsidian", "#0C0A0B"),
            "requiem-bg-recessed": palette.get("dark_iron", "#171316"),
            "requiem-bg-elevated": palette.get("elevated_iron", "#1B171F"),
            "requiem-text": palette.get("ash_white", "#E8E1E5"),
            "requiem-text-secondary": palette.get("muted_ash", "#82777D"),
            "requiem-border": palette.get("iron_border", "#2A242D"),
            "requiem-accent": palette.get("primary_accent", "#C02645"),
            "requiem-accent-deep": palette.get("deep_accent", "#81172F"),
            "requiem-accent-secondary": palette.get("secondary_accent", "#D4AF72"),
        },
    )


class RequiemApp(App[None]):
    """REQUIEM terminal application — main entry point."""

    CSS = """
    Screen {
        background: $background;
    }
    #main-area {
        height: 1fr;
    }
    #chat-log {
        height: 1fr;
        overflow-y: auto;
        padding: 1 2;
    }
    #chat-input {
        height: 3;
        width: 100%;
        margin: 0 2;
        border: solid #2A242D;
        background: $surface;
    }
    .msg-user {
        color: $requiem-text;
        padding: 0 2;
        width: 100%;
    }
    .msg-assistant {
        color: $requiem-text;
        padding: 0 2;
        width: 100%;
    }
    .msg-system {
        color: $requiem-text-secondary;
        text-style: italic;
        padding: 0 2;
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("ctrl+p", "command_palette", "Command Palette"),
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+c", "cancel_operation", "Cancel"),
        Binding("ctrl+enter", "submit_message", "Submit"),
        Binding("f1", "show_help", "Help"),
        Binding("f2", "show_agents", "Agents"),
        Binding("f3", "show_workflows", "Workflows"),
        Binding("f4", "show_logs", "Logs"),
        Binding("f5", "show_providers", "Providers"),
        Binding("f6", "show_settings", "Settings"),
        Binding("f7", "show_themes", "Themes"),
        Binding("escape", "back", "Back"),
    ]

    def __init__(self) -> None:
        # Initialize theme manager BEFORE super().__init__() because
        # App.__init__ calls get_css_variables() which needs it.
        self._theme_mgr = ThemeManager("classic")
        super().__init__()
        self._message_history: list[str] = []
        self._busy = False
        self._register_requiem_themes()

    def get_css_variables(self) -> dict[str, str]:
        """Provide REQUIEM CSS variables that are always available."""
        vars_ = super().get_css_variables()
        p = self._theme_mgr.palette
        vars_.update({
            "requiem-bg": p.obsidian,
            "requiem-bg-recessed": p.dark_iron,
            "requiem-bg-elevated": p.elevated_iron,
            "requiem-text": p.ash_white,
            "requiem-text-secondary": p.muted_ash,
            "requiem-border": p.iron_border,
            "requiem-accent": p.primary_accent,
            "requiem-accent-deep": p.deep_accent,
            "requiem-accent-secondary": p.secondary_accent,
        })
        return vars_

    def _register_requiem_themes(self) -> None:
        """Register all 5 REQUIEM themes with Textual's theme system."""
        from requiem.themes.palettes import ALL_THEMES

        for name, palette in ALL_THEMES.items():
            theme = _make_requiem_theme(name, {
                "primary_accent": palette.primary_accent,
                "secondary_accent": palette.secondary_accent,
                "ash_white": palette.ash_white,
                "obsidian": palette.obsidian,
                "dark_iron": palette.dark_iron,
                "elevated_iron": palette.elevated_iron,
                "muted_ash": palette.muted_ash,
                "iron_border": palette.iron_border,
                "deep_accent": palette.deep_accent,
            })
            self.register_theme(theme)

    def on_mount(self) -> None:
        # Load theme from config if available
        try:
            from requiem.config.loader import load_config
            cfg = load_config()
            theme_name = cfg.theme.active
        except Exception:
            theme_name = "classic"

        self._theme_mgr.set_theme(theme_name)
        # Apply the theme via Textual's theme system
        self.theme = theme_name  # This triggers Textual to look up the registered theme

        # Trigger onboarding on first run
        from requiem.config.loader import is_first_run
        if is_first_run():
            from requiem.tui.screens.onboarding import OnboardingScreen
            self.push_screen(OnboardingScreen())

    def compose(self) -> ComposeResult:
        yield Static("REQUIEM  ·  Chat", id="requiem-header")
        with Container(id="main-area"), VerticalScroll(id="chat-log"):
            yield Static(
                "Welcome to REQUIEM. Type a message below, or press "
                "Ctrl+P for the command palette.",
                id="welcome-msg",
            )
        yield Input(placeholder="Type a message… (Ctrl+Enter to send)", id="chat-input")
        yield Footer()

    # -- Chat ----------------------------------------------------------------

    def _add_message(self, text: str, style: str = "assistant") -> None:
        """Append a message to the chat log."""
        self._message_history.append(text)
        cls = {"user": "msg-user", "assistant": "msg-assistant", "system": "msg-system"}.get(style, "msg-assistant")
        label = Static(text, classes=cls)
        self.query_one("#chat-log").mount(label)
        self.query_one("#chat-log").scroll_to_bottom()  # type: ignore[attr-defined]

    async def _send_message(self) -> None:
        """Send the typed message to the provider (mock if no provider configured)."""
        input_widget = self.query_one("#chat-input", Input)
        text = input_widget.value.strip()
        if not text or self._busy:
            return

        input_widget.value = ""
        self._add_message(text, style="user")
        self._busy = True

        self._add_message(
            "[system] No provider configured. Run onboarding (F5 Providers) "
            "to connect an AI provider, or use `requiem list-providers` in a terminal.",
            style="system",
        )
        self._busy = False

    # -- Actions ---------------------------------------------------------------

    def action_submit_message(self) -> None:
        asyncio.create_task(self._send_message())

    def action_cancel_operation(self) -> None:
        logger.debug("Cancel requested")

    def action_back(self) -> None:  # type: ignore[override]
        if self.screen_stack:
            self.pop_screen()

    def action_show_help(self) -> None:
        from requiem.tui.screens.help import HelpScreen
        self.push_screen(HelpScreen())

    def action_show_agents(self) -> None:
        from requiem.tui.screens.agents import AgentsScreen
        self.push_screen(AgentsScreen())

    def action_show_workflows(self) -> None:
        from requiem.tui.screens.workflows import WorkflowsScreen
        self.push_screen(WorkflowsScreen())

    def action_show_logs(self) -> None:
        from requiem.tui.screens.logs import LogsScreen
        self.push_screen(LogsScreen())

    def action_show_providers(self) -> None:
        from requiem.tui.screens.providers import ProvidersScreen
        self.push_screen(ProvidersScreen())

    def action_show_settings(self) -> None:
        from requiem.tui.screens.settings import SettingsScreen
        self.push_screen(SettingsScreen())

    def action_show_themes(self) -> None:
        from requiem.tui.screens.themes import ThemesScreen
        self.push_screen(ThemesScreen())

    def action_command_palette(self) -> None:
        from requiem.tui.widgets.command_palette import CommandPalette
        self.push_screen(CommandPalette())

    def action_quit(self) -> None:  # type: ignore[override]
        self.exit()
