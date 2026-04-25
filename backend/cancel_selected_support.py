"""
cancel-selected endpoint — saf yardımcılar (pytest için server import gerekmez).
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping


def staff_cannot_access_appointments(
    appts: Iterable[Mapping[str, Any]],
    staff_username: str,
) -> bool:
    """
    Personel (can_view_all=False) için: listedeki her randevu bu personele atanmış olmalı.
    Erişim reddedilmeli ise True.
    """
    for a in appts:
        if a.get("staff_member_id") != staff_username:
            return True
    return False
