# UCLA Dining API

REST API for UCLA dining hall menus, operating hours, food truck schedules, recreation center hours & live occupancy, and multi-item nutrition calculation.

**Base URL**

```text
https://ddy58mflxj.execute-api.us-west-2.amazonaws.com/prod
```

## Quickstart

```bash
# Check API health
curl -s https://ddy58mflxj.execute-api.us-west-2.amazonaws.com/prod/health

# List all 11 dining locations and whether they are currently open
curl -s https://ddy58mflxj.execute-api.us-west-2.amazonaws.com/prod/halls

# Get Bruin Plate's menu for today
curl -s https://ddy58mflxj.execute-api.us-west-2.amazonaws.com/prod/halls/b-plate/menu

# Get live activity levels across all 11 dining halls + 3 gyms
curl -s https://ddy58mflxj.execute-api.us-west-2.amazonaws.com/prod/activity

# Search menu items and calculate combined nutrition
curl -s "https://ddy58mflxj.execute-api.us-west-2.amazonaws.com/prod/search?q=chicken"
curl -s "https://ddy58mflxj.execute-api.us-west-2.amazonaws.com/prod/nutrition/calculate?items=4318:1,2201:2"
```

## Supported Location IDs

### Dining Locations (`hall_id`)
| ID | Name |
|---|---|
| `b-plate` | Bruin Plate |
| `de-neve` | De Neve Dining |
| `epic-covel` | Epicuria at Covel |
| `epic-ackerman` | Epicuria at Ackerman |
| `feast` | Feast at Rieber / Spice Kitchen |
| `rende` | Rendezvous |
| `b-cafe` | Bruin Café |
| `cafe-1919` | Café 1919 |
| `drey` | The Drey |
| `study` | The Study at Hedrick |
| `bruin-bowl` | Bruin Bowl |

### Gyms (`gym_id`)
| ID | Name |
|---|---|
| `b-fit` | Bruin Fitness Center |
| `wooden` | John Wooden Center |
| `kinross` | Kinross Recreation Center |
