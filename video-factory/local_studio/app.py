from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

import requests
from flask import Flask, jsonify, redirect, render_template_string, request, send_from_directory, session, url_for

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_DIR = ROOT / ".arena"
SECRETS_FILE = PRIVATE_DIR / "local-secrets.json"
LOG_FILE = PRIVATE_DIR / "kaggle-test.log"
AUTOBOT_LOG = PRIVATE_DIR / "autobot.log"
PASSWORD = os.environ.get("LOCAL_STUDIO_PASSWORD") or secrets.token_urlsafe(12)

app = Flask(__name__)
app.secret_key = os.environ.get("LOCAL_STUDIO_SESSION_KEY") or secrets.token_bytes(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Strict",
    SESSION_COOKIE_SECURE=False,
    MAX_CONTENT_LENGTH=64 * 1024 * 1024,
)

_process_lock = threading.Lock()
_active_process: subprocess.Popen[str] | None = None
_autobot_process: subprocess.Popen[str] | None = None


STYLE = """
:root { color-scheme: dark; --bg:#071018; --card:#0f1d28; --line:#253b4a; --text:#eef7fb;
 --muted:#9bb1bf; --cyan:#38d9c5; --green:#62e6a5; --red:#ff7383; --amber:#ffc857; }
* { box-sizing:border-box; } body { margin:0; background:radial-gradient(circle at 15% 0,#123040 0,#071018 42%);
 color:var(--text); font:15px/1.5 Inter,system-ui,sans-serif; } .wrap { max-width:1080px; margin:auto; padding:28px 18px 60px; }
h1 { margin:0 0 8px; font-size:clamp(25px,5vw,43px); } h2 { margin:0 0 16px; font-size:20px; }
p { color:var(--muted); } .hero { margin-bottom:24px; } .tag { color:var(--cyan); font-weight:800; letter-spacing:.12em; font-size:12px; }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:16px; }.card { background:rgba(15,29,40,.94);
 border:1px solid var(--line); border-radius:18px; padding:20px; box-shadow:0 14px 45px #0005; }.full { grid-column:1/-1; }
label { display:block; color:#cde0e9; font-size:13px; margin:11px 0 5px; } input { width:100%; border:1px solid #2d4657;
 background:#08131c; color:white; border-radius:10px; padding:11px 12px; outline:none; } input:focus { border-color:var(--cyan); }
button { border:0; border-radius:11px; padding:11px 15px; background:var(--cyan); color:#031310; font-weight:800; cursor:pointer; margin:7px 7px 0 0; }
button.secondary { background:#203644; color:#e8f3f8; } button.danger { background:#542530; color:#ffd8dd; } button:disabled { opacity:.45; cursor:not-allowed; }
.status { display:inline-flex; align-items:center; gap:7px; border:1px solid var(--line); border-radius:99px; padding:6px 10px; color:var(--muted); margin:3px; }
.dot { width:8px; height:8px; border-radius:50%; background:#617481; }.ok .dot { background:var(--green); box-shadow:0 0 12px var(--green); }
pre { background:#050b10; color:#cfe9f5; padding:14px; border-radius:12px; min-height:95px; max-height:300px; overflow:auto; white-space:pre-wrap; word-break:break-word; }
.notice { border-left:3px solid var(--amber); padding:10px 13px; background:#342a132e; border-radius:8px; color:#ffe4a6; margin-bottom:12px; }
.row { display:flex; gap:10px; flex-wrap:wrap; }.row > div { flex:1 1 180px; }.small { font-size:12px; color:var(--muted); }.hidden { display:none; }
.video-item { background:#0a1722; padding:10px; border-radius:10px; margin-top:8px; border:1px solid #1f3342; display:flex; justify-content:space-between; align-items:center; }
"""

LOGIN = """<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Video Factory Login</title><style>{{style}}</style></head>
<body><main class="wrap" style="max-width:520px;padding-top:10vh"><section class="card"><div class="tag">LOCAL ONLY</div><h1>Video Factory</h1><p>أدخل رمز جلسة الإعداد. لا تضع أي API key هنا.</p>
{% if error %}<div class="notice">{{error}}</div>{% endif %}<form method="post"><label>رمز الدخول</label><input name="password" type="password" autocomplete="current-password" required><button type="submit">دخول آمن</button></form></section></main></body></html>"""

PAGE = """<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Video Factory Local Studio</title><style>{{style}}</style></head>
<body><main class="wrap"><header class="hero"><div class="tag">VIDEO FACTORY · AUTONOMOUS STUDIO</div><h1>مصنع الفيديوهات التلقائي بـ Arena</h1><p>تحكم كامل بنظام توليد الفيديوهات التلقائي (Wan 2.2 AI + Hybrid Premium FFmpeg Engine).</p><div class="notice">المفاتيح تُحفظ محلياً داخل <code>.arena/</code> بصلاحيات آمنة. يمكنك تشغيل الأوتوبوت تلقائياً أو فورياً.</div></header>
<section class="grid">
<div class="card"><h2>مفاتيح خدمات AI والمونتاج</h2><form id="keysForm">
<label>Hugging Face Token (ZeroGPU Priority)</label><input name="hf_token" type="password" autocomplete="off" placeholder="اتركه فارغاً للإبقاء على المحفوظ">
<label>Gemini API Key (Script Generation)</label><input name="gemini_api_key" type="password" autocomplete="off" placeholder="اتركه فارغاً للإبقاء على المحفوظ">
<label>YouTube Data API Key</label><input name="youtube_api_key" type="password" autocomplete="off" placeholder="اتركه فارغاً للإبقاء على المحفوظ">
<label>Pexels API Key</label><input name="pexels_api_key" type="password" autocomplete="off" placeholder="اتركه فارغاً للإبقاء على المحفوظ">
<button type="submit">حفظ محلي</button></form><div id="saveMsg" class="small"></div></div>
<div class="card"><h2>حالة الخدمات</h2><div id="badges"></div><div><button onclick="testService('hf')">فحص HF ZeroGPU</button><button onclick="testService('gemini')">اختبار Gemini</button><button onclick="testService('youtube')">اختبار YouTube</button></div><pre id="testResult">لم يبدأ الاختبار بعد.</pre></div>

<div class="card full"><h2>🤖 الأوتوبوت التلقائي (Autonomous Video Factory)</h2><p>يولّد فيديوهات رأسيّة 1080x1920 تلقائياً بذكاء اصطناعي كامل، مع التركيب، الصوت، والكابشنز.</p>
<button id="autoRunBtn" onclick="runAutobot()">🚀 إطلاق توليد فيديو جديد الآن</button>
<button class="secondary" onclick="refreshAutobot()">تحديث حالة الأوتوبوت</button>
<pre id="autobotLog">لا يوجد تشغيل جارٍ الآن.</pre>
<h3>🎥 الفيديوهات المولدة (Generated Videos)</h3>
<div id="videoList" class="small">جاري التحميل...</div>
</div>

<div class="card full"><h2>حسابات Kaggle & Fallbacks</h2><p class="small">ضع Username وAccess Token للحساب. الحقول الفارغة لا تمسح القيم السابقة.</p><form id="kaggleForm"><div id="accounts"></div><button type="submit">حفظ حسابات Kaggle</button></form><div id="kaggleSaveMsg" class="small"></div></div>
<div class="card full"><h2>اختبار Kaggle الحقيقي</h2><button onclick="testService('kaggle')">فحص اعتماد Kaggle</button><button id="tickBtn" onclick="kaggleTick()">تشغيل Orchestrator Tick</button><button class="secondary" onclick="refreshRuntime()">تحديث الحالة</button><pre id="runtime">لا توجد عملية قيد التشغيل.</pre></div>
<div class="card full"><h2>حماية الأسرار</h2><button class="danger" onclick="deleteSecrets()">حذف كل الأسرار المحلية</button> <a href="/logout"><button class="secondary">تسجيل الخروج</button></a></div>
</section></main>
<script>
const accountSlots=5;
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function buildAccounts(status){const root=document.getElementById('accounts');root.innerHTML='';for(let i=1;i<=accountSlots;i++){const a=(status.accounts||[]).find(x=>x.slot===i)||{};root.insertAdjacentHTML('beforeend',`<div class="row"><div><label>اسم منطقي ${i}</label><input name="account_id_${i}" value="${esc(a.id||'account-'+i)}"></div><div><label>Kaggle Username ${i}</label><input name="username_${i}" value="${esc(a.username||'')}" autocomplete="off"></div><div><label>Kaggle Token ${i}</label><input name="token_${i}" type="password" placeholder="${a.configured?'محفوظ — اتركه فارغاً':'غير محفوظ'}" autocomplete="off"></div></div>`);}}
async function api(url, options={}){const r=await fetch(url,{...options,headers:{'Content-Type':'application/json',...(options.headers||{})}});let j={};try{j=await r.json();}catch{}if(!r.ok)throw new Error(j.error||`HTTP ${r.status}`);return j;}
async function loadStatus(){try{const s=await api('/api/status');const labels=[['HF Token',s.services.hf],['Gemini',s.services.gemini],['YouTube',s.services.youtube],['Kaggle',s.services.kaggle]];document.getElementById('badges').innerHTML=labels.map(([n,v])=>`<span class="status ${v?'ok':''}"><i class="dot"></i>${n}: ${v?'محفوظ':'غير محفوظ'}</span>`).join('');buildAccounts(s);}catch(e){document.getElementById('testResult').textContent=e.message;}}
document.getElementById('keysForm').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.target),body=Object.fromEntries(f.entries());try{await api('/api/secrets',{method:'POST',body:JSON.stringify(body)});e.target.reset();document.getElementById('saveMsg').textContent='تم الحفظ بأمان.';await loadStatus();}catch(x){document.getElementById('saveMsg').textContent=x.message;}});
document.getElementById('kaggleForm').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.target),accounts=[];for(let i=1;i<=accountSlots;i++)accounts.push({slot:i,id:f.get(`account_id_${i}`),username:f.get(`username_${i}`),token:f.get(`token_${i}`)});try{await api('/api/kaggle-accounts',{method:'POST',body:JSON.stringify({accounts})});document.getElementById('kaggleSaveMsg').textContent='تم حفظ الحسابات.';await loadStatus();}catch(x){document.getElementById('kaggleSaveMsg').textContent=x.message;}});
async function testService(name){const out=document.getElementById('testResult');out.textContent=`جاري اختبار ${name}...`;try{const j=await api('/api/test/'+name,{method:'POST',body:'{}'});out.textContent=JSON.stringify(j,null,2);}catch(e){out.textContent='فشل: '+e.message;}}
async function runAutobot(){document.getElementById('autobotLog').textContent='جاري إطلاق الأوتوبوت...';try{await api('/api/autobot/run',{method:'POST',body:'{}'});refreshAutobot();}catch(e){document.getElementById('autobotLog').textContent='خطأ: '+e.message;}}
async function refreshAutobot(){try{const j=await api('/api/autobot/status');document.getElementById('autobotLog').textContent=j.log||'لا يوجد سجل.';document.getElementById('autoRunBtn').disabled=j.running;const root=document.getElementById('videoList');if(!j.videos||!j.videos.length){root.innerHTML='لا توجد فيديوهات مولدة بعد.';return;}root.innerHTML=j.videos.map(v=>`<div class="video-item"><div><strong>${esc(v.title||v.folder)}</strong><br><span class="small">${esc(v.timestamp)} · ${Math.round((v.bytes||0)/1024/1024*10)/10} MB</span></div><div><a href="/${esc(v.path)}" target="_blank"><button class="secondary">معاينة MP4 ↗</button></a></div></div>`).join('');}catch(e){document.getElementById('autobotLog').textContent=e.message;}}
async function kaggleTick(){document.getElementById('runtime').textContent='جاري بدء الخطوة...';try{await api('/api/kaggle/tick',{method:'POST',body:'{}'});await refreshRuntime();}catch(e){document.getElementById('runtime').textContent='فشل: '+e.message;}}
async function refreshRuntime(){try{const j=await api('/api/runtime');document.getElementById('runtime').textContent=JSON.stringify(j,null,2);document.getElementById('tickBtn').disabled=j.running;}catch(e){document.getElementById('runtime').textContent=e.message;}}
async function deleteSecrets(){if(confirm('هل أنت تأكد من حذف جميع الأسرار؟')){await api('/api/secrets',{method:'DELETE'});location.reload();}}
loadStatus();refreshAutobot();refreshRuntime();
</script></body></html>"""


def authenticated() -> bool:
    return session.get("authenticated") is True


def read_secrets() -> dict[str, Any]:
    if not SECRETS_FILE.exists():
        return {}
    try:
        return json.loads(SECRETS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def write_secrets(data: dict[str, Any]) -> None:
    PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
    SECRETS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    SECRETS_FILE.chmod(0o600)


def safe_error(exc: Exception, data: dict[str, Any]) -> str:
    text = str(exc)
    for account in data.get("accounts", []):
        token = account.get("token")
        if token:
            text = text.replace(token, "***")
    for key in ("gemini_api_key", "youtube_api_key", "pexels_api_key", "hf_token"):
        value = data.get(key)
        if value:
            text = text.replace(str(value), "***")
    return text[-1200:]


def require_auth_json() -> tuple[Any, int] | None:
    if not authenticated():
        return jsonify(error="انتهت جلسة الدخول"), 401
    return None


@app.get("/")
def index():
    if not authenticated():
        return redirect(url_for("login"))
    return render_template_string(PAGE, style=STYLE)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if secrets.compare_digest(request.form.get("password", ""), PASSWORD):
            session.clear()
            session["authenticated"] = True
            return redirect(url_for("index"))
        error = "رمز الدخول غير صحيح"
    return render_template_string(LOGIN, style=STYLE, error=error)


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.get("/outputs/<path:filename>")
def serve_output(filename: str):
    return send_from_directory(ROOT / "outputs", filename)


@app.get("/api/status")
def status():
    denied = require_auth_json()
    if denied:
        return denied
    data = read_secrets()
    accounts = [
        {
            "slot": index,
            "id": account.get("id", f"account-{index}"),
            "username": account.get("username", ""),
            "configured": bool(account.get("username") and account.get("token")),
        }
        for index, account in enumerate(data.get("accounts", []), start=1)
    ]
    return jsonify(
        services={
            "hf": bool(data.get("hf_token")),
            "gemini": bool(data.get("gemini_api_key")),
            "youtube": bool(data.get("youtube_api_key")),
            "pexels": bool(data.get("pexels_api_key")),
            "kaggle": any(account["configured"] for account in accounts),
        },
        accounts=accounts,
    )


@app.post("/api/secrets")
def save_service_secrets():
    denied = require_auth_json()
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    data = read_secrets()
    for key in ("gemini_api_key", "youtube_api_key", "pexels_api_key", "hf_token"):
        value = str(payload.get(key, "")).strip()
        if value:
            data[key] = value
    write_secrets(data)
    return jsonify(ok=True)


@app.delete("/api/secrets")
def delete_service_secrets():
    denied = require_auth_json()
    if denied:
        return denied
    if SECRETS_FILE.exists():
        SECRETS_FILE.unlink()
    if LOG_FILE.exists():
        LOG_FILE.unlink()
    if AUTOBOT_LOG.exists():
        AUTOBOT_LOG.unlink()
    return jsonify(ok=True)


@app.post("/api/kaggle-accounts")
def save_kaggle_accounts():
    denied = require_auth_json()
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    incoming = payload.get("accounts")
    if not isinstance(incoming, list):
        return jsonify(error="صيغة الحسابات غير صحيحة"), 400
    data = read_secrets()
    existing = data.get("accounts", [])
    saved = []
    usernames: set[str] = set()
    for index, item in enumerate(incoming[:10], start=1):
        if not isinstance(item, dict):
            continue
        old = existing[index - 1] if index <= len(existing) else {}
        username = str(item.get("username", "")).strip()
        token = str(item.get("token", "")).strip() or str(old.get("token", "")).strip()
        account_id = str(item.get("id", "")).strip() or f"account-{index}"
        if not username and not token:
            continue
        if not username or not token:
            return jsonify(error=f"الحساب {index}: يجب وجود Username وToken معًا"), 400
        if username.lower() in usernames:
            return jsonify(error=f"Username مكرر: {username}"), 400
        usernames.add(username.lower())
        saved.append({"id": account_id, "username": username, "token": token})
    data["accounts"] = saved
    write_secrets(data)
    return jsonify(ok=True, count=len(saved))


@app.post("/api/test/<service>")
def test_service(service: str):
    denied = require_auth_json()
    if denied:
        return denied
    data = read_secrets()
    try:
        if service == "hf":
            from video_factory.providers.hf_spaces import HFSpacesWanProvider
            provider = HFSpacesWanProvider(token=data.get("hf_token"))
            return jsonify(ok=True, service="hf", health=provider.health())

        if service == "gemini":
            key = data.get("gemini_api_key")
            if not key:
                raise RuntimeError("Gemini API Key غير محفوظ")
            response = requests.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                headers={"x-goog-api-key": key},
                timeout=30,
            )
            response.raise_for_status()
            names = [item.get("name", "") for item in response.json().get("models", [])]
            preferred = [name for name in names if any(x in name.lower() for x in ("3.7-flash", "3.6-flash", "3.5-flash", "2.5-flash"))]
            return jsonify(ok=True, service="gemini", models_found=len(names), preferred_models=preferred[:12])

        if service == "youtube":
            key = data.get("youtube_api_key")
            if not key:
                raise RuntimeError("YouTube API Key غير محفوظ")
            response = requests.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={"part": "snippet,statistics", "chart": "mostPopular", "maxResults": 1, "regionCode": "US", "key": key},
                timeout=30,
            )
            response.raise_for_status()
            items = response.json().get("items", [])
            return jsonify(ok=True, service="youtube", sample_title=items[0]["snippet"]["title"] if items else None)

        return jsonify(error="خدمة غير معروفة"), 404
    except Exception as exc:
        return jsonify(error=safe_error(exc, data)), 400


@app.post("/api/autobot/run")
def run_autobot():
    global _autobot_process
    denied = require_auth_json()
    if denied:
        return denied
    data = read_secrets()
    with _process_lock:
        if _autobot_process and _autobot_process.poll() is None:
            return jsonify(error="يوجد عمل أوتوبوت قيد التشغيل بالفعل"), 409
        PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
        log_handle = AUTOBOT_LOG.open("w")
        env = os.environ.copy()
        if data.get("hf_token"):
            env["HF_TOKEN"] = data["hf_token"]
        _autobot_process = subprocess.Popen(
            [sys.executable, "-m", "video_factory.autobot", "--now"],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )
    return jsonify(ok=True, pid=_autobot_process.pid)


@app.get("/api/autobot/status")
def autobot_status():
    denied = require_auth_json()
    if denied:
        return denied
    with _process_lock:
        process = _autobot_process
        running = bool(process and process.poll() is None)
        returncode = None if not process or running else process.returncode

    log = ""
    if AUTOBOT_LOG.exists():
        try:
            log = AUTOBOT_LOG.read_text(errors="replace")[-6000:]
        except OSError:
            pass

    videos = []
    outputs_dir = ROOT / "outputs"
    if outputs_dir.exists():
        for sub in sorted(outputs_dir.glob("autobot_*"), reverse=True):
            report_file = sub / "report.json"
            if report_file.exists():
                try:
                    rep = json.loads(report_file.read_text(encoding="utf-8"))
                    videos.append({
                        "folder": sub.name,
                        "timestamp": rep.get("timestamp"),
                        "title": rep.get("title"),
                        "path": rep.get("mp4_path"),
                        "bytes": rep.get("file_size"),
                        "uploaded": rep.get("uploaded_to_youtube")
                    })
                except Exception:
                    pass

    return jsonify(running=running, returncode=returncode, log=log or "لا يوجد سجل أوتوبوت بعد.", videos=videos)


@app.post("/api/kaggle/tick")
def kaggle_tick():
    global _active_process
    denied = require_auth_json()
    if denied:
        return denied
    data = read_secrets()
    if not data.get("accounts"):
        return jsonify(error="احفظ حساب Kaggle أولًا"), 400
    with _process_lock:
        if _active_process and _active_process.poll() is None:
            return jsonify(error="توجد خطوة قيد التشغيل بالفعل"), 409
        PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
        log_handle = LOG_FILE.open("w")
        _active_process = subprocess.Popen(
            [sys.executable, "-m", "video_factory.orchestrator"],
            cwd=ROOT,
            env=os.environ.copy(),
            text=True,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )
    return jsonify(ok=True, pid=_active_process.pid)


@app.get("/api/runtime")
def runtime():
    denied = require_auth_json()
    if denied:
        return denied
    data = read_secrets()
    with _process_lock:
        process = _active_process
        running = bool(process and process.poll() is None)
        returncode = None if not process or running else process.returncode
    log = ""
    if LOG_FILE.exists():
        try:
            log = LOG_FILE.read_text(errors="replace")[-6000:]
        except OSError:
            pass
    jobs = []
    for path in sorted((ROOT / "jobs").glob("*.json")):
        try:
            item = json.loads(path.read_text())
            jobs.append(
                {
                    "id": item.get("id"),
                    "status": item.get("status"),
                    "attempt": item.get("attempt"),
                    "provider_account": item.get("provider_account"),
                    "output_path": item.get("output_path"),
                    "error": item.get("error"),
                }
            )
        except (OSError, json.JSONDecodeError):
            continue
    return jsonify(running=running, returncode=returncode, jobs=jobs, log=log or "لا يوجد سجل بعد.")


@app.errorhandler(413)
def too_large(_exc: Exception):
    return jsonify(error="الطلب أكبر من الحد المسموح"), 413


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "7860"))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
