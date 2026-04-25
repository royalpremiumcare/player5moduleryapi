#!/usr/bin/env python3
"""
Wise: status=incoming_payment_waiting olan transferleri listeler ve iptal eder.

Kimlik bilgileri asla koda yazılmaz; backend/.env içinden okunur:
  WISE_API_TOKEN, WISE_PROFILE_ID, WISE_ENVIRONMENT (production|sandbox)

Kullanım (repo kökünden):
  cd /var/www/player5moduleryapi && ./venv/bin/python backend/scripts/cancel_wise_pending_transfers.py
"""

from __future__ import annotations

import os
import sys

import requests
from dotenv import load_dotenv

# Proje kökü: .../player5moduleryapi
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
load_dotenv(os.path.join(_ROOT, "backend", ".env"))

WISE_API_BASE = "https://api.transferwise.com"
WISE_SANDBOX_API_BASE = "https://api.wise-sandbox.com"


def _api_base() -> str:
    env = os.getenv("WISE_ENVIRONMENT", "sandbox")
    return WISE_SANDBOX_API_BASE if env == "sandbox" else WISE_API_BASE


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def main() -> None:
    token = os.getenv("WISE_API_TOKEN", "").strip()
    profile_id = os.getenv("WISE_PROFILE_ID", "").strip()
    if not token or not profile_id:
        print("WISE_API_TOKEN ve WISE_PROFILE_ID backend/.env içinde tanımlı olmalı.", file=sys.stderr)
        sys.exit(1)

    base = _api_base()
    print(f"API: {base}  (WISE_ENVIRONMENT={os.getenv('WISE_ENVIRONMENT', 'sandbox')})")
    print("Bekleyen (incoming_payment_waiting) transferler taranıyor...")

    # Wise list endpoint: limit çok yüksek olunca 422 dönebiliyor; max tipik 100.
    transfers: list = []
    offset = 0
    page_limit = 100
    while True:
        list_url = (
            f"{base}/v1/transfers"
            f"?profile={profile_id}&status=incoming_payment_waiting"
            f"&offset={offset}&limit={page_limit}"
        )
        try:
            r = requests.get(list_url, headers=_headers(token), timeout=30)
            if not r.ok:
                print(f"HTTP {r.status_code}: {r.text[:2000]}", file=sys.stderr)
            r.raise_for_status()
            batch = r.json()
        except Exception as e:
            print(f"Transfer listesi alınamadı: {e}", file=sys.stderr)
            sys.exit(1)
        if not batch:
            break
        transfers.extend(batch)
        if len(batch) < page_limit:
            break
        offset += page_limit
        if offset > 10000:
            print("Uyarı: 10000 kayıt üstü durduruldu.", file=sys.stderr)
            break

    if not transfers:
        print("Bekleyen transfer yok.")
        return

    print(f"{len(transfers)} adet bekleyen transfer; iptal ediliyor...\n")
    ok = 0
    for t in transfers:
        tid = t.get("id")
        cancel_url = f"{base}/v1/transfers/{tid}/cancel"
        res = requests.put(cancel_url, headers=_headers(token), timeout=30)
        if res.status_code == 200:
            print(f"Transfer {tid} iptal edildi")
            ok += 1
        else:
            print(f"Transfer {tid} iptal edilemedi ({res.status_code}): {res.text[:500]}")

    print(f"\nTamamlandı: {ok}/{len(transfers)} iptal.")


if __name__ == "__main__":
    main()
