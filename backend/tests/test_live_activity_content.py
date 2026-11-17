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
    sector_icon,
    service_display,
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
    "customerDisplay", "serviceName", "staffName", "version", "appointmentId", "icon",
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
    assert relevance(Phase.UPCOMING, START, NOW) == pytest.approx(1 + 98 * (1 - 870 / 1440))  # starts 14:30
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
    assert cs(icon="hair") == json.loads(FIXTURE.read_text())


def test_no_phone_or_price_keys():
    blob = json.dumps(aps("update")).lower()
    assert "phone" not in blob and "price" not in blob and "905551112233" not in blob


def test_missing_name_mode_is_full():
    from live_activity.content import name_mode

    assert name_mode(None) == "full"
    assert display_name("test müşteri", name_mode(None)) == "Test Müşteri"


def test_unknown_name_mode_is_initials():
    from live_activity.content import name_mode

    assert [name_mode(m) for m in ("initials", "full", "hidden")] == ["initials", "full", "hidden"]
    for bogus in ("", "FULL", "Full Name", "none", 1):
        assert name_mode(bogus) == "initials"
        assert display_name("ayşe kaya", bogus) == "Ayşe K."
    assert cs(privacy_mode="everything")["customerDisplay"] == "Ayşe Y."


@pytest.mark.parametrize("sector,token", [
    ("Kuaför", "hair"),
    ("Güzellik Salonu", "beauty"),
    ("Masaj / SPA", "spa"),
    ("Diyetisyen", "diet"),
    ("Psikolog / Danışmanlık", "therapy"),
    ("Diş Klinikleri", "dental"),
    ("Diğer", "generic"),
    ("Boş", "generic"),
    ("", "generic"),
    ("kuaför", "generic"),
    ("Bilinmeyen", "generic"),
    (None, "generic"),
])
def test_sector_icon_mapping(sector, token):
    assert sector_icon(sector) == token


def test_content_state_includes_icon():
    assert cs()["icon"] == "generic"
    assert cs(icon="beauty")["icon"] == "beauty"


def _at(h, m, day=16):
    return datetime(2026, 11, day, h, m, tzinfo=TR_TZ)


SELIN_START, SELIN_END = _at(1, 10), _at(1, 55)
ECE_START, ECE_END = _at(1, 45), _at(2, 30)


def test_processing_earlier_end_has_higher_relevance():
    # Cards are pushed at different times: Ece's push is later than Selin's.
    selin = relevance(Phase.PROCESSING, SELIN_START, _at(1, 20), SELIN_END)
    ece = relevance(Phase.PROCESSING, ECE_START, _at(1, 50), ECE_END)
    assert selin > ece
    # ... and the order holds with the pushes swapped.
    selin = relevance(Phase.PROCESSING, SELIN_START, _at(1, 50), SELIN_END)
    ece = relevance(Phase.PROCESSING, ECE_START, _at(1, 46), ECE_END)
    assert selin > ece


def test_processing_relevance_independent_of_push_time():
    scores = {relevance(Phase.PROCESSING, SELIN_START, _at(1, m), SELIN_END) for m in (11, 30, 54)}
    assert len(scores) == 1


def test_processing_still_outranks_upcoming():
    worst_processing = relevance(Phase.PROCESSING, _at(23, 0), _at(23, 30), _at(23, 59))
    best_upcoming = relevance(Phase.UPCOMING, _at(0, 0), _at(0, 0))
    assert worst_processing > best_upcoming
    assert relevance(Phase.PROCESSING, START, NOW, None) == 100
    # ends at/after midnight: clamped to the floor of the range
    assert relevance(Phase.PROCESSING, _at(23, 0), _at(23, 30), _at(0, 0, day=17)) == 100
    assert relevance(Phase.PROCESSING, _at(23, 0), _at(23, 30), _at(0, 30, day=17)) == 100


def test_upcoming_earlier_start_has_higher_relevance_whenever_pushed():
    # Field case 2026-11-18: Gizem (02:35) was pushed at 02:20 and İpek (02:45) at 02:30, both
    # 15 min ahead, so the old "minutes until start" score tied and İpek showed above Gizem.
    gizem = relevance(Phase.UPCOMING, _at(2, 35), _at(2, 20))
    ipek = relevance(Phase.UPCOMING, _at(2, 45), _at(2, 30))
    assert gizem > ipek
    assert relevance(Phase.UPCOMING, _at(2, 35), _at(2, 34)) > relevance(Phase.UPCOMING, _at(2, 45), _at(2, 0))


def test_upcoming_relevance_independent_of_push_time():
    assert len({relevance(Phase.UPCOMING, _at(9, 0), _at(h, m)) for h, m in ((6, 0), (8, 30), (8, 59))}) == 1


def test_upcoming_relevance_range_stays_below_processing():
    assert relevance(Phase.UPCOMING, _at(0, 0), _at(0, 0)) == pytest.approx(99)
    assert relevance(Phase.UPCOMING, _at(23, 59), _at(23, 30)) >= 1
    assert relevance(Phase.UPCOMING, _at(0, 0), _at(0, 0)) < relevance(Phase.PROCESSING, _at(0, 0), _at(0, 0), _at(23, 59, ))


def test_terminal_relevance_unchanged():
    end = END
    assert relevance(Phase.COMPLETED, START, NOW, end) == 0
    assert relevance(Phase.CANCELLED, START, NOW, end) == 0


@pytest.mark.parametrize("full,expected", [
    ("Mustafa Bulut", "Mustafa B."),
    ("Ayşe Yılmaz", "Ayşe Y."),
    ("Elif Nur Demir", "Elif Nur D."),
    ("Mustafa", "Mustafa"),
    ("İsmail Çelik", "İsmail Ç."),
    ("ışıl özdemir", "Işıl Ö."),
    ("  ", None),
    ("", None),
    (None, None),
])
def test_staff_name_is_first_names_plus_last_initial(full, expected):
    assert cs(staff_name=full)["staffName"] == expected


def test_staff_name_shortening_leaves_customer_name_mode_alone():
    c = cs(privacy_mode="full", staff_name="Mustafa Bulut")
    assert c["customerDisplay"] == "Ayşe Kaya Yılmaz"
    assert c["staffName"] == "Mustafa B."


def _multi(*names, seqs=None):
    seqs = seqs or list(range(1, len(names) + 1))
    return {"service_name": " + ".join(names),
            "services": [{"name_snapshot": n, "sequence": q} for n, q in zip(names, seqs)]}


def test_service_display_single_service_unchanged():
    assert service_display({"service_name": "Saç Boyama"}) == "Saç Boyama"
    assert service_display({"service_name": "Saç Boyama",
                            "services": [{"name_snapshot": "Saç Boyama", "sequence": 1}]}) == "Saç Boyama"
    assert service_display({"service_name": "x" * 50}) == "x" * 40
    assert service_display({}) == ""
    assert service_display({"service_name": None, "services": None}) == ""


def test_service_display_multi_shows_first_plus_count():
    assert service_display(_multi("Manikür", "Pedikür")) == "Manikür +1"
    assert service_display(_multi("Kesim", "Fön", "Boya")) == "Kesim +2"


def test_service_display_multi_shortens_long_first_name_so_count_stays_visible():
    apt = _multi("Standart Koltuk Takımı Yıkama", "6 Adet Sandalye Yıkama")
    assert service_display(apt) == "Standart Koltuk… +1"
    apt = _multi("2 Adet Koltuk Yıkama", "B", "C", "D", "E")
    assert service_display(apt) == "2 Adet Koltuk Y… +4"
    assert service_display(_multi("Saç Kesimi Uzun", "Fön")) == "Saç Kesimi Uzun +1"  # 15 chars: kept whole


def test_service_display_multi_uses_lowest_sequence_as_first():
    assert service_display(_multi("Fön", "Kesim", seqs=[2, 1])) == "Kesim +1"


def test_service_display_multi_skips_blank_line_names():
    apt = {"service_name": "Kesim + Fön",
           "services": [{"name_snapshot": "", "sequence": 1}, {"name_snapshot": "Fön", "sequence": 2}]}
    assert service_display(apt) == "Fön +1"
    apt = {"service_name": "Kesim + Fön", "services": [{"sequence": 1}, {"sequence": 2}]}
    assert service_display(apt) == "Kesim + Fön"


def test_content_state_uses_service_display():
    apt = dict(APT, **_multi("Manikür", "Pedikür"))
    c = build_content_state(apt, Phase.UPCOMING, START, END, privacy_mode="full",
                            staff_name="M", version=1)
    assert c["serviceName"] == "Manikür +1"


def test_service_display_multi_tolerates_odd_sequence_values():
    apt = {"services": [{"name_snapshot": "Kesim", "sequence": "1"},
                        {"name_snapshot": "Fön", "sequence": None},
                        {"name_snapshot": "Boya"}]}
    assert service_display(apt).endswith(" +2")


def test_service_display_first_name_boundary_at_16_chars():
    assert service_display(_multi("a" * 16, "b")) == "a" * 16 + " +1"
    assert service_display(_multi("a" * 17, "b")) == "a" * 15 + "… +1"


def test_service_display_malformed_lines_fall_back_to_service_name():
    base = {"service_name": "Kesim + Fön"}
    for bad in ({"a": 1, "b": 2}, ["Kesim", "Fön"], [{"name_snapshot": 5}, {"name_snapshot": ["x"]}], "Kesim,Fön"):
        assert service_display(dict(base, services=bad)) == "Kesim + Fön"
