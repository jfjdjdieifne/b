# العقل الخارق للتريكس الفردي — Grandmaster Individual Trix AI

محرك ذكاء اصطناعي واحتمالات رياضية مستقل للعبة **التريكس الفردي (4 ممالك — 5 طلبات)** مكتوب بالكامل ببايثون نقي (Python 3.11+ بدون أي مكتبات خارجية).

## المعمارية الرياضية
- **`cards.py`**: تمثيل فائق السرعة بـ `52-bit Bitmask` وجداول بحث مسبقة.
- **`engine.py`**: قوانين التريكس الفردي الكاملة (شيخ الكبة، البنات، الديناري، اللطوش، التريكس + التدبيل + الإنهاء المبكر + 4 ممالك / 20 جولة).
- **`belief.py`**: متتبع أوراق واستنتاج فراغات (`Void Inference` + `Trix Pass Inference` + `Doubling Lock`) مع حل توافقي مغلق (`4-Bucket Combinatorial Solver`) يحسب الاحتمال الهامشي الدقيق لكل ورقة ويولّد توزيعات متسقة بدون رفض (`Zero-Rejection Sampling`).
- **`endgame.py`**: حلّال نهايات دقيق (`Exact MaxN`) مع تقليم الأوراق المتكافئة (`Adjacent-Card Equivalence Pruning`) وجداول حفظ الحالات (`Transposition Tables`) وقطع الحد الأعلى الدقيق.
- **`heuristics.py`**: سياسات تكتيكية حية تتابع الفراغات لحظياً + خصوم مرجعيون (`RandomAI`, `IntermediateAI`, `ProHeuristicAI`).
- **`grandmaster.py`**: المحرك الرئيسي (`GrandmasterAI`) بدمج **PIMC + Exact Endgame + CVaR 20% + Leader Targeting + Optimal-Stopping Contract Selector + Exposed-Information Doubling Calculator**.
- **`web_app.py` + `static/index.html`**: ساحة لعب ومختبر تحليل تفاعلي بالعربية (`RTL`) يعمل في المتصفح مع وضع التحدي، وضع المشاهدة الحي، ومختبر الورق الكارثي.

## التشغيل السريع (بدون تثبيت أي حزم!)

### 1) تشغيل الساحة التفاعلية في المتصفح
```bash
python3 -m trix_ai.cli serve --host 0.0.0.0 --port 8000
```
ثم افتح المتصفح على: `http://localhost:8000`

### 2) تشغيل اختبارات البطولة (4 ممالك / 20 جولة لكل مباراة)
```bash
# ضد 3 لاعبين متوسطين
python3 -m trix_ai.cli benchmark --opponent intermediate --matches 10 --level tournament

# ضد 3 خبراء قواعد (ProHeuristicAI)
python3 -m trix_ai.cli benchmark --opponent pro --matches 10 --level tournament
```

### 3) اختبار الورق الكارثي (Bad-Hand Torture Test)
```bash
python3 -m trix_ai.cli torture --contract queens --trials 8
python3 -m trix_ai.cli torture --contract diamonds --trials 8
```

### 4) تشغيل الاختبارات الوحدوية والتكاملية
```bash
python3 -m unittest discover -s tests -v
```
