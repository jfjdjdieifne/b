# 35 — FIELD RUNNER WINDOWS REPORTING PATCHED — READY FOR OWNER RETRY

**الحالة**: PATCHED — READY_FOR_OWNER_RETRY (التدقيق المستقل يبقى مفتوحاً لكل المرشّحين)
**النطاق**: PATCH ONLY للـfield_runner الخارجي. **trading_project لم يُلمس** (مُثبَّت أدناه).
**الأمر نفسه**: `python run_btc_may_2026.py` (أو `run_btc_may_2026.bat`).

---

## 1) العائق الحقيقي (من تشغيلك على Windows 10)

المحركات والحسابات **انتهت فعلياً** بنجاح (كل الأزمنة الحقيقية وصلت)، ثم فشل فقط عند MACHINE_VALIDATION:

```
File "field_runner/reporting.py", line 685
  import resource
ModuleNotFoundError: No module named 'resource'
```

`resource` = stdlib **Unix-only**. السبب تقني بحت — لا علاقة له بأي محرك أو نتيجة.

## 2) الإصلاح — 3 ملفات خارجية + اختباراتها

### أ) `field_runner/reporting.py`
- `import resource` صار **اختيارياً** (`try/except ImportError`) — MACHINE_VALIDATION يُنتَج على Windows بدون `resource` (الشرط 1 و4).
- **Unix/Linux — بلا أي تغيير بالبتة** (الشرط 6): `peak_memory = "<N> KiB (ru_maxrss)"` — والقيمة نفسها عند فشل getrusage: `"NOT_AVAILABLE"`.
- **Windows/أخرى** — stdlib لا يملك معادلاً دقيقاً لقياس الـpeak RSS؛ حسب شرطك «ولا تخترع قياساً» سُجِّل صراحة (بنفس شكلك حرفياً):

```json
"peak_memory": {
  "status": "NOT_AVAILABLE_ON_THIS_PLATFORM",
  "platform": "<platform.platform() — مثال: Windows-10-10.0.19045-SP0>",
  "method": null
}
```

- **بلا dependency جديدة** (الشرط 3): لا `psutil` ولا ctypes/psapi — مسار ctypes تم رفضه عمداً لأنه ليس stdlib-decclared ولا «exact equivalent» (قياس working-set ≠ ru_maxrss) ويصادق «لا تخترع قياساً».
- **قياس الذاكرة ليس شرط نجاح** (الشرط 2): غيابه لا يضيف failure ولا warning — **مُختبَر انحداراً**.

### ب) `field_runner/runner_btc_may_2026.py` (رسالة فقط — لا semantics)
النص القديم `"...exact history scans ... expected TENS OF MINUTES..."` (صار قديماً بعد EXACT PERFORMANCE V2) استُبدل بالضبط بـ:

> `runtime depends on dataset and certified engine implementation; stage timings are reported below.`

(الشرط 7 و8: تعديل رسالة فقط؛ SUMMARY.json والـCSVs لم يُطَلَّم — محركات كتابتها لم تُعدَّل.)

### ج) `field_runner/runner_tests/test_windows_reporting.py` (5 بوابات جديدة) + نسخة مرجعية مثبّتة
`runner_tests/_reference_reporting_pre.py` = `aa2cfbfb3dfe9a628cec5509c018a03be22694dec575117f90a5018b49acbacc`

| البوابة | الشرط |
|---|---|
| `test_machine_validation_produced_without_resource_module` — يحاكي غياب `resource` (`sys.modules["resource"]=None`) → ينتج السجل أعلاه + `failures==[]` + `warnings==[]` | 1+2+4+5 |
| `test_pre_patch_reporting_crashes_without_resource_module` — النسخة pre المثبّتة ترتفع ImportError بنفس المحاكاة (يثبت أن الحارس يكشف الأصل) | 5 |
| `test_machine_validation_resource_path_identical_to_pre_patch` — **differential old==new**: مع `resource` (getrusage مُثبَّت بقيمة معلومة) القاموس كامل مطابق حرفياً عدا `runtime_seconds` (وهو volatile بالفعل)؛ ومسار فشل getrusage = `"NOT_AVAILABLE"` في الاثنتين؛ والصيغة الحقيقية `^\d+ KiB \(ru_maxrss\)$` | 6 |
| `test_progress_text_no_longer_claims_tens_of_minutes` — «TENS OF MINUTES» منتهية والنص الجديد موجود | 7 |
| `test_reference_reporting_snapshot_is_pinned` — النسخة pre مثبّتة بـsha256 داخل الاختبار | — |

## 3) البوابات — كلها خضراء

- **field_runner/runner_tests = 36/36** (31 سابقة + 5 جديدة) — شُغِّلت **من داخل الحزمة بعد استخراج نظيف**.
- smoke من الاستخراج: بدون resource → `{'status': 'NOT_AVAILABLE_ON_THIS_PLATFORM', 'platform': 'Linux-6.1.158+-x86_64-with-glibc2.41', 'method': None}`؛ مع resource → `69336 KiB (ru_maxrss)`.

## 4) trading_project UNCHANGED (مُثبَّت بعد الـpatch مباشرة)

- `MANIFEST.sha256` = `7796a73fc30fc311902d7ba8e033eb1699a73c5db10e824d02653fbdd1681587` (183 سطراً — لم يُعدَّل).
- **173 OK / 10 stale موثَّقة** — نفس المجموعة العشرة بالضبط (5 src + 5 tests المرشّحة من 32/33) — لا ملف جديد تغيّر.
- لا CLOSED ولا engine ولا performance patch ولا semantics ولا output fact لُمس.

## 5) الحزمة والـZIP

**`deliverables/35_BTC_MAY2026_FIELD_RUNNER_PACKAGE_WINDOWS_REPORTING_PATCHED.zip`**
**sha256 = `1dc0e13b24a93c76a64b7a7459c3eb8316efe4bfc7a13d29124771c20ad59861`** (238 ملفاً في FILE_INVENTORY — 238/238 مطابقة بعد الاستخراج).

- نفس بنية حزمة 34 + الملفات الخارجية المعدَّلة + الاختبارات + `PATCH_NOTES_WINDOWS_REPORTING_2026-09-29.txt` + reports/32+33 + perf_lab.
- **الأمر كما هو**: `python run_btc_may_2026.py` — لا flag جديد، لا إعداد جديد.

## 6) الممنوعات (ثابتة)

لا `--allow-hash-mismatch` كحل، لا تعطيل hash guards، لا تعديل trading_project، لا قياس ذاكرة مُختلَق، لا dependency جديدة، لا تغيير أي نتيجة SUMMARY/CSV، TIE_ORDER_CONTRACT = NOT_PROVEN، PROXY≠ACTUAL. REAL OWNER RUN على جهازك فقط — والتشغيل السابق أثبت أن المحركات عندك تكمل؛ هذا الـpatch يزيل آخر عائق إداري فقط.
