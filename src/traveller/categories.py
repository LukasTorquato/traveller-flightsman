from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
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
