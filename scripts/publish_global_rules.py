from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from orchestrator_common import approved_file_path, sha256_file, utc_now
from synthesize_top_level_instructions import (
    AGENT_REGISTRATIONS,
    CODEX_HOME,
    CURSOR_HOME,
    OPTIMIZED_SKILLS,
    REPO_ROOT,
    UI_AGENT,
    UI_SKILL,
    UI_SKILL_FILES,
    insert_key_in_table,
    read_toml_text,
    synthesize,
    synthesize_ui_design,
)


TARGET_PARENT_MODEL = "gpt-5.6-sol"
TARGET_PARENT_REASONING_EFFORT = "high"
OPTIMIZED_SKILL_PACKAGES = {
    **{name: ("SKILL.md",) for name in OPTIMIZED_SKILLS},
    "humanize-text": (
        "SKILL.md",
        "references/domain-profiles.md",
        "references/pattern-catalog.md",
        "scripts/audit_prose.py",
    ),
}


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def copy_tree_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def publication_targets(master_root: Path, codex_home: Path, cursor_home: Path) -> list[tuple[Path, Path, str]]:
    targets: list[tuple[Path, Path, str]] = [
        (master_root / "codex" / "AGENTS.md", codex_home / "AGENTS.md", "codex/AGENTS.md"),
        (master_root / "codex" / "skills.md", codex_home / "skills.md", "codex/skills.md"),
        (master_root / "codex" / "config.toml", codex_home / "config.toml", "codex/config.toml"),
    ]
    for source in sorted((master_root / "codex" / "agents").glob("*.toml")):
        targets.append((source, codex_home / "agents" / source.name, f"codex/agents/{source.name}"))
    for source in sorted((master_root / "cursor" / "rules").glob("*.mdc")):
        targets.append((source, cursor_home / "rules" / source.name, f"cursor/rules/{source.name}"))
    skill_source = master_root / "cursor" / "skills" / "orchestrator-knowledge" / "SKILL.md"
    targets.append(
        (
            skill_source,
            cursor_home / "skills" / "orchestrator-knowledge" / "SKILL.md",
            "cursor/skills/orchestrator-knowledge/SKILL.md",
        )
    )
    return targets


def optimized_file_targets(master_root: Path, codex_home: Path, cursor_home: Path) -> list[tuple[Path, Path, str]]:
    optimized_root = master_root / "optimized"
    targets: list[tuple[Path, Path, str]] = [
        (optimized_root / "codex" / "AGENTS.md", codex_home / "AGENTS.md", "codex/AGENTS.md"),
        (optimized_root / "codex" / "skills-index.md", codex_home / "skills.md", "codex/skills.md"),
    ]
    targets.extend(row for row in agent_only_targets(master_root, codex_home) if row[0].stem != UI_AGENT)
    for name, files in sorted(OPTIMIZED_SKILL_PACKAGES.items()):
        for file in files:
            relative = f"skills/{name}/{file}"
            source = approved_file_path(master_root, f"optimized/agents/{relative}")
            for client, home in (("codex", codex_home), ("cursor", cursor_home)):
                targets.append((source, approved_file_path(home, relative), f"{client}/{relative}"))
    targets.extend(ui_design_targets(master_root, codex_home))
    for source in sorted((optimized_root / "cursor" / "rules").glob("*.mdc")):
        targets.append((source, cursor_home / "rules" / source.name, f"cursor/rules/{source.name}"))
    return targets


def ui_design_targets(master_root: Path, codex_home: Path) -> list[tuple[Path, Path, str]]:
    registration = AGENT_REGISTRATIONS[UI_AGENT]["config_file"]
    targets = [
        (approved_file_path(master_root, f"optimized/codex/{registration}"),
         approved_file_path(codex_home, registration), f"codex/{registration}"),
    ]
    for file in UI_SKILL_FILES:
        relative = f"skills/{UI_SKILL}/{file}"
        targets.append((approved_file_path(master_root, f"optimized/agents/{relative}"),
                        approved_file_path(codex_home, relative), f"codex/{relative}"))
    return targets


def package_file_plan(targets: list[tuple[Path, Path, str]]) -> list[dict[str, str | None]]:
    validate_master_targets(targets)
    names: set[str] = set()
    plan = []
    for source, target, label in targets:
        key = str(target.resolve()).casefold()
        if key in names or source.resolve() == target.resolve():
            raise RuntimeError(f"Publication path collision at {target}")
        names.add(key)
        source_hash = sha256_file(source)
        target_hash = sha256_file(target) if target.exists() else None
        if target_hash is not None and target_hash != source_hash:
            raise RuntimeError(f"Refusing to overwrite differing publication file: {target}")
        plan.append({"label": label, "source_hash": source_hash, "target_hash": target_hash})
    return plan


def agent_only_targets(master_root: Path, codex_home: Path) -> list[tuple[Path, Path, str]]:
    source_dir = master_root / "optimized" / "codex" / "agents"
    return [
        (source, codex_home / "agents" / source.name, f"codex/agents/{source.name}")
        for source in sorted(source_dir.glob("*.toml"))
    ]


def validate_agent_only_sources(
    targets: list[tuple[Path, Path, str]], registrations: dict[str, dict[str, str]] = AGENT_REGISTRATIONS
) -> None:
    validate_master_targets(targets)
    names: dict[str, Path] = {}
    config_files = {values["config_file"]: name for name, values in registrations.items()}
    for source, target, _ in targets:
        data = read_toml_text(source.read_text(encoding="utf-8"))
        name = data.get("name")
        if not isinstance(name, str) or not name:
            raise RuntimeError(f"{source}: missing agent name")
        if name in names:
            raise RuntimeError(f"duplicate agent name {name}: {names[name]} and {source}")
        names[name] = source
        expected_name = config_files.get(f"agents/{source.name}")
        if expected_name != name:
            raise RuntimeError(f"{source}: registration collision or missing registration for agent {name}")
        for field in ("description", "developer_instructions"):
            if not data.get(field):
                raise RuntimeError(f"{source}: missing required agent field {field}")
        if target.exists():
            target_data = read_toml_text(target.read_text(encoding="utf-8"))
            target_name = target_data.get("name")
            if target_name != name:
                raise RuntimeError(f"Refusing agent target collision at {target}: expected {name}, found {target_name}")
    missing = sorted(set(registrations) - set(names))
    if missing:
        raise RuntimeError("generated agent files missing registrations: " + ", ".join(missing))


def config_without_managed_agent_registrations(data: dict[str, Any]) -> dict[str, Any]:
    result = dict(data)
    agents = result.get("agents")
    if isinstance(agents, dict):
        preserved_agents = dict(agents)
        for name in AGENT_REGISTRATIONS:
            preserved_agents.pop(name, None)
        if preserved_agents:
            result["agents"] = preserved_agents
        else:
            result.pop("agents", None)
    return result


def merge_agent_registrations(
    active_config: str, registrations: dict[str, dict[str, str]] = AGENT_REGISTRATIONS
) -> tuple[str, list[str]]:
    merged = active_config
    report: list[str] = []
    before = read_toml_text(active_config) if active_config.strip() else {}
    agents = before.get("agents", {})
    if agents and not isinstance(agents, dict):
        raise RuntimeError("[agents] exists but is not a TOML table")
    if not isinstance(agents, dict):
        agents = {}
    newline = "\r\n" if "\r\n" in active_config else "\n"
    for name, values in registrations.items():
        existing = agents.get(name)
        if existing is not None:
            if not isinstance(existing, dict) or existing.get("config_file") != values["config_file"]:
                raise RuntimeError(f"Refusing to overwrite existing custom agent registration: {name}")
            continue
        merged += (
            f"\n\n[agents.{name}]\n"
            f"description = \"{values['description']}\"\n"
            f"config_file = \"{values['config_file']}\"\n"
        ).replace("\n", newline)
        report.append(f"Inserted agents.{name}.")
    after = read_toml_text(merged)
    if config_without_managed_agent_registrations(before) != config_without_managed_agent_registrations(after):
        raise RuntimeError("agents-only merge changed non-agent configuration")
    return merged, report


def protected_hashes(codex_home: Path) -> dict[str, str | None]:
    paths = {
        "codex/AGENTS.md": codex_home / "AGENTS.md",
        "codex/auth.json": codex_home / "auth.json",
    }
    return {label: sha256_file(path) if path.exists() else None for label, path in paths.items()}


def write_config_merge_preview(path: Path, before: str, after: str, report: list[str], *, scoped: bool = False) -> None:
    diff = "\n".join(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile="active/codex/config.toml",
            tofile="planned/codex/config.toml",
            n=0 if scoped else 3,
            lineterm="",
        )
    )
    write_text(
        path,
        "# Agents-Only Config Merge\n\n"
        f"Generated: {utc_now()}\n\n"
        + "\n".join(f"- {item}" for item in report)
        + "\n\n```diff\n"
        f"{diff if diff else '# No changes'}\n"
        "```\n",
    )


def optimized_backup_targets(
    targets: list[tuple[Path, Path, str]],
    codex_home: Path,
    backup_root: Path,
) -> list[str]:
    backup_targets_list = list(targets)
    backup_targets_list.append((codex_home / "config.toml", codex_home / "config.toml", "codex/config.toml"))
    return backup_targets(backup_targets_list, backup_root)


def snapshot_tree(source: Path, target: Path) -> None:
    if not source.exists():
        write_text(target.with_suffix(target.suffix + ".missing"), f"Missing before optimized cutover: {source}")
        return
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def create_legacy_pre_optimized_snapshot(
    *,
    timestamp: str,
    master_root: Path,
    codex_home: Path,
    cursor_home: Path,
    snapshot_base: Path,
) -> Path:
    snapshot_root = snapshot_base / timestamp
    snapshot_tree(master_root / "codex", snapshot_root / "master" / "codex")
    snapshot_tree(codex_home / "AGENTS.md", snapshot_root / "active" / "codex" / "AGENTS.md")
    snapshot_tree(codex_home / "skills.md", snapshot_root / "active" / "codex" / "skills.md")
    snapshot_tree(codex_home / "config.toml", snapshot_root / "active" / "codex" / "config.toml")
    snapshot_tree(cursor_home / "rules", snapshot_root / "active" / "cursor" / "rules")
    return snapshot_root


def backup_targets(targets: list[tuple[Path, Path, str]], backup_root: Path) -> list[str]:
    backed_up: list[str] = []
    for _, target, label in targets:
        backup_path = backup_root / label
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            shutil.copy2(target, backup_path)
            backed_up.append(label)
        else:
            write_text(backup_path.with_suffix(backup_path.suffix + ".missing"), f"Missing before publication: {target}")
            backed_up.append(f"{label} (missing)")
    return backed_up


def prune_backup_roots(backup_base: Path, keep: int) -> list[str]:
    if keep < 1 or not backup_base.exists():
        return []
    backup_roots = sorted([path for path in backup_base.iterdir() if path.is_dir()], key=lambda path: path.name)
    stale_roots = backup_roots[:-keep]
    pruned: list[str] = []
    for backup_root in stale_roots:
        shutil.rmtree(backup_root)
        pruned.append(str(backup_root))
    return pruned


def validate_master_targets(targets: list[tuple[Path, Path, str]]) -> None:
    missing = [str(source) for source, _, _ in targets if not source.exists()]
    if missing:
        raise RuntimeError("Generated master files are missing: " + ", ".join(missing))


def set_root_key(config_text: str, key: str, value_line: str) -> tuple[str, bool]:
    lines = config_text.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("["):
            break
        if stripped.startswith(f"{key} "):
            if stripped == value_line:
                return config_text, False
            lines[index] = value_line
            return "\n".join(lines) + "\n", True
    insert_at = 1 if lines and lines[0].startswith("#:schema ") else 0
    lines.insert(insert_at, value_line)
    return "\n".join(lines) + "\n", True


def set_key_in_table(config_text: str, table_name: str, key_name: str, value_line: str) -> tuple[str, bool]:
    table_header = f"[{table_name}]"
    lines = config_text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() != table_header:
            continue
        insert_at = index + 1
        while insert_at < len(lines) and not lines[insert_at].lstrip().startswith("["):
            stripped = lines[insert_at].strip()
            if stripped.startswith(f"{key_name} "):
                if stripped == value_line:
                    return config_text, False
                lines[insert_at] = value_line
                return "\n".join(lines) + "\n", True
            insert_at += 1
        lines.insert(insert_at, value_line)
        return "\n".join(lines) + "\n", True
    return config_text.rstrip() + f"\n\n{table_header}\n{value_line}\n", True


def gpt56_runtime_smoke_ok(*, codex_home: Path, codex_cli: Path | None = None) -> tuple[bool, str]:
    try:
        from validate_codex_routing import EXPECTED_MODELS, model_smoke
    except ImportError:
        return False, "validate_codex_routing unavailable"
    if codex_cli is None:
        config_path = codex_home / "config.toml"
        if config_path.exists():
            data = read_toml_text(config_path.read_text(encoding="utf-8"))
            env = data.get("mcp_servers", {}).get("node_repl", {}).get("env", {})
            cli_value = env.get("CODEX_CLI_PATH")
            if cli_value:
                codex_cli = Path(str(cli_value))
        if codex_cli is None:
            codex_cli = Path("codex")
    failures: list[str] = []
    for model in dict.fromkeys(model for model, _ in EXPECTED_MODELS.values()):
        ok, summary = model_smoke(codex_cli, model, REPO_ROOT)
        if not ok:
            failures.append(f"{model}: {summary[:200]}")
    if failures:
        return False, "; ".join(failures)
    return True, "all GPT-5.6 runtime smoke tests passed"


def merge_optimized_codex_config(
    active_config: str,
    fragment: str,
    *,
    apply_parent_model: bool = True,
) -> tuple[str, list[str]]:
    read_toml_text(fragment)
    merged = active_config
    report: list[str] = []
    if not merged.startswith("#:schema "):
        merged = "#:schema https://developers.openai.com/codex/config-schema.json\n" + merged
        report.append("Added Codex config schema header.")
    if apply_parent_model:
        for key, line, label in (
            ("model", f'model = "{TARGET_PARENT_MODEL}"', "model"),
            ("model_reasoning_effort", f'model_reasoning_effort = "{TARGET_PARENT_REASONING_EFFORT}"', "model_reasoning_effort"),
        ):
            merged, changed = set_root_key(merged, key, line)
            if changed:
                report.append(f"Set {label}.")
    else:
        report.append(f"Skipped parent model switch to {TARGET_PARENT_MODEL}; runtime smoke did not pass or was bypassed.")
    data = read_toml_text(merged)
    agents = data.get("agents", {})
    if agents and not isinstance(agents, dict):
        raise RuntimeError("[agents] exists but is not a TOML table")
    if not isinstance(agents, dict):
        agents = {}
    for key, line in (
        ("max_threads", "max_threads = 4"),
        ("max_depth", "max_depth = 1"),
        ("job_max_runtime_seconds", "job_max_runtime_seconds = 1800"),
        ("interrupt_message", "interrupt_message = true"),
    ):
        merged, changed = set_key_in_table(merged, "agents", key, line)
        if changed:
            report.append(f"Set agents.{key}.")
    data = read_toml_text(merged)
    agents = data.get("agents", {})
    if not isinstance(agents, dict):
        raise RuntimeError("[agents] exists but is not a TOML table")
    for name, values in AGENT_REGISTRATIONS.items():
        existing = agents.get(name)
        if existing:
            if not isinstance(existing, dict) or existing.get("config_file") != values["config_file"]:
                raise RuntimeError(f"Refusing to overwrite existing custom agent registration: {name}")
            continue
        merged += (
            f"\n[agents.{name}]\n"
            f"description = \"{values['description']}\"\n"
            f"config_file = \"{values['config_file']}\"\n"
        )
        report.append(f"Inserted agents.{name}.")
    read_toml_text(merged)
    return merged, report


def apply_optimized_config(
    source: Path,
    target: Path,
    reports_dir: Path,
    *,
    apply_parent_model: bool = True,
) -> dict[str, Any]:
    active = target.read_text(encoding="utf-8") if target.exists() else ""
    fragment = source.read_text(encoding="utf-8")
    merged, report = merge_optimized_codex_config(active, fragment, apply_parent_model=apply_parent_model)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(merged.rstrip() + "\n", encoding="utf-8")
    diff = "\n".join(
        difflib.unified_diff(
            active.splitlines(),
            merged.splitlines(),
            fromfile="active/codex/config.toml",
            tofile="merged/codex/config.toml",
            lineterm="",
        )
    )
    write_text(
        reports_dir / "optimized-config-merge-applied.md",
        "# Optimized Config Merge Applied\n\n"
        f"Generated: {utc_now()}\n\n"
        + "\n".join(f"- {item}" for item in report)
        + "\n\n```diff\n"
        f"{diff if diff else '# No changes'}\n"
        "```\n",
    )
    return {"label": "codex/config.toml", "target": str(target), "sha256": sha256_file(target), "merge_report": report}


def stage_publication_file(target: Path, content: bytes, *, replace: bool) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=target.parent, delete=False) as output:
        temporary = Path(output.name)
        try:
            output.write(content)
            output.close()
            if replace:
                shutil.copymode(target, temporary)
                temporary.replace(target)
            else:
                target.hardlink_to(temporary)
        except FileExistsError as exc:
            raise RuntimeError(f"Publication target appeared after preview: {target}") from exc
        finally:
            temporary.unlink(missing_ok=True)


def apply_targets(
    targets: list[tuple[Path, Path, str]], *, new_only: bool = False
) -> list[dict[str, Any]]:
    applied: list[dict[str, Any]] = []
    for source, target, label in targets:
        if new_only:
            stage_publication_file(target, source.read_bytes(), replace=False)
        else:
            copy_tree_file(source, target)
        source_hash = sha256_file(source)
        target_hash = sha256_file(target)
        if source_hash != target_hash:
            raise RuntimeError(f"Hash mismatch after writing {label}")
        applied.append({"label": label, "target": str(target), "sha256": target_hash})
    return applied


def write_publication_reports(
    reports_dir: Path,
    *,
    mode: str,
    backup_root: Path | None,
    backed_up: list[str],
    pruned_backups: list[str],
    applied: list[dict[str, Any]],
    plan: list[dict[str, str | None]] | None = None,
) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_name = "publication-preview.md"
    if mode.endswith("-applied") or applied:
        report_name = "publication-applied.md"
    if mode.endswith("-apply-prepared"):
        report_name = "publication-apply-prepared.md"
    report = reports_dir / report_name
    lines = [
        "# Publication Report",
        "",
        f"Generated: {utc_now()}",
        "",
        f"- Mode: {mode}",
        f"- Global writes performed: {'true' if applied else 'false'}",
        (
            "- Target folders: `C:\\Users\\ppyxe\\.codex` only"
            if mode.startswith(("agents-only", "ui-design-engineer"))
            else "- Target folders: `C:\\Users\\ppyxe\\.codex`, `C:\\Users\\ppyxe\\.cursor`"
        ),
    ]
    if backup_root:
        lines.append(f"- Backup root: `{backup_root}`")
    if pruned_backups:
        lines.append(f"- Pruned backups: {len(pruned_backups)}")
    lines.append("")
    if plan is not None:
        lines.extend(["## File plan", "", "| Target | Planned SHA-256 | Current SHA-256 | Rollback |", "|---|---|---|---|"])
        for item in plan:
            current = item["target_hash"]
            rollback = item.get("rollback") or (
                "Keep" if current == item["source_hash"] else "Restore backup" if current else "Remove if unchanged"
            )
            lines.append(f"| `{item['label']}` | `{item['source_hash']}` | {current or 'Missing'} | {rollback} |")
        lines.append("")
    if applied:
        lines.append("## Applied files")
        for item in applied:
            lines.append(f"- `{item['label']}` -> `{item['target']}` sha256 `{item['sha256'][:12]}`")
        lines.append("")
    write_text(report, "\n".join(lines))

    if not backup_root and not applied:
        return report

    rollback = reports_dir / "global-publication-rollback.md"
    rollback_lines = [
        "# Global Publication Rollback",
        "",
        f"Generated: {utc_now()}",
        "",
    ]
    if backup_root:
        rollback_lines.append(f"Restore files from `{backup_root}` to the matching global paths.")
        if mode.startswith("ui-design-engineer"):
            rollback_lines.append(
                "Use `codex/config.toml.registration.json` to reverse the appended registration. "
                "The metadata records the prior byte length and both hashes without storing the active config. "
                "If the published hash still matches, truncate to the recorded length and check the prior hash. "
                "Otherwise review the current config and remove only the matching registration."
            )
        rollback_lines.append(
            "Review subsequent edits before restoring. For a `.missing` marker, remove only the corresponding "
            "published file after checking its publication hash. Do not remove whole skill directories."
        )
        rollback_lines.append("")
        rollback_lines.append("Backed up targets:")
        rollback_lines.extend(f"- `{item}`" for item in backed_up)
        if pruned_backups:
            rollback_lines.append("")
            rollback_lines.append("Pruned older backup roots:")
            rollback_lines.extend(f"- `{item}`" for item in pruned_backups)
    else:
        rollback_lines.append("No backups were created because publication was preview-only.")
    write_text(rollback, "\n".join(rollback_lines))
    return report


def publish_global_rules(
    *,
    reports_dir: Path,
    master_root: Path,
    backup_base: Path,
    backup_keep: int = 2,
    codex_home: Path = CODEX_HOME,
    cursor_home: Path = CURSOR_HOME,
    apply: bool = False,
    confirm_global_write: bool = False,
    profile: str = "legacy",
    runtime_smoke: bool | None = None,
    force_parent_model: bool = False,
    agents_only: bool = False,
    ui_design_engineer: bool = False,
) -> dict[str, Any]:
    if profile == "optimized" and apply and not agents_only:
        config = REPO_ROOT / "config" / "context-optimization.toml"
        if config.exists():
            data = read_toml_text(config.read_text(encoding="utf-8"))
            if not bool(data.get("allow_global_apply", False)):
                raise RuntimeError("optimized global apply is disabled by config/context-optimization.toml")
    if ui_design_engineer:
        if profile != "optimized" or agents_only or runtime_smoke is not None or force_parent_model:
            raise RuntimeError("--ui-design-engineer requires optimized without agents-only or model flags")
        if apply and not confirm_global_write:
            raise RuntimeError("global publication requires --confirm-global-write")
        for local in (master_root, reports_dir, backup_base):
            if any(local.resolve().is_relative_to(home.resolve()) for home in (codex_home, cursor_home)):
                raise RuntimeError(f"Publication output must stay outside active homes: {local}")
        active = approved_file_path(codex_home, "config.toml")
        synthesize_ui_design(master_root)
        targets = ui_design_targets(master_root, codex_home)
        plan = package_file_plan(targets)
        registrations = {UI_AGENT: AGENT_REGISTRATIONS[UI_AGENT]}
        validate_agent_only_sources(targets[:1], registrations)
        for other in sorted((codex_home / "agents").glob("*.toml")):
            if other != targets[0][1]:
                other = approved_file_path(codex_home, f"agents/{other.name}")
                if read_toml_text(other.read_text(encoding="utf-8")).get("name") == UI_AGENT:
                    raise RuntimeError(f"Duplicate UI Design Engineer agent at {other}")
        active_existed = active.exists()
        before = active.read_bytes() if active_existed else b""
        before_text = before.decode("utf-8")
        merged, merge_report = merge_agent_registrations(before_text, registrations)
        merged_bytes = merged.encode("utf-8")
        merged_hash = hashlib.sha256(merged_bytes).hexdigest()
        plan.append({
            "label": "codex/config.toml",
            "source_hash": merged_hash,
            "target_hash": hashlib.sha256(before).hexdigest() if active_existed else None,
            "rollback": "Remove appended registration" if active_existed and merge_report else None,
        })
        write_config_merge_preview(
            reports_dir / "ui-design-engineer-config-merge-preview.md", before_text, merged, merge_report, scoped=True
        )
        applied = []
        backed_up = []
        backup_root = None
        if apply:
            changes = [row for row, item in zip(targets, plan) if item["target_hash"] is None]
            if changes or merge_report:
                timestamp = utc_now().replace(":", "").replace("-", "")
                backup_root = backup_base / f"{timestamp}-ui-design-engineer"
                suffix = 1
                while backup_root.exists():
                    backup_root = backup_base / f"{timestamp}-ui-design-engineer-{suffix}"
                    suffix += 1
                backed_up = backup_targets(changes, backup_root)
                if merge_report:
                    if active_existed:
                        label = "codex/config.toml.registration.json"
                        metadata = {
                            "prior_bytes": len(before),
                            "prior_sha256": plan[-1]["target_hash"],
                            "published_sha256": merged_hash,
                        }
                        write_text(backup_root / label, json.dumps(metadata, indent=2))
                        backed_up.append(label)
                    else:
                        backed_up.extend(backup_targets([(active, active, "codex/config.toml")], backup_root))
                if (active.exists() != active_existed or
                        (active.read_bytes() if active_existed else b"") != before or
                        package_file_plan(targets) != plan[:-1]):
                    raise RuntimeError("UI Design Engineer publication inputs changed after backup")
                write_publication_reports(
                    reports_dir, mode="ui-design-engineer-apply-prepared", backup_root=backup_root,
                    backed_up=backed_up, pruned_backups=[], applied=[], plan=plan,
                )
                applied = apply_targets(changes, new_only=True)
                if merge_report:
                    if active.exists() != active_existed or (active_existed and active.read_bytes() != before):
                        raise RuntimeError("Codex registration changed during publication")
                    stage_publication_file(active, merged_bytes, replace=active_existed)
                    if sha256_file(active) != merged_hash:
                        raise RuntimeError("Hash mismatch after writing codex/config.toml")
                    applied.append({"label": "codex/config.toml", "target": str(active), "sha256": merged_hash})
        mode = "ui-design-engineer-applied" if apply else "ui-design-engineer-preview"
        report = write_publication_reports(
            reports_dir, mode=mode, backup_root=backup_root, backed_up=backed_up, pruned_backups=[],
            applied=applied, plan=plan,
        )
        return {"mode": mode, "report": str(report), "applied": applied, "plan": plan,
                "backup_root": str(backup_root) if backup_root else None}
    if agents_only:
        if profile != "optimized":
            raise RuntimeError("--agents-only requires --profile optimized")
        if runtime_smoke is not None or force_parent_model:
            raise RuntimeError("--agents-only cannot be combined with parent-model or runtime-smoke flags")
        synthesize(
            codex_home=codex_home,
            cursor_home=cursor_home,
            master_root=master_root,
            reports_dir=reports_dir,
            profile="optimized",
        )
        targets = [row for row in agent_only_targets(master_root, codex_home) if row[0].stem != UI_AGENT]
        registrations = {name: values for name, values in AGENT_REGISTRATIONS.items() if name != UI_AGENT}
        validate_agent_only_sources(targets, registrations)
        active_config_path = codex_home / "config.toml"
        active_config = active_config_path.read_text(encoding="utf-8") if active_config_path.exists() else ""
        merged_config, merge_report = merge_agent_registrations(active_config, registrations)
        protected_before = protected_hashes(codex_home)
        write_config_merge_preview(
            reports_dir / "agents-only-config-merge-preview.md",
            active_config,
            merged_config,
            merge_report,
        )
        if not apply:
            report = write_publication_reports(
                reports_dir,
                mode="agents-only-preview",
                backup_root=None,
                backed_up=[],
                pruned_backups=[],
                applied=[],
            )
            return {"mode": "agents-only-preview", "report": str(report), "applied": []}
        if not confirm_global_write:
            raise RuntimeError("global publication requires --confirm-global-write")

        timestamp = utc_now().replace(":", "").replace("-", "")
        backup_root = backup_base / timestamp
        suffix = 1
        while backup_root.exists():
            backup_root = backup_base / f"{timestamp}-{suffix}"
            suffix += 1
        backup_plan = [
            *targets,
            (active_config_path, active_config_path, "codex/config.toml"),
        ]
        backed_up = backup_targets(backup_plan, backup_root)
        applied = apply_targets(targets)
        write_text(active_config_path, merged_config)
        after_data = read_toml_text(active_config_path.read_text(encoding="utf-8"))
        before_data = read_toml_text(active_config) if active_config.strip() else {}
        if config_without_managed_agent_registrations(before_data) != config_without_managed_agent_registrations(after_data):
            raise RuntimeError("post-write validation found a non-agent config change")
        applied.append(
            {
                "label": "codex/config.toml",
                "target": str(active_config_path),
                "sha256": sha256_file(active_config_path),
                "merge_report": merge_report,
            }
        )
        protected_after = protected_hashes(codex_home)
        if protected_before != protected_after:
            raise RuntimeError("agents-only publication changed protected AGENTS.md or auth.json")
        pruned_backups: list[str] = []
        report = write_publication_reports(
            reports_dir,
            mode="agents-only-applied",
            backup_root=backup_root,
            backed_up=backed_up,
            pruned_backups=pruned_backups,
            applied=applied,
        )
        return {
            "mode": "agents-only-applied",
            "report": str(report),
            "backup_root": str(backup_root),
            "pruned_backups": pruned_backups,
            "applied": applied,
        }
    synthesize(codex_home=codex_home, cursor_home=cursor_home, master_root=master_root, reports_dir=reports_dir, profile=profile)
    if profile == "optimized":
        optimized_agents = master_root / "optimized" / "codex" / "AGENTS.md"
        optimized_skills_index = master_root / "optimized" / "codex" / "skills-index.md"
        optimized_config = master_root / "optimized" / "codex" / "config" / "orchestrator-managed.toml"
        targets = optimized_file_targets(master_root, codex_home, cursor_home)
        package_targets = [
            row for row in targets if "/skills/" in row[2] or row[2] == f"codex/agents/{UI_AGENT}.toml"
        ]
        package_plan = package_file_plan(package_targets)
        active = approved_file_path(codex_home, "config.toml")
        merge_agent_registrations(active.read_text(encoding="utf-8") if active.exists() else "",
                                  {UI_AGENT: AGENT_REGISTRATIONS[UI_AGENT]})
        validate_master_targets(
            [
                (optimized_agents, codex_home / "AGENTS.md", "optimized/codex/AGENTS.md"),
                (optimized_skills_index, codex_home / "skills.md", "optimized/codex/skills-index.md"),
                (optimized_config, codex_home / "config.toml", "optimized/codex/config/orchestrator-managed.toml"),
                *targets,
            ]
        )
        if apply:
            if not confirm_global_write:
                raise RuntimeError("global publication requires --confirm-global-write")
            unchanged = {item["label"] for item in package_plan if item["target_hash"] is not None}
            targets = [row for row in targets if row[2] not in unchanged]
            timestamp = utc_now().replace(":", "").replace("-", "")
            backup_root = backup_base / timestamp
            legacy_snapshot = create_legacy_pre_optimized_snapshot(
                timestamp=timestamp,
                master_root=master_root,
                codex_home=codex_home,
                cursor_home=cursor_home,
                snapshot_base=backup_base.parent / "legacy-pre-optimized",
            )
            backed_up = optimized_backup_targets(targets, codex_home, backup_root)
            package_labels = {item["label"] for item in package_plan}
            applied = apply_targets([row for row in targets if row[2] in package_labels], new_only=True)
            applied.extend(apply_targets([row for row in targets if row[2] not in package_labels]))
            apply_parent_model = True
            smoke_summary = ""
            if force_parent_model:
                smoke_summary = "forced parent model apply"
            elif runtime_smoke is False:
                apply_parent_model = False
                smoke_summary = "runtime smoke skipped by flag"
            else:
                smoke_ok, smoke_summary = gpt56_runtime_smoke_ok(codex_home=codex_home)
                apply_parent_model = smoke_ok
            applied.append(
                apply_optimized_config(
                    optimized_config,
                    codex_home / "config.toml",
                    reports_dir,
                    apply_parent_model=apply_parent_model,
                )
            )
            write_text(
                reports_dir / "optimized-runtime-smoke-gate.md",
                "# Optimized Runtime Smoke Gate\n\n"
                f"Generated: {utc_now()}\n\n"
                f"- apply_parent_model: {str(apply_parent_model).lower()}\n"
                f"- force_parent_model: {str(force_parent_model).lower()}\n"
                f"- summary: {smoke_summary}\n",
            )
            pruned_backups = prune_backup_roots(backup_base, backup_keep)
            report = write_publication_reports(
                reports_dir,
                mode="optimized-applied",
                backup_root=backup_root,
                backed_up=backed_up + [f"legacy pre-optimized snapshot: {legacy_snapshot}"],
                pruned_backups=pruned_backups,
                applied=applied,
                plan=package_plan,
            )
            return {
                "mode": "optimized-applied",
                "report": str(report),
                "backup_root": str(backup_root),
                "legacy_snapshot": str(legacy_snapshot),
                "pruned_backups": pruned_backups,
                "applied": applied,
            }
        report = write_publication_reports(
            reports_dir,
            mode="optimized-preview-only",
            backup_root=None,
            backed_up=[],
            pruned_backups=[],
            applied=[],
            plan=package_plan,
        )
        return {"mode": "optimized-preview", "report": str(report), "applied": []}
    targets = publication_targets(master_root, codex_home, cursor_home)
    validate_master_targets(targets)
    if not apply:
        report = write_publication_reports(
            reports_dir,
            mode="preview-only",
            backup_root=None,
            backed_up=[],
            pruned_backups=[],
            applied=[],
        )
        return {"mode": "preview", "report": str(report), "applied": []}
    if not confirm_global_write:
        raise RuntimeError("global publication requires --confirm-global-write")

    timestamp = utc_now().replace(":", "").replace("-", "")
    backup_root = backup_base / timestamp
    backed_up = backup_targets(targets, backup_root)
    applied = apply_targets(targets)
    pruned_backups = prune_backup_roots(backup_base, backup_keep)
    report = write_publication_reports(
        reports_dir,
        mode="applied",
        backup_root=backup_root,
        backed_up=backed_up,
        pruned_backups=pruned_backups,
        applied=applied,
    )
    return {
        "mode": "applied",
        "report": str(report),
        "backup_root": str(backup_root),
        "pruned_backups": pruned_backups,
        "applied": applied,
    }


def main() -> int:
    default_profile = "legacy"
    context_config = REPO_ROOT / "config" / "context-optimization.toml"
    if context_config.exists():
        default_profile = str(read_toml_text(context_config.read_text(encoding="utf-8")).get("default_profile", "legacy"))
    parser = argparse.ArgumentParser(description="Preview or publish top-level Codex/Cursor orchestrator instructions.")
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    parser.add_argument("--master-root", type=Path, default=Path("master"))
    parser.add_argument("--backup-base", type=Path, default=Path("backups") / "global-sync")
    parser.add_argument("--backup-keep", type=int, default=2, help="Number of newest backup roots to retain after apply.")
    parser.add_argument("--codex-home", type=Path, default=CODEX_HOME)
    parser.add_argument("--cursor-home", type=Path, default=CURSOR_HOME)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--preview", action="store_true", help="Generate master files and reports without global writes.")
    action.add_argument("--apply", action="store_true", help="Apply generated files to global Codex/Cursor folders.")
    parser.add_argument("--confirm-global-write", action="store_true", help="Required with --apply.")
    parser.add_argument("--profile", choices=("legacy", "optimized"), default=default_profile)
    parser.add_argument(
        "--agents-only",
        action="store_true",
        help="Publish only generated agent TOMLs and [agents.<role>] registrations; requires the optimized profile.",
    )
    parser.add_argument(
        "--ui-design-engineer", action="store_true",
        help="Publish only the UI Design Engineer agent, its skill package, and its Codex registration.",
    )
    parser.add_argument(
        "--runtime-smoke",
        action="store_true",
        help="Require GPT-5.6 runtime smoke before switching parent model on optimized apply.",
    )
    parser.add_argument(
        "--skip-runtime-smoke",
        action="store_true",
        help="Skip parent model switch on optimized apply without running smoke tests.",
    )
    parser.add_argument(
        "--force-parent-model",
        action="store_true",
        help="Apply GPT-5.6 Sol parent model even when runtime smoke fails.",
    )
    args = parser.parse_args()
    from console_style import cprint

    runtime_smoke_flag: bool | None = None
    if args.runtime_smoke:
        runtime_smoke_flag = True
    elif args.skip_runtime_smoke:
        runtime_smoke_flag = False
    try:
        result = publish_global_rules(
            reports_dir=args.reports_dir,
            master_root=args.master_root,
            backup_base=args.backup_base,
            backup_keep=args.backup_keep,
            codex_home=args.codex_home,
            cursor_home=args.cursor_home,
            apply=args.apply,
            confirm_global_write=args.confirm_global_write,
            profile=args.profile,
            runtime_smoke=runtime_smoke_flag,
            force_parent_model=args.force_parent_model,
            agents_only=args.agents_only,
            ui_design_engineer=args.ui_design_engineer,
        )
    except RuntimeError as exc:
        cprint(f"ERROR: {exc}", "fail")
        return 2
    cprint(f"Publication mode: {result['mode']}", "phase")
    cprint(f"Report: {result['report']}", "dim")
    if result.get("backup_root"):
        cprint(f"Backup root: {result['backup_root']}", "dim")
    if result.get("pruned_backups"):
        cprint(f"Pruned backups: {len(result['pruned_backups'])}", "dim")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
