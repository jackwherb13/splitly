// SPEC §T16.7 — "I paid them", opened under that person's row. The recipient
// is the row, so there is nothing to pick.
import { useState } from 'react'

import { claimPayment } from './api'
import { toCents } from './entryBody'

const money = (cents) => (cents / 100).toFixed(2)

export default function PayPanel({ to, name, owe, onChanged, onClose }) {
  // §V40 — one id per opening, so a double tap records one payment.
  const [claimId] = useState(() => crypto.randomUUID())
  const [amount, setAmount] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function send(cents) {
    setBusy(true)
    setError(null)
    try {
      await claimPayment(to, cents, claimId)
      onClose()
      await onChanged()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card pay">
      <button type="button" onClick={() => send(owe)} disabled={busy}>
        Paid in full · ${money(owe)}
      </button>
      <label htmlFor={`pay-${to}`}>Or a different amount</label>
      <input
        id={`pay-${to}`}
        inputMode="decimal"
        placeholder={money(owe)}
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
      />
      <p className="row">
        <button
          type="button"
          className="secondary"
          onClick={() => send(toCents(amount))}
          disabled={busy || !amount.trim()}
        >
          Send
        </button>
        <button type="button" className="mode" onClick={onClose} disabled={busy}>
          Cancel
        </button>
      </p>
      <p className="muted small">Counts as paid now. {name} gets asked to verify it.</p>
      {error && <p className="error">{error}</p>}
    </div>
  )
}
