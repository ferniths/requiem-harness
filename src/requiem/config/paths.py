"""Platform-appropriate file paths for REQUIEM.

Uses platformdirs for user-level paths and supports project-local
`.requiem/` directories for workflow definitions, agents, and artifacts.
"""

from __future__ import annotations

import pathlib

from platformdirs import user_config_dir, user_data_dir, user_log_dir

_APP = "requiem"


def user_config_path() -> pathlib.Path:
    """User-level configuration directory (platformdirs)."""
    p = pathlib.Path(user_config_dir(_APP))
    p.mkdir(parents=True, exist_ok=True)
    return p


def user_data_path() -> pathlib.Path:
    """User-level state and data directory (platformdirs)."""
    p = pathlib.Path(user_data_dir(_APP))
    p.mkdir(parents=True, exist_ok=True)
    return p


def user_log_path() -> pathlib.Path:
    """User-level log directory (platformdirs)."""
    p = pathlib.Path(user_log_dir(_APP))
    p.mkdir(parents=True, exist_ok=True)
    return p


def user_db_path() -> pathlib.Path:
    """Path to the workflow persistence SQLite database."""
    return user_data_path() / "requiem.db"


def user_config_file() -> pathlib.Path:
    """Path to the main user config TOML file."""
    return user_config_path() / "config.toml"


def project_requiem_dir(root: pathlib.Path) -> pathlib.Path:
    """Project-local `.requiem/` directory."""
    p = root / ".requiem"
    p.mkdir(parents=True, exist_ok=True)
    return p


def project_workflows_dir(root: pathlib.Path) -> pathlib.Path:
    p = project_requiem_dir(root) / "workflows"
    p.mkdir(parents=True, exist_ok=True)
    return p


def project_agents_dir(root: pathlib.Path) -> pathlib.Path:
    p = project_requiem_dir(root) / "agents"
    p.mkdir(parents=True, exist_ok=True)
    return p


def project_artifacts_dir(root: pathlib.Path) -> pathlib.Path:
    p = project_requiem_dir(root) / "artifacts"
    p.mkdir(parents=True, exist_ok=True)
    return p


def project_logs_dir(root: pathlib.Path) -> pathlib.Path:
    p = project_requiem_dir(root) / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p
