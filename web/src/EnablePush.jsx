import { useState } from 'react'

import { isSupported, subscribe } from './push'

const PUBLIC_KEY = import.meta.env.VITE_VAPID_PUBLIC_KEY

// §C17 — the prompt follows a user gesture and only after value has been
// shown. App.jsx does not render this until there is at least one entry on
// the ledger, because on iOS a refused prompt is close to permanent and
// asking before anyone has seen a balance is how you get refused.
export default function EnablePush() {
  const [state, setState] = useState('idle')
  const [error, setError] = useState(null)

  if (!isSupported() || !PUBLIC_KEY) return null

  // §R1 — a Safari tab reports support and then never delivers anything.
  // Only a home-screen web app gets push on iOS.
  const installed = window.matchMedia?.('(display-mode: standalone)').matches

  async function enable() {
    setState('asking')
    setError(null)
    try {
      await subscribe(PUBLIC_KEY)
      setState('on')
    } catch (err) {
      setError(err.message)
      setState('idle')
    }
  }

  if (state === 'on') {
    return <p className="muted">Notifications are on for this device.</p>
  }

  return (
    <section className="card">
      <h2>Get notified</h2>
      <p className="muted small">
        A nudge when someone adds an expense or a bill is posted, so nobody has to
        chase anyone.
      </p>

      {installed === false && (
        <p className="muted small">
          Add Splitly to your home screen first — iOS only delivers notifications to
          installed apps, not to Safari tabs.
        </p>
      )}

      <button type="button" onClick={enable} disabled={state === 'asking'}>
        {state === 'asking' ? 'Waiting...' : 'Turn on notifications'}
      </button>

      {error && <p className="error">{error}</p>}
    </section>
  )
}
