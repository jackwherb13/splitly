import { useCallback, useEffect, useState } from 'react'

import './app.css'
import { createEntry, listBalances, listEntries, listMembers } from './api'
import { getToken, signOut } from './auth'
import Balances from './Balances'
import EntryForm from './EntryForm'
import SignIn from './SignIn'

const money = (cents) => (cents / 100).toFixed(2)

export default function App() {
  const [token, setToken] = useState(getToken())
  const [entries, setEntries] = useState([])
  const [members, setMembers] = useState([])
  const [balances, setBalances] = useState([])
  const [error, setError] = useState(null)

  const refresh = useCallback(async () => {
    try {
      const [loadedEntries, loadedMembers, loadedBalances] = await Promise.all([
        listEntries(),
        listMembers(),
        listBalances(),
      ])
      setEntries(loadedEntries)
      setMembers(loadedMembers)
      setBalances(loadedBalances)
      setError(null)
    } catch (err) {
      setError(err.message)
      // api.js clears the token on a 401, so an expired session drops us
      // back to the sign-in screen rather than showing an error forever.
      if (!getToken()) setToken(null)
    }
  }, [])

  useEffect(() => {
    if (token) refresh()
  }, [token, refresh])

  async function add(body) {
    await createEntry(body)
    await refresh()
  }

  if (!token) return <SignIn onSignedIn={setToken} />

  return (
    <>
      <header>
        <h1>Splitly</h1>
        <button
          type="button"
          className="link"
          onClick={() => {
            signOut()
            setToken(null)
          }}
        >
          Sign out
        </button>
      </header>

      <main>
        {error && <p className="error">{error}</p>}

        <section>
          <h2>Who owes who</h2>
          <Balances balances={balances} entries={entries} members={members} />
        </section>

        {members.length === 0 ? (
          <p className="muted">No members in this house yet. Member admin arrives with T8.5.</p>
        ) : (
          <EntryForm members={members} onCreated={add} />
        )}

        <section>
          <h2>Ledger</h2>
          {entries.length === 0 && <p className="muted">Nothing yet.</p>}
          <ul className="entries">
            {entries.map((entry) => (
              <li key={entry.entry_id}>
                <div className="row">
                  <span>{entry.description}</span>
                  <strong>{money(entry.total)}</strong>
                </div>
                <div className="muted small">
                  {entry.payer} paid &middot;{' '}
                  {Object.entries(entry.shares)
                    .map(([who, cents]) => `${who} ${money(cents)}`)
                    .join(' · ')}
                </div>
              </li>
            ))}
          </ul>
        </section>
      </main>
    </>
  )
}
