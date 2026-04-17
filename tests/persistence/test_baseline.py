from datetime import date, timedelta
from pathlib import Path

from tests.persistence.test_jsonl_store import _obs
from traveller.persistence.baseline import load_route_history
from traveller.persistence.jsonl_store import append_observation


def test_route_history_counts_observations(tmp_path: Path):
    f = tmp_path / "observations.jsonl"
    for i in range(5):
        append_observation(
            _obs("BCN", run_date=date(2026, 1, 1) + timedelta(weeks=i), price=50 + i),
            f,
        )
    h = load_route_history(f, origin="DUB", destination_iata="BCN")
    assert h.observation_count == 5
    assert h.median_eur == 52.0  # median of 50..54 = 52


def test_route_history_only_counts_matching_route(tmp_path: Path):
    f = tmp_path / "observations.jsonl"
    append_observation(_obs("BCN", price=50), f)
    append_observation(_obs("CDG", price=80), f)
    h = load_route_history(f, origin="DUB", destination_iata="BCN")
    assert h.observation_count == 1
    assert h.median_eur == 50.0


def test_route_history_respects_window(tmp_path: Path):
    f = tmp_path / "observations.jsonl"
    for i in range(20):
        append_observation(
            _obs("BCN", run_date=date(2026, 1, 1) + timedelta(weeks=i), price=50 + i),
            f,
        )
    h = load_route_history(f, origin="DUB", destination_iata="BCN", window=12)
    assert h.observation_count == 12
    # Last 12 observations: prices 58..69; median = (63+64)/2 = 63.5
    assert h.median_eur == 63.5


def test_route_history_empty_returns_zero(tmp_path: Path):
    f = tmp_path / "observations.jsonl"
    h = load_route_history(f, origin="DUB", destination_iata="BCN")
    assert h.observation_count == 0
    assert h.median_eur is None


def test_route_history_ignores_run_metadata_rows(tmp_path: Path):
    from traveller.models import RunMetadata
    from traveller.persistence.jsonl_store import append_run_metadata

    f = tmp_path / "observations.jsonl"
    append_observation(_obs("BCN", price=50), f)
    append_run_metadata(
        RunMetadata(
            run_date=date(2026, 1, 1),
            run_started_at="x",
            run_ended_at="x",
            total_routes_queried=1,
            total_api_calls=1,
            deals_flagged=0,
            errors=[],
            git_commit_sha=None,
        ),
        f,
    )
    h = load_route_history(f, origin="DUB", destination_iata="BCN")
    assert h.observation_count == 1
