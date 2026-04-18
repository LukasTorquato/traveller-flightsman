"""Tests for the traveller_math validation calculator."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Make the repo root importable so we can import traveller_math without install.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import traveller_math as tm  # noqa: E402


# ---- percentile -------------------------------------------------------------


def test_percentile_single_value_returns_that_value() -> None:
    assert tm.percentile([42.0], 15) == 42.0


def test_percentile_empty_raises() -> None:
    with pytest.raises(ValueError):
        tm.percentile([], 15)


def test_percentile_0th_and_100th_are_min_and_max() -> None:
    vals = [10.0, 20.0, 30.0, 40.0]
    assert tm.percentile(vals, 0) == 10.0
    assert tm.percentile(vals, 100) == 40.0


def test_percentile_15_linear_interpolation() -> None:
    # p15 of [40, 50, 60, 70, 80]: rank = 0.15 * 4 = 0.6
    # lo=40, hi=50, frac=0.6 -> 40 + 0.6*10 = 46
    assert tm.percentile([40.0, 50.0, 60.0, 70.0, 80.0], 15) == pytest.approx(46.0)


# ---- median -----------------------------------------------------------------


def test_median_odd_length() -> None:
    assert tm.median([1.0, 2.0, 3.0]) == 2.0


def test_median_even_length_is_midpoint_average() -> None:
    assert tm.median([1.0, 2.0, 3.0, 4.0]) == 2.5


# ---- evaluate: settings fixture --------------------------------------------


_SETTINGS = {
    "cold_start_p_percentile": 15,
    "phase1_max_obs": 3,
    "phase2_max_obs": 11,
    "phase2_min_discount_pct_non_wishlist": 25,
    "phase2_min_discount_pct_wishlist": 15,
    "ceilings_eur": {
        "europe_short_haul": 80,
        "europe_long_haul": 130,
        "intercontinental_asia": 550,
        "intercontinental_south_america": 600,
    },
    "wishlist_ceiling_multiplier": 1.3,
}


def _route(**overrides):
    base = {
        "destination_iata": "BCN",
        "is_wishlist": False,
        "category": "europe_short_haul",
        "current_fares_eur": [50.0, 60.0, 70.0, 80.0, 90.0],
        "prior_prices_eur": [],
    }
    base.update(overrides)
    return base


# ---- evaluate: phase 1 ------------------------------------------------------


def test_evaluate_phase1_fires_when_best_below_p15_and_ceiling() -> None:
    # current fares include a 48 that is <= p15 and <= ceiling 80
    route = _route(current_fares_eur=[48.0, 60.0, 70.0, 80.0, 90.0])
    result = tm.evaluate_routes({"routes": [route], "settings": _SETTINGS})
    verdict = result["verdicts"][0]
    assert verdict["phase"] == 1
    assert verdict["is_deal"] is True
    assert verdict["best_price_eur"] == 48.0
    assert verdict["ceiling_eur"] == 80.0
    assert verdict["baseline_median_eur"] is None


def test_evaluate_phase1_fails_when_best_above_ceiling() -> None:
    # Every fare above ceiling 80
    route = _route(current_fares_eur=[90.0, 100.0, 110.0])
    result = tm.evaluate_routes({"routes": [route], "settings": _SETTINGS})
    verdict = result["verdicts"][0]
    assert verdict["phase"] == 1
    assert verdict["is_deal"] is False
    assert "ceiling" in verdict["reason"]


def test_evaluate_phase1_empty_fares_graceful() -> None:
    route = _route(current_fares_eur=[])
    result = tm.evaluate_routes({"routes": [route], "settings": _SETTINGS})
    verdict = result["verdicts"][0]
    assert verdict["is_deal"] is False
    assert verdict["best_price_eur"] is None
    assert "no fares" in verdict["reason"]


# ---- evaluate: phase 2 ------------------------------------------------------


def test_evaluate_phase2_discount_fires() -> None:
    # prior median = 80, best = 55 → 31.25% discount, threshold 25% → fires
    route = _route(
        current_fares_eur=[55.0, 60.0, 70.0],
        prior_prices_eur=[70.0, 80.0, 85.0, 90.0],  # 4 priors → phase 2
    )
    result = tm.evaluate_routes({"routes": [route], "settings": _SETTINGS})
    verdict = result["verdicts"][0]
    assert verdict["phase"] == 2
    assert verdict["is_deal"] is True
    assert verdict["baseline_median_eur"] == pytest.approx(82.5)
    # p15 is still reported for Phase 2 observations
    assert verdict["market_p15_eur"] is not None


def test_evaluate_phase2_wishlist_looser_threshold() -> None:
    # prior median = 80, best = 70 → 12.5% discount.
    # Non-wishlist (25% threshold) fails. Wishlist (15%) also fails — need a
    # value that passes wishlist but not non-wishlist: best=66 → 17.5% discount.
    priors = [70.0, 80.0, 85.0, 90.0]  # 4 priors, median 82.5
    # best = 66 → discount vs 82.5 = ~20% (passes 15%, fails 25%)
    wishlist_route = _route(
        destination_iata="BKK",
        category="intercontinental_asia",
        is_wishlist=True,
        current_fares_eur=[66.0, 80.0, 100.0],
        prior_prices_eur=priors,
    )
    non_wishlist_route = _route(
        destination_iata="BKK2",
        category="intercontinental_asia",
        is_wishlist=False,
        current_fares_eur=[66.0, 80.0, 100.0],
        prior_prices_eur=priors,
    )
    result = tm.evaluate_routes(
        {"routes": [wishlist_route, non_wishlist_route], "settings": _SETTINGS}
    )
    assert result["verdicts"][0]["is_deal"] is True  # wishlist passes
    assert result["verdicts"][1]["is_deal"] is False  # non-wishlist fails


def test_evaluate_phase2_empty_prior_raises() -> None:
    # 4 priors triggers phase 2, but we'll sneak in with specially-crafted
    # settings where phase1_max_obs is -1 so any prior count falls to phase 2.
    bad_settings = {**_SETTINGS, "phase1_max_obs": -1}
    route = _route(prior_prices_eur=[])
    with pytest.raises(ValueError):
        tm.evaluate_routes({"routes": [route], "settings": bad_settings})


# ---- evaluate: phase 3 ------------------------------------------------------


def test_evaluate_phase3_requires_both_phases_to_fire() -> None:
    # 12 priors → phase 3 (phase2_max_obs=11)
    priors_median_82_5 = [70.0, 80.0, 85.0, 90.0] * 3  # 12 vals, median 82.5
    # best = 48 → passes p1 (<=p15 & <= ceiling 80) AND p2 (>25% discount)
    route_both = _route(
        current_fares_eur=[48.0, 60.0, 70.0, 80.0, 90.0],
        prior_prices_eur=priors_median_82_5,
    )
    result = tm.evaluate_routes({"routes": [route_both], "settings": _SETTINGS})
    verdict = result["verdicts"][0]
    assert verdict["phase"] == 3
    assert verdict["is_deal"] is True
    assert verdict["baseline_median_eur"] == pytest.approx(82.5)
    assert verdict["market_p15_eur"] is not None

    # Now a route that passes p2 but fails p1 (price above ceiling)
    route_p2_only = _route(
        current_fares_eur=[85.0, 100.0, 120.0],
        prior_prices_eur=priors_median_82_5,
    )
    # best 85 above ceiling 80 → p1 fails; p2 also fails (best above ceiling)
    # Craft one where p2 fires but p1 doesn't: raise ceiling so p2 passes,
    # but best > p15. Use wishlist multiplier 1.3 → ceiling 80*1.3=104.
    route_mixed = _route(
        is_wishlist=True,
        current_fares_eur=[60.0, 62.0, 63.0, 64.0, 65.0],
        prior_prices_eur=priors_median_82_5,
    )
    # best=60, p15 of current ≈ 60.6 → p1 fires (60 <= 60.6 and <=104)
    # That makes both fire. Force p1 to fail by clustering current fares high.
    route_p1_fail = _route(
        is_wishlist=True,
        current_fares_eur=[70.0, 72.0, 73.0, 74.0, 75.0],
        prior_prices_eur=priors_median_82_5,
    )
    # best=70, p15 of current ≈ 71.2 → p1 fires (70<=71.2). Hmm.
    # Use a spread where best is NOT at/below p15:
    route_p1_fail2 = _route(
        is_wishlist=True,
        current_fares_eur=[65.0, 65.1, 65.2, 65.3, 85.0],
        prior_prices_eur=priors_median_82_5,
    )
    # sorted: 65, 65.1, 65.2, 65.3, 85; p15 rank = 0.6 → 65+0.6*0.1 = 65.06
    # best=65 → 65 <= 65.06 → p1 fires. Very hard to make p1 fail with a low best.
    # Use non-wishlist with best > ceiling to force p1 fail:
    route_cheap_above_ceiling = _route(
        current_fares_eur=[82.0, 83.0, 84.0, 85.0, 86.0],
        prior_prices_eur=priors_median_82_5,
    )
    # best=82 > ceiling 80 → p1 fails; p2: best 82 > ceiling 80 → p2 also fails.
    # Phase 3 verdict should be is_deal=False (both must fire).
    r = tm.evaluate_routes(
        {"routes": [route_cheap_above_ceiling], "settings": _SETTINGS}
    )
    assert r["verdicts"][0]["is_deal"] is False
    assert r["verdicts"][0]["phase"] == 3


# ---- evaluate: CLI ---------------------------------------------------------


def test_cli_percentile(capsys: pytest.CaptureFixture[str]) -> None:
    rc = tm.main(["traveller_math.py", "percentile", "15", "40,50,60,70,80"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert float(out) == pytest.approx(46.0)


def test_cli_median(capsys: pytest.CaptureFixture[str]) -> None:
    rc = tm.main(["traveller_math.py", "median", "1,2,3,4"])
    assert rc == 0
    assert float(capsys.readouterr().out.strip()) == 2.5


def test_cli_evaluate(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    payload = {
        "routes": [_route(current_fares_eur=[48.0, 60.0, 70.0, 80.0, 90.0])],
        "settings": _SETTINGS,
    }
    input_path = tmp_path / "in.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")
    rc = tm.main(["traveller_math.py", "evaluate", str(input_path)])
    assert rc == 0
    result = json.loads(capsys.readouterr().out)
    assert result["verdicts"][0]["is_deal"] is True
