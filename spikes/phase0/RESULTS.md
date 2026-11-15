# Phase 0 Results (as of 2026-11-15)

**Execution constraint.** The agent ran on the production Linux host: no Xcode, no Android SDK, no attached devices. It could not run anything that needs a physical iPhone, the Apple portal, a Codemagic build or Firebase delivery. Those steps are listed as **NOT RUN** with exactly what is needed.

| Spike | Result | What was verified | Still open (needs device / approval) |
|---|---|---|---|
| **S1** FCM transport | **PASS (device, iOS 26.0, TestFlight 6.4.90 (1005))** | Offline: `firebase_admin 7.1.0` `APNSConfig.live_activity_token` + `Aps(custom_data=…)` flatten correctly; payloads 541/389/323 B. **Device 2026-11-15:** push-to-start via FCM `live_activity_token` (production project `plann-54bd6`) appeared on the Lock Screen and Dynamic Island. A remote `update` (phase→processing, v2) applied instantly. A remote `end` (cancelled) showed the red bar and "İptal edildi". **iOS asks for Live Activity consent twice:** after the first local activity, and again on the first remote start ("…izin vermeyi sürdürmek istiyor musunuz? İzin Verme / Her Zaman İzin Ver"). This drives the production onboarding requirement (spec §5.6). **Bug found in the spike view:** after a terminal end, `Text(.timer)` counted up from 0. Production rule: terminal phases render no live timer (spec §6). | Pin `firebase-admin`; check the container version. Sandbox (development) APNs routing is untested: TestFlight uses production APNs. |
| **S2** background token wake | **PASS (device, iOS 26.0)** | **B, app backgrounded:** the start was sent 18:05:45Z, the activity was observed 18:05:47Z, and the per-activity `pushTokenUpdate` arrived **18:05:48Z** with `appState=2` (background). **C, app force-quit from the switcher:** the start was sent 18:08:29Z. iOS **cold-launched the app in the background** (`launch … appState=2 existing=2` at 18:08:31Z) and delivered the new activity's `pushTokenUpdate` at **18:08:31.9Z**, about 2–3 s after the send, without the user opening the app. That token was then used for a remote `update` (processing, v2) at 18:11:29 TR, which applied on the Lock Screen. **Contradicts** the anecdotal "fails after force-quit" forum reports, at least on iOS 26.0 with this device. | Only one device and OS, in a normal power state. Not tested: Low Power Mode, Background App Refresh off, no network at the moment of the start. **Design consequence:** the token upload must be done **natively** (URLSession from Swift, auth credential in the Keychain), not via the Capacitor JS bridge, because the WebView may not be loaded during a background launch. Reconciliation (spec §4.2) remains the safety net. |
| **S3** concurrency | **PASS (device: iPhone 11 / iOS 26.0, iPhone 16 Plus / iOS 26.6)** | **The limit is 5 non-ended activities per app**, identical on both devices. Locally requesting 12 gave 5 OK and 7 × `ActivityAuthorizationError.targetMaximumExceeded` (the per-app limit, not `globalMaximumExceeded`). **Stale activities still count.** **A push-to-start over the limit is silently dropped:** FCM accepted it, nothing appeared, nothing was logged in the app, and it was **not queued**, since it never appeared after a slot freed. **Ended-but-visible activities do not block starts:** an activity ended via push with `dismissal-date` = now + 15 min was **evicted by iOS** (`dismissed`) in the same instant a new push-to-start arrived (+2 s) (iPhone 11, 18:28:41 → 18:28:50Z). | The global limit (other apps' activities, e.g. the Clock timer) is not measured. The limit may differ on other iOS versions or devices: keep `observed_cap` adaptive, default **5**. |
| **S4** Codemagic signing | **PASS (device)** | The workflow `ios-spike-phase0` built a WidgetKit extension target `PlannSpikeWidgets` (`co.plannapp.app.widgets`, iOS 16.2). It was signed with a manually created App Store profile "PLANN Widgets AppStore" (expires 2027-02-26) and uploaded to TestFlight. `xcode-project use-profiles` assigned the widget profile correctly. The production App ID/profile was unchanged, and **App Groups were not needed** for Live Activities. Pitfalls hit: ASC API 403 "agreement missing"; a 409 duplicate profile name; `plistlib` failing on `security cms -D` output (use `plutil`). | App Groups (needed for data-sharing Home Screen widgets) still require modifying the production App ID and regenerating its profile. Do this at Phase 1 with owner approval. |
| **S5** Android FCM service | **PARTIAL PASS (code review)** | `@capacitor/push-notifications` 7.0.3 `MessagingService` is `public`, non-final, and forwards via static `PushNotificationsPlugin.sendRemoteMessage/onNewToken`. A subclass plus `tools:node="remove"` on the plugin service should keep JS delivery. | Emulator run. Deprioritised: Android Live Updates are out of the iOS MVP. |

## Exact platform/version limitations (verified from docs unless marked)

- **iOS 16.2** is the practical floor: `ActivityContent`, `staleDate`, `isStale` and `frequentPushesEnabled` are 16.2+. The earlier plan said 16.1; **changed to 16.2**. iOS 16.1 had only the deprecated `contentState` API.
- **iOS 17.2+:** push-to-start (`pushToStartToken`, `pushToStartTokenUpdates`). Below this there is no background start at all.
- **iOS 18+:** `input-push-token` and `input-push-channel` (broadcast). If an older device receives a start with `input-push-channel`, the activity does not start.
- **iOS 26+:** scheduled start `request(…, start: Date)` requires `alertConfiguration`, counts toward the limit, and starts even if the app is backgrounded. It can only be requested from the foreground (or via `LiveActivityIntent`).
- **Lifetime:** active ≤ 8 h; ≤ 12 h total on the Lock Screen. Combined attributes and content ≤ 4 KB.
- **Push budget:** priority 10 counts against a budget, priority 5 does not. Pushes arriving after an activity ends are ignored.
- **Background local start** throws `.visibility`.
- **FCM:** remote start needs iOS 17.2. FCM success means accepted by FCM/APNs, **not** visible on the device.
- **App target** stays at iOS 15.0. All ActivityKit code is behind `#available(iOS 16.2, *)`.

## Additional risks discovered in Phase 0

1. **`firebase-admin` is unpinned** in `backend/Dockerfile` and absent from `requirements.txt`. The production container's version is unknown, and a rebuild could silently change it. Check it with `docker exec <backend-container> pip show firebase-admin`; pin it in Phase 1.
2. **The repo working tree is on the production host**, which has uncommitted changes, including `backend/financial/*`. The 17-worker uvicorn runs in a container from this code. All Phase 1+ work must happen in an isolated worktree or a dev machine, with tests run off-host. `backend/venv` is stale (its `python3` points at the system interpreter, its packages are for 3.10), so it can't run the test suite as-is.
3. **The global Live Activity limit includes other apps.** A push-to-start can fail silently because of another app's activities. The server can't detect this until the device reconciles, so a residual "neither Live Activity nor notification" gap exists (decision D9).
4. **The Debug build's entitlements hard-code production APNs.** Device debugging of push needs a debug-only entitlements file.
5. **App Groups require modifying the production App ID and regenerating the production profile.** The next store build depends on refreshed Codemagic profiles; the existing check script already guards associated-domains and must be extended for app-groups.
6. **Business-wide owner scope (revised D2)** greatly increases concurrency on owner devices, which makes priority ordering and fallback volume central to the design (spec Revision 2 §R2).


## Device results → required spec/plan changes (2026-11-15)

1. **Default cap 5.** The server keeps at most **5 non-ended** activities per device (per-app limit, both test devices). `observed_cap` stays adaptive but starts at 5 instead of "unknown". Stale activities count; ended ones do not, because iOS evicts them.
2. **Never push-to-start over the cap.** Over-limit starts vanish without any device or app signal, and are not queued. Reconciliation cannot detect them in the background, so the server-side count is authoritative. Appointments beyond the cap get the existing standard notification (fallback), selected by the D2 priority order (ongoing > imminent > later).
3. **Swap = end, then start.** To promote a higher-priority appointment when the device is at the cap, send `end` (with the normal `dismissal-date`) to the lowest-priority activity and then the push-to-start. iOS evicts the ended card for the new one. Immediate dismissal is not required.
4. **Native token upload.** Per-activity tokens arrive ~2–3 s after a start, **even when the app was force-quit** (iOS launches it in the background). The upload must happen in Swift (URLSession, auth credential in the Keychain), independent of the WebView or Capacitor bridge.
5. **Consent prompt timing varies.** iPhone 11 / 26.0 showed the second prompt on the first remote start. iPhone 16 Plus / 26.6 showed it later, during a local start (`appState=1` at 18:25:42Z). Onboarding copy must say "if iOS asks… choose Her Zaman İzin Ver", not "you will now be asked". The Settings banner remains the safety net.
6. **Terminal phases render no live timer** (spike bug: `.timer` counted up after cancel), as already in spec §6.
7. **The compact Dynamic Island leading icon** must be the PLANN mark, not the spike's generic clock SF Symbol.
8. **A push-to-start whose `stale-date` is already in the past is silently dropped** (device, 2026-11-15, iOS 26.0 and 26.6, build 1007). A `completed` start with `stale-date` = end (1 h ago) never appeared on either phone, and the app logged nothing. The same start with `stale-date` 35 min in the future appeared immediately. **Planner rule:** never emit `start` unless the computed `stale-date` is more than ~60 s in the future (plan Task 6 `test_never_start_with_past_stale_date`; Task 3 payload builder asserts it).
9. **Push-to-start is throttled per device** (observed 2026-11-15/16 on iPhone 11 / iOS 26.0 and iPhone 16 Plus / iOS 26.6).
   - After about **13 successful priority-10 starts within ~1 hour** per device, every further start was silently dropped. FCM accepted each one, but the device had no activity and nothing appeared in the app log.
   - This included a control `completed` card whose view has no progress bar, which rules out a rendering failure in build 1009.
   - The budget size and reset window are **not documented by Apple** and were not measured.

   **Design consequences:**
   - **(a)** The server keeps a per-device start budget. Default: at most ~8 starts per rolling hour; above that it falls back to a notification. It never retries a start in a tight loop.
   - **(b)** Only appointments inside the lead window are started, and only up to the cap (rule 1a). Normal salon load (≤ 1 start per appointment, spread over the day) stays far below the observed burst.
   - **(c)** Content-only updates use priority 5, which is exempt from the budget per Apple; priority 10 is kept for start, the PROCESSING transition and end.
   - **(d)** Pilot QA must not burst-test on the owner's phone.
   - **Open:** measure the reset time (retry a single start on 2026-11-16).
10. **The throttle is per device, not per app** (fresh iPhone 11 / iOS 26.1, build 1009, 00:32 TR). While the two throttled phones still dropped every start, a third device accepted starts immediately. One user's busy phone cannot starve another user's phone.
11. **Lock Screen ordering** (same device, build 1009):
    - Without `relevance-score`, iOS stacks cards in **start order, oldest on top** (Mehmet then Ayşe).
    - A later start with `relevance-score: 100` was placed **on top** (Can B. above both), so **relevance-score controls Lock Screen order**.
    - The server should send relevance on start and on every phase change: processing 100, upcoming `50 − minutes_to_start/10` (floor 1), terminal 0.
12. **Build 1009 visual renders on device:**
    - processing: 6 pt strip, green-dot pill, "Bitmesine kalan" countdown, `scaleEffect`-thickened green bar;
    - upcoming: "Başlamasına kalan" + amber bar.

    The earlier "missing" upcoming/processing cards on the two main phones were caused by the throttle (item 9), not by the view.
13. **Slot feasibility (in-place content switch)** (fresh iPhone 11 / iOS 26.1, build 1009, 00:43–00:44 TR):
    - A **priority-5 `update`** rewrote an existing activity to a *different appointment* (Can B. processing → Selin D. upcoming) and applied **immediately**, with no banner and no sound.
    - A second priority-5 update switched it to another appointment in `processing` with an `alert`. It also applied immediately, and the alert **did** produce a banner and sound.
    - So one long-lived activity can show successive appointments without spending push-to-start budget, and the server decides exactly which transitions make noise.
14. **`relevance-score` is not sticky.** After an update without `relevance-score`, the card dropped to the **bottom** of the stack. The score must be sent on **every** update, not just on start.
15. **Offline delivery** (same device, 00:46 TR): a priority-5 update sent while the phone had **no internet** was delivered **when connectivity returned**. The card switched to the new appointment (Ece T.) and took its relevance position. While offline, the card kept rendering from local time (timers, stale fallbacks).
16. **The relevance rule produces the intended order with silent updates** (00:48 TR):
    - Silent priority-5 updates set processing Mehmet to 100 and upcoming Ece to 48 (`50 − 20 min/10`).
    - The Lock Screen order became Mehmet (processing) → Ece → Ayşe (no score).
    - There was no sound or banner, confirming that **ordering and content can be maintained silently**.
17. **Priority-5 coalescing across activities** (fresh iPhone 11 / iOS 26.1, 00:50–00:53 TR).
    - Three priority-5 updates with alerts, sent within one second to **three different activities** while the phone was idle: **only the last one was applied** (version check in the app snapshot), and there was a single sound.
    - Re-sending the two lost updates at **priority 10** (silent) applied both immediately, in the correct order.
    - Interpretation, consistent with APNs store-and-forward: while the device defers low-priority pushes, only the **most recent** Live Activity push per app topic survives.
    - **Design consequence:**
      - multiple activities per device cannot rely on priority-5 updates landing;
      - **a single activity per device turns "latest wins" into the desired semantics**, because only the current state matters;
      - when several updates must land together, use priority 10, which is budgeted, so do it sparingly.
18. **Start budget recovery** (iPhone 16 Plus / iOS 26.6): the last dropped start was at 00:28 TR. A single start at **01:03 TR (~35 min later) appeared**, so the push-to-start budget refills on the order of tens of minutes, not a daily reset. The exact refill rate is unmeasured.
19. **The priority-10 *update* budget is generous** (iPhone 16 Plus / iOS 26.6, `frequent_pushes_enabled=false`, 01:07–01:11 TR).
    - **40 silent priority-10 updates**, about one every 6 s, to one existing activity: **all 40 applied** (the card showed "Sayaç 40").
    - The update budget is therefore far larger than the push-to-start burst limit (~13/h).
    - A 5-staff owner with 3 cards needs ~40 priority-10 switches per *day*, spread out, which is well inside the observed tolerance.
    - **Design consequence:** a multi-card model is viable if card *switches* go at priority 10, with priority 5 only for cosmetic changes. Starts stay rare (1–2 per card per day).
20. **Ordering via relevance on start, iOS 26.0** (first iPhone 11, 01:15 TR, ~47 min after its last throttled start):
    - Three alerted push-to-starts were sent in **reverse** priority order, ~4 s apart: upcoming 46, then upcoming 48, then processing 100.
    - All three appeared, with **three sounds**, and the Lock Screen order was **processing (100) → upcoming 48 → upcoming 46**, above the older terminal cards.
    - This also confirms the budget refilled on this device.
    - **Rule for the slot model:** when several cards must alert at the same moment, send at most **one** alerted push. The others go silent, because each alerted push sounds separately.
21. **Slot-model day transition, end to end** (first iPhone 11 / iOS 26.0, 01:17 TR). Three existing cards were switched **in the same second** at **priority 10**, with relevance kept and an alert on **one** card only:
    - top → Zehra B. processing (100, alert);
    - middle → Murat K. upcoming (49);
    - bottom → Selin D. upcoming (46).

    **All three switched, a single sound played, and the order was correct.** This validates the D12 transition recipe: simultaneous switches go at priority 10, with at most one alerted push per batch and relevance on every push.
22. **Multi-card priority-10 stress** (first iPhone 11 / iOS 26.0, 01:18–01:20 TR, `frequent_pushes_enabled=false`).
    - 30 rounds, each sending **simultaneous silent priority-10 updates to 3 cards**: **90 updates in ~2 min**.
    - **All three cards ended at 30**, with no sound and the order kept.
    - Together with item 19 (40 updates to one card), this shows the update budget is not a practical constraint for the slot model; a real salon day needs ~1–2 orders of magnitude fewer.
    - The binding limit is **push-to-start** (~13/h/device, refilling within ~35 min), which the slot model avoids by starting each card once per day.
