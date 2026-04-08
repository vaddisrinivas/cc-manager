"""Tests for cc_manager.commands.export_import"""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest


@pytest.fixture(autouse=True)
def reset_ctx():
    import cc_manager.context as ctx_mod
    ctx_mod._ctx = None
    yield
    ctx_mod._ctx = None


def test_export_stdout():
    ctx = MagicMock()
    ctx.config = {"backup_on_change": True}
    ctx.installed = {"tools": {"rtk": {}, "context7": {}}}
    with patch("cc_manager.commands.export_import.get_ctx", return_value=ctx):
        from typer.testing import CliRunner
        from typer import Typer
        from cc_manager.commands.export_import import export_cmd
        app = Typer()
        app.command()(export_cmd)
        result = CliRunner().invoke(app)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["schema_version"] == 1
    assert set(data["tools"]) == {"rtk", "context7"}


def test_export_to_file(tmp_path):
    ctx = MagicMock()
    ctx.config = {}
    ctx.installed = {"tools": {"rtk": {}}}
    out = tmp_path / "export.json"
    with patch("cc_manager.commands.export_import.get_ctx", return_value=ctx):
        from typer.testing import CliRunner
        from typer import Typer
        from cc_manager.commands.export_import import export_cmd
        app = Typer()
        app.command()(export_cmd)
        result = CliRunner().invoke(app, ["--output", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    data = json.loads(out.read_text())
    assert "rtk" in data["tools"]


def test_export_empty_tools():
    ctx = MagicMock()
    ctx.config = {}
    ctx.installed = {"tools": {}}
    with patch("cc_manager.commands.export_import.get_ctx", return_value=ctx):
        from typer.testing import CliRunner
        from typer import Typer
        from cc_manager.commands.export_import import export_cmd
        app = Typer()
        app.command()(export_cmd)
        result = CliRunner().invoke(app)
    assert result.exit_code == 0
    assert json.loads(result.output)["tools"] == []


def test_import_dry_run(tmp_path):
    export_data = {"schema_version": 1, "cc_manager_version": "0.1.0", "tools": ["rtk", "context7"]}
    f = tmp_path / "export.json"
    f.write_text(json.dumps(export_data), encoding="utf-8")
    from typer.testing import CliRunner
    from typer import Typer
    from cc_manager.commands.export_import import import_cmd
    app = Typer()
    app.command()(import_cmd)
    result = CliRunner().invoke(app, [str(f), "--dry-run"])
    assert result.exit_code == 0
    assert "Would install" in result.output


def test_import_round_trip(tmp_path):
    """Export then import produces the same tool list."""
    ctx = MagicMock()
    ctx.config = {}
    ctx.installed = {"tools": {"rtk": {}}}
    out = tmp_path / "export.json"

    with patch("cc_manager.commands.export_import.get_ctx", return_value=ctx):
        from typer.testing import CliRunner
        from typer import Typer
        from cc_manager.commands.export_import import export_cmd
        app = Typer()
        app.command()(export_cmd)
        CliRunner().invoke(app, ["--output", str(out)])

    data = json.loads(out.read_text())
    assert data["tools"] == ["rtk"]
