// SPEC §T16.5 — one Settings section: a row that opens in place.
// Native <details>, so the browser does the toggling and the accessibility.
export default function Fold({ title, value, open = false, children }) {
  return (
    <details className="fold" open={open}>
      <summary>
        <span>{title}</span>
        {value && <span className="muted">{value}</span>}
      </summary>
      {children}
    </details>
  )
}
