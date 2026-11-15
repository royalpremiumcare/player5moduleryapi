# PLANN Live Activities & Home Screen Widgets — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give each eligible PLANN appointment its own iOS Live Activity that mirrors the appointment's existing derived phase (upcoming → processing → completed/cancelled), and add iOS/Android Home Screen widgets with a one-tap quick-add into the existing appointment wizard.

**Architecture:** A new backend package `backend/live_activity/` has three parts:
- pure functions that compute the derived phase from `appointments` (read-only);
- a planner that diffs the desired activities against a per-device registry;
- a 30-second APScheduler sweeper plus a change hook in `emit_to_organization`, which send ActivityKit pushes through FCM.

Native code is added as in-app Capacitor plugins, the same pattern as `FCMTokenPlugin`, plus a WidgetKit extension and an Android `AppWidgetProvider`. React only feeds widget snapshots and handles deep links.

**Tech Stack:** FastAPI + Motor + APScheduler 3.11 + Redis (existing), `firebase_admin` 7.1.0 (existing), React 19 + Capacitor 7, Swift/SwiftUI WidgetKit + ActivityKit, Android RemoteViews (framework only).

**Spec:** `/tmp/claude-0/-var-www-player5moduleryapi/53f81d0e-4c9d-49e9-b05f-cc6c0967bae9/scratchpad/2026-11-15-live-activities-widgets-design.md`. Section refs (§) point there.

## Global Constraints

- **Never write `appointments.status`, and never add a status value.** The Live Activity code reads `appointments` and writes only `live_activities`, `live_activity_devices` and new `settings` fields.
- No manual start action anywhere: no button, intent or endpoint that changes a phase.
- Time parse: `"%Y-%m-%d %H:%M"` in `ZoneInfo("Europe/Istanbul")`, identical to `server.py:8154-8155`. The tz is passed as a parameter.
- Duration rule (D3): `apt.service_duration` → `services[service_id].duration` → `30`.
- Live Activity active window ≤ 8 h: effective lead = `min(lead, max(0, 480 − duration − 10))` minutes.
- `live_activity_lead_minutes`: default 30, clamp 5–120. `lock_screen_name_mode` ∈ {`initials` (default), `full`, `hidden`}.
- Payload attributes + content-state ≤ 4096 bytes JSON. `serviceName` is truncated to 40 characters.
- Push priority 10 only for start, PROCESSING transition and end; 5 for everything else.
- `apns-push-type: liveactivity`, `apns-topic: co.plannapp.app.push-type.liveactivity`.
- No auth token and no phone, notes, price or customer id in the App Group or SharedPreferences.
- No new npm, pod or Gradle dependencies. JS must no-op when `Capacitor.isPluginAvailable(...)` is false (OTA JS on old native builds).
- iOS app target stays at 15.0. `PlannWidgets` extension target is 16.2. Bundle `co.plannapp.app.widgets`. App Group `group.co.plannapp.app`.
- Deep link: `plannapp://new-appointment?date=YYYY-MM-DD&time=HH:mm&source=<widget_small|widget_medium|widget_large|intent>` and `plannapp://appointment/<id>`.
- Feature flag `settings.live_activity_enabled` (default `false`). Rollout is per org.
- Env: `LIVE_ACTIVITY_POLL_SECONDS=30`, max 3 start attempts per (device, appointment). **No confirmation timeout exists:** an unresolved `start_sent` is never treated as failure (spec §4.2, Revision 2).
- Live Activity code must never import or call `_auto_complete_pending_for_org`, `get_appointments`, or write `appointments`/`transactions`. A test enforces this (Task 7).
- iOS ActivityKit floor is **16.2** (`@available(iOS 16.2, *)`), and the widget extension deployment target is 16.2.
- Scope defaults: `admin` → `business`; `staff` + `can_view_all_appointments` → `own` (preference may be `business`); `staff` → `own` only. Preference field: `users.live_activity_scope: "own" | "business" | None`.
- All implementation runs in an isolated worktree, with tests executed **off the production host** (`/var/www/player5moduleryapi` is the live deployment and has uncommitted changes).
- iOS MVP = Phases 1–3. Android = Phase 4, separately approved.

## Review Focus

1. **An appointment edited while its Live Activity is mid-PROCESSING** (service changed, so the end moves): expect an in-place update with the new end and no restart. Test: Task 6 `test_service_change_in_processing_updates_not_restarts`.
2. **The same appointment hit by the change hook and the sweeper in the same second:** expect exactly one push. Test: Task 7 `test_hook_and_sweep_race_single_push`.
3. **A device logs into a different user or org:** expect no Live Activity or widget data from the old account to remain. Tests: Task 8 `test_device_reowned_ends_old_rows_and_rotates_secret`, Task 12 `test_logout_clears_snapshot`.
4. **Appointment at 23:40 with 45 min duration** (end crosses midnight): expect a correct end and no premature completion. Test: Task 1 `test_window_crosses_midnight`.
5. **Widget quick-add tapped while the wizard has unsaved input:** expect the form state to be kept and the prefill ignored. Test: Task 11 `test_deeplink_does_not_reset_open_form`.

---

## Phase 0 — Spikes (throwaway, dev build, no merge)

**Status:** kit and partial results are on branch `spike/phase0-live-activities` under `spikes/phase0/` (`RUNBOOK.md`, `RESULTS.md`).
- S1 and S5 passed offline / by code review;
- S4 is partially done (the profile lacks App Groups);
- S2 and S3 have not run and need physical devices.

None of Tasks 1–19 starts before the owner approves the Phase 0 results.

- [ ] **S1 FCM Live Activity transport.** In the Firebase console, confirm that an APNs Auth Key (.p8) is configured. From a script, send `messaging.Message(token=<fcm>, apns=APNSConfig(live_activity_token=<push_to_start>, headers={"apns-push-type":"liveactivity","apns-topic":"co.plannapp.app.push-type.liveactivity","apns-priority":"10"}, payload=APNSPayload(aps=Aps(custom_data={...})))`. Pass: an activity starts on iOS 17.2+.
- [ ] **S2 Background token wake.** With the app force-quit, push-to-start, then confirm that the native `pushTokenUpdates` handler runs and its HTTP POST reaches a request-bin. Test on 17.2 and 18.x.
- [ ] **S3 Concurrency.** Start activities locally and by push until failure, on 2 devices. Record the count, the error case (local) and the device log (push). Do not hard-code the result.
- [ ] **S4 Codemagic signing.** Archive the App + empty `PlannWidgets` extension with the App Group through `codemagic.yaml` on a branch.
- [ ] **S5 Android FCM service.** Confirm that a custom `FirebaseMessagingService` subclassing the `@capacitor/push-notifications` service still delivers JS push events.

---

## Phase 1 — Backend core (no user-visible change while the flag is off)

### Task 1: Derived phase & window

**Files:**
- Create: `backend/live_activity/__init__.py`, `backend/live_activity/phase.py`
- Test: `backend/tests/test_live_activity_phase.py`

**Interfaces:**
- Produces:
  - `class Phase(str, Enum)`: `UPCOMING="upcoming"`, `PROCESSING="processing"`, `COMPLETED="completed"`, `CANCELLED="cancelled"`, `REMOVED="removed"`, `INELIGIBLE="ineligible"`
  - `CANCELLED_STATUSES = {"İptal","İptal Edildi","Cancelled"}`
  - `resolve_duration(apt: dict, services_by_id: dict[str,int]) -> int`
  - `appointment_window(apt: dict, duration_min: int, tz: ZoneInfo = TR_TZ) -> tuple[datetime, datetime]` (raises `ValueError` on bad date/time)
  - `compute_phase(apt: dict | None, now: datetime, duration_min: int, tz: ZoneInfo = TR_TZ) -> Phase`

- [ ] **Step 1: Write failing tests**

```python
NOW_BASE = datetime(2026, 11, 16, 14, 0, tzinfo=TR_TZ)
apt = {"status": "Bekliyor", "appointment_date": "2026-11-16", "appointment_time": "14:30", "service_duration": 45}

def test_upcoming_before_start():      assert compute_phase(apt, NOW_BASE, 45) is Phase.UPCOMING
def test_processing_at_start():        assert compute_phase(apt, NOW_BASE.replace(minute=30), 45) is Phase.PROCESSING
def test_processing_one_sec_before_end(): assert compute_phase(apt, datetime(2026,11,16,15,14,59,tzinfo=TR_TZ), 45) is Phase.PROCESSING
def test_completed_at_end_while_still_bekliyor(): assert compute_phase(apt, datetime(2026,11,16,15,15,tzinfo=TR_TZ), 45) is Phase.COMPLETED
def test_tamamlandi_is_completed_even_before_end(): assert compute_phase({**apt,"status":"Tamamlandı"}, NOW_BASE, 45) is Phase.COMPLETED
@pytest.mark.parametrize("s", ["İptal","İptal Edildi","Cancelled"])
def test_cancelled_statuses(s):        assert compute_phase({**apt,"status":s}, NOW_BASE, 45) is Phase.CANCELLED
def test_payment_pending_ineligible(): assert compute_phase({**apt,"status":"Ödeme Bekleniyor"}, NOW_BASE, 45) is Phase.INELIGIBLE
def test_missing_doc_removed():        assert compute_phase(None, NOW_BASE, 45) is Phase.REMOVED
def test_duration_rule_order():
    assert resolve_duration({"service_duration": 50, "service_id": "s"}, {"s": 20}) == 50
    assert resolve_duration({"service_id": "s"}, {"s": 20}) == 20
    assert resolve_duration({}, {}) == 30
def test_window_crosses_midnight():
    s, e = appointment_window({**apt, "appointment_time": "23:40"}, 45)
    assert e == datetime(2026, 11, 17, 0, 25, tzinfo=TR_TZ)
def test_tz_parameter_respected():
    s, _ = appointment_window(apt, 45, tz=ZoneInfo("Europe/London"))
    assert s.utcoffset() == timedelta(0)
```

- [ ] **Step 2:** Run `cd backend && pytest tests/test_live_activity_phase.py -v`. Expected: FAIL (`ModuleNotFoundError: live_activity`).
- [ ] **Step 3:** Implement in `phase.py`. The module must not import `server.py` (same convention as `tests/test_bulk_session_idempotency.py`).
- [ ] **Step 4:** Run the same command. Expected: PASS.
- [ ] **Step 5:** Commit `feat(live-activity): derived appointment phase`.

### Task 2: Eligibility & targets

**Files:**
- Create: `backend/live_activity/eligibility.py`
- Test: `backend/tests/test_live_activity_eligibility.py`

**Interfaces:**
- Consumes: `Phase`, `appointment_window`.
- Produces:
  - `effective_lead_minutes(lead: int, duration_min: int) -> int` (clamp 5–120, then the 8 h cap from Global Constraints)
  - `in_window(now, start, end, lead_min) -> bool` (`start − lead ≤ now < end`)
  - `effective_scope(user: dict) -> Literal["own","business"]`: role default per Global Constraints, then `users.live_activity_scope` if allowed. `business` is ignored for plain staff.
  - `target_usernames(apt: dict, org_users: list[dict]) -> set[str]`: the assigned user, plus every active user whose `effective_scope == "business"` (owners by default, managers who opted in)
  - `priority_key(phase, start, end, is_assigned_to_user: bool) -> tuple`: `(0, end, not assigned)` for PROCESSING, `(1, start, not assigned)` for UPCOMING

- [ ] **Step 1: Failing tests:**
  - `test_lead_clamped_low_high` (`effective_lead_minutes(1, 30) == 5`; `(500, 30) == 120`);
  - `test_lead_respects_8h_cap` (`effective_lead_minutes(120, 420) == 50`);
  - `test_in_window_boundaries` (just before start−lead is False; at start−lead is True; at end is False);
  - `test_owner_default_business`;
  - `test_owner_preference_own`;
  - `test_manager_default_own_can_opt_business`;
  - `test_plain_staff_business_pref_ignored`;
  - `test_staff_only_own` (`target_usernames({"staff_member_id":"elif"}, users)` contains `"elif"` and business-scope owners, never other staff);
  - `test_permission_revoked_narrows_scope`;
  - `test_priority_processing_then_soonest_then_assigned`.
- [ ] **Step 2:** `pytest tests/test_live_activity_eligibility.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat(live-activity): eligibility rules`.

### Task 3: Content state & APS payloads

**Files:**
- Create: `backend/live_activity/content.py`, `backend/tests/contracts/live_activity_content_state.json` (golden fixture that the Swift tests also consume in Task 16)
- Test: `backend/tests/test_live_activity_content.py`

**Interfaces:**
- Consumes: `Phase`, `appointment_window`.
- Produces:
  - `display_name(full: str, mode: Literal["initials","full","hidden"]) -> str | None` (`"ayşe kaya yılmaz"` → `"Ayşe Y."`; `hidden` → `None`)
  - `build_content_state(apt, phase, start, end, *, privacy_mode, staff_name: str|None, version: int) -> dict` with exactly the keys `phase, startEpoch, endEpoch, startLabel, endLabel, customerDisplay, serviceName, staffName, version`
  - `build_aps(event: Literal["start","update","end"], content: dict, *, now_epoch: int, stale_epoch: int|None, dismissal_epoch: int|None, alert: dict|None, appointment_id: str, org_id: str, input_push_token: bool) -> dict`
  - `PayloadTooLarge(Exception)`
  - Copy constants: `ALERT_START = ("Sıradaki randevu", "{name} · {service} · {time}")`, `ALERT_PROCESSING = ("Randevu başladı", "{name} · {service}")`, `FALLBACK_BODY = "{minutes} dk sonra · {name} · {service} · {time}"`. With `hidden` mode, `{name} · ` is dropped.

- [ ] **Step 1: Failing tests:**
  - `test_display_name_modes` (Turkish casing for `İ/i`, single-word names, whitespace);
  - `test_labels_are_stored_strings` (`startLabel == apt["appointment_time"]`);
  - `test_start_has_attributes_alert_and_type` (`aps["attributes-type"] == "PlannAppointmentAttributes"`, `aps["attributes"] == {"appointmentId":..,"orgId":..}`);
  - `test_input_push_token_only_when_flag`;
  - `test_end_has_dismissal_date`;
  - `test_payload_under_4kb_with_long_service` (raises `PayloadTooLarge` only past 4096 after truncation);
  - `test_matches_golden_fixture` (`build_content_state` for the fixture input == the JSON file);
  - `test_no_phone_or_price_keys`.
- [ ] **Step 2–4:** Run `pytest tests/test_live_activity_content.py -v`: FAIL, then implement, then PASS.
- [ ] **Step 5:** Commit `feat(live-activity): content-state and APS payloads`.

### Task 4: Registry & device store

**Files:**
- Create: `backend/live_activity/registry.py`
- Test: `backend/tests/test_live_activity_registry.py` (uses `mongomock_motor` **only if already installed**; otherwise a small in-test async fake of `find_one_and_update/update_one/find`. Check `pip show mongomock-motor` and add nothing)

**Interfaces:**
- Produces:
  - `async ensure_indexes(db) -> None` (unique `(device_id, appointment_id)`; `(organization_id, state)`; TTL on `ended_at` 3 days; unique `live_activity_devices.device_id`)
  - `async upsert_device(db, *, device_id, organization_id, user_id, role, os_version, app_build, fcm_token, push_to_start_token: str|None, activities_enabled: bool) -> tuple[dict, str]` returns the row plus a **new** device secret when the owner changed or on first registration. The secret is stored as `sha256` only.
  - `async verify_device_secret(db, device_id, secret) -> dict | None`
  - `async claim_transition(db, *, device_id, appointment_id, expect_phase: str|None, new_phase: str, set_fields: dict) -> bool` (atomic compare-and-set on `last_phase_sent`, upsert when `expect_phase is None`)
  - `async record_token(db, *, device_id, appointment_id, activity_id, update_token) -> bool` (`start_sent`/`scheduled_local`/`absent` → `active`, sets `token_received_at`)
  - `async apply_device_report(db, *, device_id, activities: list[dict], active_count: int, activities_enabled: bool, limit_errors: list[dict], now) -> dict`. The report is a **complete** list. Listed `.active` → `active`; listed `.dismissed` (not server-ended) → `dismissed_by_user`; `start_sent` rows **not listed** → `absent`; limit errors → `limit_failed` + `set_observed_cap`; disabled → device `activities_enabled=False`. Returns the changed rows.
  - `async rows_for_org(db, org_id, states: set[str]) -> list[dict]`
  - `async set_observed_cap(db, device_id, cap: int, now) -> None`

- [ ] **Step 1: Failing tests:**
  - `test_claim_is_compare_and_set` (two concurrent `claim_transition(expect="upcoming", new="processing")` produce exactly one True);
  - `test_reowned_device_rotates_secret_and_returns_old_owner`;
  - `test_secret_stored_hashed`;
  - `test_record_token_moves_start_sent_to_active`;
  - `test_record_token_unknown_row_false`;
  - `test_report_missing_start_sent_marks_absent`;
  - `test_report_dismissed_marks_dismissed_by_user`;
  - `test_report_limit_error_sets_cap_and_limit_failed`;
  - `test_no_report_leaves_start_sent_unchanged`.
- [ ] **Step 2–4:** FAIL, then implement, then PASS.
- [ ] **Step 5:** Commit `feat(live-activity): registry and device store`.

### Task 5: Transport (FCM; APNs-direct interface only)

**Files:**
- Create: `backend/live_activity/transport.py`
- Test: `backend/tests/test_live_activity_transport.py`

**Interfaces:**
- Produces:
  - `@dataclass SendResult(ok: bool, invalid_token: bool, error: str|None)`
  - `class LiveActivityTransport(Protocol): async def send(self, *, fcm_token: str, la_token: str, aps: dict, priority: Literal[5,10]) -> SendResult`
  - `class FcmLiveActivityTransport` builds `messaging.Message(token=fcm_token, apns=messaging.APNSConfig(live_activity_token=la_token, headers={"apns-push-type":"liveactivity","apns-topic":"co.plannapp.app.push-type.liveactivity","apns-priority":str(priority)}, payload=messaging.APNSPayload(aps=messaging.Aps(custom_data=aps))))` and sends it via `asyncio.to_thread(messaging.send, msg)`. It maps `registration-token-not-registered`/`invalid-argument` to `invalid_token=True` (same strings as `server.py:3012`). If spike S1 shows that `custom_data` nests incorrectly, switch to a raw `aps` dict through `APNSPayload(aps=None, **{"aps": aps})` and record that in the spec.
  - `class RecordingTransport` (test double, also used by Tasks 6–7)

- [ ] **Step 1: Failing tests:**
  - `test_fcm_message_headers` (monkeypatch `messaging.send` and capture the message: `apns.headers["apns-push-type"] == "liveactivity"`, topic as above, `live_activity_token` set);
  - `test_invalid_token_mapping`;
  - `test_priority_string`.
- [ ] **Step 2–4:** FAIL, then implement, then PASS.
- [ ] **Step 5:** Commit `feat(live-activity): FCM transport`.

### Task 6: Planner (pure diff: desired vs registry → actions)

**Files:**
- Create: `backend/live_activity/planner.py`
- Test: `backend/tests/test_live_activity_planner.py`

**Interfaces:**
- Consumes: `Phase`, `effective_lead_minutes`, `in_window`, `build_content_state`.
- Produces:
  - `@dataclass Desired(appointment_id, device_id, phase: Phase, start, end, content: dict, priority_key: tuple)` (`priority_key` from Task 2 `priority_key`)
  - `@dataclass Action(kind: Literal["start","update","end","fallback_notify","start_time_notice"], device_id, appointment_id, phase, content: dict|None, priority: int, end_reason: str|None, dismissal: Literal["soon","immediate"]|None, thread_id: str|None)`
  - `plan_device(device: dict, desired: list[Desired], rows: list[dict], now: datetime, *, max_attempts: int = 3, start_time_notice: bool) -> list[Action]` (`start_time_notice` = D9-M1 flag)

**Algorithm** (the tests pin it; there is **no** time-based failure inference):

```
LIVE       = {start_sent, scheduled_local, active}          # occupy a slot; start_sent = unresolved, not failed
for row in LIVE whose appointment not desired or desired.phase in {COMPLETED, CANCELLED, REMOVED}:
    end(reason; dismissal immediate for removed/reassigned/rescheduled_out, else soon)
    # an unresolved start_sent is ended too: the end is harmless if the activity never existed
eligible = desired with phase in {UPCOMING, PROCESSING}, sorted by priority_key
cap   = device.observed_cap if learned < 24h ago (from device-reported limit errors only) else ∞
slots = cap − |LIVE rows after ends|
for d in eligible:
    row = rows.get(d.appointment_id)
    if row.state in LIVE:            update if content != row.content (prio 10 iff phase changed, else 5); continue
    if row.state == dismissed_by_user: continue                                   # respect the user, no notify
    if not device.activities_enabled or os < 16.2
       or (no push_to_start_token and os < 26 and not device.foreground):        fallback_notify once; continue
    if row.state in {absent, limit_failed} or row is None:
        if slots > 0 and attempts < max_attempts: start (prio 10); slots -= 1
        else: fallback_notify once                                               # evidence or no slot, never time
if start_time_notice:
    for row in start_sent where d.phase == PROCESSING and not row.notified: start_time_notice once
owner devices: every fallback_notify carries thread_id = "plann-overflow-<YYYY-MM-DD>"
```

- [ ] **Step 1: Failing tests:**
  - `test_six_concurrent_cap_three_priority_order` (3 `start` actions for the 3 highest priority, 3 `fallback_notify`);
  - `test_no_cap_known_tries_all`;
  - `test_unconfirmed_start_never_marked_failed_by_time` (a `start_sent` row 3 h old produces no `fallback_notify` and no resend);
  - `test_unconfirmed_start_consumes_slot`;
  - `test_absent_report_triggers_restart_or_fallback`;
  - `test_limit_failed_falls_back_once`;
  - `test_dismissed_by_user_not_restarted_not_notified`;
  - `test_start_time_notice_only_when_flag_and_unresolved`;
  - `test_owner_overflow_has_thread_id`;
  - `test_slot_frees_starts_next_queued`;
  - `test_max_attempts_three`;
  - `test_reschedule_inside_window_updates_with_version_bump`;
  - `test_reschedule_outside_window_ends_rescheduled_out_immediate`;
  - `test_service_change_in_processing_updates_not_restarts`;
  - `test_cancel_ends_with_cancelled_content`;
  - `test_deleted_ends_removed_immediate`;
  - `test_reassigned_ends_on_old_device`;
  - `test_disabled_device_notifies_only`;
  - `test_fallback_notify_once_per_appointment`;
  - `test_missed_upcoming_starts_directly_processing`;
  - `test_past_end_never_starts`.
- [ ] **Step 2–4:** `pytest tests/test_live_activity_planner.py -v`: FAIL, then implement, then PASS.
- [ ] **Step 5:** Commit `feat(live-activity): planner`.

### Task 7: Sweeper, resync & notification fallback

**Files:**
- Create: `backend/live_activity/sweeper.py`
- Test: `backend/tests/test_live_activity_sweeper.py`

**Interfaces:**
- Consumes: Tasks 1–6.
- Produces:
  - `async run_sweep(db, *, transport: LiveActivityTransport, notify: Callable[..., Awaitable[None]], now: datetime, redis=None, org_ids: list[str]|None = None, appointment_id: str|None = None) -> dict` (stats). It queries orgs with `settings.live_activity_enabled == True`, then appointments with `appointment_date ∈ {now−1d, now, now+1d}` (date strings in TR tz) and status in Bekliyor/Tamamlandı/cancelled. It loads services for the duration rule, loads devices and rows, and calls `plan_device` per device. It executes actions with `claim_transition` **before** `transport.send`; on `invalid_token` it clears the token and the row falls back on the next sweep. Lock: `redis.set(f"live_activity_lock:{int(now.timestamp()//POLL)}", "1", nx=True, ex=POLL+10)`, skipped when `appointment_id` is given (hook path).
  - iOS MVP: only registered iOS Live Activity devices are targeted. Android and web lead-time notifications are added in Phase 4 (Task 20).
  - `async resync(db, org_id: str, appointment_id: str | None) -> None` is a wrapper that swallows and logs all exceptions.
  - `notify` is bound in Task 9 to `send_push_notification(db, org_id, title, body, data={"url": f"/?randevu={id}", "appointment_id": id}, user_id=username)` (existing, `server.py:3051`).

- [ ] **Step 1: Failing tests:**
  - `test_sweep_never_writes_appointments` (spy collection: zero writes to `appointments`);
  - `test_hook_and_sweep_race_single_push` (`asyncio.gather(run_sweep(...), run_sweep(..., appointment_id=X))` produces 1 send);
  - `test_two_workers_one_lock` (the second run returns `{"skipped":"lock"}`);
  - `test_redis_down_still_single_send`;
  - `test_worker_down_resume_processing_single_start`;
  - `test_lazy_tamamlandi_after_derived_end_no_extra_push`;
  - `test_flag_off_org_ignored`;
  - `test_invalid_token_clears_and_falls_back`;
  - `test_fcm_success_does_not_mark_active` (after a successful send the row is `start_sent`, not `active`);
  - `test_live_activity_never_touches_autocomplete_or_transactions` (an AST scan of `backend/live_activity/*.py`: no reference to `_auto_complete_pending_for_org`, `get_appointments` or `transactions`; plus a spy DB showing zero writes to `appointments`/`transactions` across a full sweep).
- [ ] **Step 2–4:** FAIL, then implement, then PASS.
- [ ] **Step 5:** Commit `feat(live-activity): sweeper and resync`.

### Task 8: HTTP endpoints (devices, token, reconcile, widget summary)

**Files:**
- Create: `backend/live_activity/endpoints.py` (`router = APIRouter()`), `backend/live_activity/widget_summary.py`
- Test: `backend/tests/test_live_activity_endpoints.py` (builds a bare `FastAPI()` with the router and overrides the dependencies `get_db` and `get_current_user` via `app.dependency_overrides`; no `server.py` import)

**Interfaces:**
- Consumes: `get_current_user`, `get_db` are injected by Task 9 through `endpoints.configure(get_current_user=..., get_db=...)` to avoid a circular import with `server.py`.
- Produces (all under `/api`):
  - `POST /live-activities/devices` (JWT) body `{device_id, os_version, app_build, fcm_token, push_to_start_token?, activities_enabled}` → `{device_secret?: str}` (present only when rotated)
  - `POST /live-activities/token` (header `X-Plann-Device-Secret`) body `{device_id, appointment_id, activity_id, update_token}` → `204`; `401` on a bad secret
  - `POST /live-activities/reconcile` (JWT **or** device secret) body `{device_id, activities_enabled, foreground: bool, os_version, push_to_start_token?, active_count, activities:[{appointment_id, activity_id, state, content_version}] /* COMPLETE list */, limit_errors:[{appointment_id, error, at}]}`. It calls `apply_device_report` (Task 4) and returns `{end:[appointment_id], update:{appointment_id: content}, start_locally:[{appointment_id, content, stale_epoch}]}`.
  - `DELETE /live-activities/devices/{device_id}` (JWT; logout) → ends rows, revokes the secret
  - `GET /widget/summary?scope=own|business&staff=<username>` (JWT) → `{generatedAt, scope, privacyMode, counts:{total, completed, remaining}, items:[≤6 × {id,startLabel,endLabel,startEpoch,endEpoch,phase,customerDisplay,serviceName,staffName?}]}`. Scope rule: copy of `server.py:8025-8037`; `scope=business` → 403 for staff without `can_view_all_appointments`. Counts exclude `Ödeme Bekleniyor` and cancelled from `total`; `completed` = phase COMPLETED; `remaining` = UPCOMING + PROCESSING. **No auto-complete side effect.**

- [ ] **Step 1: Failing tests:**
  - `test_token_requires_secret`;
  - `test_device_reowned_ends_old_rows_and_rotates_secret`;
  - `test_reconcile_returns_end_for_deleted`;
  - `test_reconcile_start_locally_respects_cap`;
  - `test_reconcile_partial_list_rejected_without_complete_flag` (a report must declare itself complete before `absent` can be inferred);
  - `test_widget_owner_default_business_manager_default_own`;
  - `test_widget_staff_sees_own_only`;
  - `test_widget_business_scope_forbidden_for_plain_staff`;
  - `test_widget_counts_by_derived_phase`;
  - `test_widget_payload_has_no_phone_notes_price`;
  - `test_widget_hidden_mode_nulls_names`.
- [ ] **Step 2–4:** FAIL, then implement, then PASS.
- [ ] **Step 5:** Commit `feat(live-activity): device, token, reconcile and widget endpoints`.

### Task 9: Wire into `server.py` (settings, router, scheduler, hook)

**Files:**
- Modify:
  - `backend/server.py:2924` (`Settings`): add `live_activity_enabled: bool = False; live_activity_lead_minutes: int = 30; lock_screen_name_mode: str = "initials"; live_activity_start_time_notice: bool = True` (D9-M1; defaults keep the API contract)
  - `backend/server.py:2861` (`User`): add `live_activity_scope: Optional[str] = None` (role default applies when None)
  - `backend/Dockerfile:20-37` and `backend/requirements.txt`: pin `firebase-admin==<version validated in S1>`. Before pinning, confirm the running container's version with `docker exec <backend-container> pip show firebase-admin`.
  - `backend/server.py:2335` `emit_to_organization`: after the emit, if `event in {"appointment_created","appointment_updated","appointment_deleted","appointments_bulk_updated"}`, run `asyncio.create_task(live_activity.sweeper.resync(_app_instance.db, organization_id, _extract_apt_id(data)))`, where `_extract_apt_id` reads `data["appointment_id"]` or `data["appointment"]["id"]`, else `None`
  - `backend/server.py:1304-1495`: register `live_activity_sweep_job` (`IntervalTrigger(seconds=LIVE_ACTIVITY_POLL_SECONDS)`, `max_instances=1`, `replace_existing=True`) wrapped in `try/except` like the Step 4c jobs; call `registry.ensure_indexes`
  - router include next to the existing `api_router` includes
- Test: `backend/tests/test_live_activity_wiring.py`: an import-light test that `_extract_apt_id` handles the three payload shapes used at `server.py:5181, 5290, 6182`; plus a manual check (below)

- [ ] **Step 1:** Failing test `test_extract_apt_id_shapes`.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Implement the wiring.
- [ ] **Step 4:** Run `pytest -q`. Expected: the whole existing suite and the new tests PASS. Then start the dev server locally and check that `GET /health` lists the scheduler with jobs +1.
- [ ] **Step 5:** Commit `feat(live-activity): wire settings, router, scheduler and change hook (flag off)`.

---

## Phase 2 — Widgets & quick add (ships independently of Live Activities)

### Task 10: Deep link parser

**Files:**
- Create: `frontend/src/native/deepLinks.js`
- Test: `frontend/src/native/deepLinks.test.js`

**Interfaces:**
- Produces: `parseAppDeepLink(url: string) -> {kind:"new-appointment", date?: string, time?: string, source: string} | {kind:"appointment", id: string} | {kind:"other"}`. It accepts `plannapp://…` and `https://plannapp.co/app/…`. It rejects invalid dates and times, passing `date: undefined` rather than throwing.

- [ ] **Step 1: Failing tests:**
  - `parses new appointment with date/time/source`;
  - `drops invalid date 2026-02-30`;
  - `drops time 25:00`;
  - `parses appointment/<id>`;
  - `stripe checkout urls return other` (they must still reach `handleCheckoutDeepLink`).
- [ ] **Step 2:** `cd frontend && CI=true npx craco test --watchAll=false src/native/deepLinks.test.js`. Expected: FAIL.
- [ ] **Step 3–4:** Implement, then PASS.
- [ ] **Step 5:** Commit `feat(widgets): deep link parser`.

### Task 11: App.js deep-link handling + wizard prefill

**Files:**
- Modify:
  - `frontend/src/App.js:1027-1057` (the `appUrlOpen` effect): call `parseAppDeepLink` first; `new-appointment` → `openNewAppointmentFromLink(link)`; `appointment` → `setCurrentView('dashboard'); setDetailAppointmentId(id)`; `other` → the existing checkout handling, unchanged
  - add a cold-start `CapacitorApp.getLaunchUrl()` effect
  - add a pending-intent effect after login (`sessionStorage['plann_pending_link']`, 10 min TTL)
  - `frontend/src/components/AppointmentFormWizard.js:78`: new optional props `initialDate?: string`, `initialTime?: string`; `initialDate` seeds `formData.appointment_date` (line 111) only when `!appointment`; `initialTime` is applied in the existing slot effect only if it is contained in `availableSlots`
- Create: `frontend/src/native/openNewAppointmentFromLink.js`: `createOpenNewAppointmentFromLink({getShowForm, setPrefill, handleNewAppointment}) -> (link) => void`. If the form is already open → no-op (keeps state). Otherwise it sets the prefill and calls the existing `handleNewAppointment` (`App.js:1483`), which preserves the Aha branch.
- Test: `frontend/src/native/openNewAppointmentFromLink.test.js`

- [ ] **Step 1: Failing tests:**
  - `test_deeplink_does_not_reset_open_form` (`getShowForm()` returns true → `handleNewAppointment` not called and prefill unchanged);
  - `calls handleNewAppointment with prefill when closed`;
  - `aha path delegated` (it always goes through `handleNewAppointment`, never `setShowForm` directly).
- [ ] **Step 2–4:** FAIL, then implement, then PASS.
- [ ] **Step 5:** Manual: in the iOS simulator run `xcrun simctl openurl booted "plannapp://new-appointment?source=widget_small"` cold, warm and logged out. In each case the wizard opens with today's date. Run the same with the wizard open and half-filled: the input is kept.
- [ ] **Step 6:** Commit `feat(widgets): quick-add deep link into existing wizard`.

### Task 12: JS native wrappers + widget snapshot sync

**Files:**
- Create:
  - `frontend/src/native/plannNative.js`: `getWidgetBridge() -> {setSnapshot(json: string): Promise<void>, clear(): Promise<void>} | null` and `getLiveActivityPlugin() -> {...Task 17 API} | null`. Each returns `null` unless `Capacitor.isNativePlatform() && Capacitor.isPluginAvailable(name)`.
  - `frontend/src/native/useWidgetSnapshotSync.js`: `useWidgetSnapshotSync({token, currentUser, socket})`. It fetches `GET /api/widget/summary` (no scope parameter, so the server applies `effective_scope`) on mount, on `appointment_*` socket events (debounced 3 s), on `visibilitychange→hidden`, and every 5 min while visible, then calls `setSnapshot`. On `token` becoming null it calls `clear()`.
- Modify: `frontend/src/App.js` mounts the hook once next to the socket effect (`App.js:1060`).
- Test: `frontend/src/native/useWidgetSnapshotSync.test.js`

- [ ] **Step 1: Failing tests:**
  - `no-op when plugin unavailable` (no fetch);
  - `test_logout_clears_snapshot`;
  - `debounces socket bursts to one fetch`;
  - `sends no scope param (server decides)`.
- [ ] **Step 2–4:** FAIL, then implement, then PASS.
- [ ] **Step 5:** Commit `feat(widgets): snapshot sync`.

### Task 13: iOS `PlannWidgets` extension + `PlannWidgetBridge`

**Files:**
- Create:
  - `frontend/ios/App/PlannWidgets/` (`PlannWidgetsBundle.swift`, `TodayWidget.swift` with small, medium, large and accessory families, `WidgetSnapshot.swift` Codable mirroring the Task 8 JSON, `SnapshotStore.swift` reading `group.co.plannapp.app/widget-snapshot.json`, `Localizable.xcstrings`, `PlannWidgets.entitlements`, `Info.plist`)
  - `frontend/ios/App/App/PlannWidgetBridge.swift` (`CAPPlugin`, methods `setSnapshot`, `clear`; writes atomically, then `WidgetCenter.shared.reloadAllTimelines()`)
- Modify:
  - `frontend/ios/App/App/MyViewController.swift:15-18`: `bridge?.registerPluginInstance(PlannWidgetBridge())`
  - `frontend/ios/App/App/App.entitlements`: add `com.apple.security.application-groups = [group.co.plannapp.app]`
  - `App.xcodeproj/project.pbxproj`: add the target, deployment 16.2, bundle `co.plannapp.app.widgets`, team `9V42VGDN9U`, and embed the extension in App. Use Xcode on a Mac, never a hand edit.
- Test: `frontend/ios/App/PlannWidgetsTests/TimelineTests.swift` (new unit-test target)

**Interfaces:**
- Produces: `func timelineEntries(for snapshot: WidgetSnapshot, now: Date) -> [TodayEntry]` (one entry at `now`, plus one at every `startEpoch`/`endEpoch` > now today; derived phase re-evaluated per entry with the same rule as Task 1).

- [ ] **Step 1: Failing tests:**
  - `testEntriesAtEveryBoundary`;
  - `testNextAppointmentRollsOverAtStart`;
  - `testStaleBannerAfter30Min`;
  - `testHiddenPrivacyShowsServiceOnly`;
  - `testEmptySnapshotShowsSignedOutPlaceholder`.
- [ ] **Step 2:** `xcodebuild test -workspace frontend/ios/App/App.xcworkspace -scheme PlannWidgetsTests -destination 'platform=iOS Simulator,name=iPhone 16'`. Expected: FAIL.
- [ ] **Step 3–4:** Implement, then PASS.
- [ ] **Step 5:** Manual: add the widget in all 3 sizes. "＋" opens the wizard (Task 11). Rows open the detail view. Light/dark both legible. VoiceOver reads "Yeni randevu".
- [ ] **Step 6:** Commit `feat(ios): Home Screen widgets with quick add`.

### Task 14: Android widget + bridge (**moved to Phase 4, Android; separate approval, not part of the iOS MVP**)

**Files:**
- Create:
  - `frontend/android/app/src/main/java/co/plannapp/app/widget/TodayWidgetProvider.java` (`AppWidgetProvider`)
  - `.../widget/WidgetSnapshot.java` (parse JSON from `SharedPreferences("plann_widget")`)
  - `.../widget/PlannWidgetBridgePlugin.java` (`@CapacitorPlugin(name="PlannWidgetBridge")`, `setSnapshot`, `clear`, then `AppWidgetManager.notifyAppWidgetViewDataChanged`/`updateAppWidget`)
  - `res/layout/widget_today_{small,medium,large}.xml`
  - `res/xml/widget_today_info.xml` (`updatePeriodMillis=1800000`, `targetCellWidth/Height`, `resizeMode`)
- Modify:
  - `MainActivity.java`: `registerPlugin(PlannWidgetBridgePlugin.class)` before `super.onCreate`
  - `AndroidManifest.xml`: `<receiver>` with `APPWIDGET_UPDATE` and the meta-data
- Test: `frontend/android/app/src/test/java/co/plannapp/app/widget/WidgetSnapshotTest.java` (JUnit, already available through the Android template; verify `testImplementation 'junit:junit'` exists and add nothing)

- [ ] **Step 1: Failing tests:** `parsesSnapshot`, `nextItemAfterNow`, `emptyWhenCleared`, `quickAddIntentUri` (`plannapp://new-appointment?source=widget_medium`).
- [ ] **Step 2:** `cd frontend/android && ./gradlew testDebugUnitTest`. Expected: FAIL.
- [ ] **Step 3–4:** Implement, then PASS.
- [ ] **Step 5:** Manual on API 26, 31 and 36 emulators: the quick-add PendingIntent from a killed app opens the wizard.
- [ ] **Step 6:** Commit `feat(android): Home Screen widget with quick add`.

### Task 15: Codemagic & signing

**Files:**
- Modify: `codemagic.yaml:10-12` (`ios_signing` also fetches `co.plannapp.app.widgets`, using the syntax proven in spike S4); `codemagic.yaml:45-76` (extend the profile check to also require `com.apple.security.application-groups` in both profiles, same fail-fast style)
- Apple portal (manual): App Group `group.co.plannapp.app`, App ID `co.plannapp.app.widgets`, regenerate both App Store profiles

- [ ] **Step 1:** Run the branch build. Expected: archive and upload to TestFlight succeed; the logged profile dump shows the app-groups entitlement in both profiles.
- [ ] **Step 2:** Commit `ci: sign widgets extension and App Group`.

---

## Phase 3 — iOS Live Activities (requires S1–S3 results)

### Task 16: Attributes + Live Activity UI

**Files:**
- Create:
  - `frontend/ios/App/Shared/PlannAppointmentAttributes.swift` (target membership: App **and** PlannWidgets). `struct PlannAppointmentAttributes: ActivityAttributes { let appointmentId: String; let orgId: String; struct ContentState: Codable, Hashable { phase, startEpoch, endEpoch, startLabel, endLabel, customerDisplay: String?, serviceName, staffName: String?, version: Int } }`, with `startEpoch/endEpoch: Double` decoded with the default `JSONDecoder`
  - `frontend/ios/App/PlannWidgets/AppointmentLiveActivity.swift` (`ActivityConfiguration`: Lock Screen, Dynamic Island compact/minimal/expanded per spec §6; `Text(timerInterval:)` countdown, `Text(start, style: .timer)` elapsed, `ProgressView(timerInterval:)`; an `isStale` branch shows "Başlıyor"; `widgetURL(plannapp://appointment/<id>)`)
- Modify: `PlannWidgetsBundle.swift` adds `if #available(iOS 16.2, *) { AppointmentLiveActivity() }`. Start from the Phase 0 spike views in `spikes/phase0/ios/SpikeWidgets/`.
- Test: `frontend/ios/App/PlannWidgetsTests/ContentStateContractTests.swift`

- [ ] **Step 1: Failing tests:**
  - `testDecodesBackendGoldenFixture` (decodes `backend/tests/contracts/live_activity_content_state.json`, copied into the test bundle by a build phase);
  - `testRelevanceProcessingBeatsUpcoming` (`relevanceScore(for:)` returns 100 vs < 100).
- [ ] **Step 2–4:** FAIL, then implement, then PASS.
- [ ] **Step 5:** Manual: SwiftUI previews of all four presentations × {upcoming, processing, stale, completed, cancelled}, in light and dark.
- [ ] **Step 6:** Commit `feat(ios): appointment Live Activity UI`.

### Task 17: `PlannLiveActivityPlugin` (native)

**Files:**
- Create:
  - `frontend/ios/App/App/PlannLiveActivityPlugin.swift`
  - `frontend/ios/App/App/LiveActivityCoordinator.swift` (non-Capacitor core, so it runs without the WebView)
  - `frontend/ios/App/App/DeviceIdentity.swift` (install UUID + device secret in Keychain, `kSecAttrAccessibleAfterFirstUnlock`)
- Modify:
  - `MyViewController.swift`: register the plugin
  - `AppDelegate.swift:11-15`: `if #available(iOS 16.2, *) { LiveActivityCoordinator.shared.startObserving() }` in `didFinishLaunching`, so token observers run on background launches; register `BGTaskScheduler` id `co.plannapp.app.la-reconcile`
  - `Info.plist`: `NSSupportsLiveActivities = YES`; `BGTaskSchedulerPermittedIdentifiers`; `UIBackgroundModes += fetch`
  - Coordinator posts a **complete** activity list (`complete: true`) on launch, foreground, BG refresh, and every `activityUpdates`/`activityStateUpdates`/`pushTokenUpdates` event (debounced 2 s)

**Interfaces:**
- JS API (`jsName: "PlannLiveActivity"`):
  - `register({apiBaseUrl, jwt}) -> {deviceId}`: posts `/live-activities/devices` with the JWT **once** and stores the returned secret; the JWT is never persisted natively
  - `reconcile() -> {ended:number, started:number, failed:[{appointmentId, error}]}`
  - `unregister()`: logout
- Coordinator:
  - observes `pushToStartTokenUpdates` (17.2+), `activityUpdates`, each `activity.pushTokenUpdates`, `activityStateUpdates` and `ActivityAuthorizationInfo().activityEnablementUpdates`;
  - posts to `/live-activities/token` and `/reconcile` with `X-Plann-Device-Secret`;
  - local start uses `Activity.request(attributes:content:pushType: .token)`;
  - maps `ActivityAuthorizationError` `.targetMaximumExceeded`/`.globalMaximumExceeded` → `failed[].error = "limit"`, `.denied` → `"disabled"`, `.visibility` → `"background"`; reports these in the next reconcile so the server learns `observed_cap`;
  - ends any activity whose `appointmentId` appears in `end`.

- [ ] **Step 1: Failing tests** in `PlannWidgetsTests` (coordinator logic behind a protocol `ActivityGateway` with a fake):
  - `testReconcileEndsServerRejected`;
  - `testLimitErrorReportedNotRetriedImmediately`;
  - `testDuplicateAppointmentIdNotStartedTwice`;
  - `testSecretRotatedOnReRegister`;
  - `testReportIsCompleteListIncludingDismissed`;
  - `testStateChangeEventsDebouncedToOneReport`.
- [ ] **Step 2–4:** FAIL, then implement, then PASS.
- [ ] **Step 5:** Commit `feat(ios): Live Activity native bridge`.

### Task 18: JS integration

**Files:**
- Create: `frontend/src/native/useLiveActivities.js` with `useLiveActivities({token, currentUser})`. When the plugin is available and the user is logged in, it calls `register` once per login, calls `reconcile` on mount and on `visibilitychange→visible`, and calls `unregister` on logout.
- Modify: `frontend/src/App.js` mounts the hook next to `useWidgetSnapshotSync`. `frontend/src/components/Settings.js` adds two groups:
- admin-only org settings: `live_activity_enabled`, `live_activity_lead_minutes` (5–120), `lock_screen_name_mode`, `live_activity_start_time_notice`;
- a per-user "Kilit ekranı kapsamı: Tüm işletme / Yalnızca bana atananlar" control, shown only to admins and to staff with `can_view_all_appointments`, which saves `users.live_activity_scope` through a new `PUT /api/live-activities/scope`.

Both use the existing settings save flow.
- **Required (owner decision 2026-11-15): Live Activity consent onboarding** (spec §5.6).
  - Create `frontend/src/components/LiveActivityConsentSheet.js`: shown once per device after login on iOS 16.2+ when the org flag is on and the user has an eligible appointment today.
  - It explains that iOS will ask twice and that the second prompt ("izin vermeyi sürdürmek istiyor musunuz?") should be answered **"Her Zaman İzin Ver"**.
  - The "seen" flag is stored in `localStorage` (try/catch).
  - Re-showable from Settings, with an "activities disabled" banner that deep-links to iOS Settings.
- Test: `frontend/src/native/useLiveActivities.test.js` covering:
  - `no-op without plugin`;
  - `register once per login`;
  - `unregister on logout`;
  - `reconcile on visible`;
  - `consent sheet shown once after login, never before login`;
  - `disabled banner when activities_enabled false`.

- [ ] **Step 1–4:** FAIL, then implement, then PASS (`CI=true npx craco test --watchAll=false src/native`).
- [ ] **Step 5:** Commit `feat: Live Activities client integration and settings`.

### Task 19: Pilot rollout & device QA

- [ ] Enable `live_activity_enabled` for one internal org via the admin UI.
- [ ] Run the spec §12 iOS matrix (16.4, 17.2, 18.x, 26.x; 1/3/5/8 concurrent; offline at start; reboot; force-quit; LA disabled; Island and non-Island). Record the results in the spec.
- [ ] Acceptance (all must hold):
  - for every eligible appointment, the server sends a start or a fallback within `POLL` seconds of `start − lead`;
  - on-device outcomes (visible / absent / limit / dismissed) are captured by the next device report and match the server rows **100 %** after a foreground reconcile;
  - no `start_sent` row is ever treated as failure by time alone;
  - PROCESSING is shown within 30 s of `start` (stale "Başlıyor" otherwise);
  - completed/cancelled/deleted activities leave the Lock Screen within 30 s + the dismissal policy;
  - zero writes to `appointments` attributable to `live_activity`, verified by a Mongo profiler sample;
  - no duplicate pushes in logs for the same `(device, appointment, phase)`.
- [ ] Commit any spec updates: `docs: Live Activities pilot results`.

---

## Phase 4 — Android (separate approval after the iOS MVP)

- **Task 14** (above): Android widget + bridge with quick add.
- **Task 20: Android standard-notification fallback.** The sweeper targets users whose devices are Android-only (from `push_subscriptions.platform == "android"`) with one lead-time notification per appointment, tracked as `live_activities` rows `device_id = "user:<username>"`, `state = "notified"`. Tests: `test_android_user_gets_lead_notification_once`, `test_android_scope_rules_match_ios`. No Live Updates and no custom FCM service.

## Phase 5 — Optional (each needs separate approval)

- **iOS 26 scheduled starts:** the coordinator calls `request(…, start:)` for appointments whose `start − lead` falls within 2 h when foregrounded, and the planner skips push-to-start for those (reported via reconcile).
- **App Intent "Yeni Randevu" + iOS 18 Control:** these open the Task 10 deep link only.
- **Android ongoing PROCESSING notification:** a custom FCM service (S5); promotion is requested on API 36+ only behind a flag after a Play policy review.
- **Widget self-refresh (D5):** a scoped read-only widget key in a shared Keychain group.

## Acceptance criteria (feature-level)

1. No new appointment status, no manual start, and zero Live Activity-originated writes to `appointments`.
2. One Live Activity per appointment. Concurrency failures produce a notification fallback, never a silent drop.
3. Owner and employee data scopes are enforced server-side and match `GET /appointments`.
4. iOS MVP: widgets in 3 sizes on iOS (Android in Phase 4). Quick add reaches the existing wizard in one tap through the deep link, cold or warm, never discards in-progress form input, and is never a native creation form.
5. The App Group and SharedPreferences contain no tokens and no phone, notes or price data (verified by inspecting the container on a test device).
6. Old native builds running new OTA JS behave exactly as today.
7. The full backend `pytest`, frontend `craco test` and iOS/Android unit tests pass, and the Codemagic iOS and Android workflows produce store-uploadable builds.
