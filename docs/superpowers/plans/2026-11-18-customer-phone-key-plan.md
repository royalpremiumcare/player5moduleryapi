# Customer Phone Key, Merge and Partial Unique Index — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Owner rule: every subagent invokes superpowers skills (implementers: test-driven-development, systematic-debugging, verification-before-completion; reviewers: verification-before-completion).

**Goal:** Stop duplicate customers: canonical `phone_key` on every write path, owner-approved merge of existing duplicates, then a partial unique index on `(organization_id, phone_key)`.

**Architecture:** A pure identity module (`customer_identity.py`) computes keys and name matches. A resolver in `customer_resolver.py` is the single place every write path asks "existing customer or new?". A merge engine (`customer_merge.py`) powers both the one-off cleanup script and the in-app "same person?" merge. Prod data changes run only through `scripts/customer_phone_key.py` with `--dry-run` first.

**Tech Stack:** FastAPI + Motor (Python 3.10), MongoDB 8.2, React 19 + Capacitor 7, jest, pytest.

**Spec:** `docs/superpowers/specs/2026-11-18-customer-phone-key-design.md` (read it; its "Decisions from the builder check" section is binding).

## Global Constraints

- Python 3.10; no new dependencies (backend or frontend).
- Existing response shapes and request fields unchanged; only **additive optional** fields. The `POST /customers` duplicate answer stays `400` with detail `"Bu telefon numarasına sahip bir müşteri zaten var"`.
- Stored `customers.phone` is never rewritten by Faz 7 code (merge re-points references to the survivor's phone; it does not reformat numbers).
- New customer fields, exact names: `phone_key` (str, only on unique records), `shared_phone` (bool true on intentional shared-number records), `merge_suggestion_for` (str: `id` of the keyed customer a public-booking record may duplicate).
- Index name and spec: `customers_org_phone_key_unique`, keys `{organization_id: 1, phone_key: 1}`, `unique=True`, `partialFilterExpression={"phone_key": {"$exists": True}}`.
- Public booking (`create_public_appointment`, `verify_code_and_create_appointment`, `_process_whatsapp_verification`) must never fail because of a customer write.
- Backend test command (prod image, read-only mount): `docker run --rm --network none -v $PWD/backend:/app:ro -w /app -e PYTHONDONTWRITEBYTECODE=1 player5moduleryapi-backend:e1486d9f python -m pytest tests -q -p no:cacheprovider --ignore=tests/integration` and the same with `tests/integration`. Frontend: `CI=true npx craco test --watchAll=false` (symlink `frontend/node_modules` to the live tree's; remove the link before committing).
- Real-Mongo tests: `docker run -d --rm --name pk-mongo-test mongo:8` on a private network; tests read `PK_TEST_MONGO_URL` and are skipped when unset. Never point them at prod.
- Copy (TR exact; EN in parentheses): add-customer prompt "Bu numara zaten {{name}} adına kayıtlı. Aynı kişi mi?" / "Aynı kişi" / "Farklı kişi" ("This number is already saved for {{name}}. Is it the same person?" / "Same person" / "Different person"); suggestion "Bu numarada zaten {{name}} kayıtlı. Aynı kişi mi?" / "Birleştir" / "Farklı kişi" ("{{name}} is already saved with this number. Same person?" / "Merge" / "Different person").
- No prod DB writes and no deploy inside any task; the rollout section is owner-gated.

## Review Focus

1. Public booking where the typed name is a typo or only a first name → booking succeeds; a shared record with `merge_suggestion_for` is created, or the existing customer is reused when the names match. (Task 4 test)
2. Two concurrent creates of the same number → one keyed record, no 500 (`DuplicateKeyError` re-read). (Task 2 test)
3. A walk-in appointment with phone `"0"` → still works, creates or updates an unkeyed record, never collides. (Task 2 test)
4. A GBP business entering `07700 900123` → key `447700900123`; a TRY business entering `0555 111 22 33` → `905551112233`. (Task 1 test)
5. An appointment update that changes the phone → counters leave the old customer and land on the new one, both resolved by key. (Task 4 test)

---

### Task 1: Identity module (keys and name matching)

**Files:** Create `backend/customer_identity.py`; Test `backend/tests/test_customer_identity.py`.

**Interfaces — Produces:**
- `phone_key(phone: str | None, default_country: Literal["TR","UK"] = "TR") -> str | None`
- `country_for_currency(currency: str | None) -> Literal["TR","UK"]` (`GBP`→`UK`, anything else→`TR`)
- `normalize_name(name: str | None) -> str` (casefold with Turkish İ/I handling, ç→c ğ→g ı→i ö→o ş→s ü→u, drop a trailing word "müşteri", collapse spaces)
- `names_match(a: str | None, b: str | None, *, allow_subset: bool) -> bool` (equal after normalization; with `allow_subset`, one token set ⊆ the other)

- [ ] **Step 1: Write failing table tests** `test_phone_key_rules` with exact cases:
  `("0555 111 22 33","TR")→"905551112233"`, `("5551112233","TR")→"905551112233"`, `("+90 555 111 22 33","TR")→"905551112233"`, `("00905551112233","TR")→"905551112233"`, `("07700 900123","UK")→"447700900123"`, `("7700900123","UK")→"447700900123"`, `("+44 7700 900123","TR")→"447700900123"`, `("+49 1512 3456789","TR")→"4915123456789"`, `("0","TR")→None`, `("00","TR")→None`, `("12345","TR")→None`, `(None,"TR")→None`, `("055511122334455","TR")→None` (starts with 0 after cleaning and is not a TR/UK local shape).
  `test_country_for_currency`: `GBP→UK`, `TRY→TR`, `None→TR`, `EUR→TR`.
  `test_names_match`: `("Canan Çelik","canan celik Müşteri",allow_subset=False)→True`; `("Alara","Alara Kaya",allow_subset=True)→True`; same with `allow_subset=False→False`; `("Elif","Elif Naz",allow_subset=False)→False`; `("İrem","irem")→True`; `("Makbule","Kadir Burak")→False` (both modes).
- [ ] **Step 2:** Run → FAIL (module missing).
- [ ] **Step 3:** Implement. Rules exactly as spec "Canonical key" + builder decision 5 (11–15 digits not starting with `0` after stripping `+`/`00` are keyed as-is).
- [ ] **Step 4:** Run → PASS; full backend suite green.
- [ ] **Step 5:** Commit `feat(customers): canonical phone key and name matching`.

### Task 2: Resolver and `_apply_customer_delta`

**Files:** Create `backend/customer_resolver.py`; Modify `backend/server.py` `_apply_customer_delta` (~5079–5160); Test `backend/tests/test_customer_resolver.py` (uses `tests/live_activity_fakes.FakeDB`; extend the fake only if an operator is missing, and keep it backward compatible).

**Interfaces:**
- Consumes: Task 1.
- Produces:
  - `async def org_country(db, organization_id: str) -> Literal["TR","UK"]` (reads `settings.base_currency`).
  - `async def find_customer_for(db, organization_id: str, phone: str, name: str | None) -> dict | None`: records with the same key or the same exact phone string; among several, prefer the `names_match(..., allow_subset=False)` one, then the keyed one.
  - `async def resolve_customer(db, organization_id: str, phone: str, name: str | None, *, mode: Literal["admin","appointment","public"], allow_shared: bool = False) -> tuple[dict, bool]`: returns `(customer_doc, created)`. `admin` and `appointment` reuse the existing customer whatever the name. `public` reuses only on `names_match` (`allow_subset=True` only when that number has exactly one customer); otherwise it inserts `{shared_phone: True, merge_suggestion_for: <keyed id>}` without a key. `allow_shared=True` (admin "Farklı kişi") inserts `shared_phone: True` without a key. New unique records get `phone_key`. An insert that raises `DuplicateKeyError` re-reads and returns the winner.
  - `_apply_customer_delta(...)`: same signature. It resolves the target with `find_customer_for` and updates **that** document by `id`. When nothing exists, it upserts as today plus `phone_key` (unkeyed phones: as today). Errors are still swallowed and logged.

- [ ] **Step 1: Failing tests:**
  - `test_format_variant_reuses_keyed_customer` (stored `905551112233`, delta with `05551112233` → counters on the existing doc, no new doc);
  - `test_walk_in_zero_stays_unkeyed` (Review Focus 3);
  - `test_shared_number_counters_follow_name` (keyed "Makbule" + shared "Kadir Burak" on the same string; a delta for "Kadir Burak" updates the shared doc);
  - `test_public_name_mismatch_creates_shared_suggestion`;
  - `test_public_single_token_matches_when_only_customer` ("Alara" vs "Alara Kaya");
  - `test_concurrent_resolve_one_record` (two `asyncio.gather` resolves of a new number → one keyed doc; the second call gets `created=False`; make the fake raise `DuplicateKeyError` on the second keyed insert to simulate the index) (Review Focus 2);
  - `test_admin_allow_shared_creates_unkeyed`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement per Interfaces.
- [ ] **Step 4:** Targeted tests plus full backend and integration suites green.
- [ ] **Step 5:** Commit `feat(customers): resolver; appointment counters follow the keyed customer`.

### Task 3: Admin customer endpoints

**Files:** Modify `backend/server.py` `create_customer` (~12745), `create_customers_bulk` (~12831), `update_customer` (~12922), models `CustomerCreate`/`CustomerBulkCreate` (add optional `allow_shared_phone: bool = False` to `CustomerCreate` only); Test `backend/tests/integration/test_customer_phone_key_endpoints.py` (existing integration harness; extend `mocks.CustomersColl` minimally if needed).

**Interfaces:** Consumes Task 2 `resolve_customer(mode="admin", allow_shared=...)`, `phone_key`.

- [ ] **Step 1: Failing tests:**
  - `test_create_with_zero_prefixed_duplicate_is_400` (stored `905551112233`, post `05551112233` → 400, exact existing detail);
  - `test_create_sets_phone_key`;
  - `test_allow_shared_phone_creates_second_record` (→ 200, `shared_phone` true, no key);
  - `test_bulk_counts_keyed_number_as_duplicate`;
  - `test_put_phone_change_to_existing_key_is_400`;
  - `test_put_phone_change_recomputes_key`;
  - `test_response_shapes_unchanged` (compare keys of the create/bulk/put responses before vs after).
- [ ] **Step 2–4:** FAIL → implement → PASS (plus full suites).
- [ ] **Step 5:** Commit `feat(customers): admin endpoints dedupe by phone key; same-person prompt support`.

### Task 4: Appointment and public write paths

**Files:** Modify `backend/server.py`: `create_appointment` customer insert (~6149), `create_bulk_session` (~6804), `register_user` (~3519), `create_public_appointment` customer block (~15601–15640), `verify_code_and_create_appointment` (~15948), `_process_whatsapp_verification` (~18100), and every appointment update/delete path that calls `_apply_customer_delta` (no signature change); `backend/ai_service.py` (~542). Test `backend/tests/integration/test_customer_phone_key_appointments.py`.

**Interfaces:** Consumes Task 2. Rule (builder decision 1): when a write path matches an existing customer, the **appointment is saved with that customer's stored `phone`**.

- [ ] **Step 1: Failing tests:**
  - `test_appointment_with_variant_phone_stored_as_customer_phone`;
  - `test_public_booking_typo_name_succeeds_and_flags_suggestion` (Review Focus 1);
  - `test_public_booking_never_raises_on_customer_write_error` (resolver raises → booking 200, error logged);
  - `test_appointment_phone_change_moves_counters` (Review Focus 5);
  - `test_ai_tool_customer_uses_resolver`.
- [ ] **Step 2–4:** FAIL → implement → PASS (full suites).
- [ ] **Step 5:** Commit `feat(customers): appointment and public paths resolve customers by key`.

### Task 5: Startup index handling

**Files:** Modify `backend/server.py` startup customers index block (~1201–1241); Create `backend/customer_indexes.py`; Test `backend/tests/test_customer_indexes.py`.

**Interfaces — Produces:** `async def ensure_customer_indexes(db) -> str`, returning `"created"`, `"exists"` or `"skipped_duplicates"`. It never raises; it keeps the existing non-unique `customers_org_phone_nonunique` and the other existing indexes. The plain unique `(organization_id, phone)` attempt is removed.

- [ ] **Step 1: Failing tests:**
  - `test_no_plain_unique_attempt` (assert `create_index` is never called with `unique=True` on `[("organization_id",1),("phone",1)]`);
  - `test_partial_index_spec_exact`;
  - `test_duplicate_keys_logged_not_raised`.
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** Commit `feat(customers): partial unique phone_key index at startup; drop plain unique attempt`.

### Task 6: Merge engine

**Files:** Create `backend/customer_merge.py`; Test `backend/tests/test_customer_merge.py` (FakeDB) and `backend/tests/test_customer_merge_mongo.py` (real Mongo, skipped without `PK_TEST_MONGO_URL`).

**Interfaces — Produces:**
- `@dataclass DuplicateGroup(organization_id: str, key: str, members: list[dict], klass: Literal["A","B","CD"], survivor_id: str)`.
  - Class A: same normalized name. Class B: `names_match(allow_subset=True)` pairwise. Otherwise CD.
  - Survivor: most `total_appointments`, then oldest `created_at`.
- `async def find_duplicate_groups(db, organization_id: str | None = None) -> list[DuplicateGroup]`
- `async def reference_counts(db, group: DuplicateGroup) -> dict[str, int]`, keyed by collection: `appointments`, `customer_notes`, `marketing_autopilot_tasks`, `merchant_transactions`, `refund_requests`, `stripe_customers`.
- `async def merge_into(db, organization_id: str, survivor_id: str, source_id: str, *, backup: list | None = None) -> dict`. It re-points references from the source's phone to the survivor's phone, using exact field names from the spec. When both share the exact phone string, appointments stay untouched. `customer_notes` are re-pointed and concatenated if single-per-phone. `stripe_customers` are re-pointed only if the survivor has none. Notes are concatenated with `"\n"`. The source document is deleted. Survivor counters and first/last dates are recomputed from appointments matched by `find_customer_for` semantics. Every touched document's prior state is appended to `backup`. Returns a summary.
- `async def mark_not_duplicate(db, organization_id: str, customer_id: str) -> None` (unsets `merge_suggestion_for`, keeps `shared_phone`).

- [ ] **Step 1: Failing tests:**
  - `test_classification_A_B_CD` (use the Faz 0 shapes: "Canan Çelik"/"Canan Çelik Müşteri"=A, "Melek Hilal Kaplan"/"Melek Hilal Ölmez Kaplan"=B, "Makbule"/"Kadir Burak"=CD);
  - `test_survivor_most_appointments_then_oldest`;
  - `test_merge_repoints_all_references_and_recomputes` (real Mongo);
  - `test_merge_backup_restores_exact_state` (real Mongo: apply → restore from backup → identical);
  - `test_merge_idempotent_second_run_noop`.
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** Commit `feat(customers): duplicate classification and merge engine`.

### Task 7: Rollout script

**Files:** Create `backend/scripts/customer_phone_key.py`; Test `backend/tests/test_customer_phone_key_script_mongo.py` (real Mongo).

**Interfaces:** CLI subcommands, all requiring `--dry-run` or `--apply` (`--apply` also requires `--backup-dir`, which must not exist yet):
- `backfill`: keys every customer with a usable number. Inside duplicate groups it keys only the survivor (builder decision 6). Report: counts per org, unkeyed reasons.
- `merge`: classes A and B merge into the survivor. Class CD: non-survivors get `shared_phone: true` and no key. Report: one line per group with org id prefix, class, member count, reference counts. Customer names are shown only as initials, because the report is reviewed in chat.
- `index`: runs `ensure_customer_indexes`, then fails loudly if any duplicate key remains.
- `verify`: checks that no keyed duplicates exist, that every appointment phone resolves to a customer, and that counters equal recomputed values.

Each `--apply` writes a JSON backup plus `restore.py` instructions into the backup dir. The script reads `MONGO_URL`/`DB_NAME` from env and prints the target DB name before acting.

- [ ] **Step 1: Failing tests:**
  - `test_dry_run_writes_nothing`;
  - `test_backfill_then_merge_then_index_then_verify_clean`;
  - `test_apply_requires_fresh_backup_dir`;
  - `test_rerun_is_noop`.
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** Commit `feat(customers): owner-gated rollout script (backfill, merge, index, verify)`.

### Task 8: Suggestion and merge API

**Files:** Modify `backend/server.py` (new routes next to the customer routes; customer list projection gains the additive `shared_phone` and `merge_suggestion_for`); Test `backend/tests/integration/test_customer_merge_api.py`.

**Interfaces — Produces:**
- `POST /api/customers/merge`, body `{survivor_id, source_id}`, admin only. Both ids must be in the caller's org (else 404). Calls `merge_into`. Returns `{merged: true, survivor_id}`.
- `POST /api/customers/{customer_id}/not-duplicate`, admin only. Calls `mark_not_duplicate`. Returns `{ok: true}`.
- `GET /api/customers` items include `shared_phone`/`merge_suggestion_for` when present (additive only).

- [ ] **Step 1: Failing tests:**
  - `test_merge_endpoint_org_scoped` (other org's id → 404);
  - `test_merge_endpoint_staff_403`;
  - `test_not_duplicate_clears_suggestion`;
  - `test_list_includes_suggestion_fields_additively` (legacy keys unchanged).
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** Commit `feat(customers): merge and not-duplicate endpoints`.

### Task 9: Frontend — "same person?" prompt and merge suggestion

**Files:** Modify `frontend/src/components/Customers.js` (add-customer submit ~362; list rows); Create `frontend/src/components/SamePersonPrompt.js`, `frontend/src/components/MergeSuggestion.js`; i18n TR/EN keys under `customers.samePerson.*` and `customers.mergeSuggestion.*` (exact copy in Global Constraints); Tests `frontend/src/components/SamePersonPrompt.test.js`, `MergeSuggestion.test.js`. Run modern-web-guidance before UI work (CLAUDE.md) and use an accessible dialog (existing `ui/dialog`).

**Interfaces:** Consumes the Task 3 400 behaviour and `allow_shared_phone`, plus the Task 8 endpoints.
- On a 400 duplicate from `POST /customers`: call `GET /customers?search=<digits>&limit=5` to get the existing name (no contract change), then show the prompt.
  - **Aynı kişi:** close and open the existing customer.
  - **Farklı kişi:** re-post with `allow_shared_phone: true`.
- Rows with `merge_suggestion_for` show the suggestion.
  - **Birleştir:** `POST /customers/merge` with `{survivor_id: merge_suggestion_for, source_id: row.id}`.
  - **Farklı kişi:** `POST /customers/{id}/not-duplicate`.
  - Either action refreshes the list.

- [ ] **Step 1: Failing jest tests:**
  - `shows existing name and both choices`;
  - `different person resends with allow_shared_phone`;
  - `merge calls endpoint with survivor and source`;
  - `different person clears suggestion`.
- [ ] **Step 2–4:** FAIL → implement → PASS; full jest suite plus `craco build` succeed.
- [ ] **Step 5:** Commit `feat(customers): same-person prompt and merge suggestion`.

---

## Rollout (owner-gated; not a task — the controller runs it with explicit owner approval at each numbered gate)

1. **Code deploy.** Merge, then build the backend code-only and the web from `git archive`; OTA via Capgo internal, then production.
   - New writes start keying.
   - The index does not exist yet. That is expected: `ensure_customer_indexes` returns `skipped_duplicates` and only logs.
2. **Backfill.** Run `backfill --dry-run` and show the report. **Owner approves**, then run `--apply` with a backup dir under `/root/backups/`.
3. **Merge.** Run `merge --dry-run` and show the report. **Owner approves**, then run `--apply` with a backup.
4. **Index.** Run `index --apply`, then `verify`.
5. **Re-run `verify` the next day** and report.
