<div align="center">
    <img src="./media/logo_large.webp" alt="Spec Kit Logo" width="200" height="200"/>
    <h1>🌱 Spec Kit</h1>
    <h3><em>ابنِ برمجيات عالية الجودة بشكل أسرع.</em></h3>
</div>

<p align="center">
    <strong>مجموعة أدوات مفتوحة المصدر تساعدك على التركيز على سيناريوهات المنتج ونتائج متوقعة بدلاً من «البرمجة بالحدس» لكل جزء من الصفر.</strong>
</p>

<p align="center">
    <a href="https://github.com/github/spec-kit/releases/latest"><img src="https://img.shields.io/github/v/release/github/spec-kit" alt="Latest Release"/></a>
    <a href="https://github.com/github/spec-kit/stargazers"><img src="https://img.shields.io/github/stars/github/spec-kit?style=social" alt="GitHub stars"/></a>
    <a href="https://github.com/github/spec-kit/blob/main/LICENSE"><img src="https://img.shields.io/github/license/github/spec-kit" alt="License"/></a>
    <a href="https://github.github.io/spec-kit/"><img src="https://img.shields.io/badge/docs-GitHub_Pages-blue" alt="Documentation"/></a>
</p>

---

## جدول المحتويات

- [🤔 ما هو التطوير المعتمد على المواصفات؟](#-what-is-spec-driven-development)
- [⚡ البدء السريع](#-get-started)
- [📽️ نظرة عامة بالفيديو](#️-video-overview)
- [🧩 امتدادات المجتمع](#-community-extensions)
- [🎨 وصفات المجتمع](#-community-presets)
- [🚶 جولات المجتمع](#-community-walkthroughs)
- [🛠️ أصدقاء المجتمع](#️-community-friends)
- [🤖 وكلاء البرمجة بالذكاء الاصطناعي المدعومون](#-supported-ai-coding-agent-integrations)
- [🔧 مرجع Specify CLI](#-specify-cli-reference)
- [🧩 خصّص Spec Kit حسب احتياجك: الامتدادات والوصفات](#-making-spec-kit-your-own-extensions--presets)
- [📚 الفلسفة الأساسية](#-core-philosophy)
- [🌟 مراحل التطوير](#-development-phases)
- [🎯 الأهداف التجريبية](#-experimental-goals)
- [🔧 المتطلبات الأساسية](#-prerequisites)
- [📖 تعلّم المزيد](#-learn-more)
- [📋 الخطوات التفصيلية](#-detailed-process)
- [🔍 حل المشكلات](#-troubleshooting)
- [💬 الدعم](#-support)
- [🙏 شكر وتقدير](#-acknowledgements)
- [📄 الترخيص](#-license)

## 🤔 ما هو التطوير المعتمد على المواصفات (Spec-Driven Development)؟

بدل ما المواصفة «ورقة جانبية» والكود هو الحقيقة الوحيدة، الـ SDD يخلي **المواصفة مصدراً للتنفيذ**: نص واضح يترجم مباشرة إلى خطوات وتنفيذ، مو بس «توجيه عام» قبل البرمجة.

## ⚡ البدء السريع

### 1. تثبيت Specify CLI

اختر طريقة التثبيت المناسبة:

> **مهم:** الحزم الرسمية والمدعومة لـ Spec Kit تُنشر من هذا المستودع على GitHub فقط. أي حزم بنفس الاسم على PyPI **ليست** تابعة لهذا المشروع. ثبّت دائماً من GitHub كما يلي.

#### الخيار 1: تثبيت دائم (موصى به)

ثبّت مرة واحدة واستخدم في كل مكان. ثبّت إصدارًا محددًا من أجل الاستقرار (راجع [Releases](https://github.com/github/spec-kit/releases) لمعرفة الأحدث):

```bash
# تثبيت إصدار مستقر محدد (موصى به — استبدل vX.Y.Z بأحدث إصدار)
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@vX.Y.Z

# أو ثبّت أحدث نسخة من main (قد تتضمن تغييرات لم تُصدر بعد)
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git

# بديل: باستخدام pipx (يعمل أيضًا)
pipx install git+https://github.com/github/spec-kit.git@vX.Y.Z
pipx install git+https://github.com/github/spec-kit.git
```

ثم تحقق من تثبيت الإصدار الصحيح:

```bash
specify version
```

واستخدم الأداة مباشرة:

```bash
# إنشاء مشروع جديد
specify init <PROJECT_NAME>

# أو التهيئة في مشروع قائم
specify init . --integration copilot
# أو
specify init --here --integration copilot

# فحص الأدوات المثبتة
specify check
```

لترقية Specify، راجع [دليل الترقية](./docs/upgrade.md) للحصول على تعليمات مفصّلة. ترقية سريعة:

```bash
uv tool install specify-cli --force --from git+https://github.com/github/spec-kit.git@vX.Y.Z
# لمستخدمي pipx: pipx install --force git+https://github.com/github/spec-kit.git@vX.Y.Z
```

#### الخيار 2: استخدام لمرة واحدة

شغّل الأداة مباشرة دون تثبيت:

```bash
# إنشاء مشروع جديد (مرتبط بإصدار مستقر — استبدل vX.Y.Z بأحدث إصدار)
uvx --from git+https://github.com/github/spec-kit.git@vX.Y.Z specify init <PROJECT_NAME>

# أو التهيئة في مشروع قائم
uvx --from git+https://github.com/github/spec-kit.git@vX.Y.Z specify init . --integration copilot
# أو
uvx --from git+https://github.com/github/spec-kit.git@vX.Y.Z specify init --here --integration copilot
```

**مزايا التثبيت الدائم:**

- تبقى الأداة مثبّتة ومتاحة في PATH
- لا حاجة لإنشاء اختصارات في الـ shell
- إدارة أفضل للأدوات عبر `uv tool list`، `uv tool upgrade`، `uv tool uninstall`
- إعدادات أنظف للـ shell

#### الخيار 3: تثبيت للمؤسسات / البيئات المعزولة

إذا كانت بيئتك تحجب الوصول إلى PyPI أو GitHub، راجع دليل [التثبيت في المؤسسات / البيئات المعزولة](./docs/installation.md#enterprise--air-gapped-installation) للحصول على إرشادات خطوة بخطوة لاستخدام `pip download` وإنشاء حزم wheel قابلة للنقل ومخصصة لكل نظام تشغيل على جهاز متصل بالإنترنت.

### 2. أرسِ مبادئ المشروع

شغّل وكيل البرمجة الخاص بك داخل مجلد المشروع. معظم الوكلاء يكشفون spec-kit عبر أوامر `/speckit.*`؛ بينما يستخدم Codex CLI في وضع المهارات `$speckit-*` بدلاً منها.

استخدم أمر **`/speckit.constitution`** لإنشاء المبادئ الحاكمة لمشروعك وإرشادات التطوير التي ستوجّه كل ما يليها من تطوير.

```bash
/speckit.constitution Create principles focused on code quality, testing standards, user experience consistency, and performance requirements
```

### 3. أنشئ المواصفة

استخدم أمر **`/speckit.specify`** لوصف ما تريد بناءه. ركّز على **ماذا** و**لماذا**، لا على المكدّس التقني.

```bash
/speckit.specify Build an application that can help me organize my photos in separate photo albums. Albums are grouped by date and can be re-organized by dragging and dropping on the main page. Albums are never in other nested albums. Within each album, photos are previewed in a tile-like interface.
```

### 4. أنشئ خطة تنفيذ تقنية

استخدم أمر **`/speckit.plan`** لتقديم اختياراتك للمكدّس التقني والمعمارية.

```bash
/speckit.plan The application uses Vite with minimal number of libraries. Use vanilla HTML, CSS, and JavaScript as much as possible. Images are not uploaded anywhere and metadata is stored in a local SQLite database.
```

### 5. قسّم العمل إلى مهام

استخدم **`/speckit.tasks`** لإنشاء قائمة مهام قابلة للتنفيذ من خطة التنفيذ.

```bash
/speckit.tasks
```

### 6. نفّذ

استخدم **`/speckit.implement`** لتنفيذ كل المهام وبناء الميزة وفق الخطة.

```bash
/speckit.implement
```

للحصول على تعليمات تفصيلية خطوة بخطوة، راجع [الدليل الشامل](./spec-driven.md).

## 📽️ نظرة عامة بالفيديو

تريد رؤية Spec Kit أثناء العمل؟ شاهد [نظرتنا العامة بالفيديو](https://www.youtube.com/watch?v=a9eR1xsfvHg&pp=0gcJCckJAYcqIYzv)!

[![Spec Kit video header](/media/spec-kit-video-header.jpg)](https://www.youtube.com/watch?v=a9eR1xsfvHg&pp=0gcJCckJAYcqIYzv)

## 🧩 امتدادات المجتمع

> [!NOTE]
> امتدادات المجتمع يصنعها ويصونها مؤلفوها بشكل مستقل. قد يراجع فريق GitHub ومشرفو Spec Kit طلبات الدمج التي تضيف مدخلات إلى كتالوج المجتمع من حيث التنسيق أو بنية الكتالوج أو الالتزام بالسياسة، لكنهم **لا يراجعون ولا يدققون ولا يصادقون ولا يدعمون كود الامتداد نفسه**. كذلك فإن موقع امتدادات المجتمع هو مورد طرف ثالث. راجع الشيفرة المصدرية للامتدادات قبل التثبيت واستخدمها بناءً على تقديرك الشخصي.

🔍 **تصفّح وابحث في امتدادات المجتمع عبر [موقع امتدادات المجتمع](https://speckit-community.github.io/extensions/).**

الامتدادات المساهَم بها من قِبل المجتمع متاحة في [`catalog.community.json`](extensions/catalog.community.json):

**التصنيفات:**

- `docs` — قراءة أو تحقق أو توليد لمصنوعات المواصفة
- `code` — مراجعة أو تحقق أو تعديل للشيفرة المصدرية
- `process` — تنسيق سير العمل عبر المراحل
- `integration` — مزامنة مع منصات خارجية
- `visibility` — تقارير عن صحة المشروع أو تقدّمه

**الأثر:**

- `Read-only` — يُنتج تقارير دون تعديل الملفات
- `Read+Write` — يعدّل الملفات أو يُنشئ مصنوعات أو يحدّث المواصفات

| الامتداد | الغرض | التصنيف | الأثر | الرابط |
|-----------|---------|----------|--------|-----|
| Agent Assign | تعيين وكلاء Claude Code متخصصين لمهام spec-kit من أجل تنفيذ موجّه | `process` | Read+Write | [spec-kit-agent-assign](https://github.com/xymelon/spec-kit-agent-assign) |
| AI-Driven Engineering (AIDE) | سير عمل منظَّم من 7 خطوات لبناء مشاريع جديدة من الصفر بمساعدة الذكاء الاصطناعي — من الرؤية حتى التنفيذ | `process` | Read+Write | [aide](https://github.com/mnriem/spec-kit-extensions/tree/main/aide) |
| Architect Impact Previewer | يتنبأ بالأثر المعماري والتعقيد والمخاطر للتغييرات المقترحة قبل التنفيذ. | `visibility` | Read-only | [spec-kit-architect-preview](https://github.com/UmmeHabiba1312/spec-kit-architect-preview) |
| Archive Extension | أرشفة الميزات المدموجة في الذاكرة الرئيسية للمشروع. | `docs` | Read+Write | [spec-kit-archive](https://github.com/stn1slv/spec-kit-archive) |
| Azure DevOps Integration | مزامنة قصص المستخدم والمهام إلى عناصر عمل Azure DevOps باستخدام مصادقة OAuth | `integration` | Read+Write | [spec-kit-azure-devops](https://github.com/pragya247/spec-kit-azure-devops) |
| Blueprint | ابقَ ملمًّا بالكود في التطوير المدفوع بالذكاء الاصطناعي: راجع مخططًا برمجيًا كاملاً لكل مهمة من مصنوعات المواصفة قبل تشغيل /speckit.implement | `docs` | Read+Write | [spec-kit-blueprint](https://github.com/chordpli/spec-kit-blueprint) |
| Branch Convention | أعراف قابلة للضبط لتسمية الفروع والمجلدات لأمر /specify مع وصفات وأنماط مخصصة | `process` | Read+Write | [spec-kit-branch-convention](https://github.com/Quratulain-bilal/spec-kit-branch-convention) |
| Brownfield Bootstrap | تهيئة spec-kit لقواعد كود قائمة — اكتشاف تلقائي للمعمارية وتبنّي SDD تدريجيًا | `process` | Read+Write | [spec-kit-brownfield](https://github.com/Quratulain-bilal/spec-kit-brownfield) |
| Bugfix Workflow | سير عمل منظَّم لإصلاح العلل — التقاط الأعطال وتتبّعها إلى مصنوعات المواصفة وترقيع المواصفات بدقّة | `process` | Read+Write | [spec-kit-bugfix](https://github.com/Quratulain-bilal/spec-kit-bugfix) |
| Canon | يضيف سير عمل قائمًا على المرجعية (canon-driven): spec-first و code-first و spec-drift. يتطلب تثبيت وصفة Canon Core. | `process` | Read+Write | [spec-kit-canon](https://github.com/maximiliamus/spec-kit-canon/tree/master/extension) |
| Catalog CI | تحقق آلي من مدخلات كتالوج مجتمع spec-kit — البنية والروابط والفروقات والـ linting | `process` | Read-only | [spec-kit-catalog-ci](https://github.com/Quratulain-bilal/spec-kit-catalog-ci) |
| CI Guard | بوابات امتثال للمواصفة في CI/CD — التحقق من وجود المواصفات، رصد الانحراف، وحجب الدمج عند الفجوات | `process` | Read-only | [spec-kit-ci-guard](https://github.com/Quratulain-bilal/spec-kit-ci-guard) |
| Checkpoint Extension | إجراء commit للتغييرات في منتصف التنفيذ حتى لا تنتهي بأمر commit ضخم واحد في النهاية | `code` | Read+Write | [spec-kit-checkpoint](https://github.com/aaronrsun/spec-kit-checkpoint) |
| Cleanup Extension | بوابة جودة بعد التنفيذ تراجع التغييرات وتصلح المشكلات الصغيرة (scout rule)، وتُنشئ مهامًا للمشكلات المتوسطة، وتولّد تحليلًا للكبيرة | `code` | Read+Write | [spec-kit-cleanup](https://github.com/dsrednicki/spec-kit-cleanup) |
| Conduct Extension | تنسيق مراحل spec-kit عبر تفويض الوكلاء الفرعيين لتقليل تلوّث السياق. | `process` | Read+Write | [spec-kit-conduct-ext](https://github.com/twbrandon7/spec-kit-conduct-ext) |
| Confluence Extension | إنشاء مستند في Confluence يلخّص ملفات المواصفة والتخطيط | `integration` | Read+Write | [spec-kit-confluence](https://github.com/aaronrsun/spec-kit-confluence) |
| DocGuard — CDD Enforcement | فرض التطوير المرجعي (CDD). يتحقق ويقيّم ويتتبع وثائق المشروع بفحوصات آلية وسير عمل مدفوع بالذكاء الاصطناعي وخطافات spec-kit. لا تبعيات NPM وقت التشغيل. | `docs` | Read+Write | [spec-kit-docguard](https://github.com/raccioly/docguard) |
| Extensify | إنشاء وتحقق من الامتدادات وكتالوجات الامتدادات | `process` | Read+Write | [extensify](https://github.com/mnriem/spec-kit-extensions/tree/main/extensify) |
| Fix Findings | حلقة آلية تحلل-تُصلح-تعيد التحليل تحلّ ملاحظات المواصفة حتى تخلو من الأخطاء | `code` | Read+Write | [spec-kit-fix-findings](https://github.com/Quratulain-bilal/spec-kit-fix-findings) |
| FixIt Extension | إصلاح علل بوعي بالمواصفة — ربط الأعطال بمصنوعات المواصفة، اقتراح خطة، وتطبيق أقل تغييرات ممكنة | `code` | Read+Write | [spec-kit-fixit](https://github.com/speckit-community/spec-kit-fixit) |
| Fleet Orchestrator | تنسيق دورة حياة كاملة لميزة مع بوابات يتدخل فيها الإنسان عبر كل مراحل SpecKit | `process` | Read+Write | [spec-kit-fleet](https://github.com/sharathsatish/spec-kit-fleet) |
| GitHub Issues Integration 1 | توليد مصنوعات المواصفة من GitHub Issues — استيراد المشاكل، مزامنة التحديثات، وتتبع ثنائي الاتجاه | `integration` | Read+Write | [spec-kit-github-issues](https://github.com/Fatima367/spec-kit-github-issues) |
| GitHub Issues Integration 2 | إنشاء ومزامنة مواصفات محلية من مشكلة GitHub قائمة | `integration` | Read+Write | [spec-kit-issue](https://github.com/aaronrsun/spec-kit-issue) |
| Iterate | كرّر على مستندات المواصفة بسير عمل من مرحلتين «تعريف وتطبيق» — صقل المواصفات في منتصف التنفيذ والعودة مباشرةً للبناء | `docs` | Read+Write | [spec-kit-iterate](https://github.com/imviancagrace/spec-kit-iterate) |
| Jira Integration | إنشاء Epics و Stories و Issues في Jira من مواصفات spec-kit وتقسيمات المهام مع تسلسل هرمي قابل للضبط ودعم الحقول المخصصة | `integration` | Read+Write | [spec-kit-jira](https://github.com/mbachorik/spec-kit-jira) |
| Learning Extension | توليد أدلة تعليمية من عمليات التنفيذ وإثراء التوضيحات بسياق إرشادي | `docs` | Read+Write | [spec-kit-learn](https://github.com/imviancagrace/spec-kit-learn) |
| MAQA — Multi-Agent & Quality Assurance | سير عمل بوكيل منسّق ← ميزة ← ضمان جودة مع تنفيذ متوازٍ مبنيٍّ على worktrees. مستقل عن اللغة. يكتشف إضافات اللوحات المثبتة تلقائيًا. بوابة CI اختيارية. | `process` | Read+Write | [spec-kit-maqa-ext](https://github.com/GenieRobot/spec-kit-maqa-ext) |
| MAQA Azure DevOps Integration | تكامل لوحات Azure DevOps مع MAQA — يزامن قصص المستخدم وأبناء المهام مع تقدّم الميزات | `integration` | Read+Write | [spec-kit-maqa-azure-devops](https://github.com/GenieRobot/spec-kit-maqa-azure-devops) |
| MAQA CI/CD Gate | يكتشف تلقائيًا GitHub Actions و CircleCI و GitLab CI و Bitbucket Pipelines. يحجب التسليم لـ QA حتى يكتمل الـ pipeline بنجاح. | `process` | Read+Write | [spec-kit-maqa-ci](https://github.com/GenieRobot/spec-kit-maqa-ci) |
| MAQA GitHub Projects Integration | تكامل GitHub Projects v2 مع MAQA — يزامن المسوّدات وأعمدة الحالة مع تقدّم الميزات | `integration` | Read+Write | [spec-kit-maqa-github-projects](https://github.com/GenieRobot/spec-kit-maqa-github-projects) |
| MAQA Jira Integration | تكامل Jira مع MAQA — يزامن Stories و Subtasks مع تقدّم الميزات عبر اللوحة | `integration` | Read+Write | [spec-kit-maqa-jira](https://github.com/GenieRobot/spec-kit-maqa-jira) |
| MAQA Linear Integration | تكامل Linear مع MAQA — يزامن المشاكل والمشاكل الفرعية عبر حالات سير العمل مع تقدّم الميزات | `integration` | Read+Write | [spec-kit-maqa-linear](https://github.com/GenieRobot/spec-kit-maqa-linear) |
| MAQA Trello Integration | تكامل لوحات Trello مع MAQA — يملأ اللوحة من المواصفات وينقل البطاقات ويعلّم قوائم التحقق في الوقت الحقيقي | `integration` | Read+Write | [spec-kit-maqa-trello](https://github.com/GenieRobot/spec-kit-maqa-trello) |
| MarkItDown Document Converter | تحويل المستندات (PDF و Word و PowerPoint و Excel وغيرها) إلى Markdown لاستخدامها كمراجع للمواصفة | `docs` | Read+Write | [spec-kit-markitdown](https://github.com/BenBtg/spec-kit-markitdown) |
| Memory Loader | يحمّل ملفات .specify/memory/ قبل أوامر دورة الحياة لتزويد وكلاء LLM بسياق حوكمة المشروع | `docs` | Read-only | [spec-kit-memory-loader](https://github.com/KevinBrown5280/spec-kit-memory-loader) |
| Memory MD | ذاكرة دائمة أصيلة داخل المستودع لمشاريع Spec Kit | `docs` | Read+Write | [spec-kit-memory-hub](https://github.com/DyanGalih/spec-kit-memory-hub) |
| MemoryLint | أداة حوكمة لذاكرة الوكيل: تدقّق وتصلح تلقائيًا تعارضات الحدود بين AGENTS.md ودستور المشروع. | `process` | Read+Write | [memorylint](https://github.com/RbBtSn0w/spec-kit-extensions/tree/main/memorylint) |
| Microsoft 365 Integration | جلب رسائل Teams ونصوص الاجتماعات وملفات SharePoint/OneDrive كملفات Markdown محلية لتوليد المواصفات | `integration` | Read+Write | [spec-kit-m365](https://github.com/BenBtg/spec-kit-m365) |
| Onboard | تأهيل سياقي ونمو تدريجي للمطورين الجدد على مشاريع spec-kit. يشرح المواصفات ويرسم الاعتماديات ويتحقق من الفهم ويرشد إلى الخطوة التالية | `process` | Read+Write | [spec-kit-onboard](https://github.com/dmux/spec-kit-onboard) |
| Optimize | تدقيق وتحسين حوكمة الذكاء الاصطناعي لكفاءة السياق — ميزانيات الرموز، صحة القواعد، القابلية للتفسير، الضغط، التماسك، واكتشاف الترديد | `process` | Read+Write | [spec-kit-optimize](https://github.com/sakitA/spec-kit-optimize) |
| OWASP LLM Threat Model | تحليل تهديدات OWASP Top 10 لتطبيقات LLM لعام 2025 على مصنوعات الوكيل | `code` | Read-only | [spec-kit-threatmodel](https://github.com/NaviaSamal/spec-kit-threatmodel) |
| Plan Review Gate | اشتراط دمج spec.md و plan.md عبر MR/PR قبل السماح بتوليد المهام | `process` | Read-only | [spec-kit-plan-review-gate](https://github.com/luno/spec-kit-plan-review-gate) |
| PR Bridge | توليد تلقائي لأوصاف طلبات الدمج وقوائم التحقق والملخصات من مصنوعات المواصفة | `process` | Read-only | [spec-kit-pr-bridge-](https://github.com/Quratulain-bilal/spec-kit-pr-bridge-) |
| Presetify | إنشاء وتحقق من الوصفات وكتالوجات الوصفات | `process` | Read+Write | [presetify](https://github.com/mnriem/spec-kit-extensions/tree/main/presetify) |
| Product Forge | دورة حياة منتج كاملة من البحث إلى الإصدار — محفظة، وضع مبسط، monorepo، V-Model اختياري | `process` | Read+Write | [speckit-product-forge](https://github.com/VaiYav/speckit-product-forge) |
| Project Health Check | تشخيص مشروع Spec Kit والإبلاغ عن مشكلات الصحة عبر البنية والوكلاء والميزات والسكربتات والامتدادات و git | `visibility` | Read-only | [spec-kit-doctor](https://github.com/KhawarHabibKhan/spec-kit-doctor) |
| Project Status | عرض تقدّم سير عمل SDD الحالي — الميزة النشطة، حالة المصنوعات، اكتمال المهام، مرحلة سير العمل، وملخص الامتدادات | `visibility` | Read-only | [spec-kit-status](https://github.com/KhawarHabibKhan/spec-kit-status) |
| QA Testing Extension | اختبار ضمان جودة منهجي مع تحقق من معايير القبول من المواصفة عبر المتصفح أو CLI | `code` | Read-only | [spec-kit-qa](https://github.com/arunt14/spec-kit-qa) |
| Ralph Loop | حلقة تنفيذ ذاتية باستخدام CLI لوكيل ذكاء اصطناعي | `code` | Read+Write | [spec-kit-ralph](https://github.com/Rubiss/spec-kit-ralph) |
| Reconcile Extension | معالجة الانحراف في التنفيذ بتحديث مصنوعات الميزة بدقّة. | `docs` | Read+Write | [spec-kit-reconcile](https://github.com/stn1slv/spec-kit-reconcile) |
| Red Team | مراجعة معاكسة للمواصفات قبل /speckit.plan — وكلاء بعدسات متوازية يكشفون مخاطر لا تستطيع clarify/analyze رصدها بنيويًا (حقن المطالبات، فجوات النزاهة، انحراف بين المواصفات، الأعطال الصامتة). يُنتج تقرير ملاحظات منظَّم؛ لا تعديلات تلقائية على المواصفات. | `docs` | Read+Write | [spec-kit-red-team](https://github.com/ashbrener/spec-kit-red-team) |
| Repository Index | توليد فهرس لمستودع قائم على مستوى النظرة العامة والمعمارية والوحدات. | `docs` | Read-only | [spec-kit-repoindex](https://github.com/liuyiyu/spec-kit-repoindex) |
| Retro Extension | تحليل استرجاعي للسبرنت بقياسات وتقييم دقة المواصفة واقتراحات تحسين | `process` | Read+Write | [spec-kit-retro](https://github.com/arunt14/spec-kit-retro) |
| Retrospective Extension | استرجاع ما بعد التنفيذ مع تقييم الالتزام بالمواصفة وتحليل الانحراف وتحديثات للمواصفات يصادق عليها الإنسان | `docs` | Read+Write | [spec-kit-retrospective](https://github.com/emi-dm/spec-kit-retrospective) |
| Review Extension | مراجعة شاملة للكود بعد التنفيذ بوكلاء متخصصين في جودة الكود والتعليقات والاختبارات ومعالجة الأخطاء وتصميم الأنواع والتبسيط | `code` | Read-only | [spec-kit-review](https://github.com/ismaelJimenez/spec-kit-review) |
| Ripple | اكتشاف الآثار الجانبية التي لا تلتقطها الاختبارات بعد التنفيذ — تحليل مرتكز على الفروق عبر 9 تصنيفات مستقلة عن المجال | `code` | Read+Write | [spec-kit-ripple](https://github.com/chordpli/spec-kit-ripple) |
| SDD Utilities | استئناف سير العمل المتوقف، التحقق من صحة المشروع، والتأكد من تتبّع المواصفة إلى المهام | `process` | Read+Write | [speckit-utils](https://github.com/mvanhorn/speckit-utils) |
| Security Review | مراجعات أمنية شاملة للمشروع بمبدأ secure-by-design إضافة إلى مراجعات مرحلية على الفرع/طلب الدمج والخطة والمهام والمتابعة والتطبيق | `code` | Read+Write | [spec-kit-security-review](https://github.com/DyanGalih/spec-kit-security-review) |
| SFSpeckit | دورة حياة Salesforce للمؤسسات مع 18 أمرًا لدورة SDD كاملة. | `process` | Read+Write | [spec-kit-sf](https://github.com/ysumanth06/spec-kit-sf) |
| Ship Release Extension | أتمتة خط إصدار: فحوصات ما قبل الإقلاع، مزامنة الفروع، توليد changelog، التحقق من CI، وإنشاء PR | `process` | Read+Write | [spec-kit-ship](https://github.com/arunt14/spec-kit-ship) |
| Spec Reference Loader | يقرأ قسم ## References من مواصفة الميزة ويحمّل فقط المستندات المدرجة إلى السياق | `docs` | Read-only | [spec-kit-spec-reference-loader](https://github.com/KevinBrown5280/spec-kit-spec-reference-loader) |
| Spec Critique Extension | مراجعة نقدية بعدستين للمواصفة والخطة من منظور استراتيجية المنتج ومخاطر الهندسة | `docs` | Read-only | [spec-kit-critique](https://github.com/arunt14/spec-kit-critique) |
| Spec Diagram | توليد تلقائي لمخططات Mermaid لحالة سير عمل SDD وتقدّم الميزة واعتماديات المهام | `visibility` | Read-only | [spec-kit-diagram-](https://github.com/Quratulain-bilal/spec-kit-diagram-) |
| Spec Orchestrator | تنسيق عابر للميزات — تتبّع الحالة، اختيار المهام، واكتشاف التعارضات عبر المواصفات المتوازية | `process` | Read-only | [spec-kit-orchestrator](https://github.com/Quratulain-bilal/spec-kit-orchestrator) |
| Spec Refine | تحديث المواصفات في مكانها ونشر التغييرات إلى الخطة والمهام ورصد الأثر عبر المصنوعات | `process` | Read+Write | [spec-kit-refine](https://github.com/Quratulain-bilal/spec-kit-refine) |
| Spec Scope | تقدير الجهد وتتبّع النطاق — تقدير العمل، اكتشاف التضخّم، وتخصيص وقت لكل مرحلة | `process` | Read-only | [spec-kit-scope-](https://github.com/Quratulain-bilal/spec-kit-scope-) |
| Spec Sync | اكتشاف وحلّ الانحراف بين المواصفات والتنفيذ. حلّ بمساعدة الذكاء الاصطناعي بموافقة بشرية | `docs` | Read+Write | [spec-kit-sync](https://github.com/bgervin/spec-kit-sync) |
| Spec Validate | التحقق من الفهم وبوابات المراجعة وحالة الموافقة لمصنوعات spec-kit — اختبارات مرحلية و SLA لمراجعة الأقران وبوابة صارمة قبل /speckit.implement | `process` | Read+Write | [spec-kit-spec-validate](https://github.com/aeltayeb/spec-kit-spec-validate) |
| Spec2Cloud | سير عمل مدفوع بالمواصفة مهيَّأ للنشر على Azure | `process` | Read+Write | [spec2cloud](https://github.com/Azure-Samples/Spec2Cloud) |
| SpecTest | توليد تلقائي لهياكل اختبار من معايير المواصفة، ربط التغطية، وإيجاد المتطلبات غير المختبَرة | `code` | Read+Write | [spec-kit-spectest](https://github.com/Quratulain-bilal/spec-kit-spectest) |
| Squad Bridge | تهيئة ومزامنة فريق وكلاء Squad من مواصفة Speckit ومهامها | `process` | Read+Write | [spec-kit-squad](https://github.com/jwill824/spec-kit-squad) |
| Staff Review Extension | مراجعة كود بمستوى staff engineer تتحقق من مطابقة التنفيذ للمواصفة وتفحص الأمان والأداء وتغطية الاختبارات | `code` | Read-only | [spec-kit-staff-review](https://github.com/arunt14/spec-kit-staff-review) |
| Status Report | حالة المشروع وتقدّم الميزة وتوصيات الإجراء التالي لسير العمل المدفوع بالمواصفة | `visibility` | Read-only | [Open-Agent-Tools/spec-kit-status](https://github.com/Open-Agent-Tools/spec-kit-status) |
| Superpowers Bridge | ينسّق مهارات obra/superpowers ضمن سير عمل spec-kit عبر كامل دورة الحياة (التوضيح، TDD، المراجعة، التحقق، النقد، التنقيح، إكمال الفرع) | `process` | Read+Write | [superpowers-bridge](https://github.com/RbBtSn0w/spec-kit-extensions/tree/main/superpowers-bridge) |
| Superpowers Bridge (WangX0111) | يربط spec-kit بـ obra/superpowers (العصف الذهني، TDD، الوكيل الفرعي، مراجعة الكود) في سير عمل موحّد قابل للاستئناف مع تدهور سلس وتتبّع تقدّم الجلسة | `process` | Read+Write | [superspec](https://github.com/WangX0111/superspec) |
| TinySpec | سير عمل خفيف بملف واحد للمهام الصغيرة — تخطّي عملية SDD الثقيلة متعددة الخطوات | `process` | Read+Write | [spec-kit-tinyspec](https://github.com/Quratulain-bilal/spec-kit-tinyspec) |
| Token Consumption Analyzer | يلتقط ويحلّل ويقارن استهلاك الرموز عبر مسارات سير عمل SDD | `visibility` | Read-only | [spec-kit-token-analyzer](https://github.com/coderandhiker/spec-kit-token-analyzer) |
| V-Model Extension Pack | يفرض توليدًا مزدوجًا وفق V-Model لمواصفات التطوير ومواصفات الاختبار مع تتبّع كامل | `docs` | Read+Write | [spec-kit-v-model](https://github.com/leocamello/spec-kit-v-model) |
| Verify Extension | بوابة جودة بعد التنفيذ تتحقق من مطابقة الكود المنفَّذ لمصنوعات المواصفة | `code` | Read-only | [spec-kit-verify](https://github.com/ismaelJimenez/spec-kit-verify) |
| Verify Tasks Extension | اكتشاف الإنجازات الوهمية: المهام المعلَّمة [X] في tasks.md دون تنفيذ حقيقي | `code` | Read-only | [spec-kit-verify-tasks](https://github.com/datastone-inc/spec-kit-verify-tasks) |
| Version Guard | التحقق من إصدارات المكدّس التقني مقابل سجلات npm الحيّة قبل التخطيط والتنفيذ | `process` | Read-only | [spec-kit-version-guard](https://github.com/KevinBrown5280/spec-kit-version-guard) |
| What-if Analysis | معاينة الأثر اللاحق (التعقيد، الجهد، المهام، المخاطر) لتغييرات المتطلبات قبل الالتزام بها | `visibility` | Read-only | [spec-kit-whatif](https://github.com/DevAbdullah90/spec-kit-whatif) |
| Wireframe Visual Feedback Loop | توليد ومراجعة واعتماد wireframes بصيغة SVG للتطوير المدفوع بالمواصفة. تصبح الـ wireframes المعتمدة قيودًا تلتزم بها /speckit.plan و /speckit.tasks و /speckit.implement | `visibility` | Read+Write | [spec-kit-extension-wireframe](https://github.com/TortoiseWolfe/spec-kit-extension-wireframe) |
| Work IQ | دمج معرفة مؤسسة Microsoft 365 في سير العمل المدفوع بالمواصفة | `integration` | Read-only | [spec-kit-workiq](https://github.com/sakitA/spec-kit-workiq) |
| Worktree Isolation | إنشاء worktrees معزولة في git لتطوير ميزات متوازية دون التبديل بـ checkout | `process` | Read+Write | [spec-kit-worktree](https://github.com/Quratulain-bilal/spec-kit-worktree) |
| Worktrees | عزل worktree افتراضي للوكلاء المتوازين — بترتيب شقيق أو متشعّب | `process` | Read+Write | [spec-kit-worktree-parallel](https://github.com/dango85/spec-kit-worktree-parallel) |

لتقديم امتدادك الخاص، راجع [دليل نشر الامتدادات](extensions/EXTENSION-PUBLISHING-GUIDE.md).

## 🎨 وصفات المجتمع

تخصّص وصفات المجتمع طريقة عمل Spec Kit — إذ تتجاوز القوالب والأوامر والمصطلحات دون أي تعديل في الأدوات. راجع القائمة الكاملة على صفحة [وصفات المجتمع](https://github.github.io/spec-kit/community/presets.html).

> [!NOTE]
> وصفات المجتمع مساهمات طرف ثالث ولا يصونها فريق Spec Kit. راجعها بعناية قبل الاستخدام، واطّلع على إخلاء المسؤولية الكامل في صفحة الوثائق أعلاه.

لتقديم وصفتك الخاصة، راجع [دليل نشر الوصفات](presets/PUBLISHING.md).

## 🚶 جولات المجتمع

شاهد التطوير المعتمد على المواصفات في سيناريوهات مختلفة عبر جولات مساهَم بها من المجتمع؛ القائمة الكاملة موجودة على صفحة [جولات المجتمع](https://github.github.io/spec-kit/community/walkthroughs.html).

## 🛠️ أصدقاء المجتمع

مشاريع مجتمعية تمدّ أو تصوّر أو تبني فوق Spec Kit. راجع القائمة الكاملة على صفحة [أصدقاء المجتمع](https://github.github.io/spec-kit/community/friends.html).

## 🤖 وكلاء البرمجة بالذكاء الاصطناعي المدعومون

يعمل Spec Kit مع أكثر من 30 وكيل برمجة بالذكاء الاصطناعي — سواء أكانت أدوات CLI أم مساعدين داخل بيئات التطوير. راجع القائمة الكاملة مع الملاحظات وتفاصيل الاستخدام في دليل [وكلاء البرمجة بالذكاء الاصطناعي المدعومين](https://github.github.io/spec-kit/reference/integrations.html).

شغّل `specify integration list` لعرض كل التكاملات المتاحة في الإصدار المثبت لديك.

## الأوامر المتاحة (Slash Commands)

بعد تشغيل `specify init`، سيتمكن وكيل البرمجة لديك من الوصول إلى هذه الأوامر للتطوير المنظَّم. للتكاملات التي تدعم وضع المهارات، يؤدي تمرير `--integration <agent> --integration-options="--skills"` إلى تثبيت مهارات الوكيل بدلاً من ملفات المطالبات الخاصة بأوامر slash.

#### الأوامر الأساسية

الأوامر الجوهرية لسير عمل التطوير المعتمد على المواصفات:

| الأمر                  | مهارة الوكيل            | الوصف                                                                |
| ------------------------ | ---------------------- | -------------------------------------------------------------------------- |
| `/speckit.constitution`  | `speckit-constitution` | إنشاء أو تحديث المبادئ الحاكمة للمشروع وإرشادات التطوير   |
| `/speckit.specify`       | `speckit-specify`      | تعريف ما تريد بناءه (المتطلبات وقصص المستخدم)              |
| `/speckit.plan`          | `speckit-plan`         | إنشاء خطط تنفيذ تقنية بالمكدّس الذي تختاره          |
| `/speckit.tasks`         | `speckit-tasks`        | توليد قوائم مهام قابلة للتنفيذ                          |
| `/speckit.taskstoissues` | `speckit-taskstoissues`| تحويل قوائم المهام المولَّدة إلى GitHub issues للتتبّع والتنفيذ |
| `/speckit.implement`     | `speckit-implement`    | تنفيذ كل المهام لبناء الميزة وفق الخطة               |

#### الأوامر الاختيارية

أوامر إضافية لتحسين الجودة والتحقق:

| الأمر              | مهارة الوكيل            | الوصف                                                                                                                          |
| -------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `/speckit.clarify`   | `speckit-clarify`      | توضيح المناطق غير المحدَّدة بشكل كافٍ (موصى به قبل `/speckit.plan`؛ كان سابقًا `/quizme`)                                                |
| `/speckit.analyze`   | `speckit-analyze`      | تحليل الاتساق والتغطية عبر المصنوعات (يُشغَّل بعد `/speckit.tasks` وقبل `/speckit.implement`)                             |
| `/speckit.checklist` | `speckit-checklist`    | توليد قوائم تحقق جودة مخصصة تتحقق من اكتمال المتطلبات ووضوحها واتساقها (مثل «اختبارات وحدة للغة الإنجليزية») |

## 🔧 مرجع Specify CLI

للاطلاع على تفاصيل الأوامر والخيارات والأمثلة كاملةً، راجع [مرجع CLI](https://github.github.io/spec-kit/reference/overview.html).

## 🧩 خصّص Spec Kit حسب احتياجك: الامتدادات والوصفات

يمكنك تكييف Spec Kit مع احتياجاتك عبر نظامين متكاملين — **الامتدادات** و**الوصفات** — إضافة إلى التجاوزات المحلية للمشروع للتعديلات الفردية:

| الأولوية | نوع المكوّن                                    | الموقع                         |
| -------: | ------------------------------------------------- | -------------------------------- |
|      ⬆ 1 | تجاوزات محلية للمشروع                           | `.specify/templates/overrides/`  |
|        2 | الوصفات — تخصيص النواة والامتدادات             | `.specify/presets/templates/`    |
|        3 | الامتدادات — إضافة قدرات جديدة                 | `.specify/extensions/templates/` |
|      ⬇ 4 | نواة Spec Kit — أوامر وقوالب SDD المدمجة | `.specify/templates/`            |

- **القوالب** تُحلّ في **وقت التشغيل** — يمشي Spec Kit من أعلى المكدّس إلى أسفله ويستخدم أول مطابقة.
- التجاوزات المحلية للمشروع (`.specify/templates/overrides/`) تتيح لك إجراء تعديلات فردية لمشروع واحد دون إنشاء وصفة كاملة.
- **أوامر الامتدادات/الوصفات** تُطبَّق **وقت التثبيت** — عندما تشغّل `specify extension add` أو `specify preset add`، تُكتب ملفات الأوامر إلى مجلدات الوكلاء (مثل `.claude/commands/`).
- إذا قدّمت عدة وصفات أو امتدادات الأمر نفسه، يفوز الإصدار صاحب الأولوية الأعلى. وعند الإزالة، يُستعاد الإصدار التالي في الأولوية تلقائيًا.
- إن لم تكن هناك تجاوزات أو تخصيصات، يستخدم Spec Kit إعداداته الافتراضية الأساسية.

### الامتدادات — إضافة قدرات جديدة

استخدم **الامتدادات** عندما تحتاج وظيفة تتجاوز نواة Spec Kit. تُقدّم الامتدادات أوامر وقوالب جديدة — مثلاً إضافة سير عمل خاص بمجال معين لا تغطّيه أوامر SDD المدمجة، أو التكامل مع أدوات خارجية، أو إضافة مراحل تطوير جديدة كليًا. هي توسّع *ما يستطيع Spec Kit فعله*.

```bash
# البحث عن الامتدادات المتاحة
specify extension search

# تثبيت امتداد
specify extension add <extension-name>
```

مثلًا قد تضيف الامتدادات تكامل Jira، أو مراجعة الكود بعد التنفيذ، أو تتبّع اختبارات V-Model، أو تشخيص صحة المشروع.

راجع [مرجع الامتدادات](https://github.github.io/spec-kit/reference/extensions.html) للدليل الكامل للأوامر. تصفّح [امتدادات المجتمع](#-community-extensions) أعلاه لمعرفة المتاح.

### الوصفات — تخصيص سير العمل القائم

استخدم **الوصفات** حين تريد تغيير *كيفية* عمل Spec Kit دون إضافة قدرات جديدة. تتجاوز الوصفات القوالب والأوامر المرفقة بالنواة *وبالامتدادات المثبتة* — مثلًا فرض صيغة مواصفة متوافقة مع الامتثال، أو استخدام مصطلحات متخصصة بمجال معيّن، أو تطبيق معايير المؤسسة على الخطط والمهام. هي تخصّص المصنوعات والتعليمات التي يولّدها Spec Kit وامتداداته.

```bash
# البحث عن الوصفات المتاحة
specify preset search

# تثبيت وصفة
specify preset add <preset-name>
```

مثلًا قد تعيد الوصفات تشكيل قوالب المواصفة لاشتراط تتبّع تنظيمي، أو تكيّف سير العمل ليناسب المنهجية التي تستخدمها (Agile أو Kanban أو Waterfall أو jobs-to-be-done أو التصميم المدفوع بالمجال)، أو تضيف بوابات إلزامية للمراجعة الأمنية على الخطط، أو تفرض ترتيب المهام بإسبقية الاختبارات، أو تترجم سير العمل بالكامل إلى لغة أخرى. يُظهر [العرض التوضيحي pirate-speak](https://github.com/mnriem/spec-kit-pirate-speak-preset-demo) كم يمكن أن يصل التخصيص. يمكن تكديس عدة وصفات وترتيبها بالأولوية.

راجع [مرجع الوصفات](https://github.github.io/spec-kit/reference/presets.html) للدليل الكامل للأوامر، بما في ذلك ترتيب الحلّ وتكديس الأولوية.

### متى تستخدم كلًّا منها

| الهدف | الاستخدام |
| --- | --- |
| إضافة أمر أو سير عمل جديد كليًا | امتداد |
| تخصيص صيغة المواصفات أو الخطط أو المهام | وصفة |
| التكامل مع أداة أو خدمة خارجية | امتداد |
| فرض معايير مؤسسية أو تنظيمية | وصفة |
| توفير قوالب قابلة لإعادة الاستخدام خاصة بمجال | كلاهما — وصفات لتجاوز القوالب، وامتدادات للقوالب المحزَّمة مع أوامر جديدة |

## 📚 الفلسفة الأساسية

التطوير المعتمد على المواصفات عملية منظَّمة تركّز على:

- **التطوير المدفوع بالنية** حيث تعرّف المواصفات «*ماذا*» قبل «*كيف*»
- **إنشاء مواصفات غنية** باستخدام ضوابط ومبادئ تنظيمية
- **الصقل متعدد الخطوات** بدلاً من توليد كود من المطالبات بمحاولة واحدة
- **اعتماد كبير** على قدرات نماذج الذكاء الاصطناعي المتقدمة لتفسير المواصفات

## 🌟 مراحل التطوير

| المرحلة                                    | التركيز                    | الأنشطة الرئيسية                                                                                                                                                     |
| ---------------------------------------- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **التطوير من 0 إلى 1** («Greenfield»)    | التوليد من الصفر    | <ul><li>الانطلاق من متطلبات عالية المستوى</li><li>توليد المواصفات</li><li>التخطيط لخطوات التنفيذ</li><li>بناء تطبيقات جاهزة للإنتاج</li></ul> |
| **الاستكشاف الإبداعي**                 | تنفيذات متوازية | <ul><li>استكشاف حلول متنوعة</li><li>دعم مكدّسات تقنية ومعماريات متعددة</li><li>تجريب أنماط تجربة المستخدم</li></ul>                         |
| **التحسين التكراري** («Brownfield») | تحديث الأنظمة القائمة | <ul><li>إضافة الميزات تكراريًا</li><li>تحديث الأنظمة القديمة</li><li>تكييف العمليات</li></ul>                                                                |

## 🎯 الأهداف التجريبية

يركّز بحثنا وتجريبنا على:

### استقلالية التقنية

- إنشاء تطبيقات باستخدام مكدّسات تقنية متنوعة
- التحقق من فرضية أن التطوير المعتمد على المواصفات عملية لا ترتبط بتقنيات أو لغات برمجة أو أُطر بعينها

### قيود المؤسسات

- إثبات إمكانية تطوير تطبيقات بالغة الأهمية
- دمج قيود المؤسسة (مزودي السحابة، المكدّسات التقنية، الممارسات الهندسية)
- دعم أنظمة التصميم الخاصة بالمؤسسات ومتطلبات الامتثال

### التطوير المتمحور حول المستخدم

- بناء تطبيقات لشرائح وتفضيلات مستخدمين مختلفة
- دعم مقاربات تطوير متنوعة (من vibe-coding إلى التطوير الأصيل بالذكاء الاصطناعي)

### العمليات الإبداعية والتكرارية

- التحقق من مفهوم استكشاف التنفيذ المتوازي
- تقديم مسارات قوية للتطوير التكراري للميزات
- توسيع العمليات لتشمل الترقيات ومهام التحديث

## 🔧 المتطلبات الأساسية

- **Linux/macOS/Windows**
- وكيل برمجة بالذكاء الاصطناعي [مدعوم](#-supported-ai-coding-agent-integrations).
- [uv](https://docs.astral.sh/uv/) لإدارة الحزم (موصى به) أو [pipx](https://pypa.github.io/pipx/) للتثبيت الدائم
- [Python 3.11+](https://www.python.org/downloads/)
- [Git](https://git-scm.com/downloads)

إذا واجهت مشكلات مع وكيل، الرجاء فتح issue لكي نتمكن من تحسين التكامل.

## 📖 تعلّم المزيد

- **[منهجية التطوير المعتمد على المواصفات الكاملة](./spec-driven.md)** - تعمّق في العملية الكاملة
- **[الجولة التفصيلية](#-detailed-process)** - دليل تنفيذ خطوة بخطوة

---

## 📋 الخطوات التفصيلية

<details>
<summary>اضغط لتوسيع الجولة التفصيلية خطوة بخطوة</summary>

يمكنك استخدام Specify CLI لتهيئة مشروعك، حيث سيُحضر المصنوعات المطلوبة إلى بيئتك. شغّل:

```bash
specify init <project_name>
```

أو هيّئ في المجلد الحالي:

```bash
specify init .
# أو استخدم خيار --here
specify init --here
# تخطّي التأكيد إذا كان المجلد يحوي ملفات
specify init . --force
# أو
specify init --here --force
```

![Specify CLI bootstrapping a new project in the terminal](./media/specify_cli.gif)

ستُطالَب باختيار تكامل وكيل البرمجة الذي تستخدمه. ويمكنك أيضًا تحديده مباشرة من سطر الأوامر:

```bash
specify init <project_name> --integration copilot
specify init <project_name> --integration gemini
specify init <project_name> --integration codex

# أو في المجلد الحالي:
specify init . --integration copilot
specify init . --integration codex --integration-options="--skills"

# أو استخدم خيار --here
specify init --here --integration copilot
specify init --here --integration codex --integration-options="--skills"

# فرض الدمج داخل مجلد حالي غير فارغ
specify init . --force --integration copilot

# أو
specify init --here --force --integration copilot
```

سيتحقق CLI من تثبيت Claude Code أو Gemini CLI أو Cursor CLI أو Qwen CLI أو opencode أو Codex CLI أو Qoder CLI أو Tabnine CLI أو Kiro CLI أو Pi أو Forge أو Goose أو Mistral Vibe لديك. إن لم تكن مثبتة، أو إن كنت تفضّل الحصول على القوالب دون التحقق من الأدوات المناسبة، استخدم `--ignore-agent-tools` مع أمرك:

```bash
specify init <project_name> --integration copilot --ignore-agent-tools
```

### **الخطوة 1:** أرسِ مبادئ المشروع

اذهب إلى مجلد المشروع وشغّل وكيل البرمجة. في مثالنا، نستخدم `claude`.

![Bootstrapping Claude Code environment](./media/bootstrap-claude-code.gif)

ستعرف أن الإعداد صحيح إذا رأيت أوامر `/speckit.constitution` و `/speckit.specify` و `/speckit.plan` و `/speckit.tasks` و `/speckit.implement` متاحة.

الخطوة الأولى ينبغي أن تكون إرساء المبادئ الحاكمة لمشروعك باستخدام أمر `/speckit.constitution`. يساعد ذلك في ضمان اتخاذ قرارات متّسقة في كل مراحل التطوير اللاحقة:

```text
/speckit.constitution Create principles focused on code quality, testing standards, user experience consistency, and performance requirements. Include governance for how these principles should guide technical decisions and implementation choices.
```

تنشئ هذه الخطوة أو تحدّث ملف `.specify/memory/constitution.md` بإرشادات مشروعك التأسيسية التي سيرجع إليها وكيل البرمجة أثناء مراحل المواصفة والتخطيط والتنفيذ.

### **الخطوة 2:** أنشئ مواصفات المشروع

بعد إرساء مبادئ مشروعك، يمكنك الآن إنشاء المواصفات الوظيفية. استخدم أمر `/speckit.specify` ثم قدّم متطلبات ملموسة للمشروع الذي تريد تطويره.

> [!IMPORTANT]
> كن صريحًا قدر الإمكان حول *ما* تحاول بناءه و*لماذا*. **لا تركّز على المكدّس التقني في هذه المرحلة**.

مثال على مطالبة:

```text
Develop Taskify, a team productivity platform. It should allow users to create projects, add team members,
assign tasks, comment and move tasks between boards in Kanban style. In this initial phase for this feature,
let's call it "Create Taskify," let's have multiple users but the users will be declared ahead of time, predefined.
I want five users in two different categories, one product manager and four engineers. Let's create three
different sample projects. Let's have the standard Kanban columns for the status of each task, such as "To Do,"
"In Progress," "In Review," and "Done." There will be no login for this application as this is just the very
first testing thing to ensure that our basic features are set up. For each task in the UI for a task card,
you should be able to change the current status of the task between the different columns in the Kanban work board.
You should be able to leave an unlimited number of comments for a particular card. You should be able to, from that task
card, assign one of the valid users. When you first launch Taskify, it's going to give you a list of the five users to pick
from. There will be no password required. When you click on a user, you go into the main view, which displays the list of
projects. When you click on a project, you open the Kanban board for that project. You're going to see the columns.
You'll be able to drag and drop cards back and forth between different columns. You will see any cards that are
assigned to you, the currently logged in user, in a different color from all the other ones, so you can quickly
see yours. You can edit any comments that you make, but you can't edit comments that other people made. You can
delete any comments that you made, but you can't delete comments anybody else made.
```

بعد إدخال هذه المطالبة، سترى Claude Code يبدأ عملية التخطيط وصياغة المواصفة. سيشغّل Claude Code أيضًا بعض السكربتات المدمجة لإعداد المستودع.

عند اكتمال هذه الخطوة، يجب أن يكون لديك فرع جديد (مثل `001-create-taskify`) ومواصفة جديدة في مجلد `specs/001-create-taskify`.

ينبغي أن تتضمن المواصفة المنتَجة مجموعة من قصص المستخدم والمتطلبات الوظيفية، كما هو محدد في القالب.

في هذه المرحلة، يجب أن تشبه محتويات مجلد مشروعك ما يلي:

```text
└── .specify
    ├── memory
    │  └── constitution.md
    ├── scripts
    │  ├── check-prerequisites.sh
    │  ├── common.sh
    │  ├── create-new-feature.sh
    │  ├── setup-plan.sh
    │  └── update-claude-md.sh
    ├── specs
    │  └── 001-create-taskify
    │      └── spec.md
    └── templates
        ├── plan-template.md
        ├── spec-template.md
        └── tasks-template.md
```

### **الخطوة 3:** توضيح المواصفة الوظيفية (مطلوب قبل التخطيط)

بعد إنشاء المواصفة الأساسية، يمكنك المضي قُدمًا وتوضيح أي متطلبات لم تُلتقَط بشكل صحيح من المحاولة الأولى.

ينبغي عليك تشغيل سير عمل التوضيح المنظَّم **قبل** إنشاء خطة تقنية لتقليل العمل المكرَّر لاحقًا.

الترتيب المفضّل:

1. استخدم `/speckit.clarify` (المنظَّم) – أسئلة متسلسلة قائمة على التغطية تسجّل الإجابات في قسم Clarifications.
2. اختياريًا، تابع بصقل حرّ ارتجالي إن بقي شيء غامض.

إذا كنت تريد تخطّي التوضيح عمدًا (مثل spike أو نموذج استكشافي)، أعلن ذلك صراحةً حتى لا يتوقف الوكيل بسبب توضيحات ناقصة.

مثال على مطالبة صقل حرّ (بعد `/speckit.clarify` إن دعت الحاجة):

```text
For each sample project or project that you create there should be a variable number of tasks between 5 and 15
tasks for each one randomly distributed into different states of completion. Make sure that there's at least
one task in each stage of completion.
```

ينبغي أيضًا أن تطلب من Claude Code التحقق من **قائمة المراجعة والقبول**، بحيث يضع علامة على البنود التي تجاوزت المتطلبات ويترك ما لم يجتزها دون علامة. يمكن استخدام المطالبة التالية:

```text
Read the review and acceptance checklist, and check off each item in the checklist if the feature spec meets the criteria. Leave it empty if it does not.
```

من المهم استخدام التفاعل مع Claude Code فرصةً للتوضيح وطرح الأسئلة حول المواصفة - **لا تعتبر محاولته الأولى نهائية**.

### **الخطوة 4:** ولّد خطة

يمكنك الآن أن تكون محددًا بشأن المكدّس التقني وغيره من المتطلبات التقنية. يمكنك استخدام أمر `/speckit.plan` المدمج في قالب المشروع بمطالبة كهذه:

```text
We are going to generate this using .NET Aspire, using Postgres as the database. The frontend should use
Blazor server with drag-and-drop task boards, real-time updates. There should be a REST API created with a projects API,
tasks API, and a notifications API.
```

سيتضمن مخرج هذه الخطوة عددًا من مستندات تفاصيل التنفيذ، مع شجرة مجلد مشابهة لهذه:

```text
.
├── CLAUDE.md
├── memory
│  └── constitution.md
├── scripts
│  ├── check-prerequisites.sh
│  ├── common.sh
│  ├── create-new-feature.sh
│  ├── setup-plan.sh
│  └── update-claude-md.sh
├── specs
│  └── 001-create-taskify
│      ├── contracts
│      │  ├── api-spec.json
│      │  └── signalr-spec.md
│      ├── data-model.md
│      ├── plan.md
│      ├── quickstart.md
│      ├── research.md
│      └── spec.md
└── templates
    ├── CLAUDE-template.md
    ├── plan-template.md
    ├── spec-template.md
    └── tasks-template.md
```

راجع مستند `research.md` للتأكد من استخدام المكدّس التقني الصحيح، بناءً على تعليماتك. يمكنك أن تطلب من Claude Code صقله إن لفت نظرك أي من المكوّنات، أو حتى أن يتحقق من الإصدار المثبت محليًا للمنصة/الإطار الذي تريد استخدامه (مثل .NET).

علاوةً على ذلك، قد ترغب في أن تطلب من Claude Code البحث في تفاصيل المكدّس التقني المختار إن كان شيئًا سريع التغيير (مثل .NET Aspire أو أُطر JS)، بمطالبة كهذه:

```text
I want you to go through the implementation plan and implementation details, looking for areas that could
benefit from additional research as .NET Aspire is a rapidly changing library. For those areas that you identify that
require further research, I want you to update the research document with additional details about the specific
versions that we are going to be using in this Taskify application and spawn parallel research tasks to clarify
any details using research from the web.
```

خلال هذه العملية، قد تجد أن Claude Code يعلق في بحث الشيء الخطأ - يمكنك مساعدته بدفعه في الاتجاه الصحيح بمطالبة كهذه:

```text
I think we need to break this down into a series of steps. First, identify a list of tasks
that you would need to do during implementation that you're not sure of or would benefit
from further research. Write down a list of those tasks. And then for each one of these tasks,
I want you to spin up a separate research task so that the net results is we are researching
all of those very specific tasks in parallel. What I saw you doing was it looks like you were
researching .NET Aspire in general and I don't think that's gonna do much for us in this case.
That's way too untargeted research. The research needs to help you solve a specific targeted question.
```

> [!NOTE]
> قد يكون Claude Code متحمسًا أكثر من اللازم ويضيف مكوّنات لم تطلبها. اطلب منه توضيح المنطق ومصدر التغيير.

### **الخطوة 5:** اجعل Claude Code يتحقق من الخطة

بعد جاهزية الخطة، ينبغي أن تطلب من Claude Code المرور عليها للتأكد من عدم وجود قطع ناقصة. يمكنك استخدام مطالبة كهذه:

```text
Now I want you to go and audit the implementation plan and the implementation detail files.
Read through it with an eye on determining whether or not there is a sequence of tasks that you need
to be doing that are obvious from reading this. Because I don't know if there's enough here. For example,
when I look at the core implementation, it would be useful to reference the appropriate places in the implementation
details where it can find the information as it walks through each step in the core implementation or in the refinement.
```

يساعد هذا في صقل خطة التنفيذ وتجنّب نقاط عمى محتملة فاتت Claude Code في دورة تخطيطه. بمجرد اكتمال الصقل الأولي، اطلب من Claude Code المرور على القائمة مرة أخرى قبل الانتقال إلى التنفيذ.

يمكنك أيضًا أن تطلب من Claude Code (إن كان لديك [GitHub CLI](https://docs.github.com/en/github-cli/github-cli) مثبتًا) إنشاء طلب دمج من فرعك الحالي إلى `main` بوصف مفصل، للتأكد من تتبّع الجهد بشكل صحيح.

> [!NOTE]
> قبل أن تطلب من الوكيل التنفيذ، من المفيد كذلك توجيه Claude Code للتدقيق في التفاصيل لرؤية ما إذا كانت هناك أجزاء مفرطة في الهندسة (تذكّر - قد يكون متحمسًا أكثر من اللازم). إن وُجدت مكوّنات أو قرارات مفرطة الهندسة، يمكنك أن تطلب من Claude Code حلّها. تأكّد من أن Claude Code يتبع [الدستور](base/memory/constitution.md) باعتباره الأساس الذي يجب أن يلتزم به عند وضع الخطة.

### **الخطوة 6:** ولّد تقسيم المهام عبر /speckit.tasks

بعد التحقق من خطة التنفيذ، يمكنك الآن تقسيم الخطة إلى مهام محددة وقابلة للتنفيذ يمكن تنفيذها بالترتيب الصحيح. استخدم أمر `/speckit.tasks` لتوليد تقسيم مهام مفصّل تلقائيًا من خطة التنفيذ:

```text
/speckit.tasks
```

تنشئ هذه الخطوة ملف `tasks.md` في مجلد مواصفة الميزة يحتوي على:

- **تقسيم المهام منظمًا حسب قصة المستخدم** - كل قصة مستخدم تصبح مرحلة تنفيذ مستقلة بمجموعتها الخاصة من المهام
- **إدارة الاعتماديات** - تُرتَّب المهام لتحترم الاعتماديات بين المكوّنات (مثلًا النماذج قبل الخدمات، والخدمات قبل النقاط الطرفية)
- **علامات التنفيذ المتوازي** - المهام التي يمكن تنفيذها بالتوازي تُعلَّم بـ `[P]` لتحسين سير العمل
- **مواصفات مسارات الملفات** - كل مهمة تتضمن المسارات الدقيقة للملفات التي يجب أن يحدث فيها التنفيذ
- **بنية التطوير المدفوع بالاختبارات** - إن طُلبت الاختبارات، تُدرَج مهام الاختبارات وتُرتَّب لتُكتَب قبل التنفيذ
- **تحقّق عند نقاط الفحص** - كل مرحلة قصة مستخدم تتضمن نقاط فحص للتحقق من وظائف مستقلة

يوفّر tasks.md المولَّد خارطة طريق واضحة لأمر `/speckit.implement`، مما يضمن تنفيذًا منهجيًا يحافظ على جودة الكود ويتيح تسليمًا تدريجيًا لقصص المستخدم.

### **الخطوة 7:** التنفيذ

عند الجاهزية، استخدم أمر `/speckit.implement` لتنفيذ خطة التنفيذ الخاصة بك:

```text
/speckit.implement
```

سيقوم أمر `/speckit.implement` بـ:

- التحقق من اكتمال جميع المتطلبات الأساسية (الدستور، المواصفة، الخطة، والمهام)
- تحليل تقسيم المهام من `tasks.md`
- تنفيذ المهام بالترتيب الصحيح، مع احترام الاعتماديات وعلامات التنفيذ المتوازي
- اتباع منهج TDD المعرَّف في خطة المهام
- تقديم تحديثات تقدّم ومعالجة الأخطاء بالشكل المناسب

> [!IMPORTANT]
> سيُنفّذ وكيل البرمجة أوامر CLI محلية (مثل `dotnet`، `npm`، إلخ) - تأكّد من تثبيت الأدوات المطلوبة على جهازك.

عند اكتمال التنفيذ، اختبر التطبيق وعالج أي أخطاء وقت التشغيل قد لا تكون مرئية في سجلات CLI (مثل أخطاء وحدة تحكم المتصفح). يمكنك نسخ هذه الأخطاء ولصقها لوكيل البرمجة لحلّها.

</details>

---

## 🔍 حل المشكلات

### Git Credential Manager على Linux

إذا واجهت مشكلات في مصادقة Git على Linux، يمكنك تثبيت Git Credential Manager:

```bash
#!/usr/bin/env bash
set -e
echo "Downloading Git Credential Manager v2.6.1..."
wget https://github.com/git-ecosystem/git-credential-manager/releases/download/v2.6.1/gcm-linux_amd64.2.6.1.deb
echo "Installing Git Credential Manager..."
sudo dpkg -i gcm-linux_amd64.2.6.1.deb
echo "Configuring Git to use GCM..."
git config --global credential.helper manager
echo "Cleaning up..."
rm gcm-linux_amd64.2.6.1.deb
```

## 💬 الدعم

للحصول على الدعم، الرجاء فتح [GitHub issue](https://github.com/github/spec-kit/issues/new). نرحب ببلاغات الأخطاء وطلبات الميزات والأسئلة حول استخدام التطوير المعتمد على المواصفات.

## 🙏 شكر وتقدير

هذا المشروع متأثر بشدة ومبني على عمل وأبحاث [John Lam](https://github.com/jflam).

## 📄 الترخيص

هذا المشروع مرخّص بموجب شروط رخصة MIT مفتوحة المصدر. الرجاء الرجوع إلى ملف [LICENSE](./LICENSE) للشروط الكاملة.
