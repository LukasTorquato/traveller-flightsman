from datetime import date

from traveller.evaluator.dispatcher import evaluate_route
from traveller.models import BaselineConfig, CategoryCeilings, Fare, PhaseThresholds


def _fare(price: float) -> Fare:
    return Fare(
        price_eur=price,
        departure_date=date(2026, 6, 12),
        return_date=date(2026, 6, 15),
        nights=3,
        airline="FR",
        stops=0,
        source="kiwi",
        booking_url="x",
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
        europe_short_haul=80,
        europe_long_haul=130,
        intercontinental_asia=550,
        intercontinental_south_america=600,
    )


def test_dispatcher_uses_phase1_when_no_history():
    fares = [_fare(40 + i * 2) for i in range(20)]
    result = evaluate_route(
        fares=fares,
        observation_count=0,
        prior_prices=(),
        category="europe_short_haul",
        is_wishlist=False,
        baseline=_baseline(),
        ceilings=_ceilings(),
        wishlist_multiplier=1.3,
    )
    assert result.phase == 1


def test_dispatcher_uses_phase2_with_medium_history():
    fares = [_fare(40) for _ in range(20)]
    prior = tuple(float(x) for x in range(80, 90))  # 10 priors, median ~84.5
    result = evaluate_route(
        fares=fares,
        observation_count=10,
        prior_prices=prior,
        category="europe_short_haul",
        is_wishlist=False,
        baseline=_baseline(),
        ceilings=_ceilings(),
        wishlist_multiplier=1.3,
    )
    assert result.phase == 2


def test_dispatcher_uses_phase3_with_long_history():
    fares = [_fare(40) for _ in range(20)]
    prior = tuple(float(x) for x in range(80, 100))  # 20 priors
    result = evaluate_route(
        fares=fares,
        observation_count=20,
        prior_prices=prior,
        category="europe_short_haul",
        is_wishlist=False,
        baseline=_baseline(),
        ceilings=_ceilings(),
        wishlist_multiplier=1.3,
    )
    assert result.phase == 3


def test_dispatcher_empty_fares_returns_no_deal():
    result = evaluate_route(
        fares=[],
        observation_count=0,
        prior_prices=(),
        category="europe_short_haul",
        is_wishlist=False,
        baseline=_baseline(),
        ceilings=_ceilings(),
        wishlist_multiplier=1.3,
    )
    assert result.is_deal is False
    assert result.market_p15_eur is None
    assert result.baseline_median_eur is None


def test_dispatcher_phase2_preserves_market_p15_from_phase1():
    # Use a spread of fares so p1 produces a meaningful p15
    fares = [_fare(40 + i * 2) for i in range(20)]  # 40, 42, ..., 78
    prior = tuple(float(x) for x in range(80, 90))  # 10 priors, median 84.5
    result = evaluate_route(
        fares=fares,
        observation_count=10,
        prior_prices=prior,
        category="europe_short_haul",
        is_wishlist=False,
        baseline=_baseline(),
        ceilings=_ceilings(),
        wishlist_multiplier=1.3,
    )
    assert result.phase == 2
    assert result.market_p15_eur is not None
    assert result.baseline_median_eur == 84.5
    # best=40 vs baseline=84.5 is a 52% discount - triggers is_deal
    assert result.is_deal is True


def test_dispatcher_phase3_requires_both_signals():
    # Fares: best=40, below ceiling(80). p15 of 40..58 range is ~42.7, best<=p15 -> p1 fires.
    # prior median of 80..99 = 89.5; discount = (1 - 40/89.5)*100 = 55.3% > 25% -> p2 fires.
    # Both fire -> phase 3 is_deal = True.
    fares = [_fare(40 + i) for i in range(20)]  # 40..59
    prior = tuple(float(x) for x in range(80, 100))
    result = evaluate_route(
        fares=fares,
        observation_count=20,
        prior_prices=prior,
        category="europe_short_haul",
        is_wishlist=False,
        baseline=_baseline(),
        ceilings=_ceilings(),
        wishlist_multiplier=1.3,
    )
    assert result.phase == 3
    assert result.is_deal is True


def test_dispatcher_wishlist_uses_looser_threshold():
    # Set up so non-wishlist would NOT flag but wishlist would.
    # Need discount between 15 and 25 percent.
    # best=85, median=100 -> 15% discount; exactly at wishlist threshold
    # Use best=83 (17% discount) to be safely above 15 but below 25.
    fares = [_fare(83)]
    prior = tuple([100.0] * 10)  # median 100
    # Without wishlist: 17% < 25% -> NO deal
    non_w = evaluate_route(
        fares=fares,
        observation_count=10,
        prior_prices=prior,
        category="europe_short_haul",
        is_wishlist=False,
        baseline=_baseline(),
        ceilings=_ceilings(),
        wishlist_multiplier=1.3,
    )
    assert non_w.is_deal is False
    # With wishlist: 17% >= 15% -> IS a deal (and ceiling 80*1.3=104 > 83, passes)
    wish = evaluate_route(
        fares=fares,
        observation_count=10,
        prior_prices=prior,
        category="europe_short_haul",
        is_wishlist=True,
        baseline=_baseline(),
        ceilings=_ceilings(),
        wishlist_multiplier=1.3,
    )
    assert wish.is_deal is True


def test_dispatcher_phase2_with_empty_prior_raises():
    import pytest

    fares = [_fare(40)]
    with pytest.raises(ValueError):
        evaluate_route(
            fares=fares,
            observation_count=10,
            prior_prices=(),
            category="europe_short_haul",
            is_wishlist=False,
            baseline=_baseline(),
            ceilings=_ceilings(),
            wishlist_multiplier=1.3,
        )
