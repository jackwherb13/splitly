// SPEC §T15 — who sees the install screen and who sees the notifications card.

// §R1 — iOS only sends push to the home-screen app, so a Safari tab is never
// let past this point. The dev server is left open so it stays usable.
export const mustInstall = ({ standalone, prod }) => prod && !standalone

// §C17 still holds: nothing about notifications until the ledger has an entry.
// No dismiss — the card stays until this device allows notifications.
export const showNotifyCard = (entries, permission) =>
  entries.length > 0 && permission !== 'granted'

export const notificationPermission = () =>
  typeof Notification === 'undefined' ? 'unsupported' : Notification.permission
