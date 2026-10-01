"""Cryptocurrency research using CoinGecko market data."""

from __future__ import annotations

import logging
import math
from typing import Callable

import requests

from . import config
from .indicators import risk_level, scale, weighted_score
from .stocks import rank

log = logging.getLogger(__name__)

CRYPTO_WEIGHTS = {
    "momentum_1m": 0.25,
    "momentum_1w": 0.25,
    "momentum_1d": 0.10,
    "consistency": 0.15,
    "turnover": 0.15,
    "size": 0.10,
}

STABLECOIN_SYMBOLS = {
    "usdt", "usdc", "dai", "busd", "tusd", "usdp", "fdusd", "usde", "pyusd", "usdd",
    "gusd", "frax", "lusd", "eurc", "eurs", "usds", "susde", "usd0", "rlusd", "usdtb",
    "bfusd", "usdf", "usdx", "usdg", "usd1", "crvusd", "gho", "dola", "susds", "xaut",
    "paxg", "buidl", "usyc", "ustb", "ousg",
}
WRAPPED_OR_STAKED_SYMBOLS = {
    "wbtc", "weth", "steth", "wsteth", "weeth", "cbbtc", "reth", "wbeth", "ezeth",
    "rseth", "lbtc", "solvbtc", "meth", "jitosol", "msol", "bnsol", "tbtc", "cbeth",
    "wbnb", "btcb", "jupsol", "oseth", "sweth", "ethx", "wtrx", "wavax", "wmatic",
}
EXCLUDED_NAME_KEYWORDS = ("wrapped", "staked", "bridged", "liquid staking", "restaked")


def fetch_markets(session: requests.Session | None = None) -> list[dict]:
    """Fetch top coins by market cap with 24h/7d/30d price changes."""
    session = session or requests.Session()
    headers = {"Accept": "application/json"}
    if config.COINGECKO_API_KEY:
        headers["x-cg-demo-api-key"] = config.COINGECKO_API_KEY
    coins: list[dict] = []
    remaining = config.CRYPTO_UNIVERSE_SIZE
    page = 1
    while remaining > 0:
        per_page = min(remaining, 250)
        response = session.get(
            f"{config.COINGECKO_API_URL}/coins/markets",
            params={
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": per_page,
                "page": page,
                "sparkline": "false",
                "price_change_percentage": "24h,7d,30d",
            },
            headers=headers,
            timeout=config.HTTP_TIMEOUT,
        )
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break
        coins.extend(batch)
        remaining -= per_page
        page += 1
    return coins


def is_excluded(coin: dict) -> bool:
    """Exclude stablecoins and wrapped/staked derivatives, which aren't growth picks."""
    symbol = (coin.get("symbol") or "").lower()
    name = (coin.get("name") or "").lower()
    if symbol in STABLECOIN_SYMBOLS or symbol in WRAPPED_OR_STAKED_SYMBOLS:
        return True
    if any(keyword in name for keyword in EXCLUDED_NAME_KEYWORDS):
        return True
    price = coin.get("current_price") or 0
    change_7d = coin.get("price_change_percentage_7d_in_currency")
    if "usd" in symbol and 0.97 <= price <= 1.03:
        return True
    if 0.98 <= price <= 1.02 and change_7d is not None and abs(change_7d) < 1.0:
        return True
    return False


def analyze_coin(coin: dict) -> dict | None:
    """Compute a composite score for one coin, or ``None`` if ineligible."""
    if is_excluded(coin):
        return None
    price = coin.get("current_price")
    market_cap = coin.get("market_cap") or 0
    volume = coin.get("total_volume") or 0
    if not price or market_cap < config.CRYPTO_MIN_MARKET_CAP or volume < config.CRYPTO_MIN_VOLUME:
        return None

    change_1d = coin.get("price_change_percentage_24h_in_currency")
    if change_1d is None:
        change_1d = coin.get("price_change_percentage_24h")
    change_1w = coin.get("price_change_percentage_7d_in_currency")
    change_1m = coin.get("price_change_percentage_30d_in_currency")
    turnover = volume / market_cap if market_cap else 0.0
    rank_value = coin.get("market_cap_rank") or config.CRYPTO_UNIVERSE_SIZE

    positives = sum(1 for change in (change_1d, change_1w, change_1m) if change is not None and change > 0)
    components = {
        "momentum_1m": scale(change_1m, -40, 80),
        "momentum_1w": scale(change_1w, -20, 40),
        "momentum_1d": scale(change_1d, -10, 15),
        "consistency": positives / 3,
        "turnover": scale(turnover, 0.0, 0.3),
        "size": 1.0 - scale(rank_value, 1, config.CRYPTO_UNIVERSE_SIZE),
    }
    score = weighted_score(components, CRYPTO_WEIGHTS)
    # Approximate daily volatility from the magnitude of recent moves.
    moves = [abs(change_1d)] if change_1d is not None else []
    if change_1w is not None:
        moves.append(abs(change_1w) / math.sqrt(7))
    volatility = max(moves) if moves else None

    symbol = (coin.get("symbol") or "").upper()
    return {
        "symbol": symbol,
        "name": coin.get("name") or symbol,
        "id": coin.get("id"),
        "image": coin.get("image"),
        "price": price,
        "change_1d": _round(change_1d),
        "change_1w": _round(change_1w),
        "change_1m": _round(change_1m),
        "market_cap": market_cap,
        "market_cap_rank": coin.get("market_cap_rank"),
        "volume_24h": volume,
        "turnover": round(turnover, 3),
        "risk": risk_level(volatility),
        "score": score,
        "rationale": coin_rationale(change_1d, change_1w, change_1m, turnover, coin.get("market_cap_rank")),
        "url": f"https://www.coingecko.com/en/coins/{coin.get('id')}" if coin.get("id") else None,
    }


def coin_rationale(change_1d, change_1w, change_1m, turnover, market_cap_rank) -> str:
    reasons = []
    if change_1m is not None and change_1m > 0:
        reasons.append(f"up {change_1m:.1f}% over 30 days")
    if change_1w is not None and change_1w > 0:
        reasons.append(f"up {change_1w:.1f}% this week")
    if change_1d is not None and change_1d > 0:
        reasons.append(f"positive 24h momentum ({change_1d:+.1f}%)")
    if all(c is not None and c > 0 for c in (change_1d, change_1w, change_1m)):
        reasons.append("consistent uptrend across timeframes")
    if turnover >= 0.15:
        reasons.append(f"high trading activity ({turnover:.0%} of market cap traded in 24h)")
    if market_cap_rank and market_cap_rank <= 50:
        reasons.append(f"established large-cap asset (rank #{market_cap_rank})")
    if not reasons:
        return "Ranked on relative momentum and liquidity versus other cryptocurrencies."
    text = "; ".join(reasons)
    return text[0].upper() + text[1:] + "."


def research_crypto(
    top_n: int = config.TOP_N,
    fetch: Callable[[], list[dict]] = fetch_markets,
) -> list[dict]:
    """Fetch, analyze and rank cryptocurrencies; returns the top ``top_n``."""
    coins = fetch()
    analyzed = [result for result in (analyze_coin(coin) for coin in coins) if result]
    log.info("Analyzed %d of %d cryptocurrencies", len(analyzed), len(coins))
    return rank(analyzed, top_n)


def _round(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(value, digits)
