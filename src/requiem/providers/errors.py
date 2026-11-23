"""Provider error classification and mapping to REQUIEM exceptions.

Each provider implementation calls `classify_provider_error()` when
the HTTP response is an error.  This centralizes the logic so that
retry behavior and user-facing messages are consistent.
"""

from __future__ import annotations

import contextlib
import logging

import httpx

from requiem.core.exceptions import (
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)

logger = logging.getLogger("requiem.providers.errors")


def classify_http_error(
    status_code: int,
    response_text: str,
    *,
    provider: str,
    headers: dict[str, str] | None = None,
) -> Exception:
    """Map an HTTP error status to the appropriate REQUIEM exception."""

    if status_code in (401, 403):
        return ProviderAuthError(
            f"{provider}: Authentication failed (HTTP {status_code}). Check your API key.",
            component=provider,
        )
    if status_code == 429:
        retry_after: float | None = None
        if headers and "retry-after" in headers:
            with contextlib.suppress(ValueError, KeyError):
                retry_after = float(headers["retry-after"])
        return ProviderRateLimitError(
            f"{provider}: Rate limited (HTTP 429).",
            component=provider,
            retry_after=retry_after,
        )
    if status_code == 413:
        return ProviderError(
            f"{provider}: Context length exceeded (HTTP 413). The message is too long.",
            component=provider,
        )
    if status_code in (400, 422):
        return ProviderError(
            f"{provider}: Invalid request (HTTP {status_code}). {response_text[:200]}",
            component=provider,
        )
    if status_code in (500, 502, 503, 504):
        return ProviderError(
            f"{provider}: Server error (HTTP {status_code}). {response_text[:200]}",
            component=provider,
            status_code=status_code,
        )
    return ProviderError(
        f"{provider}: Unexpected HTTP {status_code}. {response_text[:200]}",
        component=provider,
        status_code=status_code,
    )


def classify_timeout(timeout: float) -> ProviderTimeoutError:
    return ProviderTimeoutError(f"Request timed out after {timeout:.1f}s.", component="timeout")


def classify_connect_error(exc: httpx.ConnectError, *, provider: str) -> ProviderError:
    return ProviderError(f"{provider}: Connection failed — {exc}", component=provider)


def classify_read_error(exc: httpx.ReadError, *, provider: str) -> ProviderError:
    return ProviderError(f"{provider}: Read error — {exc}", component=provider)


def is_safe_to_retry(exc: Exception) -> bool:
    """Return True if *exc* represents a safely retryable operation."""
    if isinstance(exc, ProviderAuthError):
        return False
    if isinstance(exc, ProviderRateLimitError):
        return True
    if isinstance(exc, ProviderTimeoutError):
        return True
    if isinstance(exc, ProviderError):
        return exc.retryable
    return False
