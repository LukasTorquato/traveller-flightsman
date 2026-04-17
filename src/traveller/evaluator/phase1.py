from __future__ import annotations

from traveller.models import DealFlag, Fare


def evaluate_phase1(
    *,
    fares: list[Fare],
    percentile: float,
    ceiling: float,
    override_best_price: float | None = None,
) -> DealFlag:
    if not fares:
        return DealFlag(
            is_deal=False,
            phase=1,
            reason="no fares returned",
            market_p15_eur=None,
            baseline_median_eur=None,
        )
    prices = sorted(f.price_eur for f in fares)
    p = _percentile(prices, percentile)
    best = override_best_price if override_best_price is not None else prices[0]
    if best > ceiling:
        return DealFlag(
            is_deal=False,
            phase=1,
            reason=f"best {best:.2f} above ceiling {ceiling:.2f}",
            market_p15_eur=p,
            baseline_median_eur=None,
        )
    if best > p:
        return DealFlag(
            is_deal=False,
            phase=1,
            reason=f"best {best:.2f} above p15 {p:.2f}",
            market_p15_eur=p,
            baseline_median_eur=None,
        )
    return DealFlag(
        is_deal=True,
        phase=1,
        reason=f"best {best:.2f} <= p15 {p:.2f} and <= ceiling {ceiling:.2f}",
        market_p15_eur=p,
        baseline_median_eur=None,
    )


def _percentile(sorted_prices: list[float], pct: float) -> float:
    """Linear-interpolation percentile on sorted input."""
    if not sorted_prices:
        raise ValueError("empty prices")
    if len(sorted_prices) == 1:
        return sorted_prices[0]
    rank = (pct / 100.0) * (len(sorted_prices) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(sorted_prices) - 1)
    frac = rank - lo
    return sorted_prices[lo] + frac * (sorted_prices[hi] - sorted_prices[lo])
