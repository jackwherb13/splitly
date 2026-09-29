// SPEC §T13 — what happens every time the app starts.
// §C15 re-subscribe + persist the subscription, when permission is already granted
// §V6  and never ask for permission to do it
// §V26 a dead endpoint (server says 410) is replaced, not re-saved
// §C16 ask for persistent storage
// plus the new-version prompt: an installed PWA keeps running its cached
//      bundle until relaunched, so it has to be told a new one is waiting

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const KEY = 'BJxIadV0v1Lx8bLbKPLSEUqmVJDLUCp1BWKCMBsZ9nCL'

const fakeSubscription = (endpoint) => ({
  endpoint,
  toJSON: () => ({ endpoint, keys: {} }),
  unsubscribe: vi.fn().mockResolvedValue(true),
})

function stubBrowser({ permission = 'granted', existing = null, persist = vi.fn() } = {}) {
  const requestPermission = vi.fn().mockResolvedValue('granted')
  const fresh = fakeSubscription('https://push.example.com/fresh')
  const pushManager = {
    getSubscription: vi.fn().mockResolvedValue(existing),
    subscribe: vi.fn().mockResolvedValue(fresh),
  }
  vi.stubGlobal('Notification', { permission, requestPermission })
  vi.stubGlobal('navigator', {
    serviceWorker: { ready: Promise.resolve({ pushManager }) },
    storage: persist ? { persist } : undefined,
  })
  return { requestPermission, pushManager, fresh, persist }
}

function stubApi(...results) {
  const saveSubscription = vi.fn()
  for (const result of results) {
    if (result instanceof Error) saveSubscription.mockRejectedValueOnce(result)
    else saveSubscription.mockResolvedValueOnce(result)
  }
  vi.doMock('./api', () => ({ saveSubscription }))
  return saveSubscription
}

const gone = () => Object.assign(new Error('this subscription is dead'), { status: 410 })

beforeEach(() => vi.resetModules())
afterEach(() => {
  vi.unstubAllGlobals()
  vi.doUnmock('./api')
  vi.doUnmock('virtual:pwa-register')
})

describe('§C15, §V6 — re-subscribe at launch, never prompt', () => {
  it('re-saves the existing subscription when permission was granted', async () => {
    const existing = fakeSubscription('https://push.example.com/mine')
    const { requestPermission, pushManager } = stubBrowser({ existing })
    const save = stubApi({})
    const { onLaunch } = await import('./launch')

    expect(await onLaunch(KEY)).toBe(true)
    expect(save).toHaveBeenCalledWith({ endpoint: 'https://push.example.com/mine', keys: {} })
    expect(pushManager.subscribe).not.toHaveBeenCalled()
    expect(requestPermission).not.toHaveBeenCalled()
  })

  it('makes a subscription when permission was granted but none exists', async () => {
    const { pushManager, requestPermission } = stubBrowser()
    const save = stubApi({})
    const { onLaunch } = await import('./launch')

    await onLaunch(KEY)
    expect(pushManager.subscribe).toHaveBeenCalledOnce()
    expect(save).toHaveBeenCalledWith({ endpoint: 'https://push.example.com/fresh', keys: {} })
    expect(requestPermission).not.toHaveBeenCalled()
  })

  it.each(['default', 'denied'])('does nothing at all when permission is %s', async (permission) => {
    const { requestPermission, pushManager } = stubBrowser({ permission })
    const save = stubApi()
    const { onLaunch } = await import('./launch')

    expect(await onLaunch(KEY)).toBe(false)
    expect(requestPermission).not.toHaveBeenCalled()
    expect(pushManager.subscribe).not.toHaveBeenCalled()
    expect(save).not.toHaveBeenCalled()
  })

  it('never throws — a failure leaves the manual button to do it', async () => {
    const { pushManager } = stubBrowser()
    pushManager.subscribe.mockRejectedValue(new Error('needs a user gesture'))
    stubApi()
    const { onLaunch } = await import('./launch')

    await expect(onLaunch(KEY)).resolves.toBe(false)
  })
})

describe('§V26 — a dead endpoint is replaced, not saved back', () => {
  it('drops the browser subscription and saves a fresh one on a 410', async () => {
    const existing = fakeSubscription('https://push.example.com/dead')
    const { pushManager } = stubBrowser({ existing })
    const save = stubApi(gone(), {})
    const { onLaunch } = await import('./launch')

    expect(await onLaunch(KEY)).toBe(true)
    expect(existing.unsubscribe).toHaveBeenCalledOnce()
    expect(pushManager.subscribe).toHaveBeenCalledOnce()
    expect(save).toHaveBeenLastCalledWith({ endpoint: 'https://push.example.com/fresh', keys: {} })
  })

  it('the button path does the same', async () => {
    const existing = fakeSubscription('https://push.example.com/dead')
    const { pushManager } = stubBrowser()
    pushManager.subscribe.mockResolvedValueOnce(existing)
    const save = stubApi(gone(), {})
    const { subscribe } = await import('./push')

    await subscribe(KEY)
    expect(existing.unsubscribe).toHaveBeenCalledOnce()
    expect(save).toHaveBeenCalledTimes(2)
  })
})

describe('§C16 — persistent storage is requested at launch', () => {
  it('asks for it', async () => {
    const persist = vi.fn().mockResolvedValue(true)
    stubBrowser({ permission: 'default', persist })
    stubApi()
    const { onLaunch } = await import('./launch')

    await onLaunch(KEY)
    expect(persist).toHaveBeenCalledOnce()
  })

  it('carries on where the Storage API is missing', async () => {
    stubBrowser({ persist: null })
    stubApi({})
    const { onLaunch } = await import('./launch')

    await expect(onLaunch(KEY)).resolves.toBe(true)
  })
})

describe('a new version is offered, not forced', () => {
  function stubRegister() {
    const updateSW = vi.fn()
    let options
    vi.doMock('virtual:pwa-register', () => ({
      registerSW: (given) => {
        options = given
        return updateSW
      },
    }))
    const listeners = {}
    vi.stubGlobal('document', {
      visibilityState: 'visible',
      addEventListener: (type, fn) => (listeners[type] = fn),
    })
    return { updateSW, options: () => options, listeners }
  }

  it('reports a waiting version, and reloads only when told to', async () => {
    const { updateSW, options } = stubRegister()
    const { watchForUpdates } = await import('./update')
    const offered = vi.fn()

    watchForUpdates(offered)
    options().onNeedRefresh()

    expect(offered).toHaveBeenCalledOnce()
    expect(updateSW).not.toHaveBeenCalled()
    offered.mock.calls[0][0]()
    expect(updateSW).toHaveBeenCalledWith(true)
  })

  it('checks again whenever the app comes back to the foreground', async () => {
    // iOS resumes an installed app without reloading it.
    const { options, listeners } = stubRegister()
    const { watchForUpdates } = await import('./update')
    const registration = { update: vi.fn() }

    watchForUpdates(vi.fn())
    options().onRegisteredSW('/sw.js', registration)
    listeners.visibilitychange()

    expect(registration.update).toHaveBeenCalledOnce()
  })
})
