import json
import re
from pathlib import Path

from freezegun import freeze_time
from pytest_httpx import HTTPXMock

from traveller.orchestrator import run_scan


def _kiwi_cheap() -> dict:
    return {
        "data": [
            {
                "price": 40 + i,
                "local_departure": "2026-06-12T09:30:00.000Z",
                "nightsInDest": 3,
                "route": [
                    {"airline": "FR", "return": 0},
                    {
                        "airline": "FR",
                        "return": 1,
                        "local_departure": "2026-06-15T10:00:00.000Z",
                    },
                ],
                "airlines": ["FR"],
                "deep_link": f"https://kiwi.com/deep/{i}",
            }
            for i in range(20)
        ]
    }


@freeze_time("2026-04-21")
def test_orchestrator_happy_path_single_route(
    tmp_path: Path, httpx_mock: HTTPXMock, monkeypatch
) -> None:
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "settings.json").write_text(
        json.dumps(
            {
                "origin_iata": "DUB",
                "currency": "EUR",
                "email_recipient": "l@example.com",
                "search_windows": {
                    "europe_short_haul": {
                        "days_ahead_max": 90,
                        "nights_min": 2,
                        "nights_max": 7,
                    },
                    "europe_long_haul": {
                        "days_ahead_max": 120,
                        "nights_min": 2,
                        "nights_max": 7,
                    },
                    "intercontinental": {
                        "days_ahead_max": 240,
                        "nights_min": 10,
                        "nights_max": 21,
                    },
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
                "kiwi_rate_limit_delay_ms": 0,
            }
        )
    )
    (cfg / "destinations.json").write_text(
        json.dumps(
            {
                "europe_short_haul": [{"iata": "BCN", "city": "Barcelona"}],
                "europe_long_haul": [],
                "intercontinental_asia": [],
                "intercontinental_south_america": [],
            }
        )
    )
    (cfg / "wishlist.json").write_text(json.dumps({"wishlist": []}))

    monkeypatch.setenv("KIWI_TEQUILA_API_KEY", "dummy")
    httpx_mock.add_response(
        url=re.compile(r".*api\.tequila\.kiwi\.com/v2/search.*"),
        json=_kiwi_cheap(),
        status_code=200,
    )
    # Ryanair: 503 so it's logged as unavailable but doesn't fail the run
    httpx_mock.add_response(
        url=re.compile(r".*services-api\.ryanair\.com/farfnd/v4/roundTripFares.*"),
        status_code=503,
        text="down",
    )

    report, envelope_path = run_scan(
        config_dir=cfg,
        history_path=tmp_path / "history" / "observations.jsonl",
        reports_dir=tmp_path / "reports",
        state_path=tmp_path / "state" / "rotation.json",
        email_output_path=tmp_path / "output" / "email.json",
    )
    # One route scanned
    assert len(report.outcomes) == 1
    assert report.outcomes[0].destination_iata == "BCN"
    assert report.outcomes[0].flag is not None
    # JSONL written (1 observation + 1 run_metadata)
    rows = (
        (tmp_path / "history" / "observations.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert len(rows) == 2
    # Report written
    rpt = tmp_path / "reports" / "2026-04-21.md"
    assert rpt.is_file()
    assert "Barcelona" in rpt.read_text(encoding="utf-8")
    # Email envelope written (deal flagged because cheap prices + cold start)
    env = json.loads(envelope_path.read_text(encoding="utf-8"))
    assert env["should_send"] is True
