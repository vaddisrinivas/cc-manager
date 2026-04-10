"""Install and remove tools — the core workflow."""
from __future__ import annotations

import json
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from cc_manager.paths import INSTALLED_PATH, MANAGER_DIR
from cc_manager import registry, settings


# -- Exceptions -------------------------------------------------------------

class ToolNotFoundError(Exception): ...
class AlreadyInstalledError(Exception): ...
class ConflictError(Exception): ...
class InstallError(Exception): ...


# -- Installed state --------------------------------------------------------

def load_installed() -> dict:
    """Read installed.json. Returns {"tools": {}} if missing."""
    if not INSTALLED_PATH.exists():
        return {"tools": {}}
    try:
        return json.loads(INSTALLED_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError):
        return {"tools": {}}


def save_installed(data: dict) -> None:
    """Write installed.json."""
    INSTALLED_PATH.parent.mkdir(parents=True, exist_ok=True)
    INSTALLED_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def record_installed(name: str, method: str, version: str = "latest") -> None:
    """Add tool to installed.json."""
    data = load_installed()
    data.setdefault("tools", {})[name] = {
        "method": method,
        "version": version,
        "installed_at": datetime.now(timezone.utc).isoformat(),
    }
    save_installed(data)


def remove_installed(name: str) -> None:
    """Remove tool from installed.json."""
    data = load_installed()
    data.get("tools", {}).pop(name, None)
    save_installed(data)


# -- Subprocess helper ------------------------------------------------------

def run_cmd(cmd: str, timeout: int = 30) -> tuple[int, str]:
    """Run a shell command safely (no shell=True). Returns (rc, output)."""
    try:
        args = shlex.split(cmd)
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except FileNotFoundError:
        return 127, f"command not found: {shlex.split(cmd)[0]}"
    except subprocess.TimeoutExpired:
        return 124, f"timeout after {timeout}s"
    except Exception as e:
        return 1, str(e)


# -- Install / Remove -------------------------------------------------------

def install_tool(
    name: str,
    reg_map: dict[str, dict],
    installed: dict,
    dry_run: bool = False,
) -> str:
    """Install a tool. Returns the method type used.

    Raises ToolNotFoundError, AlreadyInstalledError, ConflictError, InstallError.
    """
    tool = reg_map.get(name)
    if not tool:
        raise ToolNotFoundError(f"Tool '{name}' not found in registry.")

    if name in installed.get("tools", {}):
        raise AlreadyInstalledError(f"'{name}' is already installed.")

    for conflict in tool.get("conflicts_with", []):
        if conflict in installed.get("tools", {}):
            raise ConflictError(f"'{name}' conflicts with installed tool '{conflict}'.")

    methods = tool.get("install_methods", [])
    if not methods:
        raise InstallError(f"No install methods for '{name}'.")

    method = methods[0]
    mtype = method.get("type", "unknown")

    if dry_run:
        return mtype

    if mtype in ("cargo", "npm", "go", "pip", "brew"):
        cmd = method.get("command", "")
        if not cmd:
            raise InstallError(f"No command for method '{mtype}'.")
        if mtype == "cargo" and "--force" not in cmd:
            cmd += " --force"
        timeout = 600 if mtype == "cargo" else 120
        rc, output = run_cmd(cmd, timeout=timeout)
        if rc != 0:
            raise InstallError(f"Install failed (rc={rc}): {output}")
        record_installed(name, mtype)

    elif mtype == "mcp":
        mcp_config = method.get("mcp_config", {})
        if not mcp_config and method.get("command"):
            parts = method["command"].split()
            if not parts:
                raise InstallError(f"Empty command for MCP tool '{name}'.")
            mcp_config = {"command": parts[0], "args": parts[1:]}
        settings.merge_mcp(name, mcp_config)
        record_installed(name, "mcp")

    elif mtype == "plugin":
        cmd = method.get("command", "")
        if cmd:
            rc, output = run_cmd(cmd)
            if rc != 0:
                raise InstallError(f"Plugin install failed (rc={rc}): {output}")
        record_installed(name, "plugin")

    elif mtype in ("github_action", "manual"):
        record_installed(name, "manual")

    else:
        raise InstallError(f"Unknown method type '{mtype}'.")

    return mtype


def remove_tool(name: str, installed: dict) -> None:
    """Remove a tool — clean installed.json and settings.json."""
    if name not in installed.get("tools", {}):
        raise ToolNotFoundError(f"'{name}' is not installed.")

    info = installed["tools"][name]
    if info.get("method") == "mcp":
        settings.remove_mcp(name)

    remove_installed(name)
