// SPEC §C3 — "installable" is the goal line's word, so it gets checked against
// the built output rather than against vite.config.js. Asserting on the config
// would prove only that we asked; this proves what shipped.
//
// `npm run verify` builds before it tests, for exactly this reason.

import { existsSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

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
