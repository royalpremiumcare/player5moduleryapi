# Phase 0 Spike Runbook — Live Activities (throwaway, branch `spike/phase0-live-activities`)

Nothing here ships. Do not merge this branch, and do not trigger any workflow that has a `publishing:` section.
The Swift in `ios/` was written on a Linux host without Xcode and has **not been compiled**, so expect small compile fixes.

## Who and what you need

- A Mac with Xcode 26 and access to Apple team `9V42VGDN9U`.
- Physical iPhones. Simulators can't receive push-to-start.
  - **Required:** ≥ 1 on iOS 18.x and ≥ 1 on iOS 26.x.
  - **Wanted:** 1 on iOS 17.2–17.7 (it exercises the no-`input-push-token` path) and 1 Dynamic Island model.
- The Firebase service-account JSON for the PLANN project. Set `GOOGLE_APPLICATION_CREDENTIALS` yourself before running the sender.
- Python 3.10+ with `firebase-admin` (the backend's version, 7.1.0 if possible) on the Mac.

## One-time setup on the Mac (spike branch)

1. Run `cd frontend && npm install --legacy-peer-deps && npm run build:app && npx cap sync ios && cd ios/App && pod install`.
2. Open `App.xcworkspace`, then **File › New › Target › Widget Extension**.
   - Name: `SpikeWidgets`. Bundle id: `co.plannapp.app.widgets`.
   - Untick "Include Live Activity" and "Include Configuration App Intent".
   - Set the deployment target to **16.2**, and set "Embed in Application" to App.
3. Delete the generated Swift files and add `spikes/phase0/ios/SpikeWidgets/*.swift` to **SpikeWidgets**.
4. Add `spikes/phase0/ios/Shared/PlannAppointmentAttributes.swift` with target membership **App + SpikeWidgets**.
5. Add `spikes/phase0/ios/App/*.swift` to **App**.
6. In `MyViewController.capacitorDidLoad`, add `bridge?.registerPluginInstance(LASpikePlugin())`.
7. In `AppDelegate.didFinishLaunching`, after `Messaging.messaging().delegate = self`, add:
   `if #available(iOS 16.2, *) { Task { @MainActor in LASpikeObservers.shared.start() } }`
8. In the App target's `Info.plist`, add `NSSupportsLiveActivities` = `YES`.
9. **Debug-only signing:** `App.entitlements` hard-codes `aps-environment = production`. For Xcode device runs, create `App-Debug.entitlements` with `development` and point the Debug config's `CODE_SIGN_ENTITLEMENTS` at it. Keep the change on this branch only.
10. Run on each device and log in. From the Xcode console, copy:
    - the FCM token (the `📱 FCM Token:` line);
    - `pushToStartToken`, via Safari › Develop › device › PLANN › console: `await Capacitor.Plugins.LASpike.state()`.

> **APNs environment caveat:** Xcode Debug builds use **sandbox** APNs, while TestFlight and App Store builds use **production**. Run S1 and S2 in sandbox first. A production-environment run needs either an **Ad Hoc** profile (additive portal change) or a TestFlight internal build. Both need owner approval, see S4.

---

## S1 — FCM delivers ActivityKit start/update/end

Already **passed offline**: `firebase_admin 7.1.0` encodes `apns.live_activity_token`, the headers, and the flattened `aps` (start = 541 B). See `RESULTS.md`.

| Step | Command (`cd spikes/phase0`) | Pass |
|---|---|---|
| 1a dry run | `python3 s1_send_la_push.py --event start --fcm-token $FCM --la-token $P2S` (no `--send`) | FCM returns `projects/.../messages/...` without error |
| 1b start, app foreground | same + `--send --starts-in 300` (18+: add `--input-push-token`) | activity visible ≤ 10 s; countdown runs |
| 1c start, app background (Home) | same, new `--appointment-id` | visible ≤ 10 s |
| 1d start, app **force-quit** | same | visible ≤ 10 s |
| 1e start after **reboot + unlock**, app never opened | same | visible ≤ 10 s |
| 1f update → processing | `--event update --phase processing --version 2 --start-epoch <same> --la-token $ACTIVITY_TOKEN --send` (token from `readLog`) | label flips to "İşlemde", shows `v2` |
| 1g end cancelled | `--event end --phase cancelled --dismiss-now --la-token $ACTIVITY_TOKEN --send` | gone from the Lock Screen at once |
| 1h FCM-success ≠ visible | (i) start with `--no-alert`; (ii) start with a corrupted `--la-token` | record the FCM response vs the device outcome. Expected: FCM may return success while nothing appears, which proves D6's caveat |

Record for each row: iOS version, device, app state, FCM response, seconds to appear (or "never").

## S2 — Does iOS wake the app to deliver tokens? (decides how fast reconciliation can be)

Prepare by running `await Capacitor.Plugins.LASpike.clearLog()`, then put the app in the state under test.

| Case | Action | Evidence to collect (`(await Capacitor.Plugins.LASpike.readLog()).log` after reopening) |
|---|---|---|
| A foreground | push-to-start | `pushTokenUpdate` line, appState=0 |
| B background | Home, wait 1 min, push-to-start | `launch`/`observe`/`pushTokenUpdate` lines with appState=2 and timestamps **before** you reopened the app |
| C force-quit | swipe away, push-to-start | same as B (forum reports say it is often missing) |
| D after reboot, not opened | reboot, unlock, push-to-start | same as B |
| E first-ever push start | fresh install, push-to-start before any local start | does iOS show an "Allow Live Activities?" choice? Does the token arrive only after "Allow"? |
| F token stability | after B–D | is `pushToStartToken(sync)` non-nil at every launch? did `pushToStartTokenUpdate` fire on fresh install, reinstall or reboot? |
| G timer semantics | start with `--starts-in 120`, send no further pushes | at start, `Text(.timer)` switches from counting down to counting up by itself; at `stale-date` the label shows "Başlıyor" |
| H end with no app | case C, then `--event end` using a token captured earlier | activity ends with the app never launched |

**Pass/fail:** there is no fail. S2 *measures*. Record per iOS version which of B, C and D deliver the token in the background. The design no longer depends on this (see the updated spec §4); it only determines how quickly the server learns about new activities.

## S3 — Concurrency limits (measure only; never hard-code)

| Step | Action | Record |
|---|---|---|
| 3a | `LASpike.endAll()`, then `LASpike.startLocal({count: 12})` (app foreground) | index of the first failure and the `ActivityAuthorizationError` case |
| 3b | start a Clock-app timer (system Live Activity), repeat 3a | does the PLANN limit shrink? which error (`globalMaximumExceeded`?) |
| 3c | with PLANN at its limit, swipe one activity away on the Lock Screen, retry `startLocal({count:1})` | does a dismissed activity free a slot? does `stateUpdate` say `dismissed`? |
| 3d | `endAll()`, then push-to-start 8 distinct appointment ids 5 s apart, app force-quit | how many appear; check Console.app (filter `ActivityKit` / `liveactivitiesd`) for `targetMaximumExceeded` |
| 3e | iOS 26 only, optional: schedule a start ~3 min ahead (needs a 10-line addition using `request(…, start:)`) | does a scheduled activity count against the limit immediately? |

## S4 — Codemagic signing with an extension (+ App Group)

**Owner approval needed before the portal steps.** They change the live Apple Developer configuration.

1. **S4a (additive):** in the Apple portal, create App ID `co.plannapp.app.widgets` (no capabilities required for Live Activities), plus its App Store provisioning profile. Refresh Codemagic's code-signing identities ("Fetch profiles").
2. Push **this spike branch only**. Add `codemagic-spike-workflow.yaml`'s workflow to `codemagic.yaml` on the branch; it has **no publishing and no triggering**. Start it manually in the Codemagic UI.
   **Pass:** the archive is signed; the IPA contains `PlugIns/SpikeWidgets.appex`; the profile dump lists both bundle ids.
3. **S4b (modifies the production App ID):**
   - enable **App Groups** on `co.plannapp.app` and `co.plannapp.app.widgets`;
   - create `group.co.plannapp.app`;
   - regenerate **both** App Store profiles;
   - add the group to both entitlements on the branch;
   - re-run the workflow.

   **Pass:** the dump shows `com.apple.security.application-groups` in both profiles.
   Note: the next production build will use the regenerated profile, and the existing "Apple Sertifikalarini Hazirla" check will then need to look for app-groups too.

## S5 — Android FCM service coexistence (deprioritised: post-MVP)

Apply `android/PlannMessagingService.java` as described in its header, on an API 34 or 36 emulator with Google Play. Send a data-only FCM message `{plann_kind: la_spike, start_ms, title, body, apt}`.
**Pass:** JS `pushNotificationReceived` still fires in the foreground; the ongoing chronometer notification appears while backgrounded and after swipe-away; token refresh still reaches JS.

---

## Clean-up

On every device, run `LASpike.endAll()` and then uninstall the spike build. Delete the remote spike branch if one was pushed. Keep the Apple portal objects only if Phase 1 is approved.
