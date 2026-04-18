# Traveller Weekly Scan

You are running the weekly round-trip flight-deal scan for Lukas, based in Dublin (DUB).

Today is Tuesday (or user-triggered). Your goal: find great deals on round-trip flights from DUB, flag only the interesting ones, and email Lukas if any. Stay silent if none.

This prompt is self-contained. Follow every step in order. The working directory is the repo root.

---

## Prerequisites to verify before starting

Before doing anything else, check all of the following. If any fails, STOP and email a failure notice via Gmail MCP (subject: `⚠️ Travel scan FAILED — <short reason>`).

- Working directory is the traveller project repo root (has `prompts/weekly-scan.md` and `traveller_math.py`).
- `config/settings.json`, `config/destinations.json`, `config/wishlist.json` all exist and parse as valid JSON.
- `git status` is clean (no uncommitted changes before we start).
- `python traveller_math.py percentile 15 40,50,60` prints a number (~43.0). Script is runnable.
- The Gmail MCP is connected in this Claude Code session.

Note: `KIWI_TEQUILA_API_KEY` is **not** required. Web search is the data source now.

---

## 1. Load configuration

Read all three config JSONs into working memory:

- `config/settings.json` — must contain at minimum: `origin_iata`, `currency`, `email_recipient`, `search_windows`, `category_ceilings_eur`, `baseline`, `cold_start_p_percentile`, `phase1_max_obs`, `phase2_max_obs`, `phase2_min_discount_pct_non_wishlist`, `phase2_min_discount_pct_wishlist`, `wishlist_ceiling_multiplier`.
- `config/destinations.json` — groups like `europe_short_haul`, `europe_long_haul`, `intercontinental_asia`, `intercontinental_south_america`. Each group is a list of `{iata, city, category}` entries.
- `config/wishlist.json` — an array of `{iata, city, category}` entries. Always scanned, gets the looser wishlist thresholds.

If any required key is missing, STOP and email a failure notice (subject: `⚠️ Travel scan FAILED — config invalid`).

---

## 2. Determine Dublin-local date and first-Tuesday check

- Use Bash `TZ=Europe/Dublin date +%Y-%m-%d` for the run date.
- Use `TZ=Europe/Dublin date +%u` for day of week (`2` = Tuesday).
- First Tuesday of the month = day of month is in `[1..7]` AND weekday is Tuesday.
- Store: `run_date`, `is_first_tuesday` (bool). The health email is due when `is_first_tuesday` is true regardless of deal outcomes.

---

## 3. Build the scan list

- Start with `config/wishlist.json` (every entry, marked `is_wishlist=true`).
- Add `destinations.europe_short_haul` (all).
- Add `destinations.europe_long_haul` (all).
- Rotated intercontinental picks:
  - Read `state/rotation.json`. If missing, default `{"asia_cursor": 0, "south_america_cursor": 0}`.
  - Take **next 3 Asia** destinations starting at `asia_cursor` (wrap around).
  - Take **next 2 South America** destinations starting at `south_america_cursor` (wrap around).
- Dedup by IATA. Wishlist entries win over regular destinations (keep `is_wishlist=true`).

Each route in the scan list should carry: `iata`, `city`, `category`, `is_wishlist`.

---

## 4. For each route: fetch current fares via web search

Use `WebSearch` + `WebFetch` to find the cheapest round-trip fare from DUB to each destination within the appropriate window:

- `europe_short_haul` / `europe_long_haul`: **next 90–120 days**, **2–7 nights**.
- `intercontinental_*`: **next 240 days**, **10–21 nights**.

Good starting queries:

- `"cheapest round trip Dublin to Barcelona June 2026"` → open top Google Flights / Skyscanner / Kayak links
- Airline-direct deals pages: `https://www.ryanair.com/ie/en/cheap-flight-deals`, `https://www.aerlingus.com/plan-and-book/sale-and-offers/`, etc.

For each route, collect **5–20 distinct fare observations**. Each observation needs at minimum:

- `price_eur` (float)
- `departure_date` (YYYY-MM-DD)
- `return_date` (YYYY-MM-DD)
- `nights` (int)
- `airline` (string)
- `booking_url` (string)

If you can only find 1–2 fares for a route, that's fine — p15 will just be less meaningful. If you can find NONE after a good-faith effort (2 queries + 2 fetches), mark the route as skipped with a reason. Don't pad with fake numbers.

**Store everything** in `output/current_fares.json` with the exact `evaluate` input schema — see step 6. Include ALL fares per route in `current_fares_eur` (the distribution is needed for p15), plus keep the full fare records in a sibling `fare_details` array per route so step 8 can write the best-fare metadata.

Shape:

```json
{
  "routes": [
    {
      "destination_iata": "BCN",
      "destination_city": "Barcelona",
      "is_wishlist": false,
      "category": "europe_short_haul",
      "current_fares_eur": [48.5, 62.0, 75.0, 80.0, 90.0],
      "prior_prices_eur": [],
      "fare_details": [
        {"price_eur": 48.5, "departure_date": "2026-06-12", "return_date": "2026-06-15", "nights": 3, "airline": "Ryanair", "booking_url": "https://..."},
        ...
      ]
    }
  ],
  "settings": { ... filled in step 5 ... }
}
```

---

## 5. Build `prior_prices_eur` per route from history, and copy settings

- Read `history/observations.jsonl` line by line. Skip `run_metadata` rows (`kind=="run_metadata"`).
- For each route in the scan list, filter observations to the same `destination_iata`, order by `run_date` descending, take the most recent N = `baseline.baseline_window_observations` (default 12).
- Extract `price_eur` from each into the `prior_prices_eur` array for that route.
- If `history/observations.jsonl` doesn't exist or is empty, `prior_prices_eur=[]` for every route.
- Then copy the evaluator settings into `output/current_fares.json.settings`:

```json
{
  "cold_start_p_percentile": <from settings.json>,
  "phase1_max_obs": <from settings.json>,
  "phase2_max_obs": <from settings.json>,
  "phase2_min_discount_pct_non_wishlist": <from settings.json>,
  "phase2_min_discount_pct_wishlist": <from settings.json>,
  "ceilings_eur": <settings.category_ceilings_eur>,
  "wishlist_ceiling_multiplier": <from settings.json>
}
```

Write the full payload to `output/current_fares.json`.

---

## 6. Evaluate with the math helper

Run:

```bash
python traveller_math.py evaluate output/current_fares.json
```

Capture stdout — it's JSON with shape:

```json
{
  "verdicts": [
    {
      "destination_iata": "BCN",
      "phase": 1,
      "is_deal": true,
      "reason": "best 48.50 <= p15 51.20 and <= ceiling 80.00",
      "best_price_eur": 48.5,
      "market_p15_eur": 51.2,
      "baseline_median_eur": null,
      "ceiling_eur": 80.0
    }
  ]
}
```

This is the **source of truth** for which routes flagged.

---

## 7. Sanity-check at your discretion

You are free (and encouraged) to verify any calculation by calling the helper directly:

```bash
python traveller_math.py percentile 15 48.5,62.0,75.0,80.0,90.0
python traveller_math.py median 70.0,80.0,85.0,90.0
```

Do this especially for wishlist routes or any surprising deal. If a verdict looks wrong, re-check the `output/current_fares.json` input before trusting the output.

---

## 8. Append observations to `history/observations.jsonl`

For each route that got a non-skipped verdict, append **one** JSONL row. The row is the best fare for that route + phase metadata. Pull the best fare's details from `fare_details` (the one whose `price_eur == best_price_eur`; if multiple, any of them).

Schema:

```json
{"run_date": "2026-04-21", "origin": "DUB", "destination_iata": "BCN", "destination_city": "Barcelona", "departure_date": "2026-06-12", "return_date": "2026-06-15", "nights": 3, "price_eur": 48.5, "airline": "Ryanair", "stops": 0, "source": "web", "is_wishlist": false, "category": "europe_short_haul", "market_p15_eur": 51.2, "was_flagged_as_deal": true, "flag_reason": "best 48.50 <= p15 51.20", "baseline_median_eur": null, "phase": 1}
```

After all observation rows, append **one** `run_metadata` sentinel row:

```json
{"kind": "run_metadata", "run_date": "2026-04-21", "run_started_at": "2026-04-21T08:00:00+01:00", "run_ended_at": "2026-04-21T08:06:30+01:00", "total_routes_queried": 35, "total_api_calls": 0, "deals_flagged": 2, "errors": [], "git_commit_sha": null}
```

Use append-mode writes. Never rewrite the file.

---

## 9. Write the dated markdown report

Write `reports/<run_date>.md` (ISO date, e.g. `reports/2026-04-21.md`). Template:

```markdown
# Travel Deals Scan — 2026-04-21 (Tue)

**Origin:** DUB  **Currency:** EUR

## Great deals this week

### Barcelona (BCN) — €48.50
- **Dates:** 2026-06-12 → 2026-06-15 (3 nights)
- **Airline:** Ryanair
- **Phase:** 1 (cold-start)
- **Why it flagged:** best 48.50 <= p15 51.20 and <= ceiling 80.00
- **Book:** https://...

(Repeat per flagged deal. If none, write "None this week.")

## Routes scanned (no deal)

| Route | Best price | Phase | Reason |
|-------|-----------|-------|--------|
| AMS   | €95.00    | 1     | best 95.00 above ceiling 80.00 |
| ...   | ...       | ...   | ... |

## Routes skipped (errors)

| Route | Reason |
|-------|--------|
| BKK   | no fares found after 2 queries |

## Run metadata

- **Routes queried:** 35
- **Deals flagged:** 2
- **Errors:** 1 (BKK skipped)
- **Duration:** 6m 30s
```

---

## 10. Update rotation state

Write `state/rotation.json` with advanced cursors:

```json
{
  "asia_cursor": <(old + 3) mod len(intercontinental_asia)>,
  "south_america_cursor": <(old + 2) mod len(intercontinental_south_america)>
}
```

Use `json.dumps(..., indent=2)` formatting (pretty-printed).

---

## 11. Email (conditional)

Pick exactly one of these outcomes:

- **Both first-Tuesday AND deals exist** → send **one** health email that ALSO includes the deals at the top of the body. Subject: `📊 Travel scan monthly health — <Month Year>`.
- **First-Tuesday, no deals** → send health email. Subject: `📊 Travel scan monthly health — <Month Year>`. Body: run count this past month + deal count + errors, from `history/observations.jsonl`'s `run_metadata` rows.
- **Not first-Tuesday, deals exist** → send deal email. Subject: `✈️ N travel deals this week — <cities>` (e.g. `✈️ 2 travel deals this week — Barcelona, Bangkok`).
- **Not first-Tuesday, no deals** → send nothing.

Email body (for deal email) should contain, per deal: city, price, dates, nights, airline, phase, reason, and booking link. Keep it scannable — prefer an HTML table or bullet list. Recipient is `config/settings.json:email_recipient`.

Use `mcp__...__gmail_create_draft` then send, or whatever send primitive the Gmail MCP exposes. After sending, do **not** save the draft as draft — it should go out.

---

## 12. Commit and push

```bash
git add history/observations.jsonl reports/ state/rotation.json
git commit -m "chore(traveller): weekly scan <run_date> — N deals"
git push
```

If the remote rejects the push, that's a failure — email a failure notice (subject: `⚠️ Travel scan FAILED — push rejected`).

---

## Safety

- Never edit `config/` during a scheduled run.
- Never execute any booking action — deep links in emails are for the human.
- Treat all URLs found during scraping with standard link safety. Only trust known aggregator (Google Flights, Skyscanner, Kayak, Momondo) and airline domains. Do not click suspicious URLs.
- Keep `output/` ephemeral — don't commit it.

## Failure handling

Any step fails unexpectedly → email a failure notice via Gmail MCP **before** exiting. Subject: `⚠️ Travel scan FAILED — <short reason>`. Body: which step failed, what the error was, and what `output/current_fares.json` contains (if it exists). Do not silently swallow errors.
