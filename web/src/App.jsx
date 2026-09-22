import './app.css'

// The shell only. Entry CRUD arrives with T7, balances with T8.
export default function App() {
  return (
    <>
      <header>
        <h1>Splitly</h1>
      </header>
      <main>
        <p>Shared house ledger — who owes who.</p>
        <p className="muted">Nothing to show yet.</p>
      </main>
    </>
  )
}
