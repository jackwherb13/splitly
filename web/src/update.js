// SPEC §T13 — an installed PWA keeps running the bundle it loaded until it
// is relaunched, often twice (the T12 deploy). So a waiting version is
// announced, and applied only when the user taps Reload: reloading on its
// own would throw away a half-typed entry.

import { registerSW } from 'virtual:pwa-register'

export function watchForUpdates(onVersionWaiting) {
  const updateSW = registerSW({
    onNeedRefresh: () => onVersionWaiting(() => updateSW(true)),
    onRegisteredSW(_url, registration) {
      if (!registration) return
      // iOS resumes an installed app without reloading, so look again then.
      document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') registration.update()
      })
    },
  })
}
