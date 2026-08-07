#!/usr/bin/env python3
"""
PLANN — Customers Denormalize Backfill

Amaç:
    `customers` collection'ında yeni denormalize sayaçları backfill etmek:
      - total_appointments
      - completed_appointments
      - first_appointment_at
      - last_appointment_at
      - updated_at

    /api/customers cursor pagination bu sayaçlara dayanır — full appointments
    tarama yerine sadece customers'tan okur. Yeni endpoint bu backfill olmadan
    da çalışır ama sayaçlar sıfır görünür.

Nasıl çalışır:
    1. `appointments` üzerinde (organization_id, phone) grup aggregasyonu yapar.
    2. Her (org, phone) için toplam / tamamlandı sayısı ve tarih aralığı çıkarır.
    3. `customers.update_one(..., upsert=True)` ile denormalize alanları set eder.
    4. Idempotent — her çalıştırmada aynı sonuç.

Kullanım:
    # Tüm organizasyonlar için
    docker exec plann_backend python -m scripts.backfill_customers

    # Tek organizasyon için
    docker exec plann_backend python -m scripts.backfill_customers --org-id <uuid>

    # Dry-run (yazma yok, sadece rapor)
    docker exec plann_backend python -m scripts.backfill_customers --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import uuid
from datetime import datetime, timezone

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_BACKEND = os.path.join(_ROOT, "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from dotenv import load_dotenv
load_dotenv(os.path.join(_BACKEND, ".env"))

from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("backfill_customers")


def _appt_iso(date_str: str, time_str: str) -> str | None:
    try:
        if not date_str:
            return None
        tstr = time_str or "00:00"
        return datetime.strptime(f"{date_str} {tstr}", "%Y-%m-%d %H:%M").isoformat()
    except Exception:
        return None


async def backfill_org(db, organization_id: str, dry_run: bool = False) -> dict:
    """Tek organizasyon için backfill. Return: rapor dict."""
    pipeline = [
        {"$match": {"organization_id": organization_id, "phone": {"$ne": None, "$ne": ""}}},
        {
            "$group": {
                "_id": "$phone",
                "total": {"$sum": 1},
                "completed": {
                    "$sum": {"$cond": [{"$eq": ["$status", "Tamamlandı"]}, 1, 0]}
                },
                "last_name": {"$last": "$customer_name"},
                "min_date": {"$min": "$appointment_date"},
                "max_date": {"$max": "$appointment_date"},
                "min_time": {"$first": "$appointment_time"},
                "max_time": {"$last": "$appointment_time"},
            }
        },
    ]

    now_iso = datetime.now(timezone.utc).isoformat()
    groups = await db.appointments.aggregate(pipeline).to_list(None)

    written = 0
    skipped = 0
    created = 0

    for g in groups:
        phone = g.get("_id")
        if not phone:
            skipped += 1
            continue

        total = int(g.get("total") or 0)
        completed = int(g.get("completed") or 0)
        name = (g.get("last_name") or "").strip()
        first_iso = _appt_iso(g.get("min_date") or "", g.get("min_time") or "00:00")
        last_iso = _appt_iso(g.get("max_date") or "", g.get("max_time") or "23:59")

        query = {"organization_id": organization_id, "phone": phone}
        set_ops = {
            "total_appointments": total,
            "completed_appointments": completed,
            "updated_at": now_iso,
        }
        if name:
            set_ops["name"] = name
        if first_iso:
            set_ops["first_appointment_at"] = first_iso
        if last_iso:
            set_ops["last_appointment_at"] = last_iso

        set_on_insert = {
            "id": str(uuid.uuid4()),
            "organization_id": organization_id,
            "phone": phone,
            "created_at": now_iso,
            "notes": "",
        }
        if not name:
            set_on_insert["name"] = ""

        if dry_run:
            existing = await db.customers.find_one(query, {"_id": 0, "id": 1})
            if existing:
                logger.info(
                    f"[DRY] UPDATE phone={phone} total={total} completed={completed} name={name!r}"
                )
            else:
                logger.info(
                    f"[DRY] INSERT phone={phone} total={total} completed={completed} name={name!r}"
                )
                created += 1
            written += 1
            continue

        result = await db.customers.update_one(
            query,
            {"$set": set_ops, "$setOnInsert": set_on_insert},
            upsert=True,
        )
        if result.upserted_id is not None:
            created += 1
        written += 1

    # Randevusu olmayan (manuel eklenmiş) müşteriler — sayaç yoksa 0'a set et.
    # Eksik alanları tamamlar; verisi olan customers yukarıda güncellendi.
    fill_query = {
        "organization_id": organization_id,
        "total_appointments": {"$exists": False},
    }
    if dry_run:
        pending_count = await db.customers.count_documents(fill_query)
        logger.info(f"[DRY] fill 0-counters for {pending_count} manuel müşteri")
    else:
        fill_result = await db.customers.update_many(
            fill_query,
            {
                "$set": {
                    "total_appointments": 0,
                    "completed_appointments": 0,
                    "updated_at": now_iso,
                }
            },
        )
        if fill_result.modified_count:
            logger.info(
                f"org={organization_id[:8]} manuel müşteri sayaçları 0'landı: {fill_result.modified_count}"
            )

    return {
        "organization_id": organization_id,
        "groups": len(groups),
        "written": written,
        "created": created,
        "skipped": skipped,
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description="PLANN customers denormalize backfill")
    parser.add_argument("--org-id", type=str, default=None, help="Sadece bu org")
    parser.add_argument("--dry-run", action="store_true", help="Yazma yapma, rapor et")
    args = parser.parse_args()

    mongo_url = os.environ.get("MONGO_URL") or os.environ.get("MONGODB_URL")
    db_name = os.environ.get("DB_NAME") or "plann"
    if not mongo_url:
        logger.error("MONGO_URL / MONGODB_URL bulunamadı (backend/.env)")
        return 2

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    logger.info(f"Bağlandı: db={db_name}")

    if args.org_id:
        org_ids = [args.org_id]
    else:
        # Tüm distinct organization_id'leri appointments + customers'tan topla
        appt_orgs = await db.appointments.distinct("organization_id")
        cust_orgs = await db.customers.distinct("organization_id")
        org_ids = sorted({o for o in (list(appt_orgs) + list(cust_orgs)) if o})

    logger.info(f"Toplam {len(org_ids)} organizasyon işlenecek (dry_run={args.dry_run})")

    total_report = {"orgs": 0, "groups": 0, "written": 0, "created": 0, "skipped": 0}
    for org_id in org_ids:
        try:
            report = await backfill_org(db, org_id, dry_run=args.dry_run)
            logger.info(
                f"✓ org={org_id[:8]} groups={report['groups']} written={report['written']} "
                f"created={report['created']} skipped={report['skipped']}"
            )
            total_report["orgs"] += 1
            total_report["groups"] += report["groups"]
            total_report["written"] += report["written"]
            total_report["created"] += report["created"]
            total_report["skipped"] += report["skipped"]
        except Exception as exc:
            logger.error(f"✗ org={org_id[:8]} FAILED: {exc}", exc_info=True)

    logger.info(
        f"BITTI — orgs={total_report['orgs']} groups={total_report['groups']} "
        f"written={total_report['written']} created={total_report['created']} "
        f"skipped={total_report['skipped']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
