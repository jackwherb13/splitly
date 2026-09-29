// §T14 — the delivery rate as the Admin screen words it.
import { describe, expect, it } from 'vitest'

import { deliveryText } from './deliveryText'

describe('deliveryText', () => {
  it('states received of settled, and the rate', () => {
    expect(deliveryText({ received: 9, undelivered: 1, pending: 0, rate: 0.9 })).toBe(
      '9 of 10 delivered (90%)',
    )
  })

  it('mentions pushes still inside the grace period', () => {
    expect(deliveryText({ received: 1, undelivered: 0, pending: 2, rate: 1 })).toBe(
      '1 of 1 delivered (100%), 2 waiting',
    )
  })

  it('does not claim 100% when nothing has settled', () => {
    expect(deliveryText({ received: 0, undelivered: 0, pending: 0, rate: null })).toBe(
      'No notifications sent yet',
    )
  })
})
