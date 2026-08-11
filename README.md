# Travel Price Tracker

Track flight and hotel prices over time using official travel APIs — no
scraping, no proxies, no anti-bot evasion.

Prices are shown in GBP by default (configurable) for a UK-based traveller.

> **⚠️ Amadeus's free Self-Service API is gone.** This project originally
> used it as the primary source. Amadeus paused new signups in spring 2026
> and fully decommissioned the Self-Service portal (test API keys included)
> on **17 July 2026**. Only their Enterprise APIs remain, which require a
> business application and sales approval — not usable for personal
> tracking. The code still supports Amadeus if you have Enterprise access,
> but it's optional now.
>
> **⚠️ Hotellook is also gone.** The hotel data source this project
> originally used shut down completely as a brand on **20 October 2025**
> — confirmed live (a real 404) and independently (Travelpayouts' own
> closure notice). Hotel tracking now runs on Duffel instead (§3).
>
> **Current setup: [Travelpayouts](#1-travelpayouts-cached-flight-fares)
> for flights (cached fares), [Duffel](#2-duffel-live-flights--hotels)
> for live exact-date flights and hotels. Either works alone; both together
> is best.**

## 1. Travelpayouts (cached flight fares)

[Travelpayouts](https://www.travelpayouts.com/) (Aviasales' affiliate/data
platform) offers a free, self-service **Data API** for flights — genuinely
instant signup, no business approval needed.

1. Sign up free at https://www.travelpayouts.com/, then find your API token
   under your account's API/Tools section.
2. Copy `.env.example` to `.env` and set `TRAVELPAYOUTS_TOKEN`.

**Important limitation:** this endpoint returns the cheapest fare *other
users have recently found* for a route (any nearby date, cached — not a
live search locked to your exact dates). It's a real, useful trend signal,
not a bookable quote for your specific trip.

## 2. Duffel (live flights + hotels)

[Duffel](https://duffel.com/) is a self-service modern replacement for what
Amadeus/Hotellook used to offer — real live prices for your exact dates,
covering flights (300+ airlines) *and* hotels (2M+ properties, "Stays") in
one account. It's currently the only working hotel source in this project.

Worth knowing before you set it up:
- Sign-up is instant, but their **test mode only returns fake sandbox data**
  (a made-up airline called "Duffel Airways") — useless for real price
  tracking. You need a **live** token (`duffel_live_...`, not
  `duffel_test_...`).
- Getting a live token means "activating" your account with identity/
  payment details, since Duffel is built for travel sellers, not just data
  consumers. You don't need to be an accredited travel agency.
- When creating the access token in the Duffel dashboard (Developers →
  Access tokens), use **Read only** scope — this tool only ever searches,
  never books, so a read-only token is strictly safer to hold.
- Pricing is pay-per-outcome, not pay-per-search: no charge for searching
  itself (aside from a small $0.005/search fee only if your search-to-book
  ratio exceeds 1500:1, which personal tracking won't come close to), $3
  per confirmed booking (irrelevant here — this tool never books anything).

Setup:
1. Sign up at duffel.com, create a **Read only** live access token.
2. Set `DUFFEL_TOKEN` in `.env`.
3. For hotels, each entry in `config/hotels.json` needs
   `duffel_latitude` / `duffel_longitude` (Duffel Stays searches by a point
   + radius, not a city name) and optionally `duffel_radius_km` (default 5).

## 3. Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit .env with your token(s)
```

## 4. Configure, run, and schedule it

Edit `config/routes.json` for flights. Each entry needs a unique `label`
(used for history lookups and alerts):

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

Edit `config/hotels.json` for hotels (Duffel only — see §2):

```json
{
  "label": "Paris",
  "checkin_date": "2026-09-05",
  "checkout_date": "2026-09-08",
  "adults": 2,
  "duffel_latitude": 48.8566,
  "duffel_longitude": 2.3522,
  "duffel_radius_km": 5
}
```

Airport codes are IATA codes (e.g. `LHR` = London Heathrow). For
`duffel_latitude`/`duffel_longitude`, look up the city centre coordinates
(e.g. search "\<city\> latitude longitude").

```bash
python -m tracker.cli track     # fetch current prices, store a snapshot, flag new lows
python -m tracker.cli list      # show all configured searches + lowest price seen
python -m tracker.cli report LHR-BCN   # full price history for one route/hotel
```

Each `track` run appends a row to `prices.db` (SQLite, gitignored) so you
build up a price history over time. Results are tagged by source
(`travelpayouts`, `duffel`, `amadeus`) so different sources' prices are
never compared against each other as if they were the same kind of quote.

Schedule it with cron, matching how often prices actually change:

```cron
# every 6 hours
0 */6 * * * cd /path/to/-Travel-Price-Tracker && .venv/bin/python -m tracker.cli track >> tracker.log 2>&1
```

Optional email alerts on a new lowest price: set `SMTP_HOST` and
`ALERT_EMAIL_TO` in `.env` (see `.env.example`).

### Partner APIs that were considered but aren't usable here

- **Skyscanner Partner API** — no self-service signup; requires a business
  application with >100k monthly site traffic and ~2 week approval. Not
  viable for personal tracking.
- **Kiwi.com Tequila API** — used to offer easy self-serve keys, but new
  signups now appear to require a direct partnership; too unreliable to
  build against.
- **Booking.com Demand API** — partner/affiliate approval only, not open
  registration.

## Notes

- Every source here is an official, documented API reached with your own
  registered credentials — nothing scrapes Airbnb, Booking.com, Google
  Flights, etc., and nothing evades anti-bot protection. Those sites block
  automated access because it's against their terms of service.
- Travelpayouts' response field names have been found to differ from their
  own published docs in places (confirmed against live calls — see git
  history). The Duffel integration follows Duffel's documented schema but
  hasn't been confirmed against a live call the same way — if `track`
  reports an "expected field not found" error with a list of actual keys,
  that's this working as intended: it surfaces the real shape instead of
  crashing, so it's easy to fix the field mapping from the diagnostic.
