"""Tests for cc_manager.installer."""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from cc_manager import installer
from cc_manager.installer import (
    ToolNotFoundError, AlreadyInstalledError, ConflictError, InstallError,
    run_cmd,
)


@pytest.fixture
def tmp_installed(tmp_path):
    """Redirect installed.json to tmp_path."""
    p = tmp_path / "installed.json"
    with patch.object(installer, "INSTALLED_PATH", p):
        yield p


# -- run_cmd -----------------------------------------------------------------

def test_run_cmd_success():
    rc, out = run_cmd("echo hello")
    assert rc == 0
    assert "hello" in out


def test_run_cmd_not_found():
    rc, out = run_cmd("nonexistent_binary_xyz_123")
    assert rc == 127
    assert "not found" in out


def test_run_cmd_timeout():
    rc, out = run_cmd("sleep 10", timeout=1)
    assert rc == 124
    assert "timeout" in out


# -- load / save installed ---------------------------------------------------

def test_load_installed_missing(tmp_installed):
    assert installer.load_installed() == {"tools": {}}


def test_record_and_load(tmp_installed):
    installer.record_installed("rtk", "cargo", "1.0.0")
    data = installer.load_installed()
    assert "rtk" in data["tools"]
    assert data["tools"]["rtk"]["method"] == "cargo"


def test_remove_installed(tmp_installed):
    installer.record_installed("rtk", "cargo")
    installer.remove_installed("rtk")
    assert "rtk" not in installer.load_installed()["tools"]


# -- install_tool ------------------------------------------------------------

def _make_reg(name="test-tool", mtype="cargo", cmd="echo ok", conflicts=None):
    return {name: {
        "name": name,
        "install_methods": [{"type": mtype, "command": cmd}],
        "conflicts_with": conflicts or [],
    }}


def test_install_not_found(tmp_installed):
    with pytest.raises(ToolNotFoundError):
        installer.install_tool("nope", {}, {"tools": {}})


def test_install_already_installed(tmp_installed):
    reg = _make_reg()
    with pytest.raises(AlreadyInstalledError):
        installer.install_tool("test-tool", reg, {"tools": {"test-tool": {}}})


def test_install_conflict(tmp_installed):
    reg = _make_reg(conflicts=["other"])
    with pytest.raises(ConflictError):
        installer.install_tool("test-tool", reg, {"tools": {"other": {}}})


def test_install_dry_run(tmp_installed):
    reg = _make_reg()
    mtype = installer.install_tool("test-tool", reg, {"tools": {}}, dry_run=True)
    assert mtype == "cargo"
    assert installer.load_installed() == {"tools": {}}


def test_install_cargo_success(tmp_installed):
    reg = _make_reg(cmd="echo installed")
    mtype = installer.install_tool("test-tool", reg, {"tools": {}})
    assert mtype == "cargo"
    data = installer.load_installed()
    assert "test-tool" in data["tools"]


def test_install_cargo_failure(tmp_installed):
    reg = _make_reg(cmd="false")
    with pytest.raises(InstallError, match="Install failed"):
        installer.install_tool("test-tool", reg, {"tools": {}})


def test_install_mcp(tmp_installed):
    reg = {"mcp-tool": {
        "name": "mcp-tool",
        "install_methods": [{"type": "mcp", "command": "node server.js --port 3000"}],
        "conflicts_with": [],
    }}
    with patch("cc_manager.settings.merge_mcp") as mock_merge:
        mtype = installer.install_tool("mcp-tool", reg, {"tools": {}})
    assert mtype == "mcp"
    mock_merge.assert_called_once()
    config = mock_merge.call_args[0][1]
    assert config["command"] == "node"
    assert config["args"] == ["server.js", "--port", "3000"]


def test_install_no_methods(tmp_installed):
    reg = {"t": {"name": "t", "install_methods": [], "conflicts_with": []}}
    with pytest.raises(InstallError, match="No install methods"):
        installer.install_tool("t", reg, {"tools": {}})


# -- remove_tool -------------------------------------------------------------

def test_remove_tool(tmp_installed):
    installer.record_installed("rtk", "cargo")
    installed = installer.load_installed()
    installer.remove_tool("rtk", installed)
    assert "rtk" not in installer.load_installed()["tools"]


def test_remove_not_installed(tmp_installed):
    with pytest.raises(ToolNotFoundError):
        installer.remove_tool("nope", {"tools": {}})


def test_remove_mcp_tool(tmp_installed):
    installer.record_installed("mcp-srv", "mcp")
    installed = installer.load_installed()
    with patch("cc_manager.settings.remove_mcp") as mock_rm:
        installer.remove_tool("mcp-srv", installed)
    mock_rm.assert_called_once_with("mcp-srv")
