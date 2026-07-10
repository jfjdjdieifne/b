# -*- coding: utf-8 -*-
"""
Trading Bot - Main CLI Interface
Version 3.1 with Backtesting & Multi-API
"""
import os
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)

import logging
import json
import time
from brain_core import BrainCore
from openrouter_client import OpenRouterClient
from signal_tracker import SignalTracker
from backtest_engine import BacktestEngine
from config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-15s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)


def _format_providers_summary(status):
    """يبني سطر مختصر لحالة كل مزودي الـ AI (متوافق مع نظام Multi-Provider)"""
    parts = []
    for pname, pinfo in status.get("providers", {}).items():
        parts.append(f"{pname}:{pinfo['active_keys']}/{pinfo['total_keys']}")
    return " | ".join(parts) if parts else "لا يوجد مزود مفعّل"


def _print_wrapped(text, width=58, prefix="║    "):
    """يطبع نص طويل مع التفاف الأسطر داخل الصندوق"""
    words = str(text).split()
    line = prefix
    for word in words:
        if len(line) + len(word) > width:
            print(line)
            line = prefix + word + " "
        else:
            line += word + " "
    if line.strip() != "║":
        print(line)


def _display_target(value):
    """Render numeric or structured TP fields without dumping a dict."""
    if isinstance(value, dict):
        if value.get("mode") == "OPEN_TRAILING":
            return "OPEN / TRAILING (لا رقم موثّق)"
        price = value.get("price", value.get("value"))
        kind = value.get("kind")
        source = value.get("source")
        suffix = " | ".join(str(x) for x in (kind, source) if x)
        return f"{price}" + (f" ({suffix})" if suffix else "")
    return value if value not in (None, 0, "") else "غير موجود"


def print_analysis(result):
    """عرض نتائج التحليل"""

    if "error" in result:
        print(f"\n❌ {result['error']}")
        return

    print("\n" + "╔" + "═" * 58 + "╗")
    print(f"║  📊 تحليل {result.get('symbol', 'N/A')} - تنفيذ {result.get('timeframe', 'N/A')}")
    print("╠" + "═" * 58 + "╣")
    if result.get("exchange"):
        print(f"║  🏦 مصدر الشموع: {str(result['exchange']).upper()} | مغلقة فقط: {result.get('closed_candles_only')}")
    cutoff = (result.get("data_cutoff") or {}).get("close", {})
    if cutoff:
        print(f"║  🕒 NY: {cutoff.get('new_york')}")
        print(f"║  🕒 دمشق: {cutoff.get('damascus')}")

    ai = result.get("ai_analysis", {})

    if not isinstance(ai, dict):
        print(f"║  AI Response: {str(ai)[:200]}")
        print("╚" + "═" * 58 + "╝")
        return

    signal = ai.get("signal", "N/A")
    # ⚠️ BUY_LIMIT/SELL_LIMIT (أوامر معلقة - حل جذري
    # بطلب صريح من المستخدم: اتجاه ومنطقة دخول
    # معروفة، لكن السعر لم يصلها بعد) - رمز
    # مختلف (⬜️⏳) يوضح أنها أمر معلق لا تنفيذاً فورياً.
    emoji = {
        "BUY": "🟢", "SELL": "🔴", "HOLD": "🟡",
        "BUY_LIMIT": "🟩⏳", "SELL_LIMIT": "🟥⏳",
    }.get(signal, "⚪")
    print(f"║  {emoji} Signal: {signal}")
    if ai.get("setup_status") == "WAIT_CONFIRMATION":
        print("║  ⏳ الحالة: مراقبة فقط — الشروط Pending وليست Limit Order")
        if ai.get("reason"):
            _print_wrapped(ai["reason"])
    print(f"║  📐 Bias: {ai.get('bias', 'N/A')}")
    print(f"║  🎯 Confidence: {ai.get('confidence', 'N/A')}%")
    print(f"║  📊 Market: {ai.get('market_regime', 'N/A')}")
    print(f"║  🌍 Macro: {ai.get('macro_bias', 'N/A')}")

    # ═══ NARRATIVE + ARCHETYPE (طبقة الفهم الشامل - لا تُخفى أبداً) ═══
    narrative = ai.get("narrative", "")
    if narrative:
        print("║  " + "─" * 40)
        print("║  📖 Narrative (القصة الكاملة):")
        _print_wrapped(narrative)

    archetype = ai.get("archetype", "")
    if archetype:
        print("║  " + "─" * 40)
        print("║  🧩 Archetype (النمط المشابه):")
        _print_wrapped(archetype)

    # ═══ BOS Reconciliation (قسم 24 - فحص التناقض الإلزامي) ═══
    # يعرض صراحة هل القرار متوافق مع آخر BOS مؤكد أو متعارض معه، ولماذا.
    # هذا الحقل بالذات هو الإصلاح المباشر لخطأ حقيقي مُكتشف: تصنيف شمعة
    # اندفاع صاعدة كـ"Bearish OB" وإصدار SELL بعكس اتجاه انعكاس حقيقي.
    bos_check = ai.get("bos_reconciliation", "")
    if bos_check:
        print("║  " + "─" * 40)
        print("║  🔀 BOS Reconciliation (فحص تناقض الهيكل):")
        _print_wrapped(bos_check)

    if signal in ["BUY", "SELL", "BUY_LIMIT", "SELL_LIMIT"]:
        print("║  " + "─" * 40)
        if signal in ("BUY_LIMIT", "SELL_LIMIT"):
            print("║  ⏳ أمر معلق (Limit Order) - السعر لم يصل منطقة الدخول بعد - حط أوردر عند هذا السعر وانتظر")
        print(f"║  💰 Entry:     ${ai.get('entry', 'N/A')}")
        print(f"║  🛑 Stop Loss: ${ai.get('stop_loss', 'N/A')}")
        print(f"║  🎯 TP1 (50%): {_display_target(ai.get('tp1') or ai.get('tp'))}")
        print(f"║  🎯 TP2/Runner (50%): {_display_target(ai.get('tp2'))}")
        if ai.get('tp3'):
            print(f"║  🎯 TP3:       {_display_target(ai.get('tp3'))}")
        print(f"║  📏 R:R:       {ai.get('rr', 'N/A')}")

    reasoning = ai.get("reasoning", "")
    if reasoning:
        print("║  " + "─" * 40)
        print("║  💭 Mechanical Verification (تحقق رقمي):")
        _print_wrapped(reasoning)

    # ═══ تقرير التحقق الآلي (Verification Layer) ═══
    verification = result.get("verification")
    if verification:
        print("║  " + "─" * 40)
        # ⚠️ إصلاح عرض حقيقي (2026-07-03): بعد إصلاح verification_layer.py،
        # score_pct يمكن يكون None صراحة (لا مفقود) لما يكون التحقق
        # غير قابل للتطبيق أصلاً (مثلاً HOLD مبكر عند Gate) - `.get('score_pct',
        # 'N/A')` لا يلتقط هذه الحالة (المفتاح موجود بقيمة None، ليس
        # مفقوداً)، فكان يطبع مربكاً "None%" بدل رسالة واضحة.
        _score = verification.get("score_pct")
        _score_display = f"{_score}%" if _score is not None else "N/A (لا يوجد ادعاء سعري للتحقق منه - طبيعي لـHOLD/Gate)"
        print(f"║  🔍 Verification Score: {_score_display} "
              f"({verification.get('verified', 0)}/{verification.get('total_claims', 0)} claims verified)")
        for issue in verification.get("issues", [])[:5]:
            print(f"║    ⚠️ {issue}")

    struct = ai.get("structure_analysis", "")
    if struct:
        print(f"║  📐 Structure: {str(struct)[:80]}")

    smc = ai.get("smc_zones_found", {})
    if isinstance(smc, dict) and any(smc.values()):
        print("║  " + "─" * 40)
        print("║  🏦 SMC Zones Found:")
        for key, vals in smc.items():
            if vals:
                if isinstance(vals, list):
                    for v in vals[:2]:
                        print(f"║    • {key}: {str(v)[:50]}")
                else:
                    print(f"║    • {key}: {str(vals)[:50]}")

    conf = ai.get("confluence_factors", [])
    if conf and isinstance(conf, list):
        print("║  " + "─" * 40)
        print(f"║  🔗 Confluence ({len(conf)} factors):")
        for c in conf[:6]:
            print(f"║    ✅ {c}")

    levels = ai.get("key_levels", [])
    if levels:
        if isinstance(levels, list):
            print(f"║  📍 Key Levels: {levels[:5]}")
        else:
            print(f"║  📍 Key Levels: {levels}")

    risks = ai.get("risks", [])
    if risks and isinstance(risks, list):
        for r in risks[:3]:
            print(f"║  ⚠️  {r}")

    inv = ai.get("invalidation", "")
    if inv:
        print(f"║  ❌ Invalid if: {str(inv)[:60]}")

    risk = result.get("risk", {})
    if isinstance(risk, dict) and risk.get("approved") is not None:
        status = "✅ APPROVED" if risk.get("approved") else "❌ REJECTED"
        print(f"║  Risk: {status}")

    print("║  " + "─" * 40)
    print(f"║  💰 Cost: {result.get('cost', 'N/A')}")
    k_tokens = result.get("knowledge_tokens_used", 0)
    # ⚠️ حل جذري (يوليو 2026، بعد كراش حقيقي: ValueError "Cannot specify
    # ',' with 's'"): بوضع multi_pass (المسار الوحيد الفعّال فعلياً بكل
    # المشروع - راجع brain_core.py::full_analysis)، `knowledge_tokens_
    # used` هي نص "multi_pass_variable" (لا رقم واحد ذو معنى - كل مرحلة
    # top-down تحمّل جزءاً مختلفاً من الدستور) - لكن `f"{k_tokens:,}"`
    # يفترض دائماً رقماً (تنسيق الفاصلة الألفية لا ينطبق على نص). الحل:
    # نطبع الرقم بتنسيق الفاصلة فقط لو كان فعلاً رقماً، وإلا نطبع النص
    # كما هو (بلا محاولة تنسيقه كرقم).
    if isinstance(k_tokens, (int, float)) and k_tokens:
        print(f"║  📚 Knowledge: ~{k_tokens:,.0f} tokens")
    elif k_tokens:
        print(f"║  📚 Knowledge: {k_tokens}")

    if result.get("saved_signal"):
        print("║  💾 Signal saved!")

    print("╚" + "═" * 58 + "╝")


def print_json(data):
    """طباعة JSON منسّق"""
    print("\n" + "=" * 60)
    if isinstance(data, (dict, list)):
        print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    else:
        print(data)
    print("=" * 60)


def run_backtest_menu(backtest_engine, ai):
    """قائمة الـ Backtesting"""

    while True:
        print("\n" + "═" * 50)
        print("📊 BACKTESTING MENU")
        print("═" * 50)

        st = ai.status()
        print(f"💰 Budget: {st['remaining']} | Spent: {st['total_cost']}")
        print(f"🔑 المزودين: {_format_providers_summary(st)}")

        print("\n1. 🚀 بدء Backtest جديد")
        print("2. ▶️  استئناف Backtest سابق")
        print("3. 📈 عرض آخر نتائج")
        print("4. 📋 عرض تفاصيل الصفقات")
        print("5. 🔄 إعادة تفعيل API Keys")
        print("0. ↩️  رجوع للقائمة الرئيسية")

        choice = input("\n➤ اختر: ").strip()

        if choice == "1":
            symbol = input("  الزوج (Enter=BTC/USDT): ").strip() or "BTC/USDT"
            timeframe = input("  فريم التنفيذ فقط (Enter=5m؛ 1D/4H/15m تلقائي): ").strip() or "5m"

            try:
                num_points = int(input("  عدد نقاط الفحص (Enter=20): ").strip() or "20")
            except ValueError:
                num_points = 20

            try:
                budget = float(input("  الحد الأقصى للتكلفة $ (Enter=10): ").strip() or "10")
            except ValueError:
                budget = 10.0

            est_cost = num_points * 0.35
            print(f"\n📊 التقدير: ~{num_points} تحليل = ~${est_cost:.2f}")

            confirm = input("❓ متابعة؟ (Y/n): ").strip().lower()
            if confirm == 'n':
                continue

            print("\n⏳ جاري تشغيل الـ Backtest...")
            print("   (ممكن ياخد وقت طويل حسب عدد النقاط)")
            print("   (يمكنك إيقافه بـ Ctrl+C وسيُحفظ التقدم)\n")

            try:
                result = backtest_engine.run_backtest(
                    symbol=symbol,
                    timeframe=timeframe,
                    num_points=num_points,
                    budget_limit=budget,
                    resume=False
                )

                if "error" in result:
                    print(f"\n❌ Error: {result['error']}")
                    if "candles_analyzed" in result:
                        print(f"   Candles: {result['candles_analyzed']}")
                    if "suggestion" in result:
                        print(f"   💡 {result['suggestion']}")
                else:
                    print("\n✅ Backtest completed!")
                    print(f"   Points: {result.get('completed', 0)}/{result.get('total', 0)}")
                    print(f"   Cost: {result.get('total_cost', 'N/A')}")
                    backtest_engine.print_summary()

            except KeyboardInterrupt:
                print("\n⏸️ Backtest paused - progress saved!")
                backtest_engine._save_state()
            except Exception as e:
                print(f"\n❌ Error: {e}")

        elif choice == "2":
            saved = backtest_engine._load_state()
            if saved:
                print("\n📂 Found saved backtest:")
                print(f"   Symbol: {saved.get('symbol')}")
                print(f"   Progress: {saved.get('completed_points')}/{saved.get('total_points')}")
                print(f"   Cost so far: ${saved.get('total_cost', 0):.2f}")

                confirm = input("\n❓ استئناف؟ (Y/n): ").strip().lower()
                if confirm == 'n':
                    continue

                try:
                    budget = float(input("  الحد الأقصى للتكلفة $ (Enter=10): ").strip() or "10")
                except ValueError:
                    budget = 10.0

                print("\n⏳ جاري الاستئناف...")

                try:
                    result = backtest_engine.run_backtest(
                        symbol=saved['symbol'],
                        timeframe=saved['timeframe'],
                        num_points=saved['total_points'],
                        budget_limit=budget,
                        resume=True
                    )

                    if "error" in result:
                        print(f"\n❌ Error: {result['error']}")
                    else:
                        print("\n✅ Backtest completed!")
                        backtest_engine.print_summary()

                except KeyboardInterrupt:
                    print("\n⏸️ Backtest paused - progress saved!")
                except Exception as e:
                    print(f"\n❌ Error: {e}")
            else:
                print("\n❌ لا يوجد backtest محفوظ")

        elif choice == "3":
            backtest_engine.print_summary()

        elif choice == "4":
            if backtest_engine.current_state and backtest_engine.current_state.get("results"):
                results = backtest_engine.current_state["results"]
                print(f"\n📋 تفاصيل {len(results)} صفقة:")
                print("─" * 70)

                for i, r in enumerate(results):
                    rec = r.get("recommendation", {})
                    ev = r.get("evaluation", {})

                    signal = rec.get("signal", "N/A")
                    outcome = ev.get("outcome", "N/A")
                    emoji = "✅" if "WIN" in outcome else "❌" if outcome == "LOSS" else "⏸️"

                    date = r.get('date', 'N/A')
                    chart_info = r.get('check_on_chart', {})

                    print(
                        f"{i+1}. 📅 {date} | "
                        f"{r.get('point_type', 'N/A')[:20]:20} | "
                        f"{signal:4} {rec.get('confidence', 0):3}% | "
                        f"{outcome:12} {emoji}"
                    )
                    if chart_info:
                        print(
                            f"   🔍 {chart_info.get('go_to', '')}"
                        )
                    if rec.get('entry'):
                        print(
                            f"   💰 Entry: ${rec['entry']} | "
                            f"SL: ${rec.get('stop_loss', 'N/A')} | "
                            f"TP: ${rec.get('tp', rec.get('tp1', 'N/A'))}"
                        )

                print("─" * 70)
            else:
                print("\n❌ لا توجد نتائج")

        elif choice == "5":
            ai.reset_exhausted_keys()
            print("✅ تم إعادة تفعيل كل الـ API Keys")

        elif choice == "0":
            break

        else:
            print("❌ خيار غير صحيح")


def main():
    """القائمة الرئيسية"""

    print("""
╔════════════════════════════════════════════════════════════╗
║  🧠 BrainCore V3.1 | AI-Driven Trading Intelligence       ║
║  ──────────────────────────────────────────────────────── ║
║  AI = Brain | Python = Eyes | Knowledge = Experience       ║
║  Now with Advanced Backtesting & Multi-API Support         ║
╚════════════════════════════════════════════════════════════╝
    """)

    bot = BrainCore()
    ai = OpenRouterClient()
    tracker = SignalTracker()
    backtest = BacktestEngine()

    k_info = bot.get_knowledge_info()
    if k_info.get("exists"):
        print(
            f"  📚 Knowledge: {k_info['total_chars']:,} chars "
            f"(~{k_info['estimated_tokens']:,} tokens)"
        )
        print(
            f"  📂 Sections: {k_info['section_count']} | "
            f"💰 Cost/analysis: {k_info['cost_per_analysis']}"
        )
    else:
        print("  ⚠️  No knowledge file found")

    api_status = ai.status()
    print(f"  🔑 المزودين: {_format_providers_summary(api_status)}")
    print()

    while True:
        st = ai.status()
        print(
            f"\n💰 Budget: {st['remaining']} | "
            f"Requests: {st['total_requests']} | "
            f"Spent: {st['total_cost']}"
        )

        print("\n" + "─" * 50)
        print("📌 القائمة الرئيسية:")
        print("─" * 50)
        print("  1.  📊 تحليل شامل (AI + MTF)")
        print("  2.  ⚡ تحليل سريع (محلي)")
        print("  3.  💵 تقدير تكلفة")
        print("  4.  💬 دردشة مع البوت")
        print("  5.  📚 معلومات المعرفة")
        print("─" * 25)
        print("  6.  📝 تعليم من نص")
        print("  7.  🔍 بحث في المعرفة")
        print("  8.  📖 عرض كل المعرفة")
        print("─" * 25)
        print("  9.  📋 الصفقات المقترحة")
        print("  10. ❓ صفقات غير مفحوصة")
        print("  11. ✅ فحص الصفقات")
        print("─" * 25)
        print("  12. 🧪 BACKTESTING (جديد!)")
        print("  13. 📈 اختبار استراتيجية (AI)")
        print("  14. 📊 إحصائيات الذاكرة")
        print("  15. 🔄 تقييم ذاتي")
        print("  16. 🔑 حالة API Keys")
        print("  17. 🧪 اختبار استقرار القرار (Consistency Test)")
        print("  18. 🔍 مسح شامل لكل العملات (Market Scanner)")
        print("  19. 🕰️  اختبار على أحداث تاريخية حقيقية موثقة")
        print("  20. 🎯 اكتشاف صفقات موضوعية + Backtest عليها")
        print("  21. 🧩 اختبار التحليل متعدد المراحل (Multi-Pass, تجريبي)")
        print("  22. 📜 باك تيست على صفقات بشرية موثّقة (Capital Street FX)")
        print("─" * 25)
        print("  0.  🚪 خروج")

        c = input("\n➤ اختر: ").strip()

        if c == "1":
            s = input("  الزوج (Enter=BTC/USDT): ").strip() or None
            exchange = input("  المنصة (auto/okx/binance/kucoin/gate/bybit/mexc، Enter=auto): ").strip() or "auto"
            t = input("  فريم التنفيذ فقط (Enter=5m؛ 1D/4H/15m تلقائي): ").strip() or None
            est = bot.estimate_analysis_cost(s, t)
            print(
                f"\n  📊 تقدير: ~{est['total_tokens']:,} tokens | "
                f"Cost: {est['total_cost_per_analysis']}"
            )
            go = input("  متابعة؟ (Enter=نعم / n=لا): ").strip().lower()
            if go == "n":
                continue
            print("\n⏳ جاري التحليل...")
            result = bot.full_analysis(s, t, exchange=exchange)
            print_analysis(result)

        elif c == "2":
            s = input("  الزوج (Enter=BTC/USDT): ").strip() or None
            exchange = input("  المنصة (auto/okx/binance/kucoin/gate/bybit/mexc، Enter=auto): ").strip() or "auto"
            t = input("  فريم التنفيذ فقط (Enter=5m؛ 1D/4H/15m تلقائي): ").strip() or None
            print("\n⚡ تحليل محلي...")
            result = bot.quick_analysis(s, t, exchange=exchange)
            if "error" in result:
                print(f"❌ {result['error']}")
            else:
                print(f"\n{result.get('summary', '')}")

        elif c == "3":
            est = bot.estimate_analysis_cost()
            print("\n📊 تقدير تكلفة التحليل:")
            print_json(est)

        elif c == "4":
            print("\n💬 دردشة (اكتب 'خروج' للرجوع)")
            while True:
                m = input("  أنت: ").strip()
                if m in ("خروج", "exit", "q", ""):
                    break
                print(f"\n  🤖 {bot.chat(m)}\n")

        elif c == "5":
            info = bot.get_knowledge_info()
            if info.get("exists"):
                print(f"\n  📁 Path: {info['path']}")
                print(f"  📏 Size: {info['total_chars']:,} chars")
                print(f"  🔤 Tokens: ~{info['estimated_tokens']:,}")
                print(f"  💰 Cost/analysis: {info['cost_per_analysis']}")
                print(f"  📂 Sections: {info['section_count']}")
                if info.get("sections"):
                    print("\n  📑 Section sizes:")
                    for name, size in info["sections"].items():
                        print(f"    [{name}]: {size:,} chars")
            else:
                print("  ⚠️  Knowledge file not found")

        elif c == "6":
            print("\n📘 اكتب النص (سطر فارغ = إنهاء):")
            lines = []
            while True:
                line = input()
                if line.strip() == "":
                    break
                lines.append(line)
            text = "\n".join(lines).strip()
            if text:
                print("\n⏳ جاري الاستخراج...")
                print_json(bot.learn_text(text))
            else:
                print("❌ ما تم إدخال نص.")

        elif c == "7":
            kw = input("  كلمة البحث: ").strip()
            if kw:
                print_json(bot.search_knowledge(kw))

        elif c == "8":
            print_json(bot.get_all_knowledge())

        elif c == "9":
            print_json(bot.get_proposed_signals())

        elif c == "10":
            print_json(bot.get_unchecked_signals())

        elif c == "11":
            print("\n⏳ جاري الفحص...")
            print_json(tracker.check_all_unchecked())

        elif c == "12":
            run_backtest_menu(backtest, ai)

        elif c == "13":
            st_text = input("  اشرح الاستراتيجية: ").strip()
            if st_text:
                print("\n⏳ باك تست بـ AI...")
                print_json(bot.backtest(st_text))

        elif c == "14":
            print_json(bot.memory.get_stats())

        elif c == "15":
            print("\n🧠 تقييم...")
            print_json(bot.self_evaluate())

        elif c == "16":
            print("\n🔑 حالة مزودي الـ AI:")
            status = ai.status()
            print(f"  ترتيب المزودين: {' → '.join(status['provider_order'])}")
            print(f"  Total Requests: {status['total_requests']}")
            print(f"  Total Cost: {status['total_cost']}")
            print(f"  Remaining: {status['remaining']}")
            for pname, pinfo in status.get('providers', {}).items():
                print(f"\n  📡 {pname} ({pinfo['model']}):")
                print(f"     Active Keys: {pinfo['active_keys']}/{pinfo['total_keys']}")
                for key, stats in pinfo.get('per_key', {}).items():
                    exhausted = "❌ EXHAUSTED" if stats.get('exhausted') else "✅ Active"
                    print(
                        f"       {key}: {stats['requests']} req | "
                        f"{stats['errors']} errors | {exhausted}"
                    )

            reset = input("\n  إعادة تفعيل كل الـ Keys؟ (y/N): ").strip().lower()
            if reset == 'y':
                ai.reset_exhausted_keys()
                print("  ✅ تم إعادة تفعيل كل الـ Keys لكل المزودين")

        elif c == "17":
            print("\n🧪 اختبار استقرار القرار (Consistency Test)")
            print("   يشغّل نفس التحليل عدة مرات على نفس البيانات بالضبط")
            print("   ويقيس هل الإشارة/الثقة ثابتة أو متذبذبة عشوائياً.")
            print("   ⚠️ ملاحظة: يستهلك عدة طلبات من حصتك المجانية.\n")
            s = input("  الزوج (Enter=BTC/USDT): ").strip() or None
            t = input("  فريم التنفيذ فقط (Enter=5m؛ 1D/4H/15m تلقائي): ").strip() or None
            runs = input("  عدد المحاولات (Enter=3): ").strip()
            runs = int(runs) if runs.isdigit() else 3

            from consistency_test import ConsistencyTester
            tester = ConsistencyTester(bot)

            print("\n⏳ جاري جلب بيانات ثابتة أولاً...")
            # نجلب لقطة واحدة من البيانات الحقيقية ونجمّدها كـ custom_data
            # لكل المحاولات (لعزل عشوائية النموذج عن عشوائية تغيّر
            # السوق الفعلي بين الطلبات - نفس البيانات بالضبط كل مرة)
            entry_snapshot = bot.data_manager.get_ohlcv(s, t, output_format="dict")
            if not entry_snapshot:
                print("❌ فشل جلب البيانات")
                continue

            custom_data = {"entry": entry_snapshot}
            report = tester.run(symbol=s, timeframe=t, custom_data=custom_data, runs=runs)
            print("\n" + "=" * 50)
            print(f"📊 النتيجة: {report.get('verdict')}")
            print(f"   توافق الإشارة: {report.get('signal_agreement_pct')}%")
            print(f"   توزيع الإشارات: {report.get('signal_distribution')}")
            if report.get("confidence_stats"):
                cs = report["confidence_stats"]
                print(f"   الثقة: متوسط={cs['mean']}% | مدى={cs['range']} نقطة")
            for issue in report.get("issues", []):
                print(f"   {issue}")
            print(f"\n💡 {report.get('recommendation')}")

        elif c == "18":
            print("\n🔍 مسح شامل لكل العملات (Market Scanner)")
            print(f"   العملات: {', '.join(Config.SCAN_SYMBOLS[:5])}... "
                  f"({len(Config.SCAN_SYMBOLS)} عملة)")
            print(f"   ⚠️ يستهلك حتى {len(Config.SCAN_SYMBOLS)} طلب من حصتك المجانية\n")

            t = input("  فريم التنفيذ فقط (Enter=5m؛ 1D/4H/15m تلقائي): ").strip() or None
            min_conf = input(f"  الحد الأدنى للثقة (Enter={Config.SCANNER_MIN_CONFIDENCE}%): ").strip()
            min_conf = int(min_conf) if min_conf.isdigit() else Config.SCANNER_MIN_CONFIDENCE
            stop_first = input("  توقف عند أول تطابق؟ (y/N): ").strip().lower() == 'y'

            from market_scanner import MarketScanner
            scanner = MarketScanner(bot)

            print("\n⏳ جاري المسح... (قد يأخذ عدة دقائق)")
            if stop_first:
                report = scanner.scan_until_found(timeframe=t, min_confidence=min_conf)
            else:
                report = scanner.scan(timeframe=t, min_confidence=min_conf)

            print("\n" + "=" * 60)
            print(f"📊 نتيجة المسح: {report['scanned']} عملة | "
                  f"{report['successful_analyses']} تحليل ناجح | "
                  f"{len(report['errors'])} خطأ")
            print(f"🎯 صفقات مطابقة (ثقة ≥ {report['min_confidence_used']}%): "
                  f"{len(report['matches'])}")

            if report["matches"]:
                for m in report["matches"]:
                    print(f"\n  {'🟢' if m['signal']=='BUY' else '🔴'} {m['symbol']} - {m['signal']} "
                          f"(ثقة {m['confidence']}%)")
                    print(f"     Entry: {m['entry_price']} | SL: {m['stop_loss']} | "
                          f"TP: {m['tp']} | R:R: {m['rr']}")
                    print(f"     Archetype: {m['archetype'][:100]}")
                    print(f"     Verification Score: {m['verification_score']}%")
            else:
                print("\n  😐 لا توجد صفقات تحقق الحد المطلوب حالياً بهذه القائمة.")

        elif c == "19":
            print("\n🕰️ اختبار الكود على أحداث تاريخية حقيقية وموثقة")
            print("   (انهيار FTX نوفمبر 2022 + ارتداد أزمة SVB مارس 2023)")
            print("   ⚠️ يستهلك طلبين من حصتك المجانية\n")

            from known_trades_backtest import KnownTradesBacktest
            kt = KnownTradesBacktest(bot)

            print("⏳ جاري التحليل على البيانات التاريخية...")
            report = kt.run_all()

            for r in report["results"]:
                print("\n" + "-" * 60)
                print(f"📌 {r.get('event')}")
                if "error" in r:
                    print(f"   ❌ خطأ: {r['error']}")
                    continue
                print(f"   النتيجة الفعلية الموثقة: {r['documented_outcome']}")
                print(f"   {r['outcome_description']}")
                print(f"   آخر سعر رآه البوت: ${r['last_price_seen_by_bot']}")
                print(f"   قراءة البوت: bias={r['bot_bias']} | "
                      f"signal={r['bot_signal']} | confidence={r['bot_confidence']}%")
                print(f"   التقييم: {r['alignment_assessment']}")

        elif c == "20":
            print("\n🎯 اكتشاف صفقات تاريخية موضوعية + Backtest عليها")
            print("   يمر رياضياً على بيانات BTC الحقيقية (لا اختيار يدوي)")
            print("   ويكتشف صفقات فعلية بمعيار موضوعي (سحب سيولة + انعكاس)")
            print("   ثم يختبر هل البوت يعطي نفس القراءة على نفس البيانات\n")
            print("   ⚠️ يستهلك حتى 5 طلبات من حصتك المجانية\n")

            from known_setups_finder import KnownSetupsFinder
            finder = KnownSetupsFinder(bot.data_manager, bot.authenticity)

            print("⏳ جاري اكتشاف الصفقات من البيانات التاريخية...")
            setups = finder.find_setups_multi_timeframe(symbol="BTC/USDT")

            if not setups:
                print("❌ لم يتم اكتشاف أي صفقة تحقق المعيار الموضوعي حالياً")
                continue

            print(f"\n✅ تم اكتشاف {len(setups)} صفقة حقيقية موثقة رياضياً:")
            for s in setups:
                print(f"   • {s['signal_date_readable']} | {s['direction']} | "
                      f"دخول: ${s['entry_price_actual']} | "
                      f"حركة فعلية: {s['actual_move_pct']}%")

            go = input("\n  متابعة لتشغيل البوت على هذه الصفقات؟ (Enter=نعم / n=لا): ").strip().lower()
            if go == "n":
                continue

            print("\n⏳ جاري تشغيل تحليل البوت على كل صفقة (بدون رؤية المستقبل)...")
            report = finder.run_backtest(bot, setups)

            print("\n" + "=" * 60)
            print(f"📊 النتيجة: {report['total_setups_tested']} صفقة مختبرة")
            print(f"   تطابق الإشارة (BUY/SELL بالضبط): "
                  f"{report['signal_match_count']}/{report['total_setups_tested']} "
                  f"({report['signal_match_pct']}%)")
            print(f"   تطابق الاتجاه (bias فقط): "
                  f"{report['bias_match_count']}/{report['total_setups_tested']} "
                  f"({report['bias_match_pct']}%)")

            for r in report["detailed_results"]:
                print(f"\n  📅 {r['signal_date_readable']} | متوقع: {r['expected_signal']} "
                      f"(حركة فعلية {r['actual_move_pct']}%)")
                if "bot_error" in r:
                    print(f"     ❌ خطأ: {r['bot_error']}")
                    continue
                print(f"     البوت قال: {r['bot_signal']} (ثقة {r['bot_confidence']}%)")
                print(f"     {r['verdict']}")

        elif c == "21":
            print("\n🧩 Multi-Pass Analysis Test (تحليل متعدد المراحل)")
            print("   بدل طلب واحد ضخم بكل الدستور، يقسّم التحليل لـ5")
            print("   مراحل متسلسلة (نظرة شمولية → هيكل → مناطق → دخول")
            print("   → تركيب نهائي) لمعالجة مشكلة 'Lost in the Middle'")
            print("   (قواعد مدفونة بمنتصف دستور ضخم قد تُهمَل فعلياً).")
            print("   ⚠️ يستهلك 5× الحصة العادية لكل صفقة (5 نداءات API")
            print("   بدل نداء واحد) ووقتاً أطول (~100-150 ثانية/صفقة)\n")

            from known_setups_finder import KnownSetupsFinder
            finder = KnownSetupsFinder(bot.data_manager, bot.authenticity)

            print("⏳ جاري اكتشاف الصفقات من البيانات التاريخية...")
            setups = finder.find_setups_multi_timeframe(symbol="BTC/USDT", max_setups=3)

            if not setups:
                print("❌ لم يتم اكتشاف أي صفقة تحقق المعيار الموضوعي حالياً")
                continue

            print(f"\n✅ تم اكتشاف {len(setups)} صفقة حقيقية موثقة رياضياً:")
            for s in setups:
                print(f"   • {s['signal_date_readable']} | {s['direction']} | "
                      f"حركة فعلية: {s['actual_move_pct']}%")

            go = input(
                f"\n  متابعة لتشغيل {len(setups)} صفقة بالوضع متعدد المراحل "
                f"(~{len(setups)*5} طلبات)؟ (Enter=نعم / n=لا): "
            ).strip().lower()
            if go == "n":
                continue

            print("\n⏳ جاري تشغيل التحليل متعدد المراحل (قد يأخذ عدة دقائق)...")
            report = finder.run_backtest(bot, setups, use_multi_pass=True)

            print("\n" + "=" * 60)
            print(f"📊 النتيجة (Multi-Pass): {report['total_setups_tested']} صفقة مختبرة")
            print(f"   تطابق الإشارة: {report['signal_match_count']}/"
                  f"{report['total_setups_tested']} ({report['signal_match_pct']}%)")
            print(f"   تطابق الاتجاه: {report['bias_match_count']}/"
                  f"{report['total_setups_tested']} ({report['bias_match_pct']}%)")

            for r in report["detailed_results"]:
                print(f"\n  📅 {r['signal_date_readable']} | متوقع: {r['expected_signal']} "
                      f"(حركة فعلية {r['actual_move_pct']}%)")
                if "bot_error" in r:
                    print(f"     ❌ خطأ: {r['bot_error']}")
                    continue
                print(f"     البوت قال: {r['bot_signal']} (ثقة {r['bot_confidence']}%)")
                print(f"     {r['verdict']}")

        elif c == "22":
            print("\n📜 باك تيست على صفقات بشرية موثّقة (Capital Street FX)")
            print("   ⚠️ هذه صفقات نُشرت فعلياً من مصدر بشري حقيقي (لا اختلاق")
            print("   رياضي) - البوت يُحلَّل عند نفس لحظة النشر بالضبط (لا")
            print("   تسريب مستقبلي)، ثم تُقارن إشارته بنتيجة حقيقية محسوبة")
            print("   شمعة بشمعة (لا تخمين اتجاه فقط - ربح/خسارة فعلية).")

            from human_trades_backtest import (
                _load_human_trades, run_human_trades_backtest,
                summarize_human_trades, get_journal_stats,
            )
            all_trades, src_path = _load_human_trades()
            if not all_trades:
                print("\n❌ لم يُعثر على ملف الصفقات البشرية (human_trades/"
                      "all_human_trades_with_outcomes.json) - تأكد من وجوده "
                      "بمجلد المشروع.")
                continue

            # ── 1) عرض جدول كامل بكل الصفقات البشرية الجاهزة (بلا أي
            # نداء API - كل هذا موثّق مسبقاً بالملف) ──
            summary_rows = summarize_human_trades()
            print(f"\n✅ {len(summary_rows)} صفقة بشرية موثّقة متاحة (من {src_path})")
            print("\n" + "─" * 100)
            print(f"{'#':>3} {'الرمز':<9} {'التاريخ':<11} {'الاتجاه البشري':<32} "
                  f"{'دخول':<20} {'ستوب':<9} {'تارغت':<20} {'النتيجة الفعلية':<20}")
            print("─" * 100)
            for r in summary_rows:
                entry_disp = str(r["human_entry"])[:18]
                tp_disp = str(r["human_tp"])[:18]
                bias_disp = str(r["human_bias"])[:30]
                outcome_disp = f"{r['human_outcome']} ({r['human_pnl_pct']}%)" if r["human_pnl_pct"] is not None else r["human_outcome"]
                print(f"{r['id']:>3} {r['symbol']:<9} {str(r['publish_date']):<11} {bias_disp:<32} "
                      f"{entry_disp:<20} {str(r['human_sl']):<9} {tp_disp:<20} {outcome_disp:<20}")
            print("─" * 100)

            jstats = get_journal_stats()
            print(f"\n📔 سجل البوت الدائم حتى الآن: {jstats['total_wins']} ربح مسجَّل | "
                  f"{jstats['total_losses']} خسارة مسجَّلة | {jstats['total_neutral']} محايد")

            # ── 2) اختيار: صفقة واحدة / عدة صفقات محددة / كل الصفقات ──
            print("\nكيف تريد الاختبار؟")
            print("  1. صفقة واحدة محددة (بالرقم #)")
            print("  2. عدة صفقات محددة (أرقام مفصولة بفواصل، مثال: 1,3,7)")
            print("  3. أول N صفقة (توفير حصة)")
            print("  4. كل الصفقات (19)")
            choice = input("➤ اختر (Enter=4): ").strip() or "4"

            trade_ids = None
            limit = None
            if choice == "1":
                tid = input("  رقم الصفقة #: ").strip()
                try:
                    trade_ids = [int(tid)]
                except ValueError:
                    print("  ⚠️ رقم غير صالح.")
                    continue
            elif choice == "2":
                ids_input = input("  أرقام الصفقات (مفصولة بفواصل): ").strip()
                try:
                    trade_ids = [int(x.strip()) for x in ids_input.split(",") if x.strip()]
                except ValueError:
                    print("  ⚠️ صيغة غير صالحة.")
                    continue
            elif choice == "3":
                n_input = input(f"  كم صفقة؟ (من أصل {len(all_trades)}): ").strip()
                try:
                    limit = int(n_input)
                except ValueError:
                    print("  ⚠️ رقم غير صالح - سيُستخدم الكل.")

            n_selected = len(trade_ids) if trade_ids else (limit or len(all_trades))

            # ── 3) رأس مال اختياري لحساب ربح/خسارة بالدولار الفعلي ──
            cap_input = input(
                "\n  💰 حدّد رأس مال بالدولار لحساب الربح/الخسارة الفعلي "
                "(Enter=تجاهل، فقط نسبة%): "
            ).strip()
            capital_usd = None
            if cap_input:
                try:
                    capital_usd = float(cap_input)
                except ValueError:
                    print("  ⚠️ قيمة غير صالحة - سيُتجاهل حساب رأس المال.")

            lessons_input = input(
                "  📚 استخراج درس تحليلي من كل نتيجة؟ (Enter=نعم، يستهلك نداء "
                "API إضافي لكل صفقة حاسمة / n=لا): "
            ).strip().lower()
            extract_lessons = lessons_input != "n"

            est_calls = n_selected * (6 if extract_lessons else 5)
            go = input(
                f"\n  متابعة اختبار {n_selected} صفقة؟ (~{est_calls} نداء API "
                f"تقديرياً، قد يأخذ عدة دقائق لكل صفقة) (Enter=نعم / n=لا): "
            ).strip().lower()
            if go == "n":
                continue

            def _progress(idx, total, r):
                if "error" in r:
                    print(f"\n  [{idx}/{total}] صفقة #{r.get('id')} ({r.get('symbol')}) "
                          f"❌ خطأ: {r['error']}")
                    return
                print(
                    f"\n  [{idx}/{total}] صفقة #{r['id']} ({r['symbol']}, {r['publish_date']}) "
                    f"| ⏱️ {r['elapsed_seconds']}s"
                )
                print(f"       بشري: {r['human_bias']} → {r['human_outcome']} ({r['human_pnl_pct']}%)")
                print(f"       البوت: {r['bot_signal']} (ثقة {r.get('bot_confidence')}%) "
                      f"entry={r.get('bot_entry')} sl={r.get('bot_sl')} tp={r.get('bot_tp')}")
                print(f"       نتيجة البوت الفعلية: {r.get('bot_outcome')} ({r.get('bot_pnl_pct')}%)")
                if r.get("capital_result", {}).get("pnl_usd") is not None:
                    print(f"       💰 على رأس مال ${r['capital_result']['capital_usd']}: "
                          f"${r['capital_result']['pnl_usd']} "
                          f"(حجم مركز ${r['capital_result']['position_size_usd']})")
                print(f"       {r['verdict_text']}")
                if r.get("lesson_extracted"):
                    print(f"       📚 درس مستخلص: {r['lesson_extracted']}")

            print("\n⏳ جاري تشغيل التحليل الكامل (Multi-Pass) على كل صفقة...")
            report = run_human_trades_backtest(
                bot, limit=limit, trade_ids=trade_ids, capital_usd=capital_usd,
                extract_lessons=extract_lessons, progress_callback=_progress,
            )

            if "error" in report:
                print(f"\n❌ {report['error']}")
                continue

            # ── 4) جدول مقارنة نهائي منظّم (بشري مقابل بوت) ──
            print("\n" + "=" * 110)
            print("📊 جدول المقارنة الكامل: القرار البشري مقابل قرار البوت")
            print("=" * 110)
            print(f"{'#':>3} {'الرمز':<9} {'بشري→نتيجة':<22} {'بوت→إشارة':<12} "
                  f"{'بوت→نتيجة':<22} {'الحكم':<45}")
            print("─" * 110)
            for r in report["results"]:
                if "error" in r:
                    print(f"{r['id']:>3} {r['symbol']:<9} خطأ: {r['error']}")
                    continue
                human_disp = f"{r['human_outcome']}({r['human_pnl_pct']}%)"
                bot_outcome_disp = f"{r.get('bot_outcome')}({r.get('bot_pnl_pct')}%)" if r.get("bot_outcome") else "-"
                verdict_short = r["verdict_text"][:43]
                print(f"{r['id']:>3} {r['symbol']:<9} {human_disp:<22} {r['bot_signal']:<12} "
                      f"{bot_outcome_disp:<22} {verdict_short:<45}")
            print("=" * 110)

            print("\n📊 ملخص إحصائي")
            print(f"  الصفقات المختبرة: {report['total_trades_tested']}")
            print(f"  تحليلات ناجحة: {report['successful_analyses']} | "
                  f"فاشلة: {report['failed_analyses']}")
            print(f"  إشارات HOLD (تحفّظ): {report['hold_count']} | "
                  f"إشارات اتجاهية: {report['directional_signals_count']}")
            print(f"  🟢 ربح فعلي محسوب: {report['win_count']} | "
                  f"🔴 خسارة فعلية محسوبة: {report['loss_count']}")
            if capital_usd:
                total_pnl_usd = sum(
                    r.get("capital_result", {}).get("pnl_usd", 0) or 0
                    for r in report["results"] if "capital_result" in r
                )
                print(f"  💰 صافي الربح/الخسارة الإجمالي على رأس مال ${capital_usd}: "
                      f"${round(total_pnl_usd, 2)}")
            print(f"  الوقت الكلي: {report['total_wall_time_sec']}s | "
                  f"المتوسط لكل صفقة: {report['avg_time_per_trade_sec']}s")

            jstats_after = get_journal_stats()
            print(f"\n📔 سجل البوت الدائم بعد هذا الاختبار: {jstats_after['total_wins']} ربح | "
                  f"{jstats_after['total_losses']} خسارة | {jstats_after['total_neutral']} محايد")
            print("   (محفوظ بـ data/trade_journal.json - يُراكَم عبر كل الجلسات)")

            save = input("\n  حفظ التقرير الكامل بملف JSON؟ (Enter=نعم / n=لا): ").strip().lower()
            if save != "n":
                out_path = f"human_trades_backtest_report_{int(time.time())}.json"
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(report, f, ensure_ascii=False, indent=2, default=str)
                print(f"  ✅ حُفظ بـ: {out_path}")

        elif c == "0":
            final = ai.status()
            print("\n📊 Session Summary:")
            print(f"   Total Cost: {final['total_cost']}")
            print(f"   Requests: {final['total_requests']}")
            print("\n👋 مع السلامة!")
            break

        else:
            print("❌ خيار غير صحيح")


if __name__ == "__main__":
    import sys
    if "--legacy" in sys.argv:
        main()
    else:
        # الواجهة الافتراضية نفسها المستخدمة في التطبيق/Telegram.
        # استخدم `python main.py --legacy` فقط للقائمة البحثية القديمة.
        from run import main as unified_main
        unified_main()
