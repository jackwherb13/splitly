import { useState } from 'react'

import { describeBalance } from './balanceText'

const money = (cents) => (cents / 100).toFixed(2)

// What one entry did to one person's balance: credited if they paid for it,
// debited by whatever they owe. These add up to the figure above them, which
// is §C7's "drills down to the entries that produced it" made visible rather
// than merely true.
const contribution = (entry, memberId) =>
  (entry.payer === memberId ? entry.total : 0) - (entry.shares[memberId] ?? 0)

export default function Balances({ balances, entries, members }) {
  const [openFor, setOpenFor] = useState(null)

  const nameOf = (id) => members.find((member) => member.member_id === id)?.name ?? id
  const byId = Object.fromEntries(entries.map((entry) => [entry.entry_id, entry]))

  if (balances.length === 0) return <p className="muted">Nothing owed yet.</p>

  return (
    <ul className="balances">
      {balances.map((row) => {
        const { label, amount, settled } = describeBalance(row.net)
        const open = openFor === row.member_id

        return (
          <li key={row.member_id}>
            <button
              type="button"
              className="balance"
              aria-expanded={open}
              onClick={() => setOpenFor(open ? null : row.member_id)}
            >
              <span>{nameOf(row.member_id)}</span>
              <span className={settled ? 'muted' : 'owed'}>
                {settled ? 'settled' : `${label} ${amount}`}
              </span>
            </button>

            {open && (
              <ul className="drill">
                {row.entry_ids.map((entryId) => {
                  const entry = byId[entryId]
                  if (!entry) return null
                  const part = contribution(entry, row.member_id)
                  return (
                    <li key={entryId} className="row small">
                      <span>{entry.description}</span>
                      <span>
                        {part >= 0 ? '+' : '−'} {money(Math.abs(part))}
                      </span>
                    </li>
                  )
                })}
              </ul>
            )}
          </li>
        )
      })}
    </ul>
  )
}
