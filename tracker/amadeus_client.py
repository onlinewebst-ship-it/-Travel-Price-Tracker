"""Thin client for the Amadeus for Developers Self-Service API.

Docs: https://developers.amadeus.com/self-service

Uses the standard OAuth2 client-credentials flow and calls only public,
documented endpoints — no scraping, no anti-bot evasion, no proxies.
"""
from __future__ import annotations

import os
import time
from typing import Any

import requests


class AmadeusError(RuntimeError):
    pass


class AmadeusClient:
    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.client_id = client_id or os.environ.get("AMADEUS_CLIENT_ID")
        self.client_secret = client_secret or os.environ.get("AMADEUS_CLIENT_SECRET")
        self.base_url = (base_url or os.environ.get("AMADEUS_BASE_URL") or "https://test.api.amadeus.com").rstrip("/")

        if not self.client_id or not self.client_secret:
            raise AmadeusError(
                "Missing Amadeus API credentials. Set AMADEUS_CLIENT_ID and "
                "AMADEUS_CLIENT_SECRET (see .env.example) — get free keys at "
                "https://developers.amadeus.com/register"
            )

        self._token: str | None = None
        self._token_expires_at: float = 0.0

    # -- auth -----------------------------------------------------------
    def _get_token(self) -> str:
        if self._token and time.time() < self._token_expires_at - 30:
            return self._token

        resp = requests.post(
            f"{self.base_url}/v1/security/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        if resp.status_code != 200:
            raise AmadeusError(f"Amadeus auth failed ({resp.status_code}): {resp.text}")

        data = resp.json()
        self._token = data["access_token"]
        self._token_expires_at = time.time() + data.get("expires_in", 1800)
        return self._token

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        token = self._get_token()
        resp = requests.get(
            f"{self.base_url}{path}",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        if resp.status_code != 200:
            raise AmadeusError(f"Amadeus GET {path} failed ({resp.status_code}): {resp.text}")
        return resp.json()

    # -- flights ----------------------------------------------------------
    def search_flight_offers(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str | None = None,
        adults: int = 1,
        currency: str = "GBP",
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "originLocationCode": origin,
            "destinationLocationCode": destination,
            "departureDate": departure_date,
            "adults": adults,
            "currencyCode": currency,
            "max": max_results,
        }
        if return_date:
            params["returnDate"] = return_date

        data = self._get("/v2/shopping/flight-offers", params)
        return data.get("data", [])

    # -- hotels -------------------------------------------------------------
    def list_hotels_by_city(self, city_code: str, max_hotels: int = 20) -> list[dict[str, Any]]:
        data = self._get(
            "/v1/reference-data/locations/hotels/by-city",
            {"cityCode": city_code},
        )
        return data.get("data", [])[:max_hotels]

    def search_hotel_offers(
        self,
        hotel_ids: list[str],
        checkin_date: str,
        checkout_date: str,
        adults: int = 1,
        currency: str = "GBP",
    ) -> list[dict[str, Any]]:
        if not hotel_ids:
            return []
        params = {
            "hotelIds": ",".join(hotel_ids),
            "checkInDate": checkin_date,
            "checkOutDate": checkout_date,
            "adults": adults,
            "currency": currency,
            "bestRateOnly": "true",
        }
        data = self._get("/v3/shopping/hotel-offers", params)
        return data.get("data", [])
