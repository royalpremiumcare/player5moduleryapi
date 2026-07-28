"""
PLANN Asistan — 3 katmanlı zeka motoru (Analytics → Health → Notification).

TR-only (Europe/Istanbul, TRY, Türkçe metinler). Alıcı: işletme sahibi (admin).
ASSISTANT_ENABLED env flag'i ile kontrol edilir.
"""

from .scheduler_jobs import register_assistant_jobs, ASSISTANT_ENABLED  # noqa: F401

__all__ = ["register_assistant_jobs", "ASSISTANT_ENABLED"]
