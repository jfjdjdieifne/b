# Official Google Colab CLI deployment

هذا المسار يستخدم **Google Colab CLI الرسمي** فقط. لا يستخدم Selenium أو
Playwright، ولا يفتح Notebook UI، ولا يعتمد على `runtime.unassign()`.

## النتيجة الحية المثبتة — 19 أغسطس 2026

تم الاختبار على الحساب المصرح به عبر OAuth:

- نجح إنشاء runtime مجاني مطلوب صراحةً كـ`T4` بلا بطاقة أو توثيق هاتف أثناء الاختبار.
- GPU الفعلي: `Tesla T4` بذاكرة قابلة للاستخدام `14.56 GiB`.
- نجح تنفيذ CUDA script بعيدًا، ثم أطفأ `colab run` الجلسة تلقائيًا.
- نجح lifecycle الكامل `new -> exec -> download -> stop`.
- نجح توليد Wan T2V حقيقي وتنزيل MP4 محليًا ثم إطفاء الجلسة.
- لا توجد جلسات نشطة بعد الاختبار.

قياس Wan smoke:

```text
model: Wan-AI/Wan2.1-T2V-1.3B-Diffusers
output: 832x480, 17 frames, 16 fps, 1.0625 s
steps: 10
GPU generation: 89.01 s
peak allocated VRAM: 9.93 GiB
total first-run time: 498.91 s (يشمل تنزيل الأوزان والتكميم)
```

هذا يثبت النقل والتشغيل والـGPU، لكنه **ليس بروفايل الجودة النهائي**. الاختبار
الأول استخدم Wan 1.3B T2V لتقليل المخاطرة. الـI2V النهائي يحتاج اختبار Wan
2.2 TI2V-5B المكمم أو WanGP/ComfyUI-GGUF على T4.

## تثبيت العميل المحلي

```bash
python -m pip install -r deployments/colab_cli/requirements-local.txt
```

يوجد pin مؤقت لـ`jupyter-kernel-client==0.15.0`: إصدار `1.0.1` غيّر الاسم
`KernelClient` وكسر `google-colab-cli==0.6.0` عند تنفيذ الكود، مع أن تخصيص T4
كان ينجح. أزل الـpin فقط بعد إصلاح التوافق upstream.

أول استخدام يحتاج OAuth يدويًا مرة واحدة. يُحفظ refresh token محليًا في:

```text
~/.config/colab-cli/token.json
```

هذا الملف Secret: لا ترفعه إلى Git ولا تضعه داخل ZIP. رموز authorization
المؤقتة لا تُستخدم مرة أخرى بعد صرفها.

## CUDA smoke مع teardown تلقائي

```bash
colab --auth=oauth2 run --gpu T4 --timeout 120 \
  deployments/colab_cli/gpu_smoke.py
```

## Job ينتج ملفًا

`colab run` ممتاز للوظائف التي يكفي stdout فيها. عندما يجب استرجاع MP4، استخدم
الـwrapper الذي يضمن الإطفاء داخل `finally`:

```bash
python deployments/colab_cli/run_job.py \
  deployments/colab_cli/wan_t2v_smoke.py \
  /content/wan_t2v_smoke.mp4 \
  artifacts/wan_t2v_smoke.mp4 \
  --gpu T4 --timeout 1800
```

التسلسل:

```text
allocate -> execute -> download to .part -> atomic rename -> stop
```

استخدم `--keep-on-failure` للتشخيص فقط؛ ترك T4 عاملًا يهدر الحصة.

## لماذا لا نستخدم Google Drive؟

`colab drivemount` قد يطلب consent تفاعليًا لكل runtime جديد. لذلك المسار غير
المراقب يستخدم `colab upload/download` للمدخلات والنتائج، وينزّل الموديل من
Hugging Face مرة واحدة داخل جلسة الدفعة اليومية. يمكن إبقاء الجلسة لمعالجة عدة
لقطات ثم إطفاؤها، بدل تنزيل الأوزان لكل لقطة.

## ملاحظات تنزيل Hugging Face

في الاختبار، علّق HF Xet عند استكمال ملفات متعددة كبيرة في جلسة headless.
السكربت يضبط:

```text
HF_HUB_DISABLE_XET=1
```

ثم يستخدم HTTP متسلسلًا مع استكمال ملفات `.incomplete`. التنزيل الكامل استغرق
نحو 4.5 دقائق في التشغيل الحي. التحذيران التاليان غير قاتلين:

- Flax deprecation في Diffusers.
- محاولة قراءة `HF_TOKEN` من Colab Secrets لموديل عام.

## حدود لا يجوز إخفاؤها

- نجاح T4 اليوم لا يضمن توفره في كل مرة؛ Colab free best-effort وحدوده ديناميكية.
- يجب تسجيل quota-denied/assignment failures وتطبيق queue/backoff وfallback.
- لا نستخدم حسابات متعددة للتحايل على الحصة.
- لا نعتبر 1.06 ثانية أو 1.3B جودة إنتاج؛ الاختبار التالي هو I2V 5B مكمم، ثم
  batch لقطات 30/60 ثانية، وبعدها فقط ربط Telegram أو النشر.
