"""Unit tests for the security module (credentials and permissions)."""

from __future__ import annotations

import os

import pytest

from requiem.core.exceptions import CredentialError
from requiem.security.credentials import CredentialVault
from requiem.security.permissions import PermissionChecker, PermissionLevel


class TestCredentialVault:
    def test_mask_short_key(self):
        vault = CredentialVault(use_keyring=False)
        assert vault.mask("abc") == "****"

    def test_mask_long_key(self):
        vault = CredentialVault(use_keyring=False)
        result = vault.mask("sk-very-long-key-1234567890")
        assert result.endswith("7890")
        assert "sk-" not in result

    def test_store_and_retrieve_env_fallback(self, monkeypatch):
        monkeypatch.delenv("REQUIEM_TESTPROV", raising=False)
        vault = CredentialVault(use_keyring=False)
        vault.store("testprov", None, "secret-key-123")
        # Env-var backend stores in os.environ
        assert os.environ.get("REQUIEM_TESTPROV") == "secret-key-123"
        assert vault.retrieve("testprov") == "secret-key-123"

    def test_require_missing_key_raises(self):
        vault = CredentialVault(use_keyring=False)
        with pytest.raises(CredentialError):
            vault.require("nonexistent-provider-xyz")

    def test_has_key(self, monkeypatch):
        monkeypatch.setenv("REQUIEM_MYPROV", "test123")
        vault = CredentialVault(use_keyring=False)
        assert vault.has("myprov") is True
        assert vault.has("otherprov") is False

    def test_delete_key(self, monkeypatch):
        monkeypatch.setenv("REQUIEM_DELMYPROV", "delete-me")
        vault = CredentialVault(use_keyring=False)
        assert vault.delete("delmyprov") is True
        assert vault.has("delmyprov") is False

    def test_backend_is_env_when_keyring_disabled(self):
        vault = CredentialVault(use_keyring=False)
        assert vault.backend == "env"


class TestPermissionLevel:
    def test_from_string(self):
        assert PermissionLevel.from_string("read") is PermissionLevel.READ
        assert PermissionLevel.from_string("destructive") is PermissionLevel.DESTRUCTIVE

    def test_all_levels(self):
        assert len(list(PermissionLevel)) == 5


class TestPermissionChecker:
    def test_check_known_tool_returns_level(self):
        checker = PermissionChecker(workspace_root="/tmp/test-ws")
        level = checker.check("read_file", {})
        assert level is PermissionLevel.READ

    def test_check_unknown_tool_returns_none(self):
        checker = PermissionChecker(workspace_root="/tmp/test-ws")
        assert checker.check("nonexistent_tool", {}) is None

    def test_check_path_inside_workspace(self, tmp_path):
        checker = PermissionChecker(workspace_root=str(tmp_path))
        inside = tmp_path / "somefile.py"
        assert checker.check_path(str(inside)) is True

    def test_check_path_outside_workspace_denied(self, tmp_path):
        checker = PermissionChecker(workspace_root=str(tmp_path))
        assert checker.check_path("/etc/passwd") is False

    def test_check_path_traversal_denied(self):
        import pathlib
        root = pathlib.Path(__file__).parent
        checker = PermissionChecker(workspace_root=str(root))
        assert checker.check_path("../../etc/passwd") is False
