#!/usr/bin/env python3
import argparse
import json
import sys
import time
import re
from datetime import datetime
from urllib.parse import unquote

# Renk Kodları
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
DIM = "\033[2m"
RESET = "\033[0m"

# Kategoriler
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
    if not line or not line.startswith("{") or not line.endswith("}"):
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None

def extract_url(job_text):
    if not job_text:
        return "-"
    # String parçalama yerine Regex kullanımı (Daha güvenli ve hatasız)
    match = re.search(r"URL:\s*(http[^,]+)", job_text)
    if match:
        return match.group(1).strip()
    return "-"

def extract_place_name(url):
    if not url or url == "-":
        return "-"
    try:
        marker = "/maps/place/"
        if marker not in url:
            return "-"
        part = url.split(marker, 1)[1]
        raw_name = part.split("/data=", 1)[0].split("?")[0]
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
    job_text = obj.get("job", "")
    
    url = extract_url(job_text)
    place_name = extract_place_name(url)
    category = infer_category(place_name, url)

    # Terminalde düzgün görünmesi için sabit uzunlukta (pad) ayarlamalar
    time_pad = time_str.ljust(19)
    
    # URL olmayan sistem/durum mesajlarını (örn: "54 places found") daha temiz gösterme
    if place_name == "-" and message and not status:
        sys_msg = "SİSTEM BİLGİSİ".ljust(30)
        cat_pad = "Genel".ljust(15)
        return f"{color(time_pad, DIM)} | {color(sys_msg, CYAN)} | {color(cat_pad, YELLOW)} | {color('INFO'.ljust(7), YELLOW)} | {'-'.ljust(7)} | {message}"

    place_pad = place_name[:30].ljust(30) # Çok uzun isimleri kesip hizalar
    cat_pad = category[:15].ljust(15)

    if status == "success":
        status_txt = color("SUCCESS".ljust(7), GREEN)
    elif status in {"error", "failed", "fail"}:
        status_txt = color("FAILED".ljust(7), RED)
    else:
        status_txt = color((status.upper() or "INFO")[:7].ljust(7), YELLOW)

    dur_txt = f"{duration:.0f} ms" if isinstance(duration, (int, float)) else "-"
    dur_pad = dur_txt.ljust(7)

    parts = [
        color(time_pad, DIM),
        color(place_pad, CYAN),
        color(cat_pad, YELLOW),
        status_txt,
        color(dur_pad, YELLOW),
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
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            f.seek(0, 2) # Dosyanın sonuna git
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.1) # İşlemciyi yormamak için ufak bekleme
                    continue
                yield line
    except FileNotFoundError:
        print(color(f"Hata: '{path}' dosyası bulunamadı!", RED))
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stdin", action="store_true", help="stdin'den oku")
    parser.add_argument("--file", help="log dosyası")
    args = parser.parse_args()

    if not args.stdin and not args.file:
        print("Kullanım: docker logs -f gmaps-scraper 2>&1 | python3 live_log_viewer.py --stdin")
        print("     veya python3 live_log_viewer.py --file /yol/scraper.log")
        sys.exit(1)

    source = stream_stdin() if args.stdin else tail_file(args.file)

    print(color("🚀 Canlı log izleme başladı. Ctrl+C ile durdurabilirsiniz.", CYAN))
    print(color("-" * 90, DIM))

    try:
        for line in source:
            obj = parse_line(line)
            if not obj:
                continue

            formatted = format_line(obj)
            if formatted:
                print(formatted)

    except KeyboardInterrupt:
        print("\n" + color("Log izleme durduruldu.", RED))

if __name__ == "__main__":
    main()