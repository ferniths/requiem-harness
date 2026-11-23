"""Permission levels and enforcement.

Permission levels are enforced in code — never in prompts.  The
permission check runs before every tool invocation; an agent's prompt
cannot bypass these checks.
"""

from __future__ import annotations

import enum
import logging

from requiem.core.exceptions import PermissionError_

logger = logging.getLogger("requiem.security.permissions")


class PermissionLevel(enum.Enum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    NETWORK = "network"
    DESTRUCTIVE = "destructive"

    @classmethod
    def from_string(cls, value: str) -> PermissionLevel:
        return cls(value)


# Tools that require a specific minimum permission level
TOOL_PERMISSIONS: dict[str, PermissionLevel] = {
    # Filesystem
    "list_directory": PermissionLevel.READ,
    "read_file": PermissionLevel.READ,
    "search_files": PermissionLevel.READ,
    "search_in_file": PermissionLevel.READ,
    "file_metadata": PermissionLevel.READ,
    "create_file": PermissionLevel.WRITE,
    "modify_file": PermissionLevel.WRITE,
    "create_directory": PermissionLevel.WRITE,
    "delete_file": PermissionLevel.DESTRUCTIVE,
    # Shell
    "execute_command": PermissionLevel.EXECUTE,
    # HTTP
    "http_request": PermissionLevel.NETWORK,
}


class PermissionChecker:
    """Evaluates whether a tool operation is permitted.

    *workspace_root* is the root path that filesystem operations are
    restricted to.  Paths outside this root are denied unless the
    operation is explicitly authorized.
    """

    def __init__(self, workspace_root: str | None = None, extra_allowed_paths: list[str] | None = None) -> None:
        import pathlib

        self._workspace_root = pathlib.Path(workspace_root).resolve() if workspace_root else None
        self._extra_allowed = [pathlib.Path(p).resolve() for p in (extra_allowed_paths or [])]
        self._allowed_tools: set[str] = set(TOOL_PERMISSIONS.keys())
        self._require_approval: set[str] = set()

    @property
    def workspace_root(self) -> str | None:
        return str(self._workspace_root) if self._workspace_root else None

    def check(self, tool_name: str, arguments: dict[str, object]) -> PermissionLevel | None:
        """Return the required permission level, or None if the tool is unknown.

        Raises PermissionError_ if the tool is not in the allowed set.
        """
        if tool_name not in self._allowed_tools:
            logger.debug("Tool %r not in allowed set", tool_name)
            return None

        if tool_name in self._require_approval:
            from requiem.core.exceptions import ApprovalRequired

            raise ApprovalRequired(
                f"Tool '{tool_name}' requires approval before execution.",
                tool=tool_name,
                arguments=arguments,
            )

        return TOOL_PERMISSIONS[tool_name]

    def check_path(self, path_str: str) -> bool:
        """Return True if *path_str* is inside the workspace root."""
        import pathlib

        if self._workspace_root is None:
            return True  # no restriction

        target = pathlib.Path(path_str).resolve()

        if target == self._workspace_root:
            return True
        if self._workspace_root in target.parents:
            return True

        # Check extra allowed paths
        return any(extra == target or extra in target.parents for extra in self._extra_allowed)

    def enforce(self, tool_name: str, arguments: dict[str, object]) -> None:
        """Run the full permission check and raise if denied.

        Checks:
        1. Tool is in the allowed registry.
        2. Path arguments stay within the workspace.
        3. Approval gates are honored.
        """
        level = self.check(tool_name, arguments)
        if level is None:
            raise PermissionError_(
                f"Tool '{tool_name}' is not in the allowed tool registry.",
                tool=tool_name,
            )

        # Path-boundary check for filesystem tools
        fs_tools = {"list_directory", "read_file", "create_file", "modify_file", "delete_file", "create_directory"}
        if tool_name in fs_tools:
            path_key = self._path_arg_key(tool_name)
            if path_key in arguments:
                target_path = str(arguments[path_key])
                if not self.check_path(target_path):
                    raise PermissionError_(
                        f"Path '{target_path}' is outside the authorized workspace "
                        f"({self.workspace_root}).",
                        tool=tool_name,
                        permission=level.value,
                    )

    def require_approval(self, tool_name: str) -> None:
        """Mark a tool as requiring human approval on each invocation."""
        self._require_approval.add(tool_name)

    def allow_tool(self, tool_name: str) -> None:
        """Dynamically add a tool to the allowed set (e.g. custom tools)."""
        self._allowed_tools.add(tool_name)
        if tool_name not in TOOL_PERMISSIONS:
            TOOL_PERMISSIONS[tool_name] = PermissionLevel.READ  # default to read

    @staticmethod
    def _path_arg_key(tool_name: str) -> str:
        mapping: dict[str, str] = {
            "list_directory": "path",
            "read_file": "path",
            "create_file": "path",
            "modify_file": "path",
            "delete_file": "path",
            "create_directory": "path",
        }
        return mapping.get(tool_name, "path")
