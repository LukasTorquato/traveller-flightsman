import json
from datetime import date
from pathlib import Path

from traveller.health import (
    is_first_tuesday_of_month,
    summarise_month,
    write_health_envelope,
)


def test_is_first_tuesday_true_for_known_dates():
    assert is_first_tuesday_of_month(date(2026, 5, 5)) is True
    assert is_first_tuesday_of_month(date(2026, 6, 2)) is True


def test_is_first_tuesday_false_for_other_tuesdays():
    assert is_first_tuesday_of_month(date(2026, 5, 12)) is False
    assert is_first_tuesday_of_month(date(2026, 4, 21)) is False


def test_is_first_tuesday_false_for_non_tuesday():
    assert is_first_tuesday_of_month(date(2026, 5, 6)) is False  # Wed


def test_summarise_month_counts_runs_and_deals(tmp_path: Path):
    f = tmp_path / "observations.jsonl"
    rows = [
        {
            "kind": "run_metadata",
            "run_date": "2026-04-07",
            "run_started_at": "",
            "run_ended_at": "",
            "total_routes_queried": 35,
            "total_api_calls": 36,
            "deals_flagged": 2,
            "errors": [],
            "git_commit_sha": None,
        },
        {
            "kind": "run_metadata",
            "run_date": "2026-04-14",
            "run_started_at": "",
            "run_ended_at": "",
            "total_routes_queried": 35,
            "total_api_calls": 36,
            "deals_flagged": 0,
            "errors": ["fco-504"],
            "git_commit_sha": None,
        },
        {
            "kind": "run_metadata",
            "run_date": "2026-05-05",
            "run_started_at": "",
            "run_ended_at": "",
            "total_routes_queried": 35,
            "total_api_calls": 36,
            "deals_flagged": 3,
            "errors": [],
            "git_commit_sha": None,
        },
    ]
    f.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    summary = summarise_month(f, for_month=date(2026, 4, 1))
    assert summary.run_count == 2
    assert summary.deals_flagged == 2
    assert summary.errors == 1


def test_write_health_envelope_on_first_tuesday(tmp_path: Path):
    f = tmp_path / "observations.jsonl"
    out = tmp_path / "email.json"
    f.write_text("", encoding="utf-8")
    wrote = write_health_envelope(
        today=date(2026, 5, 5),
        recipient="l@example.com",
        observations_path=f,
        output_path=out,
    )
    assert wrote is True
    p = json.loads(out.read_text())
    assert p["should_send"] is True
    assert "monthly health" in p["subject"].lower()


def test_write_health_envelope_skips_non_first_tuesday(tmp_path: Path):
    f = tmp_path / "observations.jsonl"
    out = tmp_path / "email.json"
    wrote = write_health_envelope(
        today=date(2026, 5, 12),
        recipient="l@example.com",
        observations_path=f,
        output_path=out,
    )
    assert wrote is False
    assert not out.exists()
