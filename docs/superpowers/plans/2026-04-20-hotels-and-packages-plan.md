# Hotels + Packages Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox syntax.

**Goal:** Implement the hotels + packages extension per spec at `docs/superpowers/specs/2026-04-20-hotels-and-packages-design.md`.

**Architecture:** Phase A — evaluator + config infrastructure (TDD). Phase B — prompt rewrite + split slash commands. Phase C — first real run smoke test.

**Tech Stack:** Python 3.12 stdlib only (traveller_math.py), Markdown (prompts + commands), JSON (config).

---

## Task 1: Extend traveller_math.py to accept combined-total input schema

**Files:**
- Modify: `traveller_math.py`
- Modify: `tests/test_traveller_math.py`

- [ ] **Step 1: Write RED tests for the new input schema**

Append to `tests/test_traveller_math.py`:

```python
# ---- evaluate: combined-total input schema (v2) ----------------------------


_V2_SETTINGS = {
    "cold_start_p_percentile": 15,
    "phase1_max_obs": 3,
    "phase2_max_obs": 11,
    "phase2_min_discount_pct_non_wishlist": 25,
    "phase2_min_discount_pct_wishlist": 15,
    "wishlist_ceiling_multiplier": 1.3,
}


def _v2_route(**overrides):
    base = {
        "destination_iata": "BCN",
        "is_wishlist": False,
        "category": "europe_short_haul",
        "trip_profile": "short_haul_1_night",
        "nights": 1,
        "current_combined_totals_eur": [100.5, 112.0, 125.0, 140.0, 150.0],
        "prior_combined_totals_eur": [],
        "combined_ceiling_eur": 120.0,
    }
    base.update(overrides)
    return base


def test_evaluate_v2_accepts_combined_totals_and_ceiling() -> None:
    # combined totals: [60, 90, 100, 110, 120] → p15 = 60+0.6*30 = 78
    # threshold = 0.85*78 = 66.3. best = 60 <= 66.3 and <= ceiling 120.
    route = _v2_route(
        current_combined_totals_eur=[60.0, 90.0, 100.0, 110.0, 120.0],
        combined_ceiling_eur=120.0,
    )
    result = tm.evaluate_routes({"routes": [route], "settings": _V2_SETTINGS})
    verdict = result["verdicts"][0]
    assert verdict["phase"] == 1
    assert verdict["is_deal"] is True
    # v2 output uses combined-total field names
    assert verdict["best_combined_eur"] == 60.0
    assert verdict["combined_ceiling_eur"] == 120.0
    assert verdict["baseline_median_combined_eur"] is None
    assert verdict["market_p15_combined_eur"] is not None


def test_evaluate_v2_phase2_uses_prior_combined_totals() -> None:
    # 4 priors → phase 2. median = 150. best = 100 → 33% discount, threshold 25%.
    route = _v2_route(
        current_combined_totals_eur=[100.0, 130.0, 140.0],
        prior_combined_totals_eur=[140.0, 150.0, 160.0, 170.0],
        combined_ceiling_eur=180.0,
    )
    result = tm.evaluate_routes({"routes": [route], "settings": _V2_SETTINGS})
    verdict = result["verdicts"][0]
    assert verdict["phase"] == 2
    assert verdict["is_deal"] is True
    assert verdict["baseline_median_combined_eur"] == pytest.approx(155.0)


def test_evaluate_v2_respects_explicit_combined_ceiling() -> None:
    # best = 60, but ceiling = 50 → should fail on ceiling
    route = _v2_route(
        current_combined_totals_eur=[60.0, 90.0, 100.0],
        combined_ceiling_eur=50.0,
    )
    result = tm.evaluate_routes({"routes": [route], "settings": _V2_SETTINGS})
    verdict = result["verdicts"][0]
    assert verdict["is_deal"] is False
    assert "ceiling" in verdict["reason"]
    assert verdict["combined_ceiling_eur"] == 50.0


def test_evaluate_legacy_flight_only_schema_still_works() -> None:
    # Legacy v1 call path (current_fares_eur + ceilings_eur in settings) unchanged
    legacy_settings = {
        **_V2_SETTINGS,
        "ceilings_eur": {"europe_short_haul": 80},
    }
    legacy_route = {
        "destination_iata": "BCN",
        "is_wishlist": False,
        "category": "europe_short_haul",
        "current_fares_eur": [30.0, 60.0, 70.0, 80.0, 90.0],
        "prior_prices_eur": [],
    }
    result = tm.evaluate_routes(
        {"routes": [legacy_route], "settings": legacy_settings}
    )
    verdict = result["verdicts"][0]
    assert verdict["is_deal"] is True
    # v1 output shape preserved
    assert "best_price_eur" in verdict
    assert verdict["best_price_eur"] == 30.0
    assert "ceiling_eur" in verdict
```

- [ ] **Step 2: Run tests, verify failure**

```bash
.venv/Scripts/pytest.exe tests/test_traveller_math.py -k "v2 or legacy"
```
Expected: 4 failures (new tests hit missing schema support).

- [ ] **Step 3: Extend `traveller_math.py` to accept both schemas**

Modify `_effective_ceiling` to prefer explicit `combined_ceiling_eur` input, fall back to `ceilings_eur[category]` lookup:

```python
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
```

Add a helper to detect the input shape and extract the value arrays + resolve the output field names:

```python
def _resolve_schema(route: dict) -> dict:
    """Return schema info: which input keys to read, which output keys to emit."""
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
```

Rewrite `evaluate_route` to use `_resolve_schema` for every verdict-dict key it emits. The phase math itself is unchanged — only input-array selection and output-field naming vary.

- [ ] **Step 4: Run tests, verify pass**

```bash
.venv/Scripts/pytest.exe
```
Expected: 17 original + 4 new = 21 tests pass, zero failures.

- [ ] **Step 5: Commit**

```bash
git add traveller_math.py tests/test_traveller_math.py
git commit -m "feat(math): accept combined-total input schema; legacy flight-only still works"
```

---

## Task 2: Migrate config/settings.json to v2 shape

**Files:**
- Modify: `config/settings.json`
- No tests (JSON schema only — covered implicitly by smoke run)

- [ ] **Step 1: The current state is already committed** (HEAD has the v1 settings.json). No extra backup step needed — `git show HEAD:config/settings.json` recovers it.

- [ ] **Step 2: Rewrite `config/settings.json` with v2 shape**

```json
{
  "origin_iata": "DUB",
  "currency": "EUR",
  "email_recipient": "lukasmtorquato@gmail.com",

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
  },

  "category_cost_caps_eur": {
    "europe_short_haul":        { "flight": 45,  "hotel_per_night": 75 },
    "europe_long_haul":         { "flight": 90,  "hotel_per_night": 100 },
    "intercontinental_asia":    { "flight": 500, "hotel_per_night": 80 },
    "intercontinental_south_america": { "flight": 550, "hotel_per_night": 70 }
  },

  "wishlist_ceiling_multiplier": 1.3,

  "departure_day_preference": ["mon", "tue", "fri", "sat", "sun"],

  "hotel_quality_floor": {
    "min_rating": 7.5,
    "min_review_count": 100
  },
  "hotel_sampling": {
    "candidates_to_fetch": 10,
    "median_of_cheapest_n": 3
  },

  "airbnb_quality_floor": {
    "min_rating": 4.5,
    "min_review_count": 50,
    "property_type": "entire_place"
  },
  "airbnb_enabled_categories": ["europe_long_haul", "intercontinental_asia"],
  "airbnb_sampling": {
    "candidates_to_fetch": 10,
    "median_of_cheapest_n": 3
  },

  "bundled_sites": [
    "loveholidays",
    "Jet2 Holidays",
    "TUI",
    "easyJet Holidays",
    "On the Beach",
    "Expedia",
    "Booking.com Packages",
    "Kayak Packages",
    "Trivago Packages",
    "Holiday Pirates"
  ],

  "baseline": {
    "cold_start_p_percentile": 15,
    "baseline_window_observations": 12,
    "phase2_min_discount_pct_non_wishlist": 25,
    "phase2_min_discount_pct_wishlist": 15,
    "phase_thresholds": {"phase1_max_obs": 3, "phase2_max_obs": 11}
  },

  "kiwi_api_key_env_var": "KIWI_TEQUILA_API_KEY",
  "kiwi_rate_limit_delay_ms": 200
}
```

**Removed:** `category_ceilings_eur`, `search_windows` (replaced by `category_cost_caps_eur` + `trip_profiles`).

- [ ] **Step 3: Smoke-parse the new config**

```bash
python -c "import json; s = json.load(open('config/settings.json')); print(list(s['trip_profiles']), list(s['category_cost_caps_eur']), list(s['airbnb_enabled_categories']))"
```
Expected: four trip profiles, four cost-cap categories, two Airbnb-enabled categories.

- [ ] **Step 4: Commit**

```bash
git add config/settings.json
git commit -m "feat(config): migrate to v2 shape (trip profiles, hotel/airbnb/package knobs)"
```

---

## Task 3: Update CLAUDE.md slash-command references

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Rewrite the "Triggering the scan" section**

Replace the current "Triggering the scan" section with:

```markdown
## Triggering the scan

Three slash commands, pick the one that matches the user's intent:

- `/weekly-scan` — runs **both** scopes back-to-back (canonical combined run, produces one unified report).
- `/weekly-scan-europe` — `europe_short_haul` + `europe_long_haul` + EU-category wishlist entries only.
- `/weekly-scan-intercontinental` — `intercontinental_asia` + `intercontinental_south_america` + intercontinental-category wishlist entries only.

### Natural-language routing

| User phrasing                                          | Slash command                   |
|--------------------------------------------------------|---------------------------------|
| "check EU flights", "european deals", "weekend trip"   | `/weekly-scan-europe`           |
| "check intercontinental", "long-haul", "asia deals", "south america" | `/weekly-scan-intercontinental` |
| "check travel deals", "run the weekly scan", "scan for trips" | `/weekly-scan` (both)           |
| "cheap flights from Dublin" (generic)                  | `/weekly-scan` (both)           |

Don't improvise the scan — always delegate to the relevant slash command, which reads `prompts/weekly-scan.md` with the appropriate `scope` argument.
```

- [ ] **Step 2: Verify the rest of CLAUDE.md still reads correctly** (no other edits needed — "Editing config vs running the scan" and "Boundaries" sections stay as-is).

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude-md): reference new split slash commands"
```

---

## Task 4: Rewrite prompts/weekly-scan.md

**Files:**
- Modify: `prompts/weekly-scan.md`

- [ ] **Step 1: Add a "Scope parameter" section at the top (after Philosophy, before Prerequisites)**

```markdown
## Scope parameter

This prompt accepts one argument: `scope ∈ {"europe", "intercontinental", "all"}`. Default: `"all"`.

The slash commands pass scope explicitly:
- `/weekly-scan-europe` → `scope=europe`
- `/weekly-scan-intercontinental` → `scope=intercontinental`
- `/weekly-scan` → `scope=all` (runs both back-to-back, produces one report)

Scope filters which category groups contribute to the scan list in step 3. Everything else in this prompt (math, history, email) is scope-agnostic.
```

- [ ] **Step 2: Rewrite step 3 (build the scan list) to filter by scope and carry trip-profile**

```markdown
## 3. Build the scan list

Start with an empty list. Then, based on `scope`:

- **scope in {"europe", "all"}:**
  - Add `config/wishlist.json` entries whose `category` is `europe_short_haul` or `europe_long_haul`.
  - Add all `destinations.europe_short_haul`.
  - Add all `destinations.europe_long_haul`.

- **scope in {"intercontinental", "all"}:**
  - Add `config/wishlist.json` entries whose `category` is `intercontinental_asia` or `intercontinental_south_america`.
  - Rotated picks (same rotation logic as v1):
    - Read `state/rotation.json`. Default `{"asia_cursor": 0, "south_america_cursor": 0}` if missing.
    - Take **next 3 Asia** entries from `destinations.intercontinental_asia` starting at `asia_cursor` (wrap).
    - Take **next 2 South America** entries from `destinations.intercontinental_south_america` starting at `south_america_cursor` (wrap).

Dedup by IATA. Wishlist wins ties. Attach to each route: `iata`, `city`, `category`, `is_wishlist`, and pick a `trip_profile` string per category from `settings.trip_profiles`:

| Category                         | trip_profile string                       | Default `nights` pick                                   |
|----------------------------------|-------------------------------------------|---------------------------------------------------------|
| europe_short_haul                | `short_haul_1_night`, `short_haul_2_nights`, `short_haul_same_day` (0-night — see step 4 for the gate) | 1 or 2 |
| europe_long_haul                 | `europe_long_haul_<N>_nights`             | 5 (middle of [2, 7])                                    |
| intercontinental_asia            | `asia_<N>_nights`                         | 14 (middle of [10, 21])                                 |
| intercontinental_south_america   | `south_america_<N>_nights`                | 14                                                      |

A single route may enter the scan list multiple times if Claude wants to evaluate different nights (e.g. BCN at 1 night AND 2 nights). Cap to at most 2 profile variants per route to keep scan time bounded.
```

- [ ] **Step 3: Rewrite step 4 (fetch data) into three-part workflow with conditional Airbnb**

```markdown
## 4. For each route: fetch flights, accommodation, and packages

This step is category-conditional. Per route (or per route+profile variant):

### 4a. Flights (always)

Use `WebSearch` + `WebFetch` on Google Flights / Skyscanner / Kayak and airline-direct deals pages. Honour `settings.departure_day_preference` — prefer Mon/Tue/Fri/Sat/Sun departures over Wed/Thu.

Collect 5–15 candidate fares. Each candidate: `price_eur`, `departure_date`, `return_date`, `nights`, `airline`, `stops`, `booking_url`.

**Short-haul same-day gate:** if this is a `europe_short_haul` route and `trip_profile = short_haul_same_day`, first do a quick flight-only check for the cheapest round-trip on the day. If cheapest fare > `trip_profiles.europe_short_haul.allow_same_day_if_flight_under_eur` (€40), drop this variant — same-day isn't worth it. Otherwise keep it with `nights=0`.

Keep only the top **5 cheapest** flight date-pairs per route to bound downstream fetches.

### 4b. Accommodation (always — conditionally includes Airbnb)

For each of the top 5 flight date-pairs:

**Hotels (every category):**

- Search Booking.com for the destination, those exact dates, 2 adults.
- Filter: `rating ≥ settings.hotel_quality_floor.min_rating` AND `review_count ≥ settings.hotel_quality_floor.min_review_count`.
- Take the **cheapest 10** qualifying by per-night price.
- `hotel_price_per_night_eur = median(cheapest 3 per-night prices)`.
- Record `hotel_sample_size`, `hotel_rating_min` (lowest rating of the top 3), `hotel_example_name`, `hotel_example_booking_url` (single cheapest, for one-click booking).
- If <3 qualify, set hotel fields to null for that date pair.
- Skip hotels entirely for `nights=0` variants.

**Airbnb (only if category ∈ `settings.airbnb_enabled_categories`):**

Currently enabled: `europe_long_haul`, `intercontinental_asia`. Skip for `europe_short_haul` and `intercontinental_south_america` — set `airbnb_*` fields to null.

- Search Airbnb for the destination, those exact dates, 2 guests.
- Filter: `rating ≥ settings.airbnb_quality_floor.min_rating` (4.5), `review_count ≥ settings.airbnb_quality_floor.min_review_count` (50), property type = "Entire place" only.
- Take the **cheapest 10** qualifying by **effective per-night price** — compute as `total_stay_cost / nights`, including cleaning and service fees. Do NOT use the headline nightly rate.
- `airbnb_price_per_night_eur = median(cheapest 3 effective per-night prices)`.
- Record `airbnb_sample_size`, `airbnb_rating_min`, `airbnb_example_name`, `airbnb_example_booking_url`.
- If <3 qualify, set Airbnb fields to null and fall back to hotel-only for that date pair.

**Combined accommodation:**

- If both hotel and Airbnb available: `accommodation_price_per_night_eur = min(hotel_price_per_night_eur, airbnb_price_per_night_eur)`, `accommodation_source` = whichever side won (`"hotel"` or `"airbnb"`).
- If only hotel available: use hotel, `accommodation_source = "hotel"`.
- If neither: skip this date pair.

### 4c. Packages (always, except for 0-night variants)

For each of the top 5 flight date-pairs, query **all 10 `settings.bundled_sites`** for "DUB → destination, dates X → Y, 2 adults":

- Record cheapest total per site (normalised per-room, 2 adults).
- Unreachable sites (CAPTCHA / 403 / rate-limited) → log once and treat as "not offered". No retries.
- `package_cheapest_eur = min(all site totals)`; record `package_cheapest_site` and `package_cheapest_url`.

Skip packages entirely for `nights=0` variants (packages generally require ≥2 nights).

### 4d. Pragmatism

You have a ~20-minute soft budget per scope (see "Time budget" near the bottom of this prompt). Skip remaining flight candidates / accommodation lookups / package sites if approaching it. Better to cover every route with 3 candidates than to stall on one route chasing a 6th flight option.

Store everything in `output/current_fares.json` (see step 5).
```

- [ ] **Step 4: Rewrite step 5 to build evaluator input with combined totals**

```markdown
## 5. Build `current_combined_totals_eur` per route, copy settings

For each route in the scan list:

For every date-pair where both flight AND accommodation data exist, compute:

```
diy_total = flight_price + nights × accommodation_price_per_night_eur
```

Also include package totals where available. Collect all DIY totals and all package totals into `current_combined_totals_eur` (a flat list — the evaluator just needs the distribution).

Build `prior_combined_totals_eur` by scanning `history/observations.jsonl` for this destination with `schema == "v2"` only. Take the most recent N = `settings.baseline.baseline_window_observations` (12) rows, extract `best_total_eur` from each. v1 rows are **ignored** for combined-total baselines — Phase 2 will be cold for ~4 weeks after v2 rollout (accepted by user).

Compute `combined_ceiling_eur` per route:

```
base = category_cost_caps_eur[category].flight + nights × category_cost_caps_eur[category].hotel_per_night
if is_wishlist: base *= wishlist_ceiling_multiplier
combined_ceiling_eur = base
```

For `nights == 0` (same-day): `combined_ceiling_eur = category_cost_caps_eur[category].flight` only.

Shape of `output/current_fares.json`:

```json
{
  "routes": [
    {
      "destination_iata": "BCN",
      "destination_city": "Barcelona",
      "is_wishlist": false,
      "category": "europe_short_haul",
      "trip_profile": "short_haul_1_night",
      "nights": 1,
      "current_combined_totals_eur": [100.5, 112.0, 125.0],
      "prior_combined_totals_eur": [],
      "combined_ceiling_eur": 120.0,
      "fare_details": [
        {"date_pair": ["2026-06-12", "2026-06-13"], "flight_price_eur": 38.0, "flight_airline": "Ryanair", "flight_stops": 0, "flight_booking_url": "...", "hotel_price_per_night_eur": 62.5, "hotel_sample_size": 8, "airbnb_price_per_night_eur": null, "airbnb_sample_size": null, "accommodation_source": "hotel", "accommodation_price_per_night_eur": 62.5, "diy_total_eur": 100.5, "package_cheapest_eur": 115.0, "package_cheapest_site": "loveholidays", "package_cheapest_url": "..."}
      ]
    }
  ],
  "settings": {
    "cold_start_p_percentile": 15,
    "phase1_max_obs": 3,
    "phase2_max_obs": 11,
    "phase2_min_discount_pct_non_wishlist": 25,
    "phase2_min_discount_pct_wishlist": 15,
    "wishlist_ceiling_multiplier": 1.3
  }
}
```

Note: v2 settings block no longer passes `ceilings_eur` — each route carries `combined_ceiling_eur` directly.
```

- [ ] **Step 5: Update step 6 (evaluate) — same command, v2 input shape**

```markdown
## 6. Evaluate with the math helper

```bash
python traveller_math.py evaluate output/current_fares.json
```

Capture stdout — v2 shape:

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

This is the **source of truth** for which routes flagged.
```

- [ ] **Step 6: Rewrite step 8 (append observations) with v2 schema + Airbnb fields**

```markdown
## 8. Append observations to `history/observations.jsonl`

For each route that got a non-skipped verdict, append **one** JSONL row — the best date-pair (the one whose total matches `best_combined_eur`). Pull the winning detail from `fare_details`.

v2 schema (newline-separated, one per route):

```json
{"schema": "v2", "run_date": "...", "origin": "DUB", "destination_iata": "ATH", "destination_city": "Athens", "category": "europe_long_haul", "is_wishlist": false, "trip_profile": "europe_long_haul_5_nights", "nights": 5, "departure_date": "2026-06-12", "return_date": "2026-06-17", "flight_price_eur": 110.0, "flight_airline": "Aegean", "flight_stops": 0, "flight_booking_url": "...", "hotel_price_per_night_eur": 85.0, "hotel_sample_size": 9, "hotel_rating_min": 7.8, "hotel_example_name": "...", "hotel_example_booking_url": "...", "airbnb_price_per_night_eur": 62.0, "airbnb_sample_size": 7, "airbnb_rating_min": 4.7, "airbnb_example_name": "...", "airbnb_example_booking_url": "...", "accommodation_source": "airbnb", "accommodation_price_per_night_eur": 62.0, "diy_total_eur": 420.0, "package_cheapest_eur": 510.0, "package_cheapest_site": "loveholidays", "package_cheapest_url": "...", "best_total_eur": 420.0, "best_source": "diy_airbnb", "combined_ceiling_eur": 590.0, "market_p15_combined_eur": 480.0, "baseline_median_combined_eur": null, "was_flagged_as_deal": true, "flag_reason": "best_total 420 ≤ 0.85×p15 (408), Airbnb 27% cheaper than hotel", "phase": 1}
```

For short-haul + SA routes, `airbnb_*` fields are **null** and `accommodation_source = "hotel"`. `best_source` values:

- `"diy_hotel"` — DIY total won, accommodation was a hotel
- `"diy_airbnb"` — DIY total won, accommodation was an Airbnb
- `"package_<site>"` — package won (e.g., `"package_loveholidays"`)

Append the single `run_metadata` sentinel row at the end (same as v1):

```json
{"kind": "run_metadata", "schema": "v2", "run_date": "...", "run_started_at": "...", "run_ended_at": "...", "total_routes_queried": 35, "total_api_calls": 0, "deals_flagged": 2, "scope": "europe", "errors": [], "git_commit_sha": null}
```

Append-mode only. Never rewrite the file.
```

- [ ] **Step 7: Rewrite step 9 (report) with DIY vs Package + accommodation source**

```markdown
## 9. Write the dated markdown report

Write `reports/<run_date>.md`. Template:

```markdown
# Travel Deals Scan — <run_date> (<weekday>)

**Origin:** DUB  **Currency:** EUR  **Scope:** <scope>

## Great deals this week

### Athens (ATH) — €420 / 5 nights (DIY, Airbnb)
- **Dates:** 2026-06-12 → 2026-06-17 (5 nights)
- **Flight:** Aegean, €110 return (direct)
- **Accommodation:** Airbnb €62/night (hotel median was €85/night — Airbnb wins)
- **Package alternative:** loveholidays €510 — DIY beats by €90
- **Phase:** 1 (cold-start)
- **Why it flagged:** best_total 420 ≤ 0.85×p15 (408); Airbnb 27% cheaper than hotel
- **Book flight:** https://... &nbsp; **Book Airbnb:** https://...

## Routes scanned (no deal)

| Route | Best total | Source | DIY vs Package | Phase | Reason |
|-------|-----------|--------|----------------|-------|--------|
| AMS   | €250      | diy_hotel | DIY €250 / Pkg €310 | 1 | best_total above ceiling 245 |

## Routes skipped (errors)

| Route | Reason |
|-------|--------|
| BKK   | no flights found after 2 queries |

## Run metadata

- **Scope:** <scope>
- **Routes queried:** 35
- **Deals flagged:** 2
- **Errors:** 1 (BKK skipped)
- **Duration:** 18m 40s
```

When `/weekly-scan` (scope=all) runs both scopes back-to-back, produce **one** report combining both — the "Great deals" sections merge and the metadata lists both durations.
```

- [ ] **Step 8: Extend step 11 (deal reasoning ladder)**

```markdown
## 11. Filter math-verdicts to REAL deals (with reasoning)

For each route where `is_deal == true`, build a reason using this extended ladder (in order of preference):

1. **All-time low for combined trip cost** — scan v2 rows in `history/observations.jsonl`. If `best_total_eur` is the lowest ever recorded `best_total_eur` for this `destination_iata`, cite: "all-time low combined total — previous best was €X on YYYY-MM-DD".
2. **Well below recent combined-total baseline** — if ≥4 v2 priors exist for this route (Phase 2+), and `best_total_eur` is ≥30% below `baseline_median_combined_eur`, cite: "30%+ below your 12-week combined-total median of €X".
3. **Well below the combined-total p15 market reference** — if the math flagged it for Phase 1, cite: "bottom-15% of currently-listed combined totals (p15=€X, best=€Y, ≥15% cheaper)".
4. **Package beats DIY by ≥ €X** — if `best_source` starts with `"package_"` AND beats the cheapest DIY total by ≥ 15% OR ≥ €50 (whichever is smaller), cite: "package via <site> beats DIY by €X".
5. **Airbnb beats hotel by ≥ €X** — only for applicable categories. If `accommodation_source == "airbnb"` AND Airbnb beats the hotel median by ≥ 20%, cite: "Airbnb 20%+ cheaper than hotels for this stay". Bonus reason — do not flag solely on this.
6. **Flight alone is -X% vs 12-week flight-only median** — secondary signal from v1 history. If this destination has ≥4 v1 rows and the new `flight_price_eur` is ≥20% below the v1 flight-only median, cite: "flight alone is -X% vs your 12-week flight-only median of €Y". **Never the sole reason** — use as a bonus to reinforce one of reasons 1-3.
7. **Same-day round trip feasible and flight <€40** — specific to 0-night short-haul. Cite: "same-day round trip works — €X flight, home by night".
8. **Seasonally striking** — use general knowledge. "Unusual for peak season" is valid; "cheap" alone is not.
9. **Wishlist** — never a reason by itself. Lowers the bar for reasons 1-3 (handled by math via looser thresholds).

**If you cannot cite a specific, concrete reason from 1-8, DO NOT include the route in the email.** Demote to "Routes scanned (no compelling deal)". A route merely under the ceiling is NOT a deal.
```

- [ ] **Step 9: Update step 13 (sanity check if >50% flagged)**

```markdown
## 13. Sanity check: if every route "flagged"

If the math flagged >50% of scanned routes, the cold-start noise is too high (combined totals make this more likely than v1 flight-only because of the extra accommodation variance). Keep only the 3 strongest combined-total deal-reasons and demote the rest. Mention in the report that more routes were in range but needed stronger combined-total signal. Prevents spammy first emails while v2 history builds.
```

- [ ] **Step 10: Add a "Time budget" section near the end of the prompt**

```markdown
## Time budget (soft)

Each scope (europe OR intercontinental) has a **20-minute soft budget**:

- Flights + accommodation + packages across ~15-20 routes × up to 5 date-pairs × up to 10 package sites is a lot.
- When 20 minutes elapses, stop fetching new routes — evaluate what you've got, write the report, email if warranted.
- Partial coverage is better than stalling. Log skipped routes in the report.

When `/weekly-scan` runs both scopes (40-minute total soft budget), do europe first, then intercontinental.
```

- [ ] **Step 11: Commit**

```bash
git add prompts/weekly-scan.md
git commit -m "docs(prompt): rewrite weekly-scan for combined totals + accommodation sources + split scope"
```

---

## Task 5: Add split slash commands

**Files:**
- Create: `.claude/commands/weekly-scan-europe.md`
- Create: `.claude/commands/weekly-scan-intercontinental.md`
- Modify: `.claude/commands/weekly-scan.md`

- [ ] **Step 1: Create `.claude/commands/weekly-scan-europe.md`**

```markdown
Run the Europe-only travel deals scan for Dublin round trips.

Read and follow the full runbook at `prompts/weekly-scan.md` from start to finish with `scope=europe`. Do not deviate — that file is the source of truth.

Scope = `europe` means:
- `europe_short_haul` destinations
- `europe_long_haul` destinations
- Wishlist entries in those two categories
- **No** intercontinental routes

Today's date is used as the `run_date`. Dublin-local time determines whether this is the first Tuesday of the month.

Soft budget: 20 minutes. Partial coverage is better than stalling.

When finished, report back with:
- Scope (europe)
- Number of routes scanned
- Number of deals flagged
- Whether email was sent
- Git commit SHA
```

- [ ] **Step 2: Create `.claude/commands/weekly-scan-intercontinental.md`**

```markdown
Run the intercontinental travel deals scan for Dublin round trips.

Read and follow the full runbook at `prompts/weekly-scan.md` from start to finish with `scope=intercontinental`. Do not deviate — that file is the source of truth.

Scope = `intercontinental` means:
- Rotated picks from `intercontinental_asia` (next 3 from `state/rotation.json` cursor)
- Rotated picks from `intercontinental_south_america` (next 2 from cursor)
- Wishlist entries in those two categories
- **No** European routes

Airbnb prices are fetched for `intercontinental_asia` only (not SA — user preference).

Today's date is used as the `run_date`. Dublin-local time determines whether this is the first Tuesday of the month.

Soft budget: 20 minutes. Partial coverage is better than stalling.

When finished, report back with:
- Scope (intercontinental)
- Number of routes scanned
- Number of deals flagged
- Whether email was sent
- Git commit SHA
```

- [ ] **Step 3: Update `.claude/commands/weekly-scan.md`**

Replace its entire contents with:

```markdown
Run the full travel deals scan for Dublin round trips — **both scopes, back-to-back**.

Execute in this order:

1. Run the europe scope first, as if the user invoked `/weekly-scan-europe`. Follow `prompts/weekly-scan.md` with `scope=europe`. Soft budget: 20 minutes.
2. Then run the intercontinental scope, as if the user invoked `/weekly-scan-intercontinental`. Follow `prompts/weekly-scan.md` with `scope=intercontinental`. Soft budget: 20 minutes.
3. Produce **one combined report** at `reports/<run_date>.md` merging both scopes' "Great deals" sections and run metadata. Commit once, with message `chore(traveller): weekly scan <run_date> — N deals (all scopes)`.

If one scope fails catastrophically, still complete the other and note the failure in the combined report.

Today's date is used as the `run_date`. Dublin-local time determines whether this is the first Tuesday of the month.

When finished, report back with:
- Scope (all)
- Per-scope route counts + deal counts
- Whether email was sent
- Git commit SHA
```

- [ ] **Step 4: Commit**

```bash
git add .claude/commands/weekly-scan-europe.md .claude/commands/weekly-scan-intercontinental.md .claude/commands/weekly-scan.md
git commit -m "feat(slash-commands): split by scope (europe / intercontinental / all)"
```

---

## Task 6: Update README + docs

**Files:**
- Modify: `README.md`
- Modify: `docs/operations/schedule-setup.md`

- [ ] **Step 1: Update `README.md`**

In the "What it does" section, replace the description with combined-total + accommodation language. In the "Quick start" section, mention the split slash commands. Suggested patch:

- Change "searches the web for cheap round-trip fares" → "searches the web for flights, hotels, Airbnbs (where applicable), and package deals"
- Add a bullet: "Compares DIY trip cost (flight + accommodation) against 10 bundled package sites"
- Add to "Quick start": "Run `/weekly-scan-europe` for EU-only, `/weekly-scan-intercontinental` for intercontinental, or `/weekly-scan` for both"
- Add to "Project layout": note `.claude/commands/weekly-scan-{europe,intercontinental}.md`
- In the feature list, add: "Airbnb prices included for long-haul Europe and Asia (trips are long enough to benefit)"

- [ ] **Step 2: Update `docs/operations/schedule-setup.md`**

Replace the "Manual weekly invocation" and "Automated invocation via /loop" sections:

```markdown
## Manual weekly invocation (recommended)

Every Tuesday (or whenever you want to scan), open this repo in Claude Code and run one of:

    /weekly-scan                    # both scopes, ~40 min
    /weekly-scan-europe             # EU only, ~20 min
    /weekly-scan-intercontinental   # intercontinental only, ~20 min

Claude follows `prompts/weekly-scan.md` end-to-end with the matching scope.

## Automated invocation via /loop (optional)

For weekly cadence:

    /loop 7d /weekly-scan

(or set a cron equivalent via the scheduled-tasks MCP if you prefer)

You can also loop the split commands independently — e.g. europe every Tuesday, intercontinental every other Tuesday.
```

- [ ] **Step 3: Commit**

```bash
git add README.md docs/operations/schedule-setup.md
git commit -m "docs: update README and setup guide for v2 features"
```

---

## Task 7: Full-suite verification + first smoke run

- [ ] **Step 1: All tests pass**

```bash
.venv/Scripts/pytest.exe -v
```
Expected: 21 tests pass (17 original + 4 new combined-total), zero failures.

- [ ] **Step 2: Verify `python traveller_math.py evaluate` works with both input shapes**

Create a quick throwaway JSON to test legacy shape:

```bash
echo '{"routes":[{"destination_iata":"BCN","is_wishlist":false,"category":"europe_short_haul","current_fares_eur":[30,60,70,80,90],"prior_prices_eur":[]}],"settings":{"cold_start_p_percentile":15,"phase1_max_obs":3,"phase2_max_obs":11,"phase2_min_discount_pct_non_wishlist":25,"phase2_min_discount_pct_wishlist":15,"ceilings_eur":{"europe_short_haul":80},"wishlist_ceiling_multiplier":1.3}}' > /tmp/v1.json
python traveller_math.py evaluate /tmp/v1.json
```
Expected: verdict with `best_price_eur` + `ceiling_eur` (v1 output field names).

And v2:

```bash
echo '{"routes":[{"destination_iata":"BCN","is_wishlist":false,"category":"europe_short_haul","trip_profile":"short_haul_1_night","nights":1,"current_combined_totals_eur":[60,90,100,110,120],"prior_combined_totals_eur":[],"combined_ceiling_eur":120}],"settings":{"cold_start_p_percentile":15,"phase1_max_obs":3,"phase2_max_obs":11,"phase2_min_discount_pct_non_wishlist":25,"phase2_min_discount_pct_wishlist":15,"wishlist_ceiling_multiplier":1.3}}' > /tmp/v2.json
python traveller_math.py evaluate /tmp/v2.json
```
Expected: verdict with `best_combined_eur` + `combined_ceiling_eur` (v2 output field names).

- [ ] **Step 3: Working tree + commit log clean**

```bash
git status    # clean
git log --oneline -8
```
Expected: 6 new v2 commits on top of the spec-amendment commit, in order.

---

## Self-review checklist

- [ ] Every reference to `price_eur` / `current_fares_eur` in the prompt is replaced with combined-total equivalents or preserved only in v1-specific context (step 11 reason 6 about the historical flight-only signal).
- [ ] `accommodation_source` is set in every v2 observation row (either `"hotel"` or `"airbnb"`).
- [ ] Airbnb fields are **null** for `europe_short_haul` and `intercontinental_south_america` routes (per spec §6b + user decision 6).
- [ ] `best_source` uses the documented naming: `diy_hotel`, `diy_airbnb`, `package_<site>`. No legacy `"diy"` values.
- [ ] The category filter in step 3 of the prompt respects `scope ∈ {europe, intercontinental, all}`.
- [ ] `CLAUDE.md` natural-language routing table sends each phrasing to the right slash command.
- [ ] `combined_ceiling_eur` is computed and attached per-route in step 5 of the prompt (not looked up from a map — the v2 math helper expects it explicitly on the route object).
- [ ] v1 history rows still parse without crashes (they're ignored by the Phase 2 baseline builder but readable by any consumer).
- [ ] Airbnb effective per-night rate includes cleaning + service fees (per spec §6b + risk in §14).
