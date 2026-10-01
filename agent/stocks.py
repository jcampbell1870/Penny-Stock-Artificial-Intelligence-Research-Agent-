"""Penny stock research: universe screening, feature extraction and scoring."""

from __future__ import annotations

import logging
import math
from typing import Callable, Iterable

from . import config
from .indicators import (
    daily_volatility,
    pct_change,
    risk_level,
    rsi,
    scale,
    sma,
    weighted_score,
)

log = logging.getLogger(__name__)

STOCK_WEIGHTS = {
    "momentum_1m": 0.25,
    "momentum_1w": 0.15,
    "trend": 0.20,
    "rsi": 0.15,
    "volume_surge": 0.15,
    "liquidity": 0.10,
}

MIN_HISTORY_BARS = 55


def screen_penny_universe() -> dict[str, str]:
    """Return ``{symbol: name}`` for liquid US-listed stocks priced under $5."""
    if config.PENNY_STOCK_UNIVERSE:
        return {symbol: symbol for symbol in config.PENNY_STOCK_UNIVERSE}

    try:
        import yfinance as yf
        from yfinance import EquityQuery

        query = EquityQuery("and", [
            EquityQuery("eq", ["region", "us"]),
            EquityQuery("is-in", ["exchange", "NMS", "NYQ", "ASE", "NGM", "NCM"]),
            EquityQuery("btwn", ["intradayprice", config.PENNY_MIN_PRICE, config.PENNY_MAX_PRICE]),
            EquityQuery("gt", ["avgdailyvol3m", 500000]),
        ])
        result = yf.screen(
            query,
            size=min(config.PENNY_SCREEN_SIZE, 250),
            sortField="dayvolume",
            sortAsc=False,
        )
        universe = {
            quote["symbol"]: quote.get("shortName") or quote.get("longName") or quote["symbol"]
            for quote in result.get("quotes", [])
            if quote.get("symbol")
        }
        if universe:
            log.info("Yahoo screener returned %d penny stock candidates", len(universe))
            return universe
        log.warning("Yahoo screener returned no results; using fallback universe")
    except Exception as exc:  # network/API errors should not stop the agent
        log.warning("Yahoo screener failed (%s); using fallback universe", exc)

    return {symbol: symbol for symbol in config.FALLBACK_PENNY_UNIVERSE}


def fetch_price_history(symbols: Iterable[str]) -> dict[str, dict[str, list[float]]]:
    """Download ~6 months of daily closes and volumes for ``symbols``."""
    import yfinance as yf

    symbols = list(symbols)
    if not symbols:
        return {}
    frame = yf.download(
        symbols,
        period="6mo",
        interval="1d",
        group_by="ticker",
        auto_adjust=True,
        threads=True,
        progress=False,
    )
    history: dict[str, dict[str, list[float]]] = {}
    if frame is None or frame.empty:
        return history
    for symbol in symbols:
        try:
            data = frame[symbol] if symbol in frame.columns.get_level_values(0) else None
            if data is None:
                continue
            data = data[["Close", "Volume"]].dropna()
            history[symbol] = {
                "close": [float(v) for v in data["Close"].tolist()],
                "volume": [float(v) for v in data["Volume"].tolist()],
            }
        except (KeyError, ValueError) as exc:
            log.debug("No usable history for %s: %s", symbol, exc)
    return history


def lookup_names(symbols: Iterable[str]) -> dict[str, str]:
    """Best-effort company name lookup for symbols lacking one."""
    names: dict[str, str] = {}
    try:
        import yfinance as yf
    except ImportError:
        return names
    for symbol in symbols:
        try:
            info = yf.Ticker(symbol).info or {}
            name = info.get("shortName") or info.get("longName")
            if name:
                names[symbol] = name
        except Exception as exc:
            log.debug("Name lookup failed for %s: %s", symbol, exc)
    return names


def analyze_stock(symbol: str, name: str, close: list[float], volume: list[float]) -> dict | None:
    """Compute features and a composite score for one stock, or ``None`` if ineligible."""
    if len(close) < MIN_HISTORY_BARS or len(volume) != len(close):
        return None
    price = close[-1]
    if not (config.PENNY_MIN_PRICE <= price < config.PENNY_MAX_PRICE):
        return None

    avg_volume_20 = sum(volume[-20:]) / 20
    dollar_volume = avg_volume_20 * price
    if dollar_volume < config.PENNY_MIN_DOLLAR_VOLUME:
        return None

    change_1w = pct_change(close, 5)
    change_1m = pct_change(close, 21)
    change_3m = pct_change(close, min(63, len(close) - 1))
    rsi_14 = rsi(close, 14)
    sma_20 = sma(close, 20)
    sma_50 = sma(close, 50)
    avg_volume_5 = sum(volume[-5:]) / 5
    volume_ratio = avg_volume_5 / avg_volume_20 if avg_volume_20 else 0.0
    volatility = daily_volatility(close, 20)

    trend = 0.0
    if sma_20 and price > sma_20:
        trend += 0.5
    if sma_20 and sma_50 and sma_20 > sma_50:
        trend += 0.5

    components = {
        "momentum_1m": scale(change_1m, -30, 60),
        "momentum_1w": scale(change_1w, -15, 30),
        "trend": trend,
        # Favor healthy momentum (RSI ~55) and penalize overbought/oversold extremes.
        "rsi": max(0.0, 1.0 - abs((rsi_14 if rsi_14 is not None else 50.0) - 55.0) / 45.0),
        "volume_surge": scale(volume_ratio, 0.5, 2.5),
        "liquidity": scale(math.log10(dollar_volume) if dollar_volume > 0 else 0, 5.5, 7.5),
    }
    score = weighted_score(components, STOCK_WEIGHTS)

    return {
        "symbol": symbol,
        "name": name or symbol,
        "price": round(price, 4),
        "change_1w": _round(change_1w),
        "change_1m": _round(change_1m),
        "change_3m": _round(change_3m),
        "rsi": _round(rsi_14),
        "volume_ratio": round(volume_ratio, 2),
        "avg_dollar_volume": round(dollar_volume),
        "volatility": _round(volatility),
        "risk": risk_level(volatility),
        "score": score,
        "rationale": stock_rationale(components, change_1w, change_1m, rsi_14, volume_ratio),
        "url": f"https://finance.yahoo.com/quote/{symbol}",
    }


def stock_rationale(components, change_1w, change_1m, rsi_14, volume_ratio) -> str:
    reasons = []
    if change_1m is not None and change_1m > 0:
        reasons.append(f"up {change_1m:.1f}% over the past month")
    if change_1w is not None and change_1w > 0:
        reasons.append(f"up {change_1w:.1f}% this week")
    if components["trend"] >= 1.0:
        reasons.append("trading above a rising 20-day average")
    elif components["trend"] >= 0.5:
        reasons.append("improving short-term trend")
    if volume_ratio >= 1.3:
        reasons.append(f"volume running {volume_ratio:.1f}x its 20-day average")
    if rsi_14 is not None:
        if rsi_14 >= 70:
            reasons.append(f"RSI {rsi_14:.0f} (overbought - watch for pullbacks)")
        elif rsi_14 <= 30:
            reasons.append(f"RSI {rsi_14:.0f} (oversold - potential rebound)")
        else:
            reasons.append(f"RSI {rsi_14:.0f}")
    if components["liquidity"] >= 0.75:
        reasons.append("strong trading liquidity")
    if not reasons:
        return "Ranked on relative technical strength versus other penny stocks."
    text = "; ".join(reasons)
    return text[0].upper() + text[1:] + "."


def research_penny_stocks(
    top_n: int = config.TOP_N,
    screen: Callable[[], dict[str, str]] = screen_penny_universe,
    fetch_history: Callable[[Iterable[str]], dict] = fetch_price_history,
    fetch_names: Callable[[Iterable[str]], dict[str, str]] = lookup_names,
) -> list[dict]:
    """Screen, analyze and rank penny stocks; returns the top ``top_n``."""
    universe = screen()
    history = fetch_history(universe.keys())
    analyzed = []
    for symbol, name in universe.items():
        data = history.get(symbol)
        if not data:
            continue
        result = analyze_stock(symbol, name, data["close"], data["volume"])
        if result:
            analyzed.append(result)
    log.info("Analyzed %d of %d penny stock candidates", len(analyzed), len(universe))

    top = rank(analyzed, top_n)
    missing = [item["symbol"] for item in top if item["name"] == item["symbol"]]
    if missing:
        for symbol, name in fetch_names(missing).items():
            for item in top:
                if item["symbol"] == symbol:
                    item["name"] = name
    return top


def rank(items: list[dict], top_n: int) -> list[dict]:
    ranked = sorted(items, key=lambda item: item["score"], reverse=True)[:top_n]
    for position, item in enumerate(ranked, start=1):
        item["rank"] = position
    return ranked


def _round(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(value, digits)
