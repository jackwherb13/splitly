// Push subscription — SPEC §C17, §V6, §R1.
//
// Nothing here runs on import. §V6 says the permission prompt follows a user
// gesture, and §C17 adds "after value has been shown": on iOS a refused
// prompt is close to permanent, and a prompt that appears before anyone has
// seen a balance is the surest way to get refused.
//
// §R1 also means this only works at all from a home-screen web app. A Safari
// tab will report support and then never deliver anything.

import { saveSubscription } from './api'

export function isSupported() {
  return (
    typeof Notification !== 'undefined' &&
    typeof navigator !== 'undefined' &&
    'serviceWorker' in navigator
  )
}

// pushManager wants raw bytes; VAPID keys are written as unpadded base64url.
export function urlBase64ToUint8Array(base64url) {
  const padded = base64url.padEnd(base64url.length + ((4 - (base64url.length % 4)) % 4), '=')
  const binary = atob(padded.replace(/-/g, '+').replace(/_/g, '/'))
  return Uint8Array.from(binary, (character) => character.charCodeAt(0))
}

export async function subscribe(publicKey) {
  if (Notification.permission === 'denied') {
    throw new Error('Notifications are blocked for this site in your browser settings.')
  }

  const permission = await Notification.requestPermission()
  if (permission !== 'granted') {
    throw new Error('Notifications were not enabled.')
  }

  const registration = await navigator.serviceWorker.ready
  const subscription = await registration.pushManager.subscribe({
    // Required by every browser: a push must result in something visible.
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(publicKey),
  })

  await saveSubscription(subscription.toJSON())
  return subscription
}
