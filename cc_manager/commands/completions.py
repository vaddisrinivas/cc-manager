"""cc-manager completions command."""
from __future__ import annotations
import typer
from rich.console import Console
console = Console()
app = typer.Typer()

BASH_COMPLETION = """
_ccm_completion() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    local commands="init install uninstall list search info status doctor backup-create backup-list backup-restore config-get config-set config-edit config-reset update pin unpin pin-list diff audit why clean logs analyze recommend export import migrate-check migrate reset completions"
    COMPREPLY=($(compgen -W "${commands}" -- "${cur}"))
}
complete -F _ccm_completion ccm
complete -F _ccm_completion cc-manager
"""

ZSH_COMPLETION = """
#compdef ccm cc-manager
_ccm() {
    local commands=(init install uninstall list search info status doctor update pin unpin diff audit why clean logs analyze recommend export import migrate reset completions)
    _describe 'commands' commands
}
compdef _ccm ccm cc-manager
"""

FISH_COMPLETION = """
complete -c ccm -f -a 'init install uninstall list search info status doctor update pin unpin diff audit why clean logs analyze recommend export import migrate reset completions'
"""

@app.command("completions")
def completions_cmd(shell: str = typer.Argument(..., help="Shell: bash, zsh, or fish")) -> None:
    """Print shell completion script."""
    if shell == "bash":
        console.print(BASH_COMPLETION)
    elif shell == "zsh":
        console.print(ZSH_COMPLETION)
    elif shell == "fish":
        console.print(FISH_COMPLETION)
    else:
        console.print(f"[red]Unknown shell: {shell}. Use bash, zsh, or fish.[/red]")
        raise typer.Exit(1)
