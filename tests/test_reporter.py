from datetime import date

from traveller.models import DealFlag, Fare, Observation
from traveller.reporter import RouteOutcome, RunReport, render_report


def _obs(
    iata: str = "BCN", price: float = 48.5, flagged: bool = True, phase: int = 1,
) -> Observation:
    return Observation(
        run_date=date(2026, 4, 21), origin="DUB",
        destination_iata=iata, destination_city="Barcelona",
        departure_date=date(2026, 6, 12), return_date=date(2026, 6, 15), nights=3,
        price_eur=price, airline="Ryanair", stops=0, source="kiwi",
        is_wishlist=False, category="europe_short_haul",
        market_p15_eur=62.0, was_flagged_as_deal=flagged,
        flag_reason="r", baseline_median_eur=None, phase=phase,
    )


def _fare(price: float) -> Fare:
    return Fare(
        price_eur=price, departure_date=date(2026, 6, 12),
        return_date=date(2026, 6, 15), nights=3,
        airline="FR", stops=0, source="kiwi",
        booking_url="https://kiwi.com/deep/BCN",
    )


def _outcome(
    iata: str = "BCN",
    deal: bool = True,
    phase: int = 1,
    price: float = 48.5,
    skipped: bool = False,
    err: str | None = None,
) -> RouteOutcome:
    flag = DealFlag(
        is_deal=deal, phase=phase, reason="r",
        market_p15_eur=62.0 if phase in (1, 3) else None,
        baseline_median_eur=None,
    )
    return RouteOutcome(
        origin="DUB", destination_iata=iata, destination_city="Barcelona",
        category="europe_short_haul", is_wishlist=False,
        best_fare=_fare(price) if not skipped else None,
        flag=flag if not skipped else None,
        skipped=skipped, error=err,
    )


def test_renders_header_and_no_deals() -> None:
    report = RunReport(
        run_date=date(2026, 4, 21), origin="DUB", currency="EUR",
        runtime_seconds=222,
        outcomes=[_outcome("CDG", deal=False, price=94)],
        total_api_calls=1,
    )
    md = render_report(report)
    assert "# Travel Deals Scan \u2014 2026-04-21" in md
    assert "CDG" in md
    assert "Great deals this week" in md
    assert "No great deals" in md


def test_renders_deals_section_when_flagged() -> None:
    report = RunReport(
        run_date=date(2026, 4, 21), origin="DUB", currency="EUR",
        runtime_seconds=222,
        outcomes=[_outcome("BCN", deal=True, price=48.5)],
        total_api_calls=1,
    )
    md = render_report(report)
    assert "Barcelona" in md
    assert "\u20ac48.50" in md
    assert "https://kiwi.com/deep/BCN" in md
    assert "No great deals" not in md


def test_renders_skipped_routes() -> None:
    report = RunReport(
        run_date=date(2026, 4, 21), origin="DUB", currency="EUR",
        runtime_seconds=222,
        outcomes=[_outcome("FCO", skipped=True, err="Kiwi 504")],
        total_api_calls=0,
    )
    md = render_report(report)
    assert "Routes skipped" in md
    assert "FCO" in md
    assert "Kiwi 504" in md
