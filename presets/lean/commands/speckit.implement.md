---
description: تنفيذ خطة التنفيذ بمعالجة كل المهام في tasks.md.
---

> **اللغة**: أبلغ التقدم والأخطاء بالعربية الفصحى.

## إدخال المستخدم

```text
$ARGUMENTS
```

## الخطوات

1. اقرأ `.specify/feature.json` لمعرفة مسار مجلد الميزة.

2. **حمّل السياق**: `.specify/memory/constitution.md` و`<feature_directory>/spec.md` و`<feature_directory>/plan.md` و`<feature_directory>/tasks.md`.

3. **نفّذ المهام** بالترتيب:
   - أكمل كل مهمة قبل التالية
   - علّم المهام المكتملة بتغيير `- [ ]` إلى `- [x]` في `<feature_directory>/tasks.md`
   - توقّف عند الفشل وأبلغ عن المشكلة

4. **تحقق**: تأكد من إكمال كل المهام ومطابقة التنفيذ للمواصفة.
