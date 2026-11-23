"""Unit tests for the tool registry and filesystem tools."""

from __future__ import annotations

import pathlib
import tempfile

import pytest

from requiem.security.permissions import PermissionLevel
from requiem.tools.base import ToolContext, ToolStatus
from requiem.tools.filesystem import (
    CreateFileTool,
    DeleteFileTool,
    ListDirectoryTool,
    ReadFileTool,
)
from requiem.tools.registry import ToolRegistry


@pytest.fixture
def workspace() -> str:
    """Create a temporary workspace directory."""
    with tempfile.TemporaryDirectory() as tmp:
        # Create some files for testing
        pathlib.Path(tmp, "test.txt").write_text("hello world")
        pathlib.Path(tmp, "src").mkdir()
        pathlib.Path(tmp, "src", "main.py").write_text("print('hi')")
        yield tmp


def _ctx(workspace: str) -> ToolContext:
    return ToolContext(workspace_root=workspace)


class TestFilesystemTools:
    async def test_list_directory(self, workspace: str):
        tool = ListDirectoryTool()
        result = await tool.execute({"path": "."}, context=_ctx(workspace))
        assert result.status == ToolStatus.SUCCESS
        names = [e["name"] for e in result.data["entries"]]
        assert "test.txt" in names
        assert "src" in names

    async def test_read_file(self, workspace: str):
        tool = ReadFileTool()
        result = await tool.execute({"path": "test.txt"}, context=_ctx(workspace))
        assert result.status == ToolStatus.SUCCESS
        assert result.data["lines"] == ["hello world"]

    async def test_read_file_not_found(self, workspace: str):
        tool = ReadFileTool()
        result = await tool.execute({"path": "nonexistent.txt"}, context=_ctx(workspace))
        assert result.status == ToolStatus.ERROR

    async def test_create_file(self, workspace: str):
        tool = CreateFileTool()
        result = await tool.execute({"path": "newfile.txt", "content": "new content"}, context=_ctx(workspace))
        assert result.status == ToolStatus.SUCCESS
        assert pathlib.Path(workspace, "newfile.txt").read_text() == "new content"

    async def test_create_file_already_exists(self, workspace: str):
        tool = CreateFileTool()
        result = await tool.execute({"path": "test.txt", "content": "overwrite"}, context=_ctx(workspace))
        assert result.status == ToolStatus.ERROR
        assert "already exists" in result.error

    async def test_delete_file(self, workspace: str):
        tool = DeleteFileTool()
        result = await tool.execute({"path": "test.txt"}, context=_ctx(workspace))
        assert result.status == ToolStatus.SUCCESS
        assert not pathlib.Path(workspace, "test.txt").exists()

    async def test_path_traversal_denied(self, workspace: str):
        tool = ReadFileTool()
        # Try to escape the workspace
        result = await tool.execute({"path": "../../etc/passwd"}, context=_ctx(workspace))
        assert result.status == ToolStatus.DENIED
        assert "outside the workspace" in result.error


class TestToolRegistry:
    async def test_registry_has_all_tools(self):
        reg = ToolRegistry(workspace_root="/tmp")
        names = reg.tool_names
        assert "read_file" in names
        assert "list_directory" in names
        assert "execute_command" in names
        assert "http_request" in names

    def test_get_definitions_returns_openai_format(self):
        reg = ToolRegistry(workspace_root="/tmp")
        defs = reg.get_definitions()
        assert isinstance(defs, list)
        assert len(defs) > 0
        for d in defs:
            assert d["type"] == "function"
            assert "name" in d["function"]
            assert "parameters" in d["function"]

    async def test_call_unknown_tool_denied(self):
        reg = ToolRegistry(workspace_root="/tmp")
        result = await reg.call("nonexistent_tool", {}, context=ToolContext())
        assert result.status == ToolStatus.DENIED
        assert "Unknown tool" in result.error

    async def test_call_read_file_permission_denied_at_read_level(self):
        """A registry capped at READ level should deny WRITE tools."""
        reg = ToolRegistry(workspace_root="/tmp", permission_level=PermissionLevel.READ)
        result = await reg.call("create_file", {"path": "x.txt", "content": "hi"}, context=ToolContext())
        assert result.status == ToolStatus.DENIED
        assert "Permission level" in result.error

    async def test_call_read_file_allowed(self, workspace: str):
        reg = ToolRegistry(workspace_root=workspace, permission_level=PermissionLevel.READ)
        result = await reg.call("read_file", {"path": "test.txt"}, context=ToolContext(workspace_root=workspace))
        assert result.status == ToolStatus.SUCCESS
