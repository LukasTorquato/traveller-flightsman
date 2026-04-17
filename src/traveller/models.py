from __future__ import annotations

from datetime import date  # noqa: TC003 - needed at runtime by pydantic
from typing import Literal

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
    market_p15_eur: float | None
    was_flagged_as_deal: bool
    flag_reason: str | None
    baseline_median_eur: float | None
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
    git_commit_sha: str | None


class DealFlag(BaseModel):
    """Result of evaluating a single fare against deal logic."""
    model_config = ConfigDict(extra="forbid")
    is_deal: bool
    phase: Literal[1, 2, 3]
    reason: str
    market_p15_eur: float | None
    baseline_median_eur: float | None
