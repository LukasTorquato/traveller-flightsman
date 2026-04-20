# Traveller Weekly Scan

You are running the weekly trip-deal scan for the repo owner, based at `<TRAVELLER_ORIGIN_IATA>` in `<TRAVELLER_TIMEZONE>`.

Today is Tuesday (or user-triggered). Your goal: find great deals on round-trip **trips** (flight + accommodation, compared against bundled packages) from `<TRAVELLER_ORIGIN_IATA>`, flag only the interesting ones, and email the recipient if any. Stay silent if none.

This prompt is self-contained. Follow every step in order. The working directory is the repo root.

---

## Philosophy

Silence on a Tuesday with no outstanding deal is a feature, not a bug. The user's explicit request: *"I want to know about the deals, not average good prices."*

Every email should answer the question *"why is this one noteworthy?"* with a concrete reason. If you can't, don't email.

---

## Scope parameter

This prompt accepts one argument: `scope ∈ {"europe", "intercontinental", "all"}`. Default: `"all"`.

The slash commands pass scope explicitly:
- `/weekly-scan-europe` → `scope=europe`
- `/weekly-scan-intercontinental` → `scope=intercontinental`
- `/weekly-scan` → `scope=all` (runs both back-to-back, produces one report)

Scope filters which category groups contribute to the scan list in step 3. Everything else in this prompt (math, history, email) is scope-agnostic.

---

## Prerequisites to verify before starting

Before doing anything else, check all of the following. If any fails, STOP and email a failure notice via Gmail MCP (subject: `⚠️ Travel scan FAILED — <short reason>`).

- Working directory is the traveller project repo root (has `prompts/weekly-scan.md` and `traveller_math.py`).
- `.env` exists at repo root and contains `TRAVELLER_EMAIL`, `TRAVELLER_ORIGIN_IATA`, `TRAVELLER_CURRENCY`, `TRAVELLER_TIMEZONE`, `TRAVELLER_NAME`. If missing, STOP and instruct the user to copy `.env.example` to `.env` and fill it in.
- `config/settings.json`, `config/destinations.json`, `config/wishlist.json` all exist and parse as valid JSON.
- `config/settings.json` contains v2 keys: `trip_profiles`, `category_cost_caps_eur`, `departure_day_preference`, `hotel_quality_floor`, `hotel_sampling`, `airbnb_quality_floor`, `airbnb_enabled_categories`, `airbnb_sampling`, `bundled_sites`.
- `git status` is clean (no uncommitted changes before we start).
- `python traveller_math.py percentile 15 40,50,60` prints a number (~43.0). Script is runnable.
- The Gmail MCP is connected in this Claude Code session.


---

## 1. Load configuration

Read `.env` using the Read tool. Parse each non-empty, non-comment line as `KEY=VALUE` (strip whitespace around `=`; ignore lines starting with `#` and blank lines). Store the values for use downstream:

  - `TRAVELLER_EMAIL` → email recipient
  - `TRAVELLER_ORIGIN_IATA` → origin airport code
  - `TRAVELLER_CURRENCY` → currency code
  - `TRAVELLER_TIMEZONE` → IANA timezone for "today" and first-Tuesday checks
  - `TRAVELLER_NAME` → greeting name (default `"traveller"` if empty or blank)

Then read all three config JSONs into working memory (project-wide defaults — no user-specific values live here anymore):

- `config/settings.json` — v2 shape. Must contain at minimum: `trip_profiles`, `category_cost_caps_eur`, `wishlist_ceiling_multiplier`, `departure_day_preference`, `hotel_quality_floor`, `hotel_sampling`, `airbnb_quality_floor`, `airbnb_enabled_categories`, `airbnb_sampling`, `bundled_sites`, `baseline`.
- `config/destinations.json` — groups: `europe_short_haul`, `europe_long_haul`, `intercontinental_asia`, `intercontinental_south_america`. Each group is a list of `{iata, city, category}` entries.
- `config/wishlist.json` — an array of `{iata, city, category}` entries. Always scanned (within scope), gets the looser wishlist thresholds.

If any required key is missing (from `.env` or `config/settings.json`), STOP and email a failure notice (subject: `⚠️ Travel scan FAILED — config invalid`).

---

## 2. Determine local date and first-Tuesday check

- Use Bash `TZ=<TRAVELLER_TIMEZONE> date +%Y-%m-%d` for the run date (substitute the value read from `.env`; e.g. `TZ=Europe/Dublin`).
- Use `TZ=<TRAVELLER_TIMEZONE> date +%u` for day of week (`2` = Tuesday).
- First Tuesday of the month = day of month is in `[1..7]` AND weekday is Tuesday.
- Store: `run_date`, `is_first_tuesday` (bool). The health email is due when `is_first_tuesday` is true regardless of deal outcomes.

---

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

---

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

For each of the top 5 flight date-pairs, query **all 10 `settings.bundled_sites`** for "`<TRAVELLER_ORIGIN_IATA>` → destination, dates X → Y, 2 adults":

- Record cheapest total per site (normalised per-room, 2 adults).
- Unreachable sites (CAPTCHA / 403 / rate-limited) → log once and treat as "not offered". No retries.
- `package_cheapest_eur = min(all site totals)`; record `package_cheapest_site` and `package_cheapest_url`.

Skip packages entirely for `nights=0` variants (packages generally require ≥2 nights).

### 4d. Pragmatism

You have a ~20-minute soft budget per scope (see "Time budget" near the bottom of this prompt). Skip remaining flight candidates / accommodation lookups / package sites if approaching it. Better to cover every route with 3 candidates than to stall on one route chasing a 6th flight option.

Store everything in `output/current_fares.json` (see step 5).

---

## 5. Build `current_combined_totals_eur` per route, copy settings

For each route in the scan list:

For every date-pair where both flight AND accommodation data exist, compute:

```
diy_total = flight_price + nights × accommodation_price_per_night_eur
```

Also include package totals where available. Collect all DIY totals and all package totals into `current_combined_totals_eur` (a flat list — the evaluator just needs the distribution).

Build `prior_combined_totals_eur` by scanning `history/observations.jsonl` for this destination with `schema == "v2"` only. Take the most recent N = `settings.baseline.baseline_window_observations` (12) rows, extract `best_total_eur` from each. v1 rows (those without a `schema` field, or with v1-style `price_eur`) are **ignored** for combined-total baselines — Phase 2 will be cold for ~4 weeks after v2 rollout (accepted by user).

**Important:** when iterating `history/observations.jsonl`, do not crash on v1 rows. Just skip them for the purpose of combined-total baselines. They remain readable for the bonus flight-only signal in step 11.

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

Write the full payload to `output/current_fares.json`.

---

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

---

## 7. Sanity-check at your discretion

You are free (and encouraged) to verify any combined-total calculation by calling the helper directly:

```bash
python traveller_math.py percentile 15 100.5,112.0,125.0,140.0,150.0
python traveller_math.py median 140.0,150.0,160.0,170.0
```

Do this especially for wishlist routes or any surprising deal. If a verdict looks wrong, re-check the `output/current_fares.json` input before trusting the output.

**Package prices are trusted from site output** — do not apply any math sanity check to them. If a package total looks wildly off in practice, revisit in a follow-up spec iteration.

---

## 8. Append observations to `history/observations.jsonl`

For each route that got a non-skipped verdict, append **one** JSONL row — the best date-pair (the one whose total matches `best_combined_eur`). Pull the winning detail from `fare_details`.

v2 schema (newline-separated, one per route — example uses `DUB`/EUR field names; substitute `origin` with your `TRAVELLER_ORIGIN_IATA`, and note the `_eur` suffixes are historical schema identifiers — values are always in `TRAVELLER_CURRENCY`):

```json
{"schema": "v2", "run_date": "...", "origin": "DUB", "destination_iata": "ATH", "destination_city": "Athens", "category": "europe_long_haul", "is_wishlist": false, "trip_profile": "europe_long_haul_5_nights", "nights": 5, "departure_date": "2026-06-12", "return_date": "2026-06-17", "flight_price_eur": 110.0, "flight_airline": "Aegean", "flight_stops": 0, "flight_booking_url": "...", "hotel_price_per_night_eur": 85.0, "hotel_sample_size": 9, "hotel_rating_min": 7.8, "hotel_example_name": "...", "hotel_example_booking_url": "...", "airbnb_price_per_night_eur": 62.0, "airbnb_sample_size": 7, "airbnb_rating_min": 4.7, "airbnb_example_name": "...", "airbnb_example_booking_url": "...", "accommodation_source": "airbnb", "accommodation_price_per_night_eur": 62.0, "diy_total_eur": 420.0, "package_cheapest_eur": 510.0, "package_cheapest_site": "loveholidays", "package_cheapest_url": "...", "best_total_eur": 420.0, "best_source": "diy_airbnb", "combined_ceiling_eur": 590.0, "market_p15_combined_eur": 480.0, "baseline_median_combined_eur": null, "was_flagged_as_deal": true, "flag_reason": "best_total 420 ≤ 0.85×p15 (408), Airbnb 27% cheaper than hotel", "phase": 1}
```

For short-haul + SA routes, `airbnb_*` fields are **null** and `accommodation_source = "hotel"`. `best_source` values:

- `"diy_hotel"` — DIY total won, accommodation was a hotel
- `"diy_airbnb"` — DIY total won, accommodation was an Airbnb
- `"package_<site>"` — package won (e.g., `"package_loveholidays"`)

`accommodation_source` MUST be present in every v2 row (never null): it's `"hotel"` whenever the winning accommodation came from Booking.com (including short-haul and SA routes), and `"airbnb"` only for long-haul Europe / Asia when Airbnb beat the hotel median.

Append the single `run_metadata` sentinel row at the end (same as v1):

```json
{"kind": "run_metadata", "schema": "v2", "run_date": "...", "run_started_at": "...", "run_ended_at": "...", "total_routes_queried": 35, "total_api_calls": 0, "deals_flagged": 2, "scope": "europe", "errors": [], "git_commit_sha": null}
```

Append-mode only. Never rewrite the file.

---

## 9. Write the dated markdown report

Write `reports/<run_date>.md`. Template:

```markdown
# Travel Deals Scan — <run_date> (<weekday>)

**Origin:** <TRAVELLER_ORIGIN_IATA>  **Currency:** <TRAVELLER_CURRENCY>  **Scope:** <scope>

## Great deals this week

### Athens (ATH) — €420 / 5 nights (DIY, Airbnb)
- **Dates:** 2026-06-12 → 2026-06-17 (5 nights)
- **Flight:** Aegean, €110 return (direct)
- **Accommodation:** Airbnb €62/night (hotel median was €85/night — Airbnb wins)
- **Package alternative:** loveholidays €510 — DIY beats by €90
- **Phase:** 1 (cold-start)
- **Why it flagged:** best_total 420 ≤ 0.85×p15 (408); Airbnb 27% cheaper than hotel
- **Book flight:** https://...  **Book Airbnb:** https://...

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

---

## 10. Update rotation state

Write `state/rotation.json` with advanced cursors — only advance cursors for categories that were actually scanned in this invocation:

```json
{
  "asia_cursor": <(old + 3) mod len(intercontinental_asia)>,
  "south_america_cursor": <(old + 2) mod len(intercontinental_south_america)>
}
```

- For `scope=europe`, leave the cursors unchanged (no intercontinental categories were scanned).
- For `scope=intercontinental` or `scope=all`, advance both cursors.

Use `json.dumps(..., indent=2)` formatting (pretty-printed).

---

## 11. Filter math-verdicts to REAL deals (with reasoning)

The `traveller_math.py evaluate` script gives you a binary `is_deal` per route based on phase math. **This is a necessary but not sufficient condition for emailing the user.** Before an email goes out, each flagged route MUST also have a compelling human-readable reason.

For each route where `is_deal == true`, build a **reason** using this extended ladder (in order of preference):

1. **All-time low for combined trip cost** — scan v2 rows in `history/observations.jsonl`. If `best_total_eur` is the lowest ever recorded `best_total_eur` for this `destination_iata`, cite: "all-time low combined total — previous best was €X on YYYY-MM-DD".
2. **Well below recent combined-total baseline** — if ≥4 v2 priors exist for this route (Phase 2+), and `best_total_eur` is ≥30% below `baseline_median_combined_eur`, cite: "30%+ below your 12-week combined-total median of €X".
3. **Well below the combined-total p15 market reference** — if the math flagged it for Phase 1, cite: "bottom-15% of currently-listed combined totals (p15=€X, best=€Y, ≥15% cheaper)".
4. **Package beats DIY by ≥ €X** — if `best_source` starts with `"package_"` AND beats the cheapest DIY total by ≥ 15% OR ≥ €50 (whichever is smaller), cite: "package via <site> beats DIY by €X".
5. **Airbnb beats hotel by ≥ €X** — only for applicable categories. If `accommodation_source == "airbnb"` AND Airbnb beats the hotel median by ≥ 20%, cite: "Airbnb 20%+ cheaper than hotels for this stay". Bonus reason — do not flag solely on this.
6. **Flight alone is -X% vs 12-week flight-only median** — secondary signal from v1 history. If this destination has ≥4 v1 rows (historical flight-only observations) and the new `flight_price_eur` is ≥20% below the v1 flight-only median, cite: "flight alone is -X% vs your 12-week flight-only median of €Y". **Never the sole reason** — use as a bonus to reinforce one of reasons 1–3.
7. **Same-day round trip feasible and flight <€40** — specific to 0-night short-haul. Cite: "same-day round trip works — €X flight, home by night".
8. **Seasonally striking** — use general knowledge of typical travel prices. "Unusual for peak season" is valid; "cheap" alone is not.
9. **Wishlist** — never a reason by itself. Lowers the bar for reasons 1–3 (handled by math via looser thresholds).

**If you cannot cite a specific, concrete reason from 1–8, DO NOT include the route in the email.** Demote to "Routes scanned (no compelling deal)". A route merely under the ceiling is NOT a deal. A route being cheap when history has only 0–2 prior combined-total observations is NOT confidently a deal — it's a data point.

---

## 12. Compose the email

- **Subject:** `✈️ N travel deals this week — <top-deal-city> <TRAVELLER_CURRENCY><total> <reason-tag>` where `<reason-tag>` is a short marker like "all-time low", "package wins", "Airbnb wins", "seasonal", or "-30% vs baseline". If N=0, no email (unless it's a monthly health email day).
- **Greeting:** open the body with `Hi <TRAVELLER_NAME>,` (substitute the value from `.env`; if empty or blank, use `Hi there,`).
- **Body:** one block per deal. Each block MUST contain:
  - City + IATA
  - Best total, dates, nights
  - Flight leg (airline, stops, price)
  - Accommodation leg (source + price per night, including sample size)
  - Package alternative (site + total, or "no package beat DIY")
  - **"Why this is a deal:"** — the concrete reason from step 11.
  - Book links

**Example email body block (good):**
```
✈️ ATHENS (ATH) — €420 total for 5 nights (DIY)
Jun 12 → Jun 17, Aegean direct €110
Airbnb: €62/night (hotel median €85 — Airbnb wins)
Package via loveholidays: €510 — DIY beats by €90
Why this is a deal: bottom-15% of currently-listed combined totals (p15=€480, best=€420); Airbnb 27% cheaper than hotels for this stay.
→ Book flight: https://...
→ Book Airbnb: https://...
```

**Example email body block (bad, do not send):**
```
✈️ ATHENS — €420
Why: cheap.
```

Email routing — pick exactly one of these outcomes:

- **Both first-Tuesday AND deals exist** → send **one** health email that ALSO includes the deals at the top of the body. Subject: `📊 Travel scan monthly health — <Month Year>`.
- **First-Tuesday, no deals** → send health email. Subject: `📊 Travel scan monthly health — <Month Year>`. Body: run count this past month + deal count + errors, from `history/observations.jsonl`'s `run_metadata` rows.
- **Not first-Tuesday, deals exist** → send deal email with the subject format above.
- **Not first-Tuesday, no deals** → send nothing.

Recipient is `TRAVELLER_EMAIL` from `.env`. Use `mcp__...__gmail_create_draft` then send, or whatever send primitive the Gmail MCP exposes. After sending, do **not** leave it as a draft — it should go out.

---

## 13. Sanity check: if every route "flagged"

If the math flagged >50% of scanned routes, the cold-start noise is too high (combined totals make this more likely than v1 flight-only because of the extra accommodation variance). Keep only the 3 strongest combined-total deal-reasons and demote the rest. Mention in the report that more routes were in range but needed stronger combined-total signal. Prevents spammy first emails while v2 history builds.

---

## Time budget (soft)

Each scope (europe OR intercontinental) has a **20-minute soft budget**:

- Flights + accommodation + packages across ~15–20 routes × up to 5 date-pairs × up to 10 package sites is a lot.
- When 20 minutes elapses, stop fetching new routes — evaluate what you've got, write the report, email if warranted.
- Partial coverage is better than stalling. Log skipped routes in the report.

When `/weekly-scan` runs both scopes (40-minute total soft budget), do europe first, then intercontinental.

---

## 14. Commit and push

```bash
git add history/observations.jsonl reports/ state/rotation.json
git commit -m "chore(traveller): weekly scan <run_date> — N deals (<scope>)"
```

Pushing to a remote is optional and depends on whether the repo has one. Run `git remote -v` first:

- If a remote is configured, `git push`. If the push is rejected, email a failure notice (subject: `⚠️ Travel scan FAILED — push rejected`).
- If no remote is configured, stop after the commit. Local-only is acceptable for this repo.

---

## Safety

- Never edit `config/` during a scheduled run.
- Never execute any booking action — deep links in emails are for the human.
- Treat all URLs found during scraping with standard link safety. Only trust known aggregator (Google Flights, Skyscanner, Kayak, Momondo), accommodation (Booking.com, Airbnb), package (see `settings.bundled_sites`), and airline domains. Do not click suspicious URLs.
- Keep `output/` ephemeral — don't commit it.

## Failure handling

Any step fails unexpectedly → email a failure notice via Gmail MCP **before** exiting. Subject: `⚠️ Travel scan FAILED — <short reason>`. Body: which step failed, what the error was, and what `output/current_fares.json` contains (if it exists). Do not silently swallow errors.
