"""REQUIEM main TUI application.

Architecture:
- The App composes a persistent shell: branded header, navigation rail,
  workspace container, and status bar.
- Workspace views (Chat, Agents, Workflows, Providers, Logs, Settings,
  Appearance, Help) are Widgets that swap inside the workspace.
- Modal interactions (command palette, provider forms, confirmations)
  are reserved for ModalScreens.
- Theme is managed via Textual's Theme system with REQUIEM CSS variables.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.theme import Theme
from textual.widgets import Static

from requiem.themes.manager import ThemeManager

logger = logging.getLogger("requiem.tui")

# View import map — lazy to avoid circular imports at module load time.
_VIEW_IMPORTS: dict[str, str] = {
    "chat": "requiem.tui.views.chat.ChatView",
    "agents": "requiem.tui.views.agents.AgentsView",
    "workflows": "requiem.tui.views.workflows.WorkflowsView",
    "providers": "requiem.tui.views.providers.ProvidersView",
    "logs": "requiem.tui.views.logs.LogsView",
    "settings": "requiem.tui.views.settings.SettingsView",
    "themes": "requiem.tui.views.themes.ThemesView",
    "help": "requiem.tui.views.help.HelpView",
}

_NAV_ITEMS: list[tuple[str, str, str]] = [
    # (view_id, label, group)
    ("chat", "Chat", "Workspace"),
    ("agents", "Agents", "Workspace"),
    ("workflows", "Workflows", "Workspace"),
    ("providers", "Providers", "Management"),
    ("logs", "Logs", "Management"),
    ("settings", "Settings", "Management"),
    ("themes", "Appearance", "Management"),
    ("help", "Help", "Management"),
]


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
            "requiem-text-muted": palette.get("muted_ash", "#82777D"),
            "requiem-border": palette.get("iron_border", "#2A242D"),
            "requiem-accent": palette.get("primary_accent", "#C02645"),
            "requiem-accent-deep": palette.get("deep_accent", "#81172F"),
            "requiem-accent-alt": palette.get("secondary_accent", "#D4AF72"),
            "requiem-success": "#5A9E6F",
            "requiem-error": palette.get("primary_accent", "#C02645"),
        },
    )


class RequiemApp(App[None]):
    """REQUIEM terminal application — persistent shell architecture."""

    CSS = """
    /* Shell layout — component styles in styles/app.tcss */
    #req-shell {
        height: 1fr;
        width: 100%;
    }
    """

    CSS_PATH = [Path(__file__).parent / "styles" / "app.tcss"]

    BINDINGS = [
        Binding("ctrl+p", "command_palette", "Commands"),
        Binding("ctrl+m", "menu_launcher", "Menus"),
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+c", "cancel_operation", "Cancel"),
        Binding("ctrl+enter", "submit_message", "Send"),
        Binding("f1", "nav_help", "Help"),
        Binding("f2", "nav_agents", "Agents"),
        Binding("f3", "nav_workflows", "Workflows"),
        Binding("f4", "nav_logs", "Logs"),
        Binding("f5", "nav_providers", "Providers"),
        Binding("f6", "nav_settings", "Settings"),
        Binding("f7", "nav_themes", "Appearance"),
        Binding("escape", "back", "Back"),
    ]

    # Reactive state
    active_view: reactive[str] = reactive("chat")
    status_text: reactive[str] = reactive("Ready")

    def __init__(self) -> None:
        # Initialize theme manager BEFORE super().__init__() because
        # App.__init__ calls get_css_variables() which needs it.
        self._theme_mgr = ThemeManager("classic")
        super().__init__()
        self._views: dict[str, Any] = {}
        self._active_provider: Any = None
        self._active_model: str = ""
        self._active_api_key: str | None = None
        self._chat_view: Any = None
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
            "requiem-text-muted": p.muted_ash,
            "requiem-border": p.iron_border,
            "requiem-accent": p.primary_accent,
            "requiem-accent-deep": p.deep_accent,
            "requiem-accent-alt": p.secondary_accent,
            "requiem-success": p.success,
            "requiem-error": p.error,
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

    # ── Provider resolution ────────────────────────────────────────────────

    def _resolve_api_key(self) -> str | None:
        """Return the active provider's API key, resolved by config ID.

        The key is captured when the provider is loaded in
        _load_active_provider, where the correct config ID is available.
        Fallback to env-var lookup if the provider was loaded without a key.
        """
        if self._active_provider is None:
            return None
        if self._active_api_key is not None:
            return self._active_api_key
        # Fallback: try to retrieve via the provider's config id if it's set
        config_id = getattr(self._active_provider, "config_id", None)
        if config_id:
            return self._resolve_api_key_for_config(config_id)
        return None

    def _load_active_provider(self) -> None:
        """Load the default provider from config and create the provider instance."""
        from requiem.config.loader import load_config
        from requiem.providers.registry import provider_for_config

        try:
            cfg = load_config()
        except Exception:
            return

        if not cfg.providers:
            return

        # Find the default or first enabled provider
        target = None
        for p in cfg.providers:
            if p.id == cfg.default_provider and p.enabled:
                target = p
                break
        if target is None:
            for p in cfg.providers:
                if p.enabled:
                    target = p
                    break
        if target is None:
            return

        try:
            api_key = self._resolve_api_key_for_config(target.id)
            self._active_provider = provider_for_config(
                target, api_key=api_key,
            )
            self._active_model = target.default_model or target.credentials.model or ""
            self._active_api_key = api_key
        except Exception:
            logger.debug("Failed to load provider %s", target.id, exc_info=True)

    def _resolve_api_key_for_config(self, provider_id: str) -> str | None:
        from requiem.security.credentials import CredentialVault
        vault = CredentialVault()
        return vault.retrieve(provider_id)

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        # Load theme from config
        try:
            from requiem.config.loader import load_config
            cfg = load_config()
            theme_name = cfg.theme.active
        except Exception:
            theme_name = "classic"

        self._theme_mgr.set_theme(theme_name)
        self.theme = theme_name

        # Load the active provider
        self._load_active_provider()

        # Mount the active view
        self._mount_view("chat")

        # Check first-run onboarding
        from requiem.config.loader import is_first_run
        if is_first_run():
            from requiem.tui.screens.onboarding import OnboardingScreen
            self.push_screen(OnboardingScreen())

    def on_active_view_changed(self, value: str) -> None:
        """Switch the visible workspace view."""
        self._mount_view(value)

    # ── Shell layout ───────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        # Header
        yield Horizontal(
            Static("REQUIEM", id="req-header-title"),
            Static("  ·  Chat", id="req-header-subtitle"),
            Static("● Ready", id="req-header-status"),
            id="req-header",
        )

        # Body: nav rail + workspace
        with Container(id="req-shell"):
            # Navigation rail
            with Vertical(id="req-nav-rail"):
                for view_id, label, group in _NAV_ITEMS:
                    if self._is_group_start(view_id, label):
                        yield Static(group.upper(), id=f"nav-group-{view_id}", classes="req-nav-group-label")
                    yield Static(
                        f"  ◈ {label}" if view_id == "chat" else f"  ◇ {label}",
                        id=f"nav-{view_id}",
                        classes=f"req-nav-item{' active' if view_id == 'chat' else ''}",
                    )

            # Workspace
            yield Container(id="req-workspace")

        # Status bar
        yield Static("", id="req-status-bar")

    @staticmethod
    def _is_group_start(view_id: str, label: str) -> bool:
        """Return True if this nav item starts a new group (first in its group)."""
        groups: dict[str, int] = {}
        for vid, _, grp in _NAV_ITEMS:
            if vid == view_id:
                break
            groups[grp] = groups.get(grp, 0) + 1
        else:
            return False
        for vid, _, grp in _NAV_ITEMS:
            if vid == view_id:
                # Check if any earlier item is in the same group
                for vid2, _, grp2 in _NAV_ITEMS:
                    if vid2 == view_id:
                        break
                    if grp2 == grp:
                        return False
                return True
        return False

    # ── View management ────────────────────────────────────────────────────

    def _mount_view(self, view_id: str) -> None:
        """Mount a view into the workspace, unmounting any previous one."""
        workspace: Any = self.query_one("#req-workspace")
        # Clear existing view
        for child in list(workspace.children):
            workspace.remove_children([child])

        # Build the view
        view = self._build_view(view_id)
        workspace.mount(view)
        self.active_view = view_id

        # Update nav highlighting
        self._update_nav(view_id)

        # Update status bar
        self._update_status_bar()

    def _build_view(self, view_id: str) -> Any:
        """Instantiate a view by view_id using the lazy import map."""
        import importlib

        dotted = _VIEW_IMPORTS.get(view_id, "")
        if not dotted:
            from requiem.tui.views.chat import ChatView
            return ChatView()

        module_path, cls_name = dotted.rsplit(".", 1)
        module = importlib.import_module(module_path)
        cls = getattr(module, cls_name)

        view = cls(on_status=self._on_chat_status) if view_id == "chat" else cls()
        return view

    def _update_nav(self, active_id: str) -> None:
        """Update navigation rail highlighting."""
        for item in self.query(".req-nav-item"):
            cls = "req-nav-item"
            if item.id == f"nav-{active_id}":
                cls += " active"
            item.classes = set(cls.split())

    def _update_status_bar(self) -> None:
        """Update the bottom status bar with current context."""
        provider_name = getattr(self._active_provider, "display_name", "No provider") if self._active_provider else "No provider"
        model = self._active_model or "—"
        view = self.active_view.capitalize()
        status: Any = self.query_one("#req-status-bar")
        status.update(
            f"  {provider_name}  ·  {model}  ·  {view}  ·  Ctrl+P Commands  ·  {self.status_text}"
        )

    def _on_chat_status(self, status: str) -> None:
        """Callback from ChatView to update the status bar."""
        self.status_text = status
        self._update_status_bar()

    # ── Navigation actions ────────────────────────────────────────────────

    def action_nav_chat(self) -> None:
        self.active_view = "chat"

    def action_nav_agents(self) -> None:
        self.active_view = "agents"

    def action_nav_workflows(self) -> None:
        self.active_view = "workflows"

    def action_nav_logs(self) -> None:
        self.active_view = "logs"

    def action_nav_providers(self) -> None:
        self.active_view = "providers"

    def action_nav_settings(self) -> None:
        self.active_view = "settings"

    def action_nav_themes(self) -> None:
        self.active_view = "themes"

    def action_nav_help(self) -> None:
        self.active_view = "help"

    # ── Chat actions ──────────────────────────────────────────────────────

    def action_submit_message(self) -> None:
        """Submit the chat composer input."""
        view = self._get_view("chat")
        if view is not None:
            asyncio.create_task(view.send_message())

    def action_cancel_operation(self) -> None:
        """Cancel an in-flight generation."""
        view = self._get_view("chat")
        if view is not None:
            view.cancel_generation()

    def _get_view(self, view_id: str) -> Any:
        """Get the mounted view widget by view_id."""
        try:
            workspace = self.query_one("#req-workspace")
            for child in workspace.children:
                if getattr(child, "view_id", "") == view_id:
                    return child
        except Exception:
            pass
        return None

    # ── Back / Escape ─────────────────────────────────────────────────────

    def action_back(self) -> None:  # type: ignore[override]
        if self.screen_stack:
            self.pop_screen()

    # ── Modals ────────────────────────────────────────────────────────────

    def action_command_palette(self) -> None:
        from requiem.tui.widgets.command_palette import CommandPalette
        self.push_screen(CommandPalette())

    def action_menu_launcher(self) -> None:
        """Open the menu-kit launcher modal (Ctrl+M)."""
        from requiem.tui.menus import MenuCommand, MenuRegistry, ModalMenuScreen
        from requiem.tui.widgets.command_palette import CommandPalette

        registry = MenuRegistry()
        commands: list[MenuCommand] = []
        for label, action_name, _kw, desc in CommandPalette._COMMANDS:
            handler = getattr(self, f"action_{action_name}", None)
            commands.append(
                MenuCommand(
                    id=action_name,
                    label=label,
                    hint=desc,
                    category="",
                    enabled=handler is not None,
                    icon="•",
                    action=f"action_{action_name}",
                ),
            )
        self.push_screen(ModalMenuScreen(commands=commands, registry=registry, title="REQUIEM"))
        # The screen's on_selected calls registry.resolve(action) which is the
        # same dispatch path as the palette. Bind handlers at open time.
        for cmd in commands:
            handler = getattr(self, str(cmd.action), None)
            if handler is not None:
                registry.register(cmd.id, handler, cmd.label)

    def action_quit(self) -> None:  # type: ignore[override]
        self.exit()
