from __future__ import annotations

import statistics
from typing import TYPE_CHECKING

from traveller.categories import ceiling_for
from traveller.evaluator.phase1 import evaluate_phase1
from traveller.evaluator.phase2 import evaluate_phase2
from traveller.evaluator.phase3 import evaluate_phase3
from traveller.evaluator.phase_selector import select_phase
from traveller.models import DealFlag

if TYPE_CHECKING:
    from traveller.models import BaselineConfig, Category, CategoryCeilings, Fare


def evaluate_route(
    *,
    fares: list[Fare],
    observation_count: int,
    prior_prices: tuple[float, ...],
    category: Category,
    is_wishlist: bool,
    baseline: BaselineConfig,
    ceilings: CategoryCeilings,
    wishlist_multiplier: float,
) -> DealFlag:
    phase = select_phase(
        observation_count=observation_count,
        thresholds=baseline.phase_thresholds,
    )
    ceiling = ceiling_for(
        category, ceilings,
        is_wishlist=is_wishlist, multiplier=wishlist_multiplier,
    )
    p1 = evaluate_phase1(
        fares=fares,
        percentile=baseline.cold_start_p_percentile,
        ceiling=ceiling,
    )
    if phase == 1:
        return p1
    if not fares:
        return DealFlag(
            is_deal=False, phase=phase,
            reason="no fares returned",
            market_p15_eur=p1.market_p15_eur, baseline_median_eur=None,
        )
    best = min(f.price_eur for f in fares)
    median = statistics.median(prior_prices) if prior_prices else 0.0
    p2 = evaluate_phase2(
        best_price=best, baseline_median=median, ceiling=ceiling,
        is_wishlist=is_wishlist,
        min_discount_pct_non_wishlist=baseline.phase2_min_discount_pct_non_wishlist,
        min_discount_pct_wishlist=baseline.phase2_min_discount_pct_wishlist,
    )
    if phase == 2:
        # Preserve market p15 for observation record
        return DealFlag(
            is_deal=p2.is_deal, phase=2, reason=p2.reason,
            market_p15_eur=p1.market_p15_eur,
            baseline_median_eur=p2.baseline_median_eur,
        )
    return evaluate_phase3(phase1_flag=p1, phase2_flag=p2)
