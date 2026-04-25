#!/usr/bin/env python3
"""
Wise: Profil bazlı STANDARD bakiye listesi (GBP vurgulu).

backend/.env:
  WISE_API_TOKEN
  WISE_ENVIRONMENT=production|sandbox
  WISE_PROFILE_IDS=84997960,84998050   (opsiyonel; virgülle ayrılmış)

Kullanım:
  cd /var/www/player5moduleryapi && ./venv/bin/python backend/scripts/check_balance.py
"""

from __future__ import annotations

import json
import os
import sys

import requests
from dotenv import load_dotenv

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
load_dotenv(os.path.join(_ROOT, "backend", ".env"))

WISE_API_BASE = "https://api.transferwise.com"
WISE_SANDBOX_API_BASE = "https://api.wise-sandbox.com"

DEFAULT_PROFILE_IDS = ("84997960", "84998050")


def _api_base() -> str:
    env = os.getenv("WISE_ENVIRONMENT", "sandbox")
    return WISE_SANDBOX_API_BASE if env == "sandbox" else WISE_API_BASE


def _profile_ids() -> list[str]:
    raw = os.getenv("WISE_PROFILE_IDS", "").strip()
    if raw:
        return [p.strip() for p in raw.split(",") if p.strip()]
    return list(DEFAULT_PROFILE_IDS)


def main() -> None:
    token = os.getenv("WISE_API_TOKEN", "").strip()
    if not token:
        print("WISE_API_TOKEN backend/.env içinde tanımlı olmalı.", file=sys.stderr)
        sys.exit(1)

    base = _api_base()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    print("Wise bakiyeleri sorgulanıyor...\n")
    print(f"API: {base}  (WISE_ENVIRONMENT={os.getenv('WISE_ENVIRONMENT', 'sandbox')})\n")

    for pid in _profile_ids():
        url = f"{base}/v4/profiles/{pid}/balances?types=STANDARD"
        try:
            response = requests.get(url, headers=headers, timeout=30)
        except Exception as e:
            print(f"--- PROFIL ID: {pid} ---")
            print(f"İstek hatası: {e}\n")
            continue

        print(f"--- PROFIL ID: {pid} ---")
        if response.status_code == 200:
            balances = response.json()
            gbp_found = False
            for b in balances:
                if b.get("currency") == "GBP":
                    val = (b.get("amount") or {}).get("value")
                    print(f"GBP bakiyesi: {val} GBP")
                    gbp_found = True
            if not gbp_found:
                print("GBP cüzdanı yok veya bakiye yok.")
            # Debug: ham yapı farklıysa görmek için (isteğe bağlı kısa özet)
            if os.getenv("WISE_BALANCE_DEBUG_JSON") == "1":
                print("(debug)", json.dumps(balances, ensure_ascii=False)[:800])
        else:
            print(
                f"Cüzdana erişilemedi: HTTP {response.status_code} — "
                f"{(response.text or '')[:500]}"
            )
        print()


if __name__ == "__main__":
    main()
