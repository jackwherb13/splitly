// SPEC §T14.5 — the Home card: your own balance. §C40: the sign is carried by
// the words, never by a green or red number.
// §T16.7 — person to person: what you owe and what you're owed are never
// netted against each other, so you're settled only when both are zero.
const dollars = (cents) => `$${(Math.abs(cents) / 100).toFixed(2)}`

export function headline(debts, me) {
  const owe = debts.filter((d) => d.from === me).reduce((sum, d) => sum + d.amount, 0)
  const owedBy = debts.filter((d) => d.to === me)
  const owed = owedBy.reduce((sum, d) => sum + d.amount, 0)

  if (owe === 0 && owed === 0) return { label: "You're settled up", amount: '$0.00', detail: '' }
  if (owe > 0) {
    return { label: 'You owe', amount: dollars(owe), detail: owed > 0 ? `You're owed ${dollars(owed)}` : '' }
  }
  const people = new Set(owedBy.map((d) => d.from)).size
  return {
    label: "You're owed",
    amount: dollars(owed),
    detail: `by ${people} ${people === 1 ? 'person' : 'people'}`,
  }
}
