from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from orchestrator_common import utc_now, write_json
from synthesize_top_level_instructions import CODEX_HOME, CURSOR_HOME, REPO_ROOT


WORD_RE = re.compile(r"\b\S+\b")
TOKEN_DIVISOR = 4


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def classify(path: Path) -> str:
    parts = [part.lower() for part in path.parts]
    name = path.name.lower()
    if ".codex" in parts and name in {"agents.md", "config.toml"}:
        return "always_loaded"
    if ".cursor" in parts and name.endswith(".mdc"):
        return "cursor_rule"
    if "master" in parts or "reports" in parts:
        return "generated"
    if name == "agents.md":
        return "repository_loaded"
    if name == "skills.md" or name == "skill.md":
        return "manual_or_skill"
    return "conditional"


def estimate_file(path: Path, label: str) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {
            "label": label,
            "path": str(path),
            "exists": False,
            "bytes": 0,
            "characters": 0,
            "words": 0,
            "estimated_tokens": 0,
            "load_type": classify(path),
        }
    text = read_text(path)
    return {
        "label": label,
        "path": str(path),
        "exists": True,
        "bytes": path.stat().st_size,
        "characters": len(text),
        "words": len(WORD_RE.findall(text)),
        "estimated_tokens": max(1, len(text) // TOKEN_DIVISOR) if text else 0,
        "load_type": classify(path),
    }


def collect_targets(repo_root: Path, codex_home: Path, cursor_home: Path, master_root: Path) -> list[tuple[str, Path]]:
    targets: list[tuple[str, Path]] = [
        ("active codex AGENTS", codex_home / "AGENTS.md"),
        ("active codex skills", codex_home / "skills.md"),
        ("active codex config", codex_home / "config.toml"),
        ("legacy master codex AGENTS", master_root / "codex" / "AGENTS.md"),
        ("legacy master codex skills", master_root / "codex" / "skills.md"),
        ("optimized master codex AGENTS", master_root / "optimized" / "codex" / "AGENTS.md"),
        ("repository AGENTS", repo_root / "AGENTS.md"),
        ("repository skills", repo_root / "skills.md"),
    ]
    targets.extend((f"active cursor rule {path.name}", path) for path in sorted((cursor_home / "rules").glob("*.mdc")))
    targets.extend((f"repo cursor rule {path.name}", path) for path in sorted((repo_root / ".cursor" / "rules").glob("*.mdc")))
    targets.extend((f"generated cursor rule {path.name}", path) for path in sorted((master_root / "cursor" / "rules").glob("*.mdc")))
    targets.extend(
        (f"optimized skill {path.parent.name}", path)
        for path in sorted((master_root / "optimized" / "agents" / "skills").glob("*/SKILL.md"))
    )
    return targets


def write_markdown(path: Path, result: dict[str, Any]) -> None:
    lines = [
        "# Context Budget Baseline",
        "",
        f"Generated: {result['generated_at']}",
        "",
        "Token counts are estimates based on character count divided by 4. They are for relative budget tracking, not billing.",
        "",
        f"- Estimated persistent instruction tokens: {result['persistent_estimated_tokens']}",
        f"- Existing files audited: {sum(1 for item in result['files'] if item['exists'])}",
        "",
        "| Label | Load type | Bytes | Words | Est. tokens | Path |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for item in result["files"]:
        lines.append(
            f"| {item['label']} | {item['load_type']} | {item['bytes']} | {item['words']} | "
            f"{item['estimated_tokens']} | `{item['path']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def audit_context_budget(
    *,
    repo_root: Path = REPO_ROOT,
    codex_home: Path = CODEX_HOME,
    cursor_home: Path = CURSOR_HOME,
    master_root: Path = REPO_ROOT / "master",
    reports_dir: Path = REPO_ROOT / "reports",
) -> dict[str, Any]:
    files = [estimate_file(path, label) for label, path in collect_targets(repo_root, codex_home, cursor_home, master_root)]
    persistent_tokens = sum(
        item["estimated_tokens"]
        for item in files
        if item["exists"] and item["load_type"] in {"always_loaded", "repository_loaded"}
    )
    result = {
        "generated_at": utc_now(),
        "persistent_estimated_tokens": persistent_tokens,
        "files": files,
    }
    reports_dir.mkdir(parents=True, exist_ok=True)
    write_json(reports_dir / "context-budget-baseline.json", result)
    write_markdown(reports_dir / "context-budget-baseline.md", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Estimate active and generated instruction context footprint.")
    parser.add_argument("--reports-dir", type=Path, default=REPO_ROOT / "reports")
    parser.add_argument("--master-root", type=Path, default=REPO_ROOT / "master")
    parser.add_argument("--codex-home", type=Path, default=CODEX_HOME)
    parser.add_argument("--cursor-home", type=Path, default=CURSOR_HOME)
    args = parser.parse_args()
    result = audit_context_budget(
        reports_dir=args.reports_dir,
        master_root=args.master_root,
        codex_home=args.codex_home,
        cursor_home=args.cursor_home,
    )
    from console_style import cprint

    cprint(
        f"Context budget audit: files={len(result['files'])} "
        f"persistent_estimated_tokens={result['persistent_estimated_tokens']}",
        "ok",
    )
    cprint(f"Report: {args.reports_dir / 'context-budget-baseline.md'}", "dim")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
