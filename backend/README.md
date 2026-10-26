# GB day-ahead wind forecast backend

National-level GB wind **actuals** (Elexon BMRS `FUELHH`) and **forecast vintages** (`WINDFOR`) for electricity purchase decisions covering delivery in **January 2026**.

The React frontend lives in `../frontend`; this folder is the Python API (FastAPI) that serves JSON under `/api`.

## Decision-cutoff assumption

For delivery day **D**, the purchase decision is made on **D−1 at `cutoff_time` UTC**. The default is **09:00 UTC**. January is GMT, so 09:00 UTC is 09:00 Europe/London.

For each target half-hour `startTime` T on day D the API selects the WINDFOR vintage with the same T and the **latest `publishTime` ≤ cutoff(D−1)**. Forecasts published after the cutoff are never used (no look-ahead leakage).

WINDFOR is **hourly**. FUELHH is **half-hourly**. Joins are exact `startTime` matches only. Half-hours ending `:30` have no native forecast and are returned as null, not interpolated. See `docs/API_NOTES.md`.

Every JSON response includes `decision_cutoff_rule` restating this.

## Run locally

Python 3.11+ (3.12 also works). From `backend/`:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m pytest
uvicorn app.main:app --reload --port 8000
```

The process loads `data/snapshot/*.csv` (or `.parquet`) at startup and does **not** call Elexon unless you `POST /api/refresh`.

OpenAPI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Rebuild the snapshot from Elexon

```bash
python -m app.build_snapshot
```

## Docker

```bash
docker build -t wind-backend .
docker run --rm -p 8000:8000 -e PORT=8000 wind-backend
```

The image runs as a non-root user. `PORT` defaults to 8000 for Heroku-style platforms.

## Environment variables

| Variable | Default | Meaning |
| --- | --- | --- |
| `PORT` | `8000` | Listen port |
| `CORS_ORIGINS` | `*` | Comma-separated origins, or `*` |
| `REFRESH_TOKEN` | empty | If set, `POST /api/refresh` requires header `X-Refresh-Token` |
| `DEFAULT_CUTOFF_TIME` | `09:00` | UTC gate closure `HH:MM` |
| `ELEXON_BASE_URL` | `https://data.elexon.co.uk/bmrs/api/v1` | BMRS Insights API |
| `DATA_CACHE_DIR` | `./data_cache` | Mutable parquet/JSON cache |
| `SNAPSHOT_DIR` | `./data/snapshot` | Committed January 2026 snapshot |
| `LOG_LEVEL` | `INFO` | Logging level |
| `STATIC_DIR` | `./static` | Built React app, served at `/` when present |
| `DATA_START` / `DATA_END_EXCLUSIVE` | `2026-01-01` / `2026-02-01` | Delivery window |
| `FORECAST_PUBLISH_START` / `FORECAST_PUBLISH_END_EXCLUSIVE` | `2025-12-25` / `2026-02-01` | WINDFOR publish fetch window |

## Endpoints

All timestamps are ISO-8601 UTC with a `Z` suffix. Invalid input returns HTTP 4xx with `{"error":{"code","message","details"}}`.

| Method | Path | Example |
| --- | --- | --- |
| GET | `/api/health` | `curl http://127.0.0.1:8000/api/health` |
| GET | `/api/meta` | `curl http://127.0.0.1:8000/api/meta` |
| GET | `/api/actuals` | `curl "http://127.0.0.1:8000/api/actuals?start=2026-01-01&end=2026-01-02"` |
| GET | `/api/forecasts/decision` | `curl "http://127.0.0.1:8000/api/forecasts/decision?delivery_date=2026-01-15&cutoff_time=09:00"` |
| GET | `/api/forecasts/decision/range` | `curl "http://127.0.0.1:8000/api/forecasts/decision/range?start_date=2026-01-01&end_date=2026-01-31"` |
| GET | `/api/forecasts/vintages` | `curl "http://127.0.0.1:8000/api/forecasts/vintages?target_time=2026-01-01T00:00:00Z"` |
| GET | `/api/accuracy/summary` | `curl "http://127.0.0.1:8000/api/accuracy/summary"` |
| GET | `/api/accuracy/by-day` | `curl "http://127.0.0.1:8000/api/accuracy/by-day"` |
| GET | `/api/accuracy/by-hour` | `curl "http://127.0.0.1:8000/api/accuracy/by-hour"` |
| GET | `/api/accuracy/by-horizon` | `curl "http://127.0.0.1:8000/api/accuracy/by-horizon"` |
| GET | `/api/accuracy/by-wind-level` | `curl "http://127.0.0.1:8000/api/accuracy/by-wind-level"` |
| GET | `/api/accuracy/error-distribution` | `curl "http://127.0.0.1:8000/api/accuracy/error-distribution"` |
| POST | `/api/refresh` | `curl -X POST http://127.0.0.1:8000/api/refresh` |

Accuracy uses an inner join of decision-time forecasts and actuals on `startTime`. Horizon breakdowns use a separate mode: every vintage published at or before the target is scored and bucketed by horizon (hours between `publishTime` and `startTime`), not just the D−1 decision-time forecast.

MAPE is the mean of `|error|/actual` where actual ≠ 0. NMAE is `MAE / mean(actual)` so a purchase buffer can still be discussed when actuals hit zero.

## Tests

```bash
python -m pytest
RUN_LIVE_TESTS=1 python -m pytest -m live
```

## AI tools used

AI tools used: Claude (Anthropic) and Cursor/Codex for scaffolding, code generation and review; design decisions, selection logic and validation reviewed by the author. (Edit to match what you used.)
