// SPEC §T14.5 — layout 4 (canvas board "4 · Wide Add in the bar").
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { renderToString } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { historyRows } from './historyRows'
import { headline } from './homeText'
import NavBar from './NavBar'
import { tabFromHash } from './route'
import Settings from './Settings'

describe('tabs live in the URL hash — back swipe and Reload land on the same tab', () => {
  it.each([
    ['', 'home'],
    ['#/', 'home'],
    ['#/add', 'add'],
    ['#/history', 'history'],
    ['#/settings', 'settings'],
    ['#/nonsense', 'home'],
  ])('%s → %s', (hash, tab) => {
    expect(tabFromHash(hash)).toBe(tab)
  })
})

describe('the Home card states your own balance', () => {
  const house = [
    { member_id: 'jackson', net: 4500 },
    { member_id: 'gabe', net: -4500 },
  ]

  it('owed, and by how many', () => {
    expect(headline(house, 'jackson')).toEqual({
      label: "You're owed",
      amount: '$45.00',
      detail: 'by 1 person',
    })
  })

  it('owing — §C40, the sign is carried by words, never a minus in green', () => {
    expect(headline(house, 'gabe')).toEqual({ label: 'You owe', amount: '$45.00', detail: '' })
  })

  it('settled, including someone with no entries yet', () => {
    expect(headline([], 'jackson').label).toBe("You're settled up")
  })

  it('counts people, not rows', () => {
    const three = [...house, { member_id: 'alice', net: -100 }]
    expect(headline(three, 'jackson').detail).toBe('by 2 people')
  })
})

describe('History — every entry, newest first, by name', () => {
  const members = [
    { member_id: 'jackson', name: 'Jackson' },
    { member_id: 'gabe', name: 'Gabe' },
  ]
  const entries = [
    { entry_id: 'a', created_at: '2026-09-28T10:00:00+00:00', description: 'Pizza', total: 1000,
      payer: 'gabe', shares: { gabe: 500, jackson: 500 } },
    { entry_id: 'b', created_at: '2026-09-29T15:08:00+00:00', description: 'Beach', total: 10000,
      payer: 'jackson', shares: { gabe: 10000 } },
  ]

  it('orders newest first', () => {
    expect(historyRows(entries, members).map((row) => row.description)).toEqual(['Beach', 'Pizza'])
  })

  it('names people instead of showing their ids', () => {
    const [beach, pizza] = historyRows(entries, members)
    expect(beach.paidBy).toBe('Jackson paid')
    expect(pizza.split).toBe('Gabe $5.00 · Jackson $5.00')
  })

  it('dates each entry', () => {
    expect(historyRows(entries, members)[0].date).toMatch(/Sep 29/)
  })

  it('falls back to the id for someone no longer listed', () => {
    const [, pizza] = historyRows(entries, [])
    expect(pizza.paidBy).toBe('gabe paid')
  })
})

describe('the bottom bar', () => {
  const html = (tab) => renderToString(<NavBar tab={tab} />)

  it('has Home, a labelled Add expense, and History', () => {
    expect(html('home')).toMatch(/href="#\/"/)
    expect(html('home')).toMatch(/href="#\/add"[^>]*>[\s\S]*Add expense/)
    expect(html('home')).toMatch(/href="#\/history"/)
  })

  it('marks the current tab for screen readers', () => {
    expect(html('history')).toMatch(/href="#\/history"[^>]*aria-current="page"/)
    expect(html('history')).not.toMatch(/href="#\/"[^>]*aria-current/)
  })

  it('clears the iPhone home indicator', () => {
    const css = readFileSync(fileURLToPath(new URL('./app.css', import.meta.url)), 'utf8')
    expect(css).toMatch(/\.navbar[^}]*env\(safe-area-inset-bottom\)/)
  })
})

describe('Settings', () => {
  const render = (props) =>
    renderToString(<Settings entries={[]} members={[]} balances={[]} session={{}} onSignOut={() => {}} onChanged={() => {}} {...props} />)

  it('§C17 — no notifications control until the ledger has shown something', () => {
    expect(render()).not.toMatch(/Turn on notifications|cannot show notifications/)
  })

  it('always offers sign out', () => {
    expect(render()).toMatch(/Sign out/)
  })

  it('admin sections only for an admin', () => {
    expect(render({ session: { admin: false } })).not.toMatch(/Add a member/)
    expect(render({ session: { admin: true } })).toMatch(/Add a member/)
  })
})

// §T16.5 — option A: every section folds, tapped open in place.
describe('Settings folds', () => {
  const members = [
    { member_id: 'jackson', name: 'Jackson', active: true },
    { member_id: 'gabe', name: 'Gabe', active: true },
    { member_id: 'old', name: 'Old', active: false },
  ]
  const render = (props) =>
    renderToString(
      <Settings entries={[{ entry_id: 'a' }]} members={members} balances={[]} session={{ admin: true }}
        onSignOut={() => {}} onChanged={() => {}} {...props} />,
    )
  const folds = (html) => [...html.matchAll(/<details class="fold"( open="")?><summary>(.*?)<\/summary>/g)]
    .map(([, open, summary]) => ({ open: Boolean(open), summary: summary.replace(/<[^>]+>/g, ' ') }))
  const withPermission = (permission, fn) => {
    globalThis.Notification = { permission }
    try {
      return fn()
    } finally {
      delete globalThis.Notification
    }
  }

  it('admin sees five sections, each with its own row', () => {
    expect(folds(render()).map((f) => f.summary.trim().split(/\s+/)[0])).toEqual([
      'Notifications', 'Members', 'Add', 'Write', 'Notification',
    ])
  })

  it('every admin section starts folded', () => {
    expect(folds(render()).slice(1).every((f) => !f.open)).toBe(true)
  })

  it('Notifications is open while they are off — the T15 card lands here', () => {
    const [notifications] = withPermission('default', () => folds(render()))
    expect(notifications).toEqual({ open: true, summary: expect.stringMatching(/Notifications\s+Off/) })
  })

  it('Notifications folds once they are on', () => {
    const [notifications] = withPermission('granted', () => folds(render()))
    expect(notifications).toEqual({ open: false, summary: expect.stringMatching(/Notifications\s+On/) })
  })

  it('Members shows how many are active, not how many rows', () => {
    expect(folds(render())[1].summary).toMatch(/Members\s+2/)
  })

  it('Delivery says its window', () => {
    expect(folds(render())[4].summary).toMatch(/last 7 days/)
  })

  it('a non-admin gets only the Notifications fold', () => {
    expect(folds(render({ session: { admin: false } }))).toHaveLength(1)
  })

  it('§C17 — no Notifications fold while the ledger is empty', () => {
    expect(folds(render({ entries: [], session: {} }))).toHaveLength(0)
  })

  it('Sign out is never folded away', () => {
    const outside = render().replace(/<details[\s\S]*?<\/details>/g, '')
    expect(outside).toMatch(/Sign out/)
  })
})
