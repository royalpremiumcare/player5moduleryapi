# Final-review fix wave: Live Activities Phase 3 iOS

Branch `feature/live-activities-ios`. Started at 90bf3825; HEAD is now d00e0f05. I worked only in the scratchpad worktree. Nothing was pushed, merged or deployed, and Codemagic was not triggered.

Skills I invoked, in order:
1. receiving-code-review
2. test-driven-development
3. modern-web-guidance (searched; retrieved `detect-initial-visibility-state` and `color`)
4. systematic-debugging (for one unexpected red; see G)
5. verification-before-completion

## Status: DONE_WITH_CONCERNS

All 13 items (A–M) are done. The concerns are listed at the end. The main one: the App-target Swift files can't be compiled on Linux, so the first Codemagic build is still the compile check for them.

## Commits (90bf3825..HEAD)

| Commit | Summary |
|---|---|
| 77239734 | fix(live-activity-core): persisted push-to-start token fallback; Sendable content types |
| 20635c81 | fix(ios): register keeps push-to-start token, reports hasFcmToken; iPhone only |
| 70bb9a19 | fix(ios): this-device-only Keychain class; widget bundle and island hedges |
| 75491b5b | fix(app): dedupe Live Activity unregister, re-register until FCM token sent, base64url sub |
| 2c5b783d | fix(app): logout unregisters Live Activities before clearing the session |
| 6cb6e78f | fix(app): Live Activity settings: slot select only for scope all; refresh status on return |
| a14f62b8 | fix(app): consent sheet uses theme colour tokens |
| d00e0f05 | ci(ios): beta disables Capgo auto-update; production syncs widget versions |

## Per item

### A. Beta: Capgo auto-update off (Important #1, Ruling F2)

**Change:** in `codemagic.yaml:320`, the `ios-live-activities-beta` workflow has a new step "Beta'da Capgo OTA kapalı". It runs right after `npx cap sync ios`.
- A python3 json edit sets `plugins.CapacitorUpdater.autoUpdate=false` in `frontend/ios/App/App/capacitor.config.json`, the generated copy, which is not tracked.
- The step exits non-zero with a message if `plugins.CapacitorUpdater` or `autoUpdate` is missing.
- It prints the resulting `CapacitorUpdater` block.
- `frontend/capacitor.config.json` and the production workflow are unchanged (`git diff --quiet` confirms).

**Test:** I extracted the step from the parsed YAML and ran it on Linux against a copy of `frontend/capacitor.config.json`.
- The only change is `"autoUpdate": "atInstall"` → `false`.
- A copy without `plugins.CapacitorUpdater` → exit 1 with "plugins.CapacitorUpdater bulunamadı".
- A missing file → exit 1.

### B. Production: sync App versions to all targets (MUST-FIX)

**Change:** in `codemagic.yaml:47`, the `ios-capacitor-workflow` has a new step "Sürüm numaralarını tüm hedeflere eşitle", placed after pod install and before the widget-profile and build steps.
- A python3 helper reads `MARKETING_VERSION` and `CURRENT_PROJECT_VERSION` from the App target's Release `XCBuildConfiguration` (the block with `INFOPLIST_FILE = App/Info.plist;`).
- It writes them to a mktemp file, which is read with `read -r`. I used no heredoc inside `$(...)` because of bash 3.2 parsing quirks.
- The same `sed -i '' -E` lines as the beta step then apply the values to every target.
- If the App values are not found, it exits 1 (`set -e`).
- The step is additive only.

**Test:** run on Linux with a BSD `sed -i ''` shim.
- **Already equal (current pbxproj):** prints "App sürümü: 6.4.2 (70)" and `cmp` shows the file unchanged, so the step is a no-op.
- **App bumped to 6.5.0/71 with PlannWidgets left at 6.4.2/70:** afterwards all 4 configs read 6.5.0 / 71.
- **App block missing:** exit 1 with the message, and the file is untouched.

### C. Logout unregisters Live Activities deterministically (Important #2)

**Changes:**
- `frontend/src/context/AuthContext.js:6,245-252`: `logout()` reads the current JWT, then calls `unregister({ jwt: currentToken })` from `native/liveActivities`. This happens before the push-unsubscribe await, before state is cleared and before navigation.
  - It is not awaited and is wrapped in try.
  - It is a no-op off iOS, because the wrapper resolves null.
  - It is skipped when no token is stored.
- `frontend/src/native/liveActivities.js:31-52`: dedupe at module level.
  - `unregister` returns the previous promise for the same JWT, whether in flight or finished, so logout plus the hook's token-cleared effect produce one native call.
  - `register` re-arms it.
  - A null result (failed or unsupported) clears the entry so a retry is possible.

**Tests:**
- New `frontend/src/context/AuthContext.test.js`. It uses react-dom/client + act. axios, api, posthog, i18n and `native/liveActivities` are mocked by factory, and window.location is stubbed. There are 3 tests:
  - The order is la-unregister → push-unsubscribe → navigate. The JWT is still in localStorage when unregister is sent, and it is cleared afterwards.
  - Logout completes and navigates even though the native promise never resolves.
  - There is no unregister without a stored token.
- New in `useLiveActivities.test.js`:
  - same-JWT dedupe (plugin called once);
  - logout call + hook effect → one native unregister;
  - register re-arms;
  - a failed unregister can be retried.

**RED:** before the change, the AuthContext order test failed with "Expected number of calls: 1, Received: 0", and the dedupe tests failed.

**Note:** no craco or jest config was changed. CRA's jest does not transform axios's ESM, so the test mocks `axios` with a factory.

### D. Fresh install sends `fcm_token: null` (Important #3)

I inspected AppDelegate first. It already implements `MessagingDelegate.messaging(_:didReceiveRegistrationToken:)`, which only prints the token. There is no JWT-less register path, so the native side only stores the token.

**Changes:**
- `LiveActivityCoordinator.swift`:
  - `:111` `updateFcmToken(_:)` stores the newest FCM token, which the next register uses.
  - `:308-348` `register` now returns `hasFcmToken`. `performRegister` returns `RegisterOutcome(newSecret:hasFcmToken: fcm != nil)`.
- `PlannLiveActivityPlugin.swift:97-98`: `register` resolves `hasFcmToken`.
- `AppDelegate.swift:31-35`: after the existing print, it runs `Task { @MainActor in LiveActivityCoordinator.shared.updateFcmToken(fcmToken) }`, gated on iOS 16.2. The existing FCM flow is untouched.
- `useLiveActivities.js:46-91`: the session holds `needsFcm`, which is set from `result.hasFcmToken === false`.
  - On visibilitychange → visible, it re-calls `register` before the reconcile. The server upsert is idempotent.
  - It keeps re-registering while the result is null or still has `hasFcmToken:false`.
  - Older native builds don't return the field (undefined), which means no re-register.

**Tests:**
- "re-registers on visible while the server has no FCM token": register is called a second time, then not a third once `hasFcmToken` is true.
- "does not re-register on visible once the FCM token was sent".
- RED before: register count stayed 1.

### E. Keychain class: ThisDeviceOnly (Important #4, Ruling F1)

`KeychainSecretStore.swift:29` now uses `kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly`, and the doc comment at `:5-7` says why. Items written with the old class are migrated on the next write, because `SecItemUpdate` carries the attribute.

I had no test for this: it is Keychain-only and can't be tested on Linux.

### F. Slot select only for scope 'all' (Minor #1, MUST-FIX)

**Change:** `LiveActivitySettings.js:103` is now `prefs.can_choose_slots && prefs.scope === 'all'`.

**Tests:**
- "slot select hidden while scope is own (the server forces 1)". RED before: the select was rendered.
- "slot select appears once scope is switched to all".

### G. `subOf()` decodes base64url (Minor #2)

**Change:** `useLiveActivities.js:10-25`.
- It maps `-`→`+` and `_`→`/` and pads before `atob`.
- It then decodes the bytes as UTF-8 with `TextDecoder`. This is Baseline and present in WKWebView. Where `TextDecoder` is missing, the binary string is kept, which is still exact for ASCII.

**Tests:**
- A payload `{sub:'ayse', full_name:'Ömer Ağaoğlu'}` whose segment contains `_` (the test asserts that `-` or `_` is present) gives `'ayse'`.
- A non-ASCII sub `'ayşe'` decodes correctly. That test sets `TextDecoder` from node `util` because jsdom 16 lacks it.
- Garbage → null.

**Debugging note:** my first version of the test used `TextEncoder`, which jsdom 16 lacks. So its "red" was for the wrong reason. I rewrote the helper with `Buffer.toString('base64url')`. Against the old implementation it then went RED for the right reasons: `null` for the `_` payload, and `"ayÅe"` for the UTF-8 sub. After the fix both pass.

### H. Register never nulls a known push-to-start token (Minor #3)

**Core (Linux-tested):**
- `CoordinatorLogic.swift:62` `pushToStartTokenToSend(fresh:latest:persisted:)` returns the first non-empty value.
- `LiveActivityAPI.swift:48` `lastPushToStartToken` is persisted in UserDefaults under `la.push_to_start_token`.
  - UserDefaults is wiped on uninstall.
  - The value is kept across unregister, because it belongs to the install, not the user.

**Coordinator:**
- `rememberPushToStartToken` stores the token both in memory and persisted. It is used by `start()` and by the 17.2 update stream.
- `pushToStartTokenNow()` at `:98` re-reads `PlannActivity.pushToStartToken` on 17.2+, then falls back to latest, then to persisted.
- It is used in `performRegister` (`:335`) and `performReconcile` (`:205`).

**Tests** (`PushToStartAndSendableTests.swift`, 6 tests): order of precedence, empty strings ignored, all-nil → nil, persists across API instances, and survives unregister. RED before: the code did not compile (no such symbols).

### I. iPad reports `supported: false` (Minor #5)

**Change:** `PlannLiveActivityPlugin.swift:22` adds `@MainActor static var isPhone` (`userInterfaceIdiom == .phone`).
- register, reconcile, unregister, getStatus and openSettings all check it inside `Task { @MainActor in … }` and resolve `{supported:false}` otherwise. getStatus also includes iosVersion.
- `UIDevice` is touched only on the main actor, the same pattern as the existing getStatus fallback.

This is native-only, so there is no Linux test. JS already treats `supported:false` as "not registered, no retry".

### J. Settings banner refreshes on return (Minor #6)

**Change:** `LiveActivitySettings.js:36-46` adds a `visibilitychange` listener. When the page becomes visible it re-reads `getStatus()` and updates the status only. Preferences are not refetched. The listener is removed on unmount.

I used `visibilitychange` rather than `@capacitor/app` `appStateChange` to match `useLiveActivities` and add no import. WKWebView fires it on background/foreground.

**Tests:**
- "re-reads the status when the page becomes visible again": the banner stays while hidden, is gone after visible, and preferences GET runs once. RED before: the banner was still shown.
- "stops listening after unmount".

### K. Consent sheet uses theme tokens (Minor #7)

**Change:** `LiveActivityConsentSheet.js:72,79,82`.

| Before | After |
|---|---|
| `text-zinc-600` | `text-muted-foreground` |
| `border-zinc-200 text-zinc-700` | `border-input text-foreground` |
| `bg-zinc-900 text-white` | `bg-primary text-primary-foreground` |

Copy is unchanged.

Light-mode values:
- input #e5e5e5 vs zinc-200 #e4e4e7: equal.
- primary #171717 / #fafafa vs zinc-900 / white: equal.
- muted-foreground #737373 vs zinc-600 #52525b: slightly lighter. It is the same token as the DialogDescription directly above it, with 4.7:1 contrast on white (AA).
- foreground #0a0a0a vs zinc-700: slightly darker.

**Test:** "uses theme colour tokens, not fixed zinc/white" checks the sheet's own note and its two buttons. The shared `ui/dialog` close button still uses zinc and is out of scope. RED before.

### L. Minimal Dynamic Island: no ring for `.empty` (T4)

`AppointmentLiveActivity.swift:136-139`: the minimal view is `if l != .empty { IslandMark(...) }`, the same pattern as compactLeading.

### M. Compile hedges

1. `PlannWidgetsBundle.swift:7`: lists `AppointmentLiveActivity()` directly. The `if #available` is dropped; the extension target is 16.2 (pbxproj :587/:610).
2. `LiveActivityCoordinator.swift:384-392`: `BackgroundTaskGuard` keeps the task id in a local `var`, and the expiration closure calls `UIApplication.shared.endBackgroundTask(taskId)` directly. There is no `@MainActor` method call from the closure.
   - I type-checked a mock of this shape with swiftc 6.0 for the `@MainActor @Sendable` and the plain-closure signatures, in `-swift-version 5` and `6`. All were clean.
3. `ContentModel.swift:3,12,50`: `PlannPhase`, `PlannContentState` and `SlotId` are `Sendable`.
   - Test `SendableHedgeTests` uses a `requireSendable<T: Sendable>` helper.
   - Swift 5 mode does not diagnose this, so I showed RED with `swift build --build-tests -Xswiftc -strict-concurrency=complete`. Before the change: "type 'PlannPhase' / 'PlannContentState' / 'SlotId' does not conform to the 'Sendable' protocol". After: none.

**Not in scope (Ruling F3):** Minor #4, the `foreground` field.

**No new files in the App or extension targets.** The only new files are a SwiftPM test and two jest tests, so `add_live_activity_targets.py` needed no change. `--check` passes.

## Verification (raw tails)

### Swift core

Command: `docker run --rm -v <worktree>:/w -w /w/frontend/ios/LiveActivityCore swift:6.0 swift test`. That is 51 tests, up from 44.

```
Test Suite 'All tests' passed at 2026-11-16 16:15:12.600
	 Executed 51 tests, with 0 failures (0 unexpected) in 0.331 (0.331) seconds
◇ Test run started.
↳ Testing Library Version: 6.0.3 (18c42c19cac3faf)
✔ Test run with 0 tests passed after 0.001 seconds.
exit=0
```

### jest (scoped)

Command: `CI=true npx craco test --watchAll=false src/components/LiveActivity src/native src/lib src/context`. That is 52 tests, up from 35.

```
PASS src/components/LiveActivityConsentSheet.test.js
PASS src/components/LiveActivitySettings.test.js

Test Suites: 5 passed, 5 total
Tests:       52 passed, 52 total
Snapshots:   0 total
Time:        1.751 s, estimated 2 s
Ran all test suites matching /src\/components\/LiveActivity|src\/native|src\/lib|src\/context/i.
exit=0
```

The unscoped `CI=true npx craco test --watchAll=false` runs the same 5 suites: 52/52 passed, exit 0.

### Production web build

Command: `CI=false npx craco build`.

```
Compiled with warnings.

Failed to parse source map: 'webpack://ReactPixel/fb-pixel.js' URL is not supported
...
  890.26 kB (+619 B)  build/static/js/main.44c05197.js
...
The build folder is ready to be deployed.
exit=0
```

The only warning is a third-party source map (react-facebook-pixel). It is **pre-existing**: a baseline build of 90bf3825, taken with `git archive` into the scratchpad and the same node_modules, prints the identical "Compiled with warnings." and the same ReactPixel line. There are no ESLint warnings from the changed files. `frontend/build` is gitignored (`frontend/.gitignore:12:/build`) and already existed before this run. I left it in place.

### Backend

Not touched (`git diff --quiet 90bf3825..HEAD -- backend`), so pytest was not run.

### Targets, YAML and plists

```
$ python3 frontend/ios/scripts/add_live_activity_targets.py --check
CHECK OK
exit=0
$ python3 -c "import yaml;yaml.safe_load(open('codemagic.yaml'))"
yaml ok ['ios-capacitor-workflow', 'ios-live-activities-beta', 'android-capacitor-workflow']
plist ok frontend/ios/App/App/Info.plist 24
plist ok frontend/ios/App/PlannWidgets/Info.plist 10
```

### git status

```
(empty)
```

## Concerns

1. **App and extension Swift is not compiled anywhere yet.** No UIKit or ActivityKit on Linux, so the first Codemagic build is the compile check. The highest-touch spots:
   - the plugin's `Task { @MainActor in guard Self.isPhone … self.runX(call) }`: it captures non-Sendable `self` and `call`, the same pattern the plugin already used for `call`;
   - `RegisterOutcome` passing through `enqueueIdentity<T: Sendable>`;
   - the AppDelegate `Task { @MainActor in … }` in the MessagingDelegate method.
2. **A double `endBackgroundTask` is possible.** If the expiration handler fires, the later `BackgroundTaskGuard.end()` calls `endBackgroundTask` again on the same id. iOS only logs this; it is harmless. It was the trade-off for the ruling's "local id" form.
3. **A dead push-to-start token can be re-sent.** If APNs invalidates it, the sweeper clears it server-side (`sweeper.py:328`), but the persisted value can be sent again on the next register until ActivityKit issues a new one. That costs a wasted push attempt, and is still better than nulling a live token.
4. **The FCM fix only helps on the next resume.** The re-register runs on visibility→visible. On a fresh install, the FCM token arrives during the same foreground session, so the server gets it on the next resume (or reload), not immediately. The native side only stores the token, because there is no JWT-less register path.
5. **Capgo:** `autoUpdate=false` stops new downloads. A device that installs the beta over a production install that already holds a downloaded OTA bundle depends on Capgo's default reset-on-native-update behaviour. That is worth a glance during device QA (check that the JS has the consent sheet).
6. **Consent sheet light mode is equivalent but not pixel-identical:** the note text is #737373 vs #52525b, and the "Şimdi değil" text is #0a0a0a vs #3f3f46.

## Modern Web Guidance

- **`detect-initial-visibility-state`**: this guide is about measuring whether the page first loaded in the background. Neither J nor D needs that; they only need to react to later foregrounding. So I kept the plain `visibilitychange` + `document.visibilityState === 'visible'` check. The guide calls that "the `visibilitychange` event" fallback for "future visibility changes".
- **`color`**: I swapped the fixed zinc/white classes for the existing design tokens, following "Before generating tints dynamically, check if you can use an existing, predefined, design token". The note text stays at 4.7:1, above the "4.5:1 for normal text" minimum.
