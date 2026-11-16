"""FCM transport for iOS Live Activity pushes.

Live Activity updates are delivered as FCM messages carrying an APNs
``live_activity_token`` plus the ``liveactivity`` push-type headers. The
``aps`` dict is passed as ``custom_data`` so its keys are flattened into the
encoded ``aps`` object (device-validated encoding).
"""

import asyncio
from dataclasses import dataclass
from typing import Literal, Protocol

from firebase_admin import messaging

LIVE_ACTIVITY_TOPIC = "co.plannapp.app.push-type.liveactivity"
UNREGISTERED_MARKER = "registration-token-not-registered"


@dataclass(frozen=True)
class SendResult:
    ok: bool
    invalid_token: bool
    error: str | None


class LiveActivityTransport(Protocol):
    async def send(
        self,
        *,
        fcm_token: str,
        la_token: str,
        aps: dict,
        alert: tuple[str, str] | None,
        priority: Literal[5, 10],
    ) -> SendResult: ...


def _is_unregistered(exc: Exception) -> bool:
    # Only an unregistered token may invalidate a stored token. Payload errors
    # (invalid-argument) are reported but never clear the token.
    if isinstance(exc, messaging.UnregisteredError):
        return True
    return UNREGISTERED_MARKER in str(exc)


class FcmLiveActivityTransport:
    async def send(
        self,
        *,
        fcm_token: str,
        la_token: str,
        aps: dict,
        alert: tuple[str, str] | None,
        priority: Literal[5, 10],
    ) -> SendResult:
        aps_alert = None
        if alert is not None:
            title, body = alert
            aps_alert = messaging.ApsAlert(title=title, body=body)

        msg = messaging.Message(
            token=fcm_token,
            apns=messaging.APNSConfig(
                live_activity_token=la_token,
                headers={
                    "apns-push-type": "liveactivity",
                    "apns-topic": LIVE_ACTIVITY_TOPIC,
                    "apns-priority": str(priority),
                },
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(alert=aps_alert, custom_data=aps),
                ),
            ),
        )

        try:
            await asyncio.to_thread(messaging.send, msg)
        except Exception as exc:  # FCM raises many exception types
            return SendResult(
                ok=False,
                invalid_token=_is_unregistered(exc),
                error=str(exc),
            )
        return SendResult(ok=True, invalid_token=False, error=None)


class RecordingTransport:
    """In-memory transport for tests; records every call in ``.sent``."""

    def __init__(self, fail_tokens: dict[str, SendResult] | None = None):
        self.fail_tokens = dict(fail_tokens or {})
        self.sent: list[dict] = []

    async def send(
        self,
        *,
        fcm_token: str,
        la_token: str,
        aps: dict,
        alert: tuple[str, str] | None,
        priority: Literal[5, 10],
    ) -> SendResult:
        self.sent.append({
            "fcm_token": fcm_token,
            "la_token": la_token,
            "aps": aps,
            "alert": alert,
            "priority": priority,
        })
        return self.fail_tokens.get(fcm_token, SendResult(True, False, None))
