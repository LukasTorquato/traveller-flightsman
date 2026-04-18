Run the weekly travel deals scan for Dublin round trips.

Read and follow the full runbook at `prompts/weekly-scan.md` from start to finish. Do not deviate — that file is the source of truth.

Today's date is used as the `run_date`. Dublin-local time determines whether this is the first Tuesday of the month.

When finished, report back with:
- Number of routes scanned
- Number of deals flagged
- Whether email was sent
- Git commit SHA
