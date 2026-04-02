#!/usr/bin/env python3
import argparse
import json
import sys
import time
from datetime import datetime
from urllib.parse import unquote

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
DIM = "\033[2m"
RESET = "\033[0m"

CATEGORY_KEYWORDS = [
    ("Diyetisyen", ["diyet", "beslenme", "nutrition", "diet"]),
    ("Güzellik", ["güzellik", "beauty", "estetik", "epilasyon", "lazer", "nail", "tırnak", "hair"]),
    ("Kuaför", ["kuaför", "berber", "salon", "hair"]),
    ("Psikolog", ["psikolog", "psikolojik", "terapi", "danışmanlık", "psikiyatri"]),
    ("Diş", ["diş", "dent", "ortodonti", "klinik", "poliklinik"]),
    ("Dövme", ["dövme", "tattoo", "piercing", "stüdyo"]),
    ("Fizyoterapi", ["fizyoterapi", "fizyoterapist"]),
    ("Veteriner", ["veteriner"]),
    ("Pilates/Yoga", ["pilates", "yoga"]),
]


def color(text, code):
    return f"{code}{text}{RESET}"


def human_time(ts):
    if not ts:
        return "-"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ts


def parse_line(line):
    line = line.strip()
    if not line:
        return None
    if not line.startswith("{") or not line.endswith("}"):
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def extract_url(job_text):
    if not job_text or "URL:" not in job_text:
        return "-"
    try:
        return job_text.split("URL:", 1)[1].split(", UrlParams:", 1)[0].strip()
    except Exception:
        return "-"


def extract_place_name(url):
    if not url or url == "-":
        return "-"
    try:
        marker = "/maps/place/"
        if marker not in url:
            return "-"
        part = url.split(marker, 1)[1]
        raw_name = part.split("/data=", 1)[0]
        raw_name = raw_name.split("?")[0]
        name = unquote(raw_name).replace("+", " ").strip()
        return name if name else "-"
    except Exception:
        return "-"


def infer_category(place_name, url):
    text = f"{place_name} {url}".lower()
    for category, keywords in CATEGORY_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return category
    return "Diğer"


def format_line(obj):
    component = obj.get("component", "")
    if component and component != "scrapemate":
        return None

    status = str(obj.get("status", "")).lower()
    duration = obj.get("duration")
    time_str = human_time(obj.get("time"))
    message = obj.get("message", "")
    url = extract_url(obj.get("job", ""))
    place_name = extract_place_name(url)
    category = infer_category(place_name, url)

    if status == "success":
        status_txt = color("SUCCESS", GREEN)
    elif status in {"error", "failed", "fail"}:
        status_txt = color("FAILED", RED)
    else:
        status_txt = color(status.upper() or "INFO", YELLOW)

    dur_txt = f"{duration:.0f} ms" if isinstance(duration, (int, float)) else "-"

    parts = [
        color(time_str, DIM),
        color(place_name, CYAN),
        color(category, YELLOW),
        status_txt,
        color(dur_txt, YELLOW),
    ]

    if message:
        parts.append(message)

    return " | ".join(parts)


def stream_stdin():
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        yield line


def tail_file(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        f.seek(0, 2)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.15)
                continue
            yield line


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stdin", action="store_true", help="stdin'den oku")
    parser.add_argument("--file", help="log dosyası")
    args = parser.parse_args()

    if not args.stdin and not args.file:
        print("Kullanım: docker logs -f gmaps-scraper 2>&1 | python3 live_log_viewer.py --stdin")
        sys.exit(1)

    source = stream_stdin() if args.stdin else tail_file(args.file)

    print(color("Canlı scrapemate log başladı. Ctrl+C ile durdur.", CYAN))

    try:
        for line in source:
            obj = parse_line(line)
            if not obj:
                continue

            formatted = format_line(obj)
            if formatted:
                print(formatted)

    except KeyboardInterrupt:
        print("\nDurduruldu.")


if __name__ == "__main__":
    main()