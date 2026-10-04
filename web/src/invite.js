// SPEC §T15.6 — tell a new member they were added. The phone's share sheet
// picks the recipient from its own contacts, so Splitly never sees a number.

export const inviteText = (name, email, appUrl) =>
  `Hi ${name} — you've been added to Splitly for splitting house bills. ` +
  `Open ${appUrl} in Safari and sign in with ${email}.`

export async function sendInvite(text, nav = navigator, open = (href) => (window.location.href = href)) {
  if (nav.share) {
    try {
      await nav.share({ text })
      return
    } catch (err) {
      // Closing the share sheet is a choice, not a failure.
      if (err.name === 'AbortError') return
    }
  }
  open(`sms:&body=${encodeURIComponent(text)}`)
}
