# Travel Price Tracker

Track flight and hotel prices over time using the official
[Amadeus for Developers](https://developers.amadeus.com/) Self-Service API —
no scraping, no proxies, no anti-bot evasion. Amadeus is the same GDS data
provider that powers many real booking sites, and its free test tier is
enough for personal price tracking.

Prices are shown in GBP by default (configurable) for a UK-based traveller.

## 1. Get free API credentials

1. Sign up at https://developers.amadeus.com/register (no card needed for the test tier).
2. Create an app in the dashboard — you'll get an **API Key** (Client ID) and **API Secret** (Client Secret).
3. Copy `.env.example` to `.env` and fill in `AMADEUS_CLIENT_ID` / `AMADEUS_CLIENT_SECRET`.

The free test tier has a limited call quota and a smaller flight/hotel dataset
than production — it's fine for checking prices a few times a day.

## 2. Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit .env with your Amadeus keys
```

## 3. Configure what to track

Edit `config/routes.json` for flights and `config/hotels.json` for hotels.
Each entry needs a unique `label` (used for history lookups and alerts):

```json
{
  "label": "LHR-BCN",
  "origin": "LHR",
  "destination": "BCN",
  "departure_date": "2026-09-05",
  "return_date": "2026-09-08",
  "adults": 1
}
```

Airport/city codes are IATA codes (e.g. `LHR` = London Heathrow, `PAR` = Paris).

## 4. Run it

```bash
python -m tracker.cli track     # fetch current prices, store a snapshot, flag new lows
python -m tracker.cli list      # show all configured searches + lowest price seen
python -m tracker.cli report LHR-BCN   # full price history for one route/hotel
```

Each `track` run appends a row to `prices.db` (SQLite, gitignored) so you build
up a price history over time. It doesn't overwrite past data.

## 5. Schedule it (optional)

Run it a few times a day with cron, matching how often flight/hotel prices
actually change:

```cron
# every 6 hours
0 */6 * * * cd /path/to/-Travel-Price-Tracker && .venv/bin/python -m tracker.cli track >> tracker.log 2>&1
```

## 6. Optional email alerts

Set the `SMTP_*` and `ALERT_EMAIL_TO` variables in `.env` to get an email
whenever a route or hotel hits a new lowest price. Leave them blank to skip
email — new lows are always printed to the terminal/log either way.

## Notes

- This only queries Amadeus's own API — it doesn't scrape Airbnb, Booking.com,
  Google Flights, etc. Those sites' anti-bot protections exist because
  automated access is against their terms of service.
- Amadeus's hotel content and flight inventory won't be 100% identical to
  what you see on Google Flights or Booking.com, but it's real, current GDS
  pricing and is the same category of data those aggregators are built on.
- If you outgrow the free test tier, Amadeus offers a paid production tier
  with a full dataset and higher quotas — swap `AMADEUS_BASE_URL` to
  `https://api.amadeus.com` and use production keys.
