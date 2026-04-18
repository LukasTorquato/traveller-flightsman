# Running the weekly scan in Claude Code

This routine runs inside Claude Code — no external cron, no remote scheduled agent.

## One-time setup

1. Clone this repo to your machine.
2. Ensure Python 3.12+ is on PATH (the math helper needs it).
3. Install dev deps if you plan to run tests: `pip install -e ".[dev]"`.
4. Populate `config/wishlist.json` with your real dream destinations.
5. Connect the Gmail MCP to your account inside Claude Code (one-time OAuth).
6. Make sure this repo has a remote configured (`git remote -v`) if you want commits pushed automatically.

## Manual weekly invocation (recommended)

Every Tuesday (or whenever you want to scan), open this repo in Claude Code and run:

    /weekly-scan

Claude follows `prompts/weekly-scan.md` end-to-end. The whole scan takes ~5–10 minutes with web searches.

## Automated invocation via /loop (optional)

If you want it to run automatically on a weekly cadence, you can use Claude Code's `/loop` feature:

    /loop 7d /weekly-scan

(or set a cron equivalent via the scheduled-tasks MCP if you prefer)

## Verifying each run

- `git log --oneline` should show a new `chore(traveller): weekly scan ...` commit.
- `reports/YYYY-MM-DD.md` should exist for every run.
- `history/observations.jsonl` should grow by one `run_metadata` row per run.
- Your inbox should have an email if deals were found, or no email if none.

## Silent-failure check

On the 1st Tuesday of each month, you'll get a `📊 Travel scan monthly health` email. If that email doesn't arrive, the routine has likely broken — check the git log for the last run date.
