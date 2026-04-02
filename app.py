from flask import Flask, Response, render_template_string, request, jsonify
import json
import time
from datetime import datetime
from urllib.parse import unquote
import os
import requests

app = Flask(__name__)

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
    ("Diğer", [])
]

def human_time(ts):
    if not ts: return "-"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except: return ts

def parse_line(line):
    line = line.strip()
    if not line or not (line.startswith("{") and line.endswith("}")): return None
    try: return json.loads(line)
    except: return None

def extract_url(job_text):
    if not job_text or "URL:" not in job_text: return "-"
    try: return job_text.split("URL:", 1)[1].split(", UrlParams:", 1)[0].strip()
    except: return "-"

def extract_place_name(url):
    if not url or url == "-": return "-"
    try:
        marker = "/maps/place/"
        if marker not in url: return "-"
        part = url.split(marker, 1)[1]
        raw_name = part.split("/data=", 1)[0].split("?")[0]
        name = unquote(raw_name).replace("+", " ").strip()
        return name if name else "-"
    except: return "-"

def infer_category(place_name, url):
    text = f"{place_name} {url}".lower()
    for category, keywords in CATEGORY_KEYWORDS:
        if any(keyword in text for keyword in keywords): return category
    return "Diğer"

def format_line(obj):
    component = obj.get("component", "")
    if component and component != "scrapemate": return None
    status = str(obj.get("status", "")).lower()
    url = extract_url(obj.get("job", ""))
    place_name = extract_place_name(url)
    category = infer_category(place_name, url)
    if place_name == "-": return None
    return json.dumps({"place_name": place_name, "category": category, "status": status, "time": human_time(obj.get("time"))})

def tail_file_stream(path):
    last_api_check = 0
    working_jobs = {}
    if not os.path.exists(path):
        yield f"data: {json.dumps({'error': 'Log dosyasi bekleniyor...'})}\n\n"
    
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        f.seek(0, 2)
        while True:
            now = time.time()
            if now - last_api_check > 10:
                last_api_check = now
                try:
                    r = requests.get("http://127.0.0.1:8080/api/v1/jobs", timeout=2)
                    if r.status_code == 200:
                        jobs = r.json()
                        if isinstance(jobs, dict): jobs = jobs.get('data', [])
                        current_working = {str(j['ID']): j['Name'] for j in jobs if str(j.get('Status')).lower() == 'working'}
                        for old_id, old_name in list(working_jobs.items()):
                            if old_id not in current_working:
                                yield f"data: {json.dumps({'type': 'auto_save', 'job_id': old_id, 'job_name': old_name})}\n\n"
                                del working_jobs[old_id]
                        working_jobs.update(current_working)
                except: pass

            line = f.readline()
            if not line:
                time.sleep(0.1)
                continue
            obj = parse_line(line)
            if obj:
                fmt = format_line(obj)
                if fmt: yield f"data: {fmt}\n\n"

@app.route('/save_note', methods=['POST'])
def save_note():
    d = request.json
    job_name = d.get('job_name', 'Bilinmeyen İşlem')
    job_id = d.get('job_id', 'Bilinmeyen ID') # Job ID eklendi
    total = d.get('total', 0)
    details = d.get('details', {})
    
    fname = "/var/www/player5moduleryapi/islem_ozetleri.txt"
    with open(fname, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*40}\n")
        f.write(f"OTOMATİK KAYIT: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"İşlem Adı: {job_name}\n")
        f.write(f"İşlem ID:  {job_id}\n") # Dosyaya yazdırılıyor
        f.write(f"Toplam Veri: {total}\n")
        f.write(f"{'-'*20}\n")
        f.write("Sektörel Dağılım:\n")
        for cat_name, count in details.items():
            if count > 0:
                f.write(f"  • {cat_name}: {count} adet\n")
        f.write(f"{'='*40}\n")
    return jsonify({"status": "ok"})

@app.route('/')
def index():
    html = """
    <!DOCTYPE html><html><head><meta charset="UTF-8"><title>Sektörel Canlı Pano</title>
    <style>
        body { margin: 0; padding: 20px; font-family: 'Segoe UI', sans-serif; background: #0f2027; color: #fff; background: linear-gradient(-45deg, #0f2027, #203a43, #2c5364); min-height: 100vh; }
        .top { display: flex; justify-content: space-between; align-items: center; background: rgba(255,255,255,0.05); backdrop-filter: blur(10px); padding: 15px; border-radius: 12px; margin-bottom: 20px; border: 1px solid rgba(255,255,255,0.1); }
        .board { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 15px; }
        .column { background: rgba(0,0,0,0.3); backdrop-filter: blur(10px); border-radius: 12px; height: 400px; display: flex; flex-direction: column; border: 1px solid rgba(255,255,255,0.05); }
        .column-header { padding: 12px; font-weight: bold; border-bottom: 1px solid rgba(255,255,255,0.1); text-align: center; display: flex; justify-content: center; gap: 8px; }
        .column-content { padding: 10px; overflow-y: auto; flex-grow: 1; display: flex; flex-direction: column; gap: 8px; }
        .card { background: rgba(255,255,255,0.05); border-left: 4px solid #00e676; padding: 8px; border-radius: 4px; font-size: 13px; }
        .badge { background: rgba(255,255,255,0.2); padding: 2px 8px; border-radius: 10px; font-size: 11px; }
        button { padding: 10px 20px; border-radius: 8px; border: none; cursor: pointer; font-weight: bold; transition: 0.3s; }
        #toast { visibility: hidden; position: fixed; bottom: 20px; right: 20px; background: #00e676; color: #000; padding: 15px; border-radius: 8px; font-weight: bold; z-index: 99; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }
        #toast.show { visibility: visible; animation: fadeIn 0.5s; }
        @keyframes fadeIn { from {opacity:0; transform: translateY(20px);} to {opacity:1; transform: translateY(0);} }
    </style>
    </head><body>
    <div class="top">
        <div style="font-size: 20px; font-weight: 300;">✨ Sektörel Veri Akış Panosu</div>
        <div><button onclick="toggle()" id="btn" style="background:rgba(0,123,255,0.3);color:#fff;border:1px solid rgba(0,123,255,0.5)">▶ İzlemeyi Başlat</button>
        <button onclick="clearAll()" style="background:rgba(255,193,7,0.2);color:#ffc107;margin-left:10px;border:1px solid rgba(255,193,7,0.4)">🧹 Temizle</button></div>
        <div style="font-size:18px">Canlı Toplam: <span id="gt" style="color:#00e676;font-weight:bold;font-size:24px">0</span></div>
    </div>
    <div class="board" id="board"></div>
    <div id="toast"></div>
    <script>
        const cats = ["Diyetisyen","Güzellik","Kuaför","Psikolog","Diş","Dövme","Fizyoterapi","Veteriner","Pilates/Yoga","Diğer"];
        let counts = {}; let globalCount = 0; let es;
        
        cats.forEach(c => {
            const id = c.replace(/[^a-z]/gi, ''); counts[id] = 0;
            document.getElementById('board').innerHTML += `<div class="column"><div class="column-header">${c} <span class="badge" id="b-${id}">0</span></div><div class="column-content" id="c-${id}"></div></div>`;
        });

        function clearAll() {
            globalCount = 0; document.getElementById('gt').innerText = 0;
            cats.forEach(c => { const id = c.replace(/[^a-z]/gi, ''); counts[id] = 0; document.getElementById('b-'+id).innerText = 0; document.getElementById('c-'+id).innerHTML = ''; });
        }

        function toggle() {
            const btn = document.getElementById('btn');
            if (es) { es.close(); es = null; btn.innerText = "▶ İzlemeyi Başlat"; return; }
            btn.innerText = "⏹ Durdur";
            es = new EventSource('/stream');
            es.onmessage = (e) => {
                const d = JSON.parse(e.data);
                if (d.type === 'auto_save') {
                    let sectoralDetails = {};
                    cats.forEach(c => {
                        const id = c.replace(/[^a-z]/gi, '');
                        if(counts[id] > 0) sectoralDetails[c] = counts[id];
                    });
                    // Kaydetme isteğine job_id eklendi
                    fetch('/save_note',{
                        method:'POST',
                        headers:{'Content-Type':'application/json'},
                        body:JSON.stringify({
                            job_name: d.job_name, 
                            job_id: d.job_id,
                            total: globalCount,
                            details: sectoralDetails
                        })
                    });
                    const t = document.getElementById('toast'); t.innerText = "✅ Detaylı Kaydedildi: " + d.job_name; t.className = "show";
                    setTimeout(()=>t.className="", 4500);
                    clearAll(); return;
                }
                const id = d.category.replace(/[^a-z]/gi, '');
                const col = document.getElementById('c-'+id);
                if (col && d.status === 'success') {
                    globalCount++; document.getElementById('gt').innerText = globalCount;
                    counts[id]++; document.getElementById('b-'+id).innerText = counts[id];
                    col.insertAdjacentHTML('beforeend', `<div class="card"><div style="font-weight:bold">${d.place_name}</div><div style="color:#00e676;font-size:10px">SUCCESS</div></div>`);
                    col.scrollTop = col.scrollHeight;
                }
            };
        }
    </script></body></html>
    """
    return render_template_string(html)

@app.route('/stream')
def stream():
    return Response(tail_file_stream("/var/www/player5moduleryapi/scraper.log"), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)