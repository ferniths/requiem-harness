"""Configuration loader — reads and validates TOML config files.

The loader returns a fully-validated `ConfigModel`.  If the file does
not exist, a default `ConfigModel` is returned (first-run state).
"""

from __future__ import annotations

import logging
import pathlib
import tomllib

from pydantic import ValidationError

from requiem.config.models import ConfigModel
from requiem.config.paths import user_config_file
from requiem.core.exceptions import ConfigError

logger = logging.getLogger("requiem.config")


def load_config(path: pathlib.Path | None = None) -> ConfigModel:
    """Load and validate the user configuration.

    If *path* is None, the default user config location is used.
    If the file does not exist, a default ConfigModel is returned.
    """
    if path is None:
        path = user_config_file()

    if not path.exists():
        logger.info("Config file not found at %s; using defaults", path)
        return ConfigModel()

    try:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ConfigError(f"Failed to read config file {path}: {e}") from e

    try:
        return ConfigModel(**raw)
    except ValidationError as e:
        errors = "; ".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors())
        raise ConfigError(f"Config validation failed: {errors}") from e


def _strip_none(obj: dict[str, object]) -> dict[str, object]:
    """Recursively remove None values from a dict (TOML doesn't support null)."""
    result: dict[str, object] = {}
    for k, v in obj.items():
        if v is None:
            continue
        if isinstance(v, dict):
            result[k] = _strip_none(v)
        elif isinstance(v, list):
            result[k] = [_strip_none(i) if isinstance(i, dict) else i for i in v]
        else:
            result[k] = v
    return result


def save_config(config: ConfigModel, path: pathlib.Path | None = None) -> None:
    """Serialize and write the config model to disk.

    Secrets are NOT written here — API keys stay in the credential vault.
    """
    import tomli_w

    if path is None:
        path = user_config_file()

    path.parent.mkdir(parents=True, exist_ok=True)
    data = _strip_none(config.model_dump(mode="json"))
    with open(path, "w", encoding="utf-8") as f:
        f.write(tomli_w.dumps(data))
    logger.info("Config saved to %s", path)


def is_first_run() -> bool:
    """Return True if the user config file does not exist yet."""
    return not user_config_file().exists()
