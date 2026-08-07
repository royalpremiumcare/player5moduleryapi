"""
response_model alan-seti SNAPSHOT testi — TÜM API'yi tek testle koruyan ucuz güvenlik ağı.

ChatGPT'nin doğru tespiti: korunması gereken endpoint değil, RESPONSE MODELİDİR. /customers,
/customers/search, /dashboard aynı modeli kullanıyorsa o modelden bir alan silmek dört
endpoint'i birden kırar. Bu test, response_model olarak kullanılan (ve iç içe geçen) tüm
Pydantic modellerin alan setini golden'a kilitler.

Politika:
- Alan/model EKLEME -> GÜVENLİ (eski client bilmediği alanı yok sayar) -> test PATLAMAZ.
- Alan/model SİLME veya RENAME -> donmuş mobil build kırılır -> test PATLAR.
- Golden'ı bilinçli güncelleme: UPDATE_CONTRACTS=1 python -m pytest .../test_model_fieldset_contract.py

Sınır: Bu test ŞEMA testidir, DAVRANIŞ testi değildir. Alan adı/tipi aynı kalıp ANLAMI
değişirse (price TL->kuruş, status değer seti) yakalamaz — onlar için golden JSON davranış
testleri (test_legacy_contracts) ve Mobil API Surface disiplini var.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

CONTRACTS_DIR = Path(__file__).resolve().parents[1] / "contracts"
GOLDEN = CONTRACTS_DIR / "models_fieldset_v1.json"


def _load_helper():
    spec = importlib.util.spec_from_file_location(
        "_model_contract", CONTRACTS_DIR / "_model_contract.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_response_model_fieldsets_locked():
    from server import app

    current = _load_helper().build_fieldset_map(app)

    # Regenerate mode (bilinçli güncelleme)
    if os.environ.get("UPDATE_CONTRACTS") == "1":
        payload = json.loads(GOLDEN.read_text(encoding="utf-8"))
        payload["models"] = current
        GOLDEN.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return

    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))["models"]

    # (1) Kaybolan model: golden'da response_model iken artık ulaşılamıyor
    missing_models = sorted(set(golden) - set(current))

    # (2) Silinen/rename edilen alan: golden alanlarından current'ta olmayanlar
    removed_fields = {}
    for name, fields in golden.items():
        if name in current:
            gone = sorted(set(fields) - set(current[name]))
            if gone:
                removed_fields[name] = gone

    assert not missing_models and not removed_fields, (
        "LEGACY CONTRACT KIRILDI (response_model alan-seti).\n"
        f"- Kaybolan modeller: {missing_models}\n"
        f"- Silinen/rename edilen alanlar: {removed_fields}\n"
        "Bir response modelinden alan SİLME/RENAME donmuş mobil build'i sessizce kırar. "
        "Alanı geri koy VEYA yeni davranışı yeni bir alan/parametre ile additive yap. "
        "Bilinçli+güvenli bir silme yaptıysan golden'ı güncelle: "
        "UPDATE_CONTRACTS=1 python -m pytest tests/integration/test_model_fieldset_contract.py"
    )
