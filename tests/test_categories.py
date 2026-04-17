from traveller.categories import category_for_iata, ceiling_for
from traveller.models import CategoryCeilings, DestinationPool


def _pool():
    return DestinationPool.model_validate(
        {
            "europe_short_haul": [{"iata": "BCN", "city": "Barcelona"}],
            "europe_long_haul": [{"iata": "ATH", "city": "Athens"}],
            "intercontinental_asia": [{"iata": "BKK", "city": "Bangkok"}],
            "intercontinental_south_america": [{"iata": "GRU", "city": "Sao Paulo"}],
        }
    )


def _ceilings():
    return CategoryCeilings(
        europe_short_haul=80,
        europe_long_haul=130,
        intercontinental_asia=550,
        intercontinental_south_america=600,
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
