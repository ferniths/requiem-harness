"""Configuration migration support.

Currently only schema_version=1 exists, so migration is a no-op.
This module is the designated extension point for future schema changes.
"""

from __future__ import annotations

from requiem.config.models import ConfigModel

CURRENT_SCHEMA_VERSION = 1


def migrate(config: ConfigModel) -> ConfigModel:
    """Migrate a config model to the current schema version.

    Returns the same model unchanged if already at current version.
    Future migrations will add version-specific transforms here.
    """
    if config.schema_version == CURRENT_SCHEMA_VERSION:
        return config

    # Future: add version-specific migration steps.
    # For now, just bump the version (safe for v1 -> v1).
    config.schema_version = CURRENT_SCHEMA_VERSION
    return config
