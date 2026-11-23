"""Abstract base class and shared utilities for all provider implementations.

Every provider conforms to this interface.  The agent engine and TUI
depend only on `BaseProvider`, never on a specific implementation.
"""

from __future__ import annotations

import abc
import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from requiem.providers.models import (
    ChatMessage,
    ProviderCapabilities,
    ProviderRequest,
    ProviderResponse,
    StreamEvent,
    ToolDefinition,
)

logger = logging.getLogger("requiem.providers")


class BaseProvider(abc.ABC):
    """Unified provider interface.

    Subclasses implement the four abstract methods.  Everything else
    (retry logic, capability queries, normalization) is handled here.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Short identifier, e.g. 'openai', 'anthropic'."""
        ...

    @property
    @abc.abstractmethod
    def display_name(self) -> str:
        """Human-readable name, e.g. 'OpenAI / ChatGPT'."""
        ...

    @abc.abstractmethod
    async def complete(
        self,
        request: ProviderRequest,
        *,
        api_key: str | None = None,
    ) -> ProviderResponse:
        """Execute a single (non-streaming) completion."""
        ...

    @abc.abstractmethod
    def stream(
        self,
        request: ProviderRequest,
        *,
        api_key: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Execute a streaming completion, yielding normalized events."""
        ...

    @abc.abstractmethod
    async def list_models(
        self,
        *,
        api_key: str | None = None,
    ) -> list[str] | None:
        """Return available model identifiers, or None if discovery is unsupported."""
        ...

    @abc.abstractmethod
    async def validate_connection(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
    ) -> tuple[bool, str]:
        """Validate credentials and endpoint.  Returns (ok, message)."""
        ...

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities()

    def supports_tools(self) -> bool:
        return self.get_capabilities().tool_calls

    # -- Convenience helpers -------------------------------------------------

    def build_request(
        self,
        messages: list[ChatMessage],
        *,
        model: str,
        tools: list[ToolDefinition] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
        metadata: dict[str, Any] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> ProviderRequest:
        return ProviderRequest(
            model=model,
            messages=messages,
            tools=tools or [],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
            metadata=metadata or {},
            tool_choice=tool_choice,
        )

    # -- Retry / backoff -----------------------------------------------------

    async def complete_with_retry(
        self,
        request: ProviderRequest,
        *,
        api_key: str | None = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
        jitter: float = 0.5,
    ) -> ProviderResponse:
        """Complete with exponential backoff for retryable errors.

        Non-retryable errors (auth, invalid request) are raised immediately.
        """
        import random

        from requiem.core.exceptions import (
            ProviderAuthError,
            ProviderError,
            ProviderRateLimitError,
            ProviderTimeoutError,
        )

        last_error: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                return await self.complete(request, api_key=api_key)
            except ProviderAuthError:
                raise  # never retry auth failures
            except ProviderRateLimitError as e:
                last_error = e
                delay = e.retry_after or (base_delay * (2**attempt)) + random.uniform(0, jitter)
                logger.warning(
                    "Rate limited on %s (attempt %d/%d); retrying in %.1fs",
                    self.name,
                    attempt + 1,
                    max_retries + 1,
                    delay,
                )
                if attempt < max_retries:
                    await asyncio.sleep(delay)
                    continue
                raise
            except ProviderTimeoutError as e:
                last_error = e
                if attempt < max_retries:
                    delay = base_delay * (2**attempt) + random.uniform(0, jitter)
                    logger.warning("Timeout on %s (attempt %d); retrying in %.1fs", self.name, attempt + 1, delay)
                    await asyncio.sleep(delay)
                    continue
                raise
            except ProviderError as e:
                if e.retryable and attempt < max_retries:
                    last_error = e
                    delay = base_delay * (2**attempt) + random.uniform(0, jitter)
                    logger.warning(
                        "Provider error on %s (attempt %d): %s; retrying in %.1fs",
                        self.name,
                        attempt + 1,
                        e.message,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise

        # Unreachable — all paths raise
        if last_error:
            raise last_error
        raise ProviderError("complete_with_retry: unexpected state", component=self.name)
