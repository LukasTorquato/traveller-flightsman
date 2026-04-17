import json
from datetime import date
from pathlib import Path

from tests.test_reporter import _outcome
from traveller.emailer import write_email_envelope
from traveller.reporter import RunReport


def _report(outcomes: list) -> RunReport:
    return RunReport(
        run_date=date(2026, 4, 21),
        origin="DUB",
        currency="EUR",
        runtime_seconds=200,
        outcomes=outcomes,
        total_api_calls=5,
    )


def test_no_deals_writes_should_send_false(tmp_path: Path) -> None:
    out = tmp_path / "email.json"
    write_email_envelope(
        report=_report([_outcome("CDG", deal=False, price=94)]),
        recipient="lukas@example.com",
        output_path=out,
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["should_send"] is False
    assert payload["subject"] == ""


def test_single_deal_formats_subject_and_body(tmp_path: Path) -> None:
    out = tmp_path / "email.json"
    write_email_envelope(
        report=_report([_outcome("BCN", deal=True, price=48.5)]),
        recipient="lukas@example.com",
        output_path=out,
    )
    p = json.loads(out.read_text(encoding="utf-8"))
    assert p["should_send"] is True
    assert "1 travel deal" in p["subject"]
    assert "Barcelona" in p["subject"]
    assert "\u20ac48" in p["subject"]
    assert p["to"] == "lukas@example.com"
    assert "Barcelona" in p["body_html"]
    assert "https://kiwi.com/deep/BCN" in p["body_html"]


def test_multiple_deals_pluralised(tmp_path: Path) -> None:
    out = tmp_path / "email.json"
    o1 = _outcome("BCN", deal=True, price=48.5)
    o2 = _outcome("CDG", deal=True, price=72.0)
    write_email_envelope(
        report=_report([o1, o2]),
        recipient="lukas@example.com",
        output_path=out,
    )
    p = json.loads(out.read_text(encoding="utf-8"))
    assert "2 travel deals" in p["subject"]
