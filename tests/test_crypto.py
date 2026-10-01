from agent import crypto


def coin(symbol, name=None, price=10.0, c1d=1.0, c7d=5.0, c30d=10.0, mcap=1e9, volume=1e8, rank=20):
    return {
        "id": symbol.lower(),
        "symbol": symbol.lower(),
        "name": name or symbol.title(),
        "image": "https://example.com/x.png",
        "current_price": price,
        "market_cap": mcap,
        "market_cap_rank": rank,
        "total_volume": volume,
        "price_change_percentage_24h_in_currency": c1d,
        "price_change_percentage_7d_in_currency": c7d,
        "price_change_percentage_30d_in_currency": c30d,
    }


def test_excludes_stablecoins_and_wrapped_tokens():
    assert crypto.is_excluded(coin("USDT", price=1.0))
    assert crypto.is_excluded(coin("WBTC", price=60000))
    assert crypto.is_excluded(coin("XYZ", name="Wrapped Something"))
    assert crypto.is_excluded(coin("NEWUSD", price=1.001, c7d=0.1))
    assert not crypto.is_excluded(coin("SOL", price=150))


def test_analyze_coin_filters_small_and_scores_momentum():
    assert crypto.analyze_coin(coin("TINY", mcap=1e6)) is None
    assert crypto.analyze_coin(coin("DRY", volume=1e3)) is None
    strong = crypto.analyze_coin(coin("UP", c1d=5, c7d=20, c30d=50))
    weak = crypto.analyze_coin(coin("DN", c1d=-5, c7d=-15, c30d=-30))
    assert strong["score"] > weak["score"]
    assert strong["symbol"] == "UP"
    assert strong["url"] == "https://www.coingecko.com/en/coins/up"
    assert "consistent uptrend" in strong["rationale"]


def test_research_crypto_returns_ranked_top_n():
    coins = [coin(f"C{i}", c7d=i, c30d=2 * i, rank=i + 1) for i in range(20)]
    coins.append(coin("USDC", price=1.0))
    results = crypto.research_crypto(top_n=10, fetch=lambda: coins)
    assert len(results) == 10
    assert all(r["symbol"] != "USDC" for r in results)
    assert [r["rank"] for r in results] == list(range(1, 11))
    assert results[0]["symbol"] == "C19"


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self):
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append(params)
        return FakeResponse([coin("BTC")] * params["per_page"])


def test_fetch_markets_paginates(monkeypatch):
    monkeypatch.setattr(crypto.config, "CRYPTO_UNIVERSE_SIZE", 300)
    session = FakeSession()
    coins = crypto.fetch_markets(session)
    assert len(coins) == 300
    assert [c["page"] for c in session.calls] == [1, 2]
    assert [c["per_page"] for c in session.calls] == [250, 50]
