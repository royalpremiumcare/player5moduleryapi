"""Slot planner (D12): which start/update/end pushes a device's slots need this sweep.

Pure: no DB, no network, no clock reads. The caller supplies `now` and persists the outcome.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from .content import MIN_START_STALE_SECONDS, relevance, stale_epoch
from .eligibility import VisibleAppt
from .phase import TR_TZ, Phase

USABLE_STATES = {"start_sent", "active"}
DISMISSED_STATE = "dismissed_by_user"
RESTART_AGE_SEC = 7.5 * 3600  # iOS ends an activity after 8 h
FINAL_PHASES = {Phase.COMPLETED, Phase.CANCELLED}


@dataclass
class Action:
    kind: Literal["start", "update", "end"]
    slot_index: int
    appointment_id: str | None
    phase: Phase | None
    priority: Literal[5, 10]
    alert: Literal["start", "processing"] | None
    relevance: float
    dismissal: Literal["soon", "now"] | None


def plan_device(
    *,
    slots: list[dict],
    visible: list[VisibleAppt],
    n_slots: int,
    now: datetime,
    lead: timedelta,
    starts_last_hour: int,
    start_budget: int,
    start_alert_enabled: bool,
    has_push_to_start: bool,
    content_hash: Callable[[VisibleAppt], str],
    final_phases: Mapping[str, Phase] | None = None,
) -> list[Action]:
    """Plan one sweep for one device.

    `visible` is `visible_for_user` output (processing by end, then upcoming by start).
    `lead` is the org's effective lead window: a slot the user dismissed today reopens only
    for an appointment that needs a card soon (processing, or upcoming inside the lead).
    `final_phases` maps appointment ids to their derived phase so an `end` can show
    "completed"/"cancelled"; without it an end repeats the slot's last phase.
    At most one action carries an alert, so a start (whose alert is mandatory) waits for
    a sweep without a "processing" alert.
    """
    today = now.astimezone(TR_TZ).strftime("%Y-%m-%d")
    now_epoch = now.timestamp()
    final_phases = final_phases or {}
    ordered = sorted(slots, key=lambda s: s["slot_index"])

    def dismissed_today(s: dict) -> bool:
        return s.get("state") == DISMISSED_STATE and s.get("day") == today

    # A card the user dismissed today is not reopened that day, in any slot (even one beyond a
    # lowered slot count), and it does not take one of the top-N places either. The registry keeps
    # the day's dismissed ids on the slot, so they stay hidden after the slot is reused.
    hidden = {s.get("appointment_id") for s in ordered if dismissed_today(s)}
    for s in ordered:
        if s.get("dismissed_day") == today:
            hidden.update(s.get("dismissed_ids") or ())
    top = [v for v in visible if v.id not in hidden][:n_slots]
    by_id = {v.id: v for v in top}
    visible_ids = {v.id for v in visible}
    already_processing = {s.get("appointment_id") for s in slots if s.get("phase_sent") == Phase.PROCESSING.value}

    def end(s: dict, dismissal: Literal["soon", "now"]) -> Action:
        phase = final_phases.get(s.get("appointment_id"))
        if phase not in FINAL_PHASES:
            phase = Phase(s["phase_sent"]) if s.get("phase_sent") else None
        return Action("end", s["slot_index"], s.get("appointment_id"), phase, 10, None, 0.0, dismissal)

    actions: list[Action] = []
    usable = [s for s in ordered if s.get("state") in USABLE_STATES]
    for s in usable:
        if s["slot_index"] > n_slots and s.get("update_token"):
            actions.append(end(s, "now"))  # slot count lowered

    # Stability within the top N: a held appointment keeps its slot.
    in_range = [s for s in ordered if s["slot_index"] <= n_slots]
    held: set = set()
    target: dict[int, VisibleAppt | None] = {}
    free: list[dict] = []
    for s in in_range:
        if s.get("state") not in USABLE_STATES:
            continue
        aid = s.get("appointment_id")
        if aid in by_id and aid not in held:
            held.add(aid)
            target[s["slot_index"]] = by_id[aid]
        else:
            free.append(s)
    queue = [v for v in top if v.id not in held]
    for s in free:  # a queue item is reserved for its slot even if the switch cannot be sent yet
        target[s["slot_index"]] = queue.pop(0) if queue else None

    alert_used = False
    for s in in_range:
        if s["slot_index"] not in target:
            continue
        v = target[s["slot_index"]]
        if not s.get("update_token"):
            continue  # no token yet (start_sent): retried next sweep
        if v is None:
            aid = s.get("appointment_id")
            if final_phases.get(aid) in FINAL_PHASES or aid in visible_ids:
                actions.append(end(s, "soon"))  # nothing left to show: idle or day end
            else:
                # Left the user's scope (reassigned, rescheduled out, ineligible again): spec §1.2
                # ends it immediately, with no appointment data left on the card.
                actions.append(Action("end", s["slot_index"], aid, Phase.REMOVED, 10, None, 0.0, "now"))
            continue
        started_at = s.get("started_at")
        if has_push_to_start and started_at is not None and now_epoch - started_at >= RESTART_AGE_SEC \
                and v.phase is not Phase.PROCESSING:
            actions.append(end(s, "now"))  # 8 h limit; reopened next sweep by push-to-start
            continue
        if v.id != s.get("appointment_id") or v.phase.value != s.get("phase_sent"):
            priority = 10
        elif content_hash(v) != s.get("content_hash"):
            priority = 5
        else:
            continue
        alert = None
        if start_alert_enabled and not alert_used and priority == 10 and v.phase is Phase.PROCESSING \
                and v.id not in already_processing:
            alert, alert_used = "processing", True
        actions.append(Action("update", s["slot_index"], v.id, v.phase, priority, alert,
                              float(relevance(v.phase, v.start, now, v.end)), None))

    # One start per sweep at most: its alert is mandatory and the sweep may carry only one.
    # A slot dismissed today is not closed for the day (a few accidental swipes must not stop
    # every card), but it reopens only for an appointment needed soon, which keeps a burst of
    # dismissals from spending the start budget on far-off appointments.
    # Intentional: once a reopened card has ended, its index is an ordinary free one again (its
    # dismissed appointments stay hidden; the budget and one start per sweep still apply).
    closed = {s["slot_index"] for s in ordered if s.get("state") in USABLE_STATES}
    dismissed_idx = {s["slot_index"] for s in ordered if dismissed_today(s)}
    fresh = [i for i in range(1, n_slots + 1) if i not in closed and i not in dismissed_idx]
    reopenable = [i for i in range(1, n_slots + 1) if i not in closed and i in dismissed_idx]
    if queue and (fresh or reopenable) and has_push_to_start and starts_last_hour < start_budget \
            and not alert_used:
        startable = [v for v in queue if (stale_epoch(v.phase, v.start, v.end) or 0) - now_epoch >= MIN_START_STALE_SECONDS]
        soon = [v for v in startable if v.phase is Phase.PROCESSING or v.start - lead <= now]
        if fresh and startable:
            index, v = fresh[0], startable[0]
        elif reopenable and soon:
            index, v = reopenable[0], soon[0]
        else:
            index, v = None, None
        if v is not None:
            actions.append(Action("start", index, v.id, v.phase, 10, "start",
                                  float(relevance(v.phase, v.start, now, v.end)), None))
    return actions
