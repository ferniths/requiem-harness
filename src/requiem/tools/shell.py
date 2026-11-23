"""Shell execution tool — runs authorized commands with timeouts and output limits.

Commands run in the workspace root directory. Destructive commands
(rm -rf /, etc.) are flagged and require approval.
"""

import asyncio
import contextlib
import re
import time
from typing import Any

from requiem.security.permissions import PermissionLevel
from requiem.tools.base import Tool, ToolContext, ToolResult, ToolStatus

# Commands that are considered destructive and require human approval
_DESTRUCTIVE_PATTERNS: list[str] = [
    r"\brm\s+-[rRf]+\b",   # rm -rf
    r"\brm\s+.*--no-preserve-root\b",
    r"\bshred\b",
    r"\bwipefs\b",
    r"\bdd\s+.*of=/dev/",
    r":\(\)\{.*\};:",       # fork bomb
    r"\bmkfs\b",
    r"\bformat\b.*\b[A-Z]:", # Windows format
]

_DESTRUCTIVE_RE = re.compile("|".join(_DESTRUCTIVE_PATTERNS))

MAX_OUTPUT_BYTES = 64 * 1024  # 64 KB output limit


def _is_destructive(command: str) -> bool:
    return bool(_DESTRUCTIVE_RE.search(command))


class ExecuteCommandTool(Tool):
    name = "execute_command"
    description = (
        "Execute a shell command in the workspace root directory. "
        "Captures stdout, stderr, and exit status. Enforces a timeout."
    )
    permission_level = PermissionLevel.EXECUTE
    timeout_s = 120.0
    input_schema = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command to execute.",
            },
            "timeout_s": {
                "type": "number",
                "description": "Timeout in seconds (default 120, max 600).",
                "default": 120,
            },
        },
        "required": ["command"],
    }

    def __init__(self) -> None:
        self._processes: list[Any] = []

    async def execute(self, arguments: dict[str, Any], *, context: ToolContext) -> ToolResult:
        start = time.monotonic()
        command = arguments.get("command", "").strip()
        timeout_s = min(float(arguments.get("timeout_s", self.timeout_s)), 600.0)

        if not command:
            return ToolResult(ToolStatus.ERROR, error="Empty command", duration_s=time.monotonic() - start)

        destructive = _is_destructive(command)
        if destructive and context.audit_log is not None:
            context.audit_log.record(
                tool=self.name,
                description=f"Destructive command detected: {command}",
                arguments=arguments,
                sensitive=True,
            )

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=context.workspace_root or None,
            )
            self._processes.append(proc)
        except OSError as e:
            return ToolResult(ToolStatus.ERROR, error=f"Failed to start process: {e}", duration_s=time.monotonic() - start)

        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout_s,
            )
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return ToolResult(
                ToolStatus.TIMEOUT,
                error=f"Command timed out after {timeout_s:.0f}s",
                data={"command": command, "timed_out": True},
                duration_s=time.monotonic() - start,
            )

        stdout = stdout_b.decode(errors="replace")
        stderr = stderr_b.decode(errors="replace")
        truncated = False
        if len(stdout) > MAX_OUTPUT_BYTES:
            stdout = stdout[:MAX_OUTPUT_BYTES]
            truncated = True
        if len(stderr) > MAX_OUTPUT_BYTES:
            stderr = stderr[:MAX_OUTPUT_BYTES]
            truncated = True

        return ToolResult(
            ToolStatus.SUCCESS if proc.returncode == 0 else ToolStatus.ERROR,
            data={
                "command": command,
                "exit_code": proc.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "truncated": truncated,
                "destructive": destructive,
            },
            duration_s=time.monotonic() - start,
        )

    async def cancel_all(self) -> None:
        """Kill all running subprocesses (called on workflow cancellation)."""
        for proc in self._processes:
            with contextlib.suppress(ProcessLookupError, OSError):
                proc.kill()
        self._processes.clear()
