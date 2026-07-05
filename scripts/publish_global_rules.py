from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any

from orchestrator_common import sha256_file, utc_now
from synthesize_top_level_instructions import CODEX_HOME, CURSOR_HOME, REPO_ROOT, synthesize


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
        raise RuntimeError("optimized profile is preview-only; global apply requires a separate cutover task")
    synthesize(codex_home=codex_home, cursor_home=cursor_home, master_root=master_root, reports_dir=reports_dir, profile=profile)
    if profile == "optimized":
        optimized_agents = master_root / "optimized" / "codex" / "AGENTS.md"
        optimized_config = master_root / "optimized" / "codex" / "config" / "orchestrator-managed.toml"
        validate_master_targets(
            [
                (optimized_agents, codex_home / "AGENTS.md", "optimized/codex/AGENTS.md"),
                (optimized_config, codex_home / "config.toml", "optimized/codex/config/orchestrator-managed.toml"),
            ]
        )
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
    parser.add_argument("--profile", choices=("legacy", "optimized"), default="legacy")
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
