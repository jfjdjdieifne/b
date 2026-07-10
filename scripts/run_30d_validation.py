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
summary={
 'method':'PER_SYMBOL_STRICT_WALK_FORWARD_30D',
 'portfolio_warning':'Each symbol starts with its own $100 test account; dollar PnL is not summed as one simultaneous portfolio.',
 'period':{'start':start.date().isoformat(),'end':end.date().isoformat()},
 'exchange':a.exchange,'symbols':[r.get('symbol') for r in results],
 'total_trades':sum(r.get('trade_count',0) for r in valid),
 'wins':sum(r.get('wins',0) for r in valid),'losses':sum(r.get('losses',0) for r in valid),
 'no_fills':sum(r.get('no_fills',0) for r in valid),
 'results':results,'generated_at':dual_time(),
}
with open(a.output,'w',encoding='utf-8') as f:json.dump(summary,f,ensure_ascii=False,indent=2,default=str)
print('\nWROTE',a.output,flush=True)
