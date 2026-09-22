// SPEC §C23 — three input modes, one storage format (§C22).

import { describe, expect, it } from 'vitest'

import { allocated, buildBody, remaining, toCents, validate } from './entryBody'

const base = { description: 'groceries', total: 1000, payer: 'jackson' }

describe('§C23 — each mode shapes its own request', () => {
  it('even sends the member list and lets the server split it', () => {
    const body = buildBody({ ...base, mode: 'even', members: ['jackson', 'alice'] })
    expect(body).toEqual({
      description: 'groceries',
      kind: 'expense',
      total: 1000,
      payer: 'jackson',
      mode: 'even',
      members: ['jackson', 'alice'],
    })
    expect(body).not.toHaveProperty('amounts')
  })

  it('never computes shares itself — §C24 lives on the server only', () => {
    const body = buildBody({ ...base, mode: 'even', members: ['jackson', 'alice', 'dan'] })
    // 1000/3 has a remainder. If the UI were splitting, it would be here.
    expect(body).not.toHaveProperty('shares')
    expect(body).not.toHaveProperty('amounts')
  })

  it('all_to_one sends a single member', () => {
    expect(buildBody({ ...base, mode: 'all_to_one', member: 'dan' }).member).toBe('dan')
  })

  it('manual sends the typed amounts verbatim', () => {
    const amounts = { jackson: 400, alice: 600 }
    expect(buildBody({ ...base, mode: 'manual', amounts }).amounts).toEqual(amounts)
  })

  it('refuses a mode it does not know', () => {
    expect(() => buildBody({ ...base, mode: 'psychic' })).toThrow(/psychic/)
  })
})

describe('manual mode tracks what is left', () => {
  it('sums what has been allocated', () => {
    expect(allocated({ jackson: 400, alice: 600 })).toBe(1000)
  })

  it('ignores blanks rather than producing NaN', () => {
    expect(allocated({ jackson: 400, alice: undefined })).toBe(400)
  })

  it('reports the shortfall, and overshoot as a negative', () => {
    expect(remaining(1000, { jackson: 400 })).toBe(600)
    expect(remaining(1000, { jackson: 1200 })).toBe(-200)
  })
})

describe('money is parsed to integer cents, never floats', () => {
  it('rounds rather than truncating binary float error', () => {
    // 19.99 * 100 is 1998.9999... in binary floating point.
    expect(toCents('19.99')).toBe(1999)
    expect(toCents('0.1')).toBe(10)
    expect(toCents('10')).toBe(1000)
  })

  it('is NaN for nonsense, so validate can catch it', () => {
    expect(Number.isNaN(toCents('abc'))).toBe(true)
  })
})

describe('validation catches what the server would 400 on', () => {
  it('rejects manual amounts that do not add up (§V11)', () => {
    const form = { ...base, mode: 'manual', amounts: { jackson: 999 } }
    expect(validate(form)).toMatch(/add up/)
  })

  it('accepts manual amounts that do', () => {
    const form = { ...base, mode: 'manual', amounts: { jackson: 400, alice: 600 } }
    expect(validate(form)).toBeNull()
  })

  it('rejects a non-positive total', () => {
    expect(validate({ ...base, total: 0, mode: 'even', members: ['a'] })).toMatch(/zero/)
  })

  it('rejects an even split with nobody in it', () => {
    expect(validate({ ...base, mode: 'even', members: [] })).toMatch(/person/)
  })
})
