"""Centralized tool registry — registers, validates, and dispatches tool calls.

The registry enforces permission checks before any tool executes.
Agents cannot bypass these checks through prompts.
"""

from __future__ import annotations

import logging
from typing import Any

from requiem.security.permissions import PermissionChecker, PermissionLevel
from requiem.tools.base import Tool, ToolContext, ToolResult, ToolStatus
from requiem.tools.filesystem import (
    CreateDirectoryTool,
    CreateFileTool,
    DeleteFileTool,
    FileMetadataTool,
    ListDirectoryTool,
    ModifyFileTool,
    ReadFileTool,
    SearchFilesTool,
    SearchInFileTool,
)
from requiem.tools.http import HttpRequestTool
from requiem.tools.shell import ExecuteCommandTool

logger = logging.getLogger("requiem.tools.registry")

# Default tool instances (one per tool type)
_BUILTIN_TOOLS: list[type[Tool]] = [
    ListDirectoryTool,
    ReadFileTool,
    SearchFilesTool,
    SearchInFileTool,
    FileMetadataTool,
    CreateFileTool,
    ModifyFileTool,
    CreateDirectoryTool,
    DeleteFileTool,
    ExecuteCommandTool,
    HttpRequestTool,
]

def _level_rank(level: PermissionLevel) -> int:
    """Numeric rank for permission level comparison (READ=0 … DESTRUCTIVE=4)."""
    return {
        PermissionLevel.READ: 0,
        PermissionLevel.WRITE: 1,
        PermissionLevel.EXECUTE: 2,
        PermissionLevel.NETWORK: 3,
        PermissionLevel.DESTRUCTIVE: 4,
    }.get(level, 99)


class ToolRegistry:

    """Holds all available tools and dispatches calls with permission checks.

    Usage:
        registry = ToolRegistry()
        result = await registry.call("read_file", {"path": "src/main.py"}, context)
    """

    def __init__(
        self,
        workspace_root: str = ".",
        permission_level: PermissionLevel = PermissionLevel.WRITE,
        allowed_tools: list[str] | None = None,
    ) -> None:
        self._tools: dict[str, Tool] = {}
        self._permission_level = permission_level
        self._permission_checker = PermissionChecker(
            workspace_root=workspace_root,
        )
        self._allowed = set(allowed_tools) if allowed_tools else None


        # Instantiate all built-in tools
        for tool_cls in _BUILTIN_TOOLS:
            tool = tool_cls()
            self._tools[tool.name] = tool

        # Filter if a whitelist was provided
        if self._allowed is not None:
            self._tools = {k: v for k, v in self._tools.items() if k in self._allowed}

    @property
    def tool_names(self) -> list[str]:
        """List of available tool names."""
        return sorted(self._tools.keys())

    def get_tool(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def get_definitions(self) -> list[dict[str, Any]]:
        """Return tool definitions in OpenAI tool-call format for LLM prompts."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                },
            }
            for tool in self._tools.values()
        ]

    async def call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        context: ToolContext | None = None,
    ) -> ToolResult:
        """Execute a tool call with permission enforcement.

        Raises:
            KeyError: if tool_name is not in the registry.
            PermissionError_: if the permission level is insufficient.
        """
        tool = self._tools.get(tool_name)
        if tool is None:
            return ToolResult(
                ToolStatus.DENIED,
                error=f"Unknown tool: {tool_name!r}. Available: {self.tool_names}",
            )

        ctx = context or ToolContext()

        # Permission level check — enforced in code, not in prompts
        required_level = tool.permission_level
        if required_level and _level_rank(required_level) > _level_rank(self._permission_level):
            return ToolResult(
                ToolStatus.DENIED,
                error=f"Permission level {required_level.value} required; registry max is {self._permission_level.value}",
            )

        try:
            self._permission_checker.check(tool_name, arguments)
        except Exception as e:
            logger.warning("Permission denied for tool %s: %s", tool_name, e)
            if ctx.audit_log is not None:
                ctx.audit_log.record(
                    tool=tool_name,
                    description=f"Permission denied: {e}",
                    arguments=arguments,
                    sensitive=True,
                )
            return ToolResult(ToolStatus.DENIED, error=str(e))

        try:
            result = await tool.execute(arguments, context=ctx)
            if ctx.audit_log is not None and (required_level is PermissionLevel.DESTRUCTIVE or required_level is PermissionLevel.EXECUTE):
                ctx.audit_log.record(
                    tool=tool_name,
                    description=f"Tool {tool_name} executed (status={result.status.value})",
                    arguments=arguments,
                    sensitive=required_level is PermissionLevel.DESTRUCTIVE,
                )
            return result
        except Exception as e:
            logger.exception("Tool %s raised unexpected error", tool_name)
            return ToolResult(ToolStatus.ERROR, error=str(e))
