# Splitly — Decisions

Source of truth. Vault note `MyNotes/Projects/Splitly/Decisions.md` is an at-a-glance index pointing here.

## §V14 extended to Terraform artifacts — before `infra/` exists — 2026-09-15
- **`.terraform/` and `*.tfstate*` added to the §V14 marker set**, to `test_repo_hygiene.py`, and to `.gitignore`. Commit `523ae6f`
- **Done as prep for T1.5, deliberately before the directory exists.** B1 was found *after* `*.egg-info/` was already committed. The provider cache runs to hundreds of MB and state files can contain secrets — both are B1's exact shape
- **Proven red before green**, same as B1: staged a fake `infra/.terraform/dummy.bin` and `infra/terraform.tfstate`, confirmed the existing test **passed blind**, then added the markers and watched it fail naming both. A test that only ever passes proves nothing
- **`.terraform.lock.hcl` is explicitly NOT a marker and NOT ignored** — it is committed on purpose, because it pins provider hashes so CI resolves exactly what was resolved locally. Noted in the test docstring so nobody "tidies" it into the ignore list later
- Not a §T row, so no status flipped

## AWS auth: assume-role + MFA, NOT Identity Center — free-tier credits decided it — 2026-09-15
- **Decided.** Local AWS auth is an IAM user holding *only* `sts:AssumeRole` into an `AdminMFA` role gated on `aws:MultiFactorAuthPresent`. Profile `splitly` in `~/.aws/config` with `role_arn` + `source_profile` + `mfa_serial`, 4-hour sessions. Terraform reads the profile via `AWS_PROFILE`; **no credentials in `.tf` files, ever**
- **IAM Identity Center was the recommendation and was rejected on cost** — not its own cost (Identity Center and Organizations both carry no service fee) but a second-order one. Identity Center requires an *organization instance*; account instances do not support AWS account access or permission sets. On AWS's post-July-2025 account model, **creating an organization force-upgrades a free-plan account to paid and expires remaining Free Tier credits immediately**. Jackson had **$150 left**. A documented Dec-2025 case shows ~$140 going to $0.00 exactly this way
- **The claim we did NOT bet on:** several secondary sources say upgrading to the paid plan *voluntarily first* preserves the credits to their original expiry. Plausible, **not in AWS's own docs**, and being wrong costs the full $150. Not worth the bet when a no-org path exists
- **Why the fallback is nearly as good:** assume-role + MFA was the standard practice for years before Identity Center existed. The long-lived key on disk can do exactly one thing, and only with the phone in hand. From T1.5 onward CI authenticates via **OIDC**, so Jackson's personal credentials never enter the pipeline regardless
- **Revisit trigger, not "someday":** the free plan expires on its own — 6 months from account opening, or when credits run out. **At that point upgrading is consequence-free and Identity Center should be revisited.** Until then, do not create an organization
- **Account + human identity sit below the §C42 floor.** §C45 puts the state bucket, OIDC provider and CI role *inside* Terraform. The AWS account itself and the admin identity Terraform authenticates *as* cannot be — they are what Terraform authenticates with. Clicking those in the console is not a §C42 violation
- Terraform **v1.16.2** installed, clears the `>= 1.11` floor §C43 requires
- **Still open: the region.** `us-east-1` recommended — ACM certificates for CloudFront must live there regardless (§C26), so a single region avoids a two-region cert dance. Not yet confirmed by Jackson, and T1.5's `provider` block needs it

## `?5` resolved — state bucket lives in the main config, local state then migrate — 2026-09-15
- **Decided: option A.** One `infra/` config. Apply the S3 state bucket with the default local backend, then add the `backend "s3"` block and run `terraform init -migrate-state`. **Closes `?5`, unblocks T1.5**
- **Verified as the documented path, not folklore** — this is HashiCorp's own migration flow: `init` detects local state and offers to copy it up. Both patterns are in wide use; the separate-config pattern is mostly a multi-account org habit, which does not apply to one personal AWS account
- **Rejected: a separate `bootstrap/` config.** It buys clean separation at the price of a second Terraform config and a state file committed to git *permanently*, for exactly one resource
- **Rejected: exempting bootstrap infrastructure from §C42.** Bootstrap infra is what must exist before Terraform can manage anything — here: the state bucket, the GitHub OIDC provider, and the IAM role CI assumes. A circular dependency is a reason to sequence carefully, not a licence to click. Now **§C45**
- **Bootstrap does not mean "outside Terraform."** The OIDC role is created by Terraform too, just with *Jackson's local credentials* — CI cannot bootstrap its own access. That ordering constraint is the whole definition
- **New §C43 — native state locking.** `use_lockfile = true`, `required_version >= 1.11`. **No DynamoDB lock table:** Terraform 1.10 shipped S3 native locking as experimental, 1.11 promoted it to GA and deprecated `dynamodb_table`, which is scheduled for removal. Sourced as **§R10**. This removes a resource T1.5 would otherwise have created
- **New §C44** records the sequence itself so the build loop does not have to rediscover it
- T1.5 scope unchanged and still Jackson's: state bucket + provider + OIDC provider/role. The entries table stays in T2.5

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

## Terraform bootstrap pulled forward as T1.5 — 2026-09-15
- **New §C42:** every AWS resource is born in Terraform. No console-first-then-import
- **New T1.5** (before T2): remote state, provider, and OIDC role. *(Narrowed 2026-09-15 in `55bc9c8`: the DynamoDB entries table was split out to **T2.5** — its key schema is not decided until T2 designs the entry model, so T1.5 could not have created it)*
- **Why:** §C33 said all infra is Terraform, but T20 sat at the *end* of the task list while T2 needs a table and T5 needs Cognito. As ordered, resources would be clicked into the console and imported months later — which contradicts §C33 and is a materially weaker interview answer than "every resource was code from the first one"
- Side benefit: it front-loads the least familiar tool, which at 5-10 h/wk is where the hard part belongs
- **T20 shrinks** to an IaC sweep confirming no console drift, rather than a build-it-all task

## `?1` partial payments split — 2026-09-15
- **The ledger half is already closed** by §C6 + §C22: a payment is an ordinary entry, and a partial payment is just an entry with a smaller number. The derived balance drops by exactly that much. No special handling, no new concept
- **The real open question is the reminder, not the ledger:** does a partial payment reset the §C11 cap? Someone owing $300 pays $5 and buys three days of silence — gameable as currently written
- Moved to **T19** (unpaid reminder job) where it belongs. **It no longer blocks T2**

## CLAUDE.md numbering fixed across all five copies — 2026-09-15
- Every `CLAUDE.md` on the machine had **two sections numbered `## 4`** — "Goal-Driven Execution" and "Builds are one click" — so seven sections were numbered as six
- Renumbered in all five: `~/.claude`, `Documents`, `Projects/Splitly`, `Projects/ATS_website`, `Projects/Rob-quote-tool`. Builds →§5, TDD →§6, final section →§7
- **Spec citations updated:** §C36 →§6 (TDD), §C37 →§5 (was citing by name to dodge the ambiguity, now a clean number). §C9 →§2, unchanged
- **The copies have diverged**, which the renumber exposed: ATS carries its own §7 "Docs are part of the change, not a follow-up"; Rob-quote-tool has no §7 at all; Splitly/Documents/user-level carry the Obsidian mirror. They are **not** interchangeable copies
- Jackson wants a `CLAUDE.md` kept in each project folder, so divergence is by design — but the shared §1-§6 now exist in five places and will drift again

## `~/.claude/CLAUDE.md` stays exactly Jackson's six sections — 2026-09-15
- **Reverses the merge recorded below.** The user-level file is restored to Jackson's original content verbatim: §1 Think Before Coding · §2 Simplicity First · §3 Surgical Changes · §4 Goal-Driven Execution · §4 Builds are one click *(duplicate number kept as written)* · §5 TDD · §6 Obsidian
- Claude's three additions (pre-build brief, docs-current, infra/code split) were **removed from that file and moved to memory instead**, where they load every session without altering Jackson's ruleset
- The full §6 body was kept even though only its heading was quoted back — it carries the live vault rules
- **Spec citations corrected** for the restored numbering: §C36 → §5 (TDD). §C37 now cites the section **by name** — `"Builds are one click"` — rather than §4, because two sections share that number and a numeric citation is ambiguous
- **Still true:** the user-level file applies to *every* session on this machine, including ATS and any existing repo — not only new projects

## SUPERSEDED — `~/.claude/CLAUDE.md` is now the basis for all projects — 2026-09-15
- The project `CLAUDE.md` was merged up to user level, which loads in every session regardless of directory. New projects inherit the whole ruleset without being set up
- **Defect found and fixed in the merge:** the original had **two sections numbered `## 4`** — "Goal-Driven Execution" and "Builds are one click". `SPEC.md` §C37 cited "§4", which was ambiguous between them
- Renumbered: builds §4→**§5**, TDD §5→**§6**. Added §7 (pre-build brief), §8 (docs current), §10 (infra vs code split)
- **Spec citations repointed** from `repo CLAUDE.md` to `~/.claude/CLAUDE.md` with corrected numbers: §C9 →§2, §C36 →§6, §C37 →§5
- `Projects/Splitly/CLAUDE.md` still exists and is now redundant with the user-level copy. **Left in place rather than deleted** — drift risk is real, so it should either be removed or trimmed to Splitly-only overrides

## Docs are updated as work happens, not at session end — 2026-09-15
- **`SPEC.md` §C41 added.** Every completed §T row updates `docs/Decisions.md` (if a decision was made), vault `Progress.md`, and vault `Status.md` if the phase moved
- **Gap it closes:** the vault CLAUDE.md already said to update project notes as work happens, but **nothing anywhere covered the repo's own `docs/`** — the source of truth. That was held in Claude's head, which is exactly how the ATS notes went stale
- Put in `SPEC.md` rather than only `CLAUDE.md` so the build loop reads it every time
- **Made global:** created `C:/Users/jwesl/.claude/CLAUDE.md` (user-level, loads in every session regardless of directory) carrying the same rule, so future projects inherit it without being told

## Every build task gets a pre-build brief — 2026-09-15
- Before starting any §T row, Claude states up front: **Will change** (files + what each does) · **Won't change** (adjacent things left alone) · **You'll see** (exact command + what good output looks like) · **Not yet visible** (stated honestly)
- **Why:** `npm run verify` exiting 0 is the oracle, not confirmation Jackson can see. He wants to check the work himself rather than take "tests pass" on faith
- Backend tasks (T2-T5) confirm via command output, and that gets said plainly rather than dressed up as visual. From T6 the PWA shell exists and confirmation becomes literal — run the dev server, look at it
- Where an invariant is the point of the task, showing it fail first and then pass is the strongest confirmation available (as B1/§V14 did in T1)

## Division of labor REVERSED — Jackson owns GitHub + AWS, Claude owns the code — 2026-09-15
- **Jackson writes:** everything GitHub (Actions workflows, repo/PR flow, OIDC) and everything AWS (Cognito, DynamoDB, Lambda config, S3/CloudFront, EventBridge, CloudWatch alarms, Budgets) plus all Terraform/IaC
- **Claude writes:** the application code — React components and CSS, the PWA shell, Python ledger core, Lambda handler bodies, `notifications.py`, and the pytest/Hypothesis property tests
- Stated as a standing preference for **future work too**, not just Splitly: "any of these github or aws features I want to do all myself and you handle most of the developing"
- **Supersedes the entry below**, which had Jackson writing the ledger and property tests and Claude writing UI chrome
- **The tradeoff, named once:** the old split's rule was "Jackson writes whatever an interviewer would ask him to explain," and it named the ledger as exactly that. This split moves the ledger to Claude. That is **correct for a cloud-engineer target** — there the pipeline, IAM and Terraform are the interview material — and **weaker for a straight SWE target**, where the ledger is what gets asked about. Revisit if the role target sharpens
- Review style unchanged: Claude names the bug, does not hand over the fix

## SUPERSEDED — Division of labor — Jackson writes anything an interviewer would ask about — 2026-09-15
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
