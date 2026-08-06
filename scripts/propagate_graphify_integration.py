from __future__ import annotations

import argparse
import difflib
from pathlib import Path
from typing import Any

from orchestrator_common import load_repository_registry, read_toml, utc_now
from synthesize_top_level_instructions import REPO_ROOT


BLOCK_ID = "graphify-policy"
BEGIN = f"<!-- BEGIN ORCHESTRATOR-MANAGED: {BLOCK_ID} -->"
END = f"<!-- END ORCHESTRATOR-MANAGED: {BLOCK_ID} -->"
GRAPHIFY_IGNORE = """# Governed Graphify exclusions: architecture index, never data inventory.
.env
.env.*
*.pem
*.key
*.pfx
*.p12
*secret*
*credential*
*token*
*password*
.git/
.venv/
venv/
__pycache__/
.cache/
tmp/
logs/
data/
sessions/
reports/
backups/
graphify-out/
*.db
*.sqlite
*.sqlite-*
*.csv
*.tsv
*.xlsx
*.xls
*.parquet
node_modules/
dist/
build/
vendor/
"""
CURSOR_RULE = f"""---
description: Governed Graphify architectural index and source-verification policy
alwaysApply: true
---

Use the governed federated Graphify graph first for orientation, architecture, relationships, symbols, and likely implementation files. Query with `{REPO_ROOT}\scripts\query_graph.py`; select `--repo <id>` for this repository when focused context is required, and `--directed` on path traces when call direction matters.

Graphify is an index, not source of truth: use direct reads and `rg` for exact behavior, configuration, contracts, security-sensitive code, migrations, tests, and edits. Keep graph artifacts local and respect `.graphifyignore`. Approved governed surface: code graphs, direction-aware path/explain, wiki exports under `graphify-out/`, MCP stdio serving of local graphs, and semantic-document extraction only for repositories opted in via the orchestrator registry. Do not use remote/URL ingestion, live-database, media, cloud, or global-graph features without repository-specific approval. Dirty graphs cannot justify knowledge promotion.
"""


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def policy_block() -> str:
    return f"""{BEGIN}

## Graphify architectural index

Use the governed federated Graphify graph first for repository orientation, architecture discovery, relationship tracing, symbol discovery, and locating likely implementation files. Query with `{REPO_ROOT}\scripts\query_graph.py`; select `--repo <id>` for focused repository context, and `--directed` on path traces when call direction matters.

Graphify is an index, not source of truth. Use actual source and `rg` for exact behavior, configuration, contracts, security-sensitive code, migrations, tests, assertions, error handling, and edits. Keep graphs local, respect `.graphifyignore`, and regenerate graphs after material structural changes. Approved governed surface: code graphs, direction-aware path/explain, wiki exports under `graphify-out/`, MCP stdio serving of local graphs, and semantic-document extraction only for repositories opted in via the orchestrator registry. Do not use remote/URL ingestion, live-database, media, cloud, or global-graph features without repository-specific approval. Dirty graphs cannot justify knowledge promotion.

{END}"""


def replace_or_append(content: str, block: str) -> str:
    if BEGIN in content and END in content:
        start = content.index(BEGIN)
        end = content.index(END, start) + len(END)
        suffix = content[end:].lstrip()
        return content[:start].rstrip() + "\n\n" + block + ("\n\n" + suffix if suffix else "\n")
    return content.rstrip() + "\n\n" + block + "\n"


def append_line(content: str, line: str) -> str:
    return content if line in content.splitlines() else content.rstrip() + "\n" + line + "\n"


def append_missing_lines(content: str, additions: str) -> str:
    result = content.rstrip()
    existing = set(content.splitlines())
    for line in additions.splitlines():
        if line and line not in existing:
            result += "\n" + line
    return result.rstrip() + "\n"


def preview_diff(path: Path, before: str, after: str) -> str:
    return "\n".join(difflib.unified_diff(before.splitlines(), after.splitlines(), fromfile=str(path), tofile=str(path), lineterm=""))


def compatible_cursor_rule(content: str) -> bool:
    lowered = content.lower()
    return "governed graphify" in lowered and "alwaysapply: true" in lowered and "source of truth" in lowered


def review_reasons(repo: dict[str, Any], repo_path: Path) -> list[str]:
    del repo_path
    # Reference-only clones (graphify_cycle = false) are read-only learning
    # material; never write policy files into a third-party working tree.
    if not bool(repo.get("graphify_cycle", True)):
        return ["graphify-cycle-disabled-reference-repo"]
    return []


def propagate_graphify(
    *, repositories_path: Path, reports_dir: Path, config_path: Path, apply: bool, confirm_repo_write: bool
) -> dict[str, Any]:
    config = read_toml(config_path)
    if apply and not confirm_repo_write:
        raise RuntimeError("--apply requires --confirm-repo-write")
    if apply and not bool(config.get("allow_other_repository_writes", False)):
        raise RuntimeError("other repository writes are disabled by config/context-optimization.toml")

    results: list[dict[str, Any]] = []
    report = ["# Graphify Propagation Preview", "", f"Generated: {utc_now()}", "", f"- Apply mode: {str(apply).lower()}", ""]
    for repo in load_repository_registry(repositories_path):
        repo_path = Path(str(repo.get("path", "")))
        agents = repo_path / "AGENTS.md"
        if not repo_path.is_dir() or not agents.exists():
            results.append({"id": repo.get("id"), "status": "missing-repository-or-agents"})
            continue
        reasons = review_reasons(repo, repo_path)
        cursor_rule_path = repo_path / ".cursor" / "rules" / "graphify.mdc"
        existing_cursor_rule = cursor_rule_path.read_text(encoding="utf-8", errors="replace") if cursor_rule_path.exists() else ""
        if existing_cursor_rule and not compatible_cursor_rule(existing_cursor_rule):
            reasons.append("existing-graphify-cursor-rule")
        if reasons:
            results.append({"id": repo.get("id"), "status": "review-required", "reasons": reasons})
            report.extend([f"## {repo.get('id')}", "", "- Status: review-required", f"- Reasons: {', '.join(reasons)}", ""])
            continue

        preserve_local_cursor = repo_path.resolve() == REPO_ROOT.resolve() and compatible_cursor_rule(existing_cursor_rule)
        changes = {
            agents: (agents.read_text(encoding="utf-8", errors="replace"), replace_or_append(agents.read_text(encoding="utf-8", errors="replace"), policy_block())),
            cursor_rule_path: (existing_cursor_rule, existing_cursor_rule if preserve_local_cursor else CURSOR_RULE),
            repo_path / ".graphifyignore": ((repo_path / ".graphifyignore").read_text(encoding="utf-8", errors="replace") if (repo_path / ".graphifyignore").exists() else "", ""),
            repo_path / ".gitignore": ((repo_path / ".gitignore").read_text(encoding="utf-8", errors="replace") if (repo_path / ".gitignore").exists() else "", ""),
        }
        gitignore = repo_path / ".gitignore"
        graphifyignore = repo_path / ".graphifyignore"
        changes[graphifyignore] = (changes[graphifyignore][0], append_missing_lines(changes[graphifyignore][0], GRAPHIFY_IGNORE))
        changes[gitignore] = (changes[gitignore][0], append_line(changes[gitignore][0], "graphify-out/"))
        changed = {path: pair for path, pair in changes.items() if pair[0] != pair[1]}
        if apply:
            for path, (_, after) in changed.items():
                write_text(path, after)
        report.extend([f"## {repo.get('id')}", "", f"- Status: {'written' if apply else 'preview'}", f"- Changed files: {len(changed)}", ""])
        for path, (before, after) in changed.items():
            report.extend([f"### `{path.relative_to(repo_path)}`", "", "```diff", preview_diff(path, before, after), "```", ""])
        results.append({
            "id": repo.get("id"),
            "status": "written" if apply and changed else "ready" if apply else "preview",
            "changed_files": [str(path) for path in changed],
            "risk_tags": list(repo.get("risk_tags", [])),
        })
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "graphify-propagation-preview.md"
    write_text(report_path, "\n".join(report))
    return {"generated_at": utc_now(), "apply": apply, "results": results, "report": str(report_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview or apply governed Graphify integration to eligible registered repositories.")
    parser.add_argument("--repositories", type=Path, default=REPO_ROOT / "config" / "repositories.toml")
    parser.add_argument("--reports-dir", type=Path, default=REPO_ROOT / "reports")
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "config" / "context-optimization.toml")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-repo-write", action="store_true")
    parser.add_argument("--skip-build", action="store_true", help="Apply policy files without starting the graph cycle.")
    args = parser.parse_args()
    try:
        result = propagate_graphify(
            repositories_path=args.repositories,
            reports_dir=args.reports_dir,
            config_path=args.config,
            apply=args.apply,
            confirm_repo_write=args.confirm_repo_write,
        )
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return 2
    print(f"Graphify propagation mode: {'apply' if args.apply else 'preview'}")
    print(f"Report: {result['report']}")
    if args.apply and not args.skip_build:
        from run_graphify_cycle import run_cycle

        ready_ids = [str(item["id"]) for item in result["results"] if item.get("status") in {"written", "ready"}]
        if ready_ids:
            return run_cycle(
                repository_ids=ready_ids,
                force=False,
                max_parallel=2,
                skip_merge=False,
                strict=False,
                reports_dir=args.reports_dir,
                merge_selected=True,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
