// SPEC §T15 — onboarding: the install gate and the notifications card.
import { renderToString } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import Install from './Install'
import NotifyCard from './NotifyCard'
import SignIn from './SignIn'
import { mustInstall, showNotifyCard } from './onboarding'

describe('§T15a — a Safari tab gets the install screen, never sign-in (§C18, §R1)', () => {
  it('a tab in a production build must install', () => {
    expect(mustInstall({ standalone: false, prod: true })).toBe(true)
  })

  it('the home-screen app goes straight on', () => {
    expect(mustInstall({ standalone: true, prod: true })).toBe(false)
  })

  it('the dev server is never gated', () => {
    expect(mustInstall({ standalone: false, prod: false })).toBe(false)
  })

  it('walks the three steps, with the screenshot on step 2', () => {
    const html = renderToString(<Install />)
    expect(html).toContain('Add Splitly to your Home Screen')
    expect(html).toMatch(/Tap <strong>•••<\/strong> then <strong>Share<\/strong>/)
    expect(html).toMatch(/Tap <strong>Add to Home Screen<\/strong>/)
    expect(html).toMatch(/Open <strong>Splitly<\/strong> from your Home Screen/)
    expect(html).toMatch(/<img[^>]+alt="[^"]*Add to Home Screen[^"]*"/)
  })
})

describe('§T15b — Home asks for notifications until they are on', () => {
  const entries = [{ entry_id: 'a' }]

  it('§C17 — hidden while the ledger is empty', () => {
    expect(showNotifyCard([], 'default')).toBe(false)
  })

  it.each(['default', 'denied', 'unsupported'])('shown when permission is %s', (permission) => {
    expect(showNotifyCard(entries, permission)).toBe(true)
  })

  it('gone once notifications are allowed', () => {
    expect(showNotifyCard(entries, 'granted')).toBe(false)
  })

  it('links to Settings and has no way to dismiss it', () => {
    const html = renderToString(<NotifyCard />)
    expect(html).toContain('Last step: turn on notifications')
    expect(html).toContain('href="#/settings"')
    expect(html).not.toContain('<button')
  })
})

describe('§T15.5 — sign-in says where the code might land', () => {
  it('tells them to check Spam', () => {
    const html = renderToString(<SignIn onSignedIn={() => {}} />)
    expect(html).toContain('Check Spam')
  })
})
