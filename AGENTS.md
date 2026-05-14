# AGENTS.md

## حول Spec Kit و Specify

**GitHub Spec Kit** هو مجموعة أدوات شاملة لتطبيق التطوير المعتمد على المواصفات (SDD) - منهجية تُركّز على إنشاء مواصفات واضحة قبل التنفيذ. تتضمن مجموعة الأدوات قوالب وسكربتات وسير عمل تُرشد فرق التطوير عبر نهج منظم لبناء البرمجيات.

**Specify CLI** هو واجهة سطر الأوامر التي تُنشئ المشاريع باستخدام إطار عمل Spec Kit. يُعدّ هياكل المجلدات والقوالب وتكاملات وكلاء الذكاء الاصطناعي اللازمة لدعم سير عمل التطوير المعتمد على المواصفات.

تدعم مجموعة الأدوات العديد من مساعدي البرمجة بالذكاء الاصطناعي، مما يسمح للفرق باستخدام الأدوات المفضّلة لديها مع الحفاظ على بنية مشروع وممارسات تطوير متّسقة.

---

## بنية التكامل

كل وكيل برمجة بالذكاء الاصطناعي هو **حزمة فرعية للتكامل** قائمة بذاتها ضمن `src/specify_cli/integrations/<key>/`. تكشف الحزمة الفرعية عن صنف واحد يُصرّح بجميع البيانات الوصفية ويرث منطق الإعداد والإلغاء من صنف أساسي. ثم يتم إنشاء التكاملات المُدمجة وإضافتها إلى السجل العام `INTEGRATION_REGISTRY` بواسطة `src/specify_cli/integrations/__init__.py` عبر `_register_builtins()`.

```
src/specify_cli/integrations/
├── __init__.py            # INTEGRATION_REGISTRY + _register_builtins()
├── base.py                # IntegrationBase, MarkdownIntegration, TomlIntegration, YamlIntegration, SkillsIntegration
├── manifest.py            # IntegrationManifest (file tracking)
├── claude/                # Example: SkillsIntegration subclass
│   └── __init__.py        #   ClaudeIntegration class
├── gemini/                # Example: TomlIntegration subclass
│   └── __init__.py
├── windsurf/              # Example: MarkdownIntegration subclass
│   └── __init__.py
├── copilot/               # Example: IntegrationBase subclass (custom setup)
│   └── __init__.py
└── ...                    # One subpackage per supported agent
```

السجل هو **المصدر الوحيد للحقيقة فيما يخص البيانات الوصفية لتكامل Python**. الوكلاء المدعومون ومجلداتهم وصيغهم وقدراتهم وملفات سياقهم مُشتقّة من أصناف التكامل في طبقة تكامل Python.

---

## إضافة تكامل جديد

### 1. اختر صنفاً أساسياً

| ما يحتاجه وكيلك… | الصنف الفرعي |
|---|---|
| أوامر markdown قياسية (`.md`) | `MarkdownIntegration` |
| أوامر بصيغة TOML (`.toml`) | `TomlIntegration` |
| ملفات وصفات YAML (`.yaml`) | `YamlIntegration` |
| مجلدات مهارات (`speckit-<name>/SKILL.md`) | `SkillsIntegration` |
| مُخرَج مخصّص بالكامل (ملفات مرافقة، دمج إعدادات، إلخ.) | `IntegrationBase` مباشرةً |

معظم الوكلاء يحتاجون فقط إلى `MarkdownIntegration` — صنف فرعي مُبسّط دون أي تجاوز للدوال.

### 2. أنشئ الحزمة الفرعية

أنشئ `src/specify_cli/integrations/<package_dir>/__init__.py`، حيث `<package_dir>` هو اسم المجلد المتوافق مع Python والمشتق من `<key>`: استخدم المفتاح كما هو عندما لا يحتوي على شرطات (مثلاً، المفتاح `"gemini"` ← `gemini/`)، أو استبدل الشرطات بشرطات سفلية عندما يحتوي عليها (مثلاً، المفتاح `"kiro-cli"` ← `kiro_cli/`). تحتفظ سمة الصنف `IntegrationBase.key` دائماً بالقيمة الأصلية المحتوية على الشرطات، لأن ذلك هو ما يستخدمه CLI والسجل. بالنسبة للتكاملات القائمة على CLI (`requires_cli: True`)، يجب أن يتطابق `key` مع اسم أداة CLI الفعلية (الملف التنفيذي الذي يقوم المستخدمون بتثبيته وتشغيله) حتى تتمكن فحوصات CLI من تحديده بشكل صحيح. بالنسبة للتكاملات القائمة على IDE (`requires_cli: False`)، استخدم المعرّف القانوني للتكامل بدلاً من ذلك.

**مثال مُبسّط — وكيل Markdown (Windsurf):**

```python
"""Windsurf IDE integration."""

from ..base import MarkdownIntegration


class WindsurfIntegration(MarkdownIntegration):
    key = "windsurf"
    config = {
        "name": "Windsurf",
        "folder": ".windsurf/",
        "commands_subdir": "workflows",
        "install_url": None,
        "requires_cli": False,
    }
    registrar_config = {
        "dir": ".windsurf/workflows",
        "format": "markdown",
        "args": "$ARGUMENTS",
        "extension": ".md",
    }
    context_file = ".windsurf/rules/specify-rules.md"
```

**وكيل TOML (Gemini):**

```python
"""Gemini CLI integration."""

from ..base import TomlIntegration


class GeminiIntegration(TomlIntegration):
    key = "gemini"
    config = {
        "name": "Gemini CLI",
        "folder": ".gemini/",
        "commands_subdir": "commands",
        "install_url": "https://github.com/google-gemini/gemini-cli",
        "requires_cli": True,
    }
    registrar_config = {
        "dir": ".gemini/commands",
        "format": "toml",
        "args": "{{args}}",
        "extension": ".toml",
    }
    context_file = "GEMINI.md"
```

**وكيل المهارات (Codex):**

```python
"""Codex CLI integration — skills-based agent."""

from __future__ import annotations

from ..base import IntegrationOption, SkillsIntegration


class CodexIntegration(SkillsIntegration):
    key = "codex"
    config = {
        "name": "Codex CLI",
        "folder": ".agents/",
        "commands_subdir": "skills",
        "install_url": "https://github.com/openai/codex",
        "requires_cli": True,
    }
    registrar_config = {
        "dir": ".agents/skills",
        "format": "markdown",
        "args": "$ARGUMENTS",
        "extension": "/SKILL.md",
    }
    context_file = "AGENTS.md"

    @classmethod
    def options(cls) -> list[IntegrationOption]:
        return [
            IntegrationOption(
                "--skills",
                is_flag=True,
                default=True,
                help="Install as agent skills (default for Codex)",
            ),
        ]
```

#### الحقول المطلوبة

| الحقل | الموقع | الغرض |
|---|---|---|
| `key` | سمة الصنف | معرّف فريد؛ بالنسبة للتكاملات القائمة على CLI (`requires_cli: True`)، يجب أن يتطابق مع اسم الملف التنفيذي لـ CLI |
| `config` | سمة الصنف (dict) | البيانات الوصفية للوكيل: `name`، `folder`، `commands_subdir`، `install_url`، `requires_cli` |
| `registrar_config` | سمة الصنف (dict) | إعداد مُخرَج الأوامر: `dir`، `format`، عنصر نائب لـ `args`، امتداد الملف `extension` |
| `context_file` | سمة الصنف (str أو None) | المسار إلى ملف سياق/تعليمات الوكيل (مثل `"CLAUDE.md"`، `".github/copilot-instructions.md"`) |

**قاعدة التصميم الأساسية:** بالنسبة للتكاملات القائمة على CLI (`requires_cli: True`)، يجب أن يكون `key` هو الاسم الفعلي للملف التنفيذي (مثل `"cursor-agent"` وليس `"cursor"`). يضمن ذلك أن `shutil.which(key)` يعمل لفحوصات أدوات CLI دون الحاجة إلى تعيينات استثنائية. التكاملات القائمة على IDE (`requires_cli: False`) ينبغي أن تستخدم معرّفها القانوني (مثل `"windsurf"`، `"copilot"`).

### 3. سجّله

في `src/specify_cli/integrations/__init__.py`، أضف استيراداً واحداً واستدعاءً واحداً لـ `_register()` داخل `_register_builtins()`. كلتا القائمتين مرتّبتان أبجدياً:

```python
def _register_builtins() -> None:
    # -- Imports (alphabetical) -------------------------------------------
    from .claude import ClaudeIntegration
    # ...
    from .newagent import NewAgentIntegration   # ← أضف الاستيراد
    # ...

    # -- Registration (alphabetical) --------------------------------------
    _register(ClaudeIntegration())
    # ...
    _register(NewAgentIntegration())            # ← أضف التسجيل
    # ...
```

### 4. سلوك ملف السياق

اضبط `context_file` في صنف التكامل. يقوم إعداد التكامل الأساسي بإنشاء أو تحديث قسم Spec Kit المُدار في ذلك الملف، ويزيل إلغاء التثبيت القسم المُدار عند الاقتضاء.

أضف منطق إعداد مخصّصاً فقط عندما يحتاج الوكيل إلى سلوك غير قياسي. معظم التكاملات لا تحتاج إلى سكربتات تغليف أو شيفرة إرسال منفصلة لتحديث السياق.

### 5. اختبره

```bash
# التثبيت في مشروع اختباري
specify init my-project --integration <key>

# تحقق من إنشاء الملفات في مجلد الأوامر المُعدّ عبر
# config["folder"] + config["commands_subdir"] (مثل .windsurf/workflows/)
ls -R my-project/.windsurf/workflows/

# إلغاء التثبيت بنظافة
cd my-project && specify integration uninstall <key>
```

لكل تكامل أيضاً ملف اختبار مخصّص في `tests/integrations/test_integration_<key>.py`. لاحظ أن الشرطات في المفتاح تُستبدل بشرطات سفلية في اسم الملف (مثلاً، المفتاح `cursor-agent` ← `test_integration_cursor_agent.py`، المفتاح `kiro-cli` ← `test_integration_kiro_cli.py`). شغّله عبر:

```bash
pytest tests/integrations/test_integration_<key_with_underscores>.py -v
```

### 6. التجاوزات الاختيارية

تعالج الأصناف الأساسية معظم العمل تلقائياً. تجاوَزها فقط عندما ينحرف الوكيل عن الأنماط القياسية:

| التجاوز | متى يُستخدم | مثال |
|---|---|---|
| `command_filename(template_name)` | تسمية أو امتداد ملف مخصّص | Copilot ← `speckit.{name}.agent.md` |
| `options()` | رايات CLI خاصة بالتكامل عبر `--integration-options` | Codex ← راية `--skills`، Copilot ← راية `--skills` |
| `setup()` | منطق تثبيت مخصّص (ملفات مرافقة، دمج إعدادات) | Copilot ← `.agent.md` + `.prompt.md` + `.vscode/settings.json` (الافتراضي) أو `speckit-<name>/SKILL.md` (وضع المهارات) |
| `teardown()` | منطق إلغاء تثبيت مخصّص | نادراً ما يلزم؛ الأساس يتولى الملفات المتعقّبة في البيان |

**مثال — Copilot (`setup` مخصّص بالكامل):**

يمتد Copilot من `IntegrationBase` مباشرةً لأنه ينشئ أوامر `.agent.md`، وملفات `.prompt.md` المرافقة، ويدمج `.vscode/settings.json`. كما يدعم وضع `--skills` الذي يُنشئ هيكلية `speckit-<name>/SKILL.md` تحت `.github/skills/` باستخدام التركيب مع مساعد داخلي `_CopilotSkillsHelper`. راجع `src/specify_cli/integrations/copilot/__init__.py` للاطلاع على التنفيذ الكامل.

### 7. تحديث ملفات Devcontainer (اختياري)

بالنسبة للوكلاء الذين لديهم امتدادات VS Code أو يتطلّبون تثبيت CLI، حدّث ملفات إعداد devcontainer:

#### الوكلاء القائمون على امتدادات VS Code

بالنسبة للوكلاء المتاحين كامتدادات VS Code، أضفهم إلى `.devcontainer/devcontainer.json`:

```jsonc
{
  "customizations": {
    "vscode": {
      "extensions": [
        // ... الامتدادات الحالية ...
        "[New Agent Extension ID]"
      ]
    }
  }
}
```

#### الوكلاء القائمون على CLI

بالنسبة للوكلاء الذين يتطلّبون أدوات CLI، أضف أوامر التثبيت إلى `.devcontainer/post-create.sh`:

```bash
#!/bin/bash

# عمليات التثبيت الحالية...

echo -e "\n🤖 Installing [New Agent Name] CLI..."
# run_command "npm install -g [agent-cli-package]@latest"
echo "✅ Done"
```

---

## صيغ ملفات الأوامر

### صيغة Markdown

**الصيغة القياسية:**

```markdown
---
description: "Command description"
---

Command content with {SCRIPT} and $ARGUMENTS placeholders.
```

**صيغة وضع الدردشة لـ GitHub Copilot:**

```markdown
---
description: "Command description"
mode: speckit.command-name
---

Command content with {SCRIPT} and $ARGUMENTS placeholders.
```

### صيغة TOML

```toml
description = "Command description"

prompt = """
Command content with {SCRIPT} and {{args}} placeholders.
"""
```

### صيغة YAML

تُستخدم من قِبَل: Goose

```yaml
version: 1.0.0
title: "Command Title"
description: "Command description"
author:
  contact: spec-kit
extensions:
  - type: builtin
    name: developer
activities:
  - Spec-Driven Development
prompt: |
  Command content with {SCRIPT} and {{args}} placeholders.
```

## أنماط الوسائط

الوكلاء المختلفون يستخدمون عناصر نائبة مختلفة للوسائط. العنصر النائب المستخدم في ملفات الأوامر يُؤخذ دائماً من `registrar_config["args"]` لكل تكامل — تحقّق منه أولاً عند الشك:

- **القائمة على Markdown/المُوجِّه**: `$ARGUMENTS` (الافتراضي لمعظم وكلاء markdown)
- **القائمة على TOML**: `{{args}}` (مثل Gemini)
- **القائمة على YAML**: `{{args}}` (مثل Goose)
- **المخصّصة**: بعض الوكلاء يتجاوزون الافتراضي (مثلاً، Forge يستخدم `{{parameters}}`)
- **عناصر نائبة للسكربتات**: `{SCRIPT}` (يُستبدل بمسار السكربت الفعلي)
- **عناصر نائبة للوكيل**: `__AGENT__` (يُستبدل باسم الوكيل)

## متطلبات معالجة خاصة

بعض الوكلاء يتطلّبون معالجة مخصّصة تتجاوز تحويلات القوالب القياسية:

### تكامل Copilot

لدى GitHub Copilot متطلّبات فريدة:
- الأوامر تستخدم امتداد `.agent.md` (وليس `.md`)
- كل أمر يحصل على ملف مرافق `.prompt.md` في `.github/prompts/`
- يُثبّت `.vscode/settings.json` مع توصيات ملفات المُوجِّه
- ملف السياق يقع في `.github/copilot-instructions.md`

التنفيذ: يمتد من `IntegrationBase` مع دالة `setup()` مخصّصة تقوم بـ:
1. معالجة القوالب عبر `process_template()`
2. توليد ملفات `.prompt.md` المرافقة
3. دمج إعدادات VS Code

**وضع المهارات (`--skills`):** يدعم Copilot أيضاً بنية بديلة قائمة على المهارات
عبر `--integration-options="--skills"`. عند التفعيل:
- يُنشأ هيكل الأوامر كـ `speckit-<name>/SKILL.md` تحت `.github/skills/`
- لا تُولَّد ملفات `.prompt.md` مرافقة
- لا يتم دمج `.vscode/settings.json`
- `post_process_skill_content()` يُدرج حقل frontmatter `mode: speckit.<stem>`
- `build_command_invocation()` يُعيد `/speckit-<stem>` بدلاً من الوسائط المجرّدة

الوضعان متنافيان — يستخدم المشروع أحدهما أو الآخر:

```bash
# الوضع الافتراضي: وكلاء .agent.md + ملفات .prompt.md مرافقة + دمج الإعدادات
specify init my-project --integration copilot

# وضع المهارات: speckit-<name>/SKILL.md تحت .github/skills/
specify init my-project --integration copilot --integration-options="--skills"
```

### تكامل Forge

لدى Forge متطلبات خاصة بـ frontmatter والوسائط:
- يستخدم `{{parameters}}` بدلاً من `$ARGUMENTS`
- يحذف مفتاح `handoffs` من frontmatter (ميزة تعاون خاصة بـ Forge)
- يُدرج حقل `name` في frontmatter عند غيابه

التنفيذ: يمتد من `MarkdownIntegration` مع دالة `setup()` مخصّصة تقوم بـ:
1. وراثة معالجة القوالب القياسية من `MarkdownIntegration`
2. إضافة استبدال إضافي `$ARGUMENTS` ← `{{parameters}}` بعد معالجة القالب
3. تطبيق التحويلات الخاصة بـ Forge عبر `_apply_forge_transformations()`
4. حذف مفتاح `handoffs` من frontmatter
5. إدراج حقول `name` المفقودة

### تكامل Goose

Goose هو وكيل بصيغة YAML يستخدم نظام الوصفات الخاص بـ Block:
- يستخدم المجلد `.goose/recipes/` لملفات وصفات YAML
- يستخدم العنصر النائب للوسائط `{{args}}`
- يُنتج YAML مع scalar كتلي `prompt: |` لمحتوى الأمر

التنفيذ: يمتد من `YamlIntegration` (موازياً لـ `TomlIntegration`):
1. يعالج القوالب عبر خط أنابيب العناصر النائبة القياسي
2. يستخرج العنوان والوصف من frontmatter
3. يُصيِّر المُخرَج كـ YAML وصفة Goose (version، title، description، author، extensions، activities، prompt)
4. يستخدم `yaml.safe_dump()` لحقول الترويسة لضمان التهريب الصحيح
5. يضبط `context_file = "AGENTS.md"` بحيث يُدير الإعداد الأساسي قسم سياق Spec Kit هناك

## المزالق الشائعة

1. **استخدام مفاتيح مختصرة للتكاملات القائمة على CLI**: بالنسبة للتكاملات القائمة على CLI (`requires_cli: True`)، يجب أن يتطابق `key` مع اسم الملف التنفيذي (مثل `"cursor-agent"` وليس `"cursor"`). تُستخدم `shutil.which(key)` لفحوصات أدوات CLI — وعدم التطابق يتطلّب تعيينات استثنائية. التكاملات القائمة على IDE (`requires_cli: False`) ليست خاضعة لهذا القيد.
2. **نسيان سكربتات التحديث**: يجب تحديث كل من المُغلِّفَين الرقيقَين بـ bash و PowerShell وسكربتات تحديث السياق المشتركة.
3. **قيمة `requires_cli` غير صحيحة**: اضبطها على `True` فقط للوكلاء الذين لديهم أداة CLI؛ واضبطها على `False` للوكلاء القائمين على IDE.
4. **صيغة وسائط خاطئة**: استخدم `$ARGUMENTS` لوكلاء Markdown، و`{{args}}` لوكلاء TOML.
5. **تخطّي التسجيل**: يجب إضافة كلٍّ من الاستيراد واستدعاء `_register()` في `_register_builtins()`.

---

*ينبغي تحديث هذه الوثيقة كلما تمت إضافة تكاملات جديدة للحفاظ على الدقة والاكتمال.*
