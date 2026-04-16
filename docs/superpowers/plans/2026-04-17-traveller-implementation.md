# Traveller Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a weekly scheduled routine that scans round-trip flight deals from Dublin (DUB) across Europe and select intercontinental destinations, flags only great deals via email, and records every observation in a JSONL history for progressively smarter future detection.

**Architecture:** Python 3.12 package that performs the deterministic work (HTTP fetching, percentile math, baseline median, JSONL persistence, Markdown/Email rendering). A scheduled Claude agent (via the `scheduled-tasks` MCP, Tuesdays 08:00 Dublin time) invokes the package via `python -m traveller`, then uses the connected Gmail MCP to send the email produced by the package and `git` to commit new history + report files. Logic is split into small focused modules following the spec's three-phase deal-evaluation model.

**Tech Stack:** Python 3.12, httpx (HTTP), pydantic v2 (config & schema validation), pytest + pytest-httpx + freezegun (tests), ruff (lint/format), Jinja2 (markdown + email templating), `python-dotenv` (local development).

---

## File Structure

```
traveller/
├── config/
│   ├── settings.json             # thresholds, windows, ceilings, env-var names
│   ├── destinations.json         # curated Europe + intercontinental pool
│   └── wishlist.json             # track-harder list
├── history/                      # generated at runtime; .gitkeep placeholder
│   └── observations.jsonl
├── reports/                      # generated; .gitkeep placeholder
│   └── YYYY-MM-DD.md
├── state/                        # generated; rotation cursor etc.
│   └── rotation.json
├── output/                       # per-run handoff to Claude (not committed)
│   └── email.json                # subject/body/should_send for Gmail MCP
├── prompts/
│   └── weekly-scan.md            # instructions for the scheduled Claude run
├── scripts/
│   ├── init_config.py            # write seed config files on first run
│   └── jsonl_to_xlsx.py          # optional Excel export helper
├── src/
│   └── traveller/
│       ├── __init__.py
│       ├── __main__.py           # entry: `python -m traveller`
│       ├── cli.py                # argparse + dispatch
│       ├── config.py             # load + validate config files
│       ├── models.py             # dataclasses: Fare, Observation, DealFlag, RunResult
│       ├── categories.py         # IATA → category + ceiling lookup
│       ├── rotation.py           # intercontinental rotation cursor
│       ├── sources/
│       │   ├── __init__.py
│       │   ├── kiwi.py           # Kiwi Tequila client
│       │   └── ryanair.py        # Ryanair open fares client
│       ├── evaluator/
│       │   ├── __init__.py
│       │   ├── phase_selector.py # per-route phase from observation count
│       │   ├── phase1.py         # cold-start p15 + ceiling
│       │   ├── phase2.py         # baseline median + discount %
│       │   ├── phase3.py         # hybrid (both signals agree)
│       │   └── dispatcher.py     # route + obs + fares → DealFlag
│       ├── persistence/
│       │   ├── __init__.py
│       │   ├── jsonl_store.py    # append observations + run_metadata
│       │   └── baseline.py       # read-history, compute medians
│       ├── reporter.py           # Markdown report writer
│       ├── emailer.py            # produce output/email.json envelope
│       ├── health.py             # monthly health-email logic
│       └── orchestrator.py       # run(): glue everything together
├── tests/
│   └── (mirror src layout)
├── docs/superpowers/
│   ├── specs/2026-04-16-traveller-design.md
│   └── plans/2026-04-17-traveller-implementation.md  (this file)
├── pyproject.toml
├── ruff.toml
├── pytest.ini
├── .gitignore
├── .env.example
└── README.md
```

---

## Environment Assumption & Task 0 Verification

The remote scheduled Claude agent is assumed to have: shell access (Bash), Python 3.12+, network access, and the Gmail MCP + scheduled-tasks MCP connected. **Task 0** verifies this before any other work begins. If Python isn't available in the scheduled environment, the plan pivots (documented at the end of Task 0).

---

### Task 0: Verify scheduled-runtime environment & scaffold project

**Files:**
- Create: `pyproject.toml`
- Create: `ruff.toml`
- Create: `pytest.ini`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `README.md`
- Create: `src/traveller/__init__.py`
- Create: `tests/__init__.py`
- Create: `history/.gitkeep`, `reports/.gitkeep`, `state/.gitkeep`, `output/.gitkeep`

- [ ] **Step 1: Verify the scheduled environment can run Python**

Run in terminal:
```bash
python --version
pip --version
```
Expected: Python 3.12+ and pip present. If Python isn't available, stop and report: the orchestration must then run entirely through the Claude agent and MCP calls (no Python) — that's a different plan.

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[project]
name = "traveller"
version = "0.1.0"
description = "Weekly round-trip flight-deal scanner from Dublin"
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.27",
    "pydantic>=2.6",
    "jinja2>=3.1",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-httpx>=0.30",
    "freezegun>=1.4",
    "ruff>=0.4",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[project.scripts]
traveller = "traveller.cli:main"
```

- [ ] **Step 3: Create `ruff.toml`**

```toml
line-length = 100
target-version = "py312"

[lint]
select = ["E", "F", "I", "UP", "B", "SIM", "TCH"]
ignore = ["E501"]
```

- [ ] **Step 4: Create `pytest.ini`**

```ini
[pytest]
testpaths = tests
pythonpath = src
addopts = -ra --strict-markers
```

- [ ] **Step 5: Create `.gitignore`**

```
__pycache__/
*.pyc
.venv/
.env
output/*.json
!output/.gitkeep
dist/
build/
*.egg-info/
.pytest_cache/
.ruff_cache/
```

- [ ] **Step 6: Create `.env.example`**

```
# Kiwi Tequila API key — required
KIWI_TEQUILA_API_KEY=your_key_here
```

- [ ] **Step 7: Create minimal `README.md`**

```markdown
# Traveller

Weekly round-trip flight-deal scanner from Dublin. Runs Tuesdays 08:00 Dublin time as a scheduled Claude agent.

See `docs/superpowers/specs/2026-04-16-traveller-design.md` for the full design.

## Development

```
python -m venv .venv
.venv/Scripts/activate  # Windows
pip install -e ".[dev]"
pytest
```

## Running a scan locally

```
export KIWI_TEQUILA_API_KEY=...
python -m traveller run
```
```

- [ ] **Step 8: Create placeholder package files**

`src/traveller/__init__.py`:
```python
__version__ = "0.1.0"
```

`tests/__init__.py`: (empty file)

`history/.gitkeep`, `reports/.gitkeep`, `state/.gitkeep`, `output/.gitkeep`: (empty files, commit the directories)

- [ ] **Step 9: Install deps and verify pytest runs**

```bash
python -m venv .venv
source .venv/Scripts/activate  # or .venv\Scripts\activate on Windows cmd
pip install -e ".[dev]"
pytest
```
Expected: `no tests ran` (no tests yet) — pytest exits clean.

- [ ] **Step 10: Commit**

```bash
git add pyproject.toml ruff.toml pytest.ini .gitignore .env.example README.md src/ tests/ history/.gitkeep reports/.gitkeep state/.gitkeep output/.gitkeep
git commit -m "chore: scaffold traveller project"
```

---

### Task 1: Config models (pydantic)

**Files:**
- Create: `src/traveller/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write failing test for `Settings` model validation**

`tests/test_models.py`:
```python
import pytest
from pydantic import ValidationError
from traveller.models import Settings, SearchWindow, CategoryCeilings, BaselineConfig


def _valid_settings_dict():
    return {
        "origin_iata": "DUB",
        "currency": "EUR",
        "email_recipient": "lukasmtorquato@gmail.com",
        "search_windows": {
            "europe_short_haul": {"days_ahead_max": 90, "nights_min": 2, "nights_max": 7},
            "europe_long_haul": {"days_ahead_max": 120, "nights_min": 2, "nights_max": 7},
            "intercontinental": {"days_ahead_max": 240, "nights_min": 10, "nights_max": 21},
        },
        "category_ceilings_eur": {
            "europe_short_haul": 80,
            "europe_long_haul": 130,
            "intercontinental_asia": 550,
            "intercontinental_south_america": 600,
        },
        "wishlist_ceiling_multiplier": 1.3,
        "baseline": {
            "cold_start_p_percentile": 15,
            "baseline_window_observations": 12,
            "phase2_min_discount_pct_non_wishlist": 25,
            "phase2_min_discount_pct_wishlist": 15,
            "phase_thresholds": {"phase1_max_obs": 3, "phase2_max_obs": 11},
        },
        "kiwi_api_key_env_var": "KIWI_TEQUILA_API_KEY",
        "kiwi_rate_limit_delay_ms": 200,
    }


def test_settings_parses_valid_dict():
    s = Settings.model_validate(_valid_settings_dict())
    assert s.origin_iata == "DUB"
    assert s.currency == "EUR"
    assert s.search_windows["europe_short_haul"].nights_max == 7
    assert s.baseline.phase_thresholds.phase1_max_obs == 3


def test_settings_rejects_missing_required_field():
    d = _valid_settings_dict()
    del d["origin_iata"]
    with pytest.raises(ValidationError):
        Settings.model_validate(d)


def test_settings_rejects_nights_min_gt_max():
    d = _valid_settings_dict()
    d["search_windows"]["europe_short_haul"]["nights_min"] = 10
    d["search_windows"]["europe_short_haul"]["nights_max"] = 5
    with pytest.raises(ValidationError):
        Settings.model_validate(d)
```

- [ ] **Step 2: Run test, verify it fails**

```bash
pytest tests/test_models.py -v
```
Expected: ImportError / ModuleNotFoundError for `traveller.models`.

- [ ] **Step 3: Implement `models.py`**

`src/traveller/models.py`:
```python
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

Category = Literal[
    "europe_short_haul",
    "europe_long_haul",
    "intercontinental_asia",
    "intercontinental_south_america",
]


class SearchWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    days_ahead_max: int = Field(gt=0, le=365)
    nights_min: int = Field(ge=1)
    nights_max: int = Field(ge=1)

    @model_validator(mode="after")
    def _check_nights(self) -> SearchWindow:
        if self.nights_min > self.nights_max:
            raise ValueError("nights_min must be <= nights_max")
        return self


class CategoryCeilings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    europe_short_haul: float = Field(gt=0)
    europe_long_haul: float = Field(gt=0)
    intercontinental_asia: float = Field(gt=0)
    intercontinental_south_america: float = Field(gt=0)


class PhaseThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phase1_max_obs: int = Field(ge=0)
    phase2_max_obs: int = Field(ge=0)


class BaselineConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cold_start_p_percentile: float = Field(gt=0, lt=100)
    baseline_window_observations: int = Field(gt=0)
    phase2_min_discount_pct_non_wishlist: float = Field(ge=0, le=100)
    phase2_min_discount_pct_wishlist: float = Field(ge=0, le=100)
    phase_thresholds: PhaseThresholds


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    origin_iata: str = Field(min_length=3, max_length=3)
    currency: str = Field(min_length=3, max_length=3)
    email_recipient: str
    search_windows: dict[str, SearchWindow]
    category_ceilings_eur: CategoryCeilings
    wishlist_ceiling_multiplier: float = Field(gt=1.0)
    baseline: BaselineConfig
    kiwi_api_key_env_var: str
    kiwi_rate_limit_delay_ms: int = Field(ge=0)


class Destination(BaseModel):
    model_config = ConfigDict(extra="forbid")
    iata: str = Field(min_length=3, max_length=3)
    city: str


class DestinationPool(BaseModel):
    model_config = ConfigDict(extra="forbid")
    europe_short_haul: list[Destination]
    europe_long_haul: list[Destination]
    intercontinental_asia: list[Destination]
    intercontinental_south_america: list[Destination]


class WishlistEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    iata: str = Field(min_length=3, max_length=3)
    city: str
    category: Category
    note: str = ""


class Wishlist(BaseModel):
    model_config = ConfigDict(extra="forbid")
    wishlist: list[WishlistEntry]


class Fare(BaseModel):
    """A single returned fare from a data source."""
    model_config = ConfigDict(extra="forbid")
    price_eur: float
    departure_date: date
    return_date: date
    nights: int
    airline: str
    stops: int
    source: Literal["kiwi", "ryanair"]
    booking_url: str


class Observation(BaseModel):
    """A single row in observations.jsonl."""
    model_config = ConfigDict(extra="forbid")
    run_date: date
    origin: str
    destination_iata: str
    destination_city: str
    departure_date: date
    return_date: date
    nights: int
    price_eur: float
    airline: str
    stops: int
    source: Literal["kiwi", "ryanair"]
    is_wishlist: bool
    category: Category
    market_p15_eur: Optional[float]
    was_flagged_as_deal: bool
    flag_reason: Optional[str]
    baseline_median_eur: Optional[float]
    phase: Literal[1, 2, 3]


class RunMetadata(BaseModel):
    """One-per-run row distinguishable from observation rows."""
    model_config = ConfigDict(extra="forbid")
    kind: Literal["run_metadata"] = "run_metadata"
    run_date: date
    run_started_at: str
    run_ended_at: str
    total_routes_queried: int
    total_api_calls: int
    deals_flagged: int
    errors: list[str]
    git_commit_sha: Optional[str]


class DealFlag(BaseModel):
    """Result of evaluating a single fare against deal logic."""
    model_config = ConfigDict(extra="forbid")
    is_deal: bool
    phase: Literal[1, 2, 3]
    reason: str
    market_p15_eur: Optional[float]
    baseline_median_eur: Optional[float]
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
pytest tests/test_models.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/traveller/models.py tests/test_models.py
git commit -m "feat(models): pydantic models for config, fares, observations"
```

---

### Task 2: Config loader

**Files:**
- Create: `src/traveller/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing test**

`tests/test_config.py`:
```python
import json
from pathlib import Path

import pytest

from traveller.config import ConfigBundle, load_config


def _write(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj), encoding="utf-8")


def _settings() -> dict:
    return {
        "origin_iata": "DUB", "currency": "EUR",
        "email_recipient": "a@b.com",
        "search_windows": {
            "europe_short_haul": {"days_ahead_max": 90, "nights_min": 2, "nights_max": 7},
            "europe_long_haul": {"days_ahead_max": 120, "nights_min": 2, "nights_max": 7},
            "intercontinental": {"days_ahead_max": 240, "nights_min": 10, "nights_max": 21},
        },
        "category_ceilings_eur": {
            "europe_short_haul": 80, "europe_long_haul": 130,
            "intercontinental_asia": 550, "intercontinental_south_america": 600,
        },
        "wishlist_ceiling_multiplier": 1.3,
        "baseline": {
            "cold_start_p_percentile": 15, "baseline_window_observations": 12,
            "phase2_min_discount_pct_non_wishlist": 25,
            "phase2_min_discount_pct_wishlist": 15,
            "phase_thresholds": {"phase1_max_obs": 3, "phase2_max_obs": 11},
        },
        "kiwi_api_key_env_var": "KIWI_TEQUILA_API_KEY",
        "kiwi_rate_limit_delay_ms": 200,
    }


def _destinations() -> dict:
    return {
        "europe_short_haul": [{"iata": "BCN", "city": "Barcelona"}],
        "europe_long_haul": [{"iata": "ATH", "city": "Athens"}],
        "intercontinental_asia": [{"iata": "BKK", "city": "Bangkok"}],
        "intercontinental_south_america": [{"iata": "GRU", "city": "Sao Paulo"}],
    }


def _wishlist() -> dict:
    return {"wishlist": [
        {"iata": "HND", "city": "Tokyo",
         "category": "intercontinental_asia", "note": "bucket list"}
    ]}


def test_load_config_full_bundle(tmp_path: Path):
    cfg = tmp_path / "config"
    cfg.mkdir()
    _write(cfg / "settings.json", _settings())
    _write(cfg / "destinations.json", _destinations())
    _write(cfg / "wishlist.json", _wishlist())

    bundle = load_config(cfg)
    assert isinstance(bundle, ConfigBundle)
    assert bundle.settings.origin_iata == "DUB"
    assert bundle.destinations.europe_short_haul[0].iata == "BCN"
    assert bundle.wishlist.wishlist[0].city == "Tokyo"


def test_load_config_missing_file(tmp_path: Path):
    cfg = tmp_path / "config"
    cfg.mkdir()
    _write(cfg / "settings.json", _settings())
    with pytest.raises(FileNotFoundError):
        load_config(cfg)
```

- [ ] **Step 2: Run, verify fail**

```bash
pytest tests/test_config.py -v
```
Expected: ImportError for `traveller.config`.

- [ ] **Step 3: Implement `config.py`**

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from traveller.models import DestinationPool, Settings, Wishlist


@dataclass(frozen=True)
class ConfigBundle:
    settings: Settings
    destinations: DestinationPool
    wishlist: Wishlist


def _read_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"config file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_config(config_dir: Path) -> ConfigBundle:
    settings = Settings.model_validate(_read_json(config_dir / "settings.json"))
    destinations = DestinationPool.model_validate(_read_json(config_dir / "destinations.json"))
    wishlist = Wishlist.model_validate(_read_json(config_dir / "wishlist.json"))
    return ConfigBundle(settings=settings, destinations=destinations, wishlist=wishlist)
```

- [ ] **Step 4: Run tests, verify pass**

```bash
pytest tests/test_config.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/traveller/config.py tests/test_config.py
git commit -m "feat(config): load + validate config bundle"
```

---

### Task 3: Categories & ceiling lookup

**Files:**
- Create: `src/traveller/categories.py`
- Test: `tests/test_categories.py`

- [ ] **Step 1: Write failing test**

`tests/test_categories.py`:
```python
from traveller.categories import category_for_iata, ceiling_for
from traveller.models import CategoryCeilings, DestinationPool


def _pool():
    return DestinationPool.model_validate({
        "europe_short_haul": [{"iata": "BCN", "city": "Barcelona"}],
        "europe_long_haul": [{"iata": "ATH", "city": "Athens"}],
        "intercontinental_asia": [{"iata": "BKK", "city": "Bangkok"}],
        "intercontinental_south_america": [{"iata": "GRU", "city": "Sao Paulo"}],
    })


def _ceilings():
    return CategoryCeilings(
        europe_short_haul=80, europe_long_haul=130,
        intercontinental_asia=550, intercontinental_south_america=600,
    )


def test_category_for_iata_matches_pool():
    pool = _pool()
    assert category_for_iata("BCN", pool) == "europe_short_haul"
    assert category_for_iata("ATH", pool) == "europe_long_haul"
    assert category_for_iata("BKK", pool) == "intercontinental_asia"
    assert category_for_iata("GRU", pool) == "intercontinental_south_america"


def test_category_for_iata_missing_raises():
    import pytest
    pool = _pool()
    with pytest.raises(KeyError):
        category_for_iata("ZZZ", pool)


def test_ceiling_non_wishlist():
    c = _ceilings()
    assert ceiling_for("europe_short_haul", c, is_wishlist=False, multiplier=1.3) == 80


def test_ceiling_wishlist_uses_multiplier():
    c = _ceilings()
    assert ceiling_for("europe_short_haul", c, is_wishlist=True, multiplier=1.3) == 80 * 1.3
```

- [ ] **Step 2: Run, verify fail**

```bash
pytest tests/test_categories.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `categories.py`**

```python
from __future__ import annotations

from traveller.models import Category, CategoryCeilings, DestinationPool


def category_for_iata(iata: str, pool: DestinationPool) -> Category:
    iata_upper = iata.upper()
    for cat_name in (
        "europe_short_haul",
        "europe_long_haul",
        "intercontinental_asia",
        "intercontinental_south_america",
    ):
        for dest in getattr(pool, cat_name):
            if dest.iata.upper() == iata_upper:
                return cat_name  # type: ignore[return-value]
    raise KeyError(f"IATA {iata} not found in destination pool")


def ceiling_for(
    category: Category,
    ceilings: CategoryCeilings,
    *,
    is_wishlist: bool,
    multiplier: float,
) -> float:
    base = getattr(ceilings, category)
    return base * multiplier if is_wishlist else base
```

- [ ] **Step 4: Run tests, verify pass**

```bash
pytest tests/test_categories.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/traveller/categories.py tests/test_categories.py
git commit -m "feat(categories): IATA-to-category + ceiling lookup"
```

---

### Task 4: Kiwi Tequila API client (happy path)

**Files:**
- Create: `src/traveller/sources/__init__.py`
- Create: `src/traveller/sources/kiwi.py`
- Test: `tests/sources/test_kiwi.py`
- Create: `tests/sources/__init__.py`

- [ ] **Step 1: Write failing test with pytest-httpx**

`tests/sources/__init__.py`: (empty)

`tests/sources/test_kiwi.py`:
```python
from datetime import date

import pytest
from pytest_httpx import HTTPXMock

from traveller.sources.kiwi import KiwiClient, KiwiError


def _kiwi_response_json():
    return {
        "data": [
            {
                "price": 48.5,
                "local_departure": "2026-06-12T09:30:00.000Z",
                "local_arrival": "2026-06-12T13:15:00.000Z",
                "nightsInDest": 3,
                "route": [
                    {"airline": "FR", "return": 0},
                    {"airline": "FR", "return": 1, "local_departure": "2026-06-15T10:00:00.000Z"},
                ],
                "airlines": ["FR"],
                "deep_link": "https://www.kiwi.com/deep/BCN-abc",
            },
            {
                "price": 62.0,
                "local_departure": "2026-06-19T07:00:00.000Z",
                "local_arrival": "2026-06-19T10:45:00.000Z",
                "nightsInDest": 5,
                "route": [
                    {"airline": "EI", "return": 0},
                    {"airline": "EI", "return": 1, "local_departure": "2026-06-24T11:00:00.000Z"},
                ],
                "airlines": ["EI"],
                "deep_link": "https://www.kiwi.com/deep/BCN-def",
            },
        ]
    }


def test_kiwi_search_happy_path(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url__contains="api.tequila.kiwi.com/v2/search",
        json=_kiwi_response_json(),
        status_code=200,
    )
    client = KiwiClient(api_key="test-key")
    fares = client.search(
        origin="DUB",
        destination="BCN",
        date_from=date(2026, 6, 1),
        date_to=date(2026, 8, 31),
        nights_min=2,
        nights_max=7,
        limit=50,
    )
    assert len(fares) == 2
    assert fares[0].price_eur == 48.5
    assert fares[0].departure_date == date(2026, 6, 12)
    assert fares[0].return_date == date(2026, 6, 15)
    assert fares[0].nights == 3
    assert fares[0].airline == "FR"
    assert fares[0].source == "kiwi"
    assert fares[0].booking_url.startswith("https://www.kiwi.com/")


def test_kiwi_search_rejects_non_200(httpx_mock: HTTPXMock):
    httpx_mock.add_response(status_code=500, text="oops")
    client = KiwiClient(api_key="test-key")
    with pytest.raises(KiwiError):
        client.search(
            origin="DUB", destination="BCN",
            date_from=date(2026, 6, 1), date_to=date(2026, 8, 31),
            nights_min=2, nights_max=7, limit=50,
        )
```

- [ ] **Step 2: Run, verify fail**

```bash
pytest tests/sources/test_kiwi.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `sources/__init__.py` (empty) and `sources/kiwi.py`**

`src/traveller/sources/__init__.py`: (empty)

`src/traveller/sources/kiwi.py`:
```python
from __future__ import annotations

from datetime import date, datetime
from typing import Any

import httpx

from traveller.models import Fare


class KiwiError(RuntimeError):
    """Raised on any non-2xx response from the Kiwi API."""


_SEARCH_URL = "https://api.tequila.kiwi.com/v2/search"


def _parse_local_date(s: str) -> date:
    """Kiwi returns ISO timestamps like '2026-06-12T09:30:00.000Z'."""
    return datetime.fromisoformat(s.replace("Z", "+00:00")).date()


def _parse_fare(entry: dict[str, Any]) -> Fare:
    dep_date = _parse_local_date(entry["local_departure"])
    ret_leg = next((leg for leg in entry["route"] if leg.get("return") == 1), None)
    if ret_leg is None:
        raise KiwiError("Kiwi entry missing return leg")
    ret_date = _parse_local_date(ret_leg["local_departure"])
    airlines = entry.get("airlines") or []
    airline = airlines[0] if airlines else entry["route"][0].get("airline", "??")
    stops = max(0, len(entry["route"]) - 2)
    return Fare(
        price_eur=float(entry["price"]),
        departure_date=dep_date,
        return_date=ret_date,
        nights=int(entry.get("nightsInDest", (ret_date - dep_date).days)),
        airline=airline,
        stops=stops,
        source="kiwi",
        booking_url=entry["deep_link"],
    )


class KiwiClient:
    def __init__(self, *, api_key: str, timeout_s: float = 20.0):
        if not api_key:
            raise KiwiError("Kiwi API key is empty")
        self._api_key = api_key
        self._timeout_s = timeout_s

    def search(
        self,
        *,
        origin: str,
        destination: str,
        date_from: date,
        date_to: date,
        nights_min: int,
        nights_max: int,
        limit: int = 50,
        currency: str = "EUR",
    ) -> list[Fare]:
        params = {
            "fly_from": origin,
            "fly_to": destination,
            "date_from": date_from.strftime("%d/%m/%Y"),
            "date_to": date_to.strftime("%d/%m/%Y"),
            "nights_in_dst_from": nights_min,
            "nights_in_dst_to": nights_max,
            "curr": currency,
            "sort": "price",
            "limit": limit,
            "flight_type": "round",
        }
        headers = {"apikey": self._api_key, "accept": "application/json"}
        try:
            resp = httpx.get(
                _SEARCH_URL, params=params, headers=headers, timeout=self._timeout_s
            )
        except httpx.HTTPError as exc:
            raise KiwiError(f"Kiwi network error: {exc}") from exc
        if resp.status_code != 200:
            raise KiwiError(
                f"Kiwi {resp.status_code}: {resp.text[:200]}"
            )
        payload = resp.json()
        return [_parse_fare(e) for e in payload.get("data", [])]
```

- [ ] **Step 4: Run tests, verify pass**

```bash
pytest tests/sources/test_kiwi.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/traveller/sources/ tests/sources/
git commit -m "feat(sources): Kiwi Tequila search client with error handling"
```

---

### Task 5: Kiwi rate-limit retry

**Files:**
- Modify: `src/traveller/sources/kiwi.py`
- Modify: `tests/sources/test_kiwi.py`

- [ ] **Step 1: Write failing test for 429 retry**

Append to `tests/sources/test_kiwi.py`:
```python
def test_kiwi_retries_on_429(httpx_mock: HTTPXMock):
    httpx_mock.add_response(status_code=429, text="throttled")
    httpx_mock.add_response(status_code=429, text="throttled")
    httpx_mock.add_response(status_code=200, json=_kiwi_response_json())
    client = KiwiClient(api_key="test-key", backoff_seconds=0.0, max_retries=2)
    fares = client.search(
        origin="DUB", destination="BCN",
        date_from=date(2026, 6, 1), date_to=date(2026, 8, 31),
        nights_min=2, nights_max=7, limit=50,
    )
    assert len(fares) == 2


def test_kiwi_gives_up_after_max_retries(httpx_mock: HTTPXMock):
    for _ in range(3):
        httpx_mock.add_response(status_code=429, text="throttled")
    client = KiwiClient(api_key="test-key", backoff_seconds=0.0, max_retries=2)
    with pytest.raises(KiwiError):
        client.search(
            origin="DUB", destination="BCN",
            date_from=date(2026, 6, 1), date_to=date(2026, 8, 31),
            nights_min=2, nights_max=7, limit=50,
        )
```

- [ ] **Step 2: Run, verify fail**

```bash
pytest tests/sources/test_kiwi.py -v
```
Expected: 2 failures (`TypeError: unexpected keyword argument`).

- [ ] **Step 3: Add retry logic to `KiwiClient`**

Replace the `KiwiClient` class body in `src/traveller/sources/kiwi.py`:
```python
import time


class KiwiClient:
    def __init__(
        self,
        *,
        api_key: str,
        timeout_s: float = 20.0,
        backoff_seconds: float = 5.0,
        max_retries: int = 2,
    ):
        if not api_key:
            raise KiwiError("Kiwi API key is empty")
        self._api_key = api_key
        self._timeout_s = timeout_s
        self._backoff_seconds = backoff_seconds
        self._max_retries = max_retries

    def search(
        self,
        *,
        origin: str,
        destination: str,
        date_from: date,
        date_to: date,
        nights_min: int,
        nights_max: int,
        limit: int = 50,
        currency: str = "EUR",
    ) -> list[Fare]:
        params = {
            "fly_from": origin,
            "fly_to": destination,
            "date_from": date_from.strftime("%d/%m/%Y"),
            "date_to": date_to.strftime("%d/%m/%Y"),
            "nights_in_dst_from": nights_min,
            "nights_in_dst_to": nights_max,
            "curr": currency,
            "sort": "price",
            "limit": limit,
            "flight_type": "round",
        }
        headers = {"apikey": self._api_key, "accept": "application/json"}
        last_status: int | None = None
        last_text: str = ""
        attempts = self._max_retries + 1
        for attempt in range(attempts):
            try:
                resp = httpx.get(
                    _SEARCH_URL, params=params, headers=headers, timeout=self._timeout_s
                )
            except httpx.HTTPError as exc:
                raise KiwiError(f"Kiwi network error: {exc}") from exc
            if resp.status_code == 200:
                return [_parse_fare(e) for e in resp.json().get("data", [])]
            last_status, last_text = resp.status_code, resp.text[:200]
            if resp.status_code == 429 and attempt < attempts - 1:
                time.sleep(self._backoff_seconds)
                continue
            break
        raise KiwiError(f"Kiwi {last_status}: {last_text}")
```

- [ ] **Step 4: Run all kiwi tests, verify pass**

```bash
pytest tests/sources/test_kiwi.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/traveller/sources/kiwi.py tests/sources/test_kiwi.py
git commit -m "feat(sources): retry on 429 with configurable backoff"
```

---

### Task 6: Ryanair fares client

**Files:**
- Create: `src/traveller/sources/ryanair.py`
- Test: `tests/sources/test_ryanair.py`

- [ ] **Step 1: Write failing test**

`tests/sources/test_ryanair.py`:
```python
from datetime import date

from pytest_httpx import HTTPXMock

from traveller.sources.ryanair import RyanairClient, RyanairUnavailable


def _ryanair_response():
    return {
        "fares": [
            {
                "outbound": {
                    "departureAirport": {"iataCode": "DUB", "name": "Dublin"},
                    "arrivalAirport": {"iataCode": "BCN", "name": "Barcelona"},
                    "departureDate": "2026-06-12T09:30:00",
                    "price": {"value": 22.99, "currencyCode": "EUR"},
                },
                "inbound": {
                    "departureAirport": {"iataCode": "BCN", "name": "Barcelona"},
                    "arrivalAirport": {"iataCode": "DUB", "name": "Dublin"},
                    "departureDate": "2026-06-15T18:00:00",
                    "price": {"value": 19.99, "currencyCode": "EUR"},
                },
                "summary": {"price": {"value": 42.98, "currencyCode": "EUR"}},
            }
        ]
    }


def test_ryanair_search_happy_path(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url__contains="services-api.ryanair.com/farfnd/v4/roundTripFares",
        json=_ryanair_response(),
        status_code=200,
    )
    client = RyanairClient()
    fares = client.search(
        origin="DUB",
        destination="BCN",
        date_from=date(2026, 6, 1),
        date_to=date(2026, 8, 31),
        nights_min=2,
        nights_max=7,
    )
    assert len(fares) == 1
    assert fares[0].price_eur == 42.98
    assert fares[0].departure_date == date(2026, 6, 12)
    assert fares[0].return_date == date(2026, 6, 15)
    assert fares[0].nights == 3
    assert fares[0].airline == "Ryanair"
    assert fares[0].source == "ryanair"


def test_ryanair_returns_empty_on_endpoint_down(httpx_mock: HTTPXMock):
    import pytest
    httpx_mock.add_response(status_code=503, text="down")
    client = RyanairClient()
    with pytest.raises(RyanairUnavailable):
        client.search(
            origin="DUB", destination="BCN",
            date_from=date(2026, 6, 1), date_to=date(2026, 8, 31),
            nights_min=2, nights_max=7,
        )
```

- [ ] **Step 2: Run, verify fail**

```bash
pytest tests/sources/test_ryanair.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `sources/ryanair.py`**

```python
from __future__ import annotations

from datetime import date, datetime

import httpx

from traveller.models import Fare


class RyanairUnavailable(RuntimeError):
    """Raised when the Ryanair endpoint is unreachable or returns non-2xx."""


_URL = "https://services-api.ryanair.com/farfnd/v4/roundTripFares"


def _parse_date(s: str) -> date:
    return datetime.fromisoformat(s).date()


class RyanairClient:
    def __init__(self, *, timeout_s: float = 15.0):
        self._timeout_s = timeout_s

    def search(
        self,
        *,
        origin: str,
        destination: str,
        date_from: date,
        date_to: date,
        nights_min: int,
        nights_max: int,
        currency: str = "EUR",
    ) -> list[Fare]:
        params = {
            "departureAirportIataCode": origin,
            "arrivalAirportIataCode": destination,
            "outboundDepartureDateFrom": date_from.isoformat(),
            "outboundDepartureDateTo": date_to.isoformat(),
            "inboundDepartureDateFrom": date_from.isoformat(),
            "inboundDepartureDateTo": date_to.isoformat(),
            "durationFrom": nights_min,
            "durationTo": nights_max,
            "priceValueTo": 1000,
            "currency": currency,
            "limit": 50,
        }
        try:
            resp = httpx.get(_URL, params=params, timeout=self._timeout_s)
        except httpx.HTTPError as exc:
            raise RyanairUnavailable(f"Ryanair network error: {exc}") from exc
        if resp.status_code != 200:
            raise RyanairUnavailable(
                f"Ryanair {resp.status_code}: {resp.text[:200]}"
            )
        payload = resp.json()
        fares: list[Fare] = []
        for entry in payload.get("fares", []):
            try:
                dep = _parse_date(entry["outbound"]["departureDate"])
                ret = _parse_date(entry["inbound"]["departureDate"])
                price = float(entry["summary"]["price"]["value"])
                fares.append(Fare(
                    price_eur=price,
                    departure_date=dep,
                    return_date=ret,
                    nights=(ret - dep).days,
                    airline="Ryanair",
                    stops=0,
                    source="ryanair",
                    booking_url=(
                        f"https://www.ryanair.com/ie/en/trip/flights/select"
                        f"?adults=1&children=0&infants=0&teens=0"
                        f"&dateOut={dep.isoformat()}&dateIn={ret.isoformat()}"
                        f"&originIata={origin}&destinationIata={destination}"
                        f"&isReturn=true"
                    ),
                ))
            except (KeyError, ValueError):
                continue
        return fares
```

- [ ] **Step 4: Run tests, verify pass**

```bash
pytest tests/sources/test_ryanair.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/traveller/sources/ryanair.py tests/sources/test_ryanair.py
git commit -m "feat(sources): Ryanair open fares client with unavailable sentinel"
```

---

### Task 7: JSONL observation store

**Files:**
- Create: `src/traveller/persistence/__init__.py`
- Create: `src/traveller/persistence/jsonl_store.py`
- Test: `tests/persistence/test_jsonl_store.py`
- Create: `tests/persistence/__init__.py`

- [ ] **Step 1: Write failing test**

`tests/persistence/__init__.py`: (empty)

`tests/persistence/test_jsonl_store.py`:
```python
from datetime import date
from pathlib import Path

from traveller.models import Observation, RunMetadata
from traveller.persistence.jsonl_store import append_observation, append_run_metadata, read_all


def _obs(iata="BCN", run_date=date(2026, 4, 21), price=48.5) -> Observation:
    return Observation(
        run_date=run_date, origin="DUB",
        destination_iata=iata, destination_city="Barcelona",
        departure_date=date(2026, 6, 12), return_date=date(2026, 6, 15), nights=3,
        price_eur=price, airline="Ryanair", stops=0, source="kiwi",
        is_wishlist=False, category="europe_short_haul",
        market_p15_eur=62.0, was_flagged_as_deal=True,
        flag_reason="price <= p15", baseline_median_eur=None, phase=1,
    )


def test_append_and_read_single_observation(tmp_path: Path):
    f = tmp_path / "observations.jsonl"
    append_observation(_obs(), f)
    rows = read_all(f)
    assert len(rows) == 1
    assert rows[0]["destination_iata"] == "BCN"
    assert rows[0]["price_eur"] == 48.5


def test_append_multiple_preserves_order(tmp_path: Path):
    f = tmp_path / "observations.jsonl"
    append_observation(_obs("BCN", price=48.5), f)
    append_observation(_obs("CDG", price=94.0), f)
    rows = read_all(f)
    assert [r["destination_iata"] for r in rows] == ["BCN", "CDG"]


def test_append_run_metadata_adds_sentinel_kind(tmp_path: Path):
    f = tmp_path / "observations.jsonl"
    append_observation(_obs(), f)
    meta = RunMetadata(
        run_date=date(2026, 4, 21),
        run_started_at="2026-04-21T08:00:00+01:00",
        run_ended_at="2026-04-21T08:03:17+01:00",
        total_routes_queried=35,
        total_api_calls=36,
        deals_flagged=1,
        errors=[],
        git_commit_sha=None,
    )
    append_run_metadata(meta, f)
    rows = read_all(f)
    assert len(rows) == 2
    assert "kind" not in rows[0]
    assert rows[1]["kind"] == "run_metadata"
    assert rows[1]["total_routes_queried"] == 35


def test_read_all_missing_file_returns_empty(tmp_path: Path):
    assert read_all(tmp_path / "nope.jsonl") == []
```

- [ ] **Step 2: Run, verify fail**

```bash
pytest tests/persistence/test_jsonl_store.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `persistence/__init__.py` (empty) and `jsonl_store.py`**

`src/traveller/persistence/__init__.py`: (empty)

`src/traveller/persistence/jsonl_store.py`:
```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from traveller.models import Observation, RunMetadata


def append_observation(obs: Observation, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(obs.model_dump_json() + "\n")


def append_run_metadata(meta: RunMetadata, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(meta.model_dump_json() + "\n")


def read_all(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows
```

- [ ] **Step 4: Run tests, verify pass**

```bash
pytest tests/persistence/test_jsonl_store.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/traveller/persistence/ tests/persistence/
git commit -m "feat(persistence): append-only JSONL store with run_metadata sentinel"
```

---

### Task 8: Baseline computation

**Files:**
- Create: `src/traveller/persistence/baseline.py`
- Test: `tests/persistence/test_baseline.py`

- [ ] **Step 1: Write failing test**

`tests/persistence/test_baseline.py`:
```python
from datetime import date, timedelta
from pathlib import Path

from traveller.persistence.baseline import RouteHistory, load_route_history
from traveller.persistence.jsonl_store import append_observation
from tests.persistence.test_jsonl_store import _obs


def test_route_history_counts_observations(tmp_path: Path):
    f = tmp_path / "observations.jsonl"
    for i in range(5):
        append_observation(_obs("BCN", run_date=date(2026, 1, 1) + timedelta(weeks=i), price=50 + i), f)
    h = load_route_history(f, origin="DUB", destination_iata="BCN")
    assert h.observation_count == 5
    assert h.median_eur == 52.0  # median of 50..54 = 52


def test_route_history_only_counts_matching_route(tmp_path: Path):
    f = tmp_path / "observations.jsonl"
    append_observation(_obs("BCN", price=50), f)
    append_observation(_obs("CDG", price=80), f)
    h = load_route_history(f, origin="DUB", destination_iata="BCN")
    assert h.observation_count == 1
    assert h.median_eur == 50.0


def test_route_history_respects_window(tmp_path: Path):
    f = tmp_path / "observations.jsonl"
    for i in range(20):
        append_observation(_obs("BCN", run_date=date(2026, 1, 1) + timedelta(weeks=i), price=50 + i), f)
    h = load_route_history(f, origin="DUB", destination_iata="BCN", window=12)
    assert h.observation_count == 12
    # Last 12 observations: prices 58..69; median = (63+64)/2 = 63.5
    assert h.median_eur == 63.5


def test_route_history_empty_returns_zero(tmp_path: Path):
    f = tmp_path / "observations.jsonl"
    h = load_route_history(f, origin="DUB", destination_iata="BCN")
    assert h.observation_count == 0
    assert h.median_eur is None


def test_route_history_ignores_run_metadata_rows(tmp_path: Path):
    from traveller.models import RunMetadata
    from traveller.persistence.jsonl_store import append_run_metadata
    f = tmp_path / "observations.jsonl"
    append_observation(_obs("BCN", price=50), f)
    append_run_metadata(RunMetadata(
        run_date=date(2026, 1, 1),
        run_started_at="x", run_ended_at="x",
        total_routes_queried=1, total_api_calls=1, deals_flagged=0,
        errors=[], git_commit_sha=None,
    ), f)
    h = load_route_history(f, origin="DUB", destination_iata="BCN")
    assert h.observation_count == 1
```

- [ ] **Step 2: Run, verify fail**

```bash
pytest tests/persistence/test_baseline.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `persistence/baseline.py`**

```python
from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class RouteHistory:
    observation_count: int
    median_eur: Optional[float]
    prices: tuple[float, ...]


def load_route_history(
    path: Path,
    *,
    origin: str,
    destination_iata: str,
    window: Optional[int] = None,
) -> RouteHistory:
    if not path.is_file():
        return RouteHistory(observation_count=0, median_eur=None, prices=())
    matching: list[tuple[str, float]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("kind") == "run_metadata":
            continue
        if row.get("origin") != origin:
            continue
        if row.get("destination_iata") != destination_iata:
            continue
        matching.append((row["run_date"], float(row["price_eur"])))
    matching.sort(key=lambda t: t[0])
    if window is not None and len(matching) > window:
        matching = matching[-window:]
    prices = tuple(p for _, p in matching)
    median = statistics.median(prices) if prices else None
    return RouteHistory(
        observation_count=len(prices),
        median_eur=median,
        prices=prices,
    )
```

- [ ] **Step 4: Run tests, verify pass**

```bash
pytest tests/persistence/test_baseline.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/traveller/persistence/baseline.py tests/persistence/test_baseline.py
git commit -m "feat(persistence): route history with rolling-window median"
```

---

### Task 9: Phase selector

**Files:**
- Create: `src/traveller/evaluator/__init__.py`
- Create: `src/traveller/evaluator/phase_selector.py`
- Test: `tests/evaluator/test_phase_selector.py`
- Create: `tests/evaluator/__init__.py`

- [ ] **Step 1: Write failing test**

`tests/evaluator/__init__.py`: (empty)

`tests/evaluator/test_phase_selector.py`:
```python
from traveller.evaluator.phase_selector import select_phase
from traveller.models import PhaseThresholds


def _th():
    return PhaseThresholds(phase1_max_obs=3, phase2_max_obs=11)


def test_phase_1_when_fewer_than_four():
    th = _th()
    for n in (0, 1, 2, 3):
        assert select_phase(observation_count=n, thresholds=th) == 1


def test_phase_2_between_four_and_eleven():
    th = _th()
    for n in (4, 5, 8, 11):
        assert select_phase(observation_count=n, thresholds=th) == 2


def test_phase_3_at_twelve_or_above():
    th = _th()
    for n in (12, 26, 104):
        assert select_phase(observation_count=n, thresholds=th) == 3
```

- [ ] **Step 2: Run, verify fail**

```bash
pytest tests/evaluator/test_phase_selector.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `evaluator/__init__.py` (empty) and `phase_selector.py`**

`src/traveller/evaluator/__init__.py`: (empty)

`src/traveller/evaluator/phase_selector.py`:
```python
from __future__ import annotations

from typing import Literal

from traveller.models import PhaseThresholds

Phase = Literal[1, 2, 3]


def select_phase(*, observation_count: int, thresholds: PhaseThresholds) -> Phase:
    if observation_count <= thresholds.phase1_max_obs:
        return 1
    if observation_count <= thresholds.phase2_max_obs:
        return 2
    return 3
```

- [ ] **Step 4: Run tests, verify pass**

```bash
pytest tests/evaluator/test_phase_selector.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/traveller/evaluator/ tests/evaluator/
git commit -m "feat(evaluator): per-route phase selector"
```

---

### Task 10: Phase 1 evaluator (p15 + ceiling)

**Files:**
- Create: `src/traveller/evaluator/phase1.py`
- Test: `tests/evaluator/test_phase1.py`

- [ ] **Step 1: Write failing test**

`tests/evaluator/test_phase1.py`:
```python
from datetime import date

from traveller.evaluator.phase1 import evaluate_phase1
from traveller.models import Fare


def _fare(price: float) -> Fare:
    return Fare(
        price_eur=price,
        departure_date=date(2026, 6, 12),
        return_date=date(2026, 6, 15),
        nights=3, airline="FR", stops=0, source="kiwi",
        booking_url="https://kiwi.com/x",
    )


def test_phase1_flags_when_best_below_p15_and_ceiling():
    # 20 fares ranging 40..78 — p15 is around the 15th percentile ~ 45
    fares = [_fare(40 + i * 2) for i in range(20)]
    result = evaluate_phase1(
        fares=fares, percentile=15.0, ceiling=80.0,
    )
    assert result.is_deal is True
    assert result.market_p15_eur is not None
    assert result.market_p15_eur < 50
    assert "p15" in result.reason


def test_phase1_no_flag_when_best_above_ceiling():
    # Best fare is 100, ceiling is 80 — no flag even if p15 fires
    fares = [_fare(100 + i) for i in range(20)]
    result = evaluate_phase1(
        fares=fares, percentile=15.0, ceiling=80.0,
    )
    assert result.is_deal is False


def test_phase1_no_flag_when_best_above_p15():
    # All 20 fares identical → p15 == best; best <= p15 holds; still flags.
    # For "best above p15", construct a distribution where the best is unusually high.
    # Simulate: one cheap outlier removed, rest clustered.
    fares = [_fare(100) for _ in range(19)] + [_fare(80)]
    # p15 of 19*100+1*80 ~ 100; best=80 <= p15=100; under ceiling(80).
    # So WILL flag. To force no flag, raise ceiling above best but make best above p15:
    fares2 = [_fare(50 + i) for i in range(20)]  # 50..69; p15 ~ 52-53
    # Raise artificial ceiling huge, but choose evaluator where `best` is set externally = 75 via a second param?
    # Simpler: directly test by feeding a minimum_price larger than computed p15.
    result = evaluate_phase1(
        fares=fares2, percentile=15.0, ceiling=100.0, override_best_price=75.0,
    )
    assert result.is_deal is False
    assert "above p15" in result.reason


def test_phase1_empty_fares_returns_no_deal():
    result = evaluate_phase1(fares=[], percentile=15.0, ceiling=80.0)
    assert result.is_deal is False
    assert result.market_p15_eur is None
```

- [ ] **Step 2: Run, verify fail**

```bash
pytest tests/evaluator/test_phase1.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `phase1.py`**

`src/traveller/evaluator/phase1.py`:
```python
from __future__ import annotations

import statistics
from typing import Optional

from traveller.models import DealFlag, Fare


def evaluate_phase1(
    *,
    fares: list[Fare],
    percentile: float,
    ceiling: float,
    override_best_price: Optional[float] = None,
) -> DealFlag:
    if not fares:
        return DealFlag(
            is_deal=False, phase=1,
            reason="no fares returned",
            market_p15_eur=None, baseline_median_eur=None,
        )
    prices = sorted(f.price_eur for f in fares)
    p = _percentile(prices, percentile)
    best = override_best_price if override_best_price is not None else prices[0]
    if best > ceiling:
        return DealFlag(
            is_deal=False, phase=1,
            reason=f"best {best:.2f} above ceiling {ceiling:.2f}",
            market_p15_eur=p, baseline_median_eur=None,
        )
    if best > p:
        return DealFlag(
            is_deal=False, phase=1,
            reason=f"best {best:.2f} above p15 {p:.2f}",
            market_p15_eur=p, baseline_median_eur=None,
        )
    return DealFlag(
        is_deal=True, phase=1,
        reason=f"best {best:.2f} <= p15 {p:.2f} and <= ceiling {ceiling:.2f}",
        market_p15_eur=p, baseline_median_eur=None,
    )


def _percentile(sorted_prices: list[float], pct: float) -> float:
    """Linear-interpolation percentile on sorted input."""
    if not sorted_prices:
        raise ValueError("empty prices")
    if len(sorted_prices) == 1:
        return sorted_prices[0]
    rank = (pct / 100.0) * (len(sorted_prices) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(sorted_prices) - 1)
    frac = rank - lo
    return sorted_prices[lo] + frac * (sorted_prices[hi] - sorted_prices[lo])
```

- [ ] **Step 4: Run tests, verify pass**

```bash
pytest tests/evaluator/test_phase1.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/traveller/evaluator/phase1.py tests/evaluator/test_phase1.py
git commit -m "feat(evaluator): Phase 1 cold-start (p15 + ceiling)"
```

---

### Task 11: Phase 2 evaluator (baseline discount)

**Files:**
- Create: `src/traveller/evaluator/phase2.py`
- Test: `tests/evaluator/test_phase2.py`

- [ ] **Step 1: Write failing test**

`tests/evaluator/test_phase2.py`:
```python
from traveller.evaluator.phase2 import evaluate_phase2


def test_phase2_flags_when_price_25pct_below_baseline_non_wishlist():
    result = evaluate_phase2(
        best_price=60.0, baseline_median=100.0, ceiling=120.0,
        is_wishlist=False, min_discount_pct_non_wishlist=25.0,
        min_discount_pct_wishlist=15.0,
    )
    assert result.is_deal is True
    assert "40.0% below" in result.reason


def test_phase2_no_flag_when_discount_under_threshold():
    result = evaluate_phase2(
        best_price=80.0, baseline_median=100.0, ceiling=120.0,
        is_wishlist=False, min_discount_pct_non_wishlist=25.0,
        min_discount_pct_wishlist=15.0,
    )
    assert result.is_deal is False


def test_phase2_wishlist_looser_threshold():
    # 18% discount: below 25% (non-wishlist) but above 15% (wishlist)
    result = evaluate_phase2(
        best_price=82.0, baseline_median=100.0, ceiling=120.0,
        is_wishlist=True, min_discount_pct_non_wishlist=25.0,
        min_discount_pct_wishlist=15.0,
    )
    assert result.is_deal is True


def test_phase2_ceiling_cap():
    # 50% discount but above ceiling → no flag
    result = evaluate_phase2(
        best_price=200.0, baseline_median=400.0, ceiling=180.0,
        is_wishlist=False, min_discount_pct_non_wishlist=25.0,
        min_discount_pct_wishlist=15.0,
    )
    assert result.is_deal is False
    assert "above ceiling" in result.reason
```

- [ ] **Step 2: Run, verify fail**

```bash
pytest tests/evaluator/test_phase2.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `phase2.py`**

`src/traveller/evaluator/phase2.py`:
```python
from __future__ import annotations

from traveller.models import DealFlag


def evaluate_phase2(
    *,
    best_price: float,
    baseline_median: float,
    ceiling: float,
    is_wishlist: bool,
    min_discount_pct_non_wishlist: float,
    min_discount_pct_wishlist: float,
) -> DealFlag:
    if best_price > ceiling:
        return DealFlag(
            is_deal=False, phase=2,
            reason=f"best {best_price:.2f} above ceiling {ceiling:.2f}",
            market_p15_eur=None, baseline_median_eur=baseline_median,
        )
    discount_pct = (1.0 - best_price / baseline_median) * 100.0 if baseline_median > 0 else 0.0
    threshold = min_discount_pct_wishlist if is_wishlist else min_discount_pct_non_wishlist
    if discount_pct < threshold:
        return DealFlag(
            is_deal=False, phase=2,
            reason=(
                f"discount {discount_pct:.1f}% below required "
                f"{threshold:.0f}%"
            ),
            market_p15_eur=None, baseline_median_eur=baseline_median,
        )
    return DealFlag(
        is_deal=True, phase=2,
        reason=(
            f"{discount_pct:.1f}% below baseline "
            f"{baseline_median:.2f} (>= {threshold:.0f}%)"
        ),
        market_p15_eur=None, baseline_median_eur=baseline_median,
    )
```

- [ ] **Step 4: Run tests, verify pass**

```bash
pytest tests/evaluator/test_phase2.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/traveller/evaluator/phase2.py tests/evaluator/test_phase2.py
git commit -m "feat(evaluator): Phase 2 baseline-discount"
```

---

### Task 12: Phase 3 evaluator (hybrid)

**Files:**
- Create: `src/traveller/evaluator/phase3.py`
- Test: `tests/evaluator/test_phase3.py`

- [ ] **Step 1: Write failing test**

`tests/evaluator/test_phase3.py`:
```python
from traveller.evaluator.phase3 import evaluate_phase3
from traveller.models import DealFlag


def _flag(is_deal: bool, phase: int, market_p15=None, baseline=None) -> DealFlag:
    return DealFlag(
        is_deal=is_deal, phase=phase, reason="x",
        market_p15_eur=market_p15, baseline_median_eur=baseline,
    )


def test_phase3_flags_only_when_both_agree():
    r = evaluate_phase3(
        phase1_flag=_flag(True, 1, market_p15=60),
        phase2_flag=_flag(True, 2, baseline=80),
    )
    assert r.is_deal is True
    assert r.market_p15_eur == 60
    assert r.baseline_median_eur == 80


def test_phase3_no_flag_when_only_phase1_fires():
    r = evaluate_phase3(
        phase1_flag=_flag(True, 1, market_p15=60),
        phase2_flag=_flag(False, 2, baseline=80),
    )
    assert r.is_deal is False


def test_phase3_no_flag_when_only_phase2_fires():
    r = evaluate_phase3(
        phase1_flag=_flag(False, 1, market_p15=60),
        phase2_flag=_flag(True, 2, baseline=80),
    )
    assert r.is_deal is False
```

- [ ] **Step 2: Run, verify fail**

```bash
pytest tests/evaluator/test_phase3.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `phase3.py`**

`src/traveller/evaluator/phase3.py`:
```python
from __future__ import annotations

from traveller.models import DealFlag


def evaluate_phase3(*, phase1_flag: DealFlag, phase2_flag: DealFlag) -> DealFlag:
    is_deal = phase1_flag.is_deal and phase2_flag.is_deal
    if is_deal:
        reason = (
            f"both signals fire — {phase1_flag.reason}; {phase2_flag.reason}"
        )
    elif not phase1_flag.is_deal and not phase2_flag.is_deal:
        reason = "neither signal fires"
    elif not phase1_flag.is_deal:
        reason = f"phase1 vetoes ({phase1_flag.reason})"
    else:
        reason = f"phase2 vetoes ({phase2_flag.reason})"
    return DealFlag(
        is_deal=is_deal, phase=3, reason=reason,
        market_p15_eur=phase1_flag.market_p15_eur,
        baseline_median_eur=phase2_flag.baseline_median_eur,
    )
```

- [ ] **Step 4: Run tests, verify pass**

```bash
pytest tests/evaluator/test_phase3.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/traveller/evaluator/phase3.py tests/evaluator/test_phase3.py
git commit -m "feat(evaluator): Phase 3 hybrid"
```

---

### Task 13: Dispatcher (per-route phase + evaluate)

**Files:**
- Create: `src/traveller/evaluator/dispatcher.py`
- Test: `tests/evaluator/test_dispatcher.py`

- [ ] **Step 1: Write failing test**

`tests/evaluator/test_dispatcher.py`:
```python
from datetime import date

from traveller.evaluator.dispatcher import evaluate_route
from traveller.models import BaselineConfig, CategoryCeilings, Fare, PhaseThresholds


def _fare(price: float) -> Fare:
    return Fare(
        price_eur=price, departure_date=date(2026, 6, 12),
        return_date=date(2026, 6, 15), nights=3,
        airline="FR", stops=0, source="kiwi", booking_url="x",
    )


def _baseline():
    return BaselineConfig(
        cold_start_p_percentile=15,
        baseline_window_observations=12,
        phase2_min_discount_pct_non_wishlist=25,
        phase2_min_discount_pct_wishlist=15,
        phase_thresholds=PhaseThresholds(phase1_max_obs=3, phase2_max_obs=11),
    )


def _ceilings():
    return CategoryCeilings(
        europe_short_haul=80, europe_long_haul=130,
        intercontinental_asia=550, intercontinental_south_america=600,
    )


def test_dispatcher_uses_phase1_when_no_history():
    fares = [_fare(40 + i * 2) for i in range(20)]
    result = evaluate_route(
        fares=fares, observation_count=0, prior_prices=(),
        category="europe_short_haul", is_wishlist=False,
        baseline=_baseline(), ceilings=_ceilings(),
        wishlist_multiplier=1.3,
    )
    assert result.phase == 1


def test_dispatcher_uses_phase2_with_medium_history():
    fares = [_fare(40) for _ in range(20)]
    prior = tuple(float(x) for x in range(80, 90))  # 10 priors, median ~84.5
    result = evaluate_route(
        fares=fares, observation_count=10, prior_prices=prior,
        category="europe_short_haul", is_wishlist=False,
        baseline=_baseline(), ceilings=_ceilings(),
        wishlist_multiplier=1.3,
    )
    assert result.phase == 2


def test_dispatcher_uses_phase3_with_long_history():
    fares = [_fare(40) for _ in range(20)]
    prior = tuple(float(x) for x in range(80, 100))  # 20 priors
    result = evaluate_route(
        fares=fares, observation_count=20, prior_prices=prior,
        category="europe_short_haul", is_wishlist=False,
        baseline=_baseline(), ceilings=_ceilings(),
        wishlist_multiplier=1.3,
    )
    assert result.phase == 3
```

- [ ] **Step 2: Run, verify fail**

```bash
pytest tests/evaluator/test_dispatcher.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `dispatcher.py`**

`src/traveller/evaluator/dispatcher.py`:
```python
from __future__ import annotations

import statistics

from traveller.categories import ceiling_for
from traveller.evaluator.phase1 import evaluate_phase1
from traveller.evaluator.phase2 import evaluate_phase2
from traveller.evaluator.phase3 import evaluate_phase3
from traveller.evaluator.phase_selector import select_phase
from traveller.models import (
    BaselineConfig,
    Category,
    CategoryCeilings,
    DealFlag,
    Fare,
)


def evaluate_route(
    *,
    fares: list[Fare],
    observation_count: int,
    prior_prices: tuple[float, ...],
    category: Category,
    is_wishlist: bool,
    baseline: BaselineConfig,
    ceilings: CategoryCeilings,
    wishlist_multiplier: float,
) -> DealFlag:
    phase = select_phase(
        observation_count=observation_count,
        thresholds=baseline.phase_thresholds,
    )
    ceiling = ceiling_for(
        category, ceilings,
        is_wishlist=is_wishlist, multiplier=wishlist_multiplier,
    )
    p1 = evaluate_phase1(
        fares=fares,
        percentile=baseline.cold_start_p_percentile,
        ceiling=ceiling,
    )
    if phase == 1:
        return p1
    if not fares:
        return DealFlag(
            is_deal=False, phase=phase,
            reason="no fares returned",
            market_p15_eur=p1.market_p15_eur, baseline_median_eur=None,
        )
    best = min(f.price_eur for f in fares)
    median = statistics.median(prior_prices) if prior_prices else 0.0
    p2 = evaluate_phase2(
        best_price=best, baseline_median=median, ceiling=ceiling,
        is_wishlist=is_wishlist,
        min_discount_pct_non_wishlist=baseline.phase2_min_discount_pct_non_wishlist,
        min_discount_pct_wishlist=baseline.phase2_min_discount_pct_wishlist,
    )
    if phase == 2:
        # Preserve market p15 for observation record
        return DealFlag(
            is_deal=p2.is_deal, phase=2, reason=p2.reason,
            market_p15_eur=p1.market_p15_eur,
            baseline_median_eur=p2.baseline_median_eur,
        )
    return evaluate_phase3(phase1_flag=p1, phase2_flag=p2)
```

- [ ] **Step 4: Run tests, verify pass**

```bash
pytest tests/evaluator/test_dispatcher.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/traveller/evaluator/dispatcher.py tests/evaluator/test_dispatcher.py
git commit -m "feat(evaluator): dispatcher selects phase and evaluates"
```

---

### Task 14: Rotation cursor for intercontinental routes

**Files:**
- Create: `src/traveller/rotation.py`
- Test: `tests/test_rotation.py`

- [ ] **Step 1: Write failing test**

`tests/test_rotation.py`:
```python
import json
from pathlib import Path

from traveller.models import Destination
from traveller.rotation import load_rotation_state, next_intercontinental_selection, save_rotation_state


def _asia():
    return [Destination(iata=c, city=c) for c in ("BKK", "HND", "SIN", "DEL", "KUL", "HKG", "CGK")]


def _sa():
    return [Destination(iata=c, city=c) for c in ("GRU", "GIG", "EZE", "BOG", "LIM")]


def test_rotation_first_run_starts_at_zero(tmp_path: Path):
    f = tmp_path / "rotation.json"
    state = load_rotation_state(f)
    assert state.asia_cursor == 0
    assert state.south_america_cursor == 0


def test_rotation_selects_next_three_asia_two_sa(tmp_path: Path):
    f = tmp_path / "rotation.json"
    state = load_rotation_state(f)
    sel, new_state = next_intercontinental_selection(
        state=state, asia=_asia(), south_america=_sa(),
        asia_pick=3, sa_pick=2,
    )
    assert [d.iata for d in sel.asia] == ["BKK", "HND", "SIN"]
    assert [d.iata for d in sel.south_america] == ["GRU", "GIG"]
    assert new_state.asia_cursor == 3
    assert new_state.south_america_cursor == 2


def test_rotation_wraps_around(tmp_path: Path):
    from traveller.rotation import RotationState
    f = tmp_path / "rotation.json"
    state = RotationState(asia_cursor=6, south_america_cursor=4)
    sel, new_state = next_intercontinental_selection(
        state=state, asia=_asia(), south_america=_sa(),
        asia_pick=3, sa_pick=2,
    )
    assert [d.iata for d in sel.asia] == ["CGK", "BKK", "HND"]
    assert [d.iata for d in sel.south_america] == ["LIM", "GRU"]
    assert new_state.asia_cursor == 2  # (6 + 3) % 7
    assert new_state.south_america_cursor == 1  # (4 + 2) % 5


def test_rotation_save_and_load_roundtrip(tmp_path: Path):
    from traveller.rotation import RotationState
    f = tmp_path / "rotation.json"
    save_rotation_state(RotationState(asia_cursor=5, south_america_cursor=3), f)
    loaded = load_rotation_state(f)
    assert loaded.asia_cursor == 5
    assert loaded.south_america_cursor == 3
    assert json.loads(f.read_text())["asia_cursor"] == 5
```

- [ ] **Step 2: Run, verify fail**

```bash
pytest tests/test_rotation.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `rotation.py`**

`src/traveller/rotation.py`:
```python
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from traveller.models import Destination


@dataclass(frozen=True)
class RotationState:
    asia_cursor: int = 0
    south_america_cursor: int = 0


@dataclass(frozen=True)
class IntercontinentalSelection:
    asia: list[Destination]
    south_america: list[Destination]


def load_rotation_state(path: Path) -> RotationState:
    if not path.is_file():
        return RotationState()
    data = json.loads(path.read_text(encoding="utf-8"))
    return RotationState(
        asia_cursor=int(data.get("asia_cursor", 0)),
        south_america_cursor=int(data.get("south_america_cursor", 0)),
    )


def save_rotation_state(state: RotationState, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(state), indent=2), encoding="utf-8")


def _take(items: list[Destination], start: int, count: int) -> list[Destination]:
    if not items or count <= 0:
        return []
    out: list[Destination] = []
    n = len(items)
    for i in range(count):
        out.append(items[(start + i) % n])
    return out


def next_intercontinental_selection(
    *,
    state: RotationState,
    asia: list[Destination],
    south_america: list[Destination],
    asia_pick: int = 3,
    sa_pick: int = 2,
) -> tuple[IntercontinentalSelection, RotationState]:
    asia_sel = _take(asia, state.asia_cursor, asia_pick)
    sa_sel = _take(south_america, state.south_america_cursor, sa_pick)
    new_asia_cursor = (state.asia_cursor + asia_pick) % max(1, len(asia))
    new_sa_cursor = (state.south_america_cursor + sa_pick) % max(1, len(south_america))
    return (
        IntercontinentalSelection(asia=asia_sel, south_america=sa_sel),
        RotationState(asia_cursor=new_asia_cursor, south_america_cursor=new_sa_cursor),
    )
```

- [ ] **Step 4: Run tests, verify pass**

```bash
pytest tests/test_rotation.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/traveller/rotation.py tests/test_rotation.py
git commit -m "feat(rotation): intercontinental cursor with wrap-around"
```

---

### Task 15: Seed config files

**Files:**
- Create: `config/settings.json`
- Create: `config/destinations.json`
- Create: `config/wishlist.json`

- [ ] **Step 1: Create `config/settings.json`**

```json
{
  "origin_iata": "DUB",
  "currency": "EUR",
  "email_recipient": "lukasmtorquato@gmail.com",
  "search_windows": {
    "europe_short_haul": {"days_ahead_max": 90, "nights_min": 2, "nights_max": 7},
    "europe_long_haul": {"days_ahead_max": 120, "nights_min": 2, "nights_max": 7},
    "intercontinental": {"days_ahead_max": 240, "nights_min": 10, "nights_max": 21}
  },
  "category_ceilings_eur": {
    "europe_short_haul": 80,
    "europe_long_haul": 130,
    "intercontinental_asia": 550,
    "intercontinental_south_america": 600
  },
  "wishlist_ceiling_multiplier": 1.3,
  "baseline": {
    "cold_start_p_percentile": 15,
    "baseline_window_observations": 12,
    "phase2_min_discount_pct_non_wishlist": 25,
    "phase2_min_discount_pct_wishlist": 15,
    "phase_thresholds": {"phase1_max_obs": 3, "phase2_max_obs": 11}
  },
  "kiwi_api_key_env_var": "KIWI_TEQUILA_API_KEY",
  "kiwi_rate_limit_delay_ms": 200
}
```

- [ ] **Step 2: Create `config/destinations.json`**

```json
{
  "europe_short_haul": [
    {"iata": "BCN", "city": "Barcelona"},
    {"iata": "CDG", "city": "Paris"},
    {"iata": "AMS", "city": "Amsterdam"},
    {"iata": "BER", "city": "Berlin"},
    {"iata": "LIS", "city": "Lisbon"},
    {"iata": "MAD", "city": "Madrid"},
    {"iata": "FCO", "city": "Rome"},
    {"iata": "MXP", "city": "Milan"},
    {"iata": "VIE", "city": "Vienna"},
    {"iata": "PRG", "city": "Prague"},
    {"iata": "BRU", "city": "Brussels"},
    {"iata": "CPH", "city": "Copenhagen"},
    {"iata": "ZRH", "city": "Zurich"},
    {"iata": "WAW", "city": "Warsaw"},
    {"iata": "BUD", "city": "Budapest"}
  ],
  "europe_long_haul": [
    {"iata": "ATH", "city": "Athens"},
    {"iata": "IST", "city": "Istanbul"},
    {"iata": "OSL", "city": "Oslo"},
    {"iata": "ARN", "city": "Stockholm"},
    {"iata": "HEL", "city": "Helsinki"},
    {"iata": "KEF", "city": "Reykjavik"},
    {"iata": "TLV", "city": "Tel Aviv"},
    {"iata": "SPU", "city": "Split"},
    {"iata": "FNC", "city": "Madeira"},
    {"iata": "TFS", "city": "Tenerife"}
  ],
  "intercontinental_asia": [
    {"iata": "BKK", "city": "Bangkok"},
    {"iata": "HND", "city": "Tokyo"},
    {"iata": "SIN", "city": "Singapore"},
    {"iata": "DEL", "city": "Delhi"},
    {"iata": "KUL", "city": "Kuala Lumpur"},
    {"iata": "HKG", "city": "Hong Kong"},
    {"iata": "CGK", "city": "Jakarta"}
  ],
  "intercontinental_south_america": [
    {"iata": "GRU", "city": "Sao Paulo"},
    {"iata": "GIG", "city": "Rio de Janeiro"},
    {"iata": "EZE", "city": "Buenos Aires"},
    {"iata": "BOG", "city": "Bogota"},
    {"iata": "LIM", "city": "Lima"}
  ]
}
```

- [ ] **Step 3: Create `config/wishlist.json`** (empty list; user fills in later)

```json
{
  "wishlist": []
}
```

- [ ] **Step 4: Verify loading works**

```bash
python -c "from traveller.config import load_config; from pathlib import Path; b = load_config(Path('config')); print(b.settings.origin_iata, len(b.destinations.europe_short_haul), 'wishlist:', len(b.wishlist.wishlist))"
```
Expected: `DUB 15 wishlist: 0`

- [ ] **Step 5: Commit**

```bash
git add config/
git commit -m "feat(config): seed settings, destinations, empty wishlist"
```

---

### Task 16: Markdown reporter

**Files:**
- Create: `src/traveller/reporter.py`
- Test: `tests/test_reporter.py`

- [ ] **Step 1: Write failing test**

`tests/test_reporter.py`:
```python
from datetime import date, timedelta

from traveller.models import DealFlag, Fare, Observation
from traveller.reporter import RouteOutcome, RunReport, render_report


def _obs(iata="BCN", price=48.5, flagged=True, phase=1) -> Observation:
    return Observation(
        run_date=date(2026, 4, 21), origin="DUB",
        destination_iata=iata, destination_city="Barcelona",
        departure_date=date(2026, 6, 12), return_date=date(2026, 6, 15), nights=3,
        price_eur=price, airline="Ryanair", stops=0, source="kiwi",
        is_wishlist=False, category="europe_short_haul",
        market_p15_eur=62.0, was_flagged_as_deal=flagged,
        flag_reason="r", baseline_median_eur=None, phase=phase,
    )


def _fare(price: float) -> Fare:
    return Fare(
        price_eur=price, departure_date=date(2026, 6, 12),
        return_date=date(2026, 6, 15), nights=3,
        airline="FR", stops=0, source="kiwi",
        booking_url="https://kiwi.com/deep/BCN",
    )


def _outcome(iata="BCN", deal=True, phase=1, price=48.5, skipped=False, err=None):
    flag = DealFlag(
        is_deal=deal, phase=phase, reason="r",
        market_p15_eur=62.0 if phase in (1, 3) else None,
        baseline_median_eur=None,
    )
    return RouteOutcome(
        origin="DUB", destination_iata=iata, destination_city="Barcelona",
        category="europe_short_haul", is_wishlist=False,
        best_fare=_fare(price) if not skipped else None,
        flag=flag if not skipped else None,
        skipped=skipped, error=err,
    )


def test_renders_header_and_no_deals():
    report = RunReport(
        run_date=date(2026, 4, 21), origin="DUB", currency="EUR",
        runtime_seconds=222,
        outcomes=[_outcome("CDG", deal=False, price=94)],
        total_api_calls=1,
    )
    md = render_report(report)
    assert "# Travel Deals Scan — 2026-04-21" in md
    assert "CDG" in md
    assert "Great deals this week" in md
    assert "No great deals" in md


def test_renders_deals_section_when_flagged():
    report = RunReport(
        run_date=date(2026, 4, 21), origin="DUB", currency="EUR",
        runtime_seconds=222,
        outcomes=[_outcome("BCN", deal=True, price=48.5)],
        total_api_calls=1,
    )
    md = render_report(report)
    assert "Barcelona" in md
    assert "€48.50" in md
    assert "https://kiwi.com/deep/BCN" in md
    assert "No great deals" not in md


def test_renders_skipped_routes():
    report = RunReport(
        run_date=date(2026, 4, 21), origin="DUB", currency="EUR",
        runtime_seconds=222,
        outcomes=[_outcome("FCO", skipped=True, err="Kiwi 504")],
        total_api_calls=0,
    )
    md = render_report(report)
    assert "Routes skipped" in md
    assert "FCO" in md
    assert "Kiwi 504" in md
```

- [ ] **Step 2: Run, verify fail**

```bash
pytest tests/test_reporter.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `reporter.py`**

`src/traveller/reporter.py`:
```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from traveller.models import Category, DealFlag, Fare


@dataclass(frozen=True)
class RouteOutcome:
    origin: str
    destination_iata: str
    destination_city: str
    category: Category
    is_wishlist: bool
    best_fare: Optional[Fare]
    flag: Optional[DealFlag]
    skipped: bool
    error: Optional[str]


@dataclass(frozen=True)
class RunReport:
    run_date: date
    origin: str
    currency: str
    runtime_seconds: int
    outcomes: list[RouteOutcome]
    total_api_calls: int


def _format_duration(seconds: int) -> str:
    mins, secs = divmod(seconds, 60)
    return f"{mins}m {secs:02d}s"


def _deal_card(outcome: RouteOutcome) -> str:
    assert outcome.best_fare is not None and outcome.flag is not None
    f = outcome.best_fare
    star = " ⭐ WISHLIST" if outcome.is_wishlist else ""
    lines = [
        f"### ✈️ {outcome.destination_city} ({outcome.destination_iata}) — €{f.price_eur:.2f} return{star}",
        f"- **Dates:** {f.departure_date.isoformat()} → {f.return_date.isoformat()} ({f.nights} nights)",
        f"- **Airline:** {f.airline} ({'direct' if f.stops == 0 else f'{f.stops} stop(s)'})",
        f"- **Phase:** {outcome.flag.phase} — {outcome.flag.reason}",
        f"- **Book:** {f.booking_url}",
        "",
    ]
    return "\n".join(lines)


def render_report(report: RunReport) -> str:
    deals = [o for o in report.outcomes if o.flag and o.flag.is_deal and not o.skipped]
    no_deals = [o for o in report.outcomes if o.flag and not o.flag.is_deal and not o.skipped]
    skipped = [o for o in report.outcomes if o.skipped]

    out: list[str] = []
    out.append(f"# Travel Deals Scan — {report.run_date.isoformat()} ({report.run_date.strftime('%a')})")
    out.append("")
    out.append(
        f"**Origin:** {report.origin}  **Currency:** {report.currency}  "
        f"**Runtime:** {_format_duration(report.runtime_seconds)}"
    )
    out.append("")
    out.append("## Great deals this week")
    out.append("")
    if deals:
        for d in deals:
            out.append(_deal_card(d))
    else:
        out.append("_No great deals this week._")
        out.append("")

    if no_deals:
        out.append("## Routes scanned (no deal)")
        out.append("")
        out.append("| Route | Best price | Phase | Reason |")
        out.append("|-------|-----------|-------|--------|")
        for o in no_deals:
            best = f"€{o.best_fare.price_eur:.2f}" if o.best_fare else "n/a"
            phase = o.flag.phase if o.flag else "-"
            reason = o.flag.reason if o.flag else "-"
            out.append(f"| {o.destination_iata} | {best} | {phase} | {reason} |")
        out.append("")

    if skipped:
        out.append("## Routes skipped (errors)")
        out.append("")
        out.append("| Route | Reason |")
        out.append("|-------|--------|")
        for o in skipped:
            out.append(f"| {o.destination_iata} | {o.error or 'unknown'} |")
        out.append("")

    out.append("## Run metadata")
    out.append("")
    out.append(f"- Total routes queried: {len([o for o in report.outcomes if not o.skipped])}")
    out.append(f"- Total API calls: {report.total_api_calls}")
    out.append(f"- Deals flagged: {len(deals)}")
    out.append(f"- Errors: {len(skipped)}")
    return "\n".join(out) + "\n"
```

- [ ] **Step 4: Run tests, verify pass**

```bash
pytest tests/test_reporter.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/traveller/reporter.py tests/test_reporter.py
git commit -m "feat(reporter): markdown report with deals, skipped, metadata"
```

---

### Task 17: Emailer (JSON envelope for Claude to send)

**Files:**
- Create: `src/traveller/emailer.py`
- Test: `tests/test_emailer.py`

- [ ] **Step 1: Write failing test**

`tests/test_emailer.py`:
```python
import json
from datetime import date
from pathlib import Path

from traveller.emailer import write_email_envelope
from traveller.reporter import RouteOutcome, RunReport
from tests.test_reporter import _outcome


def _report(outcomes):
    return RunReport(
        run_date=date(2026, 4, 21), origin="DUB", currency="EUR",
        runtime_seconds=200, outcomes=outcomes, total_api_calls=5,
    )


def test_no_deals_writes_should_send_false(tmp_path: Path):
    out = tmp_path / "email.json"
    write_email_envelope(
        report=_report([_outcome("CDG", deal=False, price=94)]),
        recipient="lukas@example.com",
        output_path=out,
    )
    payload = json.loads(out.read_text())
    assert payload["should_send"] is False
    assert payload["subject"] == ""


def test_single_deal_formats_subject_and_body(tmp_path: Path):
    out = tmp_path / "email.json"
    write_email_envelope(
        report=_report([_outcome("BCN", deal=True, price=48.5)]),
        recipient="lukas@example.com",
        output_path=out,
    )
    p = json.loads(out.read_text())
    assert p["should_send"] is True
    assert "1 travel deal" in p["subject"]
    assert "Barcelona" in p["subject"]
    assert "€48" in p["subject"]
    assert p["to"] == "lukas@example.com"
    assert "Barcelona" in p["body_html"]
    assert "https://kiwi.com/deep/BCN" in p["body_html"]


def test_multiple_deals_pluralised(tmp_path: Path):
    out = tmp_path / "email.json"
    o1 = _outcome("BCN", deal=True, price=48.5)
    o2 = _outcome("CDG", deal=True, price=72.0)
    write_email_envelope(
        report=_report([o1, o2]),
        recipient="lukas@example.com",
        output_path=out,
    )
    p = json.loads(out.read_text())
    assert "2 travel deals" in p["subject"]
```

- [ ] **Step 2: Run, verify fail**

```bash
pytest tests/test_emailer.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `emailer.py`**

`src/traveller/emailer.py`:
```python
from __future__ import annotations

import json
from pathlib import Path

from traveller.reporter import RouteOutcome, RunReport


def _deal_block_html(o: RouteOutcome) -> str:
    assert o.best_fare is not None
    star = " ⭐ wishlist" if o.is_wishlist else ""
    f = o.best_fare
    return (
        f"<p><strong>{o.destination_city} ({o.destination_iata})</strong>{star}<br>"
        f"€{f.price_eur:.2f} return — {f.departure_date.isoformat()} → "
        f"{f.return_date.isoformat()} ({f.nights} nights, {f.airline}"
        f"{', direct' if f.stops == 0 else f', {f.stops} stop(s)'})<br>"
        f"{o.flag.reason if o.flag else ''}<br>"
        f"<a href=\"{f.booking_url}\">Book</a></p>"
    )


def _subject(deals: list[RouteOutcome]) -> str:
    if not deals:
        return ""
    n = len(deals)
    noun = "deal" if n == 1 else "deals"
    head = deals[0]
    assert head.best_fare is not None
    star = " ⭐" if head.is_wishlist else ""
    parts = [f"{head.destination_city} €{head.best_fare.price_eur:.0f}{star}"]
    if n >= 2 and deals[1].best_fare is not None:
        s2 = " ⭐" if deals[1].is_wishlist else ""
        parts.append(f"{deals[1].destination_city} €{deals[1].best_fare.price_eur:.0f}{s2}")
    return f"✈️ {n} travel {noun} this week — " + ", ".join(parts)


def write_email_envelope(
    *,
    report: RunReport,
    recipient: str,
    output_path: Path,
) -> None:
    deals = [o for o in report.outcomes if o.flag and o.flag.is_deal and not o.skipped]
    body_lines = [
        "<p>Hi Lukas,</p>",
        f"<p>{len(deals)} great deal(s) detected on your Tuesday scan:</p>",
        *[_deal_block_html(o) for o in deals],
        f"<p>Scanned {len([o for o in report.outcomes if not o.skipped])} routes, "
        f"skipped {len([o for o in report.outcomes if o.skipped])}.</p>",
    ]
    envelope = {
        "should_send": bool(deals),
        "to": recipient,
        "subject": _subject(deals),
        "body_html": "\n".join(body_lines),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
```

- [ ] **Step 4: Run tests, verify pass**

```bash
pytest tests/test_emailer.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/traveller/emailer.py tests/test_emailer.py
git commit -m "feat(emailer): JSON envelope for Claude Gmail MCP to consume"
```

---

### Task 18: Monthly health email

**Files:**
- Create: `src/traveller/health.py`
- Test: `tests/test_health.py`

- [ ] **Step 1: Write failing test**

`tests/test_health.py`:
```python
from datetime import date
from pathlib import Path

from traveller.health import (
    is_first_tuesday_of_month,
    summarise_month,
    write_health_envelope,
)
import json


def test_is_first_tuesday_true_for_known_dates():
    assert is_first_tuesday_of_month(date(2026, 5, 5)) is True
    assert is_first_tuesday_of_month(date(2026, 6, 2)) is True


def test_is_first_tuesday_false_for_other_tuesdays():
    assert is_first_tuesday_of_month(date(2026, 5, 12)) is False
    assert is_first_tuesday_of_month(date(2026, 4, 21)) is False


def test_is_first_tuesday_false_for_non_tuesday():
    assert is_first_tuesday_of_month(date(2026, 5, 6)) is False  # Wed


def test_summarise_month_counts_runs_and_deals(tmp_path: Path):
    f = tmp_path / "observations.jsonl"
    rows = [
        {"kind": "run_metadata", "run_date": "2026-04-07",
         "run_started_at": "", "run_ended_at": "",
         "total_routes_queried": 35, "total_api_calls": 36,
         "deals_flagged": 2, "errors": [], "git_commit_sha": None},
        {"kind": "run_metadata", "run_date": "2026-04-14",
         "run_started_at": "", "run_ended_at": "",
         "total_routes_queried": 35, "total_api_calls": 36,
         "deals_flagged": 0, "errors": ["fco-504"], "git_commit_sha": None},
        {"kind": "run_metadata", "run_date": "2026-05-05",
         "run_started_at": "", "run_ended_at": "",
         "total_routes_queried": 35, "total_api_calls": 36,
         "deals_flagged": 3, "errors": [], "git_commit_sha": None},
    ]
    f.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    summary = summarise_month(f, for_month=date(2026, 4, 1))
    assert summary.run_count == 2
    assert summary.deals_flagged == 2
    assert summary.errors == 1


def test_write_health_envelope_on_first_tuesday(tmp_path: Path):
    f = tmp_path / "observations.jsonl"
    out = tmp_path / "email.json"
    f.write_text("", encoding="utf-8")
    wrote = write_health_envelope(
        today=date(2026, 5, 5),
        recipient="l@example.com",
        observations_path=f,
        output_path=out,
    )
    assert wrote is True
    p = json.loads(out.read_text())
    assert p["should_send"] is True
    assert "monthly health" in p["subject"].lower()


def test_write_health_envelope_skips_non_first_tuesday(tmp_path: Path):
    f = tmp_path / "observations.jsonl"
    out = tmp_path / "email.json"
    wrote = write_health_envelope(
        today=date(2026, 5, 12),
        recipient="l@example.com",
        observations_path=f,
        output_path=out,
    )
    assert wrote is False
    assert not out.exists()
```

- [ ] **Step 2: Run, verify fail**

```bash
pytest tests/test_health.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `health.py`**

`src/traveller/health.py`:
```python
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path


def is_first_tuesday_of_month(d: date) -> bool:
    return d.weekday() == 1 and d.day <= 7


@dataclass(frozen=True)
class MonthSummary:
    run_count: int
    deals_flagged: int
    errors: int


def summarise_month(observations_path: Path, *, for_month: date) -> MonthSummary:
    if not observations_path.is_file():
        return MonthSummary(0, 0, 0)
    run_count = 0
    deals = 0
    errs = 0
    for line in observations_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("kind") != "run_metadata":
            continue
        run_date = date.fromisoformat(row["run_date"])
        if run_date.year == for_month.year and run_date.month == for_month.month:
            run_count += 1
            deals += int(row.get("deals_flagged", 0))
            errs += len(row.get("errors", []))
    return MonthSummary(run_count=run_count, deals_flagged=deals, errors=errs)


def write_health_envelope(
    *,
    today: date,
    recipient: str,
    observations_path: Path,
    output_path: Path,
) -> bool:
    if not is_first_tuesday_of_month(today):
        return False
    last_month = date(today.year, today.month, 1)
    if today.month == 1:
        last_month = date(today.year - 1, 12, 1)
    else:
        last_month = date(today.year, today.month - 1, 1)
    summary = summarise_month(observations_path, for_month=last_month)
    month_name = last_month.strftime("%B %Y")
    body = (
        f"<p>Monthly health check for {month_name}.</p>"
        f"<ul>"
        f"<li>Runs: {summary.run_count}</li>"
        f"<li>Deals flagged: {summary.deals_flagged}</li>"
        f"<li>Errors: {summary.errors}</li>"
        f"</ul>"
        f"<p>If you don't get this email on the first Tuesday of next month, the routine has likely broken — check the git repo for the last run date.</p>"
    )
    envelope = {
        "should_send": True,
        "to": recipient,
        "subject": f"📊 Travel scan monthly health — {month_name}",
        "body_html": body,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
    return True
```

- [ ] **Step 4: Run tests, verify pass**

```bash
pytest tests/test_health.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/traveller/health.py tests/test_health.py
git commit -m "feat(health): monthly first-Tuesday health email"
```

---

### Task 19: Orchestrator (the run function)

**Files:**
- Create: `src/traveller/orchestrator.py`
- Test: `tests/test_orchestrator.py`

- [ ] **Step 1: Write failing test**

`tests/test_orchestrator.py`:
```python
import json
from datetime import date
from pathlib import Path

from freezegun import freeze_time
from pytest_httpx import HTTPXMock

from traveller.orchestrator import run_scan


def _kiwi_cheap():
    return {"data": [
        {
            "price": 40 + i,
            "local_departure": "2026-06-12T09:30:00.000Z",
            "nightsInDest": 3,
            "route": [
                {"airline": "FR", "return": 0},
                {"airline": "FR", "return": 1,
                 "local_departure": "2026-06-15T10:00:00.000Z"},
            ],
            "airlines": ["FR"],
            "deep_link": f"https://kiwi.com/deep/{i}",
        } for i in range(20)
    ]}


@freeze_time("2026-04-21")
def test_orchestrator_happy_path_single_route(tmp_path: Path, httpx_mock: HTTPXMock, monkeypatch):
    # Minimal config: one route
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "settings.json").write_text(json.dumps({
        "origin_iata": "DUB", "currency": "EUR",
        "email_recipient": "l@example.com",
        "search_windows": {
            "europe_short_haul": {"days_ahead_max": 90, "nights_min": 2, "nights_max": 7},
            "europe_long_haul": {"days_ahead_max": 120, "nights_min": 2, "nights_max": 7},
            "intercontinental": {"days_ahead_max": 240, "nights_min": 10, "nights_max": 21},
        },
        "category_ceilings_eur": {
            "europe_short_haul": 80, "europe_long_haul": 130,
            "intercontinental_asia": 550, "intercontinental_south_america": 600,
        },
        "wishlist_ceiling_multiplier": 1.3,
        "baseline": {
            "cold_start_p_percentile": 15, "baseline_window_observations": 12,
            "phase2_min_discount_pct_non_wishlist": 25,
            "phase2_min_discount_pct_wishlist": 15,
            "phase_thresholds": {"phase1_max_obs": 3, "phase2_max_obs": 11},
        },
        "kiwi_api_key_env_var": "KIWI_TEQUILA_API_KEY",
        "kiwi_rate_limit_delay_ms": 0,
    }))
    (cfg / "destinations.json").write_text(json.dumps({
        "europe_short_haul": [{"iata": "BCN", "city": "Barcelona"}],
        "europe_long_haul": [],
        "intercontinental_asia": [],
        "intercontinental_south_america": [],
    }))
    (cfg / "wishlist.json").write_text(json.dumps({"wishlist": []}))

    monkeypatch.setenv("KIWI_TEQUILA_API_KEY", "dummy")
    httpx_mock.add_response(
        url__contains="api.tequila.kiwi.com",
        json=_kiwi_cheap(),
        status_code=200,
    )
    # Ryanair: return 503 so it's logged as unavailable but doesn't fail run
    httpx_mock.add_response(
        url__contains="services-api.ryanair.com",
        status_code=503, text="down",
    )

    report, envelope_path = run_scan(
        config_dir=cfg,
        history_path=tmp_path / "history" / "observations.jsonl",
        reports_dir=tmp_path / "reports",
        state_path=tmp_path / "state" / "rotation.json",
        email_output_path=tmp_path / "output" / "email.json",
    )
    # One route scanned
    assert len(report.outcomes) == 1
    assert report.outcomes[0].destination_iata == "BCN"
    assert report.outcomes[0].flag is not None
    # JSONL written (1 observation + 1 run_metadata)
    rows = (tmp_path / "history" / "observations.jsonl").read_text().splitlines()
    assert len(rows) == 2
    # Report written
    rpt = tmp_path / "reports" / "2026-04-21.md"
    assert rpt.is_file()
    assert "Barcelona" in rpt.read_text()
    # Email envelope written (deal flagged because cheap prices + cold start)
    env = json.loads(envelope_path.read_text())
    assert env["should_send"] is True
```

- [ ] **Step 2: Run, verify fail**

```bash
pytest tests/test_orchestrator.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `orchestrator.py`**

`src/traveller/orchestrator.py`:
```python
from __future__ import annotations

import os
import time
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from traveller.categories import category_for_iata
from traveller.config import ConfigBundle, load_config
from traveller.emailer import write_email_envelope
from traveller.evaluator.dispatcher import evaluate_route
from traveller.health import write_health_envelope
from traveller.models import (
    Category,
    Destination,
    Fare,
    Observation,
    RunMetadata,
)
from traveller.persistence.baseline import load_route_history
from traveller.persistence.jsonl_store import append_observation, append_run_metadata
from traveller.reporter import RouteOutcome, RunReport, render_report
from traveller.rotation import (
    load_rotation_state,
    next_intercontinental_selection,
    save_rotation_state,
)
from traveller.sources.kiwi import KiwiClient, KiwiError
from traveller.sources.ryanair import RyanairClient, RyanairUnavailable


def _category_for_intercontinental(dest: Destination, pool) -> Category:
    if any(d.iata == dest.iata for d in pool.intercontinental_asia):
        return "intercontinental_asia"
    return "intercontinental_south_america"


def _scan_route(
    *,
    destination: Destination,
    category: Category,
    is_wishlist: bool,
    bundle: ConfigBundle,
    kiwi: KiwiClient,
    ryanair: RyanairClient,
    today: date,
    history_path: Path,
) -> tuple[RouteOutcome, int, list[str]]:
    """Returns (outcome, api_calls_made, errors_for_this_route)."""
    errors: list[str] = []
    api_calls = 0
    win_key = (
        "europe_short_haul" if category == "europe_short_haul"
        else "europe_long_haul" if category == "europe_long_haul"
        else "intercontinental"
    )
    win = bundle.settings.search_windows[win_key]
    date_from = today + timedelta(days=1)
    date_to = today + timedelta(days=win.days_ahead_max)

    fares: list[Fare] = []
    try:
        fares.extend(kiwi.search(
            origin=bundle.settings.origin_iata,
            destination=destination.iata,
            date_from=date_from,
            date_to=date_to,
            nights_min=win.nights_min,
            nights_max=win.nights_max,
            limit=50,
            currency=bundle.settings.currency,
        ))
        api_calls += 1
    except KiwiError as exc:
        errors.append(f"{destination.iata}: kiwi: {exc}")
        return (
            RouteOutcome(
                origin=bundle.settings.origin_iata,
                destination_iata=destination.iata,
                destination_city=destination.city,
                category=category, is_wishlist=is_wishlist,
                best_fare=None, flag=None, skipped=True, error=str(exc),
            ),
            api_calls, errors,
        )
    try:
        fares.extend(ryanair.search(
            origin=bundle.settings.origin_iata,
            destination=destination.iata,
            date_from=date_from,
            date_to=date_to,
            nights_min=win.nights_min,
            nights_max=win.nights_max,
            currency=bundle.settings.currency,
        ))
        api_calls += 1
    except RyanairUnavailable as exc:
        errors.append(f"{destination.iata}: ryanair unavailable: {exc}")

    history = load_route_history(
        history_path,
        origin=bundle.settings.origin_iata,
        destination_iata=destination.iata,
        window=bundle.settings.baseline.baseline_window_observations,
    )
    flag = evaluate_route(
        fares=fares,
        observation_count=history.observation_count,
        prior_prices=history.prices,
        category=category,
        is_wishlist=is_wishlist,
        baseline=bundle.settings.baseline,
        ceilings=bundle.settings.category_ceilings_eur,
        wishlist_multiplier=bundle.settings.wishlist_ceiling_multiplier,
    )
    best_fare = min(fares, key=lambda f: f.price_eur) if fares else None
    return (
        RouteOutcome(
            origin=bundle.settings.origin_iata,
            destination_iata=destination.iata,
            destination_city=destination.city,
            category=category, is_wishlist=is_wishlist,
            best_fare=best_fare, flag=flag,
            skipped=False, error=None,
        ),
        api_calls, errors,
    )


def run_scan(
    *,
    config_dir: Path,
    history_path: Path,
    reports_dir: Path,
    state_path: Path,
    email_output_path: Path,
    today: Optional[date] = None,
) -> tuple[RunReport, Path]:
    t0 = time.monotonic()
    today = today or date.today()
    bundle = load_config(config_dir)
    api_key = os.environ.get(bundle.settings.kiwi_api_key_env_var, "")
    kiwi = KiwiClient(api_key=api_key, backoff_seconds=5.0, max_retries=2)
    ryanair = RyanairClient()

    # Build the per-run route list
    pool = bundle.destinations
    rotation = load_rotation_state(state_path)
    intercont, new_rotation = next_intercontinental_selection(
        state=rotation,
        asia=pool.intercontinental_asia,
        south_america=pool.intercontinental_south_america,
    )

    to_scan: list[tuple[Destination, Category, bool]] = []
    # Wishlist: always
    for w in bundle.wishlist.wishlist:
        to_scan.append((Destination(iata=w.iata, city=w.city), w.category, True))
    # Europe short-haul: all
    for d in pool.europe_short_haul:
        to_scan.append((d, "europe_short_haul", False))
    # Europe long-haul: all
    for d in pool.europe_long_haul:
        to_scan.append((d, "europe_long_haul", False))
    # Intercontinental: rotated
    for d in intercont.asia:
        to_scan.append((d, "intercontinental_asia", False))
    for d in intercont.south_america:
        to_scan.append((d, "intercontinental_south_america", False))

    # Dedup: wishlist entries may duplicate a destination already in pool.
    # Keep only the first (is_wishlist=True takes precedence).
    seen: set[str] = set()
    deduped: list[tuple[Destination, Category, bool]] = []
    for tup in to_scan:
        if tup[0].iata in seen:
            continue
        seen.add(tup[0].iata)
        deduped.append(tup)

    outcomes: list[RouteOutcome] = []
    total_calls = 0
    errors: list[str] = []
    for dest, cat, is_w in deduped:
        outcome, calls, errs = _scan_route(
            destination=dest, category=cat, is_wishlist=is_w,
            bundle=bundle, kiwi=kiwi, ryanair=ryanair,
            today=today, history_path=history_path,
        )
        outcomes.append(outcome)
        total_calls += calls
        errors.extend(errs)

    # Persist observations
    for o in outcomes:
        if o.skipped or o.best_fare is None or o.flag is None:
            continue
        f = o.best_fare
        obs = Observation(
            run_date=today, origin=o.origin,
            destination_iata=o.destination_iata, destination_city=o.destination_city,
            departure_date=f.departure_date, return_date=f.return_date, nights=f.nights,
            price_eur=f.price_eur, airline=f.airline, stops=f.stops, source=f.source,
            is_wishlist=o.is_wishlist, category=o.category,
            market_p15_eur=o.flag.market_p15_eur,
            was_flagged_as_deal=o.flag.is_deal,
            flag_reason=o.flag.reason,
            baseline_median_eur=o.flag.baseline_median_eur,
            phase=o.flag.phase,
        )
        append_observation(obs, history_path)

    runtime = int(time.monotonic() - t0)
    report = RunReport(
        run_date=today, origin=bundle.settings.origin_iata,
        currency=bundle.settings.currency,
        runtime_seconds=runtime, outcomes=outcomes,
        total_api_calls=total_calls,
    )
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"{today.isoformat()}.md"
    report_path.write_text(render_report(report), encoding="utf-8")

    meta = RunMetadata(
        run_date=today,
        run_started_at=datetime.now(timezone.utc).isoformat(),
        run_ended_at=datetime.now(timezone.utc).isoformat(),
        total_routes_queried=len([o for o in outcomes if not o.skipped]),
        total_api_calls=total_calls,
        deals_flagged=len([o for o in outcomes if o.flag and o.flag.is_deal]),
        errors=errors,
        git_commit_sha=None,
    )
    append_run_metadata(meta, history_path)
    save_rotation_state(new_rotation, state_path)

    # Email envelope — monthly health takes priority on first Tuesdays
    wrote_health = write_health_envelope(
        today=today,
        recipient=bundle.settings.email_recipient,
        observations_path=history_path,
        output_path=email_output_path,
    )
    if not wrote_health:
        write_email_envelope(
            report=report,
            recipient=bundle.settings.email_recipient,
            output_path=email_output_path,
        )
    return report, email_output_path
```

- [ ] **Step 4: Run tests, verify pass**

```bash
pytest tests/test_orchestrator.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Run full test suite**

```bash
pytest -v
```
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/traveller/orchestrator.py tests/test_orchestrator.py
git commit -m "feat(orchestrator): end-to-end run_scan with persistence + email envelope"
```

---

### Task 20: CLI entry point

**Files:**
- Create: `src/traveller/cli.py`
- Create: `src/traveller/__main__.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing test**

`tests/test_cli.py`:
```python
import subprocess
import sys


def test_cli_help_exits_zero():
    r = subprocess.run(
        [sys.executable, "-m", "traveller", "--help"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0
    assert "traveller" in r.stdout.lower() or "usage" in r.stdout.lower()
```

- [ ] **Step 2: Run, verify fail**

```bash
pytest tests/test_cli.py -v
```
Expected: non-zero exit / module not runnable.

- [ ] **Step 3: Implement `cli.py` and `__main__.py`**

`src/traveller/cli.py`:
```python
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="traveller", description="Weekly DUB deal scanner")
    parser.add_argument(
        "--config-dir", default="config",
        help="Path to config directory (default: ./config)",
    )
    parser.add_argument(
        "--history", default="history/observations.jsonl",
        help="Path to JSONL history (default: history/observations.jsonl)",
    )
    parser.add_argument(
        "--reports-dir", default="reports",
        help="Path to reports output dir (default: reports)",
    )
    parser.add_argument(
        "--state", default="state/rotation.json",
        help="Rotation state path (default: state/rotation.json)",
    )
    parser.add_argument(
        "--email-output", default="output/email.json",
        help="Email envelope output path (default: output/email.json)",
    )
    sub = parser.add_subparsers(dest="command", required=False)
    sub.add_parser("run", help="Execute one weekly scan")
    args = parser.parse_args(argv)

    # Default command is "run" if none given
    if args.command in (None, "run"):
        from traveller.orchestrator import run_scan
        report, envelope = run_scan(
            config_dir=Path(args.config_dir),
            history_path=Path(args.history),
            reports_dir=Path(args.reports_dir),
            state_path=Path(args.state),
            email_output_path=Path(args.email_output),
        )
        deals = [o for o in report.outcomes if o.flag and o.flag.is_deal]
        print(f"Scan complete. {len(deals)} deal(s); envelope at {envelope}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
```

`src/traveller/__main__.py`:
```python
from traveller.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests, verify pass**

```bash
pytest tests/test_cli.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/traveller/cli.py src/traveller/__main__.py tests/test_cli.py
git commit -m "feat(cli): argparse entry point with run subcommand"
```

---

### Task 21: Scheduled-run prompt for Claude agent

**Files:**
- Create: `prompts/weekly-scan.md`

- [ ] **Step 1: Create `prompts/weekly-scan.md`**

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add prompts/weekly-scan.md
git commit -m "feat(prompts): weekly-scan runbook for scheduled Claude agent"
```

---

### Task 22: scheduled-tasks MCP registration (manual runbook)

**Files:**
- Create: `docs/operations/schedule-setup.md`

- [ ] **Step 1: Create `docs/operations/schedule-setup.md`**

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add docs/operations/schedule-setup.md
git commit -m "docs: scheduled-task setup runbook"
```

---

### Task 23: Excel export helper (optional)

**Files:**
- Create: `scripts/jsonl_to_xlsx.py`
- Create: `tests/test_jsonl_to_xlsx.py`

- [ ] **Step 1: Add `openpyxl` to dev deps**

Edit `pyproject.toml`, append `"openpyxl>=3.1"` to `[project.optional-dependencies] dev`:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-httpx>=0.30",
    "freezegun>=1.4",
    "ruff>=0.4",
    "openpyxl>=3.1",
]
```

Run:
```bash
pip install -e ".[dev]"
```

- [ ] **Step 2: Write failing test**

`tests/test_jsonl_to_xlsx.py`:
```python
import json
import subprocess
import sys
from pathlib import Path

import openpyxl


def test_jsonl_to_xlsx_round_trip(tmp_path: Path):
    src = tmp_path / "observations.jsonl"
    dst = tmp_path / "observations.xlsx"
    rows = [
        {"run_date": "2026-04-21", "origin": "DUB",
         "destination_iata": "BCN", "destination_city": "Barcelona",
         "departure_date": "2026-06-12", "return_date": "2026-06-15",
         "nights": 3, "price_eur": 48.5, "airline": "FR", "stops": 0,
         "source": "kiwi", "is_wishlist": False, "category": "europe_short_haul",
         "market_p15_eur": 62.0, "was_flagged_as_deal": True,
         "flag_reason": "x", "baseline_median_eur": None, "phase": 1},
        {"kind": "run_metadata", "run_date": "2026-04-21",
         "run_started_at": "x", "run_ended_at": "y",
         "total_routes_queried": 1, "total_api_calls": 1,
         "deals_flagged": 1, "errors": [], "git_commit_sha": None},
    ]
    src.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

    r = subprocess.run(
        [sys.executable, "scripts/jsonl_to_xlsx.py", str(src), str(dst)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    wb = openpyxl.load_workbook(dst)
    assert "observations" in wb.sheetnames
    assert "run_metadata" in wb.sheetnames
    obs_ws = wb["observations"]
    assert obs_ws.cell(row=1, column=1).value == "run_date"
    assert obs_ws.cell(row=2, column=3).value == "BCN"
```

- [ ] **Step 3: Run, verify fail**

```bash
pytest tests/test_jsonl_to_xlsx.py -v
```
Expected: failure (script doesn't exist).

- [ ] **Step 4: Implement `scripts/jsonl_to_xlsx.py`**

```python
"""Convert observations.jsonl to an Excel workbook with two sheets."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import openpyxl


def main(src: Path, dst: Path) -> int:
    if not src.is_file():
        print(f"source file not found: {src}", file=sys.stderr)
        return 2
    observations: list[dict] = []
    run_metadata: list[dict] = []
    for line in src.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("kind") == "run_metadata":
            run_metadata.append(row)
        else:
            observations.append(row)
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for sheet_name, rows in (("observations", observations), ("run_metadata", run_metadata)):
        ws = wb.create_sheet(sheet_name)
        if not rows:
            continue
        headers = list(rows[0].keys())
        ws.append(headers)
        for r in rows:
            ws.append([_coerce(r.get(h)) for h in headers])
    wb.save(dst)
    return 0


def _coerce(v):
    if isinstance(v, list):
        return json.dumps(v)
    return v


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: jsonl_to_xlsx.py <src.jsonl> <dst.xlsx>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
```

- [ ] **Step 5: Run tests, verify pass**

```bash
pytest tests/test_jsonl_to_xlsx.py -v
```
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml scripts/jsonl_to_xlsx.py tests/test_jsonl_to_xlsx.py
git commit -m "feat(scripts): optional JSONL-to-XLSX exporter"
```

---

### Task 24: README polish + operations handbook

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace README with fuller version**

```markdown
# Traveller

Weekly round-trip flight-deal scanner. Runs Tuesdays at 08:00 Dublin time as a scheduled Claude agent, emails only when it finds a great deal.

See [the design spec](docs/superpowers/specs/2026-04-16-traveller-design.md) for the full rationale.

## What it does

Every Tuesday:
1. Queries Kiwi Tequila + Ryanair for round-trip fares from DUB to ~35 destinations
2. Evaluates each result against a tiered deal logic (Phase 1 cold-start → Phase 2 baseline → Phase 3 hybrid)
3. Appends observations to `history/observations.jsonl`
4. Writes `reports/YYYY-MM-DD.md`
5. Emails you only if a great deal was found
6. Commits and pushes the new history + report
7. On the first Tuesday of each month, sends a terse "I'm alive" health email regardless of deals

## Development

```bash
python -m venv .venv
source .venv/Scripts/activate  # Windows
pip install -e ".[dev]"
pytest -v
```

## Local dry run

```bash
export KIWI_TEQUILA_API_KEY=your_kiwi_key
python -m traveller run
cat output/email.json
```

## Configuration

- `config/settings.json` — thresholds, ceilings, windows
- `config/destinations.json` — curated Europe + intercontinental pool
- `config/wishlist.json` — "track harder" list (edit to add dream destinations)

Edit these directly. Every run re-reads them.

## Scheduled run

See [docs/operations/schedule-setup.md](docs/operations/schedule-setup.md).

## History → Excel (optional)

```bash
python scripts/jsonl_to_xlsx.py history/observations.jsonl history.xlsx
```

## When to look at the data

- Weekly deal emails are auto-generated — act on them if you want to travel
- Monthly health email (1st Tuesday): confirms the routine is alive
- If you don't get a health email on the expected day, the routine has broken — check `history/observations.jsonl` via `git log`
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: expand README with usage and ops links"
```

---

### Task 25: End-to-end sanity check + push

**Files:** none (verification only)

- [ ] **Step 1: Run full test suite**

```bash
pytest -v
```
Expected: all tests pass.

- [ ] **Step 2: Run ruff**

```bash
ruff check .
ruff format --check .
```
Expected: no lint errors. (If formatting complaints, run `ruff format .` and commit with `style: ruff format`.)

- [ ] **Step 3: Local dry run with real API key (optional, requires network)**

```bash
export KIWI_TEQUILA_API_KEY=<real_key>
python -m traveller run
cat output/email.json
head -n 2 history/observations.jsonl
ls reports/
```
Expected: at least one observation appended; a dated report file exists; `output/email.json` is valid JSON with `should_send` boolean.

- [ ] **Step 4: Push to remote**

```bash
git push -u origin main
```

- [ ] **Step 5: Register the scheduled task** (once remote is live)

Follow `docs/operations/schedule-setup.md`.

---

## Self-review summary

Checked the plan against the spec with fresh eyes:

### Spec coverage

| Spec section | Covered by |
|---|---|
| 3. Architecture | Tasks 0, 19, 20, 21, 22 |
| 4. Data sources (Kiwi, Ryanair, market-ref) | Tasks 4, 5, 6 |
| 5. Storage format (JSONL + Markdown) | Tasks 7, 15, 16 |
| 6. Three-phase evaluator | Tasks 9, 10, 11, 12, 13 |
| 7. Configuration (settings, destinations, wishlist, rotation) | Tasks 1, 2, 3, 14, 15 |
| 8. Outputs (markdown report + email) | Tasks 16, 17 |
| 9. Error handling + monthly health email | Tasks 4, 5, 6, 18, 19 |
| 10. Open items (language, git mechanism, rotation state, wishlist seed, test strategy) | Addressed: Python chosen (Task 0), git handled in scheduled-run prompt (Task 21), rotation state file (Task 14), wishlist empty seed left for user to populate (Task 15), TDD applied throughout |
| 11. Success criteria | Verified by Task 25's sanity-check steps; monthly health + reliability are observed in production over time |
| 12. Future work | Explicitly deferred, nothing in plan |

### Placeholder scan

Checked all steps for TBD / TODO / "implement later" / "add appropriate error handling" / "similar to Task N" / bare "write tests" — none found. Every code step contains the actual code.

### Type consistency check

- `Observation` schema matches across `models.py`, `jsonl_store.py`, `reporter.py`, `orchestrator.py`, and Section 5 of the spec ✓
- `DealFlag` fields (`is_deal`, `phase`, `reason`, `market_p15_eur`, `baseline_median_eur`) consistent across Phase 1/2/3/dispatcher ✓
- `Fare` fields consistent between Kiwi and Ryanair clients and reporter ✓
- `Category` type is the same `Literal[...]` in every file that references it ✓
- `evaluate_phase1` signature matches its call site in `dispatcher.py` ✓
- `evaluate_phase2` and `evaluate_phase3` signatures match dispatcher calls ✓

No inconsistencies found. Plan is ready for execution.
