import { getToken, signOut } from './auth'

const BASE = import.meta.env.VITE_API_URL

async function call(path, options = {}) {
  const token = getToken()
  const response = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      ...options.headers,
      'content-type': 'application/json',
      authorization: `Bearer ${token}`,
    },
  })

  // The id token lasts an hour (§T5). An expired one is a sign-in prompt,
  // not an error to show.
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
export const createEntry = (body) =>
  call('/entries', { method: 'POST', body: JSON.stringify(body) })
