"""In-memory Redis + Mongo benzeri koleksiyonlar (entegrasyon testleri)."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


class FakeRedis:
    """redis.asyncio ile uyumlu minimal alt küme."""

    def __init__(self):
        self._data: Dict[str, Any] = {}

    async def get(self, key: str):
        return self._data.get(key)

    async def set(self, key: str, value, nx: bool = False, ex: Optional[int] = None):
        if nx and key in self._data:
            return False
        self._data[key] = value
        return True

    async def setnx(self, key: str, value):
        if key in self._data:
            return False
        self._data[key] = value
        return True

    async def delete(self, *keys: str):
        for k in keys:
            self._data.pop(k, None)

    async def incr(self, key: str, amount: int = 1):
        value = int(self._data.get(key) or 0) + amount
        self._data[key] = value
        return value

    async def expire(self, key: str, seconds: int):
        """TTL prod'da kullanılır; entegrasyon testinde anahtar yeterli."""
        if key not in self._data:
            return False
        return True

    async def ping(self):
        return True


class MockCursor:
    def __init__(self, items: List[dict]):
        self._items = items

    async def to_list(self, length: int = None):
        return list(self._items)

    def sort(self, *args, **kwargs):
        return self


class AppointmentsColl:
    def __init__(self):
        self.docs: List[dict] = []

    def find(self, query: dict, projection=None, *args, **kwargs):
        matched = []
        for d in self.docs:
            if self._match(query, d):
                matched.append({k: v for k, v in d.items() if k != "_id"})
        return MockCursor(matched)

    def _match(self, query: dict, doc: dict) -> bool:
        oid = query.get("organization_id")
        if oid and doc.get("organization_id") != oid:
            return False
        if "id" in query and "$in" in query["id"]:
            if doc.get("id") not in query["id"]["$in"]:
                return False
        if "appointment_date" in query and doc.get("appointment_date") != query["appointment_date"]:
            return False
        if "staff_member_id" in query and doc.get("staff_member_id") != query["staff_member_id"]:
            return False
        if "session_group_id" in query:
            sg = query["session_group_id"]
            if isinstance(sg, dict) and "$in" in sg:
                if doc.get("session_group_id") not in sg["$in"]:
                    return False
            elif doc.get("session_group_id") != sg:
                return False
        st = query.get("status")
        if isinstance(st, dict) and "$nin" in st:
            if doc.get("status") in st["$nin"]:
                return False
        return True

    async def insert_many(self, docs: List[dict]):
        for d in docs:
            self.docs.append(dict(d))

    async def update_many(self, query: dict, update: dict):
        n = 0
        for d in self.docs:
            if self._match(query, d):
                if "$set" in update:
                    d.update(update["$set"])
                n += 1
        return MagicModified(n)

    async def find_one(self, query: dict, projection=None):
        for d in self.docs:
            if self._match_simple(query, d):
                out = {k: v for k, v in d.items() if k != "_id"}
                return out
        return None

    def _match_simple(self, query: dict, doc: dict) -> bool:
        for k, v in query.items():
            if k == "$or":
                continue
            if doc.get(k) != v:
                if isinstance(v, dict) and "$in" in v:
                    if doc.get(k) not in v["$in"]:
                        return False
                elif isinstance(v, dict) and "$gte" in v:
                    if (doc.get(k) or 0) < v["$gte"]:
                        return False
                else:
                    return False
        return True


class MagicModified:
    def __init__(self, n):
        self.modified_count = n


class ServicesColl:
    def __init__(self, service_doc: dict):
        self._doc = service_doc

    async def find_one(self, query: dict, projection=None):
        if query.get("id") == self._doc.get("id"):
            return dict(self._doc)
        return None


class SettingsColl:
    """bulk-session / _assert_staff için minimal ayar."""

    def __init__(self, org_id: str):
        self.org_id = org_id

    async def find_one(self, query: dict, projection=None):
        if query.get("organization_id") == self.org_id:
            return {"organization_id": self.org_id, "admin_provides_service": True}
        return None


class OrgPlansColl:
    def __init__(self, org_id: str):
        self.org_id = org_id
        self.quota_usage = 0

    async def find_one(self, query: dict, projection=None):
        if query.get("organization_id") == self.org_id:
            return {
                "organization_id": self.org_id,
                "plan_id": "tier_pro",
                "quota_usage": self.quota_usage,
                "quota_limit": 5000,
                "quota_reset_date": "2099-01-01T00:00:00+00:00",
                "trial_start_date": "2020-01-01T00:00:00+00:00",
                "trial_end_date": "2099-12-31T00:00:00+00:00",
            }
        return None

    async def update_one(self, query: dict, update: dict):
        if "$inc" in update and query.get("organization_id") == self.org_id:
            inc = update["$inc"].get("quota_usage", 0)
            self.quota_usage += inc
        return MagicModified(1)


class MerchantTxColl:
    def __init__(self, txn: Optional[dict] = None):
        self.txn = txn

    async def find_one(self, query: dict, projection=None):
        if not self.txn:
            return None
        if query.get("organization_id") != self.txn.get("organization_id"):
            return None
        if query.get("session_group_id") and self.txn.get("session_group_id") != query["session_group_id"]:
            return None
        if query.get("appointment_id") and self.txn.get("appointment_id") != query["appointment_id"]:
            return None
        st = query.get("state", {})
        if isinstance(st, dict) and "$in" in st:
            if self.txn.get("state") not in st["$in"]:
                return None
        return dict(self.txn)

    async def update_one(self, query: dict, update: dict):
        return MagicModified(1)

    async def insert_one(self, doc: dict):
        pass


class MerchantWalletsColl:
    async def update_one(self, query: dict, update: dict):
        return MagicModified(1)


class CustomersColl:
    def __init__(self):
        self.docs: List[dict] = []

    def find(self, query: dict, projection=None, *args, **kwargs):
        oid = query.get("organization_id")
        matched = []
        for d in self.docs:
            if oid and d.get("organization_id") != oid:
                continue
            matched.append({k: v for k, v in d.items() if k != "_id"})
        return MockCursor(matched)

    async def find_one(self, query: dict, projection=None):
        return None

    async def insert_one(self, doc: dict):
        self.docs.append(dict(doc))


class AuditLogsColl:
    async def insert_one(self, doc: dict):
        pass


class OperationAuditColl:
    async def insert_one(self, doc: dict):
        pass


class RefundReconciliationColl:
    """Stripe iade sonrası DB hatası mutabakat kuyruğu (test)."""

    def __init__(self):
        self.docs: List[dict] = []

    async def insert_one(self, doc: dict):
        self.docs.append(dict(doc))


class IntegrationDB:
    """server.get_db_from_request için yeterli yüzey."""

    def __init__(self, org_id: str = "org_test"):
        self.organization_id = org_id
        self.appointments = AppointmentsColl()
        self.services = ServicesColl(
            {
                "id": "svc1",
                "organization_id": org_id,
                "name": "Test Service",
                "duration": 30,
                "price": 100,
            }
        )
        self.organization_plans = OrgPlansColl(org_id)
        self.settings = SettingsColl(org_id)
        self.customers = CustomersColl()
        self.audit_logs = AuditLogsColl()
        self.operation_audit_logs = OperationAuditColl()
        self.refund_reconciliation_pending = RefundReconciliationColl()
        self.merchant_transactions: MerchantTxColl = MerchantTxColl()
        self.merchant_wallets = MerchantWalletsColl()
        self.users = MagicMockUsers()


class MagicMockUsers:
    # Motor: find senkron cursor döndürür; await cursor.to_list() kullanılır.
    def find(self, query, projection=None, *a, **k):
        return MockCursor([])

    async def find_one(self, query, projection=None):
        return None


def make_txn_refund_scenario(org_id: str, group_id: str):
    """cancel-selected refund test için işlem + randevular."""
    txn = {
        "id": "tx_refund_1",
        "organization_id": org_id,
        "session_group_id": group_id,
        "state": "captured",
        "amount_display_minor": 100000,
        "partial_refund_total_minor": 0,
        "stripe_payment_intent_id": "pi_test_integration",
        "base_currency": "TRY",
    }
    appts = [
        {
            "id": "apt1",
            "organization_id": org_id,
            "session_group_id": group_id,
            "session_number": 1,
            "session_total": 2,
            "status": "Bekliyor",
            "staff_member_id": "staff1",
        },
        {
            "id": "apt2",
            "organization_id": org_id,
            "session_group_id": group_id,
            "session_number": 2,
            "session_total": 2,
            "status": "Bekliyor",
            "staff_member_id": "staff1",
        },
    ]
    return txn, appts
