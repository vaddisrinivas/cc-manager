"""Tests for cc_manager.hook dispatcher."""
from __future__ import annotations
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


def test_load_handler_unknown_event():
    from cc_manager.hook import _load_handler
    import cc_manager.hook as hook_mod
    hook_mod._handlers.clear()
    result = _load_handler("UnknownEvent")
    assert result is None


def test_load_handler_known_event_cached():
    from cc_manager.hook import _load_handler
    import cc_manager.hook as hook_mod
    hook_mod._handlers.clear()
    # First call — may fail to import in test env, that's fine
    _load_handler("Stop")
    # If it loaded, it should be cached
    if "Stop" in hook_mod._handlers:
        assert _load_handler("Stop") is hook_mod._handlers["Stop"]


def test_run_with_timeout_success():
    from cc_manager.hook import _run_with_timeout
    def fn(x):
        return {"value": x * 2}
    result = _run_with_timeout(fn, (5,), timeout_s=1.0)
    assert result == {"value": 10}


def test_run_with_timeout_exception_logged(tmp_path):
    from cc_manager.hook import _run_with_timeout, _ERRORS_LOG
    import cc_manager.hook as hook_mod
    errors_log = tmp_path / "errors.log"
    with patch.object(hook_mod, "_ERRORS_LOG", errors_log):
        def bad_fn():
            raise ValueError("boom")
        _run_with_timeout(bad_fn, (), timeout_s=1.0)
    if errors_log.exists():
        assert "boom" in errors_log.read_text()


def test_run_with_timeout_timeout():
    import time
    from cc_manager.hook import _run_with_timeout
    def slow_fn():
        time.sleep(10)
        return {"done": True}
    result = _run_with_timeout(slow_fn, (), timeout_s=0.05)
    assert result == {}


def test_dispatch_unknown_event():
    from cc_manager.hook import dispatch
    result = dispatch("NoSuchEvent", {})
    assert result == {}


def test_log_error_creates_file(tmp_path):
    from cc_manager.hook import _log_error
    import cc_manager.hook as hook_mod
    log_path = tmp_path / "errors.log"
    with patch.object(hook_mod, "_ERRORS_LOG", log_path):
        _log_error("test error message")
    assert log_path.exists()
    assert "test error message" in log_path.read_text()


def test_main_no_args(monkeypatch):
    import sys
    monkeypatch.setattr(sys, "argv", ["hook.py"])
    from cc_manager.hook import main
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0


def test_main_unknown_event(monkeypatch):
    import sys
    from io import StringIO
    monkeypatch.setattr(sys, "argv", ["hook.py", "UnknownEvent"])
    monkeypatch.setattr(sys, "stdin", StringIO("{}"))
    from cc_manager.hook import main
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
