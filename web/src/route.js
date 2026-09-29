// SPEC §T14.5 — the tab lives in the URL hash, so the iOS back swipe moves
// between tabs and a Reload (T13's banner) lands where you were. No router
// library: four fixed tabs do not need one.
import { useEffect, useState } from 'react'

const TABS = ['add', 'history', 'settings']

export function tabFromHash(hash) {
  const name = (hash || '').replace(/^#\/?/, '')
  return TABS.includes(name) ? name : 'home'
}

export const hrefFor = (tab) => (tab === 'home' ? '#/' : `#/${tab}`)

export function go(tab) {
  window.location.hash = hrefFor(tab)
}

export function useTab() {
  const [tab, setTab] = useState(() => tabFromHash(window.location.hash))
  useEffect(() => {
    const follow = () => setTab(tabFromHash(window.location.hash))
    window.addEventListener('hashchange', follow)
    return () => window.removeEventListener('hashchange', follow)
  }, [])
  return tab
}
