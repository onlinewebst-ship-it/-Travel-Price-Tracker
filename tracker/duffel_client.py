"""Duffel API client — live flight search (Offer Requests) and hotel search
(Stays), replacing what Amadeus/Hotellook used to cover.

Requires a **live** access token (`duffel_live_...`) for real prices — test
tokens (`duffel_test_...`) only return fake sandbox data from a made-up
airline ("Duffel Airways"). Getting a live token means activating the
Duffel account (identity/payment details) — see README §4.

Docs:
  Flights: https://duffel.com/docs/api/v2/offer-requests
  Stays:   https://duffel.com/docs/api/v2/search

Not yet confirmed against a live call at the time this was written (unlike
the Travelpayouts client, which was fixed against real responses earlier
today) — field names below follow Duffel's documented schema, but expect to
report back an unexpected-shape diagnostic rather than crash if reality
differs, same pattern used for Travelpayouts.
"""
from __future__ import annotations

import os
from typing import Any

import requests

BASE_URL = "https://api.duffel.com"
DUFFEL_VERSION = "v2"


class DuffelError(RuntimeError):
    pass


def is_enabled() -> bool:
    return bool(os.environ.get("DUFFEL_TOKEN"))


def _headers() -> dict[str, str]:
    token = os.environ.get("DUFFEL_TOKEN")
    if not token:
        raise DuffelError("DUFFEL_TOKEN not set")
    return {
        "Authorization": f"Bearer {token}",
        "Duffel-Version": DUFFEL_VERSION,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def search_flight_offers(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str | None = None,
    adults: int = 1,
    cabin_class: str = "economy",
) -> list[dict[str, Any]]:
    """Live search for an exact-date itinerary. Returns Duffel 'offer' objects."""
    slices = [{"origin": origin, "destination": destination, "departure_date": departure_date}]
    if return_date:
        slices.append({"origin": destination, "destination": origin, "departure_date": return_date})

    body = {
        "data": {
            "slices": slices,
            "passengers": [{"type": "adult"} for _ in range(adults)],
            "cabin_class": cabin_class,
        }
    }
    resp = requests.post(
        f"{BASE_URL}/air/offer_requests",
        params={"return_offers": "true"},
        json=body,
        headers=_headers(),
        timeout=45,
    )
    if resp.status_code not in (200, 201):
        raise DuffelError(f"Duffel offer_requests failed ({resp.status_code}): {resp.text}")

    data = resp.json().get("data", {})
    return data.get("offers", [])


def search_stays(
    latitude: float,
    longitude: float,
    checkin_date: str,
    checkout_date: str,
    adults: int = 1,
    radius_km: float = 5,
) -> list[dict[str, Any]]:
    """Live hotel search around a point. Returns Duffel Stays 'search result' objects."""
    body = {
        "data": {
            "location": {
                "radius": radius_km,
                "geographic_coordinates": {"latitude": latitude, "longitude": longitude},
            },
            "check_in_date": checkin_date,
            "check_out_date": checkout_date,
            "guests": [{"type": "adult"} for _ in range(adults)],
        }
    }
    resp = requests.post(
        f"{BASE_URL}/stays/search",
        json=body,
        headers=_headers(),
        timeout=45,
    )
    if resp.status_code not in (200, 201):
        raise DuffelError(f"Duffel stays search failed ({resp.status_code}): {resp.text}")

    data = resp.json().get("data", {})
    return data.get("results", [])
