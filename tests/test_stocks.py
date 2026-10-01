from agent import stocks


def make_series(start, daily_growth, days=80, volume=2_000_000):
    close = [start * (1 + daily_growth) ** i for i in range(days)]
    return close, [float(volume)] * days


def test_analyze_stock_rejects_ineligible():
    close, volume = make_series(10.0, 0.0)  # above $5
    assert stocks.analyze_stock("BIG", "Big Co", close, volume) is None
    close, volume = make_series(1.0, 0.0, days=20)  # not enough history
    assert stocks.analyze_stock("NEW", "New Co", close, volume) is None
    close, volume = make_series(1.0, 0.0, volume=1_000)  # illiquid
    assert stocks.analyze_stock("THIN", "Thin Co", close, volume) is None


def test_analyze_stock_scores_uptrend_above_downtrend():
    up = stocks.analyze_stock("UP", "Up Co", *make_series(1.0, 0.01))
    down = stocks.analyze_stock("DOWN", "Down Co", *make_series(4.0, -0.01))
    assert up and down
    assert up["score"] > down["score"]
    assert up["change_1m"] > 0 > down["change_1m"]
    assert 0 <= up["score"] <= 100
    assert up["url"] == "https://finance.yahoo.com/quote/UP"
    assert up["rationale"].endswith(".")


def test_research_penny_stocks_ranks_top_n_and_fills_names():
    universe = {f"S{i}": f"S{i}" for i in range(15)}
    history = {}
    for i, symbol in enumerate(universe):
        close, volume = make_series(1.0, 0.001 * i)
        history[symbol] = {"close": close, "volume": volume}

    results = stocks.research_penny_stocks(
        top_n=10,
        screen=lambda: universe,
        fetch_history=lambda symbols: history,
        fetch_names=lambda symbols: {s: f"{s} Inc" for s in symbols},
    )
    assert len(results) == 10
    assert [r["rank"] for r in results] == list(range(1, 11))
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)
    assert results[0]["symbol"] == "S14"
    assert results[0]["name"] == "S14 Inc"


def test_fetch_price_history_parses_grouped_download(monkeypatch):
    import pandas as pd
    import yfinance as yf

    index = pd.date_range("2026-01-01", periods=3)
    columns = pd.MultiIndex.from_product([["AAA", "BBB"], ["Open", "Close", "Volume"]])
    frame = pd.DataFrame(
        [[1, 1.1, 100, 2, 2.1, 200], [1, 1.2, 110, 2, None, None], [1, 1.3, 120, 2, 2.3, 230]],
        index=index,
        columns=columns,
    )
    monkeypatch.setattr(yf, "download", lambda *args, **kwargs: frame)
    history = stocks.fetch_price_history(["AAA", "BBB", "MISSING"])
    assert history["AAA"] == {"close": [1.1, 1.2, 1.3], "volume": [100.0, 110.0, 120.0]}
    assert history["BBB"]["close"] == [2.1, 2.3]
    assert "MISSING" not in history


def test_screen_falls_back_when_screener_fails(monkeypatch):
    import yfinance as yf

    def broken(*args, **kwargs):
        raise RuntimeError("blocked")

    monkeypatch.setattr(stocks.config, "PENNY_STOCK_UNIVERSE", [])
    monkeypatch.setattr(yf, "screen", broken)
    universe = stocks.screen_penny_universe()
    assert list(universe) == stocks.config.FALLBACK_PENNY_UNIVERSE

    monkeypatch.setattr(yf, "screen", lambda *a, **k: {"quotes": [{"symbol": "ABC", "shortName": "ABC Corp"}]})
    assert stocks.screen_penny_universe() == {"ABC": "ABC Corp"}
