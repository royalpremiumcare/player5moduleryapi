"""
PLANN Financial Engine — Conversion Idempotency

Aynı Stripe payout veya aynı merchant transaction HİÇBİR koşulda ikinci kez
convert edilemez. Üç katmanlı savunma:

  1) Unique constraint (birincil):  `conversions` koleksiyonu — `idempotency_key`
     (deterministik sha256), `merchant_transaction_id` ve
     `stripe_balance_transaction_id` üzerinde unique index. İkinci deneme
     DuplicateKeyError alır → sessizce skip.
  2) Distributed lock (race):       Redis `SET NX EX` (proje `reminder_lock` deseni).
     Redis yoksa yalnızca unique constraint'e düşülür (fail-safe).
  3) State/flag guard (mantıksal):  `merchant_transactions.converted` üzerinde
     atomik `find_one_and_update({id, converted:False}, ...)` optimistic-lock.

Bu modül mekanizmayı sağlar; gerçek GBP→TRY hareketi wise_conversion_service.py'de
(şimdilik Noop) yapılır.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# pymongo DuplicateKeyError'ı yumuşak import (test ortamında yoksa kırılmasın).
try:  # pragma: no cover
    from pymongo.errors import DuplicateKeyError
except Exception:  # pragma: no cover
    class DuplicateKeyError(Exception):
        pass


_LOCK_TTL_SECONDS = 300

# Retry politikası (reliability)
MAX_RETRY_COUNT = 5                 # bu eşikten sonra otomatik retry DURUR → needs_manual
_BACKOFF_BASE_SECONDS = 60          # exponential backoff taban süresi
_BACKOFF_MAX_SECONDS = 1800         # tavan (30 dk)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _backoff_seconds(retry_count: int) -> int:
    """Exponential backoff: 60s, 120s, 240s, 480s, ... (tavan 30 dk)."""
    if retry_count <= 0:
        return 0
    delay = _BACKOFF_BASE_SECONDS * (2 ** (retry_count - 1))
    return min(delay, _BACKOFF_MAX_SECONDS)


def _seconds_since(iso_ts: Optional[str]) -> float:
    """Verilen ISO zamanından bu yana geçen saniye (parse edilemezse sonsuz)."""
    if not iso_ts:
        return float("inf")
    try:
        then = datetime.fromisoformat(iso_ts)
        if then.tzinfo is None:
            then = then.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - then).total_seconds()
    except Exception:
        return float("inf")


def build_idempotency_key(merchant_transaction_id: str,
                          stripe_balance_transaction_id: Optional[str]) -> str:
    """Deterministik idempotency anahtarı. Aynı (tx, balance_txn) → aynı hash."""
    raw = f"{merchant_transaction_id}:{stripe_balance_transaction_id or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ConversionLock:
    """
    Redis SET NX EX distributed lock (async context manager).
    Redis yoksa lock 'başarılı' sayılır (fail-safe: unique constraint devreye girer).
    """

    def __init__(self, redis_client, key: str, ttl: int = _LOCK_TTL_SECONDS):
        self.redis = redis_client
        self.key = key
        self.ttl = ttl
        self.acquired = False

    async def __aenter__(self) -> bool:
        if self.redis is None:
            self.acquired = True  # fail-safe
            return True
        try:
            ok = await self.redis.set(self.key, "1", nx=True, ex=self.ttl)
            self.acquired = bool(ok)
        except Exception as e:
            logger.warning("Conversion lock redis error (fail-safe open): %s", e)
            self.acquired = True  # Redis hatasında unique constraint'e güven
        return self.acquired

    async def __aexit__(self, exc_type, exc, tb):
        if self.redis is None or not self.acquired:
            return
        try:
            await self.redis.delete(self.key)
        except Exception as e:
            logger.warning("Conversion lock release error (non-fatal): %s", e)


async def _resume_or_block(db, idem_key: str, tx_id: str) -> Optional[Dict[str, Any]]:
    """
    Var olan conversion kaydını retry için 'devral' veya blokla.

    Dönüş:
      - dict  → retry hakkı var, backoff süresi doldu → çağıran devam edebilir.
      - None  → tamamlanmış / manuel müdahale gerektiriyor / backoff süresi dolmadı.
    """
    existing = await db.conversions.find_one({"idempotency_key": idem_key})
    if not existing:
        return None

    status = existing.get("status")
    if status == "converted":
        return None  # zaten başarıyla çevrilmiş

    retry_count = int(existing.get("retry_count", 0) or 0)

    # Eşik aşıldı → otomatik retry DUR, manuel müdahale gerek.
    if status == "needs_manual" or retry_count >= MAX_RETRY_COUNT:
        if status != "needs_manual":
            await db.conversions.update_one(
                {"idempotency_key": idem_key},
                {"$set": {"status": "needs_manual", "updated_at": _utcnow()}},
            )
        logger.warning(
            "Conversion needs MANUAL intervention (retry_count=%d>=%d) tx=%s",
            retry_count, MAX_RETRY_COUNT, tx_id,
        )
        return None

    # Backoff: son denemeden bu yana yeterli süre geçmediyse şimdilik atla.
    delay = _backoff_seconds(retry_count)
    elapsed = _seconds_since(existing.get("last_retry_at"))
    if elapsed < delay:
        logger.info(
            "Conversion retry backoff tx=%s retry_count=%d elapsed=%.0fs<%ds — skip.",
            tx_id, retry_count, elapsed, delay,
        )
        return None

    # Retry'ı devral: converting'e al (per-tx Redis lock zaten yarışı engelliyor).
    await db.conversions.update_one(
        {"idempotency_key": idem_key},
        {"$set": {"status": "converting", "updated_at": _utcnow()}},
    )
    existing["status"] = "converting"
    logger.info("Conversion retry #%d başlıyor tx=%s", retry_count + 1, tx_id)
    return existing


async def begin_conversion(db, tx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    `conversions` koleksiyonunda pending kayıt açar (unique constraint katmanı).

    Dönüş:
      - dict  → conversion kaydı (yeni veya retry-devralınmış) → devam edilebilir.
      - None  → zaten çevrilmiş / manuel gerek / backoff bekliyor → skip.
    """
    tx_id = tx.get("id")
    if not tx_id:
        return None

    bt_id = tx.get("stripe_balance_transaction_id")
    idem_key = build_idempotency_key(tx_id, bt_id)

    doc: Dict[str, Any] = {
        "idempotency_key": idem_key,
        "merchant_transaction_id": tx_id,
        "organization_id": tx.get("organization_id", ""),
        "stripe_payout_id": tx.get("stripe_payout_id"),
        "stripe_balance_transaction_id": bt_id,
        "status": "converting",
        "source_currency": "GBP",
        "target_currency": "TRY",
        "source_gbp_minor": int(tx.get("amount_settled_gbp_minor") or 0),
        "target_try_minor": 0,
        "rate_micro": 0,
        "retry_count": 0,
        "last_retry_at": None,
        "last_error": None,
        "created_at": _utcnow(),
        "updated_at": _utcnow(),
    }
    # None sparse alanları çıkar (sparse unique index null'ları reddetmesin).
    for k in ("stripe_payout_id", "stripe_balance_transaction_id"):
        if doc.get(k) is None:
            doc.pop(k, None)

    try:
        result = await db.conversions.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc
    except DuplicateKeyError:
        # Kayıt zaten var → başarılıysa skip, başarısızsa (retry hakkı + backoff) devral.
        return await _resume_or_block(db, idem_key, tx_id)
    except Exception as e:
        # Motor bazı sürümlerde DuplicateKeyError'ı farklı sarabilir; mesajdan tespit.
        if "duplicate key" in str(e).lower() or "E11000" in str(e):
            return await _resume_or_block(db, idem_key, tx_id)
        logger.error("begin_conversion insert failed tx=%s: %s", tx_id, e, exc_info=True)
        raise


async def complete_conversion(
    db,
    *,
    conversion: Dict[str, Any],
    target_try_minor: int,
    rate_micro: int,
    wise_quote_id: Optional[str],
    conversion_reference: str,
    wise_movement_id: Optional[str] = None,
    wise_fee_minor: int = 0,
) -> bool:
    """
    State/flag guard katmanı: atomik find_one_and_update ile `converted` flag'ini
    False→True çevirir (optimistic lock). Yalnızca gerçekten flip eden çağıran True döner.
    """
    tx_id = conversion["merchant_transaction_id"]
    now = _utcnow()

    updated = await db.merchant_transactions.find_one_and_update(
        {"id": tx_id, "converted": False},
        {"$set": {
            "converted": True,
            "converted_at": now,
            "conversion_reference": conversion_reference,
            "amount_settled_try_minor": target_try_minor,
            "updated_at": now,
        }},
    )

    await db.conversions.update_one(
        {"idempotency_key": conversion["idempotency_key"]},
        {"$set": {
            "status": "converted",
            "target_try_minor": target_try_minor,
            "rate_micro": rate_micro,
            "wise_quote_id": wise_quote_id,
            "wise_movement_id": wise_movement_id,
            "wise_fee_minor": wise_fee_minor,
            "conversion_reference": conversion_reference,
            "updated_at": now,
        }},
    )

    if updated is None:
        # Başka bir çağıran zaten flip etmiş — çift conversion engellendi.
        logger.info("Conversion flag already set for tx=%s (guard caught duplicate).", tx_id)
        return False
    return True


async def fail_conversion(
    db,
    conversion: Dict[str, Any],
    error: str,
    *,
    transient: bool = True,
) -> Dict[str, Any]:
    """
    Conversion'ı başarısız işaretle ve retry sayacını artır. converted flag'e
    DOKUNULMAZ (retry güvenli).

    - retry_count her başarısızlıkta +1 artar.
    - Kalıcı hata (transient=False) VEYA retry_count >= MAX_RETRY_COUNT ise
      status='needs_manual' olur → otomatik retry durur, manuel müdahale gerekir.
    - Geçici hata (429/500/timeout vb.) ise status='failed' kalır ve backoff ile
      sonraki tetiklemede yeniden denenir.

    Dönüş: {"status": ..., "retry_count": ..., "needs_manual": bool}
    """
    idem_key = conversion["idempotency_key"]
    now = _utcnow()

    existing = await db.conversions.find_one({"idempotency_key": idem_key})
    retry_count = int((existing or {}).get("retry_count", 0) or 0) + 1

    needs_manual = (not transient) or (retry_count >= MAX_RETRY_COUNT)
    status = "needs_manual" if needs_manual else "failed"

    await db.conversions.update_one(
        {"idempotency_key": idem_key},
        {"$set": {
            "status": status,
            "retry_count": retry_count,
            "last_retry_at": now,
            "last_error": error[:500],
            "error_message": error[:500],
            "updated_at": now,
        }},
    )

    tx_id = conversion.get("merchant_transaction_id")
    if needs_manual:
        logger.error(
            "Conversion FAILED (manuel gerek): tx=%s retry_count=%d transient=%s err=%s",
            tx_id, retry_count, transient, error[:200],
        )
    else:
        logger.warning(
            "Conversion failed (retry edilecek): tx=%s retry_count=%d err=%s",
            tx_id, retry_count, error[:200],
        )

    return {"status": status, "retry_count": retry_count, "needs_manual": needs_manual}
