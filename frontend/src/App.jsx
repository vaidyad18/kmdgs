import { useState } from "react";
import { buildUrl, useFetch } from "./api";
import AccuracyView from "./components/AccuracyView";
import DecisionView from "./components/DecisionView";
import MethodView from "./components/MethodView";
import VintagesView from "./components/VintagesView";
import { ErrorBox, Loading } from "./components/ui";

const TABS = [
  { id: "decision", label: "Decision view", number: "01" },
  { id: "accuracy", label: "Forecast accuracy", number: "02" },
  { id: "vintages", label: "Forecast evolution", number: "03" },
  { id: "method", label: "Method", number: "04" },
];

const TIME_RE = /^([01]\d|2[0-3]):[0-5]\d$/;

export default function App() {
  const [tab, setTab] = useState("decision");
  const [cutoffInput, setCutoffInput] = useState(null);
  const metaState = useFetch(buildUrl("/meta"));
  const meta = metaState.data;
  const cutoff = TIME_RE.test(cutoffInput ?? "") ? cutoffInput : meta?.defaults?.cutoff_time ?? "09:00";

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo" aria-hidden="true">
            <svg viewBox="0 0 48 48" fill="none">
              <circle cx="24" cy="24" r="21" />
              <path d="M24 24 13 12m11 12 15-3M24 24l-2 16" />
              <circle cx="24" cy="24" r="3" />
            </svg>
          </span>
          <div>
            <div className="brand-kicker">FIELDNOTES / ENERGY</div>
            <h1>Wind Forecast Desk</h1>
            <p>GB day-ahead purchasing · national wind · January 2026</p>
          </div>
        </div>
        <div className="header-tools">
          <span className="archive-status"><span /> JAN 2026 ARCHIVE</span>
          <label className="cutoff">
            <span className="cutoff-label">DAY-AHEAD CUTOFF <span>UTC · D−1</span></span>
            <input
              type="time"
              value={cutoffInput ?? cutoff}
              onChange={(e) => setCutoffInput(e.target.value)}
              aria-label="Day-ahead cutoff time"
            />
          </label>
        </div>
      </header>

      <div className="workspace-heading">
        <div>
          <p className="eyebrow">THE NATIONAL WIND PICTURE <span>·</span> GREAT BRITAIN</p>
          <h2>Read the wind before it moves.</h2>
        </div>
        <p className="workspace-note">Forecast intelligence for the day-ahead desk.<br />One month. Every forecast vintage.</p>
      </div>

      <nav className="tabs" role="tablist" aria-label="Forecast workspace">
        {TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} className={tab === t.id ? "active" : ""} onClick={() => setTab(t.id)}>
            <span className="tab-number">{t.number}</span>
            <span>{t.label}</span>
          </button>
        ))}
      </nav>

      <main>
        {metaState.error && <ErrorBox message={`Could not reach the API. ${metaState.error}`} />}
        {!meta && !metaState.error && <Loading label="Connecting to the forecast service…" />}
        {meta && tab === "decision" && <DecisionView meta={meta} cutoff={cutoff} />}
        {meta && tab === "accuracy" && <AccuracyView meta={meta} cutoff={cutoff} />}
        {meta && tab === "vintages" && <VintagesView meta={meta} cutoff={cutoff} />}
        {meta && tab === "method" && <MethodView meta={meta} />}
      </main>

      <footer>
        <span>DATA: ELEXON BMRS · FUELHH ACTUALS · WINDFOR FORECASTS</span>
        <span>JANUARY 2026 <i /> NOT INVESTMENT ADVICE</span>
      </footer>
    </div>
  );
}
