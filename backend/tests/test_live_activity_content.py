import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from live_activity.content import (
    PayloadTooLarge,
    StaleStartRejected,
    build_aps,
    build_content_state,
    display_name,
    format_alert,
    relevance,
    stale_epoch,
)
from live_activity.phase import TR_TZ, Phase

NOW = datetime(2026, 11, 16, 14, 0, tzinfo=TR_TZ)
START = datetime(2026, 11, 16, 14, 30, tzinfo=TR_TZ)
END = START + timedelta(minutes=45)
APT = {
    "id": "apt-123",
    "customer_name": "ayşe kaya yılmaz",
    "service_name": "Saç Boyama",
    "appointment_time": "14:30",
    "phone": "+905551112233",
    "price": 900,
}
KEYS = {
    "phase", "startEpoch", "endEpoch", "startLabel", "endLabel",
    "customerDisplay", "serviceName", "staffName", "version", "appointmentId",
}
FIXTURE = Path(__file__).parent / "contracts" / "live_activity_content_state.json"


def cs(**kw):
    args = dict(privacy_mode="initials", staff_name="Mehmet", version=3)
    args.update(kw)
    return build_content_state(APT, Phase.UPCOMING, START, END, **args)


def aps(event="update", **kw):
    args = dict(
        now_epoch=int(NOW.timestamp()), relevance=48.0,
        stale_epoch=int(START.timestamp()), dismissal_epoch=None,
        slot_id=None, org_id=None, input_push_token=False,
    )
    args.update(kw)
    return build_aps(event, cs(), **args)


def test_display_name_modes():
    assert display_name("ayşe kaya yılmaz", "initials") == "Ayşe Y."
    assert display_name("  ışıl   inci  ", "initials") == "Işıl İ."
    assert display_name("ışıl inci", "full") == "Işıl İnci"
    assert display_name("ayşe", "initials") == "Ayşe"
    assert display_name("ayşe kaya", "hidden") is None
    assert display_name("", "initials") is None
    assert display_name(None, "full") is None


def test_relevance_values():
    assert relevance(Phase.PROCESSING, START, NOW) == 100
    assert relevance(Phase.UPCOMING, START, NOW + timedelta(minutes=10)) == 48
    assert relevance(Phase.UPCOMING, START + timedelta(minutes=900), NOW) == 1
    assert relevance(Phase.COMPLETED, START, NOW) == 0


def test_content_keys_exact():
    assert set(cs()) == KEYS


def test_labels_are_stored_strings():
    c = cs()
    assert c["startLabel"] == "14:30" and c["endLabel"] == "15:15"
    assert c["startEpoch"] == float(START.timestamp())
    assert isinstance(c["endEpoch"], float)
    assert c["phase"] == "upcoming" and c["appointmentId"] == "apt-123"


def test_start_has_slot_attributes_no_inline_alert():
    a = aps("start", slot_id="s1", org_id="o1", input_push_token=True,
            now_epoch=int(NOW.timestamp()) - 3600)
    assert a["attributes-type"] == "PlannAppointmentAttributes"
    assert a["attributes"] == {"slotId": "s1", "orgId": "o1"}
    assert "alert" not in a
    assert a["input-push-token"] == 1


def test_format_alert_copy_and_hidden_mode():
    c = cs()
    assert format_alert("start", c) == ("Sıradaki randevu", "Ayşe Y. · Saç Boyama · 14:30")
    assert format_alert("processing", c) == ("Randevu başladı", "Ayşe Y. · Saç Boyama")
    h = cs(privacy_mode="hidden")
    assert format_alert("start", h) == ("Sıradaki randevu", "Saç Boyama · 14:30")
    assert format_alert("processing", h) == ("Randevu başladı", "Saç Boyama")


def test_every_event_has_relevance_score():
    for ev in ("start", "update", "end"):
        a = aps(ev, now_epoch=int(NOW.timestamp()) - 3600, slot_id="s", org_id="o")
        assert a["relevance-score"] == 48.0
        assert a["event"] == ev and a["content-state"]["appointmentId"] == "apt-123"
        assert a["timestamp"] == int(NOW.timestamp()) - 3600


def test_start_with_past_stale_rejected():
    with pytest.raises(StaleStartRejected):
        aps("start", stale_epoch=int(NOW.timestamp()) + 59)
    with pytest.raises(StaleStartRejected):
        aps("start", stale_epoch=None)
    assert aps("start", stale_epoch=int(NOW.timestamp()) + 60)["stale-date"]
    # non-start events are not rejected
    assert aps("update", stale_epoch=int(NOW.timestamp()) - 5)["stale-date"]


def test_stale_epoch_by_phase():
    assert stale_epoch(Phase.UPCOMING, START, END) == int(START.timestamp())
    assert stale_epoch(Phase.PROCESSING, START, END) == int(END.timestamp())
    assert stale_epoch(Phase.COMPLETED, START, END) is None
    assert "stale-date" not in aps("update", stale_epoch=None)


def test_end_has_dismissal_date():
    a = aps("end", dismissal_epoch=1234)
    assert a["dismissal-date"] == 1234
    assert "dismissal-date" not in aps("update")
    assert "attributes" not in a and "input-push-token" not in a


def test_input_push_token_only_when_flag():
    assert "input-push-token" not in aps("start", slot_id="s", org_id="o",
                                         now_epoch=0, stale_epoch=100)
    assert "input-push-token" not in aps("update", input_push_token=True)


def test_payload_under_4kb_with_long_service():
    apt = dict(APT, service_name="x" * 5000)
    c = build_content_state(apt, Phase.UPCOMING, START, END, privacy_mode="full",
                            staff_name="M", version=1)
    assert len(c["serviceName"]) == 40
    a = build_aps("update", c, now_epoch=0, relevance=1.0, stale_epoch=None,
                  dismissal_epoch=None, slot_id=None, org_id=None, input_push_token=False)
    assert len(json.dumps(a, ensure_ascii=False).encode()) < 4096


def test_oversize_payload_raises():
    c = build_content_state(APT, Phase.UPCOMING, START, END, privacy_mode="full",
                            staff_name="s" * 5000, version=1)
    with pytest.raises(PayloadTooLarge):
        build_aps("update", c, now_epoch=0, relevance=1.0, stale_epoch=None,
                  dismissal_epoch=None, slot_id=None, org_id=None, input_push_token=False)


def test_matches_golden_fixture():
    assert cs() == json.loads(FIXTURE.read_text())


def test_no_phone_or_price_keys():
    blob = json.dumps(aps("update")).lower()
    assert "phone" not in blob and "price" not in blob and "905551112233" not in blob
