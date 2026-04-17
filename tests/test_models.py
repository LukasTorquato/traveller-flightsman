import pytest
from pydantic import ValidationError

from traveller.models import Settings


def _valid_settings_dict():
    return {
        "origin_iata": "DUB",
        "currency": "EUR",
        "email_recipient": "lukasmtorquato@gmail.com",
        "search_windows": {
            "europe_short_haul": {"days_ahead_max": 90, "nights_min": 2, "nights_max": 7},
            "europe_long_haul": {"days_ahead_max": 120, "nights_min": 2, "nights_max": 7},
            "intercontinental": {"days_ahead_max": 240, "nights_min": 10, "nights_max": 21},
        },
        "category_ceilings_eur": {
            "europe_short_haul": 80,
            "europe_long_haul": 130,
            "intercontinental_asia": 550,
            "intercontinental_south_america": 600,
        },
        "wishlist_ceiling_multiplier": 1.3,
        "baseline": {
            "cold_start_p_percentile": 15,
            "baseline_window_observations": 12,
            "phase2_min_discount_pct_non_wishlist": 25,
            "phase2_min_discount_pct_wishlist": 15,
            "phase_thresholds": {"phase1_max_obs": 3, "phase2_max_obs": 11},
        },
        "kiwi_api_key_env_var": "KIWI_TEQUILA_API_KEY",
        "kiwi_rate_limit_delay_ms": 200,
    }


def test_settings_parses_valid_dict():
    s = Settings.model_validate(_valid_settings_dict())
    assert s.origin_iata == "DUB"
    assert s.currency == "EUR"
    assert s.search_windows["europe_short_haul"].nights_max == 7
    assert s.baseline.phase_thresholds.phase1_max_obs == 3


def test_settings_rejects_missing_required_field():
    d = _valid_settings_dict()
    del d["origin_iata"]
    with pytest.raises(ValidationError):
        Settings.model_validate(d)


def test_settings_rejects_nights_min_gt_max():
    d = _valid_settings_dict()
    d["search_windows"]["europe_short_haul"]["nights_min"] = 10
    d["search_windows"]["europe_short_haul"]["nights_max"] = 5
    with pytest.raises(ValidationError):
        Settings.model_validate(d)


def test_phase_thresholds_rejects_phase1_ge_phase2():
    from traveller.models import PhaseThresholds

    with pytest.raises(ValidationError):
        PhaseThresholds(phase1_max_obs=11, phase2_max_obs=3)
    with pytest.raises(ValidationError):
        PhaseThresholds(phase1_max_obs=5, phase2_max_obs=5)


def test_settings_rejects_invalid_email():
    d = _valid_settings_dict()
    d["email_recipient"] = "not-an-email"
    with pytest.raises(ValidationError):
        Settings.model_validate(d)


def test_settings_rejects_delay_ms_too_high():
    d = _valid_settings_dict()
    d["kiwi_rate_limit_delay_ms"] = 120_000
    with pytest.raises(ValidationError):
        Settings.model_validate(d)


def test_settings_rejects_percentile_out_of_range():
    d = _valid_settings_dict()
    d["baseline"]["cold_start_p_percentile"] = 0.5
    with pytest.raises(ValidationError):
        Settings.model_validate(d)


def test_observation_is_frozen():
    from datetime import date

    from traveller.models import Observation

    obs = Observation(
        run_date=date(2026, 4, 21),
        origin="DUB",
        destination_iata="BCN",
        destination_city="Barcelona",
        departure_date=date(2026, 6, 12),
        return_date=date(2026, 6, 15),
        nights=3,
        price_eur=48.5,
        airline="FR",
        stops=0,
        source="kiwi",
        is_wishlist=False,
        category="europe_short_haul",
        market_p15_eur=62.0,
        was_flagged_as_deal=True,
        flag_reason="x",
        baseline_median_eur=None,
        phase=1,
    )
    with pytest.raises(ValidationError):
        obs.price_eur = 99.9
