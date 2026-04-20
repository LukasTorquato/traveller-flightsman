"""traveller_math — validation calculator for the weekly scan routine.

Pure-stdlib helper Claude Code calls ad-hoc to double-check arithmetic during
the weekly scan. Three subcommands:

    python traveller_math.py percentile <pct> <comma-separated-values>
    python traveller_math.py median <comma-separated-values>
    python traveller_math.py evaluate <input-json-path>

`percentile` and `median` print a single number to stdout.

`evaluate` reads a JSON file describing routes + settings and prints a JSON
object with deal verdicts per route. Phase logic mirrors the original design:

    phase 1 (cold start): is_deal if best <= PHASE1_P15_FACTOR *
                          p15(current) AND best <= ceiling
    phase 2 (baseline):   is_deal if discount vs median(prior) >=
                          threshold (25% non-wishlist, 15% wishlist)
                          AND best <= ceiling
    phase 3 (hybrid):     is_deal only if BOTH phase 1 and phase 2 fire.

Two input schemas are accepted per route:

v1 (legacy flight-only):
    {
      "destination_iata": "BCN",
      "is_wishlist": false,
      "category": "europe_short_haul",
      "current_fares_eur": [48.5, 62.0, 75.0],
      "prior_prices_eur": [80.0, 82.0, 85.0]
    }
  settings must include `ceilings_eur` mapping.
  Output verdict keys: best_price_eur, market_p15_eur, baseline_median_eur,
  ceiling_eur.

v2 (combined flight + accommodation totals):
    {
      "destination_iata": "BCN",
      "is_wishlist": false,
      "category": "europe_short_haul",
      "trip_profile": "short_haul_1_night",
      "nights": 1,
      "current_combined_totals_eur": [100.5, 112.0, 125.0],
      "prior_combined_totals_eur": [118.0, 122.0],
      "combined_ceiling_eur": 120.0
    }
  Ceiling is caller-supplied per route — settings do not need `ceilings_eur`.
  Output verdict keys: best_combined_eur, market_p15_combined_eur,
  baseline_median_combined_eur, combined_ceiling_eur.

Output JSON schema: see docstring of `evaluate_routes`.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

# Phase 1 tightness factor: best must be <= PHASE1_P15_FACTOR * p15 to
# count as meaningfully below the market. With small web-search samples (5-10
# observations), p15 lands close to the minimum and a naive best<=p15 bar is
# trivially easy to clear. This factor forces a real discount vs the bottom of
# the listed market.
PHASE1_P15_FACTOR = 0.85


def percentile(values: list[float], pct: float) -> float:
    """Linear-interpolation percentile. Raises ValueError on empty input."""
    if not values:
        raise ValueError("percentile of empty sequence")
    if not 0 <= pct <= 100:
        raise ValueError(f"percentile must be in [0, 100], got {pct}")
    sorted_vals = sorted(values)
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    rank = (pct / 100.0) * (len(sorted_vals) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = rank - lo
    return sorted_vals[lo] + frac * (sorted_vals[hi] - sorted_vals[lo])


def median(values: list[float]) -> float:
    """Median using stdlib statistics. Raises StatisticsError on empty input."""
    return statistics.median(values)


def _select_phase(prior_count: int, phase1_max: int, phase2_max: int) -> int:
    if prior_count <= phase1_max:
        return 1
    if prior_count <= phase2_max:
        return 2
    return 3


def _resolve_schema(route: dict) -> dict:
    """Detect input shape and resolve input/output field names.

    v2 path: route contains `current_combined_totals_eur` — use combined-total
    naming throughout. v1 path: legacy `current_fares_eur` — preserve original
    flight-only key names.
    """
    if "current_combined_totals_eur" in route:
        return {
            "version": "v2",
            "current_key": "current_combined_totals_eur",
            "prior_key": "prior_combined_totals_eur",
            "out_best": "best_combined_eur",
            "out_p15": "market_p15_combined_eur",
            "out_baseline": "baseline_median_combined_eur",
            "out_ceiling": "combined_ceiling_eur",
        }
    return {
        "version": "v1",
        "current_key": "current_fares_eur",
        "prior_key": "prior_prices_eur",
        "out_best": "best_price_eur",
        "out_p15": "market_p15_eur",
        "out_baseline": "baseline_median_eur",
        "out_ceiling": "ceiling_eur",
    }


def _effective_ceiling(route: dict, settings: dict) -> float:
    # v2 path: caller pre-computes and passes combined_ceiling_eur.
    if "combined_ceiling_eur" in route:
        base = float(route["combined_ceiling_eur"])
    else:
        # v1 legacy path: look up by category in settings.ceilings_eur.
        category = route["category"]
        base = float(settings["ceilings_eur"][category])
    if route.get("is_wishlist"):
        base *= float(settings["wishlist_ceiling_multiplier"])
    return base


def _evaluate_phase1(
    current: list[float],
    best: float,
    ceiling: float,
    pct: float,
) -> tuple[bool, str, float]:
    p = percentile(current, pct)
    threshold = PHASE1_P15_FACTOR * p
    if best > ceiling:
        return False, f"best {best:.2f} above ceiling {ceiling:.2f}", p
    if best > threshold:
        return (
            False,
            (
                f"best {best:.2f} > {PHASE1_P15_FACTOR}×p{int(pct)} "
                f"({threshold:.2f}) — not meaningfully below market"
            ),
            p,
        )
    return (
        True,
        (
            f"best {best:.2f} <= {PHASE1_P15_FACTOR}×p{int(pct)} "
            f"({threshold:.2f}) and <= ceiling {ceiling:.2f}"
        ),
        p,
    )


def _evaluate_phase2(
    prior: list[float],
    best: float,
    ceiling: float,
    is_wishlist: bool,
    threshold_non_wishlist: float,
    threshold_wishlist: float,
) -> tuple[bool, str, float]:
    if not prior:
        raise ValueError("phase 2 requires at least one prior observation")
    baseline = median(prior)
    threshold = threshold_wishlist if is_wishlist else threshold_non_wishlist
    if best > ceiling:
        return False, f"best {best:.2f} above ceiling {ceiling:.2f}", baseline
    if baseline <= 0:
        return False, "baseline median <= 0, cannot compute discount", baseline
    discount_pct = (1.0 - best / baseline) * 100.0
    if discount_pct < threshold:
        return (
            False,
            f"discount {discount_pct:.1f}% below required {threshold:.0f}%",
            baseline,
        )
    return (
        True,
        f"{discount_pct:.1f}% below baseline {baseline:.2f} (>= {threshold:.0f}%)",
        baseline,
    )


def evaluate_route(route: dict, settings: dict) -> dict:
    """Produce a single verdict dict for a route.

    Handles both v1 (flight-only) and v2 (combined-total) input schemas.
    Output field names reflect which input schema was used — see
    `_resolve_schema` for the mapping.
    """
    schema = _resolve_schema(route)
    iata = route["destination_iata"]
    current = [float(x) for x in route.get(schema["current_key"], [])]
    prior = [float(x) for x in route.get(schema["prior_key"], [])]
    ceiling = _effective_ceiling(route, settings)
    phase = _select_phase(
        len(prior),
        int(settings["phase1_max_obs"]),
        int(settings["phase2_max_obs"]),
    )

    if not current:
        return {
            "destination_iata": iata,
            "phase": phase,
            "is_deal": False,
            "reason": "no fares provided",
            schema["out_best"]: None,
            schema["out_p15"]: None,
            schema["out_baseline"]: None,
            schema["out_ceiling"]: ceiling,
        }

    best = min(current)
    pct = float(settings["cold_start_p_percentile"])
    is_wishlist = bool(route.get("is_wishlist", False))

    if phase == 1:
        is_deal, reason, p_val = _evaluate_phase1(current, best, ceiling, pct)
        return {
            "destination_iata": iata,
            "phase": 1,
            "is_deal": is_deal,
            "reason": reason,
            schema["out_best"]: best,
            schema["out_p15"]: p_val,
            schema["out_baseline"]: None,
            schema["out_ceiling"]: ceiling,
        }

    # Phase 2 and 3 both need p1 value for historical continuity
    p_val = percentile(current, pct)

    if phase == 2:
        is_deal, reason, baseline = _evaluate_phase2(
            prior,
            best,
            ceiling,
            is_wishlist,
            float(settings["phase2_min_discount_pct_non_wishlist"]),
            float(settings["phase2_min_discount_pct_wishlist"]),
        )
        return {
            "destination_iata": iata,
            "phase": 2,
            "is_deal": is_deal,
            "reason": reason,
            schema["out_best"]: best,
            schema["out_p15"]: p_val,
            schema["out_baseline"]: baseline,
            schema["out_ceiling"]: ceiling,
        }

    # Phase 3: both phase 1 and phase 2 must agree
    p1_deal, p1_reason, p1_val = _evaluate_phase1(current, best, ceiling, pct)
    p2_deal, p2_reason, baseline = _evaluate_phase2(
        prior,
        best,
        ceiling,
        is_wishlist,
        float(settings["phase2_min_discount_pct_non_wishlist"]),
        float(settings["phase2_min_discount_pct_wishlist"]),
    )
    is_deal = p1_deal and p2_deal
    reason = (
        f"phase1={p1_deal} ({p1_reason}); phase2={p2_deal} ({p2_reason})"
        if is_deal
        else f"phase1={p1_deal} ({p1_reason}); phase2={p2_deal} ({p2_reason}) — both required"
    )
    return {
        "destination_iata": iata,
        "phase": 3,
        "is_deal": is_deal,
        "reason": reason,
        schema["out_best"]: best,
        schema["out_p15"]: p1_val,
        schema["out_baseline"]: baseline,
        schema["out_ceiling"]: ceiling,
    }


def evaluate_routes(payload: dict) -> dict:
    """Evaluate all routes in the input payload.

    Returns {"verdicts": [ {...verdict...}, ... ]}. Each verdict's field names
    reflect the input schema used for that route (v1 or v2) — see
    `_resolve_schema`.
    """
    settings = payload["settings"]
    verdicts = [evaluate_route(r, settings) for r in payload["routes"]]
    return {"verdicts": verdicts}


def _parse_values(arg: str) -> list[float]:
    return [float(x) for x in arg.split(",") if x.strip()]


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(_USAGE, file=sys.stderr)
        return 2
    cmd = argv[1]
    try:
        if cmd == "percentile":
            if len(argv) != 4:
                print(_USAGE, file=sys.stderr)
                return 2
            pct = float(argv[2])
            vals = _parse_values(argv[3])
            print(percentile(vals, pct))
            return 0
        if cmd == "median":
            if len(argv) != 3:
                print(_USAGE, file=sys.stderr)
                return 2
            vals = _parse_values(argv[2])
            print(median(vals))
            return 0
        if cmd == "evaluate":
            if len(argv) != 3:
                print(_USAGE, file=sys.stderr)
                return 2
            payload = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
            result = evaluate_routes(payload)
            print(json.dumps(result, indent=2))
            return 0
        print(_USAGE, file=sys.stderr)
        return 2
    except (ValueError, KeyError, FileNotFoundError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


_USAGE = """usage:
  python traveller_math.py percentile <pct> <comma-separated-values>
  python traveller_math.py median <comma-separated-values>
  python traveller_math.py evaluate <input-json-path>"""


if __name__ == "__main__":
    sys.exit(main(sys.argv))
