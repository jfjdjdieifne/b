# FIELD RUNNER — PERFORMANCE DIAGNOSIS + PROGRESS PATCH — READY FOR OWNER RETRY

**Date:** 2026-09-28 (Asia/Damascus)
**السبب المختصر:** ليس عالقاً — المحركات المغلقة المُصدَّقة تعمل بحسابات percentile على **تاريخ متمدد كامل لكل شمعة** (عقد O(n²) مقصود: exact empirical percentiles بلا نافذة) + آلة سردية per-bar. على 44,640 شمعة = مليارات التكرارات في Python ⇒ **عشرات الدقائق** طبيعية جداً. لا بطء بسبب بياناتك ولا بسبب ملفاتك.

## 1 — القياس (SYNTHETIC month-scale fixtures — لا بيانات مالك)

n = 22,320 (نصف الشهر) — على آلة البناء — والتقدير ×4 للأجزاء التربيعية على 44,640:

| stage | نصف (22,320) | تقدير الشهر (44,640) |
|---|---|---|
| dynamic_volatility 1.1 (2 trackers) | 16.8s | ~67s |
| fvg 4.2A (tracker + events) | **83.6s** | **~5.6 min** |
| order_flow PROXY 3.1 | 20.6s | ~82s |
| order_flow ACTUAL 3.1 | 19.8s | ~80s |
| absorption 3.2 ×2 | 0.4s | ~2s |
| HTF 5.1 | 3.3s | ~13s |
| swings 2.1A + 2.1B + 2.1C | 3.6s | ~15s |
| liquidity 2.2 | 12.2s | ~49s |
| order_blocks 4.1 | 3.5s | ~14s |
| dealing_range 4.2B | 1.8s | ~7s |
| evidence 6.1A ×2 | ~0s | ~0s |
| **narrative 6.1B ×2** | **94.1s** | **~6.3 min** |
| timeline seal | 1.3s | ~5s |
| **المجموع** | **~4.2 min** | **~17–20 min** |

+ تقرير/مخرجات ~1–2 دقيقة. على Windows (Python أبطأ + مضاد فيروسات + CPU أقدم) المعتاد ×1.5–3 ⇒ **30–60 دقيقة متوقعة للشهر كامل** — «نص ساعة وما خلص» يقع داخل هذا النطاق؛ **سينتهي**. (Primitive مُقسَّم: tracker واحد × 44,640 = 40.6s؛ وعدد الـtrackers في المحركات ~18+.)

## 2 — ماذا تفعل الآن مع التشغيل الجاري؟

- الآلة الحالية **تتقدم بصمت** (المخرجات تُكتب في النهاية فقط) — لا شيء تالف، ولا ملفات نصف مكتوبة. خياران:
  1. **انتظر** — يُرجَّح أن يكمل قريباً؛ أو
  2. **Ctrl+C ثم أعد التشغيل بالـZIP الجديد** — يُظهر كل مرحلة بتوقيتها (موصى به).
- إذا ظهر عندك التنصيب: تأكد من عدم تعليق **تنزيل klines** (بطء شبكتك مع data.binance.vision) — الـZIP الجديد يطبع حالة التنزيل + يوقفه بعد 600 ثانية برسالة تطلب ملفاً محلياً (`--klines-csv`).

## 3 — الـPATCH (runner فقط — لا CLOSED ولا semantics)

1. **سطور تقدّم لكل مرحلة** بتوقيت (inputs → gates → klines → sources → seal → كل محرك على حدة → evidence/narrative → التقارير) + لافتة مسبقة صريحة للتكلفة المتوقعة.
2. **حراسة تنزيل klines**: رسائل بايتات/ثانية + deadline (600s) ⇒ `NETWORK_UNAVAILABLE_OR_DOWNLOAD_TOO_SLOW` مع اسم الملف المحلي المطلوب بدل الانتظار اللانهائي.
3. تسريع glue في التقارير (groupby بدل iterrows — نفس النتائج).
4. لا defaults تغيّرت (`swing_quantile: null`)؛ لا engine جديد؛ لا Reality analysis؛ لا تعديل trading_project.

**الاختبارات:** 31/31 runner tests PASS بعد الرقعة. **MANIFEST** = `7796a73f…1587` (183/183 OK، لم يتغير). **CLOSED tree = NONE changed**.

## 4 — الملفات المعدَّلة (قبل ← بعد)

| file | قبل (v2) | بعد (v3) |
|---|---|---|
| `field_runner/pipeline.py` | `58fe777e…440e5c` | `9774b5e1809d841c…` |
| `field_runner/reporting.py` | `5b7f39b6…d9f20` | `aa2cfbfb3dfe9a62…` |
| `field_runner/runner_btc_may_2026.py` | `a15672ca…df74e` | `ceb6529de0554eda…` |
| `field_runner/binance_kline_downloader.py` | `cb13c80c…6edd` | `a15666c7c59beb87…` |

## 5 — ZIP + الأمر

`deliverables/30_BTC_MAY2026_FIELD_RUNNER_PACKAGE_PROGRESS_PATCHED.zip`
**zip_sha256 = `b35ebcd289e646c32f2f5855e072013473364254bba0c25c62a29829ea9c5dd6`** (729,677 bytes — 205 entries — roundtrip 203/203)

```text
python run_btc_may_2026.py
```

## 6 — خيار مستقبلي (يحتاج قرارك — لم يُنفَّذ)

التسريع الحقيقي للشهر = تغيير **داخل CLOSED** (مثلاً بنية percentile مرتبة، أو `max_history` مُعايَر بعقد موثّق) — هذا تغيير على وحدة مغلقة/مُصدَّقة ويحتاج تفويضاً منفصلاً وإجراء إغلاقك المعتاد. **ممنوع على البيلدر فعله ضمن patch.** إن أردته فهو مشروع مستقل بحدّه.

**STOP.**
