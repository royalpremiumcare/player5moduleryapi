#!/usr/bin/env bash
# Mobil API Surface'ı frontend'den yeniden üretir → mobile_api_surface.md
# Kullanım: bash backend/tests/contracts/gen_mobile_surface.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
OUT="$ROOT/backend/tests/contracts/mobile_api_surface.md"

cat > "$OUT" <<'HDR'
# MOBİL API SURFACE — Donmuş Build Sözleşme Yüzeyi

> **AMAÇ:** App Store / Play Store'daki DONMUŞ mobil build (Capacitor, aynı React bundle)
> aşağıdaki endpoint'leri çağırır. Bu endpoint'lerin **response ŞEKLİNİ** değiştirmek
> (alan silme/rename/tip/anlam değişimi, array→obje) sahadaki uygulamayı SESSİZCE kırar.
> Bir endpoint'e dokunmadan önce burada olup olmadığını kontrol et; buradaysa additive-only
> kuralına uy ve `backend/tests/integration/` contract testlerini çalıştır.
>
> Bu liste `frontend/src` içindeki `api.*()` / `publicApi.*()` çağrılarından OTOMATİK üretilir.
> Yenilemek için `backend/tests/contracts/gen_mobile_surface.sh` çalıştır.
>
> NOT: Liste tüm frontend bundle'ını kapsar (merchant + superadmin + marketing). Hepsi aynı
> bundle'da olduğu için hepsi potansiyel donmuş yüzeydir.

## Endpoint listesi (auto)

```
HDR

( cd "$ROOT/frontend/src" && python3 - <<'PY'
import re, pathlib
pat = re.compile(r"""\b(?:api|publicApi)\.(get|post|put|patch|delete)\(\s*([`'"])([^`'"]+)\2""")
found=set()
for p in pathlib.Path('.').rglob('*.js'):
    if any(x in p.name for x in ('.bak','.backup')): continue
    for m in pat.finditer(p.read_text(encoding='utf-8')):
        mth,_,path=m.groups(); path=re.sub(r'\$\{[^}]+\}','{param}',path)
        found.add((mth.upper(),'/'+path.lstrip('/').split('?')[0].rstrip('/')))
for mth,path in sorted(found,key=lambda x:(x[1],x[0])): print(f"{mth:6} {path}")
print(f"\n# TOPLAM: {len(found)} distinct endpoint")
PY
) >> "$OUT"
echo '```' >> "$OUT"
echo "Yazıldı: $OUT"
