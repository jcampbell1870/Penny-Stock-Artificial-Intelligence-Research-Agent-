# Penny Stock & Crypto AI Research Agent

An automated research agent that screens **penny stocks** and **cryptocurrencies**, scores
them on momentum, trend, RSI, volume and liquidity, and publishes the
**top 10 buy recommendations** for each asset class:

- 🌐 **GitHub Pages** – a static dashboard (`docs/`) rebuilt by GitHub Actions.
- ☁️ **Render** – a web service (`app.py`) that serves the same dashboard and a JSON API.

Recommendations refresh **once per week, every Monday at 7:00 PM Eastern Time**
(7 PM EST in winter / 7 PM EDT in summer).

> ⚠️ For informational and educational purposes only. This is not financial advice.

## How it works

| Step | Penny stocks | Cryptocurrencies |
| --- | --- | --- |
| Data source | Yahoo Finance (`yfinance`) screener + 6 months of daily prices | CoinGecko `/coins/markets` (top 250 by market cap) |
| Universe filter | US-listed, $0.10–$5.00, ≥ $250k average daily dollar volume | Excludes stablecoins and wrapped/staked tokens, ≥ $50M market cap, ≥ $5M 24h volume |
| Scoring (0–100) | 1-month & 1-week momentum, 20/50-day moving-average trend, RSI(14), volume surge, liquidity | 30-day, 7-day & 24h momentum, trend consistency, volume/market-cap turnover, market-cap rank |
| Output | Top 10 with price, changes, RSI, risk level, score and research notes | Top 10 with price, changes, rank, risk level, score and research notes |

If `OPENAI_API_KEY` is set, the agent also asks an LLM (any OpenAI-compatible API) to
write a short research note for each pick. Without a key, rule-based notes are used.

The report is written to JSON (`docs/data/recommendations.json` for GitHub Pages, or
`$DATA_DIR/recommendations.json` for Render) and rendered by `docs/index.html`.

## Project layout

```
agent/            Research agent (screening, indicators, scoring, AI notes, schedule)
docs/             Static dashboard published to GitHub Pages
app.py            Flask web service for Render (with weekly in-process scheduler)
render.yaml       Render Blueprint
.github/workflows/weekly-research.yml   Weekly research + GitHub Pages deploy
tests/            pytest suite
```

## Run locally

```bash
pip install -r requirements-dev.txt
python -m pytest                     # run tests
python -m agent.research             # writes docs/data/recommendations.json
python -m http.server -d docs 8000   # view the dashboard at http://localhost:8000
python -m agent.schedule             # show last/next scheduled refresh times
```

Or run the web service: `gunicorn app:app --workers 1 --threads 4` and open http://localhost:8000.

## Deploy to GitHub Pages

1. In **Settings → Pages**, set **Source** to **GitHub Actions**.
2. (Optional) Add repository secrets `OPENAI_API_KEY` and `COINGECKO_API_KEY`, and the
   repository variable `OPENAI_MODEL` (defaults to `gpt-4o-mini`).
3. The **Weekly research & GitHub Pages** workflow runs every Monday at 7 PM Eastern,
   on pushes to `main`, and on demand via **Run workflow**.

GitHub Actions cron schedules are UTC-only, so the workflow registers both
`0 23 * * 1` (7 PM EDT) and `0 0 * * 2` (7 PM EST); a gate job runs only the trigger
that matches the current Eastern daylight-saving offset. If either data source fails, the
job fails and the previously published recommendations remain live.

## Deploy to Render

1. In Render, choose **New → Blueprint** and select this repository (uses `render.yaml`).
2. Optionally set `OPENAI_API_KEY` / `COINGECKO_API_KEY` environment variables.

The service runs a scheduler that refreshes recommendations every Monday at 7 PM
Eastern (`America/New_York`). Because free Render instances sleep when idle, any request
that finds data older than the most recent Monday 7 PM refresh also triggers a background
refresh. Endpoints:

- `/` – dashboard
- `/api/recommendations` (or `/data/recommendations.json`) – JSON report
- `/healthz` – health check

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `TOP_N` | `10` | Number of recommendations per asset class |
| `PENNY_MIN_PRICE` / `PENNY_MAX_PRICE` | `0.10` / `5.00` | Penny stock price range |
| `PENNY_MIN_DOLLAR_VOLUME` | `250000` | Minimum average daily dollar volume |
| `PENNY_STOCK_UNIVERSE` | _(screener)_ | Comma-separated tickers to use instead of the Yahoo screener |
| `CRYPTO_UNIVERSE_SIZE` | `250` | Number of coins (by market cap) to analyze |
| `CRYPTO_MIN_MARKET_CAP` / `CRYPTO_MIN_VOLUME` | `50000000` / `5000000` | Crypto liquidity filters |
| `COINGECKO_API_KEY` | _(none)_ | Optional CoinGecko demo API key |
| `OPENAI_API_KEY` / `OPENAI_MODEL` / `OPENAI_BASE_URL` | _(none)_ / `gpt-4o-mini` / OpenAI | Optional LLM research notes |
| `DATA_DIR` | `./data` | Where the Render service stores the report |
