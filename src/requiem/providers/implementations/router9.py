"""9Router provider — first-class OpenAI-compatible aggregator integration.

9Router is a self-hosted / configurable API aggregator that exposes an
OpenAI-compatible endpoint.  Users configure their own base URL, API key,
custom headers, and model list.

Key differences from stock OpenAI:
- No /models discovery endpoint by default (may be available on some builds).
- May return slightly different usage fields.
- Custom headers may be required for authentication.

The provider accepts a `compat` dict to tune behavior for specific 9Router
builds (e.g. {"stream_format": "openai" | "simplified"}).
"""

from __future__ import annotations

import logging

import httpx

from requiem.providers.implementations.openai import OpenAICompatibleProvider

logger = logging.getLogger("requiem.providers.router9")


class Router9Provider(OpenAICompatibleProvider):
    """9Router — configurable OpenAI-compatible aggregator."""

    def __init__(
        self,
        *,
        base_url: str = "https://api.router9.com/v1",
        api_key: str = "",
        timeout_s: float = 60.0,
        custom_headers: dict[str, str] | None = None,
        compat: dict[str, str] | None = None,
        model_list: list[str] | None = None,
    ) -> None:
        super().__init__(
            base_url=base_url,
            api_key=api_key,
            timeout_s=timeout_s,
            custom_headers=custom_headers,
            compat=compat,
        )
        # Manually configured model list (used when discovery is unavailable)
        self._model_list: list[str] | None = model_list

    @property
    def name(self) -> str:
        return "router9"

    @property
    def display_name(self) -> str:
        return "9Router"

    async def list_models(
        self,
        *,
        api_key: str | None = None,
    ) -> list[str] | None:
        """Return the configured model list, or try discovery if available.

        9Router installations vary — some expose /models, some don't.
        If the user provided an explicit model_list, use that first.
        """
        if api_key:
            self._api_key = api_key

        # Use manually configured list when available
        if self._model_list:
            return list(self._model_list)

        # Try discovery endpoint; some 9Router builds don't support it
        client = await self._get_client()
        try:
            resp = await client.get("/models")
            if resp.status_code == 404:
                logger.debug("9Router: /models endpoint not available (404)")
                return None
            if resp.status_code >= 400:
                return None
            data = resp.json()
            return [m.get("id", "") for m in data.get("data", []) if m.get("id")]
        except httpx.ConnectError:
            return None
        except Exception:
            logger.debug("9Router: model discovery failed", exc_info=True)
            return None

    async def validate_connection(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
    ) -> tuple[bool, str]:
        """Validate 9Router endpoint with special handling for aggregators.

        9Router may not expose /models, so we fall back to a minimal
        completion probe when discovery is unavailable.
        """
        if api_key:
            self._api_key = api_key

        # First try model discovery
        client = await self._get_client()
        try:
            resp = await client.get("/models")
            if resp.status_code in (401, 403):
                return False, "Authentication failed. Check your 9Router API key."
            if resp.status_code == 404:
                # No models endpoint — try a minimal completion instead
                return await self._validate_by_probe(model)
            if resp.status_code >= 400:
                return False, f"Endpoint returned HTTP {resp.status_code}"

            # Endpoint reachable and authenticated
            models = [m.get("id", "") for m in resp.json().get("data", []) if m.get("id")]
            if model and models and model not in models:
                return True, f"Connected. Model '{model}' not in 9Router's model list."
            return True, "9Router connection OK"

        except httpx.ConnectError:
            return False, f"Cannot reach 9Router at {self._base_url}. Check the URL."
        except httpx.TimeoutException:
            return False, f"9Router connection timed out after {self._timeout}s"

    async def _validate_by_probe(self, model: str | None) -> tuple[bool, str]:
        """Validate via a minimal completion request when /models is unavailable."""
        probe_model = model or "gpt-4o-mini"
        client = await self._get_client()
        try:
            resp = await client.post(
                "/chat/completions",
                json={
                    "model": probe_model,
                    "messages": [{"role": "user", "content": "Hi"}],
                    "max_tokens": 5,
                },
            )
            if resp.status_code in (401, 403):
                return False, "Authentication failed. Check your 9Router API key."
            if resp.status_code >= 400:
                body = resp.text[:300]
                return False, f"9Router probe failed (HTTP {resp.status_code}): {body}"
            return True, "9Router connection OK (validated via completion probe)"
        except httpx.ConnectError:
            return False, f"Cannot reach 9Router at {self._base_url}"
        except httpx.TimeoutException:
            return False, f"9Router probe timed out after {self._timeout}s"
