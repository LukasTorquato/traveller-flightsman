from __future__ import annotations

import time
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
