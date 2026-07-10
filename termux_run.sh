#!/data/data/com.termux/files/usr/bin/bash
set -e
cd "$(dirname "$0")"
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock || true
mkdir -p data
# One process owns the monitor/account/agent files; do not launch a second agent.
python web_app.py --host 0.0.0.0 --port 8787 > data/termux.log 2>&1 &
pid=$!
sleep 3
python - <<'PY'
import json, urllib.request
payload=json.dumps({}).encode()
req=urllib.request.Request('http://127.0.0.1:8787/api/agent/start',data=payload,headers={'Content-Type':'application/json'},method='POST')
with urllib.request.urlopen(req,timeout=15) as r:
 print('✅ Market agent:',json.loads(r.read()).get('agent',{}).get('thread_alive'))
PY
printf '✅ يعمل 24/7. الواجهة من الهاتف: http://127.0.0.1:8787\n'
printf 'السجل: data/termux.log | للإيقاف: kill %s\n' "$pid"
wait "$pid"
