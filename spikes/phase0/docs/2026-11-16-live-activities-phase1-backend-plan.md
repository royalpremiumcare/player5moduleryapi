# PLANN Live Activities — Phase 1 Backend Core (D12 slot model) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the server side of iOS Live Activities using the owner-chosen **slot model** (D12). Each device has a fixed number of long-lived activities whose content moves through the day's appointments. Everything ships dark behind `settings.live_activity_enabled = false`.

**Architecture:** A new package `backend/live_activity/` contains:
- pure functions: phase, eligibility and scope, content and APS payloads, and the slot planner;
- a Motor-backed registry for devices and slots;
- an FCM transport;
- a sweeper that runs every 30 s (APScheduler) and on appointment change (a hook in `emit_to_organization`), executes the planner's actions and pushes through FCM;
- HTTP endpoints for device registration, activity tokens, reconcile reports, preferences and the widget summary.

The reference behaviour is the device-validated simulator `spikes/phase0/sim_day.py`.

**Tech Stack:** FastAPI + Motor + APScheduler 3.11 + Redis (existing), `firebase_admin` (existing; pinned in Task 9), pytest.

**Spec:** `spikes/phase0/docs/2026-11-15-live-activities-widgets-design.md` on branch `spike/phase0-live-activities`. The sections used are §3A (D12), §5 (tokens and transport), §6.0 (visual contract) and §13 (D2c). Device evidence is in `spikes/phase0/RESULTS.md` (items cited as R#). This plan **replaces Tasks 1–9** of `2026-11-15-live-activities-widgets-plan.md`; Tasks 10+ are unchanged and re-planned later.

## Global Constraints

- **Never write `appointments` or `transactions`, never add a status value, and never import or call `_auto_complete_pending_for_org` or `get_appointments`.** Live Activity code writes only `live_activity_devices`, `live_activity_slots`, and the new `settings` and `users` fields below.
- There is no manual start action (no endpoint changes a phase). The phase is derived from the DB status plus the clock.
- Time parse: `"%Y-%m-%d %H:%M"` in `ZoneInfo("Europe/Istanbul")` (`server.py:8154-8155`). The tz is a parameter.
- Duration rule (D3): `apt.service_duration` → `services[service_id].duration` → `30`.
- **Slots:** plain staff get 1. Owners (`role == "admin"`) and managers (staff with `can_view_all_appointments`) get `users.live_activity_slot_count`, which is **1–5, default 4**. With scope `own`, any user gets 1.
- **Scope (D2c):** `users.live_activity_scope ∈ {"own","all", None}`. Defaults: admin → `all`, manager → `own`, plain staff → `own` (fixed).
  - **Unassigned** (`staff_member_id` null) appointments are visible to admins in **both** scopes.
  - If `settings.admin_provides_service is False` **and** the org has no staff users, the admin scope is forced to `all`.
- **Lead:** `settings.live_activity_lead_minutes`, default 30, clamped 5–120.
- **Pushes:**
  - start: priority 10;
  - slot switch or phase change: **priority 10, silent**;
  - cosmetic content change (same appointment, same phase): priority 5;
  - `relevance-score` on **every** push (R14): processing `100`, upcoming `max(1, 50 − minutes_to_start/10)`, completed/cancelled `0`.
- **Alerts:** at most **one alerted push per device per sweep** (R20). "Randevu başladı" only when `users.live_activity_start_alert` is true (default **false**). The push-to-start alert is mandatory: "Sıradaki randevu".
- **Never push-to-start** when the computed `stale-date` is less than 60 s in the future (R8). Per-device start budget: **8 starts per rolling hour** (R9); env `LIVE_ACTIVITY_START_BUDGET_PER_HOUR=8`.
- **Day end / idle slot:** `end` with `dismissal-date = now + 900` (owner decision: 15 min).
- **8 h limit:** restart a slot when `now − started_at ≥ 7.5 h` and its appointment is not processing.
- **Payload:** attributes + content-state ≤ 4096 B; `serviceName` truncated to 40 chars.
  - Attributes: `{"slotId": "<device_id>:<n>", "orgId": "<org>"}`, attributes-type `PlannAppointmentAttributes`.
  - ContentState keys: `phase, startEpoch, endEpoch, startLabel, endLabel, customerDisplay, serviceName, staffName, version, appointmentId`.
- APNs headers: `apns-push-type: liveactivity`, `apns-topic: co.plannapp.app.push-type.liveactivity`.
- Feature flag `settings.live_activity_enabled` (default `false`); env `LIVE_ACTIVITY_POLL_SECONDS=30`.
- `lock_screen_name_mode ∈ {"initials" (default), "full", "hidden"}`.
- Work only in an isolated worktree on branch `feature/live-activities-phase1`, created from `main`. **Never edit the production working tree `/var/www/player5moduleryapi`, and never deploy.** Merging or deploying needs separate owner approval.
- Run tests in a fresh venv inside the worktree, because the host `backend/venv` is stale (RESULTS risk 2). No new runtime dependencies.

## Review Focus

1. **An appointment rescheduled to another day while it sits in a slot:** the slot drops it and switches (or ends) on the next sweep. Test: Task 6 `test_rescheduled_out_of_day_leaves_slot`.
2. **A switch is due before the slot's update token has arrived:** no push, no crash; the switch is applied on the sweep after the token arrives. Tests: Task 6 `test_no_token_no_update`, Task 7 `test_token_arrival_applies_pending_switch`.
3. **An appointment reassigned from Elif to Can:** Elif's slot releases it, Can's device picks it up, and the owner's slot keeps it. Test: Task 6 `test_reassignment_moves_between_staff_devices`.
4. **The owner lowers the slot count from 4 to 2 mid-day:** the highest-numbered slots end immediately (dismissal now), and the processing appointments stay in the remaining slots. Test: Task 6 `test_slot_count_decrease_ends_extra_slots`.
5. **Two admins in one org, each with their own phone:** each device gets its own independent slots and state. Test: Task 7 `test_two_admin_devices_independent`.

---

## File structure

| File | Responsibility |
|---|---|
| `backend/live_activity/__init__.py` | package marker |
| `backend/live_activity/phase.py` | derived phase and time window (pure) |
| `backend/live_activity/eligibility.py` | scope, slot count, visible appointments per user (pure) |
| `backend/live_activity/content.py` | content-state, relevance, APS dicts (pure) |
| `backend/live_activity/planner.py` | slot planner: desired assignment → actions (pure) |
| `backend/live_activity/registry.py` | Motor access to `live_activity_devices`, `live_activity_slots` |
| `backend/live_activity/transport.py` | FCM transport and a recording test double |
| `backend/live_activity/sweeper.py` | loads data, runs the planner, claims, sends, persists |
| `backend/live_activity/endpoints.py` | FastAPI router |
| `backend/live_activity/widget_summary.py` | widget summary query (read-only) |
| `backend/tests/test_live_activity_*.py`, `backend/tests/contracts/live_activity_content_state.json` | tests and the golden fixture shared with Swift (Phase 3) |
| `backend/server.py`, `backend/Dockerfile`, `backend/requirements.txt` | Task 9 wiring only |

---

### Task 0: Worktree and test environment

- [ ] **Step 1:** From the repository (read-only use of the production clone is allowed for `git worktree add` only), run `git worktree add <scratch>/la-phase1 -b feature/live-activities-phase1 main`. The worktree has no `node_modules` or venv.
- [ ] **Step 2:** In `<scratch>/la-phase1/backend`, run `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt pytest pytest-asyncio`. Expected: install succeeds.
- [ ] **Step 3:** Run `.venv/bin/pytest -q -x tests/test_bulk_session_idempotency.py`. Expected: PASS. This is the baseline and proves the env works. Record the full-suite baseline with `pytest -q` (failures that pre-exist are noted, not fixed).

### Task 1: Derived phase & window

**Files:** Create `backend/live_activity/__init__.py`, `backend/live_activity/phase.py`. Test: `backend/tests/test_live_activity_phase.py`.

**Interfaces — Produces:**
- `TR_TZ = ZoneInfo("Europe/Istanbul")`
- `class Phase(str, Enum)`: `UPCOMING, PROCESSING, COMPLETED, CANCELLED, REMOVED, INELIGIBLE` (values lowercase)
- `CANCELLED_STATUSES = {"İptal", "İptal Edildi", "Cancelled"}`
- `resolve_duration(apt: dict, services_by_id: dict[str, int]) -> int`
- `appointment_window(apt: dict, duration_min: int, tz: ZoneInfo = TR_TZ) -> tuple[datetime, datetime]` (raises `ValueError`)
- `compute_phase(apt: dict | None, now: datetime, duration_min: int, tz: ZoneInfo = TR_TZ) -> Phase`

- [ ] **Step 1: Failing tests.** Use the same cases as the original plan Task 1:
  - `test_upcoming_before_start`, `test_processing_at_start`, `test_processing_one_sec_before_end`;
  - `test_completed_at_end_while_still_bekliyor`, `test_tamamlandi_is_completed_even_before_end`;
  - `test_cancelled_statuses` (parametrized), `test_payment_pending_ineligible` ("Ödeme Bekleniyor"), `test_missing_doc_removed`;
  - `test_duration_rule_order` (`50` / `20` / `30`);
  - `test_window_crosses_midnight` (23:40 + 45 → `2026-11-17 00:25` TR);
  - `test_tz_parameter_respected`.
- [ ] **Step 2:** Run `.venv/bin/pytest tests/test_live_activity_phase.py -v`. Expected: FAIL (`ModuleNotFoundError`).
- [ ] **Step 3:** Implement. Do not import `server`.
- [ ] **Step 4:** Same command. Expected: PASS.
- [ ] **Step 5:** Commit `feat(live-activity): derived appointment phase`.

### Task 2: Eligibility, scope & slot count

**Files:** Create `backend/live_activity/eligibility.py`. Test: `backend/tests/test_live_activity_eligibility.py`.

**Interfaces:**
- Consumes: `Phase`, `compute_phase`, `appointment_window`, `resolve_duration`.
- Produces:
  - `is_manager(user: dict) -> bool` (`role == "staff" and user.get("can_view_all_appointments")`)
  - `effective_scope(user: dict, *, admin_provides_service: bool, org_has_staff: bool) -> Literal["own","all"]`
  - `slot_count(user: dict, scope: str) -> int` (1 for plain staff or scope `own`; otherwise `clamp(user.get("live_activity_slot_count") or 4, 1, 5)`)
  - `effective_lead_minutes(lead: int | None) -> int` (None→30; clamp 5–120)
  - `@dataclass(frozen=True) VisibleAppt(id: str, phase: Phase, start: datetime, end: datetime, apt: dict)`
  - `visible_for_user(apts: list[dict], user: dict, scope: str, *, now: datetime, services_by_id: dict, lead_min: int, day_open: bool, tz=TR_TZ) -> list[VisibleAppt]`. Rules:
    - Filter: same TR day as `now`; phase ∈ {UPCOMING, PROCESSING}; scope filter (`own` → `staff_member_id == user["username"]`, plus unassigned when the user is an admin; `all` → every appointment).
    - When `day_open` is False, only appointments with `start − lead ≤ now` qualify.
    - Sort: processing by `(0, end)`, upcoming by `(1, start)`.
    - Unparseable dates are skipped (logged), never raised.

- [ ] **Step 1: Failing tests:**
  - `test_admin_default_all`, `test_admin_pref_own`;
  - `test_manager_default_own_can_choose_all`;
  - `test_plain_staff_all_pref_ignored`;
  - `test_forced_all_when_admin_not_service_and_no_staff`;
  - `test_unassigned_visible_to_admin_in_own_and_all` (`staff_member_id=None`);
  - `test_unassigned_not_visible_to_staff`;
  - `test_slot_count_defaults_and_clamp` (admin None→4; 9→5; 0→1; staff→1; admin scope own→1);
  - `test_lead_clamp` (1→5, 500→120, None→30);
  - `test_day_closed_only_lead_window` (an appointment 40 min away is not visible; 25 min away is visible);
  - `test_day_open_shows_rest_of_day` (with `day_open=True`, an appointment at 16:00 is visible at 10:00; tomorrow's is not);
  - `test_order_processing_by_end_then_upcoming_by_start`;
  - `test_cancelled_and_completed_excluded`;
  - `test_bad_date_skipped`.
- [ ] **Step 2:** `.venv/bin/pytest tests/test_live_activity_eligibility.py -v` → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** → PASS.
- [ ] **Step 5:** Commit `feat(live-activity): scope, slot count and visibility`.

### Task 3: Content state, relevance & APS payloads

**Files:** Create `backend/live_activity/content.py`, `backend/tests/contracts/live_activity_content_state.json`. Test: `backend/tests/test_live_activity_content.py`.

**Interfaces:**
- Consumes: `Phase`.
- Produces:
  - `display_name(full: str, mode: Literal["initials","full","hidden"]) -> str | None` (`"ayşe kaya yılmaz"` → `"Ayşe Y."`; Turkish İ/ı casing; hidden → None)
  - `relevance(phase: Phase, start: datetime, now: datetime) -> float` (100 / `max(1, 50 − minutes_to_start/10)` / 0)
  - `build_content_state(apt: dict, phase: Phase, start: datetime, end: datetime, *, privacy_mode: str, staff_name: str | None, version: int) -> dict`. Exactly the 10 ContentState keys from Global Constraints. `startLabel` = `apt["appointment_time"]`; `endLabel` = `end.strftime("%H:%M")`.
  - `stale_epoch(phase: Phase, start: datetime, end: datetime) -> int | None` (upcoming → start; processing → end; else None)
  - `build_aps(event: Literal["start","update","end"], content: dict, *, now_epoch: int, relevance: float, stale_epoch: int | None, dismissal_epoch: int | None, alert: tuple[str, str] | None, slot_id: str | None, org_id: str | None, input_push_token: bool) -> dict`. `start` carries `attributes-type`, `attributes={"slotId","orgId"}` and the mandatory alert. The key is `relevance-score`.
  - `PayloadTooLarge(Exception)`, `StaleStartRejected(Exception)` (raised by `build_aps("start", …)` when `stale_epoch − now_epoch < 60`)
  - Copy:
    - `ALERT_START = ("Sıradaki randevu", "{name} · {service} · {time}")`
    - `ALERT_PROCESSING = ("Randevu başladı", "{name} · {service}")`
    - in hidden mode `"{name} · "` is dropped.

- [ ] **Step 1: Failing tests:**
  - `test_display_name_modes`;
  - `test_relevance_values` (processing 100; upcoming in 20 min → 48; in 900 min → 1; completed 0);
  - `test_content_keys_exact` (set equality with the 10 keys, including `appointmentId`);
  - `test_labels_are_stored_strings`;
  - `test_start_has_slot_attributes_and_alert`;
  - `test_every_event_has_relevance_score`;
  - `test_start_with_past_stale_rejected` (R8);
  - `test_end_has_dismissal_date`;
  - `test_input_push_token_only_when_flag`;
  - `test_payload_under_4kb_with_long_service`;
  - `test_matches_golden_fixture`;
  - `test_no_phone_or_price_keys`.
- [ ] **Step 2:** `.venv/bin/pytest tests/test_live_activity_content.py -v` → FAIL.
- [ ] **Step 3:** Implement; write the golden fixture from one canonical input.
- [ ] **Step 4:** → PASS.
- [ ] **Step 5:** Commit `feat(live-activity): content-state, relevance and APS payloads`.

### Task 4: Device & slot registry

**Files:** Create `backend/live_activity/registry.py`. Test: `backend/tests/test_live_activity_registry.py`. Use an in-test async fake collection (`find_one`, `find`, `find_one_and_update`, `update_one`, `update_many`, `create_index`); add no dependency.

**Interfaces — Produces:**
- Collections:
  - `live_activity_devices{device_id (unique), organization_id, user_id, username, os_version, app_build, fcm_token, push_to_start_token, activities_enabled, secret_sha256, start_log: list[float] (epochs, last hour), day: "YYYY-MM-DD"|None, updated_at}`
  - `live_activity_slots{device_id, slot_index (1..5), unique(device_id, slot_index), state: "start_sent"|"active"|"ended"|"dismissed_by_user", activity_id, update_token, appointment_id, phase_sent, content_hash, version, started_at, day}`
- `async ensure_indexes(db) -> None`
- `async upsert_device(db, *, device_id, organization_id, user_id, username, os_version, app_build, fcm_token, push_to_start_token, activities_enabled) -> tuple[dict, str | None]`. The second value is a new secret on first registration or owner change. Owner change also ends that device's slots (`state="ended"`). Only the sha256 of the secret is stored.
- `async verify_device_secret(db, device_id: str, secret: str) -> dict | None`
- `async slots_for_device(db, device_id: str) -> list[dict]` (ordered by slot_index)
- `async claim_slot(db, *, device_id: str, slot_index: int, expect_version: int | None, set_fields: dict) -> bool` (atomic CAS on `version`; upsert when `expect_version is None`; increments `version`)
- `async record_slot_token(db, *, device_id: str, slot_index: int, activity_id: str, update_token: str) -> bool` (`start_sent`→`active`)
- `async apply_device_report(db, *, device_id: str, slots: list[dict], activities_enabled: bool, complete: bool, now: datetime) -> list[dict]`. Each slot in `slots` is `{slot_index, activity_id, state}`.
  - Listed `dismissed` → `dismissed_by_user` for `day`.
  - Listed `ended` → `ended`.
  - `start_sent` and active rows **not listed** → `ended`, only when `complete` is true.
- `async record_start(db, device_id: str, now_epoch: float) -> None` and `starts_last_hour(device: dict, now_epoch: float) -> int` (pure)

- [ ] **Step 1: Failing tests:**
  - `test_claim_slot_is_cas` (two concurrent claims with the same `expect_version` → exactly one True);
  - `test_reowned_device_rotates_secret_and_ends_slots`;
  - `test_secret_stored_hashed`;
  - `test_record_token_moves_start_sent_to_active`;
  - `test_record_token_unknown_slot_false`;
  - `test_report_dismissed_marks_for_today`;
  - `test_partial_report_does_not_end_unlisted`;
  - `test_complete_report_ends_unlisted`;
  - `test_start_log_prunes_older_than_hour`.
- [ ] **Step 2:** `.venv/bin/pytest tests/test_live_activity_registry.py -v` → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** → PASS.
- [ ] **Step 5:** Commit `feat(live-activity): device and slot registry`.

### Task 5: Transport

**Files:** Create `backend/live_activity/transport.py`. Test: `backend/tests/test_live_activity_transport.py`.

**Interfaces — Produces:**
- `@dataclass SendResult(ok: bool, invalid_token: bool, error: str | None)`
- `class LiveActivityTransport(Protocol)`: `async def send(self, *, fcm_token: str, la_token: str, aps: dict, alert: tuple[str, str] | None, priority: Literal[5, 10]) -> SendResult`
- `class FcmLiveActivityTransport`: `messaging.Message(token=…, apns=APNSConfig(live_activity_token=la_token, headers={push-type, topic, "apns-priority": str(priority)}, payload=APNSPayload(aps=Aps(alert=ApsAlert(title, body) if alert else None, custom_data=aps))))`. This is the device-validated encoding (R S1). It runs through `asyncio.to_thread(messaging.send, msg)`. `registration-token-not-registered` and `invalid-argument` map to `invalid_token=True` (strings as `server.py:3012`).
- `class RecordingTransport` keeps a `.sent: list[dict]` and can be configured to fail per token.

- [ ] **Step 1: Failing tests:**
  - `test_fcm_message_headers_and_token` (monkeypatched `messaging.send`);
  - `test_alert_attached_only_when_given`;
  - `test_invalid_token_mapping`;
  - `test_priority_string`.
- [ ] **Step 2:** `.venv/bin/pytest tests/test_live_activity_transport.py -v` → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** → PASS.
- [ ] **Step 5:** Commit `feat(live-activity): FCM transport`.

### Task 6: Slot planner (pure)

**Files:** Create `backend/live_activity/planner.py`. Test: `backend/tests/test_live_activity_planner.py`.

**Interfaces:**
- Consumes: `VisibleAppt`, `Phase`, `relevance`, `stale_epoch`.
- Produces:
  - `@dataclass Action(kind: Literal["start","update","end"], slot_index: int, appointment_id: str | None, phase: Phase | None, priority: Literal[5, 10], alert: Literal["start","processing"] | None, relevance: float, dismissal: Literal["soon","now"] | None)`
  - `plan_device(*, slots: list[dict], visible: list[VisibleAppt], n_slots: int, now: datetime, starts_last_hour: int, start_budget: int, start_alert_enabled: bool, has_push_to_start: bool, content_hash: Callable[[VisibleAppt], str]) -> list[Action]`

**Algorithm.** The tests pin it; it ports `sim_day.py` and adds the D12 rules.

```
usable = slots in state {start_sent, active}, index ≤ n_slots
end(now) every usable slot with index > n_slots                      # slot count lowered
assigned = {slot.appointment_id: slot for slot in usable if that id ∈ visible ids}   # stability
free = usable slots whose appointment is not in visible (completed/cancelled/moved/reassigned)
queue = [v for v in visible[:n_slots] if v.id not in assigned]
for slot in free (ascending index): take next from queue → switch: update, priority 10
leftover free slots with nothing to take → end(soon)                 # idle / day end, +15 min
for remaining queue items: open the lowest free index with state ∉ {dismissed_by_user today}
   → start only if has_push_to_start and starts_last_hour < start_budget (else skip this sweep)
for assigned slots: phase changed → update priority 10; same phase & content_hash changed → update priority 5
updates and switches to a slot without update_token are dropped (retried next sweep)
8 h: slot.started_at ≤ now − 7.5 h and its appt not PROCESSING → end(now); reopened on the next sweep
alerts: at most one Action carries alert="processing" (first slot that turned PROCESSING, if start_alert_enabled); every start carries alert="start"
every action carries relevance(phase, start, now)
```

- [ ] **Step 1: Failing tests.** Each uses fixed `now` and hand-built slots/visible lists:
  - `test_first_open_starts_one_slot_per_visible_up_to_n`;
  - `test_stable_assignment_keeps_slots`;
  - `test_completed_slot_switches_to_next_silently_p10`;
  - `test_idle_slot_ends_soon_at_day_end`;
  - `test_processing_outranks_upcoming_when_full` (Burak waits for a free slot, as in RESULTS 24);
  - `test_phase_change_is_p10_cosmetic_is_p5`;
  - `test_single_alert_per_device_batch`;
  - `test_alert_off_by_default`;
  - `test_relevance_on_every_action`;
  - `test_no_token_no_update`;
  - `test_start_budget_blocks_extra_starts`;
  - `test_no_push_to_start_no_start`;
  - `test_dismissed_slot_not_reopened_today`;
  - `test_8h_restart_not_during_processing`;
  - `test_slot_count_decrease_ends_extra_slots`;
  - `test_rescheduled_out_of_day_leaves_slot`;
  - `test_reassignment_moves_between_staff_devices` (two `plan_device` calls with Elif's and Can's visible lists);
  - `test_replays_sim_day_scenario`. Feed the five appointments of `sim_day.py` at the tick times in RESULTS 24 and assert the same action sequence for the 3-slot owner and the 1-slot staff.
- [ ] **Step 2:** `.venv/bin/pytest tests/test_live_activity_planner.py -v` → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** → PASS.
- [ ] **Step 5:** Commit `feat(live-activity): slot planner`.

### Task 7: Sweeper & resync

**Files:** Create `backend/live_activity/sweeper.py`. Test: `backend/tests/test_live_activity_sweeper.py`.

**Interfaces:**
- Consumes: Tasks 1–6.
- Produces:
  - `async run_sweep(db, *, transport: LiveActivityTransport, now: datetime, redis=None, org_ids: list[str] | None = None) -> dict` (stats).
    - Orgs where `settings.live_activity_enabled`.
    - Today's appointments (TR date strings) for those orgs, plus services (for duration), users (scope, slot count, alert pref), devices and slots.
    - Per device: `visible_for_user` → `plan_device` → for each action: `claim_slot` (CAS) **before** `transport.send`; on success persist `appointment_id, phase_sent, content_hash, state`; on `invalid_token` clear `update_token` (slot) or `push_to_start_token` (device).
    - Starts call `record_start`.
    - `day_open` = device `day == today`, set when the first start of the day succeeds.
    - Global lock `redis.set(f"live_activity_lock:{int(now.timestamp()//POLL)}", "1", nx=True, ex=POLL+10)`; skipped for `org_ids` (hook path).
  - `async resync(db, org_id: str) -> None` wraps `run_sweep(org_ids=[org_id])` and logs and swallows all exceptions.

- [ ] **Step 1: Failing tests** (fake db + `RecordingTransport`):
  - `test_sweep_never_writes_appointments_or_transactions` (spy db; plus an AST scan of `backend/live_activity/*.py` for the forbidden names in Global Constraints);
  - `test_hook_and_sweep_race_single_push` (`asyncio.gather(run_sweep(...), run_sweep(..., org_ids=[o]))` → 1 send per change);
  - `test_two_workers_one_lock`;
  - `test_redis_down_still_single_send`;
  - `test_flag_off_org_ignored`;
  - `test_invalid_slot_token_cleared`;
  - `test_fcm_success_does_not_mark_active` (state stays `start_sent` until `record_slot_token`);
  - `test_token_arrival_applies_pending_switch`;
  - `test_two_admin_devices_independent`;
  - `test_lazy_tamamlandi_no_extra_push` (status flips to "Tamamlandı" after the derived end → no second push).
- [ ] **Step 2:** `.venv/bin/pytest tests/test_live_activity_sweeper.py -v` → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** → PASS.
- [ ] **Step 5:** Commit `feat(live-activity): sweeper and resync`.

### Task 8: HTTP endpoints

**Files:** Create `backend/live_activity/endpoints.py` (`router = APIRouter()`, `configure(get_current_user, get_db)`), `backend/live_activity/widget_summary.py`. Test: `backend/tests/test_live_activity_endpoints.py` (a bare `FastAPI()` with `dependency_overrides`; no `server` import).

**Interfaces — Produces** (all under `/api`):
- `POST /live-activities/devices` (JWT): `{device_id, os_version, app_build, fcm_token, push_to_start_token?, activities_enabled}` → `{device_secret?}`
- `POST /live-activities/token` (header `X-Plann-Device-Secret`): `{device_id, slot_index, activity_id, update_token}` → 204; 401 on a bad secret. It triggers `resync(org)` so a pending switch lands immediately (Review Focus 2).
- `POST /live-activities/reconcile` (JWT **or** device secret): `{device_id, activities_enabled, complete: bool, push_to_start_token?, slots: [{slot_index, activity_id, state}]}` → `{end: [slot_index], start_locally: [{slot_index, content, stale_epoch, relevance}]}`. `start_locally` is used only for iOS 16.2–17.1 devices without push-to-start, and only while foregrounded.
- `PUT /live-activities/preferences` (JWT): `{scope?: "own"|"all", slot_count?: 1..5, start_alert?: bool}`. 403 if a plain staff user sends `scope="all"` or `slot_count>1`. Returns the effective values.
- `DELETE /live-activities/devices/{device_id}` (JWT; logout) → ends slots, revokes the secret.
- `GET /widget/summary?scope=own|all` (JWT) → `{generatedAt, scope, privacyMode, counts: {total, completed, remaining}, items: [≤ 6 × {id, startLabel, endLabel, startEpoch, endEpoch, phase, customerDisplay, serviceName, staffName?}]}`. Scope rules are those of Task 2. **No auto-complete side effect.**

- [ ] **Step 1: Failing tests:**
  - `test_token_requires_secret`;
  - `test_token_triggers_resync`;
  - `test_device_reowned_rotates_secret`;
  - `test_reconcile_partial_does_not_end_unlisted`;
  - `test_reconcile_start_locally_only_without_push_to_start`;
  - `test_preferences_staff_cannot_choose_all_or_slots`;
  - `test_preferences_admin_slot_count_clamped`;
  - `test_widget_admin_default_all_manager_default_own`;
  - `test_widget_includes_unassigned_for_admin`;
  - `test_widget_payload_has_no_phone_notes_price`;
  - `test_widget_hidden_mode_nulls_names`.
- [ ] **Step 2:** `.venv/bin/pytest tests/test_live_activity_endpoints.py -v` → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** → PASS.
- [ ] **Step 5:** Commit `feat(live-activity): device, token, reconcile, preferences and widget endpoints`.

### Task 9: Wire into `server.py` (flag off)

**Files:**
- Modify `backend/server.py:2924` (`Settings`): add `live_activity_enabled: bool = False; live_activity_lead_minutes: int = 30; lock_screen_name_mode: str = "initials"`.
- Modify `backend/server.py:2861` (`User`): add `live_activity_scope: Optional[str] = None; live_activity_slot_count: Optional[int] = None; live_activity_start_alert: bool = False`.
- Modify `backend/server.py:2335` (`emit_to_organization`): for the events `appointment_created`, `appointment_updated`, `appointment_deleted` and `appointments_bulk_updated`, call `asyncio.create_task(live_activity.sweeper.resync(_app_instance.db, organization_id))`.
- Modify `backend/server.py:1304-1495`: register `live_activity_sweep_job` (`IntervalTrigger(seconds=LIVE_ACTIVITY_POLL_SECONDS)`, `max_instances=1`, `replace_existing=True`, try/except like the existing jobs), call `registry.ensure_indexes`, `endpoints.configure(...)` and include the router.
- Modify `backend/Dockerfile`, `backend/requirements.txt`: pin `firebase-admin==7.1.0` (S1-validated). Before merge, the owner checks the running container with `docker exec <backend> pip show firebase-admin`.
- Test: `backend/tests/test_live_activity_wiring.py`.

- [ ] **Step 1:** Failing tests:
  - `test_settings_defaults_flag_off` (`Settings()` has `live_activity_enabled is False`);
  - `test_user_new_fields_optional`;
  - `test_emit_hook_events_listed`. This is import-light: it reads `server.py` text and asserts that the four event names and `live_activity.sweeper.resync` appear inside `emit_to_organization`.
- [ ] **Step 2:** → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `.venv/bin/pytest -q`. Expected: all new tests pass, and the existing suite has no new failures versus the Task 0 baseline.
- [ ] **Step 5:** Commit `feat(live-activity): wire settings, router, scheduler and hook (flag off)`.

---

**After Task 9:**
1. Whole-branch review.
2. Report to the owner.
3. **Stop.** Merging to `main`, deploying, enabling the flag for a pilot org, and Phase 2/3 (widgets, native slot plugin with `slotId` attributes, onboarding, settings UI) each need separate owner approval.
