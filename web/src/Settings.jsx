// SPEC §T14.5 — notifications, sign out, and (admins only) house admin.
import Admin from './Admin'
import EnablePush from './EnablePush'
import Fold from './Fold'
import { notificationPermission } from './onboarding'

export default function Settings({ entries, members, balances, session, onSignOut, onChanged }) {
  return (
    <>
      <h2 className="eyebrow">Settings</h2>
      {/* §C17 — only once the ledger has shown something worth being
          notified about. Never on load. */}
      {entries.length > 0 && (
        // §T16.5 — open until notifications are on, because T15's card sends people here.
        <Fold
          title="Notifications"
          value={notificationPermission() === 'granted' ? 'On' : 'Off'}
          open={notificationPermission() !== 'granted'}
        >
          <EnablePush />
        </Fold>
      )}
      <p>
        <button type="button" className="secondary" onClick={onSignOut}>
          Sign out
        </button>
      </p>
      {session?.admin && <Admin members={members} balances={balances} onChanged={onChanged} />}
    </>
  )
}
