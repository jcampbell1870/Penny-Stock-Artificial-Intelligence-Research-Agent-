"""Weekly refresh schedule: every Monday at 7:00 PM Eastern Time."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from . import config


def _tz() -> ZoneInfo:
    return ZoneInfo(config.REFRESH_TIMEZONE)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def last_scheduled_run(now: datetime | None = None) -> datetime:
    """Most recent scheduled refresh time at or before ``now`` (timezone-aware)."""
    local_now = (now or _now()).astimezone(_tz())
    days_back = (local_now.weekday() - config.REFRESH_WEEKDAY) % 7
    candidate_date = (local_now - timedelta(days=days_back)).date()
    candidate = datetime(
        candidate_date.year, candidate_date.month, candidate_date.day,
        config.REFRESH_HOUR, config.REFRESH_MINUTE, tzinfo=_tz(),
    )
    if candidate > local_now:
        candidate_date -= timedelta(days=7)
        candidate = candidate.replace(
            year=candidate_date.year, month=candidate_date.month, day=candidate_date.day,
        )
    return candidate


def next_scheduled_run(now: datetime | None = None) -> datetime:
    """Next scheduled refresh time strictly after ``now`` (timezone-aware)."""
    last = last_scheduled_run(now)
    next_date = (last + timedelta(days=7)).date()
    return last.replace(year=next_date.year, month=next_date.month, day=next_date.day)


def is_stale(generated_at: datetime | None, now: datetime | None = None) -> bool:
    """True if data generated at ``generated_at`` predates the latest scheduled refresh."""
    if generated_at is None:
        return True
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)
    return generated_at < last_scheduled_run(now)


def cron_matches_local_schedule(cron: str, now: datetime | None = None) -> bool:
    """Check whether a UTC cron trigger corresponds to Monday 7 PM Eastern right now.

    GitHub Actions cron schedules are UTC-only, so the workflow registers both
    ``0 23 * * 1`` (7 PM EDT) and ``0 0 * * 2`` (7 PM EST). This returns True only
    for the trigger that matches Eastern Time's current DST offset, so the research
    runs exactly once per week at 7 PM local time.
    """
    minute, hour, _, _, weekday = cron.split()[:5]
    now_utc = (now or _now()).astimezone(timezone.utc)
    # Cron weekday: 0/7 = Sunday; Python weekday(): 0 = Monday.
    cron_weekday = (int(weekday) - 1) % 7
    days_back = (now_utc.weekday() - cron_weekday) % 7
    fired = (now_utc - timedelta(days=days_back)).replace(
        hour=int(hour), minute=int(minute), second=0, microsecond=0,
    )
    if fired > now_utc:
        fired -= timedelta(days=7)
    local = fired.astimezone(_tz())
    return (
        local.weekday() == config.REFRESH_WEEKDAY
        and local.hour == config.REFRESH_HOUR
        and local.minute == config.REFRESH_MINUTE
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Weekly research schedule helper")
    parser.add_argument("--check-cron", metavar="CRON", help="exit 0 if this UTC cron trigger should run now")
    args = parser.parse_args(argv)
    if args.check_cron:
        should_run = cron_matches_local_schedule(args.check_cron)
        print("true" if should_run else "false")
        return 0 if should_run else 1
    print(f"Last scheduled run: {last_scheduled_run().isoformat()}")
    print(f"Next scheduled run: {next_scheduled_run().isoformat()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
