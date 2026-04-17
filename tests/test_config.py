import json
from pathlib import Path

import pytest

from traveller.config import ConfigBundle, load_config


def _write(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj), encoding="utf-8")


def _settings() -> dict:
    return {
        "origin_iata": "DUB", "currency": "EUR",
        "email_recipient": "a@b.com",
        "search_windows": {
            "europe_short_haul": {"days_ahead_max": 90, "nights_min": 2, "nights_max": 7},
            "europe_long_haul": {"days_ahead_max": 120, "nights_min": 2, "nights_max": 7},
            "intercontinental": {"days_ahead_max": 240, "nights_min": 10, "nights_max": 21},
        },
        "category_ceilings_eur": {
            "europe_short_haul": 80, "europe_long_haul": 130,
            "intercontinental_asia": 550, "intercontinental_south_america": 600,
        },
        "wishlist_ceiling_multiplier": 1.3,
        "baseline": {
            "cold_start_p_percentile": 15, "baseline_window_observations": 12,
            "phase2_min_discount_pct_non_wishlist": 25,
            "phase2_min_discount_pct_wishlist": 15,
            "phase_thresholds": {"phase1_max_obs": 3, "phase2_max_obs": 11},
        },
        "kiwi_api_key_env_var": "KIWI_TEQUILA_API_KEY",
        "kiwi_rate_limit_delay_ms": 200,
    }


def _destinations() -> dict:
    return {
        "europe_short_haul": [{"iata": "BCN", "city": "Barcelona"}],
        "europe_long_haul": [{"iata": "ATH", "city": "Athens"}],
        "intercontinental_asia": [{"iata": "BKK", "city": "Bangkok"}],
        "intercontinental_south_america": [{"iata": "GRU", "city": "Sao Paulo"}],
    }


def _wishlist() -> dict:
    return {"wishlist": [
        {"iata": "HND", "city": "Tokyo",
         "category": "intercontinental_asia", "note": "bucket list"}
    ]}


def test_load_config_full_bundle(tmp_path: Path):
    cfg = tmp_path / "config"
    cfg.mkdir()
    _write(cfg / "settings.json", _settings())
    _write(cfg / "destinations.json", _destinations())
    _write(cfg / "wishlist.json", _wishlist())

    bundle = load_config(cfg)
    assert isinstance(bundle, ConfigBundle)
    assert bundle.settings.origin_iata == "DUB"
    assert bundle.destinations.europe_short_haul[0].iata == "BCN"
    assert bundle.wishlist.wishlist[0].city == "Tokyo"


def test_load_config_missing_file(tmp_path: Path):
    cfg = tmp_path / "config"
    cfg.mkdir()
    _write(cfg / "settings.json", _settings())
    with pytest.raises(FileNotFoundError):
        load_config(cfg)
