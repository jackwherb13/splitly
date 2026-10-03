// SPEC §T15b — T14.5 moved the notifications toggle into Settings; this points there.
import { hrefFor } from './route'

export default function NotifyCard() {
  return (
    <section className="card notify">
      <strong>Last step: turn on notifications</strong>
      <p className="muted small">So you hear when someone adds an expense or nudges you.</p>
      <a className="cta" href={hrefFor('settings')}>
        Open Settings
      </a>
    </section>
  )
}
