from datetime import date

from traveller.evaluator.phase1 import evaluate_phase1
from traveller.models import Fare


def _fare(price: float) -> Fare:
    return Fare(
        price_eur=price,
        departure_date=date(2026, 6, 12),
        return_date=date(2026, 6, 15),
        nights=3,
        airline="FR",
        stops=0,
        source="kiwi",
        booking_url="https://kiwi.com/x",
    )


def test_phase1_flags_when_best_below_p15_and_ceiling():
    # 20 fares ranging 40..78 — p15 is around the 15th percentile ~ 45
    fares = [_fare(40 + i * 2) for i in range(20)]
    result = evaluate_phase1(
        fares=fares, percentile=15.0, ceiling=80.0,
    )
    assert result.is_deal is True
    assert result.market_p15_eur is not None
    assert result.market_p15_eur < 50
    assert "p15" in result.reason


def test_phase1_no_flag_when_best_above_ceiling():
    # Best fare is 100, ceiling is 80 — no flag even if p15 fires
    fares = [_fare(100 + i) for i in range(20)]
    result = evaluate_phase1(
        fares=fares, percentile=15.0, ceiling=80.0,
    )
    assert result.is_deal is False


def test_phase1_no_flag_when_best_above_p15():
    # Force "best above p15" via override_best_price to simulate scenario.
    fares2 = [_fare(50 + i) for i in range(20)]  # 50..69; p15 ~ 52-53
    result = evaluate_phase1(
        fares=fares2,
        percentile=15.0,
        ceiling=100.0,
        override_best_price=75.0,
    )
    assert result.is_deal is False
    assert "above p15" in result.reason


def test_phase1_empty_fares_returns_no_deal():
    result = evaluate_phase1(fares=[], percentile=15.0, ceiling=80.0)
    assert result.is_deal is False
    assert result.market_p15_eur is None
