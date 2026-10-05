// SPEC §T16.6 — "I paid" from the debtor, Verify from the person paid.
import { renderToString } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import Balances from './Balances'
import Home from './Home'
import { largestCreditor, pendingContribution } from './pendingText'

// React marks text/value seams with <!-- --> when rendering to a string.
const text = (html) => html.replaceAll('<!-- -->', '')

const members = [
  { member_id: 'jackson', name: 'Jackson', active: true },
  { member_id: 'gabe', name: 'Gabe', active: true },
  { member_id: 'sam', name: 'Sam', active: true },
]
const waiting = { pending_id: 'p1', from: 'gabe', to: 'jackson', amount: 2000, status: 'pending' }

describe('who "I paid" suggests', () => {
  it('the person the house owes the most', () => {
    const balances = [
      { member_id: 'jackson', net: 500 },
      { member_id: 'sam', net: 3000 },
      { member_id: 'gabe', net: -3500 },
    ]
    expect(largestCreditor(balances, 'gabe')).toBe('sam')
  })

  it('nobody when nobody is owed', () => {
    expect(largestCreditor([{ member_id: 'gabe', net: 0 }], 'gabe')).toBe(null)
  })
})

describe('§V3 — a pending payment in the drilldown', () => {
  it('credits the payer and debits the person paid, like the payment it stands for', () => {
    expect(pendingContribution(waiting, 'gabe')).toBe(2000)
    expect(pendingContribution(waiting, 'jackson')).toBe(-2000)
  })
})

describe('Home — the debtor side', () => {
  const render = (props) =>
    renderToString(
      <Home balances={[]} entries={[]} members={members} pending={[]} me="gabe" onChanged={() => {}} {...props} />,
    )

  it('offers "I paid" to someone who owes', () => {
    const balances = [{ member_id: 'gabe', net: -2000 }, { member_id: 'jackson', net: 2000 }]
    expect(render({ balances })).toContain('I paid')
  })

  it('not to someone settled or owed', () => {
    expect(render({ balances: [{ member_id: 'gabe', net: 0 }] })).not.toContain('I paid')
    expect(render({ balances: [{ member_id: 'gabe', net: 500 }] })).not.toContain('I paid')
  })

  it('says what is waiting on someone else, and who', () => {
    expect(text(render({ pending: [waiting] }))).toMatch(/Pending: \$20\.00 to Jackson/)
  })
})

describe('Balances — the side that got paid', () => {
  const balances = [
    { member_id: 'gabe', net: 0, entry_ids: [], pending_ids: ['p1'] },
    { member_id: 'jackson', net: 0, entry_ids: [], pending_ids: ['p1'] },
  ]
  const render = (me) =>
    renderToString(
      <Balances balances={balances} entries={[]} members={members} pending={[waiting]} me={me} onChanged={() => {}} />,
    )

  it('the person paid sees the claim with Verify and Didn’t get it', () => {
    const html = text(render('jackson'))
    expect(html).toMatch(/Says they paid you \$20\.00/)
    expect(html).toContain('Verify')
    expect(html).toContain('Didn’t get it')
  })

  it('nobody else gets the buttons', () => {
    expect(render('sam')).not.toContain('Verify')
    expect(render('gabe')).not.toContain('Verify')
  })
})
