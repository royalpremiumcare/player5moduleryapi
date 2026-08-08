#!/usr/bin/env bash
# ============================================================================
# PLANN — Capgo OTA yayın yardımcısı
# ============================================================================
# Kullanım:
#   ./ota-release.sh build   <sürüm>   # derle + internal kanala yükle (TEST)
#   ./ota-release.sh promote <sürüm>   # mevcut sürümü production'a al (HERKES)
#   ./ota-release.sh release <sürüm>   # derle + internal + production (tek adım)
#   ./ota-release.sh status            # kanal durumunu göster
#
# Örnek akış:
#   ./ota-release.sh build 6.3.1       # önce internal'a at, cihazında dene
#   ./ota-release.sh promote 6.3.1     # doğrulayınca herkese aç
#
# Sürüm kuralı: native sürümden YÜKSEK + aynı major olmalı.
#   Şu an native 6.3  →  OTA: 6.3.1, 6.3.2, ...
#
# CAPGO_TOKEN nasıl verilir (biri yeterli):
#   1) export CAPGO_TOKEN="capgo-api-anahtarin"          (oturum boyunca)
#   2) proje kökünde .capgo.token dosyasına anahtarı yaz  (kalıcı; gitignore'da)
# ============================================================================
set -euo pipefail

APP_ID="co.plannapp.app"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

c_g(){ printf "\033[32m%s\033[0m\n" "$*"; }   # yeşil
c_y(){ printf "\033[33m%s\033[0m\n" "$*"; }   # sarı
c_r(){ printf "\033[31m%s\033[0m\n" "$*"; }   # kırmızı
c_b(){ printf "\033[36m%s\033[0m\n" "$*"; }   # mavi

usage(){
  cat <<EOF
PLANN OTA yayın:
  $0 build   <sürüm>   # derle + internal kanala yükle (TEST cihazında dene)
  $0 promote <sürüm>   # mevcut sürümü production'a al (TÜM kullanıcılar)
  $0 release <sürüm>   # derle + internal + production (tek adımda)
  $0 status            # kanal durumunu göster

Örnek: $0 build 6.3.1

Token: export CAPGO_TOKEN="..."  ya da  proje kökünde .capgo.token dosyası
EOF
}

# --- token'ı bul ---
if [ -z "${CAPGO_TOKEN:-}" ] && [ -f "$SCRIPT_DIR/.capgo.token" ]; then
  CAPGO_TOKEN="$(tr -d ' \n\r' < "$SCRIPT_DIR/.capgo.token")"
fi

capgo(){ ( cd "$FRONTEND_DIR" && npx @capgo/cli@latest "$@" ); }

require_token(){
  if [ -z "${CAPGO_TOKEN:-}" ]; then
    c_r "CAPGO_TOKEN yok. Ya 'export CAPGO_TOKEN=...' yap ya da proje köküne .capgo.token dosyası koy."
    exit 1
  fi
}

validate_ver(){
  if ! [[ "$1" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    c_r "Sürüm x.y.z biçiminde olmalı (ör. 6.3.1). Verdiğin: '$1'"
    exit 1
  fi
}

do_build(){
  c_b "→ Derleniyor (CI=false npm run build)…"
  ( cd "$FRONTEND_DIR" && CI=false npm run build )
  c_g "✓ Derleme bitti: $FRONTEND_DIR/build"
}

do_upload_internal(){
  local ver="$1"
  c_b "→ internal kanala yükleniyor: $ver"
  capgo bundle upload "$APP_ID" -a "$CAPGO_TOKEN" -c internal --path ./build --bundle "$ver"
  c_g "✓ internal'a yüklendi: $ver"
  c_y "▶ TEST: internal'a bağlı cihazında uygulamayı 2 kez soğuk başlat, çalıştığını doğrula."
  c_y "  Doğrulayınca herkese açmak için:  $0 promote $ver"
}

do_promote(){
  local ver="$1"
  c_b "→ production'a alınıyor (TÜM KULLANICILAR): $ver"
  capgo channel set production "$APP_ID" -a "$CAPGO_TOKEN" --bundle "$ver" --state default --ignore-metadata-check
  c_g "✓ production = $ver  (bundan sonra herkes bunu alır)"
  do_status
}

do_status(){
  c_b "→ Kanal durumu:"
  capgo channel list "$APP_ID" -a "$CAPGO_TOKEN" | tail -10 || true
}

CMD="${1:-}"; VER="${2:-}"
case "$CMD" in
  build)
    require_token; validate_ver "$VER"
    do_build; do_upload_internal "$VER"
    ;;
  promote)
    require_token; validate_ver "$VER"
    do_promote "$VER"
    ;;
  release)
    require_token; validate_ver "$VER"
    do_build; do_upload_internal "$VER"
    c_y "▶ 'release' seçildi: internal testi ATLANIYOR, doğrudan production'a alınıyor…"
    do_promote "$VER"
    ;;
  status)
    require_token; do_status
    ;;
  -h|--help|help|"")
    usage
    ;;
  *)
    c_r "Bilinmeyen komut: $CMD"; usage; exit 1
    ;;
esac

c_g "Bitti."
