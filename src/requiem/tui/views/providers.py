"""Provider management view.

Shows configured providers with status, supports add/edit/remove,
connection testing, and model selection.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from textual.app import ComposeResult
import textual.events
from textual.message import Message
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Static

logger = logging.getLogger("requiem.tui.views.providers")

_PROVIDER_KINDS = [
    ("openai", "OpenAI", "OpenAI / ChatGPT — GPT-4, GPT-4o, o1"),
    ("anthropic", "Anthropic", "Anthropic / Claude — Sonnet, Opus, Haiku"),
    ("openrouter", "OpenRouter", "OpenRouter — 300+ models via unified API"),
    ("router9", "9Router", "9Router — custom multi-model routing gateway"),
    ("custom", "Custom", "Any OpenAI-compatible endpoint"),
]

_DEFAULT_URLS = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com",
    "openrouter": "https://openrouter.ai/api/v1",
    "router9": "",  # user must enter their 9Router endpoint
    "custom": "",
}

_ENV_VARS = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "router9": "ROUTER9_API_KEY",
    "custom": "CUSTOM_API_KEY",
}


class ProvidersView(Vertical):
    """Provider management workspace."""

    view_id = "providers"
    view_label = "Providers"
    view_group = "Management"

    selected_provider: reactive[str] = reactive("")
    provider_status: reactive[dict[str, str]] = reactive({})

    def __init__(self) -> None:
        super().__init__(id="req-providers-view")
        self._providers: list[dict[str, Any]] = []
        self._vault: Any = None

    def compose(self) -> ComposeResult:
        with Vertical(id="req-providers-layout"):
            yield Static("Providers", classes="req-section-title")
            yield Static("", id="req-providers-list")
            with Container(id="req-providers-detail"):
                yield Static("Select a provider to view details.", classes="req-empty-state")

    def on_mount(self) -> None:
        self._load_providers()

    def _load_providers(self) -> None:
        """Load providers from config and check credential status."""
        from requiem.config.loader import load_config
        from requiem.security.credentials import CredentialVault

        try:
            cfg = load_config()
            self._vault = CredentialVault()
            self._providers = []
            default_id = cfg.default_provider or ""
            for p in cfg.providers:
                has_key = self._vault.has(p.id) if self._vault else False
                self._providers.append({
                    "id": p.id,
                    "name": p.name,
                    "kind": p.kind,
                    "base_url": p.credentials.base_url or "",
                    "model": p.credentials.model or "",
                    "enabled": p.enabled,
                    "has_key": has_key,
                    "is_default": p.id == default_id,
                })
            self._render_list()
        except Exception as e:
            list_w: Any = self.query_one("#req-providers-list")
            list_w.mount(Static(f"Failed to load providers: {e}", classes="req-empty-state"))

    def _render_list(self) -> None:
        container = self.query_one("#req-providers-list")
        container.remove_children("*")
        if not self._providers:
            container.mount(Static(
                "No providers configured.\n"
                "Press Enter to add a provider, or open the command palette (Ctrl+P).",
                classes="req-empty-state",
            ))
            return

        for prov in self._providers:
            marker = "★" if prov["is_default"] else " "
            status = "Configured" if prov["has_key"] else "Missing credentials"
            status_style = "req-status-configured" if prov["has_key"] else "req-status-error"
            row = Horizontal(
                Static(f"{marker} {prov['name']}", classes="req-row"),
                Static(prov["kind"], classes="req-status-idle"),
                Static(status, classes=status_style),
                id=f"prov-{prov['id']}",
                classes="req-row",
            )
            container.mount(row)

    def _show_detail(self, provider_id: str) -> None:
        detail = self.query_one("#req-providers-detail")
        detail.remove_children("*")
        prov = next((p for p in self._providers if p["id"] == provider_id), None)
        if prov is None:
            return

        p: Any = cast(Any, getattr(self.app, "_theme_mgr", None)).palette
        accent = p.primary_accent
        gold = p.secondary_accent
        muted = p.muted_ash

        from rich.text import Text
        lines = [
            Text(f"◈ {prov['name']}", style=f"bold {accent}"),
            Text(f"Type: {prov['kind']}"),
            Text(f"Base URL: {prov['base_url'] or '(default)'}", style=muted),
            Text(f"Model: {prov['model'] or '(not set)'}", style=muted),
            Text(f"Credentials: {'✓ stored' if prov['has_key'] else '✗ missing'}", style=accent if prov["has_key"] else gold),
            Text(f"Status: {'Enabled' if prov['enabled'] else 'Disabled'}"),
        ]
        detail.mount(Static("\n".join(str(t) for t in lines)))

        # Action buttons
        actions = Horizontal(
            Static("  Test Connection  ", classes="req-button", id="act-test-conn"),
            Static("  Set Default  ", classes="req-button", id="act-set-default"),
            Static("  Manage Keys  ", classes="req-button", id="act-keys"),
        )
        detail.mount(actions)

    def on_key(self, event: textual.events.Key) -> None:
        if event.key == "enter" and not self._providers:
            self._open_add_provider()
        elif event.key in ("up", "down"):
            event.stop()
            event.prevent_default()
            ids = [p["id"] for p in self._providers]
            if self.selected_provider in ids:
                idx = ids.index(self.selected_provider)
            else:
                idx = -1 if event.key == "down" else len(self._providers)
            idx = min(idx + 1, len(self._providers) - 1) if event.key == "down" else max(idx - 1, 0)
            if 0 <= idx < len(self._providers):
                self.selected_provider = self._providers[idx]["id"]
                self._show_detail(self.selected_provider)

    def _open_add_provider(self) -> None:
        """Open the add-provider modal form."""
        from requiem.tui.widgets.provider_form import ProviderFormModal
        self.app.push_screen(ProviderFormModal())

    def _test_connection(self, provider_id: str) -> None:
        """Run an async connection test."""
        prov = next((p for p in self._providers if p["id"] == provider_id), None)
        if prov is None:
            return

        async def _run() -> None:
            from requiem.providers.registry import create_provider
            from requiem.security.credentials import CredentialVault

            vault = CredentialVault()
            key = vault.retrieve(provider_id)
            provider = create_provider(
                prov["kind"],
                base_url=prov["base_url"] or None,
                api_key=key,
            )
            try:
                ok, msg = await provider.validate_connection(api_key=key, model=prov["model"] or None)
                self.post_message(_ProviderTestMsg(provider_id, ok, msg))
            except Exception as e:
                self.post_message(_ProviderTestMsg(provider_id, False, str(e)))

        workers: Any = self.app.workers
        workers.run_worker(_run)

    def on_provider_test_result(self, msg: _ProviderTestMsg) -> None:
        """Handle connection test result."""
        detail: Any = self.query_one("#req-providers-detail")
        status_cls = "req-status-connected" if msg.ok else "req-status-error"
        label = "Connected ✓" if msg.ok else "Failed ✗"
        detail.mount(Static(f"{label}: {msg.detail}", classes=status_cls))


class _ProviderTestMsg(Message):
    """Message carrying a connection test result."""
    NAME = "provider_test_result"

    def __init__(self, provider_id: str, ok: bool, detail: str) -> None:
        self.provider_id = provider_id
        self.ok = ok
        self.detail = detail
        super().__init__()
