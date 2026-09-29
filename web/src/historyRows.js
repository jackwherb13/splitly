// SPEC §T14.5 — History rows: newest first, names instead of ids, dated.
const money = (cents) => `$${(cents / 100).toFixed(2)}`

export function historyRows(entries, members) {
  const nameOf = (id) => members.find((member) => member.member_id === id)?.name ?? id
  return [...entries]
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .map((entry) => ({
      id: entry.entry_id,
      description: entry.description,
      total: money(entry.total),
      date: new Date(entry.created_at).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      }),
      paidBy: `${nameOf(entry.payer)} paid`,
      split: Object.entries(entry.shares)
        .map(([id, cents]) => `${nameOf(id)} ${money(cents)}`)
        .sort()
        .join(' · '),
    }))
}
