// SPEC §T16.6, §T16.7 — person-to-person debts, "I paid them" on the row,
// Verify from the person paid.
import { renderToString } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import Balances from './Balances'
import Home from './Home'
import PayPanel from './PayPanel'
import { pairLine, pendingLine, withMe } from './pendingText'

// React marks text/value seams with <!-- --> when rendering to a string.
const text = (html) => html.replaceAll('<!-- -->', '').replaceAll('&#x27;', "'")

const members = [
  { member_id: 'jackson', name: 'Jackson', active: true },
  { member_id: 'gabe', name: 'Gabe', active: true },
  { member_id: 'sam', name: 'Sam', active: true },
]
// Gabe owes Jackson $20; Jackson owes Sam $10.
const debts = [
  { from: 'gabe', to: 'jackson', amount: 2000, entry_ids: [], pending_ids: [] },
  { from: 'jackson', to: 'sam', amount: 1000, entry_ids: [], pending_ids: [] },
]
const waiting = { pending_id: 'p1', from: 'gabe', to: 'jackson', amount: 2000, status: 'pending' }

describe('withMe — one pair, from my side', () => {
  it('positive when they owe me, negative when I owe them, zero otherwise', () => {
    expect(withMe(debts, 'jackson', 'gabe')).toBe(2000)
    expect(withMe(debts, 'jackson', 'sam')).toBe(-1000)
    expect(withMe(debts, 'gabe', 'sam')).toBe(0)
  })
})

describe('§V39 — the drilldown for a pair adds up to that pair', () => {
  const groceries = {
    entry_id: 'e1', payer: 'jackson', total: 9000,
    shares: { jackson: 3000, gabe: 3000, sam: 3000 },
  }
  const pizza = { entry_id: 'e2', payer: 'gabe', total: 1000, shares: { jackson: 1000 } }

  it('counts only the share between the two, never the whole entry', () => {
    expect(pairLine(groceries, 'jackson', 'gabe')).toBe(3000)
    expect(pairLine(groceries, 'gabe', 'jackson')).toBe(-3000)
    expect(pairLine(pizza, 'jackson', 'gabe')).toBe(-1000)
  })

  it('an entry neither paid for is nothing between them', () => {
    expect(pairLine(pizza, 'sam', 'jackson')).toBe(0)
  })

  it('a pending payment from me counts for me, to me against me', () => {
    expect(pendingLine(waiting, 'gabe')).toBe(2000)
    expect(pendingLine(waiting, 'jackson')).toBe(-2000)
  })
})

describe('Home card — owed and owing are never netted across people', () => {
  const render = (me, props = {}) =>
    text(renderToString(
      <Home balances={[]} debts={debts} entries={[]} members={members} pending={[]} me={me} onChanged={() => {}} {...props} />,
    ))

  it('Jackson owes Sam and is owed by Gabe — both show', () => {
    const html = render('jackson')
    expect(html).toMatch(/You owe.*\$10\.00/)
    expect(html).toMatch(/You're owed \$20\.00/)
  })

  it('no "I paid" under the card any more — it lives on the row', () => {
    expect(render('gabe')).not.toMatch(/>I paid</)
  })

  it('says what is waiting on someone else, and who', () => {
    expect(render('gabe', { pending: [waiting] })).toMatch(/Pending: \$20\.00 to Jackson/)
  })
})

describe('The House — each row relative to me', () => {
  const render = (me, pending = []) =>
    text(renderToString(
      <Balances debts={debts} entries={[]} members={members} pending={pending} me={me} onChanged={() => {}} />,
    ))

  it('says who owes who, from my side', () => {
    const html = render('jackson')
    expect(html).toMatch(/Gabe.*owes you \$20\.00/)
    expect(html).toMatch(/Sam.*you owe \$10\.00/)
  })

  it('"I paid them" only on someone I owe', () => {
    const html = render('jackson')
    expect(html.match(/I paid them/g)).toHaveLength(1)
    expect(render('gabe')).toMatch(/Jackson.*I paid them/)
    expect(render('sam')).not.toContain('I paid them')
  })

  it('Nudge only on someone who owes me', () => {
    expect(render('jackson').match(/Nudge/g)).toHaveLength(1)
    expect(render('gabe')).not.toContain('Nudge')
  })

  it('the person paid sees the claim with Verify and Didn’t get it', () => {
    const html = render('jackson', [waiting])
    expect(html).toMatch(/Says they paid you \$20\.00/)
    expect(html).toContain('Verify')
    expect(html).toContain('Didn’t get it')
  })

  it('nobody else gets the buttons', () => {
    expect(render('sam', [waiting])).not.toContain('Verify')
    expect(render('gabe', [waiting])).not.toContain('Verify')
  })
})

describe('PayPanel — opened from "I paid them"', () => {
  const html = text(renderToString(
    <PayPanel to="sam" name="Sam" owe={1000} onChanged={() => {}} onClose={() => {}} />,
  ))

  it('one tap pays exactly what I owe that person', () => {
    expect(html).toContain('Paid in full · $10.00')
  })

  it('or a different amount', () => {
    expect(html).toMatch(/<input[^>]+id="pay-sam"/)
    expect(html).toContain('Send')
  })

  it('and it can be closed without sending — T16.6 had no way out', () => {
    expect(html).toContain('Cancel')
  })
})
