# Customer phone key, duplicate merge, partial unique index (Faz 7 + Faz 8)

Date: 2026-11-18 · Status: draft for owner approval · Branch: `feature/customer-phone-key`
Source plan: `/root/.cursor/plans/plann_master_uygulama_planı_bbedf5f9.plan.md` (Faz 0 findings, Faz 7, Faz 8).

## Intent

PLANN keeps creating duplicate customers. In Aug 2026 there were 34 duplicate groups; on 2026-11-18 there are **75 groups / 77 extra records in 15 businesses** (5,379 customers). Duplicates split a customer's history, counters and reminders, and the merge gets harder as data grows. The owner wants a **database-level guarantee** that the same person cannot be stored twice, while still allowing the salon realities the Faz 0 analysis found: a mother booking for her daughter with her own number, spouses sharing a number, and walk-ins stored with phone `"0"`.

Owner decision (2026-11-18, replaces Faz 0 Bulgu 4c "no unique index"): canonical phone key + merge + **partial** unique index.

## How it works today (recon, 2026-11-18)

- A customer's identity is effectively `(organization_id, phone string)`. Appointments link to customers by the exact `phone` string (`appointments.phone`, plus `customer_name`); `PUT /api/customers/{phone}` addresses a customer by phone.
- Index: `customers_org_phone_nonunique`. `server.py` (~1201) tries to create a plain unique `(organization_id, phone)` index on every startup and falls back to non-unique when duplicates exist.
- Phone formats stored: `90…` (12 digits) 4,765; `0…` (11) 480; 10-digit 10; `44…` 12; ~100 odd lengths; 32 records with no usable number (placeholders `"0"`, `"00"`, short/broken).
- Write paths to `customers` (all in `server.py` unless noted): `register_user` (owner's own customer doc), `_apply_customer_delta` (upsert by exact `{org, phone}` — called by every appointment create/update/delete path; **main duplicate source**: an appointment typed as `0555…` creates a second customer next to `90555…`), `create_appointment`, `create_bulk_session`, `create_customer` (`POST /customers`, variant check but asymmetric for `0…` input), `create_customers_bulk` (`POST /customers/bulk`), `update_customer` (`PUT /customers/{phone}`, exact-string duplicate check), `create_public_appointment` (variant match + exact case-insensitive name match, else new customer), `verify_code_and_create_appointment`, `_process_whatsapp_verification`, `ai_service.py` (AI tool). `app/api/v1/endpoints/*` is not mounted (dead code; untouched).
- Collections that reference a customer by phone/name: `appointments` (phone, customer_name), `customer_notes` (phone), `marketing_autopilot_tasks` (phone, customer_name), `merchant_transactions` (customer_phone), `refund_requests` (customer_phone), `stripe_customers` (customer_phone), `transactions` (customer_name only). `leads` is not customers.
- MongoDB 8.2.5 (partial indexes supported).

## Goals

1. Every customer with a usable phone gets a canonical `phone_key` (E.164 digits without `+`, e.g. `905551234567`, `447700900123`). The stored `phone` string is **not** rewritten (no behaviour change for WhatsApp, links, old apps).
2. All write paths resolve "is this an existing customer?" by `phone_key`, so format differences stop creating duplicates.
3. Existing "same person" duplicates are merged after an owner-approved dry run.
4. A partial unique index on `(organization_id, phone_key)` makes a second keyed record for the same number impossible.
5. Legitimate shared numbers and walk-ins keep working.

## Non-goals / anti-goals

- No rewrite of stored `phone` values; no change to response shapes of existing endpoints; no new required request fields (frozen mobile builds).
- Public booking must **never** fail because of the index (anti-goal: a lost booking).
- No automatic merge of different people (Faz 0 class C) or nonsense names (class D).
- No change to `leads`.
- No UI redesign of the customer list beyond the "same person?" prompt and the merge suggestion (decision 4 below).

## Design

### Canonical key
`phone_key(phone, *, default_country)` in a new module `backend/customer_identity.py`: digits only; strip leading `00`; TR: 11 digits starting `0` → `90`+rest, 10 digits starting `5` → `90`+digits, 12 digits starting `90` kept; UK: 11 digits starting `07` → `44`+rest, `44…` kept; GBP org with 10 digits starting `7` → `44`+digits. Fewer than 10 digits after cleaning, or unrecognised shapes → **no key** (the record is unkeyed). `default_country` comes from the org's base currency (TRY→TR, GBP→UK). Pure function, table-tested.

### Fields
- `phone_key: str` — set only on records that should be unique.
- `shared_phone: true` — set on a record that intentionally shares a number with another person; such records have **no** `phone_key`.
- Walk-ins / broken numbers: no `phone_key`, no flag.

### Index
`customers_org_phone_key_unique`: `{organization_id: 1, phone_key: 1}`, `unique: true`, `partialFilterExpression: {phone_key: {$exists: true}}`. Created only after the merge (step 4 below); startup code creates it if missing and logs (does not crash) on failure. The old startup attempt to create a plain unique `(organization_id, phone)` index is **removed**.

### Write-path behaviour (one shared resolver)
`resolve_customer(db, org_id, phone, name, *, allow_shared=False)` returns the existing customer for the key or creates one, catching `DuplicateKeyError` (concurrent insert) by re-reading. Callers:
- `_apply_customer_delta`: look up by `phone_key` first; if a keyed customer exists, apply counters to **that** document (its stored phone), else upsert as today with `phone_key` set. Unkeyed phones behave exactly as today.
- `POST /customers` and `/customers/bulk`: same "zaten var" 400 / duplicate counting as today, but decided by `phone_key` (fixes the `0…` asymmetry). New optional body field `allow_shared_phone: true` (ignored by old clients) creates the record with `shared_phone: true` and no key — used by the new "same person?" prompt.
- `PUT /customers/{phone}` phone change: duplicate check by key; recompute `phone_key`.
- Public booking / code / WhatsApp verification: if a keyed customer exists and the name matches (normalized: case, Turkish characters, spacing, trailing "Müşteri"; token-subset match only when the number has a single customer) → use it; otherwise create the new record with `shared_phone: true` (no key). Never raises on the index.
- `create_appointment`, `create_bulk_session`, AI tool, `register_user`: route through the resolver.

### Frontend (OTA + web)
When `POST /customers` answers "zaten var", the add-customer form shows: "Bu numara zaten **{name}** adına kayıtlı. Aynı kişi mi?" → **Aynı kişi** (open existing) / **Farklı kişi** (resend with `allow_shared_phone: true`). Plain-language copy, TR/EN.

### Backfill and merge (owner-gated, scripted, dry-run first)
1. **Backfill (Faz 7 deploy):** set `phone_key` on every customer with a usable number **except** inside duplicate groups. Read-only report first.
2. **Dry-run report (Faz 8):** for every duplicate group, the class (A same name / B variant / C-D different), the proposed survivor (most appointments, then oldest), and every reference that would change. Owner reviews.
3. **Apply (after owner approval, with a backup of every touched document):**
   - A + B groups: merge into the survivor. Reference updates: `appointments.phone` → survivor's phone (appointment `customer_name` is left as recorded); `customer_notes.phone`, `marketing_autopilot_tasks.phone`, `merchant_transactions.customer_phone`, `refund_requests.customer_phone`, `stripe_customers.customer_phone` → survivor's phone. Notes are concatenated. Counters and first/last appointment dates are recomputed from appointments. Merged records are deleted (they remain in the backup).
   - C/D groups: no merge; the survivor keeps the key, the others get `shared_phone: true`.
   - Survivors get `phone_key`.
4. **Integrity check**, then **create the partial unique index**.

## Constraints

Python 3.10 backend; no new dependencies; response shapes and existing request fields unchanged (contract tests in `backend/tests/integration/` must pass); deploy from `git archive` only (never from the live tree); DB writes on prod only after a dry-run report and explicit owner approval, with a restorable backup; every new or changed behaviour test-driven.

## Approaches considered

1. **Plain unique index on `(organization_id, phone)`** — rejected: does not catch format variants and breaks families/walk-ins.
2. **Rewrite every stored phone to canonical form + plain unique index** — rejected: changes data that WhatsApp sending, links and old app builds rely on, and still breaks families.
3. **Canonical `phone_key` + partial unique index + explicit shared flag (chosen)** — catches format variants, gives a DB guarantee, keeps shared numbers and walk-ins working, leaves existing data and contracts intact.

## Decisions from the builder check (2026-11-18)

Marked **[owner, Faz 0]** where the owner already decided it, **[existing]** where today's system answers it, **[call]** where it is the author's call (the owner can override).

1. **Appointment ↔ customer linkage [call].** When a write path matches an existing customer by key, the appointment is stored with **that customer's stored `phone` string** (the same number, possibly in a different format than typed). This keeps the exact-string link that history, update/delete deltas and the merge rely on. It is what public booking already does with `resolved_customer_phone`, now applied to every appointment path.
2. **Shared numbers and counters [call].** When more than one customer has the same phone (a keyed record plus `shared_phone` records), `_apply_customer_delta` picks the record whose normalized name matches the appointment's `customer_name`, falling back to the keyed record. This needs no schema change. Fully id-based linkage stays a separate item (see known limitation).
3. **Unkeyed phones / walk-ins [existing].** Today's index is already non-unique: the startup unique attempt fails on every boot. So removing that attempt changes nothing for `"0"` walk-ins or shared records, and several walk-in records per org remain allowed, as today.
4. **Public booking with a name mismatch [owner, Faz 0 Bulgu 4d + scope decision].** The booking never fails, and a new record is created (`shared_phone: true`, no key). The business owner then sees an in-app suggestion: "Bu numarada zaten {name} kayıtlı — aynı kişi mi?", with **Birleştir** / **Farklı kişi**. Merge uses the Faz 8 merge engine; "Farklı kişi" clears the suggestion. The owner approved this in Faz 0 and queued it into Faz 8, so it is **in scope** (it replaces the non-goal line above about the merge-suggestion UI). This keeps typo duplicates from becoming a permanent backlog.
5. **Country rules [call].** Local TR and UK forms are converted as listed above. Any other number with 11 to 15 digits that does not start with `0`, after stripping `+` and `00`, is keyed as-is (already international). Orgs with an unknown currency or no settings default to TR. Anything else is unkeyed and reported in the dry run.
6. **Backfill vs merge [call].** At backfill, the proposed **survivor of each duplicate group is keyed immediately**; the other members stay unkeyed until the merge. The resolver therefore finds the survivor and creates no new records in the window between backfill and merge.
7. **Merge scope [call].** The merge runs over all orgs; only orgs with duplicate groups change. `customer_notes`: rows are re-pointed to the survivor's phone, and if the model allows a single note per phone, the texts are concatenated. `stripe_customers`: re-pointed only when the survivor has no row of its own; otherwise left as is and listed in the report (6 rows exist in total).
8. **Lower-priority items [call].** A phone change via `PUT /customers/{phone}` keeps rewriting that customer's appointments, as today. `/customers/bulk` counts a number that is already keyed as a duplicate, as today, and never creates shared records (the contacts import cannot ask "same person?").

## Left to the builder

Exact module layout, test structure, how the resolver is threaded through each endpoint, migration script mechanics (idempotent, resumable), report format.

## Known limitation (unchanged by this work)

Records that share an exact phone string are still ambiguous for `PUT /customers/{phone}` (addresses the first match). Fixing that needs id-based customer endpoints — a separate item.
