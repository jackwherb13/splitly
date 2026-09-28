// §C40 — the brand is green, so a green "+" would read as branding rather
// than as meaning. Amounts stay in ink and the sign is carried by the label
// and by weight, which is also why the amount here is never negative.
//
// Sign convention comes from ledger.balances: positive means the house owes
// them, negative means they owe the house.

export function describeBalance(net) {
  const amount = (Math.abs(net) / 100).toFixed(2)
  if (net === 0) return { label: 'settled', amount, settled: true }
  return { label: net > 0 ? 'is owed' : 'owes', amount, settled: false }
}
