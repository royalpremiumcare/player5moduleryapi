#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# PLANN k6 — 3 Profilli Yük Testi Orkestratörü
#   ./run_profiles.sh cold|warm|large|all
#
# cold  : Gerçek org. Redis cache flush → tekil cache-miss dashboard ölçümü → k6.
# warm  : Gerçek org. Prewarm (cache doldur) → tekil cache-hit ölçümü → k6.
# large : İZOLE sentetik org (10k müşteri / 100k randevu). Yoksa seed eder → k6.
#
# NOT: Token'lar çalışma anında backend container'da mint edilir (süre dolmaz).
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

BASE_URL="http://127.0.0.1:8002/api"
REAL_ORG="bd215db0-cd7d-46bb-a091-a205a624b45b"
REAL_USER="royalpremiumcare@gmail.com"
SYNTH_ORG="k6-loadtest-synthetic-org"
SYNTH_USER="k6-loadtest@synthetic.local"
SYNTH_CUSTOMERS=10000
SYNTH_APPTS=100000

RESULTS="single_request_timings.txt"

mint_token() {  # $1=sub $2=org  → prints JWT
  local sub="$1" org="$2"
  docker exec plann_backend python -c "
from jose import jwt
import os, time
sec=os.environ['JWT_SECRET_KEY']  # env_file (docker-compose) enjekte eder
p={'sub':'$sub','org_id':'$org','role':'admin','onboarding_completed':True,'exp':int(time.time())+7200}
print(jwt.encode(p, sec, algorithm='HS256'))
"
}

flush_cache() {  # $1=org
  echo "🧹 Redis cache flush: plann:org_$1:*"
  docker exec plann_redis sh -c "redis-cli --scan --pattern 'plann:org_$1:*' | xargs -r redis-cli del" || true
}

time_dashboard() {  # $1=token  → prints total seconds
  curl -s -o /dev/null -w "%{time_total}" \
    -H "Authorization: Bearer $1" "$BASE_URL/stats/dashboard"
}

run_k6() {  # $1=profile $2=token
  local prof="$1" tok="$2"
  echo "🚀 k6 run — PROFILE=$prof"
  # k6 threshold aşımında exit 99 döner — bu beklenen, script'i durdurmasın.
  k6 run \
    -e PROFILE="$prof" -e TOKEN="$tok" -e BASE_URL="$BASE_URL" \
    --summary-export "k6_${prof}_summary.json" \
    k6_profiles.js 2>&1 | tee "k6_${prof}.log" | tail -40 || true
}

profile_cold() {
  echo "════════ COLD START PROFİLİ ════════"
  local tok; tok="$(mint_token "$REAL_USER" "$REAL_ORG")"
  flush_cache "$REAL_ORG"
  local cold_ms; cold_ms="$(time_dashboard "$tok")"
  echo "COLD single dashboard (cache-miss): ${cold_ms}s" | tee -a "$RESULTS"
  run_k6 cold "$tok"
}

profile_warm() {
  echo "════════ WARM PRODUCTION PROFİLİ ════════"
  local tok; tok="$(mint_token "$REAL_USER" "$REAL_ORG")"
  echo "🔥 Prewarm: dashboard cache doldur"
  time_dashboard "$tok" >/dev/null   # ilk çağrı cache'i doldurur
  sleep 1
  local warm_ms; warm_ms="$(time_dashboard "$tok")"
  echo "WARM single dashboard (cache-hit): ${warm_ms}s" | tee -a "$RESULTS"
  run_k6 warm "$tok"
}

profile_large() {
  echo "════════ LARGE DATASET PROFİLİ ════════"
  # ⚠️ GÜVENLİK KİLİDİ: Large profili 100k randevu + ağır legacy payload üretir.
  # PostHog ile AYNI kutuda çalıştırıldığında belleği taşırıp MongoDB'yi OOM-kill
  # etti (bkz. k6_analiz_raporu §12). Bu kutuda çalıştırma. İZOLE bir test
  # sunucusunda ya da PostHog ayrıştıktan (Faz 4) sonra ALLOW_LARGE=1 ile aç.
  if [ "${ALLOW_LARGE:-0}" != "1" ]; then
    echo "🚫 Large profili kilitli (bu kutuda OOM riski). Çalıştırmak için: ALLOW_LARGE=1 $0 large"
    echo "   Öneri: İzole test sunucusunda veya PostHog ayrıştıktan sonra."
    return 0
  fi
  local appt_count
  appt_count="$(docker exec plann_backend sh -c "cd /app && python -m scripts.seed_synthetic_loadtest --count 2>&1 | grep -E 'appointments:' | awk '{print \$NF}'" || echo 0)"
  appt_count="${appt_count:-0}"
  echo "Mevcut sentetik randevu sayısı: $appt_count (hedef: $SYNTH_APPTS)"
  if [ "$appt_count" -lt "$SYNTH_APPTS" ]; then
    echo "🌱 Sentetik veri seed ediliyor ($SYNTH_CUSTOMERS müşteri / $SYNTH_APPTS randevu)…"
    docker exec plann_backend sh -c "cd /app && python -m scripts.seed_synthetic_loadtest --seed --customers $SYNTH_CUSTOMERS --appointments $SYNTH_APPTS"
  else
    echo "✓ Sentetik veri zaten mevcut, seed atlanıyor"
  fi
  local tok; tok="$(mint_token "$SYNTH_USER" "$SYNTH_ORG")"
  # Doğrulama: token çalışıyor mu?
  local st; st="$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $tok" "$BASE_URL/stats/dashboard")"
  echo "Sentetik token dashboard status: $st"
  run_k6 large "$tok"
}

echo "=== PLANN k6 3-Profil — $(date '+%F %T') ===" | tee "$RESULTS"

case "${1:-all}" in
  cold)  profile_cold ;;
  warm)  profile_warm ;;
  large) profile_large ;;
  all)   profile_cold; profile_warm; profile_large ;;
  *) echo "Kullanım: $0 cold|warm|large|all"; exit 1 ;;
esac

echo ""
echo "=== TEKİL ÖLÇÜMLER ==="
cat "$RESULTS"
echo ""
echo "Özet dosyaları: k6_{cold,warm,large}_summary.json"
