// SPEC §T16.6 — pending payments, as the screens need them.

// Balances are net against the house, not person to person, so "who did you
// pay?" has no stored answer. The person owed the most is the best guess.
export function largestCreditor(balances, me) {
  const owed = balances.filter((row) => row.member_id !== me && row.net > 0)
  if (owed.length === 0) return null
  return owed.reduce((top, row) => (row.net > top.net ? row : top)).member_id
}

// §V3 — what a pending payment did to one person's figure, like a payment.
export const pendingContribution = (pending, memberId) =>
  (pending.from === memberId ? pending.amount : 0) - (pending.to === memberId ? pending.amount : 0)
