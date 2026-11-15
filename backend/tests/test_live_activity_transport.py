import pytest
from firebase_admin import messaging
from firebase_admin._messaging_encoder import MessageEncoder
from firebase_admin.exceptions import FirebaseError

from live_activity.transport import (
    FcmLiveActivityTransport,
    RecordingTransport,
    SendResult,
)

FCM_TOKEN = "fcm-token-abc"
LA_TOKEN = "la-token-xyz"
APS = {"content-state": {"phase": "live", "score": 3}, "timestamp": 1700000000}


def _capture(monkeypatch, response="projects/x/messages/1"):
    sent = []

    def fake_send(msg, *args, **kwargs):
        sent.append(msg)
        return response

    monkeypatch.setattr(messaging, "send", fake_send)
    return sent


def _encode(msg):
    return MessageEncoder().default(msg)


async def test_fcm_message_headers_and_token(monkeypatch):
    sent = _capture(monkeypatch)
    transport = FcmLiveActivityTransport()

    result = await transport.send(
        fcm_token=FCM_TOKEN, la_token=LA_TOKEN, aps=APS, alert=None, priority=10,
    )

    assert result == SendResult(ok=True, invalid_token=False, error=None)
    assert len(sent) == 1
    encoded = _encode(sent[0])
    assert encoded["token"] == FCM_TOKEN
    apns = encoded["apns"]
    assert apns["live_activity_token"] == LA_TOKEN
    assert apns["headers"] == {
        "apns-push-type": "liveactivity",
        "apns-topic": "co.plannapp.app.push-type.liveactivity",
        "apns-priority": "10",
    }
    assert apns["payload"]["aps"]["content-state"] == {"phase": "live", "score": 3}
    assert apns["payload"]["aps"]["timestamp"] == 1700000000


async def test_alert_attached_only_when_given(monkeypatch):
    sent = _capture(monkeypatch)
    transport = FcmLiveActivityTransport()

    await transport.send(
        fcm_token=FCM_TOKEN, la_token=LA_TOKEN, aps=APS, alert=None, priority=5,
    )
    await transport.send(
        fcm_token=FCM_TOKEN, la_token=LA_TOKEN, aps=APS,
        alert=("Randevu", "Birazdan başlıyor"), priority=10,
    )

    no_alert = _encode(sent[0])["apns"]["payload"]["aps"]
    assert "alert" not in no_alert
    assert no_alert["content-state"] == {"phase": "live", "score": 3}

    with_alert = _encode(sent[1])["apns"]["payload"]["aps"]
    assert with_alert["alert"] == {"title": "Randevu", "body": "Birazdan başlıyor"}
    assert with_alert["content-state"] == {"phase": "live", "score": 3}


async def test_invalid_token_mapping(monkeypatch):
    transport = FcmLiveActivityTransport()

    def raise_unregistered(msg, *args, **kwargs):
        raise messaging.UnregisteredError("Requested entity was not found.")

    monkeypatch.setattr(messaging, "send", raise_unregistered)
    unregistered = await transport.send(
        fcm_token=FCM_TOKEN, la_token=LA_TOKEN, aps=APS, alert=None, priority=10,
    )
    assert unregistered.ok is False
    assert unregistered.invalid_token is True
    assert unregistered.error

    def raise_text_unregistered(msg, *args, **kwargs):
        raise RuntimeError("messaging/registration-token-not-registered: gone")

    monkeypatch.setattr(messaging, "send", raise_text_unregistered)
    by_text = await transport.send(
        fcm_token=FCM_TOKEN, la_token=LA_TOKEN, aps=APS, alert=None, priority=10,
    )
    assert by_text.ok is False
    assert by_text.invalid_token is True

    def raise_invalid_argument(msg, *args, **kwargs):
        raise FirebaseError("invalid-argument", "malformed apns payload")

    monkeypatch.setattr(messaging, "send", raise_invalid_argument)
    bad_payload = await transport.send(
        fcm_token=FCM_TOKEN, la_token=LA_TOKEN, aps=APS, alert=None, priority=10,
    )
    assert bad_payload.ok is False
    assert bad_payload.invalid_token is False
    assert bad_payload.error and "malformed apns payload" in bad_payload.error


async def test_priority_string(monkeypatch):
    sent = _capture(monkeypatch)
    transport = FcmLiveActivityTransport()

    for priority in (5, 10):
        await transport.send(
            fcm_token=FCM_TOKEN, la_token=LA_TOKEN, aps=APS, alert=None, priority=priority,
        )

    assert _encode(sent[0])["apns"]["headers"]["apns-priority"] == "5"
    assert _encode(sent[1])["apns"]["headers"]["apns-priority"] == "10"


async def test_recording_transport_records_and_fails_per_token():
    failure = SendResult(ok=False, invalid_token=True, error="unregistered")
    transport = RecordingTransport(fail_tokens={"bad-fcm": failure})

    ok = await transport.send(
        fcm_token="good-fcm", la_token=LA_TOKEN, aps=APS,
        alert=("T", "B"), priority=10,
    )
    bad = await transport.send(
        fcm_token="bad-fcm", la_token=LA_TOKEN, aps=APS, alert=None, priority=5,
    )

    assert ok == SendResult(ok=True, invalid_token=False, error=None)
    assert bad == failure
    assert transport.sent == [
        {"fcm_token": "good-fcm", "la_token": LA_TOKEN, "aps": APS,
         "alert": ("T", "B"), "priority": 10},
        {"fcm_token": "bad-fcm", "la_token": LA_TOKEN, "aps": APS,
         "alert": None, "priority": 5},
    ]
