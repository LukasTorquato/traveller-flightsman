from datetime import date

from traveller.evaluator.dispatcher import evaluate_route
from traveller.models import BaselineConfig, CategoryCeilings, Fare, PhaseThresholds


def _fare(price: float) -> Fare:
    return Fare(
        price_eur=price, departure_date=date(2026, 6, 12),
        return_date=date(2026, 6, 15), nights=3,
        airline="FR", stops=0, source="kiwi", booking_url="x",
    )


def _baseline():
    return BaselineConfig(
        cold_start_p_percentile=15,
        baseline_window_observations=12,
        phase2_min_discount_pct_non_wishlist=25,
        phase2_min_discount_pct_wishlist=15,
        phase_thresholds=PhaseThresholds(phase1_max_obs=3, phase2_max_obs=11),
    )


def _ceilings():
    return CategoryCeilings(
        europe_short_haul=80, europe_long_haul=130,
        intercontinental_asia=550, intercontinental_south_america=600,
    )


def test_dispatcher_uses_phase1_when_no_history():
    fares = [_fare(40 + i * 2) for i in range(20)]
    result = evaluate_route(
        fares=fares, observation_count=0, prior_prices=(),
        category="europe_short_haul", is_wishlist=False,
        baseline=_baseline(), ceilings=_ceilings(),
        wishlist_multiplier=1.3,
    )
    assert result.phase == 1


def test_dispatcher_uses_phase2_with_medium_history():
    fares = [_fare(40) for _ in range(20)]
    prior = tuple(float(x) for x in range(80, 90))  # 10 priors, median ~84.5
    result = evaluate_route(
        fares=fares, observation_count=10, prior_prices=prior,
        category="europe_short_haul", is_wishlist=False,
        baseline=_baseline(), ceilings=_ceilings(),
        wishlist_multiplier=1.3,
    )
    assert result.phase == 2


def test_dispatcher_uses_phase3_with_long_history():
    fares = [_fare(40) for _ in range(20)]
    prior = tuple(float(x) for x in range(80, 100))  # 20 priors
    result = evaluate_route(
        fares=fares, observation_count=20, prior_prices=prior,
        category="europe_short_haul", is_wishlist=False,
        baseline=_baseline(), ceilings=_ceilings(),
        wishlist_multiplier=1.3,
    )
    assert result.phase == 3
