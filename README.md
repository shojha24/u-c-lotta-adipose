DEV NOTE: Scraper and API have been updated for UCLA's new dining hall menu format; AWS resource usage is currently paused to save money (see [PRODUCTION.md](PRODUCTION.md) for deployment and CloudWatch instructions).

API formerly accessible via `https://5xjgg3ho6c.execute-api.us-west-2.amazonaws.com/`

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

- [ ] Redeploy scraper, S3, Lambda/API Gateway, and CloudWatch alarms on AWS (see [PRODUCTION.md](PRODUCTION.md))
- [ ] Add food truck menus and ASUCLA menus/hours
- [ ] Create online API documentation
- [ ] Make Python package as an API wrapper
- [ ] Make a cool project with this!!
