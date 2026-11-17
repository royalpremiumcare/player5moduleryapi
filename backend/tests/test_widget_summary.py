"""Widget summary additions: tomorrowFirst and orgName (spec §4.2, §7A.6)."""

from tests.test_live_activity_endpoints import apt, env, jwt_user, seed_day  # noqa: F401  (env is a fixture)

URL = "/api/widget/summary"
TOMORROW = "2026-11-17"


def summary(env):
    resp = env.client.get(URL)
    assert resp.status_code == 200
    return resp.json()


def test_tomorrow_first_is_earliest_visible_next_day(env):
    seed_day(env)
    env.db.appointments.docs.extend([
        apt("t-late", "15:00", staff="elif", date=TOMORROW, customer="Geç Müşteri"),
        apt("t-early", "09:30", staff="elif", date=TOMORROW, customer="Ayşe Kaya", service="Boya"),
        apt("t-after", "09:00", staff="elif", date="2026-11-18"),
    ])
    assert summary(env)["tomorrowFirst"] == {
        "startLabel": "09:30", "customerDisplay": "Ayşe Kaya", "serviceName": "Boya"}


def test_tomorrow_first_excludes_cancelled_and_other_staff_for_own_scope(env):
    seed_day(env)
    env.db.appointments.docs.extend([
        apt("t-cancel", "08:00", staff="can", date=TOMORROW, status="İptal"),
        apt("t-other", "08:30", staff="elif", date=TOMORROW, customer="Başka Personel"),
        apt("t-mine", "11:00", staff="can", date=TOMORROW, customer="Zeynep Acar"),
    ])
    env.current["user"] = jwt_user("can", role="staff", can_view_all_appointments=True)
    body = summary(env)
    assert body["scope"] == "own"
    assert body["tomorrowFirst"]["startLabel"] == "11:00"
    assert body["tomorrowFirst"]["customerDisplay"] == "Zeynep Acar"
    # the all-staff view does see the earlier colleague appointment (cancelled one still skipped)
    env.current["user"] = jwt_user("ali")
    assert summary(env)["tomorrowFirst"]["startLabel"] == "08:30"


def test_tomorrow_first_null_when_none(env):
    seed_day(env)
    env.db.appointments.docs[:] = [a for a in env.db.appointments.docs if a["appointment_date"] != TOMORROW]
    env.db.appointments.docs.append(apt("t-other-org", "09:00", date=TOMORROW, org="org2"))
    env.db.appointments.docs.append(apt("t-cancel", "09:00", date=TOMORROW, status="İptal"))
    assert summary(env)["tomorrowFirst"] is None


def test_org_name_present(env):
    env.db.settings.docs[0]["company_name"] = "Güzellik Salonu"
    assert summary(env)["orgName"] == "Güzellik Salonu"
    del env.db.settings.docs[0]["company_name"]
    assert summary(env)["orgName"] == ""


def test_tomorrow_first_respects_privacy_mode(env):
    seed_day(env, lock_screen_name_mode="hidden")
    env.db.appointments.docs.append(
        apt("t1", "09:30", staff="elif", date=TOMORROW))
    body = summary(env)
    assert body["privacyMode"] == "hidden"
    assert body["tomorrowFirst"]["customerDisplay"] is None
    assert body["tomorrowFirst"]["startLabel"] == "09:30"
