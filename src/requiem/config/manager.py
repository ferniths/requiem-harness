"""Configuration manager — in-memory accessor for the active config.

Singleton-ish pattern: the application creates one `ConfigManager` at
startup and passes it to subsystems that need configuration access.
"""

from __future__ import annotations

import logging
import pathlib

from requiem.config.loader import load_config, save_config
from requiem.config.migration import migrate
from requiem.config.models import ConfigModel, ProviderConfig

logger = logging.getLogger("requiem.config")


class ConfigManager:
    """Manages the application configuration lifecycle."""

    def __init__(self, config_path: pathlib.Path | None = None) -> None:
        self._path = config_path
        self._config = load_config(config_path)
        self._config = migrate(self._config)

    @property
    def config(self) -> ConfigModel:
        return self._config

    def get_provider(self, provider_id: str) -> ProviderConfig | None:
        for p in self._config.providers:
            if p.id == provider_id:
                return p
        return None

    def add_provider(self, provider: ProviderConfig) -> None:
        # Replace if same id exists
        self._config.providers = [p for p in self._config.providers if p.id != provider.id]
        self._config.providers.append(provider)
        self.save()

    def remove_provider(self, provider_id: str) -> None:
        self._config.providers = [p for p in self._config.providers if p.id != provider_id]
        if self._config.default_provider == provider_id:
            self._config.default_provider = None
        self.save()

    def set_default_provider(self, provider_id: str) -> None:
        if self.get_provider(provider_id):
            self._config.default_provider = provider_id
            self.save()

    def save(self) -> None:
        save_config(self._config, self._path)

    @property
    def path(self) -> pathlib.Path:
        return self._path or pathlib.Path()

    @property
    def schema_version(self) -> int:
        return self._config.schema_version
