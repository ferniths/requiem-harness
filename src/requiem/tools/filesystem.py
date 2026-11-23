"""Filesystem tools — all operations are relative to the workspace root.

Path traversal and symlink escapes are rejected.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from requiem.security.permissions import PermissionLevel
from requiem.tools.base import Tool, ToolContext, ToolResult, ToolStatus


def _resolve_safe(workspace_root: str, relative_path: str) -> Path:
    """Resolve *relative_path* inside *workspace_root*, rejecting traversal.

    Raises ValueError if the resolved path escapes the workspace.
    """
    root = Path(workspace_root).resolve()
    target = (root / relative_path).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise ValueError(
            f"Path '{relative_path}' resolves outside the workspace root"
        ) from None
    return target

class ListDirectoryTool(Tool):
    name = "list_directory"
    description = "List files and subdirectories in a directory."
    permission_level = PermissionLevel.READ
    timeout_s = 10.0
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory path relative to workspace root (use '.' for root).",
                "default": ".",
            },
        },
        "required": [],
    }

    async def execute(self, arguments: dict[str, Any], *, context: ToolContext) -> ToolResult:
        start = time.monotonic()
        path_str = arguments.get("path", ".")
        try:
            target = _resolve_safe(context.workspace_root, path_str)
            if not target.is_dir():
                return ToolResult(ToolStatus.ERROR, error=f"Not a directory: {path_str}", duration_s=time.monotonic() - start)
            entries = []
            for item in sorted(target.iterdir()):
                entry: dict[str, Any] = {"name": item.name, "type": "dir" if item.is_dir() else "file"}
                if item.is_file():
                    try:
                        entry["size"] = item.stat().st_size
                    except OSError:
                        entry["size"] = None
                entries.append(entry)
            return ToolResult(ToolStatus.SUCCESS, data={"path": path_str, "entries": entries}, duration_s=time.monotonic() - start)
        except ValueError as e:
            return ToolResult(ToolStatus.DENIED, error=str(e), duration_s=time.monotonic() - start)
        except OSError as e:
            return ToolResult(ToolStatus.ERROR, error=str(e), duration_s=time.monotonic() - start)


class ReadFileTool(Tool):
    name = "read_file"
    description = "Read the contents of a text file."
    permission_level = PermissionLevel.READ
    timeout_s = 15.0
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path relative to workspace root."},
            "offset": {"type": "integer", "description": "Start line (1-indexed). Omit for from beginning."},
            "limit": {"type": "integer", "description": "Max lines to return."},
        },
        "required": ["path"],
    }

    MAX_BYTES = 256 * 1024  # 256 KB read limit

    async def execute(self, arguments: dict[str, Any], *, context: ToolContext) -> ToolResult:
        start = time.monotonic()
        path_str = arguments.get("path", "")
        offset = int(arguments.get("offset") or 1)
        limit = int(arguments.get("limit") or 10_000)
        try:
            target = _resolve_safe(context.workspace_root, path_str)
            if not target.is_file():
                return ToolResult(ToolStatus.ERROR, error=f"File not found: {path_str}", duration_s=time.monotonic() - start)
            stat = target.stat()
            truncated = False
            if stat.st_size > self.MAX_BYTES:
                truncated = True
            content = target.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            if offset > 1:
                lines = lines[offset - 1:]
            if len(lines) > limit:
                lines = lines[:limit]
                truncated = True
            return ToolResult(
                ToolStatus.SUCCESS,
                data={"path": path_str, "lines": lines, "total_lines": stat.st_size and len(content.splitlines()), "truncated": truncated},
                duration_s=time.monotonic() - start,
            )
        except ValueError as e:
            return ToolResult(ToolStatus.DENIED, error=str(e), duration_s=time.monotonic() - start)
        except OSError as e:
            return ToolResult(ToolStatus.ERROR, error=str(e), duration_s=time.monotonic() - start)


class SearchFilesTool(Tool):
    name = "search_files"
    description = "Find files matching a glob pattern."
    permission_level = PermissionLevel.READ
    timeout_s = 15.0
    input_schema = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Glob pattern (e.g. '*.py')."},
            "path": {"type": "string", "description": "Subdirectory to search (default: workspace root)."},
        },
        "required": ["pattern"],
    }

    async def execute(self, arguments: dict[str, Any], *, context: ToolContext) -> ToolResult:
        start = time.monotonic()
        pattern = arguments.get("pattern", "*")
        path_str = arguments.get("path", ".")
        try:
            target = _resolve_safe(context.workspace_root, path_str)
            if not target.is_dir():
                return ToolResult(ToolStatus.ERROR, error=f"Not a directory: {path_str}", duration_s=time.monotonic() - start)
            matches = sorted(str(p.relative_to(context.workspace_root)) for p in target.rglob(pattern) if p.is_file())
            return ToolResult(ToolStatus.SUCCESS, data={"pattern": pattern, "matches": matches[:200]}, duration_s=time.monotonic() - start)
        except ValueError as e:
            return ToolResult(ToolStatus.DENIED, error=str(e), duration_s=time.monotonic() - start)


class SearchInFileTool(Tool):
    name = "search_in_file"
    description = "Search for a regex pattern within a file's lines."
    permission_level = PermissionLevel.READ
    timeout_s = 15.0
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path."},
            "pattern": {"type": "string", "description": "Regex pattern to search for."},
        },
        "required": ["path", "pattern"],
    }

    async def execute(self, arguments: dict[str, Any], *, context: ToolContext) -> ToolResult:
        start = time.monotonic()
        path_str = arguments.get("path", "")
        pattern = arguments.get("pattern", "")
        try:
            target = _resolve_safe(context.workspace_root, path_str)
            if not target.is_file():
                return ToolResult(ToolStatus.ERROR, error=f"File not found: {path_str}", duration_s=time.monotonic() - start)
            content = target.read_text(encoding="utf-8", errors="replace")
            try:
                regex = re.compile(pattern, re.MULTILINE)
            except re.error as e:
                return ToolResult(ToolStatus.ERROR, error=f"Invalid regex: {e}", duration_s=time.monotonic() - start)
            results = []
            for i, line in enumerate(content.splitlines(), 1):
                if regex.search(line):
                    results.append({"line": i, "text": line})
                if len(results) >= 100:
                    break
            return ToolResult(ToolStatus.SUCCESS, data={"path": path_str, "pattern": pattern, "matches": results, "truncated": len(results) >= 100}, duration_s=time.monotonic() - start)
        except ValueError as e:
            return ToolResult(ToolStatus.DENIED, error=str(e), duration_s=time.monotonic() - start)
        except OSError as e:
            return ToolResult(ToolStatus.ERROR, error=str(e), duration_s=time.monotonic() - start)


class FileMetadataTool(Tool):
    name = "file_metadata"
    description = "Get file/directory metadata (size, modified time, permissions)."
    permission_level = PermissionLevel.READ
    timeout_s = 5.0
    input_schema = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    }

    async def execute(self, arguments: dict[str, Any], *, context: ToolContext) -> ToolResult:
        start = time.monotonic()
        try:
            target = _resolve_safe(context.workspace_root, arguments.get("path", ""))
            st = target.stat()
            return ToolResult(
                ToolStatus.SUCCESS,
                data={
                    "path": arguments.get("path"),
                    "is_file": target.is_file(),
                    "is_dir": target.is_dir(),
                    "size": st.st_size if target.is_file() else None,
                    "modified": st.st_mtime,
                },
                duration_s=time.monotonic() - start,
            )
        except ValueError as e:
            return ToolResult(ToolStatus.DENIED, error=str(e), duration_s=time.monotonic() - start)
        except OSError as e:
            return ToolResult(ToolStatus.ERROR, error=str(e), duration_s=time.monotonic() - start)


class CreateFileTool(Tool):
    name = "create_file"
    description = "Create a new file with the given content. Fails if the file already exists."
    permission_level = PermissionLevel.WRITE
    timeout_s = 10.0
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path relative to workspace root."},
            "content": {"type": "string", "description": "File content."},
        },
        "required": ["path", "content"],
    }

    async def execute(self, arguments: dict[str, Any], *, context: ToolContext) -> ToolResult:
        start = time.monotonic()
        path_str = arguments.get("path", "")
        content = arguments.get("content", "")
        try:
            target = _resolve_safe(context.workspace_root, path_str)
            if target.exists():
                return ToolResult(ToolStatus.ERROR, error=f"File already exists: {path_str}", duration_s=time.monotonic() - start)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return ToolResult(ToolStatus.SUCCESS, data={"path": path_str, "bytes_written": len(content.encode())}, duration_s=time.monotonic() - start)
        except ValueError as e:
            return ToolResult(ToolStatus.DENIED, error=str(e), duration_s=time.monotonic() - start)
        except OSError as e:
            return ToolResult(ToolStatus.ERROR, error=str(e), duration_s=time.monotonic() - start)


class ModifyFileTool(Tool):
    name = "modify_file"
    description = "Write content to an existing or new file (replaces content)."
    permission_level = PermissionLevel.WRITE
    timeout_s = 10.0
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["path", "content"],
    }

    async def execute(self, arguments: dict[str, Any], *, context: ToolContext) -> ToolResult:
        start = time.monotonic()
        path_str = arguments.get("path", "")
        content = arguments.get("content", "")
        try:
            target = _resolve_safe(context.workspace_root, path_str)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return ToolResult(ToolStatus.SUCCESS, data={"path": path_str, "bytes_written": len(content.encode())}, duration_s=time.monotonic() - start)
        except ValueError as e:
            return ToolResult(ToolStatus.DENIED, error=str(e), duration_s=time.monotonic() - start)
        except OSError as e:
            return ToolResult(ToolStatus.ERROR, error=str(e), duration_s=time.monotonic() - start)


class CreateDirectoryTool(Tool):
    name = "create_directory"
    description = "Create a directory (and parents as needed)."
    permission_level = PermissionLevel.WRITE
    timeout_s = 5.0
    input_schema = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    }

    async def execute(self, arguments: dict[str, Any], *, context: ToolContext) -> ToolResult:
        start = time.monotonic()
        try:
            target = _resolve_safe(context.workspace_root, arguments.get("path", ""))
            target.mkdir(parents=True, exist_ok=True)
            return ToolResult(ToolStatus.SUCCESS, data={"path": arguments.get("path")}, duration_s=time.monotonic() - start)
        except ValueError as e:
            return ToolResult(ToolStatus.DENIED, error=str(e), duration_s=time.monotonic() - start)
        except OSError as e:
            return ToolResult(ToolStatus.ERROR, error=str(e), duration_s=time.monotonic() - start)


class DeleteFileTool(Tool):
    name = "delete_file"
    description = "Delete a file. This is a destructive operation and requires approval."
    permission_level = PermissionLevel.DESTRUCTIVE
    timeout_s = 5.0
    input_schema = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    }

    async def execute(self, arguments: dict[str, Any], *, context: ToolContext) -> ToolResult:
        start = time.monotonic()
        try:
            target = _resolve_safe(context.workspace_root, arguments.get("path", ""))
            if not target.is_file():
                return ToolResult(ToolStatus.ERROR, error=f"File not found: {arguments.get('path')}", duration_s=time.monotonic() - start)
            target.unlink()
            return ToolResult(ToolStatus.SUCCESS, data={"deleted": arguments.get("path")}, duration_s=time.monotonic() - start)
        except ValueError as e:
            return ToolResult(ToolStatus.DENIED, error=str(e), duration_s=time.monotonic() - start)
        except OSError as e:
            return ToolResult(ToolStatus.ERROR, error=str(e), duration_s=time.monotonic() - start)
