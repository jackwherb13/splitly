# Splitly — Decisions

Source of truth. Vault note `MyNotes/Projects/Splitly/Decisions.md` is an at-a-glance index pointing here.

## T6 PWA shell + B4, and T5 auth is a code not a link — 2026-09-22

### T5 — email OTP, not a magic link (§C4 amended)

- **A magic link is the wrong mechanism on iOS, and iOS is the whole house (§C3).** The app runs from the home screen because §R1 requires that before Safari will deliver push at all. A link tapped in Mail opens **Safari**, a different browsing context with different storage from the standalone PWA — so the session lands somewhere the app cannot see it. There is no reliable way to route an https link into an installed PWA on iOS
- **A six-digit code typed into the already-open app has no cross-context problem**, and Cognito ships managed passwordless email OTP natively. The link version needs three custom-auth Lambda triggers (`DefineAuthChallenge`, `CreateAuthChallenge`, `VerifyAuthChallengeResponse`) written, deployed and maintained. Better mechanism *and* far less code
- **Confidence, stated honestly:** the iOS routing claim is reasoned from how standalone web apps work, **not tested on Jackson's phone**. It is recorded in §C4 as rationale rather than as an §R row, because §R is for sourced external findings and this has no source
- **`ESSENTIALS` tier, deliberately.** Email OTP is not in the Lite tier. At four users the tier difference is cents
- **There is no pool-level passwordless in Cognito (§R12, learned from a 400 on first apply).** `CreateUserPool` rejects any `allowed_first_auth_factors` list that omits `PASSWORD`: *"Password should be configured as one of the allowed first auth factors."* So the pool lists it. **The client is what actually withholds it** — `explicit_auth_flows` carries only `ALLOW_USER_AUTH` and `ALLOW_REFRESH_TOKEN_AUTH`, no password flow — and no password is ever set or delivered, so there is nothing to use. Worth being precise about: the pool is *configured* to permit a factor the app can never reach, which is weaker than a pool that forbids it. AWS does not offer the latter
- **Create users with `--message-action SUPPRESS`.** Without it `admin-create-user` emails a temporary password, which both confuses the invite and puts a usable credential in an inbox. Suppressed, the only mail a user ever gets is the OTP
- **`generate_secret = false`** — a browser app cannot keep a secret, so the client is public and the trust boundary is the OTP, not a shared string
- **T5 does not satisfy §V10.** T5 issues a session; §V10 is about guarding admin routes with one, which is T8.5's named test. The row was not allowed to claim more than it does

### T6 — PWA shell

- **B4: §C39's `muted` token was 5.19:1 on surface, violating §V13's own 7:1 AAA requirement.** Caught by writing §V13's test, which had never existed — §C39 and §V13 were written in the same session and the test was not due until T6, so concrete hex values sat in prose, governed by an invariant, unchecked. Fixed to `#4B5851` (7.28:1) by darkening in HLS with hue and saturation held, so it is the same colour and not a new one
- **New §V16: the spec's palette and `tokens.css` must carry an identical hex set.** Without it, §V13 keeps passing on the code while §C38/§C39 quietly lie. That is the actual B4 lesson — values living in prose go unchecked — so closing it needed an invariant, not just a corrected number
- **The token table is `tokens.css`, not a JS constants file.** The test parses the CSS that actually ships, so the spec, the test and the browser cannot disagree
- **Added vitest rather than parsing CSS from pytest.** Frontend tests are inevitable from T7, §V13 is a frontend concern, and a JS project testing its own stylesheet from Python is the wrong answer. **Pinned to 2.x**: vitest 5 requires Vite 6+ and the project is on Vite 5, and upgrading Vite mid-task is churn this row did not ask for
- **`npm run verify` now builds *before* it tests.** §C3's word is "installable", so the check reads the built `manifest.webmanifest` and `sw.js`. Asserting on `vite.config.js` would prove only that we asked for a manifest — the §B2 shape again. It also catches a manifest naming an icon that was never built, which was mutation-tested
- **Icons are generated PNGs, not SVG.** iOS ignores SVG for `apple-touch-icon`, and the house is 100% iOS. Four files: 192, 512, a maskable 512 with an 18% safe zone for Android circle masks, and the 180 apple-touch-icon

## T8.5 stays its own row — 2026-09-22

- **Decided: keep T8.5 separate, do not fold it into T7.** Member admin (the §C48 active toggle and the §C50 write-off action) ships as its own task after T8
- **The reason is §V10, not size.** T8.5 is the **first and only row in §T that touches an admin-only surface**. Folded into T7 — which does not cite §V10 — the session guard would have no owning row until T20's IaC sweep at the very end. §V10's own text is `∀ admin route → session guard (⊥ forgotten)`, and merging the row is precisely how it gets forgotten
- **The counter-argument, recorded because it is real:** the write-off half *is* mechanically T7's entry form with a different `kind`, and §C50's allocation uses the §C23 manual split mode that T7 builds. So T8.5 genuinely depends on T7. The existing order (T7 → T8 → T8.5) already handles that, and it is the right order regardless — you need to see a balance before you can sensibly forgive one
- **The row was sharpened rather than just left alone.** It now names the §V10 test (`non-admin session → 403 on both routes`), records why it is not folded, and cites T7 as a dependency. An invariant whose row says only "admin-only" is an intention; one that names its test is a contract

## B3 — the ledger was silently truncated, and §V1 could not see it — 2026-09-22

- **Found by auditing T1–T4 against the spec, not by a failing test.** `Store._query` read `response["Items"]` and ignored `LastEvaluatedKey`. DynamoDB caps a Query at 1MB, so past that point `list_entries()` returned a **prefix** of the ledger and `balances()` reported confidently wrong numbers. Reproduced against moto before it was believed: **500 entries written, 316 returned, the payer's balance off by 37%**, no error
- **§V1 passed the whole time, and always would have.** A prefix of a zero-sum ledger also sums to zero. The T3 property test is *structurally* incapable of catching truncation — which is why this needed a new invariant rather than a better test
- **New §V15:** every store list returns every matching item; pagination exhausted, no silent prefix. Proven red first — 122 of 200 — then green
- **This is B1→B2→B3, the same failure three times, each one subtler.** B1: no check existed. B2: a check existed and tested the wrong property (filename, not content). B3: a check existed, tested the right property, and *that property was blind to the defect*. The lesson is not "write more tests" — it is that an invariant needs to be checked against the failure it is supposed to exclude
- **Not §C20 scale work.** At roughly 300 bytes an entry the page breaks near 3,500 entries; three entries a day reaches that in about three years. A correctness bug on a normal household timeline, not a scaling concern
- **Two weak guards hardened in the same pass, both the same shape.** `test_store_exposes_no_update_or_delete` searched method names for "update" and "delete" — `amend_entry` would have walked past it; it is now an allowlist of the four public methods. §C22's "no stored split style" had no test at all (T4 was closed on 09-15 as a *decision*, before any code existed to satisfy it); it is now an allowlist over `Entry`'s dataclass fields. Both were mutation-tested: adding `amend_entry` and adding a `split_style` field each fail exactly one test

## T2.5 DynamoDB table — 2026-09-20

- **Table is named `splitly`, not `splitly-entries`.** §T2.5's row says "entries table", but T2 put entries *and* members in the same partition (`HOUSE#<id>` with `ENTRY#`/`MEMBER#` sort-key prefixes), and subscriptions, bill defs and houses will land in it too. Single-table design — naming it `entries` would be a lie by T13
- **Streams deliberately left off.** §C29 wants DynamoDB Streams → Lambda, but T11 is the row that cites §C29. `stream_enabled` flips later as an **in-place update, not a table replacement**, so nothing is bought by enabling a feature no code calls
- **`prevent_destroy = true`**, matching the state bucket. §C6 promises entries are immutable; a stray `terraform destroy` would make that promise worthless
- **`PAY_PER_REQUEST`** — four users (§C20). Provisioned capacity means picking numbers with nothing to justify them and paying for idle
- **No `output` for the table name.** Nothing reads it until the API lands; an output no consumer uses is speculation
- **No SSE block** — DynamoDB encrypts at rest by default with an AWS-owned key
- Verified against the live account, not just the plan: `describe-table` returns `pk` HASH / `sk` RANGE, both `S`, `PAY_PER_REQUEST`, `ACTIVE`. Apply was `1 added, 0 changed, 0 destroyed`, confirming no drift against the bucket, OIDC provider or CI role

## Division of labor — narrowed for one task, then restored — 2026-09-20

- **Tried and reverted the same day.** Claude was briefly given Terraform authoring (Jackson keeping AWS terminal, AWS console and CI/CD). It covered exactly one task: Claude wrote `infra/dynamodb.tf`, Jackson ran `plan` and `apply`. Jackson then restored the 09-15 split
- **The 09-15 reversal stands unchanged:** Jackson writes everything GitHub, everything AWS, and all Terraform/IaC. Claude writes application code and guides/reviews the rest
- **Recorded rather than deleted** because the boundary has now moved three times (09-15 original → 09-15 reversal → 09-20 narrowing → 09-20 restored). The recurring pressure point is Terraform authoring, and the restored answer is that Jackson writes it

## T3 property tests over §V1 and §V11 — 2026-09-18

- **Red-before-green had nothing to drive.** T3 adds tests over invariants T2 already implements, so there was no production code to write. The honest substitute is **mutation testing**: each property was run against a deliberately broken `ledger.py` and had to fail. Dropping the §V11 check killed exactly `test_v11_rejects_any_total_disagreeing_with_shares`; crediting the payer one cent too much in `balances()` killed exactly the two §V1 properties. Both mutations reverted via `git checkout`. This is the §B2 lesson applied — a check that exists and passes blind is worse than no check
- **One drafted property was deleted for being tautological.** "Every entry in any generated ledger has shares summing to its total" tests the Hypothesis strategy, not `ledger.py`, because the strategy builds `total` as `sum(shares)`. It would have passed against *any* implementation. Exactly §B2's shape, caught before it landed
- **Added one property beyond the two cited:** `test_balances_are_order_independent`. §C6 says balances are derived by summing and never stored; a ledger that sums to zero in one order but not another would satisfy §V1's letter and break its meaning. One line, and it guards the claim §C6 actually makes
- **Fixed four-person roster instead of generated member names** (§C20). Members then genuinely collide across entries — with freely generated names almost every entry would touch a disjoint set of people, and the ledger-wide sum would be a much weaker test. It also keeps shrunk counterexamples readable
- **The example tests in `test_ledger.py` stay.** §C32 says §V1 and §V11 must be *properties*, not that examples are forbidden. The examples document what an entry means; the properties prove the invariant holds

## T2 ledger core — entry shape and the key schema T2.5 needs — 2026-09-16
- **The entry shape is the decision everything downstream reads:** `total` (int cents) + `payer` + `shares{member_id: cents}`, where shares must sum to total. Net effect is payer `+total`, each member `−their share`
- **§V1 needs no enforcement — it falls out of the shape.** Every entry nets to zero, so the ledger does too. An invariant that is a consequence of the data model cannot be violated by a future caller forgetting to check it
- **`total` is stored, not derived from `shares`.** Deriving it would make §V11 vacuous — there would be nothing left to disagree with. The point of §V11 is that a UI calculator splitting $100 three ways must still produce shares adding to $100, and that is only checkable if both numbers exist
- **A payment and a write-off are ordinary entries, not special cases.** Dan paying $50 is `total=50, payer=Dan, shares={Jackson:50}`; a §C50 write-off is the same shape with a different `kind`. This is §C6 paying for itself — no new concepts were needed for either
- **Money is integer cents everywhere, never float.** §V11 and §V12 are unprovable against binary floating point
- **`kind` is deliberately unvalidated.** No invariant constrains it yet, and validating it would be untested code; T8.5 introduces the write-off path that first cares
- **Frozen dataclass was not enough for §V8** — it blocks rebinding the attribute but still hands out a mutable `shares` dict, so the mapping is copied and wrapped in `MappingProxyType`. `test_entry_shares_cannot_be_mutated_through_the_mapping` covers the back door
- **§V8 on the store is enforced by absence:** there is no update and no delete method, and `test_store_exposes_no_update_or_delete` asserts none appears later

### Key schema — this is T2.5's input
```
pk = HOUSE#<house_id>    sk = ENTRY#<entry_id>
pk = HOUSE#<house_id>    sk = MEMBER#<member_id>
```
- One partition per house: listing a ledger is a single query, and entries and members are separated only by the sort-key prefix
- **`created_at` is deliberately NOT in the key.** A scheduled job firing twice (§C8 — EventBridge is at-least-once) derives its `entry_id` from its idempotency key, and the conditional write `attribute_not_exists(pk) AND attribute_not_exists(sk)` makes the retry a no-op — which is §V2, obtained for free at T17. **A timestamp in the key would give the retry a different key and post the bill twice.** Ordering is done in Python instead; at four users that is free (§C20)
- Table is billed `PAY_PER_REQUEST` in tests; T2.5 chooses the real billing mode

### Testing
- **`moto` added as a dev dependency** so store tests run offline in CI — the alternative was deferring `store.py` until T2.5 built a real table, which would have left the §T2 row half-done
- Store tests set dummy AWS credentials as a safety belt: if a mock ever fails to engage, the call fails on bad credentials instead of reaching a live account
- **Decimal round-trip is tested explicitly.** DynamoDB returns every number as `Decimal`; without conversion, cents come back as `Decimal` and quietly poison every downstream sum

## `?2` closed — move-in / move-out with an outstanding balance — 2026-09-16
- **Decided.** §C48, §C49, §C50 added; `?2` removed from the open list. T2 unblocked
- **Moving out changes exactly one thing: the member's `active` flag, which excludes them from *new* splits.** Everything else was already free under §C6 — entries are immutable, so the debt persists by construction. Jackson's instinct ("keep them there until they settle") turned out not to be a feature to build but the default behaviour of an append-only ledger
- **"Settled" is not stored.** It is `balance == 0`, derived. Same argument as §C6: a stored flag can disagree with the ledger, a derived one cannot
- **No proration (§C49).** A mid-cycle month uses the manual split mode §C23 already provides — the house agrees the number, the app records it. Day-based proration was costed and rejected: it needs move-in/out dates, billing-period math, and a rounding rule interacting with §C24, to serve a calculator used maybe twice in the project's life (§C20: four users, known personally)
- **Write-off is an offsetting entry, not a deletion (§C50).** Jackson asked for the ability to "remove" a debt that had persisted too long. §C6/§V8 forbid deletion, but the outcome he wanted — balance goes to zero — is reachable by posting an ordinary entry, and is strictly better: the ledger records that $X was *forgiven* rather than leaving a hole where the history was. Reminders then stop **for free** via the §C12/§V5 $10 floor
- **Allocation of a write-off uses manual mode, not an even split.** An even split would recover one person's loss from someone who never fronted the money — if Jackson paid most of what the departing housemate owed, evenly absorbing it makes Alice reimburse Jackson for a debt she had no part in. Same philosophy as §C49: the humans agree the number
- **Admin-gating needed no new machinery** — §V10 already requires a session guard on every admin route
- **No new §V invariant was added, deliberately.** §V1 (sum = 0), §V5, §V8 and §V10 already cover the behaviour. Needing no new invariant is evidence the design fits the existing model rather than fighting it
- **New §T8.5** (member admin — active toggle + write-off) exists because a constraint with no task is drift by construction. Flagged to Jackson as foldable into T7 if he prefers

## T1.5 COMPLETE — GitHub OIDC provider + CI role applied — 2026-09-16
- **Applied and verified.** `terraform state list` returns all seven resources: the four state-bucket resources plus `aws_iam_openid_connect_provider.github`, `aws_iam_role.ci`, `aws_iam_role_policy_attachment.ci`. Verified from a second shell, so it is state, not terminal scrollback
- **No thumbprint.** `thumbprint_list` is optional on the provider resource, and AWS ignores it for GitHub — it validates against its own trusted-CA library. The hardcoded `6938fd4d...` fingerprint in most tutorials is obsolete and used to break pipelines when it rotated. Verified against the provider docs before writing, not assumed
- **The security lives in the trust policy, not the permissions.** `sub` is pinned with `StringEquals` to exactly `repo:jackwherb13/splitly:ref:refs/heads/main`, plus `aud = sts.amazonaws.com`. **`StringLike` with `repo:owner/repo:*` was explicitly rejected** — that wildcard matches `pull_request`, so anyone who opens a PR against the repo could assume the role. With `aud` alone and no `sub`, any repo on GitHub could
- **`AdministratorAccess`, deliberately, with T20 to scope it.** Terraform needs IAM write to create Lambda execution roles, Cognito pools and the rest — that is effectively admin. The defensible position is that blast radius is controlled at the **trust boundary**: the credential is short-lived, mintable only by GitHub's OIDC issuer, only for this repo, only on `main`, and **no long-lived AWS key exists anywhere**. The stronger alternative (PowerUser + an IAM carve-out under a path prefix + a permissions boundary) was costed and deferred — it churns with every new service
- **One role, not two.** Pinned to `main`; PR builds cannot assume it. A read-only plan role for PRs was considered and deferred to T20, since no workflow calls either role yet and an untestable second role is speculation (`CLAUDE.md` §2)
- **Known consequence, recorded now so T20 does not rediscover it:** adding a GitHub **Environment** for a deploy approval gate changes the token's `sub` claim from `...:ref:refs/heads/main` to `...:environment:<name>`. The pinned condition would stop matching and the deploy would fail with an authorization error that looks nothing like its cause
- **Nothing in GitHub changed.** The role exists and is assumable; no workflow assumes it until T20. Verified as *correctly configured*, not as *working* — first real proof is T20's first run

## Terraform DOES read `~/.aws/cli/cache` — 09-15 finding falsified — 2026-09-16
- **Verified mechanism, replacing two wrong explanations.** The cached session at `~/.aws/cli/cache/` is named `botocore-session-...`. **botocore is the Python AWS CLI's SDK** — Terraform is Go and would never write that name. So the AWS CLI wrote the cache during the step-0 `aws iam list-open-id-connect-providers` call, and **Terraform consumed it**
- Proof it is a disk cache and not terminal state: a **non-interactive shell** — one that cannot prompt for MFA at all — ran `terraform state list` with only `AWS_PROFILE=splitly` set and authenticated cleanly
- Cache expiry matched `duration_seconds = 14400` exactly: written 15:21:50, expires 19:21:50. The next Terraform command after expiry prompts again
- **This kills the 09-15 prescription** that `AWS_PROFILE` is "the wrong lever" and that credentials must be exported every 4h. It also kills **my own** intermediate guess that the S3 backend could prompt in-process but the provider could not — `plan` refreshed all resources and falsified it immediately
- **Two wrong mechanisms in a row for one error message.** The error on 09-15 was real; every explanation offered for it since was invented. The cause of *that specific failure* is still unknown and is now recorded as unknown. See the vault note [[Terraform with MFA-Gated AWS Roles]]

## T1.5 two-thirds done — state bucket applied, state migrated to S3 — 2026-09-15
- **The §C44 sequence ran to completion and worked as specced.** Commits `8b0d725` (provider + `versions.tf`), `d2efdd8` (bucket), `fc70edb` (`backend "s3"` + `terraform init -migrate-state`). `infra/.terraform/terraform.tfstate` now records the S3 backend; the local `terraform.tfstate` is 0 bytes, which is what a completed migration looks like
- **State bucket `splitly-tfstate-725423737107`** — account-ID suffix because S3 bucket names are globally unique across all AWS customers, and a bucket named `splitly-tfstate` would be a coin flip. Carries versioning (a corrupted or truncated state push is recoverable), AES256 SSE, a full public-access block, and `prevent_destroy` — `terraform destroy` on the config that holds your state is an own-goal worth making impossible rather than careful
- **§C43 native locking is in the backend block** — `use_lockfile = true`, `required_version >= 1.11`, no DynamoDB lock table. Decided earlier (§R10); this records that it actually applied
- **The MFA credential path is confirmed, not assumed.** `aws configure export-credentials --profile splitly --format powershell | Invoke-Expression` with `AWS_PROFILE` **removed** is what lets the provider authenticate; the apply and the migration are the proof, since neither is possible without working credentials. **The predicted second wall did not materialise** — the S3 backend resolves credentials independently of the provider, but it reads the same exported environment variables, so `init -migrate-state` needed no extra work. Re-export every 4h per `duration_seconds = 14400`, per shell
- **What T1.5 still owes: the GitHub OIDC provider and the CI role.** Nothing for either exists in `infra/*.tf`. Both must be applied with Jackson's local credentials — CI cannot bootstrap its own access (§C45)
- **Found during the 2026-09-16 resume audit: `infra/state.json` is tracked by git**, committed in `fc70edb`. It is a genuine Terraform state file (`"version": 4`, `serial: 1`, resource attributes inline) and **orphaned** — its `lineage` `3461d0c8…` is not the live state's `d307d0aa…`, so it is a stale snapshot from an earlier run rather than the working state. Logged and fixed as **B2** (see below)

## §V14's marker list was the wrong shape — B2 fixed — 2026-09-16
- **The finding:** `.gitignore` and `test_repo_hygiene.py` both matched `*.tfstate*` / `.tfstate`. A state file named `state.json` matched neither and was committed. The §V14 test **passed blind on a real violation** — exactly the blind pass the 09-15 entry below congratulated itself for closing
- **Why it is not just a missing pattern:** adding `state.json` to the marker list fixes this one filename and leaves the class open. §V14 is written as *"no build artifact is tracked"* but implemented as *"no file whose **name** looks like a build artifact is tracked"* — and the artifact chooses its own name. `terraform show -json > state.json`, `plan.out`, `tfplan`, a hand-copied backup: all pass
- **The fix that matches the invariant:** identify state by **content**, not filename — any tracked file parsing as JSON with both `"terraform_version"` and `"lineage"` keys is Terraform state regardless of what it is called. Keeps the existing filename markers (cheap, catches directories like `.terraform/` that have no content signature) and adds the content check alongside
- **This is B1's failure mode a second time**, which is the argument for treating it as a class rather than an incident: B1 was `*.egg-info/` slipping past a check that did not exist; B2 is a state file slipping past a check that did exist but tested the wrong property
- **Done 2026-09-16.** §V14 is now **two clauses, both required**: (a) the existing filename markers, (b) any tracked file that parses as a JSON object carrying both `terraform_version` and `lineage`. `test_no_terraform_state_tracked` enforces (b); `infra/state.json` untracked via `git rm --cached` and added to `.gitignore`. `npm run verify` exits 0
- **Proven red before green, and the blind pass was visible in one run:** the new test failed naming `infra/state.json` while the old filename test passed alongside it — same repo, same commit, one check blind and one not
- **Substring matching was tried in the design and rejected**: `docs/Decisions.md` now discusses the key names `terraform_version` and `lineage` in prose, so a grep-style check flags this very file. Parsing the JSON and inspecting **top-level keys** distinguishes a state file from a document *about* state files. A content check still needs to be a check on *structure*, not on text
- **The file was left on disk, only untracked** — it is an orphaned snapshot (lineage `3461d0c8…` ≠ the live `d307d0aa…`), so nothing reads it, and deleting a file Jackson created is not the bug's fix
- **History deliberately not rewritten.** The blob remains at `fc70edb`. Private repo, orphaned state, no live credentials in it — a force-push to scrub one stale file costs more than it buys. Revisit only if the repo goes public

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
