// SPEC §T11.6 — stay signed in, and remember the email.
// §V19 the email reaching Cognito is lowercased (B7)
// §V21 only a 401 is replayed after a refresh — POST /entries is not
//      idempotent, so replaying anything that might have landed duplicates it
// §V22 sign-out clears every credential, or a 30-day refresh token signs
//      you straight back in

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

function stubStorage() {
  const store = new Map()
  vi.stubGlobal('localStorage', {
    getItem: (key) => (store.has(key) ? store.get(key) : null),
    setItem: (key, value) => store.set(key, String(value)),
    removeItem: (key) => store.delete(key),
  })
  return store
}

const json = (status, body) => ({ ok: status < 400, status, json: async () => body })

// Cognito calls are told apart from API calls by their target header.
function stubFetch({ api = [], cognito = {} } = {}) {
  const calls = { api: [], cognito: [] }
  const fetch = vi.fn(async (url, options) => {
    const target = options.headers['x-amz-target']
    if (target) {
      const body = JSON.parse(options.body)
      calls.cognito.push(body)
      const answer = cognito[body.AuthFlow ?? target.split('.').pop()]
      if (answer instanceof Error) throw answer
      return answer ?? json(400, { message: 'refresh refused' })
    }
    calls.api.push({ url, options })
    const next = api.shift()
    if (next instanceof Error) throw next
    return next
  })
  vi.stubGlobal('fetch', fetch)
  return calls
}

const REFRESHED = json(200, { AuthenticationResult: { IdToken: 'new-id' } })

let storage
beforeEach(() => {
  vi.resetModules()
  storage = stubStorage()
})
afterEach(() => vi.unstubAllGlobals())

describe('§V19 — the email is lowercased before Cognito sees it', () => {
  it('when asking for a code', async () => {
    const calls = stubFetch({ cognito: { USER_AUTH: json(200, { Session: 's' }) } })
    const { requestCode } = await import('./auth')
    await requestCode('  Gmetcal@GMU.edu ')
    expect(calls.cognito[0].AuthParameters.USERNAME).toBe('gmetcal@gmu.edu')
  })

  it('when answering with the code', async () => {
    const calls = stubFetch({
      cognito: {
        RespondToAuthChallenge: json(200, {
          AuthenticationResult: { IdToken: 'id', RefreshToken: 'refresh' },
        }),
      },
    })
    const { submitCode } = await import('./auth')
    await submitCode('Gmetcal@gmu.edu', '123456', 's')
    expect(calls.cognito[0].ChallengeResponses.USERNAME).toBe('gmetcal@gmu.edu')
  })
})

describe('signing in keeps what is needed to stay signed in', () => {
  it('keeps the refresh token and the email', async () => {
    stubFetch({
      cognito: {
        RespondToAuthChallenge: json(200, {
          AuthenticationResult: { IdToken: 'id', RefreshToken: 'refresh' },
        }),
      },
    })
    const auth = await import('./auth')
    await auth.submitCode('Gabe@example.com', '123456', 's')
    expect(auth.getToken()).toBe('id')
    expect(auth.lastEmail()).toBe('gabe@example.com')
    expect([...storage.values()]).toContain('refresh')
  })
})

describe('§V22 — sign-out clears every credential', () => {
  it('removes the id token and the refresh token', async () => {
    storage.set('splitly.id_token', 'id')
    storage.set('splitly.refresh_token', 'refresh')
    const auth = await import('./auth')
    auth.signOut()
    expect([...storage.values()]).not.toContain('id')
    expect([...storage.values()]).not.toContain('refresh')
  })

  it('so a reload after sign-out cannot refresh its way back in', async () => {
    storage.set('splitly.refresh_token', 'refresh')
    const calls = stubFetch({ cognito: { REFRESH_TOKEN_AUTH: REFRESHED } })
    const auth = await import('./auth')
    auth.signOut()
    await expect(auth.refreshSession()).rejects.toThrow()
    expect(calls.cognito).toEqual([])
  })
})

describe('§V21 — an expired session renews itself, and only a 401 is replayed', () => {
  beforeEach(() => {
    storage.set('splitly.id_token', 'old-id')
    storage.set('splitly.refresh_token', 'refresh')
  })

  it('refreshes on a 401 and replays the request with the new token', async () => {
    const calls = stubFetch({
      api: [json(401, {}), json(200, { entries: ['e'] })],
      cognito: { REFRESH_TOKEN_AUTH: REFRESHED },
    })
    const { listEntries } = await import('./api')
    expect(await listEntries()).toEqual(['e'])
    expect(calls.api).toHaveLength(2)
    expect(calls.api[1].options.headers.authorization).toBe('Bearer new-id')
    expect(calls.cognito[0].AuthParameters.REFRESH_TOKEN).toBe('refresh')
  })

  it('does not replay a 500 — the entry may already have been written', async () => {
    const calls = stubFetch({ api: [json(500, { error: 'boom' })] })
    const { createEntry } = await import('./api')
    await expect(createEntry({})).rejects.toThrow()
    expect(calls.api).toHaveLength(1)
    expect(calls.cognito).toEqual([])
  })

  it('does not replay a network failure', async () => {
    const calls = stubFetch({ api: [new TypeError('Load failed')] })
    const { createEntry } = await import('./api')
    await expect(createEntry({})).rejects.toThrow('Load failed')
    expect(calls.api).toHaveLength(1)
  })

  it('a network failure on the replay is reported, not turned into a sign-out', async () => {
    stubFetch({
      api: [json(401, {}), new TypeError('Load failed')],
      cognito: { REFRESH_TOKEN_AUTH: REFRESHED },
    })
    const { listEntries } = await import('./api')
    await expect(listEntries()).rejects.toThrow('Load failed')
    expect([...storage.values()]).toContain('refresh')
  })

  it('signs out when the refresh itself is refused', async () => {
    stubFetch({ api: [json(401, {})] })
    const { listEntries } = await import('./api')
    await expect(listEntries()).rejects.toThrow(/sign in/i)
    expect([...storage.values()]).not.toContain('refresh')
    expect([...storage.values()]).not.toContain('old-id')
  })

  it('refreshes once when several requests expire together', async () => {
    const calls = stubFetch({
      api: [json(401, {}), json(401, {}), json(200, { entries: [] }), json(200, { members: [] })],
      cognito: { REFRESH_TOKEN_AUTH: REFRESHED },
    })
    const { listEntries, listMembers } = await import('./api')
    await Promise.all([listEntries(), listMembers()])
    expect(calls.cognito).toHaveLength(1)
  })
})
