// Loaded by app.js via script tag; paper-account rendering helpers.
async function loadAccount(){
  try{
    const [a,j]=await Promise.all([api('/api/account'),api('/api/journal')]);
    const x=a.account;$('#accountBalance').textContent=`$${num(x.balance)}`;
    $('#accountSummary').innerHTML=`<div class="metric"><small>الرصيد الحالي</small><b class="${x.realized_pnl>=0?'bull':'bear'}">$${num(x.balance)}</b><p>ابتدائي $${num(x.initial_balance)}</p></div><div class="metric"><small>الربح المحقق</small><b>$${num(x.realized_pnl)}</b><p>${num(x.return_pct)}%</p></div><div class="metric"><small>المخاطرة المفتوحة</small><b>$${num(x.open_risk_usd)}</b><p>سقف إجمالي ديناميكي، وليس عدد صفقات</p></div>`;
    renderJournal(j.journal||[]);
  }catch(e){$('#journalList').innerHTML=`<div class="error-box">${esc(e.message)}</div>`}
}
function renderJournal(rows){
  if(!rows.length){$('#journalList').innerHTML='<div class="metric"><b>السجل فارغ</b><p>أضف خطة للمراقبة؛ عند الدخول ستُسجل كل الأحداث والنتيجة.</p></div>';return}
  $('#journalList').innerHTML=rows.slice().reverse().map(j=>`<article class="trade-card"><div class="trade-head"><div><span class="eyebrow">${esc(j.audit_id||'MANUAL')} • ${esc(j.model)}</span><h3>${esc(j.symbol)} ${esc(j.side)}</h3></div><span class="status ${esc(j.status)}">${esc(statusAr[j.status]||j.status)}</span></div>
  <p class="muted">Entry ${num(j.planned_entry)} • SL ${num(j.planned_stop)} • TP1 ${num(j.planned_tp1)} • TP2 ${num(j.planned_tp2)}</p><p>${esc(j.why_entered||'خطة يدوية')}</p>
  <div class="analysis-form" style="grid-template-columns:1fr 1fr auto;margin-top:10px"><label><span>رأس مال السيناريو $</span><input id="cap-${esc(j.trade_id)}" type="number" value="${esc(j.scenario.capital)}" min="1"></label><label><span>المخاطرة %</span><input id="risk-${esc(j.trade_id)}" type="number" value="${esc(j.scenario.risk_pct)}" min="0.1" max="10" step="0.1"></label><button class="mini" onclick="saveScenario('${esc(j.trade_id)}')">احسب</button></div>
  <p class="muted">النتيجة الأصلية: ${esc(j.result?.realized_r??'مفتوحة')}R / $${num(j.result?.pnl_usd)} • السيناريو: $${num(j.scenario.hypothetical_pnl)} → رصيد $${num(j.scenario.hypothetical_balance)}</p>
  <details><summary>كل الشروط والأحداث</summary><pre style="white-space:pre-wrap;color:#9fb1c0;font-size:10px">${esc(JSON.stringify({conditions:j.conditions,result:j.result},null,2))}</pre></details></article>`).join('');
}
window.saveScenario=async id=>{try{await api('/api/journal/scenario',{method:'POST',body:JSON.stringify({trade_id:id,capital:$(`#cap-${id}`).value,risk_pct:$(`#risk-${id}`).value})});loadAccount()}catch(e){alert(e.message)}};
$('#resetAccount').onclick=async()=>{const value=prompt('الرصيد الابتدائي الجديد','100');if(!value)return;if(!confirm('سيتم مسح حساب المحاكاة وسجله. متابعة؟'))return;try{await api('/api/account/reset',{method:'POST',body:JSON.stringify({initial_balance:value})});loadAccount()}catch(e){alert(e.message)}};
