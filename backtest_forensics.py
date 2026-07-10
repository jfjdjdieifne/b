# -*- coding: utf-8 -*-
"""Aggregate per-case evidence into a backtest forensic report."""
from __future__ import annotations
import json
from collections import Counter, defaultdict
from pathlib import Path


def generate_forensics(bundle, report=None):
    base=Path(bundle); case_root=(base/'trade_cases') if (base/'trade_cases').is_dir() else base
    if report is None:
        report=json.load(open(base/'report.json',encoding='utf8'))
    diagnoses=[]
    for d in sorted(case_root.iterdir()) if case_root.is_dir() else []:
        p=d/'04_outcome_and_management.json'
        a=d/'01_analysis_at_signal.json'
        if not p.is_file():continue
        outcome=json.load(open(p,encoding='utf8'))
        analysis=json.load(open(a,encoding='utf8')) if a.is_file() else {}
        trade=outcome.get('trade')
        diag=outcome.get('forensic_diagnosis') or {}
        diagnoses.append({
            'case_id':d.name,'symbol':analysis.get('symbol'),'model':(analysis.get('candidate') or {}).get('model'),
            'side':(analysis.get('candidate') or {}).get('side'),'decision':(analysis.get('decision') or {}).get('state'),
            'classification':diag.get('classification'),'explanation_ar':diag.get('explanation_ar'),
            'mfe_r':diag.get('mfe_r'),'mae_r':diag.get('mae_r'),'stop_hunt_suspected':diag.get('stop_hunt_suspected'),
            'realized_r':trade.get('realized_r') if trade else 0,'net_pnl':trade.get('net_pnl') if trade else 0,
            'path':str(d),
        })
    executed=[x for x in diagnoses if x['classification']!='NO_FILL_NOT_A_LOSS' and x.get('realized_r') is not None]
    cause_counts=Counter(x.get('classification') or 'UNKNOWN' for x in diagnoses)
    by_model=defaultdict(lambda:{'trades':0,'wins':0,'losses':0,'total_r':0.0})
    by_symbol=defaultdict(lambda:{'trades':0,'wins':0,'losses':0,'total_r':0.0})
    for x in executed:
        r=float(x.get('realized_r') or 0)
        for group,key in ((by_model,x.get('model') or 'UNKNOWN'),(by_symbol,x.get('symbol') or 'UNKNOWN')):
            z=group[key];z['trades']+=1;z['wins']+=r>0;z['losses']+=r<0;z['total_r']+=r
    for group in (by_model,by_symbol):
        for z in group.values():
            z['total_r']=round(z['total_r'],4);z['average_r']=round(z['total_r']/z['trades'],4) if z['trades'] else None
    sorted_r=sorted(executed,key=lambda x:float(x.get('realized_r') or 0))
    streak=max_streak=current=0
    for trade in report.get('trades',[]):
        if float(trade.get('realized_r') or 0)<0:current+=1;max_streak=max(max_streak,current)
        else:current=0
    curve=report.get('equity_curve',[]);peak=None;max_dd=0
    for point in curve:
        b=float(point.get('balance',0));peak=b if peak is None else max(peak,b)
        if peak:max_dd=max(max_dd,(peak-b)/peak*100)
    recommendations=[]
    tight=cause_counts.get('STOP_TOO_TIGHT_OR_STOP_HUNT_SUSPECTED',0)
    direction=cause_counts.get('DIRECTION_OR_TIMING_FAILED',0)
    if tight:recommendations.append(f'{tight} حالات ضربت SL ثم وصلت TP1 لاحقاً: اختبر invalidation أوسع، لا تحرّك SL اعتباطياً.')
    if direction:recommendations.append(f'{direction} حالات لم تصل TP1 بعد SL: راجع Bias/التوقيت/المنطقة قبل تعديل الستوب.')
    if report.get('win_rate') is not None and report['win_rate']<40:recommendations.append('Win rate أقل من40%؛ يلزم Average Winner كبير مثبت، لا RR مكتوبة فقط.')
    if max_dd>10:recommendations.append('Drawdown تجاوز10%؛ لا يصلح للتداول الحقيقي قبل خفض المخاطر أو تحسين الفلتر.')
    result={
        'report_id':report.get('id'),'trade_count':report.get('trade_count'),'win_rate':report.get('win_rate'),
        'return_pct':report.get('return_pct'),'max_drawdown_pct':round(max_dd,3),'max_losing_streak':max_streak,
        'cause_counts':dict(cause_counts),'by_model':dict(by_model),'by_symbol':dict(by_symbol),
        'worst_five':sorted_r[:5],'best_five':list(reversed(sorted_r[-5:])),
        'recommendations_ar':recommendations,'cases':diagnoses,
        'warning':'Forensic labels are evidence-based diagnostics, not proof of market intent.',
    }
    out=base/'forensics.json';json.dump(result,open(out,'w',encoding='utf8'),ensure_ascii=False,indent=2,default=str)
    md=[f"# Forensics {report.get('id')}","",f"- Trades: {report.get('trade_count')}",f"- Win rate: {report.get('win_rate')}%",f"- Return: {report.get('return_pct')}%",f"- Max drawdown: {round(max_dd,3)}%",f"- Max losing streak: {max_streak}","","## أسباب النتائج",'```json',json.dumps(dict(cause_counts),ensure_ascii=False,indent=2),'```',"","## توصيات"]
    md += [f"- {x}" for x in recommendations] or ['- لا توجد توصيات آلية كافية.']
    md += ["","## أسوأ خمس"]+[f"- {x['case_id']} {x['symbol']} {x['realized_r']}R — {x['classification']}" for x in sorted_r[:5]]
    md += ["","## أفضل خمس"]+[f"- {x['case_id']} {x['symbol']} {x['realized_r']}R — {x['classification']}" for x in reversed(sorted_r[-5:])]
    (base/'FORENSICS_AR.md').write_text('\n'.join(md)+'\n',encoding='utf8')
    result['saved_to']=str(out);return result
