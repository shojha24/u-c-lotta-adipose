# API Endpoints

All endpoints return JSON and include CORS headers (`Access-Control-Allow-Origin: *`).

## Health

### `GET /health`
Returns service health status.

```json
{"status": "healthy", "service": "ucla-dining-api"}
```

---

## Dining Halls

### `GET /halls`
Lists all dining halls with their ID, display name, URL, and `isOpen` status.

- **Query params**:
  - `open` *(bool, optional)* — pass `open=true` to return only currently open halls.

### `GET /halls/{hall_id}`
Returns details, 7-day hours, and `isOpen` status for one hall.

### `GET /halls/{hall_id}/hours`
Returns operating hours for a hall.

- **Query params**:
  - `day` *(string, optional)* — 3-letter lowercase weekday (`mon`, `tue`, `wed`, `thu`, `fri`, `sat`, `sun`).

### `GET /halls/{hall_id}/menu`
Returns menus grouped dynamically by date, meal period (e.g., `breakfast`, `lunch`, `dinner`, `all_day`), and station name, with arrays of `item_id`s.

- **Query params**:
  - `date` *(string, optional)* — `YYYY-MM-DD`
  - `meal` *(string, optional)* — normalized meal period key (e.g., `breakfast`, `lunch`, `dinner`, `all_day`)

### `GET /halls/{hall_id}/menu/{date}`
Returns the menu for a specific `YYYY-MM-DD` date.

---

## Menu Items, Search & Nutrition

### `GET /items/{item_id}`
Returns nutrition facts, serving size, description, dietary/allergen labels, and ingredients for a recipe ID (or sub-recipe groups for custom Build-Your-Own items).

### `GET /search`
Searches across all scraped menu items.

- **Query params**:
  - `q` *(string, optional)* — case-insensitive substring match against item `name`
  - `dietary` *(string, optional)* — include items containing this label (e.g., `vegetarian`, `vegan`)
  - `allergen` *(string, optional)* — exclude items containing this allergen label (e.g., `eggs`, `soy`, `wheat`)

### `GET /nutrition/calculate`
Calculates combined nutrition facts live via UCLA's nutrition calculator API.

- **Query params**:
  - `items` *(string, required)* — supports either:
    - Shorthand: `4318:1,2201:2` (`<id>:<multiplier>`) or `4318,2201`
    - UCLA native format: `4318,recipe,1;2201,subrecipe,2;`

---

## Food Trucks

### `GET /trucks`
Returns weekly food truck schedules (`sproul`, `rieber`) keyed by weekday (`mon`–`sun`) and time slot (e.g., `11:00 a.m. – 2:00 p.m.`, `5:00 p.m. – 8:30 p.m.`, `9:00 p.m. – 12:00 a.m.`).

---

## Gyms

### `GET /gyms`
Lists all 3 recreation facilities (`b-fit`, `wooden`, `kinross`) with regular 7-day hours, special/holiday hours, notes, and locations.

### `GET /gyms/{gym_id}`
Returns full details for a single gym (`b-fit`, `wooden`, or `kinross`).

### `GET /gyms/{gym_id}/hours`
Returns regular and special operating hours for a gym.

- **Query params**:
  - `day` *(string, optional)* — weekday (`mon`–`sun`, or full day name).

---

## Live Activity & Occupancy

### `GET /activity`
Returns live activity percentages for all 11 dining halls and live area-by-area headcounts/capacities for all 3 gyms (`b-fit`, `wooden`, `kinross`).

### `GET /activity/{location_id}`
Returns live activity/occupancy for a single dining hall or gym ID.
