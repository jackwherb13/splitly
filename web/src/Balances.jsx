import { useState } from 'react'

import { answerPayment, nudge } from './api'
import PayPanel from './PayPanel'
import { pairLine, pendingLine, withMe } from './pendingText'

const money = (cents) => (cents / 100).toFixed(2)
const signed = (cents) => `${cents >= 0 ? '+' : '−'} ${money(Math.abs(cents))}`

// §T16.7 — The House, person to person: each row is one other member and
// what stands between the two of you. Raw pairs, never simplified (§V37).
export default function Balances({ debts, entries, members, pending = [], me, onChanged }) {
  const [openFor, setOpenFor] = useState(null)
  const [payingFor, setPayingFor] = useState(null)
  const [nudged, setNudged] = useState({})
  const [answering, setAnswering] = useState(null)

  async function sendNudge(memberId) {
    setNudged({ ...nudged, [memberId]: 'Sending...' })
    try {
      await nudge(memberId)
      setNudged((now) => ({ ...now, [memberId]: 'Nudged' }))
    } catch (err) {
      setNudged((now) => ({ ...now, [memberId]: err.message }))
    }
  }

  // §T16.6, §V32 — only the person paid answers. The server checks again.
  async function answer(pendingId, action) {
    setAnswering(pendingId)
    try {
      await answerPayment(pendingId, action)
      await onChanged()
    } finally {
      setAnswering(null)
    }
  }

  // Everyone but me who is still here, or who still has money between us.
  const others = members.filter(
    (m) => m.member_id !== me && (m.active || withMe(debts, me, m.member_id) !== 0),
  )
  if (others.length === 0) return <p className="muted">Nobody else here yet.</p>

  return (
    <ul className="balances">
      {others.map(({ member_id: other, name }) => {
        const between = withMe(debts, me, other)
        const open = openFor === other
        const between2 = entries.filter((e) => pairLine(e, me, other) !== 0)
        const waiting = pending.filter((p) => [p.from, p.to].includes(me) && [p.from, p.to].includes(other))

        return (
          <li key={other}>
            <button
              type="button"
              className="balance"
              aria-expanded={open}
              onClick={() => setOpenFor(open ? null : other)}
            >
              <span>{name}</span>
              <span className={between === 0 ? 'muted' : 'owed'}>
                {between > 0 && `owes you $${money(between)}`}
                {between < 0 && `you owe $${money(-between)}`}
                {between === 0 && 'settled with you'}
              </span>
            </button>

            {/* §V24 — only someone I'm owed by. The server checks again. */}
            {between > 0 && (
              <p className="row small">
                <button
                  type="button"
                  className="mode"
                  disabled={Boolean(nudged[other])}
                  onClick={() => sendNudge(other)}
                >
                  Nudge
                </button>
                {nudged[other] && <span className="muted">{nudged[other]}</span>}
              </p>
            )}

            {between < 0 &&
              (payingFor === other ? (
                <PayPanel
                  to={other}
                  name={name}
                  owe={-between}
                  onChanged={onChanged}
                  onClose={() => setPayingFor(null)}
                />
              ) : (
                <p className="row small">
                  <button type="button" className="mode" onClick={() => setPayingFor(other)}>
                    I paid them
                  </button>
                </p>
              ))}

            {waiting
              .filter((p) => p.from === other)
              .map((p) => (
                <div key={p.pending_id} className="small">
                  <p className="row">
                    <span>Says they paid you ${money(p.amount)}</span>
                  </p>
                  <p className="row">
                    <button
                      type="button"
                      className="mode"
                      disabled={answering === p.pending_id}
                      onClick={() => answer(p.pending_id, 'verify')}
                    >
                      Verify
                    </button>
                    <button
                      type="button"
                      className="mode"
                      disabled={answering === p.pending_id}
                      onClick={() => answer(p.pending_id, 'reject')}
                    >
                      Didn’t get it
                    </button>
                  </p>
                </div>
              ))}

            {/* §V39 — only what is between the two of us; the lines add up to the row. */}
            {open && (
              <ul className="drill">
                {between2.map((entry) => (
                  <li key={entry.entry_id} className="row small">
                    <span>{entry.description}</span>
                    <span>{signed(pairLine(entry, me, other))}</span>
                  </li>
                ))}
                {waiting.map((p) => (
                  <li key={p.pending_id} className="row small">
                    <span>Payment to {p.to === me ? 'you' : name} · waiting for verify</span>
                    <span>{signed(pendingLine(p, me))}</span>
                  </li>
                ))}
              </ul>
            )}
          </li>
        )
      })}
    </ul>
  )
}
