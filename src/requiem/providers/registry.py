"""Provider registry — maps provider kind to implementation class."""

from __future__ import annotations

import logging
from typing import Any

from requiem.providers.implementations.openai import (
    OpenAICompatibleProvider,
    OpenAIProvider,
)

logger = logging.getLogger("requiem.providers.registry")

KIND_OPENAI = "openai"
KIND_ANTHROPIC = "anthropic"
KIND_OPENROUTER = "openrouter"
KIND_ROUTER9 = "router9"
KIND_CUSTOM = "custom"

SUPPORTED_KINDS = (KIND_OPENAI, KIND_ANTHROPIC, KIND_OPENROUTER, KIND_ROUTER9, KIND_CUSTOM)


def create_provider(
    kind: str,
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout_s: float = 60.0,
    custom_headers: dict[str, str] | None = None,
    compat: dict[str, str] | None = None,
    model_list: list[str] | None = None,
) -> Any:
    """Instantiate a provider implementation for the given kind.

    Lazy-imports implementation modules so that missing dependencies
    produce clear errors at call time rather than at import time.
    """
    if kind == KIND_OPENAI:
        return OpenAIProvider(
            base_url=base_url or "https://api.openai.com/v1",
            api_key=api_key or "",
            timeout_s=timeout_s,
            custom_headers=custom_headers,
            compat=compat,
        )

    if kind == KIND_ANTHROPIC:
        from requiem.providers.implementations.anthropic import AnthropicProvider

        return AnthropicProvider(
            base_url=base_url or "https://api.anthropic.com",
            api_key=api_key or "",
            timeout_s=timeout_s,
        )

    if kind == KIND_OPENROUTER:
        from requiem.providers.implementations.openrouter import OpenRouterProvider

        return OpenRouterProvider(
            base_url=base_url or "https://openrouter.ai/api/v1",
            api_key=api_key or "",
            timeout_s=timeout_s,
            custom_headers=custom_headers,
            compat=compat,
        )

    if kind == KIND_ROUTER9:
        from requiem.providers.implementations.router9 import Router9Provider

        return Router9Provider(
            base_url=base_url or "https://api.router9.com/v1",
            api_key=api_key or "",
            timeout_s=timeout_s,
            custom_headers=custom_headers,
            compat=compat,
            model_list=model_list,
        )

    if kind == KIND_CUSTOM:
        if not base_url:
            raise ValueError("Custom provider requires a base_url")
        return OpenAICompatibleProvider(
            base_url=base_url,
            api_key=api_key or "",
            timeout_s=timeout_s,
            custom_headers=custom_headers,
            compat=compat,
        )

    raise ValueError(
        f"Unknown provider kind: {kind!r}. Supported: {', '.join(SUPPORTED_KINDS)}"
    )


def provider_for_config(
    config: Any,
    *,
    api_key: str | None = None,
    model_list: list[str] | None = None,
) -> Any:
    """Build a provider from a ProviderConfig object."""
    creds = getattr(config, "credentials", None)
    base_url = getattr(creds, "base_url", None) if creds else None
    timeout_s = getattr(creds, "timeout_s", 60.0) if creds else 60.0
    custom_headers = getattr(creds, "custom_headers", None) if creds else None
    compat = getattr(creds, "compat", None) if creds else None

    return create_provider(
        config.kind,
        base_url=base_url,
        api_key=api_key,
        timeout_s=timeout_s,
        custom_headers=custom_headers,
        compat=compat,
        model_list=model_list,
    )


__all__ = [
    "SUPPORTED_KINDS",
    "KIND_ANTHROPIC",
    "KIND_CUSTOM",
    "KIND_OPENAI",
    "KIND_OPENROUTER",
    "KIND_ROUTER9",
    "create_provider",
    "provider_for_config",
]
