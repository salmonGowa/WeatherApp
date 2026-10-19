# Weather-Aware Truck Routing

A React + Django app that helps a truck driver choose the safest route between two places, given a departure time and load weight. It generates three route options, samples the forecast along each route **at the truck's estimated arrival time at each checkpoint**, scores the conditions with the assessment's risk and load rules, and recommends a route. Routes, checkpoints, ETAs and a 0–48 h corridor weather heatmap are shown on a map.
                                                                                    |

**Frontend**  React 19, TypeScript, Vite, Tailwind CSS v4, Leaflet, TanStack Query                  
**Backend**   Django 4.2, Django REST Framework, httpx                                              
**Routing**   [OSRM](https://project-osrm.org/) public                     
**Weather**   [Open-Meteo](https://open-meteo.com/) hourly forecast (wind, rain, showers, snowfall) 
**Geocoding** [Photon](https://photon.komoot.io/) (OpenStreetMap)                                   
All third-party services are free and need no API keys.

---

## Quick start

bash
# Backend (Python 3.12+)
cd backend
python -m venv ../env && source ../env/bin/activate
pip install -r requirements.txt     # requirements-mysql.txt to use MySQL
python manage.py runserver            # http://127.0.0.1:8000/api/

# Frontend -have node installed
cd frontend
npm install
npm run dev                           # http://localhost:5173


No configuration is required. With no `DATABASE_NAME` set, Django uses SQLite; the API is stateless and only Django admin uses a database. See 
### Code style

The Python code follows **PEP 8**: 79-character lines, and 72 for comments and docstrings. Black formats it and Ruff lints it, both configured in [`backend/pyproject.toml`](backend/pyproject.toml):

```bash
cd backend && black . && ruff check .
```

`pre-commit install` runs both checks on every commit (see [`.pre-commit-config.yaml`](.pre-commit-config.yaml)).

### Tests

```bash
cd backend && pytest        # 87 tests: risk rules, HOS, planner, heatmap grid, API adapters, endpoints
cd frontend && npm test     # timeline interpolation, colour ramps, formatting
```

---



### 1. Routes (`api/services/routing.py`)

- OSRM is asked for `alternatives=3`. It often returns fewer, because it only reports alternatives that pass its own quality filters. In that case extra candidates are made by routing through a **via point offset perpendicular** to the origin-destination line (+/-15%, then +/-30% of the straight-line distance).
- A candidate is kept only if it is **genuinely different**: less than 85% of its length runs within 1.5 km of an existing route. It must also take no more than 1.5× the fastest route's time. Such routes carry a `via` tag in the UI.

### 2. Checkpoints and ETAs (`api/services/planner.py`, `api/services/hos.py`)

- Checkpoints are placed at 0, N, 2N, … miles along the route geometry, plus the destination, where N is 10, 25 or 50 as chosen by the user.
- **ETAs come from OSRM's per-segment durations.** The public OSRM server uses a car profile, so each segment's speed is capped at `TRUCK_MAX_SPEED_MPH` (default 65).
- **Hours of service** (on by default, toggle in the UI): a simplified FMCSA model for property carriers. It adds a 30-minute break after 8 hours of driving and a 10-hour rest after 11 hours. On long trips this changes ETAs, and so the forecast hour used, by many hours. Break and rest locations appear on the map.

### 3. Weather at the ETA (`api/services/weather.py`)

- Open-Meteo hourly variables are requested in mph and inches. Rain rate = `rain + showers`, since Open-Meteo reports convective showers separately. Snow rate = `snowfall` in in/hr.
- Each checkpoint reads its series **at its own ETA**. Wind is interpolated linearly between hourly values. Precipitation uses the hourly bucket the ETA falls in, because Open-Meteo's hourly value is the total for the preceding hour.
- Wind risk uses the **sustained** 10 m wind. Gusts are shown for information only.
- Points are snapped to a 0.1 degrees grid (~11 km), roughly the native resolution of the forecast models. This removes duplicate requests where routes overlap and lets the plan and the heatmap share cached forecasts.

### 4. Risk rules (`api/services/risk.py`)

The thresholds are in the assessment document. Where the table's bands touch.

- Wind bands are whole mph ("25–34", "35–44"), so fractional speeds fall in the band of their lower edge: 34.9 mph is Moderate.
- For rain and snow, the top band is exclusive (">1.00"), so every band includes its upper edge: 0.25 in/hr is Moderate.
- **Load rules** raise the wind level: 45–54 mph with > 30,000 lb becomes **No Travel**, and 35–44 mph with > 40,000 lb becomes **Severe**. At => 55 mph the base table already gives No Travel.
- A checkpoint's level is the **worst** of its wind, rain and snow levels. The popup shows which condition caused it and whether a load rule applied.

### 5. Recommendation

Each checkpoint represents the stretch of road halfway to its neighbours, so the represented miles add up exactly to the route length. Routes are ranked **lexicographically**:

1. fewest **No Travel** miles (a stricter form of rule 1: a route the truck shouldn't drive never wins a tie-break)
2. fewest **Severe** miles
3. fewest **High** miles
4. lowest **average risk** (distance-weighted mean of 0 = Low … 4 = No Travel)
5. shortest **travel time** (including HOS stops)

Values are rounded (0.1 mi, 0.01 risk, 0.01 h) before comparing, so floating-point noise can't decide the result. The UI states the criterion that separated the winner from each other route, and warns when even the best route includes Severe or No Travel conditions.

### 6. Corridor heatmap (`api/services/heatmap.py`, `components/map/GridHeatmapLayer.ts`)

- The backend lays a **regular grid in Web Mercator** over the routes and keeps the cells within 40 miles of any route. It aims for about 250 cells, sized between 10 and 80 km depending on trip length. It returns 49 hourly frames (departure hour + 0…48 h) of wind, rain, snow and load-adjusted risk.
- The frontend draws the grid as a **canvas with one pixel per cell**, stretched over the grid bounds as a Leaflet image overlay. The grid is regular in Mercator, like the map, so the stretch is exact. The browser's bilinear scaling produces the smooth gradient, and transparent cells outside the corridor give it soft edges.
- Moving the slider rewrites a few hundred pixels with `putImageData`, interpolating between hourly frames. It makes no network requests and doesn't re-render React or Leaflet layers. Playback uses `requestAnimationFrame`.
- A truck icon marker shows where the selected route's truck is at the slider time, staying parked during HOS stops. A tick on the slider marks its arrival.

---

## API

| Method | Path                     | Purpose                                   |
| ------ | ------------------------ | ----------------------------------------- |
| `GET`  | `/api/geocode/?q=denver` | Place search                              |
| `POST` | `/api/plan/`             | Routes, checkpoints, risk, recommendation |
| `POST` | `/api/heatmap/`          | Corridor grid + 0–48 h hourly frames      |
| `GET`  | `/api/health/`           | Health check                              |

```jsonc
// POST /api/plan/
{
  "origin": { "lat": 41.88, "lon": -87.63, "label": "Chicago" },
  "destination": { "lat": 39.74, "lon": -104.99, "label": "Denver" },
  "departure": "2026-10-18T14:00:00Z", //10 days ahead (forecast horizon)
  "load_lb": 42000,
  "interval_miles": 25, // 10 | 25 | 50
  "apply_hos": true,
}
```

If an upstream service fails, the API returns `502` with `{"detail", "service"}`, and the UI shows that message. Transient `429`/`5xx` errors and timeouts are retried with exponential backoff.

---

## Project layout

```
backend/
  api/services/   routing · weather · geocoding · risk · hos · planner · heatmap · geometry · http
  api/tests/      pytest suite (external APIs mocked with respx)
  api/controllers/  request handling per resource (validate - call services - respond, upstream failures - 502)
  api/views.py    thin DRF ViewSets that only delegate to controllers; routes via SimpleRouter in urls.py
frontend/
  src/components/ TripForm, LocationInput, RouteList, CheckpointList
  src/components/map/  MapView (imperative Leaflet), GridHeatmapLayer, HeatmapControls, popups
  src/lib/        risk palette, colour ramps, timeline interpolation, formatting, shared Tailwind class strings (ui.ts)
  src/index.css   Tailwind import, design tokens (@theme, light/dark), Leaflet overrides
  src/services/api.ts  typed API client
```

## Deployment

[`render.yaml`](render.yaml) defines the API (gunicorn + WhiteNoise) and the static frontend. Set:

- API: `CORS_ALLOWED_ORIGINS` = the frontend URL. Set `REDIS_URL` too if you want a cache shared across workers.
- Frontend: `VITE_API_URL` = `https://<api-host>/api/`

`mysqlclient` lives in `backend/requirements-mysql.txt`, so hosted builds don't need MySQL client headers. Install that file instead only if you run locally with `DATABASE_NAME` set.

## Limitations and notes

- **Free-tier APIs.** The public Open-Meteo API is sometimes slow or overloaded. A cold plan can take 30–90 s, and responses are cached for 30 minutes, so repeat plans return almost instantly. For production, set `OPEN_METEO_API_KEY` with `OPEN_METEO_URL=https://customer-api.open-meteo.com/v1/forecast`, and point `OSRM_URL` at a self-hosted OSRM, ideally with a truck profile.
- Routes come from a car-profile router: they don't account for truck restrictions (height, weight, hazmat). ETAs approximate truck speeds through the speed cap.
- The HOS model ignores the 14-hour window, which can't bind under the 8 + 0.5 + 3 schedule, and the 60/70-hour weekly limit.
- Forecasts are limited to departures up to 10 days ahead, so the trip and the 48 h heatmap window stay inside Open-Meteo's 16-day horizon.
