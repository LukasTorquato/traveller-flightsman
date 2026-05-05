Run the Europe-only travel deals scan for Dublin round trips.

Read and follow `prompts/weekly-scan.md` from start to finish, but pass the scope parameter `scope: europe`. This limits the scan to:
- `europe_short_haul` (Barcelona, Paris, Amsterdam, etc.)
- `europe_long_haul` (Athens, Istanbul, Oslo, Canaries, etc.)
- Any wishlist entries whose `category` falls into the two buckets above

Trip profiles applied:
- Short-haul: 1-2 nights preferred, same-day (0 nights) allowed if cheapest flight <= 40 EUR, max 3 nights.
- Long-haul Europe: 2-7 nights.

Accommodation:
- Short-haul: hotel only.
- Long-haul Europe: hotel + Airbnb (whichever cheaper with quality floor).

Time budget: 20 minutes soft cap. If approaching the budget, skip remaining routes and flag in report.

At the end: one report file `runtime/reports/YYYY-MM-DD.md` (europe scope section only), appended observations, updated `runtime/state/rotation.json` (irrelevant for europe but leave untouched), one email (if any deals), one git commit (in the `runtime/` submodule plus a pointer-bump in the parent repo).

Report back with: routes scanned, deals flagged, accommodation-source breakdown, git commit SHA.
