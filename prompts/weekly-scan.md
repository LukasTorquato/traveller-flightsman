# Weekly Travel-Deal Scan

You are running the Traveller weekly scan. The current working directory is the project repo root. Dublin local time is the source of truth for "today".

## Steps

1. **Pull latest changes**

   ```bash
   git pull --ff-only
   ```

2. **Run the scan**

   Ensure `KIWI_TEQUILA_API_KEY` is present in the environment. Then:

   ```bash
   python -m traveller run
   ```

   Expected output: `Scan complete. N deal(s); envelope at output/email.json`.

3. **Check the email envelope**

   Read `output/email.json`. It has the shape:

   ```json
   {
     "should_send": true|false,
     "to": "lukasmtorquato@gmail.com",
     "subject": "...",
     "body_html": "..."
   }
   ```

4. **If `should_send` is `true`, send the email**

   Use the Gmail MCP tool (`mcp__...__gmail_create_draft` then send, or direct send) to send the email with the `to`, `subject`, and `body_html` from the envelope.

5. **Commit and push the new history and report**

   ```bash
   git add history/observations.jsonl reports/ state/rotation.json
   git commit -m "chore(traveller): weekly scan $(date -u +%Y-%m-%d)"
   git push
   ```

6. **Handle failures loudly**

   If `python -m traveller run` exits non-zero, send an email via Gmail MCP with subject `⚠️ Travel scan FAILED` and include stderr in the body. Do not silently swallow the error.

## Safety

- Never edit `config/` during a scheduled run.
- Never execute any booking action — the deep links in the email are for the human.
