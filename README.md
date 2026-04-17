# Traveller

Weekly round-trip flight-deal scanner. Runs Tuesdays at 08:00 Dublin time as a scheduled Claude agent, emails only when it finds a great deal.

See [the design spec](docs/superpowers/specs/2026-04-16-traveller-design.md) for the full rationale.

## What it does

Every Tuesday:
1. Queries Kiwi Tequila + Ryanair for round-trip fares from DUB to ~35 destinations
2. Evaluates each result against a tiered deal logic (Phase 1 cold-start → Phase 2 baseline → Phase 3 hybrid)
3. Appends observations to `history/observations.jsonl`
4. Writes `reports/YYYY-MM-DD.md`
5. Emails you only if a great deal was found
6. Commits and pushes the new history + report
7. On the first Tuesday of each month, sends a terse "I'm alive" health email regardless of deals

## Development

```bash
python -m venv .venv
source .venv/Scripts/activate  # Windows
pip install -e ".[dev]"
pytest -v
```

## Local dry run

```bash
export KIWI_TEQUILA_API_KEY=your_kiwi_key
python -m traveller run
cat output/email.json
```

## Configuration

- `config/settings.json` — thresholds, ceilings, windows
- `config/destinations.json` — curated Europe + intercontinental pool
- `config/wishlist.json` — "track harder" list (edit to add dream destinations)

Edit these directly. Every run re-reads them.

## Scheduled run

See [docs/operations/schedule-setup.md](docs/operations/schedule-setup.md).

## History → Excel (optional)

```bash
python scripts/jsonl_to_xlsx.py history/observations.jsonl history.xlsx
```

## When to look at the data

- Weekly deal emails are auto-generated — act on them if you want to travel
- Monthly health email (1st Tuesday): confirms the routine is alive
- If you don't get a health email on the expected day, the routine has broken — check `history/observations.jsonl` via `git log`
