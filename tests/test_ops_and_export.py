"""The owner's ops panel, the feed-plan CSV, and the offline evals staying above their floors."""
import csv
import io
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from api.main import app  # noqa: E402
from harness import metrics  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    monkeypatch.setenv("ADMIN_KEY", "test-admin")
    metrics.reset()


def test_ops_needs_the_admin_key():
    assert client.get("/api/admin/ops").status_code == 401
    assert client.get("/api/admin/ops", headers={"x-admin-key": "wrong"}).status_code == 401


def test_ops_reports_traffic_by_route_template():
    for day in (5, 17):
        client.post("/api/feed/ration", json={"day": day, "birds": 10})
    snap = client.get("/api/admin/ops", headers={"x-admin-key": "test-admin"}).json()
    ration = next(r for r in snap["routes"] if r["route"] == "POST /api/feed/ration")
    assert ration["count"] == 2
    assert ration["server_errors"] == 0
    assert ration["p50_ms"] is not None
    assert snap["requests"] >= 2


def test_model_calls_and_failures_are_counted():
    metrics.record_model_call(True, 800, {"prompt_tokens": 120, "completion_tokens": 40})
    metrics.record_model_call(False, 15000)
    model = metrics.snapshot()["model"]
    assert (model["calls"], model["failed"], model["fallback_rate"]) == (2, 1, 0.5)
    assert (model["prompt_tokens"], model["completion_tokens"]) == (120, 40)


def test_server_errors_and_farms_are_tracked():
    metrics.record_request("POST /api/count/image", 500, 30, "green-farm")
    metrics.record_request("POST /api/count/image", 200, 20, "green-farm")
    snap = metrics.snapshot()
    assert snap["server_error_rate"] == 0.5
    assert snap["farms_today"] == {"green-farm": 2}


def test_feed_plan_csv_has_one_row_per_day():
    res = client.get("/api/feed/plan.csv", params={"day_from": 1, "day_to": 7, "birds": 500})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(res.text)))
    assert [int(r["day"]) for r in rows] == list(range(1, 8))
    assert float(rows[0]["flock_feed_kg"]) > 0


def test_feed_plan_csv_rejects_a_bad_range():
    assert client.get("/api/feed/plan.csv", params={"day_from": 10, "day_to": 2}).status_code == 422


def test_offline_evals_stay_above_their_floors():
    done = subprocess.run([sys.executable, "-m", "evals.run", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr


def test_path_ids_are_grouped_into_one_route():
    for rid in ("abc123", "def456"):
        client.post(f"/api/admin/registrations/{rid}/reject", headers={"x-admin-key": "test-admin"})
    routes = [r["route"] for r in metrics.snapshot()["routes"]]
    assert "POST /api/admin/registrations/{rid}/reject" in routes
    assert not any("abc123" in r for r in routes)
