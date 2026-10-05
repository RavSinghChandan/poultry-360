"""Farm sign-in: register, approve, sign in with a tenant key, daily caps.

Locally sign-in is off so every other test runs unchanged; these switch it on.
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from api.main import app
from core import tenancy

client = TestClient(app)
ADMIN = {"x-admin-key": "test-admin"}


@pytest.fixture(autouse=True)
def signed_in_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("POULTRY_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("POULTRY_AUTH", "on")
    monkeypatch.setenv("ADMIN_KEY", "test-admin")
    monkeypatch.setenv("POULTRY_SECRET", "test-secret")
    tenancy._attempts.clear()
    tenancy._usage.clear()
    yield


def _approved(farm="Rahim Poultry", owner="Rahim", username=""):
    rid = client.post("/api/auth/register", json={"farm": farm, "owner": owner, "phone": "9800000000"}).json()["id"]
    return client.post(f"/api/admin/registrations/{rid}/approve", json={"username": username}, headers=ADMIN).json()


def _token(row):
    return client.post("/api/auth/login", json={"tenant_key": row["tenant_key"], "username": row["username"]}).json()["token"]


def test_status_reports_sign_in_required():
    assert client.get("/api/auth/status").json()["required"] is True


def test_register_needs_a_way_to_reach_the_farm():
    r = client.post("/api/auth/register", json={"farm": "Farm", "owner": "A"})
    assert r.status_code == 422


def test_register_then_approve_issues_key_and_username():
    row = _approved(username="rahim")
    assert row["status"] == "approved" and row["tenant"] == "rahim-poultry" and row["username"] == "rahim"
    assert row["tenant_key"].startswith("rahim-poultry.")


def test_admin_endpoints_need_the_admin_key():
    assert client.get("/api/admin/registrations").status_code == 401
    assert client.get("/api/admin/registrations", headers={"x-admin-key": "wrong"}).status_code == 401
    assert client.get("/api/admin/registrations", headers=ADMIN).status_code == 200


def test_login_with_key_and_username():
    row = _approved(username="rahim")
    r = client.post("/api/auth/login", json={"tenant_key": row["tenant_key"], "username": "Rahim "})
    assert r.status_code == 200 and r.json()["tenant_name"] == "Rahim Poultry"


def test_login_rejects_wrong_username_or_forged_key():
    row = _approved(username="rahim")
    assert client.post("/api/auth/login", json={"tenant_key": row["tenant_key"], "username": "other"}).status_code == 401
    assert client.post("/api/auth/login", json={"tenant_key": "rahim-poultry.AAAAAAAAAAAAAAAA", "username": "rahim"}).status_code == 401


def test_key_survives_a_wiped_disk(tmp_path, monkeypatch):
    row = _approved(username="rahim")
    monkeypatch.setenv("POULTRY_DATA_DIR", str(tmp_path / "fresh"))
    assert client.post("/api/auth/login", json={"tenant_key": row["tenant_key"], "username": "rahim"}).status_code == 200


def test_feature_actions_need_sign_in_but_reading_stays_open():
    assert client.post("/api/feed/ration", json={"day": 10, "birds": 100}).status_code == 401
    assert client.get("/api/feed/schedule").status_code == 200
    token = _token(_approved(username="rahim"))
    r = client.post("/api/feed/ration", json={"day": 10, "birds": 100}, headers={"authorization": f"Bearer {token}"})
    assert r.status_code == 200 and r.json()["ok"] is True


def test_turning_off_access_blocks_sign_in():
    row = _approved(username="rahim")
    assert client.post(f"/api/admin/registrations/{row['id']}/reject", headers=ADMIN).json()["status"] == "revoked"
    assert client.post("/api/auth/login", json={"tenant_key": row["tenant_key"], "username": "rahim"}).status_code == 403


def test_daily_cap_per_user(monkeypatch):
    monkeypatch.setattr(tenancy, "DAILY_PER_USER", 2)
    auth = {"authorization": f"Bearer {_token(_approved(username='rahim'))}"}
    codes = [client.post("/api/feed/ration", json={"day": 5, "birds": 10}, headers=auth).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_same_farm_name_gets_a_distinct_tenant():
    a, b = _approved(username="a1"), _approved(username="b1")
    assert a["tenant"] != b["tenant"] and b["tenant"] == "rahim-poultry-2"


def test_issue_directly():
    r = client.post("/api/admin/issue", json={"farm": "Sona Farm", "owner": "Sona"}, headers=ADMIN).json()
    assert r["tenant_key"].startswith("sona-farm.") and r["username"] == "sona"


def test_expired_or_tampered_token_is_refused():
    old = tenancy.make_token("R", "rahim", "rahim-poultry", "Rahim Poultry", now=0)
    assert tenancy.read_token(old) is None
    good = tenancy.make_token("R", "rahim", "rahim-poultry", "Rahim Poultry")
    assert tenancy.read_token(good[:-2] + "xx") is None


def test_render_deploy_fails_closed(monkeypatch):
    monkeypatch.delenv("POULTRY_AUTH")
    monkeypatch.setenv("RENDER", "true")
    assert tenancy.auth_required()


def test_login_attempts_are_limited():
    codes = [client.post("/api/auth/login", json={"tenant_key": "x.Y", "username": "zz"}).status_code for _ in range(11)]
    assert codes[-1] == 429
