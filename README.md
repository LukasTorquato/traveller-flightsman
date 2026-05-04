# Traveller

Weekly round-trip flight + accommodation deal scanner for your configured origin airport (e.g. DUB for Dublin). Runs inside **Claude Code** as a slash-command routine — no servers, no API keys, just the prompt at `prompts/weekly-scan.md` and a small math helper.

## What it does
Whenever you (or your scheduler) invoke the slash command:
1. Claude Code web-searches for cheap round-trip fares from your configured origin (e.g. DUB for Dublin) to ~30 destinations (Europe + rotating intercontinental picks)
2. For each route, also fetches hotel prices (always) and **Airbnb** prices (for long-haul Europe + Asia only) — picks the cheapest qualifying accommodation that meets a quality floor
3. Fetches **10 bundled-package sites** (loveholidays, Jet2, TUI, easyJet Holidays, On the Beach, Expedia, Booking.com Packages, Kayak, Trivago, Holiday Pirates) and compares DIY vs package totals
4. Evaluates combined (flight + accommodation) totals against a tiered deal-logic (Phase 1 cold-start → Phase 2 baseline → Phase 3 hybrid)
5. Appends observations to `history/observations.jsonl`
6. Writes a dated markdown report
7. Emails you only if a deal passes the strict reasoning ladder (all-time low, baseline drop, package-beats-DIY, Airbnb-beats-hotel, etc.) — silence is a feature
8. Commits the new history + report

The prompt (`prompts/weekly-scan.md`) is the source of truth. Claude drives everything; `traveller_math.py` is a stdlib-only calculator Claude calls when it wants to verify its own arithmetic.

## Slash commands
- `/weekly-scan` — runs both Europe and Intercontinental scopes back-to-back, produces one combined report + one commit (canonical)
- `/weekly-scan-europe` — Europe only (short-haul + long-haul + EU wishlist)
- `/weekly-scan-intercontinental` — Asia + South America only (plus intercontinental wishlist)

You can also just say "check my travel deals" in natural language — `CLAUDE.md` routes the right slash command.

## Trip profiles
- **Europe short-haul** — 1-2 nights preferred, same-day (0 nights) allowed if flight <= 40 EUR, max 3 nights. Hotel only.
- **Europe long-haul** — 2-7 nights. Hotel + Airbnb.
- **Intercontinental Asia** — 10-21 nights. Hotel + Airbnb.
- **Intercontinental South America** — 10-21 nights. Hotel only (explicit preference).

Departure-day bias: Mon/Tue/Fri/Sat/Sun preferred; Wed/Thu avoided.

## Quick start
1. Copy `.env.example` to `.env` and fill in your email, origin airport, currency, timezone, and name.
2. Edit `config/wishlist.json` to add your real dream destinations — each entry needs a `category` field matching one of the four profiles below.
3. Connect the Gmail MCP in Claude Code (one-time OAuth).
4. Open the repo in Claude Code and run `/weekly-scan`.

See `docs/operations/schedule-setup.md` for full setup.

## Project layout
- `.env.example` — template for user-specific settings (email, origin airport, currency, timezone, name)
- `LICENSE` — MIT
- `prompts/weekly-scan.md` — the runbook Claude follows (THE product)
- `.claude/commands/weekly-scan*.md` — slash-command entry points
- `config/` — destinations, wishlist, thresholds, trip profiles, quality floors
- `traveller_math.py` — validation calculator (percentile / median / evaluate, supports both v1 flight-only and v2 combined-total schemas)
- `tests/test_traveller_math.py` — tests for the calculator
- `history/observations.jsonl` — append-only scan history (v1 and v2 rows mixed; `schema` field distinguishes)
- `reports/YYYY-MM-DD.md` — per-run markdown reports
- `state/rotation.json` — intercontinental rotation cursor
- `docs/superpowers/specs/` — original design + hotels/packages extension spec
- `docs/superpowers/plans/` — implementation plans (historical)

## Running the math helper standalone
    python traveller_math.py percentile 15 40,50,60,70,80
    python traveller_math.py median 40,50,60,70
    python traveller_math.py evaluate input.json

Input JSON accepts either legacy flight-only schema (`current_fares_eur`, `prior_prices_eur`) or v2 combined-total schema (`current_combined_totals_eur`, `prior_combined_totals_eur`, `combined_ceiling_eur`). Output key names match the input schema.

## Running the tests
    pip install -e ".[dev]"
    pytest

## Why no email?
Philosophy: *"silence on a scan day with no outstanding deal is a feature."* Every email must answer the question *"why is this one noteworthy?"* with a concrete reason (all-time low, baseline drop, package wins, Airbnb wins, seasonal quirk, etc.). If there's no compelling reason, no email. Day of week never gates email — schedule the scan whenever suits you.

## License
MIT. See `LICENSE`.
