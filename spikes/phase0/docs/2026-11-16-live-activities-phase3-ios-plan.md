# PLANN Live Activities — Phase 3 iOS Client (D12 slot model) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the iOS app consume the merged Phase 1 backend. Device registration, per-activity tokens posted natively (even without the WebView), reconcile, slot Live Activities rendered in the owner-approved design, Settings controls and the consent onboarding. All of it stays invisible until the operator enables an org.

**Architecture:**
- **Foundation-only core:** `frontend/ios/LiveActivityCore/`, a SwiftPM package. It holds the content model, the API client, reconcile report and response logic, and the slot-id parsing. It is unit-tested on Linux in Docker and compiled into the app and widget targets by file reference.
- **Thin Apple layers:**
  - a WidgetKit extension `PlannWidgets` for the Live Activity UI, ported from the device-approved spike build 1009;
  - an app-side `LiveActivityCoordinator` for the ActivityKit observers;
  - a Capacitor plugin `PlannLiveActivity` that bridges JS.
- **React:** a no-op-safe wrapper and hook, plus the Settings section and the consent sheet.

**Tech Stack:** Swift 5.9+/SwiftUI/ActivityKit/WidgetKit, Capacitor 7 (CAPBridgedPlugin), React 19 + CRA/craco + jest, Codemagic, Docker `swift:6.0` (tests only).

**Specs (binding):** on branch `spike/phase0-live-activities`, `spikes/phase0/docs/`:
- `2026-11-15-live-activities-widgets-design.md`: §3A D12, §5.4/§5.6 consent, §6.0 visual, §13 D2c scope;
- `2026-11-16-phase3-ios-contract.md`: the exact backend contract;
- `../RESULTS.md`: device facts, items 8–24.

The backend is merged on local `main` at `473e0095` (`backend/live_activity/`). This plan replaces Tasks 15–19 of `2026-11-15-live-activities-widgets-plan.md`. Widgets/quick-add (old Tasks 10–14) are Phase 2 and out of scope.

## Global Constraints

- **Work location:** an isolated worktree on branch `feature/live-activities-ios`, created from local `main` 473e0095.
  - Never edit `/var/www/player5moduleryapi` (live production tree), never push, never deploy.
  - Merge needs owner approval.
- **No new npm, pod or SPM *app* dependencies.** The SwiftPM package is test-only scaffolding around files compiled into the existing targets.
- **JS no-op on old builds:** JS must no-op when `Capacitor.isPluginAvailable("PlannLiveActivity")` is false (OTA JS on old native builds) and on web/Android.
- **Deployment targets and guards:**
  - App target stays at iOS **15.0**; `ActivityKit` is weak-linked (`OTHER_LDFLAGS = -weak_framework ActivityKit`).
  - Every ActivityKit use is behind `@available(iOS 16.2, *)`; push-to-start is behind `@available(iOS 17.2, *)`.
- **Extension `PlannWidgets`:**
  - bundle `co.plannapp.app.widgets`, deployment 16.2, team `9V42VGDN9U`, Manual signing;
  - profile "PLANN Widgets AppStore" (exists, expires 2027-02-26);
  - **no App Group** (Phase 2 adds it).
- **App `Info.plist`:** `NSSupportsLiveActivities = YES`. **Not** `NSSupportsLiveActivitiesFrequentUpdates`: the p10 budget proved sufficient (R19/R22).
- **Attributes:** `PlannAppointmentAttributes { slotId: String, orgId: String }`. ContentState keys and types are exactly as in the contract doc, including `appointmentId`. Decoding must accept the golden fixture `backend/tests/contracts/live_activity_content_state.json`.
- **Backend calls:**
  - Native calls go to `{apiBaseUrl}/api/live-activities/...` with header `X-Plann-Device-Secret`, through **URLSession**. They never go through the WebView or axios. Reason: axios auto-logs-out on 401 (`frontend/src/api/api.js:19-39`).
  - The JWT is passed from JS only for `register` and `unregister`, and is **never persisted natively**.
  - `apiBaseUrl` is persisted in `UserDefaults`.
- **Secrets and identity:**
  - Device secret and install UUID live in the **app's** Keychain, `kSecAttrAccessibleAfterFirstUnlock`. Never in an App Group or shared storage.
  - `device_id` = a Keychain-persisted UUID string, created once.
- **Reconcile reports:** `complete: true` on launch, foreground and after a registration that returned a secret. State values: `active|stale|pending|ended|dismissed`.
- **Applying the reconcile response:**
  - `end: [slot_index]` → end the activity whose `slotId` index matches;
  - `end_activities: [activity_id]` → end by id;
  - `start_locally` → start only when foregrounded on iOS 16.2–17.1.
- **Version:** content `version` is monotonic per slot. Ignore any local update with a lower version.
- **Visual (§6.0, device-approved):**
  - white card, 3 rows;
  - amber strip 4 pt, 6 pt while processing; green processing dot and bar;
  - **default bar thickness** (no `scaleEffect`); no strikethrough on cancelled;
  - **terminal phases render no timer**;
  - copy "Başlamasına kalan", "Bitmesine kalan", "Başlıyor ·", "Süre doldu ·";
  - compact Dynamic Island leading = "P" mark;
  - `removed` renders an empty card;
  - `widgetURL` = `plannapp://appointment/<appointmentId>` (empty id → `plannapp://`).
- **Settings (D2c, D12):**
  - Owner (`role=="admin"`) and manager (staff with `can_view_all_appointments`) see:
    - scope "Canlı bildirimler: Sadece benim randevularım / Tüm personelin randevuları";
    - slot count 1–5, default 4;
    - "Randevu başladığında sesli uyarı" toggle, default off.
  - Plain staff see only the start-alert toggle.
  - Scope is hidden and treated as `all` when `admin_provides_service === false` and the org has no staff.
  - Everything is saved via `PUT /api/live-activities/preferences`.
  - The whole section is hidden unless the org flag `live_activity_enabled` (from `GET /api/settings`, read-only) is true **and** the plugin is available.
- **Consent sheet (§5.6, owner requirement):**
  - shown once per device after login on iOS ≥ 16.2 when the org flag is on;
  - it can be shown again from Settings;
  - "activities disabled" banner deep-links to iOS Settings.
  - Copy, verbatim (Turkish):
    - title: "Randevularınız kilit ekranında"
    - body: "Sıradaki randevunuz kilit ekranında ve Dynamic Island'da geri sayımla görünür. Saati gelince kendiliğinden \"İşlemde\" olur."
    - note: "iOS izin isteyecek. İleride \"izin vermeyi sürdürmek istiyor musunuz?\" diye tekrar sorabilir. Sorarsa Her Zaman İzin Ver'i seçin, yoksa randevular kilit ekranına gelmez."
    - buttons: "Devam", "Şimdi değil"
- **Frontend process:** CLAUDE.md requires consulting the `modern-web-guidance` skill before frontend UI/JS work, using existing `src/components/ui/*` (dialog, sheet, switch, select, radio-group). Must work at phone and desktop widths. Light/dark per the existing theme.
- **Swift tests:** run `docker run --rm -v <worktree>/frontend/ios/LiveActivityCore:/pkg -w /pkg swift:6.0 swift test`.
- **JS tests:** run `cd frontend && CI=true npx craco test --watchAll=false <path>`.
- **ActivityKit/SwiftUI/plugin code** cannot be compiled on this host. It is verified by the Codemagic beta build (Task 8, owner-triggered) and device QA.

## Review Focus

1. **Background launch by push-to-start with no WebView:** the per-activity token must still reach the server. Test: Task 2 `testTokenPostUsesPersistedBaseUrlAndSecretOnly` (no JWT, no WebView dependency). Device: Task 8 step "force-quit then start".
2. **Logout, then a different user logs in on the same phone:** every local activity ends, the secret is deleted, and register runs fresh. Tests: Task 2 `testUnregisterClearsSecretEvenIfServerFails`; Task 6 `unregister on logout then register on next login`.
3. **New OTA JS on an old native build (no plugin):** no errors, and the Settings section and sheet stay hidden. Tests: Task 6 `no-op without plugin`; Task 7 `section hidden when plugin unavailable`.
4. **JWT expired while foregrounded:** reconcile must not cause a logout. Test: Task 2 `testReconcileRequestHasSecretHeaderAndNoAuthorization`.
5. **User disabled Live Activities in iOS Settings:** the banner shows and the report carries `activities_enabled:false`. Tests: Task 2 `testReportCarriesActivitiesEnabledFlag`; Task 7 `disabled banner deep-links to iOS settings`.

---

## File structure

| File | Responsibility |
|---|---|
| `frontend/ios/LiveActivityCore/Package.swift` | test-only SwiftPM manifest, Linux-compatible |
| `frontend/ios/LiveActivityCore/Sources/LiveActivityCore/ContentModel.swift` | `PlannContentState`, `PlannPhase`, `SlotId` (Foundation only) |
| `frontend/ios/LiveActivityCore/Sources/LiveActivityCore/LiveActivityAPI.swift` | URL building, request encoding, response decoding, `HTTPTransport` and `SecretStore` protocols |
| `frontend/ios/LiveActivityCore/Sources/LiveActivityCore/ReconcileLogic.swift` | report building, response → `[EndInstruction]`/`[LocalStart]` |
| `frontend/ios/LiveActivityCore/Tests/LiveActivityCoreTests/*.swift` | Linux unit tests, plus a copy of the golden fixture as a resource |
| `frontend/ios/App/Shared/PlannAppointmentAttributes.swift` | `ActivityAttributes` wrapper (App + PlannWidgets targets) |
| `frontend/ios/App/PlannWidgets/{PlannWidgetsBundle,AppointmentLiveActivity}.swift`, `Info.plist` | extension, UI |
| `frontend/ios/App/App/{LiveActivityCoordinator,PlannLiveActivityPlugin,KeychainSecretStore,URLSessionTransport}.swift`, `PlannLiveActivityPlugin.m` | app-side native |
| `frontend/ios/App/App.xcodeproj/project.pbxproj`, `App/Info.plist`, `App/AppDelegate.swift`, `App/MyViewController.swift` | wiring |
| `frontend/ios/scripts/add_live_activity_targets.py` | idempotent pbxproj editor (ported from the spike's `add_spike_target.py`) |
| `codemagic.yaml` | production signing for the extension + `ios-live-activities-beta` workflow |
| `frontend/src/native/liveActivities.js`, `frontend/src/native/useLiveActivities.js` (+ `.test.js`) | JS bridge + lifecycle hook |
| `frontend/src/components/LiveActivitySettings.js`, `LiveActivityConsentSheet.js` (+ `.test.js`) | UI |
| `frontend/src/App.js`, `frontend/src/components/Settings.js` | mount points only |

---

### Task 0 (controller): Worktree and tooling

- [ ] `git -C /var/www/player5moduleryapi worktree add <scratch>/la-ios -b feature/live-activities-ios main` (main = 473e0095).
- [ ] JS deps: symlink `<scratch>/la-ios/frontend/node_modules` → `/var/www/player5moduleryapi/frontend/node_modules` (read-only use). Baseline: run `CI=true npx craco test --watchAll=false src/lib` and record the result.
- [ ] Swift: `docker pull swift:6.0`. Record `docker run --rm swift:6.0 swift --version`.

### Task 1: Core content model (Linux-tested)

**Files:**
- Create: `Package.swift` (swift-tools-version 5.9; library `LiveActivityCore`; test target with `resources: [.copy("Fixtures")]`)
- Create: `Sources/LiveActivityCore/ContentModel.swift`
- Create: `Tests/LiveActivityCoreTests/ContentModelTests.swift`
- Create: `Tests/LiveActivityCoreTests/Fixtures/live_activity_content_state.json`. This is a byte copy of `backend/tests/contracts/live_activity_content_state.json`; a test asserts the two files are identical when both paths exist.

**Interfaces — Produces:**
- `public enum PlannPhase: String, Codable { case upcoming, processing, completed, cancelled, removed, unknown }`. Decoding an unknown string yields `.unknown`.
- `public struct PlannContentState: Codable, Hashable { phase, startEpoch: Double, endEpoch: Double, startLabel, endLabel, customerDisplay: String?, serviceName, staffName: String?, version: Int, appointmentId: String }`. It has `startDate`/`endDate` computed properties and `var isTerminal: Bool` (completed, cancelled, removed, unknown).
- `public struct SlotId: Hashable { deviceId: String; index: Int; init?(_ raw: String) }`. It parses `"<device_id>:<n>"` at the **last** colon; n must be in 1...5. `var raw: String`.
- `public func shouldApply(incoming: Int, current: Int?) -> Bool` returns true when `current == nil || incoming >= current`.

- [ ] **Step 1:** Failing tests:
  - `testDecodesBackendGoldenFixture`: every key decodes, epochs are Doubles, `appointmentId` is non-empty.
  - `testFixtureMatchesBackendCopy`.
  - `testUnknownPhaseDecodesAsUnknown`.
  - `testRemovedStubDecodes`: empty labels, service and appointmentId; null names.
  - `testTerminalPhases`.
  - `testSlotIdParsing`: `"ABC:DEF:3"` gives deviceId `"ABC:DEF"` and index 3; `"x:0"`, `"x:6"`, `"x"` and `"x:a"` give nil.
  - `testVersionMonotonic`.
- [ ] **Step 2:** `docker run … swift test` → FAIL (no module).
- [ ] **Step 3:** Implement. Use Foundation only, and no `#available` in this package.
- [ ] **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat(ios-core): Live Activity content model`.

### Task 2: Core API client & reconcile logic (Linux-tested)

**Files:**
- Create: `Sources/LiveActivityCore/LiveActivityAPI.swift`, `Sources/LiveActivityCore/ReconcileLogic.swift`
- Test: `Tests/LiveActivityCoreTests/APITests.swift`, `Tests/LiveActivityCoreTests/ReconcileTests.swift`

**Interfaces:**
- Consumes: Task 1 types.
- Produces:
  - `public protocol HTTPTransport { func send(_ request: URLRequest) async throws -> (Data, Int) }`. On Linux this needs `#if canImport(FoundationNetworking) import FoundationNetworking #endif`.
  - `public protocol SecretStore { func read(_ key: String) -> String?; func write(_ key: String, _ value: String); func delete(_ key: String) }`. Keys: `"la.device_id"`, `"la.device_secret"`.
  - `public final class LiveActivityAPI(transport: HTTPTransport, secrets: SecretStore, defaults: UserDefaults)`:
    - `apiBaseUrl: String?`, persisted in defaults key `"la.api_base_url"`;
    - `deviceId() -> String`: read or create a UUID and store it;
    - `register(apiBaseUrl: String, jwt: String, osVersion: String, appBuild: String, fcmToken: String?, pushToStartToken: String?, activitiesEnabled: Bool) async throws -> Bool`. POST `/api/live-activities/devices` with `Authorization: Bearer <jwt>`. It stores `device_secret` when non-null, and returns true if a new secret was stored.
    - `postToken(slotIndex: Int, activityId: String, updateToken: String) async throws`. POST `/api/live-activities/token`, secret header only. It throws `.noSecret` if there is no secret.
    - `reconcile(_ report: ReconcileReport) async throws -> ReconcileResponse`. POST `/api/live-activities/reconcile`, secret header only, **no Authorization header**.
    - `unregister(jwt: String) async`. DELETE `/api/live-activities/devices/{id}` with the JWT. Errors are ignored, and it **always** deletes the secret afterwards.
  - `public struct ActivitySnapshot { slotIndex: Int; activityId: String; state: String /* active|stale|pending|ended|dismissed */ }`
  - `public struct ReconcileReport: Encodable { device_id, activities_enabled: Bool, complete: Bool, push_to_start_token: String?, slots: [ActivitySnapshotDTO] }`
  - `public struct ReconcileResponse: Decodable { end: [Int]; end_activities: [String]; start_locally: [LocalStart] }`. Missing keys decode as empty.
  - `public struct LocalStart: Decodable { slot_index: Int; content: PlannContentState; stale_epoch: Double?; relevance: Double; attributes: [String: String]? }`
  - `public func endInstructions(response: ReconcileResponse, current: [ActivitySnapshot]) -> Set<String>`: the activity ids to end, as the union of matches by slot index and the explicit `end_activities`.
  - `public enum APIError: Error { case noSecret, noBaseUrl, http(Int) }`

- [ ] **Step 1:** Failing tests, using a recording fake transport and an in-memory `SecretStore`:
  - `testRegisterSendsBearerOnceAndStoresSecret`;
  - `testRegisterWithNullSecretKeepsExisting`;
  - `testTokenPostUsesPersistedBaseUrlAndSecretOnly`: no Authorization header, URL `https://plannapp.co/api/live-activities/token`, JSON keys exactly `device_id, slot_index, activity_id, update_token`;
  - `testTokenPostWithoutSecretThrowsNoSecret`;
  - `testReconcileRequestHasSecretHeaderAndNoAuthorization`;
  - `testReportCarriesActivitiesEnabledFlag`;
  - `testResponseMissingKeysDecodeEmpty`;
  - `testEndInstructionsBySlotAndById`. Current `[1:A1, 1:OLD, 2:B]`, response `end:[2], end_activities:["OLD"]` gives `{"B","OLD"}`, and A1 is kept.
  - `testUnregisterClearsSecretEvenIfServerFails`;
  - `testDeviceIdStableAcrossCalls`.
- [ ] **Step 2–4:** FAIL, then implement, then PASS (docker command).
- [ ] **Step 5:** Commit `feat(ios-core): Live Activity API client and reconcile logic`.

### Task 3: Extension target, signing and CI

**Files:**
- Create: `frontend/ios/scripts/add_live_activity_targets.py`. It is idempotent (re-running is a no-op) and ported from the spike's `add_spike_target.py` (scratchpad; read it). It adds:
  - target `PlannWidgets` (app-extension, `co.plannapp.app.widgets`, 16.2, Manual, team 9V42VGDN9U, `INFOPLIST_FILE = PlannWidgets/Info.plist`);
  - an "Embed Foundation Extensions" phase placed **before** "[CP] Embed Pods Frameworks";
  - App target `OTHER_LDFLAGS += -weak_framework ActivityKit`;
  - file references for `Shared/PlannAppointmentAttributes.swift` (both targets);
  - `../LiveActivityCore/Sources/LiveActivityCore/ContentModel.swift` (both targets) and the other core files (App only);
  - the extension sources;
  - the app-side files from Task 5 (App only).
- Create: `frontend/ios/App/PlannWidgets/Info.plist` (NSExtensionPointIdentifier `com.apple.widgetkit-extension`) and `PlannWidgetsBundle.swift`. The bundle is `@main struct PlannWidgetsBundle: WidgetBundle` with body `AppointmentLiveActivity()`, using a placeholder view until Task 4.
- Create: `frontend/ios/App/Shared/PlannAppointmentAttributes.swift`: `@available(iOS 16.2, *) struct PlannAppointmentAttributes: ActivityAttributes { typealias ContentState = PlannContentState; let slotId: String; let orgId: String }`.
- Modify: `frontend/ios/App/App/Info.plist`: `NSSupportsLiveActivities` true.
- Modify: `codemagic.yaml`.
  - In `ios-capacitor-workflow`, insert before "Apple Sertifikalarini Hazirla" the spike's step "Widget extension profili (yoksa oluştur)". It downloads the existing "PLANN Widgets AppStore" profile with `app-store-connect profiles list --json` and uses plutil detection (proven in the spike).
  - Extend the existing profile dump to also print the widgets profile.
  - Add an `ios-live-activities-beta` workflow: a copy of `ios-spike-phase0` with `SPIKE_MARKETING_VERSION` → `LA_BETA_MARKETING_VERSION: "6.4.91"`, build `2000 + BUILD_NUMBER`, TestFlight only, and an IPA check that the appex is present.
- Test: `python3 frontend/ios/scripts/add_live_activity_targets.py --check` must exit 0 after it is applied. `--check` verifies the target, phase order, LDFLAGS and the refs. `plutil -lint` is not available on Linux, so use `python3 -c "import plistlib; plistlib.load(open(p,'rb'))"` for both Info.plists.

- [ ] **Step 1:** Write the script with `--apply` and `--check`. Run `--check` and see it FAIL.
- [ ] **Step 2:** Run `--apply`, then `--check` → PASS. Run `--apply` again: there is no diff (idempotent).
- [ ] **Step 3:** Make the plist, Swift and Codemagic edits. Validate the YAML with `python3 -c "import yaml,sys; yaml.safe_load(open('codemagic.yaml'))"`.
- [ ] **Step 4:** Commit `build(ios): PlannWidgets extension target, Live Activities plist and Codemagic signing`.

### Task 4: Live Activity UI (port of the device-approved spike)

**Files:**
- Create: `frontend/ios/App/PlannWidgets/AppointmentLiveActivity.swift`. Port it from the spike branch file `frontend/ios/App/PlannSpikeWidgets/AppointmentLiveActivity.swift` at commit `452900a9` (the 1009 design with default bar thickness). Changes:
  - attributes `slotId`/`orgId`;
  - `widgetURL` from `context.state.appointmentId`;
  - `PlannPhase` enum instead of string compares;
  - `.removed` / `.unknown` render an empty card (white background, no text);
  - no `la-spike` URLs;
  - no spike comments.
- Modify: `PlannWidgetsBundle.swift` to use the real view.

- [ ] **Step 1:** Port. Self-check with grep that:
  - no `scaleEffect` remains;
  - no `strikethrough` remains;
  - no `.timer`/`timerInterval` appears inside any terminal-phase branch;
  - the copy strings match Global Constraints verbatim.
- [ ] **Step 2:** Commit `feat(ios): slot Live Activity UI (approved design)`. Compilation is verified at Task 8.

### Task 5: App-side coordinator, plugin and Keychain

**Files:**
- Create: `App/KeychainSecretStore.swift` (`SecretStore`, generic-password items, service `co.plannapp.app.la`, `kSecAttrAccessibleAfterFirstUnlock`).
- Create: `App/URLSessionTransport.swift` (`HTTPTransport`, 15 s timeout).
- Create: `App/LiveActivityCoordinator.swift`: `@available(iOS 16.2, *) final class LiveActivityCoordinator`, `static let shared`. It:
  - observes `Activity<PlannAppointmentAttributes>.activityUpdates`, and for each activity its `pushTokenUpdates` and `activityStateUpdates`;
  - observes `ActivityAuthorizationInfo().activityEnablementUpdates`;
  - on iOS 17.2+, observes `pushToStartTokenUpdates`;
  - posts tokens via `api.postToken`, with the slot index parsed from `attributes.slotId`;
  - builds a `complete` report from `Activity.activities`, mapping `activityState` `.active`/`.stale`/`.pending`/`.ended`/`.dismissed` to strings;
  - `reconcile()` applies `endInstructions` with `end(dismissalPolicy: .immediate)`, plus `start_locally` only when `UIApplication.shared.applicationState == .active` and on iOS < 17.2;
  - `endAll()`;
  - debounces state-change reports by 2 s;
  - keeps `latestPushToStartToken`, used in `register` and `reconcile`.
- Create: `App/PlannLiveActivityPlugin.swift` + `.m`. `jsName "PlannLiveActivity"`, with methods:
  - `register({apiBaseUrl, jwt, fcmToken?}) -> {deviceId, newSecret}`
  - `reconcile() -> {ended, startedLocally}`
  - `unregister({jwt})`, which calls `endAll()` and then `api.unregister`
  - `getStatus() -> {supported, enabled, iosVersion}`
  - `openSettings()`, which opens `UIApplication.openSettingsURLString`

  Below iOS 16.2, every method resolves `{supported:false}` without error.

  `register` calls are **serialized**: a single in-flight registration, and later calls await it (contract doc). `register` always sends the last-known `fcmToken` and `push_to_start_token`. After a `register` that returned `newSecret: true`, run one `complete` reconcile.
- Modify:
  - `MyViewController.capacitorDidLoad`: `registerPluginInstance(PlannLiveActivityPlugin())`.
  - `AppDelegate.didFinishLaunching`: `if #available(iOS 16.2, *) { LiveActivityCoordinator.shared.start() }`, so it also runs on background launches (R13).
  - `AppDelegate.applicationDidBecomeActive`: trigger `reconcile()` when a secret exists.
- Modify: the Task 3 script so it adds these files to the App target. Re-run `--apply` and `--check`.

- [ ] **Step 1:** Implement, keeping all decision logic in the core (Tasks 1–2); the coordinator only adapts ActivityKit. Self-check with grep:
  - no `localStorage`/WebView access;
  - no `Authorization` header except in `register`/`unregister`;
  - every ActivityKit symbol is inside `@available` scopes.
- [ ] **Step 2:** `--check` PASS. Commit `feat(ios): Live Activity coordinator, plugin and Keychain store`.

### Task 6: JS bridge and lifecycle hook (jest)

**Files:**
- Create: `frontend/src/native/liveActivities.js`. It exports:
  - `isLiveActivitySupported(): boolean`, which is `Capacitor.isNativePlatform() && Capacitor.getPlatform()==='ios' && Capacitor.isPluginAvailable('PlannLiveActivity')`;
  - async wrappers `register`, `reconcile`, `unregister`, `getStatus`, `openSettings`. They resolve to `null` when unsupported and never throw (they catch and return null).
- Create: `frontend/src/native/useLiveActivities.js`: `useLiveActivities({ token, currentUser, orgFlagEnabled })`.
  - When supported and enabled with a token: call `register({apiBaseUrl: <origin of REACT_APP_BACKEND_URL or window.location.origin>, jwt: token, fcmToken})` once per (user_id, token-session).
  - Call `reconcile` after register and on `visibilitychange`→visible.
  - On logout (token becomes falsy after being set), call `unregister({jwt: <previous token>})`.
  - Returns `{ status }` from `getStatus`.
- Modify: `frontend/src/App.js`. Mount the hook once next to the existing push setup, passing `token`, `currentUser` and the org flag from settings. Only add lines; change no other behavior.
- Test: `frontend/src/native/useLiveActivities.test.js`, which mocks `@capacitor/core`:
  - `no-op without plugin`
  - `no-op when org flag off`
  - `register once per login`
  - `reconcile on visible`
  - `unregister on logout then register on next login`
  - `wrappers swallow plugin errors`

- [ ] **Step 0:** Consult the `modern-web-guidance` skill: search "page visibility change", and apply anything relevant.
- [ ] **Step 1–4:** FAIL, then implement, then PASS: `CI=true npx craco test --watchAll=false src/native`.
- [ ] **Step 5:** Commit `feat(app): Live Activities JS bridge and lifecycle hook`.

### Task 7: Settings section, consent sheet, disabled banner (jest)

**Files:**
- Create: `frontend/src/components/LiveActivitySettings.js`.
  - Props: `{ currentUser, settings, onOpenConsent }`.
  - Visibility rules are in Global Constraints. Use the existing `ui/*` components.
  - Saves via `PUT /api/live-activities/preferences`, with sonner toasts (as in Settings.js).
  - Shows the disabled banner when `getStatus().enabled === false`; it calls `openSettings`.
- Create: `frontend/src/components/LiveActivityConsentSheet.js`.
  - Uses the existing dialog or sheet component, with the verbatim copy from Global Constraints.
  - Stores the "seen" flag in `localStorage` key `la_consent_seen:<user_id>` inside try/catch.
  - Shown automatically once after login when supported, the flag is on, and it has not been seen.
- Modify: `frontend/src/components/Settings.js` to mount the section (lines added only). Modify `App.js` to mount the sheet next to the hook.
- Tests:
  - `LiveActivitySettings.test.js`:
    - `section hidden when plugin unavailable`
    - `section hidden when org flag off`
    - `owner sees scope, slots and alert`
    - `manager sees scope and slots`
    - `plain staff sees only alert`
    - `scope hidden when admin does not provide service and no staff`
    - `slot count limited to 1..5 default 4`
    - `saves via preferences endpoint`
    - `disabled banner deep-links to iOS settings`
  - `LiveActivityConsentSheet.test.js`:
    - `shown once after login, never before login`
    - `copy is verbatim`
    - `Şimdi değil dismisses and records seen`
    - `localStorage failure still renders and dismisses`

- [ ] **Step 0:** Consult `modern-web-guidance`: "modal dialog", "settings toggle switch", "accessible radio group". Apply what fits the existing `ui/*` components without adding dependencies.
- [ ] **Step 1–4:** FAIL, then implement, then PASS: `CI=true npx craco test --watchAll=false src/components/LiveActivity`.
- [ ] **Step 5:** Check at 375 px and 1280 px widths with the existing dev tooling, if available. Otherwise note it for owner QA.
- [ ] **Step 6:** Commit `feat(app): Live Activity settings and consent onboarding`.

### Task 8 (owner + controller): Beta build and device QA

- [ ] **Owner:** run Codemagic workflow **`ios-live-activities-beta`** on branch `feature/live-activities-ios`. Any Swift compile errors go back to the controller, which runs a fix loop on Tasks 3–5.
- [ ] Backend for the beta: the beta talks to production `plannapp.co`, but that backend does not yet run the Phase 1 code. The beta can only be QA'd after the owner deploys the merged backend (flag off for everyone) and the controller enables `live_activity_enabled` for **one internal test org** only, via a direct DB update by the owner.
- [ ] **Device matrix** (owner):
  - iPhone 11 / 26.0, 16 Plus / 26.6, plus any iOS 17/18 device available;
  - login → consent sheet → register;
  - morning slot open;
  - switch on completion;
  - processing alert on/off;
  - slot count 4 → 2 with one card dismissed (it must stay hidden);
  - force-quit then start (token arrives);
  - offline then reconnect;
  - logout → cards gone;
  - another user logs in on the same phone;
  - Live Activities disabled → banner.
- [ ] Record the results in RESULTS.md (spike branch).
- [ ] Merging `feature/live-activities-ios` to main needs owner approval. So does enabling more orgs.
