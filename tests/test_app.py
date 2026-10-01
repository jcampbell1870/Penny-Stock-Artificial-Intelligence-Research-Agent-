import json
import os

import pytest

os.environ["DISABLE_SCHEDULER"] = "1"

import app as web  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(web, "DATA_FILE", str(tmp_path / "recommendations.json"))
    triggered = []
    monkeypatch.setattr(web, "refresh_in_background", lambda: triggered.append(True))
    flask_app = web.create_app(start_scheduler=False)
    flask_app.testing = True
    client = flask_app.test_client()
    client.triggered = triggered
    return client


def test_serves_dashboard_and_assets(client):
    assert b"Top 10 Penny Stock" in client.get("/").data
    assert client.get("/app.js").status_code == 200
    assert client.get("/style.css").status_code == 200
    assert client.get("/healthz").get_json() == {"status": "ok"}


def test_pending_when_no_data_triggers_refresh(client):
    response = client.get("/data/recommendations.json")
    assert response.status_code == 503
    assert response.get_json()["status"] == "pending"
    assert client.triggered


def test_serves_fresh_report_without_refresh(client):
    from datetime import datetime, timezone

    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "penny_stocks": [], "crypto": []}
    with open(web.DATA_FILE, "w") as handle:
        json.dump(report, handle)
    response = client.get("/api/recommendations")
    assert response.status_code == 200
    assert response.get_json()["generated_at"] == report["generated_at"]
    assert not client.triggered


def test_stale_report_served_and_refresh_triggered(client):
    report = {"generated_at": "2020-01-01T00:00:00+00:00", "penny_stocks": [], "crypto": []}
    with open(web.DATA_FILE, "w") as handle:
        json.dump(report, handle)
    assert client.get("/data/recommendations.json").status_code == 200
    assert client.triggered


def test_refresh_writes_report(tmp_path, monkeypatch):
    path = tmp_path / "out.json"
    monkeypatch.setattr(web, "DATA_FILE", str(path))
    monkeypatch.setattr(web, "run_research", lambda: {"penny_stocks": [{"symbol": "A"}], "crypto": []})
    assert web.refresh() is True
    assert json.loads(path.read_text())["penny_stocks"][0]["symbol"] == "A"
