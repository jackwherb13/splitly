// SPEC §T14.5 — layout 4's Home: your balance, then the house.
import Balances from './Balances'
import { headline } from './homeText'
import IPaid from './IPaid'
import NotifyCard from './NotifyCard'
import { notificationPermission, showNotifyCard } from './onboarding'

const dollars = (cents) => `$${(cents / 100).toFixed(2)}`

export default function Home({ balances, entries, members, pending = [], me, onChanged }) {
  const { label, amount, detail } = headline(balances, me)
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
      <IPaid balances={balances} members={members} me={me} onChanged={onChanged} />
      <h2 className="eyebrow">The house</h2>
      <Balances
        balances={balances}
        entries={entries}
        members={members}
        pending={pending}
        me={me}
        onChanged={onChanged}
      />
    </>
  )
}
