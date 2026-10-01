import json
from datetime import datetime, timezone

from agent import ai, research


def test_run_research_builds_report_and_isolates_failures():
    def failing():
        raise RuntimeError("boom")

    report = research.run_research(
        stock_researcher=lambda: [{"symbol": "ABC", "score": 70, "rank": 1}],
        crypto_researcher=failing,
        summarizer=lambda items, kind: False,
        now=datetime(2026, 1, 14, 12, tzinfo=timezone.utc),
    )
    assert report["penny_stocks"][0]["symbol"] == "ABC"
    assert report["crypto"] == []
    assert report["errors"] == ["Cryptocurrency research failed: boom"]
    assert report["generated_at"] == "2026-01-14T12:00:00+00:00"
    assert report["next_refresh"] == "2026-01-19T19:00:00-05:00"
    assert report["schedule"] == "Every Monday at 7:00 PM Eastern Time"
    assert report["ai_summaries"] is False
    assert "not financial advice" in report["disclaimer"]


def test_write_report_and_cli_exit_code(tmp_path, monkeypatch):
    output = tmp_path / "nested" / "recommendations.json"
    monkeypatch.setattr(research, "run_research", lambda: {"penny_stocks": [{}], "crypto": [], "errors": ["x"]})
    assert research.main(["--output", str(output)]) == 1
    assert json.loads(output.read_text())["errors"] == ["x"]
    assert research.main(["--output", str(output), "--allow-partial"]) == 0


def test_ai_summaries_skipped_without_key(monkeypatch):
    monkeypatch.setattr(ai.config, "OPENAI_API_KEY", "")
    items = [{"symbol": "ABC"}]
    assert ai.add_ai_summaries(items, "stocks") is False
    assert "ai_summary" not in items[0]


def test_ai_summaries_added_from_llm_response(monkeypatch):
    monkeypatch.setattr(ai.config, "OPENAI_API_KEY", "test-key")

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": json.dumps({"ABC": "Strong momentum."})}}]}

    class Session:
        def post(self, url, headers=None, json=None, timeout=None):
            assert url.endswith("/chat/completions")
            assert headers["Authorization"].split() == ["Bearer", "test-key"]
            return Response()

    items = [{"symbol": "ABC", "price": 1.0}, {"symbol": "XYZ"}]
    assert ai.add_ai_summaries(items, "stocks", session=Session()) is True
    assert items[0]["ai_summary"] == "Strong momentum."
    assert "ai_summary" not in items[1]
