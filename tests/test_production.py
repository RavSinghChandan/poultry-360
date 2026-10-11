"""Production behaviour: data that survives a restart, request ids, audit log, readiness, safe errors.

A "restart" here drops the pooled database engine, the way a new process would
start with nothing in memory; only what is in the database comes back.
Set TEST_DATABASE_URL to run the same tests against Postgres (CI does).
"""
import json
import logging
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from api.main import app
from core import logs, store, tenancy

client = TestClient(app, raise_server_exceptions=False)
ADMIN = {"x-admin-key": "test-admin"}


@pytest.fixture(autouse=True)
def signed_in_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("POULTRY_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("POULTRY_AUTH", "on")
    monkeypatch.setenv("ADMIN_KEY", "test-admin")
    monkeypatch.setenv("POULTRY_SECRET", "test-secret")
    tenancy._attempts.clear()
    yield


def restart():
    for eng in store._engines.values():
        eng.dispose()
    store._engines.clear()
    tenancy._attempts.clear()


def _approved(farm="Rahim Poultry", username="rahim"):
    rid = client.post("/api/auth/register", json={"farm": farm, "owner": "Rahim", "phone": "9800000000"}).json()["id"]
    return client.post(f"/api/admin/registrations/{rid}/approve", json={"username": username}, headers=ADMIN).json()


def _login(row):
    return client.post("/api/auth/login", json={"tenant_key": row["tenant_key"], "username": row["username"]})


def test_pending_registration_survives_a_restart():
    rid = client.post("/api/auth/register", json={"farm": "Sita Farm", "owner": "Sita", "phone": "98"}).json()["id"]
    restart()
    rows = client.get("/api/admin/registrations", headers=ADMIN).json()
    assert [r["id"] for r in rows] == [rid]


def test_revoked_farm_stays_blocked_after_a_restart():
    row = _approved()
    client.post(f"/api/admin/registrations/{row['id']}/reject", headers=ADMIN)
    restart()
    assert _login(row).status_code == 403


def test_daily_cap_survives_a_restart(monkeypatch):
    monkeypatch.setattr(tenancy, "DAILY_PER_USER", 2)
    auth = {"authorization": f"Bearer {_login(_approved()).json()['token']}"}
    assert client.post("/api/feed/ration", json={"day": 5, "birds": 10}, headers=auth).status_code == 200
    assert client.post("/api/feed/ration", json={"day": 5, "birds": 10}, headers=auth).status_code == 200
    restart()
    assert client.post("/api/feed/ration", json={"day": 5, "birds": 10}, headers=auth).status_code == 429


def test_admin_actions_are_audited_with_their_request_id():
    rid = client.post("/api/auth/register", json={"farm": "Ali Farm", "owner": "Ali", "phone": "98"}).json()["id"]
    approved = client.post(f"/api/admin/registrations/{rid}/approve", json={"username": "ali"},
                           headers={**ADMIN, "x-request-id": "approve-req-1"})
    client.post(f"/api/admin/registrations/{rid}/reject", headers=ADMIN)
    log = client.get("/api/admin/audit", headers=ADMIN).json()
    assert [(e["action"], e["target"]) for e in log] == [("revoke", "ali-farm"), ("approve", "ali-farm")]
    assert log[1]["request_id"] == approved.headers["x-request-id"] == "approve-req-1"
    assert client.get("/api/admin/audit").status_code == 401


def test_every_response_has_a_request_id_and_security_headers():
    r = client.get("/api/health")
    assert len(r.headers["x-request-id"]) == 16
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert client.get("/api/health", headers={"x-request-id": "abc"}).headers["x-request-id"] == "abc"


def test_readiness_checks_the_database():
    r = client.get("/api/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"
    assert r.json()["durable"] is bool(os.environ.get("TEST_DATABASE_URL"))


def test_readiness_fails_when_the_database_is_unreachable(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://nobody:x@127.0.0.1:1/none?connect_timeout=1")
    r = client.get("/api/ready")
    assert r.status_code == 503
    assert r.json() == {"status": "not_ready", "database": "unreachable", "durable": True}


def test_an_unexpected_error_returns_json_with_the_request_id(caplog):
    @app.post("/api/test-boom")
    def boom():
        raise RuntimeError("secret internals")
    try:
        r = client.post("/api/test-boom")
    finally:
        app.router.routes.pop()
    assert r.status_code == 500
    assert r.json()["request_id"] == r.headers["x-request-id"]
    assert "secret internals" not in r.text


def test_each_request_is_one_json_log_line(caplog):
    caplog.set_level(logging.INFO, logger="poultry360")
    r = client.get("/api/health")
    line = json.loads(logs.JsonFormatter().format(next(x for x in caplog.records if x.getMessage() == "request")))
    assert line["request_id"] == r.headers["x-request-id"]
    assert (line["method"], line["route"], line["status"]) == ("GET", "/api/health", 200)


def test_postgres_urls_from_hosting_get_the_driver_named(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@host/db")
    assert store.database_url() == "postgresql+psycopg://u:p@host/db"
