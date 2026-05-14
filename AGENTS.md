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

#### Required fields

| Field | Location | Purpose |
|---|---|---|
| `key` | Class attribute | Unique identifier; for CLI-based integrations (`requires_cli: True`), must match the CLI executable name |
| `config` | Class attribute (dict) | Agent metadata: `name`, `folder`, `commands_subdir`, `install_url`, `requires_cli` |
| `registrar_config` | Class attribute (dict) | Command output config: `dir`, `format`, `args` placeholder, file `extension` |
| `context_file` | Class attribute (str or None) | Path to agent context/instructions file (e.g., `"CLAUDE.md"`, `".github/copilot-instructions.md"`) |

**Key design rule:** For CLI-based integrations (`requires_cli: True`), `key` must be the actual executable name (e.g., `"cursor-agent"` not `"cursor"`). This ensures `shutil.which(key)` works for CLI-tool checks without special-case mappings. IDE-based integrations (`requires_cli: False`) should use their canonical identifier (e.g., `"windsurf"`, `"copilot"`).

### 3. Register it

In `src/specify_cli/integrations/__init__.py`, add one import and one `_register()` call inside `_register_builtins()`. Both lists are alphabetical:

```python
def _register_builtins() -> None:
    # -- Imports (alphabetical) -------------------------------------------
    from .claude import ClaudeIntegration
    # ...
    from .newagent import NewAgentIntegration   # ← add import
    # ...

    # -- Registration (alphabetical) --------------------------------------
    _register(ClaudeIntegration())
    # ...
    _register(NewAgentIntegration())            # ← add registration
    # ...
```

### 4. Context file behavior

Set `context_file` on the integration class. The base integration setup creates or updates the managed Spec Kit section in that file, and uninstall removes the managed section when appropriate.

Only add custom setup logic when the agent needs non-standard behavior. Most integrations do not need wrapper scripts or separate context-update dispatch code.

### 5. Test it

```bash
# Install into a test project
specify init my-project --integration <key>

# Verify files were created in the commands directory configured by
# config["folder"] + config["commands_subdir"] (for example, .windsurf/workflows/)
ls -R my-project/.windsurf/workflows/

# Uninstall cleanly
cd my-project && specify integration uninstall <key>
```

Each integration also has a dedicated test file at `tests/integrations/test_integration_<key>.py`. Note that hyphens in the key are replaced with underscores in the filename (e.g., key `cursor-agent` → `test_integration_cursor_agent.py`, key `kiro-cli` → `test_integration_kiro_cli.py`). Run it with:

```bash
pytest tests/integrations/test_integration_<key_with_underscores>.py -v
```

### 6. Optional overrides

The base classes handle most work automatically. Override only when the agent deviates from standard patterns:

| Override | When to use | Example |
|---|---|---|
| `command_filename(template_name)` | Custom file naming or extension | Copilot → `speckit.{name}.agent.md` |
| `options()` | Integration-specific CLI flags via `--integration-options` | Codex → `--skills` flag, Copilot → `--skills` flag |
| `setup()` | Custom install logic (companion files, settings merge) | Copilot → `.agent.md` + `.prompt.md` + `.vscode/settings.json` (default) or `speckit-<name>/SKILL.md` (skills mode) |
| `teardown()` | Custom uninstall logic | Rarely needed; base handles manifest-tracked files |

**Example — Copilot (fully custom `setup`):**

Copilot extends `IntegrationBase` directly because it creates `.agent.md` commands, companion `.prompt.md` files, and merges `.vscode/settings.json`. It also supports a `--skills` mode that scaffolds `speckit-<name>/SKILL.md` under `.github/skills/` using composition with an internal `_CopilotSkillsHelper`. See `src/specify_cli/integrations/copilot/__init__.py` for the full implementation.

### 7. Update Devcontainer files (Optional)

For agents that have VS Code extensions or require CLI installation, update the devcontainer configuration files:

#### VS Code Extension-based Agents

For agents available as VS Code extensions, add them to `.devcontainer/devcontainer.json`:

```jsonc
{
  "customizations": {
    "vscode": {
      "extensions": [
        // ... existing extensions ...
        "[New Agent Extension ID]"
      ]
    }
  }
}
```

#### CLI-based Agents

For agents that require CLI tools, add installation commands to `.devcontainer/post-create.sh`:

```bash
#!/bin/bash

# Existing installations...

echo -e "\n🤖 Installing [New Agent Name] CLI..."
# run_command "npm install -g [agent-cli-package]@latest"
echo "✅ Done"
```

---

## Command File Formats

### Markdown Format

**Standard format:**

```markdown
---
description: "Command description"
---

Command content with {SCRIPT} and $ARGUMENTS placeholders.
```

**GitHub Copilot Chat Mode format:**

```markdown
---
description: "Command description"
mode: speckit.command-name
---

Command content with {SCRIPT} and $ARGUMENTS placeholders.
```

### TOML Format

```toml
description = "Command description"

prompt = """
Command content with {SCRIPT} and {{args}} placeholders.
"""
```

### YAML Format

Used by: Goose

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

## Argument Patterns

Different agents use different argument placeholders. The placeholder used in command files is always taken from `registrar_config["args"]` for each integration — check there first when in doubt:

- **Markdown/prompt-based**: `$ARGUMENTS` (default for most markdown agents)
- **TOML-based**: `{{args}}` (e.g., Gemini)
- **YAML-based**: `{{args}}` (e.g., Goose)
- **Custom**: some agents override the default (e.g., Forge uses `{{parameters}}`)
- **Script placeholders**: `{SCRIPT}` (replaced with actual script path)
- **Agent placeholders**: `__AGENT__` (replaced with agent name)

## Special Processing Requirements

Some agents require custom processing beyond the standard template transformations:

### Copilot Integration

GitHub Copilot has unique requirements:
- Commands use `.agent.md` extension (not `.md`)
- Each command gets a companion `.prompt.md` file in `.github/prompts/`
- Installs `.vscode/settings.json` with prompt file recommendations
- Context file lives at `.github/copilot-instructions.md`

Implementation: Extends `IntegrationBase` with custom `setup()` method that:
1. Processes templates with `process_template()`
2. Generates companion `.prompt.md` files
3. Merges VS Code settings

**Skills mode (`--skills`):** Copilot also supports an alternative skills-based layout
via `--integration-options="--skills"`. When enabled:
- Commands are scaffolded as `speckit-<name>/SKILL.md` under `.github/skills/`
- No companion `.prompt.md` files are generated
- No `.vscode/settings.json` merge
- `post_process_skill_content()` injects a `mode: speckit.<stem>` frontmatter field
- `build_command_invocation()` returns `/speckit-<stem>` instead of bare args

The two modes are mutually exclusive — a project uses one or the other:

```bash
# Default mode: .agent.md agents + .prompt.md companions + settings merge
specify init my-project --integration copilot

# Skills mode: speckit-<name>/SKILL.md under .github/skills/
specify init my-project --integration copilot --integration-options="--skills"
```

### Forge Integration

Forge has special frontmatter and argument requirements:
- Uses `{{parameters}}` instead of `$ARGUMENTS`
- Strips `handoffs` frontmatter key (Forge-specific collaboration feature)
- Injects `name` field into frontmatter when missing

Implementation: Extends `MarkdownIntegration` with custom `setup()` method that:
1. Inherits standard template processing from `MarkdownIntegration`
2. Adds extra `$ARGUMENTS` → `{{parameters}}` replacement after template processing
3. Applies Forge-specific transformations via `_apply_forge_transformations()`
4. Strips `handoffs` frontmatter key
5. Injects missing `name` fields

### Goose Integration

Goose is a YAML-format agent using Block's recipe system:
- Uses `.goose/recipes/` directory for YAML recipe files
- Uses `{{args}}` argument placeholder
- Produces YAML with `prompt: |` block scalar for command content

Implementation: Extends `YamlIntegration` (parallel to `TomlIntegration`):
1. Processes templates through the standard placeholder pipeline
2. Extracts title and description from frontmatter
3. Renders output as Goose recipe YAML (version, title, description, author, extensions, activities, prompt)
4. Uses `yaml.safe_dump()` for header fields to ensure proper escaping
5. Sets `context_file = "AGENTS.md"` so the base setup manages the Spec Kit context section there

## Common Pitfalls

1. **Using shorthand keys for CLI-based integrations**: For CLI-based integrations (`requires_cli: True`), the `key` must match the executable name (e.g., `"cursor-agent"` not `"cursor"`). `shutil.which(key)` is used for CLI tool checks — mismatches require special-case mappings. IDE-based integrations (`requires_cli: False`) are not subject to this constraint.
2. **Forgetting update scripts**: Both bash and PowerShell thin wrappers and the shared context-update scripts must be updated.
3. **Incorrect `requires_cli` value**: Set to `True` only for agents that have a CLI tool; set to `False` for IDE-based agents.
4. **Wrong argument format**: Use `$ARGUMENTS` for Markdown agents, `{{args}}` for TOML agents.
5. **Skipping registration**: The import and `_register()` call in `_register_builtins()` must both be added.

---

*This documentation should be updated whenever new integrations are added to maintain accuracy and completeness.*
