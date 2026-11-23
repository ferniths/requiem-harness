"""Provider add/edit modal form.

Used by the Providers view to add or edit a provider configuration.
Handles all 5 provider kinds with kind-specific fields.
"""

from __future__ import annotations

import logging

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Select, Static

logger = logging.getLogger("requiem.tui.widgets.provider_form")

_KIND_OPTIONS = [
    ("OpenAI / ChatGPT", "openai"),
    ("Anthropic / Claude", "anthropic"),
    ("OpenRouter", "openrouter"),
    ("9Router (custom gateway)", "router9"),
    ("Custom (OpenAI-compatible)", "custom"),
]

_KIND_DEFAULTS: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com",
    "openrouter": "https://openrouter.ai/api/v1",
    "router9": "",
    "custom": "",
}

_KIND_HINTS: dict[str, str] = {
    "router9": "Enter your 9Router endpoint URL. Each deployment has its own address.",
    "custom": "Enter your OpenAI-compatible API endpoint (e.g. /v1 path included).",
}


class ProviderFormModal(ModalScreen[None]):
    """Modal form for adding or editing a provider."""

    CSS = """
    ProviderFormModal {
        content-align: center middle;
        background: $requiem-bg-recessed;
    }
    #prov-form {
        width: 55%;
        height: auto;
        border: solid $requiem-border;
        background: $requiem-bg-elevated;
        padding: 1 2;
    }
    .prov-label {
        color: $requiem-text-muted;
        height: 1;
        padding-bottom: 0;
    }
    .prov-input {
        height: 1;
        margin-bottom: 1;
    }
    .prov-hint {
        color: $requiem-text-muted;
        text-style: italic;
        height: 1;
        margin-bottom: 1;
    }
    """

    def __init__(self, existing: dict[str, str] | None = None) -> None:
        super().__init__()
        self._existing = existing or {}
        self._result: dict[str, str] = {}

    @property
    def saved_data(self) -> dict[str, str]:
        return self._result

    def compose(self) -> ComposeResult:
        with Vertical(id="prov-form"):
            yield Static("Add Provider", classes="prov-label")
            yield Static("", id="prov-form-body")

    def on_mount(self) -> None:
        body = self.query_one("#prov-form-body")

        kind = self._existing.get("kind", "openai")
        base_url = self._existing.get("base_url", _KIND_DEFAULTS.get(kind, ""))
        model = self._existing.get("model", "")
        name = self._existing.get("name", "")
        api_key = self._existing.get("api_key", "")

        kind_select = Select(options=_KIND_OPTIONS, value=kind, id="prov-kind")
        yield_from = [
            Static("Provider type", classes="prov-label"),
            kind_select,
            Static("Display name", classes="prov-label"),
            Input(value=name or kind.title(), id="prov-name", classes="prov-input"),
            Static("Base URL", classes="prov-label"),
            Input(value=base_url, id="prov-base-url", classes="prov-input"),
        ]
        if kind in _KIND_HINTS:
            yield_from.append(Static(_KIND_HINTS[kind], classes="prov-hint"))
        yield_from.extend([
            Static("API Key (stored in system credential vault)", classes="prov-label"),
            Input(value="••••••••" if api_key else "", id="prov-api-key", password=True, classes="prov-input"),
            Static("Default Model", classes="prov-label"),
            Input(value=model, placeholder="e.g. gpt-4o, claude-sonnet-4-20250514", id="prov-model", classes="prov-input"),
            Static("", ),
            Static("  Save  ", classes="req-button", id="prov-save"),
            Static("  Cancel  ", classes="req-button", id="prov-cancel"),
        ])
        for w in yield_from:
            body.mount(w)

    def on_select_changed(self, event: Select.Changed) -> None:
        """Update the base URL field when the provider kind changes."""
        if event.select.id == "prov-kind":
            kind = str(event.value)
            default_url = _KIND_DEFAULTS.get(kind, "")
            url_input = self.query_one("#prov-base-url", Input)
            if not url_input.value:
                url_input.value = default_url
            # Show hint for router9/custom
            hint = _KIND_HINTS.get(kind, "")
            body = self.query_one("#prov-form-body")
            # Remove old hint if any
            for child in body.children:
                if getattr(child, "classes", "") == "prov-hint":
                    body.remove_children([child])
            if hint:
                body.mount(Static(hint, classes="prov-hint"))

    def action_save(self) -> None:
        kind = str(self.query_one("#prov-kind", Select).value)
        name = self.query_one("#prov-name", Input).value.strip() or kind
        base_url = self.query_one("#prov-base-url", Input).value.strip()
        api_key = self.query_one("#prov-api-key", Input).value.strip()
        model = self.query_one("#prov-model", Input).value.strip()

        self._result = {
            "kind": kind,
            "name": name,
            "base_url": base_url,
            "api_key": api_key,
            "model": model,
        }
        self.dismiss()

    def action_cancel(self) -> None:
        self.dismiss()
