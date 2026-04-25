#!/usr/bin/env python3
"""
Wise: Token'a bağlı tüm profilleri (bireysel + kurumsal) listeler.

Kimlik bilgisi backend/.env: WISE_API_TOKEN
Ortam: WISE_ENVIRONMENT=production | sandbox

Kullanım:
  cd /var/www/player5moduleryapi && ./venv/bin/python backend/scripts/get_profiles.py
"""

from __future__ import annotations

import os
import sys

import requests
from dotenv import load_dotenv

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
load_dotenv(os.path.join(_ROOT, "backend", ".env"))

WISE_API_BASE = "https://api.transferwise.com"
WISE_SANDBOX_API_BASE = "https://api.wise-sandbox.com"


def _api_base() -> str:
    env = os.getenv("WISE_ENVIRONMENT", "sandbox")
    return WISE_SANDBOX_API_BASE if env == "sandbox" else WISE_API_BASE


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

    print("Wise profilleri sorgulanıyor...\n")
    print(f"API: {base}  (WISE_ENVIRONMENT={os.getenv('WISE_ENVIRONMENT', 'sandbox')})\n")

    url = f"{base}/v2/profiles"
    try:
        response = requests.get(url, headers=headers, timeout=30)
    except Exception as e:
        print(f"İstek başarısız: {e}", file=sys.stderr)
        sys.exit(1)

    if response.status_code != 200:
        print(f"Hata HTTP {response.status_code}: {response.text[:2000]}", file=sys.stderr)
        sys.exit(1)

    profiles = response.json()
    if not profiles:
        print("Profil bulunamadı.")
        return

    for p in profiles:
        p_type = "KURUMSAL (Business)" if p.get("type") == "business" else "BİREYSEL (Personal)"
        print(f"Tip: {p_type}")
        print(f"İsim: {p.get('name', 'Bilinmiyor')}")
        print(f"PROFIL ID: {p.get('id')}")
        print("-" * 30)

    print(f"\nToplam: {len(profiles)} profil")


if __name__ == "__main__":
    main()
