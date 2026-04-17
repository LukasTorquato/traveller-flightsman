# Traveller

Weekly round-trip flight-deal scanner from Dublin. Runs Tuesdays 08:00 Dublin time as a scheduled Claude agent.

See [the design spec](docs/superpowers/specs/2026-04-16-traveller-design.md) for the full design.

## Development

```bash
python -m venv .venv
.venv/Scripts/activate      # Windows
source .venv/bin/activate   # macOS / Linux
pip install -e ".[dev]"
pytest
```

## Running a scan locally

```bash
export KIWI_TEQUILA_API_KEY=...
python -m traveller run
```
