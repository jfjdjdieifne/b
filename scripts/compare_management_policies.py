#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compare exit/runner policies on the first N executed audit cases."""
from __future__ import annotations
import argparse,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from ict_math_engine import simulate_managed_trade_outcome

p=argparse.ArgumentParser()
p.add_argument('bundle',help='WFT directory or extracted ZIP directory')
p.add_argument('--count',type=int,default=5)
p.add_argument('--output',default='five_trade_policy_comparison.json')
a=p.parse_args()
base=Path(a.bundle)
case_root=base/'trade_cases' if (base/'trade_cases').is_dir() else base
cases=[]
for d in sorted(x for x in case_root.iterdir() if x.is_dir() and x.name.startswith('CASE-')):
    analysis=json.load(open(d/'01_analysis_at_signal.json',encoding='utf8'))
    old=json.load(open(d/'04_outcome_and_management.json',encoding='utf8'))
    if old.get('trade') is None:continue
    post=json.load(open(d/'03_ohlc_after_signal_execution_tf.json',encoding='utf8'))
    cases.append((d,analysis,post))
    if len(cases)>=a.count:break
policies=[
 ('80_BE',.80,'BE_THEN_STRUCTURE'),
 ('50_BE',.50,'BE_THEN_STRUCTURE'),
 ('50_STRUCTURE',.50,'STRUCTURE_ONLY'),
 ('20_STRUCTURE_BIG_RUNNER',.20,'STRUCTURE_ONLY'),
]
rows=[]
for d,analysis,candles in cases:
    c=analysis['candidate'];tp1=c['targets'][0]['price']
    second=c['targets'][1] if len(c['targets'])>1 else None
    tp2={'mode':'TARGET','price':second['price']} if second else {'mode':'OPEN_TRAILING'}
    risk=abs(c['entry']-c['stop_loss']);risk_pct=risk/c['entry']*100
    result={'case_id':d.name,'symbol':analysis['symbol'],'entry':c['entry'],'sl':c['stop_loss'],'tp1':tp1,'variants':{}}
    for name,fraction,policy in policies:
        o=simulate_managed_trade_outcome(candles,c['entry'],c['stop_loss'],tp1,tp2,
             is_short='SELL' in c['side'],tp1_fraction=fraction,post_tp1_stop_policy=policy)
        realized_r=(o.get('pnl_pct_blended',0)/risk_pct) if risk_pct else 0
        result['variants'][name]={'realized_r':round(realized_r,4),'outcome':o}
    rows.append(result)
summary={}
for name,_,_ in policies:
    vals=[r['variants'][name]['realized_r'] for r in rows]
    summary[name]={'trades':len(vals),'total_r':round(sum(vals),4),
                   'wins':sum(x>0 for x in vals),'losses':sum(x<0 for x in vals),
                   'average_r':round(sum(vals)/len(vals),4) if vals else None}
out={'source_bundle':str(base),'case_count':len(rows),'summary':summary,'rows':rows,
     'warning':'Policy comparison only; same frozen entries/stops/targets and OHLC are reused.'}
json.dump(out,open(a.output,'w',encoding='utf8'),ensure_ascii=False,indent=2,default=str)
print(json.dumps(summary,ensure_ascii=False,indent=2));print('Saved',a.output)
