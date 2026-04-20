# Hotels + Packages — Design Extension to Traveller v1

**Status:** Proposed — awaiting user approval
**Date:** 2026-04-20
**Extends:** 2026-04-16 traveller-design.md (historical; Kiwi architecture superseded)
**Relates to:** `prompts/weekly-scan.md`, `traveller_math.py`, `config/settings.json`, `history/observations.jsonl`

## 1. Problem / motivation

User feedback: a cheap flight doesn't matter if the destination's hotels are expensive. Real signal is trip-level value (flight + accommodation). UK/IE bundled travel sites often beat DIY — worth comparing explicitly. Also: short-haul day trips and overnighters have a distinct price profile worth handling separately.

## 2. Goals

- Evaluate trip-level combined cost (flight + hotel), not flight-only
- Compare DIY total vs cheapest bundled package per route
- Support short-haul 0-2 night trip profiles
- Keep existing phase/baseline logic; generalize the unit of comparison
- Maintain auditable JSONL history

## 3. Non-goals (unchanged)

- No booking actions
- No car rental, activities, lounges, insurance, or travel cards
- Not supporting multi-city trips
- Not evaluating trains / Eurostar alternatives
- Not accounting for airport transfer costs

## 4. Trip-length profiles (new concept)

Introduce `trip_profile` per category. Config:

```json
{
  "trip_profiles": {
    "europe_short_haul": {
      "preferred_nights_range": [1, 2],
      "max_nights": 3,
      "allow_same_day_if_flight_under_eur": 40
    },
    "europe_long_haul": {
      "preferred_nights_range": [2, 7],
      "max_nights": 7,
      "allow_same_day_if_flight_under_eur": 0
    },
    "intercontinental_asia": {
      "preferred_nights_range": [10, 21],
      "max_nights": 21,
      "allow_same_day_if_flight_under_eur": 0
    },
    "intercontinental_south_america": {
      "preferred_nights_range": [10, 21],
      "max_nights": 21,
      "allow_same_day_if_flight_under_eur": 0
    }
  }
}
```

Also add `departure_day_preference`: `["mon", "tue", "fri", "sat", "sun"]` at settings root — passed to the prompt to bias flight searches away from Wed/Thu starts.

## 5. Ceiling model (new)

Replace the old flat per-category ceiling with a **flight-ceiling + hotel-per-night** pair. The combined ceiling scales linearly with nights.

```json
{
  "category_cost_caps_eur": {
    "europe_short_haul":        { "flight": 45,  "hotel_per_night": 75 },
    "europe_long_haul":         { "flight": 90,  "hotel_per_night": 100 },
    "intercontinental_asia":    { "flight": 500, "hotel_per_night": 80 },
    "intercontinental_south_america": { "flight": 550, "hotel_per_night": 70 }
  }
}
```

Combined ceiling computation: `combined_ceiling = flight_cap + nights × hotel_per_night_cap`. For 0-night same-day trips: `combined_ceiling = flight_cap` only. Wishlist multiplier still applies to the combined ceiling (× 1.3).

## 6. Hotel sampling strategy

For each (destination, date-range) pair:

1. Claude fetches Booking.com search results for dates, filtering: **rating ≥ 7.5**, **review count ≥ 100**.
2. Of qualifying results, Claude takes the **cheapest 10** by per-night price, then computes the **median of the cheapest 3** → representative `hotel_price_per_night_eur`.
3. Store: `hotel_sample_size` (how many qualified), `hotel_rating_min` (lowest rating of the top 3), `hotel_example_name`, `hotel_example_booking_url` (the single cheapest for one-click book).

If < 3 hotels qualify: mark the route as "hotel data insufficient" and exclude from evaluator; still report in the observation row with nulls.

Skip hotel fetch entirely for 0-night (same-day) trips.

## 7. Package sampling strategy

For each (destination, date-range) pair, Claude queries **all 10 bundled sites**:

1. loveholidays
2. Jet2 Holidays
3. TUI
4. easyJet Holidays
5. On the Beach
6. Expedia
7. Booking.com Packages
8. Kayak Packages
9. Trivago Packages
10. Holiday Pirates

For each site:

- Search "DUB → destination, dates X → Y, 2 adults"
- Apply same hotel-quality floor where site exposes it (rating filter); otherwise accept site's default
- Record cheapest total
- If site doesn't serve this route, log and skip (most sites skip intercontinental to obscure destinations)

Pick `package_cheapest_eur = min(site_price for site in 10)`, record `package_cheapest_site`.

Skip package lookup for 0-night trips (packages generally require ≥ 2 nights).

## 8. Date coupling (answer C)

For each route:

1. Claude gathers 10-20 candidate flight options across the window (varied dates within the profile).
2. For each flight candidate: fetch hotel price for that specific (depart, return) date pair.
3. Compute `diy_total = flight_price + nights × hotel_price_per_night` for each candidate.
4. Separately fetch each of the 10 package sites for several date options; record cheapest.
5. For each candidate date pair where both DIY and package data are available, compare.
6. `best_total_eur = min(all diy_total, all package_totals)`. `best_source ∈ { "diy", "package_<site>" }`.

Practical note: this is expensive. Claude should batch sensibly — fetch flights once, fetch hotels only for the 5 cheapest flight date pairs, fetch packages for 3-4 representative date windows. Prompt should encourage pragmatism.

## 9. Observation schema v2

Add `"schema": "v2"` field to distinguish from v1 rows. Full v2 row:

```json
{
  "schema": "v2",
  "run_date": "2026-04-27",
  "origin": "DUB",
  "destination_iata": "BCN",
  "destination_city": "Barcelona",
  "category": "europe_short_haul",
  "is_wishlist": false,
  "trip_profile": "short_haul_1_night",
  "nights": 1,
  "departure_date": "2026-06-12",
  "return_date": "2026-06-13",

  "flight_price_eur": 38.0,
  "flight_airline": "Ryanair",
  "flight_stops": 0,
  "flight_booking_url": "...",

  "hotel_price_per_night_eur": 62.5,
  "hotel_sample_size": 8,
  "hotel_rating_min": 7.8,
  "hotel_example_name": "Some Hotel",
  "hotel_example_booking_url": "...",

  "diy_total_eur": 100.5,
  "package_cheapest_eur": 115.0,
  "package_cheapest_site": "loveholidays",
  "package_cheapest_url": "...",

  "best_total_eur": 100.5,
  "best_source": "diy",

  "combined_ceiling_eur": 120.0,
  "market_p15_combined_eur": 118.0,
  "baseline_median_combined_eur": null,

  "was_flagged_as_deal": true,
  "flag_reason": "best_total 100.50 ≤ 0.85×p15 (100.30), DIY beats package by €14.50",
  "phase": 1
}
```

Null fields allowed when:

- `hotel_*` — for 0-night trips
- `package_*` — for 0-night trips or routes without package coverage
- `baseline_median_combined_eur` — Phase 1 routes

## 10. Backward compatibility with v1 rows

Existing `history/observations.jsonl` has v1 rows (flight-only `price_eur`). Strategy:

- Mark untagged rows as v1 implicitly (no `schema` field).
- **Phase 2 baselines** use `best_total_eur` from v2 rows only. v1 rows are ignored for combined-total baselines. This means Phase 2 for combined totals starts cold at v2 rollout and takes ~4 weeks of v2 runs to kick in per route.
- Reports still show v1 historical flight-only data where useful ("6 weeks ago: €48 flight; today: €100 combined — can't compare directly").

## 11. Evaluator (traveller_math.py) changes

### Input schema extension

```json
{
  "routes": [
    {
      "destination_iata": "BCN",
      "is_wishlist": false,
      "category": "europe_short_haul",
      "trip_profile": "short_haul_1_night",
      "nights": 1,
      "current_combined_totals_eur": [100.5, 112.0, 125.0, ...],
      "prior_combined_totals_eur": [118.0, 122.0, ...],
      "combined_ceiling_eur": 120.0
    }
  ],
  "settings": {
    "cold_start_p_percentile": 15,
    "phase1_max_obs": 3,
    "phase2_max_obs": 11,
    "phase2_min_discount_pct_non_wishlist": 25,
    "phase2_min_discount_pct_wishlist": 15,
    "wishlist_ceiling_multiplier": 1.3,
    "phase1_p15_factor": 0.85
  }
}
```

The caller (Claude, following the prompt) pre-computes `combined_ceiling_eur` and hands it in. Math script stays pure (no config-file knowledge). Phase 1/2/3 math is unchanged — it just operates on combined totals now.

### Output schema extension

```json
{
  "verdicts": [
    {
      "destination_iata": "BCN",
      "phase": 1,
      "is_deal": true,
      "reason": "best_combined 100.50 ≤ 0.85×p15 (100.30) and ≤ ceiling 120.00",
      "best_combined_eur": 100.5,
      "market_p15_combined_eur": 118.0,
      "baseline_median_combined_eur": null,
      "combined_ceiling_eur": 120.0
    }
  ]
}
```

### Backward compatibility for the script

Keep the old flight-only `current_fares_eur` / `prior_prices_eur` input keys as aliases — the script accepts either `current_combined_totals_eur` or legacy `current_fares_eur` (treating them as flight-only totals). This means we don't break any existing code paths; v1 prompt flows still work.

## 12. Prompt (prompts/weekly-scan.md) changes

Steps that need rewriting:

- **Step 3 (pick routes):** Add trip-profile selection per category. For short-haul, Claude chooses preferred_nights_range by default (1-2 nights). Decides whether to ALSO include a same-day (0-night) variant: Claude does a quick flight-only check first; if the cheapest round-trip fare for the day is ≤ €40, add a 0-night variant. Otherwise skip.
- **Step 4 (fetch fares):** Becomes a three-fetch workflow per route: (a) flight candidates, (b) hotel candidates for each, (c) package totals from all 10 sites. Prompt includes explicit pragmatism hints — "don't fetch hotels for all 20 flight candidates; pick the cheapest 5".
- **Step 5 (build evaluate input):** Build `current_combined_totals_eur` by pairing dates.
- **Step 6 (call traveller_math evaluate):** Same interface, pass combined totals.
- **Step 7 (sanity check):** Claude may verify percentile / median of combined totals.
- **Step 8 (append observations):** Use v2 schema. Include ALL the new fields.
- **Step 9 (report):** Add a "DIY vs Package" column. Break down reasoning: flight cost, hotel cost, package alternative, winner.
- **Step 11 (deal reasoning ladder):** Extend with new reason types:
  - "Package beats DIY by ≥ €X" — explicit package-win reason
  - "Combined cost is all-time low for this route" — combined-total history check
  - "Flight is same-day-round-trip cheap" — specific to 0-night short-haul
- **Step 12 (email):** Email body block template gains `Flight: €X / Hotel: €Y / Total: €Z (DIY)` or `Package via loveholidays: €Z`.

## 13. Config changes

`config/settings.json` migrates:

- `category_ceilings_eur` (flat) → `category_cost_caps_eur` (nested with flight + hotel_per_night)
- Add `trip_profiles`
- Add `departure_day_preference` (list of allowed weekday strings)
- Add `hotel_quality_floor` (`min_rating`, `min_review_count`)
- Add `hotel_sampling` (`candidates_to_fetch`, `median_of_cheapest_n`)
- Add `bundled_sites` (list of 10 site names)

Example settings.json diff (conceptual):

```json
{
  "category_cost_caps_eur": { ... },
  "wishlist_ceiling_multiplier": 1.3,
  "trip_profiles": { ... },
  "departure_day_preference": ["mon", "tue", "fri", "sat", "sun"],
  "hotel_quality_floor": { "min_rating": 7.5, "min_review_count": 100 },
  "hotel_sampling": { "candidates_to_fetch": 10, "median_of_cheapest_n": 3 },
  "bundled_sites": [
    "loveholidays", "Jet2 Holidays", "TUI", "easyJet Holidays", "On the Beach",
    "Expedia", "Booking.com Packages", "Kayak Packages", "Trivago Packages", "Holiday Pirates"
  ],
  "baseline": { ... unchanged ... },
  ...
}
```

`config/destinations.json` unchanged.
`config/wishlist.json` unchanged.

## 14. Risks & open considerations

- **Scraping cost** — 10 package sites × ~30 routes × several date options = a lot. Claude must be pragmatic: skip sites that don't cover a route fast, cap total time. Prompt should enforce a 15-minute soft budget per run.
- **Package site rate limiting / CAPTCHAs** — some sites aggressively block scraping. Claude may need to treat unreachable sites as "not offered" and move on. No retries.
- **Hotel "quality" is subjective** — 7.5+ on Booking.com is a good floor but misses brand-new hotels with few reviews. Accepted trade-off.
- **Package price ambiguity** — some sites price per-person, some per-room. Claude must normalise to per-room (2 adults assumption) before comparing.
- **Run-time of the scan** — expect 15-25 minutes per Tuesday run, up from ~5. Acceptable (runs unattended).
- **Phase 2 cold start** — v2 baselines reset. Same mitigation as v1 initial rollout: Phase 1 tightened factor + reasoning requirement prevents noise.

## 15. Implementation plan (high-level)

Phased rollout:

**Phase A — infrastructure (one implementation cycle):**

- Extend `traveller_math.py` to accept the new input schema (combined totals) — keep legacy keys as aliases
- Add new tests covering combined-total evaluator
- Migrate `config/settings.json` to new shape; update any tests that reference old ceilings
- Add `schema: "v2"` marker handling

**Phase B — prompt rewrite (one cycle):**

- Rewrite `prompts/weekly-scan.md` steps 3-12 per this spec
- Update `CLAUDE.md` with new route semantics if needed (probably unchanged)
- Update `README.md` to mention hotels + packages

**Phase C — smoke test (one cycle):**

- User runs `/weekly-scan` manually with new prompt
- Inspect output/current_fares.json for v2 shape
- Inspect generated report and email
- Iterate based on real-world observations

## 16. Success criteria

- First v2 run produces observations with all new fields populated (nulls allowed per documented rules)
- At least one route surfaces a package-beats-DIY winner
- At least one short-haul route considers same-day with `nights=0`
- Email reasoning cites combined-total specifics (no route surfaces as "just cheap")
- No ruff failures, all tests pass
- v1 history rows remain readable (no crashes parsing them)

## 17. Deferred / future work

- Price-history line charts per route (all-time combined trajectory)
- Seasonal baseline (compare current to same-month prior-year)
- Alternative origins (e.g., ORK, SNN, BFS) — user travels from DUB but could sometimes deadhead
- Train/ferry bundle (Dover-Calais + Paris hotel as a "trip")
- Frequent-flyer credit optimization
- Concert/event awareness (hotels spike during F1 weekend, etc.)
