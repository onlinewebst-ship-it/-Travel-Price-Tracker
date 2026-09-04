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
> originally used shut down completely as a brand on **20 October 2025**.
> Duffel Stays looked like a self-service replacement from their docs, but
> a live test confirmed it's gated behind a sales conversation — not
> self-serve after all (code's still there, ready to go if that ever
> changes). **[LiteAPI](#3-liteapi-hotels)** is the current hotel source instead.
>
> **Current setup: [Travelpayouts](#1-travelpayouts-cached-flight-fares)
> for cached flight fares, [Duffel](#2-duffel-live-flights) for live
> exact-date flights, [LiteAPI](#3-liteapi-hotels) for hotels. Each works
> independently — set up whichever combination you want.**

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

## 2. Duffel (live flights)

[Duffel](https://duffel.com/) does real live flight search (300+ airlines)
for your exact dates — self-service for flights specifically (hotels/Stays
is not, see the warning above).

Worth knowing before you set it up:
- Sign-up is instant, but their **test mode only returns fake sandbox data**
  (a made-up airline called "Duffel Airways") — useless for real price
  tracking. You need a **live** token (`duffel_live_...`, not
  `duffel_test_...`).
- Getting a live token means "activating" your account with identity/
  payment details, since Duffel is built for travel sellers, not just data
  consumers. You don't need to be an accredited travel agency.
- **Scope must be "Read and write", not "Read only".** This was gotten
  wrong once already: Duffel treats creating an offer request (i.e.
  searching) as a "create" action requiring write permission, even though
  nothing gets booked. A read-only token gets a 403
  `insufficient_permissions` on every search. Practical consequence: this
  token *can* technically create real bookings against your Duffel balance
  even though this tool's code never does — treat `.env` as sensitive as a
  password, not just an API key.
- Pricing is pay-per-outcome, not pay-per-search: no charge for searching
  itself (aside from a small $0.005/search fee only if your search-to-book
  ratio exceeds 1500:1, which personal tracking won't come close to), $3
  per confirmed booking (irrelevant here — this tool never books anything).

Setup:
1. Sign up at duffel.com, create a **Read and write** live access token.
2. Set `DUFFEL_TOKEN` in `.env`.

(`tracker/duffel_client.py` also has a `search_stays()` function ready to
go for hotels the moment Stays access is actually enabled on an account —
no code changes needed then, just get access and add
`duffel_latitude`/`duffel_longitude` to `config/hotels.json` entries.)

## 3. LiteAPI (hotels)

[LiteAPI](https://www.liteapi.travel/) (by Nuitée) is the current hotel
source — a free, instant, no-credit-card sandbox signup, unlike Duffel
Stays. **Working and confirmed live**: a sandbox key correctly returned a
real, specific, identifiable property (a real B&B Hotels location in
Paris's 17th arrondissement, not a generic "Test Hotel" placeholder) at a
plausible rate — unlike Duffel, LiteAPI's sandbox key returns real rate
data, not synthetic test data.

Setup:
1. Sign up free at https://www.liteapi.travel/ (redirects into a "Nuitee
   Connect" branded dashboard — that's expected, same company).
2. Dashboard → Developer page → API Keys tab → copy the sandbox key.
3. Set `LITEAPI_KEY` in `.env`.
4. Each entry in `config/hotels.json` needs `liteapi_city_name` and
   `liteapi_country_code` (ISO 2-letter, e.g. `FR` for France).

## 4. Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit .env with your token(s)
```

## 5. Configure, run, and schedule it

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

Edit `config/hotels.json` for hotels — the fields for whichever source(s)
you've configured:

```json
{
  "label": "Paris",
  "checkin_date": "2026-09-05",
  "checkout_date": "2026-09-08",
  "adults": 2,
  "liteapi_city_name": "Paris",
  "liteapi_country_code": "FR",
  "duffel_latitude": 48.8566,
  "duffel_longitude": 2.3522,
  "duffel_radius_km": 5
}
```

Airport codes are IATA codes (e.g. `LHR` = London Heathrow). For
`duffel_latitude`/`duffel_longitude`, look up the city centre coordinates
(e.g. search "\<city\> latitude longitude"). `liteapi_country_code` is the
ISO 2-letter country code (e.g. `FR`, `GB`, `US`).

```bash
python -m tracker.cli track     # fetch current prices, store a snapshot, flag new lows
python -m tracker.cli list      # show all configured searches + lowest price seen
python -m tracker.cli report LHR-BCN   # full price history for one route/hotel
```

Each `track` run appends a row to `prices.db` (SQLite, gitignored) so you
build up a price history over time. Results are tagged by source
(`travelpayouts`, `duffel`, `liteapi`, `amadeus`) so different sources'
prices are never compared against each other as if they were the same
kind of quote.

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
- **Duffel Stays** — looked self-service from the docs, but live-tested as
  gated behind a sales conversation for hotel access specifically (flights
  worked fine on the same account). Code is ready (`search_stays()`) if
  access ever gets granted.

## Notes

- Every source here is an official, documented API reached with your own
  registered credentials — nothing scrapes Airbnb, Booking.com, Google
  Flights, etc., and nothing evades anti-bot protection. Those sites block
  automated access because it's against their terms of service.
- Travelpayouts' response field names differ from their own published docs
  in places, and Duffel Stays turned out to be sales-gated despite reading
  as self-service — both found by testing live, not by trusting docs (see
  git history). Travelpayouts (flights), Duffel (flights), and LiteAPI
  (hotels) are all now confirmed working against live calls with real
  data. If `track` ever reports an "expected field not found" error with a
  list of actual keys — e.g. if a provider changes their response shape in
  the future — that's the defensive handling working as intended: it
  surfaces the real shape instead of crashing, so it's easy to fix the
  field mapping from the diagnostic.
