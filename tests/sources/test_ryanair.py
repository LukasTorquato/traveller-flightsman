import re
from datetime import date

import pytest
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
        url=re.compile(r".*services-api\.ryanair\.com/farfnd/v4/roundTripFares.*"),
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
    httpx_mock.add_response(status_code=503, text="down")
    client = RyanairClient()
    with pytest.raises(RyanairUnavailable):
        client.search(
            origin="DUB",
            destination="BCN",
            date_from=date(2026, 6, 1),
            date_to=date(2026, 8, 31),
            nights_min=2,
            nights_max=7,
        )
