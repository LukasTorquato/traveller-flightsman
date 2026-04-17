from __future__ import annotations

from traveller.models import DealFlag


def evaluate_phase3(*, phase1_flag: DealFlag, phase2_flag: DealFlag) -> DealFlag:
    is_deal = phase1_flag.is_deal and phase2_flag.is_deal
    if is_deal:
        reason = f"both signals fire - {phase1_flag.reason}; {phase2_flag.reason}"
    elif not phase1_flag.is_deal and not phase2_flag.is_deal:
        reason = "neither signal fires"
    elif not phase1_flag.is_deal:
        reason = f"phase1 vetoes ({phase1_flag.reason})"
    else:
        reason = f"phase2 vetoes ({phase2_flag.reason})"
    return DealFlag(
        is_deal=is_deal,
        phase=3,
        reason=reason,
        market_p15_eur=phase1_flag.market_p15_eur,
        baseline_median_eur=phase2_flag.baseline_median_eur,
    )
