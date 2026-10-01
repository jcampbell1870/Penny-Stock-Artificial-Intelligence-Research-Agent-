"""Configuration for the research agent (overridable with environment variables)."""

import os

TOP_N = int(os.environ.get("TOP_N", "10"))

# Weekly refresh: every Monday at 7:00 PM Eastern Time.
REFRESH_TIMEZONE = os.environ.get("REFRESH_TIMEZONE", "America/New_York")
REFRESH_WEEKDAY = 0  # Monday (datetime.weekday())
REFRESH_HOUR = 19
REFRESH_MINUTE = 0
SCHEDULE_DESCRIPTION = "Every Monday at 7:00 PM Eastern Time"

# Penny stocks: the SEC defines a penny stock as trading below $5 per share.
PENNY_MIN_PRICE = float(os.environ.get("PENNY_MIN_PRICE", "0.10"))
PENNY_MAX_PRICE = float(os.environ.get("PENNY_MAX_PRICE", "5.00"))
PENNY_MIN_DOLLAR_VOLUME = float(os.environ.get("PENNY_MIN_DOLLAR_VOLUME", "250000"))
PENNY_SCREEN_SIZE = int(os.environ.get("PENNY_SCREEN_SIZE", "250"))

# Used when the Yahoo Finance screener is unavailable. Tickers that are no
# longer priced as penny stocks are filtered out automatically.
FALLBACK_PENNY_UNIVERSE = [
    "SNDL", "TLRY", "ACB", "OCGN", "GSAT", "BBAI", "CLOV", "WKHS",
    "IDEX", "SENS", "CTRM", "TOP", "GEVO", "FCEL", "PLUG", "BNGO",
    "TELL", "AMC", "LCID", "OPEN", "SOUN", "MVIS", "RIG", "NAK",
    "HL", "UUUU", "CENN", "KULR", "DNN", "BTG", "ITUB",
    "ABEV", "VALE", "NIO", "XPEV", "GRAB", "SIRI", "CHPT", "QS", "RIOT",
    "MARA", "HIVE", "BITF", "CIFR", "HUT",
]
PENNY_STOCK_UNIVERSE = [
    t.strip().upper()
    for t in os.environ.get("PENNY_STOCK_UNIVERSE", "").split(",")
    if t.strip()
]

# Cryptocurrencies (CoinGecko public API).
COINGECKO_API_URL = os.environ.get("COINGECKO_API_URL", "https://api.coingecko.com/api/v3")
COINGECKO_API_KEY = os.environ.get("COINGECKO_API_KEY", "")
CRYPTO_UNIVERSE_SIZE = int(os.environ.get("CRYPTO_UNIVERSE_SIZE", "250"))
CRYPTO_MIN_MARKET_CAP = float(os.environ.get("CRYPTO_MIN_MARKET_CAP", "50000000"))
CRYPTO_MIN_VOLUME = float(os.environ.get("CRYPTO_MIN_VOLUME", "5000000"))

# Optional LLM commentary (any OpenAI-compatible chat completions API).
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

HTTP_TIMEOUT = float(os.environ.get("HTTP_TIMEOUT", "30"))

DISCLAIMER = (
    "For informational and educational purposes only. This is not financial advice. "
    "Penny stocks and cryptocurrencies are highly speculative and volatile; you can "
    "lose some or all of your investment. Do your own research."
)
