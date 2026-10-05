import { useCallback, useEffect, useState } from 'react'

import './app.css'
import { createEntry, listBalances, listEntries, listMembers, listPending, whoami } from './api'
import { getToken, signOut } from './auth'
import EntryForm from './EntryForm'
import { splittable } from './entryBody'
import History from './History'
import Home from './Home'
import Install from './Install'
import { onLaunch } from './launch'
import NavBar from './NavBar'
import { mustInstall } from './onboarding'
import { go, hrefFor, useTab } from './route'
import Settings from './Settings'
import SignIn from './SignIn'
import { watchForUpdates } from './update'


export default function App() {
  const [token, setToken] = useState(getToken())
  const [entries, setEntries] = useState([])
  const [members, setMembers] = useState([])
  const [balances, setBalances] = useState([])
  const [pending, setPending] = useState([])
  const [session, setSession] = useState(null)
  const [reload, setReload] = useState(null)
  const tab = useTab()
  const [error, setError] = useState(null)

  const refresh = useCallback(async () => {
    try {
      const [loadedEntries, loadedMembers, loadedBalances, me, loadedPending] = await Promise.all([
        listEntries(),
        listMembers(),
        listBalances(),
        whoami(),
        listPending(),
      ])
      setEntries(loadedEntries)
      setMembers(loadedMembers)
      setBalances(loadedBalances)
      setPending(loadedPending)
      setSession(me)
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

  // §T13 — the rest of startup: keep this device's push subscription current
  // and storage persistent. Never prompts, never throws.
  useEffect(() => {
    if (token) onLaunch(import.meta.env.VITE_VAPID_PUBLIC_KEY)
  }, [token])

  useEffect(() => watchForUpdates((apply) => setReload(() => apply)), [])

  async function add(body) {
    await createEntry(body)
    await refresh()
    // §T14.5 — straight to Home, where the balance just changed.
    go('home')
  }

  // §T15a — a Safari tab never reaches sign-in (§C18, §R1).
  const standalone = window.matchMedia?.('(display-mode: standalone)').matches
  if (mustInstall({ standalone, prod: import.meta.env.PROD })) return <Install />

  if (!token) return <SignIn onSignedIn={setToken} />

  return (
    <>
      {reload && (
        <p className="card row">
          <span>A new version of Splitly is ready.</span>
          <button type="button" onClick={reload}>
            Reload
          </button>
        </p>
      )}
      <header>
        <h1>Splitly</h1>
        <a href={hrefFor('settings')} className="icon" aria-label="Settings">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
            <path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6" />
          </svg>
        </a>
      </header>

      <main>
        {error && <p className="error">{error}</p>}

        {tab === 'home' && (
          <Home
            balances={balances}
            entries={entries}
            members={members}
            pending={pending}
            me={session?.member_id}
            onChanged={refresh}
          />
        )}

        {tab === 'add' &&
          (members.length === 0 ? (
            <p className="muted">No members in this house yet.</p>
          ) : (
            <EntryForm members={splittable(members)} onCreated={add} />
          ))}

        {tab === 'history' && <History entries={entries} members={members} />}

        {tab === 'settings' && (
          <Settings
            entries={entries}
            members={members}
            balances={balances}
            session={session}
            onChanged={refresh}
            onSignOut={() => {
              signOut()
              setToken(null)
            }}
          />
        )}
      </main>

      <NavBar tab={tab} />
    </>
  )
}
