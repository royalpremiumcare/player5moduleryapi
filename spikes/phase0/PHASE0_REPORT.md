# Phase 0 Report: PLANN Live Activities & Home Screen Widgets

**Date:** 2026-11-15
**Branch:** `spike/phase0-live-activities` (throwaway; never merged)
**Devices:**
- iPhone 11, iOS 26.0
- iPhone 16 Plus, iOS 26.6 (Dynamic Island)

**Build:** TestFlight 6.4.90 (1005), Codemagic workflow `ios-spike-phase0`
**Push path:** production Firebase project `plann-54bd6` → FCM HTTP v1 → APNs (production)
**Production impact:** none.
- No change on `main`.
- No backend deploy.
- The App Store production App ID and profile are untouched.

Evidence (raw device logs, timings, payloads) lives in `RESULTS.md`. The design and plan were updated to **Revision 3** in `docs/`.

---

## 1. Verdict

**The iOS Live Activity architecture is viable as designed, with four corrections.** All four iOS spikes passed on real devices. No result requires a different transport, a different backend model, or the iOS 18 broadcast-channel fallback.

| Spike | Result | One-line evidence |
|---|---|---|
| **S1** FCM transport (start / update / end) | ✅ PASS | Push-to-start appeared ~2 s after send; "İşlemde" update and "İptal edildi" end applied instantly; identical on 26.0 and 26.6 |
| **S2** Token delivery with app backgrounded / force-quit | ✅ PASS | Force-quit app was cold-launched in background by iOS; per-activity token logged 2–3 s after send; that token then drove a successful remote update |
| **S3** Concurrency limit | ✅ PASS (measured) | **5 per app** on both devices; 6th+ → `targetMaximumExceeded`; over-limit push-to-start silently dropped; ended activities evicted to make room |
| **S4** Codemagic signing with a WidgetKit extension | ✅ PASS | Extension `co.plannapp.app.widgets` signed and uploaded to TestFlight; Live Activities need no App Group |
| **S5** Android FCM service coexistence | ⏸ Code review only | Android is a separate post-MVP phase (decision D7) |

---

## 2. Exact platform behaviour observed

| Behaviour | Observed | Devices |
|---|---|---|
| Max concurrent PLANN activities | **5** (non-ended; stale ones count) | both |
| Error for the 6th local start | `ActivityAuthorizationError.targetMaximumExceeded` (per-app, not global) | both |
| Push-to-start when at 5 | **Silently dropped**: FCM success, nothing shown, no app callback, **not queued** | iPhone 11 |
| Push-to-start when 1 of 5 is *ended but still visible* | Starts normally; iOS dismisses the ended card at the same instant | iPhone 11 |
| Push-to-start → visible | ~2 s | both |
| Push-to-start → per-activity token on device, app backgrounded | ~3 s | iPhone 11 |
| Push-to-start → per-activity token on device, app force-quit | ~2–3 s (iOS background-launches the app) | iPhone 11 |
| Remote update / end → visible | immediate | iPhone 11 |
| `staleDate` = start → "Başlıyor" | works | both |
| Consent prompt 1 ("…izin verilsin mi?") | after the first activity | iPhone 11 |
| Consent prompt 2 ("…izin vermeyi sürdürmek istiyor musunuz?") | iPhone 11: on the **first remote start**. iPhone 16 Plus: **later**, during a local start | both: timing differs |
| Dynamic Island compact | renders leading icon and trailing timer | iPhone 16 Plus |

---

## 3. What changed in the design (Revision 3)

1. **Cap defaults to 5** (spec §4.1, §4.2 rule 1; plan Task 4, Task 6). It replaces "unknown until learned". It stays adaptive: device-reported limit errors can lower it.
2. **The server never push-starts over the cap** (§4.2 rule 1a). Over-limit starts vanish without trace, so the server's own count is authoritative. Overflow appointments get the standard notification, chosen by the D2 priority order.
3. **Swap = end, then start** (§4.2 rule 1b, new decision **D11**). When a more urgent appointment needs a slot, the server ends the least urgent live activity and starts the new one on the next sweeper pass. Instant dismissal is not needed, because iOS evicts ended cards.
4. **Token upload runs natively** (§5.4; plan Task 17 adds `testTokenPostedOnBackgroundLaunchWithoutWebView`). This confirms the existing design: on a background launch only Swift runs, so the WebView/JWT path can't be relied on.
5. **Consent onboarding copy** (§5.6; plan Task 18). The copy says "iOS *may* ask again; if it does, choose Her Zaman İzin Ver". It never says "you will now be asked twice".
6. **UI fixes found on device** (§6; plan Task 16):
   - terminal phases (completed / cancelled / removed) show **no live timer** (the spike counted up from 0 after a cancel);
   - the compact Dynamic Island shows the **PLANN mark**, not a generic clock glyph.
7. **D10 (iOS 18 broadcast channels) is deferred.** S2 proved that per-activity tokens arrive even after force-quit.

---

## 4. Risks that remain (not covered by Phase 0)

| # | Risk | Severity | Handling |
|---|---|---|---|
| R1 | **Global** device limit shared with other apps (e.g. a Clock timer, delivery apps) was not measured | Medium | D9 M1: start-time notice for unresolved starts; reconciliation marks them `absent` |
| R2 | Only iOS 26.x was tested; 17.2–18.x may differ (cap, token wake) | Medium | Pilot (Task 19) on at least one iOS 17/18 device; `observed_cap` stays adaptive |
| R3 | Low Power Mode, Background App Refresh off, no network at start time | Medium | Not tested; reconciliation on next foreground is the recovery path |
| R4 | Back-to-back end+start ordering (sent within the same second) | Low | Design sends the start on the *next* sweeper pass (verified with a 9 s gap) |
| R5 | `firebase-admin` is unpinned in `backend/Dockerfile` | Medium | Pin it in Phase 1 (plan Task 5) |
| R6 | Home Screen widgets need an **App Group**, which means modifying the production App ID and regenerating the App Store profile | Medium | Phase 2, Task 15, with explicit owner approval at that time |
| R7 | TestFlight build **6.4.90 (1005)** exists in App Store Connect | Low | Never submit it for review; expire it in TestFlight after sign-off |
| R8 | REM-1 duplicate transactions and REM-2 duration divergence (pre-existing) | High | Separate remediation tickets (`REMEDIATION.md`), not part of this feature |

---

## 5. Decisions needed from you

| # | Question | Recommendation |
|---|---|---|
| **Phase 1 go** | Start production Tasks 1–9 (backend core, behind a flag that is off) | **Approve.** No user-visible change until the flag is enabled |
| **D11** (new) | At the cap, may a more urgent appointment replace the least urgent Live Activity? | **Yes.** Otherwise a running appointment can be hidden behind five later ones |
| **D9** | Start-time notice for starts never confirmed by the device | **M1** (one notice at start time, only if unconfirmed) |
| **D2b** | Managers' Lock Screen default | Own appointments, switchable to business-wide |
| **R6 timing** | When to add the App Group to the production App ID | At the start of Phase 2 (widgets), not before |

---

## 6. Spike cleanup checklist (after your sign-off)

- [ ] Expire TestFlight build 6.4.90 (1005).
- [ ] Keep branch `spike/phase0-live-activities` as reference; delete it when Phase 3 ships.
- [ ] Keep App ID `co.plannapp.app.widgets` and profile "PLANN Widgets AppStore" (expires 2027-02-26); Phase 2 reuses them.
- [ ] Remove the spike debug screen (`plannapp://la-spike`); it exists only on the spike branch.
