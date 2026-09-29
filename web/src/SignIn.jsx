import { useState } from 'react'

import { lastEmail, requestCode, submitCode } from './auth'

// §C4 — a code, not a link. A link tapped in Mail opens Safari, which is a
// different browsing context from the installed app, so the session would
// land somewhere this page cannot see.
export default function SignIn({ onSignedIn }) {
  // §T11.6 — the last address used, so signing back in is one tap.
  const [email, setEmail] = useState(lastEmail)
  const [code, setCode] = useState('')
  const [session, setSession] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function attempt(action) {
    setBusy(true)
    setError(null)
    try {
      await action()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const sendCode = () => attempt(async () => setSession(await requestCode(email.trim())))

  const signIn = () =>
    attempt(async () => onSignedIn(await submitCode(email.trim(), code.trim(), session)))

  return (
    <main className="signin">
      <h1>Splitly</h1>
      <p className="muted">Invite only. Enter the address you were added with.</p>

      <label htmlFor="email">Email</label>
      <input
        id="email"
        type="email"
        inputMode="email"
        autoComplete="email"
        value={email}
        disabled={session !== null}
        onChange={(event) => setEmail(event.target.value)}
      />

      {session === null ? (
        <button type="button" onClick={sendCode} disabled={busy || !email.trim()}>
          {busy ? 'Sending...' : 'Email me a code'}
        </button>
      ) : (
        <>
          <label htmlFor="code">Code</label>
          <input
            id="code"
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            value={code}
            onChange={(event) => setCode(event.target.value)}
          />
          <button type="button" onClick={signIn} disabled={busy || !code.trim()}>
            {busy ? 'Checking...' : 'Sign in'}
          </button>
        </>
      )}

      {error && <p className="error">{error}</p>}
    </main>
  )
}
