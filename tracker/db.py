"""SQLite storage for flight and hotel price snapshots."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

DB_PATH = os.environ.get("TRACKER_DB_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "prices.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS flight_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    departure_date TEXT NOT NULL,
    return_date TEXT,
    adults INTEGER NOT NULL,
    price REAL NOT NULL,
    currency TEXT NOT NULL,
    airline TEXT,
    checked_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hotel_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    hotel_id TEXT NOT NULL,
    hotel_name TEXT,
    city_code TEXT NOT NULL,
    checkin_date TEXT NOT NULL,
    checkout_date TEXT NOT NULL,
    adults INTEGER NOT NULL,
    price REAL NOT NULL,
    currency TEXT NOT NULL,
    checked_at TEXT NOT NULL
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_flight_price(
    label: str,
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str | None,
    adults: int,
    price: float,
    currency: str,
    airline: str | None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO flight_prices
               (label, origin, destination, departure_date, return_date, adults, price, currency, airline, checked_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (label, origin, destination, departure_date, return_date, adults, price, currency, airline, _now()),
        )


def record_hotel_price(
    label: str,
    hotel_id: str,
    hotel_name: str | None,
    city_code: str,
    checkin_date: str,
    checkout_date: str,
    adults: int,
    price: float,
    currency: str,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO hotel_prices
               (label, hotel_id, hotel_name, city_code, checkin_date, checkout_date, adults, price, currency, checked_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (label, hotel_id, hotel_name, city_code, checkin_date, checkout_date, adults, price, currency, _now()),
        )


def min_flight_price(label: str, exclude_latest: bool = False) -> float | None:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT price FROM flight_prices WHERE label = ? ORDER BY checked_at ASC", (label,)
        ).fetchall()
    if not rows:
        return None
    prices = [r["price"] for r in rows]
    if exclude_latest and len(prices) > 1:
        prices = prices[:-1]
    return min(prices)


def min_hotel_price(label: str, exclude_latest: bool = False) -> float | None:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT price FROM hotel_prices WHERE label = ? ORDER BY checked_at ASC", (label,)
        ).fetchall()
    if not rows:
        return None
    prices = [r["price"] for r in rows]
    if exclude_latest and len(prices) > 1:
        prices = prices[:-1]
    return min(prices)


def flight_history(label: str, limit: int = 30) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM flight_prices WHERE label = ? ORDER BY checked_at DESC LIMIT ?",
            (label, limit),
        ).fetchall()


def hotel_history(label: str, limit: int = 30) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM hotel_prices WHERE label = ? ORDER BY checked_at DESC LIMIT ?",
            (label, limit),
        ).fetchall()
