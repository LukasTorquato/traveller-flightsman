from __future__ import annotations

from traveller.models import DealFlag


def evaluate_phase2(
    *,
    best_price: float,
    baseline_median: float,
    ceiling: float,
    is_wishlist: bool,
    min_discount_pct_non_wishlist: float,
    min_discount_pct_wishlist: float,
) -> DealFlag:
    if best_price > ceiling:
        return DealFlag(
            is_deal=False,
            phase=2,
            reason=f"best {best_price:.2f} above ceiling {ceiling:.2f}",
            market_p15_eur=None,
            baseline_median_eur=baseline_median,
        )
    discount_pct = (1.0 - best_price / baseline_median) * 100.0 if baseline_median > 0 else 0.0
    threshold = min_discount_pct_wishlist if is_wishlist else min_discount_pct_non_wishlist
    if discount_pct < threshold:
        return DealFlag(
            is_deal=False,
            phase=2,
            reason=(f"discount {discount_pct:.1f}% below required {threshold:.0f}%"),
            market_p15_eur=None,
            baseline_median_eur=baseline_median,
        )
    return DealFlag(
        is_deal=True,
        phase=2,
        reason=(f"{discount_pct:.1f}% below baseline {baseline_median:.2f} (>= {threshold:.0f}%)"),
        market_p15_eur=None,
        baseline_median_eur=baseline_median,
    )
