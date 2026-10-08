"""Every sign the app shows has guidance, and the frontend has words for it."""
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from api.main import app  # noqa: E402

client = TestClient(app)
EN = json.loads((ROOT / "frontend/src/assets/i18n/en.json").read_text())


def test_signs_include_the_urgent_ones():
    keys = {s["key"] for s in client.get("/api/health/signs").json()["data"]}
    assert {"huddling", "panting", "loose_droppings", "not_eating", "noisy_breathing", "lame", "sudden_deaths"} <= keys


def test_every_sign_has_words_and_advice_in_the_app():
    for sign in client.get("/api/health/signs").json()["data"]:
        assert f"health.sign.{sign['key']}" in EN
        assert f"health.advice.{sign['key']}" in EN


def test_sudden_deaths_points_to_a_vet():
    body = client.post("/api/health/assess", json={"signs": ["sudden_deaths"]}).json()
    assert "vet" in body["matched"][0]["suggests_en"].lower()
