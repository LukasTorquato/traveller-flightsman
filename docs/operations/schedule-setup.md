# Scheduled-task setup

One-time setup for the Tuesday 08:00 Dublin-time run.

## Prerequisites
- Project repo pushed to GitHub (private or public)
- `KIWI_TEQUILA_API_KEY` available to the scheduled environment (via secrets)
- Gmail MCP connected to the account that should send the email
- `scheduled-tasks` MCP available in the Claude Code / Cowork environment

## Registering the task

From a Claude Code session in this repo, run:

"Use the scheduled-tasks MCP (`mcp__scheduled-tasks__create_scheduled_task`) to create a weekly task with:
- **Name:** `traveller-weekly-scan`
- **Cron:** `0 7 * * 2`   (Tuesday 07:00 UTC = 08:00 Dublin during BST, 07:00 during GMT — see note)
- **Prompt:** the full contents of `prompts/weekly-scan.md`
- **Working directory:** this repo"

### Timezone note
Ireland observes BST (UTC+1) from late March through late October, and GMT (UTC+0) the rest of the year. The cron above fires at **07:00 UTC** year-round, which is:
- **08:00 Dublin during BST** ✓
- **07:00 Dublin during GMT** (one hour earlier than target — acceptable for a weekly flight-deal scan)

If precise 08:00 Dublin year-round is required, use a timezone-aware cron (e.g. `0 8 * * 2 Europe/Dublin`) if the scheduled-tasks MCP supports it.

## Verifying
After creation, use `mcp__scheduled-tasks__list_scheduled_tasks` to confirm `traveller-weekly-scan` is registered and shows a next-fire time in the future.

## Manually triggering a dry run
Run locally first to confirm everything works:

```bash
export KIWI_TEQUILA_API_KEY=your_key
python -m traveller run
cat output/email.json
```

Then pass the Tuesday prompt through Claude once as a manual rehearsal before the first real Tuesday.
