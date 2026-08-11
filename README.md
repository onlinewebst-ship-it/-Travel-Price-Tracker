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

## 6. Optional second source: Travelpayouts + Hotellook

[Travelpayouts](https://www.travelpayouts.com/) (Aviasales' affiliate/data
platform) offers a free, self-service **Data API** for flights and a
companion **Hotellook** API for hotels — no business approval needed, just a
free account and an API token. It's a good second opinion alongside Amadeus.

1. Sign up free at https://www.travelpayouts.com/, then find your API token
   under your account's API/Tools section.
2. Put it in `TRAVELPAYOUTS_TOKEN` in `.env`.
3. For hotels, add a `"travelpayouts_location"` field to each entry in
   `config/hotels.json` (a plain city name like `"Paris"` — see the example).

When the token is set, `track` automatically also queries Travelpayouts/
Hotellook and stores results tagged with `source = "travelpayouts"` /
`"hotellook"`, separately from `source = "amadeus"`. `list` and `report`
show both.

**Important difference:** Travelpayouts' flight endpoint returns the
cheapest fare *other users have recently found* for that route (any nearby
date, cached — not a live search for your exact dates), while Amadeus does a
live search for your exact dates. Treat Travelpayouts as a rough trend
signal, and Amadeus as the source of truth for actual bookable prices.

### Partner APIs that were considered but aren't usable here

- **Skyscanner Partner API** — no self-service signup; requires a business
  application with >100k monthly site traffic and ~2 week approval. Not
  viable for personal tracking.
- **Kiwi.com Tequila API** — used to offer easy self-serve keys, but new
  signups now appear to require a direct partnership; too unreliable to
  build against.
- **Booking.com Demand API** — partner/affiliate approval only, not open
  registration.

If any of these becomes accessible to you directly (e.g. you already have
partner credentials), tell me and I can wire it in the same way as
Travelpayouts above.

## Notes

- Every source here is an official, documented API reached with your own
  registered credentials — nothing scrapes Airbnb, Booking.com, Google
  Flights, etc., and nothing evades anti-bot protection. Those sites block
  automated access because it's against their terms of service.
- Amadeus's hotel content and flight inventory won't be 100% identical to
  what you see on Google Flights or Booking.com, but it's real, current GDS
  pricing and is the same category of data those aggregators are built on.
- If you outgrow the free test tier, Amadeus offers a paid production tier
  with a full dataset and higher quotas — swap `AMADEUS_BASE_URL` to
  `https://api.amadeus.com` and use production keys.
