# -*- coding: utf-8 -*-
"""Unified console: same capabilities as Desktop/Web/Telegram."""
from __future__ import annotations
import json, sys


def instant_analysis():
    from snapshot_analyzer import SnapshotAnalyzer
    symbol=input("الزوج [ETH/USDT]: ").strip() or "ETH/USDT"
    exchange=input("المنصة [auto]: ").strip() or "auto"
    tf=input("فريم التنفيذ [5m]: ").strip() or "5m"
    balance=float(input("الرصيد $ [100]: ").strip() or 100)
    risk=float(input("المخاطرة % [1]: ").strip() or 1)
    allocation=float(input("إغلاق TP1 % [50]: ").strip() or 50)
    r=SnapshotAnalyzer().analyze(symbol,exchange,tf,balance,risk,allocation)
    if not r.get("ok"):
        print("❌",r.get("error_ar"));return
    print(f"\n🧾 {r['audit_id']} | {r['symbol']} | {r['exchange'].upper()}")
    print("NY:",r['data_cutoff']['close']['new_york']);print("دمشق:",r['data_cutoff']['close']['damascus'])
    print("📐",r['bias']['direction'],"—",r['bias']['explanation_ar'])
    print("⚖️",r['decision']['label_ar'],"—",r['decision']['reason_ar'])
    print("🔭",r['expectation']['expects_ar'])
    for x in r['expectation'].get('waits_for',[]):print("  •",x)
    c=r.get('candidate')
    if c:
        print(f"{c['model']} | Entry {c['entry']} | SL {c['stop_loss']}")
        for t in c['targets']:print(f"  {t['name']} {t['price']} | إغلاق {t['allocation_pct']}% | {t.get('rr')}R")
        if c.get('runner'):print(f"  Runner {c['runner']['allocation_pct']}% — HL/LH trail")
        print("تنتهي:",c['lifecycle']['expires_at']['new_york'])


def run_backtest():
    from walk_forward_backtest import WalkForwardBacktester
    symbol=input("الزوج [ETH/USDT]: ").strip() or "ETH/USDT"
    start=input("من YYYY-MM-DD: ").strip();end=input("إلى YYYY-MM-DD: ").strip()
    exchange=input("المنصة [kucoin] (Binance قد يكون محجوباً حسب البلد): ").strip() or "kucoin"
    capital=float(input("الرصيد [100]: ").strip() or 100)
    risk=float(input("المخاطرة % [1]: ").strip() or 1)
    alloc=float(input("إغلاق TP1 % [50]: ").strip() or 50)
    checkpoint=int(input("كل كم دقيقة نفحص؟ [15] (5=مطابق أكثر للايف وأبطأ، 60=سريع): ").strip() or 15)

    def progress(event):
        stage=event.get("stage")
        if stage=="FRAME_DOWNLOAD_START":
            print(f"\n📥 [{event['frame_no']}/{event['frame_total']}] جلب {event['frame']}…",flush=True)
        elif stage=="OHLCV_CACHE_HIT":
            print(f"   ♻️ كاش محلي: {event.get('candles')} شمعة",flush=True)
        elif stage=="OHLCV_DOWNLOAD_PAGE":
            print(f"   صفحة {event.get('page')} | المجموع الخام {event.get('candles_total')}",flush=True)
        elif stage=="FRAME_DOWNLOAD_DONE":
            print(f"   ✅ {event['frame']}: {event['candles']} شمعة مغلقة",flush=True)
        elif stage=="ANALYSIS_START":
            print(f"\n🧪 بدء {event['eligible_checkpoints']} نقطة Walk-forward…",flush=True)
        elif stage=="ANALYSIS_PROGRESS":
            print(f"   {event['percent']:5.1f}% | {event['completed']}/{event['total']} | "
                  f"صفقات={event['trades']} إشارات={event['signals']} | ETA≈{event.get('eta_seconds')}s",flush=True)
        elif stage=="BACKTEST_DONE":
            print(f"\n✅ اكتمل: {event['trades']} صفقة | {event['wins']} ربح / {event['losses']} خسارة",flush=True)

    print("⏳ تنزيل/تحميل OHLC ثم Walk-forward؛ سترى التقدم الآن.")
    r=WalkForwardBacktester().run(
        symbol,start,end,exchange=exchange,initial_balance=capital,risk_pct=risk,
        tp1_allocation_pct=alloc,checkpoint_minutes=checkpoint,progress_callback=progress,
    )
    print(f"{r['id']} | صفقات {r['trade_count']} | {r['wins']}W/{r['losses']}L | "
          f"${r['initial_balance']} → ${r['final_balance']} ({r['return_pct']}%) | {r['runtime_seconds']}s")
    if r.get('zero_trade_diagnosis'):
        print("🚨 تشخيص صفر صفقات:",json.dumps(r['zero_trade_diagnosis'],ensure_ascii=False,indent=2))
    print("أكثر أسباب الرفض:",json.dumps(r.get('top_rejection_reasons',{}),ensure_ascii=False,indent=2))
    print("حُفظ:",r['saved_to'])


def account_view():
    from paper_account import PaperAccount
    from trade_monitor import TradeMonitor
    p=PaperAccount();m=TradeMonitor();p.reconcile(m.list())
    print(json.dumps(p.snapshot(),ensure_ascii=False,indent=2,default=str))


def main():
    while True:
        print("""
╔════════════════════════════════════════════════════════════╗
║  مرصد السوق — نفس وظائف الكمبيوتر والويب وتلغرام          ║
╚════════════════════════════════════════════════════════════╝
1. 🖥️  تطبيق الكمبيوتر (نافذة بلا رابط)
2. 🌐 واجهة الويب/الهاتف
3. 🔍 تحليل فوري
4. 📡 تحليل السوق الورقي 24/7
5. 🧪 اختبار فترة Walk-forward بلا غش
6. 💵 حساب المحاكاة $100 واللوغ
7. 🔄 تحديث الصفقات
8. 🤖 Telegram
0. خروج
""")
        c=input("اختر: ").strip()
        try:
            if c=="1":
                from desktop_app import main as f;return f()
            if c=="2":
                from web_app import main as f;sys.argv=[sys.argv[0],"--open"];return f()
            if c=="3":instant_analysis()
            elif c=="4":
                from market_agent import main as f;return f()
            elif c=="5":run_backtest()
            elif c=="6":account_view()
            elif c=="7":
                from trade_monitor import TradeMonitor
                from paper_account import PaperAccount
                m=TradeMonitor();print(json.dumps(m.refresh_all(),ensure_ascii=False,indent=2,default=str));PaperAccount().reconcile(m.list())
            elif c=="8":
                from telegram_bot import TelegramBot;return TelegramBot().run()
            elif c=="0":return
            else:print("خيار غير صحيح")
        except Exception as exc:print("❌",exc)

if __name__=="__main__":main()
