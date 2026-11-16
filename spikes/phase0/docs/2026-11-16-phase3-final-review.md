## Final whole-branch review: Live Activities Phase 3 iOS (473e0095..90bf3825)

I read the whole range (40 files) against the plan, the contract doc, `backend/live_activity/endpoints.py`, `registry.py`, `sweeper.py` and `eligibility.py`, and the ledger. I also diffed the widget UI against spike commit 452900a9. I read the code for the real logout path (`AuthContext.logout`, the axios 401 interceptor) and for the Capgo config.

**Checks I re-ran myself (worktree clean afterwards):**
- Docker `swift test`: 44 tests, 0 failures.
- jest `src/components/LiveActivity` + `src/native`: 3 suites, 30/30 passed. The controller's 35 also included `src/lib`.
- `add_live_activity_targets.py --check`: "CHECK OK", exit 0.
- `codemagic.yaml` loads with 3 workflows; both Info.plists load.

**Not re-run:** the backend suite. Neither available venv has pytest. I read the 5 new GET-preferences tests and the endpoint instead.

### Strengths
- The core / thin-adapter split is good. Every decision (report, end instructions, local-start attributes, retry policy, token re-post) is Linux-tested pure Swift. The coordinator only adapts ActivityKit.
- The contract matches field by field: register, token, reconcile (explicit nulls) and the response with missing keys decoding as empty. The `start_locally` item shape matches `sweeper.start_locally`, and `_slot_attributes` emits string values.
- Security is clean:
  - The JWT only passes through register/unregister and is never stored.
  - Secret calls carry `X-Plann-Device-Secret` and no `Authorization`. The URLSession is ephemeral with no cookies and no cache.
  - Logs carry only the error code or error type. No tokens or secrets are logged.
  - The device secret is in the app Keychain, with no access group.
- After a reinstall, the stale Keychain secret is harmless. `apiBaseUrl` lives in UserDefaults, which is wiped on uninstall, so every call fails with `noBaseUrl` until the next register.
- Account switch is robust even if the logout unregister is lost:
  - the server's owner change issues a new secret and ends the old slots;
  - the post-register `complete` reconcile then gets `end:[slot]` back for the old cards (`_sort_reports`, `is_tracked` and not usable).
- Unregister FIFO, the `unregistersInFlight` gate, token re-post and the lost-secret recovery are well reasoned.
- Owner decisions are honoured:
  - consent copy (tr) is verbatim;
  - settings labels are verbatim;
  - scope rules (owner/manager/staff, forced-all) are server-owned through the new GET;
  - slots 1–5 with default 4 and start alert default off come from `eligibility.py`;
  - the widget is a faithful port, with no `scaleEffect` or strikethrough and no timer in terminal phases.
- JS is a no-op on web, Android and old native builds. App.js and Settings.js changes are additive (+12 / +3 lines).

### Issues

#### Critical (Must Fix)
None in the code.

#### Important (Should Fix)

1. **The beta JS can be replaced by the production OTA bundle.**
   - Where: `codemagic.yaml` 258–499 (beta workflow) and `frontend/capacitor.config.json:29-31`.
   - What: `CapacitorUpdater` runs with `autoUpdate: "atInstall"` on `defaultChannel: "production"`. A non-boolean value reads as truthy. On first launch the TestFlight beta can download the production bundle from main, which has no hook, no consent sheet and no settings. The device would then register nothing, and QA would test the wrong JS.
   - Whether Capgo's "disable auto-update under native" setting blocks this (native 6.4.91 is above bundle 6.4.38) depends on the Capgo channel configuration, which I could not check.
   - Fix: in the beta workflow, after `npx cap sync ios`, set `plugins.CapacitorUpdater.autoUpdate=false` in `frontend/ios/App/App/capacitor.config.json` (python/plutil step). Alternatively, the owner confirms the Capgo channel setting before running the beta.

2. **Logout unregister depends on a passive effect racing a full-page navigation.**
   - Where: `frontend/src/context/AuthContext.js:238-281` and `frontend/src/native/useLiveActivities.js:79-83`.
   - What: `logout()` calls `setToken(null)` and then immediately sets `window.location.href`. The native `unregister` is only sent from the hook's `useEffect` after React re-renders. If the page unloads first:
     - the cards stay on the lock screen;
     - the secret stays;
     - the server keeps sweeping and push-starting the logged-out user's appointments.
   - The "unregister on logout" test only flips the hook's prop, so the real path is untested.
   - Fix: call `unregister({ jwt: currentToken })` from `native/liveActivities` directly in `logout()` before clearing state and navigating. It is a no-op off-iOS. The native dispatch happens within the current task's microtasks, and the native side continues after the reload. Add a test on `AuthContext.logout`.

3. **The first registration on a fresh install very likely sends `fcm_token: null`, and nothing re-sends it.**
   - Where: `LiveActivityCoordinator.swift:293-305` and `useLiveActivities.js:92`.
   - What:
     - The hook always passes `fcmToken: undefined`.
     - On a fresh install, `Messaging.messaging().fcmToken` is nil until JS push setup calls `registerForRemoteNotifications` (App.js ~769-803, which takes up to about 16 s).
     - `_sweep_device` returns early without an `fcm_token` (sweeper.py:438), so the device gets no cards until the WebView reloads.
     - Reconcile never carries the FCM token. FCM token rotation is also never re-sent while the app stays alive.
   - Upgrade installs, like the QA phones, have a cached token, so QA will likely not see this.
   - Fix:
     - The plugin returns `hasFcmToken` from `register`.
     - The hook calls `register` again on `visible` while that is false. The server upsert is idempotent and issues no new secret.
     - Optionally, AppDelegate `messaging(_:didReceiveRegistrationToken:)` updates `lastFcmToken` in the coordinator.

4. **The Keychain class allows backup migration to a second device.**
   - Where: `KeychainSecretStore.swift:151`.
   - What: `kSecAttrAccessibleAfterFirstUnlock` items travel in encrypted and iCloud backups. A new iPad set up from the iPhone's backup ends up with the same `device_id` and secret. The app target is `TARGETED_DEVICE_FAMILY 1,2`, and the plugin reports `supported` on iPadOS 16.2+.
   - Its register overwrites the iPhone row's `fcm_token` and `push_to_start_token` (null on iPad) and sets `activities_enabled:false`. Its `complete` reports then claim zero slots. The two devices ping-pong, and the iPhone's cards stop updating.
   - Fix: `kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly`. This is an owner decision because the plan names the other class. It is a one-constant change while no production items exist.

#### Minor (Nice to Have)

1. **Slot select shown while scope is "own".**
   - Where: `LiveActivitySettings.js:95`.
   - When scope is `own` the select shows 1. Picking another value saves it and shows "Kaydedildi", then snaps back to 1, because `slot_count()` forces 1 for `own`.
   - Fix: render the select only when `prefs.scope === 'all'`.
2. **`subOf()` uses `atob` on a base64url JWT segment.**
   - Where: `useLiveActivities.js:45-51`.
   - It throws on `-` or `_`. In a synthetic test it failed on 6 of 100 payloads with Turkish names. The consent sheet then never auto-opens for that login (`sub` is null).
   - Fix: replace `-`→`+` and `_`→`/` before `atob`. The same pattern already exists elsewhere in the code and is out of scope.
3. **Register can overwrite the server's push-to-start token with null.**
   - Where: `LiveActivityCoordinator.swift:64-66, 304`.
   - On a cold launch, if `latestPushToStartToken` is still nil, the server's stored token is overwritten with null. On 17.2+, a following reconcile then gets `start_locally` claims that the device ignores. Slots stay stuck in `start_sent` until the lost-start timeout.
   - Fix: re-read `PlannActivity.pushToStartToken` in `performRegister` when nil, and/or persist the last known value.
4. **Background reconcile can claim local starts the device ignores.**
   - Where: `LiveActivityCoordinator.swift:231-233`.
   - A background reconcile on 16.2–17.1 can claim `start_locally` slots that the device ignores. The proposed `foreground` field is not implemented. This is rare because background code seldom runs on those devices.
5. **Live Activity UI is offered on iPad.**
   - Where: `PlannLiveActivityPlugin.swift:39-47`.
   - iPad reports `supported:true`, so it gets the consent sheet and a "disabled in iOS Settings" banner for a feature iPad does not have.
   - Fix: `supported = userInterfaceIdiom == .phone`.
6. **Disabled banner can be stale.**
   - Where: `LiveActivitySettings.js:22-39`.
   - `getStatus` is read once on mount, so the banner is stale after returning from iOS Settings until Settings remounts.
7. **Consent sheet uses fixed colours.**
   - Where: `LiveActivityConsentSheet.js:206-216`.
   - The fixed zinc classes sit on a theme-aware `bg-background`. Use `text-muted-foreground`, `border-input` and `bg-primary text-primary-foreground`. See the triage below for why this can wait.

### Ledger triage
| Line | Item | Verdict | Reason |
|---|---|---|---|
| T1 | fixture path via `#filePath` | OK-TO-DEFER | It fails loudly, never silently. |
| T2 | `try?` swallows a malformed 2xx register body | OK-TO-DEFER | It becomes `newSecret=false`, and `registerEnsuringSecret` recovers. |
| T2 | `apiBaseUrl` persisted before register succeeds | OK-TO-DEFER | The value is the app's own config, and the next register overwrites it. |
| T2 | device id not percent-encoded in DELETE | OK-TO-DEFER | It is always a `UUID().uuidString`. |
| T2 | `LocalStart.attributes` strict `[String:String]` | OK-TO-DEFER | The backend always emits strings (`_slot_attributes`). |
| T2 | not Sendable | OK-TO-DEFER | Swift 5 mode. Adding `Sendable` to `PlannPhase`/`PlannContentState` is an optional zero-cost hedge (see compile list). |
| Note | production workflow does not sync App/PlannWidgets versions | **MUST-FIX-BEFORE-MERGE** | A one-sided pbxproj bump makes the extension's CFBundleShortVersionString/CFBundleVersion differ from the app's: App Store validation warnings at least, a rejected upload at worst. Add a sync step to `ios-capacitor-workflow` that copies App's versions to all targets (same `sed` as the beta step). |
| T3 | `CODE_SIGN_IDENTITY` head check / duplicate key | OK-TO-DEFER | The extension settings have no such key; a duplicate would be harmless. |
| T3 | version bump together | **MUST-FIX-BEFORE-MERGE** | Same as the Note above. |
| T3 | widget-profile block duplicated in 2 workflows | OK-TO-DEFER | Maintenance only. |
| T3 | production calls the ASC API every run | OK-TO-DEFER | Read-only `profiles list`. It is non-fatal unless no valid profile exists (after 2027-02-26). |
| T4 | minimal Dynamic Island draws the "P" ring for `.empty` (`AppointmentLiveActivity.swift:136-138`) | OK-TO-DEFER | The removed stub is dismissed at once, and the ring is a brand mark that shows no data. One-line fix: `if l != .empty`. |
| T4 | un-reindented `if` bodies | OK-TO-DEFER | Style only. |
| T5 | Keychain read error overwrites the device id | OK-TO-DEFER | Rare: the write also fails while locked, and register only runs in the foreground. |
| T5 | ThisDeviceOnly keychain class | **MUST-FIX-BEFORE-MERGE** (owner decision, ideally before beta) | Backup restore to a second device clones `device_id` and secret; see Important #4. |
| T5 | server-side token dedupe across device rows | OK-TO-DEFER | Backend follow-up. |
| T5 | DECODE error code | OK-TO-DEFER | Reported as NETWORK; cosmetic. |
| T5 | `apiBaseUrl` https validation | OK-TO-DEFER | JS that controls the URL already holds the stronger JWT. |
| T5 | `beginBackgroundTask` closure fallback | OK-TO-DEFER | Only needed if the first compile fails. |
| T5 | `.pending` via `String(describing:)` | OK-TO-DEFER | Works on any SDK because of `default:`. |
| T5 | doubled foreground reconcile | OK-TO-DEFER | Serialized and idempotent. |
| T5b | token post not guarded during unregister | OK-TO-DEFER | The DELETE removes the rows afterwards. |
| T5b | `postedTokens` may re-add a stale entry | OK-TO-DEFER | Only causes an extra or skipped re-post. |
| T5b | possible duplicate token post | OK-TO-DEFER | The endpoint is idempotent. |
| T6 | session ref stays set after `supported:false` | OK-TO-DEFER | The calls are no-ops below 16.2. |
| T6 | org flag true→false does not unregister | OK-TO-DEFER | `_end_disabled_orgs` ends the cards server-side. |
| T6 | vacuous assertion at test :347 | OK-TO-DEFER | Test hygiene. |
| T6 | no account-switch / same-sub refresh tests | OK-TO-DEFER | Superseded: the needed test is on `AuthContext.logout` (Important #2). |
| T7 | admin on scope own sees slot select = 1 | **MUST-FIX-BEFORE-MERGE** | It shows a "saved" toast for a value with no effect; one-line fix (Minor #1). |
| T7 | forced-all/privileged computed inline in GET, not shared with PUT | OK-TO-DEFER | A forced-all admin who PUTs scope writes a value the effective scope ignores; harmless. |
| T7 | consent sheet fixed zinc/white classes | OK-TO-DEFER | Dark mode cannot be reached: `toggleTheme` is never called anywhere, and `Settings.js`, `dialog.jsx`, `switch.jsx` and `radio-group.jsx` have 0 `dark:` classes. The sheet matches the surrounding light-only Settings. Token-class swap recommended (Minor #7). |

### Codemagic first-compile risk list
(Xcode 26, `SWIFT_VERSION = 5.0`, no strict-concurrency setting. App target 15.0 with ActivityKit weak-linked; extension 16.2. Build settings are identical to the spike that already built on Codemagic.)

1. **`PlannWidgets/PlannWidgetsBundle.swift:7-9`, `if #available(iOS 16.2, *)` inside a `WidgetBundle` body.** Highest uncertainty. It relies on `WidgetBundleBuilder` limited-availability support, and the spike had no `if`. The check is redundant at a 16.2 deployment target. Fix: drop the `if` and list `AppointmentLiveActivity()` directly.
2. **`LiveActivityCoordinator.swift:356`, `beginBackgroundTask` expiration closure calling the `@MainActor` method `end()`.** In recent SDKs the handler is main-actor; with an older signature this could raise an isolation diagnostic. Fix if needed: `Task { @MainActor in self?.end() }`, or keep the id in a local and call `UIApplication.shared.endBackgroundTask` directly.
3. **`ContentModel.swift:3,12`: `public` `PlannPhase`/`PlannContentState` are not implicitly Sendable** (public types get no inference). This would only matter if the Xcode 26 ActivityKit SDK requires `ContentState: Sendable`. Even then it is warning-level in Swift 5 mode. Zero-cost hedge: add `, Sendable` to both; this also compiles on Linux.
4. **`public` declarations in non-module targets:** no issue. `public` is legal inside the App and PlannWidgets modules. `ContentModel.swift` and `PlannAppointmentAttributes.swift` compile into two different modules, so there are no duplicate symbols. I found no name collisions between core global functions (`pushTokenHex`, `completeReport`, `endInstructions`, `localStartAttributes`, `tokensToRepost`, `pluginErrorCode`, ...) and members of the coordinator or plugin.
5. **`@MainActor` and `Task` patterns:** `@MainActor` class, `static let shared`, the task-chaining FIFOs and the `Task { @MainActor in … }` wrappers in the plugin follow the spike's proven pattern. AppDelegate (a UIResponder) is main-actor, so `start()` and `reconcileIfRegistered()` calls are fine.
6. **Availability:** every ActivityKit symbol is inside `@available(iOS 16.2, *)` scopes. `pushToStartToken`/`pushToStartTokenUpdates` are under `#available(iOS 17.2, *)`. `guard #unavailable(iOS 17.2)` is valid. `session.data(for:)` needs iOS 15.0, which matches the app target.
7. **Capacitor 7:** `CAPBridgedPlugin` (identifier/jsName/pluginMethods) together with a `CAP_PLUGIN` .m mirrors the production `FCMTokenPlugin`. The .m method list (register, reconcile, unregister, getStatus, openSettings) equals the Swift list and the `@objc func`s. `register` as a selector is proven by `@capacitor/push-notifications`. `call.getString`, `resolve`, `reject(msg, code)` and `registerPluginInstance` are Capacitor 7 APIs.
8. **Runtime check, not compile:** confirm on the first device run that `Capacitor.isPluginAvailable('PlannLiveActivity')` is true for an instance-registered plugin. If it is false, everything no-ops silently. Production code never relied on `isPluginAvailable` for `FCMTokenPlugin`.

### Declined to judge
- Phase 1 backend sweeper, planner and owner-change logic: merged and reviewed in Phase 1. I used it only to check the client.
- Widgets and quick-add (Phase 2): out of scope.
- The 401-interceptor logout (full reload, no unregister) keeps the LA registration. This matches the existing push policy comment in `api/api.js` ("Token süresi dolunca cihaz kaydı korunur").
- A user who denies notification permission never gets an FCM token, so Live Activities can never arrive. This is a product-design question.
- Live Activity copy is Turkish-only. The spec fixes it.
- Native `<select>` instead of `ui/select`. It is accessible, adds no dependency, and CLAUDE.md prefers native.
- The existing `print("📱 FCM Token…")` in AppDelegate: not part of this branch.
- Settings' `bg-white` cards without dark mode: an existing pattern.
- Consent sheet stacking with other startup modals or the iOS push prompt: the spec says nothing on this; it needs device QA.
- Android: out of scope for the iOS MVP.
- `shouldApply` is unused: the app has no path that applies a local content update, so the version rule is vacuous on the client.

### Assessment
**Ready for owner beta build?** With fixes. The one beta blocker is Important #1: disable Capgo auto-update in the beta workflow, or the owner confirms the channel blocks it. Strongly recommended in the same pass because they are cheap:
- compile hedge #1 (drop `if #available` in the WidgetBundle);
- compile hedge #3 (add `Sendable`);
- Important #2 (deterministic logout unregister), so the "logout → cards gone" QA result is not timing-dependent.

**Ready to merge after device QA?** With fixes:
- Important #2, #3 and #4 (#4 is the owner's Keychain-class decision);
- the four MUST-FIX-BEFORE-MERGE triage rows. Three distinct fixes: the production version-sync step, the slot select shown only for scope "all", and the ThisDeviceOnly Keychain class (same as Important #4).

**Reasoning:** The native and contract work is solid and well tested where Linux allows. The remaining risks are integration gaps the unit tests can't see: OTA replacing the beta JS, logout racing the page navigation, a missing FCM token on fresh installs, and backup-cloned device ids. All have small, local fixes.

Files referenced, all under `/tmp/claude-0/-var-www-player5moduleryapi/53f81d0e-4c9d-49e9-b05f-cc6c0967bae9/scratchpad/la-ios/`:
- `codemagic.yaml`
- `frontend/capacitor.config.json`
- `frontend/src/context/AuthContext.js`
- `frontend/src/native/useLiveActivities.js`
- `frontend/src/components/LiveActivitySettings.js`
- `frontend/src/components/LiveActivityConsentSheet.js`
- `frontend/ios/App/App/LiveActivityCoordinator.swift`
- `frontend/ios/App/App/KeychainSecretStore.swift`
- `frontend/ios/App/App/PlannLiveActivityPlugin.swift`
- `frontend/ios/App/PlannWidgets/PlannWidgetsBundle.swift`
- `frontend/ios/App/PlannWidgets/AppointmentLiveActivity.swift`
- `frontend/ios/LiveActivityCore/Sources/LiveActivityCore/ContentModel.swift`