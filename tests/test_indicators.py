from agent.indicators import daily_volatility, pct_change, risk_level, rsi, scale, sma, weighted_score


def test_scale_clips_and_interpolates():
    assert scale(5, 0, 10) == 0.5
    assert scale(-5, 0, 10) == 0.0
    assert scale(50, 0, 10) == 1.0
    assert scale(None, 0, 10) == 0.0
    assert scale(float("nan"), 0, 10) == 0.0


def test_pct_change_and_sma():
    values = [10, 11, 12, 13, 14, 15]
    assert pct_change(values, 5) == 50.0
    assert pct_change(values, 10) is None
    assert sma(values, 2) == 14.5
    assert sma(values, 10) is None


def test_rsi_extremes_and_midpoint():
    rising = [float(i) for i in range(1, 40)]
    falling = list(reversed(rising))
    assert rsi(rising) == 100.0
    assert rsi(falling) == 0.0
    alternating = [10.0 + (i % 2) for i in range(40)]
    assert 40 < rsi(alternating) < 60
    assert rsi([1.0, 2.0]) is None


def test_volatility_and_risk():
    flat = [10.0] * 30
    assert daily_volatility(flat) == 0.0
    assert risk_level(0.0) == "Moderate"
    assert risk_level(4.0) == "High"
    assert risk_level(10.0) == "Very High"
    assert risk_level(None) == "Unknown"


def test_weighted_score():
    assert weighted_score({"a": 1.0, "b": 0.0}, {"a": 0.5, "b": 0.5}) == 50.0
    assert weighted_score({}, {}) == 0.0
