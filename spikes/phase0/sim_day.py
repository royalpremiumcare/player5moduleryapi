"""PHASE 0 SPIKE — compressed 'salon morning' for the D12 slot model.

Usage: sim_day.py <tokens.json>
tokens.json: {"viewers": [{"name": "owner", "scope": "all", "fcm": "...", "slots": ["tok1", "tok2", "tok3"]},
                          {"name": "elif", "scope": "Elif", "fcm": "...", "slots": ["tok"]}]}
Every TICK seconds: derive each appointment's phase from the clock, pick the visible appointments
per viewer (processing first by end, then upcoming inside LEAD by start), keep slot assignments
stable, and push only the slots whose (appointment, phase) changed. Priority 10; relevance on every
push; at most one alerted push per viewer per tick (only for a processing transition).
"""
import argparse
import json
import sys
import threading
import time
from datetime import datetime

sys.path.insert(0, "/var/www/player5moduleryapi/backend/venv/lib/python3.10/site-packages")
sys.path.insert(0, "/tmp/claude-0/-var-www-player5moduleryapi/53f81d0e-4c9d-49e9-b05f-cc6c0967bae9/scratchpad/spike-phase0/spikes/phase0")
import firebase_admin  # noqa: E402
from firebase_admin import credentials, messaging  # noqa: E402
import s1_send_la_push as s1  # noqa: E402

TICK = 5
LEAD = 120  # compressed "30 minutes before"
T0 = time.time() + 60
APPTS = [  # (id, customer, service, staff, start offset s, duration min)
    ("a1", "Ayşe K.", "Saç Kesimi", "Elif", 0, 3),
    ("a2", "Mehmet Y.", "Sakal Tıraşı", "Can", 60, 3),
    ("a3", "Zeynep A.", "Manikür", "Ali", 120, 2),
    ("a4", "Burak T.", "Fön", "Elif", 210, 2),
    ("a5", "Selin D.", "Kaş", "Can", 270, 2),
]


def appt(a):
    i, c, sv, st, off, dur = a
    s = T0 + off
    return {"id": i, "customer": c, "service": sv, "staff": st, "start": s, "end": s + dur * 60, "dur": dur}


APPTS = [appt(a) for a in APPTS]


def phase(a, now):
    if now >= a["end"]:
        return "completed"
    return "processing" if now >= a["start"] else "upcoming"


def relevance(a, ph, now):
    if ph == "processing":
        return 100
    if ph == "upcoming":
        return max(1, round(50 - (a["start"] - now) / 60))
    return 0


def log(msg):
    print(f"{datetime.now().strftime('%H:%M:%S')} {msg}", flush=True)


def push(fcm, tok, a, ph, version, rel, alert, event="update"):
    ns = argparse.Namespace(
        event=event, fcm_token=fcm, la_token=tok, appointment_id=a["id"], phase=ph,
        starts_in=0, start_epoch=a["start"], duration_min=a["dur"], version=version,
        input_push_token=False, no_alert=not alert, alert=False, priority="10",
        dismiss_now=False, send=True, print_only=False, relevance=float(rel),
        customer=a["customer"], service=a["service"], staff=a["staff"])
    try:
        messaging.send(s1.build_message(ns))
        return "ok"
    except Exception as e:  # spike
        return f"ERR {e}"


def main():
    cfg = json.load(open(sys.argv[1]))
    firebase_admin.initialize_app(credentials.ApplicationDefault())
    state = {v["name"]: {"slots": [None] * len(v["slots"]), "sent": [None] * len(v["slots"]),
                         "ver": [1] * len(v["slots"]), "closed": [False] * len(v["slots"])}
             for v in cfg["viewers"]}
    log(f"T0 in 60 s; day ends ~{int(max(a['end'] for a in APPTS) - time.time())} s from now")
    while True:
        now = time.time()
        jobs = []
        all_done = True
        for v in cfg["viewers"]:
            st = state[v["name"]]
            mine = [a for a in APPTS if v["scope"] == "all" or a["staff"] == v["scope"]]
            remaining = [a for a in mine if phase(a, now) != "completed"]
            if remaining:
                all_done = False
            vis = [a for a in remaining if phase(a, now) == "processing" or a["start"] - now <= LEAD]
            vis.sort(key=lambda a: (0, a["end"]) if phase(a, now) == "processing" else (1, a["start"]))
            vis = vis[: len(v["slots"])]
            vis_ids = {a["id"] for a in vis}
            # stable assignment: keep slots whose appointment is still visible
            for k, cur in enumerate(st["slots"]):
                if cur and cur["id"] not in vis_ids and phase(cur, now) != "completed":
                    st["slots"][k] = None  # dropped out of view
            held = {s["id"] for s in st["slots"] if s and s["id"] in vis_ids}
            for a in vis:
                if a["id"] in held:
                    continue
                free = [k for k, s in enumerate(st["slots"]) if s is None or phase(s, now) == "completed"]
                if free:
                    st["slots"][free[0]] = a
            alerted = False
            for k, a in enumerate(st["slots"]):
                if a is None or st["closed"][k]:
                    continue
                ph = phase(a, now)
                key = (a["id"], ph)
                if st["sent"][k] == key:
                    continue
                if not remaining and ph == "completed":
                    event = "end"  # day over for this viewer: final card, then the system dismisses
                    st["closed"][k] = True
                else:
                    event = "update"
                alert = ph == "processing" and not alerted
                alerted = alerted or alert
                st["ver"][k] += 1
                st["sent"][k] = key
                jobs.append((v["name"], k, a, ph, st["ver"][k], relevance(a, ph, now), alert, event, v["fcm"], v["slots"][k]))
            # viewers whose day is over: end any slot still open that was showing a completed card
            if not remaining:
                for k, a in enumerate(st["slots"]):
                    if a is not None and not st["closed"][k]:
                        st["closed"][k] = True
                        st["ver"][k] += 1
                        jobs.append((v["name"], k, a, "completed", st["ver"][k], 0, False, "end", v["fcm"], v["slots"][k]))
        results = {}

        def run(j):
            name, k, a, ph, ver, rel, alert, event, fcm, tok = j
            results[(name, k)] = push(fcm, tok, a, ph, ver, rel, alert, event)

        threads = [threading.Thread(target=run, args=(j,)) for j in jobs]
        [t.start() for t in threads]
        [t.join() for t in threads]
        for j in jobs:
            name, k, a, ph, ver, rel, alert, event = j[:8]
            log(f"{name} slot{k + 1} -> {a['customer']} {ph} rel={rel}{' ALERT' if alert else ''}{' END' if event == 'end' else ''} [{results[(name, k)]}]")
        if all_done and all(all(s["closed"][k] or s["slots"][k] is None for k in range(len(s["slots"]))) for s in state.values()):
            log("DAY OVER")
            return
        time.sleep(TICK)


if __name__ == "__main__":
    main()
