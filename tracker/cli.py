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

from tracker import alerts, db, duffel_client as duffel, liteapi_client as liteapi, travelpayouts_client as tp
from tracker.amadeus_client import AmadeusClient, AmadeusError

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
CURRENCY = os.environ.get("CURRENCY", "GBP")


def _load_json(name: str) -> list[dict]:
    path = os.path.join(CONFIG_DIR, name)
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


def track_flights(client: AmadeusClient | None) -> None:
    routes = _load_json("routes.json")
    if not routes:
        print("No routes configured in config/routes.json")
        return

    for route in routes:
        label = route["label"]

        if client is None:
            print(f"[{label}] amadeus: skipped (no AMADEUS_CLIENT_ID/SECRET configured — "
                  f"Amadeus's free Self-Service API was discontinued 17 Jul 2026, see README)")
        else:
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
                print(f"[{label}] amadeus: ERROR: {e}")
                offers = None

            if offers is not None and not offers:
                print(f"[{label}] amadeus: no offers found for {route['origin']}->{route['destination']} on {route['departure_date']}")
            elif offers:
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
                tp_dates = f"{cheapest.get('depart_date', '?')} -> {cheapest.get('return_date', '?')}"
                tp_gate = cheapest.get("gate", "unknown source")
                print(f"[{label}] travelpayouts: cached fare {tp_price:.2f} {tp_currency} "
                      f"for {tp_dates} via {tp_gate} (found {cheapest.get('found_at', 'n/a')}, "
                      f"not necessarily your configured dates — see README){tp_marker}")
            else:
                print(f"[{label}] travelpayouts: no cached fares found")

        if duffel.is_enabled():
            try:
                offers = duffel.search_flight_offers(
                    origin=route["origin"],
                    destination=route["destination"],
                    departure_date=route["departure_date"],
                    return_date=route.get("return_date"),
                    adults=route.get("adults", 1),
                )
            except Exception as e:
                print(f"[{label}] duffel: ERROR: {e}")
                offers = []

            if not offers:
                print(f"[{label}] duffel: no offers found for {route['origin']}->{route['destination']} on {route['departure_date']}")
            else:
                best = min(offers, key=lambda o: float(o.get("total_amount", float("inf"))))
                if "total_amount" not in best:
                    print(f"[{label}] duffel: ERROR: expected 'total_amount' field not found. "
                          f"Got keys: {sorted(best.keys())} — report this so the field mapping can be fixed.")
                else:
                    d_price = float(best["total_amount"])
                    d_currency = best.get("total_currency", CURRENCY)
                    d_airline = best.get("owner", {}).get("name")

                    d_prev_min = db.min_flight_price(label, source="duffel")
                    db.record_flight_price(
                        label=label,
                        origin=route["origin"],
                        destination=route["destination"],
                        departure_date=route["departure_date"],
                        return_date=route.get("return_date"),
                        adults=route.get("adults", 1),
                        price=d_price,
                        currency=d_currency,
                        airline=d_airline,
                        source="duffel",
                    )
                    d_is_new_low = d_prev_min is not None and d_price < d_prev_min
                    d_marker = " *** NEW LOW ***" if d_is_new_low else ""
                    print(f"[{label}] duffel: {route['origin']}->{route['destination']}: "
                          f"{d_price:.2f} {d_currency} ({len(offers)} offers, live search){d_marker}")

                    if d_is_new_low:
                        alerts.send_alert(
                            subject=f"Price drop: {label} now {d_price:.2f} {d_currency}",
                            body=(
                                f"New lowest fare found for {route['origin']} -> {route['destination']}\n"
                                f"Depart: {route['departure_date']}  Return: {route.get('return_date', 'n/a')}\n"
                                f"Price: {d_price:.2f} {d_currency} (previous low: {d_prev_min:.2f} {d_currency})\n"
                                f"Airline: {d_airline or 'n/a'}\n"
                                f"Source: Duffel (live search)"
                            ),
                        )


def track_hotels(client: AmadeusClient | None) -> None:
    hotels_cfg = _load_json("hotels.json")
    if not hotels_cfg:
        print("No hotel searches configured in config/hotels.json")
        return

    for cfg in hotels_cfg:
        label = cfg["label"]

        if client is None:
            print(f"[{label}] amadeus: skipped (no AMADEUS_CLIENT_ID/SECRET configured — "
                  f"Amadeus's free Self-Service API was discontinued 17 Jul 2026, see README)")
        elif "city_code" not in cfg:
            print(f"[{label}] amadeus: skipped (no 'city_code' set in config/hotels.json — "
                  f"only needed if you have Amadeus Enterprise access)")
        else:
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
                print(f"[{label}] amadeus: ERROR: {e}")
                offers = None

            if offers is not None and not offers:
                print(f"[{label}] amadeus: no hotel offers found for {cfg['city_code']}")
            elif offers:
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

        # Hotellook (engine.hotellook.com) shut down completely on 20 Oct 2025 —
        # confirmed by a live 404 from this exact code, and independently by
        # Travelpayouts' own "closure of Hotellook" notice. Not attempting that
        # call anymore: it's a dead host, not a transient error.
        if not duffel.is_enabled() and not liteapi.is_enabled():
            print(f"[{label}] hotellook: skipped — Hotellook shut down 20 Oct 2025. "
                  f"No hotel source configured (set DUFFEL_TOKEN or LITEAPI_KEY in .env, see README)")
        if duffel.is_enabled():
            lat = cfg.get("duffel_latitude")
            lon = cfg.get("duffel_longitude")
            if lat is None or lon is None:
                print(f"[{label}] duffel: skipped (no 'duffel_latitude'/'duffel_longitude' "
                      f"set in config/hotels.json)")
            else:
                try:
                    results = duffel.search_stays(
                        latitude=lat,
                        longitude=lon,
                        checkin_date=cfg["checkin_date"],
                        checkout_date=cfg["checkout_date"],
                        adults=cfg.get("adults", 1),
                        radius_km=cfg.get("duffel_radius_km", 5),
                    )
                except Exception as e:
                    print(f"[{label}] duffel: ERROR: {e}")
                    results = []

                if not results:
                    print(f"[{label}] duffel: no hotel results found near ({lat}, {lon})")
                else:
                    best = min(results, key=lambda r: float(r.get("cheapest_rate_total_amount", float("inf"))))
                    if "cheapest_rate_total_amount" not in best:
                        print(f"[{label}] duffel: ERROR: expected 'cheapest_rate_total_amount' field not found. "
                              f"Got keys: {sorted(best.keys())} — report this so the field mapping can be fixed.")
                    else:
                        d_price = float(best["cheapest_rate_total_amount"])
                        d_currency = best.get("cheapest_rate_currency", CURRENCY)
                        accommodation = best.get("accommodation", {})
                        d_hotel_name = accommodation.get("name")
                        d_hotel_id = accommodation.get("id", "unknown")

                        d_prev_min = db.min_hotel_price(label, source="duffel")
                        db.record_hotel_price(
                            label=label,
                            hotel_id=d_hotel_id,
                            hotel_name=d_hotel_name,
                            city_code=cfg.get("city_code", ""),
                            checkin_date=cfg["checkin_date"],
                            checkout_date=cfg["checkout_date"],
                            adults=cfg.get("adults", 1),
                            price=d_price,
                            currency=d_currency,
                            source="duffel",
                        )
                        d_is_new_low = d_prev_min is not None and d_price < d_prev_min
                        d_marker = " *** NEW LOW ***" if d_is_new_low else ""
                        print(f"[{label}] duffel: {d_hotel_name or d_hotel_id}: "
                              f"{d_price:.2f} {d_currency} ({len(results)} results, live search){d_marker}")

                        if d_is_new_low:
                            alerts.send_alert(
                                subject=f"Price drop: {label} hotel now {d_price:.2f} {d_currency}",
                                body=(
                                    f"New lowest hotel rate found near ({lat}, {lon})\n"
                                    f"Check-in: {cfg['checkin_date']}  Check-out: {cfg['checkout_date']}\n"
                                    f"Hotel: {d_hotel_name or d_hotel_id}\n"
                                    f"Price: {d_price:.2f} {d_currency} (previous low: {d_prev_min:.2f} {d_currency})\n"
                                    f"Source: Duffel (live search)"
                                ),
                            )

        if liteapi.is_enabled():
            city_name = cfg.get("liteapi_city_name")
            country_code = cfg.get("liteapi_country_code")
            if not city_name or not country_code:
                print(f"[{label}] liteapi: skipped (no 'liteapi_city_name'/'liteapi_country_code' "
                      f"set in config/hotels.json)")
            else:
                hotel_list: list[dict] = []
                try:
                    hotel_list = liteapi.list_hotels(country_code, city_name, limit=cfg.get("max_hotels", 20))
                    hotel_ids = [h["id"] for h in hotel_list if "id" in h]
                    rates_data = liteapi.search_rates(
                        hotel_ids=hotel_ids,
                        checkin_date=cfg["checkin_date"],
                        checkout_date=cfg["checkout_date"],
                        adults=cfg.get("adults", 1),
                        currency=CURRENCY,
                    )
                except Exception as e:
                    print(f"[{label}] liteapi: ERROR: {e}")
                    rates_data = []

                if not rates_data:
                    print(f"[{label}] liteapi: no rates found for {city_name}, {country_code}")
                else:
                    hotel_name_by_id = {h.get("id"): h.get("name") for h in hotel_list}
                    li_price = None
                    li_currency = CURRENCY
                    li_hotel_id = None
                    for entry in rates_data:
                        result = liteapi.cheapest_rate(entry)
                        if result is None:
                            continue
                        amount, curr = result
                        if li_price is None or amount < li_price:
                            li_price, li_currency = amount, (curr or CURRENCY)
                            li_hotel_id = entry.get("hotelId")

                    if li_price is None:
                        sample_keys = sorted(rates_data[0].keys()) if rates_data else []
                        print(f"[{label}] liteapi: ERROR: couldn't find a rate in the response shape. "
                              f"First entry keys: {sample_keys} — report this so the field mapping can be fixed.")
                    else:
                        li_hotel_name = hotel_name_by_id.get(li_hotel_id, li_hotel_id)

                        li_prev_min = db.min_hotel_price(label, source="liteapi")
                        db.record_hotel_price(
                            label=label,
                            hotel_id=str(li_hotel_id or "unknown"),
                            hotel_name=li_hotel_name,
                            city_code=cfg.get("city_code", ""),
                            checkin_date=cfg["checkin_date"],
                            checkout_date=cfg["checkout_date"],
                            adults=cfg.get("adults", 1),
                            price=li_price,
                            currency=li_currency,
                            source="liteapi",
                        )
                        li_is_new_low = li_prev_min is not None and li_price < li_prev_min
                        li_marker = " *** NEW LOW ***" if li_is_new_low else ""
                        print(f"[{label}] liteapi: {li_hotel_name}: {li_price:.2f} {li_currency} "
                              f"({len(rates_data)} hotels checked){li_marker}")

                        if li_is_new_low:
                            alerts.send_alert(
                                subject=f"Price drop: {label} hotel now {li_price:.2f} {li_currency}",
                                body=(
                                    f"New lowest hotel rate found in {city_name}, {country_code}\n"
                                    f"Check-in: {cfg['checkin_date']}  Check-out: {cfg['checkout_date']}\n"
                                    f"Hotel: {li_hotel_name}\n"
                                    f"Price: {li_price:.2f} {li_currency} (previous low: {li_prev_min:.2f} {li_currency})\n"
                                    f"Source: LiteAPI"
                                ),
                            )


def cmd_track(_args: argparse.Namespace) -> None:
    db.init_db()
    try:
        client = AmadeusClient()
    except AmadeusError:
        # Amadeus's free Self-Service API portal was discontinued 17 Jul 2026 —
        # no new signups, existing keys deactivated. Not fatal: Travelpayouts/
        # Hotellook can still run. See README for the current source situation.
        client = None

    if client is None and not tp.is_enabled() and not duffel.is_enabled() and not liteapi.is_enabled():
        print("No price sources configured. Amadeus's free API was discontinued — "
              "set TRAVELPAYOUTS_TOKEN, DUFFEL_TOKEN, and/or LITEAPI_KEY in .env (see README).")
        return

    print("== Flights ==")
    track_flights(client)
    print("\n== Hotels ==")
    track_hotels(client)

    if not alerts.email_alerts_enabled():
        print("\n(Email alerts disabled — set SMTP_HOST and ALERT_EMAIL_TO in .env to enable.)")


def _source_summary(min_fn, label: str) -> str:
    parts = []
    for source in ("amadeus", "travelpayouts", "duffel", "liteapi"):
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
        where = cfg.get("city_code") or f"({cfg.get('duffel_latitude')}, {cfg.get('duffel_longitude')})"
        print(f"  {cfg['label']}: {where} {cfg['checkin_date']}..{cfg['checkout_date']} — "
              f"lowest seen: {_source_summary(db.min_hotel_price, cfg['label'])}")

    if not tp.is_enabled():
        print("\n(Travelpayouts disabled — set TRAVELPAYOUTS_TOKEN in .env to enable.)")
    if not duffel.is_enabled():
        print("(Duffel disabled — set DUFFEL_TOKEN in .env to enable live flight search.)")
    if not liteapi.is_enabled():
        print("(LiteAPI disabled — set LITEAPI_KEY in .env to enable hotel search.)")


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
    parser = argparse.ArgumentParser(description="Travel Price Tracker (flights & hotels via Travelpayouts/Hotellook, optionally Amadeus)")
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
