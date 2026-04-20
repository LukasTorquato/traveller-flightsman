# Traveller — Claude Code Project Instructions

This repo is a weekly flight-deal scanner. The only routine it runs is the **weekly scan** — everything the scan does is defined in `prompts/weekly-scan.md`, which is invoked via the `/weekly-scan` slash command.

## Triggering the scan

When the user asks in natural language to:
- "check the travel deals" / "check my flight deals" / "any good flight deals?"
- "run the weekly scan" / "run the travel routine" / "scan for trips"
- "look for Dublin flight deals" / "find cheap flights from Dublin"
- any similar phrasing about travel deals, flights from DUB, or running the scanner

→ Invoke `/weekly-scan`. Don't improvise the scan — follow the slash command, which reads `prompts/weekly-scan.md`.

## Editing config vs running the scan

- If the user asks to **edit the wishlist, destinations, or settings**, edit the relevant file under `config/` directly. These are JSON files with schemas documented in the design spec (`docs/superpowers/specs/2026-04-16-traveller-design.md` — historical) and the prompt.
- If the user asks to **review a past scan**, look at `reports/YYYY-MM-DD.md` and `history/observations.jsonl`.
- If the user asks to **reset history or rotation state**, confirm before deleting anything and do it with explicit `rm` / `git rm` commands.

## Boundaries

- Never send an email outside of a scan run — the scan decides when to email.
- Never make bookings — all deep links in reports are for the human.
- Never edit `history/observations.jsonl` to fake history — this is an audit trail.
