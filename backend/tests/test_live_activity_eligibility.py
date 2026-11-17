from datetime import datetime

from live_activity.eligibility import (
    effective_lead_minutes,
    effective_scope,
    is_manager,
    slot_count,
    visible_for_user,
)
from live_activity.phase import TR_TZ, Phase

NOW = datetime(2026, 11, 16, 10, 0, tzinfo=TR_TZ)

ADMIN = {"username": "owner", "role": "admin"}
STAFF = {"username": "elif", "role": "staff", "can_view_all_appointments": False}
MANAGER = {"username": "mert", "role": "staff", "can_view_all_appointments": True}


def apt(id, time, staff="elif", date="2026-11-16", status="Onaylandı", **kw):
    return {
        "id": id,
        "appointment_date": date,
        "appointment_time": time,
        "staff_member_id": staff,
        "status": status,
        "service_duration": 30,
        **kw,
    }


def visible(apts, user, scope="all", now=NOW, day_open=True, lead_min=30):
    return visible_for_user(
        apts, user, scope, now=now, services_by_id={}, lead_min=lead_min, day_open=day_open
    )


def ids(result):
    return [v.id for v in result]


def test_is_manager():
    assert is_manager(MANAGER)
    assert not is_manager(STAFF)
    assert not is_manager(ADMIN)


def test_admin_default_all():
    assert effective_scope(ADMIN, admin_provides_service=True, org_has_staff=True) == "all"


def test_admin_pref_own():
    u = {**ADMIN, "live_activity_scope": "own"}
    assert effective_scope(u, admin_provides_service=True, org_has_staff=True) == "own"


def test_manager_default_own_can_choose_all():
    assert effective_scope(MANAGER, admin_provides_service=True, org_has_staff=True) == "own"
    u = {**MANAGER, "live_activity_scope": "all"}
    assert effective_scope(u, admin_provides_service=True, org_has_staff=True) == "all"


def test_plain_staff_all_pref_ignored():
    u = {**STAFF, "live_activity_scope": "all"}
    assert effective_scope(u, admin_provides_service=True, org_has_staff=True) == "own"


def test_forced_all_when_admin_not_service_and_no_staff():
    u = {**ADMIN, "live_activity_scope": "own"}
    assert effective_scope(u, admin_provides_service=False, org_has_staff=False) == "all"
    assert effective_scope(u, admin_provides_service=False, org_has_staff=True) == "own"


def test_unassigned_visible_to_admin_in_own_and_all():
    a = [apt("u", "11:00", staff=None)]
    assert ids(visible(a, ADMIN, "own")) == ["u"]
    assert ids(visible(a, ADMIN, "all")) == ["u"]


def test_unassigned_not_visible_to_staff():
    a = [apt("u", "11:00", staff=None)]
    assert visible(a, STAFF, "own") == []


def test_own_scope_filters_by_staff():
    a = [apt("a", "11:00", staff="elif"), apt("b", "11:30", staff="other")]
    assert ids(visible(a, STAFF, "own")) == ["a"]
    assert ids(visible(a, ADMIN, "all")) == ["a", "b"]


def test_slot_count_defaults_and_clamp():
    assert slot_count(ADMIN, "all") == 4
    assert slot_count({**ADMIN, "live_activity_slot_count": 9}, "all") == 5
    assert slot_count({**ADMIN, "live_activity_slot_count": 0}, "all") == 1
    assert slot_count({**ADMIN, "live_activity_slot_count": -3}, "all") == 1
    assert slot_count(STAFF, "own") == 1
    assert slot_count({**STAFF, "live_activity_slot_count": 5}, "own") == 1
    assert slot_count({**ADMIN, "live_activity_slot_count": 5}, "own") == 1


def test_lead_clamp():
    assert effective_lead_minutes(1) == 5
    assert effective_lead_minutes(500) == 120
    assert effective_lead_minutes(None) == 30
    assert effective_lead_minutes(45) == 45


def test_day_closed_only_lead_window():
    a = [apt("far", "10:40"), apt("near", "10:25")]
    assert ids(visible(a, ADMIN, day_open=False, lead_min=30)) == ["near"]


def test_day_open_shows_rest_of_day():
    a = [apt("late", "16:00"), apt("tomorrow", "09:00", date="2026-11-17")]
    assert ids(visible(a, ADMIN, day_open=True)) == ["late"]


def test_order_processing_by_end_then_upcoming_by_start():
    a = [
        apt("up2", "12:00"),
        apt("up1", "11:00"),
        apt("pr_long", "09:00", service_duration=90),  # ends 10:30
        apt("pr_short", "09:45"),  # ends 10:15
    ]
    res = visible(a, ADMIN)
    assert ids(res) == ["pr_short", "pr_long", "up1", "up2"]
    assert [v.phase for v in res] == [
        Phase.PROCESSING, Phase.PROCESSING, Phase.UPCOMING, Phase.UPCOMING
    ]


def test_cancelled_and_completed_excluded():
    a = [
        apt("c", "11:00", status="İptal"),
        apt("d", "11:00", status="Tamamlandı"),
        apt("old", "08:00"),
        apt("ok", "11:00"),
    ]
    assert ids(visible(a, ADMIN)) == ["ok"]


def test_bad_date_skipped():
    a = [
        apt("bad", "25:99"),
        {"id": "missing", "appointment_date": "2026-11-16", "staff_member_id": "elif", "status": "Onaylandı"},
        apt("ok", "11:00"),
    ]
    assert ids(visible(a, ADMIN)) == ["ok"]


def test_processing_across_midnight_stays_visible():
    a = [apt("late", "23:40", date="2026-11-16", service_duration=45)]
    now = datetime(2026, 11, 17, 0, 10, tzinfo=TR_TZ)
    res = visible(a, ADMIN, now=now)
    assert ids(res) == ["late"]
    assert res[0].phase == Phase.PROCESSING


def test_non_int_duration_skipped():
    bad_own = apt("bad1", "10:10", service_duration="45")                 # string duration
    bad_service = apt("bad2", "10:15", service_duration=None, service_id="s1")
    good = apt("good", "10:20")
    result = visible_for_user([bad_own, bad_service, good], STAFF, "own", now=NOW,
                              services_by_id={"s1": "forty"}, lead_min=30, day_open=True)
    assert ids(result) == ["good"]


# --- across midnight: the lead window ignores the calendar date ------------------------

LATE = datetime(2026, 11, 16, 23, 50, tzinfo=TR_TZ)
TOMORROW_APT = apt("n", "00:15", date="2026-11-17")


def test_upcoming_tomorrow_inside_lead_is_visible():
    assert ids(visible([TOMORROW_APT], ADMIN, now=LATE, day_open=False)) == ["n"]
    assert ids(visible([TOMORROW_APT], ADMIN, now=LATE, day_open=True)) == ["n"]


def test_upcoming_tomorrow_outside_lead_not_visible_even_if_day_open():
    now = datetime(2026, 11, 16, 22, 0, tzinfo=TR_TZ)
    assert visible([TOMORROW_APT], ADMIN, now=now, day_open=True) == []


def test_day_open_today_unchanged():
    later = apt("l", "15:00")
    assert ids(visible([later], ADMIN, day_open=True)) == ["l"]
    assert visible([later], ADMIN, day_open=False) == []
