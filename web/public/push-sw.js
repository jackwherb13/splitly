// §T11 — imported into the generated service worker (vite.config.js).
// Every push must show something: iOS revokes a subscription that stays silent.
//
// §T14, §C19 — then the device reports that it displayed it. The receipt
// never holds up or cancels the notification, and a failed one is dropped:
// that push simply counts as undelivered.
self.addEventListener('push', (event) => {
  const { title, body, push_id, house_id, receipt_url } = event.data.json()
  const shown = self.registration.showNotification(title, { body })
  const receipt =
    push_id && receipt_url
      ? shown
          .then(() =>
            fetch(receipt_url, {
              method: 'POST',
              headers: { 'content-type': 'application/json' },
              body: JSON.stringify({ house_id, push_id }),
            }),
          )
          .catch(() => {})
      : shown
  event.waitUntil(receipt)
})
