import { useEffect, useState } from 'react'

import { addMember, createWriteOff, listDeliveries, setMemberActive } from './api'
import { deliveryText } from './deliveryText'
import { toCents } from './entryBody'

const money = (cents) => (cents / 100).toFixed(2)

// Admin-only, and this component is not the guard — the router is (§V10).
// Hiding the controls only avoids offering buttons the API would refuse.
export default function Admin({ members, balances, onChanged }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const owing = balances.filter((row) => row.net < 0)
  const [forgiven, setForgiven] = useState(owing[0]?.member_id ?? '')
  const [absorber, setAbsorber] = useState('')
  const [amount, setAmount] = useState('')
  const [newName, setNewName] = useState('')
  const [newEmail, setNewEmail] = useState('')
  const [deliveries, setDeliveries] = useState(null)

  // §C19 — measured delivery. A failure to load it is not worth an error.
  useEffect(() => {
    listDeliveries().then(setDeliveries, () => {})
  }, [])

  const nameOf = (id) => members.find((m) => m.member_id === id)?.name ?? id
  const owedBy = (id) => Math.abs(balances.find((row) => row.member_id === id)?.net ?? 0)

  async function run(action) {
    setBusy(true)
    setError(null)
    try {
      await action()
      await onChanged()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  function writeOff() {
    const total = amount.trim() === '' ? owedBy(forgiven) : toCents(amount)
    return run(() =>
      createWriteOff({
        description: `Write-off for ${nameOf(forgiven)}`,
        forgiven,
        total,
        // §C50 — manual allocation. An even split would make someone who
        // fronted nothing reimburse the person who fronted everything.
        amounts: { [absorber]: total },
      }),
    )
  }

  function add() {
    return run(async () => {
      await addMember(newName, newEmail)
      setNewName('')
      setNewEmail('')
    })
  }

  return (
    <section className="card">
      <h2>Admin</h2>

      <h3>Members</h3>
      <ul className="entries">
        {members.map((member) => (
          <li key={member.member_id} className="row">
            <span className={member.active ? undefined : 'muted'}>
              {member.name}
              {member.active ? '' : ' (left)'}
            </span>
            <button
              type="button"
              className="mode"
              disabled={busy}
              onClick={() => run(() => setMemberActive(member.member_id, !member.active))}
            >
              {member.active ? 'Mark as left' : 'Bring back'}
            </button>
          </li>
        ))}
      </ul>
      <p className="muted small">
        Someone who has left keeps their entries and their balance. They are only
        taken out of new splits.
      </p>

      <h3>Add a member</h3>
      <label htmlFor="new-name">Name</label>
      <input id="new-name" value={newName} onChange={(e) => setNewName(e.target.value)} />
      <label htmlFor="new-email">Email</label>
      <input
        id="new-email"
        type="email"
        autoCapitalize="none"
        value={newEmail}
        onChange={(e) => setNewEmail(e.target.value)}
      />
      <button type="button" onClick={add} disabled={busy || !newName.trim() || !newEmail.trim()}>
        {busy ? 'Saving...' : 'Add member'}
      </button>
      <p className="muted small">
        No email is sent. Tell them to open the app and sign in with this address.
      </p>

      <h3>Write off a debt</h3>
      {owing.length === 0 ? (
        <p className="muted">Nobody is in debt.</p>
      ) : (
        <>
          <label htmlFor="forgiven">Forgive</label>
          <select
            id="forgiven"
            value={forgiven}
            onChange={(e) => setForgiven(e.target.value)}
          >
            {owing.map((row) => (
              <option key={row.member_id} value={row.member_id}>
                {nameOf(row.member_id)} — owes {money(Math.abs(row.net))}
              </option>
            ))}
          </select>

          <label htmlFor="amount">Amount (blank writes off the lot)</label>
          <input
            id="amount"
            inputMode="decimal"
            placeholder={money(owedBy(forgiven))}
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
          />

          <label htmlFor="absorber">Who absorbs it?</label>
          <select id="absorber" value={absorber} onChange={(e) => setAbsorber(e.target.value)}>
            <option value="">Choose someone</option>
            {members
              .filter((member) => member.member_id !== forgiven)
              .map((member) => (
                <option key={member.member_id} value={member.member_id}>
                  {member.name}
                </option>
              ))}
          </select>

          <button type="button" onClick={writeOff} disabled={busy || !absorber || !forgiven}>
            {busy ? 'Saving...' : 'Write it off'}
          </button>
          <p className="muted small">
            This posts an entry, it does not delete anything. The original expense
            stays on the ledger and the drilldown will show the debt as forgiven
            rather than paid.
          </p>
        </>
      )}

      <h3>Notification delivery — last 7 days</h3>
      {deliveries ? (
        <ul className="entries">
          <li className="row">
            <span>Everyone</span>
            <span>{deliveryText(deliveries.overall)}</span>
          </li>
          {Object.entries(deliveries.members).map(([memberId, tally]) => (
            <li key={memberId} className="row small">
              <span>{nameOf(memberId)}</span>
              <span>{deliveryText(tally)}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">Loading...</p>
      )}
      <p className="muted small">
        Counted from receipts the phones send back, so it can only undercount: a
        phone that was offline shows the notification but cannot report it.
      </p>

      {error && <p className="error">{error}</p>}
    </section>
  )
}
