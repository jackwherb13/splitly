// SPEC §T13 — once per launch, after sign-in.
//
// Never prompts (§V6) and never throws: if iOS refuses to subscribe without
// a tap, the "Turn on notifications" button is still there to do it by hand.

import { resubscribe } from './push'

export async function onLaunch(publicKey) {
  try {
    // §C16 — without this, iOS may evict storage, and the session with it.
    await navigator.storage?.persist?.()
  } catch {
    /* best effort */
  }
  try {
    return await resubscribe(publicKey)
  } catch {
    return false
  }
}
