from __future__ import annotations

import argparse
import difflib
import shutil
from pathlib import Path
from typing import Any

from orchestrator_common import sha256_file, utc_now
from synthesize_top_level_instructions import (
    AGENT_REGISTRATIONS,
    CODEX_HOME,
    CURSOR_HOME,
    REPO_ROOT,
    insert_key_in_table,
    read_toml_text,
    synthesize,
)


TARGET_PARENT_MODEL = "gpt-5.6-terra"
TARGET_PARENT_REASONING_EFFORT = "medium"


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
    for source in sorted((optimized_root / "codex" / "agents").glob("*.toml")):
        targets.append((source, codex_home / "agents" / source.name, f"codex/agents/{source.name}"))
    for source in sorted((optimized_root / "agents" / "skills").glob("*/SKILL.md")):
        name = source.parent.name
        targets.append((source, cursor_home / "skills" / name / "SKILL.md", f"cursor/skills/{name}/SKILL.md"))
        targets.append((source, codex_home / "skills" / name / "SKILL.md", f"codex/skills/{name}/SKILL.md"))
    rule = optimized_root / "cursor" / "rules" / "06-orchestrator-knowledge.mdc"
    targets.append((rule, cursor_home / "rules" / rule.name, f"cursor/rules/{rule.name}"))
    return targets


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


def merge_optimized_codex_config(active_config: str, fragment: str) -> tuple[str, list[str]]:
    read_toml_text(fragment)
    merged = active_config
    report: list[str] = []
    if not merged.startswith("#:schema "):
        merged = "#:schema https://developers.openai.com/codex/config-schema.json\n" + merged
        report.append("Added Codex config schema header.")
    for key, line, label in (
        ("model", f'model = "{TARGET_PARENT_MODEL}"', "model"),
        ("model_reasoning_effort", f'model_reasoning_effort = "{TARGET_PARENT_REASONING_EFFORT}"', "model_reasoning_effort"),
    ):
        merged, changed = set_root_key(merged, key, line)
        if changed:
            report.append(f"Set {label}.")
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


def apply_optimized_config(source: Path, target: Path, reports_dir: Path) -> dict[str, Any]:
    active = target.read_text(encoding="utf-8") if target.exists() else ""
    fragment = source.read_text(encoding="utf-8")
    merged, report = merge_optimized_codex_config(active, fragment)
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


def apply_targets(targets: list[tuple[Path, Path, str]]) -> list[dict[str, Any]]:
    applied: list[dict[str, Any]] = []
    for source, target, label in targets:
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
) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    report = reports_dir / ("publication-applied.md" if applied else "publication-preview.md")
    lines = [
        "# Publication Report",
        "",
        f"Generated: {utc_now()}",
        "",
        f"- Mode: {mode}",
        f"- Global writes performed: {'true' if applied else 'false'}",
        "- Target folders: `C:\\Users\\ppyxe\\.codex`, `C:\\Users\\ppyxe\\.cursor`",
    ]
    if backup_root:
        lines.append(f"- Backup root: `{backup_root}`")
    if pruned_backups:
        lines.append(f"- Pruned backups: {len(pruned_backups)}")
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
) -> dict[str, Any]:
    if profile == "optimized" and apply:
        config = REPO_ROOT / "config" / "context-optimization.toml"
        if config.exists():
            data = read_toml_text(config.read_text(encoding="utf-8"))
            if not bool(data.get("allow_global_apply", False)):
                raise RuntimeError("optimized global apply is disabled by config/context-optimization.toml")
    synthesize(codex_home=codex_home, cursor_home=cursor_home, master_root=master_root, reports_dir=reports_dir, profile=profile)
    if profile == "optimized":
        optimized_agents = master_root / "optimized" / "codex" / "AGENTS.md"
        optimized_skills_index = master_root / "optimized" / "codex" / "skills-index.md"
        optimized_config = master_root / "optimized" / "codex" / "config" / "orchestrator-managed.toml"
        targets = optimized_file_targets(master_root, codex_home, cursor_home)
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
            applied = apply_targets(targets)
            applied.append(apply_optimized_config(optimized_config, codex_home / "config.toml", reports_dir))
            pruned_backups = prune_backup_roots(backup_base, backup_keep)
            report = write_publication_reports(
                reports_dir,
                mode="optimized-applied",
                backup_root=backup_root,
                backed_up=backed_up + [f"legacy pre-optimized snapshot: {legacy_snapshot}"],
                pruned_backups=pruned_backups,
                applied=applied,
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
    parser.add_argument("--preview", action="store_true", help="Generate master files and reports without global writes.")
    parser.add_argument("--apply", action="store_true", help="Apply generated files to global Codex/Cursor folders.")
    parser.add_argument("--confirm-global-write", action="store_true", help="Required with --apply.")
    parser.add_argument("--profile", choices=("legacy", "optimized"), default=default_profile)
    args = parser.parse_args()
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
        )
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return 2
    print(f"Publication mode: {result['mode']}")
    print(f"Report: {result['report']}")
    if result.get("backup_root"):
        print(f"Backup root: {result['backup_root']}")
    if result.get("pruned_backups"):
        print(f"Pruned backups: {len(result['pruned_backups'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
