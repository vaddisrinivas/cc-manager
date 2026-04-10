"""Tests for cc_manager.hooks."""
from unittest.mock import patch

from cc_manager import hooks


def test_dispatch_unknown_event():
    assert hooks.dispatch("UnknownEvent", {}) == {}


def test_session_end_noop():
    assert hooks._session_end({}) == {}


def test_post_tool_use_noop():
    assert hooks._post_tool_use({}) == {}


def test_stop_noop():
    assert hooks._stop({}) == {}


def test_session_start_no_tools():
    with patch("cc_manager.hooks.installer.load_installed", return_value={"tools": {}}):
        result = hooks._session_start({})
    assert result == {}


def test_session_start_all_tools_present():
    installed = {"tools": {"rtk": {"method": "cargo"}}}
    reg = {"rtk": {"name": "rtk", "detect": {"command": "echo ok"}}}
    with patch("cc_manager.hooks.installer.load_installed", return_value=installed), \
         patch("cc_manager.hooks.registry.as_map", return_value=reg):
        result = hooks._session_start({})
    assert result == {}


def test_session_start_missing_tool():
    installed = {"tools": {"bad-tool": {"method": "cargo"}}}
    reg = {"bad-tool": {"name": "bad-tool", "detect": {"command": "nonexistent_binary_xyz"}}}
    with patch("cc_manager.hooks.installer.load_installed", return_value=installed), \
         patch("cc_manager.hooks.registry.as_map", return_value=reg):
        result = hooks._session_start({})
    assert "bad-tool" in result.get("additionalContext", "")


def test_session_start_no_detect_command():
    installed = {"tools": {"t": {"method": "manual"}}}
    reg = {"t": {"name": "t", "detect": {}}}
    with patch("cc_manager.hooks.installer.load_installed", return_value=installed), \
         patch("cc_manager.hooks.registry.as_map", return_value=reg):
        result = hooks._session_start({})
    assert result == {}
