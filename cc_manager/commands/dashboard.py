"""cc-manager dashboard command — serves the HTML dashboard with API + static files."""
import importlib.resources
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import typer
from rich.console import Console

console = Console()

# ---------------------------------------------------------------------------
# Static-file + API handler factory
# ---------------------------------------------------------------------------

_CONTENT_TYPES = {
    ".html": "text/html",
    ".css": "text/css",
    ".js": "application/javascript",
    ".json": "application/json",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


def _base_handler():
    """Return CCManagerHandler if serve.py is available, else BaseHTTPRequestHandler."""
    try:
        from cc_manager.commands.serve import CCManagerHandler  # type: ignore
        return CCManagerHandler
    except ImportError:
        return BaseHTTPRequestHandler


def make_handler_class(static_dir=None):
    """Factory: returns an HTTPRequestHandler class that serves static files
    from *static_dir* for non-/api/ routes, and delegates /api/* to the
    CCManagerHandler (from serve.py) when available.
    """
    BaseHandler = _base_handler()

    class DashboardHandler(BaseHandler):
        # Silence default request logging to keep terminal clean
        def log_message(self, fmt, *args):  # noqa: N802
            pass

        def do_GET(self):  # noqa: N802
            if self.path.startswith("/api/"):
                # Delegate to API handler if available
                try:
                    super().do_GET()
                except AttributeError:
                    self._json_error({"error": "API not available"}, 501)
                return

            # Static file serving
            if static_dir is None:
                self._json_error({"error": "dashboard not available"}, 404)
                return

            # Strip query string and leading slash; default to index.html
            path_str = self.path.split("?")[0].lstrip("/") or "index.html"
            file_path = Path(static_dir) / path_str

            if file_path.exists() and file_path.is_file():
                self._serve_file(file_path)
            else:
                # SPA fallback: serve index.html for unknown paths
                index = Path(static_dir) / "index.html"
                if index.exists():
                    self._serve_file(index)
                else:
                    self._json_error({"error": "not found"}, 404)

        def _serve_file(self, file_path: Path):
            content_type = _CONTENT_TYPES.get(file_path.suffix, "text/plain")
            body = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        def _json_error(self, payload: dict, status: int):
            import json as _json
            body = _json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        # Provide _json_response alias used by CCManagerHandler callers
        _json_response = _json_error

    return DashboardHandler


# ---------------------------------------------------------------------------
# Typer command
# ---------------------------------------------------------------------------

def run(
    port: int = typer.Option(9847, "--port", help="Port to serve on"),
    no_open: bool = typer.Option(False, "--no-open", help="Don't open browser"),
):
    """Start dashboard (API + static files) and open browser."""
    # Resolve dashboard directory from the installed package
    try:
        with importlib.resources.path("cc_manager.dashboard", "index.html") as p:
            dashboard_dir = p.parent
    except Exception:
        dashboard_dir = Path(__file__).parent.parent / "dashboard"

    # Try to use serve.py's make_handler_class first; fall back to our own
    try:
        from cc_manager.commands.serve import make_handler_class as serve_factory  # type: ignore
        HandlerClass = serve_factory(dashboard_dir)
    except (ImportError, AttributeError):
        HandlerClass = make_handler_class(dashboard_dir)

    server = HTTPServer(("127.0.0.1", port), HandlerClass)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    url = f"http://localhost:{port}"
    console.print(f"[green]cc-manager dashboard: {url}[/green]")

    if not no_open:
        webbrowser.open(url)

    try:
        thread.join()
    except KeyboardInterrupt:
        server.shutdown()
