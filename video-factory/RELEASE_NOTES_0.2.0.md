# Video Factory 0.2.0 — Hybrid Premium Core

تاريخ الدمج: 2026-08-19

## ما أُضيف إلى القلب

- صيغة `edit_plan.json` قابلة للأتمتة والتدقيق.
- Plan Validator يمنع الصور الثابتة من احتسابها كحركة ويتحقق من المدة والكثافة والتراخيص.
- FFmpeg Renderer متعدد المصادر مع إعادة تأطير، تلوين، كابشن، Motion Graphics، وStereo mix.
- QA آلي للمدة والدقة والإطارات والتجمّد والسواد وtrue peak/loudness.
- Manifest لكل Render يتضمن hash الخطة والناتج.
- مثال Ancient Mystery كامل: 15 ثانية، 15 visual beat، ستة مصادر حركة، مع الاعتمادات.
- إعداد النشر مثبت على `draft_only` و`enabled: false`.
- متطلبات واختبارات محدثة؛ النتيجة النهائية: **22 passed**.

## إثبات إعادة البناء

أعاد المحرك الموجود داخل المشروع بناء Full HD master من الخطة ونجح QA:

- 1080×1920، 30fps، 450 frame
- Stereo AAC، -14.2 LUFS، -1.5 dBFS true peak
- أطول امتداد منخفض الحركة جدًا: 0.2667 ثانية
- لا Full-black frames
- الناتج المرجعي: `examples/hybrid_premium/ancient_mystery/sample_preview.mp4`

## ما لم يُدّعَ إنجازه

- Queue التوليد لم يُربط بعد تلقائيًا بمرحلة Assembly.
- Telegram وYouTube OAuth غير مربوطين.
- Wan2.2 TI2V-5B I2V بطولي 5 و8 ثوانٍ ما زال benchmark التالي.
- كشف watermark وAI morphing يبقيان مراجعة بشرية إلزامية؛ لا يوجد ادعاء كشف آلي كامل.
