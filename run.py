# -*- coding: utf-8 -*-
"""Simple launcher.  This replaces the slow, ambiguous legacy menu."""
from __future__ import annotations

import json
import sys


def instant_analysis():
    from snapshot_analyzer import SnapshotAnalyzer
    symbol = input("الزوج [ETH/USDT]: ").strip() or "ETH/USDT"
    exchange = input("المنصة [auto/okx/binance/kucoin/gate/bybit/mexc] (Enter=auto): ").strip() or "auto"
    print("فريم التنفيذ فقط؛ 1D و4H و15m تُحلل تلقائياً.")
    tf = input("فريم التنفيذ [5m/3m/1m] (Enter=5m): ").strip() or "5m"
    balance = input("رأس المال $ (Enter=100): ").strip() or "100"
    risk = input("المخاطرة % (Enter=1): ").strip() or "1"
    print("\n⏳ جلب شموع مغلقة من منصة واحدة وتحليل كل الفريمات…")
    result = SnapshotAnalyzer().analyze(symbol, exchange, tf, float(balance), float(risk))
    if not result.get("ok"):
        print("\n❌", result.get("error_ar"))
        for report in result.get("data_fetch_reports", []):
            print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print("\n" + "=" * 72)
    print(f"🧾 {result['audit_id']} | {result['symbol']} | {result['exchange'].upper()}")
    print(f"🕒 نيويورك: {result['data_cutoff']['close']['new_york']}")
    print(f"🕒 دمشق:    {result['data_cutoff']['close']['damascus']}")
    print(f"📐 الانحياز: {result['bias']['direction']} — {result['bias']['explanation_ar']}")
    print(f"⚖️ القرار: {result['decision']['label_ar']}\n   {result['decision']['reason_ar']}")
    for name in ("1d", "4h", "15m", result["execution_timeframe"]):
        frame = result["frames"][name]
        print(f"\n[{name}] {frame['role_ar']} | {frame['bias_anchor']['anchor_direction']}")
        for fact in frame["explanation_ar"]:
            print("  •", fact)
    candidate = result.get("candidate")
    if candidate:
        print(f"\n🧩 {candidate['model']} ({candidate['model_status']})")
        print(f"   {candidate['side']} | Entry {candidate['entry']} | SL {candidate['stop_loss']}")
        for target in candidate["targets"]:
            print(f"   🎯 {target['name']}: {target['price']} ({target['allocation_pct']}%, R={target.get('rr')})")
        if candidate.get("runner"):
            print("   🏃 Runner 50%: trailing HL/LH بعد TP1 — لا يوجد TP2 رقمي قوي")
    print("\n⚠️ تعليمي فقط. Pending للمراقبة وليس أمراً مالياً.")


def main():
    while True:
        print("""
╔════════════════════════════════════════════════════════════╗
║  مرصد السوق — سريع، موثّق، شموع مغلقة فقط                ║
╚════════════════════════════════════════════════════════════╝
1. 🌐 واجهة التطبيق (الأسرع والأسلس)
2. 🔍 تحليل فوري واضح
3. 🔄 تحديث كل الصفقات المتابعة
4. 🤖 تشغيل Telegram
0. خروج
""")
        choice = input("اختر: ").strip()
        try:
            if choice == "1":
                from web_app import main as web_main
                sys.argv = [sys.argv[0], "--open"]
                return web_main()
            if choice == "2":
                instant_analysis()
            elif choice == "3":
                from trade_monitor import TradeMonitor
                report = TradeMonitor().refresh_all()
                print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
            elif choice == "4":
                from telegram_bot import TelegramBot
                return TelegramBot().run()
            elif choice == "0":
                return
            else:
                print("خيار غير صحيح")
        except Exception as exc:
            print(f"\n❌ {exc}")


if __name__ == "__main__":
    main()
