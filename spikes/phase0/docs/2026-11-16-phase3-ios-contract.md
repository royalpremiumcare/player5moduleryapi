# Phase 3 iOS ↔ backend contract (from the Phase 1 final review, 2026-11-16)

Backend branch: `feature/live-activities-phase1`. The Swift side (plan Tasks 16–18) must implement exactly this. The final-review fix wave may add fields; any change it makes is noted in its report.

## ActivityAttributes
- `PlannAppointmentAttributes { slotId: String /* "<device_id>:<n>" — parse n as slot_index */, orgId: String }`

## ContentState
Default `JSONDecoder` rules:
- `phase: String`, one of `upcoming|processing|completed|cancelled|removed`. Tolerate unknown values.
- `startEpoch`, `endEpoch`: Double.
- `startLabel`, `endLabel`: String. May be `""` in the removed stub.
- `customerDisplay: String?`, `serviceName: String` (may be `""`), `staffName: String?`.
- `version: Int`, monotonic per slot. Ignore lower values.
- `appointmentId: String`. May be `""` in the stub. It drives `plannapp://appointment/<id>`.
- Must decode the golden fixture `backend/tests/contracts/live_activity_content_state.json`.

## Removed stub
`phase="removed"`, empty labels and service, null names, start = end = now. It arrives with dismissal now; render nothing meaningful.

## Endpoints (all under `/api`)
- **`POST /live-activities/devices`** (JWT)
  - Body: `{device_id (Keychain UUID), os_version, app_build, fcm_token, push_to_start_token?, activities_enabled}`.
  - Store the returned `device_secret` (non-null) in the **app** Keychain.
  - Always send the last known `fcm_token` and `push_to_start_token`; a null overwrites the stored one.
  - Serialize registrations.
  - Reconcile with `complete=true` right after a registration that returns a new secret.
- **`POST /live-activities/token`** (header `X-Plann-Device-Secret`, native URLSession, not the WebView)
  - Body: `{device_id, slot_index, activity_id, update_token(hex)}`.
  - Send on **every** `pushTokenUpdates` emission, including rotations. Expect 204 or 401.
- **`POST /live-activities/reconcile`** (secret preferred; JWT only when there is no secret header)
  - Body: `{device_id, activities_enabled, complete, push_to_start_token?, slots:[{slot_index, activity_id, state ∈ active|stale|pending|ended|dismissed}]}`.
  - Call on launch and on every foreground. Proposed addition: `foreground: bool`.
  - Apply **all three** parts of the response:
    - `end: [slot_index]`: end the tracked activity at that index.
    - `end_activities: [activity_id]`: end by id.
    - `start_locally: [{slot_index, content, stale_epoch, relevance, attributes?}]`: only in the foreground, iOS 16.2–17.1.
- **`DELETE /live-activities/devices/{id}`** (JWT, logout). Swift must also end **every** local activity and delete the secret.
- **`PUT /live-activities/preferences`** (JWT): `{scope?: own|all, slot_count?: 1..5, start_alert?: bool}`.
- **`GET /widget/summary?scope=own|all`** (JWT).

## Push handling
- `relevance-score` arrives on every push.
- Terminal phases render **no timer**.
- Stale fallbacks: "Başlıyor" (upcoming past its start) and "Süre doldu" (processing past its end).
- Alerts come from `aps.alert`, which FCM adds.

## Onboarding
Explain both consent prompts and the "Her Zaman İzin Ver" choice (spec §5.6).

## Visual
Spec §6.0: compact white 3-row card, amber strip, green processing dot and bar, default bar thickness, no strikethrough on cancelled.
