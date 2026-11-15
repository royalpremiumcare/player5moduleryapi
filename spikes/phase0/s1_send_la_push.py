#!/usr/bin/env python3
"""PHASE 0 SPIKE (S1/S2) — throwaway. Send an ActivityKit start/update/end through FCM.

Default is DRY RUN (FCM validate_only: nothing is delivered). Pass --send to deliver.
Credentials: set GOOGLE_APPLICATION_CREDENTIALS to the Firebase service-account JSON yourself;
this script never reads a key path on its own.

Examples
  # push-to-start (iOS 17.2+), iOS 18+ also gets input-push-token
  python3 s1_send_la_push.py --event start --fcm-token <FCM> --la-token <PUSH_TO_START> \
      --appointment-id spike-1 --starts-in 300 --input-push-token --send
  # flip to processing using the per-activity token from the device log
  python3 s1_send_la_push.py --event update --phase processing --fcm-token <FCM> --la-token <ACTIVITY_TOKEN> --send
  # end as cancelled, remove immediately
  python3 s1_send_la_push.py --event end --phase cancelled --dismiss-now --fcm-token <FCM> --la-token <ACTIVITY_TOKEN> --send
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import firebase_admin
from firebase_admin import credentials, messaging
from firebase_admin._messaging_encoder import MessageEncoder

TR = ZoneInfo("Europe/Istanbul")
TOPIC = "co.plannapp.app.push-type.liveactivity"


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--event", choices=["start", "update", "end"], required=True)
    p.add_argument("--fcm-token", required=True, help="FCM registration token of the device")
    p.add_argument("--la-token", required=True, help="push-to-start token (start) or per-activity token (update/end)")
    p.add_argument("--appointment-id", default="spike-apt-1")
    p.add_argument("--phase", default="upcoming", choices=["upcoming", "processing", "completed", "cancelled", "removed"])
    p.add_argument("--starts-in", type=int, default=600, help="seconds from now until appointment start")
    p.add_argument("--start-epoch", type=float, help="override start instant (keep it stable across start/update/end)")
    p.add_argument("--duration-min", type=int, default=45)
    p.add_argument("--version", type=int, default=1)
    p.add_argument("--input-push-token", action="store_true", help="iOS 18+: ask the system to issue an update token")
    p.add_argument("--no-alert", action="store_true", help="omit alert (Apple requires one for start; test the failure)")
    p.add_argument("--priority", choices=["5", "10"], default="10")
    p.add_argument("--dismiss-now", action="store_true", help="end: dismissal-date = now (else now + 15 min)")
    p.add_argument("--relevance", type=float, default=None, help="aps relevance-score (Lock Screen order / Dynamic Island pick)")
    p.add_argument("--customer", default="Spike K.")
    p.add_argument("--service", default="Saç Kesimi")
    p.add_argument("--staff", default=None)
    p.add_argument("--send", action="store_true", help="deliver for real (default: validate only)")
    p.add_argument("--print-only", action="store_true", help="print encoded JSON and exit, no network")
    return p.parse_args()


def content_state(a, start: datetime) -> dict:
    end = start + timedelta(minutes=a.duration_min)
    return {
        "phase": a.phase,
        "startEpoch": start.timestamp(),
        "endEpoch": end.timestamp(),
        "startLabel": start.astimezone(TR).strftime("%H:%M"),
        "endLabel": end.astimezone(TR).strftime("%H:%M"),
        "customerDisplay": a.customer,
        "serviceName": a.service,
        "staffName": a.staff,
        "version": a.version,
    }


def build_message(a) -> messaging.Message:
    now = int(time.time())
    start = datetime.fromtimestamp(a.start_epoch, TR) if a.start_epoch else datetime.now(TR) + timedelta(seconds=a.starts_in)
    cs = content_state(a, start)
    aps: dict = {"timestamp": now, "event": a.event, "content-state": cs}
    if a.relevance is not None:
        aps["relevance-score"] = a.relevance
    alert = None
    if a.event == "start":
        aps["attributes-type"] = "PlannAppointmentAttributes"
        aps["attributes"] = {"appointmentId": a.appointment_id, "orgId": "spike"}
        aps["stale-date"] = int(cs["startEpoch"] if a.phase == "upcoming" else cs["endEpoch"])
        if a.input_push_token:
            aps["input-push-token"] = 1
        if not a.no_alert:
            alert = messaging.ApsAlert(title="Sıradaki randevu", body=f"Spike K. · Saç Kesimi · {cs['startLabel']}")
    elif a.event == "update":
        aps["stale-date"] = int(cs["startEpoch"] if a.phase == "upcoming" else cs["endEpoch"])
        if a.phase == "processing":
            alert = messaging.ApsAlert(title="Randevu başladı", body="Spike K. · Saç Kesimi")
    else:  # end
        aps["dismissal-date"] = now if a.dismiss_now else now + 900

    return messaging.Message(
        token=a.fcm_token,
        apns=messaging.APNSConfig(
            live_activity_token=a.la_token,
            headers={"apns-push-type": "liveactivity", "apns-topic": TOPIC, "apns-priority": a.priority},
            payload=messaging.APNSPayload(aps=messaging.Aps(alert=alert, custom_data=aps)),
        ),
    )


def main():
    a = parse_args()
    msg = build_message(a)
    encoded = MessageEncoder().default(msg)
    print(json.dumps(encoded, ensure_ascii=False, indent=2))
    size = len(json.dumps(encoded["apns"]["payload"], ensure_ascii=False).encode())
    print(f"aps payload bytes: {size}", file=sys.stderr)
    if a.print_only:
        return
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        sys.exit("Set GOOGLE_APPLICATION_CREDENTIALS to the Firebase service-account JSON first.")
    firebase_admin.initialize_app(credentials.ApplicationDefault())
    dry = not a.send
    try:
        resp = messaging.send(msg, dry_run=dry)
        print(f"{'DRY-RUN validated' if dry else 'SENT'}: {resp}")
        print("NOTE: FCM success != activity visible on device. Check the device log / Lock Screen.")
    except Exception as e:  # spike: show the raw FCM error
        print(f"FCM ERROR {type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
