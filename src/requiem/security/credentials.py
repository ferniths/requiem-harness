"""Credential vault — secure API key storage.

Uses the OS keyring (Windows Credential Manager, macOS Keychain, Linux
secret-service) via the `keyring` package.  Falls back to environment
variables when keyring is unavailable.  Never writes plaintext keys to
the filesystem or logs.
"""

from __future__ import annotations

import logging
import os

from requiem.core.exceptions import CredentialError

logger = logging.getLogger("requiem.security.credentials")

# Service name used by keyring for all REQUIEM credentials
_SERVICE = "requiem"


class CredentialVault:
    """Abstract credential store backed by keyring with env-var fallback."""

    def __init__(self, use_keyring: bool = True) -> None:
        self._use_keyring = use_keyring and self._keyring_available()
        if not self._use_keyring:
            logger.warning("keyring unavailable; falling back to environment variables only")

    @staticmethod
    def _keyring_available() -> bool:
        try:
            import keyring  # noqa: F401

            return True
        except ImportError:
            return False

    @property
    def backend(self) -> str:
        return "keyring" if self._use_keyring else "env"

    def store(self, provider_id: str, model_id: str | None, key: str) -> None:
        """Store an API key.

        The keyring identifier is `{provider_id}` or `{provider_id}:{model_id}`
        when model-specific credentials are needed.
        """
        ref = self._ref(provider_id, model_id)
        if self._use_keyring:
            import keyring

            try:
                keyring.set_password(_SERVICE, ref, key)
                logger.debug("Stored credential for %s in keyring", ref)
            except Exception as e:
                raise CredentialError(f"Failed to store credential in keyring: {e}") from e
        else:
            env_var = self._env_name(ref)
            os.environ[env_var] = key
            logger.warning("Credential for %s stored in environment variable %s", ref, env_var)

    def retrieve(self, provider_id: str, model_id: str | None = None) -> str | None:
        """Retrieve an API key.  Returns None if not found."""
        ref = self._ref(provider_id, model_id)
        if self._use_keyring:
            import keyring

            try:
                return keyring.get_password(_SERVICE, ref)
            except Exception as e:
                logger.debug("keyring retrieval failed: %s", e)
                return None
        else:
            return os.environ.get(self._env_name(ref))

    def delete(self, provider_id: str, model_id: str | None = None) -> bool:
        ref = self._ref(provider_id, model_id)
        if self._use_keyring:
            import keyring

            try:
                keyring.delete_password(_SERVICE, ref)
                return True
            except Exception:
                return False
        else:
            var = self._env_name(ref)
            if var in os.environ:
                del os.environ[var]
                return True
            return False

    def has(self, provider_id: str, model_id: str | None = None) -> bool:
        ref = self._ref(provider_id, model_id)
        if self._use_keyring:
            import keyring

            try:
                return keyring.get_password(_SERVICE, ref) is not None
            except Exception:
                return False
        else:
            return self._env_name(ref) in os.environ

    @staticmethod
    def _ref(provider_id: str, model_id: str | None) -> str:
        return f"{provider_id}:{model_id}" if model_id else provider_id

    @staticmethod
    def _env_name(ref: str) -> str:
        return f"REQUIEM_{ref.upper().replace(':', '_').replace('-', '_')}"

    def require(self, provider_id: str, model_id: str | None = None) -> str:
        """Retrieve or raise CredentialError."""
        key = self.retrieve(provider_id, model_id)
        if key is None:
            raise CredentialError(
                f"No API key found for provider '{provider_id}'. "
                "Add credentials via the Provider Manager or set the environment variable "
                f"{self._env_name(self._ref(provider_id, model_id))}."
            )
        return key

    def mask(self, key: str) -> str:
        """Return a masked version of the key for display."""
        if len(key) <= 8:
            return "****"
        return f"{'*' * 4}{key[-4:]}"
