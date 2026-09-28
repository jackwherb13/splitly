// §T11 — imported into the generated service worker (vite.config.js).
// Every push must show something: iOS revokes a subscription that stays silent.
self.addEventListener('push', (event) => {
  const { title, body } = event.data.json()
  event.waitUntil(self.registration.showNotification(title, { body }))
})
