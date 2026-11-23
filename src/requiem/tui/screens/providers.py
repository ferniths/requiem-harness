"""Provider Manager modal screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Label, Static

from requiem.config.loader import load_config
from requiem.security.credentials import CredentialVault


class ProvidersScreen(ModalScreen[None]):
    """Shows configured providers and their status."""

    CSS = """
    ProvidersScreen {
        content-align: center middle;
        background: rgba(12, 10, 11, 0.92);
    }
    #prov-box {
        width: 70%;
        height: 80%;
        border: solid #2A242D;
        background: $surface;
        padding: 2;
    }
    """

    BINDINGS = [("escape", "close", "Close")]

    def compose(self) -> ComposeResult:
        cfg = load_config()
        vault = CredentialVault()
        default = cfg.default_provider

        with Vertical(id="prov-box"):
            yield Label("Provider Manager")

            if not cfg.providers:
                yield Static(
                    "No providers configured.\n"
                    "  Run `requiem` to start onboarding, or add providers to your config file.\n"
                    "  Supported kinds: openai, anthropic, openrouter, router9 (9Router), custom"
                )
            else:
                with VerticalScroll():
                    for p in cfg.providers:
                        marker = "★" if p.id == default else " "
                        status = "enabled" if p.enabled else "disabled"
                        base = p.credentials.base_url or "(default)"
                        key_status = "key configured" if vault.has(p.id) else "key not set"
                        # Special display for 9Router
                        kind_label = "9Router" if p.kind == "router9" else p.kind
                        yield Static(
                            f"{marker}  {p.id:<20s}  kind={kind_label:<12s}  base={base}\n"
                            f"      status={status}  credentials={key_status}"
                        )

            yield Static("")
            yield Static("Esc  Close")

    def action_close(self) -> None:
        self.dismiss()
