// SPEC §C40 — no colour-coded money. The brand is green, so a green "+"
// would read as branding rather than as meaning. The sign is carried by
// words and weight, and the amount itself is always positive.

import { describe, expect, it } from 'vitest'

import { describeBalance } from './balanceText'

describe('§C40 — the sign lives in the words, not in a colour', () => {
  it('positive means the house owes them', () => {
    expect(describeBalance(3000)).toEqual({ label: 'is owed', amount: '30.00', settled: false })
  })

  it('negative means they owe the house', () => {
    expect(describeBalance(-3000)).toEqual({ label: 'owes', amount: '30.00', settled: false })
  })

  it('the amount is never negative — the label carries the sign', () => {
    expect(describeBalance(-1).amount).toBe('0.01')
  })

  it('zero is settled, not "owes 0.00"', () => {
    expect(describeBalance(0)).toEqual({ label: 'settled', amount: '0.00', settled: true })
  })

  it('renders exact cents, never a rounded pound', () => {
    expect(describeBalance(-333).amount).toBe('3.33')
    expect(describeBalance(666).amount).toBe('6.66')
  })
})
