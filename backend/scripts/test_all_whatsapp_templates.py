"""
Plann v2 — WhatsApp Şablon E2E Test Runner
================================================================
12 onaylı template varyantını sırayla test numaralarına gönderir,
Meta API msg_id'lerini toplar ve özet rapor basar.

Hedef numaralar:
  TR: +90 543 479 3213
  UK: +44 7474 626 900

Çalıştırma:
  docker compose exec backend python scripts/test_all_whatsapp_templates.py
"""

import os
import sys
import time

# backend dizinini path'e ekle (scripts/ alt klasöründen import için)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from whatsapp_service import send_whatsapp_template  # noqa: E402

TEST_TR = "+905434793213"
TEST_EN = "+447474626900"

COMMON = dict(
    customer_name="Test Müşterisi",
    company_name="Plann Test İşletmesi",
    appointment_date="2026-04-26",
    appointment_time="14:30",
    service_name="Saç Kesim & Sakal",
    support_phone="+90 543 511 3250",
)

LOC = dict(
    business_lat=38.6248,
    business_lng=34.7142,
    business_address="Atatürk Cad. No:5, Nevşehir Merkez",
)

CASES = [
    # CONFIRMATION (klasik) — 4 varyant
    ("CONFIRMATION TR konumlu",     TEST_TR, "CONFIRMATION",          LOC, {}),
    ("CONFIRMATION TR metin",       TEST_TR, "CONFIRMATION",          {},  {}),
    ("CONFIRMATION EN konumlu",     TEST_EN, "CONFIRMATION",          LOC, {}),
    ("CONFIRMATION EN metin",       TEST_EN, "CONFIRMATION",          {},  {}),
    # CONFIRMATION_FULL_PAID — 4 varyant
    ("FULL_PAID    TR konumlu",     TEST_TR, "CONFIRMATION_FULL_PAID", LOC, {"amount_paid_display": "₺250"}),
    ("FULL_PAID    TR metin",       TEST_TR, "CONFIRMATION_FULL_PAID", {},  {"amount_paid_display": "₺250"}),
    ("FULL_PAID    EN konumlu",     TEST_EN, "CONFIRMATION_FULL_PAID", LOC, {"amount_paid_display": "£25"}),
    ("FULL_PAID    EN metin",       TEST_EN, "CONFIRMATION_FULL_PAID", {},  {"amount_paid_display": "£25"}),
    # CONFIRMATION_DEPOSIT — 4 varyant
    ("DEPOSIT      TR konumlu",     TEST_TR, "CONFIRMATION_DEPOSIT",   LOC, {"amount_paid_display": "₺75",  "on_site_amount_display": "₺175"}),
    ("DEPOSIT      TR metin",       TEST_TR, "CONFIRMATION_DEPOSIT",   {},  {"amount_paid_display": "₺75",  "on_site_amount_display": "₺175"}),
    ("DEPOSIT      EN konumlu",     TEST_EN, "CONFIRMATION_DEPOSIT",   LOC, {"amount_paid_display": "£10", "on_site_amount_display": "£15"}),
    ("DEPOSIT      EN metin",       TEST_EN, "CONFIRMATION_DEPOSIT",   {},  {"amount_paid_display": "£10", "on_site_amount_display": "£15"}),
]


def main() -> int:
    print("=" * 70)
    print("Plann WA Şablon E2E Test")
    print(f"  TR test: {TEST_TR}")
    print(f"  EN test: {TEST_EN}")
    print("=" * 70)

    results = []
    for label, to, ttype, loc_kw, extra_kw in CASES:
        try:
            kwargs = dict(COMMON)
            kwargs.update(loc_kw)
            kwargs.update(extra_kw)
            msg_id = send_whatsapp_template(
                to_number=to,
                template_type=ttype,
                **kwargs,
            )
            results.append((label, "OK  ", str(msg_id)))
            print(f"  ✓ {label:<28} → {msg_id}")
        except Exception as exc:  # noqa: BLE001
            results.append((label, "FAIL", str(exc)))
            print(f"  ✗ {label:<28} → {exc}")
        time.sleep(1.0)  # rate-limit guard

    print()
    print("=" * 70)
    print("ÖZET")
    print("=" * 70)
    ok = sum(1 for r in results if r[1] == "OK  ")
    fail = len(results) - ok
    print(f"  Başarılı: {ok}/{len(results)}")
    print(f"  Hatalı:   {fail}/{len(results)}")
    print()
    if fail:
        print("Başarısız case'ler:")
        for label, status, info in results:
            if status == "FAIL":
                print(f"  - {label}: {info}")
    print("=" * 70)
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
