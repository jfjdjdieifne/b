# Ancient Mystery — Self-contained Hybrid Premium reference

هذا المثال مضغوط ذاتيًا: يحتوي على 15 Master Clip مستخدمة فعليًا فقط، الراوي،
الموسيقى، الكابشن، خطة المونتاج، الاعتمادات، وPreview جاهز. المصادر الأرشيفية
الطويلة غير مطلوبة للبناء؛ روابطها وتراخيصها في `CREDITS.md`.

إعادة بناء Full HD من جذر المشروع:

```bash
python scripts/render_hybrid_premium.py \
  --plan examples/hybrid_premium/ancient_mystery/edit_plan.json \
  --output outputs/ancient-mystery-fullhd.mp4
```

فحص الجودة:

```bash
python scripts/qa_hybrid_premium.py \
  --plan examples/hybrid_premium/ancient_mystery/edit_plan.json \
  --video outputs/ancient-mystery-fullhd.mp4
```

النشر مقفول على `draft_only`. كل لقطة فيديو حقيقية؛ لا توجد صور ثابتة محسوبة كحركة.
