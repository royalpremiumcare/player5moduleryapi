"""
REQUEST CONTRACT snapshot testi — sözleşmenin request tarafı.

Response'u hiç değiştirmeden bir POST/PUT body'sine YENİ ZORUNLU alan eklemek eski client'ı
400'le kırar (eski uygulama o alanı göndermez). Bu test, her request body modelinin zorunlu
alan setini golden'a kilitler.

Politika:
- Opsiyonel alan EKLEME -> GÜVENLİ (eski client göndermez, default devreye girer) -> PATLAMAZ.
- Zorunlu alan KALDIRMA -> GÜVENLİ (eski client fazladan gönderir, sorun yok) -> PATLAMAZ.
- Bir alan ZORUNLU hale gelme (required set BÜYÜR) -> eski client 400 alır -> PATLAR.

Yeni zorunlu alan gerçekten gerekiyorsa: alanı Optional + default yap, VEYA yeni endpoint/sürüm aç.
Bilinçli değişiklikte golden'ı güncelle:
UPDATE_CONTRACTS=1 python -m pytest tests/integration/test_request_contract.py
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

CONTRACTS_DIR = Path(__file__).resolve().parents[1] / "contracts"
GOLDEN = CONTRACTS_DIR / "request_required_v1.json"


def _load_helper():
    spec = importlib.util.spec_from_file_location(
        "_model_contract", CONTRACTS_DIR / "_model_contract.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_request_required_fields_locked():
    from server import app

    current = _load_helper().build_request_required_map(app)

    if os.environ.get("UPDATE_CONTRACTS") == "1":
        payload = json.loads(GOLDEN.read_text(encoding="utf-8"))
        payload["request_required"] = current
        GOLDEN.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return

    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))["request_required"]

    # Sadece TEHLİKELİ yön: golden'da olan bir modele YENİ zorunlu alan eklenmesi.
    newly_required = {}
    for name, req_fields in golden.items():
        if name in current:
            added = sorted(set(current[name]) - set(req_fields))
            if added:
                newly_required[name] = added

    assert not newly_required, (
        "REQUEST CONTRACT KIRILDI: request body modeline YENİ ZORUNLU alan eklendi.\n"
        f"- Yeni zorunlu alanlar: {newly_required}\n"
        "Eski mobil build bu alan(lar)ı göndermediği için 400 alır. Alanı Optional + default yap "
        "VEYA yeni endpoint/sürüm aç. Bilinçli bir değişiklikse golden'ı güncelle: "
        "UPDATE_CONTRACTS=1 python -m pytest tests/integration/test_request_contract.py"
    )
