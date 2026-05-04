---
description: إنشاء المهام اللازمة للتنفيذ وتخزينها في tasks.md.
---

> **اللغة**: اكتب tasks.md بالعربية الفصحى مع تنسيق معرّفات المهام (T001، إلخ) كما في المشروع.

## إدخال المستخدم

```text
$ARGUMENTS
```

## الخطوات

1. اقرأ `.specify/feature.json` لمعرفة مسار مجلد الميزة.

2. **حمّل السياق**: `.specify/memory/constitution.md` و`<feature_directory>/spec.md` و`<feature_directory>/plan.md`.

3. أنشئ مهاماً مرتّبة بالتبعيات وخزّنها في `<feature_directory>/tasks.md`.
   - كل مهمة بتنسيق قائمة: `- [ ] [TaskID] وصف مع مسار ملف`
   - منظّمة بمراحل: إعداد، أساسيات، قصص مستخدمين حسب الأولوية، صقل
