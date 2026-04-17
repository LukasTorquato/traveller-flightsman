from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from traveller.reporter import RouteOutcome, RunReport


def _deal_block_html(o: RouteOutcome) -> str:
    assert o.best_fare is not None
    star = " \u2b50 wishlist" if o.is_wishlist else ""
    f = o.best_fare
    stops_label = ", direct" if f.stops == 0 else f", {f.stops} stop(s)"
    reason = o.flag.reason if o.flag else ""
    return (
        f"<p><strong>{o.destination_city} ({o.destination_iata})</strong>{star}<br>"
        f"\u20ac{f.price_eur:.2f} return \u2014 {f.departure_date.isoformat()} \u2192 "
        f"{f.return_date.isoformat()} ({f.nights} nights, {f.airline}{stops_label})<br>"
        f"{reason}<br>"
        f'<a href="{f.booking_url}">Book</a></p>'
    )


def _subject(deals: list[RouteOutcome]) -> str:
    if not deals:
        return ""
    n = len(deals)
    noun = "deal" if n == 1 else "deals"
    head = deals[0]
    assert head.best_fare is not None
    star = " \u2b50" if head.is_wishlist else ""
    parts = [f"{head.destination_city} \u20ac{head.best_fare.price_eur:.0f}{star}"]
    if n >= 2 and deals[1].best_fare is not None:
        s2 = " \u2b50" if deals[1].is_wishlist else ""
        parts.append(f"{deals[1].destination_city} \u20ac{deals[1].best_fare.price_eur:.0f}{s2}")
    return f"\u2708\ufe0f {n} travel {noun} this week \u2014 " + ", ".join(parts)


def write_email_envelope(
    *,
    report: RunReport,
    recipient: str,
    output_path: Path,
) -> None:
    deals = [o for o in report.outcomes if o.flag and o.flag.is_deal and not o.skipped]
    scanned = len([o for o in report.outcomes if not o.skipped])
    skipped = len([o for o in report.outcomes if o.skipped])
    body_lines = [
        "<p>Hi Lukas,</p>",
        f"<p>{len(deals)} great deal(s) detected on your Tuesday scan:</p>",
        *[_deal_block_html(o) for o in deals],
        f"<p>Scanned {scanned} routes, skipped {skipped}.</p>",
    ]
    envelope = {
        "should_send": bool(deals),
        "to": recipient,
        "subject": _subject(deals),
        "body_html": "\n".join(body_lines),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
