# Phase 0 Results (as of 2026-11-15)

**Execution constraint.** The agent ran on the production Linux host: no Xcode, no Android SDK, no attached devices. It could not run anything that needs a physical iPhone, the Apple portal, a Codemagic build or Firebase delivery. Those steps are listed as **NOT RUN** with exactly what is needed.

| Spike | Result | What was verified | Still open (needs device / approval) |
|---|---|---|---|
| **S1** FCM transport | **PARTIAL PASS (offline)** | `firebase_admin 7.1.0` has `APNSConfig.live_activity_token`. `Aps(custom_data=…)` flattens `event`, `attributes-type`, `attributes`, `content-state`, `stale-date`, `input-push-token`, `dismissal-date` into `aps` exactly as ActivityKit expects. Headers pass through. Start/update/end payloads are 541/389/323 B (limit 4096). | Real delivery on device (RUNBOOK 1b–1h). APNs key type in the Firebase console. **Firebase-admin version in the running container is unknown**: the Dockerfile installs it *unpinned*. Sandbox vs production APNs routing via FCM. |
| **S2** background token wake | **NOT RUN** | Apple docs/WWDC: observe `pushTokenUpdates`; the system *may* give the app runtime. Forum reports (anecdotal): delivery often fails after **force-quit**; the first push-start may wait for the user's "Allow". | RUNBOOK cases A–H on iOS 18 and 26 (and 17.x if available). |
| **S3** concurrency | **NOT RUN** | Apple documents **no numeric limit**. Scheduled activities count toward it. Errors: `targetMaximumExceeded` (app limit), `globalMaximumExceeded` (device-wide, other apps included). | RUNBOOK 3a–3e per device. |
| **S4** Codemagic signing | **PARTIAL (offline)** | Current App Store profile (`Plann_Appstore.mobileprovision`, expires 2027-02-26) has **no App Groups** entitlement. Live Activities need **no** entitlement; widgets sharing data need App Groups. Codemagic docs: the `bundle_identifier` shorthand auto-matches `co.plannapp.app.*` profiles and cannot be mixed with explicit `provisioning_profiles`. No `triggering:` exists in `codemagic.yaml`, so branch pushes don't auto-build. The existing iOS workflow **publishes to TestFlight**, so the spike workflow has no publishing. | Apple portal objects (owner approval), Xcode target creation (needs a Mac), a manual spike build. |
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
