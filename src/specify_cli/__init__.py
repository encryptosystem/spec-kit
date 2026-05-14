#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "typer",
#     "rich",
#     "platformdirs",
#     "readchar",
#     "json5",
#     "pyyaml",
#     "packaging",
# ]
# ///
"""
Specify CLI - Setup tool for Specify projects

Usage:
    uvx specify-cli.py init <project-name>
    uvx specify-cli.py init .
    uvx specify-cli.py init --here

Or install globally:
    uv tool install --from specify-cli.py specify-cli
    specify init <project-name>
    specify init .
    specify init --here
"""

import os
import subprocess
import sys
import zipfile
import tempfile
import shutil
import json
import json5
import stat
import shlex
import urllib.error
import urllib.request
import yaml
from pathlib import Path

from packaging.version import InvalidVersion, Version
from typing import Any, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.align import Align
from rich.table import Table
from rich.tree import Tree
from typer.core import TyperGroup

from .integration_runtime import (
    invoke_separator_for_integration as _invoke_separator_for_integration,
    resolve_integration_options as _resolve_integration_options_impl,
    with_integration_setting as _with_integration_setting,
)
from .integration_state import (
    INTEGRATION_JSON,
    INTEGRATION_STATE_SCHEMA,
    dedupe_integration_keys as _dedupe_integration_keys,
    default_integration_key as _default_integration_key,
    installed_integration_keys as _installed_integration_keys,
    integration_setting as _integration_setting,
    integration_settings as _integration_settings,
    normalize_integration_state as _normalize_integration_state,
    write_integration_json as _write_integration_json_file,
)
from .shared_infra import (
    install_shared_infra as _install_shared_infra_impl,
    refresh_shared_templates as _refresh_shared_templates_impl,
)

# For cross-platform keyboard input
import readchar

GITHUB_API_LATEST = "https://api.github.com/repos/github/spec-kit/releases/latest"

def _build_agent_config() -> dict[str, dict[str, Any]]:
    """Derive AGENT_CONFIG from INTEGRATION_REGISTRY."""
    from .integrations import INTEGRATION_REGISTRY
    config: dict[str, dict[str, Any]] = {}
    for key, integration in INTEGRATION_REGISTRY.items():
        if integration.config:
            config[key] = dict(integration.config)
    return config

AGENT_CONFIG = _build_agent_config()

AI_ASSISTANT_ALIASES = {
    "kiro": "kiro-cli",
}

# Agents that use TOML command format (others use Markdown)
_TOML_AGENTS = frozenset({"gemini", "tabnine"})

def _build_ai_assistant_help() -> str:
    """Build the --ai help text from AGENT_CONFIG so it stays in sync with runtime config."""

    non_generic_agents = sorted(agent for agent in AGENT_CONFIG if agent != "generic")
    base_help = (
        f"وكيل الـ AI: {', '.join(non_generic_agents)}, "
        "أو generic (لازم معه --ai-commands-dir)."
    )

    if not AI_ASSISTANT_ALIASES:
        return base_help

    alias_phrases = []
    for alias, target in sorted(AI_ASSISTANT_ALIASES.items()):
        alias_phrases.append(f"«{alias}» كنُسخة عن «{target}»")

    if len(alias_phrases) == 1:
        aliases_text = alias_phrases[0]
    else:
        aliases_text = '، '.join(alias_phrases[:-1]) + ' و' + alias_phrases[-1]

    return base_help + " يمكنك استخدام " + aliases_text + "."
AI_ASSISTANT_HELP = _build_ai_assistant_help()


def _build_integration_equivalent(
    integration_key: str,
    ai_commands_dir: str | None = None,
) -> str:
    """Build the modern --integration equivalent for legacy --ai usage."""

    parts = [f"--integration {integration_key}"]
    if integration_key == "generic" and ai_commands_dir:
        parts.append(
            f'--integration-options="--commands-dir {shlex.quote(ai_commands_dir)}"'
        )
    return " ".join(parts)


def _build_ai_deprecation_warning(
    integration_key: str,
    ai_commands_dir: str | None = None,
) -> str:
    """Build the legacy --ai deprecation warning message."""

    replacement = _build_integration_equivalent(
        integration_key,
        ai_commands_dir=ai_commands_dir,
    )
    return (
        "[bold]--ai[/bold] مهمل ولن يكون متاحاً في الإصدار 0.10.0 أو أحدث.\n\n"
        f"استخدم [bold]{replacement}[/bold] بدلاً منه."
    )

SCRIPT_TYPE_CHOICES = {"sh": "POSIX Shell (bash/zsh)", "ps": "PowerShell"}

CLAUDE_LOCAL_PATH = Path.home() / ".claude" / "local" / "claude"
CLAUDE_NPM_LOCAL_PATH = Path.home() / ".claude" / "local" / "node_modules" / ".bin" / "claude"

BANNER = """
███████╗██████╗ ███████╗ ██████╗██╗███████╗██╗   ██╗
██╔════╝██╔══██╗██╔════╝██╔════╝██║██╔════╝╚██╗ ██╔╝
███████╗██████╔╝█████╗  ██║     ██║█████╗   ╚████╔╝
╚════██║██╔═══╝ ██╔══╝  ██║     ██║██╔══╝    ╚██╔╝
███████║██║     ███████╗╚██████╗██║██║        ██║
╚══════╝╚═╝     ╚══════╝ ╚═════╝╚═╝╚═╝        ╚═╝
"""

TAGLINE = "GitHub Spec Kit — من المواصفة إلى التنفيذ بخطوات واضحة"
class StepTracker:
    """Track and render hierarchical steps without emojis, similar to Claude Code tree output.
    Supports live auto-refresh via an attached refresh callback.
    """
    def __init__(self, title: str):
        self.title = title
        self.steps = []  # list of dicts: {key, label, status, detail}
        self.status_order = {"pending": 0, "running": 1, "done": 2, "error": 3, "skipped": 4}
        self._refresh_cb = None  # callable to trigger UI refresh

    def attach_refresh(self, cb):
        self._refresh_cb = cb

    def add(self, key: str, label: str):
        if key not in [s["key"] for s in self.steps]:
            self.steps.append({"key": key, "label": label, "status": "pending", "detail": ""})
            self._maybe_refresh()

    def start(self, key: str, detail: str = ""):
        self._update(key, status="running", detail=detail)

    def complete(self, key: str, detail: str = ""):
        self._update(key, status="done", detail=detail)

    def error(self, key: str, detail: str = ""):
        self._update(key, status="error", detail=detail)

    def skip(self, key: str, detail: str = ""):
        self._update(key, status="skipped", detail=detail)

    def _update(self, key: str, status: str, detail: str):
        for s in self.steps:
            if s["key"] == key:
                s["status"] = status
                if detail:
                    s["detail"] = detail
                self._maybe_refresh()
                return

        self.steps.append({"key": key, "label": key, "status": status, "detail": detail})
        self._maybe_refresh()

    def _maybe_refresh(self):
        if self._refresh_cb:
            try:
                self._refresh_cb()
            except Exception:
                pass

    def render(self):
        tree = Tree(f"[cyan]{self.title}[/cyan]", guide_style="grey50")
        for step in self.steps:
            label = step["label"]
            detail_text = step["detail"].strip() if step["detail"] else ""

            status = step["status"]
            if status == "done":
                symbol = "[green]●[/green]"
            elif status == "pending":
                symbol = "[green dim]○[/green dim]"
            elif status == "running":
                symbol = "[cyan]○[/cyan]"
            elif status == "error":
                symbol = "[red]●[/red]"
            elif status == "skipped":
                symbol = "[yellow]○[/yellow]"
            else:
                symbol = " "

            if status == "pending":
                # Entire line light gray (pending)
                if detail_text:
                    line = f"{symbol} [bright_black]{label} ({detail_text})[/bright_black]"
                else:
                    line = f"{symbol} [bright_black]{label}[/bright_black]"
            else:
                # Label white, detail (if any) light gray in parentheses
                if detail_text:
                    line = f"{symbol} [white]{label}[/white] [bright_black]({detail_text})[/bright_black]"
                else:
                    line = f"{symbol} [white]{label}[/white]"

            tree.add(line)
        return tree

def get_key():
    """Get a single keypress in a cross-platform way using readchar."""
    key = readchar.readkey()

    if key == readchar.key.UP or key == readchar.key.CTRL_P:
        return 'up'
    if key == readchar.key.DOWN or key == readchar.key.CTRL_N:
        return 'down'

    if key == readchar.key.ENTER:
        return 'enter'

    if key == readchar.key.ESC:
        return 'escape'

    if key == readchar.key.CTRL_C:
        raise KeyboardInterrupt

    return key

def select_with_arrows(options: dict, prompt_text: str = "اختر خياراً", default_key: str = None) -> str:
    """
    Interactive selection using arrow keys with Rich Live display.

    Args:
        options: Dict with keys as option keys and values as descriptions
        prompt_text: Text to show above the options
        default_key: Default option key to start with

    Returns:
        Selected option key
    """
    option_keys = list(options.keys())
    if default_key and default_key in option_keys:
        selected_index = option_keys.index(default_key)
    else:
        selected_index = 0

    selected_key = None

    def create_selection_panel():
        """Create the selection panel with current selection highlighted."""
        table = Table.grid(padding=(0, 2))
        table.add_column(style="cyan", justify="left", width=3)
        table.add_column(style="white", justify="left")

        for i, key in enumerate(option_keys):
            if i == selected_index:
                table.add_row("▶", f"[cyan]{key}[/cyan] [dim]({options[key]})[/dim]")
            else:
                table.add_row(" ", f"[cyan]{key}[/cyan] [dim]({options[key]})[/dim]")

        table.add_row("", "")
        table.add_row("", "[dim]استخدم ↑/↓ للتنقل، Enter للاختيار، Esc للإلغاء[/dim]")

        return Panel(
            table,
            title=f"[bold]{prompt_text}[/bold]",
            border_style="cyan",
            padding=(1, 2)
        )

    console.print()

    def run_selection_loop():
        nonlocal selected_key, selected_index
        with Live(create_selection_panel(), console=console, transient=True, auto_refresh=False) as live:
            while True:
                try:
                    key = get_key()
                    if key == 'up':
                        selected_index = (selected_index - 1) % len(option_keys)
                    elif key == 'down':
                        selected_index = (selected_index + 1) % len(option_keys)
                    elif key == 'enter':
                        selected_key = option_keys[selected_index]
                        break
                    elif key == 'escape':
                        console.print("\n[yellow]تم إلغاء الاختيار[/yellow]")
                        raise typer.Exit(1)

                    live.update(create_selection_panel(), refresh=True)

                except KeyboardInterrupt:
                    console.print("\n[yellow]تم إلغاء الاختيار[/yellow]")
                    raise typer.Exit(1)

    run_selection_loop()

    if selected_key is None:
        console.print("\n[red]فشل الاختيار.[/red]")
        raise typer.Exit(1)

    return selected_key

console = Console(highlight=False)

class BannerGroup(TyperGroup):
    """Custom group that shows banner before help."""

    def format_help(self, ctx, formatter):
        # Show banner before help
        show_banner()
        super().format_help(ctx, formatter)


app = typer.Typer(
    name="specify",
    help="تهيئة مشاريع Specify — سير عمل موجّه بالمواصفات",
    add_completion=False,
    invoke_without_command=True,
    cls=BannerGroup,
)

def show_banner():
    """Display the ASCII art banner."""
    banner_lines = BANNER.strip().split('\n')
    colors = ["bright_blue", "blue", "cyan", "bright_cyan", "white", "bright_white"]

    styled_banner = Text()
    for i, line in enumerate(banner_lines):
        color = colors[i % len(colors)]
        styled_banner.append(line + "\n", style=color)

    console.print(Align.center(styled_banner))
    console.print(Align.center(Text(TAGLINE, style="italic bright_yellow")))
    console.print()

def _version_callback(value: bool):
    if value:
        console.print(f"specify {get_speckit_version()}")
        raise typer.Exit()

@app.callback()
def callback(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-V", callback=_version_callback, is_eager=True, help="عرض الإصدار والخروج."),
):
    """Show banner when no subcommand is provided."""
    if ctx.invoked_subcommand is None and "--help" not in sys.argv and "-h" not in sys.argv:
        show_banner()
        console.print(Align.center("[dim]نفّذ specify --help لعرض طريقة الاستخدام[/dim]"))
        console.print()

def run_command(cmd: list[str], check_return: bool = True, capture: bool = False, shell: bool = False) -> Optional[str]:
    """Run a shell command and optionally capture output."""
    try:
        if capture:
            result = subprocess.run(cmd, check=check_return, capture_output=True, text=True, shell=shell)
            return result.stdout.strip()
        else:
            subprocess.run(cmd, check=check_return, shell=shell)
            return None
    except subprocess.CalledProcessError as e:
        if check_return:
            console.print(f"[red]خطأ في تشغيل الأمر:[/red] {' '.join(cmd)}")
            console.print(f"[red]رمز الخروج:[/red] {e.returncode}")
            if hasattr(e, 'stderr') and e.stderr:
                console.print(f"[red]مخرجات الخطأ:[/red] {e.stderr}")
            raise
        return None

def check_tool(tool: str, tracker: StepTracker = None) -> bool:
    """Check if a tool is installed. Optionally update tracker.

    Args:
        tool: Name of the tool to check
        tracker: Optional StepTracker to update with results

    Returns:
        True if tool is found, False otherwise
    """
    # Special handling for Claude CLI local installs
    # See: https://github.com/github/spec-kit/issues/123
    # See: https://github.com/github/spec-kit/issues/550
    # Claude Code can be installed in two local paths:
    #   1. ~/.claude/local/claude          (after `claude migrate-installer`)
    #   2. ~/.claude/local/node_modules/.bin/claude  (npm-local install, e.g. via nvm)
    # Neither path may be on the system PATH, so we check them explicitly.
    if tool == "claude":
        if CLAUDE_LOCAL_PATH.is_file() or CLAUDE_NPM_LOCAL_PATH.is_file():
            if tracker:
                tracker.complete(tool, "متاح")
            return True

    if tool == "kiro-cli":
        # Kiro currently supports both executable names. Prefer kiro-cli and
        # accept kiro as a compatibility fallback.
        found = shutil.which("kiro-cli") is not None or shutil.which("kiro") is not None
    else:
        found = shutil.which(tool) is not None

    if tracker:
        if found:
            tracker.complete(tool, "متاح")
        else:
            tracker.error(tool, "غير موجود")

    return found


def is_git_repo(path: Path = None) -> bool:
    """Check if the specified path is inside a git repository."""
    if path is None:
        path = Path.cwd()

    if not path.is_dir():
        return False

    try:
        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            check=True,
            capture_output=True,
            cwd=path,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def init_git_repo(project_path: Path, quiet: bool = False) -> tuple[bool, Optional[str]]:
    """Initialize a git repository in the specified path."""
    try:
        original_cwd = Path.cwd()
        os.chdir(project_path)
        if not quiet:
            console.print("[cyan]جاري تهيئة مستودع git...[/cyan]")
        subprocess.run(["git", "init"], check=True, capture_output=True, text=True)
        subprocess.run(["git", "add", "."], check=True, capture_output=True, text=True)
        subprocess.run(["git", "commit", "-m", "Initial commit from Specify template"], check=True, capture_output=True, text=True)
        if not quiet:
            console.print("[green]✓[/green] تمت تهيئة مستودع git")
        return True, None
    except subprocess.CalledProcessError as e:
        error_msg = f"Command: {' '.join(e.cmd)}\nExit code: {e.returncode}"
        if e.stderr:
            error_msg += f"\nError: {e.stderr.strip()}"
        elif e.stdout:
            error_msg += f"\nOutput: {e.stdout.strip()}"
        if not quiet:
            console.print(f"[red]خطأ في تهيئة مستودع git:[/red] {e}")
        return False, error_msg
    finally:
        os.chdir(original_cwd)


def handle_vscode_settings(sub_item, dest_file, rel_path, verbose=False, tracker=None) -> None:
    """Handle merging or copying of .vscode/settings.json files.

    Note: when merge produces changes, rewritten output is normalized JSON and
    existing JSONC comments/trailing commas are not preserved.
    """
    def log(message, color="green"):
        if verbose and not tracker:
            console.print(f"[{color}]{message}[/] {rel_path}")

    def atomic_write_json(target_file: Path, payload: dict[str, Any]) -> None:
        """Atomically write JSON while preserving existing mode bits when possible."""
        temp_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode='w',
                encoding='utf-8',
                dir=target_file.parent,
                prefix=f"{target_file.name}.",
                suffix=".tmp",
                delete=False,
            ) as f:
                temp_path = Path(f.name)
                json.dump(payload, f, indent=4)
                f.write('\n')

            if target_file.exists():
                try:
                    existing_stat = target_file.stat()
                    os.chmod(temp_path, stat.S_IMODE(existing_stat.st_mode))
                    if hasattr(os, "chown"):
                        try:
                            os.chown(temp_path, existing_stat.st_uid, existing_stat.st_gid)
                        except PermissionError:
                            # Best-effort owner/group preservation without requiring elevated privileges.
                            pass
                except OSError:
                    # Best-effort metadata preservation; data safety is prioritized.
                    pass

            os.replace(temp_path, target_file)
        except Exception:
            if temp_path and temp_path.exists():
                temp_path.unlink()
            raise

    try:
        with open(sub_item, 'r', encoding='utf-8') as f:
            # json5 natively supports comments and trailing commas (JSONC)
            new_settings = json5.load(f)

        if dest_file.exists():
            merged = merge_json_files(dest_file, new_settings, verbose=verbose and not tracker)
            if merged is not None:
                atomic_write_json(dest_file, merged)
                log("Merged:", "green")
                log("Note: comments/trailing commas are normalized when rewritten", "yellow")
            else:
                log("تم تخطّي الدمج (الإعدادات الموجودة محفوظة)", "yellow")
        else:
            shutil.copy2(sub_item, dest_file)
            log("Copied (no existing settings.json):", "blue")

    except Exception as e:
        log(f"Warning: Could not merge settings: {e}", "yellow")
        if not dest_file.exists():
            shutil.copy2(sub_item, dest_file)


def merge_json_files(existing_path: Path, new_content: Any, verbose: bool = False) -> Optional[dict[str, Any]]:
    """Merge new JSON content into existing JSON file.

    Performs a polite deep merge where:
    - New keys are added
    - Existing keys are preserved (not overwritten) unless both values are dictionaries
    - Nested dictionaries are merged recursively only when both sides are dictionaries
    - Lists and other values are preserved from base if they exist

    Args:
        existing_path: Path to existing JSON file
        new_content: New JSON content to merge in
        verbose: Whether to print merge details

    Returns:
        Merged JSON content as dict, or None if the existing file should be left untouched.
    """
    # Load existing content first to have a safe fallback
    existing_content = None
    exists = existing_path.exists()

    if exists:
        try:
            with open(existing_path, 'r', encoding='utf-8') as f:
                # Handle comments (JSONC) natively with json5
                # Note: json5 handles BOM automatically
                existing_content = json5.load(f)
        except FileNotFoundError:
            # Handle race condition where file is deleted after exists() check
            exists = False
        except Exception as e:
            if verbose:
                console.print(f"[yellow]تحذير: تعذّرت قراءة أو تحليل JSON الموجود في {existing_path.name} ({e}).[/yellow]")
            # Skip merge to preserve existing file if unparseable or inaccessible (e.g. PermissionError)
            return None

    # Validate template content
    if not isinstance(new_content, dict):
        if verbose:
            console.print(f"[yellow]تحذير: محتوى القالب لـ {existing_path.name} ليس قاموساً. تم الحفاظ على الإعدادات الموجودة.[/yellow]")
        return None

    if not exists:
        return new_content

    # If existing content parsed but is not a dict, skip merge to avoid data loss
    if not isinstance(existing_content, dict):
        if verbose:
            console.print(f"[yellow]تحذير: JSON الموجود في {existing_path.name} ليس كائناً. تخطّي الدمج لتجنّب فقدان البيانات.[/yellow]")
        return None

    def deep_merge_polite(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
        """Recursively merge update dict into base dict, preserving base values."""
        result = base.copy()
        for key, value in update.items():
            if key not in result:
                # Add new key
                result[key] = value
            elif isinstance(result[key], dict) and isinstance(value, dict):
                # Recursively merge nested dictionaries
                result[key] = deep_merge_polite(result[key], value)
            else:
                # Key already exists and values are not both dicts; preserve existing value.
                # This ensures user settings aren't overwritten by template defaults.
                pass
        return result

    merged = deep_merge_polite(existing_content, new_content)

    # Detect if anything actually changed. If not, return None so the caller
    # can skip rewriting the file (preserving user's comments/formatting).
    if merged == existing_content:
        return None

    if verbose:
        console.print(f"[cyan]Merged JSON file:[/cyan] {existing_path.name}")

    return merged

def _locate_core_pack() -> Path | None:
    """Return the filesystem path to the bundled core_pack directory, or None.

    Only present in wheel installs: hatchling's force-include copies
    templates/, scripts/ etc. into specify_cli/core_pack/ at build time.

    Source-checkout and editable installs do NOT have this directory.
    Callers that need to work in both environments must check the repo-root
    trees (templates/, scripts/) as a fallback when this returns None.
    """
    # Wheel install: core_pack is a sibling directory of this file
    candidate = Path(__file__).parent / "core_pack"
    if candidate.is_dir():
        return candidate
    return None


def _repo_root() -> Path:
    """Return the source checkout root used for editable installs."""
    return Path(__file__).parent.parent.parent


def _locate_bundled_extension(extension_id: str) -> Path | None:
    """Return the path to a bundled extension, or None.

    Checks the wheel's core_pack first, then falls back to the
    source-checkout ``extensions/<id>/`` directory.
    """
    import re as _re
    if not _re.match(r'^[a-z0-9-]+$', extension_id):
        return None

    core = _locate_core_pack()
    if core is not None:
        candidate = core / "extensions" / extension_id
        if (candidate / "extension.yml").is_file():
            return candidate

    # Source-checkout / editable install: look relative to repo root
    candidate = _repo_root() / "extensions" / extension_id
    if (candidate / "extension.yml").is_file():
        return candidate

    return None


def _locate_bundled_workflow(workflow_id: str) -> Path | None:
    """Return the path to a bundled workflow directory, or None.

    Checks the wheel's core_pack first, then falls back to the
    source-checkout ``workflows/<id>/`` directory.
    """
    import re as _re
    if not _re.match(r'^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$', workflow_id):
        return None

    core = _locate_core_pack()
    if core is not None:
        candidate = core / "workflows" / workflow_id
        if (candidate / "workflow.yml").is_file():
            return candidate

    # Source-checkout / editable install: look relative to repo root
    candidate = _repo_root() / "workflows" / workflow_id
    if (candidate / "workflow.yml").is_file():
        return candidate

    return None


def _locate_bundled_preset(preset_id: str) -> Path | None:
    """Return the path to a bundled preset, or None.

    Checks the wheel's core_pack first, then falls back to the
    source-checkout ``presets/<id>/`` directory.
    """
    import re as _re
    if not _re.match(r'^[a-z0-9-]+$', preset_id):
        return None

    core = _locate_core_pack()
    if core is not None:
        candidate = core / "presets" / preset_id
        if (candidate / "preset.yml").is_file():
            return candidate

    # Source-checkout / editable install: look relative to repo root
    candidate = _repo_root() / "presets" / preset_id
    if (candidate / "preset.yml").is_file():
        return candidate

    return None


def _refresh_shared_templates(
    project_path: Path,
    *,
    invoke_separator: str,
    force: bool = False,
) -> None:
    """Refresh default-sensitive shared templates without touching scripts."""
    _refresh_shared_templates_impl(
        project_path,
        version=get_speckit_version(),
        core_pack=_locate_core_pack(),
        repo_root=_repo_root(),
        console=console,
        invoke_separator=invoke_separator,
        force=force,
    )


def _install_shared_infra(
    project_path: Path,
    script_type: str,
    tracker: StepTracker | None = None,
    force: bool = False,
    invoke_separator: str = ".",
) -> bool:
    """Install shared infrastructure files into *project_path*.

    Copies ``.specify/scripts/`` and ``.specify/templates/`` from the
    bundled core_pack or source checkout.  Tracks all installed files
    in ``speckit.manifest.json``.

    Page templates are processed to resolve ``__SPECKIT_COMMAND_<NAME>__``
    placeholders using *invoke_separator* (``"."`` for markdown agents,
    ``"-"`` for skills agents).

    When *force* is ``True``, existing files are overwritten with the
    latest bundled versions.  When ``False`` (default), only missing
    files are added and existing ones are skipped.

    Returns ``True`` on success.
    """
    return _install_shared_infra_impl(
        project_path,
        script_type,
        version=get_speckit_version(),
        core_pack=_locate_core_pack(),
        repo_root=_repo_root(),
        console=console,
        force=force,
        invoke_separator=invoke_separator,
    )


def _install_shared_infra_or_exit(
    project_path: Path,
    script_type: str,
    tracker: StepTracker | None = None,
    force: bool = False,
    invoke_separator: str = ".",
) -> bool:
    try:
        return _install_shared_infra(
            project_path,
            script_type,
            tracker=tracker,
            force=force,
            invoke_separator=invoke_separator,
        )
    except (ValueError, OSError) as exc:
        console.print(f"[red]خطأ:[/red] فشل تثبيت البنية التحتية المشتركة: {exc}")
        raise typer.Exit(1)


def ensure_executable_scripts(project_path: Path, tracker: StepTracker | None = None) -> None:
    """Ensure POSIX .sh scripts under .specify/scripts and .specify/extensions (recursively) have execute bits (no-op on Windows)."""
    if os.name == "nt":
        return  # Windows: skip silently
    scan_roots = [
        project_path / ".specify" / "scripts",
        project_path / ".specify" / "extensions",
    ]
    failures: list[str] = []
    updated = 0
    for scripts_root in scan_roots:
        if not scripts_root.is_dir():
            continue
        for script in scripts_root.rglob("*.sh"):
            try:
                if script.is_symlink() or not script.is_file():
                    continue
                try:
                    with script.open("rb") as f:
                        if f.read(2) != b"#!":
                            continue
                except Exception:
                    continue
                st = script.stat()
                mode = st.st_mode
                if mode & 0o111:
                    continue
                new_mode = mode
                if mode & 0o400:
                    new_mode |= 0o100
                if mode & 0o040:
                    new_mode |= 0o010
                if mode & 0o004:
                    new_mode |= 0o001
                if not (new_mode & 0o100):
                    new_mode |= 0o100
                os.chmod(script, new_mode)
                updated += 1
            except Exception as e:
                failures.append(f"{_display_project_path(project_path, script)}: {e}")
    if tracker:
        detail = f"{updated} مُحدّث" + (f"، {len(failures)} فشل" if failures else "")
        tracker.add("chmod", "ضبط صلاحيات السكربتات بشكل متكرر")
        (tracker.error if failures else tracker.complete)("chmod", detail)
    else:
        if updated:
            console.print(f"[cyan]تم تحديث صلاحيات التنفيذ لـ {updated} سكربت/سكربتات بشكل متكرر[/cyan]")
        if failures:
            console.print("[yellow]تعذّر تحديث بعض السكربتات:[/yellow]")
            for f in failures:
                console.print(f"  - {f}")

def ensure_constitution_from_template(project_path: Path, tracker: StepTracker | None = None) -> None:
    """Copy constitution template to memory if it doesn't exist (preserves existing constitution on reinitialization)."""
    memory_constitution = project_path / ".specify" / "memory" / "constitution.md"
    template_constitution = project_path / ".specify" / "templates" / "constitution-template.md"

    # If constitution already exists in memory, preserve it
    if memory_constitution.exists():
        if tracker:
            tracker.add("constitution", "إعداد الدستور")
            tracker.skip("constitution", "تم الحفاظ على الملف الموجود")
        return

    # If template doesn't exist, something went wrong with extraction
    if not template_constitution.exists():
        if tracker:
            tracker.add("constitution", "إعداد الدستور")
            tracker.error("constitution", "القالب غير موجود")
        return

    # Copy template to memory directory
    try:
        memory_constitution.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template_constitution, memory_constitution)
        if tracker:
            tracker.add("constitution", "إعداد الدستور")
            tracker.complete("constitution", "تم النسخ من القالب")
        else:
            console.print("[cyan]تمت تهيئة الدستور من القالب[/cyan]")
    except Exception as e:
        if tracker:
            tracker.add("constitution", "إعداد الدستور")
            tracker.error("constitution", str(e))
        else:
            console.print(f"[yellow]تحذير: تعذّر تهيئة الدستور: {e}[/yellow]")


INIT_OPTIONS_FILE = ".specify/init-options.json"


def save_init_options(project_path: Path, options: dict[str, Any]) -> None:
    """Persist the CLI options used during ``specify init``.

    Writes a small JSON file to ``.specify/init-options.json`` so that
    later operations (e.g. preset install) can adapt their behaviour
    without scanning the filesystem.
    """
    dest = project_path / INIT_OPTIONS_FILE
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(options, indent=2, sort_keys=True))


def load_init_options(project_path: Path) -> dict[str, Any]:
    """Load the init options previously saved by ``specify init``.

    Returns an empty dict if the file does not exist or cannot be parsed.
    """
    path = project_path / INIT_OPTIONS_FILE
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _get_skills_dir(project_path: Path, selected_ai: str) -> Path:
    """Resolve the agent-specific skills directory.

    Returns ``project_path / <agent_folder> / "skills"``, falling back
    to ``project_path / ".agents/skills"`` for unknown agents.
    """
    agent_config = AGENT_CONFIG.get(selected_ai, {})
    agent_folder = agent_config.get("folder", "")
    if agent_folder:
        return project_path / agent_folder.rstrip("/") / "skills"
    return project_path / ".agents" / "skills"


# Constants kept for backward compatibility with presets and extensions.
DEFAULT_SKILLS_DIR = ".agents/skills"
SKILL_DESCRIPTIONS = {
    "specify": "مواصفة الميزة من وصف نصّي.",
    "plan": "خطة تنفيذ تقنية من الـ spec.",
    "tasks": "تقسيم الخطة إلى مهام منفّذة.",
    "implement": "تنفيذ مهام tasks.md لحد ما الميزة تكتمل.",
    "analyze": "فحص اتساق spec / plan / tasks (قراءة فقط).",
    "clarify": "أسئلة توضيح ودمجها في المواصفة.",
    "constitution": "دستور المشروع: مبادئ وقواعد التطوير.",
    "checklist": "checklist جودة حسب المجال.",
    "taskstoissues": "من tasks.md إلى issues على GitHub.",
}


@app.command()
def init(
    project_name: str = typer.Argument(None, help="اسم مجلد المشروع الجديد (اختياري مع --here، أو استخدم '.' للمجلد الحالي)"),
    ai_assistant: str = typer.Option(None, "--ai", help=AI_ASSISTANT_HELP),
    ai_commands_dir: str = typer.Option(None, "--ai-commands-dir", help="مجلد ملفات أوامر الوكيل (مطلوب مع --ai generic، مثال: .myagent/commands/)"),
    script_type: str = typer.Option(None, "--script", help="نوع السكربت المستخدم: sh أو ps"),
    ignore_agent_tools: bool = typer.Option(False, "--ignore-agent-tools", help="تخطي فحص أدوات وكلاء البرمجة مثل Claude Code"),
    no_git: bool = typer.Option(False, "--no-git", help="تخطي تهيئة مستودع git"),
    here: bool = typer.Option(False, "--here", help="تهيئة المشروع في المجلد الحالي بدل إنشاء واحد جديد"),
    force: bool = typer.Option(False, "--force", help="فرض الدمج/الاستبدال عند استخدام --here (تخطي التأكيد)"),
    skip_tls: bool = typer.Option(False, "--skip-tls", help="مهمل (بدون تأثير). سابقاً: تخطي تحقق SSL/TLS.", hidden=True),
    debug: bool = typer.Option(False, "--debug", help="مهمل (بدون تأثير). سابقاً: عرض مخرجات تشخيصية مفصّلة.", hidden=True),
    github_token: str = typer.Option(None, "--github-token", help="مهمل (بدون تأثير). سابقاً: رمز GitHub لطلبات الـ API.", hidden=True),
    ai_skills: bool = typer.Option(False, "--ai-skills", help="تثبيت قوالب Prompt.MD كمهارات للوكيل (يتطلب --ai)"),
    offline: bool = typer.Option(False, "--offline", help="مهمل (بدون تأثير). كل عمليات التهيئة الآن تستخدم الأصول المضمّنة.", hidden=True),
    preset: str = typer.Option(None, "--preset", help="تثبيت وصفة (preset) أثناء التهيئة (بواسطة معرّف الوصفة)"),
    branch_numbering: str = typer.Option(None, "--branch-numbering", help="استراتيجية ترقيم الفروع: 'sequential' (001, 002, …, 1000, … — تتوسّع تلقائياً بعد 999) أو 'timestamp' (YYYYMMDD-HHMMSS)"),
    integration: str = typer.Option(None, "--integration", help="استخدام نظام التكاملات الجديد (مثال: --integration copilot). لا يُستخدم مع --ai."),
    integration_options: str = typer.Option(None, "--integration-options", help='خيارات التكامل (مثال: --integration-options="--commands-dir .myagent/cmds")'),
):
    """
    تبدأ مشروع Specify من الصفر أو داخل مجلد موجود.

    افتراضياً: ملفات القالب من آخر إصدار على GitHub.
    `--offline`: كل شيء من الحزمة المحلية (مناسب بدون إنترنت أو شبكات مقفلة).

    ملاحظة: من v0.6.0 الأصول المضمّنة تصير الافتراضي ويختفي `--offline` لاحقاً؛
    الهدف: قوالب دائماً متطابقة مع إصدار الـ CLI.

    يعمل `init` عادةً على الخطوات التالية:
    1. يتأكد من الأدوات المتاحة (git اختياري)
    2. يخليك تختار تكامل الـ AI
    3. ينزّل القوالب أو يستخدم المضمّن مع `--offline`
    4. يهيّئ git إذا ما مرّرت `--no-git` وما فيه repo
    5. يضبط أوامر الوكيل إن اخترت تكاملاً

    أمثلة:
        specify init my-project
        specify init my-project --integration claude
        specify init my-project --integration copilot --no-git
        specify init --ignore-agent-tools my-project
        specify init . --integration claude         # Initialize in current directory
        specify init .                     # Initialize in current directory (interactive integration selection)
        specify init --here --integration claude    # Alternative syntax for current directory
        specify init --here --integration codex --integration-options="--skills"
        specify init --here --integration codebuddy
        specify init --here --integration vibe      # Initialize with Mistral Vibe support
        specify init --here
        specify init --here --force  # Skip confirmation when current directory not empty
        specify init my-project --integration claude   # Claude installs skills by default
        specify init --here --integration gemini
        specify init my-project --integration generic --integration-options="--commands-dir .myagent/commands/"  # Bring your own agent; requires --commands-dir
        specify init my-project --integration claude --preset healthcare-compliance  # With preset
    """

    show_banner()
    ai_deprecation_warning: str | None = None

    # Detect when option values are likely misinterpreted flags (parameter ordering issue)
    if ai_assistant and ai_assistant.startswith("--"):
        console.print(f"[red]خطأ:[/red] قيمة غير صالحة لـ --ai: '{ai_assistant}'")
        console.print("[yellow]تلميح:[/yellow] هل نسيت تمرير قيمة لـ --ai؟")
        console.print("[yellow]مثال:[/yellow] specify init --integration claude --here")
        console.print(f"[yellow]الوكلاء المتاحون:[/yellow] {', '.join(AGENT_CONFIG.keys())}")
        raise typer.Exit(1)

    if ai_commands_dir and ai_commands_dir.startswith("--"):
        console.print(f"[red]خطأ:[/red] قيمة غير صالحة لـ --ai-commands-dir: '{ai_commands_dir}'")
        console.print("[yellow]تلميح:[/yellow] هل نسيت تمرير قيمة لـ --ai-commands-dir؟")
        console.print("[yellow]مثال:[/yellow] specify init --integration generic --integration-options=\"--commands-dir .myagent/commands/\"")
        raise typer.Exit(1)

    if ai_assistant:
        ai_assistant = AI_ASSISTANT_ALIASES.get(ai_assistant, ai_assistant)

    # --integration and --ai are mutually exclusive
    if integration and ai_assistant:
        console.print("[red]خطأ:[/red] --integration و --ai غير متوافقين معاً")
        raise typer.Exit(1)

    # Resolve the integration — either from --integration or --ai
    from .integrations import INTEGRATION_REGISTRY, get_integration
    if integration:
        resolved_integration = get_integration(integration)
        if not resolved_integration:
            console.print(f"[red]خطأ:[/red] تكامل غير معروف: '{integration}'")
            available = ", ".join(sorted(INTEGRATION_REGISTRY))
            console.print(f"[yellow]التكاملات المتاحة:[/yellow] {available}")
            raise typer.Exit(1)
        ai_assistant = integration
    elif ai_assistant:
        resolved_integration = get_integration(ai_assistant)
        if not resolved_integration:
            console.print(f"[red]خطأ:[/red] وكيل غير معروف '{ai_assistant}'. اختر من: {', '.join(sorted(INTEGRATION_REGISTRY))}")
            raise typer.Exit(1)
        ai_deprecation_warning = _build_ai_deprecation_warning(
            resolved_integration.key,
            ai_commands_dir=ai_commands_dir,
        )

    # Deprecation warnings for --ai-skills and --ai-commands-dir (only when
    # an integration has been resolved from --ai or --integration)
    if ai_assistant or integration:
        if ai_skills:
            from .integrations.base import SkillsIntegration as _SkillsCheck
            if isinstance(resolved_integration, _SkillsCheck):
                console.print(
                    "[dim]ملاحظة: --ai-skills غير مطلوب؛ "
                    "المهارات هي الافتراضي لهذا التكامل.[/dim]"
                )
            else:
                console.print(
                    "[dim]ملاحظة: --ai-skills لا تأثير له مع "
                    f"{resolved_integration.key}؛ هذا التكامل يستخدم الأوامر وليس المهارات.[/dim]"
                )
        if ai_commands_dir and resolved_integration.key != "generic":
            console.print(
                "[dim]ملاحظة: --ai-commands-dir مهمل؛ "
                'استخدم [bold]--integration generic --integration-options="--commands-dir <dir>"[/bold] بدلاً منه.[/dim]'
            )

    if no_git:
        console.print(
            "[yellow]⚠️  --no-git مهمل وسيُزال في الإصدار v0.10.0.[/yellow]\n"
            "[yellow]امتداد git لن يُفعّل افتراضياً بعد الآن "
            "— استخدم أوامر [bold]specify extension[/bold] لتثبيت أو تفعيل امتداد git عند الحاجة.[/yellow]"
        )

    if project_name == ".":
        here = True
        project_name = None  # Clear project_name to use existing validation logic

    if here and project_name:
        console.print("[red]خطأ:[/red] لا يمكن تحديد اسم مشروع و --here معاً")
        raise typer.Exit(1)

    if not here and not project_name:
        console.print("[red]خطأ:[/red] يجب تحديد اسم مشروع، أو استخدام '.' للمجلد الحالي، أو استخدام --here")
        raise typer.Exit(1)

    if ai_skills and not ai_assistant:
        console.print("[red]خطأ:[/red] --ai-skills يتطلب تحديد --ai")
        console.print("[yellow]الاستخدام:[/yellow] specify init <project> --ai <agent> --ai-skills")
        raise typer.Exit(1)

    BRANCH_NUMBERING_CHOICES = {"sequential", "timestamp"}
    if branch_numbering and branch_numbering not in BRANCH_NUMBERING_CHOICES:
        console.print(f"[red]خطأ:[/red] قيمة غير صالحة لـ --branch-numbering '{branch_numbering}'. اختر من: {', '.join(sorted(BRANCH_NUMBERING_CHOICES))}")
        raise typer.Exit(1)

    dir_existed_before = False
    if here:
        project_name = Path.cwd().name
        project_path = Path.cwd()
        dir_existed_before = True

        existing_items = list(project_path.iterdir())
        if existing_items:
            console.print(f"[yellow]تحذير:[/yellow] المجلد الحالي ليس فارغاً ({len(existing_items)} عناصر)")
            console.print("[yellow]ملفات القالب ستُدمج مع المحتوى الموجود وقد تستبدل ملفات موجودة[/yellow]")
            if force:
                console.print("[cyan]تم تمرير --force: تخطي التأكيد والمتابعة بالدمج[/cyan]")
            else:
                response = typer.confirm("هل تريد المتابعة؟")
                if not response:
                    console.print("[yellow]تم إلغاء العملية[/yellow]")
                    raise typer.Exit(0)
    else:
        project_path = Path(project_name).resolve()
        dir_existed_before = project_path.exists()
        if project_path.exists():
            if not project_path.is_dir():
                console.print(f"[red]خطأ:[/red] '{project_name}' موجود لكنه ليس مجلداً.")
                raise typer.Exit(1)
            existing_items = list(project_path.iterdir())
            if force:
                if existing_items:
                    console.print(f"[yellow]تحذير:[/yellow] المجلد '{project_name}' ليس فارغاً ({len(existing_items)} عناصر)")
                    console.print("[yellow]ملفات القالب ستُدمج مع المحتوى الموجود وقد تستبدل ملفات موجودة[/yellow]")
                console.print(f"[cyan]تم تمرير --force: الدمج داخل المجلد الموجود '[cyan]{project_name}[/cyan]'[/cyan]")
            else:
                error_panel = Panel(
                    f"المجلد موجود مسبقاً: '[cyan]{project_name}[/cyan]'\n"
                    "يرجى اختيار اسم مشروع آخر أو حذف المجلد الموجود.\n"
                    "استخدم [bold]--force[/bold] للدمج داخل المجلد الموجود.",
                    title="[red]تعارض في المجلد[/red]",
                    border_style="red",
                    padding=(1, 2)
                )
                console.print()
                console.print(error_panel)
                raise typer.Exit(1)

    if ai_assistant:
        if ai_assistant not in AGENT_CONFIG:
            console.print(f"[red]خطأ:[/red] وكيل AI غير صالح '{ai_assistant}'. اختر من: {', '.join(AGENT_CONFIG.keys())}")
            raise typer.Exit(1)
        selected_ai = ai_assistant
    else:
        # Create options dict for selection (agent_key: display_name)
        ai_choices = {key: config["name"] for key, config in AGENT_CONFIG.items()}
        selected_ai = select_with_arrows(
            ai_choices,
            "اختر تكامل وكيل البرمجة:",
            "copilot"
        )

    # Auto-promote interactively selected agents to the integration path
    if not ai_assistant:
        resolved_integration = get_integration(selected_ai)
        if not resolved_integration:
            console.print(f"[red]خطأ:[/red] وكيل غير معروف '{selected_ai}'")
            raise typer.Exit(1)

    # Validate --ai-commands-dir usage.
    # Skip validation when --integration-options is provided — the integration
    # will validate its own options in setup().
    if selected_ai == "generic" and not integration_options:
        if not ai_commands_dir:
            console.print("[red]خطأ:[/red] --ai-commands-dir مطلوب عند استخدام --ai generic أو --integration generic")
            console.print('[dim]مثال: specify init my-project --integration generic --integration-options="--commands-dir .myagent/commands/"[/dim]')
            raise typer.Exit(1)

    current_dir = Path.cwd()

    setup_lines = [
        "[cyan]إعداد مشروع Specify[/cyan]",
        "",
        f"{'المشروع':<15} [green]{project_path.name}[/green]",
        f"{'مسار العمل':<15} [dim]{current_dir}[/dim]",
    ]

    if not here:
        setup_lines.append(f"{'المسار الهدف':<15} [dim]{project_path}[/dim]")

    console.print(Panel("\n".join(setup_lines), border_style="cyan", padding=(1, 2)))

    should_init_git = False
    if not no_git:
        should_init_git = check_tool("git")
        if not should_init_git:
            console.print("[yellow]لم يُعثر على Git - سيتم تخطي تهيئة المستودع[/yellow]")

    if not ignore_agent_tools:
        agent_config = AGENT_CONFIG.get(selected_ai)
        if agent_config and agent_config["requires_cli"]:
            install_url = agent_config["install_url"]
            if not check_tool(selected_ai):
                error_panel = Panel(
                    f"[cyan]{selected_ai}[/cyan] غير موجود\n"
                    f"التثبيت من: [cyan]{install_url}[/cyan]\n"
                    f"{agent_config['name']} مطلوب للمتابعة مع هذا النوع من المشاريع.\n\n"
                    "تلميح: استخدم [cyan]--ignore-agent-tools[/cyan] لتخطي هذا الفحص",
                    title="[red]خطأ في اكتشاف الوكيل[/red]",
                    border_style="red",
                    padding=(1, 2)
                )
                console.print()
                console.print(error_panel)
                raise typer.Exit(1)

    if script_type:
        if script_type not in SCRIPT_TYPE_CHOICES:
            console.print(f"[red]خطأ:[/red] نوع سكربت غير صالح '{script_type}'. اختر من: {', '.join(SCRIPT_TYPE_CHOICES.keys())}")
            raise typer.Exit(1)
        selected_script = script_type
    else:
        default_script = "ps" if os.name == "nt" else "sh"

        if sys.stdin.isatty():
            selected_script = select_with_arrows(SCRIPT_TYPE_CHOICES, "اختر نوع السكربت (أو اضغط Enter)", default_script)
        else:
            selected_script = default_script

    console.print(f"[cyan]تكامل وكيل البرمجة المختار:[/cyan] {selected_ai}")
    console.print(f"[cyan]نوع السكربت المختار:[/cyan] {selected_script}")

    tracker = StepTracker("تهيئة مشروع Specify")

    sys._specify_tracker_active = True

    tracker.add("precheck", "فحص الأدوات المطلوبة")
    tracker.complete("precheck", "تم")
    tracker.add("ai-select", "اختيار تكامل وكيل البرمجة")
    tracker.complete("ai-select", f"{selected_ai}")
    tracker.add("script-select", "اختيار نوع السكربت")
    tracker.complete("script-select", selected_script)

    tracker.add("integration", "تثبيت التكامل")
    tracker.add("shared-infra", "تثبيت البنية التحتية المشتركة")

    for key, label in [
        ("chmod", "التأكد من قابلية تنفيذ السكربتات"),
        ("constitution", "إعداد الدستور"),
        ("git", "تثبيت امتداد git"),
        ("workflow", "تثبيت سير العمل المضمّن"),
        ("final", "الإنهاء"),
    ]:
        tracker.add(key, label)

    git_default_notice = False

    with Live(tracker.render(), console=console, refresh_per_second=8, transient=True) as live:
        tracker.attach_refresh(lambda: live.update(tracker.render()))
        try:
            # Integration-based scaffolding
            from .integrations.manifest import IntegrationManifest
            tracker.start("integration")
            manifest = IntegrationManifest(
                resolved_integration.key, project_path, version=get_speckit_version()
            )

            # Forward all legacy CLI flags to the integration as parsed_options.
            # Integrations receive every option and decide what to use;
            # irrelevant keys are simply ignored by the integration's setup().
            integration_parsed_options: dict[str, Any] = {}
            if ai_commands_dir:
                integration_parsed_options["commands_dir"] = ai_commands_dir
            if ai_skills:
                integration_parsed_options["skills"] = True
            # Parse --integration-options and merge into parsed_options so
            # flags like --skills reach the integration's setup().
            if integration_options:
                extra = _parse_integration_options(resolved_integration, integration_options)
                if extra:
                    integration_parsed_options.update(extra)

            resolved_integration.setup(
                project_path, manifest,
                parsed_options=integration_parsed_options or None,
                script_type=selected_script,
                raw_options=integration_options,
            )
            manifest.save()

            integration_settings = _with_integration_setting(
                {},
                resolved_integration.key,
                resolved_integration,
                script_type=selected_script,
                raw_options=integration_options,
                parsed_options=integration_parsed_options or None,
            )
            _write_integration_json(
                project_path,
                resolved_integration.key,
                [resolved_integration.key],
                integration_settings,
            )

            tracker.complete("integration", resolved_integration.config.get("name", resolved_integration.key))

            # Install shared infrastructure (scripts, templates)
            tracker.start("shared-infra")
            _install_shared_infra_or_exit(
                project_path,
                selected_script,
                tracker=tracker,
                force=force,
                invoke_separator=resolved_integration.effective_invoke_separator(integration_parsed_options),
            )
            tracker.complete("shared-infra", f"scripts ({selected_script}) + templates")

            ensure_constitution_from_template(project_path, tracker=tracker)

            if not no_git:
                tracker.start("git")
                git_messages = []
                git_has_error = False
                # Step 1: Initialize git repo if needed
                if is_git_repo(project_path):
                    git_messages.append("تم اكتشاف مستودع موجود")
                elif should_init_git:
                    success, error_msg = init_git_repo(project_path, quiet=True)
                    if success:
                        git_messages.append("تمت التهيئة")
                    else:
                        git_has_error = True
                        # Sanitize multi-line error_msg to single line for tracker
                        if error_msg:
                            sanitized = error_msg.replace('\n', ' ').strip()
                            git_messages.append(f"فشل التهيئة: {sanitized[:120]}")
                        else:
                            git_messages.append("فشل التهيئة")
                else:
                    git_messages.append("git غير متوفر")
                # Step 2: Install bundled git extension
                try:
                    from .extensions import ExtensionManager
                    bundled_path = _locate_bundled_extension("git")
                    if bundled_path:
                        manager = ExtensionManager(project_path)
                        if manager.registry.is_installed("git"):
                            git_messages.append("الامتداد مثبّت مسبقاً")
                        else:
                            manager.install_from_directory(
                                bundled_path, get_speckit_version()
                            )
                            git_default_notice = True
                            git_messages.append("تم تثبيت الامتداد")
                    else:
                        git_has_error = True
                        git_messages.append("الامتداد المضمّن غير موجود")
                except Exception as ext_err:
                    git_has_error = True
                    sanitized_ext = str(ext_err).replace('\n', ' ').strip()
                    git_messages.append(
                        f"فشل تثبيت الامتداد: {sanitized_ext[:120]}"
                    )
                summary = "; ".join(git_messages)
                if git_has_error:
                    tracker.error("git", summary)
                else:
                    tracker.complete("git", summary)
            else:
                tracker.skip("git", "العلم --no-git")

            # Install bundled speckit workflow
            try:
                bundled_wf = _locate_bundled_workflow("speckit")
                if bundled_wf:
                    from .workflows.catalog import WorkflowRegistry
                    from .workflows.engine import WorkflowDefinition
                    wf_registry = WorkflowRegistry(project_path)
                    if wf_registry.is_installed("speckit"):
                        tracker.complete("workflow", "مثبّت مسبقاً")
                    else:
                        import shutil as _shutil
                        dest_wf = project_path / ".specify" / "workflows" / "speckit"
                        dest_wf.mkdir(parents=True, exist_ok=True)
                        _shutil.copy2(
                            bundled_wf / "workflow.yml",
                            dest_wf / "workflow.yml",
                        )
                        definition = WorkflowDefinition.from_yaml(dest_wf / "workflow.yml")
                        wf_registry.add("speckit", {
                            "name": definition.name,
                            "version": definition.version,
                            "description": definition.description,
                            "source": "bundled",
                        })
                        tracker.complete("workflow", "تم تثبيت speckit")
                else:
                    tracker.skip("workflow", "سير العمل المضمّن غير موجود")
            except Exception as wf_err:
                sanitized_wf = str(wf_err).replace('\n', ' ').strip()
                tracker.error("workflow", f"فشل التثبيت: {sanitized_wf[:120]}")

            # Fix permissions after all installs (scripts + extensions)
            ensure_executable_scripts(project_path, tracker=tracker)

            # Persist the CLI options so later operations (e.g. preset add)
            # can adapt their behaviour without re-scanning the filesystem.
            # Must be saved BEFORE preset install so _get_skills_dir() works.
            init_opts = {
                "ai": selected_ai,
                "integration": resolved_integration.key,
                "branch_numbering": branch_numbering or "sequential",
                "context_file": resolved_integration.context_file,
                "here": here,
                "script": selected_script,
                "speckit_version": get_speckit_version(),
            }
            # Ensure ai_skills is set for SkillsIntegration so downstream
            # tools (extensions, presets) emit SKILL.md overrides correctly.
            # Also set for integrations running in skills mode (e.g. Copilot
            # with --skills).
            from .integrations.base import SkillsIntegration as _SkillsPersist
            if isinstance(resolved_integration, _SkillsPersist) or getattr(resolved_integration, "_skills_mode", False):
                init_opts["ai_skills"] = True
            save_init_options(project_path, init_opts)

            # Install preset if specified
            if preset:
                try:
                    from .presets import PresetManager, PresetCatalog, PresetError
                    preset_manager = PresetManager(project_path)
                    speckit_ver = get_speckit_version()

                    # Try local directory first, then bundled, then catalog
                    local_path = Path(preset).resolve()
                    if local_path.is_dir() and (local_path / "preset.yml").exists():
                        preset_manager.install_from_directory(local_path, speckit_ver)
                    else:
                        bundled_path = _locate_bundled_preset(preset)
                        if bundled_path:
                            preset_manager.install_from_directory(bundled_path, speckit_ver)
                        else:
                            preset_catalog = PresetCatalog(project_path)
                            pack_info = preset_catalog.get_pack_info(preset)
                            if not pack_info:
                                console.print(f"[yellow]تحذير:[/yellow] الوصفة '{preset}' غير موجودة في الكتالوج. سيتم التخطي.")
                            elif pack_info.get("bundled") and not pack_info.get("download_url"):
                                from .extensions import REINSTALL_COMMAND
                                console.print(
                                    f"[yellow]تحذير:[/yellow] الوصفة '{preset}' مضمّنة مع spec-kit "
                                    f"لكن لم يتم العثور عليها في الحزمة المثبّتة."
                                )
                                console.print(
                                    "هذا عادةً يعني أن تثبيت spec-kit غير مكتمل أو تالف."
                                )
                                console.print(f"حاول إعادة التثبيت: {REINSTALL_COMMAND}")
                            else:
                                zip_path = None
                                try:
                                    zip_path = preset_catalog.download_pack(preset)
                                    preset_manager.install_from_zip(zip_path, speckit_ver)
                                except PresetError as preset_err:
                                    console.print(f"[yellow]تحذير:[/yellow] فشل تثبيت الوصفة '{preset}': {preset_err}")
                                finally:
                                    if zip_path is not None:
                                        # Clean up downloaded ZIP to avoid cache accumulation
                                        try:
                                            zip_path.unlink(missing_ok=True)
                                        except OSError:
                                            # Best-effort cleanup; failure to delete is non-fatal
                                            pass
                except Exception as preset_err:
                    console.print(f"[yellow]تحذير:[/yellow] فشل تثبيت الوصفة: {preset_err}")

            tracker.complete("final", "المشروع جاهز")
        except (typer.Exit, SystemExit):
            raise
        except Exception as e:
            tracker.error("final", str(e))
            console.print(Panel(f"فشلت التهيئة: {e}", title="فشل", border_style="red"))
            if debug:
                _env_pairs = [
                    ("Python", sys.version.split()[0]),
                    ("Platform", sys.platform),
                    ("CWD", str(Path.cwd())),
                ]
                _label_width = max(len(k) for k, _ in _env_pairs)
                env_lines = [f"{k.ljust(_label_width)} → [bright_black]{v}[/bright_black]" for k, v in _env_pairs]
                console.print(Panel("\n".join(env_lines), title="بيئة التصحيح", border_style="magenta"))
            if not here and project_path.exists() and not dir_existed_before:
                shutil.rmtree(project_path)
            raise typer.Exit(1)
        finally:
            pass

    console.print(tracker.render())
    console.print("\n[bold green]المشروع جاهز.[/bold green]")

    # Agent folder security notice
    agent_config = AGENT_CONFIG.get(selected_ai)
    if agent_config:
        agent_folder = ai_commands_dir if selected_ai == "generic" else agent_config["folder"]
        if agent_folder:
            security_notice = Panel(
                f"بعض الوكلاء قد يخزّنون اعتمادات أو رموز توثيق أو معلومات خاصة أخرى داخل مجلد الوكيل في مشروعك.\n"
                f"فكّر بإضافة [cyan]{agent_folder}[/cyan] (أو أجزاء منه) إلى [cyan].gitignore[/cyan] لمنع تسرّب الاعتمادات عرضياً.",
                title="[yellow]أمان مجلد الوكيل[/yellow]",
                border_style="yellow",
                padding=(1, 2)
            )
            console.print()
            console.print(security_notice)

    if ai_deprecation_warning:
        deprecation_notice = Panel(
            ai_deprecation_warning,
            title="[bold red]تحذير الإهمال[/bold red]",
            border_style="red",
            padding=(1, 2),
        )
        console.print()
        console.print(deprecation_notice)

    if git_default_notice:
        default_change_notice = Panel(
            "امتداد git مفعّل حالياً بشكل افتراضي أثناء [bold]specify init[/bold].\n"
            "ابتداءً من [bold]v0.10.0[/bold]، سيتطلب ذلك اختيار صريح للتفعيل.\n"
            "استخدم [bold]specify extension add git[/bold] بعد التهيئة عند الحاجة.",
            title="[yellow]ملاحظة: تغيير افتراضي Git[/yellow]",
            border_style="yellow",
            padding=(1, 2),
        )
        console.print()
        console.print(default_change_notice)

    steps_lines = []
    if not here:
        steps_lines.append(f"1. انتقل إلى مجلد المشروع: [cyan]cd {project_name}[/cyan]")
        step_num = 2
    else:
        steps_lines.append("1. أنت بالفعل في مجلد المشروع!")
        step_num = 2

    # Determine skill display mode for the next-steps panel.
    # Skills integrations (codex, claude, kimi, agy, trae, cursor-agent, copilot, devin) should show skill invocation syntax.
    from .integrations.base import SkillsIntegration as _SkillsInt
    _is_skills_integration = isinstance(resolved_integration, _SkillsInt) or getattr(resolved_integration, "_skills_mode", False)

    codex_skill_mode = selected_ai == "codex" and (ai_skills or _is_skills_integration)
    claude_skill_mode = selected_ai == "claude" and (ai_skills or _is_skills_integration)
    kimi_skill_mode = selected_ai == "kimi"
    agy_skill_mode = selected_ai == "agy" and _is_skills_integration
    trae_skill_mode = selected_ai == "trae"
    cursor_agent_skill_mode = selected_ai == "cursor-agent" and (ai_skills or _is_skills_integration)
    copilot_skill_mode = selected_ai == "copilot" and _is_skills_integration
    devin_skill_mode = selected_ai == "devin"
    native_skill_mode = codex_skill_mode or claude_skill_mode or kimi_skill_mode or agy_skill_mode or trae_skill_mode or cursor_agent_skill_mode or copilot_skill_mode or devin_skill_mode

    if codex_skill_mode and not ai_skills:
        # Integration path installed skills; show the helpful notice
        steps_lines.append(f"{step_num}. ابدأ Codex في مجلد هذا المشروع؛ تم تثبيت مهارات spec-kit في [cyan].agents/skills[/cyan]")
        step_num += 1
    if claude_skill_mode and not ai_skills:
        steps_lines.append(f"{step_num}. ابدأ Claude في مجلد هذا المشروع؛ تم تثبيت مهارات spec-kit في [cyan].claude/skills[/cyan]")
        step_num += 1
    if cursor_agent_skill_mode and not ai_skills:
        steps_lines.append(f"{step_num}. ابدأ Cursor Agent في مجلد هذا المشروع؛ تم تثبيت مهارات spec-kit في [cyan].cursor/skills[/cyan]")
        step_num += 1
    if devin_skill_mode:
        steps_lines.append(f"{step_num}. ابدأ Devin في مجلد هذا المشروع؛ تم تثبيت مهارات spec-kit في [cyan].devin/skills[/cyan]")
        step_num += 1
    usage_label = "المهارات" if native_skill_mode else "أوامر السلاش"

    def _display_cmd(name: str) -> str:
        if codex_skill_mode or agy_skill_mode or trae_skill_mode:
            return f"$speckit-{name}"
        if claude_skill_mode:
            return f"/speckit-{name}"
        if kimi_skill_mode:
            return f"/skill:speckit-{name}"
        if cursor_agent_skill_mode or copilot_skill_mode or devin_skill_mode:
            return f"/speckit-{name}"
        return f"/speckit.{name}"

    steps_lines.append(f"{step_num}. ابدأ باستخدام {usage_label} مع وكيل البرمجة:")

    steps_lines.append(f"   {step_num}.1 [cyan]{_display_cmd('constitution')}[/] - تأسيس مبادئ المشروع")
    steps_lines.append(f"   {step_num}.2 [cyan]{_display_cmd('specify')}[/] - إنشاء المواصفة الأساسية")
    steps_lines.append(f"   {step_num}.3 [cyan]{_display_cmd('plan')}[/] - إنشاء خطة التنفيذ")
    steps_lines.append(f"   {step_num}.4 [cyan]{_display_cmd('tasks')}[/] - توليد مهام قابلة للتنفيذ")
    steps_lines.append(f"   {step_num}.5 [cyan]{_display_cmd('implement')}[/] - تنفيذ المهام")

    steps_panel = Panel("\n".join(steps_lines), title="الخطوات التالية", border_style="cyan", padding=(1,2))
    console.print()
    console.print(steps_panel)

    enhancement_intro = (
        "مهارات اختيارية يمكن استخدامها لمواصفاتك [bright_black](تحسّن الجودة والثقة)[/bright_black]"
        if native_skill_mode
        else "أوامر اختيارية يمكن استخدامها لمواصفاتك [bright_black](تحسّن الجودة والثقة)[/bright_black]"
    )
    enhancement_lines = [
        enhancement_intro,
        "",
        f"○ [cyan]{_display_cmd('clarify')}[/] [bright_black](اختياري)[/bright_black] - طرح أسئلة منظّمة لتقليل المخاطر في المناطق الغامضة قبل التخطيط (نفّذه قبل [cyan]{_display_cmd('plan')}[/] إن استُخدم)",
        f"○ [cyan]{_display_cmd('analyze')}[/] [bright_black](اختياري)[/bright_black] - تقرير اتساق ومحاذاة بين المخرجات (بعد [cyan]{_display_cmd('tasks')}[/]، قبل [cyan]{_display_cmd('implement')}[/])",
        f"○ [cyan]{_display_cmd('checklist')}[/] [bright_black](اختياري)[/bright_black] - توليد قوائم تحقق للجودة للتحقق من اكتمال المتطلبات ووضوحها واتساقها (بعد [cyan]{_display_cmd('plan')}[/])"
    ]
    enhancements_title = "مهارات التحسين" if native_skill_mode else "أوامر التحسين"
    enhancements_panel = Panel("\n".join(enhancement_lines), title=enhancements_title, border_style="cyan", padding=(1,2))
    console.print()
    console.print(enhancements_panel)

@app.command()
def check():
    """التحقق من تثبيت الأدوات المطلوبة."""
    show_banner()
    console.print("[bold]جاري التحقق من الأدوات المثبتة...[/bold]\n")

    tracker = StepTracker("فحص الأدوات المتاحة")

    tracker.add("git", "إدارة الإصدارات Git")
    git_ok = check_tool("git", tracker=tracker)

    agent_results = {}
    for agent_key, agent_config in AGENT_CONFIG.items():
        if agent_key == "generic":
            continue  # Generic is not a real agent to check
        agent_name = agent_config["name"]
        requires_cli = agent_config["requires_cli"]

        tracker.add(agent_key, agent_name)

        if requires_cli:
            agent_results[agent_key] = check_tool(agent_key, tracker=tracker)
        else:
            # IDE-based agent - skip CLI check and mark as optional
            tracker.skip(agent_key, "وكيل قائم على IDE، بدون فحص CLI")
            agent_results[agent_key] = False  # Don't count IDE agents as "found"

    # Check VS Code variants (not in agent config)
    tracker.add("code", "Visual Studio Code")
    check_tool("code", tracker=tracker)

    tracker.add("code-insiders", "Visual Studio Code Insiders")
    check_tool("code-insiders", tracker=tracker)

    console.print(tracker.render())

    console.print("\n[bold green]واجهة Specify CLI جاهزة للاستخدام![/bold green]")

    if not git_ok:
        console.print("[dim]نصيحة: ثبّت git لإدارة المستودع[/dim]")

    if not any(agent_results.values()):
        console.print("[dim]نصيحة: ثبّت وكيل برمجة لأفضل تجربة[/dim]")

@app.command()
def version():
    """عرض معلومات الإصدار والنظام."""
    import platform

    show_banner()

    cli_version = get_speckit_version()

    info_table = Table(show_header=False, box=None, padding=(0, 2))
    info_table.add_column("المفتاح", style="cyan", justify="right")
    info_table.add_column("القيمة", style="white")

    info_table.add_row("إصدار CLI", cli_version)
    info_table.add_row("", "")
    info_table.add_row("Python", platform.python_version())
    info_table.add_row("النظام", platform.system())
    info_table.add_row("المعمارية", platform.machine())
    info_table.add_row("إصدار النظام", platform.version())

    panel = Panel(
        info_table,
        title="[bold cyan]معلومات Specify CLI[/bold cyan]",
        border_style="cyan",
        padding=(1, 2)
    )

    console.print(panel)
    console.print()

def _get_installed_version() -> str:
    """Return the installed specify-cli distribution version or 'unknown'.

    Uses importlib.metadata so the value reflects what was actually installed
    by pip/uv/pipx — not a value read from pyproject.toml. This is
    intentional for `specify self check`, which should reason about the
    installed distribution rather than a source-tree fallback. Callers must
    treat the sentinel string 'unknown' as an indeterminate value (see FR-020).
    """

    import importlib.metadata

    metadata_errors = [importlib.metadata.PackageNotFoundError]
    invalid_metadata_error = getattr(importlib.metadata, "InvalidMetadataError", None)
    if invalid_metadata_error is not None:
        metadata_errors.append(invalid_metadata_error)

    try:
        return importlib.metadata.version("specify-cli")
    except tuple(metadata_errors):
        return "unknown"

def _normalize_tag(tag: str) -> str:
    """Strip exactly one leading 'v' from a release tag.

    Returns the rest of the string unchanged. This handles the common
    'vX.Y.Z' tag convention in this repo; it MUST NOT strip more
    aggressively (e.g., two leading 'v's keeps one).
    """
    return tag[1:] if tag.startswith("v") else tag

def _is_newer(latest: str, current: str) -> bool:
    """Return True iff `latest` is strictly greater than `current` under PEP 440.

    Returns False whenever either side is 'unknown' or fails to parse; this
    keeps the comparison indeterminate (rather than crashing or falsely
    recommending a downgrade) on edge inputs.
    """
    if latest == "unknown" or current == "unknown":
        return False
    try:
        return Version(latest) > Version(current)
    except InvalidVersion:
        return False


def _fetch_latest_release_tag() -> tuple[str | None, str | None]:
    """Return (tag, failure_category). Exactly one outbound call, 5 s timeout.

    On success: (tag_name, None).
    On a documented network/HTTP failure (added in T029/T030): (None, category).
    On anything else — including a malformed response body — the exception
    propagates; there is no catch-all (research D-006).
    """
    req = urllib.request.Request(
        GITHUB_API_LATEST,
        headers={"Accept": "application/vnd.github+json"},
    )
    token = None
    for env_var in ("GH_TOKEN", "GITHUB_TOKEN"):
        candidate = os.environ.get(env_var)
        if candidate is not None:
            candidate = candidate.strip()
            if candidate:
                token = candidate
                break
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            tag = payload.get("tag_name")
            if not isinstance(tag, str) or not tag:
                raise ValueError("GitHub API response missing valid tag_name")
            return tag, None
    except urllib.error.HTTPError as e:
        # Order matters: HTTPError is a subclass of URLError.
        if e.code == 403:
            return None, "rate limited (try setting GH_TOKEN or GITHUB_TOKEN)"
        return None, f"HTTP {e.code}"
    except (urllib.error.URLError, OSError):
        return None, "offline or timeout"


# ===== Self Commands =====
self_app = typer.Typer(
    name="self",
    help="إدارة أداة specify CLI نفسها (فحص للقراءة فقط وأمر ترقية محجوز).",
    add_completion=False,
)
app.add_typer(self_app, name="self")

@self_app.command("check")
def self_check() -> None:
    """Check whether a newer specify-cli release is available. Read-only.

    This command only checks for updates; it does not modify your installation.
    The reserved (and currently non-destructive) `specify self upgrade` command
    is the name that a future release will use for actual self-upgrade — its
    behavior is not implemented in this release and is intentionally out of
    scope here. See `specify self upgrade --help` for its current status.
    """

    installed = _get_installed_version()
    tag, failure_reason = _fetch_latest_release_tag()

    if tag is None:
        # Graceful-failure path (FR-008). `failure_reason` is one of the
        # enumerated strings produced by _fetch_latest_release_tag() — it
        # never contains a URL, headers, response body, or traceback.
        assert failure_reason is not None
        console.print(f"المثبَّت: {installed}")
        console.print(f"[yellow]تعذّر فحص آخر إصدار:[/yellow] {failure_reason}")
        return

    latest_normalized = _normalize_tag(tag)

    if installed == "unknown":
        # FR-020: surface the latest release and the recovery action even
        # when the local distribution metadata is unavailable.
        console.print("تعذّر تحديد الإصدار الحالي.")
        console.print(f"آخر إصدار: {latest_normalized}")
        console.print("\nلإعادة التثبيت:")
        console.print("  uv tool install specify-cli --force \\")
        console.print(f"    --from git+https://github.com/github/spec-kit.git@{tag}")
        return

    if _is_newer(latest_normalized, installed):
        console.print(f"[green]تحديث متوفر:[/green] {installed} → {latest_normalized}")
        console.print("\nللترقية:")
        console.print("  uv tool install specify-cli --force \\")
        console.print(f"    --from git+https://github.com/github/spec-kit.git@{tag}")
        return

    # Installed is parseable AND is >= latest → "up to date" (FR-006).
    # Also reached when the tag is unparseable (InvalidVersion) → _is_newer
    # returns False, and the up-to-date branch is the safer default per
    # FR-004 / test T016.
    console.print(f"[green]محدّث:[/green] {installed}")


@self_app.command("upgrade")
def self_upgrade() -> None:
    """Reserved command surface for self-upgrade; not implemented in this release.

    This command is a documented non-destructive stub in this release: it
    performs no outbound network request, no install-method detection, and
    invokes no installer. It prints a three-line guidance message and exits 0.
    Actual self-upgrade is planned as follow-up work.

    Use `specify self check` today to see whether a newer release is available
    and to get a copy-pasteable reinstall command.
    """
    console.print("الأمر specify self upgrade غير منفّذ بعد.")
    console.print("نفّذ 'specify self check' لمعرفة ما إذا كان هناك إصدار أحدث متاح.")
    console.print("الترقية الذاتية الفعلية مخطّط لها كعمل لاحق.")


# ===== Extension Commands =====

extension_app = typer.Typer(
    name="extension",
    help="إدارة امتدادات spec-kit",
    add_completion=False,
)
app.add_typer(extension_app, name="extension")

catalog_app = typer.Typer(
    name="catalog",
    help="إدارة كتالوجات الامتدادات",
    add_completion=False,
)
extension_app.add_typer(catalog_app, name="catalog")

preset_app = typer.Typer(
    name="preset",
    help="إدارة وصفات spec-kit",
    add_completion=False,
)
app.add_typer(preset_app, name="preset")

preset_catalog_app = typer.Typer(
    name="catalog",
    help="إدارة كتالوجات الوصفات",
    add_completion=False,
)
preset_app.add_typer(preset_catalog_app, name="catalog")


def get_speckit_version() -> str:
    """Get current spec-kit version."""
    import importlib.metadata
    try:
        return importlib.metadata.version("specify-cli")
    except Exception:
        # Fallback: try reading from pyproject.toml
        try:
            import tomllib
            pyproject_path = _repo_root() / "pyproject.toml"
            if pyproject_path.exists():
                with open(pyproject_path, "rb") as f:
                    data = tomllib.load(f)
                    return data.get("project", {}).get("version", "unknown")
        except Exception:
            # Intentionally ignore any errors while reading/parsing pyproject.toml.
            # If this lookup fails for any reason, we fall back to returning "unknown" below.
            pass
    return "unknown"


# ===== Integration Commands =====

integration_app = typer.Typer(
    name="integration",
    help="إدارة تكاملات وكلاء البرمجة",
    add_completion=False,
)
app.add_typer(integration_app, name="integration")

integration_catalog_app = typer.Typer(
    name="catalog",
    help="إدارة مصادر كتالوج التكاملات",
    add_completion=False,
)
integration_app.add_typer(integration_catalog_app, name="catalog")


def _read_integration_json(project_root: Path) -> dict[str, Any]:
    """Load ``.specify/integration.json``. Returns normalized state when present."""
    path = project_root / INTEGRATION_JSON
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        console.print(f"[red]خطأ:[/red] {path} يحتوي JSON غير صالح.")
        console.print(f"يرجى إصلاح أو حذف {INTEGRATION_JSON} والمحاولة مجدداً.")
        console.print(f"[dim]تفاصيل:[/dim] {exc}")
        raise typer.Exit(1)
    except OSError as exc:
        console.print(f"[red]خطأ:[/red] تعذّر قراءة {path}.")
        console.print(f"يرجى تصحيح صلاحيات الملف أو حذف {INTEGRATION_JSON} والمحاولة مجدداً.")
        console.print(f"[dim]تفاصيل:[/dim] {exc}")
        raise typer.Exit(1)
    if not isinstance(data, dict):
        console.print(f"[red]خطأ:[/red] {path} يجب أن يحتوي كائن JSON، تم الحصول على {type(data).__name__}.")
        console.print(f"يرجى إصلاح أو حذف {INTEGRATION_JSON} والمحاولة مجدداً.")
        raise typer.Exit(1)
    schema = data.get("integration_state_schema")
    if isinstance(schema, int) and not isinstance(schema, bool) and schema > INTEGRATION_STATE_SCHEMA:
        console.print(
            f"[red]خطأ:[/red] {path} يستخدم مخطط حالة التكامل {schema}، "
            f"لكن هذا الـ CLI يدعم فقط المخطط {INTEGRATION_STATE_SCHEMA}."
        )
        console.print("يرجى ترقية Spec Kit قبل تعديل التكاملات.")
        raise typer.Exit(1)
    return _normalize_integration_state(data)


def _write_integration_json(
    project_root: Path,
    integration_key: str | None,
    installed_integrations: list[str] | None = None,
    integration_settings: dict[str, dict[str, Any]] | None = None,
) -> None:
    """Write ``.specify/integration.json`` with legacy-compatible state."""
    _write_integration_json_file(
        project_root,
        version=get_speckit_version(),
        integration_key=integration_key,
        installed_integrations=installed_integrations,
        settings=integration_settings,
    )


def _clear_init_options_for_integration(project_root: Path, integration_key: str) -> None:
    """Clear active integration keys from init-options.json when they match."""
    opts = load_init_options(project_root)
    if opts.get("integration") == integration_key or opts.get("ai") == integration_key:
        opts.pop("integration", None)
        opts.pop("ai", None)
        opts.pop("ai_skills", None)
        opts.pop("context_file", None)
        save_init_options(project_root, opts)


def _remove_integration_json(project_root: Path) -> None:
    """Remove ``.specify/integration.json`` if it exists."""
    path = project_root / INTEGRATION_JSON
    if path.exists():
        path.unlink()


_MANIFEST_READ_ERRORS = (ValueError, FileNotFoundError, OSError, UnicodeDecodeError)


class _SharedTemplateRefreshError(RuntimeError):
    """Raised when default integration metadata should not be persisted."""


def _normalize_script_type(script_type: str, source: str) -> str:
    """Normalize and validate a script type from CLI/config sources."""
    normalized = script_type.strip().lower()
    if normalized in SCRIPT_TYPE_CHOICES:
        return normalized
    console.print(
        f"[red]خطأ:[/red] نوع سكربت غير صالح {script_type!r} من {source}. "
        f"المتوقّع أحد: {', '.join(sorted(SCRIPT_TYPE_CHOICES.keys()))}."
    )
    raise typer.Exit(1)


def _resolve_script_type(project_root: Path, script_type: str | None) -> str:
    """Resolve the script type from the CLI flag or init-options.json."""
    if script_type:
        return _normalize_script_type(script_type, "--script")
    opts = load_init_options(project_root)
    saved = opts.get("script")
    if isinstance(saved, str) and saved.strip():
        return _normalize_script_type(saved, ".specify/init-options.json")
    return "ps" if os.name == "nt" else "sh"


def _resolve_integration_script_type(
    project_root: Path,
    state: dict[str, Any],
    key: str,
    script_type: str | None = None,
) -> str:
    """Resolve script type for an integration, preferring stored settings."""
    if script_type:
        return _normalize_script_type(script_type, "--script")

    stored = _integration_setting(state, key).get("script")
    if isinstance(stored, str) and stored.strip():
        return _normalize_script_type(stored, f"{INTEGRATION_JSON} integration_settings.{key}.script")

    return _resolve_script_type(project_root, None)


def _resolve_integration_options(
    integration: Any,
    state: dict[str, Any],
    key: str,
    raw_options: str | None,
) -> tuple[str | None, dict[str, Any] | None]:
    """Resolve raw and parsed options for an integration operation."""
    return _resolve_integration_options_impl(
        integration,
        state,
        key,
        raw_options,
        parse_options=_parse_integration_options,
    )


def _set_default_integration(
    project_root: Path,
    state: dict[str, Any],
    key: str,
    integration: Any,
    installed_keys: list[str],
    *,
    script_type: str | None = None,
    raw_options: str | None = None,
    parsed_options: dict[str, Any] | None = None,
    refresh_templates: bool = True,
    refresh_templates_force: bool = False,
) -> None:
    """Persist *key* as default and align active runtime metadata."""
    resolved_script = _resolve_integration_script_type(project_root, state, key, script_type)
    settings = _with_integration_setting(
        state,
        key,
        integration,
        script_type=resolved_script,
        raw_options=raw_options,
        parsed_options=parsed_options,
    )

    if refresh_templates:
        try:
            _refresh_shared_templates(
                project_root,
                invoke_separator=_invoke_separator_for_integration(
                    integration, {"integration_settings": settings}, key, parsed_options
                ),
                force=refresh_templates_force,
            )
        except (ValueError, OSError) as exc:
            raise _SharedTemplateRefreshError(
                f"Failed to refresh shared templates for '{key}': {exc}"
            ) from exc

    _write_integration_json(project_root, key, installed_keys, settings)
    _update_init_options_for_integration(project_root, integration, script_type=resolved_script)


def _set_default_integration_or_exit(*args: Any, **kwargs: Any) -> None:
    try:
        _set_default_integration(*args, **kwargs)
    except _SharedTemplateRefreshError as exc:
        console.print(f"[red]خطأ:[/red] {exc}")
        raise typer.Exit(1)


def _display_project_path(project_root: Path, path: str | Path) -> str:
    """Return a stable POSIX-style display path for paths under a project."""
    path_obj = Path(path)
    try:
        rel_path = path_obj.relative_to(project_root) if path_obj.is_absolute() else path_obj
    except ValueError:
        try:
            rel_path = path_obj.resolve().relative_to(project_root.resolve())
        except (OSError, ValueError):
            return path_obj.as_posix()
    return rel_path.as_posix()


def _require_specify_project() -> Path:
    """Return the current project root if it is a spec-kit project, else exit."""
    project_root = Path.cwd()
    if (project_root / ".specify").is_dir():
        return project_root
    console.print("[red]خطأ:[/red] ليس مشروع spec-kit (لا يوجد مجلد .specify/)")
    console.print("نفّذ هذا الأمر من جذر مشروع spec-kit")
    raise typer.Exit(1)


@integration_app.command("list")
def integration_list(
    catalog: bool = typer.Option(False, "--catalog", help="استعراض الكتالوج الكامل (المضمّن + المجتمع)"),
):
    """عرض التكاملات المتاحة وحالة تثبيتها."""
    from .integrations import INTEGRATION_REGISTRY

    project_root = _require_specify_project()
    current = _read_integration_json(project_root)
    default_key = _default_integration_key(current)
    installed_keys = set(_installed_integration_keys(current))

    if catalog:
        from .integrations.catalog import IntegrationCatalog, IntegrationCatalogError

        ic = IntegrationCatalog(project_root)
        try:
            entries = ic.search()
        except IntegrationCatalogError as exc:
            console.print(f"[red]خطأ:[/red] {exc}")
            raise typer.Exit(1)

        if not entries:
            console.print("[yellow]لا توجد تكاملات في الكتالوج.[/yellow]")
            return

        table = Table(title="كتالوج التكاملات")
        table.add_column("المعرّف", style="cyan")
        table.add_column("الاسم")
        table.add_column("الإصدار")
        table.add_column("المصدر")
        table.add_column("الحالة")
        table.add_column("آمن للتثبيت المتعدد")

        for entry in sorted(entries, key=lambda e: e["id"]):
            eid = entry["id"]
            cat_name = entry.get("_catalog_name", "")
            install_allowed = entry.get("_install_allowed", True)
            if eid == default_key:
                status = "[green]مثبّت (افتراضي)[/green]"
            elif eid in installed_keys:
                status = "[green]مثبّت[/green]"
            elif eid in INTEGRATION_REGISTRY:
                status = "مضمّن"
            elif install_allowed is False:
                status = "للاكتشاف فقط"
            else:
                status = ""
            safe = ""
            if eid in INTEGRATION_REGISTRY:
                safe = "نعم" if getattr(INTEGRATION_REGISTRY[eid], "multi_install_safe", False) else "لا"
            table.add_row(
                eid,
                entry.get("name", eid),
                entry.get("version", ""),
                cat_name,
                status,
                safe,
            )

        console.print(table)
        return

    table = Table(title="تكاملات وكلاء البرمجة")
    table.add_column("المفتاح", style="cyan")
    table.add_column("الاسم")
    table.add_column("الحالة")
    table.add_column("CLI مطلوب")
    table.add_column("آمن للتثبيت المتعدد")

    for key in sorted(INTEGRATION_REGISTRY.keys()):
        integration = INTEGRATION_REGISTRY[key]
        cfg = integration.config or {}
        name = cfg.get("name", key)
        requires_cli = cfg.get("requires_cli", False)

        if key == default_key:
            status = "[green]مثبّت (افتراضي)[/green]"
        elif key in installed_keys:
            status = "[green]مثبّت[/green]"
        else:
            status = ""

        cli_req = "نعم" if requires_cli else "لا (IDE)"
        safe = "نعم" if getattr(integration, "multi_install_safe", False) else "لا"
        table.add_row(key, name, status, cli_req, safe)

    console.print(table)

    if installed_keys:
        console.print(f"\n[dim]التكامل الافتراضي:[/dim] [cyan]{default_key or 'لا يوجد'}[/cyan]")
        console.print(f"[dim]التكاملات المثبّتة:[/dim] [cyan]{', '.join(sorted(installed_keys))}[/cyan]")
    else:
        console.print("\n[yellow]لا يوجد تكامل مثبّت حالياً.[/yellow]")
        console.print("ثبّت واحداً بـ: [cyan]specify integration install <key>[/cyan]")


@integration_app.command("install")
def integration_install(
    key: str = typer.Argument(help="مفتاح التكامل المراد تثبيته (مثال: claude, copilot)"),
    script: str | None = typer.Option(None, "--script", help="نوع السكربت: sh أو ps (الافتراضي: من init-options.json أو الافتراضي للنظام)"),
    force: bool = typer.Option(False, "--force", help="السماح بالتثبيت المتعدد عند عدم تأكيد أمان التكاملات"),
    integration_options: str | None = typer.Option(None, "--integration-options", help='خيارات التكامل (مثال: --integration-options="--commands-dir .myagent/cmds")'),
):
    """تثبيت تكامل داخل مشروع موجود."""
    from .integrations import INTEGRATION_REGISTRY, get_integration
    from .integrations.manifest import IntegrationManifest

    project_root = _require_specify_project()
    integration = get_integration(key)
    if integration is None:
        console.print(f"[red]خطأ:[/red] تكامل غير معروف '{key}'")
        available = ", ".join(sorted(INTEGRATION_REGISTRY.keys()))
        console.print(f"التكاملات المتاحة: {available}")
        raise typer.Exit(1)

    current = _read_integration_json(project_root)
    default_key = _default_integration_key(current)
    installed_keys = _installed_integration_keys(current)

    if key in installed_keys:
        console.print(f"[yellow]التكامل '{key}' مثبّت مسبقاً.[/yellow]")
        console.print(
            f"نفّذ [cyan]specify integration upgrade {key}[/cyan] لإعادة تثبيت الملفات المُدارة، "
            f"أو [cyan]specify integration uninstall {key}[/cyan] أولاً."
        )
        raise typer.Exit(0)

    if installed_keys and not force:
        unsafe_keys = []
        for installed_key in installed_keys:
            installed_integration = get_integration(installed_key)
            if not installed_integration or not getattr(installed_integration, "multi_install_safe", False):
                unsafe_keys.append(installed_key)
        if unsafe_keys or not getattr(integration, "multi_install_safe", False):
            console.print(
                f"[red]خطأ:[/red] التكاملات المثبّتة: {', '.join(installed_keys)}."
            )
            if default_key:
                console.print(f"التكامل الافتراضي: [cyan]{default_key}[/cyan].")
            console.print(
                "تثبيت تكاملات متعددة يتم تلقائياً فقط عندما تكون جميع التكاملات المعنية "
                "مُعلنة آمنة للتثبيت المتعدد."
            )
            console.print(
                f"نفّذ [cyan]specify integration switch {key}[/cyan] لاستبدال التكامل الافتراضي، "
                f"أو أعد المحاولة مع [cyan]--force[/cyan] للموافقة."
            )
            raise typer.Exit(1)

    selected_script = _resolve_script_type(project_root, script)

    # Build parsed options from --integration-options so the integration
    # can determine its effective invoke separator before shared infra
    # is installed.
    raw_options, parsed_options = _resolve_integration_options(
        integration, current, key, integration_options
    )

    # Ensure shared infrastructure is present (safe to run unconditionally;
    # _install_shared_infra merges missing files without overwriting).
    infra_integration = integration
    infra_key = key
    infra_parsed = parsed_options
    if default_key:
        default_integration = get_integration(default_key)
        if default_integration is not None:
            infra_integration = default_integration
            infra_key = default_key
            _, infra_parsed = _resolve_integration_options(
                default_integration, current, default_key, None
            )
    _install_shared_infra_or_exit(
        project_root,
        selected_script,
        invoke_separator=_invoke_separator_for_integration(
            infra_integration, current, infra_key, infra_parsed
        ),
    )
    if os.name != "nt":
        ensure_executable_scripts(project_root)

    manifest = IntegrationManifest(
        integration.key, project_root, version=get_speckit_version()
    )

    try:
        integration.setup(
            project_root, manifest,
            parsed_options=parsed_options,
            script_type=selected_script,
            raw_options=raw_options,
        )
        manifest.save()
        new_installed = _dedupe_integration_keys([*installed_keys, integration.key])
        new_default = default_key or integration.key
        settings = _with_integration_setting(
            current,
            integration.key,
            integration,
            script_type=selected_script,
            raw_options=raw_options,
            parsed_options=parsed_options,
        )
        _write_integration_json(project_root, new_default, new_installed, settings)
        if new_default == integration.key:
            _update_init_options_for_integration(project_root, integration, script_type=selected_script)

    except Exception as e:
        # Attempt rollback of any files written by setup
        try:
            integration.teardown(project_root, manifest, force=True)
        except Exception as rollback_err:
            # Suppress so the original setup error remains the primary failure
            console.print(f"[yellow]تحذير:[/yellow] فشل التراجع عن تغييرات التكامل: {rollback_err}")
        if installed_keys:
            _write_integration_json(
                project_root, default_key, installed_keys, _integration_settings(current)
            )
        else:
            _remove_integration_json(project_root)
        console.print(f"[red]خطأ:[/red] فشل تثبيت التكامل: {e}")
        raise typer.Exit(1)

    name = (integration.config or {}).get("name", key)
    console.print(f"\n[green]✓[/green] تم تثبيت التكامل '{name}' بنجاح")
    if default_key:
        console.print(f"[dim]التكامل الافتراضي لا يزال:[/dim] [cyan]{default_key}[/cyan]")


def _parse_integration_options(integration: Any, raw_options: str) -> dict[str, Any] | None:
    """Parse --integration-options string into a dict matching the integration's declared options.

    Returns ``None`` when no options are provided.
    """
    import shlex
    parsed: dict[str, Any] = {}
    tokens = shlex.split(raw_options)
    declared_options = list(integration.options())
    declared = {opt.name.lstrip("-"): opt for opt in declared_options}
    allowed = ", ".join(sorted(opt.name for opt in declared_options))
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if not token.startswith("-"):
            console.print(f"[red]خطأ:[/red] قيمة خيار تكامل غير متوقعة '{token}'.")
            if allowed:
                console.print(f"الخيارات المسموحة: {allowed}")
            raise typer.Exit(1)
        name = token.lstrip("-")
        value: str | None = None
        # Handle --name=value syntax
        if "=" in name:
            name, value = name.split("=", 1)
        opt = declared.get(name)
        if not opt:
            console.print(f"[red]خطأ:[/red] خيار تكامل غير معروف '{token}'.")
            if allowed:
                console.print(f"الخيارات المسموحة: {allowed}")
            raise typer.Exit(1)
        key = name.replace("-", "_")
        if opt.is_flag:
            if value is not None:
                console.print(f"[red]خطأ:[/red] الخيار '{opt.name}' علم ولا يقبل قيمة.")
                raise typer.Exit(1)
            parsed[key] = True
            i += 1
        elif value is not None:
            parsed[key] = value
            i += 1
        elif i + 1 < len(tokens) and not tokens[i + 1].startswith("-"):
            parsed[key] = tokens[i + 1]
            i += 2
        else:
            console.print(f"[red]خطأ:[/red] الخيار '{opt.name}' يتطلب قيمة.")
            raise typer.Exit(1)
    return parsed or None


def _update_init_options_for_integration(
    project_root: Path,
    integration: Any,
    script_type: str | None = None,
) -> None:
    """Update ``init-options.json`` to reflect *integration* as the active one."""
    from .integrations.base import SkillsIntegration
    opts = load_init_options(project_root)
    opts["integration"] = integration.key
    opts["ai"] = integration.key
    opts["context_file"] = integration.context_file
    if script_type:
        opts["script"] = script_type
    if isinstance(integration, SkillsIntegration) or getattr(integration, "_skills_mode", False):
        opts["ai_skills"] = True
    else:
        opts.pop("ai_skills", None)
    save_init_options(project_root, opts)


@integration_app.command("use")
def integration_use(
    key: str = typer.Argument(help="مفتاح التكامل المثبّت لجعله الافتراضي"),
    force: bool = typer.Option(False, "--force", help="استبدال القوالب المشتركة المُدارة أثناء تغيير الافتراضي"),
):
    """تعيين التكامل الافتراضي دون إلغاء تثبيت التكاملات الأخرى."""
    from .integrations import get_integration

    project_root = _require_specify_project()
    current = _read_integration_json(project_root)
    installed_keys = _installed_integration_keys(current)
    if key not in installed_keys:
        console.print(f"[red]خطأ:[/red] التكامل '{key}' غير مثبّت.")
        if installed_keys:
            console.print(f"[yellow]التكاملات المثبّتة:[/yellow] {', '.join(installed_keys)}")
        else:
            console.print("ثبّت واحداً بـ: [cyan]specify integration install <key>[/cyan]")
        raise typer.Exit(1)

    integration = get_integration(key)
    if integration is None:
        console.print(f"[red]خطأ:[/red] تكامل غير معروف '{key}'")
        raise typer.Exit(1)

    raw_options, parsed_options = _resolve_integration_options(integration, current, key, None)
    _set_default_integration_or_exit(
        project_root,
        current,
        key,
        integration,
        installed_keys,
        raw_options=raw_options,
        parsed_options=parsed_options,
        refresh_templates_force=force,
    )
    console.print(f"[green]✓[/green] تم تعيين التكامل الافتراضي إلى [bold]{key}[/bold].")


@integration_app.command("uninstall")
def integration_uninstall(
    key: str = typer.Argument(None, help="مفتاح التكامل المراد إلغاء تثبيته (افتراضياً: التكامل الحالي)"),
    force: bool = typer.Option(False, "--force", help="إزالة الملفات حتى لو كانت معدّلة"),
):
    """إلغاء تثبيت تكامل مع الحفاظ على الملفات المعدّلة بأمان."""
    from .integrations import get_integration
    from .integrations.manifest import IntegrationManifest

    project_root = _require_specify_project()
    current = _read_integration_json(project_root)
    default_key = _default_integration_key(current)
    installed_keys = _installed_integration_keys(current)

    if key is None:
        if not default_key:
            console.print("[yellow]لا يوجد تكامل مثبّت حالياً.[/yellow]")
            raise typer.Exit(0)
        key = default_key

    if key not in installed_keys:
        console.print(f"[red]خطأ:[/red] التكامل '{key}' غير مثبّت.")
        raise typer.Exit(1)

    integration = get_integration(key)

    manifest_path = project_root / ".specify" / "integrations" / f"{key}.manifest.json"
    if not manifest_path.exists():
        console.print(f"[yellow]لم يُعثر على بيان (manifest) للتكامل '{key}'. لا شيء لإلغاء تثبيته.[/yellow]")
        remaining = [installed for installed in installed_keys if installed != key]
        new_default = default_key if default_key != key else (remaining[0] if remaining else None)
        if remaining:
            if default_key == key and new_default and (new_integration := get_integration(new_default)):
                raw_options, parsed_options = _resolve_integration_options(
                    new_integration, current, new_default, None
                )
                _set_default_integration_or_exit(
                    project_root,
                    current,
                    new_default,
                    new_integration,
                    remaining,
                    raw_options=raw_options,
                    parsed_options=parsed_options,
                )
            else:
                _write_integration_json(
                    project_root, new_default, remaining, _integration_settings(current)
                )
        else:
            _remove_integration_json(project_root)
        if default_key == key:
            _clear_init_options_for_integration(project_root, key)
        raise typer.Exit(0)

    try:
        manifest = IntegrationManifest.load(key, project_root)
    except _MANIFEST_READ_ERRORS as exc:
        console.print(f"[red]خطأ:[/red] بيان التكامل (manifest) لـ '{key}' غير قابل للقراءة.")
        console.print(f"البيان: {manifest_path}")
        console.print(
            f"للتعافي، احذف البيان غير القابل للقراءة، نفّذ "
            f"[cyan]specify integration uninstall {key}[/cyan] لمسح البيانات الوصفية القديمة، "
            f"ثم نفّذ [cyan]specify integration install {key}[/cyan] لإعادة التوليد."
        )
        console.print(f"[dim]تفاصيل:[/dim] {exc}")
        raise typer.Exit(1)

    removed, skipped = manifest.uninstall(project_root, force=force)

    # Remove managed context section from the agent context file
    if integration:
        integration.remove_context_section(project_root)

    remaining = [installed for installed in installed_keys if installed != key]
    new_default = default_key if default_key != key else (remaining[0] if remaining else None)
    if remaining:
        if default_key == key and new_default and (new_integration := get_integration(new_default)):
            raw_options, parsed_options = _resolve_integration_options(
                new_integration, current, new_default, None
            )
            _set_default_integration_or_exit(
                project_root,
                current,
                new_default,
                new_integration,
                remaining,
                raw_options=raw_options,
                parsed_options=parsed_options,
            )
        else:
            _write_integration_json(
                project_root, new_default, remaining, _integration_settings(current)
            )
    else:
        _remove_integration_json(project_root)

    if default_key == key:
        _clear_init_options_for_integration(project_root, key)

    name = (integration.config or {}).get("name", key) if integration else key
    console.print(f"\n[green]✓[/green] تم إلغاء تثبيت التكامل '{name}'")
    if removed:
        console.print(f"  تم حذف {len(removed)} ملف/ملفات")
    if skipped:
        console.print(f"\n[yellow]⚠[/yellow]  تم الاحتفاظ بـ {len(skipped)} ملف/ملفات معدّلة:")
        for path in skipped:
            rel = _display_project_path(project_root, path)
            console.print(f"    {rel}")


@integration_app.command("switch")
def integration_switch(
    target: str = typer.Argument(help="مفتاح التكامل المراد التبديل إليه"),
    script: str | None = typer.Option(None, "--script", help="نوع السكربت: sh أو ps (الافتراضي: من init-options.json أو الافتراضي للنظام)"),
    force: bool = typer.Option(False, "--force", help="فرض إزالة الملفات المعدّلة أثناء إلغاء التثبيت"),
    integration_options: str | None = typer.Option(None, "--integration-options", help='خيارات للتكامل الهدف'),
):
    """التبديل من التكامل الحالي إلى تكامل آخر."""
    from .integrations import INTEGRATION_REGISTRY, get_integration
    from .integrations.manifest import IntegrationManifest

    project_root = _require_specify_project()
    target_integration = get_integration(target)
    if target_integration is None:
        console.print(f"[red]خطأ:[/red] تكامل غير معروف '{target}'")
        available = ", ".join(sorted(INTEGRATION_REGISTRY.keys()))
        console.print(f"التكاملات المتاحة: {available}")
        raise typer.Exit(1)

    current = _read_integration_json(project_root)
    installed_keys = _installed_integration_keys(current)
    installed_key = _default_integration_key(current)

    if installed_key == target:
        if integration_options is not None:
            console.print(
                "[red]خطأ:[/red] لا يمكن استخدام --integration-options عند التبديل "
                "إلى تكامل مثبّت مسبقاً."
            )
            console.print(
                f"نفّذ [cyan]specify integration upgrade {target} --integration-options ...[/cyan] "
                "لتحديث الملفات/الخيارات المُدارة."
            )
            raise typer.Exit(1)
        if force:
            raw_options, parsed_options = _resolve_integration_options(
                target_integration, current, target, None
            )
            _set_default_integration_or_exit(
                project_root,
                current,
                target,
                target_integration,
                installed_keys,
                raw_options=raw_options,
                parsed_options=parsed_options,
                refresh_templates_force=True,
            )
            console.print(
                f"\n[green]✓[/green] التكامل الافتراضي لا يزال [bold]{target}[/bold]؛ "
                "تم تحديث القوالب المشتركة المُدارة."
            )
            raise typer.Exit(0)
        console.print(f"[yellow]التكامل '{target}' هو التكامل الافتراضي بالفعل. لا شيء للتبديل.[/yellow]")
        raise typer.Exit(0)

    if target in installed_keys:
        if integration_options is not None:
            console.print(
                "[red]خطأ:[/red] لا يمكن استخدام --integration-options عند التبديل "
                "إلى تكامل مثبّت مسبقاً."
            )
            console.print(
                f"نفّذ [cyan]specify integration upgrade {target} --integration-options ...[/cyan] "
                f"لتحديث الملفات/الخيارات المُدارة، ثم [cyan]specify integration use {target}[/cyan]."
            )
            raise typer.Exit(1)
        raw_options, parsed_options = _resolve_integration_options(
            target_integration, current, target, None
        )
        _set_default_integration_or_exit(
            project_root,
            current,
            target,
            target_integration,
            installed_keys,
            raw_options=raw_options,
            parsed_options=parsed_options,
            refresh_templates_force=force,
        )
        console.print(f"\n[green]✓[/green] تم تعيين التكامل الافتراضي إلى [bold]{target}[/bold].")
        raise typer.Exit(0)

    selected_script = _resolve_script_type(project_root, script)

    # Phase 1: Uninstall current integration (if any)
    if installed_key:
        current_integration = get_integration(installed_key)
        manifest_path = project_root / ".specify" / "integrations" / f"{installed_key}.manifest.json"

        if current_integration and manifest_path.exists():
            console.print(f"إلغاء تثبيت التكامل الحالي: [cyan]{installed_key}[/cyan]")
            try:
                old_manifest = IntegrationManifest.load(installed_key, project_root)
            except _MANIFEST_READ_ERRORS as exc:
                console.print(f"[red]خطأ:[/red] تعذّر قراءة بيان التكامل لـ '{installed_key}': {manifest_path}")
                console.print(f"[dim]{exc}[/dim]")
                console.print(
                    f"للتعافي، احذف البيان غير القابل للقراءة في {manifest_path}، "
                    f"نفّذ [cyan]specify integration uninstall {installed_key}[/cyan]، ثم أعد المحاولة."
                )
                raise typer.Exit(1)
            removed, skipped = old_manifest.uninstall(project_root, force=force)
            current_integration.remove_context_section(project_root)
            if removed:
                console.print(f"  تم حذف {len(removed)} ملف/ملفات")
            if skipped:
                console.print(f"  [yellow]⚠[/yellow]  تم الاحتفاظ بـ {len(skipped)} ملف/ملفات معدّلة")
        elif not current_integration and manifest_path.exists():
            # Integration removed from registry but manifest exists — use manifest-only uninstall
            console.print(f"إلغاء تثبيت تكامل غير معروف '{installed_key}' عبر البيان")
            try:
                old_manifest = IntegrationManifest.load(installed_key, project_root)
                removed, skipped = old_manifest.uninstall(project_root, force=force)
                if removed:
                    console.print(f"  تم حذف {len(removed)} ملف/ملفات")
                if skipped:
                    console.print(f"  [yellow]⚠[/yellow]  تم الاحتفاظ بـ {len(skipped)} ملف/ملفات معدّلة")
            except _MANIFEST_READ_ERRORS as exc:
                console.print(f"[yellow]تحذير:[/yellow] تعذّر قراءة البيان لـ '{installed_key}': {exc}")
        else:
            console.print(f"[red]خطأ:[/red] التكامل '{installed_key}' مثبّت لكن ليس له بيان.")
            console.print(
                f"نفّذ [cyan]specify integration uninstall {installed_key}[/cyan] لمسح البيانات الوصفية، "
                f"ثم أعد المحاولة [cyan]specify integration switch {target}[/cyan]."
            )
            raise typer.Exit(1)

        # Unregister extension commands for the old agent so they don't
        # remain as orphans in the old agent's directory.
        try:
            from .extensions import ExtensionManager

            ext_mgr = ExtensionManager(project_root)
            ext_mgr.unregister_agent_artifacts(installed_key)
        except Exception as ext_err:
            console.print(
                f"[yellow]تحذير:[/yellow] تعذّر تنظيف مخرجات الامتداد "
                f"(الأوامر، المهارات، إدخالات السجل) لـ '{installed_key}': {ext_err}"
            )

        # Clear metadata so a failed Phase 2 doesn't leave stale references
        installed_keys = [installed for installed in installed_keys if installed != installed_key]
        _clear_init_options_for_integration(project_root, installed_key)
        if installed_keys:
            fallback_key = installed_keys[0]
            fallback_integration = get_integration(fallback_key)
            if fallback_integration is not None:
                raw_options, parsed_options = _resolve_integration_options(
                    fallback_integration, current, fallback_key, None
                )
                _set_default_integration_or_exit(
                    project_root,
                    current,
                    fallback_key,
                    fallback_integration,
                    installed_keys,
                    raw_options=raw_options,
                    parsed_options=parsed_options,
                )
            else:
                _write_integration_json(
                    project_root, fallback_key, installed_keys, _integration_settings(current)
                )
        else:
            _remove_integration_json(project_root)
        current = _read_integration_json(project_root)

    # Build parsed options from --integration-options so the integration
    # can determine its effective invoke separator before shared infra
    # is installed.
    raw_options, parsed_options = _resolve_integration_options(
        target_integration, current, target, integration_options
    )

    # Ensure shared infrastructure is present (safe to run unconditionally;
    # _install_shared_infra merges missing files without overwriting).
    _install_shared_infra_or_exit(
        project_root,
        selected_script,
        invoke_separator=_invoke_separator_for_integration(
            target_integration, current, target, parsed_options
        ),
    )
    if os.name != "nt":
        ensure_executable_scripts(project_root)

    # Phase 2: Install target integration
    console.print(f"تثبيت التكامل: [cyan]{target}[/cyan]")
    manifest = IntegrationManifest(
        target_integration.key, project_root, version=get_speckit_version()
    )

    try:
        target_integration.setup(
            project_root, manifest,
            parsed_options=parsed_options,
            script_type=selected_script,
            raw_options=raw_options,
        )
        manifest.save()
        _set_default_integration(
            project_root,
            current,
            target_integration.key,
            target_integration,
            _dedupe_integration_keys([*installed_keys, target_integration.key]),
            script_type=selected_script,
            raw_options=raw_options,
            parsed_options=parsed_options,
        )

        # Re-register extension commands for the new agent so that
        # previously-installed extensions are available in the new integration.
        try:
            from .extensions import ExtensionManager

            ext_mgr = ExtensionManager(project_root)
            ext_mgr.register_enabled_extensions_for_agent(target)
        except Exception as ext_err:
            console.print(
                f"[yellow]تحذير:[/yellow] تعذّر تسجيل أوامر الامتداد، المهارات، "
                f"أو المخرجات المتعلقة لـ '{target}': {ext_err}"
            )

    except Exception as e:
        # Attempt rollback of any files written by setup
        try:
            target_integration.teardown(project_root, manifest, force=True)
        except Exception as rollback_err:
            # Suppress so the original setup error remains the primary failure
            console.print(f"[yellow]تحذير:[/yellow] فشل التراجع عن التكامل '{target}': {rollback_err}")
        if installed_keys:
            fallback_key = installed_keys[0]
            fallback_integration = get_integration(fallback_key)
            if fallback_integration is not None:
                raw_options, parsed_options = _resolve_integration_options(
                    fallback_integration, current, fallback_key, None
                )
                try:
                    _set_default_integration(
                        project_root,
                        current,
                        fallback_key,
                        fallback_integration,
                        installed_keys,
                        raw_options=raw_options,
                        parsed_options=parsed_options,
                    )
                except _SharedTemplateRefreshError as restore_err:
                    console.print(
                        f"[yellow]تحذير:[/yellow] فشل استعادة التكامل الافتراضي "
                        f"'{fallback_key}': {restore_err}"
                    )
            else:
                _write_integration_json(
                    project_root, fallback_key, installed_keys, _integration_settings(current)
                )
        else:
            _remove_integration_json(project_root)
        console.print(f"[red]خطأ:[/red] فشل تثبيت التكامل '{target}': {e}")
        raise typer.Exit(1)

    name = (target_integration.config or {}).get("name", target)
    console.print(f"\n[green]✓[/green] تم التبديل إلى التكامل '{name}'")


@integration_app.command("upgrade")
def integration_upgrade(
    key: str | None = typer.Argument(None, help="مفتاح التكامل المراد ترقيته (الافتراضي: التكامل الحالي)"),
    force: bool = typer.Option(False, "--force", help="فرض الترقية حتى لو كانت الملفات معدّلة"),
    script: str | None = typer.Option(None, "--script", help="نوع السكربت: sh أو ps (الافتراضي: من init-options.json أو الافتراضي للنظام)"),
    integration_options: str | None = typer.Option(None, "--integration-options", help="خيارات التكامل"),
):
    """ترقية تكامل بإعادة التثبيت مع معالجة ملفات مدركة للفروقات.

    تقارن تجزئات البيان لاكتشاف الملفات المعدّلة محلياً وتحجب
    الترقية إلا إذا استُخدم --force.
    """
    from .integrations import get_integration
    from .integrations.manifest import IntegrationManifest

    project_root = _require_specify_project()
    current = _read_integration_json(project_root)
    installed_key = _default_integration_key(current)
    installed_keys = _installed_integration_keys(current)

    if key is None:
        if not installed_key:
            console.print("[yellow]لا يوجد تكامل مثبّت حالياً.[/yellow]")
            raise typer.Exit(0)
        key = installed_key

    if key not in installed_keys:
        console.print(f"[red]خطأ:[/red] التكامل '{key}' غير مثبّت.")
        raise typer.Exit(1)

    integration = get_integration(key)
    if integration is None:
        console.print(f"[red]خطأ:[/red] تكامل غير معروف '{key}'")
        raise typer.Exit(1)

    manifest_path = project_root / ".specify" / "integrations" / f"{key}.manifest.json"
    if not manifest_path.exists():
        console.print(f"[yellow]لم يُعثر على بيان للتكامل '{key}'. لا شيء للترقية.[/yellow]")
        console.print(f"نفّذ [cyan]specify integration install {key}[/cyan] لإجراء تثبيت جديد.")
        raise typer.Exit(0)

    try:
        old_manifest = IntegrationManifest.load(key, project_root)
    except _MANIFEST_READ_ERRORS as exc:
        console.print(f"[red]خطأ:[/red] بيان التكامل لـ '{key}' غير قابل للقراءة: {exc}")
        raise typer.Exit(1)

    # Detect modified files via manifest hashes
    modified = old_manifest.check_modified()
    if modified and not force:
        console.print(f"[yellow]⚠[/yellow]  {len(modified)} ملف/ملفات تم تعديلها منذ التثبيت:")
        for rel in modified:
            console.print(f"    {rel}")
        console.print("\nاستخدم [cyan]--force[/cyan] للاستبدال، أو حلّ الأمر يدوياً.")
        raise typer.Exit(1)

    selected_script = _resolve_integration_script_type(project_root, current, key, script)

    # Build parsed options from --integration-options so the integration
    # can determine its effective invoke separator before shared infra
    # is installed.
    raw_options, parsed_options = _resolve_integration_options(
        integration, current, key, integration_options
    )

    # Ensure shared infrastructure is up to date; --force overwrites existing files.
    infra_integration = integration
    infra_key = key
    infra_parsed = parsed_options
    if installed_key and installed_key != key:
        default_integration = get_integration(installed_key)
        if default_integration is not None:
            infra_integration = default_integration
            infra_key = installed_key
            _, infra_parsed = _resolve_integration_options(
                default_integration, current, installed_key, None
            )
    _install_shared_infra_or_exit(
        project_root,
        selected_script,
        force=force,
        invoke_separator=_invoke_separator_for_integration(
            infra_integration, current, infra_key, infra_parsed
        ),
    )
    if os.name != "nt":
        ensure_executable_scripts(project_root)

    # Phase 1: Install new files (overwrites existing; old-only files remain)
    console.print(f"ترقية التكامل: [cyan]{key}[/cyan]")
    new_manifest = IntegrationManifest(key, project_root, version=get_speckit_version())

    try:
        integration.setup(
            project_root,
            new_manifest,
            parsed_options=parsed_options,
            script_type=selected_script,
            raw_options=raw_options,
        )
        settings = _with_integration_setting(
            current,
            key,
            integration,
            script_type=selected_script,
            raw_options=raw_options,
            parsed_options=parsed_options,
        )
        if installed_key == key:
            try:
                _refresh_shared_templates(
                    project_root,
                    invoke_separator=_invoke_separator_for_integration(
                        integration, {"integration_settings": settings}, key, parsed_options
                    ),
                    force=force,
                )
            except (ValueError, OSError) as exc:
                raise _SharedTemplateRefreshError(
                    f"Failed to refresh shared templates for '{key}': {exc}"
                ) from exc
        new_manifest.save()
        _write_integration_json(project_root, installed_key, installed_keys, settings)
        if installed_key == key:
            _update_init_options_for_integration(project_root, integration, script_type=selected_script)
    except Exception as exc:
        # Don't teardown — setup overwrites in-place, so teardown would
        # delete files that were working before the upgrade.  Just report.
        console.print(f"[red]خطأ:[/red] فشل ترقية التكامل: {exc}")
        console.print("[yellow]ملفات التكامل السابق قد تظل في مكانها.[/yellow]")
        raise typer.Exit(1)

    # Phase 2: Remove stale files from old manifest that are not in the new one
    old_files = old_manifest.files
    new_files = new_manifest.files
    stale_keys = set(old_files) - set(new_files)
    if stale_keys:
        stale_manifest = IntegrationManifest(key, project_root, version="stale-cleanup")
        stale_manifest._files = {k: old_files[k] for k in stale_keys}
        stale_removed, _ = stale_manifest.uninstall(project_root, force=True)
        if stale_removed:
            console.print(f"  تم حذف {len(stale_removed)} ملف/ملفات قديمة من التثبيت السابق")

    name = (integration.config or {}).get("name", key)
    console.print(f"\n[green]✓[/green] تمت ترقية التكامل '{name}' بنجاح")


# ===== Integration catalog discovery commands =====
#
# These commands mirror the workflow catalog CLI shape:
#   - `search` / `info` for discovery over the active catalog stack
#   - `catalog list/add/remove` for managing catalog sources
#
# They deliberately do NOT add `integration add/remove/enable/disable/
# set-priority`: integrations are single-active (install / uninstall / switch),
# not additive like extensions and presets.


@integration_app.command("search")
def integration_search(
    query: Optional[str] = typer.Argument(None, help="استعلام البحث (اختياري)"),
    tag: Optional[str] = typer.Option(None, "--tag", help="التصفية حسب الوسم"),
    author: Optional[str] = typer.Option(None, "--author", help="التصفية حسب المؤلف"),
):
    """البحث عن تكاملات في كومة الكتالوج النشطة."""
    from .integrations import INTEGRATION_REGISTRY
    from .integrations.catalog import (
        IntegrationCatalog,
        IntegrationCatalogError,
        IntegrationValidationError,
    )

    project_root = _require_specify_project()
    integration_config = _read_integration_json(project_root)
    installed_key = integration_config.get("integration")
    catalog = IntegrationCatalog(project_root)

    try:
        results = catalog.search(query=query, tag=tag, author=author)
    except IntegrationValidationError as exc:
        console.print(f"[red]خطأ:[/red] {exc}")
        console.print(
            "\nتلميح: تحقق من مسار ملف الإعداد الظاهر أعلاه لاكتشاف إعداد كتالوج غير صالح "
            "(مثل .specify/integration-catalogs.yml أو ~/.specify/integration-catalogs.yml)."
        )
        raise typer.Exit(1)
    except IntegrationCatalogError as exc:
        console.print(f"[red]خطأ:[/red] {exc}")
        if os.environ.get("SPECKIT_INTEGRATION_CATALOG_URL", "").strip():
            console.print(
                "\nتلميح: تحقق من متغير البيئة SPECKIT_INTEGRATION_CATALOG_URL لاحتمال أن يحتوي على رابط "
                "كتالوج غير صالح، أو ألغِ تعيينه لاستخدام ملفات الكتالوج المُعدّة "
                "(.specify/integration-catalogs.yml أو ~/.specify/integration-catalogs.yml)."
            )
        else:
            console.print("\nتلميح: الكتالوج قد يكون غير متاح مؤقتاً. حاول لاحقاً.")
        raise typer.Exit(1)

    if not results:
        console.print("\n[yellow]لم يُعثر على تكاملات تطابق المعايير[/yellow]")
        if query or tag or author:
            console.print("\nجرّب:")
            console.print("  • مصطلحات بحث أوسع")
            console.print("  • إزالة المرشّحات")
            console.print("  • specify integration search (عرض الكل)")
        return

    console.print(f"\n[green]تم العثور على {len(results)} تكامل/تكاملات:[/green]\n")
    for integ in sorted(results, key=lambda e: e.get("id", "")):
        iid = integ.get("id", "?")
        name = integ.get("name", iid)
        version = integ.get("version", "?")
        console.print(f"[bold]{name}[/bold] ({iid}) v{version}")
        desc = integ.get("description", "")
        if desc:
            console.print(f"  {desc}")

        console.print(f"\n  [dim]المؤلف:[/dim] {integ.get('author', 'غير معروف')}")
        tags = integ.get("tags", [])
        if isinstance(tags, list) and tags:
            console.print(f"  [dim]الوسوم:[/dim] {', '.join(str(t) for t in tags)}")

        cat_name = integ.get("_catalog_name", "")
        install_allowed = integ.get("_install_allowed", True)
        if cat_name:
            if install_allowed:
                console.print(f"  [dim]الكتالوج:[/dim] {cat_name}")
            else:
                console.print(
                    f"  [dim]الكتالوج:[/dim] {cat_name} "
                    "[yellow](للاكتشاف فقط — غير قابل للتثبيت)[/yellow]"
                )

        if iid == installed_key:
            console.print("\n  [green]✓ مثبّت[/green] (نشط حالياً)")
        elif iid in INTEGRATION_REGISTRY:
            console.print(f"\n  [cyan]التثبيت:[/cyan] specify integration install {iid}")
        elif install_allowed:
            console.print(
                "\n  [yellow]تم العثور في الكتالوج.[/yellow] فقط معرّفات التكاملات المضمّنة "
                "يمكن تثبيتها بـ 'specify integration install'."
            )
        else:
            console.print(
                f"\n  [yellow]⚠[/yellow]  غير قابل للتثبيت المباشر من '{cat_name}'."
            )
        console.print()


@integration_app.command("info")
def integration_info(
    integration_id: str = typer.Argument(..., help="معرّف التكامل"),
):
    """عرض تفاصيل الكتالوج لتكامل واحد."""
    from .integrations import INTEGRATION_REGISTRY
    from .integrations.catalog import (
        IntegrationCatalog,
        IntegrationCatalogError,
        IntegrationValidationError,
    )

    project_root = _require_specify_project()
    catalog = IntegrationCatalog(project_root)
    installed_key = _read_integration_json(project_root).get("integration")

    try:
        info = catalog.get_integration_info(integration_id)
    except IntegrationCatalogError as exc:
        info = None
        # Keep the live exception so the fallback branch below can give
        # different guidance for local-config vs. network failures.
        catalog_error: Optional[IntegrationCatalogError] = exc
    else:
        catalog_error = None

    if info:
        name = info.get("name", integration_id)
        version = info.get("version", "?")
        console.print(f"\n[bold cyan]{name}[/bold cyan] ({integration_id}) v{version}")
        if info.get("description"):
            console.print(f"  {info['description']}")
        console.print()

        console.print(f"  [dim]المؤلف:[/dim] {info.get('author', 'غير معروف')}")
        if info.get("license"):
            console.print(f"  [dim]الرخصة:[/dim] {info['license']}")

        tags = info.get("tags", [])
        if isinstance(tags, list) and tags:
            console.print(f"  [dim]الوسوم:[/dim] {', '.join(str(t) for t in tags)}")

        cat_name = info.get("_catalog_name", "")
        install_allowed = info.get("_install_allowed", True)
        if cat_name:
            install_note = "" if install_allowed else " [yellow](للاكتشاف فقط)[/yellow]"
            console.print(f"  [dim]كتالوج المصدر:[/dim] {cat_name}{install_note}")

        if info.get("repository"):
            console.print(f"  [dim]المستودع:[/dim] {info['repository']}")

        if integration_id == installed_key:
            console.print("\n  [green]✓ مثبّت[/green] (نشط حالياً)")
        elif integration_id in INTEGRATION_REGISTRY:
            console.print("\n  [dim]تكامل مضمّن (غير نشط حالياً)[/dim]")
        return

    if integration_id in INTEGRATION_REGISTRY:
        integration = INTEGRATION_REGISTRY[integration_id]
        cfg = integration.config or {}
        name = cfg.get("name", integration_id)
        console.print(f"\n[bold cyan]{name}[/bold cyan] ({integration_id})")
        console.print("  [dim]تكامل مضمّن (غير مدرج في الكتالوج)[/dim]")
        if integration_id == installed_key:
            console.print("\n  [green]✓ مثبّت[/green] (نشط حالياً)")
        if catalog_error:
            console.print(f"\n[yellow]الكتالوج غير متاح:[/yellow] {catalog_error}")
        return

    if catalog_error:
        console.print(f"[red]خطأ:[/red] تعذّر الاستعلام عن كتالوج التكاملات: {catalog_error}")
        if isinstance(catalog_error, IntegrationValidationError):
            console.print(
                "\nتحقق من مسار ملف الإعداد الظاهر أعلاه "
                "(.specify/integration-catalogs.yml أو ~/.specify/integration-catalogs.yml)، "
                "أو استخدم معرّف تكامل مضمّن مباشرة."
            )
        elif os.environ.get("SPECKIT_INTEGRATION_CATALOG_URL", "").strip():
            console.print(
                "\nتحقق ما إذا كان SPECKIT_INTEGRATION_CATALOG_URL مضبوطاً بشكل صحيح ومتاحاً، "
                "أو ألغِ تعيينه لاستخدام ملفات الكتالوج المُعدّة، أو استخدم معرّف تكامل مضمّن مباشرة."
            )
        else:
            console.print("\nحاول مجدداً عند الاتصال، أو استخدم معرّف تكامل مضمّن مباشرة.")
    else:
        console.print(f"[red]خطأ:[/red] التكامل '{integration_id}' غير موجود")
        console.print("\nجرّب: specify integration search")
    raise typer.Exit(1)


@integration_catalog_app.command("list")
def integration_catalog_list():
    """عرض مصادر كتالوج التكاملات المُعدّة."""
    from .integrations.catalog import IntegrationCatalog, IntegrationCatalogError

    project_root = _require_specify_project()
    catalog = IntegrationCatalog(project_root)
    env_override = os.environ.get("SPECKIT_INTEGRATION_CATALOG_URL", "").strip()

    try:
        if env_override:
            project_configs = None
            configs = catalog.get_catalog_configs()
        else:
            project_configs = catalog.get_project_catalog_configs()
            configs = project_configs if project_configs is not None else catalog.get_catalog_configs()
    except IntegrationCatalogError as exc:
        console.print(f"[red]خطأ:[/red] {exc}")
        raise typer.Exit(1)

    console.print("\n[bold cyan]مصادر كتالوج التكاملات:[/bold cyan]\n")
    if env_override:
        console.print(
            "  SPECKIT_INTEGRATION_CATALOG_URL مضبوط؛ يتجاوز ملفات الكتالوج المُعدّة."
        )
        console.print(
            "  مصادر كتالوج المشروع/المستخدم غير نشطة بينما تجاوز البيئة مضبوط.\n"
        )
        console.print("[bold]مصدر كتالوج نشط من البيئة (غير قابل للإزالة هنا):[/bold]\n")
    elif project_configs is None:
        console.print("  لا توجد مصادر كتالوج على مستوى المشروع.\n")
        console.print("[bold]مصادر كتالوج نشطة (غير قابلة للإزالة هنا):[/bold]\n")
    else:
        console.print("[bold]مصادر كتالوج المشروع (قابلة للإزالة):[/bold]\n")

    for i, cfg in enumerate(configs):
        install_status = (
            "[green]التثبيت مسموح[/green]"
            if cfg.get("install_allowed")
            else "[yellow]للاكتشاف فقط[/yellow]"
        )
        raw_name = cfg.get("name")
        display_name = str(raw_name).strip() if raw_name is not None else ""
        if not display_name:
            display_name = f"catalog-{i + 1}"
        if env_override or project_configs is None:
            console.print(f"  - [bold]{display_name}[/bold] — {install_status}")
        else:
            console.print(f"  [{i}] [bold]{display_name}[/bold] — {install_status}")
        console.print(f"      {cfg.get('url', '')}")
        if cfg.get("description"):
            console.print(f"      [dim]{cfg['description']}[/dim]")
        console.print()


@integration_catalog_app.command("add")
def integration_catalog_add(
    url: str = typer.Argument(
        ...,
        help=(
            "رابط الكتالوج المراد إضافته (HTTPS مطلوب، باستثناء http://localhost، "
            "http://127.0.0.1، أو http://[::1] للاختبار المحلي)"
        ),
    ),
    name: Optional[str] = typer.Option(None, "--name", help="اسم الكتالوج"),
):
    """إضافة مصدر كتالوج تكاملات إلى إعدادات المشروع."""
    from .integrations.catalog import IntegrationCatalog, IntegrationCatalogError

    project_root = _require_specify_project()
    catalog = IntegrationCatalog(project_root)

    # Normalize once here so the success message reflects what was actually
    # stored. ``IntegrationCatalog.add_catalog`` strips again defensively.
    normalized_url = url.strip()

    try:
        catalog.add_catalog(normalized_url, name)
    except IntegrationCatalogError as exc:
        # Covers both URL validation (base class) and config-file validation
        # (IntegrationValidationError subclass).
        console.print(f"[red]خطأ:[/red] {exc}")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] تمت إضافة مصدر الكتالوج: {normalized_url}")


@integration_catalog_app.command("remove")
def integration_catalog_remove(
    index: int = typer.Argument(..., help="فهرس الكتالوج المراد إزالته (من 'catalog list')"),
):
    """إزالة مصدر كتالوج تكاملات بواسطة الفهرس (يبدأ من 0)."""
    from .integrations.catalog import IntegrationCatalog, IntegrationCatalogError

    project_root = _require_specify_project()
    catalog = IntegrationCatalog(project_root)

    try:
        removed_name = catalog.remove_catalog(index)
    except IntegrationCatalogError as exc:
        console.print(f"[red]خطأ:[/red] {exc}")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] تم إزالة مصدر الكتالوج '{removed_name}'")


# ===== Preset Commands =====


@preset_app.command("list")
def preset_list():
    """عرض الوصفات المثبّتة."""
    from .presets import PresetManager

    project_root = _require_specify_project()
    manager = PresetManager(project_root)
    installed = manager.list_installed()

    if not installed:
        console.print("[yellow]لا توجد وصفات مثبّتة.[/yellow]")
        console.print("\nثبّت وصفة بـ:")
        console.print("  [cyan]specify preset add <pack-name>[/cyan]")
        return

    console.print("\n[bold cyan]الوصفات المثبّتة:[/bold cyan]\n")
    for pack in installed:
        status = "[green]مفعّل[/green]" if pack.get("enabled", True) else "[red]معطّل[/red]"
        pri = pack.get('priority', 10)
        console.print(f"  [bold]{pack['name']}[/bold] ({pack['id']}) v{pack['version']} — {status} — أولوية {pri}")
        console.print(f"    {pack['description']}")
        if pack.get("tags"):
            tags_str = ", ".join(pack["tags"])
            console.print(f"    [dim]الوسوم: {tags_str}[/dim]")
        console.print(f"    [dim]القوالب: {pack['template_count']}[/dim]")
        console.print()


@preset_app.command("add")
def preset_add(
    preset_id: str = typer.Argument(None, help="معرّف الوصفة للتثبيت من الكتالوج"),
    from_url: str = typer.Option(None, "--from", help="التثبيت من رابط (ملف ZIP)"),
    dev: str = typer.Option(None, "--dev", help="التثبيت من مجلد محلي (وضع التطوير)"),
    priority: int = typer.Option(10, "--priority", help="أولوية الحل (أقل = أعلى أولوية، الافتراضي 10)"),
):
    """تثبيت وصفة."""
    from .presets import (
        PresetManager,
        PresetCatalog,
        PresetError,
        PresetValidationError,
        PresetCompatibilityError,
    )

    project_root = _require_specify_project()
    # Validate priority
    if priority < 1:
        console.print("[red]خطأ:[/red] الأولوية يجب أن تكون عدداً صحيحاً موجباً (1 أو أعلى)")
        raise typer.Exit(1)

    manager = PresetManager(project_root)
    speckit_version = get_speckit_version()

    try:
        if dev:
            dev_path = Path(dev).resolve()
            if not dev_path.exists():
                console.print(f"[red]خطأ:[/red] لم يُعثر على المجلد: {dev}")
                raise typer.Exit(1)

            console.print(f"تثبيت الوصفة من [cyan]{dev_path}[/cyan]...")
            manifest = manager.install_from_directory(dev_path, speckit_version, priority)
            console.print(f"[green]✓[/green] تم تثبيت الوصفة '{manifest.name}' v{manifest.version} (أولوية {priority})")

        elif from_url:
            # Validate URL scheme before downloading
            from urllib.parse import urlparse as _urlparse
            _parsed = _urlparse(from_url)
            _is_localhost = _parsed.hostname in ("localhost", "127.0.0.1", "::1")
            if _parsed.scheme != "https" and not (_parsed.scheme == "http" and _is_localhost):
                console.print(f"[red]خطأ:[/red] يجب أن يستخدم الرابط HTTPS (تم استلام {_parsed.scheme}://). HTTP مسموح فقط للـ localhost.")
                raise typer.Exit(1)

            console.print(f"تثبيت الوصفة من [cyan]{from_url}[/cyan]...")
            import urllib.request
            import urllib.error
            import tempfile

            with tempfile.TemporaryDirectory() as tmpdir:
                zip_path = Path(tmpdir) / "preset.zip"
                try:
                    with urllib.request.urlopen(from_url, timeout=60) as response:
                        zip_path.write_bytes(response.read())
                except urllib.error.URLError as e:
                    console.print(f"[red]خطأ:[/red] فشل التنزيل: {e}")
                    raise typer.Exit(1)

                manifest = manager.install_from_zip(zip_path, speckit_version, priority)

            console.print(f"[green]✓[/green] تم تثبيت الوصفة '{manifest.name}' v{manifest.version} (أولوية {priority})")

        elif preset_id:
            # Try bundled preset first, then catalog
            bundled_path = _locate_bundled_preset(preset_id)
            if bundled_path:
                console.print(f"تثبيت الوصفة المضمّنة [cyan]{preset_id}[/cyan]...")
                manifest = manager.install_from_directory(bundled_path, speckit_version, priority)
                console.print(f"[green]✓[/green] تم تثبيت الوصفة '{manifest.name}' v{manifest.version} (أولوية {priority})")
            else:
                catalog = PresetCatalog(project_root)
                pack_info = catalog.get_pack_info(preset_id)

                if not pack_info:
                    console.print(f"[red]خطأ:[/red] الوصفة '{preset_id}' غير موجودة في الكتالوج")
                    raise typer.Exit(1)

                # Bundled presets should have been caught above; if we reach
                # here the bundled files are missing from the installation.
                if pack_info.get("bundled") and not pack_info.get("download_url"):
                    from .extensions import REINSTALL_COMMAND
                    console.print(
                        f"[red]خطأ:[/red] الوصفة '{preset_id}' مضمّنة مع spec-kit "
                        f"لكن لم يتم العثور عليها في الحزمة المثبّتة."
                    )
                    console.print(
                        "\nهذا عادةً يعني أن تثبيت spec-kit غير مكتمل أو تالف."
                    )
                    console.print("حاول إعادة تثبيت spec-kit:")
                    console.print(f"  {REINSTALL_COMMAND}")
                    raise typer.Exit(1)

                if not pack_info.get("_install_allowed", True):
                    catalog_name = pack_info.get("_catalog_name", "unknown")
                    console.print(f"[red]خطأ:[/red] الوصفة '{preset_id}' من كتالوج '{catalog_name}' وهو للاكتشاف فقط (التثبيت غير مسموح).")
                    console.print("أضف الكتالوج مع --install-allowed أو ثبّت من مستودع الوصفة مباشرة مع --from.")
                    raise typer.Exit(1)

                console.print(f"تثبيت الوصفة [cyan]{pack_info.get('name', preset_id)}[/cyan]...")

                try:
                    zip_path = catalog.download_pack(preset_id)
                    manifest = manager.install_from_zip(zip_path, speckit_version, priority)
                    console.print(f"[green]✓[/green] تم تثبيت الوصفة '{manifest.name}' v{manifest.version} (أولوية {priority})")
                finally:
                    if 'zip_path' in locals() and zip_path.exists():
                        zip_path.unlink(missing_ok=True)
        else:
            console.print("[red]خطأ:[/red] حدّد معرّف وصفة، أو --from URL، أو مسار --dev")
            raise typer.Exit(1)

    except PresetCompatibilityError as e:
        console.print(f"[red]خطأ توافق:[/red] {e}")
        raise typer.Exit(1)
    except PresetValidationError as e:
        console.print(f"[red]خطأ تحقق:[/red] {e}")
        raise typer.Exit(1)
    except PresetError as e:
        console.print(f"[red]خطأ:[/red] {e}")
        raise typer.Exit(1)


@preset_app.command("remove")
def preset_remove(
    preset_id: str = typer.Argument(..., help="معرّف الوصفة المراد إزالتها"),
):
    """إزالة وصفة مثبّتة."""
    from .presets import PresetManager

    project_root = _require_specify_project()
    manager = PresetManager(project_root)

    if not manager.registry.is_installed(preset_id):
        console.print(f"[red]خطأ:[/red] الوصفة '{preset_id}' غير مثبّتة")
        raise typer.Exit(1)

    if manager.remove(preset_id):
        console.print(f"[green]✓[/green] تمت إزالة الوصفة '{preset_id}' بنجاح")
    else:
        console.print(f"[red]خطأ:[/red] فشل إزالة الوصفة '{preset_id}'")
        raise typer.Exit(1)


@preset_app.command("search")
def preset_search(
    query: str = typer.Argument(None, help="استعلام البحث"),
    tag: str = typer.Option(None, "--tag", help="التصفية حسب الوسم"),
    author: str = typer.Option(None, "--author", help="التصفية حسب المؤلف"),
):
    """البحث عن وصفات في الكتالوج."""
    from .presets import PresetCatalog, PresetError

    project_root = _require_specify_project()
    catalog = PresetCatalog(project_root)

    try:
        results = catalog.search(query=query, tag=tag, author=author)
    except PresetError as e:
        console.print(f"[red]خطأ:[/red] {e}")
        raise typer.Exit(1)

    if not results:
        console.print("[yellow]لم يُعثر على وصفات تطابق معاييرك.[/yellow]")
        return

    console.print(f"\n[bold cyan]الوصفات ({len(results)} موجودة):[/bold cyan]\n")
    for pack in results:
        console.print(f"  [bold]{pack.get('name', pack['id'])}[/bold] ({pack['id']}) v{pack.get('version', '?')}")
        console.print(f"    {pack.get('description', '')}")
        if pack.get("tags"):
            tags_str = ", ".join(pack["tags"])
            console.print(f"    [dim]الوسوم: {tags_str}[/dim]")
        console.print()


@preset_app.command("resolve")
def preset_resolve(
    template_name: str = typer.Argument(..., help="اسم القالب المراد حلّه (مثال: spec-template)"),
):
    """عرض القالب الذي سيتم حلّه لاسم معيّن."""
    from .presets import PresetResolver

    project_root = _require_specify_project()
    resolver = PresetResolver(project_root)
    layers = resolver.collect_all_layers(template_name)

    if layers:
        # Use the highest-priority layer for display because the final output
        # may be composed and may not map to resolve_with_source()'s single path.
        display_layer = layers[0]
        console.print(f"  [bold]{template_name}[/bold]: {display_layer['path']}")
        console.print(f"    [dim](الطبقة العليا من: {display_layer['source']})[/dim]")

        has_composition = (
            layers[0]["strategy"] != "replace"
            and any(layer["strategy"] != "replace" for layer in layers)
        )
        if has_composition:
            # Verify composition is actually possible
            try:
                composed = resolver.resolve_content(template_name)
            except Exception as exc:
                composed = None
                console.print(f"    [yellow]تحذير: خطأ في التركيب: {exc}[/yellow]")
            if composed is None:
                console.print("    [yellow]تحذير: التركيب لا ينتج مخرجات (لا توجد طبقة أساس باستراتيجية 'replace')[/yellow]")
            else:
                console.print("    [dim]المخرج النهائي مُركّب من طبقات وصفات متعددة؛ المسار أعلاه هو الطبقة المساهمة الأعلى أولوية.[/dim]")
            console.print("\n  [bold]سلسلة التركيب:[/bold]")
            # Compute the effective base: first replace layer scanning from
            # highest priority (matching resolve_content top-down logic).
            # Only show layers from the base upward (lower layers are ignored).
            effective_base_idx = None
            for idx, lyr in enumerate(layers):
                if lyr["strategy"] == "replace":
                    effective_base_idx = idx
                    break
            # Show only contributing layers (base and above)
            if effective_base_idx is not None:
                contributing = layers[:effective_base_idx + 1]
            else:
                contributing = layers
            for i, layer in enumerate(reversed(contributing)):
                strategy_label = layer["strategy"]
                if strategy_label == "replace" and i == 0:
                    strategy_label = "أساس"
                console.print(f"    {i + 1}. [{strategy_label}] {layer['source']} → {layer['path']}")
    else:
        # No layers found — fall back to resolve_with_source for non-composition cases
        result = resolver.resolve_with_source(template_name)
        if result:
            console.print(f"  [bold]{template_name}[/bold]: {result['path']}")
            console.print(f"    [dim](من: {result['source']})[/dim]")
        else:
            console.print(f"  [yellow]{template_name}[/yellow]: غير موجود")
            console.print("    [dim]لا يوجد قالب بهذا الاسم في كومة الحل[/dim]")


@preset_app.command("info")
def preset_info(
    preset_id: str = typer.Argument(..., help="معرّف الوصفة المطلوب الحصول على معلوماتها"),
):
    """عرض معلومات تفصيلية عن وصفة."""
    from .extensions import normalize_priority
    from .presets import PresetCatalog, PresetManager, PresetError

    project_root = _require_specify_project()
    # Check if installed locally first
    manager = PresetManager(project_root)
    local_pack = manager.get_pack(preset_id)

    if local_pack:
        console.print(f"\n[bold cyan]الوصفة: {local_pack.name}[/bold cyan]\n")
        console.print(f"  المعرّف:        {local_pack.id}")
        console.print(f"  الإصدار:       {local_pack.version}")
        console.print(f"  الوصف:        {local_pack.description}")
        if local_pack.author:
            console.print(f"  المؤلف:        {local_pack.author}")
        if local_pack.tags:
            console.print(f"  الوسوم:        {', '.join(local_pack.tags)}")
        console.print(f"  القوالب:       {len(local_pack.templates)}")
        for tmpl in local_pack.templates:
            console.print(f"    - {tmpl['name']} ({tmpl['type']}): {tmpl.get('description', '')}")
        repo = local_pack.data.get("preset", {}).get("repository")
        if repo:
            console.print(f"  المستودع:     {repo}")
        license_val = local_pack.data.get("preset", {}).get("license")
        if license_val:
            console.print(f"  الرخصة:       {license_val}")
        console.print("\n  [green]الحالة: مثبّت[/green]")
        # Get priority from registry
        pack_metadata = manager.registry.get(preset_id)
        priority = normalize_priority(pack_metadata.get("priority") if isinstance(pack_metadata, dict) else None)
        console.print(f"  [dim]الأولوية:[/dim] {priority}")
        console.print()
        return

    # Fall back to catalog
    catalog = PresetCatalog(project_root)
    try:
        pack_info = catalog.get_pack_info(preset_id)
    except PresetError:
        pack_info = None

    if not pack_info:
        console.print(f"[red]خطأ:[/red] الوصفة '{preset_id}' غير موجودة (غير مثبّتة وليست في الكتالوج)")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]الوصفة: {pack_info.get('name', preset_id)}[/bold cyan]\n")
    console.print(f"  المعرّف:        {pack_info['id']}")
    console.print(f"  الإصدار:       {pack_info.get('version', '?')}")
    console.print(f"  الوصف:        {pack_info.get('description', '')}")
    if pack_info.get("author"):
        console.print(f"  المؤلف:        {pack_info['author']}")
    if pack_info.get("tags"):
        console.print(f"  الوسوم:        {', '.join(pack_info['tags'])}")
    if pack_info.get("repository"):
        console.print(f"  المستودع:     {pack_info['repository']}")
    if pack_info.get("license"):
        console.print(f"  الرخصة:       {pack_info['license']}")
    console.print("\n  [yellow]الحالة: غير مثبّت[/yellow]")
    console.print(f"  للتثبيت: [cyan]specify preset add {preset_id}[/cyan]")
    console.print()


@preset_app.command("set-priority")
def preset_set_priority(
    preset_id: str = typer.Argument(help="معرّف الوصفة"),
    priority: int = typer.Argument(help="الأولوية الجديدة (أقل = أعلى أولوية)"),
):
    """تعيين أولوية الحل لوصفة مثبّتة."""
    from .presets import PresetManager

    project_root = _require_specify_project()
    # Validate priority
    if priority < 1:
        console.print("[red]خطأ:[/red] الأولوية يجب أن تكون عدداً صحيحاً موجباً (1 أو أعلى)")
        raise typer.Exit(1)

    manager = PresetManager(project_root)

    # Check if preset is installed
    if not manager.registry.is_installed(preset_id):
        console.print(f"[red]خطأ:[/red] الوصفة '{preset_id}' غير مثبّتة")
        raise typer.Exit(1)

    # Get current metadata
    metadata = manager.registry.get(preset_id)
    if metadata is None or not isinstance(metadata, dict):
        console.print(f"[red]خطأ:[/red] الوصفة '{preset_id}' غير موجودة في السجل (حالة تالفة)")
        raise typer.Exit(1)

    from .extensions import normalize_priority
    raw_priority = metadata.get("priority")
    # Only skip if the stored value is already a valid int equal to requested priority
    # This ensures corrupted values (e.g., "high") get repaired even when setting to default (10)
    if isinstance(raw_priority, int) and raw_priority == priority:
        console.print(f"[yellow]الوصفة '{preset_id}' لها بالفعل أولوية {priority}[/yellow]")
        raise typer.Exit(0)

    old_priority = normalize_priority(raw_priority)

    # Update priority
    manager.registry.update(preset_id, {"priority": priority})

    console.print(f"[green]✓[/green] تم تغيير أولوية الوصفة '{preset_id}': {old_priority} → {priority}")
    console.print("\n[dim]أولوية أقل = أعلى أسبقية في حل القوالب[/dim]")


@preset_app.command("enable")
def preset_enable(
    preset_id: str = typer.Argument(help="معرّف الوصفة المراد تفعيلها"),
):
    """تفعيل وصفة معطّلة."""
    from .presets import PresetManager

    project_root = _require_specify_project()
    manager = PresetManager(project_root)

    # Check if preset is installed
    if not manager.registry.is_installed(preset_id):
        console.print(f"[red]خطأ:[/red] الوصفة '{preset_id}' غير مثبّتة")
        raise typer.Exit(1)

    # Get current metadata
    metadata = manager.registry.get(preset_id)
    if metadata is None or not isinstance(metadata, dict):
        console.print(f"[red]خطأ:[/red] الوصفة '{preset_id}' غير موجودة في السجل (حالة تالفة)")
        raise typer.Exit(1)

    if metadata.get("enabled", True):
        console.print(f"[yellow]الوصفة '{preset_id}' مفعّلة بالفعل[/yellow]")
        raise typer.Exit(0)

    # Enable the preset
    manager.registry.update(preset_id, {"enabled": True})

    console.print(f"[green]✓[/green] تم تفعيل الوصفة '{preset_id}'")
    console.print("\nستُضمّن قوالب هذه الوصفة الآن في الحل.")
    console.print("[dim]ملاحظة: الأوامر/المهارات المسجّلة مسبقاً تبقى نشطة.[/dim]")


@preset_app.command("disable")
def preset_disable(
    preset_id: str = typer.Argument(help="معرّف الوصفة المراد تعطيلها"),
):
    """تعطيل وصفة دون إزالتها."""
    from .presets import PresetManager

    project_root = _require_specify_project()
    manager = PresetManager(project_root)

    # Check if preset is installed
    if not manager.registry.is_installed(preset_id):
        console.print(f"[red]خطأ:[/red] الوصفة '{preset_id}' غير مثبّتة")
        raise typer.Exit(1)

    # Get current metadata
    metadata = manager.registry.get(preset_id)
    if metadata is None or not isinstance(metadata, dict):
        console.print(f"[red]خطأ:[/red] الوصفة '{preset_id}' غير موجودة في السجل (حالة تالفة)")
        raise typer.Exit(1)

    if not metadata.get("enabled", True):
        console.print(f"[yellow]الوصفة '{preset_id}' معطّلة بالفعل[/yellow]")
        raise typer.Exit(0)

    # Disable the preset
    manager.registry.update(preset_id, {"enabled": False})

    console.print(f"[green]✓[/green] تم تعطيل الوصفة '{preset_id}'")
    console.print("\nستُتخطّى قوالب هذه الوصفة أثناء الحل.")
    console.print("[dim]ملاحظة: الأوامر/المهارات المسجّلة مسبقاً تبقى نشطة حتى إزالة الوصفة.[/dim]")
    console.print(f"لإعادة التفعيل: specify preset enable {preset_id}")


# ===== Preset Catalog Commands =====


@preset_catalog_app.command("list")
def preset_catalog_list():
    """عرض جميع كتالوجات الوصفات النشطة."""
    from .presets import PresetCatalog, PresetValidationError

    project_root = _require_specify_project()
    catalog = PresetCatalog(project_root)

    try:
        active_catalogs = catalog.get_active_catalogs()
    except PresetValidationError as e:
        console.print(f"[red]خطأ:[/red] {e}")
        raise typer.Exit(1)

    console.print("\n[bold cyan]كتالوجات الوصفات النشطة:[/bold cyan]\n")
    for entry in active_catalogs:
        install_str = (
            "[green]التثبيت مسموح[/green]"
            if entry.install_allowed
            else "[yellow]للاكتشاف فقط[/yellow]"
        )
        console.print(f"  [bold]{entry.name}[/bold] (أولوية {entry.priority})")
        if entry.description:
            console.print(f"     {entry.description}")
        console.print(f"     URL: {entry.url}")
        console.print(f"     التثبيت: {install_str}")
        console.print()

    config_path = project_root / ".specify" / "preset-catalogs.yml"
    user_config_path = Path.home() / ".specify" / "preset-catalogs.yml"
    if os.environ.get("SPECKIT_PRESET_CATALOG_URL"):
        console.print("[dim]تم إعداد الكتالوج عبر متغير البيئة SPECKIT_PRESET_CATALOG_URL.[/dim]")
    else:
        try:
            proj_loaded = config_path.exists() and catalog._load_catalog_config(config_path) is not None
        except PresetValidationError:
            proj_loaded = False
        if proj_loaded:
            console.print(f"[dim]الإعداد: {_display_project_path(project_root, config_path)}[/dim]")
        else:
            try:
                user_loaded = user_config_path.exists() and catalog._load_catalog_config(user_config_path) is not None
            except PresetValidationError:
                user_loaded = False
            if user_loaded:
                console.print("[dim]الإعداد: ~/.specify/preset-catalogs.yml[/dim]")
            else:
                console.print("[dim]يستخدم كومة الكتالوج الافتراضية المضمّنة.[/dim]")
                console.print(
                    "[dim]أضف .specify/preset-catalogs.yml للتخصيص.[/dim]"
                )


@preset_catalog_app.command("add")
def preset_catalog_add(
    url: str = typer.Argument(help="رابط الكتالوج (يجب استخدام HTTPS)"),
    name: str = typer.Option(..., "--name", help="اسم الكتالوج"),
    priority: int = typer.Option(10, "--priority", help="الأولوية (أقل = أعلى أولوية)"),
    install_allowed: bool = typer.Option(
        False, "--install-allowed/--no-install-allowed",
        help="السماح بتثبيت الوصفات من هذا الكتالوج",
    ),
    description: str = typer.Option("", "--description", help="وصف الكتالوج"),
):
    """إضافة كتالوج إلى .specify/preset-catalogs.yml."""
    from .presets import PresetCatalog, PresetValidationError

    project_root = _require_specify_project()
    specify_dir = project_root / ".specify"

    # Validate URL
    tmp_catalog = PresetCatalog(project_root)
    try:
        tmp_catalog._validate_catalog_url(url)
    except PresetValidationError as e:
        console.print(f"[red]خطأ:[/red] {e}")
        raise typer.Exit(1)

    config_path = specify_dir / "preset-catalogs.yml"

    # Load existing config
    if config_path.exists():
        try:
            config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except Exception as e:
            config_label = _display_project_path(project_root, config_path)
            console.print(f"[red]خطأ:[/red] فشل قراءة {config_label}: {e}")
            raise typer.Exit(1)
    else:
        config = {}

    catalogs = config.get("catalogs", [])
    if not isinstance(catalogs, list):
        console.print("[red]خطأ:[/red] إعداد كتالوج غير صالح: 'catalogs' يجب أن يكون قائمة.")
        raise typer.Exit(1)

    # Check for duplicate name
    for existing in catalogs:
        if isinstance(existing, dict) and existing.get("name") == name:
            console.print(f"[yellow]تحذير:[/yellow] يوجد كتالوج باسم '{name}' بالفعل.")
            console.print("استخدم 'specify preset catalog remove' أولاً، أو اختر اسماً مختلفاً.")
            raise typer.Exit(1)

    catalogs.append({
        "name": name,
        "url": url,
        "priority": priority,
        "install_allowed": install_allowed,
        "description": description,
    })

    config["catalogs"] = catalogs
    config_path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False, allow_unicode=True), encoding="utf-8")

    install_label = "التثبيت مسموح" if install_allowed else "للاكتشاف فقط"
    console.print(f"\n[green]✓[/green] تمت إضافة الكتالوج '[bold]{name}[/bold]' ({install_label})")
    console.print(f"  URL: {url}")
    console.print(f"  الأولوية: {priority}")
    console.print(f"\nتم حفظ الإعدادات في {_display_project_path(project_root, config_path)}")


@preset_catalog_app.command("remove")
def preset_catalog_remove(
    name: str = typer.Argument(help="اسم الكتالوج المراد إزالته"),
):
    """إزالة كتالوج من .specify/preset-catalogs.yml."""
    project_root = _require_specify_project()
    specify_dir = project_root / ".specify"

    config_path = specify_dir / "preset-catalogs.yml"
    if not config_path.exists():
        console.print("[red]خطأ:[/red] لم يُعثر على إعدادات كتالوج الوصفات. لا شيء للإزالة.")
        raise typer.Exit(1)

    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        console.print("[red]خطأ:[/red] فشل قراءة إعدادات كتالوج الوصفات.")
        raise typer.Exit(1)

    catalogs = config.get("catalogs", [])
    if not isinstance(catalogs, list):
        console.print("[red]خطأ:[/red] إعداد كتالوج غير صالح: 'catalogs' يجب أن يكون قائمة.")
        raise typer.Exit(1)
    original_count = len(catalogs)
    catalogs = [c for c in catalogs if isinstance(c, dict) and c.get("name") != name]

    if len(catalogs) == original_count:
        console.print(f"[red]خطأ:[/red] الكتالوج '{name}' غير موجود.")
        raise typer.Exit(1)

    config["catalogs"] = catalogs
    config_path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False, allow_unicode=True), encoding="utf-8")

    console.print(f"[green]✓[/green] تمت إزالة الكتالوج '{name}'")
    if not catalogs:
        console.print("\n[dim]لا تتبقى كتالوجات في الإعدادات. ستُستخدم الافتراضيات المضمّنة.[/dim]")


# ===== Extension Commands =====


def _resolve_installed_extension(
    argument: str,
    installed_extensions: list,
    command_name: str = "command",
    allow_not_found: bool = False,
) -> tuple[Optional[str], Optional[str]]:
    """Resolve an extension argument (ID or display name) to an installed extension.

    Args:
        argument: Extension ID or display name provided by user
        installed_extensions: List of installed extension dicts from manager.list_installed()
        command_name: Name of the command for error messages (e.g., "enable", "disable")
        allow_not_found: If True, return (None, None) when not found instead of raising

    Returns:
        Tuple of (extension_id, display_name), or (None, None) if allow_not_found=True and not found

    Raises:
        typer.Exit: If extension not found (and allow_not_found=False) or name is ambiguous
    """
    from rich.table import Table

    # First, try exact ID match
    for ext in installed_extensions:
        if ext["id"] == argument:
            return (ext["id"], ext["name"])

    # If not found by ID, try display name match
    name_matches = [ext for ext in installed_extensions if ext["name"].lower() == argument.lower()]

    if len(name_matches) == 1:
        # Unique display-name match
        return (name_matches[0]["id"], name_matches[0]["name"])
    elif len(name_matches) > 1:
        # Ambiguous display-name match
        console.print(
            f"[red]خطأ:[/red] اسم الامتداد '{argument}' غامض. "
            "عدة امتدادات مثبّتة تشترك في هذا الاسم:"
        )
        table = Table(title="الامتدادات المطابقة")
        table.add_column("المعرّف", style="cyan", no_wrap=True)
        table.add_column("الاسم", style="white")
        table.add_column("الإصدار", style="green")
        for ext in name_matches:
            table.add_row(ext.get("id", ""), ext.get("name", ""), str(ext.get("version", "")))
        console.print(table)
        console.print("\nيرجى إعادة المحاولة باستخدام معرّف الامتداد:")
        console.print(f"  [bold]specify extension {command_name} <extension-id>[/bold]")
        raise typer.Exit(1)
    else:
        # No match by ID or display name
        if allow_not_found:
            return (None, None)
        console.print(f"[red]خطأ:[/red] الامتداد '{argument}' غير مثبّت")
        raise typer.Exit(1)


def _resolve_catalog_extension(
    argument: str,
    catalog,
    command_name: str = "info",
) -> tuple[Optional[dict], Optional[Exception]]:
    """Resolve an extension argument (ID or display name) from the catalog.

    Args:
        argument: Extension ID or display name provided by user
        catalog: ExtensionCatalog instance
        command_name: Name of the command for error messages

    Returns:
        Tuple of (extension_info, catalog_error)
        - If found: (ext_info_dict, None)
        - If catalog error: (None, error)
        - If not found: (None, None)
    """
    from rich.table import Table
    from .extensions import ExtensionError

    try:
        # First try by ID
        ext_info = catalog.get_extension_info(argument)
        if ext_info:
            return (ext_info, None)

        # Try by display name - search using argument as query, then filter for exact match
        search_results = catalog.search(query=argument)
        name_matches = [ext for ext in search_results if ext["name"].lower() == argument.lower()]

        if len(name_matches) == 1:
            return (name_matches[0], None)
        elif len(name_matches) > 1:
            # Ambiguous display-name match in catalog
            console.print(
                f"[red]خطأ:[/red] اسم الامتداد '{argument}' غامض. "
                "عدة امتدادات في الكتالوج تشترك في هذا الاسم:"
            )
            table = Table(title="الامتدادات المطابقة")
            table.add_column("المعرّف", style="cyan", no_wrap=True)
            table.add_column("الاسم", style="white")
            table.add_column("الإصدار", style="green")
            table.add_column("الكتالوج", style="dim")
            for ext in name_matches:
                table.add_row(
                    ext.get("id", ""),
                    ext.get("name", ""),
                    str(ext.get("version", "")),
                    ext.get("_catalog_name", ""),
                )
            console.print(table)
            console.print("\nيرجى إعادة المحاولة باستخدام معرّف الامتداد:")
            console.print(f"  [bold]specify extension {command_name} <extension-id>[/bold]")
            raise typer.Exit(1)

        # Not found
        return (None, None)

    except ExtensionError as e:
        return (None, e)


@extension_app.command("list")
def extension_list(
    available: bool = typer.Option(False, "--available", help="عرض الامتدادات المتاحة من الكتالوج"),
    all_extensions: bool = typer.Option(False, "--all", help="عرض كل من المثبّت والمتاح"),
):
    """عرض الامتدادات المثبّتة."""
    from .extensions import ExtensionManager

    project_root = _require_specify_project()
    manager = ExtensionManager(project_root)
    installed = manager.list_installed()

    if not installed and not (available or all_extensions):
        console.print("[yellow]لا توجد امتدادات مثبّتة.[/yellow]")
        console.print("\nثبّت امتداداً بـ:")
        console.print("  specify extension add <extension-name>")
        return

    if installed:
        console.print("\n[bold cyan]الامتدادات المثبّتة:[/bold cyan]\n")

        for ext in installed:
            status_icon = "✓" if ext["enabled"] else "✗"
            status_color = "green" if ext["enabled"] else "red"

            console.print(f"  [{status_color}]{status_icon}[/{status_color}] [bold]{ext['name']}[/bold] (v{ext['version']})")
            console.print(f"     [dim]{ext['id']}[/dim]")
            console.print(f"     {ext['description']}")
            console.print(f"     الأوامر: {ext['command_count']} | الـ Hooks: {ext['hook_count']} | الأولوية: {ext['priority']} | الحالة: {'مفعّل' if ext['enabled'] else 'معطّل'}")
            console.print()

    if available or all_extensions:
        console.print("\nثبّت امتداداً:")
        console.print("  [cyan]specify extension add <name>[/cyan]")


@catalog_app.command("list")
def catalog_list():
    """عرض جميع كتالوجات الامتدادات النشطة."""
    from .extensions import ExtensionCatalog, ValidationError

    project_root = _require_specify_project()
    catalog = ExtensionCatalog(project_root)

    try:
        active_catalogs = catalog.get_active_catalogs()
    except ValidationError as e:
        console.print(f"[red]خطأ:[/red] {e}")
        raise typer.Exit(1)

    console.print("\n[bold cyan]كتالوجات الامتدادات النشطة:[/bold cyan]\n")
    for entry in active_catalogs:
        install_str = (
            "[green]التثبيت مسموح[/green]"
            if entry.install_allowed
            else "[yellow]للاكتشاف فقط[/yellow]"
        )
        console.print(f"  [bold]{entry.name}[/bold] (أولوية {entry.priority})")
        if entry.description:
            console.print(f"     {entry.description}")
        console.print(f"     URL: {entry.url}")
        console.print(f"     التثبيت: {install_str}")
        console.print()

    config_path = project_root / ".specify" / "extension-catalogs.yml"
    user_config_path = Path.home() / ".specify" / "extension-catalogs.yml"
    if os.environ.get("SPECKIT_CATALOG_URL"):
        console.print("[dim]تم إعداد الكتالوج عبر متغير البيئة SPECKIT_CATALOG_URL.[/dim]")
    else:
        try:
            proj_loaded = config_path.exists() and catalog._load_catalog_config(config_path) is not None
        except ValidationError:
            proj_loaded = False
        if proj_loaded:
            console.print(f"[dim]الإعداد: {_display_project_path(project_root, config_path)}[/dim]")
        else:
            try:
                user_loaded = user_config_path.exists() and catalog._load_catalog_config(user_config_path) is not None
            except ValidationError:
                user_loaded = False
            if user_loaded:
                console.print("[dim]الإعداد: ~/.specify/extension-catalogs.yml[/dim]")
            else:
                console.print("[dim]يستخدم كومة الكتالوج الافتراضية المضمّنة.[/dim]")
                console.print(
                    "[dim]أضف .specify/extension-catalogs.yml للتخصيص.[/dim]"
                )


@catalog_app.command("add")
def catalog_add(
    url: str = typer.Argument(help="رابط الكتالوج (يجب استخدام HTTPS)"),
    name: str = typer.Option(..., "--name", help="اسم الكتالوج"),
    priority: int = typer.Option(10, "--priority", help="الأولوية (أقل = أعلى أولوية)"),
    install_allowed: bool = typer.Option(
        False, "--install-allowed/--no-install-allowed",
        help="السماح بتثبيت الامتدادات من هذا الكتالوج",
    ),
    description: str = typer.Option("", "--description", help="وصف الكتالوج"),
):
    """إضافة كتالوج إلى .specify/extension-catalogs.yml."""
    from .extensions import ExtensionCatalog, ValidationError

    project_root = _require_specify_project()
    specify_dir = project_root / ".specify"

    # Validate URL
    tmp_catalog = ExtensionCatalog(project_root)
    try:
        tmp_catalog._validate_catalog_url(url)
    except ValidationError as e:
        console.print(f"[red]خطأ:[/red] {e}")
        raise typer.Exit(1)

    config_path = specify_dir / "extension-catalogs.yml"

    # Load existing config
    if config_path.exists():
        try:
            config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except Exception as e:
            config_label = _display_project_path(project_root, config_path)
            console.print(f"[red]خطأ:[/red] فشل قراءة {config_label}: {e}")
            raise typer.Exit(1)
    else:
        config = {}

    catalogs = config.get("catalogs", [])
    if not isinstance(catalogs, list):
        console.print("[red]خطأ:[/red] إعداد كتالوج غير صالح: 'catalogs' يجب أن يكون قائمة.")
        raise typer.Exit(1)

    # Check for duplicate name
    for existing in catalogs:
        if isinstance(existing, dict) and existing.get("name") == name:
            console.print(f"[yellow]تحذير:[/yellow] يوجد كتالوج باسم '{name}' بالفعل.")
            console.print("استخدم 'specify extension catalog remove' أولاً، أو اختر اسماً مختلفاً.")
            raise typer.Exit(1)

    catalogs.append({
        "name": name,
        "url": url,
        "priority": priority,
        "install_allowed": install_allowed,
        "description": description,
    })

    config["catalogs"] = catalogs
    config_path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False, allow_unicode=True), encoding="utf-8")

    install_label = "التثبيت مسموح" if install_allowed else "للاكتشاف فقط"
    console.print(f"\n[green]✓[/green] تمت إضافة الكتالوج '[bold]{name}[/bold]' ({install_label})")
    console.print(f"  URL: {url}")
    console.print(f"  الأولوية: {priority}")
    console.print(f"\nتم حفظ الإعدادات في {_display_project_path(project_root, config_path)}")


@catalog_app.command("remove")
def catalog_remove(
    name: str = typer.Argument(help="اسم الكتالوج المراد إزالته"),
):
    """إزالة كتالوج من .specify/extension-catalogs.yml."""
    project_root = _require_specify_project()
    specify_dir = project_root / ".specify"

    config_path = specify_dir / "extension-catalogs.yml"
    if not config_path.exists():
        console.print("[red]خطأ:[/red] لم يُعثر على إعدادات كتالوج. لا شيء للإزالة.")
        raise typer.Exit(1)

    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        console.print("[red]خطأ:[/red] فشل قراءة إعدادات الكتالوج.")
        raise typer.Exit(1)

    catalogs = config.get("catalogs", [])
    if not isinstance(catalogs, list):
        console.print("[red]خطأ:[/red] إعداد كتالوج غير صالح: 'catalogs' يجب أن يكون قائمة.")
        raise typer.Exit(1)
    original_count = len(catalogs)
    catalogs = [c for c in catalogs if isinstance(c, dict) and c.get("name") != name]

    if len(catalogs) == original_count:
        console.print(f"[red]خطأ:[/red] الكتالوج '{name}' غير موجود.")
        raise typer.Exit(1)

    config["catalogs"] = catalogs
    config_path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False, allow_unicode=True), encoding="utf-8")

    console.print(f"[green]✓[/green] تمت إزالة الكتالوج '{name}'")
    if not catalogs:
        console.print("\n[dim]لا تتبقى كتالوجات في الإعدادات. ستُستخدم الافتراضيات المضمّنة.[/dim]")


@extension_app.command("add")
def extension_add(
    extension: str = typer.Argument(help="اسم الامتداد أو مساره"),
    dev: bool = typer.Option(False, "--dev", help="التثبيت من مجلد محلي"),
    from_url: Optional[str] = typer.Option(None, "--from", help="التثبيت من رابط مخصّص"),
    priority: int = typer.Option(10, "--priority", help="أولوية الحل (أقل = أعلى أولوية، الافتراضي 10)"),
):
    """تثبيت امتداد."""
    from .extensions import ExtensionManager, ExtensionCatalog, ExtensionError, ValidationError, CompatibilityError, REINSTALL_COMMAND

    project_root = _require_specify_project()
    # Validate priority
    if priority < 1:
        console.print("[red]خطأ:[/red] الأولوية يجب أن تكون عدداً صحيحاً موجباً (1 أو أعلى)")
        raise typer.Exit(1)

    manager = ExtensionManager(project_root)
    speckit_version = get_speckit_version()

    try:
        with console.status(f"[cyan]تثبيت الامتداد: {extension}[/cyan]"):
            if dev:
                # Install from local directory
                source_path = Path(extension).expanduser().resolve()
                if not source_path.exists():
                    console.print(f"[red]خطأ:[/red] لم يُعثر على المجلد: {source_path}")
                    raise typer.Exit(1)

                if not (source_path / "extension.yml").exists():
                    console.print(f"[red]خطأ:[/red] لم يُعثر على extension.yml في {source_path}")
                    raise typer.Exit(1)

                manifest = manager.install_from_directory(source_path, speckit_version, priority=priority)

            elif from_url:
                # Install from URL (ZIP file)
                import urllib.request
                import urllib.error
                from urllib.parse import urlparse

                # Validate URL
                parsed = urlparse(from_url)
                is_localhost = parsed.hostname in ("localhost", "127.0.0.1", "::1")

                if parsed.scheme != "https" and not (parsed.scheme == "http" and is_localhost):
                    console.print("[red]خطأ:[/red] يجب أن يستخدم الرابط HTTPS لأسباب أمنية.")
                    console.print("HTTP مسموح فقط لروابط localhost.")
                    raise typer.Exit(1)

                # Warn about untrusted sources
                console.print("[yellow]تحذير:[/yellow] تثبيت من رابط خارجي.")
                console.print("ثبّت الامتدادات فقط من مصادر تثق بها.\n")
                console.print(f"تنزيل من {from_url}...")

                # Download ZIP to temp location
                download_dir = project_root / ".specify" / "extensions" / ".cache" / "downloads"
                download_dir.mkdir(parents=True, exist_ok=True)
                zip_path = download_dir / f"{extension}-url-download.zip"

                try:
                    with urllib.request.urlopen(from_url, timeout=60) as response:
                        zip_data = response.read()
                    zip_path.write_bytes(zip_data)

                    # Install from downloaded ZIP
                    manifest = manager.install_from_zip(zip_path, speckit_version, priority=priority)
                except urllib.error.URLError as e:
                    console.print(f"[red]خطأ:[/red] فشل التنزيل من {from_url}: {e}")
                    raise typer.Exit(1)
                finally:
                    # Clean up downloaded ZIP
                    if zip_path.exists():
                        zip_path.unlink()

            else:
                # Try bundled extensions first (shipped with spec-kit)
                bundled_path = _locate_bundled_extension(extension)
                if bundled_path is not None:
                    manifest = manager.install_from_directory(bundled_path, speckit_version, priority=priority)
                else:
                    # Install from catalog (also resolves display names to IDs)
                    catalog = ExtensionCatalog(project_root)

                    # Check if extension exists in catalog (supports both ID and display name)
                    ext_info, catalog_error = _resolve_catalog_extension(extension, catalog, "add")
                    if catalog_error:
                        console.print(f"[red]خطأ:[/red] تعذّر الاستعلام عن كتالوج الامتدادات: {catalog_error}")
                        raise typer.Exit(1)
                    if not ext_info:
                        console.print(f"[red]خطأ:[/red] الامتداد '{extension}' غير موجود في الكتالوج")
                        console.print("\nابحث عن الامتدادات المتاحة:")
                        console.print("  specify extension search")
                        raise typer.Exit(1)

                    # If catalog resolved a display name to an ID, check bundled again
                    resolved_id = ext_info['id']
                    if resolved_id != extension:
                        bundled_path = _locate_bundled_extension(resolved_id)
                        if bundled_path is not None:
                            manifest = manager.install_from_directory(bundled_path, speckit_version, priority=priority)

                    if bundled_path is None:
                        # Bundled extensions without a download URL must come from the local package
                        if ext_info.get("bundled") and not ext_info.get("download_url"):
                            console.print(
                                f"[red]خطأ:[/red] الامتداد '{ext_info['id']}' مضمّن مع spec-kit "
                                f"لكن لم يتم العثور عليه في الحزمة المثبّتة."
                            )
                            console.print(
                                "\nهذا عادةً يعني أن تثبيت spec-kit غير مكتمل أو تالف."
                            )
                            console.print("حاول إعادة تثبيت spec-kit:")
                            console.print(f"  {REINSTALL_COMMAND}")
                            raise typer.Exit(1)

                        # Enforce install_allowed policy
                        if not ext_info.get("_install_allowed", True):
                            catalog_name = ext_info.get("_catalog_name", "community")
                            console.print(
                                f"[red]خطأ:[/red] '{extension}' متاح في كتالوج "
                                f"'{catalog_name}' لكن التثبيت غير مسموح من ذلك الكتالوج."
                            )
                            console.print(
                                f"\nلتفعيل التثبيت، أضف '{extension}' إلى كتالوج معتمد "
                                f"(install_allowed: true) في .specify/extension-catalogs.yml."
                            )
                            raise typer.Exit(1)

                        # Download extension ZIP (use resolved ID, not original argument which may be display name)
                        extension_id = ext_info['id']
                        console.print(f"تنزيل {ext_info['name']} v{ext_info.get('version', 'unknown')}...")
                        zip_path = catalog.download_extension(extension_id)

                        try:
                            # Install from downloaded ZIP
                            manifest = manager.install_from_zip(zip_path, speckit_version, priority=priority)
                        finally:
                            # Clean up downloaded ZIP
                            if zip_path.exists():
                                zip_path.unlink()

        console.print("\n[green]✓[/green] تم تثبيت الامتداد بنجاح!")
        console.print(f"\n[bold]{manifest.name}[/bold] (v{manifest.version})")
        console.print(f"  {manifest.description}")

        for warning in manifest.warnings:
            console.print(f"\n[yellow]⚠  تحذير توافق:[/yellow] {warning}")

        console.print("\n[bold cyan]الأوامر المقدّمة:[/bold cyan]")
        for cmd in manifest.commands:
            console.print(f"  • {cmd['name']} - {cmd.get('description', '')}")

        # Report agent skills registration
        reg_meta = manager.registry.get(manifest.id)
        reg_skills = reg_meta.get("registered_skills", []) if reg_meta else []
        # Normalize to guard against corrupted registry entries
        if not isinstance(reg_skills, list):
            reg_skills = []
        if reg_skills:
            console.print(f"\n[green]✓[/green] تم تسجيل {len(reg_skills)} مهارة وكيل تلقائياً")

        console.print("\n[yellow]⚠[/yellow]  قد يلزم الإعداد")
        console.print(f"   تحقق من: .specify/extensions/{manifest.id}/")

    except ValidationError as e:
        console.print(f"\n[red]خطأ تحقق:[/red] {e}")
        raise typer.Exit(1)
    except CompatibilityError as e:
        console.print(f"\n[red]خطأ توافق:[/red] {e}")
        raise typer.Exit(1)
    except ExtensionError as e:
        console.print(f"\n[red]خطأ:[/red] {e}")
        raise typer.Exit(1)


@extension_app.command("remove")
def extension_remove(
    extension: str = typer.Argument(help="معرّف الامتداد أو اسمه المراد إزالته"),
    keep_config: bool = typer.Option(False, "--keep-config", help="عدم حذف ملفات الإعدادات"),
    force: bool = typer.Option(False, "--force", help="تخطي التأكيد"),
):
    """إلغاء تثبيت امتداد."""
    from .extensions import ExtensionManager

    project_root = _require_specify_project()
    manager = ExtensionManager(project_root)

    # Resolve extension ID from argument (handles ambiguous names)
    installed = manager.list_installed()
    extension_id, display_name = _resolve_installed_extension(extension, installed, "remove")

    # Get extension info for command and skill counts
    ext_manifest = manager.get_extension(extension_id)
    reg_meta = manager.registry.get(extension_id)
    # Derive cmd_count from the registry's registered_commands (includes aliases)
    # rather than from the manifest (primary commands only). Use max() across
    # agents to get the per-agent count; sum() would double-count since users
    # think in logical commands, not per-agent file counts.
    # Use get() without a default so we can distinguish "key missing" (fall back
    # to manifest) from "key present but empty dict" (zero commands registered).
    registered_commands = reg_meta.get("registered_commands") if isinstance(reg_meta, dict) else None
    if isinstance(registered_commands, dict):
        cmd_count = max(
            (len(v) for v in registered_commands.values() if isinstance(v, list)),
            default=0,
        )
    else:
        cmd_count = len(ext_manifest.commands) if ext_manifest else 0
    raw_skills = reg_meta.get("registered_skills") if reg_meta else None
    skill_count = len(raw_skills) if isinstance(raw_skills, list) else 0

    # Confirm removal
    if not force:
        console.print("\n[yellow]⚠  سيتم حذف:[/yellow]")
        console.print(f"   • {cmd_count} أمر/أوامر لكل وكيل")
        if skill_count:
            console.print(f"   • {skill_count} مهارة وكيل")
        console.print(f"   • مجلد الامتداد: .specify/extensions/{extension_id}/")
        if not keep_config:
            console.print("   • ملفات الإعدادات (سيتم نسخها احتياطياً)")
        console.print()

        confirm = typer.confirm("هل تريد المتابعة؟")
        if not confirm:
            console.print("تم الإلغاء")
            raise typer.Exit(0)

    # Remove extension
    success = manager.remove(extension_id, keep_config=keep_config)

    if success:
        console.print(f"\n[green]✓[/green] تمت إزالة الامتداد '{display_name}' بنجاح")
        if keep_config:
            console.print(f"\nتم الحفاظ على ملفات الإعدادات في .specify/extensions/{extension_id}/")
        else:
            console.print(f"\nتم نسخ ملفات الإعدادات احتياطياً إلى .specify/extensions/.backup/{extension_id}/")
        console.print(f"\nلإعادة التثبيت: specify extension add {extension_id}")
    else:
        console.print("[red]خطأ:[/red] فشل إزالة الامتداد")
        raise typer.Exit(1)


@extension_app.command("search")
def extension_search(
    query: str = typer.Argument(None, help="استعلام البحث (اختياري)"),
    tag: Optional[str] = typer.Option(None, "--tag", help="التصفية حسب الوسم"),
    author: Optional[str] = typer.Option(None, "--author", help="التصفية حسب المؤلف"),
    verified: bool = typer.Option(False, "--verified", help="عرض الامتدادات الموثّقة فقط"),
):
    """البحث عن الامتدادات المتاحة في الكتالوج."""
    from .extensions import ExtensionCatalog, ExtensionError

    project_root = _require_specify_project()
    catalog = ExtensionCatalog(project_root)

    try:
        console.print("🔍 جاري البحث في كتالوج الامتدادات...")
        results = catalog.search(query=query, tag=tag, author=author, verified_only=verified)

        if not results:
            console.print("\n[yellow]لم يُعثر على امتدادات تطابق المعايير[/yellow]")
            if query or tag or author or verified:
                console.print("\nجرّب:")
                console.print("  • مصطلحات بحث أوسع")
                console.print("  • إزالة المرشّحات")
                console.print("  • specify extension search (عرض الكل)")
            raise typer.Exit(0)

        console.print(f"\n[green]تم العثور على {len(results)} امتداد/امتدادات:[/green]\n")

        for ext in results:
            # Extension header
            verified_badge = " [green]✓ موثّق[/green]" if ext.get("verified") else ""
            console.print(f"[bold]{ext['name']}[/bold] (v{ext['version']}){verified_badge}")
            console.print(f"  {ext['description']}")

            # Metadata
            console.print(f"\n  [dim]المؤلف:[/dim] {ext.get('author', 'غير معروف')}")
            if ext.get('tags'):
                tags_str = ", ".join(ext['tags'])
                console.print(f"  [dim]الوسوم:[/dim] {tags_str}")

            # Source catalog
            catalog_name = ext.get("_catalog_name", "")
            install_allowed = ext.get("_install_allowed", True)
            if catalog_name:
                if install_allowed:
                    console.print(f"  [dim]الكتالوج:[/dim] {catalog_name}")
                else:
                    console.print(f"  [dim]الكتالوج:[/dim] {catalog_name} [yellow](للاكتشاف فقط — غير قابل للتثبيت)[/yellow]")

            # Stats
            stats = []
            if ext.get('downloads') is not None:
                stats.append(f"التنزيلات: {ext['downloads']:,}")
            if ext.get('stars') is not None:
                stats.append(f"النجوم: {ext['stars']}")
            if stats:
                console.print(f"  [dim]{' | '.join(stats)}[/dim]")

            # Links
            if ext.get('repository'):
                console.print(f"  [dim]المستودع:[/dim] {ext['repository']}")

            # Install command (show warning if not installable)
            if install_allowed:
                console.print(f"\n  [cyan]للتثبيت:[/cyan] specify extension add {ext['id']}")
            else:
                console.print(f"\n  [yellow]⚠[/yellow]  غير قابل للتثبيت المباشر من '{catalog_name}'.")
                console.print(
                    f"  أضف إلى كتالوج معتمد بـ install_allowed: true، "
                    f"أو ثبّت من رابط ZIP: specify extension add {ext['id']} --from <zip-url>"
                )
            console.print()

    except ExtensionError as e:
        console.print(f"\n[red]خطأ:[/red] {e}")
        console.print("\nتلميح: الكتالوج قد يكون غير متاح مؤقتاً. حاول لاحقاً.")
        raise typer.Exit(1)


@extension_app.command("info")
def extension_info(
    extension: str = typer.Argument(help="معرّف الامتداد أو اسمه"),
):
    """عرض معلومات تفصيلية عن امتداد."""
    from .extensions import ExtensionCatalog, ExtensionManager, normalize_priority

    project_root = _require_specify_project()
    catalog = ExtensionCatalog(project_root)
    manager = ExtensionManager(project_root)
    installed = manager.list_installed()

    # Try to resolve from installed extensions first (by ID or name)
    # Use allow_not_found=True since the extension may be catalog-only
    resolved_installed_id, resolved_installed_name = _resolve_installed_extension(
        extension, installed, "info", allow_not_found=True
    )

    # Try catalog lookup (with error handling)
    # If we resolved an installed extension by display name, use its ID for catalog lookup
    # to ensure we get the correct catalog entry (not a different extension with same name)
    lookup_key = resolved_installed_id if resolved_installed_id else extension
    ext_info, catalog_error = _resolve_catalog_extension(lookup_key, catalog, "info")

    # Case 1: Found in catalog - show full catalog info
    if ext_info:
        _print_extension_info(ext_info, manager)
        return

    # Case 2: Installed locally but catalog lookup failed or not in catalog
    if resolved_installed_id:
        # Get local manifest info
        ext_manifest = manager.get_extension(resolved_installed_id)
        metadata = manager.registry.get(resolved_installed_id)
        metadata_is_dict = isinstance(metadata, dict)
        if not metadata_is_dict:
            console.print(
                "[yellow]تحذير:[/yellow] البيانات الوصفية للامتداد تبدو تالفة؛ "
                "قد لا تتوفّر بعض المعلومات."
            )
        version = metadata.get("version", "unknown") if metadata_is_dict else "unknown"

        console.print(f"\n[bold]{resolved_installed_name}[/bold] (v{version})")
        console.print(f"المعرّف: {resolved_installed_id}")
        console.print()

        if ext_manifest:
            console.print(f"{ext_manifest.description}")
            console.print()
            # Author is optional in extension.yml, safely retrieve it
            author = ext_manifest.data.get("extension", {}).get("author")
            if author:
                console.print(f"[dim]المؤلف:[/dim] {author}")
                console.print()

            if ext_manifest.commands:
                console.print("[bold]الأوامر:[/bold]")
                for cmd in ext_manifest.commands:
                    console.print(f"  • {cmd['name']}: {cmd.get('description', '')}")
                console.print()

        # Show catalog status
        if catalog_error:
            console.print(f"[yellow]الكتالوج غير متاح:[/yellow] {catalog_error}")
            console.print("[dim]ملاحظة: يستخدم الامتداد المثبّت محلياً؛ تعذّر التحقق من معلومات الكتالوج.[/dim]")
        else:
            console.print("[yellow]ملاحظة:[/yellow] غير موجود في الكتالوج (امتداد مخصّص/محلي)")

        console.print()
        console.print("[green]✓ مثبّت[/green]")
        priority = normalize_priority(metadata.get("priority") if metadata_is_dict else None)
        console.print(f"[dim]الأولوية:[/dim] {priority}")
        console.print(f"\nللإزالة: specify extension remove {resolved_installed_id}")
        return

    # Case 3: Not found anywhere
    if catalog_error:
        console.print(f"[red]خطأ:[/red] تعذّر الاستعلام عن كتالوج الامتدادات: {catalog_error}")
        console.print("\nحاول مجدداً عند الاتصال، أو استخدم معرّف الامتداد مباشرة.")
    else:
        console.print(f"[red]خطأ:[/red] الامتداد '{extension}' غير موجود")
        console.print("\nجرّب: specify extension search")
    raise typer.Exit(1)


def _print_extension_info(ext_info: dict, manager):
    """Print formatted extension info from catalog data."""
    from .extensions import normalize_priority

    # Header
    verified_badge = " [green]✓ موثّق[/green]" if ext_info.get("verified") else ""
    console.print(f"\n[bold]{ext_info['name']}[/bold] (v{ext_info['version']}){verified_badge}")
    console.print(f"المعرّف: {ext_info['id']}")
    console.print()

    # Description
    console.print(f"{ext_info['description']}")
    console.print()

    # Author and License
    console.print(f"[dim]المؤلف:[/dim] {ext_info.get('author', 'غير معروف')}")
    console.print(f"[dim]الرخصة:[/dim] {ext_info.get('license', 'غير معروفة')}")

    # Source catalog
    if ext_info.get("_catalog_name"):
        install_allowed = ext_info.get("_install_allowed", True)
        install_note = "" if install_allowed else " [yellow](للاكتشاف فقط)[/yellow]"
        console.print(f"[dim]كتالوج المصدر:[/dim] {ext_info['_catalog_name']}{install_note}")
    console.print()

    # Requirements
    if ext_info.get('requires'):
        console.print("[bold]المتطلبات:[/bold]")
        reqs = ext_info['requires']
        if reqs.get('speckit_version'):
            console.print(f"  • Spec Kit: {reqs['speckit_version']}")
        if reqs.get('tools'):
            for tool in reqs['tools']:
                tool_name = tool['name']
                tool_version = tool.get('version', 'any')
                required = " (مطلوب)" if tool.get('required') else " (اختياري)"
                console.print(f"  • {tool_name}: {tool_version}{required}")
        console.print()

    # Provides
    if ext_info.get('provides'):
        console.print("[bold]يوفّر:[/bold]")
        provides = ext_info['provides']
        if provides.get('commands'):
            console.print(f"  • الأوامر: {provides['commands']}")
        if provides.get('hooks'):
            console.print(f"  • Hooks: {provides['hooks']}")
        console.print()

    # Tags
    if ext_info.get('tags'):
        tags_str = ", ".join(ext_info['tags'])
        console.print(f"[bold]الوسوم:[/bold] {tags_str}")
        console.print()

    # Statistics
    stats = []
    if ext_info.get('downloads') is not None:
        stats.append(f"التنزيلات: {ext_info['downloads']:,}")
    if ext_info.get('stars') is not None:
        stats.append(f"النجوم: {ext_info['stars']}")
    if stats:
        console.print(f"[bold]الإحصائيات:[/bold] {' | '.join(stats)}")
        console.print()

    # Links
    console.print("[bold]الروابط:[/bold]")
    if ext_info.get('repository'):
        console.print(f"  • المستودع: {ext_info['repository']}")
    if ext_info.get('homepage'):
        console.print(f"  • الصفحة الرئيسية: {ext_info['homepage']}")
    if ext_info.get('documentation'):
        console.print(f"  • التوثيق: {ext_info['documentation']}")
    if ext_info.get('changelog'):
        console.print(f"  • سجل التغييرات: {ext_info['changelog']}")
    console.print()

    # Installation status and command
    is_installed = manager.registry.is_installed(ext_info['id'])
    install_allowed = ext_info.get("_install_allowed", True)
    if is_installed:
        console.print("[green]✓ مثبّت[/green]")
        metadata = manager.registry.get(ext_info['id'])
        priority = normalize_priority(metadata.get("priority") if isinstance(metadata, dict) else None)
        console.print(f"[dim]الأولوية:[/dim] {priority}")
        console.print(f"\nللإزالة: specify extension remove {ext_info['id']}")
    elif install_allowed:
        console.print("[yellow]غير مثبّت[/yellow]")
        console.print(f"\n[cyan]للتثبيت:[/cyan] specify extension add {ext_info['id']}")
    else:
        catalog_name = ext_info.get("_catalog_name", "community")
        console.print("[yellow]غير مثبّت[/yellow]")
        console.print(
            f"\n[yellow]⚠[/yellow]  '{ext_info['id']}' متاح في كتالوج '{catalog_name}' "
            f"لكنه ليس في كتالوجك المعتمد. أضفه إلى .specify/extension-catalogs.yml "
            f"بـ install_allowed: true لتفعيل التثبيت."
        )


@extension_app.command("update")
def extension_update(
    extension: str = typer.Argument(None, help="معرّف الامتداد أو اسمه المراد تحديثه (أو الكل)"),
):
    """تحديث الامتدادات إلى أحدث إصدار."""
    from .extensions import (
        ExtensionManager,
        ExtensionCatalog,
        ExtensionError,
        ValidationError,
        CommandRegistrar,
        HookExecutor,
        normalize_priority,
    )
    from packaging import version as pkg_version
    import shutil

    project_root = _require_specify_project()
    manager = ExtensionManager(project_root)
    catalog = ExtensionCatalog(project_root)
    speckit_version = get_speckit_version()

    try:
        # Get list of extensions to update
        installed = manager.list_installed()
        if extension:
            # Update specific extension - resolve ID from argument (handles ambiguous names)
            extension_id, _ = _resolve_installed_extension(extension, installed, "update")
            extensions_to_update = [extension_id]
        else:
            # Update all extensions
            extensions_to_update = [ext["id"] for ext in installed]

        if not extensions_to_update:
            console.print("[yellow]لا توجد امتدادات مثبّتة[/yellow]")
            raise typer.Exit(0)

        console.print("🔄 جاري التحقق من التحديثات...\n")

        updates_available = []

        for ext_id in extensions_to_update:
            # Get installed version
            metadata = manager.registry.get(ext_id)
            if metadata is None or not isinstance(metadata, dict) or "version" not in metadata:
                console.print(f"⚠  {ext_id}: إدخال السجل تالف أو مفقود (تخطّي)")
                continue
            try:
                installed_version = pkg_version.Version(metadata["version"])
            except pkg_version.InvalidVersion:
                console.print(
                    f"⚠  {ext_id}: إصدار مثبّت غير صالح '{metadata.get('version')}' في السجل (تخطّي)"
                )
                continue

            # Get catalog info
            ext_info = catalog.get_extension_info(ext_id)
            if not ext_info:
                console.print(f"⚠  {ext_id}: غير موجود في الكتالوج (تخطّي)")
                continue

            # Check if installation is allowed from this catalog
            if not ext_info.get("_install_allowed", True):
                console.print(f"⚠  {ext_id}: التحديثات غير مسموحة من '{ext_info.get('_catalog_name', 'catalog')}' (تخطّي)")
                continue

            try:
                catalog_version = pkg_version.Version(ext_info["version"])
            except pkg_version.InvalidVersion:
                console.print(
                    f"⚠  {ext_id}: إصدار كتالوج غير صالح '{ext_info.get('version')}' (تخطّي)"
                )
                continue

            if catalog_version > installed_version:
                updates_available.append(
                    {
                        "id": ext_id,
                        "name": ext_info.get("name", ext_id),  # Display name for status messages
                        "installed": str(installed_version),
                        "available": str(catalog_version),
                        "download_url": ext_info.get("download_url"),
                    }
                )
            else:
                console.print(f"✓ {ext_id}: محدّث (v{installed_version})")

        if not updates_available:
            console.print("\n[green]جميع الامتدادات محدّثة![/green]")
            raise typer.Exit(0)

        # Show available updates
        console.print("\n[bold]تحديثات متوفرة:[/bold]\n")
        for update in updates_available:
            console.print(
                f"  • {update['id']}: {update['installed']} → {update['available']}"
            )

        console.print()
        confirm = typer.confirm("تحديث هذه الامتدادات؟")
        if not confirm:
            console.print("تم الإلغاء")
            raise typer.Exit(0)

        # Perform updates with atomic backup/restore
        console.print()
        updated_extensions = []
        failed_updates = []
        registrar = CommandRegistrar()
        hook_executor = HookExecutor(project_root)

        for update in updates_available:
            extension_id = update["id"]
            ext_name = update["name"]  # Use display name for user-facing messages
            console.print(f"📦 جاري تحديث {ext_name}...")

            # Backup paths
            backup_base = manager.extensions_dir / ".backup" / f"{extension_id}-update"
            backup_ext_dir = backup_base / "extension"
            backup_commands_dir = backup_base / "commands"
            backup_config_dir = backup_base / "config"

            # Store backup state
            backup_registry_entry = None
            backup_hooks = None  # None means no hooks key in config; {} means hooks key existed
            backed_up_command_files = {}

            try:
                # 1. Backup registry entry (always, even if extension dir doesn't exist)
                backup_registry_entry = manager.registry.get(extension_id)

                # 2. Backup extension directory
                extension_dir = manager.extensions_dir / extension_id
                if extension_dir.exists():
                    backup_base.mkdir(parents=True, exist_ok=True)
                    if backup_ext_dir.exists():
                        shutil.rmtree(backup_ext_dir)
                    shutil.copytree(extension_dir, backup_ext_dir)

                    # Backup config files separately so they can be restored
                    # after a successful install (install_from_directory clears dest dir).
                    config_files = list(extension_dir.glob("*-config.yml")) + list(
                        extension_dir.glob("*-config.local.yml")
                    )
                    for cfg_file in config_files:
                        backup_config_dir.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(cfg_file, backup_config_dir / cfg_file.name)

                # 3. Backup command files for all agents
                from .agents import CommandRegistrar as _AgentReg
                registered_commands = backup_registry_entry.get("registered_commands", {})
                for agent_name, cmd_names in registered_commands.items():
                    if agent_name not in registrar.AGENT_CONFIGS:
                        continue
                    agent_config = registrar.AGENT_CONFIGS[agent_name]
                    commands_dir = project_root / agent_config["dir"]

                    for cmd_name in cmd_names:
                        output_name = _AgentReg._compute_output_name(agent_name, cmd_name, agent_config)
                        cmd_file = commands_dir / f"{output_name}{agent_config['extension']}"
                        if cmd_file.exists():
                            backup_cmd_path = backup_commands_dir / agent_name / cmd_file.name
                            backup_cmd_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(cmd_file, backup_cmd_path)
                            backed_up_command_files[str(cmd_file)] = str(backup_cmd_path)

                        # Also backup copilot prompt files
                        if agent_name == "copilot":
                            prompt_file = project_root / ".github" / "prompts" / f"{cmd_name}.prompt.md"
                            if prompt_file.exists():
                                backup_prompt_path = backup_commands_dir / "copilot-prompts" / prompt_file.name
                                backup_prompt_path.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(prompt_file, backup_prompt_path)
                                backed_up_command_files[str(prompt_file)] = str(backup_prompt_path)

                # 4. Backup hooks from extensions.yml
                # Use backup_hooks=None to indicate config had no "hooks" key (don't create on restore)
                # Use backup_hooks={} to indicate config had "hooks" key with no hooks for this extension
                config = hook_executor.get_project_config()
                if "hooks" in config:
                    backup_hooks = {}  # Config has hooks key - preserve this fact
                    for hook_name, hook_list in config["hooks"].items():
                        ext_hooks = [h for h in hook_list if h.get("extension") == extension_id]
                        if ext_hooks:
                            backup_hooks[hook_name] = ext_hooks

                # 5. Download new version
                zip_path = catalog.download_extension(extension_id)
                try:
                    # 6. Validate extension ID from ZIP BEFORE modifying installation
                    # Handle both root-level and nested extension.yml (GitHub auto-generated ZIPs)
                    with zipfile.ZipFile(zip_path, "r") as zf:
                        import yaml
                        manifest_data = None
                        namelist = zf.namelist()

                        # First try root-level extension.yml
                        if "extension.yml" in namelist:
                            with zf.open("extension.yml") as f:
                                manifest_data = yaml.safe_load(f) or {}
                        else:
                            # Look for extension.yml in a single top-level subdirectory
                            # (e.g., "repo-name-branch/extension.yml")
                            manifest_paths = [n for n in namelist if n.endswith("/extension.yml") and n.count("/") == 1]
                            if len(manifest_paths) == 1:
                                with zf.open(manifest_paths[0]) as f:
                                    manifest_data = yaml.safe_load(f) or {}

                        if manifest_data is None:
                            raise ValueError("Downloaded extension archive is missing 'extension.yml'")

                    zip_extension_id = manifest_data.get("extension", {}).get("id")
                    if zip_extension_id != extension_id:
                        raise ValueError(
                            f"Extension ID mismatch: expected '{extension_id}', got '{zip_extension_id}'"
                        )

                    # 7. Remove old extension (handles command file cleanup and registry removal)
                    manager.remove(extension_id, keep_config=True)

                    # 8. Install new version
                    _ = manager.install_from_zip(zip_path, speckit_version)

                    # Restore user config files from backup after successful install.
                    new_extension_dir = manager.extensions_dir / extension_id
                    if backup_config_dir.exists() and new_extension_dir.exists():
                        for cfg_file in backup_config_dir.iterdir():
                            if cfg_file.is_file():
                                shutil.copy2(cfg_file, new_extension_dir / cfg_file.name)

                    # 9. Restore metadata from backup (installed_at, enabled state)
                    if backup_registry_entry and isinstance(backup_registry_entry, dict):
                        # Copy current registry entry to avoid mutating internal
                        # registry state before explicit restore().
                        current_metadata = manager.registry.get(extension_id)
                        if current_metadata is None or not isinstance(current_metadata, dict):
                            raise RuntimeError(
                                f"Registry entry for '{extension_id}' missing or corrupted after install — update incomplete"
                            )
                        new_metadata = dict(current_metadata)

                        # Preserve the original installation timestamp
                        if "installed_at" in backup_registry_entry:
                            new_metadata["installed_at"] = backup_registry_entry["installed_at"]

                        # Preserve the original priority (normalized to handle corruption)
                        if "priority" in backup_registry_entry:
                            new_metadata["priority"] = normalize_priority(backup_registry_entry["priority"])

                        # If extension was disabled before update, disable it again
                        if not backup_registry_entry.get("enabled", True):
                            new_metadata["enabled"] = False

                        # Use restore() instead of update() because update() always
                        # preserves the existing installed_at, ignoring our override
                        manager.registry.restore(extension_id, new_metadata)

                        # Also disable hooks in extensions.yml if extension was disabled
                        if not backup_registry_entry.get("enabled", True):
                            config = hook_executor.get_project_config()
                            if "hooks" in config:
                                for hook_name in config["hooks"]:
                                    for hook in config["hooks"][hook_name]:
                                        if hook.get("extension") == extension_id:
                                            hook["enabled"] = False
                                hook_executor.save_project_config(config)
                finally:
                    # Clean up downloaded ZIP
                    if zip_path.exists():
                        zip_path.unlink()

                # 10. Clean up backup on success
                if backup_base.exists():
                    shutil.rmtree(backup_base)

                console.print(f"   [green]✓[/green] تم التحديث إلى v{update['available']}")
                updated_extensions.append(ext_name)

            except KeyboardInterrupt:
                raise
            except Exception as e:
                console.print(f"   [red]✗[/red] فشل: {e}")
                failed_updates.append((ext_name, str(e)))

                # Rollback on failure
                console.print(f"   [yellow]↩[/yellow] جاري التراجع عن {ext_name}...")

                try:
                    # Restore extension directory
                    # Only perform destructive rollback if backup exists (meaning we
                    # actually modified the extension). This avoids deleting a valid
                    # installation when failure happened before changes were made.
                    extension_dir = manager.extensions_dir / extension_id
                    if backup_ext_dir.exists():
                        if extension_dir.exists():
                            shutil.rmtree(extension_dir)
                        shutil.copytree(backup_ext_dir, extension_dir)

                    # Remove any NEW command files created by failed install
                    # (files that weren't in the original backup)
                    try:
                        new_registry_entry = manager.registry.get(extension_id)
                        if new_registry_entry is None or not isinstance(new_registry_entry, dict):
                            new_registered_commands = {}
                        else:
                            new_registered_commands = new_registry_entry.get("registered_commands", {})
                        for agent_name, cmd_names in new_registered_commands.items():
                            if agent_name not in registrar.AGENT_CONFIGS:
                                continue
                            agent_config = registrar.AGENT_CONFIGS[agent_name]
                            commands_dir = project_root / agent_config["dir"]

                            for cmd_name in cmd_names:
                                output_name = _AgentReg._compute_output_name(agent_name, cmd_name, agent_config)
                                cmd_file = commands_dir / f"{output_name}{agent_config['extension']}"
                                # Delete if it exists and wasn't in our backup
                                if cmd_file.exists() and str(cmd_file) not in backed_up_command_files:
                                    cmd_file.unlink()

                                # Also handle copilot prompt files
                                if agent_name == "copilot":
                                    prompt_file = project_root / ".github" / "prompts" / f"{cmd_name}.prompt.md"
                                    if prompt_file.exists() and str(prompt_file) not in backed_up_command_files:
                                        prompt_file.unlink()
                    except KeyError:
                        pass  # No new registry entry exists, nothing to clean up

                    # Restore backed up command files
                    for original_path, backup_path in backed_up_command_files.items():
                        backup_file = Path(backup_path)
                        if backup_file.exists():
                            original_file = Path(original_path)
                            original_file.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(backup_file, original_file)

                    # Restore hooks in extensions.yml
                    # - backup_hooks=None means original config had no "hooks" key
                    # - backup_hooks={} or {...} means config had hooks key
                    config = hook_executor.get_project_config()
                    if "hooks" in config:
                        modified = False

                        if backup_hooks is None:
                            # Original config had no "hooks" key; remove it entirely
                            del config["hooks"]
                            modified = True
                        else:
                            # Remove any hooks for this extension added by failed install
                            for hook_name, hooks_list in config["hooks"].items():
                                original_len = len(hooks_list)
                                config["hooks"][hook_name] = [
                                    h for h in hooks_list
                                    if h.get("extension") != extension_id
                                ]
                                if len(config["hooks"][hook_name]) != original_len:
                                    modified = True

                            # Add back the backed up hooks if any
                            if backup_hooks:
                                for hook_name, hooks in backup_hooks.items():
                                    if hook_name not in config["hooks"]:
                                        config["hooks"][hook_name] = []
                                    config["hooks"][hook_name].extend(hooks)
                                    modified = True

                        if modified:
                            hook_executor.save_project_config(config)

                    # Restore registry entry (use restore() since entry was removed)
                    if backup_registry_entry:
                        manager.registry.restore(extension_id, backup_registry_entry)

                    console.print("   [green]✓[/green] نجح التراجع")
                    # Clean up backup directory only on successful rollback
                    if backup_base.exists():
                        shutil.rmtree(backup_base)
                except Exception as rollback_error:
                    console.print(f"   [red]✗[/red] فشل التراجع: {rollback_error}")
                    console.print(f"   [dim]تم الحفاظ على النسخة الاحتياطية في: {backup_base}[/dim]")

        # Summary
        console.print()
        if updated_extensions:
            console.print(f"[green]✓[/green] تم تحديث {len(updated_extensions)} امتداد/امتدادات بنجاح")
        if failed_updates:
            console.print(f"[red]✗[/red] فشل تحديث {len(failed_updates)} امتداد/امتدادات:")
            for ext_name, error in failed_updates:
                console.print(f"   • {ext_name}: {error}")
            raise typer.Exit(1)

    except ValidationError as e:
        console.print(f"\n[red]خطأ تحقق:[/red] {e}")
        raise typer.Exit(1)
    except ExtensionError as e:
        console.print(f"\n[red]خطأ:[/red] {e}")
        raise typer.Exit(1)


@extension_app.command("enable")
def extension_enable(
    extension: str = typer.Argument(help="معرّف الامتداد أو اسمه المراد تفعيله"),
):
    """تفعيل امتداد معطّل."""
    from .extensions import ExtensionManager, HookExecutor

    project_root = _require_specify_project()
    manager = ExtensionManager(project_root)
    hook_executor = HookExecutor(project_root)

    # Resolve extension ID from argument (handles ambiguous names)
    installed = manager.list_installed()
    extension_id, display_name = _resolve_installed_extension(extension, installed, "enable")

    # Update registry
    metadata = manager.registry.get(extension_id)
    if metadata is None or not isinstance(metadata, dict):
        console.print(f"[red]خطأ:[/red] الامتداد '{extension_id}' غير موجود في السجل (حالة تالفة)")
        raise typer.Exit(1)

    if metadata.get("enabled", True):
        console.print(f"[yellow]الامتداد '{display_name}' مفعّل بالفعل[/yellow]")
        raise typer.Exit(0)

    manager.registry.update(extension_id, {"enabled": True})

    # Enable hooks in extensions.yml
    config = hook_executor.get_project_config()
    if "hooks" in config:
        for hook_name in config["hooks"]:
            for hook in config["hooks"][hook_name]:
                if hook.get("extension") == extension_id:
                    hook["enabled"] = True
        hook_executor.save_project_config(config)

    console.print(f"[green]✓[/green] تم تفعيل الامتداد '{display_name}'")


@extension_app.command("disable")
def extension_disable(
    extension: str = typer.Argument(help="معرّف الامتداد أو اسمه المراد تعطيله"),
):
    """تعطيل امتداد دون إزالته."""
    from .extensions import ExtensionManager, HookExecutor

    project_root = _require_specify_project()
    manager = ExtensionManager(project_root)
    hook_executor = HookExecutor(project_root)

    # Resolve extension ID from argument (handles ambiguous names)
    installed = manager.list_installed()
    extension_id, display_name = _resolve_installed_extension(extension, installed, "disable")

    # Update registry
    metadata = manager.registry.get(extension_id)
    if metadata is None or not isinstance(metadata, dict):
        console.print(f"[red]خطأ:[/red] الامتداد '{extension_id}' غير موجود في السجل (حالة تالفة)")
        raise typer.Exit(1)

    if not metadata.get("enabled", True):
        console.print(f"[yellow]الامتداد '{display_name}' معطّل بالفعل[/yellow]")
        raise typer.Exit(0)

    manager.registry.update(extension_id, {"enabled": False})

    # Disable hooks in extensions.yml
    config = hook_executor.get_project_config()
    if "hooks" in config:
        for hook_name in config["hooks"]:
            for hook in config["hooks"][hook_name]:
                if hook.get("extension") == extension_id:
                    hook["enabled"] = False
        hook_executor.save_project_config(config)

    console.print(f"[green]✓[/green] تم تعطيل الامتداد '{display_name}'")
    console.print("\nلن تكون الأوامر متاحة. لن تنفّذ الـ Hooks.")
    console.print(f"لإعادة التفعيل: specify extension enable {extension_id}")


@extension_app.command("set-priority")
def extension_set_priority(
    extension: str = typer.Argument(help="معرّف الامتداد أو اسمه"),
    priority: int = typer.Argument(help="الأولوية الجديدة (أقل = أعلى أولوية)"),
):
    """تعيين أولوية الحل لامتداد مثبّت."""
    from .extensions import ExtensionManager

    project_root = _require_specify_project()
    # Validate priority
    if priority < 1:
        console.print("[red]خطأ:[/red] الأولوية يجب أن تكون عدداً صحيحاً موجباً (1 أو أعلى)")
        raise typer.Exit(1)

    manager = ExtensionManager(project_root)

    # Resolve extension ID from argument (handles ambiguous names)
    installed = manager.list_installed()
    extension_id, display_name = _resolve_installed_extension(extension, installed, "set-priority")

    # Get current metadata
    metadata = manager.registry.get(extension_id)
    if metadata is None or not isinstance(metadata, dict):
        console.print(f"[red]خطأ:[/red] الامتداد '{extension_id}' غير موجود في السجل (حالة تالفة)")
        raise typer.Exit(1)

    from .extensions import normalize_priority
    raw_priority = metadata.get("priority")
    # Only skip if the stored value is already a valid int equal to requested priority
    # This ensures corrupted values (e.g., "high") get repaired even when setting to default (10)
    if isinstance(raw_priority, int) and raw_priority == priority:
        console.print(f"[yellow]الامتداد '{display_name}' له بالفعل أولوية {priority}[/yellow]")
        raise typer.Exit(0)

    old_priority = normalize_priority(raw_priority)

    # Update priority
    manager.registry.update(extension_id, {"priority": priority})

    console.print(f"[green]✓[/green] تم تغيير أولوية الامتداد '{display_name}': {old_priority} → {priority}")
    console.print("\n[dim]أولوية أقل = أعلى أسبقية في حل القوالب[/dim]")


# ===== Workflow Commands =====

workflow_app = typer.Typer(
    name="workflow",
    help="إدارة وتشغيل سير عمل الأتمتة",
    add_completion=False,
)
app.add_typer(workflow_app, name="workflow")

workflow_catalog_app = typer.Typer(
    name="catalog",
    help="إدارة كتالوجات سير العمل",
    add_completion=False,
)
workflow_app.add_typer(workflow_catalog_app, name="catalog")


@workflow_app.command("run")
def workflow_run(
    source: str = typer.Argument(..., help="معرّف سير العمل أو مسار ملف YAML"),
    input_values: list[str] | None = typer.Option(
        None, "--input", "-i", help="قيم الإدخال كأزواج key=value"
    ),
):
    """تشغيل سير عمل من معرّف مثبّت أو مسار YAML محلي."""
    from .workflows.engine import WorkflowEngine

    project_root = _require_specify_project()
    engine = WorkflowEngine(project_root)
    engine.on_step_start = lambda sid, label: console.print(f"  \u25b8 [{sid}] {label} \u2026")

    try:
        definition = engine.load_workflow(source)
    except FileNotFoundError:
        console.print(f"[red]خطأ:[/red] سير العمل غير موجود: {source}")
        raise typer.Exit(1)
    except ValueError as exc:
        console.print(f"[red]خطأ:[/red] سير عمل غير صالح: {exc}")
        raise typer.Exit(1)

    # Validate
    errors = engine.validate(definition)
    if errors:
        console.print("[red]فشل التحقق من سير العمل:[/red]")
        for err in errors:
            console.print(f"  • {err}")
        raise typer.Exit(1)

    # Parse inputs
    inputs: dict[str, Any] = {}
    if input_values:
        for kv in input_values:
            if "=" not in kv:
                console.print(f"[red]خطأ:[/red] صيغة إدخال غير صالحة: {kv!r} (المتوقع key=value)")
                raise typer.Exit(1)
            key, _, value = kv.partition("=")
            inputs[key.strip()] = value.strip()

    console.print(f"\n[bold cyan]تشغيل سير العمل:[/bold cyan] {definition.name} ({definition.id})")
    console.print(f"[dim]الإصدار: {definition.version}[/dim]\n")

    try:
        state = engine.execute(definition, inputs)
    except ValueError as exc:
        console.print(f"[red]خطأ:[/red] {exc}")
        raise typer.Exit(1)
    except Exception as exc:
        console.print(f"[red]فشل سير العمل:[/red] {exc}")
        raise typer.Exit(1)

    status_colors = {
        "completed": "green",
        "paused": "yellow",
        "failed": "red",
        "aborted": "red",
    }
    color = status_colors.get(state.status.value, "white")
    console.print(f"\n[{color}]الحالة: {state.status.value}[/{color}]")
    console.print(f"[dim]معرّف التشغيل: {state.run_id}[/dim]")

    if state.status.value == "paused":
        console.print(f"\nاستأنف بـ: [cyan]specify workflow resume {state.run_id}[/cyan]")


@workflow_app.command("resume")
def workflow_resume(
    run_id: str = typer.Argument(..., help="معرّف التشغيل المراد استئنافه"),
):
    """استئناف تشغيل سير عمل متوقف مؤقتاً أو فاشل."""
    from .workflows.engine import WorkflowEngine

    project_root = _require_specify_project()
    engine = WorkflowEngine(project_root)
    engine.on_step_start = lambda sid, label: console.print(f"  \u25b8 [{sid}] {label} \u2026")

    try:
        state = engine.resume(run_id)
    except FileNotFoundError:
        console.print(f"[red]خطأ:[/red] التشغيل غير موجود: {run_id}")
        raise typer.Exit(1)
    except ValueError as exc:
        console.print(f"[red]خطأ:[/red] {exc}")
        raise typer.Exit(1)
    except Exception as exc:
        console.print(f"[red]فشل الاستئناف:[/red] {exc}")
        raise typer.Exit(1)

    status_colors = {
        "completed": "green",
        "paused": "yellow",
        "failed": "red",
        "aborted": "red",
    }
    color = status_colors.get(state.status.value, "white")
    console.print(f"\n[{color}]الحالة: {state.status.value}[/{color}]")


@workflow_app.command("status")
def workflow_status(
    run_id: str | None = typer.Argument(None, help="معرّف التشغيل للفحص (يعرض الكل إذا أُهمل)"),
):
    """عرض حالة تشغيل سير العمل."""
    from .workflows.engine import WorkflowEngine

    project_root = _require_specify_project()
    engine = WorkflowEngine(project_root)

    if run_id:
        try:
            from .workflows.engine import RunState
            state = RunState.load(run_id, project_root)
        except FileNotFoundError:
            console.print(f"[red]خطأ:[/red] التشغيل غير موجود: {run_id}")
            raise typer.Exit(1)

        status_colors = {
            "completed": "green",
            "paused": "yellow",
            "failed": "red",
            "aborted": "red",
            "running": "blue",
            "created": "dim",
        }
        color = status_colors.get(state.status.value, "white")

        console.print(f"\n[bold cyan]تشغيل سير العمل: {state.run_id}[/bold cyan]")
        console.print(f"  سير العمل: {state.workflow_id}")
        console.print(f"  الحالة:   [{color}]{state.status.value}[/{color}]")
        console.print(f"  تم الإنشاء:  {state.created_at}")
        console.print(f"  آخر تحديث:  {state.updated_at}")

        if state.current_step_id:
            console.print(f"  الحالي:  {state.current_step_id}")

        if state.step_results:
            console.print(f"\n  [bold]الخطوات ({len(state.step_results)}):[/bold]")
            for step_id, step_data in state.step_results.items():
                s = step_data.get("status", "unknown")
                sc = {"completed": "green", "failed": "red", "paused": "yellow"}.get(s, "white")
                console.print(f"    [{sc}]●[/{sc}] {step_id}: {s}")
    else:
        runs = engine.list_runs()
        if not runs:
            console.print("[yellow]لم يُعثر على عمليات تشغيل لسير العمل.[/yellow]")
            return

        console.print("\n[bold cyan]عمليات تشغيل سير العمل:[/bold cyan]\n")
        for run_data in runs:
            s = run_data.get("status", "unknown")
            sc = {"completed": "green", "failed": "red", "paused": "yellow", "running": "blue"}.get(s, "white")
            console.print(
                f"  [{sc}]●[/{sc}] {run_data['run_id']}  "
                f"{run_data.get('workflow_id', '?')}  "
                f"[{sc}]{s}[/{sc}]  "
                f"[dim]{run_data.get('updated_at', '?')}[/dim]"
            )


@workflow_app.command("list")
def workflow_list():
    """عرض سير العمل المثبّت."""
    from .workflows.catalog import WorkflowRegistry

    project_root = _require_specify_project()
    registry = WorkflowRegistry(project_root)
    installed = registry.list()

    if not installed:
        console.print("[yellow]لا يوجد سير عمل مثبّت.[/yellow]")
        console.print("\nثبّت سير عمل بـ:")
        console.print("  [cyan]specify workflow add <workflow-id>[/cyan]")
        return

    console.print("\n[bold cyan]سير العمل المثبّت:[/bold cyan]\n")
    for wf_id, wf_data in installed.items():
        console.print(f"  [bold]{wf_data.get('name', wf_id)}[/bold] ({wf_id}) v{wf_data.get('version', '?')}")
        desc = wf_data.get("description", "")
        if desc:
            console.print(f"    {desc}")
        console.print()


@workflow_app.command("add")
def workflow_add(
    source: str = typer.Argument(..., help="معرّف سير العمل، رابط، أو مسار محلي"),
):
    """تثبيت سير عمل من الكتالوج، رابط، أو مسار محلي."""
    from .workflows.catalog import WorkflowCatalog, WorkflowRegistry, WorkflowCatalogError
    from .workflows.engine import WorkflowDefinition

    project_root = _require_specify_project()
    registry = WorkflowRegistry(project_root)
    workflows_dir = project_root / ".specify" / "workflows"

    def _validate_and_install_local(yaml_path: Path, source_label: str) -> None:
        """Validate and install a workflow from a local YAML file."""
        try:
            definition = WorkflowDefinition.from_yaml(yaml_path)
        except (ValueError, yaml.YAMLError) as exc:
            console.print(f"[red]\u062e\u0637\u0623:[/red] YAML \u0633\u064a\u0631 \u0639\u0645\u0644 \u063a\u064a\u0631 \u0635\u0627\u0644\u062d: {exc}")
            raise typer.Exit(1)
        if not definition.id or not definition.id.strip():
            console.print("[red]\u062e\u0637\u0623:[/red] \u062a\u0639\u0631\u064a\u0641 \u0633\u064a\u0631 \u0627\u0644\u0639\u0645\u0644 \u064a\u062d\u062a\u0648\u064a \u0639\u0644\u0649 'id' \u0641\u0627\u0631\u063a \u0623\u0648 \u0645\u0641\u0642\u0648\u062f")
            raise typer.Exit(1)

        from .workflows.engine import validate_workflow
        errors = validate_workflow(definition)
        if errors:
            console.print("[red]\u062e\u0637\u0623:[/red] \u0641\u0634\u0644 \u0627\u0644\u062a\u062d\u0642\u0642 \u0645\u0646 \u0633\u064a\u0631 \u0627\u0644\u0639\u0645\u0644:")
            for err in errors:
                console.print(f"  \u2022 {err}")
            raise typer.Exit(1)

        dest_dir = workflows_dir / definition.id
        dest_dir.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(yaml_path, dest_dir / "workflow.yml")
        registry.add(definition.id, {
            "name": definition.name,
            "version": definition.version,
            "description": definition.description,
            "source": source_label,
        })
        console.print(f"[green]✓[/green] تم تثبيت سير العمل '{definition.name}' ({definition.id})")

    # Try as URL (http/https)
    if source.startswith("http://") or source.startswith("https://"):
        from ipaddress import ip_address
        from urllib.parse import urlparse
        from urllib.request import urlopen  # noqa: S310

        parsed_src = urlparse(source)
        src_host = parsed_src.hostname or ""
        src_loopback = src_host == "localhost"
        if not src_loopback:
            try:
                src_loopback = ip_address(src_host).is_loopback
            except ValueError:
                # Host is not an IP literal (e.g., a DNS name); keep default non-loopback.
                pass
        if parsed_src.scheme != "https" and not (parsed_src.scheme == "http" and src_loopback):
            console.print("[red]خطأ:[/red] فقط روابط HTTPS مسموحة، باستثناء HTTP للـ localhost.")
            raise typer.Exit(1)

        import tempfile
        try:
            with urlopen(source, timeout=30) as resp:  # noqa: S310
                final_url = resp.geturl()
                final_parsed = urlparse(final_url)
                final_host = final_parsed.hostname or ""
                final_lb = final_host == "localhost"
                if not final_lb:
                    try:
                        final_lb = ip_address(final_host).is_loopback
                    except ValueError:
                        # Redirect host is not an IP literal; keep loopback as determined above.
                        pass
                if final_parsed.scheme != "https" and not (final_parsed.scheme == "http" and final_lb):
                    console.print(f"[red]خطأ:[/red] الرابط أعيد توجيهه إلى غير HTTPS: {final_url}")
                    raise typer.Exit(1)
                with tempfile.NamedTemporaryFile(suffix=".yml", delete=False) as tmp:
                    tmp.write(resp.read())
                    tmp_path = Path(tmp.name)
        except typer.Exit:
            raise
        except Exception as exc:
            console.print(f"[red]خطأ:[/red] فشل تنزيل سير العمل: {exc}")
            raise typer.Exit(1)
        try:
            _validate_and_install_local(tmp_path, source)
        finally:
            tmp_path.unlink(missing_ok=True)
        return

    # Try as a local file/directory
    source_path = Path(source)
    if source_path.exists():
        if source_path.is_file() and source_path.suffix in (".yml", ".yaml"):
            _validate_and_install_local(source_path, str(source_path))
            return
        elif source_path.is_dir():
            wf_file = source_path / "workflow.yml"
            if not wf_file.exists():
                console.print(f"[red]خطأ:[/red] لم يُعثر على workflow.yml في {source}")
                raise typer.Exit(1)
            _validate_and_install_local(wf_file, str(source_path))
            return

    # Try from catalog
    catalog = WorkflowCatalog(project_root)
    try:
        info = catalog.get_workflow_info(source)
    except WorkflowCatalogError as exc:
        console.print(f"[red]خطأ:[/red] {exc}")
        raise typer.Exit(1)

    if not info:
        console.print(f"[red]خطأ:[/red] سير العمل '{source}' غير موجود في الكتالوج")
        raise typer.Exit(1)

    if not info.get("_install_allowed", True):
        console.print(f"[yellow]تحذير:[/yellow] سير العمل '{source}' من كتالوج للاكتشاف فقط")
        console.print("التثبيت المباشر غير مفعّل لمصدر هذا الكتالوج.")
        raise typer.Exit(1)

    workflow_url = info.get("url")
    if not workflow_url:
        console.print(f"[red]خطأ:[/red] سير العمل '{source}' ليس له رابط تثبيت في الكتالوج")
        raise typer.Exit(1)

    # Validate URL scheme (HTTPS required, HTTP allowed for localhost only)
    from ipaddress import ip_address
    from urllib.parse import urlparse

    parsed_url = urlparse(workflow_url)
    url_host = parsed_url.hostname or ""
    is_loopback = False
    if url_host == "localhost":
        is_loopback = True
    else:
        try:
            is_loopback = ip_address(url_host).is_loopback
        except ValueError:
            # Host is not an IP literal (e.g., a regular hostname); treat as non-loopback.
            pass
    if parsed_url.scheme != "https" and not (parsed_url.scheme == "http" and is_loopback):
        console.print(
            f"[red]خطأ:[/red] سير العمل '{source}' له رابط تثبيت غير صالح. "
            "فقط روابط HTTPS مسموحة، باستثناء HTTP للـ localhost/loopback."
        )
        raise typer.Exit(1)

    workflow_dir = workflows_dir / source
    # Validate that source is a safe directory name (no path traversal)
    try:
        workflow_dir.resolve().relative_to(workflows_dir.resolve())
    except ValueError:
        console.print(f"[red]خطأ:[/red] معرّف سير عمل غير صالح: {source!r}")
        raise typer.Exit(1)
    workflow_file = workflow_dir / "workflow.yml"

    try:
        from urllib.request import urlopen  # noqa: S310 — URL comes from catalog

        workflow_dir.mkdir(parents=True, exist_ok=True)
        with urlopen(workflow_url, timeout=30) as response:  # noqa: S310
            # Validate final URL after redirects
            final_url = response.geturl()
            final_parsed = urlparse(final_url)
            final_host = final_parsed.hostname or ""
            final_loopback = final_host == "localhost"
            if not final_loopback:
                try:
                    final_loopback = ip_address(final_host).is_loopback
                except ValueError:
                    # Host is not an IP literal (e.g., a regular hostname); treat as non-loopback.
                    pass
            if final_parsed.scheme != "https" and not (final_parsed.scheme == "http" and final_loopback):
                if workflow_dir.exists():
                    import shutil
                    shutil.rmtree(workflow_dir, ignore_errors=True)
                console.print(
                    f"[red]خطأ:[/red] سير العمل '{source}' أعيد توجيهه إلى رابط غير HTTPS: {final_url}"
                )
                raise typer.Exit(1)
            workflow_file.write_bytes(response.read())
    except Exception as exc:
        if workflow_dir.exists():
            import shutil
            shutil.rmtree(workflow_dir, ignore_errors=True)
        console.print(f"[red]\u062e\u0637\u0623:[/red] \u0641\u0634\u0644 \u062a\u062b\u0628\u064a\u062a \u0633\u064a\u0631 \u0627\u0644\u0639\u0645\u0644 '{source}' \u0645\u0646 \u0627\u0644\u0643\u062a\u0627\u0644\u0648\u062c: {exc}")
        raise typer.Exit(1)

    # Validate the downloaded workflow before registering
    try:
        definition = WorkflowDefinition.from_yaml(workflow_file)
    except (ValueError, yaml.YAMLError) as exc:
        import shutil
        shutil.rmtree(workflow_dir, ignore_errors=True)
        console.print(f"[red]\u062e\u0637\u0623:[/red] \u0633\u064a\u0631 \u0627\u0644\u0639\u0645\u0644 \u0627\u0644\u0645\u0646\u0632\u0651\u0644 \u063a\u064a\u0631 \u0635\u0627\u0644\u062d: {exc}")
        raise typer.Exit(1)

    from .workflows.engine import validate_workflow
    errors = validate_workflow(definition)
    if errors:
        import shutil
        shutil.rmtree(workflow_dir, ignore_errors=True)
        console.print("[red]\u062e\u0637\u0623:[/red] \u0641\u0634\u0644 \u0627\u0644\u062a\u062d\u0642\u0642 \u0645\u0646 \u0633\u064a\u0631 \u0627\u0644\u0639\u0645\u0644 \u0627\u0644\u0645\u0646\u0632\u0651\u0644:")
        for err in errors:
            console.print(f"  \u2022 {err}")
        raise typer.Exit(1)

    # Enforce that the workflow's internal ID matches the catalog key
    if definition.id and definition.id != source:
        import shutil
        shutil.rmtree(workflow_dir, ignore_errors=True)
        console.print(
            f"[red]\u062e\u0637\u0623:[/red] \u0645\u0639\u0631\u0651\u0641 \u0633\u064a\u0631 \u0627\u0644\u0639\u0645\u0644 \u0641\u064a YAML ({definition.id!r}) "
            f"\u0644\u0627 \u064a\u0637\u0627\u0628\u0642 \u0645\u0641\u062a\u0627\u062d \u0627\u0644\u0643\u062a\u0627\u0644\u0648\u062c ({source!r}). "
            f"\u0642\u062f \u064a\u0643\u0648\u0646 \u0625\u062f\u062e\u0627\u0644 \u0627\u0644\u0643\u062a\u0627\u0644\u0648\u062c \u0645\u0639\u062f\u0651\u0627\u064b \u0628\u0634\u0643\u0644 \u062e\u0627\u0637\u0626."
        )
        raise typer.Exit(1)

    registry.add(source, {
        "name": definition.name or info.get("name", source),
        "version": definition.version or info.get("version", "0.0.0"),
        "description": definition.description or info.get("description", ""),
        "source": "catalog",
        "catalog_name": info.get("_catalog_name", ""),
        "url": workflow_url,
    })
    console.print(f"[green]✓[/green] تم تثبيت سير العمل '{info.get('name', source)}' من الكتالوج")


@workflow_app.command("remove")
def workflow_remove(
    workflow_id: str = typer.Argument(..., help="معرّف سير العمل المراد إلغاء تثبيته"),
):
    """إلغاء تثبيت سير عمل."""
    from .workflows.catalog import WorkflowRegistry

    project_root = _require_specify_project()
    registry = WorkflowRegistry(project_root)

    if not registry.is_installed(workflow_id):
        console.print(f"[red]خطأ:[/red] سير العمل '{workflow_id}' غير مثبّت")
        raise typer.Exit(1)

    # Remove workflow files
    workflow_dir = project_root / ".specify" / "workflows" / workflow_id
    if workflow_dir.exists():
        import shutil
        shutil.rmtree(workflow_dir)

    registry.remove(workflow_id)
    console.print(f"[green]✓[/green] تمت إزالة سير العمل '{workflow_id}'")


@workflow_app.command("search")
def workflow_search(
    query: str | None = typer.Argument(None, help="استعلام البحث"),
    tag: str | None = typer.Option(None, "--tag", help="التصفية حسب الوسم"),
):
    """البحث في كتالوجات سير العمل."""
    from .workflows.catalog import WorkflowCatalog, WorkflowCatalogError

    project_root = _require_specify_project()
    catalog = WorkflowCatalog(project_root)

    try:
        results = catalog.search(query=query, tag=tag)
    except WorkflowCatalogError as exc:
        console.print(f"[red]خطأ:[/red] {exc}")
        raise typer.Exit(1)

    if not results:
        console.print("[yellow]لم يُعثر على سير عمل.[/yellow]")
        return

    console.print(f"\n[bold cyan]سير العمل ({len(results)}):[/bold cyan]\n")
    for wf in results:
        console.print(f"  [bold]{wf.get('name', wf.get('id', '?'))}[/bold] ({wf.get('id', '?')}) v{wf.get('version', '?')}")
        desc = wf.get("description", "")
        if desc:
            console.print(f"    {desc}")
        tags = wf.get("tags", [])
        if tags:
            console.print(f"    [dim]الوسوم: {', '.join(tags)}[/dim]")
        console.print()


@workflow_app.command("info")
def workflow_info(
    workflow_id: str = typer.Argument(..., help="معرّف سير العمل"),
):
    """عرض تفاصيل سير العمل ومخطط الخطوات."""
    from .workflows.catalog import WorkflowCatalog, WorkflowRegistry, WorkflowCatalogError
    from .workflows.engine import WorkflowEngine

    project_root = _require_specify_project()

    # Check installed first
    registry = WorkflowRegistry(project_root)
    installed = registry.get(workflow_id)

    engine = WorkflowEngine(project_root)

    definition = None
    try:
        definition = engine.load_workflow(workflow_id)
    except FileNotFoundError:
        # Local workflow definition not found on disk; fall back to
        # catalog/registry lookup below.
        pass

    if definition:
        console.print(f"\n[bold cyan]{definition.name}[/bold cyan] ({definition.id})")
        console.print(f"  الإصدار:     {definition.version}")
        if definition.author:
            console.print(f"  المؤلف:      {definition.author}")
        if definition.description:
            console.print(f"  الوصف:      {definition.description}")
        if definition.default_integration:
            console.print(f"  التكامل: {definition.default_integration}")
        if installed:
            console.print("  [green]مثبّت[/green]")

        if definition.inputs:
            console.print("\n  [bold]المدخلات:[/bold]")
            for name, inp in definition.inputs.items():
                if isinstance(inp, dict):
                    req = "مطلوب" if inp.get("required") else "اختياري"
                    console.print(f"    {name} ({inp.get('type', 'string')}) — {req}")

        if definition.steps:
            console.print(f"\n  [bold]الخطوات ({len(definition.steps)}):[/bold]")
            for step in definition.steps:
                stype = step.get("type", "command")
                console.print(f"    → {step.get('id', '?')} [{stype}]")
        return

    # Try catalog
    catalog = WorkflowCatalog(project_root)
    try:
        info = catalog.get_workflow_info(workflow_id)
    except WorkflowCatalogError:
        info = None

    if info:
        console.print(f"\n[bold cyan]{info.get('name', workflow_id)}[/bold cyan] ({workflow_id})")
        console.print(f"  الإصدار:     {info.get('version', '?')}")
        if info.get("description"):
            console.print(f"  الوصف: {info['description']}")
        if info.get("tags"):
            console.print(f"  الوسوم:        {', '.join(info['tags'])}")
        console.print("  [yellow]غير مثبّت[/yellow]")
    else:
        console.print(f"[red]خطأ:[/red] سير العمل '{workflow_id}' غير موجود")
        raise typer.Exit(1)


@workflow_catalog_app.command("list")
def workflow_catalog_list():
    """عرض مصادر كتالوج سير العمل المُعدّة."""
    from .workflows.catalog import WorkflowCatalog, WorkflowCatalogError

    project_root = Path.cwd()
    catalog = WorkflowCatalog(project_root)

    try:
        configs = catalog.get_catalog_configs()
    except WorkflowCatalogError as exc:
        console.print(f"[red]خطأ:[/red] {exc}")
        raise typer.Exit(1)

    console.print("\n[bold cyan]مصادر كتالوج سير العمل:[/bold cyan]\n")
    for i, cfg in enumerate(configs):
        install_status = "[green]التثبيت مسموح[/green]" if cfg["install_allowed"] else "[yellow]للاكتشاف فقط[/yellow]"
        console.print(f"  [{i}] [bold]{cfg['name']}[/bold] — {install_status}")
        console.print(f"      {cfg['url']}")
        if cfg.get("description"):
            console.print(f"      [dim]{cfg['description']}[/dim]")
        console.print()


@workflow_catalog_app.command("add")
def workflow_catalog_add(
    url: str = typer.Argument(..., help="رابط الكتالوج المراد إضافته"),
    name: str = typer.Option(None, "--name", help="اسم الكتالوج"),
):
    """إضافة مصدر كتالوج سير عمل."""
    from .workflows.catalog import WorkflowCatalog, WorkflowValidationError

    project_root = _require_specify_project()
    catalog = WorkflowCatalog(project_root)
    try:
        catalog.add_catalog(url, name)
    except WorkflowValidationError as exc:
        console.print(f"[red]خطأ:[/red] {exc}")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] تمت إضافة مصدر الكتالوج: {url}")


@workflow_catalog_app.command("remove")
def workflow_catalog_remove(
    index: int = typer.Argument(..., help="فهرس الكتالوج المراد إزالته (من 'catalog list')"),
):
    """إزالة مصدر كتالوج سير عمل بواسطة الفهرس."""
    from .workflows.catalog import WorkflowCatalog, WorkflowValidationError

    project_root = _require_specify_project()
    catalog = WorkflowCatalog(project_root)
    try:
        removed_name = catalog.remove_catalog(index)
    except WorkflowValidationError as exc:
        console.print(f"[red]خطأ:[/red] {exc}")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] تمت إزالة مصدر الكتالوج '{removed_name}'")


def main():
    app()

if __name__ == "__main__":
    main()
