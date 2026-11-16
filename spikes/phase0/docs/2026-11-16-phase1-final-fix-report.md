# Final whole-branch review — fix report (Live Activities Phase 1 backend)

Branch: `feature/live-activities-phase1` (worktree `scratchpad/la-phase1`). Production tree untouched;
nothing pushed, no server started, no real push sent. No subagents.

Status: **DONE** — all 11 findings fixed, each with tests that failed before and pass after.

## Commits (oldest first)
| commit | findings |
|---|---|
| `1c0e6370` fix(live-activity): dismissed card stays hidden after slot count drop | #1 |
| `028bb4d8` fix(live-activity): out-of-scope card ends now with removed stub; 8 h restart needs push-to-start | #3, #11 |
| `5fee09c1` fix(live-activity): end live cards when the org flag is off or the user is inactive | #2 |
| `2848dd09` fix(live-activity): iOS 18 input-push-token, local start attributes and budget, day open on switch | #4, #8, #9, #10 |
| `e5452449` fix(live-activity): owner change ends the previous owner's cards | #5 |
| `258c9761` fix(live-activity): pilot flag is operator-only; unknown name mode is initials | #6 |
| `fd399208` fix(live-activity): skip appointments with a non-numeric duration | #7 |

## Per finding

### #1 Dismissed card reappears after slot-count drop (planner.py)
Change: `hidden = {appointment_id of every slot dismissed today}`; `top = [v for v in visible if v.id not in hidden][:n_slots]`.
The old in-range-only "held by dismissed slot" set is gone (now `held = set()`), so an out-of-range dismissed slot
neither reappears nor consumes a top-N place.
Test: `test_live_activity_planner.py::test_dismissed_card_not_reopened_after_slot_count_drop` (reviewer repro n=3 → [], n=2 → [];
plus out-of-range dismissed slot does not take a top-N place → slot 2 starts `w`, not `x`).
RED:
```
E       AssertionError: assert [Action(kind=...smissal=None)] == []
E         Left contains one more item: Action(kind='update', slot_index=2, appointment_id='x', phase=<Phase.PROCESSING: 'processing'>, priority=10, alert=None, relevance=100.0, dismissal=None)
FAILED tests/test_live_activity_planner.py::test_dismissed_card_not_reopened_after_slot_count_drop
```
GREEN: `1 passed, 20 deselected in 0.04s`

### #2 Stuck cards when org flag off / user inactive or missing (sweeper.py)
Change:
- `_end_live_slots(db, device, …)`: for each slot in `start_sent/active` with an `update_token`, plans
  `Action("end", …, Phase.REMOVED, …, "now")` and runs it through the existing `_execute` (claim CAS → `_same_owner` → send →
  state `ended`). Removed stub content, dismissal now.
- `_sweep_device`: user missing or inactive → `_end_live_slots` (before, it silently returned).
- `run_sweep` → `_end_disabled_orgs`: lists usable slots first (`{"state": {"$in": [active, start_sent]}}`, projection
  device_id/update_token); only if some have tokens are their devices fetched; devices whose org is not among the enabled
  (flag on) settings — flag off or settings missing — get `_end_live_slots`. On the hook path (`org_ids`) only those orgs are
  considered. Errors are counted and logged, never raised. `stats.orgs` still counts only enabled orgs.
Tests: `test_inactive_user_device_slots_ended` (replaces `test_inactive_user_device_skipped`: no slots → no sends; live slot →
one removed/now end, token-less start_sent and ended slots untouched, no repeat), `test_missing_user_device_slots_ended`,
`test_flag_off_org_ends_live_slots` (flag false, flag key missing, no settings doc; enabled org still starts; hook path ends only
the asked org).
RED:
```
E       AssertionError: assert [] == [('end', 'tok1')]
E       AssertionError: assert [] == [('end', 'tok1')]
E       AssertionError: assert [('start', 'pts-d1')] == [('end', 'tok...t', 'pts-d1')]
E         At index 0 diff: ('start', 'pts-d1') != ('end', 'tok2')
FAILED tests/test_live_activity_sweeper.py::test_inactive_user_device_slots_ended
FAILED tests/test_live_activity_sweeper.py::test_missing_user_device_slots_ended
FAILED tests/test_live_activity_sweeper.py::test_flag_off_org_ends_live_slots
3 failed, 24 deselected in 0.44s
```
GREEN: `4 passed, 23 deselected in 0.30s`

### #3 Out-of-scope appointment ends "soon" with live-looking data (planner.py + sweeper.py)
Change: when a slot has nothing to show (`v is None`): if its appointment is in `final_phases` (completed/cancelled) or still
visible → `end(s, "soon")` as before (final content); otherwise → `Action("end", …, Phase.REMOVED, …, dismissal "now")`.
`_end_content` treats `action.phase is Phase.REMOVED` as removed (no appointment lookup) → `removed_content` stub.
Existing tests that encoded the old "soon" behavior were updated to the spec: `test_idle_slot_ends_soon_at_day_end` (second
half), `test_rescheduled_out_of_day_leaves_slot`, `test_reassignment_moves_between_staff_devices` (Elif's end is now
`REMOVED`/`now`).
Tests: planner `test_out_of_scope_appointment_ends_now_removed` (none / INELIGIBLE → removed now; COMPLETED / CANCELLED → soon);
sweeper `test_reassigned_away_ends_now_with_removed_stub` (Elif→Can: dismissal = timestamp, phase removed, no customer/service/
staff/time), `test_completed_still_ends_soon_with_final_content` (Tamamlandı: completed, "Ayşe K.", now+900).
RED (together with #11):
```
E       AssertionError: assert [('end', 1, '...0, None, ...)] == [('end', 1, '...0, None, ...)]
E         At index 0 diff: ('end', 1, 'a', <Phase.UPCOMING: 'upcoming'>, 10, None, 'soon') != ('end', 1, 'a', <Phase.REMOVED: 'removed'>, 10, None, 'now')
E       assert 1794813300 == 1794812400
FAILED tests/test_live_activity_planner.py::test_out_of_scope_appointment_ends_now_removed
FAILED tests/test_live_activity_sweeper.py::test_reassigned_away_ends_now_with_removed_stub
```
(`test_completed_still_ends_soon_with_final_content` passed before and after: it guards the unchanged path.)
GREEN (#3/#11 plus the updated tests): `7 passed, 41 deselected in 0.31s`

### #4 `input-push-token` on every push-to-start (sweeper.py)
Change: `_supports_input_push_token(os_version)` — `int(str(v).strip().split(".")[0]) >= 18`, TypeError/ValueError → False.
Test fixture `device()` now defaults `os_version="26.0"` (real devices always send it; keeps the existing start assertions).
Test: `test_input_push_token_only_on_ios18_plus[...]` — absent for "17.5", "17.4.1", None, "", "beta"; present for "18.0",
"18", "26.0", " 18.2 ".
RED: `FAILED …test_input_push_token_only_on_ios18_plus[17.5-False]`, `[17.4.1-False]`, `[None-False]`, `[-False]`, `[beta-False]`
(each `AssertionError: assert ('input-push-token' in {...}) is False`).
GREEN: see combined line below.

### #5 Owner change leaves A's cards on B's lock screen (registry.py + endpoints.py)
Change: `upsert_device(..., ended_slots: list | None = None)` — return contract `(row, new_secret)` unchanged; on an owner change
the previously live slots with tokens (new helper `_live_slots`, shared with `remove_device`) are appended before the
end/version bump. `register_device` passes a list and calls `_end_now(row, token, version=old+1)` for each (removed stub,
dismissal now) — same as logout. No other callers needed changes.
Tests: `test_live_activity_registry.py::test_reowned_device_exposes_live_slots_to_end` (same owner → nothing; new owner →
only the active slot with token), `test_live_activity_endpoints.py::test_device_reowned_ends_previous_owners_cards` (ali →
veli on d1: one end to `tok-1` via `fcm-d1`, phase removed, no customer/service/staff, dismissal = now, version 4).
RED:
```
E       TypeError: upsert_device() got an unexpected keyword argument 'ended_slots'
E       AssertionError: assert [] == [('fcm-d1', 'tok-1', 'end')]
FAILED tests/test_live_activity_registry.py::test_reowned_device_exposes_live_slots_to_end
FAILED tests/test_live_activity_endpoints.py::test_device_reowned_ends_previous_owners_cards
2 failed, 2 passed, 37 deselected, 1 warning in 0.81s
```
GREEN: `4 passed, 37 deselected, 1 warning in 0.68s`

### #6 Pilot flag is operator-only (server.py update_settings) + unknown name mode
Change: one line in `update_settings` right after `update_data = settings.model_dump(exclude_unset=True)`:
`update_data.pop("live_activity_enabled", None)`. Nothing else in the endpoint changed; lead minutes and name mode still pass.
content.py: `name_mode(mode)` → mode if in `("initials","full","hidden")` else `"initials"`; `display_name` uses it, and
`load_org` sets `privacy_mode=name_mode(...)` so the widget's `privacyMode` is normalized too.
Tests: `test_live_activity_wiring.py::test_tenant_settings_update_cannot_set_pilot_flag` (text scan: pop between the dump and
the `db.settings.update_one`; lead/name mode not stripped), `test_live_activity_content.py::test_unknown_name_mode_is_initials`,
`test_live_activity_endpoints.py::test_widget_unknown_name_mode_reported_as_initials`.
RED:
```
E       ImportError: cannot import name 'name_mode' from 'live_activity.content' (...)
E       AssertionError: assert 'Full Name' == 'initials'
E       ValueError: substring not found
FAILED tests/test_live_activity_content.py::test_unknown_name_mode_is_initials
FAILED tests/test_live_activity_endpoints.py::test_widget_unknown_name_mode_reported_as_initials
FAILED tests/test_live_activity_wiring.py::test_tenant_settings_update_cannot_set_pilot_flag
3 failed, 45 deselected, 1 warning in 0.84s
```
GREEN: `3 passed, 45 deselected, 1 warning in 0.57s`

### #7 Non-int duration raises TypeError (eligibility.py, sweeper.py, widget_summary.py; phase.py docstring)
Change: every `except (KeyError, ValueError)` around phase/window computation now also catches `TypeError` (eligibility
`visible_for_user` with debug log, sweeper `_final_phases` and `_end_content`, widget counts).
Tests: `test_live_activity_eligibility.py::test_non_int_duration_skipped`, `test_live_activity_sweeper.py::test_non_int_duration_does_not_kill_device_sweep`,
`test_live_activity_endpoints.py::test_widget_non_int_duration_skipped_not_500`.
RED:
```
E       TypeError: unsupported type for timedelta minutes component: str
E       assert 1 == 0
ERROR    live_activity.sweeper:sweeper.py:533 live activity sweep: device d1 failed
E       TypeError: unsupported type for timedelta minutes component: str
FAILED tests/test_live_activity_eligibility.py::test_non_int_duration_skipped
FAILED tests/test_live_activity_sweeper.py::test_non_int_duration_does_not_kill_device_sweep
FAILED tests/test_live_activity_endpoints.py::test_widget_non_int_duration_skipped_not_500
3 failed, 81 deselected, 1 warning in 1.33s
```
GREEN: `3 passed, 81 deselected, 1 warning in 0.64s`

### #8 `start_locally` items carry attributes (sweeper.py)
Change: each item gets `"attributes": {"slotId": "<device_id>:<n>", "orgId": "<org>"}` (shared `_slot_attributes` helper, also
used for the push-to-start payload).
Test: `test_start_locally_items_carry_attributes`. RED: `E       KeyError: 'attributes'`.

### #9 Local starts must not call `record_start` (sweeper.py)
Change: `record_start` removed from `start_locally` (comment explains why).
Test: `test_start_locally_does_not_spend_push_to_start_budget` (two local starts, `start_log == []`, day opened).
RED: `E       assert [1794812400.0, 1794812400.0] == []`.

### #10 Day open only via a start (sweeper.py)
Change: on a successful send, the device day is also opened when an `update` lands on an appointment whose start is today (TR);
the in-memory device snapshot is updated so it is written once per sweep.
Tests: `test_switch_to_todays_appointment_opens_the_day` (slot carried over from yesterday switches to 10:20 → day = today; then
the 13:00 appointment outside the lead window follows), `test_update_of_yesterdays_appointment_does_not_open_the_day`
(processing past midnight stays yesterday's).
RED: `E       AssertionError: assert '2026-11-15' == '2026-11-16'` / `FAILED …test_switch_to_todays_appointment_opens_the_day`.

Combined RED for #4/#8/#9/#10: `8 failed, 5 passed, 27 deselected in 0.63s` (the 5 passing are the iOS ≥ 18 cases).
Combined GREEN (#4/#8/#9/#10 + `test_fcm_success_does_not_mark_active`): `14 passed, 26 deselected in 0.33s`

### #11 8 h restart end only with push-to-start (planner.py)
Change: the restart `end(s, "now")` requires `has_push_to_start`.
Test: `test_8h_restart_only_with_push_to_start`.
RED:
```
E       AssertionError: assert [Action(kind=...missal='now')] == []
E         Left contains one more item: Action(kind='end', slot_index=1, appointment_id='b', phase=<Phase.UPCOMING: 'upcoming'>, priority=10, alert=None, relevance=0.0, dismissal='now')
FAILED tests/test_live_activity_planner.py::test_8h_restart_only_with_push_to_start
```
GREEN: in the #3/#11 line above.

## Reviewer probes after the fixes (`review-checks/`)
```
--- probe planner
count 3, dismissed x in slot3: []
count 2, dismissed x in slot3: []
reassigned away: [('end', 1, 'a', <Phase.REMOVED: 'removed'>, 10, None, 'now')]
--- probe sweeper
(a) flag off, active slot -> sends: [('end', 'tok')] state: ended
(b) user deactivated -> sends: [('end', 'tok')] state: ended
(c) iOS 17.4 start input-push-token: None
(d) reassigned away end: phase removed customer None dismissal-now 0
(e) owner change: slot state ended token kept tok (no transport call in upsert path)
```
(e) calls `upsert_device` directly, so it still shows no send; by design the end pushes are sent by `register_device`
(covered by `test_device_reowned_ends_previous_owners_cards`).

## Verification
Live Activity tests: `167 passed, 1 warning in 1.43s` (139 before).
Full suite (`.testvenv/bin/pytest -q --ignore=tests/integration --ignore=tests/test_user_identity.py`):
```
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
388 passed, 1 warning in 2.02s
```
(360 before + 28 new test cases.)
`.testvenv/bin/python -m py_compile server.py` → `py_compile server.py: OK`

## Notes / concerns
- No finding left unfixed.
- #2 cost: every sweep now runs one extra `live_activity_slots.find` over slots in usable states (no index on `state`). Only
  enabled orgs open slots, so at pilot scale this is a handful of rows; the device lookup runs only when token-bearing
  usable slots exist. If the slots collection grows, add an index on `state`.
- #2: a `start_sent` slot with no token in a disabled org cannot be ended (no token). If its token arrives later, it becomes
  `active` and the next sweep ends it. Lost-start expiry does not run for disabled orgs (no data is shown, so this is harmless).
- #3: any non-final, non-visible slot appointment now ends removed/now. That includes one whose duration or date cannot be
  parsed (it was already treated as removed by `_end_content`).
- #5: `upsert_device` keeps the `(row, secret)` return; the old owner's slots come back through the new optional
  `ended_slots` out-list.
- #6: only `PUT /api/settings` takes a `Settings` body (grep), so no other tenant write path sets the flag. `GET /api/settings`
  still returns the flag (read-only for tenants).
