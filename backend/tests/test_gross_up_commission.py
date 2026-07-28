"""
PLANN — ALL-IN komisyon senaryo testleri + Conversion idempotency testleri.

Bölüm A: Gross-up senaryo tabloları (%10 fast / %8 standard / %7 vip × 5 tutar).
  Invariant'lar:
    - seller_pays → merchant_net == net_target - platform_fee (stripe/wise ETKİSİZ)
    - buyer_pays  → merchant_net == net_target, customer_price == net_target + platform_fee
    - Efektif oran = platform_fee / net_target (tier% + sabit)
    - Stripe/Wise merchant_net'e HİÇ yansımaz (all-in kuralı)
Bölüm B: apply_bps Decimal + ROUND_HALF_UP parity.
Bölüm C: Conversion idempotency (aynı tx/payout iki kez → tek convert; duplicate skip; race).
"""

import asyncio
import pytest

from financial.gross_up_service import compute_customer_price
from financial.fee_calculator import DepositRule
from financial.money import apply_bps, get_tier_config


TIERS = [("fast", 1000), ("standard", 800), ("vip", 700)]   # (tier, bps)
AMOUNTS_MINOR = [50_000, 109_000, 250_000, 650_000, 1_000_000]  # ₺500 .. ₺10.000
TRY_FIXED = 1_500


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("STRIPE_FEE_TR_BPS", "250")
    monkeypatch.setenv("STRIPE_FEE_TR_FIXED", "150")
    monkeypatch.setenv("WISE_PAYOUT_BPS", "0")
    monkeypatch.setenv("WISE_PAYOUT_FIXED_MINOR", "200")


# ===========================================================================
# Bölüm A — Senaryo invariant'ları
# ===========================================================================

@pytest.mark.parametrize("tier,bps", TIERS)
@pytest.mark.parametrize("amount", AMOUNTS_MINOR)
def test_seller_pays_all_in(tier, bps, amount):
    r = compute_customer_price(
        base_currency="TRY",
        service_price_minor=amount,
        fee_preference="seller_pays",
        tier=tier,
        deposit_rule=DepositRule(payment_rule="full_online"),
    )
    expected_commission = apply_bps(amount, bps) + TRY_FIXED
    assert r.platform_fee_minor == expected_commission
    # ALL-IN: net = tutar - SADECE komisyon
    assert r.merchant_net_minor == amount - expected_commission
    # customer müşteri tam tutarı öder
    assert r.customer_price_minor == amount


@pytest.mark.parametrize("tier,bps", TIERS)
@pytest.mark.parametrize("amount", AMOUNTS_MINOR)
def test_buyer_pays_all_in(tier, bps, amount):
    r = compute_customer_price(
        base_currency="TRY",
        service_price_minor=amount,
        fee_preference="buyer_pays",
        tier=tier,
        deposit_rule=DepositRule(payment_rule="full_online"),
    )
    expected_commission = apply_bps(amount, bps) + TRY_FIXED
    assert r.platform_fee_minor == expected_commission
    # İşletme tam tutarı alır; komisyon müşteriye eklenir
    assert r.merchant_net_minor == amount
    assert r.customer_price_minor == amount + expected_commission
    # 1:1 garantisi: müşteri - net == komisyon
    assert r.customer_price_minor - r.merchant_net_minor == expected_commission


@pytest.mark.parametrize("tier,bps", TIERS)
@pytest.mark.parametrize("amount", AMOUNTS_MINOR)
def test_stripe_wise_never_hit_merchant(tier, bps, amount, monkeypatch):
    """Stripe/Wise bps absürt yükseltilse bile merchant_net değişmez (all-in)."""
    monkeypatch.setenv("STRIPE_FEE_TR_BPS", "9000")
    monkeypatch.setenv("STRIPE_FEE_TR_FIXED", "99999")
    monkeypatch.setenv("WISE_PAYOUT_FIXED_MINOR", "99999")
    r = compute_customer_price(
        base_currency="TRY",
        service_price_minor=amount,
        fee_preference="seller_pays",
        tier=tier,
        deposit_rule=DepositRule(payment_rule="full_online"),
    )
    expected_commission = apply_bps(amount, bps) + TRY_FIXED
    assert r.merchant_net_minor == amount - expected_commission  # değişmedi


def test_effective_rate_matches_promised(capsys):
    """Efektif oran = komisyon/tutar; tabloyu rapora yazdırır."""
    print("\n| Tier | Tutar(₺) | Komisyon(₺) | Net(₺) | Efektif % |")
    print("|------|----------|-------------|--------|-----------|")
    for tier, bps in TIERS:
        for amount in AMOUNTS_MINOR:
            r = compute_customer_price(
                base_currency="TRY", service_price_minor=amount,
                fee_preference="seller_pays", tier=tier,
                deposit_rule=DepositRule(payment_rule="full_online"),
            )
            eff = r.platform_fee_minor / amount * 100
            base_pct = bps / 100
            # Efektif oran = taban % + sabit ücretin katkısı (sabit her zaman ekler)
            assert eff >= base_pct
            print(f"| {tier} | {amount/100:.0f} | {r.platform_fee_minor/100:.2f} | "
                  f"{r.merchant_net_minor/100:.2f} | {eff:.2f}% |")


# ===========================================================================
# Bölüm B — apply_bps Decimal parity
# ===========================================================================

def test_apply_bps_decimal_parity():
    """Yeni Decimal implementasyonu, negatif olmayan girdilerde eski formülle aynı."""
    for amount in [0, 1, 99, 100, 12_345, 999_999, 1_000_000, 7_777_777]:
        for bps in [0, 1, 150, 250, 700, 800, 1000, 9999]:
            legacy = (amount * bps + 5_000) // 10_000
            assert apply_bps(amount, bps) == legacy, (amount, bps)


def test_apply_bps_round_half_up():
    # 100 * 150 / 10000 = 1.5 → ROUND_HALF_UP = 2
    assert apply_bps(100, 150) == 2
    # 100 * 149 / 10000 = 1.49 → 1
    assert apply_bps(100, 149) == 1


# ===========================================================================
# Bölüm C — Conversion idempotency
# ===========================================================================

try:
    from pymongo.errors import DuplicateKeyError
except Exception:  # pragma: no cover
    class DuplicateKeyError(Exception):
        pass


class _UniqueMockCollection:
    """Unique index'leri simüle eden minimal async koleksiyon."""

    def __init__(self, unique_keys=None):
        self._docs = []
        self._unique_keys = unique_keys or []

    def _violates_unique(self, doc, skip_index=None):
        for i, existing in enumerate(self._docs):
            if i == skip_index:
                continue
            for key in self._unique_keys:
                if key in doc and doc.get(key) is not None and existing.get(key) == doc.get(key):
                    return True
        return False

    async def insert_one(self, doc):
        d = dict(doc)
        if self._violates_unique(d):
            raise DuplicateKeyError(f"E11000 duplicate key: {self._unique_keys}")
        self._docs.append(d)
        return type("R", (), {"inserted_id": d.get("id", len(self._docs))})()

    @staticmethod
    def _match(doc, query):
        for k, v in query.items():
            if isinstance(v, dict):
                if "$ne" in v and doc.get(k) == v["$ne"]:
                    return False
                if "$in" in v and doc.get(k) not in v["$in"]:
                    return False
            elif doc.get(k) != v:
                return False
        return True

    async def find_one(self, query):
        for d in self._docs:
            if self._match(d, query):
                return dict(d)
        return None

    def find(self, query):
        matched = [dict(d) for d in self._docs if self._match(d, query)]

        class _Cursor:
            def __init__(self, docs):
                self._docs = docs

            def limit(self, n):
                self._docs = self._docs[:n]
                return self

            async def to_list(self, n):
                return self._docs[:n]

        return _Cursor(matched)

    async def find_one_and_update(self, query, update):
        for d in self._docs:
            ok = True
            for k, v in query.items():
                if d.get(k) != v:
                    ok = False
                    break
            if ok:
                before = dict(d)
                for k, v in update.get("$set", {}).items():
                    d[k] = v
                return before
        return None

    async def update_one(self, query, update):
        for d in self._docs:
            if all(d.get(k) == v for k, v in query.items()):
                for k, v in update.get("$set", {}).items():
                    d[k] = v
                return type("R", (), {"modified_count": 1})()
        return type("R", (), {"modified_count": 0})()


class _MockDB:
    def __init__(self):
        self.conversions = _UniqueMockCollection(unique_keys=[
            "idempotency_key", "merchant_transaction_id", "stripe_balance_transaction_id",
        ])
        self.merchant_transactions = _UniqueMockCollection(unique_keys=["id"])


async def _seed_tx(db, tx_id="tx1", **over):
    doc = {
        "id": tx_id,
        "organization_id": "org1",
        "payment_type": "business",
        "state": "settled",
        "converted": False,
        "amount_settled_gbp_minor": 10_000,
        "stripe_balance_transaction_id": f"btxn_{tx_id}",
        "stripe_payout_id": "po_1",
    }
    doc.update(over)
    await db.merchant_transactions.insert_one(doc)
    return doc


@pytest.mark.asyncio
async def test_convert_twice_single_conversion():
    from financial.wise_conversion_service import NoopWiseConversionService
    db = _MockDB()
    tx = await _seed_tx(db)
    svc = NoopWiseConversionService()

    r1 = await svc.convert_transaction(db, tx, redis_client=None)
    assert r1["converted"] is True

    # İkinci deneme aynı tx (DB'den tazele) → duplicate skip
    tx2 = await db.merchant_transactions.find_one({"id": "tx1"})
    r2 = await svc.convert_transaction(db, tx2, redis_client=None)
    assert r2["converted"] is False
    assert r2.get("idempotent") is True

    # Tek conversion kaydı + converted bir kez True
    assert len(db.conversions._docs) == 1
    final = await db.merchant_transactions.find_one({"id": "tx1"})
    assert final["converted"] is True


@pytest.mark.asyncio
async def test_duplicate_balance_txn_rejected():
    """Aynı balance_transaction_id ile ikinci tx convert → unique constraint skip."""
    from financial.wise_conversion_service import NoopWiseConversionService
    db = _MockDB()
    tx_a = await _seed_tx(db, tx_id="txA")
    # Farklı tx id ama AYNI balance txn (mükerrer kaynak)
    tx_b = await _seed_tx(db, tx_id="txB", stripe_balance_transaction_id="btxn_txA")
    svc = NoopWiseConversionService()

    ra = await svc.convert_transaction(db, tx_a, redis_client=None)
    rb = await svc.convert_transaction(db, tx_b, redis_client=None)
    assert ra["converted"] is True
    assert rb["converted"] is False  # aynı balance txn → skip
    assert len(db.conversions._docs) == 1


@pytest.mark.asyncio
async def test_concurrent_convert_only_one_wins():
    """Race: aynı tx için eşzamanlı iki convert → yalnızca biri flip eder."""
    from financial.wise_conversion_service import NoopWiseConversionService
    db = _MockDB()
    tx = await _seed_tx(db)
    svc = NoopWiseConversionService()

    tx_copy1 = await db.merchant_transactions.find_one({"id": "tx1"})
    tx_copy2 = await db.merchant_transactions.find_one({"id": "tx1"})
    results = await asyncio.gather(
        svc.convert_transaction(db, tx_copy1, redis_client=None),
        svc.convert_transaction(db, tx_copy2, redis_client=None),
    )
    converted_flags = [r["converted"] for r in results]
    assert converted_flags.count(True) == 1   # yalnızca biri
    assert len(db.conversions._docs) == 1


@pytest.mark.asyncio
async def test_subscription_never_converted():
    from financial.wise_conversion_service import NoopWiseConversionService
    db = _MockDB()
    tx = await _seed_tx(db, payment_type="subscription")
    svc = NoopWiseConversionService()
    r = await svc.convert_transaction(db, tx, redis_client=None)
    assert r["converted"] is False
    assert r["reason"] == "not_convertible_type"
    assert len(db.conversions._docs) == 0


@pytest.mark.asyncio
async def test_noop_sweep_is_dry_by_default():
    from financial.wise_conversion_service import NoopWiseConversionService
    db = _MockDB()
    await _seed_tx(db)
    svc = NoopWiseConversionService()
    out = await svc.convert_business_payments(db, redis_client=None)
    assert out["dry_run"] is True
    assert out["converted"] == 0
    # DB değişmedi
    tx = await db.merchant_transactions.find_one({"id": "tx1"})
    assert tx["converted"] is False
