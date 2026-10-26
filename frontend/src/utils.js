export const COLORS = {
  forecast: "#24725c",
  actual: "#263b32",
  safe: "#b66831",
  mae: "#24725c",
  bias: "#bf5a48",
  good: "#5e9567",
  grid: "#e2e5dc",
};

export const fmtNum = (v, digits = 0) =>
  v === null || v === undefined || Number.isNaN(v)
    ? "–"
    : Number(v).toLocaleString("en-GB", { minimumFractionDigits: digits, maximumFractionDigits: digits });

export const fmtMW = (v, digits = 0) => (v === null || v === undefined ? "–" : `${fmtNum(v, digits)} MW`);

export const fmtPct = (v, digits = 1) => (v === null || v === undefined ? "–" : `${(v * 100).toFixed(digits)}%`);

/** "2026-01-15T07:30:00Z" -> "07:30" */
export const hhmm = (iso) => (iso ? iso.slice(11, 16) : "");

export const fmtDateTime = (iso) => {
  if (!iso) return "–";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${d.toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  })} UTC`;
};

export const fmtDay = (isoDate) => {
  const d = new Date(`${isoDate}T00:00:00Z`);
  return d.toLocaleDateString("en-GB", { weekday: "short", day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" });
};

export function downloadCsv(filename, rows) {
  if (!rows.length) return;
  const cols = Object.keys(rows[0]);
  const body = rows.map((r) => cols.map((c) => (r[c] ?? "")).join(",")).join("\n");
  const blob = new Blob([`${cols.join(",")}\n${body}`], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
