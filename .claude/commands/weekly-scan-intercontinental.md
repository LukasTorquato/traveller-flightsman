Run the Intercontinental-only travel deals scan for Dublin round trips.

Read and follow `prompts/weekly-scan.md` from start to finish, but pass the scope parameter `scope: intercontinental`. This limits the scan to:
- `intercontinental_asia` (Bangkok, Tokyo, Singapore, Delhi, Kuala Lumpur, Hong Kong, Jakarta)
- `intercontinental_south_america` (São Paulo, Rio, Buenos Aires, Bogotá, Lima)
- Any wishlist entries whose `category` falls into those two buckets

Trip profile: 10-21 nights (unchanged for intercontinental).

Accommodation:
- Asia: hotel + Airbnb (whichever cheaper with quality floor).
- South America: hotel only (explicit user preference, no Airbnb).

Intercontinental routes use rotation: load `runtime/state/rotation.json`, pick 3 Asia + 2 South America destinations per run, wrapping the cursor. After the scan, write the advanced cursors back.

Time budget: 20 minutes soft cap.

At the end: one report file `runtime/reports/YYYY-MM-DD.md` (intercontinental scope section only), appended observations, updated `runtime/state/rotation.json`, one email (if any deals), one git commit (in the `runtime/` submodule plus a pointer-bump in the parent repo).

Report back with: routes scanned, deals flagged, accommodation-source breakdown, rotation state advance, git commit SHA.
