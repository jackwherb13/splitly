import { useEffect, useState } from 'react'

import { addMember, createWriteOff, listDeliveries, setMemberActive } from './api'
import { deliveryText } from './deliveryText'
import { toCents } from './entryBody'
import Fold from './Fold'
import { inviteText, sendInvite } from './invite'

const money = (cents) => (cents / 100).toFixed(2)

// Admin-only, and this component is not the guard — the router is (§V10).
// Hiding the controls only avoids offering buttons the API would refuse.
export default function Admin({ members, debts = [], onChanged }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  // §T16.7, §V38 — forgive what one person owes another, never "the house".
  const pairKey = (d) => `${d.from}|${d.to}`
  const [pair, setPair] = useState(debts[0] ? pairKey(debts[0]) : '')
  const chosen = debts.find((d) => pairKey(d) === pair)
  const [amount, setAmount] = useState('')
  const [newName, setNewName] = useState('')
  const [newEmail, setNewEmail] = useState('')
  const [deliveries, setDeliveries] = useState(null)
  // §T15.6 — the member just added, until their invite is sent.
  const [invited, setInvited] = useState(null)

  // §C19 — measured delivery. A failure to load it is not worth an error.
  useEffect(() => {
    listDeliveries().then(setDeliveries, () => {})
  }, [])

  const nameOf = (id) => members.find((m) => m.member_id === id)?.name ?? id

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
    const total = amount.trim() === '' ? chosen.amount : toCents(amount)
    return run(() =>
      createWriteOff({
        description: `Write-off for ${nameOf(chosen.from)}`,
        forgiven: chosen.from,
        total,
        // §C50 — the person owed absorbs it: it is their money being forgiven.
        amounts: { [chosen.to]: total },
      }),
    )
  }

  function add() {
    return run(async () => {
      await addMember(newName, newEmail)
      setInvited({ name: newName.trim(), email: newEmail.trim() })
      setNewName('')
      setNewEmail('')
    })
  }

  return (
    <section className="card">
      <h2>Admin</h2>

      <Fold title="Members" value={String(members.filter((member) => member.active).length)}>
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
      </Fold>

      <Fold title="Add a member">
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
          No email is sent. Once they are added, send them the invite.
        </p>
        {invited && (
          <button
            type="button"
            className="secondary"
            onClick={() => sendInvite(inviteText(invited.name, invited.email, `${window.location.origin}/`))}
          >
            Send invite to {invited.name}
          </button>
        )}
      </Fold>

      <Fold title="Write off a debt">
        {debts.length === 0 ? (
          <p className="muted">Nobody is in debt.</p>
        ) : (
          <>
            <label htmlFor="forgiven">Forgive</label>
            <select id="forgiven" value={pair} onChange={(e) => setPair(e.target.value)}>
              {debts.map((d) => (
                <option key={pairKey(d)} value={pairKey(d)}>
                  {nameOf(d.from)} owes {nameOf(d.to)} {money(d.amount)}
                </option>
              ))}
            </select>

            <label htmlFor="amount">Amount (blank writes off the lot)</label>
            <input
              id="amount"
              inputMode="decimal"
              placeholder={chosen ? money(chosen.amount) : ''}
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />

            <button type="button" onClick={writeOff} disabled={busy || !chosen}>
              {busy ? 'Saving...' : 'Write it off'}
            </button>
            <p className="muted small">
              This posts an entry, it does not delete anything. The original expense
              stays on the ledger and the drilldown will show the debt as forgiven
              rather than paid.
            </p>
          </>
        )}
      </Fold>

      <Fold title="Notification delivery" value="last 7 days">
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
      </Fold>

      {error && <p className="error">{error}</p>}
    </section>
  )
}
