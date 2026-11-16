# SDD ledger — plan: /tmp/claude-0/-var-www-player5moduleryapi/53f81d0e-4c9d-49e9-b05f-cc6c0967bae9/scratchpad/spike-phase0/spikes/phase0/docs/2026-11-16-live-activities-phase1-backend-plan.md

Spec: same dir, 2026-11-15-live-activities-widgets-design.md (§3A D12, §5, §6.0, §13 D2c). Worktree: scratchpad/la-phase1, branch feature/live-activities-phase1 from main 80a94706. Never push, merge or deploy.

## Task 0 (controller): done
- Venv: backend/.testvenv (gitignored by repo), python3.12 with pins fastapi 0.110.1, starlette 0.37.2, pydantic 2.12.3, motor 3.3.1, pymongo 4.5.0, pytest 8.4.2, pytest-asyncio 0.25.3 (asyncio_mode=auto via pytest.ini), firebase-admin 7.1.0, httpx, redis 5.0.8.
- Baseline: `.testvenv/bin/pytest -q --ignore=tests/integration --ignore=tests/test_user_identity.py` gives **221 passed**. The two ignored modules fail collection on missing deps (dotenv etc.); pre-existing and out of scope.
- Ruling: minimal pinned venv instead of the full requirements.txt — prod uses python 3.10 in Docker and the host has only 3.12; the new code imports only these packages — cost if wrong: a 3.10-only incompatibility surfaces at integration (the owner's docker test before merge).

## Pre-flight scan

| Pair / task | Produces vs consumes | Finding |
|---|---|---|
| T1→T2,T3,T6 | Phase, compute_phase, appointment_window, resolve_duration, TR_TZ | consistent |
| T2→T6,T7,T8 | VisibleAppt(id, phase, start, end, apt), visible_for_user, effective_scope, slot_count, effective_lead_minutes | **F1** midnight-crossing processing appointment excluded by "same TR day" filter |
| T3→T5,T7 | build_aps(alert=…) vs transport.send(alert=…) | **F2** alert in two places; T3 test expects alert inside start aps |
| T3→T6 | relevance, stale_epoch | consistent |
| T4→T6,T7,T8 | slot dict fields (state, appointment_id, update_token, started_at, day, version, content_hash, phase_sent); apply_device_report(complete=) | consistent |
| T5→T7 | SendResult, LiveActivityTransport, RecordingTransport | consistent |
| T6→T7 | Action(kind, slot_index, appointment_id, phase, priority, alert, relevance, dismissal) | consistent; T7 maps alert kind → copy (see F2 ruling) |
| T7→T8 | resync(db, org_id) | consistent |
| T8→T9 | router, configure(get_current_user, get_db) | consistent |
| T1 self | tests vs signatures | ok |
| T2 self | `test_day_open_shows_rest_of_day` vs filter | ok after F1 |
| T3 self | `test_start_has_slot_attributes_and_alert` vs F2 | conflict → F2 ruling |
| T4 self | fake collection ops list vs functions | ok |
| T5 self | ok | ok |
| T6 self | `test_replays_sim_day_scenario` needs sim times | ok (RESULTS 24 + sim_day.py in spike dir) |
| T7 self | ok | ok |
| T8 self | ok | ok |
| T9 self | text-scan test of server.py | acceptable (import-light by design) |

**Rulings:**
- **F1:** `visible_for_user` keeps every appointment whose phase is PROCESSING, regardless of date. The same-TR-day filter applies to UPCOMING only. Reason: the spec's Review Focus covers midnight crossing (orig Task 1), and a processing card must not vanish at 00:00. Cost if wrong: a 23:40 appointment drops at midnight.
- **F2:** `build_aps` does **not** carry the alert. The alert travels only via `transport.send(alert=…)` as `Aps(alert=ApsAlert)`, which is the encoding validated on device in S1. Task 3 adds `format_alert(kind: Literal["start","processing"], content: dict) -> tuple[str, str]` (it uses `customerDisplay`, `serviceName`, `startLabel`; it drops `"{name} · "` when `customerDisplay` is None). The test `test_start_has_slot_attributes_and_alert` becomes `test_start_has_slot_attributes_no_inline_alert` plus `test_format_alert_copy_and_hidden_mode`. Reason: there must be a single source for the alert, and S1 proved this path. Cost if wrong: a trivial move.

## Tasks
- Task 1: dispatched implementer (haiku), BASE 80a94706
- Task 1: complete (commits 80a9470..345c2f7, review clean; Minor: missing date key raises KeyError not ValueError, carried into Task 2 as "catch (KeyError, ValueError)")
- Task 2: dispatched implementer (sonnet), BASE 345c2f7d
- Ruling T2: slot_count None→4, any int clamped 1..5 (0→1) — brief test list explicit; formula 'or 4' contradicted it — cost if wrong: trivial
- Task 2: complete (commits 345c2f7..99e8850, review clean). Parked Minor (carry to final review / Task 8): visible_for_user treats any scope ≠ "own" as all (fail-open on typo) — endpoints/registry must only ever pass effective_scope() output; final review to confirm.
- Task 3: dispatched implementer (sonnet), BASE 99e88509
- Task 3: review → Needs fixes (Important: serviceName not truncated to 40; the test asserted failure instead).
- Task 3: minor (deferred): customerDisplay/staffName uncapped length (content.py:91)
- Task 3: minor (deferred): upcoming relevance > 50 when start already passed (content.py:71) — consider clamp ≤ 50
- Task 3: minor (deferred): test uses `price` not real field `service_price` (test_live_activity_content.py:202)
- Task 3: fix round 1/5 (1 addressed, 0 open — serviceName[:40]; commits 536c3df..fc93b11). Controller verified 15/15 content tests pass, format_alert uses truncated content["serviceName"].
- Task 3: minor (deferred): truncation at 40 code points may split a grapheme cluster (cosmetic)
- Task 3: complete (commits 99e8850..fc93b11, review clean after fix round 1)
- Task 4: dispatched implementer (sonnet), BASE fc93b111
- Ruling F3 (Task 5): invalid_token only for UnregisteredError/'registration-token-not-registered'; invalid-argument → error, token kept — payload bugs must not wipe all slot tokens — cost if wrong: dead token retried until re-register (harmless)
- Task 4: complete (commits fc93b11..5e79009, review clean). Controller verified 13/13 registry tests, 279 suite.
- Task 4: minor (deferred → carry to Task 7): apply_device_report updates slots without version bump/state filter; concurrent claim_slot could overwrite report-driven ended/dismissed (registry.py:121-150)
- Task 4: minor (deferred): concurrent first registration can issue two secrets (second wins) (registry.py:49-72)
- Task 4: minor (deferred): no test for stale expect_version → False; fake has dead helpers
- Task 5: dispatched implementer (haiku), BASE 5e790099
- Task 5: complete (commits 5e79009..463ecd7, review clean; reviewer confirmed real UnregisteredError detected by type).
- Task 5: minor (deferred): error=str(exc) may be empty / drops type — prefer f"{type}: {exc}"; test uses bare FirebaseError for invalid-argument
- Task 6: dispatched implementer (opus — core algorithm), BASE 463ecd77
- Task 6: implementer DONE_WITH_CONCERNS (commit e1754824; 20/20 planner, 304 suite). Rulings:
  - Ruling T6-1: accept optional `final_phases: Mapping[str, Phase] | None` kwarg on plan_device — needed to tell completed or cancelled from moved — Task 7 must pass it — cost if wrong: end cards repeat last phase.
  - Ruling T6-2: starts count toward one-alert-per-sweep (≤1 start per sweep, deferred if a processing alert fires) — same total sounds, ≤90 s stagger inside a 30 min lead, protects start budget — cost if wrong: slower first open.
  - Ruling T6-3: held appointment keeps its slot only while in the top N (spec "take N") — accept.
  - Ruling T6-4: drop the spec's "≤ 2×N starts/day" expectation; the hourly budget (8/h) is the enforced guard — cost if wrong: theoretical extra starts on chaotic days, still capped hourly.
- Task 6: complete (commits 463ecd7..e175482, review clean — Approved, 0 Critical/Important).
- Task 6: minor (deferred — LIKELY MUST-FIX at final review, owner decision "a dismissed card is not reopened that day"): dismissed-today hold built from in_range only → after count drop a dismissed appointment reappears in another slot (planner.py:80; fix: build from `ordered`)
- Task 6: minor (deferred): slot above lowered count without token doesn't hold its appointment → brief duplicate card (planner.py:73-94)
- Task 6: minor (deferred): 8 h restart planned even without push-to-start → card ended and never reopened (planner.py:106-109; gate on has_push_to_start)
- Task 6: minor (deferred): replay (c) doesn't assert a4 visible during waiting ticks (test :330)
- Task 6: Ruling (load-bearing, carried to Task 7): a lost push-to-start must not lock a slot all day — Task 7 expires `start_sent` slots with no token after 120 s (state → ended; reopen subject to the hourly budget) — cost if wrong: a lost start hides one appointment on that device all day.
- Task 7: dispatched implementer (opus), BASE e1754824
- Task 7: implementer DONE_WITH_CONCERNS (commits c21fd5c3 registry $inc + shared fakes, 9270f8a3 sweeper; 19 sweeper + 14 registry; 324 suite). Fake now yields per call so race tests can fail. Rulings:
  - Ruling T7-1: a start clears the slot's old update_token — a new activity gets a new token — accept.
  - Ruling T7-2: an invalid token on update/end sets the slot to ended — the activity is gone; avoids an all-day block — accept.
  - Ruling T7-3: every start attempt counts toward the hourly budget, failures included — conservative — cost: fewer retries.
  - Ruling T7-4: a deleted appointment gets a `removed` stub end with dismissal now (spec §1) — accept. PHASE 3 NOTE: Swift must decode empty labels / removed phase.
- Task 7: review → Needs fixes. Important #1: record_slot_token doesn't bump version → lost-start expiry CAS can overwrite a just-active slot → duplicate card (reproduced by reviewer). Ruling: authorize editing registry.record_slot_token to $inc version + interleaving test.
- Task 7: minor (deferred): no try/finally between claim and outcome (CancelledError leaves claimed fields; record_start skipped) (sweeper.py:249-283)
- Task 7: minor (deferred): rollback/invalid-token revert CAS results ignored, add logging (sweeper.py:276,283)
- Task 7: minor (deferred): exclusion projection still loads address/services — prefer inclusion projection (sweeper.py:38)
- Task 7: minor (deferred): unreadable appointment silently treated as removed — add warning (sweeper.py:196-201)
- Task 7: minor (deferred): device user resolved by username not user_id (sweeper.py:293)
- Ruling (carried to Task 8): a late token (record_slot_token returns False because the slot already expired/ended) → the token endpoint sends an `end` (dismissal now, relevance 0, last known content or removed stub) to that orphan activity's token, so no orphan card lingers.
- Ruling (Task 7 round 1 extension): owner-change update_many in upsert_device also $inc version — privacy (old owner's appointments must never be pushed to a re-owned device mid-sweep) — cost if wrong: none
- Task 7: fix round 2/5 authorized — re-read the device after a successful claim and before send; if user_id/organization_id changed, skip the send and CAS the slot back to ended (closes the insert-path owner-change leak) — cost: one extra read per action
- Task 7: parked — re-own landing exactly while a push is in flight can still slip one push — Ruling: accept; closing needs a device-level lock (disproportionate); logout/re-register ends slots immediately after
- Task 7: fix round 1–2/5 (3 addressed, 0 open — token $inc version; owner-change $inc; owner re-check before send; commits 9270f8a..16c38e6)
- Task 7: complete (commits e175482..16c38e6, review clean after fix rounds; 37 sweeper+registry, 328 suite)
- Task 8: dispatched implementer (opus — auth endpoints), BASE 16c38e66
- Task 8: implementer DONE_WITH_CONCERNS (commit 900b4127; 20 endpoint + 3 registry tests; 351 suite). Touched registry (active report no longer changes state; token rotation + logout helpers), sweeper (refactor for reuse), eligibility (public scope helper), fakes (delete_one). Concerns logged as minor (deferred):
- Task 8: minor (deferred): reconcile has no foreground flag → a background call can reserve slots ~120 s
- Task 8: minor (deferred): a complete report can end a just-sent push-to-start → one extra start next sweep
- Task 8: minor (deferred): any authenticated user knowing a device_id (random UUID) can re-register it → disrupts the old owner's LAs only (no data leak: pushes go to the new registrant's tokens)
- Task 8: minor (deferred): widget drops a still-running appointment at midnight; the LA keeps it (F1 not applied to the widget)
- Task 8: review → Needs fixes. Important #1: a valid device secret is rejected (401) when a stale JWT is also sent; the app's axios interceptor attaches the bearer and auto-logs-out on 401. Important #2: same-index duplicate reports (stale OLD + tracked A1) end the tracked live card under complete=True.
- Ruling T8-R1: reconcile checks X-Plann-Device-Secret FIRST; the JWT is validated only when no secret header is present.
- Ruling T8-R2: the reconcile response adds `end_activities: [activity_id]` for stale/untracked activities; `end: [slot_index]` remains only for indices whose TRACKED activity must end; a tracked report is never dropped because of an untracked sibling. Swift (Phase 3) ends by activity id.
- Task 8: minor (deferred): a dismissed report for a start_sent slot (no activity_id yet) is dropped → day lock lost (endpoints.py:226)
- Task 8: minor (deferred): no rate limit on /token; no-op refresh still triggers an org resync (endpoints.py:183-188)
- Task 8: minor (deferred): logout end pushes awaited inline (≤5 sequential) (endpoints.py:161-162,188)
- Task 8: minor (deferred): preferences loads the full org snapshot (endpoints.py:274)
- Task 8: minor (deferred): dead "active":"active" mapping (registry.py:150)
- Task 8: minor (deferred): deactivated user with a valid JWT can read the widget/preferences (consistent with API; differs from sweeper _active)
- Task 8: minor (deferred, whole-branch): record_slot_token accepts any activity_id on a start_sent slot (an older activity's re-sent token could be recorded)
- Task 8: fix round 1/5 (2 addressed, 0 open — secret-first reconcile auth; per-activity end_activities; commits 900b412..b7b6748)
- Task 8: minor (deferred): alive report with activity_id None silently ignored; token-pending slot accepts all siblings until the token arrives. PHASE 3 NOTE: Swift must handle `end_activities`.
- Task 8: complete (commits 16c38e6..b7b6748, review clean after fix round 1; 353 suite)
- Task 9: dispatched implementer (sonnet — server.py wiring), BASE b7b6748f
- Task 9: implementer DONE (commit e10eaf80). Controller verified: wiring 6/6, py_compile ok, suite 359 passed with 1 warning.
- Task 8: minor (deferred): test hygiene — ResourceWarning unclosed event loop in test_device_reowned_rotates_secret; DeprecationWarning from starlette TestClient (third-party, env)
- Task 9: review → Approved with Important #1: module-level live_activity imports and configure/include_router not guarded (other optional routers use try/except at server.py:17864-17893) → an import error would take the API down. Enters fix loop round 1.
- Task 9: minor (deferred): emit hook create_task reference not kept (reuse endpoints._spawn) (server.py:2404)
- Task 9: minor (deferred, whole-branch): bulk deletes emit N appointment_deleted → N concurrent org resyncs (coalesce per org)
- Task 9: minor (deferred): flag-off sweep still does a Redis SET every 30 s before checking enabled orgs
- Task 9: minor (deferred): wiring test (d) not scoped to the scheduler block
- Task 9: minor (deferred, whole-branch): appointments_bulk_created (server.py:6817) not in hook set; ai_service.py direct sio.emit bypasses the hook (30 s sweep covers)
- Task 9: minor (deferred, whole-branch): new endpoints ignore live_activity_enabled (widget/devices/preferences usable for every org)
- Task 9: minor (deferred): ensure_indexes and add_job share one try
- PRE-MERGE OWNER CHECK: start in the python:3.10 container; check the build log (Dockerfile line 17 `pip install -r requirements.txt || echo` can silently skip pins) and `pip show firebase-admin`.
- Task 9: fix round 1/5 (1 addressed — guarded wiring; commits e10eaf8..e7ae95c)
- Task 9: complete (commits b7b6748..e7ae95c, review clean after fix round 1; 360 suite)
- ALL TASKS COMPLETE. Final whole-branch review dispatched (opus), range 80a94706..e7ae95c1.
- FINAL REVIEW (opus): Ready to merge "With fixes". 0 Critical. Important: #1 dismissed card reappears after count drop (MUST-FIX); #2 stuck cards when flag off / user inactive; #3 out-of-scope (reassigned/rescheduled/ineligible) ends "soon" with live data instead of now+removed stub; #4 input-push-token sent to iOS <18; #5 owner change sends no end push; #6 tenant admin can enable the flag via PUT /api/settings.
- Ruling F-6: the pilot flag is operator-only — strip `live_activity_enabled` from tenant `update_settings`; tenants may set lead minutes and name mode; an unknown `lock_screen_name_mode` is treated as "initials" in content — safest default; spec says rollout per org by us — cost if wrong: re-allow later (one line).
- Ruling F-wave: one fix wave covering Important #1–#6 plus cheap Minors: TypeError on bad durations; start_locally items carry attributes {slotId, orgId}; local starts don't consume the push-to-start budget; day_open also set by a successful switch to today's appointment; 8 h restart only when has_push_to_start.
- Final review triage: all other deferred/parked lines OK-TO-DEFER (see the reviewer's triage); PRE-MERGE OWNER CHECK remains mandatory.
- Final fix wave: 7 commits e7ae95c..fd39920 (fix agent hit a usage limit after writing its report; controller verified 388 passed, py_compile ok, py3.10 syntax ok, report complete, 'No finding left unfixed'). Scoped re-review dispatched (sonnet).
- Final fix wave re-review (sonnet): all 11 addressed, no new Critical/Important. Minor: hidden-but-visible edge ends soon; _end_disabled_orgs queries usable slots every sweep (cheap).
