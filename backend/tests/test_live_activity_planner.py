import pytest
from datetime import datetime, timedelta

from live_activity.eligibility import VisibleAppt, visible_for_user
from live_activity.phase import TR_TZ, Phase, compute_phase
from live_activity.planner import plan_device

NOW = datetime(2026, 11, 16, 10, 0, tzinfo=TR_TZ)
TODAY = "2026-11-16"
P, U = Phase.PROCESSING, Phase.UPCOMING
LEAD = timedelta(minutes=30)


def va(id, phase, start_min, dur=30):
    """A visible appointment starting `start_min` minutes from NOW."""
    start = NOW + timedelta(minutes=start_min)
    return VisibleAppt(id=id, phase=phase, start=start, end=start + timedelta(minutes=dur), apt={"id": id})


def slot(i, aid, phase, *, state="active", token="tok", hash=None, started_h=1.0, day=TODAY):
    return {
        "slot_index": i,
        "state": state,
        "appointment_id": aid,
        "phase_sent": phase.value,
        "content_hash": hash if hash is not None else f"h-{aid}",
        "update_token": token if state == "active" else None,
        "started_at": (NOW - timedelta(hours=started_h)).timestamp(),
        "day": day,
        "version": 3,
    }


def plan(slots, visible, n=3, now=NOW, **kw):
    args = dict(
        slots=slots, visible=visible, n_slots=n, now=now, starts_last_hour=0, start_budget=8,
        start_alert_enabled=False, has_push_to_start=True, content_hash=lambda v: f"h-{v.id}",
        lead=LEAD,
    )
    args.update(kw)
    return plan_device(**args)


def apply(slots, actions, now, *, token="tok", content_hash=lambda v: f"h-{v.id}", visible=()):
    """What the sweeper persists after successful sends."""
    by_index = {s["slot_index"]: dict(s) for s in slots}
    by_id = {v.id: v for v in visible}
    for a in actions:
        if a.kind == "end":
            by_index[a.slot_index]["state"] = "ended"
            continue
        s = by_index.setdefault(a.slot_index, {"slot_index": a.slot_index, "version": 0})
        if a.kind == "start":
            s.update(state="active" if token else "start_sent", update_token=token,
                     started_at=now.timestamp(), day=now.strftime("%Y-%m-%d"))
        s.update(appointment_id=a.appointment_id, phase_sent=a.phase.value,
                 content_hash=content_hash(by_id[a.appointment_id]) if by_id else f"h-{a.appointment_id}")
        s["version"] += 1
    return sorted(by_index.values(), key=lambda s: s["slot_index"])


def summary(actions):
    return [(a.kind, a.slot_index, a.appointment_id, a.phase, a.priority, a.alert, a.dismissal) for a in actions]


def test_first_open_starts_one_slot_per_visible_up_to_n():
    visible = [va("a", U, 20), va("b", U, 40), va("c", U, 60), va("d", U, 80)]
    slots, started = [], []
    for _ in range(5):  # successive sweeps at the same instant; tokens not yet arrived
        actions = plan(slots, visible, n=3)
        started += actions
        slots = apply(slots, actions, NOW, token=None)
    assert summary(started) == [
        ("start", 1, "a", U, 10, "start", None),
        ("start", 2, "b", U, 10, "start", None),
        ("start", 3, "c", U, 10, "start", None),
    ]
    assert [s["state"] for s in slots] == ["start_sent"] * 3

    slots, started = [], []
    for _ in range(4):  # fewer visible than slots: only as many starts as visible
        actions = plan(slots, visible[:2], n=3)
        started += actions
        slots = apply(slots, actions, NOW, token=None)
    assert [(a.kind, a.slot_index, a.appointment_id) for a in started] == [("start", 1, "a"), ("start", 2, "b")]


def test_stable_assignment_keeps_slots():
    slots = [slot(1, "a", P), slot(2, "b", U), slot(3, "c", U)]
    # b moved later than c: the order changes, but every appointment stays in its slot
    visible = [va("a", P, -10), va("c", U, 40), va("b", U, 50)]
    assert plan(slots, visible) == []


def test_completed_slot_switches_to_next_silently_p10():
    slots = [slot(1, "a", P), slot(2, "b", U)]
    visible = [va("b", U, 10), va("c", U, 40)]  # a completed
    actions = plan(slots, visible, n=2, start_alert_enabled=True)
    assert summary(actions) == [("update", 1, "c", U, 10, None, None)]


def test_idle_slot_ends_soon_at_day_end():
    slots = [slot(1, "a", P), slot(2, "b", U)]
    actions = plan(slots, [], n=2, final_phases={"a": Phase.COMPLETED, "b": Phase.CANCELLED})
    assert summary(actions) == [
        ("end", 1, "a", Phase.COMPLETED, 10, None, "soon"),
        ("end", 2, "b", Phase.CANCELLED, 10, None, "soon"),
    ]
    # without a completed/cancelled phase the appointment left the scope: removed, dismissed now
    for final in ({}, {"a": Phase.REMOVED, "b": Phase.INELIGIBLE}):
        assert [(a.phase, a.dismissal) for a in plan(slots, [], n=2, final_phases=final)] == [
            (Phase.REMOVED, "now"), (Phase.REMOVED, "now")]


def test_processing_outranks_upcoming_when_full():
    slots = [slot(1, "p1", P), slot(2, "p2", P), slot(3, "p3", P)]
    burak = va("burak", U, 5)
    visible = [va("p1", P, -20, 25), va("p2", P, -10, 30), va("p3", P, -5, 40), burak]
    assert plan(slots, visible) == []  # Burak waits: no start, no switch
    actions = plan(slots, visible[1:])  # p1 completes
    assert summary(actions) == [("update", 1, "burak", U, 10, None, None)]


def test_held_upcoming_outside_top_n_yields_slot_to_processing():
    # Ruling: stability holds within the top N (spec "take N; keep stable", sim_day.py).
    # A walk-in that is already processing takes the single staff slot from a later upcoming one.
    slots = [slot(1, "later", U)]
    visible = [va("walkin", P, -5), va("later", U, 30)]
    actions = plan(slots, visible, n=1, start_alert_enabled=True)
    assert summary(actions) == [("update", 1, "walkin", P, 10, "processing", None)]


def test_phase_change_is_p10_cosmetic_is_p5():
    slots = [slot(1, "a", U), slot(2, "b", U, hash="old")]
    visible = [va("a", P, 0), va("b", U, 30)]
    actions = plan(slots, visible, n=2)
    assert summary(actions) == [
        ("update", 1, "a", P, 10, None, None),
        ("update", 2, "b", U, 5, None, None),
    ]


def test_single_alert_per_device_batch():
    slots = [slot(1, "a", U), slot(2, "b", U), slot(3, "c", U)]
    visible = [va("a", P, 0), va("b", P, 0, 40), va("c", P, 0, 50), va("d", U, 30)]
    actions = plan(slots, visible, n=4, start_alert_enabled=True)
    assert [(a.kind, a.slot_index, a.priority) for a in actions] == [("update", 1, 10), ("update", 2, 10), ("update", 3, 10)]
    assert [a.alert for a in actions] == ["processing", None, None]
    # the start of slot 4 (mandatory "start" alert) waits for a sweep without an alert
    after = plan(apply(slots, actions, NOW, visible=visible), visible, n=4, start_alert_enabled=True)
    assert summary(after) == [("start", 4, "d", U, 10, "start", None)]


def test_alert_off_by_default():
    slots = [slot(1, "a", U)]
    visible = [va("a", P, 0), va("b", U, 30)]
    actions = plan(slots, visible, n=2, start_alert_enabled=False)
    # with no processing alert, the start may use the sweep's single alert
    assert summary(actions) == [
        ("update", 1, "a", P, 10, None, None),
        ("start", 2, "b", U, 10, "start", None),
    ]


def test_relevance_on_every_action():
    slots = [slot(1, "a", U), slot(2, "gone", U), slot(5, "x", U)]
    visible = [va("a", P, -1), va("c", U, 60), va("d", U, 120)]
    actions = plan(slots, visible, n=4)
    assert [(a.kind, a.slot_index, a.relevance) for a in actions] == [
        ("end", 5, 0.0),  # slot count 4 < slot 5
        ("update", 1, pytest.approx(100 + 99 * (1 - 629 / 1440))),  # processing, ends 10:29
        ("update", 2, pytest.approx(1 + 98 * (1 - 660 / 1440))),  # upcoming, starts 11:00
        ("start", 3, pytest.approx(1 + 98 * (1 - 720 / 1440))),  # upcoming, starts 12:00
    ]
    assert all(isinstance(a.relevance, float) for a in actions)


def test_no_token_no_update():
    slots = [
        slot(1, "a", U, state="start_sent"),  # phase change due
        slot(2, "gone", U, state="start_sent"),  # switch due
        slot(4, "x", U, state="start_sent"),  # beyond n: end due
    ]
    visible = [va("a", P, 0), va("c", U, 30)]
    # nothing is sent, and c is not started elsewhere: it waits for slot 2's token
    assert plan(slots, visible, n=3, start_alert_enabled=True) == []
    tokens = [{**s, "state": "active", "update_token": "tok"} for s in slots]
    actions = plan(tokens, visible, n=3, start_alert_enabled=True)
    assert summary(actions) == [
        ("end", 4, "x", U, 10, None, "now"),
        ("update", 1, "a", P, 10, "processing", None),
        ("update", 2, "c", U, 10, None, None),
    ]


def test_start_budget_blocks_extra_starts():
    visible = [va("a", U, 20)]
    assert plan([], visible, starts_last_hour=8, start_budget=8) == []
    assert [a.kind for a in plan([], visible, starts_last_hour=7, start_budget=8)] == ["start"]


def test_no_push_to_start_no_start():
    slots = [slot(1, "a", U)]
    visible = [va("a", P, 0), va("b", U, 30)]
    actions = plan(slots, visible, has_push_to_start=False)
    assert summary(actions) == [("update", 1, "a", P, 10, None, None)]


def test_start_skipped_when_stale_date_under_60s():
    soon = NOW + timedelta(seconds=30)
    near = VisibleAppt(id="near", phase=U, start=soon, end=soon + timedelta(minutes=30), apt={})
    assert plan([], [near]) == []
    actions = plan([], [near, va("later", U, 40)])
    assert [(a.kind, a.slot_index, a.appointment_id) for a in actions] == [("start", 1, "later")]


def test_dismissed_slot_not_reopened_today():
    dismissed = slot(1, "a", U, state="dismissed_by_user")
    visible = [va("a", U, 10), va("b", U, 30)]
    # slot 1 stays closed and a is not moved into another slot; b may open slot 2
    assert summary(plan([dismissed], visible, n=2)) == [("start", 2, "b", U, 10, "start", None)]
    assert plan([dismissed], visible[:1], n=2) == []
    yesterday = {**dismissed, "day": "2026-11-15"}
    assert [(a.kind, a.slot_index, a.appointment_id) for a in plan([yesterday], visible[:1], n=2)] == [
        ("start", 1, "a")
    ]


def test_8h_restart_not_during_processing():
    visible = [va("a", P, -30, 60), va("b", U, 40)]
    old_proc, old_up = slot(1, "a", P, started_h=8), slot(2, "b", U, started_h=7.5)
    assert summary(plan([old_proc, old_up], visible, n=2)) == [("end", 2, "b", U, 10, None, "now")]
    assert plan([old_proc, slot(2, "b", U, started_h=7.4)], visible, n=2) == []
    # next sweep: the ended slot is reopened with the same appointment
    ended = {**old_up, "state": "ended"}
    assert summary(plan([old_proc, ended], visible, n=2)) == [("start", 2, "b", U, 10, "start", None)]


def test_slot_count_decrease_ends_extra_slots():
    slots = [slot(1, "u1", U), slot(2, "u2", U), slot(3, "p1", P), slot(4, "p2", P)]
    visible = [va("p1", P, -10), va("p2", P, -5), va("u1", U, 30), va("u2", U, 60)]
    actions = plan(slots, visible, n=2, start_alert_enabled=True)
    # extra slots end now; the processing appointments move into the remaining slots,
    # without replaying their "Randevu başladı" alert
    assert summary(actions) == [
        ("end", 3, "p1", P, 10, None, "now"),
        ("end", 4, "p2", P, 10, None, "now"),
        ("update", 1, "p1", P, 10, None, None),
        ("update", 2, "p2", P, 10, None, None),
    ]


def test_rescheduled_out_of_day_leaves_slot():
    slots = [slot(1, "moved", U)]
    assert summary(plan(slots, [va("b", U, 30)], n=1)) == [("update", 1, "b", U, 10, None, None)]
    assert summary(plan(slots, [], n=1)) == [("end", 1, "moved", Phase.REMOVED, 10, None, "now")]


def test_reassignment_moves_between_staff_devices():
    a = va("a", U, 20)  # reassigned from Elif to Can
    elif_actions = plan([slot(1, "a", U)], [], n=1)
    can_actions = plan([], [a], n=1)
    owner_actions = plan([slot(1, "a", U), slot(2, "z", U)], [a, va("z", U, 50)], n=4)
    assert summary(elif_actions) == [("end", 1, "a", Phase.REMOVED, 10, None, "now")]
    assert summary(can_actions) == [("start", 1, "a", U, 10, "start", None)]
    assert owner_actions == []


# --- sim_day.py replay (RESULTS 24) under spec §3A rules -------------------------------------
# sim_day.py offsets are seconds; appointment times need whole minutes, so 1 sim second = 2 s.
SCALE = 2
T0 = datetime(2026, 11, 16, 10, 0, tzinfo=TR_TZ)
SIM_APPTS = [  # (id, staff, start offset s, duration min) from sim_day.py
    ("a1", "elif", 0, 3), ("a2", "can", 60, 3), ("a3", "ali", 120, 2),
    ("a4", "elif", 210, 2), ("a5", "can", 270, 2),
]
LOG_TICKS = [-59, 1, 62, 122, 182, 213, 243, 273, 334, 394]  # ref-sim_day.log, relative to T0
TICKS = sorted(set(range(-59, 461, 5)) | set(LOG_TICKS))  # sim_day.py TICK = 5
LEAD_MIN = 120 * SCALE // 60


def sim_apts():
    out = []
    for id, staff, off, dur in SIM_APPTS:
        start = T0 + timedelta(seconds=off * SCALE)
        out.append({"id": id, "appointment_date": start.strftime("%Y-%m-%d"),
                    "appointment_time": start.strftime("%H:%M"), "staff_member_id": staff,
                    "status": "Onaylandı", "service_duration": dur * SCALE})
    return out


def run_replay(user, scope, n):
    apts = sim_apts()
    slots, day_open, log = [], False, []
    for t in TICKS:
        now = T0 + timedelta(seconds=t * SCALE)
        visible = visible_for_user(apts, user, scope, now=now, services_by_id={},
                                   lead_min=LEAD_MIN, day_open=day_open)
        final = {a["id"]: compute_phase(a, now, a["service_duration"]) for a in apts}
        actions = plan_device(
            slots=slots, visible=visible, n_slots=n, now=now, lead=timedelta(minutes=LEAD_MIN),
            starts_last_hour=0, start_budget=8,
            start_alert_enabled=True, has_push_to_start=True, content_hash=lambda v: v.id,
            final_phases=final,
        )
        day_open = day_open or any(a.kind == "start" for a in actions)
        slots = apply(slots, actions, now, content_hash=lambda v: v.id, visible=visible)
        held = [s["appointment_id"] for s in slots if s["state"] == "active"]
        phases = [final[i] for i in held]
        log.append((t, now, actions, held, phases))
    return log, slots


def flat(log):
    return [(t, a.kind, a.slot_index, a.appointment_id, a.phase.value, a.alert) for t, _, acts, _, _ in log for a in acts]


def test_replays_sim_day_scenario():
    owner_log, owner_slots = run_replay({"username": "owner", "role": "admin"}, "all", 3)
    elif_log, elif_slots = run_replay(
        {"username": "elif", "role": "staff", "can_view_all_appointments": False}, "own", 1)
    ends = {a["id"]: T0 + timedelta(seconds=(off * SCALE) + dur * SCALE * 60)
            for a, (_, _, off, dur) in zip(sim_apts(), SIM_APPTS)}

    # (a) one "Randevu başladı" per appointment; never two alerted pushes in one tick
    for log, ids in ((owner_log, ["a1", "a2", "a3", "a4", "a5"]), (elif_log, ["a1", "a4"])):
        alerted = [a.appointment_id for _, _, acts, _, _ in log for a in acts if a.alert == "processing"]
        assert sorted(alerted) == ids
        assert all(sum(a.alert is not None for a in acts) <= 1 for _, _, acts, _, _ in log)

    # (b) Elif's device only ever shows her own appointments
    assert {a.appointment_id for _, _, acts, _, _ in elif_log for a in acts} == {"a1", "a4"}

    # (c) while all 3 owner slots hold processing appointments, a4 waits for a slot to free
    k = next(i for i, (_, _, acts, _, _) in enumerate(owner_log) if any(a.appointment_id == "a4" for a in acts))
    waiting = [now for _, now, _, held, ph in owner_log[:k] if len(held) == 3 and all(p is P for p in ph)]
    assert waiting  # a4 was visible but every slot held a processing appointment
    assert owner_log[k - 1][1] < ends["a1"] <= owner_log[k][1]  # it enters on the sweep a1 frees slot 1
    assert [(a.kind, a.slot_index) for a in owner_log[k][2] if a.appointment_id == "a4"] == [("update", 1)]

    # (d) after the last appointment ends, every slot gets `end` and nothing follows
    last_end = max(ends.values())
    for log, slots in ((owner_log, owner_slots), (elif_log, elif_slots)):
        after = [a for _, now, acts, _, _ in log if now >= last_end for a in acts]
        assert all(a.kind == "end" and a.dismissal == "soon" for a in after)
        assert all(s["state"] == "ended" for s in slots)
        assert log[-1][2] == [] and log[-2][2] == []

    # the full action sequence under spec §3A (staggered opening, idle ends "soon")
    assert flat(owner_log) == [
        (-59, "start", 1, "a1", "upcoming", "start"),
        (-54, "start", 2, "a2", "upcoming", "start"),
        (-49, "start", 3, "a3", "upcoming", "start"),
        (1, "update", 1, "a1", "processing", "processing"),
        (61, "update", 2, "a2", "processing", "processing"),
        (121, "update", 3, "a3", "processing", "processing"),
        (181, "update", 1, "a4", "upcoming", None),
        (211, "update", 1, "a4", "processing", "processing"),
        (241, "update", 2, "a5", "upcoming", None),
        (241, "end", 3, "a3", "completed", None),
        (271, "update", 2, "a5", "processing", "processing"),
        (331, "end", 1, "a4", "completed", None),
        (391, "end", 2, "a5", "completed", None),
    ]
    assert flat(elif_log) == [
        (-59, "start", 1, "a1", "upcoming", "start"),
        (1, "update", 1, "a1", "processing", "processing"),
        (181, "update", 1, "a4", "upcoming", None),
        (211, "update", 1, "a4", "processing", "processing"),
        (331, "end", 1, "a4", "completed", None),
    ]



# --- final review fixes ---------------------------------------------------------------------

def test_dismissed_card_not_reopened_after_slot_count_drop():
    # Slot 3 was dismissed today while holding x (processing); the count then drops 3 -> 2.
    vis = [va("x", P, -10), va("y", U, 20), va("z", U, 40)]
    slots = [slot(1, "y", U), slot(2, "z", U), slot(3, "x", P, state="dismissed_by_user")]
    assert plan(slots, vis, n=3) == []
    assert plan(slots, vis, n=2) == []  # x stays hidden: it neither reappears nor takes a top-N place
    # a dismissed slot out of range does not consume a top-N place either
    w = va("w", U, 60)
    actions = plan([slot(1, "y", U), slot(3, "x", P, state="dismissed_by_user")], vis[:2] + [w], n=2)
    assert summary(actions) == [("start", 2, "w", U, 10, "start", None)]


def test_8h_restart_only_with_push_to_start():
    old = slot(1, "b", U, started_h=8)
    visible = [va("b", U, 40)]
    assert summary(plan([old], visible, n=1)) == [("end", 1, "b", U, 10, None, "now")]
    # without push-to-start the slot could not be reopened by a push: keep it running
    assert plan([old], visible, n=1, has_push_to_start=False) == []


def test_out_of_scope_appointment_ends_now_removed():
    # reassigned / rescheduled to another day / back to an ineligible status: neither final nor visible
    s = [slot(1, "a", U)]
    assert summary(plan(s, [], n=1)) == [("end", 1, "a", Phase.REMOVED, 10, None, "now")]
    assert summary(plan(s, [], n=1, final_phases={"a": Phase.INELIGIBLE})) == [
        ("end", 1, "a", Phase.REMOVED, 10, None, "now")]
    # completed / cancelled still end soon with the final phase
    assert summary(plan(s, [], n=1, final_phases={"a": Phase.COMPLETED})) == [
        ("end", 1, "a", Phase.COMPLETED, 10, None, "soon")]
    assert summary(plan(s, [], n=1, final_phases={"a": Phase.CANCELLED})) == [
        ("end", 1, "a", Phase.CANCELLED, 10, None, "soon")]


# --- a dismissed card hides its appointment; its slot reopens only for one needed soon -------

def dismissed(i, aid, phase=U, *, earlier=()):
    """A slot as the registry records a Lock Screen dismissal today (`earlier`: ids dismissed before)."""
    return {**slot(i, aid, phase, state="dismissed_by_user"), "dismissed_day": TODAY,
            "dismissed_ids": [*earlier, aid]}


def starts(actions):
    return [(a.kind, a.slot_index, a.appointment_id, a.phase) for a in actions if a.kind == "start"]


def test_dismissed_appointment_stays_hidden_for_the_day():
    vis = [va("a", U, 10), va("b", U, 20)]
    slots = [dismissed(1, "a")]
    actions = plan(slots, vis, n=1)
    assert starts(actions) == [("start", 1, "b", U)]  # the slot reopens, but not for a
    slots = apply(slots, actions, NOW)
    # the slot now holds b; a stays hidden even with a free slot (index 2) on offer
    assert plan(slots, vis, n=2) == []
    later = NOW + timedelta(minutes=5)
    assert all(a.appointment_id != "a" for a in plan(slots, [va("a", U, 5)], n=2, now=later))
    # dismissed again later today in the same slot: both stay hidden
    again = [dismissed(1, "b", earlier=["a"])]
    assert plan(again, vis, n=2) == []
    # yesterday's dismissal no longer hides anything
    old = [{**dismissed(1, "a"), "day": "2026-11-15", "dismissed_day": "2026-11-15"}]
    assert starts(plan(old, vis, n=1)) == [("start", 1, "a", U)]


def test_dismissed_slot_reopens_for_next_appointment_inside_lead():
    assert summary(plan([dismissed(1, "a")], [va("a", U, 10), va("b", U, 25)], n=1)) == [
        ("start", 1, "b", U, 10, "start", None)]
    # the edge of the lead window counts as inside (start - lead <= now)
    assert starts(plan([dismissed(1, "a")], [va("a", U, 10), va("b", U, 30)], n=1)) == [("start", 1, "b", U)]


def test_dismissed_slot_does_not_reopen_for_appointment_outside_lead_even_if_day_open():
    # b is visible only because the device's day is open; it does not need a card yet
    assert plan([dismissed(1, "a")], [va("a", U, 10), va("b", U, 31)], n=1) == []
    assert plan([dismissed(1, "a")], [va("b", U, 45)], n=1) == []
    # it reopens once b enters the lead window
    assert starts(plan([dismissed(1, "a")], [va("b", U, 45)], n=1, now=NOW + timedelta(minutes=15))) == [
        ("start", 1, "b", U)]


def test_dismissed_slot_reopens_for_processing_appointment():
    vis = [va("p", P, -10), va("a", U, 10)]
    assert summary(plan([dismissed(1, "a")], vis, n=1)) == [("start", 1, "p", P, 10, "start", None)]


def test_three_dismissals_then_one_start_per_sweep_within_budget():
    vis = [va("d", P, -5), va("a", U, 5), va("b", U, 10), va("c", U, 15), va("e", U, 20), va("f", U, 25),
           va("g", U, 50)]
    initial = [dismissed(1, "a"), dismissed(2, "b"), dismissed(3, "c")]
    for budget, expected in ((2, [("start", 1, "d", P), ("start", 2, "e", U)]),
                             (8, [("start", 1, "d", P), ("start", 2, "e", U), ("start", 3, "f", U)])):
        slots, started, used = initial, [], 0
        for _ in range(6):  # successive sweeps; tokens not yet arrived
            actions = plan(slots, vis, n=3, starts_last_hour=used, start_budget=budget)
            assert len(starts(actions)) <= 1  # one start per sweep
            used += len(starts(actions))
            started += starts(actions)
            slots = apply(slots, actions, NOW, token=None)
        assert started == expected  # a, b, c stay hidden; g (outside the lead) never opens a dismissed slot
        assert used <= budget


def test_free_never_dismissed_index_preferred_over_dismissed_one():
    vis = [va("a", U, 5), va("b", U, 10), va("c", U, 20)]
    # index 1 dismissed, 2 held by b, 3 never used: c goes to 3
    assert starts(plan([dismissed(1, "a"), slot(2, "b", U)], vis, n=3)) == [("start", 3, "c", U)]
    # among never-dismissed free indices the lowest wins
    assert starts(plan([slot(1, "b", U), dismissed(2, "a")], vis, n=4)) == [("start", 3, "c", U)]
    # with a never-dismissed index free, an appointment outside the lead still starts there (unchanged)
    assert starts(plan([dismissed(1, "a")], [va("a", U, 5), va("g", U, 50)], n=2)) == [("start", 2, "g", U)]
    # only dismissed indices free: the lowest one
    assert starts(plan([slot(1, "b", U), dismissed(2, "a"), dismissed(3, "x")], vis, n=3)) == [
        ("start", 2, "c", U)]
