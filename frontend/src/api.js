import { useEffect, useState } from "react";

const BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

/** Build an /api URL, dropping empty params. */
export function buildUrl(path, params = {}) {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") q.set(key, value);
  });
  const qs = q.toString();
  return `${BASE}/api${path}${qs ? `?${qs}` : ""}`;
}

export async function getJson(url, signal) {
  const res = await fetch(url, { signal });
  let body = null;
  try {
    body = await res.json();
  } catch {
    /* non-JSON body */
  }
  if (!res.ok) {
    throw new Error(body?.error?.message || `Request failed (HTTP ${res.status})`);
  }
  return body;
}

/** Fetch JSON for `url` (pass null to skip). Keeps previous data while reloading. */
export function useFetch(url) {
  const [state, setState] = useState({ data: null, loading: Boolean(url), error: null });
  useEffect(() => {
    if (!url) {
      setState({ data: null, loading: false, error: null });
      return undefined;
    }
    const ctrl = new AbortController();
    setState((s) => ({ ...s, loading: true, error: null }));
    getJson(url, ctrl.signal)
      .then((data) => setState({ data, loading: false, error: null }))
      .catch((err) => {
        if (err.name !== "AbortError") setState({ data: null, loading: false, error: err.message });
      });
    return () => ctrl.abort();
  }, [url]);
  return state;
}
