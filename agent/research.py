"""Research agent orchestrator: runs all research and writes the recommendations report.

Usage::

    python -m agent.research --output docs/data/recommendations.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import tempfile
from datetime import datetime, timezone
from typing import Callable

from . import config
from .ai import add_ai_summaries
from .crypto import CRYPTO_WEIGHTS, research_crypto
from .schedule import next_scheduled_run
from .stocks import STOCK_WEIGHTS, research_penny_stocks

log = logging.getLogger(__name__)

DEFAULT_OUTPUT = os.path.join("docs", "data", "recommendations.json")


def run_research(
    stock_researcher: Callable[[], list[dict]] = research_penny_stocks,
    crypto_researcher: Callable[[], list[dict]] = research_crypto,
    summarizer: Callable[[list[dict], str], bool] = add_ai_summaries,
    now: datetime | None = None,
) -> dict:
    """Run penny stock and crypto research and build the report dictionary."""
    now = now or datetime.now(timezone.utc)
    errors: list[str] = []

    def safely(name: str, researcher: Callable[[], list[dict]]) -> list[dict]:
        try:
            return researcher()
        except Exception as exc:
            log.exception("%s research failed", name)
            errors.append(f"{name} research failed: {exc}")
            return []

    penny_stocks = safely("Penny stock", stock_researcher)
    crypto = safely("Cryptocurrency", crypto_researcher)

    ai_enabled = False
    for items, asset_class in ((penny_stocks, "US penny stocks"), (crypto, "cryptocurrencies")):
        try:
            ai_enabled = bool(summarizer(items, asset_class)) or ai_enabled
        except Exception as exc:
            log.warning("AI summaries failed for %s: %s", asset_class, exc)

    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "next_refresh": next_scheduled_run(now).isoformat(timespec="seconds"),
        "schedule": config.SCHEDULE_DESCRIPTION,
        "ai_summaries": ai_enabled,
        "penny_stocks": penny_stocks,
        "crypto": crypto,
        "methodology": {
            "penny_stocks": (
                f"US-listed stocks priced ${config.PENNY_MIN_PRICE:.2f}-${config.PENNY_MAX_PRICE:.2f} "
                "with sufficient liquidity, scored on 1-month and 1-week momentum, moving-average "
                "trend, RSI, volume surge and dollar volume."
            ),
            "penny_stock_weights": STOCK_WEIGHTS,
            "crypto": (
                f"Top {config.CRYPTO_UNIVERSE_SIZE} cryptocurrencies by market cap (excluding "
                "stablecoins and wrapped/staked tokens), scored on 30-day, 7-day and 24-hour "
                "momentum, trend consistency, trading turnover and market-cap rank."
            ),
            "crypto_weights": CRYPTO_WEIGHTS,
        },
        "disclaimer": config.DISCLAIMER,
        "errors": errors,
    }


def write_report(report: dict, path: str) -> None:
    """Atomically write the report as JSON to ``path``."""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the penny stock & crypto research agent")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="path of the JSON report to write")
    parser.add_argument(
        "--allow-partial", action="store_true",
        help="exit successfully even if one of the recommendation lists is empty",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    report = run_research()
    write_report(report, args.output)
    log.info(
        "Wrote %d penny stock and %d crypto recommendations to %s",
        len(report["penny_stocks"]), len(report["crypto"]), args.output,
    )
    if not args.allow_partial and (not report["penny_stocks"] or not report["crypto"]):
        log.error("Research incomplete: %s", "; ".join(report["errors"]) or "no recommendations")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
