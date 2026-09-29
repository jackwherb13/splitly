import { historyRows } from './historyRows'

export default function History({ entries, members }) {
  const rows = historyRows(entries, members)
  return (
    <section>
      <h2 className="eyebrow">History</h2>
      {rows.length === 0 && <p className="muted">Nothing yet.</p>}
      <ul className="entries">
        {rows.map((row) => (
          <li key={row.id}>
            <div className="row">
              <span>{row.description}</span>
              <strong>{row.total}</strong>
            </div>
            <div className="muted small">
              {row.date} · {row.paidBy} · {row.split}
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
