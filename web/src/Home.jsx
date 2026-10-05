// SPEC §T14.5 — layout 4's Home: your balance, then the house.
import Balances from './Balances'
import { headline } from './homeText'
import NotifyCard from './NotifyCard'
import { notificationPermission, showNotifyCard } from './onboarding'

const dollars = (cents) => `$${(cents / 100).toFixed(2)}`

export default function Home({ debts, entries, members, pending = [], me, onChanged }) {
  // §T16.7 — person to person: owed and owing are never netted across people.
  const { label, amount, detail } = headline(debts, me)
  const nameOf = (id) => members.find((m) => m.member_id === id)?.name ?? id
  // §T16.6 — already counted in the figure above; this says why.
  const mine = pending.filter((p) => p.from === me)
  return (
    <>
      {showNotifyCard(entries, notificationPermission()) && <NotifyCard />}
      <section className="balance-card">
        <div>{label}</div>
        <div className="amount">{amount}</div>
        {detail && <div className="small">{detail}</div>}
        {mine.map((p) => (
          <div key={p.pending_id} className="small">
            Pending: {dollars(p.amount)} to {nameOf(p.to)}
          </div>
        ))}
      </section>
      <h2 className="eyebrow">The house</h2>
      <Balances
        debts={debts}
        entries={entries}
        members={members}
        pending={pending}
        me={me}
        onChanged={onChanged}
      />
    </>
  )
}
