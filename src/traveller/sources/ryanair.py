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
                fares.append(
                    Fare(
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
                    )
                )
            except (KeyError, ValueError):
                continue
        return fares
