#!/usr/bin/env python3
"""
PLANN — Sentetik Yük Testi Verisi (İZOLE ORG)

Amaç:
    k6 "Large Dataset" profili için gerçekçi ölçek verisi üretmek: ~10.000 müşteri,
    ~100.000 randevu. Pagination'ın gerçek değeri (payload küçülmesi) ancak bu
    boyutta görünür (bkz. k6_analiz_raporu §11).

GÜVENLİK — PROD VERİSİNE DOKUNMAZ:
    Tüm veriler tek bir İZOLE organization_id altına yazılır:
        ORG_ID = "k6-loadtest-synthetic-org"
    Multi-tenant izolasyon gereği her sorgu organization_id filtreler → gerçek
    org'lar (Royal Premium Care vb.) bu veriyi ASLA görmez. Teardown tek komutla
    bu org'a ait HER ŞEYİ siler.

Kullanım:
    # Seed (önce temizler, sonra doldurur) — varsayılan 10k müşteri / 100k randevu
    docker exec plann_backend python -m scripts.seed_synthetic_loadtest --seed

    # Özel boyut
    docker exec plann_backend python -m scripts.seed_synthetic_loadtest --seed --customers 10000 --appointments 100000

    # Sadece sayımı göster
    docker exec plann_backend python -m scripts.seed_synthetic_loadtest --count

    # Teardown (izole org'a ait her şeyi sil)
    docker exec plann_backend python -m scripts.seed_synthetic_loadtest --teardown
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_BACKEND = os.path.join(_ROOT, "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from dotenv import load_dotenv
load_dotenv(os.path.join(_BACKEND, ".env"))

from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_synthetic")

# ── İZOLE sabitler ───────────────────────────────────────────────────────────
ORG_ID = "k6-loadtest-synthetic-org"
USERNAME = "k6-loadtest@synthetic.local"

# İzole org'a ait veri yazılan TÜM collection'lar (teardown bunları tarar).
OWNED_COLLECTIONS = [
    "users", "services", "customers", "appointments",
    "transactions", "organization_plans", "settings",
]

_FIRST_NAMES = [
    "Fatih", "Ahmet", "Mehmet", "Ayşe", "Fatma", "Elif", "Zeynep", "Mustafa",
    "Emre", "Burak", "Selin", "Deniz", "Cem", "Ece", "Kaan", "Merve",
    "Şenol", "Gökhan", "Büşra", "İrem",
]
_LAST_NAMES = [
    "Şenyüz", "Yılmaz", "Demir", "Kaya", "Çelik", "Şahin", "Öztürk", "Aydın",
    "Arslan", "Doğan", "Kılıç", "Aslan", "Çetin", "Koç", "Kurt", "Güneş",
]
_STATUSES = ["Tamamlandı", "Tamamlandı", "Tamamlandı", "Bekliyor", "İptal"]
_TIMES = [f"{h:02d}:{m:02d}" for h in range(9, 20) for m in (0, 30)]

_BATCH = 5000


async def _insert_batched(coll, docs, label: str):
    total = 0
    buf = []
    for d in docs:
        buf.append(d)
        if len(buf) >= _BATCH:
            await coll.insert_many(buf, ordered=False)
            total += len(buf)
            logger.info(f"  {label}: {total} yazıldı…")
            buf = []
    if buf:
        await coll.insert_many(buf, ordered=False)
        total += len(buf)
    logger.info(f"✓ {label}: toplam {total}")
    return total


async def teardown(db) -> None:
    logger.info(f"TEARDOWN — org={ORG_ID}")
    for cname in OWNED_COLLECTIONS:
        res = await db[cname].delete_many({"organization_id": ORG_ID})
        if res.deleted_count:
            logger.info(f"  {cname}: {res.deleted_count} silindi")
    logger.info("✓ Teardown tamam (izole org boşaltıldı)")


async def count(db) -> None:
    logger.info(f"SAYIM — org={ORG_ID}")
    for cname in OWNED_COLLECTIONS:
        n = await db[cname].count_documents({"organization_id": ORG_ID})
        logger.info(f"  {cname}: {n}")


async def seed(db, n_customers: int, n_appointments: int) -> None:
    logger.info(f"SEED — org={ORG_ID} | müşteri={n_customers} randevu={n_appointments}")
    await teardown(db)  # idempotent

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    today = datetime.now(ZoneInfo_safe()).date()

    # 1) User (get_current_user bunu 'sub' ile çözer)
    await db.users.insert_one({
        "id": str(uuid.uuid4()), "user_id": str(uuid.uuid4()),
        "username": USERNAME, "organization_id": ORG_ID, "role": "admin",
        "full_name": "K6 Loadtest", "status": "active",
        "onboarding_completed": True, "can_view_all_appointments": True,
        "created_at": now_iso,
    })
    logger.info("✓ user")

    # 2) Services (enrichment + fiyat için)
    services = []
    for i in range(6):
        services.append({
            "organization_id": ORG_ID, "id": f"svc_synth_{i}",
            "name": f"Sentetik Hizmet {i}", "price": float(random.choice([150, 250, 400, 600, 900])),
            "duration": random.choice([30, 45, 60]), "order": i,
            "version": 1, "is_active": True, "created_at": now_iso,
        })
    await db.services.insert_many(services)
    logger.info("✓ services (6)")

    # 3) Customers (denormalize sayaçlarla) — telefon UNIQUE
    per = max(1, n_appointments // max(1, n_customers))

    def _cust_gen():
        for i in range(n_customers):
            fn = _FIRST_NAMES[i % len(_FIRST_NAMES)]
            ln = _LAST_NAMES[(i // len(_FIRST_NAMES)) % len(_LAST_NAMES)]
            completed = int(per * 0.6)
            yield {
                "id": str(uuid.uuid4()), "organization_id": ORG_ID,
                "name": f"{fn} {ln} {i}", "phone": f"90550{i:07d}",
                "notes": "", "total_appointments": per,
                "completed_appointments": completed,
                "first_appointment_at": (now - timedelta(days=365)).isoformat(),
                "last_appointment_at": now_iso, "created_at": now_iso,
                "updated_at": now_iso,
            }

    await _insert_batched(db.customers, _cust_gen(), "customers")

    # 4) Appointments — round-robin müşteriye ata, tarih son 365 güne yay.
    #    Dashboard 'bugün' sinyali için ilk ~200 randevu bugüne set edilir.
    def _appt_gen():
        for j in range(n_appointments):
            ci = j % n_customers
            fn = _FIRST_NAMES[ci % len(_FIRST_NAMES)]
            ln = _LAST_NAMES[(ci // len(_FIRST_NAMES)) % len(_LAST_NAMES)]
            svc = services[j % len(services)]
            if j < 200:
                d = today
                status = "Bekliyor" if j % 2 else "Tamamlandı"
            else:
                d = today - timedelta(days=random.randint(1, 365))
                status = _STATUSES[j % len(_STATUSES)]
            date_str = d.isoformat()
            completed_at = now_iso if status == "Tamamlandı" else None
            yield {
                "organization_id": ORG_ID, "id": str(uuid.uuid4()),
                "customer_name": f"{fn} {ln} {ci}", "phone": f"90550{ci:07d}",
                "service_id": svc["id"], "service_name": svc["name"],
                "service_price": svc["price"], "appointment_date": date_str,
                "appointment_time": random.choice(_TIMES), "notes": "",
                "status": status, "staff_member_id": None,
                "created_at": now_iso, "completed_at": completed_at,
                "service_duration": svc["duration"], "source": "load_test",
                "session_group_id": None, "session_number": None,
                "session_total": None, "payment_status": None,
                "refund_eligible": None, "services": None,
                "selection_type": "INDIVIDUAL",
            }

    await _insert_batched(db.appointments, _appt_gen(), "appointments")

    # 5) Transactions — dashboard gelir sinyali için bugüne/bu aya bir miktar.
    def _tx_gen():
        for k in range(300):
            d = today if k < 100 else today.replace(day=1)
            yield {
                "organization_id": ORG_ID, "id": str(uuid.uuid4()),
                "appointment_id": str(uuid.uuid4()), "customer_name": "Sentetik",
                "service_name": "Sentetik Hizmet", "amount": float(random.choice([150, 250, 400])),
                "date": d.isoformat(), "staff_member_id": None, "created_at": now_iso,
            }

    await _insert_batched(db.transactions, _tx_gen(), "transactions")

    logger.info("✓ SEED TAMAM")
    await count(db)


def ZoneInfo_safe():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("Europe/Istanbul")
    except Exception:
        return timezone(timedelta(hours=3))


async def main() -> int:
    parser = argparse.ArgumentParser(description="PLANN sentetik yük testi verisi (izole org)")
    parser.add_argument("--seed", action="store_true", help="Veri üret (önce teardown)")
    parser.add_argument("--teardown", action="store_true", help="İzole org'a ait her şeyi sil")
    parser.add_argument("--count", action="store_true", help="Mevcut sayımı göster")
    parser.add_argument("--customers", type=int, default=10000)
    parser.add_argument("--appointments", type=int, default=100000)
    args = parser.parse_args()

    mongo_url = os.environ.get("MONGO_URL") or os.environ.get("MONGODB_URL")
    db_name = os.environ.get("DB_NAME") or "plann"
    if not mongo_url:
        logger.error("MONGO_URL / MONGODB_URL bulunamadı (backend/.env)")
        return 2

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    logger.info(f"Bağlandı: db={db_name}")

    if args.teardown:
        await teardown(db)
    elif args.count:
        await count(db)
    elif args.seed:
        await seed(db, args.customers, args.appointments)
    else:
        parser.print_help()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
