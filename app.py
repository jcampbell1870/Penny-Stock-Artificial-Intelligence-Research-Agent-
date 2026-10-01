"""Web service (deployed on Render) serving the weekly research recommendations.

The research agent refreshes automatically every Monday at 7:00 PM Eastern Time via
an in-process scheduler. Because free Render instances may sleep, any request that
finds the data older than the latest scheduled refresh also triggers a background run.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime

from flask import Flask, jsonify, send_from_directory

from agent import config
from agent.research import run_research, write_report
from agent.schedule import is_stale

log = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "docs")
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
DATA_FILE = os.path.join(DATA_DIR, "recommendations.json")

_refresh_lock = threading.Lock()


def load_report() -> dict | None:
    try:
        with open(DATA_FILE, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def refresh() -> bool:
    """Run the research agent and save the report. Returns False if already running."""
    if not _refresh_lock.acquire(blocking=False):
        return False
    try:
        report = run_research()
        if report["penny_stocks"] or report["crypto"]:
            write_report(report, DATA_FILE)
        else:
            log.error("Research produced no recommendations; keeping previous report")
        return True
    except Exception:
        log.exception("Research refresh failed")
        return True
    finally:
        _refresh_lock.release()


def refresh_in_background() -> None:
    if not _refresh_lock.locked():
        threading.Thread(target=refresh, name="research-refresh", daemon=True).start()


def report_is_stale(report: dict | None) -> bool:
    if not report:
        return True
    try:
        generated_at = datetime.fromisoformat(report["generated_at"])
    except (KeyError, TypeError, ValueError):
        return True
    return is_stale(generated_at)


def create_app(start_scheduler: bool = True) -> Flask:
    app = Flask(__name__, static_folder=None)

    @app.get("/")
    def index():
        return send_from_directory(STATIC_DIR, "index.html")

    @app.get("/app.js")
    def app_js():
        return send_from_directory(STATIC_DIR, "app.js")

    @app.get("/style.css")
    def style_css():
        return send_from_directory(STATIC_DIR, "style.css")

    @app.get("/data/recommendations.json")
    @app.get("/api/recommendations")
    def recommendations():
        report = load_report()
        if report_is_stale(report):
            refresh_in_background()
        if report is None:
            return jsonify({
                "status": "pending",
                "message": "Research is in progress. Please check back in a few minutes.",
                "schedule": config.SCHEDULE_DESCRIPTION,
            }), 503
        return jsonify(report)

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    if start_scheduler:
        start_background_scheduler()
    return app


def start_background_scheduler():
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = BackgroundScheduler(timezone=config.REFRESH_TIMEZONE)
    scheduler.add_job(
        refresh,
        CronTrigger(
            day_of_week="mon",
            hour=config.REFRESH_HOUR,
            minute=config.REFRESH_MINUTE,
            timezone=config.REFRESH_TIMEZONE,
        ),
        id="weekly-research",
        misfire_grace_time=6 * 60 * 60,
        coalesce=True,
        max_instances=1,
    )
    scheduler.start()
    if report_is_stale(load_report()):
        refresh_in_background()
    return scheduler


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
app = create_app(start_scheduler=os.environ.get("DISABLE_SCHEDULER") != "1")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
