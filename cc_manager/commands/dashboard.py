"""cc-manager dashboard command — Textual app (terminal + optional web via textual-web)."""
from __future__ import annotations

import typer
from rich.console import Console

console = Console()


def run(
    port: int = typer.Option(9847, "--port", help="Port for textual-web (if installed)"),
    no_open: bool = typer.Option(False, "--no-open", help="Don't open browser (textual-web mode)"),
    web: bool = typer.Option(False, "--web", help="Serve via textual-web instead of terminal"),
) -> None:
    """Launch the cc-manager dashboard.

    By default opens the Textual terminal dashboard (same as `ccm tui`).
    With --web, serves via textual-web if installed.

    Examples:
      ccm dashboard           # terminal TUI
      ccm dashboard --web     # browser via textual-web (requires: pip install textual-web)
    """
    if web:
        try:
            import subprocess
            import sys
            cmd = [
                sys.executable, "-m", "textual_web",
                "serve", "cc_manager.app:CCManagerApp",
                f"--port={port}",
            ]
            console.print(f"[green]Serving cc-manager dashboard at http://localhost:{port}[/green]")
            console.print("[dim]Install textual-web if not available: pip install textual-web[/dim]")
            if not no_open:
                import webbrowser, threading, time
                def _open():
                    time.sleep(1.5)
                    webbrowser.open(f"http://localhost:{port}")
                threading.Thread(target=_open, daemon=True).start()
            subprocess.run(cmd)
        except KeyboardInterrupt:
            pass
        except FileNotFoundError:
            console.print("[yellow]textual-web not found. Install: pip install textual-web[/yellow]")
            console.print("[cyan]Falling back to terminal dashboard...[/cyan]")
            _run_terminal()
    else:
        _run_terminal()


def _run_terminal() -> None:
    try:
        from cc_manager.app import CCManagerApp
        CCManagerApp().run()
    except ImportError as e:
        console = Console()
        console.print(f"[red]Textual not installed: {e}[/red]")
        console.print("[dim]Install: uv add textual[/dim]")
