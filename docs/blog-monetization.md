# Travelpayouts monetization for travel-blog.co.uk

Reference notes for wiring up Travelpayouts affiliate monetization on the
WordPress blog `travel-blog.co.uk`. This is a separate account feature from
the price-tracking API used elsewhere in this repo, but it's the **same
Travelpayouts account** — one login covers both.

A fuller step-by-step version of this guide (tables, checklists, and UK
disclosure notes laid out for easier reading) was also published as an
artifact for following along in the browser while working in the WordPress
dashboard. This file is the durable/plain-text copy of the same reference.

## 1. One account, two uses

If a `TRAVELPAYOUTS_TOKEN` is already set up for this repo's price tracker,
that's the same Travelpayouts account. Log into
https://www.travelpayouts.com/ and add `travel-blog.co.uk` as a new
**Project** rather than creating a second account.

## 2. Add the site & get your Partner ID

- Dashboard → **Add website** → enter `travel-blog.co.uk`, pick "Travel blog"
  as the category.
- You'll be asked to install **Drive** (a small verification script/plugin)
  to confirm ownership and unlock full functionality.
- Your account-wide **Partner ID** (formerly called "marker") is shown in
  the lower-left of the dashboard. It's baked automatically into every link
  and widget you generate — no manual URL editing needed.
- Optional: **SubIDs** let you tag links yourself (e.g. per blog post) to
  see which content converts.

**Confirmed for this account: Partner ID `763127`.** This is a public
tracking number — safe to appear in URLs, not a secret. It is **not** the
same as `TRAVELPAYOUTS_TOKEN` used by this repo's price tracker (that's a
separate, longer API secret from the account's API/Tools section) — don't
substitute one for the other.

Docs: [What is Travelpayouts](https://support.travelpayouts.com/hc/en-us/articles/203955593-What-is-Travelpayouts-and-how-it-works) · [ID and SubID](https://support.travelpayouts.com/hc/en-us/articles/203955653-ID-and-SubID-Affiliate-marker-and-additional-marker) · [Install Drive](https://support.travelpayouts.com/hc/en-us/articles/21844864838290-How-to-install-the-Travelpayouts-script-on-your-website)

## 3. Affiliate deep links

Don't hand-build URLs — use one of these so your Partner ID and tracking
stay intact:

- **Link Generator** (in-dashboard, per program: Aviasales, Booking.com,
  Hotellook, etc.) — fill in a form, get a short `tp.st` link.
- **Chrome extension** — generate a link from any page you're browsing.
- **LinkSwitcher** — free tool that auto-converts plain links already in
  your blog content into affiliate links.

Docs: [Getting started with affiliate links](https://support.travelpayouts.com/hc/en-us/articles/360027912851-Getting-started-with-affiliate-links) · [How to create and use affiliate links](https://support.travelpayouts.com/hc/en-us/articles/360027634052-How-to-%D1%81reate-and-use-affiliate-links) · [LinkSwitcher](https://www.travelpayouts.com/blog/travelpayouts-linkswitcher/)

## 4. WordPress widgets

- Install the official **Travelpayouts WordPress plugin**.
- In the dashboard, configure a widget (flight search form, hotel calendar,
  comparison table, tour carousel, map) → **Embed widget** → copy the
  shortcode → paste into any post/page via the block editor.

Docs: [Install WordPress plugin](https://support.travelpayouts.com/hc/en-us/articles/115000466572-How-to-install-Travelpayouts-Wordpress-plugin) · [Adding widgets via plugin](https://support.travelpayouts.com/hc/en-us/articles/115000456711-How-to-add-widgets-tables-and-links-using-the-plugin)

## 5. White Label (bigger commitment — do this later)

Two types:

| | Widget type | Page type |
|---|---|---|
| What it is | Search form embedded in an existing page | Full branded booking subdomain (e.g. `avia.travel-blog.co.uk`) |
| Setup | None beyond embedding | CNAME DNS record → `whitelabel.travelpayouts.com`; SSL auto-provisions in ~48h |
| Best for | Starting out | Once you have real, consistent traffic |

Revenue share model: 30% affiliate share.

Docs: [What is White Label Web](https://support.travelpayouts.com/hc/en-us/articles/203955753-What-is-White-Label-Web-by-Travelpayouts) · [White Label Web setup guide](https://support.travelpayouts.com/hc/en-us/articles/16436383582226-Travelpayouts-White-Label-Web-Setup-Guide) · [WordPress White Label](https://support.travelpayouts.com/hc/en-us/articles/115003926707-How-to-implement-a-White-Label-in-Wordpress)

## UK disclosure requirement

The ASA's CAP Code requires clear, upfront disclosure of affiliate
relationships (e.g. "This post contains affiliate links — I may earn a
commission at no extra cost to you") on any page carrying these links or
widgets. Add it near the top of posts that use them, not buried in a footer.

## Recommended order

1. Add the project, get the Partner ID (5 min).
2. Deep links via LinkSwitcher across existing posts (fast, low effort, immediate).
3. Widgets on high-traffic posts (flight/hotel search forms).
4. White Label — Widget type first; Page type only once traffic justifies it.
