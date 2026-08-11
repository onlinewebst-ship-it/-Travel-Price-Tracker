"""Command-line interface for the Travel Price Tracker.

Usage:
    python -m tracker.cli track            # run all configured flight & hotel searches
    python -m tracker.cli list             # show configured routes/hotels + last known price
    python -m tracker.cli report <label>   # show price history for one route/hotel label
"""
from __future__ import annotations

import argparse
import json
import os
import sys

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from tracker import alerts, db, travelpayouts_client as tp
from tracker.amadeus_client import AmadeusClient, AmadeusError

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
CURRENCY = os.environ.get("CURRENCY", "GBP")


def _load_json(name: str) -> list[dict]:
    path = os.path.join(CONFIG_DIR, name)
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


def track_flights(client: AmadeusClient) -> None:
    routes = _load_json("routes.json")
    if not routes:
        print("No routes configured in config/routes.json")
        return

    for route in routes:
        label = route["label"]
        try:
            offers = client.search_flight_offers(
                origin=route["origin"],
                destination=route["destination"],
                departure_date=route["departure_date"],
                return_date=route.get("return_date"),
                adults=route.get("adults", 1),
                currency=CURRENCY,
            )
        except AmadeusError as e:
            print(f"[{label}] ERROR: {e}")
            continue

        if not offers:
            print(f"[{label}] No offers found for {route['origin']}->{route['destination']} on {route['departure_date']}")
            continue

        best = min(offers, key=lambda o: float(o["price"]["total"]))
        price = float(best["price"]["total"])
        currency = best["price"]["currency"]
        airline = (best.get("validatingAirlineCodes") or [None])[0]

        prev_min = db.min_flight_price(label, source="amadeus")
        db.record_flight_price(
            label=label,
            origin=route["origin"],
            destination=route["destination"],
            departure_date=route["departure_date"],
            return_date=route.get("return_date"),
            adults=route.get("adults", 1),
            price=price,
            currency=currency,
            airline=airline,
            source="amadeus",
        )

        is_new_low = prev_min is not None and price < prev_min
        marker = " *** NEW LOW ***" if is_new_low else ""
        print(f"[{label}] amadeus: {route['origin']}->{route['destination']}: {price:.2f} {currency} ({len(offers)} offers checked){marker}")

        if is_new_low:
            alerts.send_alert(
                subject=f"Price drop: {label} now {price:.2f} {currency}",
                body=(
                    f"New lowest fare found for {route['origin']} -> {route['destination']}\n"
                    f"Depart: {route['departure_date']}  Return: {route.get('return_date', 'n/a')}\n"
                    f"Price: {price:.2f} {currency} (previous low: {prev_min:.2f} {currency})\n"
                    f"Airline: {airline or 'n/a'}\n"
                    f"Source: Amadeus (live search)"
                ),
            )

        if tp.is_enabled():
            try:
                cheapest = tp.latest_flight_price(route["origin"], route["destination"], currency=CURRENCY)
            except Exception as e:
                print(f"[{label}] travelpayouts: ERROR: {e}")
                cheapest = None

            if cheapest:
                # Field names confirmed against a live call, not Travelpayouts' docs:
                # 'value' is the price, 'depart_date'/'return_date' are plain dates,
                # and there's no 'airline' — 'gate' is the OTA/booking source name.
                tp_price = float(cheapest["value"])
                tp_currency = CURRENCY
                tp_prev_min = db.min_flight_price(label, source="travelpayouts")
                db.record_flight_price(
                    label=label,
                    origin=route["origin"],
                    destination=route["destination"],
                    departure_date=cheapest.get("depart_date", route["departure_date"]),
                    return_date=cheapest.get("return_date", route.get("return_date")),
                    adults=route.get("adults", 1),
                    price=tp_price,
                    currency=tp_currency,
                    airline=cheapest.get("gate"),
                    source="travelpayouts",
                )
                tp_is_new_low = tp_prev_min is not None and tp_price < tp_prev_min
                tp_marker = " *** NEW LOW ***" if tp_is_new_low else ""
                print(f"[{label}] travelpayouts: cached fare {tp_price:.2f} {tp_currency} "
                      f"(any date, found {cheapest.get('found_at', 'n/a')}){tp_marker}")
            else:
                print(f"[{label}] travelpayouts: no cached fares found")


def track_hotels(client: AmadeusClient) -> None:
    hotels_cfg = _load_json("hotels.json")
    if not hotels_cfg:
        print("No hotel searches configured in config/hotels.json")
        return

    for cfg in hotels_cfg:
        label = cfg["label"]
        try:
            hotel_list = client.list_hotels_by_city(cfg["city_code"], max_hotels=cfg.get("max_hotels", 20))
            hotel_ids = [h["hotelId"] for h in hotel_list if "hotelId" in h]
            offers = client.search_hotel_offers(
                hotel_ids=hotel_ids,
                checkin_date=cfg["checkin_date"],
                checkout_date=cfg["checkout_date"],
                adults=cfg.get("adults", 1),
                currency=CURRENCY,
            )
        except AmadeusError as e:
            print(f"[{label}] ERROR: {e}")
            continue

        if not offers:
            print(f"[{label}] No hotel offers found for {cfg['city_code']}")
            continue

        def offer_price(o: dict) -> float:
            return float(o["offers"][0]["price"]["total"])

        best = min(offers, key=offer_price)
        price = offer_price(best)
        currency = best["offers"][0]["price"]["currency"]
        hotel_name = best.get("hotel", {}).get("name")
        hotel_id = best.get("hotel", {}).get("hotelId", "unknown")

        prev_min = db.min_hotel_price(label, source="amadeus")
        db.record_hotel_price(
            label=label,
            hotel_id=hotel_id,
            hotel_name=hotel_name,
            city_code=cfg["city_code"],
            checkin_date=cfg["checkin_date"],
            checkout_date=cfg["checkout_date"],
            adults=cfg.get("adults", 1),
            price=price,
            currency=currency,
            source="amadeus",
        )

        is_new_low = prev_min is not None and price < prev_min
        marker = " *** NEW LOW ***" if is_new_low else ""
        print(f"[{label}] amadeus: {hotel_name or hotel_id}: {price:.2f} {currency} ({len(offers)} hotels checked){marker}")

        if is_new_low:
            alerts.send_alert(
                subject=f"Price drop: {label} hotel now {price:.2f} {currency}",
                body=(
                    f"New lowest hotel rate found in {cfg['city_code']}\n"
                    f"Check-in: {cfg['checkin_date']}  Check-out: {cfg['checkout_date']}\n"
                    f"Hotel: {hotel_name or hotel_id}\n"
                    f"Price: {price:.2f} {currency} (previous low: {prev_min:.2f} {currency})\n"
                    f"Source: Amadeus (live search)"
                ),
            )

        if tp.is_enabled():
            tp_location = cfg.get("travelpayouts_location")
            if not tp_location:
                print(f"[{label}] travelpayouts: skipped (no 'travelpayouts_location' set in config/hotels.json)")
            else:
                try:
                    tp_hotels = tp.cached_hotel_prices(
                        location=tp_location,
                        checkin_date=cfg["checkin_date"],
                        checkout_date=cfg["checkout_date"],
                        adults=cfg.get("adults", 1),
                        currency=CURRENCY,
                    )
                except Exception as e:
                    print(f"[{label}] travelpayouts: ERROR: {e}")
                    tp_hotels = []

                if tp_hotels:
                    cheapest = min(tp_hotels, key=lambda h: h.get("priceFrom", float("inf")))
                    if "priceFrom" not in cheapest:
                        # Docs promised this field; the flight endpoint already showed
                        # Travelpayouts' actual response shape can differ from docs.
                        # Fail loud with the real keys instead of crashing on a KeyError.
                        print(f"[{label}] hotellook: ERROR: expected 'priceFrom' field not found. "
                              f"Got keys: {sorted(cheapest.keys())} — report this so the field mapping can be fixed.")
                    else:
                        tp_price = float(cheapest["priceFrom"])
                        tp_prev_min = db.min_hotel_price(label, source="hotellook")
                        db.record_hotel_price(
                            label=label,
                            hotel_id=str(cheapest.get("hotelId", "unknown")),
                            hotel_name=cheapest.get("hotelName"),
                            city_code=cfg["city_code"],
                            checkin_date=cfg["checkin_date"],
                            checkout_date=cfg["checkout_date"],
                            adults=cfg.get("adults", 1),
                            price=tp_price,
                            currency=CURRENCY,
                            source="hotellook",
                        )
                        tp_is_new_low = tp_prev_min is not None and tp_price < tp_prev_min
                        tp_marker = " *** NEW LOW ***" if tp_is_new_low else ""
                        print(f"[{label}] hotellook: {cheapest.get('hotelName', 'unknown')}: "
                              f"{tp_price:.2f} {CURRENCY} ({len(tp_hotels)} cached hotels){tp_marker}")
                else:
                    print(f"[{label}] hotellook: no cached hotel prices found")


def cmd_track(_args: argparse.Namespace) -> None:
    db.init_db()
    client = AmadeusClient()
    print("== Flights ==")
    track_flights(client)
    print("\n== Hotels ==")
    track_hotels(client)

    if not alerts.email_alerts_enabled():
        print("\n(Email alerts disabled — set SMTP_HOST and ALERT_EMAIL_TO in .env to enable.)")


def _source_summary(min_fn, label: str) -> str:
    parts = []
    for source in ("amadeus", "travelpayouts", "hotellook"):
        low = min_fn(label, source=source)
        if low is not None:
            parts.append(f"{source}={low:.2f} {CURRENCY}")
    return ", ".join(parts) if parts else "no data yet"


def cmd_list(_args: argparse.Namespace) -> None:
    db.init_db()
    print("== Configured flight routes ==")
    for route in _load_json("routes.json"):
        print(f"  {route['label']}: {route['origin']}->{route['destination']} "
              f"{route['departure_date']}..{route.get('return_date', 'one-way')} — "
              f"lowest seen: {_source_summary(db.min_flight_price, route['label'])}")

    print("\n== Configured hotel searches ==")
    for cfg in _load_json("hotels.json"):
        print(f"  {cfg['label']}: {cfg['city_code']} {cfg['checkin_date']}..{cfg['checkout_date']} — "
              f"lowest seen: {_source_summary(db.min_hotel_price, cfg['label'])}")

    if not tp.is_enabled():
        print("\n(Travelpayouts/Hotellook second source disabled — set TRAVELPAYOUTS_TOKEN in .env to enable.)")


def cmd_report(args: argparse.Namespace) -> None:
    db.init_db()
    label = args.label
    flight_rows = db.flight_history(label)
    hotel_rows = db.hotel_history(label)

    if flight_rows:
        print(f"Flight price history for '{label}':")
        for row in flight_rows:
            print(f"  {row['checked_at']}  [{row['source']}]  {row['price']:.2f} {row['currency']}  ({row['airline'] or 'n/a'})")
    elif hotel_rows:
        print(f"Hotel price history for '{label}':")
        for row in hotel_rows:
            print(f"  {row['checked_at']}  [{row['source']}]  {row['price']:.2f} {row['currency']}  ({row['hotel_name'] or row['hotel_id']})")
    else:
        print(f"No price history found for label '{label}'. Run 'track' first, or check config for the exact label.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Travel Price Tracker (flights & hotels via Amadeus API)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("track", help="Run all configured searches and record prices").set_defaults(func=cmd_track)
    sub.add_parser("list", help="List configured routes/hotels and last known prices").set_defaults(func=cmd_list)

    report_parser = sub.add_parser("report", help="Show price history for one label")
    report_parser.add_argument("label", help="Label from config/routes.json or config/hotels.json")
    report_parser.set_defaults(func=cmd_report)

    args = parser.parse_args()
    try:
        args.func(args)
    except AmadeusError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
