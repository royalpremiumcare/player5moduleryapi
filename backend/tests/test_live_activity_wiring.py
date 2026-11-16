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


def test_wiring_is_guarded_by_try_except():
    lines = SERVER.splitlines()

    def guarded(idx: int, back: int = 6, fwd: int = 4) -> bool:
        before = "\n".join(lines[max(0, idx - back): idx])
        after = "\n".join(lines[idx + 1: idx + 1 + fwd])
        return "try:" in before and "except" in after and "logging.warning" in after

    imp = next(i for i, l in enumerate(lines) if l.strip() == "import live_activity.sweeper")
    assert "try:" in lines[imp - 1]
    assert "live_activity = None" in SERVER
    inc = next(i for i, l in enumerate(lines) if "include_router(live_activity.endpoints.router" in l)
    assert guarded(inc)
    assert "live_activity is not None and _LA_TRANSPORT is not None" in _block(
        r"^async def emit_to_organization", r"\n(?=\S)")


def test_tenant_settings_update_cannot_set_pilot_flag():
    # Controller ruling F-6: live_activity_enabled is operator-only; tenants keep lead/name mode.
    body = _block(r"^async def update_settings\(request: Request, settings: Settings", r"\n(?=\S)")
    dump = body.index("update_data = settings.model_dump(exclude_unset=True)")
    pop = body.index('update_data.pop("live_activity_enabled", None)')
    write = body.index("await db.settings.update_one(query, {\"$set\": update_data}, upsert=True)")
    assert dump < pop < write
    assert "live_activity_lead_minutes" not in body and "lock_screen_name_mode" not in body
