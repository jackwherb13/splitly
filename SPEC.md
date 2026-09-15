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
C9 |notifications = 1 module `notifications.py` w/ `send()`. ⊥ Protocol|adapter|selection wiring until 2nd impl exists (repo `CLAUDE.md` §2)
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
C36|TDD ! — test first, ∀ code. per repo `CLAUDE.md` §5
C37|build = 1 step. artifacts → 1 location, gitignored. per repo `CLAUDE.md` §4
C38|palette = Emerald Ink `#064E3B` + Champagne `#F8E7C9`. chosen 2026-09-15 — only pair clearing AAA
C39|derived tokens, ⊥ user-named, ? adjustable: surface `#FFFCF5` · ink `#1A2B24` · muted `#5F6F66` · rule `#E8D3AE` · on-accent `#F8E7C9`
C40|⊥ green for +/− amounts. brand is green ∴ sign colour would read as brand. amounts in ink, sign by glyph + weight
```

open `?` — ! resolve before §T reaches them:
```
?1 |partial payments
?2 |mid-month move-in / move-out w/ outstanding balance
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
```

## §T

```
id |status|task|cites
T1 |x|scaffold repo + 1-step build + CI gate (lint, pytest, build)|C5,C25,C27,C32,C34,C37
T2 |.|ledger core — entry model, append-only store, derived balance|C6,V8
T3 |.|property tests: sum=0 & per-entry total|V1,V11
T4 |x|split model resolved → C22,C23,C24|C22,V11
T5 |.|Cognito invite-only magic link auth|C4,V10
T6 |.|PWA shell — manifest, service worker, tokens, installable|C3,C25,C26,C38,C39,V13
T7 |.|entry CRUD ui — 3 split input modes|C23,V11,V12
T8 |.|balance view + drilldown|C7,V3
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
T19|.|unpaid reminder job — digest, cap 3, $10 floor, grace|C11,C12,C13,V4,V5
T20|.|IaC — ∀ infra in Terraform|C5,C33
T21|.|observability — alarms + delivery dashboard + budget|C5,C35
```

T16 deliberately mid-list: ship before reminders exist. wk8 clock ! start early, ⊥ after every feature.

## §B

```
id|date|cause|fix
```
