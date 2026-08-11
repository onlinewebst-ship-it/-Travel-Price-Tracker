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
> but it's optional now. **[Travelpayouts](#1-get-a-free-travelpayouts-api-token)
> is the primary source going forward.**
>
> **⚠️ Hotel prices are currently unsupported.** The hotel data source this
> project used (Hotellook) shut down completely as a brand on **20 October
> 2025** — confirmed live (a real 404) and independently (Travelpayouts'
> own closure notice). Flights work fine via Travelpayouts below; hotel
> tracking needs a new source wired in — see [§4](#4-optional-live-exact-date-search-duffel).

## 1. Get a free Travelpayouts API token

[Travelpayouts](https://www.travelpayouts.com/) (Aviasales' affiliate/data
platform) offers a free, self-service **Data API** for flights — genuinely
instant signup, no business approval needed. (Their companion Hotellook
hotel API is discontinued — see the warning above.)

1. Sign up free at https://www.travelpayouts.com/, then find your API token
   under your account's API/Tools section.
2. Copy `.env.example` to `.env` and set `TRAVELPAYOUTS_TOKEN`.

**Important limitation:** this endpoint returns the cheapest fare *other
users have recently found* for a route (any nearby date, cached — not a
live search locked to your exact dates). It's a real, useful trend signal,
not a bookable quote for your specific trip. See [§4](#4-optional-live-exact-date-search-duffel)
for a live-search option.

## 2. Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit .env with your Travelpayouts token
```

## 3. Configure, run, and schedule it

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

`config/hotels.json` still exists and is still read, but every entry in it
currently just prints a "hotellook: skipped, discontinued" line — see the
warning above. Leave it as-is or empty it out; either is fine.

Airport/city codes are IATA codes (e.g. `LHR` = London Heathrow, `PAR` = Paris).

```bash
python -m tracker.cli track     # fetch current prices, store a snapshot, flag new lows
python -m tracker.cli list      # show all configured searches + lowest price seen
python -m tracker.cli report LHR-BCN   # full price history for one route/hotel
```

Each `track` run appends a row to `prices.db` (SQLite, gitignored) so you
build up a price history over time. Results are tagged by source
(`travelpayouts`, `amadeus`) so different sources' prices are never
compared against each other as if they were the same kind of quote.

Schedule it with cron, matching how often prices actually change:

```cron
# every 6 hours
0 */6 * * * cd /path/to/-Travel-Price-Tracker && .venv/bin/python -m tracker.cli track >> tracker.log 2>&1
```

Optional email alerts on a new lowest price: set `SMTP_HOST` and
`ALERT_EMAIL_TO` in `.env` (see `.env.example`).

## 4. Optional: live, exact-date search — and the only current hotel option (Duffel)

If you want real live prices for your exact dates (not cached "recently
found" fares), or you want hotel tracking back at all (see the warning
above), [Duffel](https://duffel.com/) is a genuinely self-service modern
replacement for what Amadeus/Hotellook used to offer — covers flights (300+
airlines) *and* hotels (2M+ properties, "Stays") in one account.

Trade-offs versus Travelpayouts, worth knowing before you set it up:
- Sign-up is instant, but their **test mode only returns fake sandbox data**
  (a made-up airline called "Duffel Airways") — useless for real price
  tracking.
- Real prices require **live mode**, which means "activating" your account
  with identity/payment details, since Duffel is built for travel sellers,
  not just data consumers. You don't need to be an accredited travel
  agency, but you do need to go through that activation step.
- Pricing is pay-per-outcome, not pay-per-search: no charge for searching
  itself (aside from a small $0.005/search fee only if your search-to-book
  ratio exceeds 1500:1, which personal tracking won't come close to), $3
  per confirmed booking (irrelevant here — this tool never books anything).

This isn't wired into the code yet, deliberately — it involves handing over
account/identity details, which is your call to make, not something to set
up on your behalf without asking. Say the word and it can be added the same
way Travelpayouts was.

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
  history). If a future API response looks unexpected, `track` reports the
  actual field names it received rather than crashing, so it's easy to
  diagnose and fix.
