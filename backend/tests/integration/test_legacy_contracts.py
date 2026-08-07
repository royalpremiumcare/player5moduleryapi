"""
LEGACY CONTRACT testleri — Faz 0 güvenlik ağı.

Amaç: App Store'daki DONMUŞ mobil build'lerin bağlı olduğu iki endpoint'in
response ŞEKLİNİ (contract) golden dosyalara karşı kilitlemek. Bir refactor
alan silerse / tip değiştirirse / array->obje döndürürse bu testler CI'da
patlar ve eski build kırılmadan önce yakalanır.

Golden dosyalar: backend/tests/contracts/*.json
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

CONTRACTS_DIR = Path(__file__).resolve().parents[1] / "contracts"


def _load_golden(name: str) -> dict:
    return json.loads((CONTRACTS_DIR / name).read_text(encoding="utf-8"))


def test_appointments_response_contract_matches_model():
    """GET /appointments, response_model=List[Appointment].

    Response şekli tamamen Appointment modelinin serileştirmesidir; bu yüzden
    modelin alan setini golden'a kilitlemek response contract'ını kilitler.
    """
    from server import Appointment

    golden = _load_golden("appointments_legacy_v1.json")

    sample = Appointment(
        organization_id="org_test",
        customer_name="Örnek Müşteri",
        phone="905551112233",
        service_id="svc1",
        service_name="Saç Kesimi",
        service_price=250.0,
        appointment_date="2026-08-10",
        appointment_time="14:00",
    )
    dumped_keys = set(sample.model_dump(mode="json").keys())
    expected_keys = set(golden["required_keys"])

    assert dumped_keys == expected_keys, (
        "LEGACY CONTRACT KIRILDI: Appointment alan seti golden'dan farklı. "
        "Eklenen/çıkarılan alan App Store'daki donmuş build'leri bozabilir. "
        f"Fark (symmetric diff): {dumped_keys ^ expected_keys}"
    )


@pytest.mark.asyncio
async def test_customers_legacy_contract(integration_client, integration_db):
    """GET /customers (limit YOK) — flat array + is_pending invariant'ı."""
    client, _redis, db = integration_client
    org = db.organization_id

    # Randevulu müşteri (2 randevu, 1 tamamlandı) -> is_pending OLMAMALI
    db.appointments.docs.extend([
        {"organization_id": org, "phone": "905551112233",
         "customer_name": "Randevulu Kişi", "status": "Tamamlandı"},
        {"organization_id": org, "phone": "905551112233",
         "customer_name": "Randevulu Kişi", "status": "Bekliyor"},
    ])
    # Randevusuz (customers-only) müşteri -> is_pending:true OLMALI
    db.customers.docs.append(
        {"organization_id": org, "phone": "905559998877", "name": "Randevusuz Kişi"}
    )

    r = await client.get("/api/customers")
    assert r.status_code == 200, r.text

    body = r.json()
    assert isinstance(body, list), "Legacy /customers flat ARRAY dönmeli (obje DEĞİL)"

    golden = _load_golden("customers_legacy_v1.json")
    required = set(golden["required_keys"])
    allowed = required | set(golden["optional_keys"])

    by_phone = {item["phone"]: item for item in body}
    assert "905551112233" in by_phone, "Randevulu müşteri listede yok"
    assert "905559998877" in by_phone, "Randevusuz müşteri listede yok"

    for item in body:
        keys = set(item.keys())
        assert keys.issubset(allowed), (
            f"LEGACY CONTRACT KIRILDI: beklenmeyen alan {keys - allowed}"
        )
        assert required.issubset(keys), (
            f"LEGACY CONTRACT KIRILDI: eksik zorunlu alan {required - keys}"
        )
        assert isinstance(item["total_appointments"], int)
        assert isinstance(item["completed_appointments"], int)
        # Invariant: is_pending SADECE ve HER ZAMAN randevusuz (total==0) müşteride
        if item["total_appointments"] == 0:
            assert item.get("is_pending") is True, (
                "Randevusuz müşteride is_pending:true bekleniyordu"
            )
        else:
            assert "is_pending" not in item, (
                "Randevulu müşteride is_pending BULUNMAMALI"
            )

    randevulu = by_phone["905551112233"]
    assert randevulu["total_appointments"] == 2
    assert randevulu["completed_appointments"] == 1
    assert "is_pending" not in randevulu

    randevusuz = by_phone["905559998877"]
    assert randevusuz["total_appointments"] == 0
    assert randevusuz["completed_appointments"] == 0
    assert randevusuz["is_pending"] is True
