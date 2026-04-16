# Traveller — Weekly Round-Trip Deal Scanner

**Design spec**
**Date:** 2026-04-16
**Status:** Approved for planning
**Owner:** Lukas (Dublin, IE)

---

## 1. Problem statement

Lukas is based in Dublin and wants passive awareness of **great deals** on round-trip flights:

- **Europe** — short breaks to week-long trips (2-7 nights)
- **Intercontinental** — longer trips to Asia and South America (10-21 nights)

The routine runs **every Tuesday morning (08:00 Dublin time)** as a remote scheduled Claude agent. It must stay quiet when no great deal is available and notify only when something worth acting on is found.

## 2. Goals & non-goals

**Goals**
- Automatic weekly scan with zero operator action in the steady state
- High-signal notifications: no noise when the market is normal
- Get smarter over time as price history accumulates per route
- Persistent, auditable record of every scan
- Fail-loud rather than fail-silent

**Non-goals**
- Booking flights (out of scope — user books manually via the deep link)
- Hotel, car, or package deals
- Price alerts for specific user-chosen dates (this is discovery, not tracking)
- Real-time or intra-week alerts — Tuesday-only

## 3. Architecture overview

A remote scheduled Claude agent fires weekly and performs six steps:

1. Load configuration from the project repo
2. Query the Kiwi Tequila API (+ Ryanair open fares API) for round trips from DUB
3. Evaluate each result against the tiered deal logic
4. Append every observation to the JSONL history file
5. Write a dated markdown report (always, even if empty)
6. Send email via Gmail MCP only if ≥1 great deal was flagged

```
┌─────────────────────────┐
│ scheduled-tasks MCP     │ ← Tuesday 08:00 Dublin
│ (weekly cron trigger)   │
└──────────┬──────────────┘
           ▼
┌─────────────────────────┐
│ Claude agent run        │
│ 1. Load config          │
│ 2. Query Kiwi + Ryanair │
│ 3. Evaluate deals       │
│ 4. Persist history      │
│ 5. Write markdown report│
│ 6. Email if deals found │
└──────────┬──────────────┘
           ▼
    ┌──────┴───────┐
    ▼              ▼
┌────────┐   ┌──────────┐
│ Git    │   │ Gmail    │
│ repo   │   │ (MCP)    │
└────────┘   └──────────┘
```

## 4. Data sources

### Primary — Kiwi Tequila API

- **Endpoint:** `https://api.tequila.kiwi.com/v2/search`
- **Auth:** API key in request header; free tier covers our volume easily
- **Key parameters:** `fly_from=DUB`, `fly_to=<IATA>`, `date_from`/`date_to`, `nights_in_dst_from`/`nights_in_dst_to`, `curr=EUR`, `sort=price`, `limit=50` (need the full distribution to compute p15 in Phase 1 cold-start)
- **Output:** structured JSON with price, airline, exact dates, number of stops, deep-link booking URL

### Secondary — Ryanair Fares API

- **Endpoint:** `https://services-api.ryanair.com/farfnd/v4/roundTripFares` (public, no auth)
- **Role:** catch Ryanair-specific promo fares that Kiwi occasionally lags on; DUB-specific
- **If unavailable:** continue without Ryanair data; report notes this

### Market-reference query (used for cold-start logic)

For each route we run a wide-window Kiwi query (90 days Europe / 180 days intercontinental, top 50 cheapest). The **15th percentile** of returned prices acts as the market-reference "cheap tail" baseline in Phase 1 before personal history is available.

### Secret handling

- Kiwi API key stored in the scheduled-task's environment, referenced by name from `config/settings.json`
- Never committed to git

### Volume & runtime

Per-run route count (see Section 7 rotation):
- Wishlist: ~5 (user-curated, placeholder for now)
- Europe short-haul: 15
- Europe long-haul: 10
- Intercontinental rotated subset: 5 (out of ~12 total)

Total: **~35 routes per Tuesday run × 1 Kiwi call each + 1 Ryanair batched call ≈ ~36 HTTP calls**. Well within Kiwi Tequila free-tier limits. Expected runtime: **2-5 minutes** including evaluation and git commit.

### Explicitly dropped

- Aer Lingus fare pages — no public JSON API; Kiwi covers Aer Lingus fares generally, just not always the freshest promos
- Playwright scraping of Google Flights / Skyscanner — not available in a remote scheduled Claude context; replaced by Kiwi's own distribution as the market reference

## 5. Storage & history format

### Format choice: **JSONL + Markdown, not spreadsheet**

Rationale:
- Append-only, immutable-friendly (matches user's coding-style rules)
- Trivial for Claude to parse and compute baselines from
- Git diff shows exactly what each run added
- Schema-evolution-friendly (new fields don't break old lines)
- Optional `jsonl_to_xlsx.py` helper is provided for Excel export if wanted

### Repository layout

```
traveller/
├── config/
│   ├── destinations.json       # curated European + intercontinental pool
│   ├── wishlist.json           # "track harder" list
│   └── settings.json           # thresholds, nights ranges, email recipient
├── history/
│   └── observations.jsonl      # append-only, every run writes here
├── reports/
│   ├── 2026-04-21.md           # one markdown file per run (dated)
│   └── ...
├── src/                        # routine code (planned separately)
├── docs/superpowers/specs/     # this design doc lives here
└── README.md
```

### Observation schema (one line of `observations.jsonl`)

```json
{
  "run_date": "2026-04-21",
  "origin": "DUB",
  "destination_iata": "BCN",
  "destination_city": "Barcelona",
  "departure_date": "2026-06-12",
  "return_date": "2026-06-15",
  "nights": 3,
  "price_eur": 48.50,
  "airline": "Ryanair",
  "stops": 0,
  "source": "kiwi",
  "is_wishlist": false,
  "category": "europe_short_haul",
  "market_p15_eur": 62.00,
  "was_flagged_as_deal": true,
  "flag_reason": "price below market_p15 for route",
  "baseline_median_eur": null
}
```

### Run-metadata row

Each run also appends one `run_metadata` line to `observations.jsonl` (distinct shape from observation rows) capturing: run start/end timestamps, total routes queried, total API calls, deals flagged, errors. Enables silent-failure detection.

### Git hygiene

Every scheduled run commits `history/observations.jsonl` + `reports/YYYY-MM-DD.md` with message like `chore(traveller): weekly scan 2026-04-21 — 2 deals`. Git-write access from the remote scheduled agent is a prerequisite to be wired during implementation planning.

## 6. Deal evaluation logic (three phases, per-route)

The phase is determined **per route**, not globally. A popular wishlist route reaches Phase 2 in ~6 weeks; a rarely-scanned intercontinental route may stay Phase 1 for months.

```
Prior observations for route in last 26 weeks:
  < 4 observations   → Phase 1 (market-reference only)
  4–11 observations  → Phase 2 (baseline-driven, market as sanity-check)
  ≥ 12 observations  → Phase 3 (hybrid — both signals must agree)
```

### Phase 1 — Cold-start (market reference)

A single wide-window Kiwi query per route returns top 50 cheapest fare combinations across the allowed date + trip-length space. Both signals are derived from the same response:

1. Kiwi query: wide date window (90 d Europe / 180 d intercontinental) constrained by trip-length (`nights_in_dst_from/to`), sorted by price, `limit=50`
2. Compute **p15** = 15th percentile of the 50 returned prices
3. Let **best_fare** = cheapest single specific-date fare in the response (i.e. the #1 result)
4. **Flag as great deal** if `best_fare.price ≤ p15` **AND** `best_fare.price ≤ category_ceiling`

**Category ceilings (seed values, configurable):**

| Category | Ceiling (EUR return) |
|---|---|
| Europe short-haul | 80 |
| Europe long-haul (Greece, Nordic, Turkey, Canaries, Iceland, Madeira) | 130 |
| Intercontinental Asia | 550 |
| Intercontinental South America | 600 |

Wishlist destinations use **ceiling × 1.3** (more tolerant — user wants to go).

### Phase 2 — Baseline-driven

Once ≥4 observations exist for the route:

1. Compute rolling **baseline = median of last 12 observations** for that route (or all if fewer)
2. **Flag as great deal** if current best price is:
   - **≥25% below baseline** for non-wishlist routes, or
   - **≥15% below baseline** for wishlist routes
3. Sanity cap: price must also be ≤ category ceiling (prevents inflated baseline triggering false positives)

### Phase 3 — Hybrid (mature signal)

Once ≥12 observations exist:

1. Flag as great deal only if **both Phase 1 and Phase 2 conditions fire**:
   - Phase 2: ≥25% / ≥15% below baseline, AND
   - Phase 1: price ≤ market p15

### Edge cases

- **New destination added mid-history** → starts in Phase 1 regardless of global history age
- **API failure for a route** → logged as "skipped"; does not pollute baseline
- **Price spikes/outliers** → baseline uses median (not mean), naturally robust
- **Dates** → stored as ISO `YYYY-MM-DD` in Dublin local date (departure-date terms, not UTC)

## 7. Configuration

### `config/settings.json` (seed values)

```json
{
  "origin_iata": "DUB",
  "currency": "EUR",
  "email_recipient": "lukasmtorquato@gmail.com",
  "search_windows": {
    "europe_short_haul": { "days_ahead_max": 90,  "nights_min": 2,  "nights_max": 7  },
    "europe_long_haul":  { "days_ahead_max": 120, "nights_min": 2,  "nights_max": 7  },
    "intercontinental":  { "days_ahead_max": 240, "nights_min": 10, "nights_max": 21 }
  },
  "category_ceilings_eur": {
    "europe_short_haul": 80,
    "europe_long_haul": 130,
    "intercontinental_asia": 550,
    "intercontinental_south_america": 600
  },
  "wishlist_ceiling_multiplier": 1.3,
  "baseline": {
    "cold_start_p_percentile": 15,
    "baseline_window_observations": 12,
    "phase2_min_discount_pct_non_wishlist": 25,
    "phase2_min_discount_pct_wishlist": 15,
    "phase_thresholds": { "phase1_max_obs": 3, "phase2_max_obs": 11 }
  },
  "kiwi_api_key_env_var": "KIWI_TEQUILA_API_KEY",
  "kiwi_rate_limit_delay_ms": 200
}
```

### `config/destinations.json` (seed pool — user edits freely)

- **Europe short-haul (15):** BCN, CDG, AMS, BER, LIS, MAD, FCO, MXP, VIE, PRG, BRU, CPH, ZRH, WAW, BUD
- **Europe long-haul (10):** ATH, IST, OSL, ARN, HEL, KEF, TLV, SPU, FNC, TFS
- **Intercontinental Asia (7):** BKK, HND, SIN, DEL, KUL, HKG, CGK
- **Intercontinental South America (5):** GRU, GIG, EZE, BOG, LIM

### `config/wishlist.json`

User-curated list of "track harder" destinations. Same schema as `destinations.json` plus a `category` field (referencing the ceiling category) and optional `note`. Every entry is checked every run and uses the 1.3× ceiling and 15% discount threshold.

### Rotation behaviour (keeps runtime sensible)

- **Wishlist:** always checked, every run
- **Europe short-haul:** all ~15 routes, every run
- **Europe long-haul:** all ~10 routes, every run
- **Intercontinental:** rotated — 3 Asia + 2 South-America destinations per run, cycled so each is hit every 2-3 weeks (intercontinental deal windows are wider, so weekly checks aren't needed)

## 8. Outputs

### Markdown report (always written)

Saved to `reports/YYYY-MM-DD.md` with:
- Great deals section (detailed cards per deal)
- Routes scanned table (no deal)
- Routes skipped (errors)
- Run metadata (total routes, API calls, deals, errors, git commit SHA)

### Email (auto-send when ≥1 deal)

**Behaviour:** Option A — auto-send immediately when any deal is flagged. No draft-only training period.

**Subject template:** `✈️ N travel deals this week — <top-deal-city> €<price>, <second> €<price> [⭐ if wishlist]`

**Body:** simple HTML, one block per deal with city, price, dates, airline, phase reasoning, and deep-link to book.

**Sender:** user's Gmail account via connected `gmail_create_draft` (or send tool) MCP.

## 9. Error handling & observability

| Failure | Behaviour | User-visible |
|---|---|---|
| Kiwi 4xx/5xx one route | Log, skip, continue | Listed under "skipped" in report |
| Kiwi 429 rate-limit | Back off 5 s, retry up to 2× | Transparent unless all retries fail |
| Kiwi key missing/invalid | Hard stop, no partial run | Email fires with subject `⚠️ Travel scan FAILED — API key invalid` |
| Ryanair endpoint down | Log, continue | Report notes "Ryanair data unavailable" |
| Git commit fails | Continue; email still fires | Report notes `⚠️ results not persisted to git`; next run recomputes fresh |
| Gmail MCP send fails | Log in agent transcript; observations + report still committed | Detected via monthly health email missing |
| Entire run crashes | scheduled-task logs retain trace | Detected via monthly health email missing |
| Zero deals | Report written, no email | Expected silence |

### Silent-failure guard

- **Monthly "I'm alive" email** — on the first Tuesday of each month, a terse email is sent regardless of deals, summarising: runs this month, deals flagged, critical errors. If this doesn't arrive, the routine is broken — check the git repo.
- **Run-metadata rows in JSONL** — one per run. If `observations.jsonl` hasn't grown in 2+ weeks (detectable via git log), the routine is broken.

### Deliberately out of scope

- No retry queue / background worker — failed Tuesday waits for next Tuesday; flight deals are weekly-fresh anyway
- No email deduplication — if a deal stays on sale across two runs, two emails go out (low impact, simplest logic; can add later if annoying)
- No admin dashboard — git repo + monthly health email is all the observability needed

## 10. Open items for implementation planning

These are intentionally left for the writing-plans phase, not the design:

- **Language/runtime** for the routine (likely Python or Node — pick during planning based on scheduled-task environment)
- **Exact git-write mechanism** for the remote scheduled agent (SSH deploy key vs GitHub fine-grained PAT vs scheduled-tasks built-in repo sync)
- **Gmail MCP send vs draft-then-send** (some Gmail MCP builds only expose `gmail_create_draft`; may need auto-send workaround)
- **Rotation state storage** for intercontinental (needs a small counter somewhere — likely a `state.json` in repo, or derived from `observations.jsonl`)
- **Wishlist seed content** — user to fill with real destinations before first run (currently placeholder)
- **Test strategy** — stub Kiwi responses, assert evaluator correctness across Phase 1/2/3 boundaries

## 11. Success criteria

The routine is considered successful when:

1. It runs automatically every Tuesday at 08:00 Dublin time, unattended, for ≥4 consecutive weeks
2. ≥95% of runs complete without unrecoverable errors
3. Every run appends to `observations.jsonl` and writes `reports/YYYY-MM-DD.md` (committed to git)
4. Deal emails, when they fire, contain accurate price, airline, dates, and working deep-link
5. The monthly health email arrives on schedule for ≥3 consecutive months
6. After ~12 weeks, ≥50% of routes have reached Phase 2 or Phase 3 evaluation

## 12. Future work (explicitly deferred)

- Price-history visualisation (simple chart per route)
- Hotel / car bundle deals
- Per-destination date preferences (e.g., "Tokyo — only in shoulder season")
- Multi-origin support (e.g., scanning from London when already travelling)
- Slack / Discord / Telegram notification channel beyond email
- Mobile push notifications
