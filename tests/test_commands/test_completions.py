"""Tests for cc_manager.commands.completions"""
import pytest


def _invoke(shell):
    from typer.testing import CliRunner
    from typer import Typer
    from cc_manager.commands.completions import completions_cmd
    app = Typer()
    app.command()(completions_cmd)
    return CliRunner().invoke(app, [shell])


def test_completions_bash():
    result = _invoke("bash")
    assert result.exit_code == 0
    assert "_ccm_completion" in result.output
    assert "complete" in result.output


def test_completions_zsh():
    result = _invoke("zsh")
    assert result.exit_code == 0
    assert "compdef" in result.output or "_ccm" in result.output


def test_completions_fish():
    result = _invoke("fish")
    assert result.exit_code == 0
    assert "complete" in result.output
    assert "ccm" in result.output


def test_completions_invalid_shell():
    result = _invoke("powershell")
    assert result.exit_code != 0
    assert "Unknown shell" in result.output


def test_completions_bash_includes_commands():
    result = _invoke("bash")
    assert "init" in result.output
    assert "install" in result.output
    assert "list" in result.output
