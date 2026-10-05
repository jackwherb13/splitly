// SPEC §T16.6, §T16.7 — debts are person to person, read from my side:
// positive when the other person owes me, negative when I owe them.

export function withMe(debts, me, other) {
  const owedToMe = debts.find((d) => d.from === other && d.to === me)?.amount ?? 0
  const iOwe = debts.find((d) => d.from === me && d.to === other)?.amount ?? 0
  return owedToMe - iOwe
}

// §V39 — what one entry contributes between two people: only the share one
// owes the other, never the entry's whole effect on anyone's balance.
export const pairLine = (entry, me, other) =>
  (entry.payer === me ? entry.shares[other] ?? 0 : 0) -
  (entry.payer === other ? entry.shares[me] ?? 0 : 0)

// A pending payment counts like the payment it stands for (§V34).
export const pendingLine = (pending, me) =>
  (pending.from === me ? pending.amount : 0) - (pending.to === me ? pending.amount : 0)
