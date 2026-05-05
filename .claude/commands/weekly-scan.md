Run the full weekly travel deals scan for Dublin round trips — both Europe and Intercontinental scopes.

This is the canonical weekly entry point. It runs `prompts/weekly-scan.md` end-to-end twice with different scope parameters, then produces ONE combined report and ONE git commit.

Scope order (do not reorder):
1. Run the runbook with `scope: europe` — covers `europe_short_haul`, `europe_long_haul`, and any wishlist entries whose `category` falls into those two buckets.
2. Run the runbook with `scope: intercontinental` — covers `intercontinental_asia`, `intercontinental_south_america`, and any wishlist entries in those buckets.

Merge the two scope runs into a single output:
- `runtime/reports/YYYY-MM-DD.md` — one combined report (not two). Group by scope section; total deals flagged across both scopes.
- `runtime/history/observations.jsonl` — append all observation rows from both scopes + ONE final `run_metadata` row covering the combined run.
- `runtime/state/rotation.json` — update cursors from the intercontinental run (the europe run doesn't use rotation).
- Email — if any deals across BOTH scopes, send ONE email combining them. If this is the first scan of the calendar month, send ONE health email combining both.
- `git commit` — one commit covering both scopes.

Today's date is used as the `run_date`. Dublin-local time determines whether this is the first run of the calendar month. Day of week is irrelevant — the user controls scheduling.

When finished, report back with:
- Number of routes scanned (per scope + total)
- Number of deals flagged (per scope + total)
- Accommodation-source breakdown (hotel / airbnb / n/a for same-day)
- Whether email was sent and its subject
- Git commit SHA
