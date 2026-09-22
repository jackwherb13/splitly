import { useState } from 'react'

import { buildBody, remaining, toCents, validate } from './entryBody'

const MODE_LABELS = {
  even: 'Split evenly',
  all_to_one: 'All to one person',
  manual: 'Enter amounts',
}

const money = (cents) => (cents / 100).toFixed(2)

export default function EntryForm({ members, onCreated }) {
  const ids = members.map((member) => member.member_id)
  const [description, setDescription] = useState('')
  const [amount, setAmount] = useState('')
  const [payer, setPayer] = useState(ids[0] ?? '')
  const [mode, setMode] = useState('even')
  const [chosen, setChosen] = useState(ids)
  const [one, setOne] = useState(ids[0] ?? '')
  const [typed, setTyped] = useState({})
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const total = toCents(amount)
  const amounts = Object.fromEntries(
    Object.entries(typed)
      .map(([id, text]) => [id, toCents(text)])
      .filter(([, cents]) => Number.isFinite(cents)),
  )

  const form = { description, total, payer, mode, members: chosen, member: one, amounts }
  const left = Number.isFinite(total) ? remaining(total, amounts) : Number.NaN

  function toggle(id) {
    setChosen((current) =>
      current.includes(id) ? current.filter((each) => each !== id) : [...current, id],
    )
  }

  async function submit() {
    const complaint = validate(form)
    if (complaint) {
      setError(complaint)
      return
    }
    setBusy(true)
    setError(null)
    try {
      await onCreated(buildBody(form))
      setDescription('')
      setAmount('')
      setTyped({})
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card">
      <h2>Add an expense</h2>

      <label htmlFor="what">What was it?</label>
      <input id="what" value={description} onChange={(e) => setDescription(e.target.value)} />

      <label htmlFor="amount">Amount</label>
      <input
        id="amount"
        inputMode="decimal"
        placeholder="0.00"
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
      />

      <label htmlFor="payer">Who paid?</label>
      <select id="payer" value={payer} onChange={(e) => setPayer(e.target.value)}>
        {members.map((member) => (
          <option key={member.member_id} value={member.member_id}>
            {member.name}
          </option>
        ))}
      </select>

      <div className="modes" role="group" aria-label="Split mode">
        {Object.entries(MODE_LABELS).map(([value, label]) => (
          <button
            key={value}
            type="button"
            className={mode === value ? 'mode on' : 'mode'}
            onClick={() => setMode(value)}
          >
            {label}
          </button>
        ))}
      </div>

      {mode === 'even' && (
        <fieldset>
          <legend>Split between</legend>
          {members.map((member) => (
            <label key={member.member_id} className="check">
              <input
                type="checkbox"
                checked={chosen.includes(member.member_id)}
                onChange={() => toggle(member.member_id)}
              />
              {member.name}
            </label>
          ))}
        </fieldset>
      )}

      {mode === 'all_to_one' && (
        <>
          <label htmlFor="owes">Who owes it?</label>
          <select id="owes" value={one} onChange={(e) => setOne(e.target.value)}>
            {members.map((member) => (
              <option key={member.member_id} value={member.member_id}>
                {member.name}
              </option>
            ))}
          </select>
        </>
      )}

      {mode === 'manual' && (
        <fieldset>
          <legend>Who owes what</legend>
          {members.map((member) => (
            <label key={member.member_id} className="check">
              {member.name}
              <input
                inputMode="decimal"
                placeholder="0.00"
                value={typed[member.member_id] ?? ''}
                onChange={(e) => setTyped({ ...typed, [member.member_id]: e.target.value })}
              />
            </label>
          ))}
          <p className={left === 0 ? 'muted' : 'error'}>
            {Number.isFinite(left)
              ? `${money(left)} left to allocate`
              : 'Enter an amount first'}
          </p>
        </fieldset>
      )}

      <button type="button" onClick={submit} disabled={busy}>
        {busy ? 'Saving...' : 'Add it'}
      </button>

      {error && <p className="error">{error}</p>}
    </section>
  )
}
