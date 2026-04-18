# Traveller

Weekly round-trip flight-deal scanner for Dublin. Runs inside **Claude Code** as a slash-command routine — no servers, no API keys, just the prompt at `prompts/weekly-scan.md`.

## What it does

Every Tuesday (or when you invoke `/weekly-scan`):

1. Claude Code searches the web for cheap round-trip fares from DUB to ~30 destinations (Europe + rotating intercontinental picks)
2. Compares each route against a tiered evaluator (Phase 1 cold-start → Phase 2 baseline → Phase 3 hybrid)
3. Appends observations to `history/observations.jsonl`
4. Writes a dated markdown report
5. Emails you only if a great deal was found
6. Commits the new history + report

The prompt (`prompts/weekly-scan.md`) is the source of truth. Claude drives everything; `traveller_math.py` is a stdlib-only calculator Claude calls when it wants to verify its own arithmetic.

## Quick start

1. Read and edit `config/wishlist.json` to add real destinations.
2. Make sure Gmail MCP is connected in Claude Code.
3. Open the repo in Claude Code and run `/weekly-scan`.

See `docs/operations/schedule-setup.md` for full setup.

## Project layout

- `prompts/weekly-scan.md` — the runbook Claude follows (THE product)
- `.claude/commands/weekly-scan.md` — slash-command entry point
- `config/` — destinations, wishlist, thresholds
- `traveller_math.py` — validation calculator (percentile / median / evaluate)
- `tests/test_traveller_math.py` — tests for the calculator
- `history/observations.jsonl` — append-only scan history
- `reports/YYYY-MM-DD.md` — per-run markdown reports
- `state/rotation.json` — intercontinental rotation cursor
- `docs/superpowers/specs/` — original design doc (historical)
- `docs/superpowers/plans/` — original implementation plan (historical)

## Running the math helper standalone

    python traveller_math.py percentile 15 40,50,60,70,80
    python traveller_math.py median 40,50,60,70
    python traveller_math.py evaluate input.json

## Running the tests

    pip install -e ".[dev]"
    pytest
