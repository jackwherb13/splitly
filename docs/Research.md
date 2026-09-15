# Splitly — Research (§R)

Source of truth. Distilled rows also live in `SPEC.md` §R.

- Run 2026-09-15 via the `research` skill to close the blocking `?` from the grill: is iOS PWA web push good enough to carry the core loop?
- **Verdict: yes — §C stays PWA-first.** Three findings changed the design

## Findings

| # | Topic | Finding | Source |
|---|---|---|---|
| R1 | iOS push gate | iOS 16.4+, **must** be add-to-home-screen (Safari tab = no push); permission prompt only from a user gesture, on-load prompts rejected | [pushpad](https://pushpad.xyz/blog/ios-special-requirements-for-web-push-notifications) |
| R2 | iOS 26 | Sites added to Home Screen now default to opening as web apps | [mobiloud](https://www.mobiloud.com/blog/progressive-web-apps-ios/) `?` single-source |
| R3 | Home-screen storage | Home-screen web apps keep their **own day-of-use counter**; WebKit: "we do not expect the first-party in such a web application to have its website data deleted" — an **expectation, not a guarantee** | [webkit.org/blog/10218](https://webkit.org/blog/10218/full-third-party-cookie-blocking-and-more/) |
| R4 | Eviction | Still evictable under overall-quota or system storage pressure; Storage API **persistent mode** is an explicit exemption | [webkit.org/blog/14403](https://webkit.org/blog/14403/updates-to-storage-policy/) |
| R5 | Subscription loss | Field reports of push subscriptions disappearing after prolonged inactivity — conflicting, no primary source | `?` **UNVERIFIED** |
| R6 | Delivery signal | **No push service guarantees device delivery.** APNs/FCM/Expo all return success long before anything appears on screen; only the app reporting a receipt proves it | [Expo FAQ](https://docs.expo.dev/push-notifications/faq/) |
| R7 | Native vs web | Expo 0.02% error rate vs direct APNs 0.00% — transport is not the difference. Native's real edge is having **no install/permission gate** | [courier.com](https://www.courier.com/integrations/compare/apple-push-notification-vs-expo) |
| R8 | SMS fallback | A2P 10DLC Sole Proprietor brand = **$4.50 one-time**; a toll-free number skips registration entirely, free, no per-message surcharge | [Twilio](https://support.twilio.com/hc/en-us/articles/1260803965530-What-pricing-and-fees-are-associated-with-the-A2P-10DLC-service) |
| R9 | Silent failure | Do Not Disturb suppresses with no signal; a 201 from the push service says nothing about display | [Apple forums 770749](https://developer.apple.com/forums/thread/770749) |

## What changed

- **The grill's main fear was wrong.** R3 kills it — the 7-day storage wipe that hits Safari tabs does not apply to home-screen web apps. A subscription should survive a month of nobody opening the app
- **The SMS fallback was overstated as expensive** in the grill ("bureaucratic slog"). R8: $4.50, or free via toll-free. SMS is a cheap real fallback, which vindicates the `Notifier` port
- **R6 is the one that changes the build.** For an app whose entire product is the nag, "I sent it" is not good enough — and that is what makes observability *necessary* rather than decorative

## New §C lines this produced

- Re-subscribe + persist the push subscription on every app launch; server treats `410 Gone` as a dead subscription
- Request Storage API **persistent mode** (explicit eviction exemption, R4)
- Permission prompt fires from a button **after** the user has seen value — never on load (R1)
- Onboarding walks each roommate through Add to Home Screen. **The 3-step install is the single largest §G risk, not the code**
- Service worker pings the server on notification receipt — measured delivery rate, not assumed

## Links

- `SPEC.md` · `docs/Decisions.md`
