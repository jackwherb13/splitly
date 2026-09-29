// SPEC §T14.5 — the Home card: your own balance. §C40: the sign is carried by
// the words, never by a green or red number.
const dollars = (cents) => `$${(Math.abs(cents) / 100).toFixed(2)}`

export function headline(balances, me) {
  const net = balances.find((row) => row.member_id === me)?.net ?? 0
  if (net === 0) return { label: "You're settled up", amount: '$0.00', detail: '' }
  if (net < 0) return { label: 'You owe', amount: dollars(net), detail: '' }
  const debtors = balances.filter((row) => row.net < 0).length
  return {
    label: "You're owed",
    amount: dollars(net),
    detail: `by ${debtors} ${debtors === 1 ? 'person' : 'people'}`,
  }
}
