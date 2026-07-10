#!/usr/bin/env python3
"""Run reproducible 30-day KuCoin validations and write one JSON artifact."""
from __future__ import annotations
import argparse, json, os, sys
from datetime import datetime, timedelta, timezone

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,ROOT)
from walk_forward_backtest import WalkForwardBacktester
from user_utils import dual_time

p=argparse.ArgumentParser()
p.add_argument('--end',default='2026-07-10')
p.add_argument('--days',type=int,default=30)
p.add_argument('--symbols',default='ETH/USDT,BTC/USDT,SOL/USDT,XRP/USDT,BNB/USDT')
p.add_argument('--exchange',default='kucoin')
p.add_argument('--output',default='validation_30d.json')
a=p.parse_args()
end=datetime.fromisoformat(a.end).replace(tzinfo=timezone.utc)
start=end-timedelta(days=a.days)
results=[]
for symbol in [x.strip() for x in a.symbols.split(',') if x.strip()]:
    print(f'\n=== {symbol} {start.date()} -> {end.date()} ===',flush=True)
    try:
        report=WalkForwardBacktester(reports_dir=os.path.join(ROOT,'data','backtests')).run(
            symbol=symbol,start=start.date().isoformat(),end=end.date().isoformat(),
            exchange=a.exchange,execution_timeframe='5m',initial_balance=100,
            risk_pct=1,tp1_allocation_pct=50,fee_bps=10,slippage_bps=2,
        )
        results.append(report)
        print(f"trades={report['trade_count']} W={report['wins']} L={report['losses']} final={report['final_balance']}",flush=True)
    except Exception as exc:
        results.append({'symbol':symbol,'error':str(exc)})
        print('ERROR',exc,flush=True)
valid=[r for r in results if 'error' not in r]
# Recompose all frozen trades into one $100 paper portfolio. Exits update the
# balance chronologically; concurrent entries are limited by 5% aggregate risk.
events=[]
for report in valid:
    for trade in report.get('trades',[]):
        entry_ms=trade['entry_time']['timestamp_ms']; exit_ms=trade['exit_time']['timestamp_ms']
        events.append((entry_ms,1,'ENTRY',trade)); events.append((exit_ms,0,'EXIT',trade))
events.sort(key=lambda x:(x[0],x[1]))  # exits before entries at same instant
portfolio_balance=100.0; open_risk={}; accepted={}; skipped_risk=0; portfolio_log=[]
for ts,_,kind,trade in events:
    tid=trade['id']
    if kind=='ENTRY':
        risk_budget=portfolio_balance*0.01
        if sum(open_risk.values())+risk_budget > portfolio_balance*0.05+1e-9:
            skipped_risk+=1; continue
        open_risk[tid]=risk_budget; accepted[tid]=trade
        portfolio_log.append({'type':'ENTRY','time':ts,'trade_id':tid,'symbol':trade['symbol'],'risk_usd':risk_budget,'balance':portfolio_balance})
    elif tid in accepted:
        risk_budget=open_risk.pop(tid,0); pnl=risk_budget*float(trade.get('realized_r',0))
        portfolio_balance=round(portfolio_balance+pnl,6)
        portfolio_log.append({'type':'EXIT','time':ts,'trade_id':tid,'symbol':trade['symbol'],'realized_r':trade.get('realized_r'),'pnl':pnl,'balance':portfolio_balance})
portfolio={'initial_balance':100.0,'final_balance':portfolio_balance,
           'net_pnl':round(portfolio_balance-100,6),'return_pct':round(portfolio_balance-100,3),
           'accepted_trades':len(accepted),'skipped_due_total_risk':skipped_risk,
           'max_total_open_risk_pct':5,'events':portfolio_log}
summary={
 'method':'STRICT_WALK_FORWARD_30D_WITH_COMBINED_PAPER_PORTFOLIO',
 'portfolio_warning':'Per-symbol discovery is recomposed chronologically into one $100 account with 1% trade risk and 5% max aggregate open risk.',
 'period':{'start':start.date().isoformat(),'end':end.date().isoformat()},
 'exchange':a.exchange,'symbols':[r.get('symbol') for r in results],
 'total_trades':sum(r.get('trade_count',0) for r in valid),
 'wins':sum(r.get('wins',0) for r in valid),'losses':sum(r.get('losses',0) for r in valid),
 'no_fills':sum(r.get('no_fills',0) for r in valid),
 'combined_portfolio':portfolio,
 'results':results,'generated_at':dual_time(),
}
with open(a.output,'w',encoding='utf-8') as f:json.dump(summary,f,ensure_ascii=False,indent=2,default=str)
print('\nWROTE',a.output,flush=True)
