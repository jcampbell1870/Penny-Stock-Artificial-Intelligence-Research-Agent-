"""Pure-Python technical indicators and scoring helpers."""

from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Sequence


def scale(value: float | None, low: float, high: float) -> float:
    """Linearly map ``value`` from [low, high] onto [0, 1], clipping at the ends."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return 0.0
    if high == low:
        return 0.0
    return max(0.0, min(1.0, (value - low) / (high - low)))


def pct_change(values: Sequence[float], periods: int) -> float | None:
    """Percent change between the last value and the value ``periods`` bars earlier."""
    if len(values) <= periods or periods <= 0:
        return None
    start = values[-periods - 1]
    if not start:
        return None
    return (values[-1] / start - 1.0) * 100.0


def sma(values: Sequence[float], window: int) -> float | None:
    if len(values) < window or window <= 0:
        return None
    return mean(values[-window:])


def rsi(values: Sequence[float], period: int = 14) -> float | None:
    """Wilder's Relative Strength Index."""
    if len(values) <= period:
        return None
    deltas = [values[i] - values[i - 1] for i in range(1, len(values))]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]
    avg_gain = mean(gains[:period])
    avg_loss = mean(losses[:period])
    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def daily_volatility(values: Sequence[float], window: int = 20) -> float | None:
    """Standard deviation of daily percent returns over the last ``window`` bars."""
    if len(values) <= window:
        return None
    recent = values[-window - 1:]
    returns = [
        (recent[i] / recent[i - 1] - 1.0) * 100.0
        for i in range(1, len(recent))
        if recent[i - 1]
    ]
    if len(returns) < 2:
        return None
    return pstdev(returns)


def risk_level(volatility_pct: float | None) -> str:
    """Bucket a daily volatility percentage into a human-readable risk level."""
    if volatility_pct is None:
        return "Unknown"
    if volatility_pct < 3:
        return "Moderate"
    if volatility_pct < 6:
        return "High"
    return "Very High"


def weighted_score(components: dict[str, float], weights: dict[str, float]) -> float:
    """Combine 0-1 component scores into a 0-100 composite score."""
    total_weight = sum(weights.values())
    if not total_weight:
        return 0.0
    total = sum(components.get(name, 0.0) * weight for name, weight in weights.items())
    return round(100.0 * total / total_weight, 1)
