// SPEC §T14.5 — layout 4's Home: your balance, then the house.
import Balances from './Balances'
import { headline } from './homeText'
import NotifyCard from './NotifyCard'
import { notificationPermission, showNotifyCard } from './onboarding'

export default function Home({ balances, entries, members, me }) {
  const { label, amount, detail } = headline(balances, me)
  return (
    <>
      {showNotifyCard(entries, notificationPermission()) && <NotifyCard />}
      <section className="balance-card">
        <div>{label}</div>
        <div className="amount">{amount}</div>
        {detail && <div className="small">{detail}</div>}
      </section>
      <h2 className="eyebrow">The house</h2>
      <Balances balances={balances} entries={entries} members={members} me={me} />
    </>
  )
}
