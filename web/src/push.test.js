// SPEC §V6, §C17 — the permission prompt follows a user gesture and never
// fires on load. §R1: iOS only delivers push to a home-screen web app, and a
// prompt that appears before any value is shown is the surest way to get a
// permanent "no".

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

function stubBrowser({ permission = 'default', granted = 'granted' } = {}) {
  const requestPermission = vi.fn().mockResolvedValue(granted)
  const subscribe = vi.fn().mockResolvedValue({
    toJSON: () => ({ endpoint: 'https://push.example.com/abc', keys: {} }),
  })
  // globalThis.navigator is getter-only in Node, so it has to be stubbed
  // rather than assigned.
  vi.stubGlobal('Notification', { permission, requestPermission })
  vi.stubGlobal('navigator', {
    serviceWorker: { ready: Promise.resolve({ pushManager: { subscribe } }) },
  })
  return { requestPermission, subscribe }
}

beforeEach(() => {
  vi.resetModules()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('§V6 — permission is never requested on load', () => {
  it('importing the module asks for nothing', async () => {
    const { requestPermission } = stubBrowser()
    await import('./push')
    expect(requestPermission).not.toHaveBeenCalled()
  })

  it('asks only once subscribe() is called', async () => {
    const { requestPermission } = stubBrowser()
    // Mocked before the import, or the real client would try to fetch.
    vi.doMock('./api', () => ({ saveSubscription: vi.fn().mockResolvedValue({}) }))
    const push = await import('./push')

    expect(requestPermission).not.toHaveBeenCalled()
    await push.subscribe('BJxIadV0v1Lx8bLbKPLSEUqmVJDLUCp1BWKCMBsZ9nCL')
    expect(requestPermission).toHaveBeenCalledOnce()
  })

  it('refuses without asking when the browser has already blocked it', async () => {
    // Re-prompting a blocked origin does nothing except look broken.
    const { requestPermission } = stubBrowser({ permission: 'denied' })
    const push = await import('./push')

    await expect(push.subscribe('BJxIadV0v1Lx8bLbKPLSEUqmVJDLUCp1BWKCMBsZ9nCL')).rejects.toThrow(
      /blocked/i,
    )
    expect(requestPermission).not.toHaveBeenCalled()
  })

  it('does not subscribe when the user says no', async () => {
    const { subscribe } = stubBrowser({ granted: 'denied' })
    const push = await import('./push')

    await expect(push.subscribe('BJxIadV0v1Lx8bLbKPLSEUqmVJDLUCp1BWKCMBsZ9nCL')).rejects.toThrow()
    expect(subscribe).not.toHaveBeenCalled()
  })
})

describe('the VAPID key is converted to the bytes pushManager wants', () => {
  // Imported per test, not statically: a static import would run before
  // the stubs and turn a §V6 regression into a collection error rather
  // than a failure of the test that is supposed to catch it.
  it('decodes base64url to a byte array', async () => {
    const { urlBase64ToUint8Array } = await import('./push')
    // "AQID" is base64 for bytes 1, 2, 3.
    expect(Array.from(urlBase64ToUint8Array('AQID'))).toEqual([1, 2, 3])
  })

  it('handles the - and _ that base64url uses in place of + and /', async () => {
    const { urlBase64ToUint8Array } = await import('./push')
    expect(Array.from(urlBase64ToUint8Array('-_8'))).toEqual([251, 255])
  })

  it('accepts an unpadded key, which is how VAPID keys are written', async () => {
    const { urlBase64ToUint8Array } = await import('./push')
    // A real 65-byte P-256 public key is 87 base64url characters, unpadded.
    const key = 'B' + 'A'.repeat(86)
    expect(urlBase64ToUint8Array(key)).toHaveLength(65)
  })
})
