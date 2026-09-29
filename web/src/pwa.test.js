// SPEC §C3 — "installable" is the goal line's word, so it gets checked against
// the built output rather than against vite.config.js. Asserting on the config
// would prove only that we asked; this proves what shipped.
//
// `npm run verify` builds before it tests, for exactly this reason.

import { existsSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it, vi } from 'vitest'

const dist = (rel) => fileURLToPath(new URL(`../../dist/web/${rel}`, import.meta.url))
const tokens = readFileSync(fileURLToPath(new URL('./tokens.css', import.meta.url)), 'utf8')

const accent = tokens.match(/--accent:\s*(#[0-9A-Fa-f]{6})/)[1].toUpperCase()

describe('§C3 — the build produces an installable PWA', () => {
  it('emits a service worker', () => {
    // No service worker means no push at all, which is the point of §C3.
    expect(existsSync(dist('sw.js'))).toBe(true)
  })

  it('emits a manifest with the fields iOS needs to install it', () => {
    const manifest = JSON.parse(readFileSync(dist('manifest.webmanifest'), 'utf8'))
    expect(manifest.name).toBeTruthy()
    expect(manifest.short_name).toBeTruthy()
    expect(manifest.start_url).toBeTruthy()
    // §R1 — Safari tabs get no push; it has to be a home-screen web app.
    expect(manifest.display).toBe('standalone')
  })

  it('declares both icon sizes, and every icon it names actually exists', () => {
    const manifest = JSON.parse(readFileSync(dist('manifest.webmanifest'), 'utf8'))
    const sizes = manifest.icons.map((icon) => icon.sizes)
    expect(sizes).toContain('192x192')
    expect(sizes).toContain('512x512')
    for (const icon of manifest.icons) {
      expect(existsSync(dist(icon.src)), `manifest names ${icon.src}, which is not there`).toBe(
        true,
      )
    }
  })

  it('ships the PNG apple-touch-icon iOS requires', () => {
    // iOS ignores SVG here, so this one cannot be folded into the manifest.
    expect(existsSync(dist('apple-touch-icon.png'))).toBe(true)
  })

  it('themes the manifest from the token table, not a stray hex', () => {
    const manifest = JSON.parse(readFileSync(dist('manifest.webmanifest'), 'utf8'))
    expect(manifest.theme_color.toUpperCase()).toBe(accent)
  })
})

// §T11 — a push with no listener shows nothing, and iOS revokes subscriptions
// that stay silent. The generated worker has none of its own, so ours is
// imported into it; both halves are checked.
describe('§T11 — the service worker renders a push', () => {
  it('imports the push listener into the built worker', () => {
    expect(readFileSync(dist('sw.js'), 'utf8')).toMatch(/importScripts\([^)]*push-sw\.js/)
    expect(existsSync(dist('push-sw.js'))).toBe(true)
  })

  it('shows the payload as a notification, and holds the worker open until it has', async () => {
    const listeners = {}
    const showNotification = vi.fn(() => Promise.resolve())
    vi.stubGlobal('self', {
      addEventListener: (type, fn) => (listeners[type] = fn),
      registration: { showNotification },
    })
    const source = readFileSync(
      fileURLToPath(new URL('../public/push-sw.js', import.meta.url)),
      'utf8',
    )
    new Function(source)()

    const waitUntil = vi.fn()
    listeners.push({
      data: { json: () => ({ title: 'groceries', body: 'Jackson paid — your share is $10.00' }) },
      waitUntil,
    })

    expect(showNotification).toHaveBeenCalledWith('groceries', {
      body: 'Jackson paid — your share is $10.00',
    })
    expect(waitUntil).toHaveBeenCalledOnce()
    vi.unstubAllGlobals()
  })
})

// §T13 — the built worker waits to be told, rather than taking over a page
// that is running the old bundle. The Reload banner is what tells it.
describe('§T13 — a new version waits for the Reload tap', () => {
  it('skips waiting only on request', () => {
    const sw = readFileSync(dist('sw.js'), 'utf8')
    expect(sw).toContain('SKIP_WAITING')
    expect(sw).not.toMatch(/clientsClaim\(\)/)
  })
})

// §T14, §C19 — the device reports what it displayed. Display first: a failed
// receipt must never cost the notification, or iOS revokes the subscription.
describe('§T14 — the service worker sends a delivery receipt', () => {
  function runPush(payload, fetchImpl) {
    const listeners = {}
    const showNotification = vi.fn(() => Promise.resolve())
    const fetch = vi.fn(fetchImpl ?? (() => Promise.resolve({ ok: true })))
    vi.stubGlobal('self', {
      addEventListener: (type, fn) => (listeners[type] = fn),
      registration: { showNotification },
    })
    vi.stubGlobal('fetch', fetch)
    const source = readFileSync(
      fileURLToPath(new URL('../public/push-sw.js', import.meta.url)),
      'utf8',
    )
    new Function(source)()
    let held
    listeners.push({ data: { json: () => payload }, waitUntil: (p) => (held = p) })
    return { showNotification, fetch, held: () => held }
  }

  const PAYLOAD = {
    title: 'groceries',
    body: 'Jackson paid',
    push_id: 'p1',
    house_id: 'h1',
    receipt_url: 'https://api.example.com/receipts',
  }

  it('posts the receipt with the ids the push carried', async () => {
    const { fetch, held } = runPush(PAYLOAD)
    await held()
    const [url, options] = fetch.mock.calls[0]
    expect(url).toBe('https://api.example.com/receipts')
    expect(JSON.parse(options.body)).toEqual({ house_id: 'h1', push_id: 'p1' })
    vi.unstubAllGlobals()
  })

  it('still shows the notification when the receipt fails', async () => {
    const { showNotification, held } = runPush(PAYLOAD, () => Promise.reject(new TypeError('offline')))
    await expect(held()).resolves.not.toThrow()
    expect(showNotification).toHaveBeenCalledWith('groceries', { body: 'Jackson paid' })
    vi.unstubAllGlobals()
  })

  it('sends nothing for a push without an id', async () => {
    const { fetch, showNotification, held } = runPush({ title: 't', body: 'b' })
    await held()
    expect(showNotification).toHaveBeenCalledOnce()
    expect(fetch).not.toHaveBeenCalled()
    vi.unstubAllGlobals()
  })
})
