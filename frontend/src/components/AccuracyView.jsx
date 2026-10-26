import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { buildUrl, useFetch } from "../api";
import { COLORS, fmtMW, fmtNum, fmtPct } from "../utils";
import { Async, Card, Empty, Kpi } from "./ui";

const axis = { fontSize: 12 };
const mwFmt = (v) => fmtNum(v);

function MaeBiasBars({ data, xKey, height = 280, xFormatter }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 10, right: 12, left: 4, bottom: 0 }}>
        <CartesianGrid stroke={COLORS.grid} strokeDasharray="3 3" />
        <XAxis dataKey={xKey} tick={axis} tickFormatter={xFormatter} />
        <YAxis tick={axis} tickFormatter={mwFmt} width={64} />
        <Tooltip formatter={(v, n) => [`${fmtNum(v)} MW`, n]} />
        <Legend />
        <ReferenceLine y={0} stroke="#64748b" />
        <Bar name="MAE" dataKey="mae" fill={COLORS.mae} radius={[3, 3, 0, 0]} />
        <Bar name="Bias (forecast − actual)" dataKey="bias" fill={COLORS.bias} radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export default function AccuracyView({ meta, cutoff }) {
  const dates = meta.available_delivery_dates;
  const [start, setStart] = useState(dates[0]);
  const [end, setEnd] = useState(dates[dates.length - 1]);
  const valid = start <= end;
  const params = valid ? { start_date: start, end_date: end, cutoff_time: cutoff } : null;
  const url = (p) => (params ? buildUrl(p, params) : null);

  const summary = useFetch(url("/accuracy/summary"));
  const byDay = useFetch(url("/accuracy/by-day"));
  const byHour = useFetch(url("/accuracy/by-hour"));
  const byHorizon = useFetch(url("/accuracy/by-horizon"));
  const byWind = useFetch(url("/accuracy/by-wind-level"));
  const dist = useFetch(url("/accuracy/error-distribution"));

  const m = summary.data?.metrics;
  const q = m?.error_quantiles;

  return (
    <div className="stack">
      <Card
        title="How accurate are the wind forecasts?"
        subtitle="Decision-time forecasts compared with actual national wind generation. Error = forecast − actual."
        actions={
          <div className="row">
            <label>
              From
              <select value={start} onChange={(e) => setStart(e.target.value)}>
                {dates.map((d) => (
                  <option key={d}>{d}</option>
                ))}
              </select>
            </label>
            <label>
              To
              <select value={end} onChange={(e) => setEnd(e.target.value)}>
                {dates.map((d) => (
                  <option key={d}>{d}</option>
                ))}
              </select>
            </label>
          </div>
        }
      >
        {!valid ? (
          <Empty>“From” must be on or before “To”.</Empty>
        ) : (
          <Async state={summary}>
            <div className="kpi-grid">
              <Kpi label="Mean absolute error" value={fmtMW(m?.mae)} hint={`${fmtPct(m?.nmae)} of mean wind (NMAE)`} />
              <Kpi label="RMSE" value={fmtMW(m?.rmse)} hint="Penalises large misses" />
              <Kpi
                label="Bias"
                value={`${m?.bias > 0 ? "+" : ""}${fmtMW(m?.bias)}`}
                hint={m?.bias > 0 ? "Forecasts over-promise wind" : "Forecasts under-promise wind"}
                tone={m?.bias > 0 ? "warn" : "good"}
              />
              <Kpi label="95th pct. abs. error" value={fmtMW(m?.p95_abs_error)} hint={`P99 ${fmtMW(m?.p99_abs_error)}`} />
              <Kpi label="Correlation" value={m?.correlation == null ? "–" : m.correlation.toFixed(3)} hint={`R² ${m?.r2 == null ? "–" : m.r2.toFixed(2)}`} />
              <Kpi label="Forecast/actual pairs" value={fmtNum(m?.n)} hint={`${fmtNum(summary.data?.join_counts?.actuals_missing_forecast)} half-hours have no forecast`} />
            </div>

            <h4 className="sub">What should a buyer plan for?</h4>
            <div className="table-wrap narrow">
              <table>
                <thead>
                  <tr>
                    <th>Percentile of error</th>
                    <th>P5</th>
                    <th>P25</th>
                    <th>Median</th>
                    <th>P75</th>
                    <th>P95</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Forecast − actual (MW)</td>
                    <td>{fmtNum(q?.p5)}</td>
                    <td>{fmtNum(q?.p25)}</td>
                    <td>{fmtNum(q?.p50)}</td>
                    <td>{fmtNum(q?.p75)}</td>
                    <td>
                      <strong>{fmtNum(q?.p95)}</strong>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <h4 className="sub">Key findings</h4>
            <ul className="insights">
              {(summary.data?.insights ?? []).map((t) => (
                <li key={t}>{t}</li>
              ))}
            </ul>
          </Async>
        )}
      </Card>

      {valid && (
        <>
          <Card title="Error trend" subtitle="Rolling 24-hour MAE and bias across the period">
            <Async state={summary}>
              <ResponsiveContainer width="100%" height={280}>
                <ComposedChart data={summary.data?.rolling_24h ?? []} margin={{ top: 10, right: 12, left: 4, bottom: 0 }}>
                  <CartesianGrid stroke={COLORS.grid} strokeDasharray="3 3" />
                  <XAxis
                    dataKey="startTime"
                    tick={axis}
                    minTickGap={48}
                    tickFormatter={(v) => `${v.slice(8, 10)}/${v.slice(5, 7)}`}
                  />
                  <YAxis tick={axis} tickFormatter={mwFmt} width={64} />
                  <Tooltip formatter={(v, n) => [`${fmtNum(v)} MW`, n]} labelFormatter={(l) => `${l.slice(0, 16).replace("T", " ")} UTC`} />
                  <Legend />
                  <ReferenceLine y={0} stroke="#64748b" />
                  <Line name="Rolling MAE" dataKey="mae" stroke={COLORS.mae} dot={false} strokeWidth={2} />
                  <Line name="Rolling bias" dataKey="bias" stroke={COLORS.bias} dot={false} strokeWidth={2} />
                </ComposedChart>
              </ResponsiveContainer>
            </Async>
          </Card>

          <div className="grid-2">
            <Card title="Error by delivery day">
              <Async state={byDay}>
                <MaeBiasBars data={byDay.data?.records ?? []} xKey="delivery_date" xFormatter={(v) => v.slice(8)} />
              </Async>
            </Card>
            <Card title="Error by hour of day (UTC)">
              <Async state={byHour}>
                <MaeBiasBars data={byHour.data?.by_hour ?? []} xKey="hour" />
              </Async>
            </Card>
          </div>

          <div className="grid-2">
            <Card
              title="Error by forecast horizon"
              subtitle="Every forecast vintage, grouped by hours between publication and target"
            >
              <Async state={byHorizon}>
                <MaeBiasBars
                  data={(byHorizon.data?.records ?? []).filter((r) => r.n > 0)}
                  xKey="horizon_bucket"
                  xFormatter={(v) => `${v}h`}
                />
              </Async>
            </Card>
            <Card title="Distribution of forecast error" subtitle="Count of hours by signed error (forecast − actual)">
              <Async state={dist}>
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart
                    data={(dist.data?.distribution?.bins ?? []).map((b) => ({
                      mid: Math.round((b.bin_start_mw + b.bin_end_mw) / 2),
                      count: b.count,
                    }))}
                    margin={{ top: 10, right: 12, left: 4, bottom: 0 }}
                  >
                    <CartesianGrid stroke={COLORS.grid} strokeDasharray="3 3" />
                    <XAxis dataKey="mid" tick={axis} tickFormatter={mwFmt} interval={2} />
                    <YAxis tick={axis} width={44} />
                    <Tooltip formatter={(v) => [fmtNum(v), "Hours"]} labelFormatter={(l) => `≈ ${fmtNum(l)} MW`} />
                    <Bar dataKey="count" name="Hours">
                      {(dist.data?.distribution?.bins ?? []).map((b) => (
                        <Cell key={b.bin_start_mw} fill={b.bin_start_mw + b.bin_end_mw > 0 ? COLORS.bias : COLORS.good} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </Async>
            </Card>
          </div>

          <Card title="Accuracy by wind level" subtitle={byWind.data?.bucket_rule}>
            <Async state={byWind}>
              <div className="table-wrap narrow">
                <table>
                  <thead>
                    <tr>
                      <th>Wind level</th>
                      <th>Actual range (MW)</th>
                      <th>Hours</th>
                      <th>MAE (MW)</th>
                      <th>Bias (MW)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(byWind.data?.records ?? []).map((r) => (
                      <tr key={r.wind_level}>
                        <td style={{ textTransform: "capitalize" }}>{r.wind_level}</td>
                        <td>
                          {fmtNum(r.actual_mw_min)} – {fmtNum(r.actual_mw_max)}
                        </td>
                        <td>{fmtNum(r.n)}</td>
                        <td>{fmtNum(r.mae)}</td>
                        <td>{fmtNum(r.bias)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Async>
          </Card>
        </>
      )}
    </div>
  );
}
