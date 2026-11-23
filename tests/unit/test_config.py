"""Unit tests for the config module."""

from __future__ import annotations

import pathlib

import pytest
from pydantic import ValidationError

from requiem.config.loader import load_config, save_config
from requiem.config.models import (
    ConfigModel,
    ProviderConfig,
    ProviderCredentials,
)


class TestConfigModel:
    def test_default_config(self):
        cfg = ConfigModel()
        assert cfg.schema_version == 1
        assert cfg.theme.active == "classic"
        assert cfg.providers == []
        assert cfg.default_provider is None

    def test_provider_credentials_frozen(self):
        creds = ProviderCredentials(api_key_ref="test-key")
        with pytest.raises(ValidationError):
            creds.api_key_ref = "other-key"  # type: ignore[union-attr]

    def test_theme_config_valid_values(self):
        cfg = ConfigModel()
        assert cfg.theme.active in ("classic", "blue", "purple", "magenta", "grey")


class TestConfigLoader:
    def test_load_nonexistent_returns_default(self, tmp_path: pathlib.Path):
        cfg = load_config(tmp_path / "nonexistent.toml")
        assert isinstance(cfg, ConfigModel)
        assert cfg.providers == []

    def test_save_and_load_roundtrip(self, tmp_path: pathlib.Path):
        cfg = ConfigModel()
        cfg.theme.active = "blue"
        cfg.providers = [
            ProviderConfig(
                id="test-openai",
                name="Test OpenAI",
                kind="openai",
                credentials=ProviderCredentials(api_key_ref="test-openai"),
                default_model="gpt-4o-mini",
            )
        ]
        cfg.default_provider = "test-openai"

        path = tmp_path / "config.toml"
        save_config(cfg, path)
        assert path.exists()

        loaded = load_config(path)
        assert loaded.theme.active == "blue"
        assert len(loaded.providers) == 1
        assert loaded.providers[0].id == "test-openai"
        assert loaded.default_provider == "test-openai"

    def test_malformed_toml_raises(self, tmp_path: pathlib.Path):
        path = tmp_path / "bad.toml"
        path.write_text("this is not [[valid toml")
        from requiem.core.exceptions import ConfigError

        with pytest.raises(ConfigError):
            load_config(path)


class TestProviderConfig:
    def test_router9_provider(self):
        p = ProviderConfig(
            id="my-router9",
            name="My 9Router",
            kind="router9",
            credentials=ProviderCredentials(
                api_key_ref="my-router9",
                base_url="http://localhost:8080/v1",
                custom_headers={"X-Custom": "value"},
            ),
        )
        assert p.kind == "router9"
        assert p.credentials.base_url == "http://localhost:8080/v1"

    def test_custom_provider_requires_kind(self):
        p = ProviderConfig(
            id="local",
            name="Local LLM",
            kind="custom",
            credentials=ProviderCredentials(api_key_ref="local", base_url="http://localhost:11434/v1"),
        )
        assert p.kind == "custom"
