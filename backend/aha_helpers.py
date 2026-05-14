"""
Aha activation helpers — saf unit-test edilebilir parçalar.

`server.py:aha_test_appointment` endpoint'i bu modüldeki yardımcıları kullanır.
Buradaki fonksiyonların hiçbiri DB/HTTP'ye doğrudan dokunmaz; bağımlılıklar
parametre olarak geçer (`send_whatsapp_template` callable, `now_provider`, vb.)
böylece test harness mock'ları kolayca enjekte edebilir.
"""

from __future__ import annotations

import asyncio
import functools
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional, Tuple

logger = logging.getLogger(__name__)

# Aha randevu zamanlama sabitleri
AHA_OFFSET_MINUTES = 15
DEFAULT_WORK_START_HOUR = 9
DEFAULT_WORK_END_HOUR = 18

# WA gönderim retry parametreleri (plan 1.1.B step 8)
WA_FIRST_TIMEOUT_S = 2.0
WA_RETRY_DELAY_S = 1.5
WA_SECOND_TIMEOUT_S = 2.0


def pick_aha_slot(
    settings_doc: Optional[dict],
    *,
    now_provider: Callable[[], datetime] = None,
) -> Tuple[str, str]:
    """
    Aha demo randevusu için tarih/saat seç.

    Davranış:
      1. `now() + AHA_OFFSET_MINUTES` baz alınır (~15dk gelecek; kullanıcıya
         ders kıvamında "yakın bir zamana atadık" görüntüsü verir).
      2. work_start/work_end mesai pencerelerine zorlanır.
         - candidate.hour < work_start  → o günün work_start:00'ı
         - candidate.hour >= work_end   → ertesi günün work_start:00'ı
      3. work_end <= work_start şeklindeki bozuk konfig için 8 saat normalize edilir.

    Args:
        settings_doc: settings koleksiyonundaki dokuman; None / kısmi olabilir.
        now_provider: `() -> datetime` test-injection için (TZ-aware olmalı).

    Returns:
        (appointment_date, appointment_time) — `YYYY-MM-DD`, `HH:MM` string'leri.
    """
    if now_provider is None:
        try:
            from zoneinfo import ZoneInfo

            tz = ZoneInfo("Europe/Istanbul")
        except Exception:
            tz = timezone.utc
        now_provider = lambda: datetime.now(tz)

    now = now_provider()

    work_start = int((settings_doc or {}).get("work_start_hour") or DEFAULT_WORK_START_HOUR)
    work_end = int((settings_doc or {}).get("work_end_hour") or DEFAULT_WORK_END_HOUR)
    if work_end <= work_start:
        work_end = work_start + 8

    candidate = now + timedelta(minutes=AHA_OFFSET_MINUTES)
    if candidate.hour < work_start:
        candidate = candidate.replace(hour=work_start, minute=0, second=0, microsecond=0)
    elif candidate.hour >= work_end:
        candidate = (candidate + timedelta(days=1)).replace(
            hour=work_start, minute=0, second=0, microsecond=0
        )

    return candidate.strftime("%Y-%m-%d"), candidate.strftime("%H:%M")


async def send_aha_whatsapp_with_retry(
    *,
    send_callable: Callable[..., Any],
    to_number: str,
    customer_name: str,
    company_name: str,
    appointment_date: str,
    appointment_time: str,
    service_name: str,
    support_phone: str,
    business_lat: Optional[Any] = None,
    business_lng: Optional[Any] = None,
    business_address: Optional[str] = None,
    first_timeout_s: float = WA_FIRST_TIMEOUT_S,
    retry_delay_s: float = WA_RETRY_DELAY_S,
    second_timeout_s: float = WA_SECOND_TIMEOUT_S,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Aha CONFIRMATION mesajını gönderir; başarısızlıkta tek sessiz retry yapar.

    `asyncio.wait_for` worst-case latency'yi `first_timeout_s + retry_delay_s + second_timeout_s`
    ile sınırlar. `send_callable` (`whatsapp_service.send_whatsapp_template`) genellikle
    `requests.post(timeout=15)` ile worker thread'i bloke eder, ama biz wait_for ile
    erkenden vazgeçeriz; arka plan thread'i yine de bitirir.

    Args:
        send_callable: senkron `send_whatsapp_template` callable (run_in_executor ile çağrılır).
        first_timeout_s, retry_delay_s, second_timeout_s: testlerde küçültülebilir.

    Returns:
        (success, message_id, error_message)
        - success=True iken `message_id` doludur ve hata None.
        - success=False iken `message_id` None, `error` retry detaylarını içerir.
    """

    async def _try_once(timeout_s: float) -> Tuple[bool, Optional[str], Optional[str]]:
        loop = asyncio.get_event_loop()
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    functools.partial(
                        send_callable,
                        to_number,
                        "CONFIRMATION",
                        customer_name,
                        company_name,
                        appointment_date,
                        appointment_time,
                        service_name,
                        support_phone,
                        business_lat,
                        business_lng,
                        business_address,
                    ),
                ),
                timeout=timeout_s,
            )
            # send_whatsapp_template `"disabled"` döner WHATSAPP_ENABLED=False ise; bu da
            # boş olmayan string sayılır → test ortamında Aha akışı tıkanmasın.
            if isinstance(result, str) and result:
                return True, result, None
            return False, None, "empty_response"
        except asyncio.TimeoutError:
            return False, None, "timeout"
        except Exception as exc:
            return False, None, f"{type(exc).__name__}: {exc}"[:240]

    ok, msg_id, err = await _try_once(first_timeout_s)
    if ok:
        return True, msg_id, None
    first_err = err

    await asyncio.sleep(retry_delay_s)

    ok, msg_id, err = await _try_once(second_timeout_s)
    if ok:
        return True, msg_id, None

    return False, None, f"first={first_err}; second={err}"
