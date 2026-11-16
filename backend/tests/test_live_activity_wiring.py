"""Import-light wiring checks: server.py is read as text (importing it has heavy side effects)."""
import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
SERVER = (BACKEND / "server.py").read_text(encoding="utf-8")


def _block(start_pat: str, end_pat: str) -> str:
    s = re.search(start_pat, SERVER, re.M)
    assert s, start_pat
    e = re.search(end_pat, SERVER[s.end():], re.M)
    return SERVER[s.start(): s.end() + (e.start() if e else len(SERVER))]


def test_settings_defaults_flag_off():
    body = _block(r"^class Settings\(BaseModel\):", r"^class \w+")
    assert "live_activity_enabled: bool = False" in body
    assert "live_activity_lead_minutes: int = 30" in body
    assert 'lock_screen_name_mode: str = "initials"' in body


def test_user_new_fields_optional():
    body = _block(r"^class User\(BaseModel\):", r"^class \w+")
    assert "live_activity_scope: Optional[str] = None" in body
    assert "live_activity_slot_count: Optional[int] = None" in body
    assert "live_activity_start_alert: bool = False" in body


def test_emit_hook_events_listed():
    body = _block(r"^async def emit_to_organization", r"\n(?=\S)")
    for ev in ("appointment_created", "appointment_updated", "appointment_deleted", "appointments_bulk_updated"):
        assert ev in body
    assert "live_activity.sweeper.resync" in body


def test_scheduler_job_and_indexes():
    assert "live_activity_sweep_job" in SERVER
    assert "live_activity.registry.ensure_indexes" in SERVER


def test_router_included():
    assert re.search(r"include_router\(\s*live_activity\.endpoints\.router", SERVER)
    assert "live_activity.endpoints.configure(" in SERVER


def test_dockerfile_pins_firebase_admin():
    assert "firebase-admin==7.1.0" in (BACKEND / "Dockerfile").read_text()
    assert "firebase-admin==7.1.0" in (BACKEND / "requirements.txt").read_text()
