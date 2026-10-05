// SPEC §T16.6 — the debtor says they paid; it counts at once and waits for a Verify.
import { useState } from 'react'

import { claimPayment } from './api'
import { toCents } from './entryBody'
import { largestCreditor } from './pendingText'

const money = (cents) => (cents / 100).toFixed(2)

export default function IPaid({ balances, members, me, onChanged }) {
  const owes = -(balances.find((row) => row.member_id === me)?.net ?? 0)
  const owed = balances.filter((row) => row.member_id !== me && row.net > 0)
  const nameOf = (id) => members.find((m) => m.member_id === id)?.name ?? id

  const [open, setOpen] = useState(false)
  const [to, setTo] = useState(() => largestCreditor(balances, me) ?? '')
  const [amount, setAmount] = useState(() => money(owes))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  if (owes <= 0 || owed.length === 0) return null

  if (!open) {
    return (
      <button type="button" className="secondary" onClick={() => setOpen(true)}>
        I paid
      </button>
    )
  }

  async function send() {
    setBusy(true)
    setError(null)
    try {
      await claimPayment(to, toCents(amount))
      setOpen(false)
      await onChanged()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card">
      <label htmlFor="paid-to">Who did you pay?</label>
      <select id="paid-to" value={to} onChange={(e) => setTo(e.target.value)}>
        {owed.map((row) => (
          <option key={row.member_id} value={row.member_id}>
            {nameOf(row.member_id)}
          </option>
        ))}
      </select>
      <label htmlFor="paid-amount">Amount</label>
      <input
        id="paid-amount"
        inputMode="decimal"
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
      />
      <button type="button" onClick={send} disabled={busy || !to}>
        {busy ? 'Sending...' : 'Send'}
      </button>
      <p className="muted small">
        Counts as paid now. {nameOf(to)} gets asked to verify it.
      </p>
      {error && <p className="error">{error}</p>}
    </section>
  )
}
