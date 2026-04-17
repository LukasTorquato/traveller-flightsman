from traveller.evaluator.phase3 import evaluate_phase3
from traveller.models import DealFlag


def _flag(is_deal: bool, phase: int, market_p15=None, baseline=None) -> DealFlag:
    return DealFlag(
        is_deal=is_deal, phase=phase, reason="x",
        market_p15_eur=market_p15, baseline_median_eur=baseline,
    )


def test_phase3_flags_only_when_both_agree():
    r = evaluate_phase3(
        phase1_flag=_flag(True, 1, market_p15=60),
        phase2_flag=_flag(True, 2, baseline=80),
    )
    assert r.is_deal is True
    assert r.market_p15_eur == 60
    assert r.baseline_median_eur == 80


def test_phase3_no_flag_when_only_phase1_fires():
    r = evaluate_phase3(
        phase1_flag=_flag(True, 1, market_p15=60),
        phase2_flag=_flag(False, 2, baseline=80),
    )
    assert r.is_deal is False


def test_phase3_no_flag_when_only_phase2_fires():
    r = evaluate_phase3(
        phase1_flag=_flag(False, 1, market_p15=60),
        phase2_flag=_flag(True, 2, baseline=80),
    )
    assert r.is_deal is False
