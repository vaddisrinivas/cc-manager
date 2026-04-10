"""Tests for cc_manager.cli — all 8 commands."""
from unittest.mock import patch, MagicMock

import pytest
from typer.testing import CliRunner

from cc_manager.cli import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "2.0.0" in result.output


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "init" in result.output
    assert "install" in result.output
    assert "remove" in result.output


# -- list --------------------------------------------------------------------

def test_list_all():
    result = runner.invoke(app, ["list", "--tier", "recommended"])
    assert result.exit_code == 0
    assert "rtk" in result.output


def test_list_installed_empty():
    with patch("cc_manager.cli.load_installed", return_value={"tools": {}}):
        result = runner.invoke(app, ["list", "--installed"])
    assert result.exit_code == 0
    assert "No tools" in result.output


def test_list_installed():
    installed = {"tools": {"rtk": {"method": "cargo", "installed_at": "2026-01-01T00:00:00"}}}
    with patch("cc_manager.cli.load_installed", return_value=installed):
        result = runner.invoke(app, ["list", "--installed"])
    assert result.exit_code == 0
    assert "rtk" in result.output


# -- search ------------------------------------------------------------------

def test_search():
    result = runner.invoke(app, ["search", "token"])
    assert result.exit_code == 0
    assert "rtk" in result.output


def test_search_no_results():
    result = runner.invoke(app, ["search", "zzz_nonexistent_12345"])
    assert result.exit_code == 0
    assert "No tools" in result.output


# -- status ------------------------------------------------------------------

def test_status():
    with patch("cc_manager.cli.load_installed", return_value={"tools": {}}), \
         patch("cc_manager.cli.settings.read", return_value={}):
        result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "Tools installed" in result.output


# -- install -----------------------------------------------------------------

def test_install_dry_run():
    with patch("cc_manager.cli.load_installed", return_value={"tools": {}}), \
         patch("cc_manager.cli.installer.install_tool", return_value="cargo"):
        result = runner.invoke(app, ["install", "rtk", "--dry-run"])
    assert result.exit_code == 0
    assert "Would install" in result.output


def test_install_not_found():
    with patch("cc_manager.cli.load_installed", return_value={"tools": {}}), \
         patch("cc_manager.cli.installer.install_tool",
               side_effect=Exception("Tool 'nope' not found")):
        result = runner.invoke(app, ["install", "nope"])
    assert result.exit_code != 0 or "not found" in result.output.lower() or "Error" in result.output


# -- remove ------------------------------------------------------------------

def test_remove_not_installed():
    with patch("cc_manager.cli.load_installed", return_value={"tools": {}}), \
         patch("cc_manager.cli.installer.remove_tool",
               side_effect=Exception("'nope' is not installed")):
        result = runner.invoke(app, ["remove", "nope"])
    assert result.exit_code != 0 or "Error" in result.output


# -- doctor ------------------------------------------------------------------

def test_doctor():
    with patch("cc_manager.cli.load_installed", return_value={"tools": {}}), \
         patch("cc_manager.cli.settings.read", return_value={}), \
         patch("cc_manager.cli.SETTINGS_PATH") as mock_sp, \
         patch("cc_manager.cli.INSTALLED_PATH") as mock_ip:
        mock_sp.exists.return_value = True
        mock_ip.exists.return_value = True
        result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "Doctor" in result.output


# -- reset -------------------------------------------------------------------

def test_reset_requires_confirm():
    result = runner.invoke(app, ["reset"])
    assert result.exit_code == 1
    assert "--confirm" in result.output


# -- init --------------------------------------------------------------------

def test_init_quick():
    with patch("cc_manager.cli.load_installed", return_value={"tools": {}}), \
         patch("cc_manager.cli.installer.install_tool", return_value="cargo"), \
         patch("cc_manager.cli.settings.merge_hooks"):
        result = runner.invoke(app, ["init", "--quick"])
    assert result.exit_code == 0
    assert "Done" in result.output
