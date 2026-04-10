"""Tests for cc_manager.registry."""
from cc_manager import registry


def test_load_returns_list():
    tools = registry.load()
    assert isinstance(tools, list)
    assert len(tools) > 100


def test_as_map():
    m = registry.as_map()
    assert isinstance(m, dict)
    assert "rtk" in m
    assert m["rtk"]["name"] == "rtk"


def test_get_existing():
    t = registry.get("rtk")
    assert t is not None
    assert t["name"] == "rtk"
    assert "install_methods" in t


def test_get_missing():
    assert registry.get("nonexistent-tool-xyz") is None


def test_profiles():
    profs = registry.profiles()
    assert "recommended" in profs
    assert "minimal" in profs
    assert len(profs["recommended"]["tools"]) > 0
    assert isinstance(profs["recommended"]["description"], str)


def test_search():
    results = registry.search("token")
    names = [r["name"] for r in results]
    assert "rtk" in names


def test_search_case_insensitive():
    results = registry.search("TOKEN")
    assert len(results) > 0


def test_search_no_results():
    results = registry.search("zzz_nonexistent_xyz_12345")
    assert results == []


def test_filter_by_tier():
    rec = registry.filter_tools(tier="recommended")
    assert all(t["tier"] == "recommended" for t in rec)
    assert len(rec) > 0


def test_filter_by_category():
    results = registry.filter_tools(category="analytics")
    assert all(t["category"] == "analytics" for t in results)


def test_conflicts_none():
    installed = {"tools": {"rtk": {}}}
    assert registry.conflicts("ccusage", installed) == []


def test_conflicts_detected():
    installed = {"tools": {"caveman": {}}}
    c = registry.conflicts("rtk", installed)
    # rtk conflicts_with includes caveman
    assert "caveman" in c


def test_load_with_community():
    tools = registry.load_with_community()
    assert len(tools) > len(registry.load())
