# INTERPRETATION STEP — BINANCE AGGTRADES SCHEMA VERIFICATION

الحالة: **توثيق من المصادر — لا تخمين، لا افتراض**. لم يُلمس أي ملف مشروع.
ملاحظة: تقرير فحص المالك المحلي لم يصل إلى هذه الواجهة (لا يوجد مرفق في workspace)؛
الإجابات أدناه من الوثائق الرسمية + مرساة قياسية محدودة من المرحلة-0 (Pass A فقط،
على الأرشيف الرسمي المُتحقَّق منه zip checksum). قائمة مطابقة للتقرير المحلي في النهاية.

---

## المصادر الأولية

- **[S1] binance/binance-public-data — README.md (الرسمي، نص حرفي مُجلب):**
  https://raw.githubusercontent.com/binance/binance-public-data/master/README.md
- **[S2] Binance Spot API — REST Market Data Endpoints (الرسمي):**
  https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints
- **[S3] Binance Spot API — WebSocket Streams (الرسمي):**
  https://developers.binance.com/docs/binance-spot-api-docs/web-socket-streams
- **[S4] binance-spot-api-docs — CHANGELOG.md (الرسمي)، إدخال 2022-04-12:**
  https://github.com/binance/binance-spot-api-docs/blob/master/CHANGELOG.md#2022-04-12
- **[S5] binance/binance-public-data issue #350 (مستودع Binance الرسمي):**
  https://github.com/binance/binance-public-data/issues/350
- **[S6] مجتمع مطوري Binance الرسمي — From Trades to Agg Trades:**
  https://dev.binance.vision/t/from-trades-to-agg-trades/11595

---

## السؤال 1 — معنى كل عمود من الأعمدة الثمانية

الجدول الرسمي من [S1] (قسم SPOT — AggTrades، «بيانات الملفات تُحصل من
`/api/v3/aggTrades`») — أعمدة SPOT ثمانية بالضبط:

| # | العنوان الرسمي (S1) | الحقل في REST (S2) | المعنى الموثّق |
|---|---|---|---|
| 1 | Aggregate tradeId | `a` — Aggregate tradeId | معرّف فريد لسجل التداول المجمَّع |
| 2 | Price | `p` — Price | سعر التنفيذ (معرّف واحد للـ agg كله؛ التجميع يتم بنفس السعر) |
| 3 | Quantity | `q` — Quantity | **مجموع كمية** التداولات المجمَّعة (الأصل/Base) |
| 4 | First tradeId | `f` — First tradeId | معرّف أول تداول أصلي داخل التجميع |
| 5 | Last tradeId | `l` — Last tradeId | معرّف آخر تداول أصلي داخل التجميع |
| 6 | Timestamp | `T` — Timestamp (WS: "Trade time") | زمن الصفقة (انظر السؤال 4 للوحدة) |
| 7 | Was the buyer the maker | `m` — Was the buyer the maker? | هل المشتري هو صانع السوق (maker)؟ |
| 8 | Was the trade the best price match | `M` — Was the trade the best price match? | هل نُفِّذ الصفق على أفضل سعر؟ |

تعريف التجميع الرسمي [S2]: «Trades that fill at the time, from the same taker order,
with the same price will have the quantity aggregated» — أي: تداولات **نفس أمر الـtaker**
بنفس السعر في نفس اللحظة تُجمَّع كميتها في سجل واحد.

ملاحظة تاريخية موثّقة: ملفات **FUTURES** فيها 7 أعمدة فقط (بلا عمود «best price match»)
[S1] — أي أن وجود 8 أعمدة يحدد صيغة SPOT.

## السؤال 2 — الفرق بين was_the_buyer_the_maker و is_best_match

- **`was_the_buyer_the_maker` (`m`)** — «Was the buyer the maker?» [S1][S2]: هل طرف
  الشراء هو صانع السيولة. هذا حقل **دور الطرفين/اتجاه الأمر** (maker vs taker).
  - استنتاج قياسي من تعريف maker/taker (وليس اقتباساً): `m=True` ⇐ المشتري كان maker
    ⇐ البائع هو الـtaker (المبادر/الـaggressor). هذا هو الاستخدام المعتاد لاستنتاج
    جانب المبادر، وهو الآن مسموح بعد توثيق معنى الحقل من المصدر.
- **`is_best_match` (`M`)** — «Was the trade the best price match?» [S1][S2]: هل
  التنفيذ تم على أفضل سعر — حقل **جودة تنفيذ** وليس اتجاهاً.
  - مهم: توثيق WebSocket الرسمي [S3] يعلّم هذا الحقل في بث aggTrade بـ **`// Ignore`**
    — Binance نفسها تقول تجاهله في السياق الحي.

**الفرق باختصار:** `m` = من كان المبادر (اتجاه تدفق الأوامر) · `M` = هل السعر كان
الأفضل (وBinance توصي بتجاهله).

## السؤال 3 — هل العمودان السابع والثامن هما فعلاً هاتان القيمتان؟

**نعم — بسلسلة توثيق كاملة:**
1. الجدول الرسمي [S1] لملفات Spot aggTrades يذكر 8 أعمدة بأسماء «Was the buyer the
   maker» ثم «Was the trade the best price match»، ومثاله `…|False|True` تماماً كصيغة
   الملف المرصود (حقلا قيمة منطقية في النهاية).
2. [S1]: «The aggTrades files' data is obtained from `/api/v3/aggTrades`» — وتلك
   الواجهة تعيد `m` ثم `M` بنفس الترتيب بعد `T` [S2].
3. أدوات الطرف الثالث المبنية على الأرشيف تسميهما `is_buyer_maker, is_best_match`
   (gcoban/binance-public-data-downloader) — تطابق مستقل.
4. مرساة قياسية (Phase-0 Pass-A على الأرشيف الرسمي 2026-05): 8 حقول، القيمتان
   `False,True` في السطور المرصودة.

**الشرط الواجب التحقق في تقرير المالك:** عدد الأعمدة = 8، ونطاق العمودين 7/8 =
{True, False} فقط. إن كان هناك غير ذلك → أوقف وأعد الفحص.

## السؤال 4 — الوحدة الزمنية للعمود السادس

**موثّق نصاً في [S1]:** «**Note**: The timestamp for SPOT Data from January 1st 2025
onwards will be in **microseconds**.» ومثال الجدول `1735689600010866` (16 رقماً).

- ملفات Spot **من 2025-01-01 فصاعداً** (بما فيها ملف 2026-05): **ميكروثانية** (16 رقماً).
- ملفات **قبل 2025**: ميلي ثانية (13 رقماً — مثال README القديم `1608872400000`).
- REST/WS افتراضياً ميلي ثانية؛ WS يدعم `timeUnit=MICROSECOND` اختيارياً [S3].
- مرساة قياسية: قيم ملف 2026-05 المرصودة = 16 رقماً → ميكروثانية ✓ متسقة مع الوثيقة.

**الخلاصة لملف المالك (2026-05): الوحدة = ميكروثانية، وهذا موثّق لا مُخمَّن.**

## السؤال 5 — هل agg_trade_id تسلسل مستمر أم يمكن أن يكون فيه فجوات؟

**لا يوجد أي التزام رسمي بخلو الفجوات. بل العكس موثّق:**
- [S4] (changelog الرسمي 2022-04-12): «During a market data audit, we detected some
  issues with the Spot aggregate trade data. **Missing aggregate trades were recovered.**
  **Duplicated records were marked invalid** with the following values: p='0, q='0,
  f=-1, l=-1» — إقرار رسمي بأن تداولات مجمَّعة **فقدت** من بيانات Spot ثم استُردت،
  وأن سجلات مكررة وُسمّت غير صالحة.
- [S5] (issue على مستودع Binance الرسمي): فجوات موثّقة في agg_trade_id داخل أرشيف
  العقود الآجلة (11 و31,645 و557,026 معرّفاً مفقوداً في أيام مختلفة).
- توفر وسيط `fromId` «INCLUSIVE» في الواجهة [S2] يعني مفاتيح مرتبة/قابلة للترقيم —
  وليس ضمانة اتصال.

**القاعدة المعتمَدة:** `agg_trade_id` مفتاح **متزايد صارماً** في العادة، وليس إثبات
اكتمال. الفجوة ≠ تلقائياً «بيانات مفقودة من ملفك» — قد تكون استرداداً/تصحيحاً
أرشيفياً أو خصوصية سوق أخرى؛ تُفحص كل حالة. (ملاحظة قياسية Phase-0: في أرشيف
2026-05 الرسمي كان max−min+1 = عدد الصفوف = 21,080,265 بالضبط — مؤشر قوي على
خلو الفجوات في ذلك الشهر، وليس ضمانة.)

## السؤال 6 — هل first_trade_id و last_trade_id يشملان كل التداولات داخل الفترة؟

- **الموثّق:** `f` و`l` هما معرّفا **أول وآخر** تداول أصلي مُجمَّع [S1][S2]، والكمية
  = مجموع كميات التداولات المجمَّعة فعلاً [S3]: «total quantity of the individual
  trades».
- **غير موثّق صراحةً:** هل **كل** معرّف صحيح في النطاق [f, l] ينتمي للـ agg (أي أن
  النطاق متصل العضوية دون تداخل لأجنبية). الاسم «first…last» يصف الحدود لا
  العضوية. خيط المجتمع [S6] يثبت أن تداولات بنفس السعر من **أوامر taker مختلفة**
  تبقى في aggs منفصلة بمدى IDs متجاورة — لكن لا يوجد نص رسمي يضمن «لا أجنبية
  داخل [f,l]».
- **استثناء رسمي إلزامي [S4]:** السطور الموسومة غير صالحة (p=0, q=0, f=-1, l=-1)
  خارج أي عدّ.

**طريقة التحقق لاحقاً (وليست ادعاءً الآن):** Σ(l−f+1) على السطور الصالحة مقابل عدد
صفوف ملف trades الخام لنفس النطاق، أو فحص العضوية per-agg.

## السؤال 7 — الفرق بين كمية العمود الثالث والحجم الفعلي

- العمود 3 «Quantity» = **مقدار الأصل (Base)** المجمَّع — في BTCUSDT يكون **بالـBTC**،
  وهو مجموع كميات التداولات الفردية [S3]. عمود Trades الخام يسميه `qty` مقابل
  `quoteQty` منفصل [S1].
- في وثائق Klines الرسمية [S1] يُفرَّق صراحةً بين «**Volume**» (الأصل) و«**Quote
  asset volume**» (USDT) — aggTrades يحوي الأول فقط.
- إذن: **حجم التداول بالـBTC = Σ العمود 3** (موجود أصلاً) · **حجم التداول بالـUSDT
  (القيمة الاسمية) = Σ (price × quantity)** = مشتق، غير موجود كعمود.
- عدد التداولات الخام داخل المجمَّع = (l − f + 1) لكل سطر صالح — مشتق أيضاً ويخضع
  لقيد السؤال 6.

---

## القاعدة الرسمية الإضافية (مهمة للتحويل لاحقاً)

**سطور INVALID الرسمية [S4]:** سجلات مكررة وُسمّت غير صالحة بقيم
`price='0' , quantity='0' , first_trade_id=-1 , last_trade_id=-1`.
يجب في أي خطوة لاحقة: **عزلها كمشاهدات خام (لا حذف من الأثر) واستبعادها من كل
تجميع/احتساب** — هذه ليست بيانات سوق حقيقية.

## أسماء الأعمدة المقترحة للخطوات اللاحقة (تصحيح التسمية)

| الحالي (في تقرير الفحص) | الاسم المقترح | الحالة |
|---|---|---|
| col_1 | `agg_trade_id` | موثّق (Aggregate tradeId) |
| col_2 | `price` | موثّق (Price — نفس السعر داخل الـagg) |
| col_3 | `quantity_base` | موثّق (Quantity = base asset، BTC) |
| col_4 | `first_trade_id` | موثّق (First tradeId) |
| col_5 | `last_trade_id` | موثّق (Last tradeId) |
| col_6 | `transact_time_us` | موثّق (Timestamp — **ميكروثانية** لملفات ≥ 2025-01-01؛ الوحدة في الاسم صراحةً) |
| col_7 | `is_buyer_maker` | موثّق (Was the buyer the maker) |
| col_8 | `is_best_match` | موثّق (Was the trade the best price match — «Ignore» في WS) |

حقول مشتقة مقترحة (ليست أعمدة في الملف): `quote_qty = price × quantity_base`
(مشتق)، `agg_raw_trade_count = last_trade_id − first_trade_id + 1` (مشتق، تحت قيد
السؤال 6)، `aggressor_side = SELL إذا is_buyer_maker وإلا BUY` (مشتق قياسي من
maker/taker — مسموح الآن بعد توثيق الحقل)، `is_invalid_sentinel` (p=0 و q=0 و
f=-1 و l=-1 وفق S4).

## قائمة مطابقة تقرير المالك المحلي (عند وصوله)

1. عدد الأعمدة = 8، بلا header.
2. العمود 6: قيم 16 رقماً (ميكروثانية) — المدى داخل 2026-05 UTC.
3. العمودان 7/8: نطاق {True, False}.
4. agg_id: min/max/عدد الصفوف — هل max−min+1 = العدد؟ (خلو فجوات).
5. بحث عن سطور sentinel: price=0 أو qty=0 أو first=-1 أو last=-1 (عددها المتوقع
   صفر في شهر عادي، لكن وجودها مسموح رسمياً).
6. إن ظهر أي تعارض مع النقاط أعلاه → إعادة توثيق قبل أي تحويل.

---

**لم يتغير أي ملف مشروع. لا تحويل. لا Reality Check. لا 4C-2. STOP.**
