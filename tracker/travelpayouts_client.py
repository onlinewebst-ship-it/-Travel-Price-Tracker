"""Travelpayouts (Aviasales) Data API — the primary price source now that
Amadeus's free API is gone (see README).

`latest_flight_price` is confirmed working against a live token (verified
manually, field names corrected to match the real response — see git
history). Returns cached/aggregated fares (prices other users have recently
found), not a live real-time search, so treat it as a trend signal rather
than a bookable quote for your exact dates.

`cached_hotel_prices` targets the Hotellook API, which shut down completely
as a brand on 20 Oct 2025 (confirmed both by a live 404 and Travelpayouts'
own closure notice). Kept here for reference / easy resurrection if
Travelpayouts ships a documented replacement, but tracker/cli.py does not
call it — don't wire it back in without confirming a real, working
replacement endpoint first.

Docs (flights): https://travelpayouts.github.io/slate/#flight_data_api

Sign up (free): https://www.travelpayouts.com/ -> get an API token from
your account's "API" section, put it in TRAVELPAYOUTS_TOKEN in .env.
Disabled automatically (no error) if the token isn't set.
"""
from __future__ import annotations

import os
from typing import Any

import requests

FLIGHTS_URL = "https://api.travelpayouts.com/v2/prices/latest"
HOTELS_URL = "https://engine.hotellook.com/api/v2/cache.json"


def is_enabled() -> bool:
    return bool(os.environ.get("TRAVELPAYOUTS_TOKEN"))


def _token() -> str:
    token = os.environ.get("TRAVELPAYOUTS_TOKEN")
    if not token:
        raise RuntimeError("TRAVELPAYOUTS_TOKEN not set")
    return token


def latest_flight_price(
    origin: str,
    destination: str,
    currency: str = "GBP",
) -> dict[str, Any] | None:
    """Cheapest recently-found fare for a route. Dates aren't filterable on
    this endpoint (it returns whatever's been recently cached across dates),
    so use it as a rough trend indicator alongside the Amadeus live search,
    not as a same-date comparison.

    Observed response shape (differs from Travelpayouts' published docs —
    confirmed against a live call): each entry has 'value' (price, not
    'price'), 'depart_date'/'return_date' (plain dates, not
    'departure_at'/'return_at'), and 'gate' (the OTA/booking source name,
    e.g. 'Farera' — there's no 'airline' field)."""
    resp = requests.get(
        FLIGHTS_URL,
        params={
            "origin": origin,
            "destination": destination,
            "currency": currency.lower(),
            "limit": 30,
            "token": _token(),
        },
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Travelpayouts flights API failed ({resp.status_code}): {resp.text}")

    data = resp.json().get("data") or []
    if not data:
        return None
    return min(data, key=lambda d: d.get("value", float("inf")))


def cached_hotel_prices(
    location: str,
    checkin_date: str,
    checkout_date: str,
    adults: int = 1,
    currency: str = "GBP",
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Cached hotel rates for a city/location string (e.g. 'Paris')."""
    resp = requests.get(
        HOTELS_URL,
        params={
            "location": location,
            "checkIn": checkin_date,
            "checkOut": checkout_date,
            "adults": adults,
            "currency": currency.lower(),
            "limit": limit,
            "token": _token(),
        },
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Hotellook API failed ({resp.status_code}): {resp.text}")
    return resp.json() or []
