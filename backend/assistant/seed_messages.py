"""
PLANN Asistan — Mesaj havuzu DB seed (idempotent).

messages_tr.json içindeki 360 metni (3 profil × 12 senaryo × 10 varyasyon)
assistant_messages koleksiyonuna yazar. Deterministik id ile upsert edildiği
için tekrar tekrar çalıştırmak güvenlidir (mükerrer kayıt oluşturmaz).

id formatı: "{profile}:{lang}:{scenario}:{index}"
"""

import os
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_LANG = "tr"
_JSON_PATH = os.path.join(os.path.dirname(__file__), "messages_tr.json")


def load_messages(path: str = None) -> dict:
    with open(path or _JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


async def ensure_indexes(db) -> None:
    await db.assistant_messages.create_index(
        [("scenario", 1), ("lang", 1), ("profile", 1), ("is_active", 1)],
        name="assistant_messages_lookup",
    )
    await db.assistant_messages.create_index(
        [("id", 1)], unique=True, name="assistant_messages_id_unique"
    )


async def seed_messages(db, path: str = None) -> dict:
    """Tüm metinleri upsert eder. Döner: {'upserted': n, 'total': n}."""
    data = load_messages(path)
    now = datetime.now(timezone.utc).isoformat()
    total = 0
    for profile, scenarios in data.items():
        for scenario, variations in scenarios.items():
            for idx, text in enumerate(variations):
                mid = f"{profile}:{_LANG}:{scenario}:{idx}"
                await db.assistant_messages.update_one(
                    {"id": mid},
                    {"$set": {
                        "id": mid,
                        "profile": profile,
                        "scenario": scenario,
                        "lang": _LANG,
                        "variation_index": idx,
                        "text": text,
                        "is_active": True,
                        "updated_at": now,
                    }},
                    upsert=True,
                )
                total += 1
    logger.info("Assistant messages seeded: %s", total)
    return {"upserted": total, "total": total}


async def messages_status(db) -> dict:
    """Seed durumunu profil/senaryo bazında özetler (superadmin teşhis)."""
    total = await db.assistant_messages.count_documents({"is_active": True})
    by_profile = {}
    for prof in await db.assistant_messages.distinct("profile"):
        by_profile[prof] = await db.assistant_messages.count_documents(
            {"profile": prof, "is_active": True}
        )
    return {"total_active": total, "by_profile": by_profile}
