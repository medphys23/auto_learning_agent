from __future__ import annotations

import argparse
from pathlib import Path

from orchestrator_common import iter_audit_files, read_toml, sha256_file, should_audit_file, utc_now


def inventory_root(root: Path) -> dict[str, object]:
    files = []
    skipped = 0
    if root.exists():
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if should_audit_file(path):
                files.append(
                    {
                        "path": str(path),
                        "relative_path": str(path.relative_to(root)),
                        "size": path.stat().st_size,
                        "sha256": sha256_file(path),
                    }
                )
            else:
                skipped += 1
    return {"root": str(root), "exists": root.exists(), "files": files, "skipped_files": skipped}


def write_report(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_instruction_report(codex_inventory: dict[str, object], cursor_inventory: dict[str, object]) -> str:
    lines = [
        "# Global Instruction Audit",
        "",
        f"Generated: {utc_now()}",
        "",
        "This report is read-only. It inventories instruction-like files and excludes secrets, caches, sessions, SQLite state, logs, plugin caches, dependency directories, and generated artifacts.",
        "",
    ]
    for inventory in (codex_inventory, cursor_inventory):
        files = inventory["files"]
        lines.extend(
            [
                f"## {inventory['root']}",
                f"- Exists: {inventory['exists']}",
                f"- Included files: {len(files)}",
                f"- Skipped files: {inventory['skipped_files']}",
                "",
            ]
        )
        for item in files[:200]:
            lines.append(f"- `{item['relative_path']}` ({item['size']} bytes, sha256 `{item['sha256'][:12]}`)")
        if len(files) > 200:
            lines.append(f"- ... {len(files) - 200} additional files omitted from report body")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_toml_report(codex_root: Path) -> str:
    config = codex_root / "config.toml"
    lines = ["# TOML Audit", "", f"Generated: {utc_now()}", ""]
    if not config.exists():
        lines.append(f"- Missing: `{config}`")
    else:
        try:
            data = read_toml(config)
        except Exception as exc:  # noqa: BLE001 - report exact parse failure without hiding it.
            lines.append(f"- Parse status: FAILED - {exc}")
        else:
            lines.append("- Parse status: OK")
            lines.append(f"- Top-level keys: {', '.join(sorted(data.keys()))}")
            projects = data.get("projects", {})
            lines.append(f"- Trusted/project entries: {len(projects) if isinstance(projects, dict) else 0}")
            for sensitive in ("mcp_servers", "plugins", "hooks", "notify", "features", "desktop", "windows"):
                if sensitive in data:
                    lines.append(f"- Preserved surface present: `{sensitive}`")
    return "\n".join(lines).rstrip() + "\n"


def build_readiness_report(codex_inventory: dict[str, object], cursor_inventory: dict[str, object]) -> str:
    codex_files = len(codex_inventory["files"])
    cursor_files = len(cursor_inventory["files"])
    ready = codex_inventory["exists"] and cursor_inventory["exists"] and codex_files > 0 and cursor_files > 0
    lines = [
        "# Bootstrap Readiness",
        "",
        f"Generated: {utc_now()}",
        "",
        f"- Global Codex folder exists: {codex_inventory['exists']}",
        f"- Global Cursor folder exists: {cursor_inventory['exists']}",
        f"- Codex instruction-like files inventoried: {codex_files}",
        f"- Cursor instruction-like files inventoried: {cursor_files}",
        "- Global writes performed: false",
        f"- Readiness: {'READY FOR LOCAL MVP' if ready else 'NEEDS ATTENTION'}",
        "",
        "Next step: review generated reports before any separate approved global publication task.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def run_audit(codex_root: Path, cursor_root: Path, reports_dir: Path) -> dict[str, object]:
    codex_inventory = inventory_root(codex_root)
    cursor_inventory = inventory_root(cursor_root)
    write_report(reports_dir / "global-instruction-audit.md", build_instruction_report(codex_inventory, cursor_inventory))
    write_report(reports_dir / "toml-audit.md", build_toml_report(codex_root))
    write_report(reports_dir / "bootstrap-readiness.md", build_readiness_report(codex_inventory, cursor_inventory))
    return {"codex": codex_inventory, "cursor": cursor_inventory, "reports_dir": str(reports_dir)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only audit of user-level Codex and Cursor instruction surfaces.")
    parser.add_argument("--codex-root", type=Path, default=Path.home() / ".codex")
    parser.add_argument("--cursor-root", type=Path, default=Path.home() / ".cursor")
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    args = parser.parse_args()
    result = run_audit(args.codex_root, args.cursor_root, args.reports_dir)
    print(f"Audited {len(result['codex']['files'])} Codex files and {len(result['cursor']['files'])} Cursor files.")
    print(f"Reports written to {args.reports_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
