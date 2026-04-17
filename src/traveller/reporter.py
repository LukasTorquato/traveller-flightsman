from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date

    from traveller.models import Category, DealFlag, Fare


@dataclass(frozen=True)
class RouteOutcome:
    origin: str
    destination_iata: str
    destination_city: str
    category: Category
    is_wishlist: bool
    best_fare: Fare | None
    flag: DealFlag | None
    skipped: bool
    error: str | None


@dataclass(frozen=True)
class RunReport:
    run_date: date
    origin: str
    currency: str
    runtime_seconds: int
    outcomes: list[RouteOutcome]
    total_api_calls: int


def _format_duration(seconds: int) -> str:
    mins, secs = divmod(seconds, 60)
    return f"{mins}m {secs:02d}s"


def _deal_card(outcome: RouteOutcome) -> str:
    assert outcome.best_fare is not None and outcome.flag is not None
    f = outcome.best_fare
    star = " \u2b50 WISHLIST" if outcome.is_wishlist else ""
    stops_label = "direct" if f.stops == 0 else f"{f.stops} stop(s)"
    lines = [
        (
            f"### \u2708\ufe0f {outcome.destination_city} ({outcome.destination_iata}) "
            f"\u2014 \u20ac{f.price_eur:.2f} return{star}"
        ),
        (
            f"- **Dates:** {f.departure_date.isoformat()} \u2192 "
            f"{f.return_date.isoformat()} ({f.nights} nights)"
        ),
        f"- **Airline:** {f.airline} ({stops_label})",
        f"- **Phase:** {outcome.flag.phase} \u2014 {outcome.flag.reason}",
        f"- **Book:** {f.booking_url}",
        "",
    ]
    return "\n".join(lines)


def render_report(report: RunReport) -> str:
    deals = [o for o in report.outcomes if o.flag and o.flag.is_deal and not o.skipped]
    no_deals = [o for o in report.outcomes if o.flag and not o.flag.is_deal and not o.skipped]
    skipped = [o for o in report.outcomes if o.skipped]

    out: list[str] = []
    out.append(
        f"# Travel Deals Scan \u2014 {report.run_date.isoformat()} "
        f"({report.run_date.strftime('%a')})"
    )
    out.append("")
    out.append(
        f"**Origin:** {report.origin}  **Currency:** {report.currency}  "
        f"**Runtime:** {_format_duration(report.runtime_seconds)}"
    )
    out.append("")
    out.append("## Great deals this week")
    out.append("")
    if deals:
        for d in deals:
            out.append(_deal_card(d))
    else:
        out.append("_No great deals this week._")
        out.append("")

    if no_deals:
        out.append("## Routes scanned (no deal)")
        out.append("")
        out.append("| Route | Best price | Phase | Reason |")
        out.append("|-------|-----------|-------|--------|")
        for o in no_deals:
            best = f"\u20ac{o.best_fare.price_eur:.2f}" if o.best_fare else "n/a"
            phase = o.flag.phase if o.flag else "-"
            reason = o.flag.reason if o.flag else "-"
            out.append(f"| {o.destination_iata} | {best} | {phase} | {reason} |")
        out.append("")

    if skipped:
        out.append("## Routes skipped (errors)")
        out.append("")
        out.append("| Route | Reason |")
        out.append("|-------|--------|")
        for o in skipped:
            out.append(f"| {o.destination_iata} | {o.error or 'unknown'} |")
        out.append("")

    out.append("## Run metadata")
    out.append("")
    out.append(f"- Total routes queried: {len([o for o in report.outcomes if not o.skipped])}")
    out.append(f"- Total API calls: {report.total_api_calls}")
    out.append(f"- Deals flagged: {len(deals)}")
    out.append(f"- Errors: {len(skipped)}")
    return "\n".join(out) + "\n"
