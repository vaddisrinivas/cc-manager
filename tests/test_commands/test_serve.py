"""Tests for cc_manager.commands.serve — TDD, written before implementation."""
from __future__ import annotations

import io
import json
import sys
import threading
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cc_manager.commands.serve import CCManagerHandler, run
from cc_manager.context import set_ctx
from cc_manager.store import Store


def _call_post(path: str, body: dict) -> tuple[int, dict, bytes]:
    """Call do_POST on a handler and return (status_code, headers, body_bytes)."""
    h = _make_handler("POST", path)
    raw = json.dumps(body).encode()
    h.rfile = io.BytesIO(raw)
    h.headers = {"Content-Length": str(len(raw))}
    h.do_POST()
    return h._status_code, h._sent_headers, h.wfile.getvalue()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_handler(method: str, path: str) -> CCManagerHandler:
    """Instantiate CCManagerHandler without a real socket by mocking transport."""
    handler = CCManagerHandler.__new__(CCManagerHandler)
    handler.path = path
    handler.command = method
    handler.headers = {}
    handler.server = MagicMock()

    # Capture output in a BytesIO buffer
    buf = io.BytesIO()
    handler.wfile = buf
    handler.rfile = io.BytesIO()

    # Collect sent response lines so we can inspect status + headers
    handler._response_lines: list[bytes] = []
    handler._status_code: int | None = None
    handler._sent_headers: dict[str, str] = {}

    def fake_send_response(code, message=None):
        handler._status_code = code

    def fake_send_header(key, value):
        handler._sent_headers[key] = value

    def fake_end_headers():
        pass

    handler.send_response = fake_send_response
    handler.send_header = fake_send_header
    handler.end_headers = fake_end_headers

    return handler


def _call(method: str, path: str) -> tuple[int, dict, bytes]:
    """Call a handler method and return (status_code, headers, body_bytes)."""
    h = _make_handler(method, path)
    h.do_GET()
    body = h.wfile.getvalue()
    return h._status_code, h._sent_headers, body


def _json(body: bytes) -> dict:
    return json.loads(body.decode())


_DEFAULT_TOOLS = {
    "rtk": {
        "version": "0.25.0",
        "method": "cargo",
        "installed_at": "2026-01-01T00:00:00+00:00",
        "pinned": False,
    }
}


class _FakeCtx:
    """Minimal fake context for testing serve handlers."""

    def __init__(
        self,
        store: Store | None = None,
        installed_tools: dict | None = None,
    ):
        import copy
        tools = copy.deepcopy(_DEFAULT_TOOLS) if installed_tools is None else installed_tools
        self.installed = {"schema_version": 1, "tools": tools}
        self.settings = {
            "hooks": {
                "PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "rtk"}]}],
                "PostToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "rtk"}]}],
                "Stop": [{"hooks": [{"type": "command", "command": "ccm session-end"}]}],
            }
        }
        self.config = {}
        self.registry = [
            {"name": "rtk", "method": "cargo"},
            {"name": "context7", "method": "mcp"},
        ]
        self.store = store or Store(Path("/tmp/ccm-test-store.jsonl"))


def _make_ctx(
    store: Store | None = None,
    installed_tools: dict | None = None,
    hooks: int = 3,
) -> _FakeCtx:
    """Build a minimal fake context for serve handler tests."""
    return _FakeCtx(store=store, installed_tools=installed_tools)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_ctx():
    """Reset the module-level context after every test."""
    yield
    set_ctx(None)


@pytest.fixture
def empty_store(tmp_path):
    return Store(tmp_path / "events.jsonl")


@pytest.fixture
def ctx_with_sessions(tmp_path):
    store = Store(tmp_path / "events.jsonl")
    now = datetime.now(timezone.utc)
    # Write a few session_end events
    for i, (model, cost, dur) in enumerate(
        [("sonnet", 0.84, 47), ("sonnet", 1.20, 60), ("opus", 2.00, 90)]
    ):
        ts = (now - timedelta(days=i)).isoformat()
        store.append(
            "session_end",
            session=f"uuid-{i}",
            input_tokens=450000,
            output_tokens=120000,
            cache_read=340000,
            cost_usd=cost,
            duration_min=dur,
            model=model,
        )
    ctx = _make_ctx(store=store)
    return ctx


# ---------------------------------------------------------------------------
# 1. test_route_status
# ---------------------------------------------------------------------------

class TestRouteStatus:
    def test_returns_200(self, empty_store):
        ctx = _make_ctx(store=empty_store)
        set_ctx(ctx)
        status, headers, body = _call("GET", "/api/status")
        assert status == 200

    def test_content_type_json(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        _, headers, _ = _call("GET", "/api/status")
        assert headers.get("Content-Type") == "application/json"

    def test_response_shape(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        _, _, body = _call("GET", "/api/status")
        data = _json(body)
        assert "version" in data
        assert "installed_tools" in data
        assert "hooks_registered" in data
        assert "config_path" in data

    def test_version_matches(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        _, _, body = _call("GET", "/api/status")
        data = _json(body)
        assert data["version"] == "0.1.0"

    def test_installed_tools_list(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        _, _, body = _call("GET", "/api/status")
        data = _json(body)
        tools = data["installed_tools"]
        assert isinstance(tools, list)
        assert len(tools) >= 1
        assert tools[0]["name"] == "rtk"
        assert tools[0]["version"] == "0.25.0"

    def test_hooks_registered_count(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        _, _, body = _call("GET", "/api/status")
        data = _json(body)
        # settings has 3 hook categories
        assert isinstance(data["hooks_registered"], int)
        assert data["hooks_registered"] >= 0

    def test_config_path(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        _, _, body = _call("GET", "/api/status")
        data = _json(body)
        assert "cc-manager" in data["config_path"]
        assert ".toml" in data["config_path"]


# ---------------------------------------------------------------------------
# 2. test_route_tools
# ---------------------------------------------------------------------------

class TestRouteTools:
    def test_returns_200(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        status, _, _ = _call("GET", "/api/tools")
        assert status == 200

    def test_tools_key_present(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        _, _, body = _call("GET", "/api/tools")
        data = _json(body)
        assert "tools" in data
        assert isinstance(data["tools"], list)

    def test_tool_shape(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        _, _, body = _call("GET", "/api/tools")
        data = _json(body)
        t = data["tools"][0]
        assert "name" in t
        assert "version" in t
        assert "method" in t

    def test_tool_data_matches_installed(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        _, _, body = _call("GET", "/api/tools")
        data = _json(body)
        rtk = next((t for t in data["tools"] if t["name"] == "rtk"), None)
        assert rtk is not None
        assert rtk["version"] == "0.25.0"
        assert rtk["method"] == "cargo"

    def test_empty_tools(self, empty_store):
        ctx = _make_ctx(store=empty_store, installed_tools={})
        set_ctx(ctx)
        _, _, body = _call("GET", "/api/tools")
        data = _json(body)
        assert data["tools"] == []


# ---------------------------------------------------------------------------
# 3. test_route_sessions_default (7d)
# ---------------------------------------------------------------------------

class TestRouteSessionsDefault:
    def test_returns_200(self, ctx_with_sessions):
        set_ctx(ctx_with_sessions)
        status, _, _ = _call("GET", "/api/sessions")
        assert status == 200

    def test_sessions_key_present(self, ctx_with_sessions):
        set_ctx(ctx_with_sessions)
        _, _, body = _call("GET", "/api/sessions")
        data = _json(body)
        assert "sessions" in data
        assert isinstance(data["sessions"], list)

    def test_default_7d_includes_recent_sessions(self, ctx_with_sessions):
        set_ctx(ctx_with_sessions)
        _, _, body = _call("GET", "/api/sessions")
        data = _json(body)
        # All 3 sessions are within 7 days
        assert len(data["sessions"]) == 3

    def test_session_shape(self, ctx_with_sessions):
        set_ctx(ctx_with_sessions)
        _, _, body = _call("GET", "/api/sessions")
        data = _json(body)
        s = data["sessions"][0]
        for key in ("ts", "session", "cost_usd", "duration_min", "model"):
            assert key in s, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# 4. test_route_sessions_custom_since
# ---------------------------------------------------------------------------

class TestRouteSessionsCustomSince:
    def test_since_30d_includes_all(self, ctx_with_sessions):
        set_ctx(ctx_with_sessions)
        _, _, body = _call("GET", "/api/sessions?since=30d")
        data = _json(body)
        assert len(data["sessions"]) == 3

    def test_since_1d_filters_older(self, tmp_path):
        store = Store(tmp_path / "events.jsonl")
        now = datetime.now(timezone.utc)
        # Old session (10 days ago)
        old_ts = (now - timedelta(days=10)).isoformat()
        store.append("session_end", session="old", cost_usd=0.5, duration_min=30, model="sonnet")
        # Manually overwrite ts to old value
        import json as _json_mod
        lines = store.path.read_text().splitlines()
        record = _json_mod.loads(lines[-1])
        record["ts"] = old_ts
        store.path.write_text(_json_mod.dumps(record) + "\n")
        # Recent session
        store.append("session_end", session="new", cost_usd=0.8, duration_min=45, model="sonnet")

        ctx = _make_ctx(store=store)
        set_ctx(ctx)
        _, _, body = _call("GET", "/api/sessions?since=1d")
        data = _json(body)
        assert len(data["sessions"]) == 1
        assert data["sessions"][0]["session"] == "new"

    def test_since_param_respected(self, ctx_with_sessions):
        set_ctx(ctx_with_sessions)
        _, _, body = _call("GET", "/api/sessions?since=7d")
        data = _json(body)
        assert isinstance(data["sessions"], list)


# ---------------------------------------------------------------------------
# 5. test_route_analyze
# ---------------------------------------------------------------------------

class TestRouteAnalyze:
    def test_returns_200(self, ctx_with_sessions):
        set_ctx(ctx_with_sessions)
        status, _, _ = _call("GET", "/api/analyze")
        assert status == 200

    def test_response_shape(self, ctx_with_sessions):
        set_ctx(ctx_with_sessions)
        _, _, body = _call("GET", "/api/analyze")
        data = _json(body)
        for key in (
            "period", "total_sessions", "total_input_tokens", "total_output_tokens",
            "total_cache_read", "total_cost_usd", "sessions_per_day", "avg_duration_min",
            "avg_tokens_per_session", "compaction_events", "model_breakdown",
        ):
            assert key in data, f"Missing key: {key}"

    def test_total_sessions_correct(self, ctx_with_sessions):
        set_ctx(ctx_with_sessions)
        _, _, body = _call("GET", "/api/analyze")
        data = _json(body)
        assert data["total_sessions"] == 3

    def test_total_cost_correct(self, ctx_with_sessions):
        set_ctx(ctx_with_sessions)
        _, _, body = _call("GET", "/api/analyze")
        data = _json(body)
        # 0.84 + 1.20 + 2.00 = 4.04
        assert abs(data["total_cost_usd"] - 4.04) < 0.01

    def test_total_input_tokens(self, ctx_with_sessions):
        set_ctx(ctx_with_sessions)
        _, _, body = _call("GET", "/api/analyze")
        data = _json(body)
        # 3 sessions * 450000
        assert data["total_input_tokens"] == 3 * 450000

    def test_model_breakdown_keys(self, ctx_with_sessions):
        set_ctx(ctx_with_sessions)
        _, _, body = _call("GET", "/api/analyze")
        data = _json(body)
        mb = data["model_breakdown"]
        assert isinstance(mb, dict)
        # 2 sonnet, 1 opus → sonnet fraction ~0.667
        assert "sonnet" in mb
        assert "opus" in mb
        assert abs(mb["sonnet"] - 2 / 3) < 0.01
        assert abs(mb["opus"] - 1 / 3) < 0.01

    def test_period_param_reflected(self, ctx_with_sessions):
        set_ctx(ctx_with_sessions)
        _, _, body = _call("GET", "/api/analyze?period=30d")
        data = _json(body)
        assert data["period"] == "30d"

    def test_default_period_7d(self, ctx_with_sessions):
        set_ctx(ctx_with_sessions)
        _, _, body = _call("GET", "/api/analyze")
        data = _json(body)
        assert data["period"] == "7d"

    def test_empty_store_returns_zeros(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        _, _, body = _call("GET", "/api/analyze")
        data = _json(body)
        assert data["total_sessions"] == 0
        assert data["total_cost_usd"] == 0
        assert data["model_breakdown"] == {}

    def test_avg_duration_correct(self, ctx_with_sessions):
        set_ctx(ctx_with_sessions)
        _, _, body = _call("GET", "/api/analyze")
        data = _json(body)
        # (47 + 60 + 90) / 3 ≈ 65.67; rounded to 1 decimal = 65.7
        # Allow 0.1 tolerance to accommodate rounding to 1 decimal place
        assert abs(data["avg_duration_min"] - (47 + 60 + 90) / 3) < 0.1

    def test_compaction_events_counted(self, tmp_path):
        store = Store(tmp_path / "events.jsonl")
        store.append("session_end", session="a", cost_usd=0.5, duration_min=30, model="sonnet",
                     input_tokens=100, output_tokens=50, cache_read=80)
        store.append("compaction", session="a")
        store.append("compaction", session="a")
        ctx = _make_ctx(store=store)
        set_ctx(ctx)
        _, _, body = _call("GET", "/api/analyze")
        data = _json(body)
        assert data["compaction_events"] == 2


# ---------------------------------------------------------------------------
# 6. test_route_events_with_filters
# ---------------------------------------------------------------------------

class TestRouteEvents:
    def test_returns_200(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        status, _, _ = _call("GET", "/api/events")
        assert status == 200

    def test_events_key_present(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        _, _, body = _call("GET", "/api/events")
        data = _json(body)
        assert "events" in data

    def test_filter_by_event_type(self, tmp_path):
        store = Store(tmp_path / "events.jsonl")
        for _ in range(3):
            store.append("install", tool="rtk")
        store.append("doctor")
        store.append("session_end", session="x")
        set_ctx(_make_ctx(store=store))
        _, _, body = _call("GET", "/api/events?event=install")
        data = _json(body)
        assert len(data["events"]) == 3
        assert all(e["event"] == "install" for e in data["events"])

    def test_limit_param(self, tmp_path):
        store = Store(tmp_path / "events.jsonl")
        for i in range(20):
            store.append("install", tool=f"tool{i}")
        set_ctx(_make_ctx(store=store))
        _, _, body = _call("GET", "/api/events?limit=5")
        data = _json(body)
        assert len(data["events"]) == 5

    def test_since_param(self, tmp_path):
        store = Store(tmp_path / "events.jsonl")
        import json as _j
        old_ts = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
        store.append("install", tool="old")
        lines = store.path.read_text().splitlines()
        rec = _j.loads(lines[-1])
        rec["ts"] = old_ts
        store.path.write_text(_j.dumps(rec) + "\n")
        store.append("install", tool="recent")
        set_ctx(_make_ctx(store=store))
        _, _, body = _call("GET", "/api/events?since=7d")
        data = _json(body)
        assert len(data["events"]) == 1
        assert data["events"][0]["tool"] == "recent"

    def test_default_limit_100(self, tmp_path):
        store = Store(tmp_path / "events.jsonl")
        for i in range(150):
            store.append("install", tool=f"t{i}")
        set_ctx(_make_ctx(store=store))
        _, _, body = _call("GET", "/api/events")
        data = _json(body)
        assert len(data["events"]) == 100


# ---------------------------------------------------------------------------
# 7. test_route_doctor
# ---------------------------------------------------------------------------

class TestRouteDoctor:
    def test_returns_200(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        status, _, _ = _call("GET", "/api/doctor")
        assert status == 200

    def test_checks_and_summary_present(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        _, _, body = _call("GET", "/api/doctor")
        data = _json(body)
        assert "checks" in data
        assert "summary" in data

    def test_checks_is_list(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        _, _, body = _call("GET", "/api/doctor")
        data = _json(body)
        assert isinstance(data["checks"], list)
        assert len(data["checks"]) > 0

    def test_check_shape(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        _, _, body = _call("GET", "/api/doctor")
        data = _json(body)
        for check in data["checks"]:
            assert "name" in check
            assert "status" in check
            assert check["status"] in ("ok", "warn", "fail")
            assert "detail" in check

    def test_summary_keys(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        _, _, body = _call("GET", "/api/doctor")
        data = _json(body)
        summary = data["summary"]
        assert "ok" in summary
        assert "warn" in summary
        assert "fail" in summary

    def test_summary_counts_match_checks(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        _, _, body = _call("GET", "/api/doctor")
        data = _json(body)
        checks = data["checks"]
        summary = data["summary"]
        ok = sum(1 for c in checks if c["status"] == "ok")
        warn = sum(1 for c in checks if c["status"] == "warn")
        fail = sum(1 for c in checks if c["status"] == "fail")
        assert summary["ok"] == ok
        assert summary["warn"] == warn
        assert summary["fail"] == fail

    def test_expected_check_names(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        _, _, body = _call("GET", "/api/doctor")
        data = _json(body)
        names = {c["name"] for c in data["checks"]}
        expected = {"settings_json", "config_toml", "store_writable", "python_version"}
        assert expected.issubset(names), f"Missing checks: {expected - names}"


# ---------------------------------------------------------------------------
# 8. test_route_recommend
# ---------------------------------------------------------------------------

class TestRouteRecommend:
    def test_returns_200(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        status, _, _ = _call("GET", "/api/recommend")
        assert status == 200

    def test_recommendations_key_present(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        _, _, body = _call("GET", "/api/recommend")
        data = _json(body)
        assert "recommendations" in data
        assert isinstance(data["recommendations"], list)

    def test_recommendation_shape_when_present(self, empty_store):
        # Use ctx with no MCP servers to trigger the no_mcp_servers rule
        ctx = _make_ctx(
            store=empty_store,
            installed_tools={"rtk": {"version": "0.25.0", "method": "cargo",
                                     "installed_at": "2026-01-01T00:00:00+00:00", "pinned": False}},
        )
        set_ctx(ctx)
        _, _, body = _call("GET", "/api/recommend")
        data = _json(body)
        for rec in data["recommendations"]:
            assert "rule" in rec
            assert "message" in rec


# ---------------------------------------------------------------------------
# 9. test_route_404
# ---------------------------------------------------------------------------

class TestRoute404:
    def test_unknown_path_returns_404(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        status, _, body = _call("GET", "/api/nonexistent")
        assert status == 404

    def test_error_json_shape(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        _, _, body = _call("GET", "/no/such/route")
        data = _json(body)
        assert "error" in data

    def test_root_returns_404(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        status, _, body = _call("GET", "/")
        assert status == 404
        assert _json(body).get("error") == "not found"

    def test_dashboard_returns_404(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        status, _, _ = _call("GET", "/dashboard")
        assert status == 404

    def test_dashboard_wildcard_returns_404(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        status, _, _ = _call("GET", "/dashboard/overview")
        assert status == 404


# ---------------------------------------------------------------------------
# 10. test_cors_headers
# ---------------------------------------------------------------------------

class TestCorsHeaders:
    @pytest.mark.parametrize("path", [
        "/api/status",
        "/api/tools",
        "/api/sessions",
        "/api/analyze",
        "/api/events",
        "/api/doctor",
        "/api/recommend",
        "/api/unknown",
    ])
    def test_cors_header_present(self, path, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        _, headers, _ = _call("GET", path)
        assert headers.get("Access-Control-Allow-Origin") == "*", \
            f"Missing CORS header on {path}"


# ---------------------------------------------------------------------------
# 11. test_options_preflight
# ---------------------------------------------------------------------------

class TestOptionsPreflight:
    def test_options_returns_204(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        h = _make_handler("OPTIONS", "/api/status")
        h.do_OPTIONS()
        assert h._status_code == 204

    def test_options_cors_allow_origin(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        h = _make_handler("OPTIONS", "/api/status")
        h.do_OPTIONS()
        assert h._sent_headers.get("Access-Control-Allow-Origin") == "*"

    def test_options_cors_allow_methods(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        h = _make_handler("OPTIONS", "/api/status")
        h.do_OPTIONS()
        assert "GET" in h._sent_headers.get("Access-Control-Allow-Methods", "")

    def test_options_cors_allow_headers(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        h = _make_handler("OPTIONS", "/api/status")
        h.do_OPTIONS()
        assert "Content-Type" in h._sent_headers.get("Access-Control-Allow-Headers", "")


# ---------------------------------------------------------------------------
# Integration test: real HTTP server in a thread
# ---------------------------------------------------------------------------

class TestLiveServer:
    """Spin up a real HTTPServer in a thread and hit it with urllib."""

    @pytest.fixture
    def server_url(self, tmp_path):
        store = Store(tmp_path / "events.jsonl")
        store.append(
            "session_end",
            session="test-session",
            input_tokens=100000,
            output_tokens=30000,
            cache_read=80000,
            cost_usd=0.42,
            duration_min=25,
            model="sonnet",
        )
        ctx = _make_ctx(store=store)
        set_ctx(ctx)

        from http.server import HTTPServer
        from cc_manager.commands.serve import CCManagerHandler

        server = HTTPServer(("127.0.0.1", 0), CCManagerHandler)
        port = server.server_address[1]
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        yield f"http://127.0.0.1:{port}"
        server.shutdown()

    def _get(self, url):
        with urllib.request.urlopen(url) as resp:
            return resp.status, resp.headers, json.loads(resp.read())

    def test_live_status(self, server_url):
        status, headers, data = self._get(f"{server_url}/api/status")
        assert status == 200
        assert data["version"] == "0.1.0"

    def test_live_tools(self, server_url):
        status, _, data = self._get(f"{server_url}/api/tools")
        assert status == 200
        assert "tools" in data

    def test_live_sessions(self, server_url):
        status, _, data = self._get(f"{server_url}/api/sessions")
        assert status == 200
        assert len(data["sessions"]) == 1

    def test_live_analyze(self, server_url):
        status, _, data = self._get(f"{server_url}/api/analyze")
        assert status == 200
        assert data["total_sessions"] == 1
        assert abs(data["total_cost_usd"] - 0.42) < 0.001

    def test_live_events(self, server_url):
        status, _, data = self._get(f"{server_url}/api/events")
        assert status == 200
        assert "events" in data

    def test_live_doctor(self, server_url):
        status, _, data = self._get(f"{server_url}/api/doctor")
        assert status == 200
        assert "checks" in data

    def test_live_recommend(self, server_url):
        status, _, data = self._get(f"{server_url}/api/recommend")
        assert status == 200
        assert "recommendations" in data


# ---------------------------------------------------------------------------
# 12. POST /api/install
# ---------------------------------------------------------------------------

class TestPostInstall:
    def test_post_install_success(self, empty_store):
        ctx = _make_ctx(store=empty_store, installed_tools={})
        set_ctx(ctx)
        from cc_manager.commands.install import AlreadyInstalledError, ToolNotFoundError, InstallError
        with patch("cc_manager.commands.serve.CCManagerHandler._handle_install") as mock_install:
            def side_effect(body):
                h = mock_install.call_args[0][0]  # won't work, use closure
                pass
            # Test directly: patch install_tool
            pass

        # Direct test of _handle_install by patching install_tool
        h = _make_handler("POST", "/api/install")
        raw = json.dumps({"tool": "context7"}).encode()
        h.rfile = io.BytesIO(raw)
        h.headers = {"Content-Length": str(len(raw))}
        with patch("cc_manager.commands.serve.install_tool") as mock_install:
            mock_install.return_value = None  # success
            h.do_POST()
        data = _json(h.wfile.getvalue())
        assert data["ok"] is True
        assert data["tool"] == "context7"
        assert "Installed" in data["message"]

    def test_post_install_already_installed(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        from cc_manager.commands.install import AlreadyInstalledError
        h = _make_handler("POST", "/api/install")
        raw = json.dumps({"tool": "rtk"}).encode()
        h.rfile = io.BytesIO(raw)
        h.headers = {"Content-Length": str(len(raw))}
        with patch("cc_manager.commands.serve.install_tool") as mock_install:
            mock_install.side_effect = AlreadyInstalledError("already installed")
            h.do_POST()
        data = _json(h.wfile.getvalue())
        assert data["ok"] is False
        assert data["error"] == "already installed"

    def test_post_install_missing_tool_name(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        h = _make_handler("POST", "/api/install")
        raw = json.dumps({}).encode()
        h.rfile = io.BytesIO(raw)
        h.headers = {"Content-Length": str(len(raw))}
        h.do_POST()
        data = _json(h.wfile.getvalue())
        assert data["ok"] is False


# ---------------------------------------------------------------------------
# 13. POST /api/remove
# ---------------------------------------------------------------------------

class TestPostRemove:
    def test_post_remove_success(self, empty_store):
        ctx = _make_ctx(store=empty_store)
        set_ctx(ctx)
        h = _make_handler("POST", "/api/remove")
        raw = json.dumps({"tool": "rtk"}).encode()
        h.rfile = io.BytesIO(raw)
        h.headers = {"Content-Length": str(len(raw))}
        with patch("cc_manager.commands.serve.ctx_mod.REGISTRY_PATH") as mock_path:
            mock_path.write_text = MagicMock()
            h.do_POST()
        data = _json(h.wfile.getvalue())
        assert data["ok"] is True
        assert data["tool"] == "rtk"
        assert "Removed" in data["message"]

    def test_post_remove_not_installed(self, empty_store):
        set_ctx(_make_ctx(store=empty_store, installed_tools={}))
        h = _make_handler("POST", "/api/remove")
        raw = json.dumps({"tool": "nonexistent"}).encode()
        h.rfile = io.BytesIO(raw)
        h.headers = {"Content-Length": str(len(raw))}
        h.do_POST()
        data = _json(h.wfile.getvalue())
        assert data["ok"] is False
        assert "not installed" in data["error"]


# ---------------------------------------------------------------------------
# 14. POST /api/doctor/run
# ---------------------------------------------------------------------------

class TestPostDoctorRun:
    def test_post_doctor_run(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        h = _make_handler("POST", "/api/doctor/run")
        raw = b"{}"
        h.rfile = io.BytesIO(raw)
        h.headers = {"Content-Length": str(len(raw))}
        h.do_POST()
        data = _json(h.wfile.getvalue())
        assert "checks" in data
        assert "summary" in data

    def test_post_doctor_run_returns_200(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        h = _make_handler("POST", "/api/doctor/run")
        raw = b"{}"
        h.rfile = io.BytesIO(raw)
        h.headers = {"Content-Length": str(len(raw))}
        h.do_POST()
        assert h._status_code == 200


# ---------------------------------------------------------------------------
# 15. POST /api/module
# ---------------------------------------------------------------------------

class TestPostModule:
    def test_post_module_toggle(self, empty_store):
        ctx = _make_ctx(store=empty_store)
        ctx.config = {}
        set_ctx(ctx)
        h = _make_handler("POST", "/api/module")
        raw = json.dumps({"module": "later", "enabled": False}).encode()
        h.rfile = io.BytesIO(raw)
        h.headers = {"Content-Length": str(len(raw))}
        with patch("cc_manager.commands.serve.tomli_w") as mock_tomliw, \
             patch("cc_manager.commands.serve.CONFIG_PATH") as mock_path:
            mock_tomliw.dumps.return_value = ""
            mock_config_path = MagicMock()
            mock_config_path.parent.mkdir = MagicMock()
            mock_config_path.write_bytes = MagicMock()
            import cc_manager.commands.serve as serve_mod
            orig = serve_mod.CONFIG_PATH
            serve_mod.CONFIG_PATH = mock_config_path
            try:
                h.do_POST()
            finally:
                serve_mod.CONFIG_PATH = orig
        data = _json(h.wfile.getvalue())
        assert data["ok"] is True
        assert data["module"] == "later"
        assert data["enabled"] is False

    def test_post_module_missing_name(self, empty_store):
        ctx = _make_ctx(store=empty_store)
        ctx.config = {}
        set_ctx(ctx)
        h = _make_handler("POST", "/api/module")
        raw = json.dumps({"enabled": True}).encode()
        h.rfile = io.BytesIO(raw)
        h.headers = {"Content-Length": str(len(raw))}
        h.do_POST()
        data = _json(h.wfile.getvalue())
        assert data["ok"] is False


# ---------------------------------------------------------------------------
# 16. GET /api/registry
# ---------------------------------------------------------------------------

class TestGetRegistry:
    def test_get_registry_all(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        status, _, body = _call("GET", "/api/registry")
        assert status == 200
        data = _json(body)
        assert "tools" in data
        assert isinstance(data["tools"], list)

    def test_get_registry_returns_registry_entries(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        _, _, body = _call("GET", "/api/registry")
        data = _json(body)
        names = [t["name"] for t in data["tools"]]
        # Both rtk (installed) and context7 (not installed) are in registry
        assert "context7" in names or "rtk" in names

    def test_get_registry_filter_tier(self, empty_store):
        ctx = _make_ctx(store=empty_store)
        # Add tier to registry entries
        ctx.registry = [
            {"name": "tool-a", "method": "cargo", "tier": "recommended"},
            {"name": "tool-b", "method": "mcp", "tier": "popular"},
        ]
        set_ctx(ctx)
        _, _, body = _call("GET", "/api/registry?tier=recommended")
        data = _json(body)
        assert all(t.get("tier") == "recommended" for t in data["tools"])

    def test_get_registry_filter_installed_false(self, empty_store):
        ctx = _make_ctx(store=empty_store)
        # rtk is installed, context7 is not
        ctx.registry = [
            {"name": "rtk", "method": "cargo"},
            {"name": "context7", "method": "mcp"},
        ]
        set_ctx(ctx)
        _, _, body = _call("GET", "/api/registry?installed=false")
        data = _json(body)
        names = [t["name"] for t in data["tools"]]
        assert "context7" in names
        assert "rtk" not in names

    def test_get_registry_filter_installed_true(self, empty_store):
        ctx = _make_ctx(store=empty_store)
        ctx.registry = [
            {"name": "rtk", "method": "cargo"},
            {"name": "context7", "method": "mcp"},
        ]
        set_ctx(ctx)
        _, _, body = _call("GET", "/api/registry?installed=true")
        data = _json(body)
        names = [t["name"] for t in data["tools"]]
        assert "rtk" in names
        assert "context7" not in names


# ---------------------------------------------------------------------------
# 17. CORS on POST responses
# ---------------------------------------------------------------------------

class TestCorsOnPost:
    def test_cors_on_post_response(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        h = _make_handler("POST", "/api/doctor/run")
        raw = b"{}"
        h.rfile = io.BytesIO(raw)
        h.headers = {"Content-Length": str(len(raw))}
        h.do_POST()
        assert h._sent_headers.get("Access-Control-Allow-Origin") == "*"

    def test_options_allows_post(self, empty_store):
        set_ctx(_make_ctx(store=empty_store))
        h = _make_handler("OPTIONS", "/api/install")
        h.do_OPTIONS()
        methods = h._sent_headers.get("Access-Control-Allow-Methods", "")
        assert "POST" in methods
