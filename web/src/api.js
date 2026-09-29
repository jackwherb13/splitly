import { getToken, refreshSession, signOut } from './auth'

const BASE = import.meta.env.VITE_API_URL

const send = (path, options) =>
  fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      ...options.headers,
      'content-type': 'application/json',
      authorization: `Bearer ${getToken()}`,
    },
  })

async function call(path, options = {}) {
  let response = await send(path, options)

  // The id token lasts an hour; the refresh token renews it (§T11.6).
  // §V21 — only a 401 is replayed: the authorizer refused it before Lambda
  // ran, so it cannot have landed. A 5xx or a network error might have.
  if (response.status === 401) {
    const refreshed = await refreshSession().then(
      () => true,
      () => false,
    )
    // Only the refresh may end the session; a failed replay is reported.
    if (refreshed) response = await send(path, options)
  }
  if (response.status === 401) {
    signOut()
    throw new Error('Session expired — sign in again.')
  }

  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`)
  return data
}

export const listEntries = () => call('/entries').then((data) => data.entries)
export const listMembers = () => call('/members').then((data) => data.members)
export const listBalances = () => call('/balances').then((data) => data.balances)
export const whoami = () => call('/me')
export const saveSubscription = (subscription) =>
  call('/subscriptions', { method: 'POST', body: JSON.stringify({ subscription }) })
export const setMemberActive = (memberId, active) =>
  call(`/members/${memberId}`, { method: 'PUT', body: JSON.stringify({ active }) })
export const addMember = (name, email) =>
  call('/members', { method: 'POST', body: JSON.stringify({ name, email }) })
export const createWriteOff = (body) =>
  call('/write-offs', { method: 'POST', body: JSON.stringify(body) })
export const createEntry = (body) =>
  call('/entries', { method: 'POST', body: JSON.stringify(body) })
