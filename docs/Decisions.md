# Splitly — Decisions

Source of truth. Vault note `MyNotes/Projects/Splitly/Decisions.md` is an at-a-glance index pointing here.

## Palette: Emerald Ink / Champagne — 2026-09-15
- **Decided.** Emerald Ink `#064E3B` + Champagne `#F8E7C9`. Chosen from three candidates mocked as identical Splitly balance screens
- **Why it won:** WCAG contrast on the accent/ground pair — Emerald/Champagne is **7.99:1**, the only candidate clearing AAA (7:1). Signal Blue/Porcelain was 5.15:1 and Ultra Violet/Soft Apricot 5.28:1, both AA-only
- That matters more here than taste: Splitly's main screen is dense numeric text read on a phone, often in bad light
- Secondary benefit: the accent is dark enough to double as body text, so fewer colors have to be invented around it
- **Five derived tokens are Claude's placeholders, not Jackson's choices** (§C39): surface `#FFFCF5`, ink `#1A2B24`, muted `#5F6F66`, rule `#E8D3AE`, on-accent `#F8E7C9`. A two-color pair cannot dress a whole app; these are adjustable
- **§C40 — no green for +/- amounts.** The brand is green, so coloring gains green would read as brand rather than as sign. Amounts stay in ink; sign is carried by glyph and weight
- **New invariant §V13:** every body-text token pair must hit 7:1. Testable over the token table, so the reason this palette was picked cannot silently erode as tokens change
- **Parked `?4`:** dark-mode palette for the app. A champagne ground does not survive naive inversion
- Mockups: https://claude.ai/artifact/3SC2KuAKEPjCuNXPdBSoBU

## Division of labor — Jackson writes anything an interviewer would ask about — 2026-09-15
- **Jackson writes:** ledger core (entries, derived balances, split calculators), all Lambda handlers, the property tests (§V1, §V11), Terraform
- **Claude writes:** React components and UI chrome, service-worker boilerplate, CSS/layout/forms, GitHub Actions YAML
- **The line:** Jackson writes anything an interviewer would ask him to explain. "How do you guarantee balances never drift?" and "what happens when your scheduled job fires twice?" are the questions this project exists to let him answer — if Claude writes those, the résumé bullet becomes something he has to defend live without having written it
- UI chrome is the inverse: nobody asks him to justify a flexbox choice, and it is the bulk of the typing
- **Review style unchanged:** Claude names the bug, does not hand over the fix. Same as CardWatch and the standing preference

## Stack — 2026-09-15
- Written into `SPEC.md` as §C25-C35 and an expanded §I. Before this, none of it was recorded and `/build` would have been guessing
- **Frontend: Vite + React + `vite-plugin-pwa`.** Next.js rejected — every page is behind a login, so there is no SEO to serve, which is Next's entire value here. Also a different tool than ATS Website, so something is learned
- **Host: S3 + CloudFront + ACM.** HTTPS is mandatory for service workers
- **API: Python on Lambda + API Gateway.** Python is the language Jackson is deliberately building
- **DB: DynamoDB.** Append-only entries fit naturally; RDS/Aurora rejected on cost — ~$40/mo floor for a 4-user app
- **Entry-created notify: DynamoDB Streams → Lambda.** §C10 trigger 1 falls out of the write itself, no polling
- **Scheduled: EventBridge Scheduler → Lambda**
- **Push: `pywebpush` + VAPID, secrets in SSM Parameter Store** — same pattern as CardWatch
- **Tests: pytest + Hypothesis.** §V1 and §V11 are properties ("these always sum to zero"), not examples — Hypothesis is the right tool and is new tech
- **IaC: Terraform, not CDK.** CDK would be the nicer daily experience and would keep everything in Python; Terraform is what cloud-engineer job postings actually ask for, and flipping that gap-table row is part of why this project exists
- **CI: GitHub Actions**, tests gating deploy
- **Observability: CloudWatch alarms on job failure + delivery-rate dashboard (§C19) + AWS Budgets**

## Split model — exact amounts stored, split styles are UI only — 2026-09-15
- **Decided.** Closes `?1`, the last gap that blocked T7
- **Storage:** an entry always stores exact per-person amounts ("Alice $40.00, Bob $26.67, Carl $26.67, Dana $26.66"). One format forever. The split *style* is never recorded
- **Input modes in v1:** (1) assign the whole thing to one person, (2) split evenly, (3) divide it yourself. These are calculators in front of one storage format, not different kinds of record
- **Why this shape:** entries are immutable and append-only (§C6). Shipping "equal splits only" and adding weighted rent later would mean migrating a ledger promised never to be touched, or carrying two entry formats and writing every balance calculation twice. With this design, a new split style is a UI feature and never a migration
- **Uneven rent is covered without weights:** recurring bills store their split once at setup (T17), so "divide it yourself" is a one-time typing job, not a monthly chore
- **The penny rule:** $100 split 3 ways = $33.33 each = $99.99. A cent vanishes and §V1 breaks. **Payer absorbs the remainder** — deterministic, one line, socially invisible. Now §V12
- New invariant §V11: for every entry, per-person amounts sum to the entry total — the guard that makes rounding drift impossible rather than unlikely

## Named Splitly — 2026-09-15
- Working name Tally dropped. Repo `C:\Users\jwesl\Projects\Splitly`, vault folder `Projects/Splitly`, `SPEC.md` §G header updated, `?5 project name` closed in the spec
- Free to do now — no git remote, no code, nothing published
- `?` Unverified: "Splitly" may collide with an existing product. Irrelevant for a 4-person house app; **check before any public launch or domain purchase**

## Notification triggers — 2026-09-15
- **Four, all specced:** user creates an entry · manual nudge · scheduled bill posts · unpaid-balance reminder
- Jackson first narrowed to *only* user-entry + manual nudge, which would have deleted the automatic chasing §G promises — and with it the unattended scheduled job that made the cloud half of §C real rather than decorative
- Resolved by separating *entries* from *notifications*: recurring bills auto-generate **and** notify when they post. Silent auto-add was rejected as near-pointless — nobody is told the biggest bill of the month landed

## Unpaid reminder is capped, not relentless — 2026-09-15
- **Per-person digest**, every 3 days, **cap 3**, then quiet until a new entry, a payment, or a manual nudge. **$10 floor.** Grace period before the clock starts
- Per-debt reminders rejected — 5 outstanding items = 5 notifications per cycle = the uninstall path
- **The decisive reason is irreversibility:** on iOS there is exactly one shot at the notification permission (§R1). A housemate who mutes an over-aggressive nag **cannot be re-prompted** — recovery means walking them through iOS Settings by hand. The entire product is the notification, so an annoying nag doesn't just irritate, it permanently disarms the app for that person and fails wk8 for them forever
- The manual nudge is the escape hatch: when someone genuinely ignores it, a human taps a button — deliberate, not a robot barking every 72 hours

## Spec written — 2026-09-15
- `SPEC.md` at `C:\Users\jwesl\Projects\Splitly\SPEC.md`. Named **Splitly**
- `/review` judged unnecessary: greenfield, 4 users, no production blast radius. Next is `/build` at T1

## This replaces ATS as the portfolio project — 2026-09-15
- **Decided.** Reverses the 2026-09-13 choice of ATS Website
- Reason: roommates are a live user base with a weekly pull; the ATS client is blocked on *Jackson* for photos/copy he hasn't sent
- **Running both was explicitly rejected.** 5-10 h/wk split two ways is how both stall at Phase 1 — the failure mode CardWatch is currently demonstrating
- **Conditional:** ATS must be finished to a contractual minimum first (money was taken). Date still unnamed — the condition is not satisfied yet

## Usage is the success test, not shipping — 2026-09-15
- Acceptance = wk8 unprompted housemate action. Shipping is the most achievable and least meaningful measure; correctness is an invariant, not a finish line
- A money app that miscounts once loses house trust permanently, and then the usage test fails for good

## No money movement — 2026-09-15
- **Decided.** Record payments, deep-link to Venmo. Never process them
- Money-transmitter licensing, KYC, state registration is a real legal category; Splitwise itself largely avoids it. Venmo/Cash App public APIs are effectively closed to indie devs
- "Mark as paid" is a social contract in a 4-person house, not a security hole
- **"Architect for money later" explicitly rejected** — abstraction layers serving a feature that never ships

## PWA first, native second — 2026-09-15
- House is 100% iOS. Native was a stated *learning goal*, which fights the wk8 adoption criterion: $99/yr Apple account and TestFlight builds expiring every 90 days
- Ship a PWA in ~wk2, get real usage data, migrate to Expo/RN once the ledger is proven. Backend is identical either way
- If the house won't use a PWA they won't use a native app — cheaper to learn that for free

## Invite-only magic link on Cognito — 2026-09-15
- Four known users; **there is no public signup requirement**. Admin-created Cognito users + custom auth flow
- Gets the Cognito/IAM/JWT reps Jackson wanted while deleting email verification, password reset, and bot-signup work
- **Noted as a general rule:** accounts here pass the "does the product break without this?" test on their own merits. Choosing features *to justify AWS services* is a reversed driver — the CardWatch Cognito bolt-on is the cautionary case

## Append-only ledger, balances derived — 2026-09-15
- **Decided.** Entries are immutable and the truth; the net balance is computed by summing, never stored
- Jackson initially wanted a stored "running total" — that's the *feature*, and (b) produces it. The running total is the sum; it rises, falls, and flips sign exactly as wanted
- **The deciding edge:** EventBridge is *at-least-once*. A retried monthly rent job double-charges a stored balance silently and forever; an append-only entry with an idempotency key makes the second run a no-op
- Second edge: a roommate who moves out owing money. Immutable history keeps the debt computable instead of forcing a ghost row or a deletion
- Bonus: makes §V testable as one property over the whole ledger, running in CI — flips a gap-table row via data modeling rather than bolted-on tooling
- Cached balance snapshots rejected — at 4 users, summing all history is sub-millisecond, and a stale cache reintroduces the exact drift this prevents

## Notifications: one module, no port — 2026-09-15 (reverses the entry below)
- **Decided.** `notifications.py` with a `send()` function. **No Protocol, no adapter, no selection wiring** until a second implementation actually exists
- Reverses the same-day decision below, which specced a `Notifier` port with exactly one adapter
- **Why it flipped:** repo `CLAUDE.md` §2 forbids abstractions for single-use code and "flexibility that wasn't requested". The port was both — one implementation, and Claude's suggestion rather than Jackson's ask
- The R8 argument for the port (SMS is cheap, so a second impl is likely) is a *prediction*, not a requirement. YAGNI wins: extracting a Protocol from one working module later is a few lines, with callers already funnelled through one function
- **The distinction that resolved it:** a *module* is not an abstraction. One file holding all notification code is organization, and §2 has no objection — especially since §C15 (410 Gone) and §C19 (delivery receipts) make it a real module regardless. §2 objects to the Protocol + adapter + wiring layered on top
- Spec: §C9 rewritten, §I `strm`/`notify` lines and T9 updated

## SUPERSEDED — Notifications behind one port — 2026-09-15
- One `Notifier` interface, web-push adapter only for now. Same pattern as CardWatch's `ListingSource`/`PriceSource`
- Push + SMS up front rejected: two integrations serving a failure not yet observed
