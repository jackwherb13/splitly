// SPEC §T15a — shown instead of sign-in in a Safari tab (§C18, §R1).
import shareSheet from './assets/add-to-home-screen.jpg'

export default function Install() {
  return (
    <main className="install">
      <h1>Add Splitly to your Home Screen</h1>
      <p className="muted">
        iPhones only send notifications to apps on the Home Screen, so Splitly only works from there.
      </p>
      <ol className="steps">
        <li>
          Tap <strong>•••</strong> then <strong>Share</strong>
        </li>
        <li>
          Tap <strong>Add to Home Screen</strong>
          <img src={shareSheet} alt="The Share menu with Add to Home Screen at the bottom of the first group" />
        </li>
        <li>
          Open <strong>Splitly</strong> from your Home Screen
        </li>
      </ol>
    </main>
  )
}
