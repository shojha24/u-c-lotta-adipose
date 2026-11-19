# Architecture & Caching

## Pipeline Overview

1. **Daily Scraper (`scraper.py`)** runs via **AWS Lambda + EventBridge Scheduler** once daily at `00:05 America/Los_Angeles`.
2. It fetches 7-day dining hours, dynamic hall menus, item nutrition & ingredients, food truck schedules, and gym hours, then writes a **gzip-compressed** snapshot (`dining-data.json`, ~398 KB) to **Amazon S3**.
3. **REST API (`ucla-dining-api/`)** runs FastAPI + Mangum on **AWS Lambda** behind **API Gateway** (`us-west-2`, Python 3.12).

## End-of-Day Caching Strategy

- **In-memory Lambda cache (`S3Service`)**:
  - On cold start, Lambda downloads and decompresses `dining-data.json` from S3 in a single `GetObject` call and caches it in memory until `00:00:00 America/Los_Angeles`.
  - All warm invocations during the same Pacific calendar day perform **0 S3 calls** (no `HeadObject` or `GetObject`), dropping Lambda execution time from `~185ms` to `~2–3ms`.
  - After midnight PT rollover, the next request issues `HeadObject` to check `LastModified` and reloads once the daily scraper uploads fresh data.
- **HTTP `Cache-Control` headers**:
  - Daily snapshot endpoints (`/halls`, `/items`, `/search`, `/trucks`, `/gyms`, `/nutrition/calculate`) emit `Cache-Control: public, max-age=<seconds_until_midnight_PT>`.
  - Live occupancy endpoints (`/activity`, `/activity/{location_id}`) emit `Cache-Control: public, max-age=60`.

## Rate Limiting & Cost Controls

- API Gateway stage throttling caps requests at **10 req/sec** (`burstLimit: 20`).
- CloudWatch alarms monitor API Lambda `Errors`, API Gateway `5XXError`, and Scraper Lambda `Errors` via SNS email notifications.
