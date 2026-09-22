// SPEC §V13 and §V16. The token table is tokens.css — the file that actually
// ships — so the spec, the test and the browser cannot disagree. See B4.

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const read = (rel) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8')

const tokens = Object.fromEntries(
  [...read('./tokens.css').matchAll(/--([\w-]+):\s*(#[0-9A-Fa-f]{6})/g)].map(
    ([, name, hex]) => [name, hex.toUpperCase()],
  ),
)

function luminance(hex) {
  const channels = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
  const [r, g, b] = channels.map((c) =>
    c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4,
  )
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contrast(fg, bg) {
  const [hi, lo] = [luminance(fg), luminance(bg)].sort((a, b) => b - a)
  return (hi + 0.05) / (lo + 0.05)
}

// Every pair the app renders body text with. A new pair means a new line here.
const BODY_TEXT_PAIRS = [
  ['ink', 'surface'],
  ['muted', 'surface'],
  ['on-accent', 'accent'],
]

describe('§V13 — body text clears WCAG AAA', () => {
  it.each(BODY_TEXT_PAIRS)('%s on %s is at least 7:1', (fg, bg) => {
    expect(tokens[fg], `--${fg} missing from tokens.css`).toBeDefined()
    expect(tokens[bg], `--${bg} missing from tokens.css`).toBeDefined()
    expect(contrast(tokens[fg], tokens[bg])).toBeGreaterThanOrEqual(7)
  })
})

describe('§V16 — tokens.css matches the palette the spec documents', () => {
  it('has exactly the hex values named in §C38 and §C39', () => {
    const spec = read('../../SPEC.md')
      .split(/\r?\n/)
      .filter((line) => line.startsWith('C38|') || line.startsWith('C39|'))
    expect(spec, 'C38/C39 not found in SPEC.md').toHaveLength(2)

    const inSpec = new Set(spec.join(' ').match(/#[0-9A-Fa-f]{6}/g).map((h) => h.toUpperCase()))
    const inCss = new Set(Object.values(tokens))
    expect(inCss).toEqual(inSpec)
  })
})
