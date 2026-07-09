from __future__ import annotations

import argparse
import difflib
from pathlib import Path
from typing import Any

from orchestrator_common import load_repository_registry, read_toml, utc_now
from synthesize_top_level_instructions import REPO_ROOT


BLOCK_ID = "knowledge-retrieval"
BEGIN = f"<!-- BEGIN ORCHESTRATOR-MANAGED: {BLOCK_ID} -->"
END = f"<!-- END ORCHESTRATOR-MANAGED: {BLOCK_ID} -->"


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def hint_block(repo_path: Path) -> str:
    root = REPO_ROOT
    return f"""{BEGIN}

## Orchestrator Knowledge (Optimized)
- Index-first: `{root}\\knowledge\\INDEX.md` then `{root}\\knowledge\\catalog.jsonl`.
- Repo-scoped retrieval: `{root}\\scripts\\retrieve_knowledge_for_repo.py --cwd {repo_path}`.
- Open only shortlisted full records; repo `AGENTS.md` overrides catalog guidance.

{END}"""


def replace_or_append(content: str, block: str) -> str:
    if BEGIN in content and END in content:
        start = content.index(BEGIN)
        end = content.index(END, start) + len(END)
        return content[:start].rstrip() + "\n\n" + block + "\n\n" + content[end:].lstrip()
    return content.rstrip() + "\n\n" + block + "\n"


def preview_diff(path: Path, before: str, after: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile=str(path),
            tofile=str(path),
            lineterm="",
        )
    )


def propagate_hints(
    *,
    repositories_path: Path,
    reports_dir: Path,
    config_path: Path,
    apply: bool,
    confirm_repo_write: bool,
) -> dict[str, Any]:
    config = read_toml(config_path)
    if apply and not confirm_repo_write:
        raise RuntimeError("--apply requires --confirm-repo-write")
    if apply and not bool(config.get("allow_other_repository_writes", False)):
        raise RuntimeError("other repository writes are disabled by config/context-optimization.toml")
    repositories = load_repository_registry(repositories_path)
    results: list[dict[str, Any]] = []
    report_lines = [
        "# Repo Orchestrator Hints Preview",
        "",
        f"Generated: {utc_now()}",
        "",
        f"- Apply mode: {str(apply).lower()}",
        "",
    ]
    for repo in repositories:
        repo_path = Path(str(repo.get("path", "")))
        agents = repo_path / "AGENTS.md"
        if not agents.exists():
            results.append({"id": repo.get("id"), "path": str(agents), "status": "missing_agents"})
            continue
        before = agents.read_text(encoding="utf-8", errors="replace")
        after = replace_or_append(before, hint_block(repo_path))
        changed = before != after
        if apply and changed:
            agents.write_text(after, encoding="utf-8")
        diff = preview_diff(agents, before, after)
        report_lines.extend(
            [
                f"## {repo.get('id')}",
                "",
                f"- Path: `{agents}`",
                f"- Changed: {str(changed).lower()}",
                f"- Written: {str(apply and changed).lower()}",
                "",
                "```diff",
                diff if diff else "# No changes",
                "```",
                "",
            ]
        )
        results.append({"id": repo.get("id"), "path": str(agents), "status": "written" if apply and changed else "preview", "changed": changed})
    reports_dir.mkdir(parents=True, exist_ok=True)
    write_text(reports_dir / "repo-orchestrator-hints-preview.md", "\n".join(report_lines))
    return {"generated_at": utc_now(), "apply": apply, "results": results, "report": str(reports_dir / "repo-orchestrator-hints-preview.md")}


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview or apply optimized knowledge retrieval hints in registered repo AGENTS.md files.")
    parser.add_argument("--repositories", type=Path, default=REPO_ROOT / "config" / "repositories.toml")
    parser.add_argument("--reports-dir", type=Path, default=REPO_ROOT / "reports")
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "config" / "context-optimization.toml")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-repo-write", action="store_true")
    args = parser.parse_args()
    try:
        result = propagate_hints(
            repositories_path=args.repositories,
            reports_dir=args.reports_dir,
            config_path=args.config,
            apply=args.apply,
            confirm_repo_write=args.confirm_repo_write,
        )
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return 2
    print(f"Repo hint mode: {'apply' if args.apply else 'preview'}")
    print(f"Report: {result['report']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
