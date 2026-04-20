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

## 6. Accommodation sampling strategy

Accommodation now spans two sources: **hotels** (always considered) and **Airbnb** (only for long-stay categories). The combined accommodation price used downstream is `min(hotel_median, airbnb_median)` for applicable routes, with the winning source recorded.

### 6a. Hotel sampling (all categories)

For each (destination, date-range) pair:

1. Claude fetches Booking.com search results for dates, filtering: **rating ≥ 7.5**, **review count ≥ 100**.
2. Of qualifying results, Claude takes the **cheapest 10** by per-night price, then computes the **median of the cheapest 3** → representative `hotel_price_per_night_eur`.
3. Store: `hotel_sample_size` (how many qualified), `hotel_rating_min` (lowest rating of the top 3), `hotel_example_name`, `hotel_example_booking_url` (the single cheapest for one-click book).

If < 3 hotels qualify: mark hotels as "hotel data insufficient" for that date pair (set hotel fields to null). If Airbnb also insufficient for an applicable category, exclude the route from the evaluator.

Skip hotel fetch entirely for 0-night (same-day) trips.

### 6b. Airbnb sampling (long-stay categories only)

**Applies to:** `europe_long_haul` and `intercontinental_asia` only. Explicitly does NOT apply to `europe_short_haul` (trips too short to bother with Airbnb friction) or `intercontinental_south_america` (user preference — hotels only).

For each applicable (destination, date-range) pair:

1. Claude fetches Airbnb search results for dates, filtering (defaults — flagged as assumptions, tune after first real run):
   - **Rating ≥ 4.5 / 5**
   - **Review count ≥ 50** (Airbnbs typically have fewer reviews than hotels — lower floor than hotel's 100)
   - **Property type: "Entire place" only** (no shared/private room — privacy is a hard requirement for budget travel)
2. Of qualifying results, take the **cheapest 10** by effective per-night price, compute the **median of the cheapest 3** → representative `airbnb_price_per_night_eur`.
3. Store: `airbnb_sample_size`, `airbnb_rating_min`, `airbnb_example_name`, `airbnb_example_booking_url`.

Important — effective per-night price must include Airbnb cleaning/service fees. Compute `effective_per_night = total_cost_for_stay / nights` — not the headline nightly rate.

If < 3 Airbnbs qualify: mark Airbnb as insufficient (nulls), fall back to hotel-only for that route.

### 6c. Combined accommodation

For each (destination, date-range) pair, the evaluator uses:

- `accommodation_price_per_night_eur = min(hotel_price_per_night_eur, airbnb_price_per_night_eur)` when both exist for an applicable category.
- `accommodation_source ∈ {"hotel", "airbnb"}` records which side won.
- For short-haul and SA routes: `accommodation_price_per_night_eur = hotel_price_per_night_eur`, `accommodation_source = "hotel"`, Airbnb fields null.

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

Add `"schema": "v2"` field to distinguish from v1 rows. Full v2 row (long-haul Europe example, Airbnb wins):

```json
{
  "schema": "v2",
  "run_date": "2026-04-27",
  "origin": "DUB",
  "destination_iata": "ATH",
  "destination_city": "Athens",
  "category": "europe_long_haul",
  "is_wishlist": false,
  "trip_profile": "europe_long_haul_5_nights",
  "nights": 5,
  "departure_date": "2026-06-12",
  "return_date": "2026-06-17",

  "flight_price_eur": 110.0,
  "flight_airline": "Aegean",
  "flight_stops": 0,
  "flight_booking_url": "...",

  "hotel_price_per_night_eur": 85.0,
  "hotel_sample_size": 9,
  "hotel_rating_min": 7.8,
  "hotel_example_name": "...",
  "hotel_example_booking_url": "...",

  "airbnb_price_per_night_eur": 62.0,
  "airbnb_sample_size": 7,
  "airbnb_rating_min": 4.7,
  "airbnb_example_name": "...",
  "airbnb_example_booking_url": "...",

  "accommodation_source": "airbnb",
  "accommodation_price_per_night_eur": 62.0,

  "diy_total_eur": 420.0,
  "package_cheapest_eur": 510.0,
  "package_cheapest_site": "loveholidays",
  "package_cheapest_url": "...",

  "best_total_eur": 420.0,
  "best_source": "diy_airbnb",

  "combined_ceiling_eur": 590.0,
  "market_p15_combined_eur": 480.0,
  "baseline_median_combined_eur": null,

  "was_flagged_as_deal": true,
  "flag_reason": "best_total 420 ≤ 0.85×p15 (408), Airbnb 27% cheaper than hotel",
  "phase": 1
}
```

For short-haul and SA routes (Airbnb not applicable):

- `airbnb_*` fields are **null**
- `accommodation_source = "hotel"`
- `best_source ∈ {"diy_hotel", "package_<site>"}`

For long-haul Europe / Asia routes, `best_source` is one of `{"diy_hotel", "diy_airbnb", "package_<site>"}`.

Null fields allowed when:

- `hotel_*` — for 0-night trips or when hotel data insufficient
- `airbnb_*` — for short-haul + SA categories always; for long-haul / Asia when <3 qualifying Airbnbs
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

The prompt also accepts a **scope parameter** (`europe | intercontinental | all`) passed by the slash commands (see §15). Scope filters which categories are scanned — the rest of the logic is the same.

Steps that need rewriting:

- **Step 3 (pick routes):** Filter the scan list by scope. Add trip-profile selection per category. For short-haul, Claude chooses preferred_nights_range by default (1-2 nights). Decides whether to ALSO include a same-day (0-night) variant: Claude does a quick flight-only check first; if the cheapest round-trip fare for the day is ≤ €40, add a 0-night variant. Otherwise skip.
- **Step 4 (fetch data):** Becomes a category-conditional fetch workflow per route:
  - **europe_short_haul:** (a) flight candidates, (b) hotel candidates only, (c) package totals (skip packages for 0-night variants).
  - **europe_long_haul:** (a) flight candidates, (b) hotel candidates, (c) **Airbnb candidates**, (d) package totals.
  - **intercontinental_asia:** (a) flight candidates, (b) hotel candidates, (c) **Airbnb candidates**, (d) package totals.
  - **intercontinental_south_america:** (a) flight candidates, (b) hotel candidates, (c) package totals. No Airbnb.

  For applicable categories, pick the cheapest qualifying accommodation (hotel vs Airbnb) per date-pair before combining. Prompt includes explicit pragmatism hints — "don't fetch hotels or Airbnbs for all 20 flight candidates; pick the cheapest 5". Unreachable sites (CAPTCHA/403) are treated as "not offered" — log and move on, no retries.
- **Step 5 (build evaluate input):** Build `current_combined_totals_eur` by pairing dates. Use `accommodation_price_per_night_eur = min(hotel, airbnb)` where applicable.
- **Step 6 (call traveller_math evaluate):** Pass combined totals plus `combined_ceiling_eur` explicitly.
- **Step 7 (sanity check):** Claude may verify percentile / median of combined totals. **Package prices are trusted from site output — no math sanity check** (per user decision 3).
- **Step 8 (append observations):** Use v2 schema. Include ALL the new fields including Airbnb + `accommodation_source`.
- **Step 9 (report):** Add a "DIY vs Package" column plus accommodation source (hotel / airbnb). Break down reasoning: flight cost, accommodation cost + source, package alternative, winner.
- **Step 11 (deal reasoning ladder):** Extend with new reason types (see §18 decision 5 for the flight-only historical signal):
  - "All-time low for combined trip cost" — combined-total history check
  - "Package beats DIY by ≥ €X" — explicit package-win reason
  - "Airbnb beats hotel by ≥ €X (applicable categories)" — explicit Airbnb-win reason
  - "Flight alone is -X% vs 12-week flight-only median" — secondary signal from v1 history, **bonus only, never the sole reason**
  - "Same-day round trip feasible and flight <€40" — specific to 0-night short-haul
- **Step 12 (email):** Email body block template gains `Flight: €X / <Hotel|Airbnb>: €Y / Total: €Z (DIY)` or `Package via loveholidays: €Z`.

## 13. Config changes

`config/settings.json` migrates:

- `category_ceilings_eur` (flat) → `category_cost_caps_eur` (nested with flight + hotel_per_night)
- Add `trip_profiles`
- Add `departure_day_preference` (list of allowed weekday strings)
- Add `hotel_quality_floor` (`min_rating`, `min_review_count`)
- Add `hotel_sampling` (`candidates_to_fetch`, `median_of_cheapest_n`)
- Add `airbnb_quality_floor` (`min_rating`, `min_review_count`, `property_type`)
- Add `airbnb_enabled_categories` (list — currently `["europe_long_haul", "intercontinental_asia"]`)
- Add `airbnb_sampling` (`candidates_to_fetch`, `median_of_cheapest_n`)
- Add `bundled_sites` (list of 10 site names)
- Remove `category_ceilings_eur` and `search_windows` (replaced by `category_cost_caps_eur` + `trip_profiles`)

Example settings.json diff (conceptual):

```json
{
  "category_cost_caps_eur": { ... },
  "wishlist_ceiling_multiplier": 1.3,
  "trip_profiles": { ... },
  "departure_day_preference": ["mon", "tue", "fri", "sat", "sun"],
  "hotel_quality_floor": { "min_rating": 7.5, "min_review_count": 100 },
  "hotel_sampling": { "candidates_to_fetch": 10, "median_of_cheapest_n": 3 },
  "airbnb_quality_floor": { "min_rating": 4.5, "min_review_count": 50, "property_type": "entire_place" },
  "airbnb_enabled_categories": ["europe_long_haul", "intercontinental_asia"],
  "airbnb_sampling": { "candidates_to_fetch": 10, "median_of_cheapest_n": 3 },
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

- **Scraping cost** — 10 package sites × ~30 routes × several date options = a lot. Claude must be pragmatic: skip sites that don't cover a route fast, cap total time. Split slash commands (§15) cap each category's budget to ~20 min — user runs both back-to-back if desired.
- **Package site rate limiting / CAPTCHAs** — some sites aggressively block scraping. Treat unreachable sites as "not offered" (per user decision 4) and move on. No retries.
- **Hotel "quality" is subjective** — 7.5+ on Booking.com is a good floor but misses brand-new hotels with few reviews. Accepted trade-off.
- **Package price ambiguity** — some sites price per-person, some per-room. Claude must normalise to per-room (2 adults assumption) before comparing. Prompt-only trust (no math sanity check) per user decision 3.
- **Run-time of the scan** — expect 15-25 minutes per category per run. Acceptable (runs unattended; split into two slash commands per user decision 2).
- **Phase 2 cold start** — v2 baselines reset. ~4-week reset is accepted (user decision 1); no back-fill of v1 rows. Same mitigation as v1 initial rollout: Phase 1 tightened factor + reasoning requirement prevents noise.
- **Airbnb cleaning/service fees inflate real per-night cost** — Claude must compute `effective_per_night = total_cost_for_stay / nights`, not the list price. Ignoring fees leads to Airbnb falsely beating hotels.
- **Airbnb availability is sparse in some destinations** — if <3 qualifying Airbnbs in a date window, fall back to hotel-only for that route (mark `airbnb_*` null, `accommodation_source = "hotel"`).
- **Airbnb quality harder to standardise than hotels** — no single trust signal like Booking.com's 7.5+. Mitigated by rating floor (≥4.5) + review floor (≥50) + entire-place filter. Accepted trade-off; tune defaults after first real runs.

## 15. Implementation plan (high-level)

Phased rollout, matched to the split slash-command delivery (user decision 2):

**Phase A — evaluator + config migration (one implementation cycle):**

- Extend `traveller_math.py` to accept the new input schema (combined totals + explicit `combined_ceiling_eur`) — keep legacy keys as aliases (TDD: RED → GREEN → COMMIT)
- Migrate `config/settings.json` to v2 shape (trip profiles, cost caps, hotel/Airbnb/package knobs)
- Add `schema: "v2"` marker handling

**Phase B — prompt rewrite + split slash commands (one cycle):**

- Rewrite `prompts/weekly-scan.md` steps 3-13 per this spec, including `scope` parameter handling
- Create `.claude/commands/weekly-scan-europe.md` → `scope=europe`
- Create `.claude/commands/weekly-scan-intercontinental.md` → `scope=intercontinental`
- Update `.claude/commands/weekly-scan.md` to run both scopes back-to-back (canonical combined run)
- Update `CLAUDE.md` natural-language → slash-command routing
- Update `README.md` + `docs/operations/schedule-setup.md` to mention hotels + packages + Airbnb + split commands

**Phase C — smoke test (one cycle):**

- User runs `/weekly-scan-europe` first, then `/weekly-scan-intercontinental`
- Inspect `output/current_fares.json` for v2 shape (Airbnb fields populated for long-haul/Asia; null for short-haul/SA)
- Inspect generated report and email
- Iterate based on real-world observations — particularly the Airbnb quality floor defaults

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
- **Long-haul / intercontinental: serviced apartments (Silverdoor, SaylBnB) alongside Airbnb** — for monthly-stay economics on 3+ week trips, serviced apartments often beat both hotels and Airbnb. Defer until v2 Airbnb integration is proven.

## 18. User decisions log

Decisions made during spec review (2026-04-20 / iteration pass). Recorded here as the authoritative source; referenced throughout this spec:

1. **Phase 2 cold-start reset:** Accept the ~4-week reset window when v2 rolls out. Do **not** back-fill v1 flight-only rows into v2 combined-total baselines. Phase 1 carries the load during the reset.
2. **Scan runtime split:** Split per-category into two slash commands — `/weekly-scan-europe` (europe_short_haul + europe_long_haul + EU wishlist) and `/weekly-scan-intercontinental` (intercontinental_asia + intercontinental_south_america + intercontinental wishlist). User runs them back-to-back when desired. Keep `/weekly-scan` as a convenience meta-command that runs both sequentially.
3. **Package price normalisation:** Prompt-only — trust Claude to normalise per-room pricing, no Python-side math sanity check. If results look off in practice, revisit.
4. **Unreachable sites:** Acceptable. Treat as "not offered" for that route/date-pair and move on. No retries, no escalation.
5. **v1 flight-only baselines:** Not used as primary Phase 2 signal (decision 1), but **included as a secondary / bonus signal** in the deal-reasoning ladder. New reason type: *"flight alone is -X% vs your 12-week flight-only median"* — never the sole reason for flagging, but reinforces a combined-total flag and makes reporting richer while v2 history builds.
6. **Airbnb scope:** Include Airbnb prices for `europe_long_haul` and `intercontinental_asia` only. Explicitly **NOT** for `europe_short_haul` (trips too short to bother with Airbnb friction) or `intercontinental_south_america` (user preference — hotels only).
7. **Airbnb defaults (flagged as assumptions — tune after first real runs):** rating ≥ 4.5/5, review count ≥ 50, property type = "Entire place" only, same sampling rule as hotels (top 10 qualifying → median of cheapest 3).
8. **Accommodation comparison rule:** For applicable categories, `accommodation_price_per_night_eur = min(hotel_median, airbnb_median)`. The winning side is recorded in `accommodation_source`. Downstream `best_source` values expand to `{"diy_hotel", "diy_airbnb", "package_<site>"}`.
