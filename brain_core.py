# -*- coding: utf-8 -*-
"""
BrainCore V3.2 - AI-Driven Architecture
Supports custom_data for backtesting (historical candles)
"""
import logging
import json
import os
import re
from openrouter_client import OpenRouterClient
from data_manager import DataManager
from technical_analyzer import TechnicalAnalyzer
from risk_manager import RiskManager
from memory_system import MemorySystem
from config import Config
from learning_manager import LearningManager
from signal_repository import SignalRepository
from authenticity_engine import AuthenticityEngine
from verification_layer import VerificationLayer
from signal_schema import get_signal_schema, normalize_signal_dict
from user_utils import closed_candle_stamp, dual_time


class BrainCore:

    def __init__(self):
        self.logger = logging.getLogger("BrainCore")

        self.ai = OpenRouterClient()
        self.data_manager = DataManager()
        self.ta = TechnicalAnalyzer()
        self.risk_manager = RiskManager()
        self.memory = MemorySystem()
        self.learning_manager = LearningManager()
        self.authenticity = AuthenticityEngine()
        self.verifier = VerificationLayer()

        self.signal_repo = SignalRepository()

        Config.ensure_data_dir()
        self._ensure_knowledge_file()

        self.logger.info("🧠 BrainCore V3 ready - AI is the brain")

    # ══════════════════════════════════════════════
    #  KNOWLEDGE SYSTEM
    # ══════════════════════════════════════════════

    def _ensure_knowledge_file(self):
        path = Config.KNOWLEDGE_FILE
        if not os.path.exists(path):
            # ⚠️ إصلاح خطر حقيقي (يوليو 2026): كان هذا الفرع يُنشئ ملف
            # معرفة فارغ بديل (67 حرف فقط) بصمت شبه تام (فقط logger.info
            # عادي، لا استثناء، لا تحذير بارز) - بوت تداول قد يستمر
            # بالعمل واتخاذ قرارات BUY/SELL بلا أي معرفة ICT/SMC إطلاقاً
            # دون أن يلاحظ أحد. بعد إصلاح KNOWLEDGE_FILE ليكون مساراً
            # مطلقاً (راجع config.py) هذا السيناريو أصبح نادراً جداً
            # (لا يعتمد على cwd بعد الآن)، لكن يبقى ممكناً إذا حُذف ملف
            # المعرفة الحقيقي فعلاً بالخطأ - في هذه الحالة الفشل الصريح
            # والواضح أفضل بكثير من الاستمرار الصامت بمعرفة فارغة.
            self.logger.critical(
                f"🚨 ملف قاعدة المعرفة غير موجود إطلاقاً بالمسار المتوقع: "
                f"{path} - هذا يعني البوت سيعمل بلا أي معرفة ICT/SMC حقيقية "
                f"إذا استمر التشغيل. لن يُنشأ ملف بديل فارغ بصمت (كان هذا "
                f"السلوك القديم الخطير) - يجب إصلاح المسار أو استعادة "
                f"الملف الحقيقي قبل المتابعة."
            )
            raise FileNotFoundError(
                f"KNOWLEDGE_FILE غير موجود: {path} - راجع Config.KNOWLEDGE_FILE "
                f"وتأكد من وجود ملف قاعدة المعرفة الحقيقي بهذا المسار بالضبط. "
                f"لن يُستبدل تلقائياً بملف فارغ (خطر تشغيل بوت تداول بلا معرفة)."
            )

    def _load_knowledge(self):
        try:
            path = Config.KNOWLEDGE_FILE
            if not os.path.exists(path):
                return "", 0

            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()

            if not content:
                return "", 0

            total_chars = len(content)
            tokens_est = total_chars // 4
            cost_est = tokens_est * 5 / 1_000_000

            self.logger.info(
                f"📚 Knowledge: {total_chars:,} chars | "
                f"~{tokens_est:,} tokens | ~${cost_est:.3f}/analysis"
            )
            return content, tokens_est

        except Exception as e:
            self.logger.error(f"Knowledge load error: {e}")
            return "", 0

    def get_knowledge_info(self):
        try:
            path = Config.KNOWLEDGE_FILE
            if not os.path.exists(path):
                return {"exists": False, "path": path}

            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            sections = {}
            current = "HEADER"
            current_lines = []
            for line in content.split("\n"):
                match = re.match(r'^\[([A-Z_]+)\]\s*$', line.strip())
                if match:
                    if current_lines:
                        text = "\n".join(current_lines).strip()
                        if text:
                            sections[current] = len(text)
                    current = match.group(1)
                    current_lines = []
                else:
                    current_lines.append(line)
            if current_lines:
                text = "\n".join(current_lines).strip()
                if text:
                    sections[current] = len(text)

            total = len(content)
            tokens = total // 4
            cost = tokens * 5 / 1_000_000

            return {
                "exists": True,
                "path": os.path.abspath(path),
                "total_chars": total,
                "estimated_tokens": tokens,
                "sections": sections,
                "section_count": len(sections),
                "cost_per_analysis": f"~${cost:.4f}",
            }
        except Exception as e:
            return {"error": str(e)}

    def estimate_analysis_cost(self, symbol=None, timeframe=None):
        knowledge, k_tokens = self._load_knowledge()
        learned = self._build_learned_context()

        candle_tokens = (
            Config.AI_CANDLES_ENTRY * 10 +
            Config.AI_CANDLES_CONTEXT * 10 +
            Config.AI_CANDLES_MACRO * 10
        )
        indicator_tokens = 250 * 3
        instruction_tokens = 100
        system_tokens = 400
        learned_tokens = len(learned) // 4

        total_input = (
            system_tokens + k_tokens + candle_tokens +
            indicator_tokens + instruction_tokens + learned_tokens
        )
        total_output = 2500

        input_cost = total_input * 5 / 1_000_000
        output_cost = total_output * 7 / 1_000_000
        total_cost = input_cost + output_cost

        return {
            "input_tokens": total_input,
            "output_tokens": total_output,
            "total_tokens": total_input + total_output,
            "knowledge_tokens": k_tokens,
            "knowledge_chars": len(knowledge),
            "input_cost": f"${input_cost:.4f}",
            "output_cost": f"${output_cost:.4f}",
            "total_cost_per_analysis": f"${total_cost:.4f}",
            "analyses_per_dollar": int(1 / total_cost) if total_cost > 0 else 999,
            "analyses_per_5_dollars": int(5 / total_cost) if total_cost > 0 else 999,
        }

    def _build_learned_context(self, limit=8):
        try:
            items = self.learning_manager.all_knowledge()
            if not items:
                return ""
            short = items[-limit:]
            lines = []
            for item in short:
                t = item.get("type", "unknown")
                name = item.get("name", "")
                defn = item.get("definition", "")
                lines.append(f"- [{t}] {name}: {defn[:150]}")
            return "\n".join(lines)
        except Exception:
            return ""

    def _build_performance_context(self):
        try:
            signals = self.signal_repo.get_all()
            if not signals:
                return ""

            checked = [s for s in signals if s.get("checked")]
            if not checked:
                return f"Total signals: {len(signals)} (none evaluated yet)"

            wins = sum(1 for s in checked
                       if s.get("result", {}).get("outcome") == "WIN")
            losses = sum(1 for s in checked
                         if s.get("result", {}).get("outcome") == "LOSS")
            total = len(checked)
            wr = round(wins / total * 100, 1) if total > 0 else 0
            return (
                f"Evaluated: {total} | Wins: {wins} | Losses: {losses} | "
                f"Win Rate: {wr}%"
            )
        except Exception:
            return ""

    # ══════════════════════════════════════════════
    #  CANDLE FORMATTING
    # ══════════════════════════════════════════════

    def _format_candles(self, data, n=40):
        """
        ⚠️ إصلاح خطأ جذري حقيقي مُكتشف (يوليو 2026، تحليل reading_comprehension_test):
        النسخة القديمة كانت ترقّم الجدول تصاعدياً (#1=الأقدم ... #N=الأحدث)
        بينما كل الـ prompts وكل الـ schemas بكل الملفات (signal_schema.py,
        multi_pass_analysis.py, reading_comprehension_test.py) تطلب من الـ AI
        صراحة أن يرجع "index_from_end" بترقيم عكسي (سالب، -1=آخر شمعة).

        الدليل: اختبار reading_comprehension_test الفعلي أظهر أن دقة **السعر**
        المُدَّعى كانت 100% (كل سعر مذكور كان موجوداً فعلياً بالبيانات - لا
        هلوسة) بينما دقة **الـ index** (ترقيم موقع الشمعة) كانت ضعيفة جداً -
        حتى مع سعر صحيح. هذا يثبت أن المشكلة لم تكن "قراءة غلط للبيانات" بل
        "خطأ ترجمة نظام عدّ" بحت: الـ AI كان مجبراً يحوّل ذهنياً بكل مرة من
        رقم الجدول (تصاعدي) لصيغة index_from_end (تنازلي سالب) المطلوبة -
        عملية حسابية إضافية عرضة للخطأ بلا أي داعٍ.

        الإصلاح: نفس نظام العدّ المطلوب بالـ schema يُستخدم مباشرة بعرض
        الجدول نفسه (عمود idx يعرض -1, -2, -3... مباشرة) - يُلغي الحاجة
        للتحويل الذهني كلياً، لا AI "يقرأ صح ثم يترجم غلط".
        """
        if not data:
            return "No data"

        if "closes" not in data:
            return "No candle data"

        count = min(n, data.get("count", len(data["closes"])))

        has_extended = "buy_sell_ratio" in data and "num_trades" in data

        header_note = (
            "idx column = index_from_end (السالب هو نفسه المطلوب بأي حقل "
            "index_from_end/candle_index_from_end بالرد - انسخه مباشرة، "
            "-1 دائماً آخر/أحدث شمعة، لا حاجة لأي تحويل ذهني)"
        )

        if has_extended:
            lines = [header_note, "idx|O|H|L|C|Vol|Trades|Buy%"]
            for i in range(-count, 0):
                o = round(data["opens"][i], 2)
                h = round(data["highs"][i], 2)
                l = round(data["lows"][i], 2)
                c = round(data["closes"][i], 2)
                v = int(data["volumes"][i])
                trades = int(data["num_trades"][i]) if data["num_trades"][i] else 0
                buy_pct = round(data["buy_sell_ratio"][i] * 100, 1) if data["buy_sell_ratio"][i] else 50
                lines.append(f"{i}|{o}|{h}|{l}|{c}|{v}|{trades}|{buy_pct}%")
        else:
            lines = [header_note, "idx|O|H|L|C|Vol"]
            for i in range(-count, 0):
                o = round(data["opens"][i], 2)
                h = round(data["highs"][i], 2)
                l = round(data["lows"][i], 2)
                c = round(data["closes"][i], 2)
                v = int(data["volumes"][i])
                lines.append(f"{i}|{o}|{h}|{l}|{c}|{v}")

        return "\n".join(lines)

    def _format_market_snapshot(self, snapshot):
        if not snapshot:
            return ""

        parts = ["\n── MARKET SNAPSHOT ──"]

        if "price_data" in snapshot:
            pd = snapshot["price_data"]
            parts.append(f"Current Price: {pd.get('current_price', 'N/A')}")
            if pd.get("last_5_buy_ratio"):
                ratios = [f"{r*100:.1f}%" for r in pd["last_5_buy_ratio"]]
                parts.append(f"Last 5 Buy Ratios: {', '.join(ratios)}")

        if "funding" in snapshot:
            f = snapshot["funding"]
            parts.append(f"Funding Rate: {f.get('current_rate_pct', 'N/A')}%")

        if "open_interest" in snapshot:
            oi = snapshot["open_interest"]
            parts.append(f"Open Interest: {oi.get('current', 'N/A')}")
            if "change_pct" in oi:
                parts.append(f"OI Change: {oi['change_pct']}%")

        if "long_short" in snapshot:
            ls = snapshot["long_short"]
            if "top_traders_long_pct" in ls:
                parts.append(
                    f"Top Traders: Long {ls['top_traders_long_pct']}% | "
                    f"Short {ls['top_traders_short_pct']}%"
                )
            if "global_long_pct" in ls:
                parts.append(
                    f"Global: Long {ls['global_long_pct']}% | "
                    f"Short {ls['global_short_pct']}%"
                )

        if "order_book" in snapshot:
            ob = snapshot["order_book"]
            parts.append(f"Bid/Ask Ratio: {ob.get('bid_ask_ratio', 'N/A')}")

        return "\n".join(parts)

    # ══════════════════════════════════════════════
    #  FULL ANALYSIS (يدعم custom_data للباك تست)
    # ══════════════════════════════════════════════

    def full_analysis(self, symbol=None, timeframe=None, custom_data=None,
                       use_multi_pass=True, exchange=None):
        """
        تحليل كامل بالـ AI.

        Args:
            symbol: الزوج
            timeframe: الفريم
            custom_data: dict بالشكل {"entry": dict_data}
                         إذا تم تمريره، يستخدمه بدل جلب بيانات حية
                         (مستخدم للـ Backtesting)
            use_multi_pass: (اختياري) إذا True، يستخدم محرك التحليل
                         متعدد المراحل (multi_pass_analysis.py) بدل
                         طلب واحد ضخم بكل الدستور - يعالج مشكلة
                         "Lost in the Middle" (اقتراح المستخدم صراحة)
                         على حساب 5 نداءات API بدل نداء واحد (حصة
                         يومية أقل بـ5×، وقت أطول). القرارات النهائية
                         تمر بنفس طبقات التحقق (BOS check، candle
                         audit، wick check) بغض النظر عن طريقة التحليل.
        """
        symbol = symbol or Config.DEFAULT_SYMBOL
        timeframe = timeframe or Config.DEFAULT_TIMEFRAME
        self.logger.info(f"🔍 Full Analysis: {symbol} {timeframe}")

        market_snapshot = None

        # ═══ 1) جلب البيانات ═══
        if custom_data:
            # ── وضع الباك تست: استخدام البيانات المُمررة ──
            mtf_data = custom_data
            self.logger.info("📊 Using custom data (backtest mode)")
        else:
            # ── وضع التحليل الحي: جلب من الإنترنت ──
            if Config.MTF_ENABLED:
                mtf_data = self.data_manager.get_multi_timeframe(
                    symbol, timeframe, exchange=exchange
                )
            else:
                data = self.data_manager.get_ohlcv(
                    symbol, timeframe, output_format="dict", exchange=exchange,
                    closed_only=True, allow_fallback=(exchange in (None, "auto")),
                )
                mtf_data = {"entry": data} if data else None

            if not mtf_data:
                return {"error": "فشل جلب البيانات"}

            # استخراج market_snapshot بشكل منفصل
            market_snapshot = mtf_data.pop("market_snapshot", None)

        # ═══ 2) حساب المؤشرات ═══
        mtf_indicators = {}
        for label, data in mtf_data.items():
            if not isinstance(data, dict) or "closes" not in data:
                continue
            try:
                ind = self.ta.compute_all(data)
                if ind:
                    mtf_indicators[label] = ind
            except Exception as e:
                self.logger.warning(f"⚠️ Indicator calc failed for {label}: {e}")

        if "entry" not in mtf_indicators:
            return {"error": "فشل حساب المؤشرات"}

        is_backtest_mode_early = any(
            isinstance(d, dict) and d.get("source") == "backtest"
            for d in mtf_data.values()
        )

        # ═══ وضع التحليل متعدد المراحل (Multi-Pass) - اقتراح المستخدم
        # لمعالجة "Lost in the Middle" - يتفرّع هنا كلياً عن المسار
        # القديم أحادي الطلب، ثم يمر بنفس طبقات التحقق البرمجية
        # (BOS check, candle audit, wick check) بالأسفل. ═══
        if use_multi_pass:
            from multi_pass_analysis import MultiPassAnalysis
            mp = MultiPassAnalysis(self)
            # ⚠️ استخراج end_ts من آخر شمعة بالـEntry TF - يضمن أن كل
            # فريمات الـHTF (Weekly/Daily/4H/1H) تُجلب منتهية عند نفس
            # اللحظة بالضبط بوضع الباك تيست (منع تسريب مستقبلي - نفس
            # مبدأ KnownSetupsFinder._fetch_historical_up_to الأصلي)
            entry_ts_list = mtf_data.get("entry", {}).get("timestamps", [])
            end_ts = entry_ts_list[-1] if entry_ts_list and is_backtest_mode_early else None
            ai_result = mp.run(
                symbol, timeframe, mtf_data, mtf_indicators,
                is_backtest=is_backtest_mode_early, end_ts=end_ts,
            )
            prompt = None  # لا يوجد prompt واحد بهذا الوضع (لأجل _resolve_with_consensus لاحقاً)
            is_backtest_mode = is_backtest_mode_early
            signal_schema = None
        else:
            # ═══ 3) تحميل المعارف ═══
            knowledge, k_tokens = self._load_knowledge()
            learned = self._build_learned_context()
            performance = self._build_performance_context()

            # ═══ 3.5) فحص الأصالة/الزيف (AuthenticityEngine) ═══
            # طبقة تحقق رقمية مسبقة (wash trading, حجم مشبوه...) - أدلة
            # صريحة تُحقن بالـ prompt لدعم قرار الـ AI بأرقام فعلية بدل
            # الاعتماد فقط على "فهمه" اللغوي لقواعد الدستور.
            authenticity_report = {}
            try:
                for label, data in mtf_data.items():
                    if isinstance(data, dict) and "closes" in data:
                        authenticity_report[label] = self.authenticity.build_authenticity_report(data)
            except Exception as e:
                self.logger.warning(f"⚠️ Authenticity check failed: {e}")

            # ═══ 4) بناء Prompt ═══
            prompt = self._build_prompt(
                symbol, timeframe,
                mtf_data, mtf_indicators,
                knowledge, learned, performance,
                market_snapshot,
                authenticity_report,
            )

            is_backtest_mode = is_backtest_mode_early

            # ═══ 5) AI يحلل - مع Schema صارم يفرض بنية JSON ثابتة 100% ═══
            # يحل مشكلة عدم استقرار الشكل (confidence كرقم مرة وكـ dict
            # مرة أخرى) بشكل قاطع من مستوى الـ API - لا اعتماد على "فهم"
            # النموذج لتعليمات الصيغة، البنية مفروضة هيكلياً.
            signal_schema = get_signal_schema(is_backtest=is_backtest_mode)
            ai_result = self.ai.query_json(prompt, response_schema=signal_schema)

            # ═══ 5.2) طبقة تطبيع احتياطية ═══
            # حماية إضافية إذا انتقل الـ fallback لمزود لا يدعم responseSchema
            # (Groq/OpenRouter/SambaNova) - توحّد شكل confidence/signal/prices
            ai_result = normalize_signal_dict(ai_result)

            # ═══ 5.3) إجماع تلقائي عند القرارات "الحرجة" (Auto-Consensus) ═══
            # اختبارات فعلية (consistency_test.py) أثبتت أن القرارات بمنطقة
            # ثقة 60-78% هي الأكثر عرضة لعدم استقرار حقيقي (BUY في محاولة،
            # SELL في التالية على نفس البيانات بالضبط). بدل تصديق محاولة
            # واحدة بهذه المنطقة الحرجة، نشغّل محاولات إضافية ونطلب إجماع.
            # ⚠️ غير مدعوم بوضع multi_pass حالياً (كل مرحلة معقدة كفاية،
            # وسيُضاف لاحقاً إذا ثبتت فعاليته بالاختبار).
            if (
                Config.AUTO_CONSENSUS_ENABLED
                and isinstance(ai_result, dict)
                and ai_result.get("signal") in ("BUY", "SELL", "BUY_LIMIT", "SELL_LIMIT")
                and isinstance(ai_result.get("confidence"), (int, float))
                and Config.BORDERLINE_CONFIDENCE_LOW <= ai_result["confidence"] <= Config.BORDERLINE_CONFIDENCE_HIGH
            ):
                ai_result = self._resolve_with_consensus(
                    ai_result, prompt, signal_schema
                )

        # ═══ 5.45) تدقيق "هلوسة لون الشمعة" - إصلاح خطأ حقيقي موثّق ═══
        # اكتُشف فعلياً بالباك تيست: النموذج وصف الشمعة الأخيرة بعكس
        # لونها الحقيقي تماماً (O=2929.0 H=3031.0 L=2886.7 C=2904.9 -
        # هابطة فعلياً - وُصفت كـ"صاعدة قوية body_pct~80%") مرتين على
        # صفقتين منفصلتين، وبُني عليها bias/signal بالكامل. هذا ليس
        # خطأ استراتيجي (تفسير غلط) بل هلوسة بحقيقة أساسية (لون
        # الشمعة) قبل أي تحليل - أخطر من خطأ BOS لأنه يفسد الأساس
        # الذي يُبنى عليه كل شيء لاحقاً. يعمل حتى على HOLD (ما دام
        # فيه حقل last_candle_report) لأنه فحص دقة قراءة، لا قرار.
        if isinstance(ai_result, dict):
            try:
                candle_audit = self.authenticity.audit_last_candle_report(
                    ai_result, mtf_data.get("entry", {})
                )
                ai_result["last_candle_audit"] = candle_audit
                if candle_audit.get("checked") and not candle_audit.get("valid", True):
                    self.logger.warning(
                        f"🚫 هلوسة لون/قيم الشمعة الأخيرة مُكتشفة: "
                        f"{candle_audit.get('issues')}"
                    )
                    if ai_result.get("signal") in ("BUY", "SELL", "BUY_LIMIT", "SELL_LIMIT"):
                        ai_result["signal"] = "HOLD"
                        ai_result["reason"] = (
                            "تم رفض الإشارة تلقائياً: البوت وصف بيانات "
                            "الشمعة الأخيرة بشكل خاطئ (هلوسة أساسية بالبيانات "
                            f"لا مجرد خطأ تفسير): {candle_audit.get('issues')}"
                        )
            except Exception as e:
                self.logger.warning(f"⚠️ Last candle audit error: {e}")

        # ═══ 5.47) كشف "الهلوسة الانتقائية" (ذكر فتيل واحد فقط،
        # تجاهل الفتيل المعاكس بنفس الحجم تقريباً) - إصلاح خطأ حقيقي
        # موثّق: النموذج بنى قرار BUY على "فتيل رفض سفلي طويل 24.1"
        # متجاهلاً أن الفتيل العلوي كان بنفس الحجم تقريباً (18.41) -
        # الشمعة كانت دوجي حقيقي (تردد)، لا hammer/spring نظيف. كل رقم
        # مذكور كان صحيحاً، لكن العرض انتقائي ومضلل. لا يرفض الإشارة
        # فوراً (قد يكون فعلاً hammer حقيقي بحالات أخرى) لكن يُخفّض
        # الثقة ويُسجَّل كتحذير صريح للمراجعة. ═══
        if isinstance(ai_result, dict) and ai_result.get("signal") in ("BUY", "SELL", "BUY_LIMIT", "SELL_LIMIT"):
            try:
                wick_check = self.authenticity.detect_selective_wick_citation(
                    ai_result, mtf_data.get("entry", {})
                )
                ai_result["selective_wick_check"] = wick_check
                if wick_check.get("suspicious"):
                    self.logger.warning(
                        f"⚠️ هلوسة انتقائية محتملة بذكر الفتيل: {wick_check.get('details')}"
                    )
                    if isinstance(ai_result.get("confidence"), (int, float)):
                        old_conf = ai_result["confidence"]
                        ai_result["confidence"] = max(0, old_conf - 15)
                        ai_result["confidence_penalty_reason"] = (
                            "خُفّضت الثقة 15 نقطة: " + wick_check["details"]
                        )
            except Exception as e:
                self.logger.warning(f"⚠️ Selective wick check error: {e}")

        # ═══ 5.5) تدقيق نهائي على الأسعار (كشف الهلوسة) ═══
        # يتحقق أن كل سعر (entry/sl/tp) صادر فعلياً من مدى الشموع المرسلة
        if isinstance(ai_result, dict) and ai_result.get("signal") in ("BUY", "SELL", "BUY_LIMIT", "SELL_LIMIT"):
            try:
                audit = self.authenticity.audit_signal_prices(
                    ai_result, mtf_data.get("entry", {})
                )
                if not audit.get("valid", True):
                    self.logger.warning(
                        f"⚠️ Price audit failed: {audit.get('issues')}"
                    )
                    ai_result["price_audit"] = audit
                    ai_result["signal"] = "HOLD"
                    ai_result["reason"] = (
                        "تم رفض الإشارة تلقائياً: أسعار غير واقعية "
                        f"(خارج مدى البيانات الفعلية): {audit.get('issues')}"
                    )
                else:
                    ai_result["price_audit"] = audit
            except Exception as e:
                self.logger.warning(f"⚠️ Price audit error: {e}")

        # ═══ 5.6) تحقق ميكانيكي مستقل من BOS (قسم
        # [BOS_OB_DIRECTIONAL_INTEGRITY]) - أهم إصلاح بعد خطأ حقيقي
        # مُوثّق: الـ AI أصدر SELL مدّعياً "فشل follow-through" لكسر
        # صاعد، بينما 3 شموع متتالية أغلقت فعلياً متجاوزة المستوى
        # المكسور (تحقق فعلي بالأرقام). النص بالدستور وحده أثبت أنه
        # غير كافٍ - النموذج يقدر "يذكر" الفحص المطلوب بينما يقرأ
        # الأرقام بشكل غير أمين ليبرر قراراً اتخذه مسبقاً. هذا الفحص
        # مستقل 100% عن أي نص يولّده الـ AI - يحسب اتجاه آخر BOS
        # الحقيقي رياضياً من نفس بيانات الشموع، ويرفض تلقائياً أي
        # إشارة تعاكسه بدون مبرر رقمي حقيقي. ═══
        if isinstance(ai_result, dict) and ai_result.get("signal") in ("BUY", "SELL", "BUY_LIMIT", "SELL_LIMIT"):
            try:
                bos_check = self.authenticity.cross_check_bos_reconciliation(
                    ai_result, mtf_data.get("entry", {})
                )
                ai_result["bos_mechanical_check"] = bos_check
                if bos_check.get("flagged"):
                    self.logger.warning(
                        f"🚫 BOS cross-check FLAGGED: {bos_check['reason']}"
                    )
                    ai_result["signal"] = "HOLD"
                    ai_result["reason"] = (
                        "تم رفض الإشارة تلقائياً (BOS Cross-Check، قسم "
                        "24): " + bos_check["reason"]
                    )
            except Exception as e:
                self.logger.warning(f"⚠️ BOS cross-check error: {e}")

        # ═══ 5.6b) حراسة السلامة: لا BUY/SELL بدون stop_loss رقمي حقيقي ═══
        # ⚠️ إصلاح باگ حرج جداً مُكتشف بالاختبار الفعلي (2026-07-03):
        # رد فعلي كامل موثّق: النموذج أعطى signal=BUY بثقة 83% مع
        # stop_loss=None بالكامل (لا ستوب لوس إطلاقاً!) بوضع الباك تيست
        # - رغم أنه ذكر مستوى الإبطال بوضوح تام بحقل "invalidation"
        # النصي («A 4H candle body close below 2920.00»). السبب الجذري:
        # "stop_loss" كان موجوداً بالـschema لكن غير مُدرَج بـ"required"
        # (أُصلح بالـschema نفسه بـmulti_pass_analysis.py لوضع الباك
        # تيست، حيث BUY/SELL دائماً)، لكن بالوضع الحي HOLD ما زال ممكناً
        # فلا يصح فرض stop_loss بالـschema هناك (سيُجبر النموذج على
        # اختلاق رقم حتى بحالة HOLD التي لا تحتاج له أصلاً). لذلك: طبقة
        # حماية إضافية مستقلة هنا (لا تعتمد على الـschema وحده) - أي
        # BUY/SELL بلا stop_loss رقمي حقيقي (None أو غير رقم) يُرفض
        # تلقائياً ويتحول HOLD فوراً، بغض النظر عن مصدر الطلب (باك تيست
        # أو حي) - **بوت تداول بلا ستوب لوس هو خطر مالي حقيقي غير مقبول
        # مطلقاً**، هذا الفحص لا يُستثنى تحت أي ظرف.
        if isinstance(ai_result, dict) and ai_result.get("signal") in ("BUY", "SELL", "BUY_LIMIT", "SELL_LIMIT"):
            sl_value = ai_result.get("stop_loss")
            entry_value = ai_result.get("entry")
            tp_value = ai_result.get("tp")
            sig = ai_result.get("signal")
            rejection_reason = None

            if not isinstance(sl_value, (int, float)) or sl_value <= 0:
                rejection_reason = (
                    f"لا يمكن إصدار BUY/SELL بلا stop_loss رقمي صالح "
                    f"(القيمة المستلمة: {sl_value!r})"
                )
            # ⚠️ إضافة استباقية (نفس جلسة اكتشاف باگ الـstop_loss الفارغ):
            # فحصنا فوراً "ماذا لو كان stop_loss موجوداً كرقم لكن بالجهة
            # المعاكسة (BUY وSL فوق الدخول، أو SELL وSL تحته)؟" - هذا
            # أخطر من الغياب الكامل لأنه يمر بصمت عبر `abs()` بحسابات
            # `risk_manager.py` (يحسب "مخاطرة" وكأنها طبيعية رغم كونها
            # اتجاهاً معكوساً بالكامل يُبطل معنى "وقف الخسارة" أصلاً).
            # نفس المنطق يُطبَّق على TP (يجب أن يكون بالاتجاه الصحيح من
            # الدخول، لا معاكساً). فحص رياضي بحت، لا يعتمد على تفسير AI.
            elif isinstance(entry_value, (int, float)) and entry_value > 0:
                # ⚠️ BUY_LIMIT/SELL_LIMIT تتبع نفس منطق الاتجاه
                # المنطقي لـ BUY/SELL بالضبط (أوامر معلقة -
                # الفرق الوحيد هو التنفيذ الفوري مقابل المعلق)، فلا
                # نريد ثغرة حيث يتجاوز BUY_LIMIT هذا الحراس.
                is_buy_dir = sig in ("BUY", "BUY_LIMIT")
                is_sell_dir = sig in ("SELL", "SELL_LIMIT")
                if is_buy_dir and sl_value >= entry_value:
                    rejection_reason = (
                        f"{sig} لكن stop_loss ({sl_value}) ليس تحت entry ({entry_value}) "
                        "- اتجاه SL معكوس، غير منطقي إطلاقاً"
                    )
                elif is_sell_dir and sl_value <= entry_value:
                    rejection_reason = (
                        f"{sig} لكن stop_loss ({sl_value}) ليس فوق entry ({entry_value}) "
                        "- اتجاه SL معكوس، غير منطقي إطلاقاً"
                    )
                elif isinstance(tp_value, (int, float)) and tp_value > 0:
                    if is_buy_dir and tp_value <= entry_value:
                        rejection_reason = (
                            f"{sig} لكن tp ({tp_value}) ليس فوق entry ({entry_value}) "
                            "- اتجاه TP معكوس، غير منطقي إطلاقاً"
                        )
                    elif is_sell_dir and tp_value >= entry_value:
                        rejection_reason = (
                            f"{sig} لكن tp ({tp_value}) ليس تحت entry ({entry_value}) "
                            "- اتجاه TP معكوس، غير منطقي إطلاقاً"
                        )

            if rejection_reason:
                self.logger.warning(f"🚫 SAFETY GUARD: {rejection_reason} - تُرفض تلقائياً وتتحول HOLD")
                ai_result["signal"] = "HOLD"
                ai_result["reason"] = f"تم رفض الإشارة تلقائياً (Safety Guard): {rejection_reason}"

        # ═══ 5.7) طبقة التحقق الشاملة (Verification Layer) ═══
        # يفحص كل سعر/ادعاء بالرد مقابل البيانات الحقيقية، ويتحقق من
        # وجود narrative/archetype (طبقة الفهم الشامل) - هذا يجاوب على
        # سؤال "هل عم يحلل صح أو عم يشلف؟" برقم واضح قابل للمراجعة.
        verification = None
        try:
            verification = self.verifier.verify(ai_result, mtf_data)
            # ⚠️ إصلاح باگ حقيقي (2026-07-03): score_pct=None يعني "لا
            # يوجد ادعاء سعري أصلاً للتحقق منه" (مثلاً توقف HOLD مبكر
            # عند Gate - سلوك صحيح ومقصود، راجع تعليق الإصلاح المطابق
            # بـverification_layer.py) - يجب عدم معاملته كـ"0% فشل"،
            # وإلا نطلق إنذاراً كاذباً بكل مرة يتوقف البوت بشكل سليم.
            if verification["score_pct"] is not None and verification["score_pct"] < 70:
                self.logger.warning(
                    f"⚠️ Verification Score منخفض: {verification['score_pct']}% "
                    f"- راجع issues: {verification['issues']}"
                )
        except Exception as e:
            self.logger.warning(f"⚠️ Verification layer error: {e}")

        # ═══ 6) تقييم المخاطر ═══
        risk = self.risk_manager.evaluate(ai_result)

        # ═══ 7) حفظ (فقط للتحليل الحي، مش الباك تست) ═══
        saved_signal = None
        if not custom_data:
            if isinstance(ai_result, dict) and ai_result.get("signal") in ("BUY", "SELL", "BUY_LIMIT", "SELL_LIMIT"):
                saved_signal = self.signal_repo.add_signal(
                    symbol=symbol,
                    timeframe=timeframe,
                    indicators=mtf_indicators.get("entry"),
                    ai_analysis=ai_result,
                )

            self.memory.store_event({
                "type": "analysis_v3",
                "symbol": symbol,
                "timeframe": timeframe,
                "signal": ai_result,
                "risk": risk,
                "verification_score": verification["score_pct"] if verification else None,
                "saved_signal_id": saved_signal["id"] if saved_signal else None,
            })

        entry_dataset = mtf_data.get("entry", {}) if isinstance(mtf_data, dict) else {}
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "exchange": entry_dataset.get("source"),
            "analysis_time": dual_time(),
            "data_cutoff": closed_candle_stamp(entry_dataset),
            "closed_candles_only": bool(entry_dataset.get("closed_only")),
            "indicators": mtf_indicators,
            "ai_analysis": ai_result,
            "risk": risk,
            "verification": verification,
            "saved_signal": saved_signal,
            # ⚠️ k_tokens غير مُعرَّف بوضع multi_pass (كل مرحلة تحمّل
            # جزءاً مختلفاً من الدستور عبر knowledge_sections.py، لا
            # يوجد "عدد توكن دستور واحد" ذو معنى بهذا الوضع)
            "knowledge_tokens_used": k_tokens if not use_multi_pass else "multi_pass_variable",
            "cost": f"~${self.ai.total_cost:.4f}",
        }

    # ══════════════════════════════════════════════
    #  AUTO-CONSENSUS (لمعالجة عدم استقرار القرارات الحرجة)
    # ══════════════════════════════════════════════

    def _resolve_with_consensus(self, first_result, prompt, signal_schema):
        """
        يشغّل محاولات إضافية على نفس الـ prompt بالضبط عند وقوع القرار
        بمنطقة ثقة حرجة (60-78%)، ويقرر النتيجة النهائية بتصويت الأغلبية:
          - لو الأغلبية (أكثر من نصف المحاولات) اتفقت على نفس الاتجاه
            (BUY/SELL) -> اعتماد اتجاه الأغلبية، والثقة = متوسط محاولات
            الأغلبية فقط (وليس كل المحاولات - محاولة الأقلية المختلفة
            لا تدخل بحساب الثقة النهائية)
          - لو تعادل تام (كل محاولة نتيجة مختلفة عن الباقي، لا أغلبية
            واضحة) -> هذا إثبات فعلي أن الإعداد غامض حقيقة -> HOLD

        ⚠️ إصلاح خطأ حقيقي مُكتشف بالباك تيست الفعلي (يوليو 2026):
        القاعدة القديمة كانت تشترط "إجماع كامل 100%" (كل محاولة بلا
        استثناء) وإلا HOLD فوراً - هذا تشدد زائد أثبت الاختبار أنه
        يرمي قرارات كانت صحيحة فعلياً بمجرد اختلاف محاولة واحدة من
        ثلاثة (مثال حقيقي: محاولات [SELL, BUY, SELL] على صفقة كانت
        فعلياً SELL بحركة +24.9% - القرار الصحيح كان بأغلبية 2/3،
        لكن القاعدة القديمة رمته لـHOLD لمجرد وجود محاولة واحدة مختلفة
        - وهذا تذبذب احتمالي طبيعي بالنموذج، وليس دليل غموض حقيقي في
        الإعداد نفسه). قاعدة الأغلبية أكثر واقعية إحصائياً مع نفس مبدأ
        الحذر: تعادل تام حقيقي (بدون أي أغلبية) لسا يتراجع لـHOLD.
        """
        results = [first_result]
        self.logger.info(
            f"🔀 قرار بمنطقة حرجة (confidence={first_result.get('confidence')}%) "
            f"- تشغيل {Config.AUTO_CONSENSUS_EXTRA_RUNS} محاولة إجماع إضافية..."
        )

        for i in range(Config.AUTO_CONSENSUS_EXTRA_RUNS):
            try:
                self.ai.clear_cache()  # لازم وإلا رح يرجع نفس الرد المخزّن حرفياً
                extra = self.ai.query_json(prompt, response_schema=signal_schema)
                extra = normalize_signal_dict(extra)
                if isinstance(extra, dict) and "error" not in extra:
                    results.append(extra)
            except Exception as e:
                self.logger.warning(f"⚠️ Consensus run {i+1} failed: {e}")

        signals = [r.get("signal") for r in results if isinstance(r, dict)]
        total_runs = len(signals)

        # ── عدّ الأصوات لكل اتجاه (BUY/SELL فقط - HOLD لا يُحسب كـ"اتجاه") ──
        from collections import Counter
        vote_counts = Counter(s for s in signals if s in ("BUY", "SELL"))

        majority_signal, majority_count = (None, 0)
        if vote_counts:
            majority_signal, majority_count = vote_counts.most_common(1)[0]

        # أغلبية حقيقية = أكثر من نصف المحاولات (وليس فقط الأكثر تكراراً
        # بتعادل - مثال: [BUY, SELL, HOLD] كل واحد له صوت واحد، هذا ليس
        # أغلبية حقيقية رغم أن Counter قد يُرجع أولهم "الأكثر شيوعاً")
        has_real_majority = majority_count > total_runs / 2

        if has_real_majority:
            agreeing_results = [
                r for r in results
                if isinstance(r, dict) and r.get("signal") == majority_signal
            ]
            confidences = [
                r.get("confidence") for r in agreeing_results
                if isinstance(r.get("confidence"), (int, float))
            ]
            avg_confidence = round(sum(confidences) / len(confidences)) if confidences else first_result.get("confidence")
            # نأخذ كل الحقول من أول محاولة اتفقت مع الأغلبية (وليس بالضرورة
            # first_result - لو first_result نفسه كان الأقلية المخالفة)
            final = agreeing_results[0].copy()
            final["confidence"] = avg_confidence
            final["consensus_check"] = {
                "runs": total_runs,
                "agreement": "FULL" if majority_count == total_runs else "MAJORITY",
                "all_signals": signals,
                "note": (
                    f"أغلبية {majority_count}/{total_runs} محاولات اتفقت على "
                    f"{majority_signal} - ثقة = متوسط محاولات الأغلبية فقط"
                ),
            }
            self.logger.info(
                f"✅ أغلبية {majority_count}/{total_runs} على {majority_signal} "
                f"- ثقة نهائية: {avg_confidence}%"
            )
            return final
        else:
            # تعادل تام حقيقي (لا يوجد اتجاه يحصل على أغلبية واضحة) -
            # إثبات فعلي أن الإعداد غامض حقيقة
            final = dict(first_result)
            final["signal"] = "HOLD"
            final["confidence"] = min(
                c for r in results if isinstance(r, dict)
                for c in [r.get("confidence", 50)] if isinstance(c, (int, float))
            ) if any(isinstance(r, dict) and isinstance(r.get("confidence"), (int, float)) for r in results) else 50
            final["consensus_check"] = {
                "runs": total_runs,
                "agreement": "TRUE_TIE",
                "all_signals": signals,
                "note": (
                    "تعادل تام حقيقي بين المحاولات (لا يوجد اتجاه بأغلبية "
                    f"واضحة: {signals}) - تم التراجع لـ HOLD تلقائياً لأن "
                    "هذا يثبت أن الإعداد غامض حقيقة."
                ),
            }
            final["reason"] = final["consensus_check"]["note"]
            self.logger.warning(
                f"⚠️ تعادل تام بين المحاولات {signals} (لا أغلبية) - تم التراجع لـ HOLD"
            )
            return final


    # ══════════════════════════════════════════════
    #  PROMPT BUILDER
    # ══════════════════════════════════════════════

    def _build_prompt(self, symbol, timeframe,
                      mtf_data, mtf_indicators,
                      knowledge, learned, performance,
                      market_snapshot=None,
                      authenticity_report=None):

        parts = []

        if knowledge:
            parts.append(knowledge)

        if learned:
            parts.append(f"\n── LEARNED PATTERNS ──\n{learned}")

        if performance:
            parts.append(f"\n── TRACK RECORD ──\n{performance}")

        if authenticity_report:
            parts.append(
                "\n── AUTHENTICITY PRE-CHECKS (نتائج فحص مسبق رياضي) ──\n"
                "هذه أرقام محسوبة فعلياً من البيانات قبل وصولها إليك. استخدمها\n"
                "كأدلة داعمة إضافية عند تطبيق قسم [AUTHENTICITY_ENGINE] بالدستور\n"
                "(خصوصاً فحص Wash Trading في القسم 21.6). لا تتجاهلها:\n"
                f"{json.dumps(authenticity_report, ensure_ascii=False, default=str)}"
            )

        parts.append(f"\n{'='*40}\nMARKET: {symbol}\n{'='*40}")

        tf_order = ["macro", "context", "entry"]
        candle_counts = {
            "entry": Config.AI_CANDLES_ENTRY,
            "context": Config.AI_CANDLES_CONTEXT,
            "macro": Config.AI_CANDLES_MACRO,
        }
        labels_map = {
            "macro": "MACRO",
            "context": "CONTEXT",
            "entry": "ENTRY",
        }

        for label in tf_order:
            if label not in mtf_indicators or label not in mtf_data:
                continue

            ind = mtf_indicators[label]
            data = mtf_data[label]
            n = candle_counts.get(label, 20)

            parts.append(
                f"\n── {labels_map[label]}: {ind['tf']} ──\n"
                f"{self.ta.compact_summary(ind)}\n"
                f"\nCandles:\n"
                f"{self._format_candles(data, n)}"
            )

        if market_snapshot:
            snapshot_text = self._format_market_snapshot(market_snapshot)
            if snapshot_text:
                parts.append(snapshot_text)

        # ═══ Detect backtest mode ═══
        # ═══ Detect backtest mode ═══
        is_backtest = any(
            isinstance(d, dict) and d.get("source") == "backtest"
            for d in mtf_data.values()
        )

        if is_backtest:
            instruction = """

BACKTEST MODE - OVERRIDE ACTIVE:
1. You MUST output BUY or SELL. HOLD is NOT allowed.
2. Even if confidence is 30%, pick BUY or SELL.
3. Analyze fully: structure, OBs, FVGs, liquidity.
4. Determine: is NEXT move more likely UP or DOWN?
5. If UP = BUY. If DOWN = SELL. Always with entry/SL/TP.
6. R:R must be 3:1 minimum. Single TP target.
7. If 50/50: pick direction of higher TF structure.
8. Knowledge base ANALYSIS rules apply. HOLD rule is paused.

Output ONLY valid JSON:
{
  "visual_silhouette": "MANDATORY (Section 26.1) - write this FIRST,
                before anything else: describe the overall shape of the
                whole visible chart in one/two sentences as if drawn with
                one continuous line ignoring wicks (staircase up? rounded
                top? V-shaped spike and recovery? flat range with a tail?),
                where current price sits within that shape (upper/mid/
                lower third, or exactly at an inflection point), and
                whether the shape's character changed partway through
                (where exactly). This is a holistic visual first-pass,
                like a trader's eye scanning the whole picture before any
                single candle.",
  "last_candle_report": {
                "open": <number>, "high": <number>, "low": <number>,
                "close": <number>,
                "color": "BULLISH if close>open else BEARISH - purely
                          arithmetic, copy the EXACT values of the LAST
                          (most recent) candle from the data given. This
                          is a data-reading accuracy check, not analysis -
                          a documented real failure showed the model
                          describing a candle as bullish body_pct~80%
                          when it was actually bearish body_pct=16.7%.
                          Get this right BEFORE writing narrative below."
  },
  "narrative": "Plain-language story of what has been happening and why
                (Section 23.1) - written BEFORE any mechanical checklist,
                referencing the evolution of structure/volume over the
                last several swings, not just the current bar.",
  "archetype": "Which pattern family this resembles (Section 23.2:
                spring/stop-hunt reversal, exhaustion blow-off, healthy
                pullback, accumulation/distribution range, trap
                continuation, or none-clearly) and how cleanly it fits.",
  "bos_reconciliation": "MANDATORY (Section 24.3): state the direction
                of the most recent CONFIRMED BOS (UP/DOWN/none) found by
                scanning the last 10-15 candles for a genuine displacement
                (range>=2xATR, body_pct>60-70%, vol_ratio>1.5) that broke
                a prior swing high/low. State whether your final signal
                AGREES or CONFLICTS with that BOS direction. If CONFLICTS,
                cite SPECIFIC evidence (a candle index, a price, a volume
                ratio) from Section 21.1 (no trapped-trader fuel) or
                Section 21.2 (failed follow-through) proving that BOS is
                fake/discounted - restating the older trend by itself is
                NOT sufficient justification.",
  "bos_candle_index_from_end": "MANDATORY integer (negative, -1=last
                candle): which candle broke the BOS you cited above.
                A documented real failure showed the model citing a BOS
                from the middle of the window (e.g. candle #42 of 50) as
                'most recent' while a genuinely more recent break (candle
                #49) existed and was completely ignored. Scan candles -1
                through -15 explicitly for the MOST RECENT break before
                answering - do not stop at the first break you visually
                notice if a more recent one exists.",
  "bias": "BULLISH/BEARISH",
  "signal": "BUY/SELL",
  "entry": price,
  "stop_loss": price,
  "tp": price,
  "confidence": 0-100,
  "rr": "1:X",
  "reasoning": "Mechanical verification of the narrative/archetype above:
               specific OB/FVG/liquidity levels, vol_ratios, ATR multiples
               (Section 23.4 step 4) - cite the narrative, don't repeat it.",
  "market_regime": "TRENDING_UP/TRENDING_DOWN/RANGING/VOLATILE",
  "macro_bias": "highest TF direction",
  "structure_analysis": "structure on each TF",
  "smc_zones_found": {
    "order_blocks": [],
    "fvg": [],
    "liquidity": [],
    "bos_choch": []
  },
  "confluence_factors": [],
  "confluence_count": 0,
  "key_levels": [],
  "risks": [],
  "invalidation": "what cancels trade",
  "why_this_direction": "why BUY not SELL or vice versa"
}"""
        else:
            instruction = """

Apply your knowledge base to this market data.
Output ONLY valid JSON:
{
  "visual_silhouette": "MANDATORY (Section 26.1) - write this FIRST,
                before anything else: describe the overall shape of the
                whole visible chart in one/two sentences as if drawn with
                one continuous line ignoring wicks (staircase up? rounded
                top? V-shaped spike and recovery? flat range with a tail?),
                where current price sits within that shape (upper/mid/
                lower third, or exactly at an inflection point), and
                whether the shape's character changed partway through
                (where exactly). This is a holistic visual first-pass,
                like a trader's eye scanning the whole picture before any
                single candle.",
  "last_candle_report": {
                "open": <number>, "high": <number>, "low": <number>,
                "close": <number>,
                "color": "BULLISH if close>open else BEARISH - purely
                          arithmetic, copy the EXACT values of the LAST
                          (most recent) candle from the data given. This
                          is a data-reading accuracy check, not analysis -
                          a documented real failure showed the model
                          describing a candle as bullish body_pct~80%
                          when it was actually bearish body_pct=16.7%.
                          Get this right BEFORE writing narrative below."
  },
  "narrative": "Plain-language story of what has been happening and why
                (Section 23.1) - written BEFORE any mechanical checklist,
                referencing the evolution of structure/volume over the
                last several swings, not just the current bar.",
  "archetype": "Which pattern family this resembles (Section 23.2:
                spring/stop-hunt reversal, exhaustion blow-off, healthy
                pullback, accumulation/distribution range, trap
                continuation, or none-clearly) and how cleanly it fits.",
  "bos_reconciliation": "MANDATORY (Section 24.3): state the direction
                of the most recent CONFIRMED BOS (UP/DOWN/none) found by
                scanning the last 10-15 candles for a genuine displacement
                (range>=2xATR, body_pct>60-70%, vol_ratio>1.5) that broke
                a prior swing high/low. State whether your final signal
                AGREES or CONFLICTS with that BOS direction. If CONFLICTS,
                cite SPECIFIC evidence (a candle index, a price, a volume
                ratio) from Section 21.1 (no trapped-trader fuel) or
                Section 21.2 (failed follow-through) proving that BOS is
                fake/discounted - restating the older trend by itself is
                NOT sufficient justification.",
  "bos_candle_index_from_end": "MANDATORY integer (negative, -1=last
                candle): which candle broke the BOS you cited above.
                A documented real failure showed the model citing a BOS
                from the middle of the window (e.g. candle #42 of 50) as
                'most recent' while a genuinely more recent break (candle
                #49) existed and was completely ignored. Scan candles -1
                through -15 explicitly for the MOST RECENT break before
                answering - do not stop at the first break you visually
                notice if a more recent one exists.",
  "bias": "BULLISH/BEARISH/NEUTRAL",
  "signal": "BUY/SELL/HOLD",

  "entry": price,
  "stop_loss": price,
  "tp": price,
  "confidence": 0-100,
  "rr": "1:X",
  "reasoning": "Mechanical verification of the narrative/archetype above:
               specific OB/FVG/liquidity levels, vol_ratios, ATR multiples
               (Section 23.4 step 4) - cite the narrative, don't repeat it.",
  "market_regime": "TRENDING_UP/TRENDING_DOWN/RANGING/VOLATILE",
  "macro_bias": "highest TF direction",
  "structure_analysis": "structure on each TF",
  "smc_zones_found": {
    "order_blocks": [],
    "fvg": [],
    "liquidity": [],
    "bos_choch": []

  },
  "confluence_factors": [],
  "key_levels": [],
  "risks": [],
  "invalidation": "what cancels trade"
}"""

        parts.append(instruction)
        return "\n".join(parts)

    # ══════════════════════════════════════════════
    #  QUICK ANALYSIS
    # ══════════════════════════════════════════════

    def quick_analysis(self, symbol=None, timeframe=None, exchange=None):
        symbol = symbol or Config.DEFAULT_SYMBOL
        timeframe = timeframe or Config.DEFAULT_TIMEFRAME
        data = self.data_manager.get_ohlcv(
            symbol, timeframe, limit=250, output_format="dict",
            exchange=exchange, closed_only=True,
            allow_fallback=(exchange in (None, "auto")),
        )
        if not data:
            return {"error": "فشل جلب البيانات"}
        ind = self.ta.compute_all(data)
        if not ind:
            return {"error": "بيانات غير كافية"}
        return {"indicators": ind, "summary": self.ta.compact_summary(ind)}

    # ══════════════════════════════════════════════
    #  CHAT
    # ══════════════════════════════════════════════

    def chat(self, message):
        knowledge, _ = self._load_knowledge()
        learned = self._build_learned_context(limit=10)

        prompt = f"User: {message}\n\n"
        if knowledge:
            prompt += f"{knowledge}\n\n"
        if learned:
            prompt += f"Learned:\n{learned}\n\n"
        prompt += "Respond based on the knowledge above."
        return self.ai.query(prompt, max_tokens=2048)

    def backtest(self, strategy_text, symbol=None, timeframe=None):
        data = self.data_manager.get_ohlcv(
            symbol or Config.DEFAULT_SYMBOL,
            timeframe or Config.DEFAULT_TIMEFRAME,
            output_format="dict"
        )
        if not data:
            return {"error": "فشل"}
        closes = [round(c, 2) for c in data["closes"][-50:]]
        prompt = f"""Backtest: {strategy_text}
Last 50 closes: {closes}
JSON: {{"win_rate":"%","trades":0,"avg_rr":"1:X","strengths":[],"weaknesses":[]}}"""
        return self.ai.query_json(prompt)

    def self_evaluate(self):
        stats = self.memory.get_stats()
        perf = self._build_performance_context()
        prompt = f"""Evaluate: {json.dumps(stats, default=str)}
Performance: {perf}
JSON: {{"strengths":[],"weaknesses":[],"suggestions":[],"grade":"A-F"}}"""
        return self.ai.query_json(prompt, max_tokens=1024)

    def learn_text(self, text):
        return self.learning_manager.learn_text(text)

    def search_knowledge(self, keyword):
        return self.learning_manager.search(keyword)

    def get_all_knowledge(self):
        return self.learning_manager.all_knowledge()

    def get_proposed_signals(self):
        return self.signal_repo.get_all()

    def get_unchecked_signals(self):
        return self.signal_repo.get_unchecked_signals()
