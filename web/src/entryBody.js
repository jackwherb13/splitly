// Request shaping for the three §C23 input modes.
//
// The split maths deliberately does NOT live here. The server owns §C24's
// remainder rule, so the UI sends the mode and the members and lets the
// handler compute shares. Duplicating it in JS would mean two
// implementations of §V12 and a drift that silently loses cents.
//
// Manual mode is the exception, and only because the caller is typing the
// numbers: it needs a running total, which is a sum, not a split.

export const MODES = ['even', 'all_to_one', 'manual']

export function toCents(text) {
  const amount = Number.parseFloat(text)
  if (!Number.isFinite(amount)) return Number.NaN
  return Math.round(amount * 100)
}

export function allocated(amounts) {
  return Object.values(amounts).reduce((sum, cents) => sum + (cents || 0), 0)
}

export function remaining(total, amounts) {
  return total - allocated(amounts)
}

export function buildBody(form) {
  const base = {
    description: form.description,
    kind: form.kind ?? 'expense',
    total: form.total,
    payer: form.payer,
    mode: form.mode,
  }

  if (form.mode === 'even') return { ...base, members: form.members }
  if (form.mode === 'all_to_one') return { ...base, member: form.member }
  if (form.mode === 'manual') return { ...base, amounts: form.amounts }
  throw new Error(`unknown split mode: ${form.mode}`)
}

export function validate(form) {
  if (!form.description?.trim()) return 'Give it a description.'
  if (!Number.isFinite(form.total) || form.total <= 0) return 'Amount must be more than zero.'
  if (form.mode === 'even' && form.members.length === 0) return 'Pick at least one person.'
  if (form.mode === 'all_to_one' && !form.member) return 'Pick who owes it.'
  if (form.mode === 'manual' && remaining(form.total, form.amounts) !== 0) {
    return 'The amounts must add up to the total.'
  }
  return null
}


// §C48 — an inactive member is excluded from *new* splits only. They keep
// their entries and their balance, which is why this filters the roster the
// form offers and nothing else.
export function splittable(members) {
  return members.filter((member) => member.active)
}
