// SPEC §T14.5 — notifications, sign out, and (admins only) house admin.
import Admin from './Admin'
import EnablePush from './EnablePush'

export default function Settings({ entries, members, balances, session, onSignOut, onChanged }) {
  return (
    <>
      <h2 className="eyebrow">Settings</h2>
      {/* §C17 — only once the ledger has shown something worth being
          notified about. Never on load. */}
      {entries.length > 0 && <EnablePush />}
      <p>
        <button type="button" className="secondary" onClick={onSignOut}>
          Sign out
        </button>
      </p>
      {session?.admin && <Admin members={members} balances={balances} onChanged={onChanged} />}
    </>
  )
}
