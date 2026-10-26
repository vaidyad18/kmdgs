export function Card({ title, subtitle, actions, children, className = "" }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="card-head">
          <div>
            {title && <h3>{title}</h3>}
            {subtitle && <p className="muted">{subtitle}</p>}
          </div>
          {actions && <div className="card-actions">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

export function Kpi({ label, value, hint, tone }) {
  return (
    <div className={`kpi ${tone || ""}`}>
      <span className="kpi-label">{label}</span>
      <strong className="kpi-value">{value}</strong>
      {hint && <span className="kpi-hint">{hint}</span>}
    </div>
  );
}

export function Loading({ label = "Loading…" }) {
  return (
    <div className="loading" role="status">
      <span className="spinner" /> {label}
    </div>
  );
}

export function ErrorBox({ message }) {
  return (
    <div className="error-box" role="alert">
      <strong>Something went wrong.</strong> {message}
    </div>
  );
}

/** Renders loading / error states, otherwise children. */
export function Async({ state, children }) {
  if (state.error) return <ErrorBox message={state.error} />;
  if (!state.data) return <Loading />;
  return <div className={state.loading ? "stale" : ""}>{children}</div>;
}

export function Empty({ children }) {
  return <p className="empty">{children}</p>;
}
