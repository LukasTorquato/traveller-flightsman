from __future__ import annotations

import os
import time
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from traveller.config import load_config
from traveller.emailer import write_email_envelope
from traveller.evaluator.dispatcher import evaluate_route
from traveller.health import write_health_envelope
from traveller.models import (
    Destination,
    Observation,
    RunMetadata,
)
from traveller.persistence.baseline import load_route_history
from traveller.persistence.jsonl_store import append_observation, append_run_metadata
from traveller.reporter import RouteOutcome, RunReport, render_report
from traveller.rotation import (
    load_rotation_state,
    next_intercontinental_selection,
    save_rotation_state,
)
from traveller.sources.kiwi import KiwiClient, KiwiError
from traveller.sources.ryanair import RyanairClient, RyanairUnavailable

if TYPE_CHECKING:
    from datetime import date
    from pathlib import Path

    from traveller.config import ConfigBundle
    from traveller.models import Category, Fare


def _scan_route(
    *,
    destination: Destination,
    category: Category,
    is_wishlist: bool,
    bundle: ConfigBundle,
    kiwi: KiwiClient,
    ryanair: RyanairClient,
    today: date,
    history_path: Path,
) -> tuple[RouteOutcome, int, list[str]]:
    """Returns (outcome, api_calls_made, errors_for_this_route)."""
    errors: list[str] = []
    api_calls = 0
    win_key = (
        "europe_short_haul"
        if category == "europe_short_haul"
        else "europe_long_haul"
        if category == "europe_long_haul"
        else "intercontinental"
    )
    win = bundle.settings.search_windows[win_key]
    date_from = today + timedelta(days=1)
    date_to = today + timedelta(days=win.days_ahead_max)

    fares: list[Fare] = []
    try:
        fares.extend(
            kiwi.search(
                origin=bundle.settings.origin_iata,
                destination=destination.iata,
                date_from=date_from,
                date_to=date_to,
                nights_min=win.nights_min,
                nights_max=win.nights_max,
                limit=50,
                currency=bundle.settings.currency,
            )
        )
        api_calls += 1
    except KiwiError as exc:
        errors.append(f"{destination.iata}: kiwi: {exc}")
        return (
            RouteOutcome(
                origin=bundle.settings.origin_iata,
                destination_iata=destination.iata,
                destination_city=destination.city,
                category=category,
                is_wishlist=is_wishlist,
                best_fare=None,
                flag=None,
                skipped=True,
                error=str(exc),
            ),
            api_calls,
            errors,
        )
    try:
        fares.extend(
            ryanair.search(
                origin=bundle.settings.origin_iata,
                destination=destination.iata,
                date_from=date_from,
                date_to=date_to,
                nights_min=win.nights_min,
                nights_max=win.nights_max,
                currency=bundle.settings.currency,
            )
        )
        api_calls += 1
    except RyanairUnavailable as exc:
        errors.append(f"{destination.iata}: ryanair unavailable: {exc}")

    history = load_route_history(
        history_path,
        origin=bundle.settings.origin_iata,
        destination_iata=destination.iata,
        window=bundle.settings.baseline.baseline_window_observations,
    )
    flag = evaluate_route(
        fares=fares,
        observation_count=history.observation_count,
        prior_prices=history.prices,
        category=category,
        is_wishlist=is_wishlist,
        baseline=bundle.settings.baseline,
        ceilings=bundle.settings.category_ceilings_eur,
        wishlist_multiplier=bundle.settings.wishlist_ceiling_multiplier,
    )
    best_fare = min(fares, key=lambda f: f.price_eur) if fares else None
    return (
        RouteOutcome(
            origin=bundle.settings.origin_iata,
            destination_iata=destination.iata,
            destination_city=destination.city,
            category=category,
            is_wishlist=is_wishlist,
            best_fare=best_fare,
            flag=flag,
            skipped=False,
            error=None,
        ),
        api_calls,
        errors,
    )


def run_scan(
    *,
    config_dir: Path,
    history_path: Path,
    reports_dir: Path,
    state_path: Path,
    email_output_path: Path,
    today: date | None = None,
) -> tuple[RunReport, Path]:
    from datetime import date as _date

    t0 = time.monotonic()
    today = today or _date.today()
    bundle = load_config(config_dir)
    api_key = os.environ.get(bundle.settings.kiwi_api_key_env_var, "")
    kiwi = KiwiClient(api_key=api_key, backoff_seconds=5.0, max_retries=2)
    ryanair = RyanairClient()

    # Build the per-run route list
    pool = bundle.destinations
    rotation = load_rotation_state(state_path)
    intercont, new_rotation = next_intercontinental_selection(
        state=rotation,
        asia=pool.intercontinental_asia,
        south_america=pool.intercontinental_south_america,
    )

    to_scan: list[tuple[Destination, Category, bool]] = []
    # Wishlist first so that it takes precedence on dedup
    for w in bundle.wishlist.wishlist:
        to_scan.append((Destination(iata=w.iata, city=w.city), w.category, True))
    # Europe short-haul: all
    for d in pool.europe_short_haul:
        to_scan.append((d, "europe_short_haul", False))
    # Europe long-haul: all
    for d in pool.europe_long_haul:
        to_scan.append((d, "europe_long_haul", False))
    # Intercontinental: rotated
    for d in intercont.asia:
        to_scan.append((d, "intercontinental_asia", False))
    for d in intercont.south_america:
        to_scan.append((d, "intercontinental_south_america", False))

    # Dedup by IATA: wishlist entries (added first) take precedence over
    # duplicate destinations already in the main pool.
    seen: set[str] = set()
    deduped: list[tuple[Destination, Category, bool]] = []
    for tup in to_scan:
        if tup[0].iata in seen:
            continue
        seen.add(tup[0].iata)
        deduped.append(tup)

    outcomes: list[RouteOutcome] = []
    total_calls = 0
    errors: list[str] = []
    for dest, cat, is_w in deduped:
        outcome, calls, errs = _scan_route(
            destination=dest,
            category=cat,
            is_wishlist=is_w,
            bundle=bundle,
            kiwi=kiwi,
            ryanair=ryanair,
            today=today,
            history_path=history_path,
        )
        outcomes.append(outcome)
        total_calls += calls
        errors.extend(errs)

    # Persist observations (only for routes that actually returned a fare and were evaluated)
    for o in outcomes:
        if o.skipped or o.best_fare is None or o.flag is None:
            continue
        f = o.best_fare
        obs = Observation(
            run_date=today,
            origin=o.origin,
            destination_iata=o.destination_iata,
            destination_city=o.destination_city,
            departure_date=f.departure_date,
            return_date=f.return_date,
            nights=f.nights,
            price_eur=f.price_eur,
            airline=f.airline,
            stops=f.stops,
            source=f.source,
            is_wishlist=o.is_wishlist,
            category=o.category,
            market_p15_eur=o.flag.market_p15_eur,
            was_flagged_as_deal=o.flag.is_deal,
            flag_reason=o.flag.reason,
            baseline_median_eur=o.flag.baseline_median_eur,
            phase=o.flag.phase,
        )
        append_observation(obs, history_path)

    runtime = int(time.monotonic() - t0)
    report = RunReport(
        run_date=today,
        origin=bundle.settings.origin_iata,
        currency=bundle.settings.currency,
        runtime_seconds=runtime,
        outcomes=outcomes,
        total_api_calls=total_calls,
    )
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"{today.isoformat()}.md"
    report_path.write_text(render_report(report), encoding="utf-8")

    meta = RunMetadata(
        run_date=today,
        run_started_at=datetime.now(UTC).isoformat(),
        run_ended_at=datetime.now(UTC).isoformat(),
        total_routes_queried=len([o for o in outcomes if not o.skipped]),
        total_api_calls=total_calls,
        deals_flagged=len([o for o in outcomes if o.flag and o.flag.is_deal]),
        errors=errors,
        git_commit_sha=None,
    )
    append_run_metadata(meta, history_path)
    save_rotation_state(new_rotation, state_path)

    # Email envelope — monthly health takes priority on first Tuesdays.
    # If health envelope is written, skip the deal envelope to avoid overwriting it.
    wrote_health = write_health_envelope(
        today=today,
        recipient=bundle.settings.email_recipient,
        observations_path=history_path,
        output_path=email_output_path,
    )
    if not wrote_health:
        write_email_envelope(
            report=report,
            recipient=bundle.settings.email_recipient,
            output_path=email_output_path,
        )
    return report, email_output_path
