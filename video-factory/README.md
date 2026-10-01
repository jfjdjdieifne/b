# Video Factory — Hybrid Premium Core

منظومة فيديو قابلة للاستئناف تجمع توليد مشاهد Wan، إدارة مزودي GPU، وخط مونتاج
Hybrid Premium محلي ينتج MP4 عموديًا مع كابشن وصوت وفحوص جودة. لا تُحفظ مفاتيح
الخدمات في الكود أو ملفات الحالة، والنشر مقفول افتراضيًا على `draft_only`.

## ما الذي يؤتمته القلب الحالي؟

1. يُنشأ Scene Job داخل `jobs/` وتديره طبقة المزود مع failover واستئناف.
2. يتوفر مسار Colab CLI رسمي on-demand: allocate → exec → download → stop.
3. يمكن استخدام HF ZeroGPU كـfallback لمشاهد Wan القصيرة ضمن الحصة المتاحة.
4. يقرأ محرك المونتاج `edit_plan.json` ويجمع مصادر الحركة والكابشن والراوي والصوت.
5. يصدّر MP4 عموديًا ثم يشغّل Quality Gates آلية ويكتب manifest قابلًا للتدقيق.

ما زال الربط الكامل بين Queue توليد المشاهد وQueue المونتاج، التخزين الخارجي،
Telegram، benchmark Wan2.2 I2V بطولي 5 و8 ثوانٍ، وYouTube OAuth مراحل تالية.
لا يتم النشر الآن، وأي ملف يبقى Draft حتى يمر بالمراجعة اليدوية.

## الهوية البصرية المعتمدة: Hybrid Premium

اختار المستخدم نمط **Hybrid Premium**: تغطية متعددة الزوايا، إيقاع متغير، Wan
للقطات البطولية، وفيديو حقيقي/stock/public-domain وmotion graphics عندما يخدم
القصة. الخام المولد 3–5 ثوانٍ هو master take تُستخرج منه أفضل لحظة، وليس وحدة
مونتاج ثابتة. يُمنع slideshow واعتبار zoom على صورة حركة AI. المواصفات الإلزامية
وQuality Gates موثقة في
[`docs/HYBRID_PREMIUM_VISUAL_SPEC.md`](docs/HYBRID_PREMIUM_VISUAL_SPEC.md).

## محرك Hybrid Premium المدمج في قلب المشروع

لم تعد الهوية مواصفة نظرية فقط. يحتوي المشروع الآن على خط إنتاج محلي قابل
للأتمتة:

```text
edit_plan.json → plan validation → FFmpeg renderer → MP4 → automated QA
```

المكونات الأساسية:

- `video_factory/hybrid_premium/plan.py`: خطة مونتاج قابلة للفحص؛ تمنع إدخال
  صورة ثابتة باعتبارها حركة وتتحقق من المدة والكثافة والمصادر والتراخيص.
- `video_factory/hybrid_premium/renderer.py`: قص، إعادة تأطير، تلوين، Motion
  Graphics، كابشن، Stereo mix، loudness، وتصدير 1080×1920.
- `video_factory/hybrid_premium/qa.py`: فحص المدة، الدقة، الإطارات، التجمّد،
  السواد، وفواصل الصوت، مع إبقاء watermark/morphing/continuity بوابات مراجعة
  بشرية صريحة بدل ادعاء كشف غير موثوق.
- `examples/hybrid_premium/ancient_mystery/`: المثال المرجعي الذاتي بمواد Master المتحركة المستخدمة، خطة 15 visual beat،
  الاعتمادات، تقرير QA، وPreview جاهز؛ ويمكنه إعادة بناء Full HD محليًا.

إعادة بناء المثال:

```bash
python scripts/render_hybrid_premium.py \
  --plan examples/hybrid_premium/ancient_mystery/edit_plan.json \
  --output outputs/ancient-mystery-rebuilt.mp4
```

فحص الملف المرجعي:

```bash
python scripts/qa_hybrid_premium.py \
  --plan examples/hybrid_premium/ancient_mystery/edit_plan.json \
  --video outputs/ancient-mystery-rebuilt.mp4
```

النشر ما زال مقفولًا: `publishing.mode: draft_only` و`enabled: false`.

## المسار headless المثبت حيًا: Google Colab CLI الرسمي + T4

في 19 أغسطس 2026 نجح الاختبار الفعلي عبر `google-colab-cli==0.6.0`:
OAuth مرة واحدة، تخصيص `Tesla T4` مجاني بذاكرة `14.56 GiB`، تنفيذ CUDA بعيد،
توليد Wan MP4 حقيقي، تنزيل الناتج، ثم إطفاء الجلسة. لم تُطلب بطاقة أو مصادقة
هاتف أثناء الاختبار، ولا توجد جلسات نشطة بعده.

القياس الأول: Wan2.1 T2V-1.3B مكمم NF4، `832×480`، 17 إطارًا/16fps،
`1.0625s`، وتوليد GPU خلال `89.01s` مع peak VRAM بلغ `9.93 GiB`. هذا smoke
للمنصة وليس بروفايل الجودة النهائي؛ الخطوة التالية اختبار Wan2.2 TI2V-5B
المكمم لـI2V الحقيقي.

راجع [`deployments/colab_cli/README.md`](deployments/colab_cli/README.md) للتثبيت
والـwrapper الآمن `allocate -> exec -> download -> stop`. لا يُستخدم
Playwright/Selenium ولا Drive mount في المسار غير المراقب. توفر T4 والحصة
best-effort وديناميكيان، لذلك يبقى HF ZeroGPU fallback.

## المسار الحالي المثبت حيًا: Hugging Face ZeroGPU + Wan 2.2

عند تعذر Kaggle، اختُبر فعليًا Space عام يعمل على ZeroGPU عبر **Gradio API رسمي قابل للتشغيل headless**:

- Space: `Upsampler/wan-2-2-5b-video`
- Model: `Wan2.2-TI2V-5B` مفتوح بترخيص Apache-2.0، ويدعم T2V وI2V حقيقيين.
- endpoint: `/generate_video`، ومدد 1–8 ثوانٍ، أبعاد 256–1024 (مضاعفات 32)، و1–8 خطوات.
- نجح طلب anonymous بلا حساب أو token: خرج MP4 رأسي H.264 بدقة `480×832`، و24fps، و25 إطارًا/1.0417 ثانية بعد قرابة 10 ثوانٍ wall time.
- فُكّت كل الإطارات بنجاح، وثبتت حركة فعلية، ولم يظهر watermark في الإطارات المفحوصة.
- الحصة الرسمية متجددة كل 24 ساعة: دقيقتا GPU بلا تسجيل، 5 دقائق لحساب مجاني، و40 دقيقة لحساب PRO. المسار المجاني لا يطلب بطاقة؛ صفحة التسجيل تطلب البريد وكلمة المرور.
- الـSpaces المجتمعية best-effort بلا SLA وقد تتغير، لذلك يجب الإبقاء على health checks وfallbacks وعدم اعتبارها بنية إنتاج مضمونة.

ملف الإثبات الحي خارج المستودع: `/home/user/hf-wan-smoke-1s.mp4`، وSHA-256:

```text
1d65b732757e94629c24914602daaa70db2cd7dc564fe1f80096cdae09eac14c
```

### التشغيل الآمن

أنشئ Fine-grained token بصلاحية القراءة فقط وضعه في البيئة؛ لا يُحفظ في الكود ولا يُطبع:

```bash
export HF_TOKEN='hf_...'
python scripts/hf_spaces_smoke_test.py --health-only
python scripts/hf_spaces_smoke_test.py --output artifacts/hf-t2v.mp4
python scripts/hf_spaces_smoke_test.py \
  --image first-frame.png --duration 2 --steps 4 \
  --output artifacts/hf-i2v.mp4
```

الـtoken اختياري تقنيًا، لكن استخدامه هو الصحيح للأتمتة لأن Hugging Face ينسب الاستهلاك إلى حصة الحساب (5 دقائق يوميًا) بدل anonymous pool الأقل أولوية. الـAdapter يستخدم `gradio_client.handle_file()` لـI2V بدل تركيب `FileData` يدويًا.

> هذا المسار مناسب لعدة لقطات AI قصيرة يوميًا ضمن مونتاج هجين؛ ليس مجانيًا بما يكفي لتوليد كامل 30–60 ثانية بالذكاء الاصطناعي لكل فيديو. الـVisual Director يجب أن يخصص الحصة للقطات المفتاحية ويستخدم stock/public-domain/صورًا مرخصة لبقية الخط الزمني.

## مسار Free.ai المؤرشف — مرفوض وغير مفعّل

أضيف Adapter مستقل سابقًا لـFree.ai، لكن هذا المزود **مرفوض بقرار المشروع ولا يجوز اختياره كمسار الإنتاج**. بقي الكود فقط كسجل تجريبي قابل للحذف. كان العرض المعلن:

- REST API حقيقي عند `https://api.free.ai/v1/video/generate/`.
- النموذج المجاني المعلن: CogVideoX مستضاف ذاتيًا، Text-to-Video وImage-to-Video.
- حساب البريد المجاني يعلن `30,000` token يوميًا متجددة، بلا بطاقة؛ الحد المجاني للـAPI يعلن 1,000 طلب/شهر.
- لقطات قصيرة 2–3 ثوانٍ بدقة 480p في المسار المجاني، بلا watermark، مع حق الاستخدام التجاري وفق صفحة المزود وترخيص النموذج المعلن Apache-2.0.
- صفحات المزود غير متسقة في تكلفة اللقطة: جدول الـAPI يذكر 5,000 token، بينما صفحات الفيديو تقدّر 7,500 للـ3 ثوانٍ و10,000 للـ4 ثوانٍ. لذلك لا يُعتمد العدد النظري؛ يسجل اختبارنا `token_cost` و`remaining_tokens` الفعليين إن أعادهما الـAPI.

هذا المسار **غير مفعّل ومرفوض**، ولم يُنفّذ عليه اختبار MP4 حي. لا تستخدمه في الـOrchestrator. المسار المختبر حاليًا هو Hugging Face ZeroGPU أعلاه.

### اختبار Free.ai الآمن

1. أنشئ الحساب: `https://free.ai/signup/?next=/account/?tab=api`
2. من `https://free.ai/account/?tab=api` أنشئ مفتاحًا يبدأ بـ`sk-free-`.
3. خزّنه في Secret/متغير بيئة فقط:

```bash
export FREE_AI_API_KEY='sk-free-...'
```

4. شغّل أقل اختبار رأسي مدته ثانيتان:

```bash
python scripts/free_ai_smoke_test.py
```

المخرجات:

```text
outputs/free_ai_smoke/scene.mp4
outputs/free_ai_smoke/diagnostics.json
```

لا يقبل السكربت المفتاح كوسيط command-line، ولا يطبعه أو يكتبه في التشخيص. اترك `FREE_AI_VIDEO_MODEL` فارغًا ليستخدم المسار المستضاف ذاتيًا؛ أي اسم يبدأ بـ`premium/` يحتاج رصيدًا مدفوعًا.

## تعدد حسابات Kaggle والتبديل التلقائي

يدعم المشروع الآن **Pool من حسابات Kaggle مختلفة**:

- توزيع Round-robin: كل Job جديد يبدأ من الحساب التالي لتوزيع الحمل.
- Failover ضمن التشغيل نفسه: إذا رفض حساب إرسال الـKernel بسبب مفتاح/صلاحية/حصة/خطأ إرسال، يُجرَّب الحساب التالي مباشرةً.
- Cooldown: الحساب الذي يفشل يُستبعد افتراضيًا 60 دقيقة، بدل تكرار المحاولة به كل 15 دقيقة.
- الاستئناف الصحيح: يُحفظ `provider_account` داخل الـJob لكي تتم متابعة الـKernel بالمفتاح الذي أرسله، لا بحساب آخر.
- أخطاء الشبكة المؤقتة أثناء فحص الحالة لا تطلق نسخة مكررة فورًا؛ ينتظر النظام 3 فحوص افتراضيًا.
- فشل Credential قبل قبول الـKernel **لا يستهلك** `max_attempts`. أما Render قُبل ثم فشل فيستهلك محاولة، وبعده ينتقل الـRetry إلى الحساب التالي.

تُحفظ في `state/kaggle_accounts.json` أسماء الحسابات المنطقية، الدور، الـcooldown والأخطاء المختصرة فقط. **لا يُحفظ أي Token في هذا الملف.**

> استخدم فقط حسابات تملكها أو لديك تفويض صريح لاستخدامها، والتزم بسياسات Kaggle. هذه الميزة للموثوقية وتوزيع العمل المشروع، وليست للتحايل على قيود المنصة.

## الإعداد الموصى به على GitHub

اذهب إلى:

`Repository → Settings → Secrets and variables → Actions → New repository secret`

أضف زوجًا كاملًا لكل حساب:

```text
KAGGLE_USERNAME_1
KAGGLE_API_TOKEN_1

KAGGLE_USERNAME_2
KAGGLE_API_TOKEN_2

KAGGLE_USERNAME_3
KAGGLE_API_TOKEN_3
```

الـWorkflow مجهز مسبقًا للفتحات من 1 إلى 10. لا مشكلة في ترك الفتحات غير المستخدمة بلا Secrets، لكن لا تضع Username بلا Token أو العكس في الفتحة نفسها.

**مهم:** لا ترسل المفاتيح في المحادثة، ولا تضعها في `.env.example`، ولا تعمل لها Commit. إذا سبق نشر مفتاح، ألغِه وأنشئ واحدًا جديدًا.

### بديل JSON لعدد غير محدود

يمكن حفظ GitHub Secret واحد اسمه `KAGGLE_ACCOUNTS_JSON` وقيمته:

```json
[
  {"id":"primary","username":"KAGGLE_USER_1","api_token":"TOKEN_1"},
  {"id":"backup","username":"KAGGLE_USER_2","api_token":"TOKEN_2"}
]
```

لا تضع هذه القيمة في ملف داخل المستودع. الفتحات المرقمة لها أولوية على JSON إذا كان الاثنان موجودين. نوصي بالفتحات المرقمة لأن كل Token يبقى GitHub Secret مستقلًا ومقنّعًا مستقلًا في السجلات.

### توافق مع إعداد الحساب الواحد القديم

إذا لم توجد فتحات مرقمة ولا `KAGGLE_ACCOUNTS_JSON`، يستمر المشروع باستخدام:

```text
KAGGLE_USERNAME
KAGGLE_API_TOKEN
```

لذلك لا ينكسر الإعداد القديم.

## إعداد محلي

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

املأ `.env` محليًا فقط. الملف متجاهَل عبر `.gitignore`.

## إنشاء مشهد 5 ثوانٍ

Text-to-video:

```bash
python scripts/new_job.py \
  "A continuous cinematic tracking shot of a child walking toward a mysterious glowing door in a foggy forest. The child takes two natural steps, plants sway, fog drifts, and the door begins to open."
```

Image-to-video باستخدام رابط صورة متاح لـKaggle:

```bash
python scripts/new_job.py \
  "The child walks naturally toward the door; the handle turns and the door opens." \
  --image-url "https://example.com/master.png"
```

اعمل Commit لملف JSON الجديد داخل `jobs/`، ثم شغّل الـWorkflow يدويًا أو انتظر الـcron.

## إعدادات Failover

داخل `config.yaml`:

```yaml
kaggle:
  account_cooldown_minutes: 60
  status_error_retries: 3
```

- `account_cooldown_minutes`: مدة تجاهل الحساب بعد فشل إرسال/اعتماد.
- `status_error_retries`: عدد أخطاء فحص الحالة المؤقتة قبل إعادة الـJob على حساب آخر.

إذا أصلحت Secret وتريد إلغاء الـcooldown فورًا، احذف `state/kaggle_accounts.json` أو اجعل `cooldown_until` للحساب `null` ثم شغّل الـWorkflow يدويًا.

## حالات الـJob

```text
queued → submitted → running → done
                     ↘ queued (retry on next account)
                     ↘ failed (render retry limit reached)
queued → blocked (already at retry limit)
```

يضيف كل Job حقلًا غير سري:

```json
"provider_account": "account-2"
```

كما يسجل آخر أحداث التبديل داخل `metadata.kaggle_account_events` لتسهيل التشخيص دون كشف المفاتيح.

## الاختبار

```bash
pytest -q
python -m compileall -q video_factory workers scripts
```

الاختبارات الحالية تتحقق من Jobs، تحميل عدة Credentials، Round-robin، Cooldown،
عدم تسريب Tokens، صحة خطة Hybrid Premium، رفض الصور الثابتة كحركة، بناء
filtergraph متعدد المصادر، وفحص الـMP4 المرجعي كاملًا. آخر نتيجة مدمجة:
`22 passed`. ما زال اختبار Kaggle End-to-End الحقيقي يحتاج Secrets صالحة وحصة
GPU متاحة.

## قيود مهمة

- توفر Kaggle GPU والحصص غير مضمون.
- أول Worker ما زال ينزّل الموديل؛ يجب لاحقًا ربط Kaggle Model/Dataset دائم.
- لا ينبغي تخزين فيديوهات كبيرة في GitHub؛ أضف Object Storage أو ارفع مباشرةً إلى YouTube.
- الـMVP يشغّل Render نشطًا واحدًا في كل مرة؛ التوازي بين عدة Shots مرحلة لاحقة.
- النشر غير المراقب يحتاج YouTube OAuth مرة واحدة، وضوابط جودة وحقوق ومراجعة محتوى قوية.
