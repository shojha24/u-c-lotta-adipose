DEV NOTE: Scraper and API have been updated for UCLA's new dining hall menu format; AWS resource usage is currently paused to save money (see [PRODUCTION.md](PRODUCTION.md) for deployment and CloudWatch instructions).

API accessible via `https://ddy58mflxj.execute-api.us-west-2.amazonaws.com/prod/`

## What I've learned so far:
- **Moving from EC2 + Cron to Serverless (Lambda + EventBridge)**: I originally ran the daily scraper via a cron job on a provisioned EC2 instance because that workflow was familiar. After realizing a 24/7 VM sits idle ~99.7% of the time for a ~3-minute daily job, I migrated the scraper to **AWS Lambda** triggered by **EventBridge Scheduler** (`America/Los_Angeles`), dropping scraper compute costs to essentially $0/month.
- **Caching Strategy & Latency Reduction (~185ms → ~2–3ms, >60x faster)**: Understanding which data updates once a day (menus, hours, nutrition, gyms) versus live (`/activity`) enabled an **end-of-day Pacific Time TTL** in-memory cache in `S3Service` alongside dynamic HTTP `Cache-Control` headers (`max-age` until midnight PT vs. `max-age=60` for `/activity`). Eliminating per-request S3 `HeadObject`/`GetObject` checks dropped warm request latency in CloudWatch from `~185ms` to `~2–3ms`.
- **Picking the Right Storage Over Familiar Databases (S3 + Gzip vs. SQL / MongoDB / Firebase)**: Rather than reaching for SQL or a NoSQL database (MongoDB, Firebase RTDB) out of habit, I realized a once-daily, read-heavy snapshot fits **Amazon S3** much better—zero idle database cost, atomic updates, and trivial pairing with in-memory Lambda caching. Rewriting the full `dining-data.json` once a day has minimal overhead, especially after **gzipping** it down to ~398 KB.
- **Aggregating Multi-Source Data & Cost-Safe Cloud Architecture**: Learned how to combine resilient HTML scraping (handling dynamic meal periods, stations, and holiday schedules) with external/AJAX APIs (`activity_ajax.php`, `nutrition_calc_ajax.php`, GoBoard), while protecting serverless endpoints with API Gateway stage throttling and CloudWatch monitoring.

## Current Functionality

### Scraper ([scraper.py](scraper.py))
- **11 UCLA dining locations**: `b-plate`, `de-neve`, `epic-covel`, `epic-ackerman`, `drey`, `study`, `rende`, `b-cafe`, `cafe-1919`, `feast` (Spice Kitchen), and `bruin-bowl`.
- **Dynamic menus & hours**: Parses 7-day dining hours from `/hours/` and discovers meal periods (e.g., `breakfast`, `lunch`, `dinner`, `all_day`) and stations dynamically per hall.
- **Menu item details**: Scrapes nutrition facts (macro and micronutrient tables), serving size, descriptions, dietary/allergen labels, full ingredient lists, and custom Build-Your-Own items with sub-recipes.
- **Food truck schedules**: Scrapes 7-day schedules across all time slots for `sproul` and `rieber`.
- **Gym hours & locations**: Scrapes regular 7-day hours, special/holiday hours, notes, and locations for `b-fit`, `wooden`, and `kinross`.
- **UCLA APIs**: Supports live dining hall activity levels (`activity_ajax.php`) and multi-item nutrition calculation (`nutrition_calc_ajax.php`).
- **Bootstrap & storage**: Defaults to `dining-data.json` (local or S3), gzip-compresses uploads to S3 (`ContentEncoding: gzip`, with automatic decompression on load), and automatically initializes and populates the file on first run if it does not yet exist.

### REST API ([ucla-dining-api/](ucla-dining-api/))
- **FastAPI + Mangum** (`us-west-2`, Python 3.12 via Serverless Framework) backed by `dining-data.json` in S3 (automatically decompressing gzipped payloads).
- **End-of-day Pacific Time TTL caching**:
  - `S3Service` caches `dining-data.json` in memory until midnight `America/Los_Angeles` (0 S3 calls on warm Lambda invocations within the same PT calendar day, and `HeadObject` validation after rollover).
  - HTTP `Cache-Control` headers set to `public, max-age=<seconds_until_midnight_PT>` for daily data and `public, max-age=60` for live `/activity` endpoints.
- **Endpoints**:
  - `GET /health`
  - `GET /halls`, `GET /halls/{hall_id}`, `GET /halls/{hall_id}/hours`, `GET /halls/{hall_id}/menu`, `GET /halls/{hall_id}/menu/{date}`
  - `GET /items/{item_id}`, `GET /search`, `GET /nutrition/calculate?items=...`
  - `GET /trucks`
  - `GET /gyms`, `GET /gyms/{gym_id}`, `GET /gyms/{gym_id}/hours`
  - `GET /activity`, `GET /activity/{location_id}` (11 dining halls + `b-fit`, `wooden`, `kinross`)

## Next Tasks (Todo)

- [ ] Create online API documentation
- [ ] Advertise!!
- [ ] (Later) Add food truck menus and ASUCLA menus/hours
