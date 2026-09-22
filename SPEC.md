# Splitly — SPEC

## §G

shared house ledger — who owes who, recurring bills auto-split & posted, unpaid debts chased automatically ∴ Jackson ⊥ chase.

## §C

```
C1 |accept: wk8 → housemate logs|settles unprompted ∈ 7d window
C2 |⊥ money movement. record payments only → deep-link Venmo
C3 |v1 = installable PWA. Expo/RN after ledger proven. house 100% iOS
C4 |auth = invite-only magic link on Cognito. admin-created users. ⊥ self-signup
C5 |cloud = AWS. ! IaC + CI/CD + observability + known monthly cost
C6 |ledger append-only. entries immutable. balance derived by sum, ⊥ stored
C7 |∀ balance → drills down to entries that produced it
C8 |scheduled entries carry idempotency key (EventBridge at-least-once)
C9 |notifications = 1 module `notifications.py` w/ `send()`. ⊥ Protocol|adapter|selection wiring until 2nd impl exists (`~/.claude/CLAUDE.md` §2)
C10|4 notify triggers: entry created | manual nudge | scheduled bill posts | unpaid reminder
C11|unpaid reminder = per-person digest. ⊥ per-debt. every 3d, cap 3 → quiet until new entry|payment|manual nudge
C12|reminder floor = $10. ⊥ nag below
C13|reminder clock starts after grace period, ⊥ same day debt posts
C14|reminder interval default 3d. per-house configurable — later, ⊥ v1
C15|re-subscribe + persist push subscription ∀ app launch. 410 Gone → mark sub dead
C16|! request Storage API persistent mode (§R4)
C17|permission prompt ← user gesture, after value shown. ⊥ on load (§R1)
C18|onboarding ! walks each roommate through Add to Home Screen (§R1)
C19|service worker pings server ∀ notification receipt → measured delivery, ⊥ assumed (§R6)
C20|users ≈ 4, known personally. ⊥ scale work, ⊥ abuse protection
C21|budget 5-10 h/wk
C22|entry stores exact per-person amounts. 1 storage format ∀ splits. ⊥ store split style
C23|split input modes ∈ v1: (1) all → 1 person (2) even (3) manual per-person. UI calculators → C22, ⊥ record kinds
C24|even-split remainder cents → payer absorbs. deterministic
C25|frontend = Vite + React + `vite-plugin-pwa`. ⊥ Next.js — ⊥ SEO need, ∀ pages behind login
C26|host = S3 + CloudFront + ACM. https ! for service worker
C27|api = Python on Lambda + API Gateway
C28|db = DynamoDB. ⊥ RDS|Aurora — ~$40/mo floor ∀ 4 users
C29|entry written → DynamoDB Streams → Lambda → notify (= C10 trigger 1, ⊥ polling)
C30|scheduled work = EventBridge Scheduler → Lambda
C31|push = `pywebpush` + VAPID. secrets ∈ SSM Parameter Store
C32|tests = pytest + Hypothesis. V1,V11 = properties ⊥ examples
C33|IaC = Terraform. ⊥ CDK — HCL less pleasant, more transferable
C34|CI = GitHub Actions. tests gate deploy
C35|observability = CloudWatch alarms ∀ job failure + delivery-rate dashboard + AWS Budgets
C36|TDD ! — test first, ∀ code. per `~/.claude/CLAUDE.md` §6
C37|build = 1 step. artifacts → 1 location, gitignored. per `~/.claude/CLAUDE.md` §5
C38|palette = Emerald Ink `#064E3B` + Champagne `#F8E7C9`. chosen 2026-09-15 — only pair clearing AAA
C39|derived tokens, ⊥ user-named, ? adjustable: surface `#FFFCF5` · ink `#1A2B24` · muted `#5F6F66` · rule `#E8D3AE` · on-accent `#F8E7C9`
C40|⊥ green for +/− amounts. brand is green ∴ sign colour would read as brand. amounts in ink, sign by glyph + weight
C41|∀ §T complete → update `docs/Decisions.md` (if a decision was made) + vault `Progress.md` + vault `Status.md` if phase moved. ⊥ optional, ⊥ "at session end"
C42|∀ AWS resource ! born in Terraform. ⊥ console-first-then-import — weaker story & drift risk
C43|tf remote state = S3 backend, native locking `use_lockfile = true`. ⊥ DynamoDB lock table — deprecated, removal scheduled (§R10). `required_version >= 1.11`
C44|state bucket born ∈ same `infra/` cfg: local backend → apply bucket → add `backend "s3"` → `terraform init -migrate-state`. ⊥ separate `bootstrap/` cfg — leaves committed state file ∈ git ∀ 1 resource
C45|bootstrap infra (state bucket, OIDC provider, CI role) ∈ §C42. ⊥ exempt — circular dependency ≠ licence to click
C46|region = `us-east-1`, single. ACM cert ∀ CloudFront ! ∈ us-east-1 regardless (§C26) ∴ 1 region ⊥ 2-region cert dance
C47|local AWS auth = IAM user w/ only `sts:AssumeRole` → `AdminMFA` role, gated `aws:MultiFactorAuthPresent`. profile `splitly`, 4h sessions. ⊥ Identity Center while free plan alive — org creation burns Free Tier credits (§R11). ⊥ creds ∈ `.tf`
C48|member carries `active` flag. inactive → ∉ new splits. entries + balance untouched ∴ debt persists. "settled" = derived (balance == 0), ⊥ stored — same argument as C6
C49|⊥ proration ∀ mid-cycle move-in|out. partial month → manual split mode (C23). house agrees number, app records it. ⊥ move-in|out dates, ⊥ day-count math
C50|write-off = ordinary entry, admin-only (V10), tagged ⊽ payment ∴ drilldown shows forgiven, ⊥ paid. allocation via manual mode (C23) — even split would recover 1 person's loss from another. ⊥ deletion (C6,V8). balance → 0 ∴ reminders stop via V5
```

open `?` — ! resolve before §T reaches them:
```
?1 |partial payment → resets reminder cap? $5 on a $300 debt buys 3 quiet days = gameable. ledger half already closed by C6+C22 (payment = ordinary entry). belongs to T19, ⊥ blocks T2
?3 |bill amount changes month to month
?4 |dark-mode palette for the app. champagne ground ⊥ survives inversion naively
```

## §I

```
pwa   : Vite+React PWA → S3 + CloudFront. installable → iOS home screen (! for push, §R1)
auth  : Cognito magic link → JWT session
api   : API Gateway → Lambda (Python)
db    : DynamoDB — entries table, append-only
strm  : DynamoDB Streams → Lambda → `notifications.send()`
sched : EventBridge Scheduler → Lambda → post recurring bills + unpaid reminders
notify: `notifications.send()` → `pywebpush` ; ? sms → extract Protocol then, ⊥ now (§R8)
pay   : deep-link → Venmo, out-of-app. ⊥ callback
sec   : SSM Parameter Store — VAPID keys, Cognito cfg
ci    : GitHub Actions → pytest → terraform plan|apply → frontend deploy
? api route shapes undecided → defer to build
```

## §R

```
id|finding|source
R1|iOS push ! 16.4+, ! add-to-home-screen (Safari tab → ⊥ push), prompt ← user gesture|https://pushpad.xyz/blog/ios-special-requirements-for-web-push-notifications
R2|iOS 26 → home-screen sites default to opening as web apps|https://www.mobiloud.com/blog/progressive-web-apps-ios/ ?single-source
R3|home-screen web apps keep own day-of-use counter. WebKit: "we do not expect the first-party in such a web application to have its website data deleted" → expectation, ⊥ guarantee|https://webkit.org/blog/10218/full-third-party-cookie-blocking-and-more/
R4|storage still evictable @ quota|system pressure. Storage API persistent mode = explicit exemption|https://webkit.org/blog/14403/updates-to-storage-policy/
R5|field reports: push subs vanish after long inactivity. conflicting, no primary src|? UNVERIFIED
R6|⊥ push service guarantees device delivery. APNs/FCM/Expo return success long before display. only app-reported receipt proves it|https://docs.expo.dev/push-notifications/faq/
R7|Expo err 0.02% vs direct APNs 0.00% — transport ≠ difference. native edge = ⊥ install/permission gate|https://www.courier.com/integrations/compare/apple-push-notification-vs-expo
R8|A2P 10DLC Sole Proprietor brand = $4.50 one-time. toll-free number skips registration, free, ⊥ per-msg surcharge|https://support.twilio.com/hc/en-us/articles/1260803965530-What-pricing-and-fees-are-associated-with-the-A2P-10DLC-service
R9|Do Not Disturb suppresses silently. 201 from push service says ⊥ about display|https://developer.apple.com/forums/thread/770749
R10|tf 1.10 → S3 native locking experimental; 1.11 → GA + `dynamodb_table` deprecated, removal scheduled|https://developer.hashicorp.com/terraform/language/backend/s3
R11|AWS free plan (post-2025): creating an Organization force-upgrades to paid → remaining Free Tier credits expire immediately. plan self-expires @ 6mo from account open | credit exhaustion|https://aws.amazon.com/free/terms
```

## §V

```
V1 : sum(∀ entries) = 0 — property test ∈ CI
V2 : scheduled job fires ≥2× → exactly 1 entry (idempotency key)
V3 : ∀ balance shown → entries summing to it retrievable
V4 : reminders per debt ≤ 3 → then quiet
V5 : owed < $10 → ⊥ reminder
V6 : push permission requested ← user gesture only, ⊥ on load
V7 : 410 Gone → sub marked dead, ⊥ retried
V8 : ⊥ entry mutated | deleted after write
V9 : notification sent → receipt logged | flagged undelivered
V10: ∀ admin route → session guard (⊥ forgotten)
V11: ∀ entry → sum(per-person amounts) = entry total (⊥ rounding drift)
V12: even split → remainder cents to payer, ⊥ dropped
V13: ∀ body-text token pair → contrast ≥ 7:1 (WCAG AAA). test over token table
V14: ⊥ build artifact tracked by git. 2 clauses, ! both — name ⊽ content (B2)
     a) ∀ path ∈ `git ls-files` → ∉ {dist/, *.egg-info/, node_modules/, __pycache__/, *.pyc, .terraform/, *.tfstate*}
     b) ∀ tracked file parsing as JSON obj → ⊥ {terraform_version, lineage} ⊆ keys. tf state names itself ∴ name-match alone ⊥ sufficient
     `.terraform.lock.hcl` = exception, ! committed — pins provider hashes ∀ CI
V15: ∀ store list → ∀ matching item returned. pagination exhausted, ⊥ silent prefix (B3)
     §V1 ⊥ sufficient — ∀ prefix of a zero-sum ledger also sums to 0 ∴ V1 blind to truncation
```

## §T

```
id |status|task|cites
T1 |x|scaffold repo + 1-step build + CI gate (lint, pytest, build)|C5,C25,C27,C32,C34,C37,V14
T1.5|x|terraform bootstrap — remote state + provider + OIDC role only. ⊥ table: key schema undecided until T2|C5,C33,C42,C43,C44,C45
T2 |x|ledger core — entry model + member{id,name,active}, append-only store, derived balance. ! emit key schema → T2.5|C6,C48,V8,T1.5
T2.5|x|terraform: DynamoDB entries table w/ schema from T2|C28,C42
T3 |x|property tests: sum=0 & per-entry total|V1,V11
T4 |x|split model resolved → C22,C23,C24|C22,V11
T5 |.|Cognito invite-only magic link auth|C4,V10
T6 |.|PWA shell — manifest, service worker, tokens, installable|C3,C25,C26,C38,C39,V13
T7 |.|entry CRUD ui — 3 split input modes|C23,V11,V12
T8 |.|balance view + drilldown|C7,V3
T8.5|.|member admin — active toggle + write-off action. admin-only|C48,C50,V10
T9 |.|`notifications.py` — `send()` via `pywebpush`|C9,C31
T10|.|push subscribe flow, button-gated after value|C17,V6
T11|.|notify ∀ entry create, via stream|C10,C29
T12|.|manual nudge|C10
T13|.|sub lifecycle — re-subscribe @ launch, 410 handling|C15,V7
T14|.|delivery receipt ping + rate view|C19,V9
T15|.|onboarding — Add to Home Screen walkthrough|C18
T16|.|SHIP to house. wk8 clock starts|C1
T17|.|recurring bill defs + scheduled post w/ idempotency key|C8,C30,V2
T18|.|notify ∀ scheduled bill post|C10
T19|.|unpaid reminder job — digest, cap 3, $10 floor, grace. ! resolve ?1 here|C11,C12,C13,V4,V5,?1
T20|.|IaC sweep — confirm ∀ infra is Terraform, ⊥ console drift. shrinks if T1.5 held|C5,C33
T21|.|observability — alarms + delivery dashboard + budget|C5,C35
```

T16 deliberately mid-list: ship before reminders exist. wk8 clock ! start early, ⊥ after every feature.

## §B

```
id|date|cause|fix
B1|2026-09-15|`.gitignore` ⊥ `*.egg-info/` → editable pip install artifact swept in by `git add -A`, tracked outside dist/ ∴ §C37 violated. ⊥ check existed|V14
B2|2026-09-16|tf state dumped to `infra/state.json` → tracked. §V14 markers match *filename*, `state.json` ∉ `*.tfstate*` ∴ check existed + passed blind. B1 shape ×2: B1 = ⊥ check, B2 = check tested wrong property|V14b
B3|2026-09-22|`Store._query` ⊥ `LastEvaluatedKey` → `list_entries` returns only the 1st 1MB page. balance silently wrong (500 written → 316 returned, payer off 37%). §V1 passes anyway: ∀ prefix of a zero-sum ledger sums to 0 ∴ the property test is structurally blind. B1,B2 shape ×3 — B1 = ⊥ check, B2 = check tested wrong property, B3 = property untestable by the check that owns it|V15
```
