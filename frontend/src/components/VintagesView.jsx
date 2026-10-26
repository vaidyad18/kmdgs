import { useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { buildUrl, useFetch } from "../api";
import { COLORS, fmtDateTime, fmtNum } from "../utils";
import { Async, Card } from "./ui";

export default function VintagesView({ meta, cutoff }) {
  const dates = meta.available_delivery_dates;
  const [date, setDate] = useState(dates[Math.min(14, dates.length - 1)]);
  const [hour, setHour] = useState(12);
  const target = `${date}T${String(hour).padStart(2, "0")}:00:00Z`;

  const vint = useFetch(buildUrl("/forecasts/vintages", { target_time: target }));
  const day = useFetch(buildUrl("/forecasts/decision", { delivery_date: date, cutoff_time: cutoff }));

  const actual = day.data?.records?.find((r) => r.startTime === target)?.actual_mw ?? null;
  const used = day.data?.records?.find((r) => r.startTime === target) ?? null;
  const points = (vint.data?.records ?? []).map((r) => ({
    ts: Date.parse(r.publishTime),
    forecast: r.forecast_mw,
    horizon: r.horizon_hours,
  }));
  const gate = Date.parse(`${date}T00:00:00Z`) - 24 * 3600 * 1000 + hourMin(cutoff);

  return (
    <div className="stack">
      <Card
        title="How did the forecast for one hour change as delivery got closer?"
        subtitle="Each point is a forecast vintage published for the selected target hour."
        actions={
          <div className="row">
            <select value={date} onChange={(e) => setDate(e.target.value)} aria-label="Delivery date">
              {dates.map((d) => (
                <option key={d}>{d}</option>
              ))}
            </select>
            <select value={hour} onChange={(e) => setHour(Number(e.target.value))} aria-label="Hour">
              {Array.from({ length: 24 }, (_, h) => (
                <option key={h} value={h}>
                  {String(h).padStart(2, "0")}:00 UTC
                </option>
              ))}
            </select>
          </div>
        }
      >
        <Async state={vint}>
          <ResponsiveContainer width="100%" height={340}>
            <LineChart data={points} margin={{ top: 10, right: 20, left: 4, bottom: 0 }}>
              <CartesianGrid stroke={COLORS.grid} strokeDasharray="3 3" />
              <XAxis
                dataKey="ts"
                type="number"
                scale="time"
                domain={["dataMin", "dataMax"]}
                tick={{ fontSize: 12 }}
                tickFormatter={(v) => new Date(v).toISOString().slice(5, 13).replace("T", " ") + "h"}
              />
              <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => fmtNum(v)} width={64} domain={["auto", "auto"]} />
              <Tooltip
                formatter={(v) => [`${fmtNum(v)} MW`, "Forecast"]}
                labelFormatter={(l) => `Published ${fmtDateTime(new Date(l).toISOString())}`}
              />
              <ReferenceLine x={gate} stroke={COLORS.safe} strokeDasharray="5 4" label={{ value: "Day-ahead cutoff", fontSize: 12, fill: COLORS.safe, position: "insideTopRight" }} />
              {actual != null && (
                <ReferenceLine y={actual} stroke={COLORS.actual} label={{ value: `Actual ${fmtNum(actual)} MW`, fontSize: 12, position: "insideBottomRight" }} />
              )}
              <Line dataKey="forecast" stroke={COLORS.forecast} strokeWidth={2.5} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
          <p className="note">
            {vint.data?.n ?? 0} vintages exist for {target.slice(0, 16).replace("T", " ")} UTC.
            {used?.forecast_mw != null &&
              ` The decision-time forecast (published ${fmtDateTime(used.publishTime)}) was ${fmtNum(used.forecast_mw)} MW versus ${fmtNum(actual)} MW actual.`}{" "}
            Vintages published after the target hour are shown for completeness but are never used for decisions.
          </p>
        </Async>
      </Card>
    </div>
  );
}

function hourMin(hhmmStr) {
  const [h, m] = hhmmStr.split(":").map(Number);
  return (h * 60 + m) * 60 * 1000;
}
