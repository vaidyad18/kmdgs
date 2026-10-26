# Wind Forecast Desk — GB day-ahead wind forecasts vs actuals

A full-stack web app for a UK energy utility's day-ahead power desk. It answers two questions using Elexon BMRS data only (national wind, January 2026):

1. **Which wind forecast was the latest one available when the day-ahead purchase decision had to be made?**
2. **How accurate are those forecasts?** (quantified error, so buying decisions can include a buffer)

- **Live app:** `https://kmdgs.vercel.app/`
- **Demo video:** `<PASTE UNLISTED YOUTUBE URL HERE>`
- **Frontend:** React (Vite) + Recharts · **Backend:** Python (FastAPI, pandas) · **Packaging:** Docker

## What the app shows

| Tab | Purpose |
| --- | --- |
| Decision view | For a chosen delivery day: the forecast vintage that was available at the D−1 cutoff, vs actual wind; a risk-adjusted line (forecast − P95 historical over-forecast); hourly table with CSV export |
| Forecast accuracy | MAE, RMSE, bias, NMAE, error percentiles, rolling 24 h trend, error by day / hour of day / forecast horizon / wind level, error histogram, auto-generated findings |
| Forecast evolution | How the forecast for one target hour changed across all vintages, with the cutoff and the actual marked |
| Method | Rules, assumptions and data coverage |

The day-ahead cutoff (default 09:00 UTC on D−1) is adjustable in the header and drives every view.

## Quick start

### Option A — Docker (recommended; one container serves API + UI)

```bash
docker compose up --build
# or
docker build -t wind-desk . && docker run --rm -p 8000:8000 wind-desk
```

Open http://localhost:8000 (UI) and http://localhost:8000/docs (API docs).
The image ships with a committed January 2026 snapshot, so it works with no internet access.

### Option B — local development (two terminals)

```bash
# Terminal 1: backend
cd backend
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m pytest                  # 20 tests
uvicorn app.main:app --reload --port 8000

# Terminal 2: frontend
cd frontend
npm install
npm run dev                       # http://localhost:5173 (proxies /api to :8000)
```

Python 3.11 or 3.12 and Node 18+ are recommended.

## Deployment

### Vercel

The frontend and backend can be deployed as separate Vercel projects. The frontend production build uses `VITE_API_BASE_URL` from [`frontend/.env.production`](./frontend/.env.production) to call the backend; change it to your backend's public base URL if your deployment changes. Alternatively, set `VITE_API_BASE_URL` in the frontend Vercel project's Environment Variables (that setting takes precedence over the file) and redeploy the frontend. If deploying both as Vercel Services under one domain with the root [`vercel.json`](./vercel.json), leave the variable unset so requests use the same-origin `/api` rewrite instead.

## Repository layout

```
.
├── Dockerfile            # multi-stage: build React, then Python image serving both
├── heroku.yml            # Heroku container deploy
├── docker-compose.yml
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app, error handlers, static serving
│   │   ├── config.py             # env settings + the decision-cutoff rule text
│   │   ├── elexon_client.py      # HTTP client: chunking, retries, back-off
│   │   ├── data_store.py         # normalise/validate, disk cache, snapshot fallback, refresh
│   │   ├── forecast_selection.py # latest-forecast-before-cutoff logic (pure, vectorised)
│   │   ├── metrics.py            # accuracy metrics, breakdowns, insights
│   │   ├── routers/              # health/meta, data, accuracy, refresh endpoints
│   │   ├── models.py, deps.py, jsonutil.py, build_snapshot.py
│   ├── data/snapshot/    # committed Jan 2026 data (actuals.csv, forecasts.csv)
│   ├── tests/            # pytest: selection logic, metrics, API (Elexon mocked)
│   └── README.md         # backend details and env vars
└── frontend/
    ├── src/
    │   ├── App.jsx, api.js, utils.js, styles.css
    │   └── components/   # DecisionView, AccuracyView, VintagesView, MethodView, ui
    └── package.json, vite.config.js, vercel.json

```

## Key design decisions

1. **No look-ahead.** For delivery day D, only vintages with `publishTime <= D−1 at cutoff` are eligible; the latest of those is used (`forecast_selection.py`, unit-tested including day boundaries).
2. **Honest alignment.** WINDFOR is hourly and FUELHH half-hourly. Matching is by exact timestamp; no interpolation. Coverage (50%) is shown in the UI and API.
3. **Horizon analysis scores every vintage**, not only the latest, so error can be compared across 0-6 h … 48 h+ lead times.
4. **Resilient data layer.** Retries with back-off, row validation, disk cache, and a committed snapshot so the deployed app never depends on Elexon being reachable. `POST /api/refresh` re-fetches live data.
5. **One container.** FastAPI serves the built React app, which keeps deployment simple and avoids CORS in production.

## API summary

`GET /api/health`, `/api/meta`, `/api/actuals`, `/api/forecasts/decision`, `/api/forecasts/decision/range`, `/api/forecasts/vintages`, `/api/accuracy/{summary,by-day,by-hour,by-horizon,by-wind-level,error-distribution}`, `POST /api/refresh`. Full list, parameters and examples: `backend/README.md` and `/docs`.

## Testing

```bash
cd backend && python -m pytest        # 20 passed, 1 live test skipped by default
RUN_LIVE_TESTS=1 python -m pytest -m live   # optional: hits the real Elexon API
```

## Limitations

- Accuracy and the P95 buffer are computed on the same January 2026 sample (in-sample).
- The 09:00 UTC cutoff is an assumption; set it to the gate closure of the auction you trade in.
- Only national wind is covered, as specified (no demand, solar, prices or other sources).
