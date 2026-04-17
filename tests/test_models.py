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
