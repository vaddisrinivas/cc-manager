"""Registry — load, query, and filter the curated tool registry."""
from __future__ import annotations

import json
from importlib import resources
from pathlib import Path


_REGISTRY_DIR = Path(__file__).resolve().parent.parent / "registry"


def _load_file(name: str) -> dict:
    path = _REGISTRY_DIR / name
    if not path.exists():
        return {"profiles": [], "tools": []}
    return json.loads(path.read_text(encoding="utf-8"))


def load() -> list[dict]:
    """Return all tools from tools.json."""
    return _load_file("tools.json").get("tools", [])


def load_with_community() -> list[dict]:
    """Return tools from both tools.json and tools-community.json."""
    tools = load()
    tools.extend(_load_file("tools-community.json").get("tools", []))
    return tools


def profiles() -> dict[str, dict]:
    """Return built-in profiles: {name: {description, tools}}."""
    data = _load_file("tools.json")
    return {
        p["name"]: {"description": p.get("description", ""), "tools": p["tools"]}
        for p in data.get("profiles", [])
    }


def get(name: str, tools: list[dict] | None = None) -> dict | None:
    """Lookup single tool by name."""
    for t in (tools or load()):
        if t["name"] == name:
            return t
    return None


def as_map(tools: list[dict] | None = None) -> dict[str, dict]:
    """Return {name: tool} mapping for O(1) lookup."""
    return {t["name"]: t for t in (tools or load())}


def search(query: str, tools: list[dict] | None = None) -> list[dict]:
    """Case-insensitive search across name, display_name, description."""
    q = query.lower()
    results = []
    for t in (tools or load()):
        if (q in t.get("name", "").lower()
                or q in t.get("display_name", "").lower()
                or q in t.get("description", "").lower()):
            results.append(t)
    return results


def filter_tools(
    tools: list[dict] | None = None,
    *,
    tier: str | None = None,
    category: str | None = None,
) -> list[dict]:
    """Filter tools by tier and/or category."""
    result = tools or load()
    if tier:
        result = [t for t in result if t.get("tier") == tier]
    if category:
        result = [t for t in result if t.get("category") == category]
    return result


def conflicts(name: str, installed: dict, tools: list[dict] | None = None) -> list[str]:
    """Return list of installed tools that conflict with `name`."""
    tool = get(name, tools)
    if not tool:
        return []
    installed_names = set(installed.get("tools", {}).keys())
    return [c for c in tool.get("conflicts_with", []) if c in installed_names]
