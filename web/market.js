async function loadAgent(){
  try{const r=await api('/api/agent');renderAgent(r.agent)}catch(e){$('#agentResults').innerHTML=`<div class="error-box">${esc(e.message)}</div>`}
}
function renderAgent(a){
  const alive=a.thread_alive;$('#agentBadge').textContent=alive?'يعمل الآن':'متوقف';$('#agentBadge').className=`status ${alive?'runner':''}`;
  $('#agentSummary').innerHTML=`<div class="metric"><small>الدورة</small><b>${esc(a.cycle||0)}</b><p>آخر دورة ${esc(a.last_cycle?.new_york||'لم تبدأ')}</p></div><div class="metric"><small>الكون الحالي</small><b>${esc((a.symbols||[]).length)} زوج</b><p>${esc(a.last_universe_basis||'سيُرتب حسب سيولة 24h')}</p></div><div class="metric"><small>الدورة التالية</small><b>${alive?'تلقائياً':'—'}</b><p>${esc(a.next_cycle_at?.new_york||'')}</p></div>`;
  const rows=a.last_results||[];$('#agentResults').innerHTML=`<div class="model-row"><b>الزوج</b><b>القرار</b><b>السبب</b></div>${rows.map(x=>`<div class="model-row"><span>${esc(x.symbol)}</span><span>${esc(x.decision||x.error||'فشل')}</span><span>${esc(x.model||x.reason||'')}</span></div>`).join('')}`;
}
$('#startAgent').onclick=async()=>{try{const r=await api('/api/agent/start',{method:'POST',body:JSON.stringify({exchange:$('#agentExchange').value,execution_timeframe:$('#agentTf').value,universe_size:$('#agentUniverse').value,scan_interval_seconds:Number($('#agentInterval').value)*60,risk_pct:$('#agentRisk').value,tp1_allocation_pct:$('#agentAllocation').value})});renderAgent(r.agent)}catch(e){alert(e.message)}};
$('#stopAgent').onclick=async()=>{try{const r=await api('/api/agent/stop',{method:'POST',body:'{}'});renderAgent(r.agent)}catch(e){alert(e.message)}};
$('#refreshAgent').onclick=loadAgent;
