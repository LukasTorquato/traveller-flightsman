import re
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
        url=re.compile(r".*api\.tequila\.kiwi\.com/v2/search.*"),
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
            origin="DUB",
            destination="BCN",
            date_from=date(2026, 6, 1),
            date_to=date(2026, 8, 31),
            nights_min=2,
            nights_max=7,
            limit=50,
        )


def test_kiwi_retries_on_429(httpx_mock: HTTPXMock):
    httpx_mock.add_response(status_code=429, text="throttled")
    httpx_mock.add_response(status_code=429, text="throttled")
    httpx_mock.add_response(status_code=200, json=_kiwi_response_json())
    client = KiwiClient(api_key="test-key", backoff_seconds=0.0, max_retries=2)
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


def test_kiwi_gives_up_after_max_retries(httpx_mock: HTTPXMock):
    for _ in range(3):
        httpx_mock.add_response(status_code=429, text="throttled")
    client = KiwiClient(api_key="test-key", backoff_seconds=0.0, max_retries=2)
    with pytest.raises(KiwiError):
        client.search(
            origin="DUB",
            destination="BCN",
            date_from=date(2026, 6, 1),
            date_to=date(2026, 8, 31),
            nights_min=2,
            nights_max=7,
            limit=50,
        )
