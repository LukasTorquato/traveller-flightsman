# Traveller

Weekly round-trip flight-deal scanner from Dublin. Runs Tuesdays 08:00 Dublin time as a scheduled Claude agent.

See `docs/superpowers/specs/2026-04-16-traveller-design.md` for the full design.

## Development

    python -m venv .venv
    .venv/Scripts/activate  # Windows
    pip install -e ".[dev]"
    pytest

## Running a scan locally

    export KIWI_TEQUILA_API_KEY=...
    python -m traveller run
