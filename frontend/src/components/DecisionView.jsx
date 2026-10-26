import { useMemo, useState } from "react";
import {
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { buildUrl, useFetch } from "../api";
import { COLORS, downloadCsv, fmtDateTime, fmtDay, fmtMW, fmtNum, hhmm } from "../utils";
import { Async, Card, Empty, Kpi } from "./ui";

export default function DecisionView({ meta, cutoff }) {
  const dates = meta.available_delivery_dates;
  const [date, setDate] = useState(dates[Math.min(14, dates.length - 1)]);
  const [showSafe, setShowSafe] = useState(true);

  const day = useFetch(buildUrl("/forecasts/decision", { delivery_date: date, cutoff_time: cutoff }));
  const acc = useFetch(buildUrl("/accuracy/summary", { cutoff_time: cutoff }));
  const p95 = acc.data?.metrics?.error_quantiles?.p95 ?? null;

  const rows = useMemo(
    () =>
      (day.data?.records ?? []).map((r) => ({
        t: hhmm(r.startTime),
        startTime: r.startTime,
        forecast: r.forecast_mw,
        actual: r.actual_mw,
        error: r.error_mw,
        horizon: r.horizon_hours,
        published: r.publishTime,
        safe: r.forecast_mw != null && p95 != null ? Math.max(0, r.forecast_mw - p95) : null,
      })),
    [day.data, p95]
  );

  const withForecast = rows.filter((r) => r.forecast != null);
  const scored = rows.filter((r) => r.error != null);
  const mae = scored.length ? scored.reduce((s, r) => s + Math.abs(r.error), 0) / scored.length : null;
  const bias = scored.length ? scored.reduce((s, r) => s + r.error, 0) / scored.length : null;
  const mean = withForecast.length ? withForecast.reduce((s, r) => s + r.forecast, 0) / withForecast.length : null;
  const peak = withForecast.length ? Math.max(...withForecast.map((r) => r.forecast)) : null;
  const low = withForecast.length ? Math.min(...withForecast.map((r) => r.forecast)) : null;
  const summary = day.data?.summary;
  const published =
    summary?.forecast_publish_time_min === summary?.forecast_publish_time_max
      ? fmtDateTime(summary?.forecast_publish_time_min)
      : `${fmtDateTime(summary?.forecast_publish_time_min)} → ${fmtDateTime(summary?.forecast_publish_time_max)}`;

  const idx = dates.indexOf(date);
  const step = (d) => dates[Math.min(dates.length - 1, Math.max(0, idx + d))];

  return (
    <div className="stack">
      <Card
        title="Which wind forecast was available when the day-ahead decision had to be made?"
        subtitle={`For delivery on ${fmtDay(date)}, using the latest forecast published at or before ${cutoff} UTC on the previous day.`}
        actions={
          <div className="row">
            <button className="btn" onClick={() => setDate(step(-1))} disabled={idx <= 0} aria-label="Previous day">
              ←
            </button>
            <select value={date} onChange={(e) => setDate(e.target.value)} aria-label="Delivery date">
              {dates.map((d) => (
                <option key={d} value={d}>
                  {fmtDay(d)}
                </option>
              ))}
            </select>
            <button
              className="btn"
              onClick={() => setDate(step(1))}
              disabled={idx >= dates.length - 1}
              aria-label="Next day"
            >
              →
            </button>
          </div>
        }
      >
        <Async state={day}>
          <div className="kpi-grid">
            <Kpi label="Forecast used (published)" value={published} hint="Latest vintage before the cutoff" />
            <Kpi label="Mean forecast wind" value={fmtMW(mean)} hint={`Low ${fmtNum(low)} · Peak ${fmtNum(peak)} MW`} />
            <Kpi
              label="Forecast error that day"
              value={fmtMW(mae)}
              hint={bias == null ? "" : `MAE · bias ${bias > 0 ? "+" : ""}${fmtNum(bias)} MW (forecast − actual)`}
              tone={bias > 0 ? "warn" : ""}
            />
            <Kpi
              label="Planning buffer (P95 over-forecast)"
              value={fmtMW(p95)}
              hint="Wind that failed to show up in 1 of 20 hours (January sample)"
            />
          </div>

          <div className="chart-box">
            <ResponsiveContainer width="100%" height={340}>
              <ComposedChart data={rows} margin={{ top: 10, right: 16, left: 4, bottom: 0 }}>
                <CartesianGrid stroke={COLORS.grid} strokeDasharray="3 3" />
                <XAxis dataKey="t" interval={3} tick={{ fontSize: 12 }} />
                <YAxis tickFormatter={(v) => fmtNum(v)} tick={{ fontSize: 12 }} width={64} unit="" />
                <Tooltip formatter={(v, name) => [v == null ? "–" : `${fmtNum(v)} MW`, name]} labelFormatter={(l) => `${l} UTC`} />
                <Legend />
                <Line name="Forecast (decision time)" dataKey="forecast" stroke={COLORS.forecast} strokeWidth={2.5} dot={{ r: 2 }} connectNulls />
                <Line name="Actual (FUELHH)" dataKey="actual" stroke={COLORS.actual} strokeWidth={2} dot={false} />
                {showSafe && (
                  <Line
                    name="Forecast − P95 buffer"
                    dataKey="safe"
                    stroke={COLORS.safe}
                    strokeDasharray="6 4"
                    strokeWidth={2}
                    dot={false}
                    connectNulls
                  />
                )}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <label className="check">
            <input type="checkbox" checked={showSafe} onChange={(e) => setShowSafe(e.target.checked)} /> Show risk-adjusted wind
            (forecast minus the P95 historical over-forecast)
          </label>
          <p className="note">
            WINDFOR forecasts are hourly while actuals are half-hourly, so forecast points exist only on the hour
            ({summary?.slots_with_forecast ?? 0} of {summary?.slots ?? 0} half-hours). Nothing is interpolated.
          </p>
        </Async>
      </Card>

      <Card
        title="Hourly decision table"
        subtitle="Everything the trader needs for each delivery hour"
        actions={
          <button
            className="btn"
            onClick={() =>
              downloadCsv(
                `decision_${date}_cutoff_${cutoff.replace(":", "")}.csv`,
                withForecast.map((r) => ({
                  startTime: r.startTime,
                  forecast_mw: r.forecast,
                  risk_adjusted_mw: r.safe,
                  actual_mw: r.actual,
                  error_mw: r.error,
                  published: r.published,
                  horizon_hours: r.horizon,
                }))
              )
            }
            disabled={!withForecast.length}
          >
            Export CSV
          </button>
        }
      >
        {withForecast.length === 0 ? (
          <Empty>No forecast was available before the cutoff for this day.</Empty>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Hour (UTC)</th>
                  <th>Forecast MW</th>
                  <th>Risk-adjusted MW</th>
                  <th>Actual MW</th>
                  <th>Error MW</th>
                  <th>Published</th>
                  <th>Horizon (h)</th>
                </tr>
              </thead>
              <tbody>
                {withForecast.map((r) => (
                  <tr key={r.startTime}>
                    <td>{r.t}</td>
                    <td>{fmtNum(r.forecast)}</td>
                    <td>{fmtNum(r.safe)}</td>
                    <td>{fmtNum(r.actual)}</td>
                    <td className={r.error > 0 ? "neg" : "pos"}>
                      {r.error == null ? "–" : `${r.error > 0 ? "+" : ""}${fmtNum(r.error)}`}
                    </td>
                    <td>{fmtDateTime(r.published)}</td>
                    <td>{fmtNum(r.horizon, 1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="note">
          Error = forecast − actual. Positive (red) means the forecast promised more wind than arrived, so extra power
          would have had to be bought later.
        </p>
      </Card>
    </div>
  );
}
