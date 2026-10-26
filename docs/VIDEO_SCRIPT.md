# Demo video outline (max 10 minutes, unlisted on YouTube)

Record with the deployed app. Practise once; keep each part under 5 minutes.

## Part 1 — Customer pitch (≈ 4:30)

1. **(0:00) The problem.** "Every morning you must commit to day-ahead purchases before you know how much wind will actually blow. Wrong wind forecast = expensive balancing later."
2. **(0:30) Decision view.** Pick a delivery day. Point out: forecast available at the cutoff, publish time, actual wind, the dashed risk-adjusted line. "Here is exactly what you knew at 09:00 on D−1."
3. **(1:30) Change the cutoff** in the header and show the vintage/numbers change. Export the hourly table to CSV.
4. **(2:00) Accuracy tab.** Headline KPIs: MAE ≈ 2.1 GW (≈ 18% of mean wind), bias ≈ +1.85 GW, correlation 0.93. Say: "Forecasts systematically promise more wind than arrives."
5. **(3:00) What to do with it.** Percentile table: "In 1 of 20 hours wind was ≥ 5.4 GW below forecast; plan a buffer of that size." Error by hour / day / wind level: where it is riskiest.
6. **(3:45) Horizon chart.** Error grows with lead time (≈ 1.8 GW at 0-6 h to ≈ 2.4 GW at 36 h+), so re-check late forecasts. Forecast evolution tab: one hour's forecast changing.
7. **(4:15) Close.** Honest caveats (hourly forecasts, in-sample buffer) and next steps (add demand and price data).

## Part 2 — Technical review (≈ 4:30)

1. **(0:00) Architecture.** Diagram: Elexon → client (retries, chunking) → data store (validation, cache, snapshot) → selection + metrics → FastAPI → React. One Docker image serves both.
2. **(0:45) The core rule.** Open `forecast_selection.py`: mask `publishTime <= cutoff(D−1)`, sort, keep last. Show the tests for boundaries (Jan 1 uses vintages from 31 Dec).
3. **(1:45) Data findings.** `docs/API_NOTES.md`: hourly vs half-hourly, 24 vintages per target, 66.5 h max horizon, exact-match policy and coverage reporting.
4. **(2:30) Metrics.** `metrics.py`: definitions; horizon analysis scores all vintages (explain why "latest only" would put everything in one bucket).
5. **(3:15) API and frontend.** `/docs`, error format, `useFetch` hook, one chart component walkthrough.
6. **(3:50) Practices.** pytest (Elexon mocked), ruff, snapshot fallback, env-based config, Dockerfile, Heroku deploy, AI tool disclosure.
7. **(4:20) Trade-offs / next steps.** In-sample buffer, cutoff assumption, cache invalidation, adding CI.
