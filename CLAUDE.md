# Traveller — Claude Code Project Instructions

This repo is a weekly flight-deal scanner for the repo owner. The only routine it runs is the **weekly scan** — everything the scan does is defined in `prompts/weekly-scan.md`, which is invoked via the `/weekly-scan` slash command. User-specific settings (email, origin airport, currency, timezone, name) live in `.env` at the repo root — see `.env.example` for the template.

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
| "cheap flights from the configured `TRAVELLER_ORIGIN_IATA`" (generic) | `/weekly-scan` (both)           |

Don't improvise the scan — always delegate to the relevant slash command, which reads `prompts/weekly-scan.md` with the appropriate `scope` argument.

## Editing config vs running the scan

- If the user asks to **edit the wishlist, destinations, or settings**, edit the relevant file under `config/` directly. These are JSON files with schemas documented in the design spec (`docs/superpowers/specs/2026-04-16-traveller-design.md` — historical) and the prompt.
- If the user asks to **review a past scan**, look at `runtime/reports/YYYY-MM-DD.md` and `runtime/history/observations.jsonl`.
- If the user asks to **reset history or rotation state**, confirm before deleting anything and do it with explicit `rm` / `git rm` commands inside the `runtime/` submodule.

## Runtime data lives in a submodule

The `runtime/` directory is a private git submodule (`traveller-runtime` repo) holding `history/`, `reports/`, and `state/`. The public traveller repo only records the submodule pointer; the actual data is private. After a scan, commits happen inside `runtime/` first (push to private remote), then the parent repo bumps its submodule pointer. To pull a fresh clone with data, use `git clone --recurse-submodules` or run `git submodule update --init` after cloning.

## Boundaries

- Never send an email outside of a scan run — the scan decides when to email.
- Never make bookings — all deep links in reports are for the human.
- Never edit `runtime/history/observations.jsonl` to fake history — this is an audit trail.
