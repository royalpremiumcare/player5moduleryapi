# Separate HIGH-priority remediation items (outside the Live Activities scope)

These were found during the Live Activities recon. They are **not** fixed by, and not touched by, the Live Activities work. They need their own tickets and approval.

The Live Activities design adds no exposure to either item. It never calls the auto-complete code, and it never writes `appointments` or `transactions`. A Phase 1 test enforces this.

---

## REM-1 — Auto-completion can create duplicate `transactions` (financial)

**Where** (`backend/server.py` at commit `80a94706`): three independent copies of the same read-triggered pattern.

| Path | Select | Update | Insert |
|---|---|---|---|
| `GET /appointments` | in-memory loop over the fetched page, `:8152-8169` | `update_many({"id": {"$in": ids}})`, `:8170-8171` | `transactions.insert_many`, `:8172-8173` |
| Dashboard, `_auto_complete_pending_for_org` | `find(status="Bekliyor", date=today)`, `:10374` | `update_many({"id": {"$in": ids}})`, `:10423-10426` | `insert_many`, `:10427-10431` + customer counters `:10434-10447` |
| Staff dashboard | `find(status="Bekliyor", staff=me, date=today)`, `:10577` | `update_many(...)`, `:10622-10625` | `insert_many`, `:10627-10628` |

**Defect.** None of the `update_many` filters includes `"status": "Bekliyor"`, and the transaction insert does not depend on whether this request actually changed the row. The code contains no unique index on `transactions.appointment_id`; the live database was not checked.

**Failure scenario.** Two requests read the same `Bekliyor` appointment after its end time, for example the owner's dashboard and a staff member's dashboard, or the dashboard plus the appointment list loading in parallel, or two of the 17 uvicorn workers serving them. Both select it, both update it (idempotent), and both insert a `Transaction` for the same `appointment_id`.

**Consequences:**
- inflated revenue in statistics and cash views;
- double `completed_appointments` customer counters on the dashboard path;
- possibly wrong staff commission calculations if those read `transactions`.

**Fix direction (for its own design):**
1. Claim per appointment with `find_one_and_update({"id": X, "status": "Bekliyor"}, {"$set": {"status": "Tamamlandı", ...}})` and insert the transaction **only if the claim succeeded**. Alternatively, `update_many` with a status guard followed by re-reading which ids changed.
2. Add a unique (partial) index on `transactions.appointment_id` for auto-completion transactions, after de-duplicating existing data with a reviewed migration and audit report.
3. Factor the three copies into one helper.

**Measure first:** run a read-only aggregation for `transactions` grouped by `appointment_id` with count > 1, to size existing duplicates.

## REM-2 — Inconsistent duration rules decide "completed" differently

| Path | Duration used |
|---|---|
| `GET /appointments` `:8133-8146` | **live** service duration (multi-service sums live durations, falling back to `duration_snapshot`); stored `service_duration` is ignored |
| Dashboard `:10398`, staff dashboard `:10600` | **stored** `service_duration` first, then the live service duration, then 30 |
| Create `:6010-6017` | live service duration at creation (and stored as `service_duration`) |

**Failure scenario.** A service's duration is edited from 60 to 30 minutes after booking. The appointment list then auto-completes it 30 minutes after start, while the dashboard would wait 60 minutes. Calendar and Dashboard UI states also differ, because they use `apt.service_duration` from the API, which `GET /appointments` overwrites with the live value. Combined with REM-1, the path that "wins" decides when revenue is recorded.

**Fix direction:** pick one rule. Recommended: the snapshot stored at booking/edit time, since it represents what was booked. Apply it in all paths and in the Live Activity `resolve_duration`. The Live Activity code currently follows the dashboard rule (D3) and will follow whatever REM-2 decides.
