# OpenAPI Reference

This page is auto-generated from FastAPI's OpenAPI schema (`ucla-dining-api/src/main.py`).

- **Interactive Explorer**: [Open Swagger UI](api-explorer.html)
- **Raw Schema**: [openapi.json](openapi.json)

## Endpoint Summary

| Method | Path | Parameters | Summary |
|---|---|---|---|
| `GET` | `/health` | — | Health Check |
| `GET` | `/activity` | — | Get All Activity |
| `GET` | `/activity/{location_id}` | `location_id` (path*) | Get Location Activity |
| `GET` | `/halls` | `open` (query) | Get All Halls |
| `GET` | `/halls/{hall_id}` | `hall_id` (path*) | Get Hall |
| `GET` | `/halls/{hall_id}/hours` | `hall_id` (path*), `day` (query) | Get Hall Hours |
| `GET` | `/halls/{hall_id}/menu` | `hall_id` (path*), `date` (query), `meal` (query) | Get Hall Menu |
| `GET` | `/halls/{hall_id}/menu/{date}` | `hall_id` (path*), `date` (path*) | Get Hall Menu By Date |
| `GET` | `/trucks` | — | Get Trucks |
| `GET` | `/gyms` | — | Get All Gyms |
| `GET` | `/gyms/{gym_id}` | `gym_id` (path*) | Get Gym |
| `GET` | `/gyms/{gym_id}/hours` | `gym_id` (path*), `day` (query) | Get Gym Hours |
| `GET` | `/items/{item_id}` | `item_id` (path*) | Get Item |
| `GET` | `/search` | `q` (query), `dietary` (query), `allergen` (query) | Search Items |
| `GET` | `/nutrition/calculate` | `items` (query*) | Calculate Nutrition |

!!! tip "Try it live"
    Use the [Interactive Swagger UI](api-explorer.html) to inspect schemas and test endpoints directly against the production API.
