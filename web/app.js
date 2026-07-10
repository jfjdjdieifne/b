const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const esc=v=>String(v??'—').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const num=v=>v==null?'—':Number(v).toLocaleString('en-US',{maximumFractionDigits:6});
const api=async(path,opt={})=>{const r=await fetch(path,{headers:{'Content-Type':'application/json'},...opt});const j=await r.json();if(!r.ok)throw new Error(j.error_ar||`HTTP ${r.status}`);return j};
let lastAnalysis=null;

function localClocks(){
  const now=new Date();
  const ny=new Intl.DateTimeFormat('ar',{timeZone:'America/New_York',dateStyle:'short',timeStyle:'medium'}).format(now);
  const dam=new Intl.DateTimeFormat('ar',{timeZone:'Asia/Damascus',dateStyle:'short',timeStyle:'medium'}).format(now);
  $('#clock').textContent=`دمشق ${dam}  |  نيويورك ${ny}`;
} localClocks();setInterval(localClocks,1000);

$$('.tab').forEach(btn=>btn.onclick=()=>{
  $$('.tab').forEach(x=>x.classList.toggle('active',x===btn));
  $$('.tab-panel').forEach(x=>x.classList.remove('active'));
  $(`#${btn.dataset.tab}Tab`).classList.add('active');
  if(btn.dataset.tab==='trades')loadTrades();
  if(btn.dataset.tab==='account')loadAccount();
  if(btn.dataset.tab==='market')loadAgent();
  if(btn.dataset.tab==='human')loadHumanComparison();
});

async function boot(){
  try{const c=await api('/api/config');$('#exchange').innerHTML=c.exchanges.map(x=>`<option value="${esc(x.key)}">${esc(x.label)}</option>`).join('');}catch(e){showError(e.message)}
  loadTrades();
} boot();

$('#analysisForm').onsubmit=async e=>{
  e.preventDefault();$('#analysisLoading').classList.remove('hidden');$('#analysisError').classList.add('hidden');$('#analysisResult').innerHTML='';$('#analyzeBtn').disabled=true;
  try{
    lastAnalysis=await api('/api/analyze',{method:'POST',body:JSON.stringify({symbol:$('#symbol').value,exchange:$('#exchange').value,execution_timeframe:$('#executionTf').value,balance:$('#balance').value,risk_pct:$('#risk').value,tp1_allocation_pct:$('#tp1Allocation').value})});
    renderAnalysis(lastAnalysis);
  }catch(err){showError(err.message)}finally{$('#analysisLoading').classList.add('hidden');$('#analyzeBtn').disabled=false}
};
function showError(msg){$('#analysisError').textContent=`تعذر إكمال العملية\n${msg}`;$('#analysisError').classList.remove('hidden')}

function renderAnalysis(a){
  const b=a.bias||{}, dec=a.decision||{}, cand=a.candidate, biasClass=b.direction==='BULLISH'?'bull':b.direction==='BEARISH'?'bear':'warn';
  const cutoff=a.data_cutoff?.close||{};
  let h=`<div class="result-top">
    <div class="metric"><small>القرار الحالي</small><b class="${dec.state==='READY_NOW'?'bull':'warn'}">${esc(dec.label_ar)}</b><p>${esc(dec.reason_ar)}</p></div>
    <div class="metric"><small>الانحياز</small><b class="${biasClass}">${esc(b.direction)}</b><p>${esc(b.explanation_ar)}</p></div>
    <div class="metric"><small>البيانات</small><b>${esc(a.exchange.toUpperCase())}</b><p>آخر إغلاق: ${esc(cutoff.new_york)}<br>دمشق: ${esc(cutoff.damascus)}</p></div>
  </div>`;
  const exp=a.expectation||{};
  h+=`<div class="decision-card"><div><span class="eyebrow">WHAT THE BOT WAITS FOR</span><h3>شو متوقع وشو ناطر؟</h3><p>${esc(exp.expects_ar||'—')}</p><p class="muted">${(exp.waits_for||[]).map(x=>'• '+esc(x)).join('<br>')}</p></div></div>`;
  if(cand){
    h+=`<div class="decision-card ${dec.state==='READY_NOW'?'ready':''}"><div><span class="eyebrow">${esc(cand.model)}</span><h3>${esc(cand.decision.label_ar)}</h3><p>${esc(cand.decision.reason_ar)}</p></div><div class="audit">${esc(a.audit_id)}</div></div>
    <div class="target-row"><div class="target"><small>الدخول</small><b>${num(cand.entry)}</b><small>${esc(cand.side)}</small></div><div class="target"><small>وقف الخسارة</small><b class="bear">${num(cand.stop_loss)}</b><small>مخاطرة $${num(cand.risk.risk_usd)}</small></div>`;
    cand.targets.forEach(t=>h+=`<div class="target"><small>${esc(t.name)} • ${esc(t.allocation_pct)}%</small><b class="bull">${num(t.price)}</b><small>${esc(t.kind)} • R ${esc(t.rr)}</small></div>`);
    if(cand.runner)h+=`<div class="target"><small>Runner • ${cand.runner.allocation_pct}%</small><b class="warn">Trailing</b><small>HL/LH بعد TP1</small></div>`;
    const life=cand.lifecycle||{};
    h+=`</div><p class="muted">تنتهي المراقبة تلقائياً: <b>${esc(life.expires_at?.new_york||'—')}</b> نيويورك | ${esc(life.max_wait_bars||'—')} شمعة كحد أقصى. وتُلغى قبلها إذا تجاوز الإغلاق SL أو وصل TP1 بلا دخول.</p><div style="margin-top:10px"><button class="ghost" id="trackCandidate">أضف للمراقبة بضغطة</button></div>`;
  }
  h+=`<div class="frames">${['1d','4h','15m',a.execution_timeframe].map(tf=>renderFrame(a.frames[tf])).join('')}</div>`;
  h+=`<div class="model-table"><div class="model-row"><b>النموذج</b><b>الحالة</b><b>السبب المختصر</b></div>${(a.entry_models||[]).map(m=>`<div class="model-row"><span>${esc(m.model)}</span><span class="${m.status==='READY'?'bull':m.status==='PENDING_SETUP'?'warn':'bear'}">${esc(m.status)}</span><span>${m.failed?.length?'فشل: '+esc(m.failed.join(', ')):m.pending?.length?'بانتظار: '+esc(m.pending.join(', ')):'كل الشروط محسومة'}</span></div>`).join('')}</div>`;
  h+=`<details class="frame-card" style="margin-top:12px"><summary><div class="frame-title"><span class="tf">AUDIT</span><div><h4>فصفصة القرار خطوة بخطوة</h4><div class="role">المدخلات، الناتج، وأساس كل تصنيف</div></div></div></summary><pre style="white-space:pre-wrap;color:#9fb1c0;font-size:10px;direction:ltr;text-align:left">${esc(JSON.stringify(a.decision_trace||[],null,2))}</pre></details>`;
  h+=`<p class="muted">جلسة نيويورك: <b>${esc(a.session.session)}</b> • نافذة تنفيذ: ${a.session.is_executable_window?'نعم':'لا'} • كل الحسابات على شموع مغلقة فقط.</p>`;
  $('#analysisResult').innerHTML=h;
  if(cand)$('#trackCandidate').onclick=trackCandidate;
}
function renderFrame(f){
  const anchor=f.bias_anchor||{};const cls=anchor.anchor_direction==='BULLISH'?'bull':anchor.anchor_direction==='BEARISH'?'bear':'warn';
  return `<details class="frame-card" ${f.timeframe==='1d'?'open':''}><summary><div class="frame-title"><span class="tf">${esc(f.timeframe)}</span><div><h4>${esc(f.role_ar)}</h4><div class="role">${esc(f.candles)} شمعة • ${esc(f.source)}</div></div></div><b class="${cls}">${esc(anchor.anchor_direction)}</b></summary>
  <ul class="facts">${(f.explanation_ar||[]).map(x=>`<li>${esc(x)}</li>`).join('')}</ul><div class="fact-grid"><div><small>آخر إغلاق</small>${num(f.last_close)}</div><div><small>FVG نشطة</small>${f.active_fvgs.bullish.length} ↑ / ${f.active_fvgs.bearish.length} ↓</div><div><small>سيولة EQ</small>${f.unswept_liquidity.equal_highs.length} H / ${f.unswept_liquidity.equal_lows.length} L</div></div></details>`
}
async function trackCandidate(){
  if(!lastAnalysis?.candidate)return;
  try{await api('/api/trades',{method:'POST',body:JSON.stringify({...lastAnalysis.candidate.tracking_payload,analysis:lastAnalysis})});$('#trackCandidate').textContent='تمت الإضافة ✓';await loadTrades();}
  catch(e){showError(e.message)}
}

const statusAr={watchlist:'مراقبة',pending_entry:'انتظار دخول',active:'مفتوحة',runner:'Runner بعد TP1',stopped:'ستوب',tp2_hit:'TP2 تحقق',closed:'مغلقة',cancelled:'ملغاة',expired:'انتهت صلاحيتها',invalidated:'أُبطلت قبل الدخول'};
async function loadTrades(){
  try{const r=await api('/api/trades');const trades=r.trades||[];$('#tradeCount').textContent=trades.filter(t=>!['closed','cancelled','stopped','tp2_hit','expired','invalidated'].includes(t.status)).length;renderTrades(trades)}catch(e){$('#tradesList').innerHTML=`<div class="error-box">${esc(e.message)}</div>`}
}
function renderTrades(trades){
  if(!trades.length){$('#tradesList').innerHTML='<div class="metric"><b>لا توجد صفقات متابعة</b><p>حلّل زوجاً واضغط «أضف للمراقبة».</p></div>';return}
  $('#tradesList').innerHTML=trades.slice().reverse().map(t=>`<article class="trade-card"><div class="trade-head"><div><span class="eyebrow">${esc(t.exchange)} • ${esc(t.timeframe)}</span><h3>${esc(t.symbol)} <span class="${t.side.includes('BUY')?'bull':'bear'}">${esc(t.side)}</span></h3></div><span class="status ${esc(t.status)}">${esc(statusAr[t.status]||t.status)}</span></div>
  <div class="target-row" style="grid-template-columns:repeat(3,1fr)"><div class="target"><small>Entry</small><b>${num(t.entry)}</b></div><div class="target"><small>SL الحالي</small><b>${num(t.current_stop_loss)}</b></div><div class="target"><small>TP1 / TP2</small><b>${num(t.tp1)} / ${num(t.tp2)}</b></div></div>
  <p class="muted">المتبقي ${esc(t.remaining_pct)}% • المحقق ${esc(t.realized_r)}R • السعر ${num(t.last_price)}</p>
  <div class="actions">${t.status==='watchlist'&&t.activation_allowed?`<button class="mini" onclick="tradeAction('${esc(t.id)}','activate')">تفعيل انتظار الدخول</button>`:t.status==='watchlist'?'<span class="muted">بانتظار READY من إعادة التحليل</span>':''}<button class="mini" onclick="tradeAction('${esc(t.id)}','refresh')">تحديث</button>${!['closed','cancelled','stopped','tp2_hit','expired','invalidated'].includes(t.status)?`<button class="mini danger" onclick="tradeAction('${esc(t.id)}','cancel')">إلغاء</button>`:''}</div>
  <div class="event-list">${(t.events||[]).slice().reverse().map(e=>`<div class="event"><b>${esc(e.type)}</b> — ${esc(e.detail_ar||e.status||'')}<br><small>${esc(e.time?.new_york||'')} | ${esc(e.time?.damascus||'')}</small></div>`).join('')}</div></article>`).join('')
}
window.tradeAction=async(id,action)=>{try{await api(`/api/trades/${id}/${action}`,{method:'POST',body:'{}'});loadTrades()}catch(e){alert(e.message)}};
$('#refreshTrades').onclick=async()=>{const b=$('#refreshTrades');b.disabled=true;b.textContent='جاري التحديث…';try{await api('/api/trades/refresh',{method:'POST',body:'{}'});await loadTrades()}catch(e){alert(e.message)}finally{b.disabled=false;b.textContent='تحديث الكل'}};
setInterval(()=>{if($('#tradesTab').classList.contains('active')){$('#refreshTrades').click()}},30000);
