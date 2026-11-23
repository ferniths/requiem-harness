"""OpenRouter provider — OpenAI-compatible with provider routing metadata.

OpenRouter exposes an OpenAI-compatible API at https://openrouter.ai/api/v1.
It adds optional provider routing via the `provider` field in the request
payload, and a `models` endpoint for discovery.
"""

from __future__ import annotations

import logging
from typing import Any

from requiem.providers.implementations.openai import OpenAICompatibleProvider

logger = logging.getLogger("requiem.providers.openrouter")


class OpenRouterProvider(OpenAICompatibleProvider):
    def __init__(
        self,
        *,
        base_url: str = "https://openrouter.ai/api/v1",
        api_key: str = "",
        timeout_s: float = 60.0,
        custom_headers: dict[str, str] | None = None,
        compat: dict[str, str] | None = None,
    ) -> None:
        super().__init__(
            base_url=base_url,
            api_key=api_key,
            timeout_s=timeout_s,
            custom_headers=custom_headers,
            compat=compat,
        )

    @property
    def name(self) -> str:
        return "openrouter"

    @property
    def display_name(self) -> str:
        return "OpenRouter"

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            # OpenRouter identifies the client app
            "HTTP-Referer": "https://github.com/requiem/requiem",
            "X-Title": "REQUIEM",
            **self._custom_headers,
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _build_payload(self, request: Any, *, stream: bool = False) -> dict[str, Any]:
        """Extend the base payload with OpenRouter-specific fields."""
        payload = super()._build_payload(request, stream=stream)
        # Allow provider routing via metadata (e.g. {"provider": {"order": ["openai"]}})
        routing = request.metadata.get("routing") if hasattr(request, "metadata") else None
        if routing:
            payload["provider"] = routing
        return payload
