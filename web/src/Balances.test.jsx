// §T12, §V24 — the Nudge button is offered on the row of someone who owes me
// (person to person since §T16.7). The server enforces the rule; this checks the
// button actually appears when it should (it was reported missing on device).

import { renderToString } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import Balances from './Balances'

const members = [
  { member_id: 'jackson', name: 'Jackson', active: true },
  { member_id: 'gabe', name: 'Gabe', active: true },
]
// The live ledger on 2026-09-29: Gabe owes Jackson $45.
const debts = [{ from: 'gabe', to: 'jackson', amount: 4500, entry_ids: [], pending_ids: [] }]

const render = (me) =>
  renderToString(<Balances debts={debts} entries={[]} members={members} me={me} />)

describe('§V24 — where the Nudge button appears', () => {
  it('is offered to someone who is owed', () => {
    expect(render('jackson')).toContain('Nudge')
  })

  it('is not offered to someone in debt', () => {
    expect(render('gabe')).not.toContain('Nudge')
  })

  it('is not offered before the session has loaded', () => {
    expect(render(undefined)).not.toContain('Nudge')
  })
})
