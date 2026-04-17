from traveller.evaluator.phase2 import evaluate_phase2


def test_phase2_flags_when_price_25pct_below_baseline_non_wishlist():
    result = evaluate_phase2(
        best_price=60.0, baseline_median=100.0, ceiling=120.0,
        is_wishlist=False, min_discount_pct_non_wishlist=25.0,
        min_discount_pct_wishlist=15.0,
    )
    assert result.is_deal is True
    assert "40.0% below" in result.reason


def test_phase2_no_flag_when_discount_under_threshold():
    result = evaluate_phase2(
        best_price=80.0, baseline_median=100.0, ceiling=120.0,
        is_wishlist=False, min_discount_pct_non_wishlist=25.0,
        min_discount_pct_wishlist=15.0,
    )
    assert result.is_deal is False


def test_phase2_wishlist_looser_threshold():
    # 18% discount: below 25% (non-wishlist) but above 15% (wishlist)
    result = evaluate_phase2(
        best_price=82.0, baseline_median=100.0, ceiling=120.0,
        is_wishlist=True, min_discount_pct_non_wishlist=25.0,
        min_discount_pct_wishlist=15.0,
    )
    assert result.is_deal is True


def test_phase2_ceiling_cap():
    # 50% discount but above ceiling → no flag
    result = evaluate_phase2(
        best_price=200.0, baseline_median=400.0, ceiling=180.0,
        is_wishlist=False, min_discount_pct_non_wishlist=25.0,
        min_discount_pct_wishlist=15.0,
    )
    assert result.is_deal is False
    assert "above ceiling" in result.reason
