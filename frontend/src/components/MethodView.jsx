import { fmtNum } from "../utils";
import { Card } from "./ui";

export default function MethodView({ meta }) {
  const c = meta.data_coverage || {};
  return (
    <div className="stack">
      <Card title="Method and assumptions">
        <ol className="method">
          <li>
            <strong>Data.</strong> Only Elexon BMRS: actual wind from <code>FUELHH</code> (fuelType WIND, 30-minute) and
            wind forecasts from <code>WINDFOR</code> (national, hourly, many publish times per target). Delivery days:
            1–31 January 2026.
          </li>
          <li>
            <strong>Decision rule.</strong> {meta.decision_cutoff_rule}
          </li>
          <li>
            <strong>Why a cutoff?</strong> Day-ahead bids are placed on D−1. Forecasts published after that moment were
            not available to the buyer, so using them would flatter the results (look-ahead leakage). The cutoff is
            adjustable in the header; January is GMT so UTC equals London time.
          </li>
          <li>
            <strong>Alignment.</strong> WINDFOR targets are hourly, FUELHH is half-hourly. Forecasts and actuals are
            matched on exact timestamps only, so accuracy is measured on the on-the-hour half-hours. Nothing is
            interpolated or forward-filled.
          </li>
          <li>
            <strong>Metrics.</strong> Error = forecast − actual. MAE, RMSE, bias, NMAE (= MAE ÷ mean actual), error
            percentiles, and a rolling 24-hour view. Horizon analysis scores every vintage by hours between publication
            and target.
          </li>
          <li>
            <strong>Planning buffer.</strong> The P95 of the signed error is the amount by which forecasts over-promised
            wind in 1 of 20 hours. Subtracting it gives a risk-adjusted wind figure. It is computed on the same January
            data (in-sample), so treat it as a guide, not a guarantee.
          </li>
        </ol>
      </Card>
      <Card title="Data coverage">
        <div className="table-wrap narrow">
          <table>
            <tbody>
              <tr><td>Half-hours in January 2026</td><td>{fmtNum(c.expected_half_hours)}</td></tr>
              <tr><td>Half-hours with actual wind data</td><td>{fmtNum(c.actuals_in_window)} ({c.actual_coverage_pct}%)</td></tr>
              <tr><td>Half-hours with a forecast target</td><td>{fmtNum(c.targets_with_any_forecast)} ({c.native_forecast_coverage_pct}%)</td></tr>
              <tr><td>Forecast vintages stored</td><td>{fmtNum(c.forecast_records)}</td></tr>
              <tr><td>Data source</td><td>{meta.source}</td></tr>
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
