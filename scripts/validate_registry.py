#!/usr/bin/env python3
"""
Registry schema validator.

Usage:
    python3 scripts/validate_registry.py                  # validate tools.json
    python3 scripts/validate_registry.py --fix            # auto-fix normalizable issues
    python3 scripts/validate_registry.py path/to/file.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ── Schema constants ──────────────────────────────────────────────────────────

VALID_TIERS       = {"core", "recommended", "useful", "experimental", "community", "popular"}
VALID_AUDIENCES   = {"everyone", "advanced", "infra", "security", "personal"}
VALID_OWNER_TYPES = {"anthropic", "vendor", "community", "self"}
VALID_INSTALL_TYPES = {
    "npm", "npx", "pip", "uvx", "cargo", "go", "brew",
    "mcp", "plugin", "github_action", "manual",
}
VALID_INTEGRATION_TYPES = {
    "mcp_server", "mcp", "plugin", "cli", "skill",
    "github_action", "hook", "hook_only", "standalone",
}
VALID_TRANSPORT = {"stdio", "sse", "http"}

REQUIRED_FIELDS = {
    "name", "display_name", "description", "tier", "category",
    "install_methods",
}
RECOMMENDED_FIELDS = {
    "repo", "detect", "integration", "conflicts_with",
    "owner_type", "official", "audience", "last_verified_at",
}


# ── Error collection ──────────────────────────────────────────────────────────

class Errors:
    def __init__(self) -> None:
        self._errors: list[tuple[str, str, str]] = []   # (name, field, message)
        self._warns:  list[tuple[str, str, str]] = []

    def error(self, name: str, field: str, msg: str) -> None:
        self._errors.append((name, field, msg))

    def warn(self, name: str, field: str, msg: str) -> None:
        self._warns.append((name, field, msg))

    @property
    def ok(self) -> bool:
        return not self._errors

    def report(self, verbose: bool = False) -> None:
        for name, field, msg in self._errors:
            print(f"  ERROR  [{name}] {field}: {msg}")
        if verbose:
            for name, field, msg in self._warns:
                print(f"  WARN   [{name}] {field}: {msg}")
        print()
        print(f"  {len(self._errors)} error(s)  {len(self._warns)} warning(s)")


# ── Per-tool validation ───────────────────────────────────────────────────────

def validate_tool(t: dict, errs: Errors) -> None:
    name = t.get("name") or "<unnamed>"

    # Required fields
    for f in REQUIRED_FIELDS:
        if f not in t or t[f] is None:
            errs.error(name, f, "missing required field")

    # Recommended fields
    for f in RECOMMENDED_FIELDS:
        if f not in t:
            errs.warn(name, f, "missing recommended field")

    # Tier
    tier = t.get("tier")
    if tier and tier not in VALID_TIERS:
        errs.error(name, "tier", f"unknown value '{tier}' — valid: {sorted(VALID_TIERS)}")

    # Audience
    audience = t.get("audience")
    if audience and audience not in VALID_AUDIENCES:
        errs.error(name, "audience", f"unknown value '{audience}' — valid: {sorted(VALID_AUDIENCES)}")

    # Owner type
    owner_type = t.get("owner_type")
    if owner_type and owner_type not in VALID_OWNER_TYPES:
        errs.error(name, "owner_type", f"unknown value '{owner_type}' — valid: {sorted(VALID_OWNER_TYPES)}")

    # install_methods
    methods = t.get("install_methods")
    if isinstance(methods, list):
        if not methods:
            errs.error(name, "install_methods", "empty list — at least one method required")
        for i, m in enumerate(methods):
            if not isinstance(m, dict):
                errs.error(name, f"install_methods[{i}]", "must be an object")
                continue
            mtype = m.get("type")
            if not mtype:
                errs.error(name, f"install_methods[{i}].type", "missing")
            elif mtype not in VALID_INSTALL_TYPES:
                errs.error(name, f"install_methods[{i}].type",
                           f"unknown '{mtype}' — valid: {sorted(VALID_INSTALL_TYPES)}")
            if mtype != "manual" and not m.get("command"):
                errs.error(name, f"install_methods[{i}].command",
                           f"missing for type '{mtype}'")
    elif methods is not None:
        errs.error(name, "install_methods", "must be a list")

    # integration
    integ = t.get("integration")
    if integ is not None:
        if not isinstance(integ, dict):
            errs.error(name, "integration", "must be an object")
        else:
            itype = integ.get("type")
            if itype and itype not in VALID_INTEGRATION_TYPES:
                errs.error(name, "integration.type",
                           f"unknown '{itype}' — valid: {sorted(VALID_INTEGRATION_TYPES)}")
            mcp_cfg = integ.get("mcp_config")
            if mcp_cfg is not None:
                if not isinstance(mcp_cfg, dict):
                    errs.error(name, "integration.mcp_config", "must be an object")
                else:
                    if not mcp_cfg.get("command"):
                        errs.error(name, "integration.mcp_config.command", "missing")
                    transport = mcp_cfg.get("type")
                    if transport and transport not in VALID_TRANSPORT:
                        errs.error(name, "integration.mcp_config.type",
                                   f"unknown transport '{transport}' — valid: {sorted(VALID_TRANSPORT)}")

    # git_url / repo consistency
    repo = t.get("repo")
    git_url = t.get("git_url")
    if repo and not re.fullmatch(r"[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+", repo):
        errs.error(name, "repo", f"expected 'owner/name' format, got '{repo}'")
    if git_url and repo and not git_url.endswith(repo):
        errs.warn(name, "git_url", f"doesn't end with repo '{repo}'")

    # detect
    detect = t.get("detect")
    if detect is not None and not isinstance(detect, dict):
        errs.error(name, "detect", "must be an object or null")

    # safety
    safety = t.get("safety")
    if safety is not None:
        if not isinstance(safety, dict):
            errs.error(name, "safety", "must be an object")
        else:
            valid_flags = {"dangerous_shell", "writes_files", "sends_code_to_cloud", "needs_api_keys"}
            for flag in safety:
                if flag not in valid_flags:
                    errs.warn(name, f"safety.{flag}", f"unknown flag — valid: {sorted(valid_flags)}")

    # last_verified_at
    lvat = t.get("last_verified_at")
    if lvat and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", lvat):
        errs.error(name, "last_verified_at", f"expected ISO8601 date (YYYY-MM-DD), got '{lvat}'")

    # Duplicate-name check happens at top level


# ── Profile validation ────────────────────────────────────────────────────────

def validate_profiles(profiles: list, tool_names: set[str], errs: Errors) -> None:
    seen: set[str] = set()
    for p in profiles:
        if not isinstance(p, dict):
            errs.error("<profile>", "root", "each profile must be a JSON object")
            continue
        name = p.get("name")
        if not name:
            errs.error("<profile>", "name", "missing required field")
            continue
        if name in seen:
            errs.error(name, "name", "duplicate profile name")
        seen.add(name)
        if not p.get("description"):
            errs.warn(name, "description", "missing description")
        tools = p.get("tools")
        if not isinstance(tools, list) or not tools:
            errs.error(name, "tools", "must be a non-empty list")
            continue
        for t in tools:
            if t not in tool_names:
                errs.error(name, "tools", f"'{t}' not found in tools list")


# ── Top-level validation ──────────────────────────────────────────────────────

def validate(tools: list, errs: Errors, profiles: list | None = None) -> None:
    if not isinstance(tools, list):
        print("ERROR: root must be a JSON array")
        sys.exit(1)

    seen_names: set[str] = set()
    for t in tools:
        if not isinstance(t, dict):
            errs.error("<non-object>", "root", "each entry must be a JSON object")
            continue
        name = t.get("name")
        if name in seen_names:
            errs.error(name, "name", "duplicate name in registry")
        elif name:
            seen_names.add(name)
        validate_tool(t, errs)

    if profiles:
        validate_profiles(profiles, seen_names, errs)


# ── Auto-fix ──────────────────────────────────────────────────────────────────

def autofix(tools: list) -> int:
    """Fix safe, normalizable issues. Returns count of changes."""
    fixed = 0
    for t in tools:
        # ensure detect has command + pattern keys
        d = t.get("detect")
        if isinstance(d, dict):
            if "command" not in d:
                d["command"] = None; fixed += 1
            if "pattern" not in d:
                d["pattern"] = None; fixed += 1
        elif d is None:
            t["detect"] = {"command": None, "pattern": None}; fixed += 1

        # ensure conflicts_with is a list
        if "conflicts_with" not in t:
            t["conflicts_with"] = []; fixed += 1

        # ensure min_version present
        if "min_version" not in t:
            t["min_version"] = None; fixed += 1

    return fixed


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Validate cc-manager registry JSON.")
    parser.add_argument("file", nargs="?",
                        default=str(Path(__file__).parent.parent / "registry" / "tools.json"))
    parser.add_argument("--fix", action="store_true", help="Auto-fix normalizable issues in-place")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show warnings too")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"ERROR: file not found: {path}")
        sys.exit(1)

    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON: {e}")
        sys.exit(1)

    # Support both flat list and {profiles, tools} formats
    if isinstance(data, list):
        tools, profiles = data, []
    else:
        tools = data.get("tools", [])
        profiles = data.get("profiles", [])

    if args.fix:
        n = autofix(tools)
        out = {"profiles": profiles, "tools": tools} if profiles else tools
        path.write_text(json.dumps(out, indent=2) + "\n")
        print(f"Auto-fixed {n} normalizable issues in {path}")

    errs = Errors()
    validate(tools, errs, profiles=profiles)
    errs.report(verbose=args.verbose)

    if errs.ok:
        print(f"\n  OK — {len(tools)} tools, {len(profiles)} profiles")
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
