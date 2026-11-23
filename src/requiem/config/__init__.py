"""Configuration package."""

from requiem.config.manager import ConfigManager
from requiem.config.models import (
    AgentDefaults,
    ConfigModel,
    ExecutionLimits,
    LoggingConfig,
    ProviderConfig,
    ProviderCredentials,
    TerminalConfig,
    ThemeConfig,
    ToolPermissions,
)
from requiem.config.paths import (
    project_agents_dir,
    project_artifacts_dir,
    project_logs_dir,
    project_requiem_dir,
    project_workflows_dir,
    user_config_file,
    user_config_path,
    user_data_path,
    user_db_path,
    user_log_path,
)

__all__ = [
    "AgentDefaults",
    "ConfigManager",
    "ConfigModel",
    "ExecutionLimits",
    "LoggingConfig",
    "ProviderConfig",
    "ProviderCredentials",
    "TerminalConfig",
    "ThemeConfig",
    "ToolPermissions",
    # Paths
    "project_agents_dir",
    "project_artifacts_dir",
    "project_logs_dir",
    "project_requiem_dir",
    "project_workflows_dir",
    "user_config_file",
    "user_config_path",
    "user_data_path",
    "user_db_path",
    "user_log_path",
]
