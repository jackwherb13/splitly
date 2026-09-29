// SPEC §T14.5 — layout 4: Home · a wide, labelled Add expense · History.
import { hrefFor } from './route'

const current = (tab, name) => (tab === name ? 'page' : undefined)

export default function NavBar({ tab }) {
  return (
    <nav className="navbar" aria-label="Main">
      <a className="tab" href={hrefFor('home')} aria-current={current(tab, 'home')}>
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" />
        </svg>
        Home
      </a>
      <a className="add" href={hrefFor('add')} aria-current={current(tab, 'add')}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden="true">
          <path d="M12 5v14M5 12h14" />
        </svg>
        Add expense
      </a>
      <a className="tab" href={hrefFor('history')} aria-current={current(tab, 'history')}>
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
          <path d="M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01" />
        </svg>
        History
      </a>
    </nav>
  )
}
