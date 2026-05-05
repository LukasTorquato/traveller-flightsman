# Running the weekly scan in Claude Code

This routine runs inside Claude Code — no external cron, no remote scheduled agent.

## One-time setup
1. Clone this repo with submodules: `git clone --recurse-submodules <repo-url>`. If you already cloned, run `git submodule update --init runtime` to fetch the private `traveller-runtime` data repo.
2. Ensure Python 3.12+ is on PATH (the math helper needs it).
3. Install dev deps if you plan to run tests: `pip install -e ".[dev]"`.
4. Populate `config/wishlist.json` with your real dream destinations. Each entry needs a `category` field matching one of: `europe_short_haul`, `europe_long_haul`, `intercontinental_asia`, `intercontinental_south_america`.
5. Connect the Gmail MCP to your account inside Claude Code (one-time OAuth).
6. Make sure both this repo and the `runtime/` submodule have remotes configured (`git remote -v` in each) if you want commits pushed automatically.

## Weekly invocation

You have three slash commands available, all following `prompts/weekly-scan.md`:

| Command | Scope | Runtime estimate |
|---|---|---|
| `/weekly-scan` | Both (Europe + Intercontinental) | ~30-40 min |
| `/weekly-scan-europe` | Europe only | ~15-20 min |
| `/weekly-scan-intercontinental` | Asia + South America only | ~15-20 min |

Use the canonical `/weekly-scan` if you want one combined email + one commit covering everything. Use the split commands if you want to run them at different times, or if the combined run is timing out.

## Automated invocation via /loop (optional)
If you want weekly cadence without a manual trigger:

    /loop 7d /weekly-scan

Or use the scheduled-tasks MCP if you prefer a cron-style trigger.

## Verifying each run
- `git log --oneline` (parent repo) should show a new `chore(traveller): weekly scan ...` commit per invocation, bumping the `runtime/` submodule pointer.
- `cd runtime && git log --oneline` should show a matching `chore: weekly scan ...` commit with the actual data changes.
- `runtime/reports/YYYY-MM-DD.md` should exist.
- `runtime/history/observations.jsonl` should grow by one `run_metadata` row per run (plus observation rows per route).
- Your inbox should have an email if deals passed the reasoning ladder, or no email if none did.

## Silent-failure check
On the **first run of each calendar month** (whichever day of the week that lands on), you get a `📊 Travel scan monthly health` email regardless of deal outcomes. If that email doesn't arrive after a scan early in a new month, the routine has likely broken — check `runtime/history/observations.jsonl` `run_metadata` rows for the last run date.

## Data sources used
- **Flights:** WebSearch / WebFetch across Google Flights, Skyscanner, Kayak, airline-direct deal pages (Ryanair, Aer Lingus).
- **Hotels:** Booking.com (quality floor: rating >= 7.5, >= 100 reviews, top 10 -> median of cheapest 3).
- **Airbnb:** for `europe_long_haul` and `intercontinental_asia` only (quality floor: rating >= 4.5, >= 50 reviews, "Entire place" only, same sampling rule as hotels).
- **Bundled packages:** loveholidays, Jet2 Holidays, TUI, easyJet Holidays, On the Beach, Expedia, Booking.com Packages, Kayak Packages, Trivago Packages, Holiday Pirates.

Some sites will be blocked / CAPTCHA'd on any given run; Claude treats these as "not offered" and moves on. No retries.
