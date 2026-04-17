from datetime import date
from pathlib import Path

from traveller.models import Observation, RunMetadata
from traveller.persistence.jsonl_store import append_observation, append_run_metadata, read_all


def _obs(iata="BCN", run_date=date(2026, 4, 21), price=48.5) -> Observation:
    return Observation(
        run_date=run_date,
        origin="DUB",
        destination_iata=iata,
        destination_city="Barcelona",
        departure_date=date(2026, 6, 12),
        return_date=date(2026, 6, 15),
        nights=3,
        price_eur=price,
        airline="Ryanair",
        stops=0,
        source="kiwi",
        is_wishlist=False,
        category="europe_short_haul",
        market_p15_eur=62.0,
        was_flagged_as_deal=True,
        flag_reason="price <= p15",
        baseline_median_eur=None,
        phase=1,
    )


def test_append_and_read_single_observation(tmp_path: Path):
    f = tmp_path / "observations.jsonl"
    append_observation(_obs(), f)
    rows = read_all(f)
    assert len(rows) == 1
    assert rows[0]["destination_iata"] == "BCN"
    assert rows[0]["price_eur"] == 48.5


def test_append_multiple_preserves_order(tmp_path: Path):
    f = tmp_path / "observations.jsonl"
    append_observation(_obs("BCN", price=48.5), f)
    append_observation(_obs("CDG", price=94.0), f)
    rows = read_all(f)
    assert [r["destination_iata"] for r in rows] == ["BCN", "CDG"]


def test_append_run_metadata_adds_sentinel_kind(tmp_path: Path):
    f = tmp_path / "observations.jsonl"
    append_observation(_obs(), f)
    meta = RunMetadata(
        run_date=date(2026, 4, 21),
        run_started_at="2026-04-21T08:00:00+01:00",
        run_ended_at="2026-04-21T08:03:17+01:00",
        total_routes_queried=35,
        total_api_calls=36,
        deals_flagged=1,
        errors=[],
        git_commit_sha=None,
    )
    append_run_metadata(meta, f)
    rows = read_all(f)
    assert len(rows) == 2
    assert "kind" not in rows[0]
    assert rows[1]["kind"] == "run_metadata"
    assert rows[1]["total_routes_queried"] == 35


def test_read_all_missing_file_returns_empty(tmp_path: Path):
    assert read_all(tmp_path / "nope.jsonl") == []
