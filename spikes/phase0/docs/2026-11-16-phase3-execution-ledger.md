# SDD ledger — plan: /tmp/claude-0/-var-www-player5moduleryapi/53f81d0e-4c9d-49e9-b05f-cc6c0967bae9/scratchpad/spike-phase0/spikes/phase0/docs/2026-11-16-live-activities-phase3-ios-plan.md

Specs: same dir — 2026-11-15-live-activities-widgets-design.md (§3A, §5.6, §6.0, D2c), 2026-11-16-phase3-ios-contract.md, ../RESULTS.md. Worktree: scratchpad/la-ios, branch feature/live-activities-ios from main 473e0095. Never push/merge/deploy.

**Owner preference (memory always-use-superpowers):** every subagent prompt must require superpowers skills.
- Implementers: superpowers:test-driven-development before coding; superpowers:systematic-debugging on unexpected failures; superpowers:verification-before-completion before reporting; fix rounds also superpowers:receiving-code-review; frontend also modern-web-guidance.
- Reviewers: superpowers:verification-before-completion.

## Task 0 (controller): done
- Worktree created; frontend/node_modules symlinked to the production node_modules (read-only use).
- Jest baseline: src/lib 5/5 passed.
- Swift: swift:6.0 image (Swift 6.0.3) pulled.
- SDD workspace is ignored via .superpowers/sdd/.gitignore.

## Pre-flight scan

| Pair / task | Produces vs consumes | Finding |
|---|---|---|
| T1→T2,T4,T5 | PlannPhase, PlannContentState, SlotId, shouldApply | consistent |
| T2→T5 | LiveActivityAPI, HTTPTransport, SecretStore, ReconcileReport/Response, endInstructions, APIError | consistent |
| T3→T4,T5 | pbxproj script (--apply/--check), Shared attributes, PlannWidgetsBundle placeholder | **P1** T3 lists Task-5 app files that don't exist yet |
| T5→T6 | plugin jsName PlannLiveActivity, methods register/reconcile/unregister/getStatus/openSettings | consistent with T6 wrapper |
| T6→T7 | liveActivities.js wrappers, useLiveActivities status | consistent |
| T1 self | testFixtureMatchesBackendCopy "when both paths exist" vs docker mounting only the package dir | **P2** test would silently skip |
| T3 self | plist validation via plistlib; YAML via yaml.safe_load | ok |
| T4 self | port from 452900a9 (verified reachable; 0 scaleEffect) | ok |
| T5 self | coordinator adapts ActivityKit only; logic in core | ok |
| T6/T7 self | jest via craco; node_modules symlink | ok (baseline green) |
| T8 | owner-driven | ok |

**Rulings:**
- **Ruling P1:** Task 3's script adds only files that exist at Task 3 (core files, Shared, extension). Task 5 extends the script's file list with its own app files and re-runs `--apply`/`--check`. Reason: references to nonexistent files are confusing; T5 already plans to extend the script. Cost if wrong: none.
- **Ruling P2:** the Swift test command mounts the **worktree root**: `docker run --rm -v <worktree>:/w -w /w/frontend/ios/LiveActivityCore swift:6.0 swift test`. `testFixtureMatchesBackendCopy` locates the backend fixture via a `#filePath`-relative path and **fails** (never skips) if it is missing. Reason: a silent skip would hide contract drift. Cost if wrong: none.

## Tasks
- Task 1: dispatched implementer (sonnet), BASE 473e0095
- Task 1: implementer DONE_WITH_CONCERNS (6d51ac8c). Controller verified: 8/8 swift tests, clean tree. Concerns accepted: empty deviceId rejected; package .gitignore for .build/.swiftpm.
- Task 1: complete (commits 473e009..6d51ac8, review clean; fixture byte-identical to backend)
- Task 1: minor (deferred): fixture-path walk (6 levels via #filePath) is brittle if the test file moves (fails loudly)
- Task 2: dispatched implementer (sonnet), BASE 6d51ac8c
- Task 2: implementer DONE (d8b1585a). Controller verified 22/22 swift tests, clean tree.
- Task 2: complete (commits 6d51ac8..d8b1585, review clean; contract matches endpoints.py field-by-field)
- Task 2: minor (deferred): try? swallows a malformed 2xx register body (LiveActivityAPI.swift:131); apiBaseUrl persisted before register succeeds (:124); device id not percent-encoded in the DELETE path (:155); LocalStart.attributes [String:String] strict; not Sendable (strict concurrency)
- Task 3: dispatched implementer (sonnet), BASE d8b1585a
- Task 3: implementer DONE (ef229cc5). Controller verified: --check OK; second --apply byte-identical (md5 9fb00df927e5); yaml loads (3 workflows); both plists load; App NSSupportsLiveActivities true; the widget is a widgetkit-extension.
- Ruling T3-1: "Widget profilini hedefe zorla ata" sits AFTER `xcode-project use-profiles` (spike-proven order), not before "Apple Sertifikalarini Hazirla" as the brief said — the step needs the installed profiles — cost if wrong: none (non-fatal step).
- Note: production workflow doesn't rewrite versions; App and PlannWidgets MARKETING_VERSION/CURRENT_PROJECT_VERSION must be bumped together (the owner's release process).
- Ruling T5-1 (corrected before dispatch): CREATE PlannLiveActivityPlugin.m in the CAP_PLUGIN style — production has FCMTokenPlugin.m and ContactPickerPlugin.m in the App target (verified); my first reading was wrong — cost if wrong: none
- Task 3: complete (commits d8b1585..ef229cc, review clean; production workflow change additive-only)
- Task 3: minor (deferred): force-assign patch checks `head` of buildSettings for CODE_SIGN_IDENTITY (possible duplicate key); production releases must bump the extension's MARKETING_VERSION/CURRENT_PROJECT_VERSION together with the app (no sync step); widget-profile block duplicated in 2 workflows; production build calls the ASC API each run until a widget profile is installed
- Task 4: dispatched implementer (sonnet), BASE ef229cc5
- Ruling T7-0 (plan amendment): Task 7 adds a backend `GET /api/live-activities/preferences` (JWT) returning `{enabled, scope, slot_count, start_alert, can_choose_scope, can_choose_slots}`, computed with the existing eligibility helpers (effective_scope / slot_count / is_manager / admin_provides_service + org_has_staff), with pytest tests. Reason: App.js loads currentUser only for admins (App.js:582-593), so the client can't compute role/manager/org-staff visibility for staff; the server owns the rules (single source of truth). Cost if wrong: one small read-only endpoint.
- Task 4: implementer DONE (182ed75f). Controller verified: all §6.0 copy strings present; no scaleEffect/strikethrough/la-spike/SPIKE; clean tree.
- Task 4: complete (commits ef229cc..182ed75, review clean; faithful port, no visual drift)
- Task 4: minor (deferred): minimal Dynamic Island presentation draws the "P" ring for .empty (removed/unknown) — should be empty (AppointmentLiveActivity.swift:137); un-reindented if bodies
- Task 5: dispatched implementer (opus — native integration without a compiler), BASE 182ed75f
- Task 5: implementer DONE_WITH_CONCERNS (c2461ad1 core helpers, 3e7cc7f5 native). Controller verified 37/37 swift, --check OK, clean tree.
- Task 5: review → Needs fixes (0 compile errors expected; security clean). Important #1 unregister race can start the previous user's cards on iOS 16.2–17.1; #2 failed token post lost forever; #3 getStatus <16.2 returns enabled:false → false banner.
- Ruling T5-2 (load-bearing cross-task gap, included in fix round 1): lost register response → device never gets a secret. Client fix in performRegister: if !newSecret && !hasSecret → unregister(jwt) then register once more — cost if wrong: one extra DELETE+POST in a rare case.
- Ruling T5-3: Minors #1 (unregister without jwt still ends all and deletes the secret) and #2 (chain unregister on registerTail) are folded into Important #1's fix (same code; they prevent the same race).
- Task 5: minor (deferred): Keychain read error → deviceId overwrite (SecretStore not-found vs error); ThisDeviceOnly keychain class = owner decision; server-side dedupe of tokens across device rows; DECODE error code; apiBaseUrl https validation; beginBackgroundTask closure fallback if the compile fails; .pending via String(describing:); doubled foreground reconcile.
- Task 5: fix round 1/5 (4 addressed, 0 open — unregister guard + FIFO; token re-post; getStatus <16.2; register recovery; commit 233b22ba). Controller verified 44/44 swift, --check OK.
- Task 5: minor (deferred): live token-observer postToken not guarded during unregister (harmless); postedTokens may re-add a stale entry; possible duplicate token post (endpoint idempotent)
- Task 5: complete (commits 182ed75..233b22b, review clean after fix round 1)
- Task 6: dispatched implementer (sonnet), BASE 233b22ba
- Task 6: implementer DONE (d19f15c0). Controller verified: jest src/native+src/lib green; hook at App.js:102 after token (useAuth, :73) and settings (:100) — no TDZ.
- Task 6: complete (commits 233b22b..d19f15c, review clean; App.js +2 lines)
- Task 6: minor (deferred): after supported:false the session ref stays set (no-op reconcile/unregister on iOS<16.2) (useLiveActivities.js:171); org flag true→false doesn't unregister (flag-off semantics; whole-branch decision); vacuous assertion at test :347; no account-switch / same-sub refresh tests
- Task 7: dispatched implementer (sonnet), BASE d19f15c0
- Task 7: implementer DONE (2a0db72e backend GET preferences, 044c05e3 UI). Controller verified: backend 393 passed; jest LiveActivity+native+lib 34/34; production craco build 'Compiled successfully'; craco.config.js change reverted (not in commit); copy strings present.
- Task 7: review → Approved with Important #1: the settings labels deviate from the owner-decided wording (scope "Sadece benim randevularım / Tüm personelin randevuları"; alert "Randevu başladığında sesli uyarı") → fix round 1.
- Task 7: minor (deferred): admin on scope own sees slot select = 1 (server effective) (LiveActivitySettings.js:559); forced-all/privileged computed inline in GET, not shared with PUT (endpoints.py:286-290); consent sheet uses fixed zinc/white classes — not theme-aware for dark mode (CLAUDE.md light/dark) → final review triage
- Task 7: fix round 1/5 (1 addressed — owner-approved labels; commit 90bf3825). Controller verified the 4 tr strings and jest 35/35.
- Task 7: complete (commits d19f15c..90bf382, review clean after fix round 1)
- Task 8: OWNER — Codemagic `ios-live-activities-beta` build + device QA; requires the Phase 1 backend deployed (flag off) and one internal test org enabled. Not executable by the controller.
- ALL CODE TASKS (1–7) COMPLETE. Final whole-branch review dispatched (opus), range 473e0095..HEAD.
- Final review (opus): Critical none; Important 4 (Capgo OTA can replace the beta JS; logout unregister races page navigation; fresh-install fcm_token null never re-sent; Keychain class allows backup cloning); MUST-FIX-BEFORE-MERGE: production version-sync step, slot select only for scope all, ThisDeviceOnly; compile hedges #1–#3. Report: final-review-report.md
- Ruling F1: Keychain class → kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly — the owner pre-approved "whatever needs doing, professionally" while away, no production Keychain items exist yet, and a backup-cloned device_id breaks the iPhone's cards — cost if wrong: one constant; after a restore to a new phone the device re-registers (the designed recovery path)
- Ruling F2: Capgo — the beta workflow sets plugins.CapacitorUpdater.autoUpdate=false in the generated ios/App/App/capacitor.config.json after cap sync; production config untouched — cost if wrong: the beta lacks OTA (intended)
- Ruling F3: Minor #4 (background reconcile on 16.2–17.1 can claim local starts the device ignores / `foreground` field) deferred — needs a backend contract change; rare; the server's lost-start expiry (120 s) self-heals — cost if wrong: a slot stuck ≤120 s
- Ruling F4: the fix wave also includes Minors 1,2,3,5,6,7, the T4 empty-ring one-liner and compile hedges #1–#3 (#2 only as the safe local-id form) — all cheap and local — cost if wrong: small extra diff
- Final fix wave dispatched (sonnet→opus: native without compiler), FIX_BASE 90bf3825
- Final fix wave: DONE_WITH_CONCERNS (90bf382..d00e0f0, 8 commits). Controller verified: swift 51/51, jest 52/52, --check OK, yaml/plists OK, clean tree. Scoped re-review dispatched.
- Scoped re-review (opus): A–M all ADDRESSED, no new Critical/Important. Swift App shapes type-checked with mocks (swift 5/6/strict) — 0 diagnostics. Controller verified: backend 393 passed (backend dir, --ignore integration/test_user_identity: venv lacks dotenv/jose), web build exit 0 (only pre-existing ReactPixel source-map warning).
- Ruling R1: parked — the background-task double end after expiry is harmless (iOS logs only) — cost if wrong: a console log line
- Ruling R2: parked — without an FCM token (push permission denied) the hook re-registers once per foreground for the session; idempotent POST, no cap — cost if wrong: one small request per app resume for those users
- Ruling R3: parked — a theoretical re-register racing logout within the push-unsubscribe round-trip; the next app-start reconcile/owner-change handles it — cost if wrong: in a very rare case one logged-out device keeps cards until the next login/owner change
- Ruling R4: parked — the coordinator start() still observes ActivityKit on iPad (no registration, no secret) — cost if wrong: negligible idle work
- FINAL REVIEW CLEAN. Branch feature/live-activities-ios 473e0095..d00e0f05 (19 commits). Not pushed/merged.
