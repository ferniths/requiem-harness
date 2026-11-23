"""Pydantic models for REQUIEM configuration.

These models define the shape of the configuration persisted on disk.
Validation happens here; the loader just deserializes into these.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ProviderCredentials(BaseModel):
    """Non-secret parts of a provider configuration.

    The API key itself is stored in the credential vault (keyring) and
    is NOT included in this model.
    """

    api_key_ref: str = Field(description="Identifier used to look up the API key in the credential vault.")
    base_url: str | None = None
    custom_headers: dict[str, str] = Field(default_factory=dict)
    model: str | None = None
    timeout_s: float = Field(default=60.0, ge=1.0)
    # OpenAI-compatible compatibility knobs
    compat: dict[str, str] = Field(default_factory=dict, description="Provider-specific compatibility options.")

    model_config = ConfigDict(frozen=True)


class ProviderConfig(BaseModel):
    id: str = Field(description="Unique provider identifier.")
    name: str = Field(description="Display name.")
    kind: str = Field(description="openai | anthropic | openrouter | router9 | custom")
    credentials: ProviderCredentials
    default_model: str | None = None
    enabled: bool = True


class ThemeConfig(BaseModel):
    active: str = "classic"  # classic | blue | purple | magenta | grey
    use_nerd_fonts: bool = False
    use_truecolor: bool = True


class TerminalConfig(BaseModel):
    color_mode: str = "auto"  # auto | truecolor | 256 | mono
    unicode: bool = True
    wrap_text: bool = True
    mouse: bool = False


class LoggingConfig(BaseModel):
    level: str = "INFO"  # DEBUG | INFO | WARNING | ERROR
    file: str | None = None
    max_bytes: int = 5_000_000
    backup_count: int = 3


class ExecutionLimits(BaseModel):
    max_concurrent_agents: int = Field(default=8, ge=1, le=64)
    max_concurrent_tasks: int = Field(default=16, ge=1, le=128)
    max_review_iterations: int = Field(default=3, ge=0, le=10)
    default_timeout_s: float = Field(default=120.0, ge=1.0)
    max_retry_attempts: int = Field(default=3, ge=0, le=10)


class ToolPermissions(BaseModel):
    default_workspace: str | None = Field(
        default=None,
        description="Absolute path of the default workspace root. Filesystem tools are restricted to this path by default.",
    )
    allow_shell: bool = True
    allow_http: bool = True
    require_approval_for: list[str] = Field(
        default_factory=lambda: ["shell", "http", "delete_file"],
        description="Tool names that require human approval by default.",
    )


class AgentDefaults(BaseModel):
    default_provider: str | None = None
    default_model: str | None = None
    system_instructions: str | None = None


class ConfigModel(BaseModel):
    """Root configuration model.

    Mirrors the structure of the TOML file at `user_config_file()`.
    """

    schema_version: int = 1
    theme: ThemeConfig = Field(default_factory=ThemeConfig)
    terminal: TerminalConfig = Field(default_factory=TerminalConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    providers: list[ProviderConfig] = Field(default_factory=list)
    default_provider: str | None = None
    default_model: str | None = None
    agents: AgentDefaults = Field(default_factory=AgentDefaults)
    execution: ExecutionLimits = Field(default_factory=ExecutionLimits)
    tool_permissions: ToolPermissions = Field(default_factory=ToolPermissions)
