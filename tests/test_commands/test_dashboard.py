"""Tests for cc_manager dashboard (TDD - written before implementation).

API Contract Note:
  The /api/analyze endpoint (implemented in serve.py by the API agent) must return:
    {
      "daily_labels": ["Mon", "Tue", ...],  # 7 day labels
      "daily_input":  [...],                 # input tokens per day
      "daily_output": [...],                 # output tokens per day
      "daily_cost":   [...],                 # cost USD per day
      ...  # other existing analyze fields
    }
  app.js depends on these fields for the token and cost charts.
"""
import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import threading

import pytest

DASHBOARD_DIR = Path(__file__).parent.parent.parent / "cc_manager" / "dashboard"


# ---------------------------------------------------------------------------
# 1. Dashboard directory and file existence
# ---------------------------------------------------------------------------

def test_dashboard_dir_exists():
    assert DASHBOARD_DIR.is_dir(), f"Expected cc_manager/dashboard/ to exist at {DASHBOARD_DIR}"
    assert (DASHBOARD_DIR / "index.html").is_file()
    assert (DASHBOARD_DIR / "style.css").is_file()
    assert (DASHBOARD_DIR / "app.js").is_file()


# ---------------------------------------------------------------------------
# 2. index.html structure
# ---------------------------------------------------------------------------

def test_index_html_has_chart_js():
    content = (DASHBOARD_DIR / "index.html").read_text()
    assert "https://cdn.jsdelivr.net/npm/chart.js" in content, \
        "index.html must include Chart.js CDN script tag"


def test_index_html_has_required_ids():
    content = (DASHBOARD_DIR / "index.html").read_text()
    required_ids = [
        "tokenChart",
        "costChart",
        "toolsTable",
        "sessionsTable",
        "healthPanel",
        "recommendPanel",
    ]
    for id_ in required_ids:
        assert f'id="{id_}"' in content, f"index.html missing element with id='{id_}'"


def test_index_html_loads_app_js():
    content = (DASHBOARD_DIR / "index.html").read_text()
    assert 'src="app.js"' in content


def test_index_html_loads_style_css():
    content = (DASHBOARD_DIR / "index.html").read_text()
    assert 'href="style.css"' in content


# ---------------------------------------------------------------------------
# 3. style.css dark theme
# ---------------------------------------------------------------------------

def test_css_has_dark_theme():
    content = (DASHBOARD_DIR / "style.css").read_text()
    assert "--bg" in content, "style.css must define --bg CSS variable for dark theme"


def test_css_has_surface_var():
    content = (DASHBOARD_DIR / "style.css").read_text()
    assert "--surface" in content


def test_css_has_status_classes():
    content = (DASHBOARD_DIR / "style.css").read_text()
    assert "status-ok" in content
    assert "status-warn" in content
    assert "status-fail" in content


# ---------------------------------------------------------------------------
# 4. app.js functions
# ---------------------------------------------------------------------------

def test_app_js_has_fetchall():
    content = (DASHBOARD_DIR / "app.js").read_text()
    assert "function fetchAll" in content, "app.js must define fetchAll function"


def test_app_js_has_all_renderers():
    content = (DASHBOARD_DIR / "app.js").read_text()
    required = [
        "renderTokenChart",
        "renderCostChart",
        "renderTools",
        "renderSessions",
        "renderHealth",
        "renderRecommendations",
    ]
    for fn in required:
        assert f"function {fn}" in content, f"app.js missing function: {fn}"


def test_app_js_has_auto_refresh():
    content = (DASHBOARD_DIR / "app.js").read_text()
    assert "setInterval" in content, "app.js must use setInterval for auto-refresh"
    assert "60000" in content, "app.js auto-refresh interval should be 60000ms"


# ---------------------------------------------------------------------------
# 5. dashboard.py command: run() behavior
# ---------------------------------------------------------------------------

def test_dashboard_run_no_open():
    """run() starts server in background thread and prints URL without opening browser."""
    from cc_manager.commands import dashboard as dash_mod

    mock_server = MagicMock()
    mock_server_instance = MagicMock()
    mock_server.return_value = mock_server_instance

    mock_thread = MagicMock()
    mock_thread_instance = MagicMock()
    mock_thread.return_value = mock_thread_instance
    # Make join raise KeyboardInterrupt immediately so run() exits
    mock_thread_instance.join.side_effect = KeyboardInterrupt

    with patch("cc_manager.commands.dashboard.HTTPServer", mock_server), \
         patch("cc_manager.commands.dashboard.threading.Thread", mock_thread), \
         patch("cc_manager.commands.dashboard.webbrowser.open") as mock_open, \
         patch("cc_manager.commands.dashboard.console") as mock_console:

        try:
            dash_mod.run(port=19847, no_open=True)
        except (KeyboardInterrupt, SystemExit):
            pass

        # Browser should NOT be opened when --no-open
        mock_open.assert_not_called()

        # Server should have been started
        assert mock_server.called, "HTTPServer should be instantiated"
        assert mock_thread_instance.start.called, "Thread.start() should be called"

        # URL should be printed
        printed_args = " ".join(
            str(a) for call_ in mock_console.print.call_args_list for a in call_[0]
        )
        assert "19847" in printed_args or "localhost" in printed_args


def test_dashboard_run_opens_browser():
    """run() calls webbrowser.open by default."""
    from cc_manager.commands import dashboard as dash_mod

    mock_server = MagicMock()
    mock_server_instance = MagicMock()
    mock_server.return_value = mock_server_instance

    mock_thread = MagicMock()
    mock_thread_instance = MagicMock()
    mock_thread.return_value = mock_thread_instance
    mock_thread_instance.join.side_effect = KeyboardInterrupt

    with patch("cc_manager.commands.dashboard.HTTPServer", mock_server), \
         patch("cc_manager.commands.dashboard.threading.Thread", mock_thread), \
         patch("cc_manager.commands.dashboard.webbrowser.open") as mock_open, \
         patch("cc_manager.commands.dashboard.console"):

        try:
            dash_mod.run(port=19848, no_open=False)
        except (KeyboardInterrupt, SystemExit):
            pass

        mock_open.assert_called_once()
        call_url = mock_open.call_args[0][0]
        assert "19848" in call_url


# ---------------------------------------------------------------------------
# 6. Static file handler (make_handler_class)
# ---------------------------------------------------------------------------

def _make_fake_request(method, path, static_dir):
    """Build a handler instance wired to a fake socket/connection."""
    from cc_manager.commands.dashboard import make_handler_class

    HandlerClass = make_handler_class(static_dir)

    output = io.BytesIO()

    class FakeSocket:
        def makefile(self, mode, *a, **kw):
            if "r" in mode:
                request_line = f"{method} {path} HTTP/1.1\r\nHost: localhost\r\n\r\n"
                return io.BytesIO(request_line.encode())
            return output

        def sendall(self, data):
            output.write(data)

        def getpeername(self):
            return ("127.0.0.1", 0)

    # Build handler using BaseHTTPRequestHandler internal protocol
    handler = HandlerClass.__new__(HandlerClass)
    handler.server = MagicMock()
    handler.connection = FakeSocket()
    handler.client_address = ("127.0.0.1", 0)
    handler.request = handler.connection
    handler.wfile = output
    handler.rfile = io.BytesIO()

    # Capture response via send_response / send_header / end_headers / wfile
    sent_status = []
    sent_headers = {}

    def fake_send_response(code, message=None):
        sent_status.append(code)

    def fake_send_header(key, value):
        sent_headers[key.lower()] = str(value)

    def fake_end_headers():
        pass

    handler.send_response = fake_send_response
    handler.send_header = fake_send_header
    handler.end_headers = fake_end_headers

    return handler, sent_status, sent_headers, output


def test_static_file_serving(tmp_path):
    """make_handler_class serves index.html for GET /."""
    index = tmp_path / "index.html"
    index.write_text("<html><body>hello</body></html>")

    from cc_manager.commands.dashboard import make_handler_class
    HandlerClass = make_handler_class(tmp_path)

    output = io.BytesIO()
    sent_status = []
    sent_headers = {}

    handler = HandlerClass.__new__(HandlerClass)
    handler.server = MagicMock()
    handler.wfile = output
    handler.path = "/"

    handler.send_response = lambda code, msg=None: sent_status.append(code)
    handler.send_header = lambda k, v: sent_headers.__setitem__(k.lower(), str(v))
    handler.end_headers = lambda: None

    handler.do_GET()

    assert sent_status == [200]
    assert "text/html" in sent_headers.get("content-type", "")
    assert b"hello" in output.getvalue()


def test_static_file_css(tmp_path):
    """make_handler_class serves style.css with correct content-type."""
    css_file = tmp_path / "style.css"
    css_file.write_text(":root { --bg: #000; }")

    from cc_manager.commands.dashboard import make_handler_class
    HandlerClass = make_handler_class(tmp_path)

    output = io.BytesIO()
    sent_status = []
    sent_headers = {}

    handler = HandlerClass.__new__(HandlerClass)
    handler.server = MagicMock()
    handler.wfile = output
    handler.path = "/style.css"

    handler.send_response = lambda code, msg=None: sent_status.append(code)
    handler.send_header = lambda k, v: sent_headers.__setitem__(k.lower(), str(v))
    handler.end_headers = lambda: None

    handler.do_GET()

    assert sent_status == [200]
    assert "text/css" in sent_headers.get("content-type", "")
    assert b"--bg" in output.getvalue()


def test_static_file_js(tmp_path):
    """make_handler_class serves app.js with correct content-type."""
    js_file = tmp_path / "app.js"
    js_file.write_text("function fetchAll() {}")

    from cc_manager.commands.dashboard import make_handler_class
    HandlerClass = make_handler_class(tmp_path)

    output = io.BytesIO()
    sent_status = []
    sent_headers = {}

    handler = HandlerClass.__new__(HandlerClass)
    handler.server = MagicMock()
    handler.wfile = output
    handler.path = "/app.js"

    handler.send_response = lambda code, msg=None: sent_status.append(code)
    handler.send_header = lambda k, v: sent_headers.__setitem__(k.lower(), str(v))
    handler.end_headers = lambda: None

    handler.do_GET()

    assert sent_status == [200]
    assert "javascript" in sent_headers.get("content-type", "")


def test_static_file_not_found_falls_back_to_index(tmp_path):
    """Unknown paths fall through to index.html (SPA routing)."""
    index = tmp_path / "index.html"
    index.write_text("<html>spa</html>")

    from cc_manager.commands.dashboard import make_handler_class
    HandlerClass = make_handler_class(tmp_path)

    output = io.BytesIO()
    sent_status = []
    sent_headers = {}

    handler = HandlerClass.__new__(HandlerClass)
    handler.server = MagicMock()
    handler.wfile = output
    handler.path = "/some/unknown/path"

    handler.send_response = lambda code, msg=None: sent_status.append(code)
    handler.send_header = lambda k, v: sent_headers.__setitem__(k.lower(), str(v))
    handler.end_headers = lambda: None

    handler.do_GET()

    assert sent_status == [200]
    assert b"spa" in output.getvalue()


def test_api_route_passthrough(tmp_path):
    """GET /api/* routes are handled by the API handler, not static files."""
    from cc_manager.commands.dashboard import make_handler_class
    HandlerClass = make_handler_class(tmp_path)

    output = io.BytesIO()
    sent_status = []
    sent_headers = {}
    sent_body = {}

    handler = HandlerClass.__new__(HandlerClass)
    handler.server = MagicMock()
    handler.wfile = output
    handler.path = "/api/status"

    handler.send_response = lambda code, msg=None: sent_status.append(code)
    handler.send_header = lambda k, v: sent_headers.__setitem__(k.lower(), str(v))
    handler.end_headers = lambda: None

    # CCManagerHandler.do_GET should be called for /api/ routes
    with patch.object(HandlerClass.__bases__[0], "do_GET") as mock_parent_get:
        handler.do_GET()
        mock_parent_get.assert_called_once()


# ---------------------------------------------------------------------------
# 7. Interactive app.js functions
# ---------------------------------------------------------------------------

def test_app_js_has_api_post():
    content = (DASHBOARD_DIR / "app.js").read_text()
    assert "async function apiPost" in content, "app.js must define apiPost function"


def test_app_js_has_install_tool():
    content = (DASHBOARD_DIR / "app.js").read_text()
    assert "async function installTool" in content, "app.js must define installTool function"


def test_app_js_has_remove_tool():
    content = (DASHBOARD_DIR / "app.js").read_text()
    assert "async function removeTool" in content, "app.js must define removeTool function"


def test_app_js_has_toggle_module():
    content = (DASHBOARD_DIR / "app.js").read_text()
    assert "async function toggleModule" in content, "app.js must define toggleModule function"


def test_app_js_has_run_doctor():
    content = (DASHBOARD_DIR / "app.js").read_text()
    assert "async function runDoctor" in content, "app.js must define runDoctor function"


def test_app_js_has_render_registry():
    content = (DASHBOARD_DIR / "app.js").read_text()
    assert "function renderRegistry" in content, "app.js must define renderRegistry function"


def test_app_js_has_load_registry():
    content = (DASHBOARD_DIR / "app.js").read_text()
    assert "async function loadRegistry" in content, "app.js must define loadRegistry function"


# ---------------------------------------------------------------------------
# 8. Interactive index.html elements
# ---------------------------------------------------------------------------

def test_index_has_registry_panel():
    content = (DASHBOARD_DIR / "index.html").read_text()
    assert 'id="registryPanel"' in content, "index.html must have element with id='registryPanel'"


def test_index_has_registry_card():
    content = (DASHBOARD_DIR / "index.html").read_text()
    assert 'id="registryCard"' in content, "index.html must have element with id='registryCard'"


def test_index_tools_table_has_action_column():
    content = (DASHBOARD_DIR / "index.html").read_text()
    assert "ACTION" in content, "index.html tools table must have ACTION column header"


def test_index_health_card_has_rescan_button():
    content = (DASHBOARD_DIR / "index.html").read_text()
    assert "runDoctor" in content, "index.html health card must have Re-scan button calling runDoctor"


# ---------------------------------------------------------------------------
# 9. Interactive CSS classes
# ---------------------------------------------------------------------------

def test_css_has_install_btn():
    content = (DASHBOARD_DIR / "style.css").read_text()
    assert ".install-btn" in content, "style.css must define .install-btn"


def test_css_has_remove_btn():
    content = (DASHBOARD_DIR / "style.css").read_text()
    assert ".remove-btn" in content, "style.css must define .remove-btn"


def test_css_has_module_toggle():
    content = (DASHBOARD_DIR / "style.css").read_text()
    assert ".module-toggle" in content, "style.css must define .module-toggle"


def test_css_has_card_header():
    content = (DASHBOARD_DIR / "style.css").read_text()
    assert ".card-header" in content, "style.css must define .card-header"


def test_css_has_action_btn():
    content = (DASHBOARD_DIR / "style.css").read_text()
    assert ".action-btn" in content, "style.css must define .action-btn"


def test_css_has_button_disabled():
    content = (DASHBOARD_DIR / "style.css").read_text()
    assert "button:disabled" in content, "style.css must define button:disabled style"


# ---------------------------------------------------------------------------
# 10. Demo data and fetchWithFallback
# ---------------------------------------------------------------------------

def test_app_js_has_demo_data():
    content = (DASHBOARD_DIR / "app.js").read_text()
    assert "DEMO_DATA" in content, "app.js must define DEMO_DATA for offline/fallback mode"


def test_app_js_has_fetch_with_fallback():
    content = (DASHBOARD_DIR / "app.js").read_text()
    assert "fetchWithFallback" in content, "app.js must define fetchWithFallback function"
