"""
response_model alan-seti çıkarımı — TÜM API'yi tek testle koruyan güvenlik ağının çekirdeği.

FastAPI app'inin tüm route'larındaki response_model'leri (ve onların iç içe geçmiş
Pydantic modellerini transitif olarak) gezip her modelin alan setini çıkarır. Bu harita
golden'a (models_fieldset_v1.json) kilitlenince, bir response modelinden alan
SİLME / RENAME işlemi CI'da yakalanır — hangi endpoint'in etkilendiğinden bağımsız.

Neden değerli: /customers, /customers/search, /dashboard aynı modeli kullanıyorsa, o
modelden bir alan silmek DÖRT endpoint'i birden kırar. Endpoint değil MODEL korunur.
"""
from __future__ import annotations

from typing import get_args

from pydantic import BaseModel


def _extract_models(annotation, acc: set) -> None:
    """Bir type annotation içindeki tüm BaseModel alt sınıflarını transitif toplar."""
    if annotation is None:
        return
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        if annotation in acc:
            return
        acc.add(annotation)
        # İç içe modeller: alanların annotation'larına da in
        for field in annotation.model_fields.values():
            _extract_models(field.annotation, acc)
        return
    # List[X], Optional[X], Dict[str, X], Union[...] vb. → argümanlara in
    for arg in get_args(annotation):
        _extract_models(arg, acc)


def collect_response_models(app) -> set:
    """app.routes içindeki tüm response_model'lerden ulaşılan Pydantic modelleri."""
    from fastapi.routing import APIRoute

    acc: set = set()
    for route in app.routes:
        if isinstance(route, APIRoute):
            rm = getattr(route, "response_model", None)
            if rm is not None:
                _extract_models(rm, acc)
    return acc


def build_fieldset_map(app) -> dict:
    """{'<modül>:<QualName>': [alan1, alan2, ...]} — deterministik sıralı."""
    out: dict = {}
    for model in collect_response_models(app):
        key = f"{model.__module__}:{model.__qualname__}"
        out[key] = sorted(model.model_fields.keys())
    return dict(sorted(out.items()))


def build_request_required_map(app) -> dict:
    """
    REQUEST CONTRACT: her endpoint'in request BODY modelinin ZORUNLU alan seti.

    Neden: response hiç değişmese bile, bir POST/PUT body'sine YENİ ZORUNLU alan eklemek
    eski client'ı 400'le kırar (eski uygulama o alanı göndermez). Bu harita golden'a
    kilitlenince, bir alanın zorunlu hale gelmesi (required set'in BÜYÜMESİ) yakalanır.
    Opsiyonel alan eklemek veya zorunlu bir alanı kaldırmak GÜVENLİDİR (bu test patlamaz).

    {'<modül>:<QualName>': [zorunlu_alan1, ...]} — deterministik sıralı.
    """
    from fastapi.routing import APIRoute

    out: dict = {}
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        dependant = getattr(route, "dependant", None)
        for bp in (getattr(dependant, "body_params", None) or []):
            model = getattr(bp, "type_", None)
            if isinstance(model, type) and issubclass(model, BaseModel):
                key = f"{model.__module__}:{model.__qualname__}"
                out[key] = sorted(
                    name for name, f in model.model_fields.items() if f.is_required()
                )
    return dict(sorted(out.items()))
