// §T12, §V24 — the Nudge button is offered to someone the house owes, on the
// rows of people who owe it. The server enforces the rule; this checks the
// button actually appears when it should (it was reported missing on device).

import { renderToString } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import Balances from './Balances'

const members = [
  { member_id: 'jackson', name: 'Jackson', active: true },
  { member_id: 'gabe', name: 'Gabe', active: true },
]
// The live ledger on 2026-09-29.
const balances = [
  { member_id: 'gabe', net: -4500, entry_ids: [] },
  { member_id: 'jackson', net: 4500, entry_ids: [] },
]

const render = (me) =>
  renderToString(<Balances balances={balances} entries={[]} members={members} me={me} />)

describe('§V24 — where the Nudge button appears', () => {
  it('is offered to someone the house owes', () => {
    expect(render('jackson')).toContain('Nudge')
  })

  it('is not offered to someone in debt', () => {
    expect(render('gabe')).not.toContain('Nudge')
  })

  it('is not offered before the session has loaded', () => {
    expect(render(undefined)).not.toContain('Nudge')
  })
})
