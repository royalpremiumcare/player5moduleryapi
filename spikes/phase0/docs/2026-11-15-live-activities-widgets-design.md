# PLANN Live Activities & Home Screen Widgets — Revised Design

Status: **Revision 3: Phase 0 executed on devices (iPhone 11 / iOS 26.0, iPhone 16 Plus / iOS 26.6); awaiting owner approval to start Phase 1.**

**Revision 3 changes (Phase 0 device results, 2026-11-15; details in `spikes/phase0/RESULTS.md` and `PHASE0_REPORT.md`):**
- The per-app cap is 5; the default is `observed_cap = 5` (§4.1, §4.2).
- The server never push-starts over the cap, because over-limit starts are silently dropped (§4.2 rule 1a).
- Swap means end, then start: ended activities are evicted by iOS (§4.2 rule 1b, D11).
- Background and force-quit token delivery is verified (§5.4), so D10 broadcast channels are deferred.
- The consent prompt timing varies, and the onboarding copy says "if iOS asks" (§5.6).
- The compact Dynamic Island shows the PLANN mark (§6).
Date: 2026-11-15

**Revision 2 changes (from the owner's review):**
- D1 approved.
- D2 revised: owners default to business-wide, staff to own, managers follow `can_view_all_appointments`.
- D6 approved, subject to device tests.
- The 90 s "no confirmation = failure" rule is removed and replaced by device-state reconciliation (§4.2).
- The iOS floor is now 16.2.
- Android moves to a separate post-MVP phase.
- The financial and duration issues are now high-priority remediation items (§0.1).
- Phase 0 results: `spikes/phase0/RESULTS.md` on branch `spike/phase0-live-activities`.

Each claim is tagged **[V]** (verified in this repo or in official docs), **[A]** (an assumption that a spike must confirm), or **[R]** (a recommendation, which is a decision for you to approve).

---

## 0. Correction to the premise (read first)

The brief says appointments "automatically transition to the existing `processing` status when their scheduled time arrives." The code does not work that way:

| Fact | Evidence |
|---|---|
| **[V]** There is no persisted "processing" or "in-progress" appointment status. The stored values are `Bekliyor`, `Tamamlandı`, `İptal`, `İptal Edildi`, `Cancelled` (legacy) and `Ödeme Bekleniyor`. | `backend/server.py:2898` (`Appointment.status = "Bekliyor"`); every status filter in `server.py` |
| **[V]** "Processing" exists only as a **derived UI state**: `status == Bekliyor` and `start ≤ now < start + duration`. | `frontend/src/components/Calendar.js:370-380` `isAppointmentActive`; `frontend/src/components/Dashboard.js:650-652` `isDue` (breathing amber bar, 15 s clock tick at `Dashboard.js:171-175`) |
| **[V]** The only stored automatic transition is `Bekliyor → Tamamlandı`, at **start + duration**. It is not at start. | `server.py:6011-6019` (at create), `server.py:8152-8171` (`GET /appointments`), `server.py:10359-10450` `_auto_complete_pending_for_org` (dashboard) |
| **[V]** That transition is **lazy**. It runs as a side effect of reads (`GET /appointments`, the dashboard endpoints). There is no APScheduler job and no worker for it. | Scheduler jobs registered at `server.py:1304-1501`: reminders, payments, nudges, billing, financial, assistant, autopilot. None touch appointment status. |
| **[V]** The auto-complete path emits **no Socket.IO event**. Other clients learn about the change only on their next read. | `_auto_complete_pending_for_org` and the `GET /appointments` block have no `emit_to_organization` call |

**Consequence for this design [R]:** "processing" stays a derived phase. It is computed by one pure function that replicates the existing rule. The Live Activity system **reads** appointment state and **never writes** it. No new status, no manual start action, no second state machine, no change to when `Tamamlandı` is written.

### 0.1 Existing lifecycle risks found during recon (report only, not in scope)

Items 1 and 2 are **separate HIGH-priority remediation items**, outside this feature's scope.
- **REM-1:** duplicate transactions.
- **REM-2:** duration-rule divergence.

This feature adds **no** financial risk:
- it never calls `_auto_complete_pending_for_org` or the `GET /appointments` auto-complete;
- it never writes `appointments` or `transactions`;
- its read endpoints (`/widget/summary`, `/live-activities/reconcile`) have no side effects.

Phase 1 adds a test that fails if any `live_activity` module imports or calls those functions.

1. **[V] Possible duplicate transactions.** Both auto-complete paths call `update_many({"id": {"$in": ids}})` *without* a `status: "Bekliyor"` guard, then `insert_many(transactions)` (`server.py:8171-8173`, `10423-10431`). Two concurrent reads, for example the dashboard and the appointment list opened together on two devices, can both select the same appointment and both insert a `Transaction`. This is a financial-data risk and deserves its own ticket.
2. **[V] The duration rule differs between paths.** `GET /appointments` prefers the *live* service duration (`server.py:8133-8146`). The dashboard prefers the *stored* `service_duration` (`server.py:10398`). The two paths can disagree about when an appointment is complete.
3. **[V] Timezone is hard-coded.** `Europe/Istanbul` appears at about 33 sites, and there is no per-organization timezone setting. Turkey has observed fixed UTC+3 with no DST since 2016, so TR behaviour is consistent today. A `plannapp.co.uk` associated domain exists (`ios/App/App/App.entitlements`). A UK organization would get wrong times, off by 2–3 h depending on DST.
4. **[V]** The dashboard path only auto-completes *today's* appointments (`server.py:10375`). Past days stay `Bekliyor` until a ranged `GET /appointments` touches them.
5. **[V]** `push_subscriptions` keeps **one native token per user per platform** (`server.py:11141-11157`). A user with an iPhone and an iPad receives pushes on only the last-registered device.

The Live Activity design is built to work correctly *despite* items 1–4 (see §2.3) and avoids item 5 with its own per-device registry.

---

## 1. Product specification & lifecycle

### 1.1 Derived appointment phase (single source: DB status + clock)

```
phase(apt, now):
  status ∈ {İptal, İptal Edildi, Cancelled}      → CANCELLED
  status == Ödeme Bekleniyor                      → INELIGIBLE (not a real booking yet)
  status == Tamamlandı                            → COMPLETED
  status == Bekliyor and now <  start             → UPCOMING
  status == Bekliyor and start ≤ now < end        → PROCESSING   (≡ Calendar isAppointmentActive)
  status == Bekliyor and now ≥ end                → COMPLETED    (≡ the rule the backend applies lazily)
  appointment document missing                    → REMOVED
where start = parse(date + " " + time) in Europe/Istanbul   (same as today)
      end   = start + duration_minutes
      duration_minutes = apt.service_duration or service.duration or 30   (dashboard rule, see decision D3)
```

### 1.2 Live Activity lifecycle per appointment

```
 appointment created/edited ──► (sweeper or change-hook evaluates)
            │
            ▼
   now < start − lead ──────────────► NOT YET ELIGIBLE (nothing on device)
            │ now ≥ start − lead
            ▼
   ┌──────────────────────┐  slot available?  no ──► FALLBACK: standard notification
   │ START LA (UPCOMING)  │◄─────────────────────────  + widget; queued for a slot
   │ countdown to start   │        yes                  (retried when a slot frees)
   └─────────┬────────────┘
             │ now ≥ start          (push update; staleDate = start covers late pushes)
             ▼
   ┌──────────────────────┐
   │ PROCESSING           │  elapsed timer, progress start…end
   └─────────┬────────────┘
     ┌───────┼─────────────────┬────────────────────┬────────────────────┐
     ▼ now ≥ end or            ▼ status → İptal      ▼ rescheduled          ▼ document deleted /
       status → Tamamlandı       END (cancelled        (date/time/duration)   staff reassigned /
     END (completed state,       state, dismissal      UPDATE in place if     org disabled
     dismissal ≈ 15 min)         ≈ 15 min)             still eligible, else   END (dismissal:
                                                       END (immediate) and    immediate)
                                                       re-enter later
```

**[V] Hard limit:** an activity can be active for up to **8 h**, and can stay on the Lock Screen for a maximum of **12 h** in total. `lead + duration` is therefore capped at 8 h (§3.2).

### 1.3 Requirements mapping

| # | Requirement | How |
|---|---|---|
| 1–2 | Auto-start in the approaching window | Backend sweeper sends push-to-start (iOS 17.2+); the app starts locally when foregrounded (iOS 16.2+) |
| 3 | Per-appointment Lock Screen / Dynamic Island | One `Activity<PlannAppointmentAttributes>` per `appointment_id` |
| 4 | Countdown | `Text(timerInterval:)` rendered on device, no per-second pushes |
| 5 | Reflect the start-time transition | Sweeper sends an `update` with phase `PROCESSING` at `start`. `staleDate = start` renders a neutral "Başlıyor" state if the push is late |
| 6 | Elapsed time | `Text(start, style: .timer)` counts up, plus `ProgressView(timerInterval: start...end)` |
| 7 | Completed → end | Sweeper ends at `end` (derived) or immediately on an observed `Tamamlandı` |
| 8 | Cancelled → end with state | `end` event with final content `phase = CANCELLED` |
| 9 | Rescheduled | `update` (same activity) while still inside the window; otherwise `end` and restart later |
| 10 | Deleted → not stale | Registry row whose appointment no longer exists → `end`, immediate dismissal; plus device-side reconciliation |
| — | No manual start | No button, no intent, no endpoint that changes phase |

---

## 2. Backend: the authoritative-derived event source

### 2.1 What triggers Live Activity work

There is no existing "start time reached" event to hook into ([V], §0). Two mechanisms together give low latency and guaranteed convergence:

1. **Change hook [R].** `emit_to_organization` (`server.py:2335`) already runs on every appointment mutation that matters: `appointment_created/updated/deleted` and `appointments_bulk_updated`, at `server.py:5181, 5290, 5448, 6182, 7241, 7550, 7690, 7939, 12980, 15730, 15907, 18043`. One added line there schedules `live_activity.resync(org_id, appointment_id | None)` as a background task. This is fire-and-forget, so failures can never break the emit or the request. Bulk events carry no ids, so they trigger an org-wide resync.
2. **Sweeper [R].** A new APScheduler job, `live_activity_sweep_job`, runs every `LIVE_ACTIVITY_POLL_SECONDS` (default **30 s**). It copies the existing reminder job's proven pattern exactly: an `IntervalTrigger`, `max_instances=1`, a Redis bucket lock `live_activity_lock:{bucket}` with `nx=True`, and per-row atomic claims (`server.py:966-979`, `1024-1027`). On each run it:
   - loads `Bekliyor`/`Tamamlandı`/cancelled appointments with `appointment_date ∈ {yesterday, today, tomorrow}` for orgs with the feature enabled (a narrow query, like the reminder job's 3-day horizon);
   - computes `phase()` and the desired per-device action;
   - diffs against the `live_activities` registry and performs `start / update / end / fallback`;
   - ends registry rows whose appointment no longer exists (deletion).

The sweeper is the **safety net**. Worker restarts, missed hooks, Redis outages, lazy completion and deletions all converge within one poll interval.

### 2.2 Reliability properties

| Concern | Mechanism |
|---|---|
| Worker restart | Stateless sweeper. Desired state is recomputed from Mongo on every run. A missed `start` is sent late if still before `end`. A missed `end` is sent on the next run. |
| Duplicates (multi-worker) | Redis bucket lock (same as reminders), plus `find_one_and_update` compare-and-set on `live_activities.{appointment_id, device_id, last_phase_sent}`. Pushes are idempotent anyway, because every payload carries `timestamp` and APNs/ActivityKit apply the newest. |
| Redis down | Falls back to running without the lock, as the reminder job does. The Mongo compare-and-set still prevents double sends. |
| Late/missed transitions | Catch-up rules: UPCOMING missed but now in PROCESSING → start directly in PROCESSING. Already past `end` → never start. |
| Timezone/DST | Reuses the `Europe/Istanbul` parse so the Live Activity agrees with the app [V]. All pushes carry **absolute epoch seconds**. Display strings (`"14:30"`) are passed verbatim from the stored `appointment_time`, so device-timezone differences never shift the shown time. The parse function takes `tz` as a parameter so a future per-org timezone plugs in without changes. |
| Source of truth | The Live Activity code only reads `appointments`. It writes only to its own collections. |

### 2.3 Why this is correct despite the lazy auto-complete

The sweeper evaluates the **same derived rule**, so a Live Activity ends at `end` even if no client has triggered the lazy `Tamamlandı` write. When the write later happens, the phase is still COMPLETED, so nothing changes. Recommendation D3 selects the dashboard's duration rule. If the two server paths disagree (§0.1-2), the Live Activity follows one of them consistently.

**[R, needs separate approval, not in this plan]:** you could make completion eager by calling `_auto_complete_pending_for_org` from a job. That would change *when* transactions are created, which is a lifecycle change, so it is excluded here.

---

## 3. Multiple Live Activity scheduling strategy

### 3.1 Eligibility (who, which appointments)

**Revised D2 (approved).** [V] PLANN has no `manager` role. Roles are `admin`, `staff`, `superadmin` and `marketing`. The existing "manager-like" permission is `staff` + `can_view_all_appointments` (`server.py:8025-8028`).

| Viewer | Default scope (Live Activities **and** widgets) | Allowed preference |
|---|---|---|
| Owner (`admin`) | **business-wide** | `business` / `own` |
| Manager (`staff` + `can_view_all_appointments`) | **own assigned** (their existing default view is all, but the Lock Screen is personal, so own is the safer default) [R; confirm, D2b] | `own` / `business` |
| Staff | own assigned (`staff_member_id == username`) | `own` only |
| Any | Excluded: `Ödeme Bekleniyor`, cancelled before the window, phase COMPLETED | — |

- The preference is stored per **user** (`users.live_activity_scope`, nullable → role default) and enforced server-side.
- Losing `can_view_all_appointments` immediately narrows the scope; the next sweep ends disallowed activities.
- **Priority under the dynamic Apple limit**, applied to every scope:
  1. PROCESSING, soonest end first;
  2. UPCOMING, soonest start first;
  3. tie-break: assigned to this user first.

  Business-wide owners in multi-staff salons will hit the limit routinely. The overflow follows §4.2, as grouped notifications plus the widget.

### 3.2 Approaching window

- **[V]** The existing `Settings.sms_reminder_hours` (default 1.0, `server.py:2924`) is the **customer-facing WhatsApp reminder** lead. It can be large (the job scans a 3-day horizon). It is the wrong audience and the wrong scale for a staff Lock Screen.
- **[R]** Add a new per-org setting `live_activity_lead_minutes`: default **30**, allowed range **5–120**. Reasons:
  - 30 min covers walk-in, preparation and "who's next" for typical 30–90 min salon services;
  - it keeps `lead + duration ≤ 8 h`; the sweeper also clamps lead to `max(0, 8h − duration − 10 min)`;
  - it minimises overlap. Concurrency per device ≈ the appointments overlapping `[start − lead, end]`, which for one staff member is usually ≤ 2, the current one and the next.
- Appointments days in advance are **never** started. iOS 26 scheduled starts are used only inside the lead window (§4.4).

### 3.3 Registry

**Server (authoritative for intent): `live_activities` collection [R]**

```
{ id, organization_id, user_id, device_id, appointment_id,
  state: "start_sent" | "scheduled_local" | "active" | "absent" | "limit_failed" | "disabled"
       | "dismissed_by_user" | "notified" | "ended",          # Revision 2, see §4.2
  start_attempts: int, reported_at?,
  activity_id?,            # ActivityKit id reported by device
  update_token?,           # per-activity pushTokenUpdates (hex)
  last_phase_sent, content_version, start_sent_at?, token_received_at?,
  end_reason?: "completed"|"cancelled"|"rescheduled_out"|"removed"|"reassigned"|"disabled",
  fallback_notified: bool, last_error?, updated_at }
unique (device_id, appointment_id); index (organization_id, state); TTL 3 days on ended rows
```

**Server: `live_activity_devices` collection [R]** (separate from `push_subscriptions`, which keeps one token per user per platform)

```
{ device_id (install UUID, Keychain), organization_id, user_id, role,
  platform: "ios", os_version, app_build,
  fcm_token, push_to_start_token?, activities_enabled: bool,
  observed_cap?: int, observed_cap_at?, updated_at }
unique device_id; on login as another user/org → row is re-owned and old LA rows ended (mirrors server.py:11119-11135)
```

**Device:** `Activity<PlannAppointmentAttributes>.activities` *is* the device registry, because `appointmentId` is a static attribute. No parallel local store is needed.

### 3.4 Reconciliation (app launch, foreground, device reboot, token change)

On launch and every foreground, the native bridge reports `[{appointment_id, activity_id, activityState}]` plus `areActivitiesEnabled` to `POST /api/live-activities/reconcile`. The server answers with the desired set: `end` ids, `update` content per id, and `startLocally` candidates. The device:

- ends any activity the server does not want (deleted, reassigned, cancelled);
- applies content updates locally (no push needed while foregrounded);
- starts allowed activities locally (iOS 16.2+), honouring the cap handling in §4.

After a device reboot, ActivityKit restores the activities and the app reconciles on next launch. If the app is not launched, the server keeps pushing via the stored update tokens, and the sweeper ends everything by `end` time regardless.

---

## 4. Concurrency & fallback strategy

### 4.1 Platform facts

- **[V]** `ActivityAuthorizationError.targetMaximumExceeded`: "The app has already started the maximum number of concurrent Live Activities."
- **[V]** `globalMaximumExceeded`: "The device reached the maximum number of ongoing Live Activities."
- **[V]** `visibility`: thrown when starting from the background.
- **[V]** Apple documents **no numeric maximum**. "The system limits the number of simultaneous ongoing Live Activities. Scheduled Live Activities count towards this limit."
- **[V, Phase 0]** The per-app cap is **5 non-ended activities** on both iPhone 11 / iOS 26.0 and iPhone 16 Plus / iOS 26.6. Local requests 6–12 threw `targetMaximumExceeded` (not `globalMaximumExceeded`). Stale activities count toward the cap.
- **[V, Phase 0]** A **push-to-start over the cap is silently dropped**: FCM accepts it, nothing appears, the app gets no callback or log, and it is **not queued** (it never appeared after a slot freed).
- **[V, Phase 0]** An activity that was **ended but is still visible** (`dismissal-date` in the future) **does not block** a start. iOS dismissed it in the same instant the new push-started activity appeared (+2 s).
- **[A]** The global (device-wide) limit with other apps' activities was not measured.
- **[V]** A failed **push-to-start** is not reported to the server. The device only logs it.

### 4.2 Strategy [R], Revision 2: reconciliation, no time-based failure inference

**Principle.** Only the device knows whether an activity is visible: `Activity<PlannAppointmentAttributes>.activities` and `activityState`. An FCM or APNs success, or a missing token callback, is **never** treated as proof of success or of failure.

**Server row states (per device × appointment):**

| State | Meaning | Set by |
|---|---|---|
| `start_sent` | push-to-start accepted by FCM; **visibility unknown** | sweeper |
| `scheduled_local` | iOS 26 device scheduled it locally | device report |
| `active` | device reports it present and `.active` (token optional) | token callback / any device report |
| `absent` | device reported a full activity list that **does not contain** it after a start was sent | device report |
| `limit_failed` / `disabled` | device reported `targetMaximumExceeded`/`globalMaximumExceeded` / `.denied` or `areActivitiesEnabled=false` | device report |
| `dismissed_by_user` | device reported `activityState == .dismissed` before the server ended it | device report |
| `notified` | standard notification fallback sent | sweeper |
| `ended` | server sent end, or device reported `.ended` | sweeper / device |

**Device reports** go to `POST /live-activities/reconcile`. Each carries the **complete** PLANN activity list `{appointment_id, activity_id, state, content_version}`, `active_count`, `areActivitiesEnabled`, `push_to_start_token`, and any limit errors since the last report. Reports are triggered by:
1. app launch, including background launches from token wakes;
2. foreground;
3. native `activityUpdates` / `activityStateUpdates` / `pushTokenUpdates` events, posted by native code with the device secret and debounced 2 s;
4. a `BGAppRefreshTask` (opportunistic, OS-scheduled, best-effort);
5. login and logout.

**Rules:**
1. **Slots are counted by the server.** `free_slots = observed_cap − |rows in {start_sent, scheduled_local, active}|`. Ended rows do not count (see 1b). Unresolved starts *consume* a slot, which is conservative and prevents bursts.
   - `observed_cap` defaults to **5** [V Phase 0]. It is lowered by **device-reported limit errors** (local start errors) and reset to 5 after 24 h or on an OS change.
   - **1a. Never push-start over the cap.** Over-limit starts vanish without any signal [V Phase 0], so the server-side count is authoritative. Appointments that don't fit get the fallback notification (rule 4).
   - **1b. Swap = end, then start [R, D11].** When a higher-priority appointment (PROCESSING, or UPCOMING sooner than the lowest-priority live row) needs a slot at the cap, the planner ends the lowest-priority live row with the normal `dismissal-date` and push-starts the new one on the **next sweeper pass**. Eviction was verified with a 9 s gap; back-to-back delivery order is [A]. The preempted appointment is the farthest away. It is not notified at preemption; it becomes re-eligible when a slot frees, and rule 4 applies if it never gets one.
2. **Priority:** §3.1 order. The highest-priority eligible appointments get the free slots.
3. **No time-based failure.** `start_sent` stays unresolved until a device report resolves it to `active`, `absent`, `limit_failed`, `disabled` or `dismissed_by_user`. Nothing is re-sent while it is unresolved, which also prevents duplicate activities.
4. **Fallback notification** (at most one per device × appointment, `notified` flag) is sent when there is **evidence** the activity is not shown:
   - `limit_failed`, `disabled` or `absent` while still eligible;
   - no slot available (decided before sending anything);
   - iOS < 16.2;
   - no push-to-start token on iOS < 26 and the app not foregrounded.

   For owners, overflow notifications share `thread-id = "plann-overflow-<date>"` so they stack instead of flooding.
5. **Retry:** `absent` or `limit_failed` rows become eligible again when the device reports a freed slot. At most 3 start attempts per (device, appointment).
6. **User dismissal is respected.** A `dismissed_by_user` activity is never restarted and does not trigger a notification. The appointment remains in the widget.
7. **Disabled:** `areActivitiesEnabled=false` → notifications only until the device reports it re-enabled.

**Residual gap (D9).** PLANN's own per-app cap is now fully server-countable (rule 1a). The remaining gap is narrower: a push-to-start can fail silently because *another app* filled the device-wide limit (not measured), and the device may not report before the appointment. The server then has `start_sent` with no evidence either way. Options:
- **M1 [recommended]:** one redundant "Randevu başladı · Ayşe K. · Saç Kesimi" notification **at appointment start** only for rows still unresolved. This does not claim failure; it is a second channel at the moment that matters, and it is suppressed when the activity was confirmed.
- **M2:** accept the gap; the widget still lists it.
- **M3:** always send a lead-time notification as well as the Live Activity (noisy).

**Ending without a per-activity token.** If no update token ever reached the server (S2 risk), the server cannot push `end`. Mitigations:
- **(a)** `stale-date = end` and a stale view "Süre doldu";
- **(b)** the device ends it on the next reconcile;
- **(c)** the system's 8 h cap;
- **[V Phase 0]** S2 showed the update token arrives 2–3 s after a push-to-start, **even when the app was force-quit** (iOS cold-launches it in the background). The no-token case is therefore an edge case, and (a)–(c) suffice for the MVP.
- **(d) [deferred, D10]** on iOS 18+, start with `input-push-channel` (one channel per appointment) so the server can update or end via broadcast without any per-activity token. This requires direct APNs channel management. FCM support for channels is unverified, so it would use the `ApnsDirectTransport` (§5.2) and the Broadcast capability.

### 4.3 Update budget

**[V]** Priority 10 counts against a budget; priority 5 does not, and Apple recommends a mix.

**[R]** Use priority **10** for `start`, the PROCESSING transition, and `end`, which are the visible moments. Use **5** for content-only edits (service or name change). That is at most about 3 high-priority pushes per appointment, so `NSSupportsLiveActivitiesFrequentUpdates` is **not** needed.

### 4.4 Start paths by iOS version

| iOS | Start path | Updates / end |
|---|---|---|
| < 16.2 (app deploy target is 15.0 [V]) | none → notification fallback. 16.1 lacks `ActivityContent`/`staleDate`/`isStale` [V], so it is excluded | — |
| 16.2 – 17.1 | local `Activity.request` only while the app is foregrounded (reconcile) | per-activity push token |
| 17.2 – 17.x | **push-to-start** via `pushToStartToken` [V 17.2] | per-activity token from `pushTokenUpdates` |
| 18+ | push-to-start + `input-push-token: 1` [V iOS 18] so the system issues the update token immediately | same |
| 26+ | additionally, while foregrounded, `request(…, start: Date)` **scheduled** starts [V iOS 26.0; requires `alertConfiguration`; counts toward the limit; "starts … even if the app is in the background"] for appointments whose `start − lead` falls within the next 2 h. This covers devices that will be offline at start time. Push-to-start skips appointments already scheduled locally (reported via reconcile). | same |

---

## 5. APNs push-to-start & per-activity token architecture

### 5.1 Token types (never mixed)

| Token | Source | Stored in | Used for |
|---|---|---|---|
| APNs device token | `didRegisterForRemoteNotificationsWithDeviceToken` (`AppDelegate.swift:18-21`) | not stored by PLANN (FCM wraps it) | — |
| FCM registration token | `FCMTokenPlugin` (`ios/App/App/FCMTokenPlugin.swift`) | `push_subscriptions.endpoint` (existing), copied to `live_activity_devices.fcm_token` | ordinary notifications; FCM also needs it as the routing token for Live Activity messages [V FCM docs] |
| **Push-to-start token** | `Activity<PlannAppointmentAttributes>.pushToStartTokenUpdates` (iOS 17.2+) | `live_activity_devices.push_to_start_token` | `event: start` only |
| **Per-activity update token** | `activity.pushTokenUpdates` | `live_activities.update_token` | `event: update` / `end` for that one activity |

### 5.2 Transport [R]: FCM HTTP v1 via the existing `firebase_admin` (7.1.0 installed [V])

- **[V]** FCM docs: `apns.live_activity_token` accepts "either a push token or push-to-start token from Apple"; the `aps` payload goes in `apns.payload`; Live Activities require iOS 16.1, remote start iOS 17.2. The Python Admin SDK exposes `APNSConfig(live_activity_token=…)`.
- **Why:** this reuses the credentials and code path already in production (`messaging.send`, `server.py:2982-3006`) and adds no new dependency and no new key handling in the backend.
- **[V, Phase 0 S1]** Push-to-start, update and end via `firebase_admin` `APNSConfig(live_activity_token=…)` + `Aps(custom_data=…)` on project `plann-54bd6` worked on iOS 26.0 and 26.6 TestFlight builds (production APNs). The original pre-test note follows: the Firebase project's APNs configuration must be an **APNs Auth Key (.p8)**, which Apple's token-based connection requires for Live Activities. Confirm this in the Firebase console. Also confirm that `firebase_admin 7.1.0` `APNSConfig` accepts `live_activity_token` and sets `apns-push-type: liveactivity` and `apns-topic: co.plannapp.app.push-type.liveactivity` [V header values], or that we pass those in `APNSConfig.headers`.
- **Fallback transport (designed, not built):** a `LiveActivityTransport` interface with an `ApnsDirectTransport` using `httpx` + `h2` (both already installed [V]) and a .p8 key from env. It is used only if spike S1 fails.

### 5.3 Payloads (content-state encoded with default `JSONDecoder` rules, no custom strategies [V])

```
start (event=start, priority 10):
  aps: { timestamp, event:"start", "attributes-type":"PlannAppointmentAttributes",
         attributes:{ appointmentId, orgId },
         "content-state": <ContentState>,
         "stale-date": <start epoch if UPCOMING else end epoch>,
         "input-push-token": 1,                       # iOS 18+ only; omitted for 17.x devices
         alert:{ title:"Sıradaki randevu", body:"Ayşe K. · Saç Kesimi · 14:30" } }   # alert required for start [V]
update: aps: { timestamp, event:"update", "content-state", "stale-date" }  (alert only on PROCESSING transition, sound none)
end:    aps: { timestamp, event:"end", "content-state": <final>, "dismissal-date": now+15min | now (removed) }

ContentState (Codable, ≤ 4 KB total with attributes [V]):
  phase: "upcoming"|"processing"|"completed"|"cancelled"|"removed"
  startEpoch: Double, endEpoch: Double          # absolute instants
  startLabel: "14:30", endLabel: "15:15"        # stored wall-clock strings, never re-formatted on device
  customerDisplay: "Ayşe K." | null             # per privacy mode (§7.3)
  serviceName: "Saç Kesimi" (truncated 40), staffName?: "Elif" (only on owner devices)
  version: Int                                  # monotonic per appointment
```

`dismissal-date` and `stale-date` placement follow Apple's docs [V]. The system ignores pushes that arrive after an activity ends [V], so late ends are harmless.

### 5.4 Background & permission realities

- **[V]** Starting locally from the background throws `visibility` (except via `LiveActivityIntent`). That is why push-to-start is the only reliable background path.
- **[V, Phase 0 S2]** After a push-to-start, iOS delivers `pushTokenUpdates` in the background: 1 s after the activity appeared with the app backgrounded, and with the app **force-quit** iOS cold-launched it (`didFinishLaunching`, `applicationState == .background`) and delivered the token 2–3 s after the send. The token was then used for a remote update successfully. The Capacitor WebView is not needed for this: the native plugin posts the token itself using a **dedicated short-lived device credential** (§5.7), not the JS auth token.
- If the user disables Live Activities, `activityEnablementUpdates` → `areActivitiesEnabled = false` → reported to the server → notification fallback.
- **[V, Phase 0, iOS 26.0, 2026-11-15]** iOS shows **two separate consent prompts**:
  1. after the first (local) Live Activity: "PLANN canlı etkinliklerine izin verilsin mi?";
  2. when the app **first starts an activity remotely** (push-to-start): "PLANN canlı etkinliklerine izin vermeyi sürdürmek istiyor musunuz?", with options "İzin Verme" / "Her Zaman İzin Ver".
  - **[V, Phase 0] The timing of prompt 2 varies.** On iPhone 11 / iOS 26.0 it appeared on the first remote start. On iPhone 16 Plus / iOS 26.6 it did not appear then, and appeared later during a local start. The copy must therefore not promise *when* it appears.

  If the user answers "İzin Verme", later push-started activities are blocked silently; the server learns this only from device reports and falls back to notifications.

### 5.6 Required onboarding step: explain the Live Activity consent prompts **[R: required for production, owner decision 2026-11-15]**

Before the first Live Activity can appear (local or remote), PLANN shows a short **native-feeling explainer screen**, once per device and re-showable from Settings:
- **What:** "Randevularınız kilit ekranında ve Dynamic Island'da geri sayımla görünecek."
- **Why:** shown before the system prompt. It says iOS will ask for permission, and *may later* ask again ("izin vermeyi sürdürmek istiyor musunuz?"). If it does, choose **"Her Zaman İzin Ver"**. Do not say "you will now be asked twice", because the timing varies [V Phase 0].
- **Trigger:** after login on iOS 16.2+ when the org has `live_activity_enabled` and the user has ≥ 1 eligible appointment today. **Never on cold start before login.**
- **Recovery:** if `areActivitiesEnabled == false` or the device reports blocked remote starts, Settings shows a banner "Canlı etkinlikler kapalı" with a deep link to iOS Settings (`UIApplication.openSettingsURLString`).
- **Copy:** TR/EN, in the app's existing tone; light/dark; no new dependencies.

### 5.7 Native → backend calls without exposing the JWT [R]

The JWT lives in WebView `localStorage` [V `App.js:1064`]. The native token callbacks may run with no WebView. So:

- At registration the JS layer calls `POST /api/live-activities/devices` (JWT auth). The server returns a random **device secret**, bound to `device_id` and scoped *only* to `POST /live-activities/token` and `/reconcile-lite`.
- The native plugin stores the secret in the **app's own Keychain** (not the App Group, not shared with the widget).
- The secret is revoked on logout, user switch or org switch.

---

## 3A. D12 · Slot model **[owner choice 2026-11-16; supersedes per-appointment activities in §3–§4]**

Validated end to end on devices (RESULTS items 13–24).

**Idea:** a device has a fixed number of long-lived Live Activities (**slots**). Their **content** moves through the day's appointments. No activity is created per appointment.

| | Staff | Owner / manager |
|---|---|---|
| Slots | 1 | 1–5 in Settings, **default 4** (owner decision 2026-11-16: 4 fit fully on a 6.1" iPhone 11; a 5th stacks). |
| Scope | own appointments | D2c: "Sadece benim" / "Tüm personel" (unassigned are included for the owner) |

**Assignment (each sweep, per device):**
- **Opening:** the device's day opens when its first appointment of the day enters the lead window (30 min before start, or already processing).
- **Visible (once open):** processing appointments, plus **all remaining upcoming appointments of the same TR day**. Gaps show "Sıradaki 16:00" with a countdown.
- **Order:** processing first (earliest end), then upcoming (earliest start); take N.
- **Keep stable:** an appointment already in a slot stays in that slot. Free or completed slots take the next ones. Extra slots open (one start each) only while there are more visible appointments than open slots.
- **A slot with nothing left to show** (its appointment completed or cancelled, and no unassigned visible appointment) gets `end` with the final content and `dismissal-date` = now + 15 min. This covers day end. It may reopen the same day if needed (starts ≤ 2 × N per day), unless the user dismissed it.

**Pushes:**
- **Start:** each slot starts **once per day**, at the lead time of its first appointment, plus at most one restart for the 8 h limit. Push-to-start budget (~13/h/device) is therefore never at risk.
- **Switch / phase change:** **priority 10**, silent. Priority-5 updates to *different* activities coalesce while the device sleeps (RESULTS 17); priority 10 delivered 90/90 (RESULTS 22).
- **Cosmetic edits** (name or service changed): priority 5.
- **`relevance-score` on every push:** processing 100; upcoming `50 − minutes_to_start/10` (floor 1); completed 0. Without it, a card falls to the bottom (RESULTS 14).
- **Sound:** "Randevu başladı" is optional, and there is **at most one alerted push per device per sweep**. Each alerted push sounds separately (RESULTS 20).

**User dismissal:** a slot the user swipes away is not restarted that day. The appointments remain in the widget and the app.

**Offline:** the card renders from its own dates (countdown, "Başlıyor", "Süre doldu"). On reconnect APNs delivers the latest push (RESULTS 15).

**Activity attributes:** `slotId` + `orgId`, not `appointmentId`. `ContentState` gains `appointmentId`, which drives the deep link `plannapp://appointment/<id>`.

**Removed by D12:**
- per-appointment start / limit / fallback juggling;
- D11 preemption;
- the cap-5 planner;
- start-budget handling, which reduces to a guard.

The per-appointment model (§3–§4) stays documented as the fallback design.

**Day end [decided 2026-11-16]:** final cards stay **15 minutes** (`dismissal-date` = now + 15 min), then iOS removes them. The user may swipe earlier.

## 6. Live Activity & Dynamic Island design

### 6.0 Owner-approved visual (device-reviewed 2026-11-15, spike builds 1006–1009) **[decided]**

The owner reviewed the options on iPhone 11 (iOS 26.0) and iPhone 16 Plus (iOS 26.6). This section **supersedes** the black-card sketch below where they differ.

**Rejected:**
- the black card;
- option C "big timer" (44 pt ring and digits: too large on the Lock Screen);
- the 5-row white card (still too tall).

**Lock Screen card: white, 3 rows (~100 pt)**

`activityBackgroundTint(.white)`, padding 14/16/12.

```
▍ Ayşe K.                       Sıradaki          row 1: name 17 bold · status label
▍ Saç Kesimi · Elif          14:30–15:15          row 2: service · staff 13 · time range 13 semibold
▍ Başlamasına kalan 9:58  ━━━━━━━━░░░░░░          row 3: label 13 + value 20 bold (74 pt slot) + bar
```

| Phase | Left strip | Status label | Row 3 |
|---|---|---|---|
| upcoming | 4 pt amber `#D97706` | "Sıradaki" amber-700 | "Başlamasına kalan" + countdown to **start** + amber bar (lead→start) |
| starting (stale at start) | 4 pt amber | "Sıradaki" | "Başlıyor · 14:30" (**no timer**), full amber bar |
| processing | **6 pt** amber | black pill, **green dot** + "İşlemde" | "Bitmesine kalan" + countdown to **end** + **green** bar `#16A34A` (start→end) |
| overdue (stale at end) | 4 pt gray | "Süre doldu" | "Süre doldu · 15:15" (**no timer**) |
| completed | 4 pt green | "✓ Tamamlandı" green-700 | "✓ Tamamlandı · 15:15" (**no timer, no bar**) |
| cancelled | 4 pt red | "İptal edildi" red-700 | "✕ Randevu iptal edildi" (name gray, **no strikethrough**) |

**Colour meaning:**
- amber = the appointment, the same as the in-app card strip;
- green = "in progress now" (dot, bar, island timer);
- ✓ green = done;
- red = cancelled.

**Bars** use the system default linear `ProgressView(timerInterval:)` thickness (~4 pt) and 4 pt capsules for the static states. The owner rejected the ~6 pt variant on device: "too thick".

**Dynamic Island** (always black):
- compact leading: the "P" mark (amber ring; filled amber while processing) plus the first name;
- compact trailing: the countdown, amber for upcoming and **green to the end** for processing;
- expanded: mark + name, time range, service, timer row, bar;
- terminal states show ✓ / ✕ plus "Bitti" / "İptal" and no timer.

**Not possible on iOS:** a "breathing" strip. Live Activities allow no repeating animations; only timers, progress views and push-driven content transitions animate. The 6 pt strip, the green dot and the moving bar carry "live".

**Ordering [V, Phase 0]:** with no relevance score, iOS stacks cards in start order (oldest on top). A start carrying `relevance-score: 100` was placed above older cards (iOS 26.1). The server sends `relevance-score` on start and on each phase change: processing 100, upcoming `50 − minutes_to_start/10` (floor 1), terminal 0.

**Start budget [V, Phase 0]:** push-to-start is throttled **per device** after a burst (~13 starts/h observed). The planner applies a per-device budget; see RESULTS item 9.

**Spike source:** `frontend/ios/App/PlannSpikeWidgets/AppointmentLiveActivity.swift` on the spike branch is the reference implementation for plan Task 16.


The visual language follows the existing app: black/white, zinc neutrals, Figtree-like system font weights, the amber status bar for pending/due, green for completed, red for cancelled (`Dashboard.js:653-656`).

```
Lock Screen (UPCOMING)                         Lock Screen (PROCESSING)
┌──────────────────────────────────────────┐   ┌──────────────────────────────────────────┐
│ ▍ Ayşe K.                       14:30    │   │ ▍ Ayşe K.                 İşlemde  ●     │
│ ▍ Saç Kesimi · Elif             –15:15   │   │ ▍ Saç Kesimi              14:30–15:15    │
│ ▍                                        │   │ ▍ ▓▓▓▓▓▓▓▓░░░░░░░░  12:04 geçti           │
│ ▍ Başlamasına        12:41               │   └──────────────────────────────────────────┘
└──────────────────────────────────────────┘    ▍ = 4pt status bar (amber; breathing not
 isStale at start → "Başlıyor" (no timer)          possible, so a static amber with ● dot)

Dynamic Island compact          minimal          expanded
 ┌─────────┐   ┌──────┐          ┌──┐           ┌───────────────────────────────────┐
 │ ◔ Ayşe  │   │12:41 │          │◔ │           │ Ayşe K.                  14:30    │
 └─────────┘   └──────┘          └──┘           │ Saç Kesimi                        │
 leading: PLANN mark +          ring =         │ Başlamasına 12:41 ▓▓▓▓░░░         │
 first name; trailing:           progress of    └───────────────────────────────────┘
 countdown / elapsed             lead→start or
                                 start→end
COMPLETED (final, ~15 min): "✓ Tamamlandı · 15:15"   CANCELLED: "✕ İptal edildi" (red bar)
```

- **Compact leading = the PLANN mark** (template image asset in the extension), not a generic SF Symbol. The spike's clock glyph was ambiguous next to the system timer.
- **Terminal phases render NO live timer [V, Phase 0, iOS 26.0].** In the spike, `Text(start, style: .timer)` was shown in every phase, so after a remote `end` (cancelled) the ended card kept counting up from 0 once the start time passed. This is wrong for the user.
  - For `completed`, `cancelled` and `removed`, every presentation (Lock Screen, compact, minimal, expanded) shows only static text: "✕ İptal edildi · 16:34–17:19" / "✓ Tamamlandı · 17:19".
  - Timers render only in `upcoming` (countdown, then the stale "Başlıyor") and `processing` (elapsed + progress).
  - Test: Task 16 `testTerminalPhasesHaveNoTimer` (snapshot/view-inspection of each family per phase).

- With multiple activities, iOS chooses which one occupies the Island (minimal for the second) **[V system behaviour; not controllable]**. Each activity has `relevanceScore`: PROCESSING = 100, UPCOMING = 50 − minutes-to-start/10, so the current appointment wins.
- Tapping the Live Activity opens `plannapp://appointment/<id>` → the existing detail view (`setDetailAppointmentId`).
- There are no buttons in the activity. Read-only by design, so there is no manual start.
- Localization: TR/EN strings in the widget extension's `Localizable.xcstrings`, mirroring `appointments.status.*` keys.

---

## 7. Home Screen widget, quick add & deep links

### 7.1 Data flow (no auth token in the App Group) [R]

```
React app ──(appointments loaded / socket appointment_* / foreground / background)──►
  PlannWidgetBridge.setSnapshot(json)  ──► App Group "group.co.plannapp.app" /widget-snapshot.json
                                          └► WidgetCenter.reloadAllTimelines()
Widget TimelineProvider: reads snapshot, emits one entry at now and one at every start/end
boundary of the day → "next appointment", counts and status roll over without any refresh.
```

- The snapshot comes from a new server endpoint `GET /api/widget/summary`. It applies **exactly** the visibility rule of `GET /appointments` (`server.py:8025-8037`) and returns only display-ready fields: counts (total, completed, remaining by derived phase), the next 6 items `{id, startLabel, endLabel, startEpoch, endEpoch, phase, customerDisplay, serviceName, staffName?}`, `scope`, `generatedAt`, `privacyMode`. No phone numbers, notes, prices or customer ids.
- **[V] WidgetKit limits:** the timeline reload budget is system-controlled, so the design relies on precomputed boundary entries and app-triggered reloads, not periodic fetching.
- **Staleness:** an appointment created on another device while this app is closed appears when the app next runs or a Live Activity push wakes it. Widgets show "Güncellendi 10:42" when the snapshot is older than 30 min.
- **Optional (decision D5):** let widgets refresh themselves via a **scoped, read-only widget key** stored in a *shared Keychain access group* (not the App Group), hitting `/api/widget/summary` only. This is off by default. Alternative: iOS 26 widget push updates **[A, verify]**.
- Logout → the bridge clears the snapshot and reloads widgets, so they show the signed-out placeholder.

### 7.2 Sizes

| Size | Content | Quick add |
|---|---|---|
| Small | Today's count (large numeral), next appointment `14:30 · Ayşe K.`, phase dot | `widgetURL(plannapp://new-appointment?source=widget_small)`. The whole widget is tappable, so a visible "＋" badge in the corner |
| Medium | Total / completed / remaining, next 2 appointments | `Link` "＋ Randevu" pill on the right + per-row links to the detail view |
| Large | Counts + next 5 with status chips (Bekliyor / İşlemde / Tamamlandı / İptal) | header `Link` "＋ Yeni randevu" + per-row links |
| Lock Screen accessory (optional) | `accessoryCircular`: count; `accessoryRectangular`: next appointment | taps open the app |

Owner devices with business scope show the staff name per row, plus an `AppIntentConfiguration` parameter "Personel: Tümü / <staff>" (iOS 17+). On iOS 16 they show all.

### 7.3 Privacy modes (`Settings.lock_screen_name_mode`, new) [R]

`initials` (default, "Ayşe K."), `full`, or `hidden` (service + time only). This applies to Live Activities, widgets and fallback notifications. Lock Screen content is visible without unlocking, which is why the default is not `full`.

### 7.4 Quick add deep link [R]

`plannapp://new-appointment?date=YYYY-MM-DD&time=HH:mm&source=widget_{small|medium|large}` (`date` and `time` are optional).

| Step | Where | Behaviour |
|---|---|---|
| Cold start | `App.getLaunchUrl()` (from `@capacitor/app`, already installed [V]) | stored as a pending intent |
| Warm | existing `appUrlOpen` listener (`App.js:1030`) | parsed by a new `parseAppDeepLink(url)` → `{kind:"new-appointment", date, time, source}` |
| Not logged in | pending intent kept in `sessionStorage` (≤ 10 min), applied after login | |
| Aha onboarding | goes through `handleNewAppointment()` (`App.js:1483`) so the `pending_aha_appointment` branch is preserved | |
| Form already open with edits | **do not reset**; just bring the form to the front (keeps form state) | |
| Prefill | `AppointmentFormWizard` gets new optional props `initialDate`/`initialTime`. Its date already defaults to today [V `AppointmentFormWizard.js:111`]. `initialTime` is applied only if it appears in `availableSlots` once service and staff are known; otherwise no preselection | |
| Validation | unchanged: customer, service, staff, conflict and availability checks stay in the wizard and on the server (`POST /appointments`) | |

**App Intents [R, Phase 4, optional]:** an `OpenIntent` "Yeni Randevu" for Shortcuts/Siri, plus an iOS 18 Control Center control. Both only **open** the same deep link. There is no native appointment creation, which would duplicate the React workflow and its validation.

---

## 8. Business owner vs employee visibility

| Surface | Owner/admin | Staff (default) | Staff + `can_view_all_appointments` |
|---|---|---|---|
| Widget data | business-wide; per-widget staff filter | own (`staff_member_id == username`) | own by default; may switch widget scope to business |
| Live Activities | **business-wide by default** (preference `own`), priority-ordered under the device limit | own only | own by default (D2b); may choose business |
| Fallback notifications | same as Live Activity scope | own | own |
| Enforcement | **server-side**, in `/widget/summary`, the sweeper target selection and `/reconcile`, reusing the `GET /appointments` rule; the client never filters for security | | |

On role or permission change, the next sweep ends Live Activities that are no longer allowed (`end_reason: "reassigned"`). The next snapshot refresh narrows the widget.

---

## 9. Android: **separate phase after the iOS MVP** (Revision 2)

The iOS MVP contains no Android changes. The Android phase delivers:
- the Home Screen widget with quick add;
- the standard-notification fallback at lead time, sent by the same sweeper to Android devices.

Promoted Live Updates and the custom FCM service (S5) stay a later, separately approved experiment.

- **[V]** `compileSdk`/`targetSdk` 36, `minSdk` 23; no widget exists; the `plannapp` scheme intent filter already exists in `AndroidManifest.xml`.
- **Widget [R]:** `AppWidgetProvider` + `RemoteViews` (framework APIs, so **no Glance dependency**, per CLAUDE.md "never introduce new dependencies when native APIs suffice").
  - Small, medium and large layouts mirror iOS.
  - Quick add is a `PendingIntent` → `ACTION_VIEW plannapp://new-appointment?...`.
  - Data comes from `SharedPreferences` written by the same bridge API (`PlannWidgetBridge.setSnapshot`), with no token. Updates come from the bridge, plus `updatePeriodMillis = 30 min` (the platform minimum). `Chronometer` in RemoteViews gives the countdown.
- **Live Updates eligibility [V Android guidance]:**
  - They must be **ongoing, user-initiated, time-sensitive**, with a clear end time.
  - **"Upcoming calendar events" are explicitly inappropriate.** "Events that haven't started should use a standard notification, though events about to start can qualify."
  - Technical requirements: `POST_PROMOTED_NOTIFICATIONS`, `setRequestPromotedOngoing`, `FLAG_ONGOING_EVENT`, no custom RemoteViews, not colorized; the system may still decline.
- **Assessment [R]:**
  - UPCOMING (lead window) → **standard notification only**. It is a calendar entry.
  - PROCESSING has a clear end time and is time-sensitive, but "user-initiated" is debatable: the business booked it, nobody started it.
  - **v1: no promotion.** Send standard high-priority notifications via the existing FCM pipeline at lead time. An optional non-promoted ongoing notification with a chronometer during PROCESSING is Phase 4.
  - Requesting promotion for PROCESSING on API 36+ is a **flagged experiment** after a policy review.
- **[A]** A native ongoing notification needs a `FirebaseMessagingService` that coexists with `@capacitor/push-notifications`' service. Spike S5.

---

## 10. Capacitor 7 plugin vs custom native bridge

| | Community Live Activity plugins [A: exist on npm; quality and maintenance unverified] | **Custom in-app bridge (recommended)** |
|---|---|---|
| Fit | Generic JSON-driven layouts; still require us to write the Widget Extension and attributes | Exact `PlannAppointmentAttributes`, tokens, reconcile and error mapping |
| Push-to-start/token callbacks without WebView | Usually JS-event-based (needs a live WebView) | Native → backend directly (§5.7) |
| Dependencies | New npm and pod dependency (against CLAUDE.md) | None; same pattern as `FCMTokenPlugin`/`ContactPickerPlugin` registered in `MyViewController.capacitorDidLoad` [V] |
| Upgrade risk | Third-party lag on Capacitor and iOS majors | Ours to maintain (~400 lines of Swift + ~300 lines of Kotlin) |

**OTA constraint [V Capgo `@capgo/capacitor-updater` autoUpdate]:** OTA ships JS only. All new native code ships via App Store / Play builds. The JS must feature-detect with `Capacitor.isPluginAvailable('PlannLiveActivity')` and `'PlannWidgetBridge'`, because new JS will run on old native builds and must no-op.

---

## 11. Codemagic, App Groups, entitlements, store builds

| Item | Change |
|---|---|
| New target | `PlannWidgets` Widget Extension (SwiftUI). Bundle `co.plannapp.app.widgets`, deployment target **16.2** (practical ActivityKit floor, Revision 2), `if #available` for 17/18/26 APIs. The app target stays at 15.0 [V], with all ActivityKit code `@available(iOS 16.2, *)`. |
| Backend dependency | **Pin `firebase-admin`** (currently unpinned in `backend/Dockerfile`, absent from `requirements.txt`) to the version validated in S1 |
| Background refresh | `BGTaskSchedulerPermittedIdentifiers = [co.plannapp.app.la-reconcile]` + `UIBackgroundModes += fetch` for the best-effort reconcile |
| Shared code | `PlannAppointmentAttributes.swift` belongs to *both* the App and PlannWidgets targets (ActivityKit requires an identical type) |
| App Group | `group.co.plannapp.app` on App + PlannWidgets entitlements; register in the Apple Developer portal for both App IDs |
| Info.plist (App) | `NSSupportsLiveActivities = YES`; no `FrequentUpdates` (§4.3) |
| Entitlements (App) | keep `aps-environment` + associated domains [V]; add `com.apple.security.application-groups` |
| Keychain | device secret in the app's default Keychain; optional shared widget key (D5) needs `keychain-access-groups` |
| Provisioning | two App Store profiles (app + widgets), both containing App Groups (the app's also needs Push + Associated Domains) |
| Codemagic | `ios_signing` currently names only `co.plannapp.app` [V `codemagic.yaml:10-12`]. Must also fetch `co.plannapp.app.widgets` **[A: confirm the Codemagic syntax for multiple bundle ids / extension profiles]**. Extend the existing "Apple Sertifikalarini Hazirla" check to also fail fast when `com.apple.security.application-groups` is missing from either profile. `xcode-project use-profiles` handles multiple targets. `npx cap sync ios` does not touch extra targets [V Capacitor behaviour]. `Xcode: latest` (26) is required anyway [V comment in yaml]. |
| Firebase | APNs **Auth Key (.p8)** uploaded for `co.plannapp.app` (spike S1) |
| Android | `AppWidgetProvider` receiver + `appwidget-provider` XML + layouts; no signing change; Phase 4 adds `POST_PROMOTED_NOTIFICATIONS` only if the experiment is approved |
| Store review | App Store: Live Activities must show real-time info, not ads [Apple HIG]. Play: Live Updates policy as in §9 |

---

## 12. Test cases (summary; exact tests are in the plan)

**Backend unit (pure functions):**
- phase boundaries at start−lead−1 s, start−lead, start, end−1 s, end;
- each status maps to its phase;
- missing duration defaults to 30;
- multi-service total duration;
- `lead + duration > 8 h` clamp;
- appointment spanning midnight;
- `Ödeme Bekleniyor` is ineligible;
- the TR parse is stable across the year (no DST), and a parameterized tz=Europe/London check of DST transition days (future-proofing, not active);
- payload ≤ 4 KB with 40-character service names;
- privacy modes;
- the `input-push-token` flag set only on iOS 18+.

**Sweeper/registry (mongomock-style fakes):**
1. 6 concurrent eligible appointments on one device with `observed_cap = 3` → 3 started by priority, 3 fallback-notified exactly once.
2. Push-to-start with no device report for any length of time → stays `start_sent`: no failure, no resend, slot consumed. A device report missing it → `absent` → fallback once.
3. Slot frees → next queued started, max 3 attempts.
4. Reschedule inside the window → update with `version` +1; reschedule outside → end `rescheduled_out`, restart later.
5. Cancel → end with phase cancelled.
6. Delete → end `removed`, immediate dismissal.
7. Staff reassignment → end on the old device, start on the new one.
8. Two sweeper instances concurrently → exactly one push per transition.
9. Worker down from start−lead until mid-PROCESSING → a single start directly in PROCESSING.
10. Worker down past end → no start; an existing activity is ended.
11. Lazy `Tamamlandı` written after a derived end → no extra push.
12. Live Activities disabled → notifications only.
13. Device re-login as another user → old rows ended, device secret rotated.

**iOS device matrix (manual, spike + QA):**
- iOS 16.4 (local only), 17.2 (push-to-start without input-push-token), 18.x, 26.x (scheduled start);
- 1, 3, 5, 8 concurrent activities;
- offline at start time (staleDate rendering), airplane mode through `end`;
- device reboot mid-PROCESSING;
- app force-quit;
- Live Activities toggled off in Settings;
- Dynamic Island vs non-Island devices.

**Widgets:**
- boundary rollover with the app closed (entries at 14:30/15:15);
- logout clears data;
- staff vs owner scope;
- `hidden` privacy mode;
- quick add cold, warm, logged out, Aha mode, form open with unsaved edits;
- `initialTime` not in available slots.

**Android:**
- widget sizes on API 26, 31 (rounded corners) and 36;
- quick add PendingIntent from a killed app;
- notification permission denied (API 33+).

---

## 13. Decisions needing your approval

| # | Decision | Recommendation |
|---|---|---|
| D1 | Treat "processing" as the derived phase (no lifecycle change) | **APPROVED** |
| D2 | Scope defaults | **REVISED and approved**: owner business-wide, staff own, managers per existing permission, optional preference (§3.1) |
| D2b | Manager (`can_view_all_appointments`) Lock Screen default | own (can switch to business): **confirm** |
| D2c | Live Activity scope setting **[owner decision 2026-11-16]** | **Settings option for the owner AND the manager role** ("yönetici"): "Canlı bildirimler: Sadece benim randevularım / Tüm personelin randevuları". Staff without manager rights see only their own (no option). Defaults: owner = all staff; manager = own (D2b). Applies to Live Activity slots (D12); widgets keep their own filter (§7.2). **Unassigned appointments [V `server.py:5871-5877`]:** with `admin_provides_service=False` and no qualified staff, appointments are saved with `staff_member_id=None`. Rules: (1) scope `all` includes unassigned; (2) the **owner's** `own` scope also includes unassigned (the owner is de facto responsible); (3) when `admin_provides_service=False` and the org has no staff, hide the option and force `all`. |
| D9 | Residual silent-failure gap (§4.2) | M1: one start-time notice only for unresolved rows: **decide** |
| D10 | iOS 18 broadcast channels for token-less updates | **Defer**: S2 showed per-activity tokens arrive even after force-quit |
| D11 | Preemption at the cap (§4.2 rule 1b) | Higher-priority appointment ends the lowest-priority live activity, then starts: **decide** |
| D3 | Duration rule when the two server paths differ | Dashboard rule (`stored service_duration` → service → 30) |
| D4 | New `live_activity_lead_minutes` (default 30, 5–120) vs reusing `sms_reminder_hours` | New setting |
| D5 | Widget self-refresh with a scoped key in shared Keychain | Off for v1; revisit after Phase 2 |
| D6 | Transport: FCM `live_activity_token` vs direct APNs | **APPROVED; S1 passed on device** (iOS 26.0/26.6). FCM success ≠ visible |
| D7 | Android | **Separate phase after the iOS MVP**: widget + standard notifications; Live Updates later |
| D8 | REM-1 duplicate transactions, REM-2 duration divergence | **Separate HIGH-priority remediation items** |

## 14. Spikes (Phase 0, throwaway, on a dev build)

- **S1:** FCM push-to-start with `firebase_admin 7.1.0` and the .p8 key.
- **S2:** background wake delivering `pushTokenUpdates` after push-to-start, on iOS 17.2 and 18.
- **S3:** observed concurrency cap and the error surfaced for local versus push starts.
- **S4:** Codemagic signing with the extension and App Group.
- **S5:** an Android custom FCM service coexisting with `@capacitor/push-notifications`.

The results feed D6 and §4 before Phase 3 starts.

**Results (2026-11-15):** S1 ✅, S2 ✅ (background and force-quit), S3 ✅ (cap 5, silent over-limit drop, ended activities evicted), S4 ✅ (extension signing without App Groups). S5 was code-review only (Android deferred). See `spikes/phase0/PHASE0_REPORT.md`.
