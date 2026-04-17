from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def is_first_tuesday_of_month(d: date) -> bool:
    return d.weekday() == 1 and d.day <= 7


@dataclass(frozen=True)
class MonthSummary:
    run_count: int
    deals_flagged: int
    errors: int


def summarise_month(observations_path: Path, *, for_month: date) -> MonthSummary:
    if not observations_path.is_file():
        return MonthSummary(0, 0, 0)
    run_count = 0
    deals = 0
    errs = 0
    for line in observations_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("kind") != "run_metadata":
            continue
        run_date = date.fromisoformat(row["run_date"])
        if run_date.year == for_month.year and run_date.month == for_month.month:
            run_count += 1
            deals += int(row.get("deals_flagged", 0))
            errs += len(row.get("errors", []))
    return MonthSummary(run_count=run_count, deals_flagged=deals, errors=errs)


def write_health_envelope(
    *,
    today: date,
    recipient: str,
    observations_path: Path,
    output_path: Path,
) -> bool:
    if not is_first_tuesday_of_month(today):
        return False
    if today.month == 1:
        last_month = date(today.year - 1, 12, 1)
    else:
        last_month = date(today.year, today.month - 1, 1)
    summary = summarise_month(observations_path, for_month=last_month)
    month_name = last_month.strftime("%B %Y")
    body = (
        f"<p>Monthly health check for {month_name}.</p>"
        f"<ul>"
        f"<li>Runs: {summary.run_count}</li>"
        f"<li>Deals flagged: {summary.deals_flagged}</li>"
        f"<li>Errors: {summary.errors}</li>"
        f"</ul>"
        f"<p>If you don't get this email on the first Tuesday of next month, "
        f"the routine has likely broken \u2014 check the git repo for the last run date.</p>"
    )
    envelope = {
        "should_send": True,
        "to": recipient,
        "subject": f"\U0001f4ca Travel scan monthly health \u2014 {month_name}",
        "body_html": body,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
    return True
