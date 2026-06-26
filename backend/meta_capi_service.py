"""
Meta Conversions API (CAPI) Service.

Mimari özet:
  - Frontend, Meta Pixel'e olayı fırlatırken benzersiz bir `event_id` üretir
    (UUIDv4) ve aynı `event_id`'yi backend'e POST eder.
  - Backend (bu servis), aynı `event_id` ile Conversions API'a server-side
    olayı yollar. Meta, `event_id` eşleşmesi sayesinde olayı tekilleştirir
    (deduplication) — tarayıcı engellerini aşmak için hibrit takip.

Kullanım:
    from meta_capi_service import get_meta_capi_service

    svc = get_meta_capi_service()
    background_tasks.add_task(
        svc.send_event,
        event_name="Lead",
        event_id="...",
        event_source_url="https://plannapp.co/",
        action_source="website",
        client_ip="1.2.3.4",
        client_user_agent="Mozilla/...",
        user_data={"em": "x@y.com", "ph": "905551112233", "fn": "Ali", "ln": "Veli"},
        custom_data={"content_name": "Royal Salon", "value": 1990, "currency": "TRY"},
        fbp=None, fbc=None, external_id=None,
        test_event_code=None,
    )

Tasarım kararları:
  - PII (em/ph/fn/ln/external_id) SHA256 ile normalize+hash edilir.
  - `requests` (sync) kullanılır; FastAPI BackgroundTasks sync fonksiyonu
    threadpool'da çalıştırır. Böylece kullanıcının request'ini bloklamaz.
  - PIXEL_ID veya ACCESS_TOKEN yoksa servis sessizce no-op olur (dev/test
    ortamında deploy edilebilirlik).
  - Hatalar logger.warning ile yutulur — analytics, ürün akışını kırmamalı.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import time
import uuid
from typing import Any, Dict, Iterable, Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------
META_GRAPH_BASE = "https://graph.facebook.com"

# Meta CAPI tarafından önceden tanımlı standart event isimleri.
# Custom event'lere de izin veriyoruz; bu set sadece "bilinen" olayları işaretler.
STANDARD_EVENTS: frozenset = frozenset({
    "PageView",
    "ViewContent",
    "Search",
    "AddToCart",
    "AddToWishlist",
    "InitiateCheckout",
    "AddPaymentInfo",
    "Purchase",
    "Lead",
    "CompleteRegistration",
    "Contact",
    "CustomizeProduct",
    "Donate",
    "FindLocation",
    "Schedule",
    "StartTrial",
    "SubmitApplication",
    "Subscribe",
})

# action_source whitelist — Meta CAPI'da kabul edilen değerler.
VALID_ACTION_SOURCES: frozenset = frozenset({
    "email", "website", "app", "phone_call", "chat",
    "physical_store", "system_generated", "business_messaging", "other",
})

# user_data alanlarından SHA256 hashleneceklerin listesi.
# (em/ph/fn/ln/ge/db/ct/st/zp/country/external_id Meta tarafından hashli beklenir.)
HASHED_USER_DATA_FIELDS: frozenset = frozenset({
    "em", "ph", "fn", "ln", "ge", "db", "ct", "st", "zp", "country", "external_id",
})


# ---------------------------------------------------------------------------
# Hashing & normalizasyon yardımcıları
# ---------------------------------------------------------------------------
def _sha256(value: str) -> str:
    """UTF-8 SHA256 hex digest döner."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _is_already_hashed(value: str) -> bool:
    """Hex 64 karakter ise hashli kabul et (Meta tarafından yeniden hashlenmesin)."""
    return len(value) == 64 and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _norm_email(email: str) -> str:
    return email.strip().lower()


def _norm_phone(phone: str) -> str:
    """
    Meta formatı: ülke kodu dahil, başında '+' veya '0' yok, boşluksuz rakamlar.
    Örnek: '+90 (532) 111 22 33'  →  '905321112233'
           '05321112233'          →  '905321112233'
           '5321112233'           →  '905321112233'  (varsayılan TR, 10 hane)
           '905321112233'         →  '905321112233'  (zaten doğru)
           '447911123456'         →  '447911123456'  (UK — dokunma)

    Kural:
      1. Tüm non-digit karakterleri sil.
      2. Başında '0' varsa (yerel TR formatı) → '0' kaldır, '90' ekle.
      3. 10 hane kaldıysa (TR'de ülke kodu olmadan 5xx/2xx vb.) → başa '90' ekle.
      4. Aksi hâlde olduğu gibi bırak (uluslararası format zaten doğru).
    """
    digits = re.sub(r"\D", "", phone or "")
    if not digits:
        return digits
    # Yerel format: 0 ile başlayan 11 hane (örn. 05321112233)
    if digits.startswith("0") and len(digits) == 11:
        digits = "90" + digits[1:]
    # Ülke kodu olmayan 10 hane (örn. 5321112233)
    elif len(digits) == 10 and not digits.startswith("0"):
        digits = "90" + digits
    return digits


def _norm_name(name: str) -> str:
    return name.strip().lower()


def _normalize_and_hash(field: str, value: str) -> str:
    """
    Field-aware normalization + SHA256 hash.
    Zaten hashli görünen değerlere dokunmaz (idempotent).
    """
    if not value:
        return ""
    val = str(value).strip()
    if _is_already_hashed(val):
        return val.lower()

    if field == "em":
        val = _norm_email(val)
    elif field == "ph":
        val = _norm_phone(val)
    elif field in ("fn", "ln", "ct", "st", "country"):
        val = _norm_name(val)
    elif field == "ge":
        val = val[0].lower() if val else ""
    elif field == "zp":
        val = val.strip().lower()
    elif field == "db":
        # YYYYMMDD bekleniyor, sadece rakam bırak
        val = re.sub(r"\D", "", val)
    # external_id için raw string normalize edilmez (sadece trim)

    return _sha256(val)


def split_full_name(full_name: Optional[str]) -> Dict[str, str]:
    """
    `contact_name` → {fn, ln}.
    Tek kelime → fn dolar, ln boş kalır.
    """
    if not full_name:
        return {"fn": "", "ln": ""}
    parts = [p for p in full_name.strip().split() if p]
    if not parts:
        return {"fn": "", "ln": ""}
    if len(parts) == 1:
        return {"fn": parts[0], "ln": ""}
    return {"fn": parts[0], "ln": " ".join(parts[1:])}


# ---------------------------------------------------------------------------
# MetaCapiService
# ---------------------------------------------------------------------------
class MetaCapiService:
    """
    Production-ready Meta Conversions API gönderici.

    Tek instance singleton olarak kullanılır (`get_meta_capi_service()`).
    `send_event` sync'tir; FastAPI `BackgroundTasks` ile çağırın.
    """

    def __init__(
        self,
        pixel_id: Optional[str] = None,
        access_token: Optional[str] = None,
        api_version: Optional[str] = None,
        test_event_code: Optional[str] = None,
        timeout: float = 8.0,
    ) -> None:
        self.pixel_id = pixel_id or os.getenv("META_PIXEL_ID", "").strip()
        self.access_token = access_token or os.getenv("META_CAPI_ACCESS_TOKEN", "").strip()
        self.api_version = (api_version or os.getenv("META_CAPI_API_VERSION", "v19.0")).strip()
        self.default_test_event_code = (
            test_event_code if test_event_code is not None
            else os.getenv("META_CAPI_TEST_EVENT_CODE", "").strip() or None
        )
        self.timeout = timeout

        if not self.pixel_id or not self.access_token:
            logger.warning(
                "[meta_capi] PIXEL_ID veya ACCESS_TOKEN tanımlı değil — servis no-op modunda."
            )

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------
    @property
    def enabled(self) -> bool:
        return bool(self.pixel_id and self.access_token)

    def send_event(
        self,
        *,
        event_name: str,
        event_id: Optional[str] = None,
        event_time: Optional[int] = None,
        event_source_url: Optional[str] = None,
        action_source: str = "website",
        user_data: Optional[Dict[str, Any]] = None,
        custom_data: Optional[Dict[str, Any]] = None,
        client_ip: Optional[str] = None,
        client_user_agent: Optional[str] = None,
        fbp: Optional[str] = None,
        fbc: Optional[str] = None,
        external_id: Optional[str] = None,
        test_event_code: Optional[str] = None,
    ) -> bool:
        """
        Tek bir olay yollar. BackgroundTask içinden çağrılır → kullanıcı isteğini bloklamaz.
        Hatada False döner; istisna fırlatmaz (analytics asla ürün akışını kırmaz).
        """
        if not self.enabled:
            logger.debug(f"[meta_capi] devre dışı — '{event_name}' atlandı.")
            return False

        if not event_name:
            logger.warning("[meta_capi] event_name boş — gönderim iptal.")
            return False

        if action_source not in VALID_ACTION_SOURCES:
            logger.warning(
                f"[meta_capi] geçersiz action_source='{action_source}', 'website' kullanılacak."
            )
            action_source = "website"

        if event_name not in STANDARD_EVENTS:
            logger.info(f"[meta_capi] custom event_name='{event_name}' yollanıyor.")

        payload_event: Dict[str, Any] = {
            "event_name": event_name,
            "event_time": int(event_time or time.time()),
            "event_id": event_id or str(uuid.uuid4()),
            "action_source": action_source,
            "user_data": self._build_user_data(
                user_data=user_data or {},
                client_ip=client_ip,
                client_user_agent=client_user_agent,
                fbp=fbp,
                fbc=fbc,
                external_id=external_id,
            ),
        }
        if event_source_url:
            payload_event["event_source_url"] = event_source_url
        if custom_data:
            payload_event["custom_data"] = self._build_custom_data(custom_data)

        body: Dict[str, Any] = {"data": [payload_event]}

        # Test Events Manager için kod (opsiyonel)
        effective_test_code = test_event_code or self.default_test_event_code
        if effective_test_code:
            body["test_event_code"] = effective_test_code

        url = f"{META_GRAPH_BASE}/{self.api_version}/{self.pixel_id}/events"
        try:
            resp = requests.post(
                url,
                params={"access_token": self.access_token},
                json=body,
                timeout=self.timeout,
            )
            if resp.status_code >= 400:
                logger.warning(
                    "[meta_capi] '%s' hata: status=%s body=%s",
                    event_name, resp.status_code, resp.text[:500],
                )
                return False
            logger.info(
                "[meta_capi] '%s' gönderildi event_id=%s status=%s",
                event_name, payload_event["event_id"], resp.status_code,
            )
            return True
        except requests.RequestException as exc:
            logger.warning(f"[meta_capi] '{event_name}' network error: {exc}")
            return False
        except Exception as exc:
            logger.exception(f"[meta_capi] '{event_name}' beklenmeyen hata: {exc}")
            return False

    # -----------------------------------------------------------------------
    # Private builders
    # -----------------------------------------------------------------------
    def _build_user_data(
        self,
        *,
        user_data: Dict[str, Any],
        client_ip: Optional[str],
        client_user_agent: Optional[str],
        fbp: Optional[str],
        fbc: Optional[str],
        external_id: Optional[str],
    ) -> Dict[str, Any]:
        """
        user_data'yı Meta beklentisine göre normalize/hash eder.
        - Hashlenecek alanlar: em/ph/fn/ln/ge/db/ct/st/zp/country/external_id
        - Hashlenmeyenler: client_ip_address, client_user_agent, fbp, fbc
        """
        result: Dict[str, Any] = {}

        for key, raw in user_data.items():
            if raw is None or raw == "":
                continue
            if key in HASHED_USER_DATA_FIELDS:
                hashed = _normalize_and_hash(key, str(raw))
                if hashed:
                    result[key] = hashed
            elif key in {"client_ip_address", "client_user_agent", "fbp", "fbc"}:
                result[key] = str(raw)
            else:
                # Bilinmeyen alan — best-effort, raw bırak
                result[key] = raw

        # Override / kanonik alanlar
        if client_ip:
            result["client_ip_address"] = client_ip
        if client_user_agent:
            result["client_user_agent"] = client_user_agent
        if fbp:
            result["fbp"] = fbp
        if fbc:
            result["fbc"] = fbc
        if external_id and "external_id" not in result:
            result["external_id"] = _normalize_and_hash("external_id", str(external_id))

        return result

    @staticmethod
    def _build_custom_data(custom_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        custom_data'da dokunmadan geçeriz, sadece value/currency hijyeni yaparız.
        """
        cd = dict(custom_data)
        # value sayısal olmalı
        if "value" in cd:
            try:
                cd["value"] = float(cd["value"])
            except (TypeError, ValueError):
                cd.pop("value", None)
        # currency upper-case ISO-4217
        if "currency" in cd and cd["currency"]:
            cd["currency"] = str(cd["currency"]).upper()
        return cd


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------
_service_singleton: Optional[MetaCapiService] = None


def get_meta_capi_service() -> MetaCapiService:
    """Lazy-singleton; testte reset etmek için `reset_meta_capi_service()` kullanın."""
    global _service_singleton
    if _service_singleton is None:
        _service_singleton = MetaCapiService()
    return _service_singleton


def reset_meta_capi_service() -> None:
    """Sadece testler için."""
    global _service_singleton
    _service_singleton = None
