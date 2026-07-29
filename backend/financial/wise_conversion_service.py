"""
PLANN Financial Engine — Wise Conversion Extension Point

Business (işletme müşteri) ödemelerinin GBP→TRY çevrimi için genişletilebilir
arayüz. Abonelik (SUBSCRIPTION) gelirlerine ASLA dokunulmaz — bunlar zaten
merchant_transactions'a girmez ve `payment_type != business` filtresiyle dışlanır.

Bu iterasyonda GERÇEK Wise convert çağrısı YAPILMAZ (NoopWiseConversionService).
Yalnızca:
  - Bağlanabilir arayüz (IWiseConversionService) — ileride WiseConversionService.
  - Tam çalışan üç katmanlı idempotency çatısı (conversion_idempotency.py).

İleride gerçek servis eklenince yalnızca `_perform_conversion` implemente edilir;
idempotency/lock/guard çatısı değişmeden çalışır.
"""

from __future__ import annotations

import abc
import hashlib
import json
import logging
import os
import time
import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

from .payment_types import PaymentType, is_convertible
from .conversion_idempotency import (
    ConversionLock,
    begin_conversion,
    complete_conversion,
    fail_conversion,
    build_idempotency_key,
)

logger = logging.getLogger(__name__)

# Convert için uygun tx state'leri (para settle olmuş / çekilebilir).
CONVERTIBLE_STATES = {"captured", "settled", "available"}

# Geçici (retry edilebilir) hata işaretleri — exponential backoff uygulanır.
_TRANSIENT_MARKERS = (
    "_429", "_500", "_502", "_503", "_504",
    "timeout", "timed out", "connection", "temporarily",
    "insufficient",  # GBP henüz balance'a düşmemiş olabilir → sonra tekrar dene
    "rate limit", "too many requests",
)

# Wise quote'un süresi dolduğunu gösteren işaretler (yeni quote + tekrar dene).
_QUOTE_EXPIRED_MARKERS = ("expired", "quote_expired", "quote has expired", "quote not found")


def _is_transient_error(error: str) -> bool:
    """429/500/timeout/connection/insufficient gibi geçici hatalar → retry+backoff."""
    e = (error or "").lower()
    return any(m in e for m in _TRANSIENT_MARKERS)


def _is_quote_expired_error(error: str) -> bool:
    e = (error or "").lower()
    return any(m in e for m in _QUOTE_EXPIRED_MARKERS)


class IWiseConversionService(abc.ABC):
    """Wise GBP→TRY conversion arayüzü (extension point)."""

    @abc.abstractmethod
    async def convert_transaction(
        self, db, tx: Dict[str, Any], *, redis_client=None
    ) -> Dict[str, Any]:
        """Tek bir business transaction'ı idempotent olarak convert et."""
        raise NotImplementedError

    @abc.abstractmethod
    async def convert_business_payments(
        self, db, *, redis_client=None, limit: int = 100
    ) -> Dict[str, Any]:
        """Convert edilmemiş business ödemelerini toplu tara/işle."""


class BaseWiseConversionService(IWiseConversionService):
    """
    Idempotency + lock + guard çatısını sağlayan taban sınıf.
    Alt sınıflar yalnızca `_perform_conversion` implemente eder.
    """

    #: Alt sınıf gerçek para hareketi yapıyor mu? (Noop için False)
    performs_real_conversion: bool = False

    async def _perform_conversion(self, db, tx: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gerçek GBP→TRY hareketi. Dönüş: {target_try_minor, rate_micro,
        wise_quote_id, conversion_reference}. Taban sınıf implement ETMEZ.
        """
        raise NotImplementedError

    async def convert_transaction(
        self, db, tx: Dict[str, Any], *, redis_client=None
    ) -> Dict[str, Any]:
        tx_id = tx.get("id")
        if not tx_id:
            return {"converted": False, "reason": "missing_tx_id"}

        # Guard 0: sadece convertible payment_type + state.
        if not is_convertible(tx.get("payment_type", PaymentType.BUSINESS.value)):
            return {"converted": False, "reason": "not_convertible_type"}
        if tx.get("converted") is True:
            return {"converted": False, "reason": "already_converted", "idempotent": True}
        if tx.get("state") not in CONVERTIBLE_STATES:
            return {"converted": False, "reason": f"state_not_ready:{tx.get('state')}"}

        idem_key = build_idempotency_key(tx_id, tx.get("stripe_balance_transaction_id"))
        # İki seviyeli lock: tx + (varsa) payout.
        tx_lock = ConversionLock(redis_client, f"conversion_lock:tx:{tx_id}")

        async with tx_lock as tx_locked:
            if not tx_locked:
                return {"converted": False, "reason": "lock_not_acquired", "idempotent": True}

            # Katman 1: unique kayıt aç (yeni) veya backoff sonrası retry devral.
            conversion = await begin_conversion(db, tx)
            if conversion is None:
                return {"converted": False, "reason": "duplicate_or_backoff", "idempotent": True}

            started = time.monotonic()
            try:
                result = await self._perform_conversion(db, tx)
            except Exception as e:
                err = str(e)
                transient = _is_transient_error(err)
                fail_info = await fail_conversion(db, conversion, err, transient=transient)
                logger.error(
                    "Conversion perform failed tx=%s transient=%s retry_count=%d: %s",
                    tx_id, transient, fail_info.get("retry_count", 0), err, exc_info=True,
                )
                return {
                    "converted": False,
                    "reason": "perform_failed",
                    "error": err,
                    "transient": transient,
                    "needs_manual": fail_info.get("needs_manual", False),
                    "retry_count": fail_info.get("retry_count", 0),
                }

            duration_ms = int((time.monotonic() - started) * 1000)

            # Katman 3: atomik converted flag guard.
            flipped = await complete_conversion(
                db,
                conversion=conversion,
                target_try_minor=int(result.get("target_try_minor", 0)),
                rate_micro=int(result.get("rate_micro", 0)),
                wise_quote_id=result.get("wise_quote_id"),
                conversion_reference=str(result.get("conversion_reference", idem_key)),
                wise_movement_id=result.get("wise_movement_id"),
                wise_fee_minor=int(result.get("wise_fee_minor", 0) or 0),
            )

            if flipped:
                self._log_conversion_success(tx, result, duration_ms)

            return {
                "converted": flipped,
                "idempotent": not flipped,
                "reason": "ok" if flipped else "already_flipped",
                "conversion_reference": result.get("conversion_reference"),
            }

    def _log_conversion_success(
        self, tx: Dict[str, Any], result: Dict[str, Any], duration_ms: int
    ) -> None:
        """
        Başarılı her conversion için structured log — muhasebe / destek / reconciliation
        sırasında tüm dönüşümlerin uçtan uca izlenebilmesi için (observability).
        """
        rate_micro = int(result.get("rate_micro", 0) or 0)
        record = {
            "event": "wise_conversion_success",
            "merchant_id": tx.get("organization_id"),
            "merchant_transaction_id": tx.get("id"),
            "stripe_payout_id": tx.get("stripe_payout_id"),
            "stripe_balance_transaction_id": tx.get("stripe_balance_transaction_id"),
            "source_gbp_minor": int(tx.get("amount_settled_gbp_minor") or 0),
            "target_try_minor": int(result.get("target_try_minor", 0) or 0),
            "conversion_rate": round(rate_micro / 1_000_000, 6) if rate_micro else None,
            "rate_micro": rate_micro,
            "wise_fee_minor": int(result.get("wise_fee_minor", 0) or 0),
            "wise_quote_id": result.get("wise_quote_id"),
            "wise_movement_id": result.get("wise_movement_id"),
            "conversion_reference": result.get("conversion_reference"),
            "conversion_duration_ms": duration_ms,
        }
        # Tek satır JSON → log toplayıcılarda kolay parse (structured logging).
        logger.info("wise_conversion_success %s", json.dumps(record, ensure_ascii=False))

    async def _select_candidates(self, db, limit: int) -> List[Dict[str, Any]]:
        """Convert edilmemiş business + settle olmuş tx'leri seç (abonelik hariç)."""
        cursor = db.merchant_transactions.find({
            "payment_type": PaymentType.BUSINESS.value,
            "converted": {"$ne": True},
            "state": {"$in": list(CONVERTIBLE_STATES)},
        }).limit(limit)
        return await cursor.to_list(limit)

    async def convert_business_payments(
        self, db, *, redis_client=None, limit: int = 100
    ) -> Dict[str, Any]:
        candidates = await self._select_candidates(db, limit)
        converted = 0
        skipped = 0
        for tx in candidates:
            res = await self.convert_transaction(db, tx, redis_client=redis_client)
            if res.get("converted"):
                converted += 1
            else:
                skipped += 1
        return {
            "candidates": len(candidates),
            "converted": converted,
            "skipped": skipped,
            "performed_real_conversion": self.performs_real_conversion,
        }


class NoopWiseConversionService(BaseWiseConversionService):
    """
    Gerçek Wise çağrısı YAPMAYAN implementasyon. Idempotency/lock/guard çatısı
    tam çalışır; yalnızca para hareketi (Wise quote/transfer) atlanır.

    `convert_business_payments` üretimde güvenli olması için varsayılan olarak
    DRY (yalnızca aday sayısını döner) çalışır; tekil `convert_transaction`
    çağrısı ise mekanizmayı tam yürütür (testler bunu kullanır).
    """

    performs_real_conversion = False

    async def _perform_conversion(self, db, tx: Dict[str, Any]) -> Dict[str, Any]:
        # Gerçek convert yok: kur/target sıfır, referans 'noop:' önekli.
        idem_key = build_idempotency_key(tx["id"], tx.get("stripe_balance_transaction_id"))
        return {
            "target_try_minor": 0,
            "rate_micro": 0,
            "wise_quote_id": None,
            "conversion_reference": f"noop:{idem_key[:16]}",
        }

    async def convert_business_payments(
        self, db, *, redis_client=None, limit: int = 100, dry_run: bool = True
    ) -> Dict[str, Any]:
        # Üretimde toplu tarama kayıtları YANLIŞLIKLA converted işaretlemesin diye
        # varsayılan dry_run: yalnızca aday sayısını raporlar, hiçbir şeyi değiştirmez.
        if dry_run:
            candidates = await self._select_candidates(db, limit)
            return {
                "candidates": len(candidates),
                "converted": 0,
                "skipped": len(candidates),
                "dry_run": True,
                "note": "NoopWiseConversionService: gerçek convert yapılmadı.",
            }
        return await super().convert_business_payments(
            db, redis_client=redis_client, limit=limit
        )


class WiseConversionService(BaseWiseConversionService):
    """
    GERÇEK Wise GBP→TRY balance conversion implementasyonu.

    Her business transaction'ın `amount_settled_gbp_minor` tutarını PLANN'ın Wise
    GBP balance'ından TRY balance'ına çevirir. SUBSCRIPTION gelirlerine dokunulmaz
    (aday seçimi payment_type=business ile sınırlı; abonelik zaten
    merchant_transactions'a girmez).

    Aday şartı: payout mutabakatı görmüş (stripe_payout_id set) + settle GBP > 0.
    Böylece yalnızca Wise GBP balance'a GERÇEKTEN düşmüş para çevrilir.
    """

    performs_real_conversion = True

    async def _select_candidates(self, db, limit: int) -> List[Dict[str, Any]]:
        cursor = db.merchant_transactions.find({
            "payment_type": PaymentType.BUSINESS.value,
            "converted": {"$ne": True},
            "state": {"$in": list(CONVERTIBLE_STATES)},
            # Yalnızca Stripe payout'u mutabakat görmüş (GBP balance'a düşmüş) tx'ler.
            "stripe_payout_id": {"$exists": True, "$ne": None},
            "amount_settled_gbp_minor": {"$gt": 0},
        }).limit(limit)
        return await cursor.to_list(limit)

    async def _perform_conversion(self, db, tx: Dict[str, Any]) -> Dict[str, Any]:
        from .wise_service import (
            create_balance_conversion_quote,
            execute_balance_conversion,
        )
        from .money import rate_to_micro

        gbp_minor = int(tx.get("amount_settled_gbp_minor") or 0)
        if gbp_minor <= 0:
            raise RuntimeError(
                f"tx {tx.get('id')} amount_settled_gbp_minor yok; convert edilemez"
            )

        # Deterministik idempotence uuid → Wise seviyesinde de çift conversion engeli.
        # KRİTİK: Wise, X-idempotenceUuid'in RFC 4122 v4 (rastgele) FORMATINDA olmasını
        # şart koşar (aksi halde "non.idempotent.transaction: UUID must be randomly
        # generated (version 4)" 400 döner). uuid5 (v5) reddedilir. Bu yüzden idem_key'den
        # türettiğimiz 16 baytın version/variant bitlerini v4'e sabitliyoruz: değer aynı tx
        # için DETERMİNİSTİK kalır (retry idempotent) ama Wise'ın v4 format kontrolünü geçer.
        idem_key = build_idempotency_key(tx["id"], tx.get("stripe_balance_transaction_id"))
        _digest = bytearray(
            hashlib.sha256(f"plann-wise-convert:{idem_key}".encode("utf-8")).digest()[:16]
        )
        _digest[6] = (_digest[6] & 0x0F) | 0x40  # version = 4
        _digest[8] = (_digest[8] & 0x3F) | 0x80  # variant = RFC 4122
        idem_uuid = str(uuid.UUID(bytes=bytes(_digest)))

        # KRİTİK: Wise quote yalnızca ~30 dk geçerlidir. Bu nedenle quote oluşturma ve
        # balance-movement AYNI çağrı içinde, ARDA ARDA (bekleme olmadan) yapılır.
        # Buraya araya bloklayan/uzun süren bir işlem EKLENMEMELİDİR.
        quote = await create_balance_conversion_quote("GBP", "TRY", gbp_minor)
        try:
            movement = await execute_balance_conversion(quote["id"], idem_uuid)
        except RuntimeError as e:
            # Quote expire olduysa (ör. kod değişip araya gecikme girerse): taze quote
            # üret ve AYNI idempotence uuid ile bir kez daha dene (çift çevrim olmaz).
            if _is_quote_expired_error(str(e)):
                logger.warning("Wise quote expired tx=%s — taze quote ile tekrar deneniyor.", tx["id"])
                quote = await create_balance_conversion_quote("GBP", "TRY", gbp_minor)
                movement = await execute_balance_conversion(quote["id"], idem_uuid)
            else:
                raise

        target = movement.get("targetAmount", {}) or {}
        tgt_val = target.get("value", 0)
        target_try_minor = int(
            (Decimal(str(tgt_val)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )
        if target_try_minor <= 0:
            target_try_minor = int(quote.get("target_minor", 0))

        mv_rate = movement.get("rate", 0)
        rate_micro = (
            rate_to_micro(Decimal(str(mv_rate))) if mv_rate else int(quote.get("rate_micro", 0))
        )

        # Wise gerçek ücreti (feeAmounts) — observability/muhasebe için.
        wise_fee_minor = 0
        for fee in movement.get("feeAmounts", []) or []:
            try:
                wise_fee_minor += int(
                    (Decimal(str(fee.get("value", 0))) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                )
            except Exception:
                pass
        if wise_fee_minor == 0:
            wise_fee_minor = int(quote.get("fee_minor", 0) or 0)

        return {
            "target_try_minor": target_try_minor,
            "rate_micro": rate_micro,
            "wise_quote_id": quote.get("id"),
            "wise_movement_id": movement.get("id"),
            "wise_fee_minor": wise_fee_minor,
            "conversion_reference": f"wise:{movement.get('id')}",
        }


# Varsayılan (güvenli) servis: gerçek para hareketi yapmaz.
default_wise_conversion_service: IWiseConversionService = NoopWiseConversionService()

# Gerçek servis instance'ı (config açıksa kullanılır).
_real_wise_conversion_service: IWiseConversionService = WiseConversionService()


def get_wise_conversion_service() -> IWiseConversionService:
    """
    Gerçek servisi yalnızca AÇIKÇA etkinleştirildiğinde döndürür:
      WISE_AUTO_CONVERT_ENABLED=true + WISE_API_TOKEN + WISE_PROFILE_ID.
    Aksi halde Noop (güvenli varsayılan) döner — yanlışlıkla para hareketi olmaz.
    """
    if (
        os.getenv("WISE_AUTO_CONVERT_ENABLED", "false").lower() == "true"
        and os.getenv("WISE_API_TOKEN")
        and os.getenv("WISE_PROFILE_ID")
    ):
        return _real_wise_conversion_service
    return default_wise_conversion_service


async def run_auto_conversion_on_credit(
    db, *, redis_client=None, limit: int = 200
) -> Dict[str, Any]:
    """
    Wise GBP balance kredilendiğinde (balances#credit) tetiklenir.
    Bekleyen (mutabakat görmüş, henüz convert edilmemiş) BUSINESS ödemelerini
    GBP→TRY çevirir. Noop servis aktifse hiçbir şey yapmaz (güvenli).
    """
    svc = get_wise_conversion_service()
    if not getattr(svc, "performs_real_conversion", False):
        logger.info("Wise auto-convert atlandı: Noop servis (WISE_AUTO_CONVERT_ENABLED kapalı).")
        return {"skipped": True, "reason": "noop_service"}
    try:
        res = await svc.convert_business_payments(db, redis_client=redis_client, limit=limit)
        logger.info("Wise auto-convert (GBP credit): %s", res)
        return res
    except Exception as e:
        logger.error("Wise auto-convert (GBP credit) hata: %s", e, exc_info=True)
        return {"error": str(e)}
