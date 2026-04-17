from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class RouteHistory:
    observation_count: int
    median_eur: float | None
    prices: tuple[float, ...]


def load_route_history(
    path: Path,
    *,
    origin: str,
    destination_iata: str,
    window: int | None = None,
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
