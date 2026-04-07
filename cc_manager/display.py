"""Shared display utilities for cc-manager CLI."""
from rich.console import Console
from rich.panel import Panel
from rich import box

console = Console()

def header(title: str):
    """Print a section header."""
    console.print(f"\n[bold]{title}[/bold]")

def success(msg: str):
    """Print success message."""
    console.print(f"  [green]✓[/green] {msg}")

def section(title: str):
    """Print a section divider."""
    console.print(f"\n[bold]{title}[/bold]")
    console.print("[dim]" + "─" * 40 + "[/dim]")

def error(msg: str, hint: str = ""):
    """Print error message."""
    console.print(f"  [red]✗[/red] {msg}")
    if hint:
        console.print(f"    {hint}")

def warning(msg: str):
    """Print warning message."""
    console.print(f"  [yellow]![/yellow] {msg}")

def info(msg: str):
    """Print info message."""
    console.print(f"  {msg}")

def dim_info(msg: str):
    """Print dimmed info."""
    console.print(f"  [dim]{msg}[/dim]")
