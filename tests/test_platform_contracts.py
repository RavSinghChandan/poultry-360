"""Tests that keep the platform extensible.

These do not test poultry. They test that a new feature can be added without
breaking an existing one, which is the property the architecture exists for.
"""
import ast
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from api.main import app, features
from core.contracts import Feature, FeatureInfo, ToolSpec
from core.registry import FeatureRegistry

client = TestClient(app)
FEATURES_DIR = ROOT / "backend" / "features"


def all_features():
    return list(features.loaded.values())


# ── every feature honours the contract ─────────────────────────────────────

def test_at_least_one_feature_loaded():
    assert features.loaded, "no features discovered"


def test_nothing_failed_to_load():
    assert features.failed == {}, f"features failed: {features.failed}"


@pytest.mark.parametrize("lf", all_features(), ids=lambda lf: lf.key)
def test_feature_implements_the_protocol(lf):
    assert isinstance(lf.feature, Feature)


@pytest.mark.parametrize("lf", all_features(), ids=lambda lf: lf.key)
def test_feature_info_is_complete(lf):
    info = lf.feature.info()
    assert isinstance(info, FeatureInfo)
    for field in ("key", "name_en", "name_hi", "summary_en", "summary_hi"):
        assert getattr(info, field), f"{lf.key}: {field} is empty"
    assert info.status in {"live", "beta", "planned"}


@pytest.mark.parametrize("lf", all_features(), ids=lambda lf: lf.key)
def test_feature_key_matches_its_package(lf):
    assert lf.key == lf.feature.info().key


@pytest.mark.parametrize("lf", all_features(), ids=lambda lf: lf.key)
def test_feature_selfcheck_passes(lf):
    assert lf.feature.selfcheck() == [], f"{lf.key} unhealthy: {lf.problems}"


@pytest.mark.parametrize("lf", all_features(), ids=lambda lf: lf.key)
def test_feature_tools_are_namespaced(lf):
    """A tool name must start with the feature key, so two features cannot clash."""
    for tool in lf.feature.tools():
        assert isinstance(tool, ToolSpec)
        assert tool.name.startswith(lf.key), (
            f"{lf.key}: tool {tool.name!r} is not namespaced"
        )
        assert tool.description, f"{lf.key}: tool {tool.name} has no description"


def test_tool_names_are_unique_across_features():
    names = [t.name for t in features.tools()]
    assert len(names) == len(set(names)), "duplicate tool name across features"


# ── isolation: the property that stops feature N breaking feature N-1 ──────

def _imports_of(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
        elif isinstance(node, ast.Import):
            found.update(a.name for a in node.names)
    return found


def feature_packages():
    return [p for p in FEATURES_DIR.iterdir()
            if p.is_dir() and not p.name.startswith("_")]


@pytest.mark.parametrize("pkg", feature_packages(), ids=lambda p: p.name)
def test_a_feature_never_imports_another_feature(pkg):
    """The rule that makes features safe to add and remove."""
    for py in pkg.rglob("*.py"):
        for mod in _imports_of(py):
            if mod.startswith("features."):
                other = mod.split(".")[1]
                assert other == pkg.name, (
                    f"{py.relative_to(ROOT)} imports {mod} from another feature"
                )


def test_the_platform_never_imports_a_feature():
    """core/ and api/ must stay feature-agnostic, or discovery is a lie."""
    for sub in ("core", "api", "harness"):
        for py in (ROOT / "backend" / sub).rglob("*.py"):
            for mod in _imports_of(py):
                assert not mod.startswith("features."), (
                    f"{py.relative_to(ROOT)} imports {mod}; the platform must not "
                    "know about individual features"
                )


# ── a broken feature is contained ──────────────────────────────────────────

class _Broken:
    def info(self):
        return FeatureInfo(key="broken", name_en="B", name_hi="ब",
                           summary_en="s", summary_hi="स")

    def router(self):
        from fastapi import APIRouter
        return APIRouter()

    def tools(self):
        return []

    def selfcheck(self):
        return ["its data is wrong"]


def test_an_unhealthy_feature_is_not_served():
    reg = FeatureRegistry()
    reg.register(_Broken())
    assert reg.loaded["broken"].healthy is False
    assert reg.routers() == []          # not mounted
    assert reg.tools() == []            # its tools are unreachable


def test_a_duplicate_key_is_rejected_not_silently_overwritten():
    reg = FeatureRegistry()
    reg.register(_Broken())
    reg.register(_Broken())
    assert "broken" in reg.failed


def test_a_clashing_tool_name_is_rejected():
    from harness.policy import Effect

    class _A:
        def info(self):
            return FeatureInfo(key="a", name_en="A", name_hi="ए",
                               summary_en="s", summary_hi="स")
        def router(self):
            from fastapi import APIRouter
            return APIRouter()
        def tools(self):
            return [ToolSpec(name="shared", run=lambda: "x", effect=Effect.READ)]
        def selfcheck(self):
            return []

    class _B(_A):
        def info(self):
            return FeatureInfo(key="b", name_en="B", name_hi="बी",
                               summary_en="s", summary_hi="स")

    reg = FeatureRegistry()
    reg.register(_A())
    reg.register(_B())
    assert "b" in reg.failed and "shared" in reg.failed["b"]


# ── platform endpoints ─────────────────────────────────────────────────────

def test_health_reports_every_feature():
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["features_loaded"] == len(features.loaded)
    assert body["features_unhealthy"] == []


def test_feature_manifest_is_complete_enough_to_build_a_menu():
    body = client.get("/api/features").json()
    for f in body["features"]:
        for field in ("key", "name_en", "name_hi", "icon", "status", "base_path"):
            assert f.get(field), f"{f.get('key')}: manifest missing {field}"


def test_every_feature_route_is_reachable_under_its_own_prefix():
    body = client.get("/api/features").json()
    for f in body["features"]:
        assert f["base_path"] == f"/api/{f['key']}"


def test_tools_endpoint_exposes_the_authority_of_each_tool():
    body = client.get("/api/tools").json()
    assert body["tools"]
    for t in body["tools"]:
        assert t["effect"] in {"read", "write", "destroy"}


# ── the features that exist today still work ───────────────────────────────

def test_feed_feature_still_answers_correctly():
    r = client.post("/api/feed/ration", json={"day": 17, "birds": 4000})
    d = r.json()["data"]
    assert d["crude_protein_pct"] == 20.0
    assert d["feed_total_kg"] == 284.0


def test_health_feature_never_claims_a_diagnosis():
    r = client.post("/api/health/assess", json={"signs": ["huddling"]})
    body = r.json()
    assert "not a diagnosis" in body["note_en"].lower()


def test_unimplemented_photo_scoring_says_so_rather_than_guessing():
    body = client.post("/api/health/photo").json()
    assert body["ok"] is False
    assert body["status"] == "not_implemented"
