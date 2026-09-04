"""LiteAPI (Nuitée) — hotel search API. Candidate replacement for hotel
tracking now that Hotellook is dead and Duffel Stays turned out to be
sales-gated rather than self-service.

Docs:
  Hotel list: GET  https://api.liteapi.travel/v3.0/data/hotels
  Rates:      POST https://api.liteapi.travel/v3.0/hotels/rates

Auth: X-API-Key header.

Unconfirmed so far: whether a sandbox key (sand_...) returns real-looking
rates or synthetic test data — LiteAPI's docs call it a "production-like
sandbox" but don't say explicitly, unlike Duffel where test mode is
documented as fake. Needs a live call to find out; treat sandbox prices
with that in mind until confirmed either way.
"""
from __future__ import annotations

import os
from typing import Any

import requests

BASE_URL = "https://api.liteapi.travel/v3.0"


class LiteApiError(RuntimeError):
    pass


def is_enabled() -> bool:
    return bool(os.environ.get("LITEAPI_KEY"))


def _headers() -> dict[str, str]:
    key = os.environ.get("LITEAPI_KEY")
    if not key:
        raise LiteApiError("LITEAPI_KEY not set")
    return {
        "X-API-Key": key,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def list_hotels(country_code: str, city_name: str, limit: int = 20) -> list[dict[str, Any]]:
    resp = requests.get(
        f"{BASE_URL}/data/hotels",
        params={"countryCode": country_code, "cityName": city_name, "limit": limit},
        headers=_headers(),
        timeout=30,
    )
    if resp.status_code != 200:
        raise LiteApiError(f"LiteAPI hotel list failed ({resp.status_code}): {resp.text}")
    return resp.json().get("data", [])


def search_rates(
    hotel_ids: list[str],
    checkin_date: str,
    checkout_date: str,
    adults: int = 1,
    currency: str = "GBP",
    guest_nationality: str = "GB",
) -> list[dict[str, Any]]:
    if not hotel_ids:
        return []
    body = {
        "hotelIds": hotel_ids,
        "occupancies": [{"adults": adults}],
        "currency": currency,
        "guestNationality": guest_nationality,
        "checkin": checkin_date,
        "checkout": checkout_date,
        "roomMapping": True,
    }
    resp = requests.post(
        f"{BASE_URL}/hotels/rates",
        json=body,
        headers=_headers(),
        timeout=45,
    )
    if resp.status_code != 200:
        raise LiteApiError(f"LiteAPI rates failed ({resp.status_code}): {resp.text}")
    return resp.json().get("data", [])


def cheapest_rate(hotel_rate_entry: dict[str, Any]) -> tuple[float, str] | None:
    """Best-effort walk of one hotel's rate entry per the documented shape:
    data[].roomTypes[].rates[].retailRate.total[] -> {amount, currency}.
    Returns None (not a raised error) if that path isn't found, so the
    caller can decide how to report it — this is a per-hotel helper, not
    where we want to surface diagnostics."""
    room_types = hotel_rate_entry.get("roomTypes") or []
    best: tuple[float, str] | None = None
    for room in room_types:
        for rate in room.get("rates") or []:
            retail = rate.get("retailRate") or {}
            for total in retail.get("total") or []:
                amount = total.get("amount")
                currency = total.get("currency")
                if amount is None:
                    continue
                if best is None or float(amount) < best[0]:
                    best = (float(amount), currency)
    return best
