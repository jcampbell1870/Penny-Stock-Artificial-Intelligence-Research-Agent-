from datetime import datetime, timezone

import pytest

from agent.schedule import (
    cron_matches_local_schedule,
    is_stale,
    last_scheduled_run,
    main,
    next_scheduled_run,
)


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def test_last_and_next_run_winter_est():
    # Wednesday 2026-01-14 12:00 UTC -> last run Monday 2026-01-12 19:00 EST (00:00 UTC Tue)
    now = utc(2026, 1, 14, 12)
    last = last_scheduled_run(now)
    assert last.astimezone(timezone.utc) == utc(2026, 1, 13, 0)
    assert (last.weekday(), last.hour, last.minute) == (0, 19, 0)
    assert next_scheduled_run(now).astimezone(timezone.utc) == utc(2026, 1, 20, 0)


def test_last_run_summer_edt():
    now = utc(2026, 7, 15, 12)
    assert last_scheduled_run(now).astimezone(timezone.utc) == utc(2026, 7, 13, 23)
    assert next_scheduled_run(now).astimezone(timezone.utc) == utc(2026, 7, 20, 23)


def test_monday_before_and_after_refresh_time():
    before = utc(2026, 1, 12, 23, 59)  # Monday 6:59 PM EST
    after = utc(2026, 1, 13, 0, 0)  # Monday 7:00 PM EST
    assert last_scheduled_run(before).astimezone(timezone.utc) == utc(2026, 1, 6, 0)
    assert last_scheduled_run(after).astimezone(timezone.utc) == utc(2026, 1, 13, 0)


def test_dst_transition_week():
    # DST starts Sunday 2026-03-08; previous Monday run was EST, next is EDT.
    now = utc(2026, 3, 10, 12)
    assert last_scheduled_run(now).astimezone(timezone.utc) == utc(2026, 3, 9, 23)
    assert next_scheduled_run(utc(2026, 3, 5, 12)).astimezone(timezone.utc) == utc(2026, 3, 9, 23)


def test_is_stale():
    now = utc(2026, 1, 14, 12)
    assert is_stale(None, now)
    assert is_stale(utc(2026, 1, 12, 23), now)
    assert not is_stale(utc(2026, 1, 13, 0, 5), now)
    assert not is_stale(datetime(2026, 1, 13, 1), now)  # naive treated as UTC


@pytest.mark.parametrize(
    "cron, now, expected",
    [
        ("0 0 * * 2", utc(2026, 1, 13, 0, 7), True),     # winter: EST trigger runs
        ("0 23 * * 1", utc(2026, 1, 12, 23, 4), False),  # winter: EDT trigger skipped
        ("0 23 * * 1", utc(2026, 7, 13, 23, 3), True),   # summer: EDT trigger runs
        ("0 0 * * 2", utc(2026, 7, 14, 0, 2), False),    # summer: EST trigger skipped
        ("0 0 * * 2", utc(2026, 1, 13, 2, 30), True),    # delayed trigger still matched
    ],
)
def test_cron_matches_local_schedule(cron, now, expected):
    assert cron_matches_local_schedule(cron, now) is expected


def test_cli_prints_schedule(capsys):
    assert main([]) == 0
    assert "Next scheduled run" in capsys.readouterr().out
