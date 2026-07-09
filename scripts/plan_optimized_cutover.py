from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from orchestrator_common import load_repository_registry, read_catalog, read_json, read_toml, sha256_file, slugify, utc_now, write_json
from synthesize_top_level_instructions import REPO_ROOT


REQUIRED_SUFFIXES = ("repository-profile", "source-map", "verification-profile")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def catalog_path_exists(record_path: str, repo_root: Path, catalog_path: Path) -> bool:
    path = Path(record_path)
    if path.is_absolute():
        return path.exists()
    return any((base / path).exists() for base in (repo_root, catalog_path.parent, catalog_path.parent.parent))


def catalog_integrity(
    *,
    repo_root: Path,
    catalog_path: Path,
    repositories_path: Path,
    state_path: Path,
) -> dict[str, Any]:
    repositories = load_repository_registry(repositories_path)
    catalog = read_catalog(catalog_path)
    state = read_json(state_path, {"repositories": {}}).get("repositories", {})
    catalog_ids = {str(entry.get("id", "")) for entry in catalog}
    missing_paths = [
        str(entry.get("record_path", ""))
        for entry in catalog
        if entry.get("record_path") and not catalog_path_exists(str(entry["record_path"]), repo_root, catalog_path)
    ]
    missing_families: dict[str, list[str]] = {}
    harvested_repos: list[str] = []
    dirty_blockers: list[dict[str, Any]] = []
    for repo in repositories:
        repo_id = str(repo["id"])
        snapshot = state.get(repo_id, {})
        status = str(snapshot.get("harvest_status", "unknown"))
        if status == "blocked_dirty_worktree":
            dirty_blockers.append({"id": repo_id, "dirty_count": int(snapshot.get("dirty_count", 0))})
            continue
        if status != "harvested":
            continue
        harvested_repos.append(repo_id)
        prefix = slugify(repo_id)
        missing = [f"{prefix}-{suffix}" for suffix in REQUIRED_SUFFIXES if f"{prefix}-{suffix}" not in catalog_ids]
        if missing:
            missing_families[repo_id] = missing
    return {
        "catalog_entry_count": len(catalog),
        "catalog_missing_record_paths": missing_paths,
        "harvested_repositories": harvested_repos,
        "missing_required_record_families": missing_families,
        "dirty_blockers": dirty_blockers,
    }


def context_token_delta(context_report_path: Path) -> dict[str, Any]:
    report = read_json(context_report_path, {"files": []})
    files = report.get("files", [])
    by_label = {str(item.get("label", "")): item for item in files if isinstance(item, dict)}
    legacy = int(by_label.get("legacy master codex AGENTS", {}).get("estimated_tokens", 0))
    optimized = int(by_label.get("optimized master codex AGENTS", {}).get("estimated_tokens", 0))
    return {
        "legacy_master_agents_estimated_tokens": legacy,
        "optimized_master_agents_estimated_tokens": optimized,
        "delta_tokens": legacy - optimized,
        "materially_below_legacy": bool(legacy and optimized and optimized < legacy),
    }


def plan_optimized_cutover(
    *,
    repo_root: Path = REPO_ROOT,
    master_root: Path = REPO_ROOT / "master",
    reports_dir: Path = REPO_ROOT / "reports",
    config_path: Path = REPO_ROOT / "config" / "context-optimization.toml",
    catalog_path: Path = REPO_ROOT / "knowledge" / "catalog.jsonl",
    repositories_path: Path = REPO_ROOT / "config" / "repositories.toml",
    state_path: Path = REPO_ROOT / "state" / "repository-snapshots.json",
    context_report_path: Path = REPO_ROOT / "reports" / "context-budget-baseline.json",
) -> dict[str, Any]:
    config = read_toml(config_path)
    max_agents_bytes = int(config.get("global_agents_max_bytes", 8192))
    optimized_agents = master_root / "optimized" / "codex" / "AGENTS.md"
    optimized_skills = master_root / "optimized" / "codex" / "skills-index.md"
    integrity = catalog_integrity(
        repo_root=repo_root,
        catalog_path=catalog_path,
        repositories_path=repositories_path,
        state_path=state_path,
    )
    token_delta = context_token_delta(context_report_path)
    gates = [
        {
            "name": "optimized_agents_exists",
            "passed": optimized_agents.exists(),
            "detail": str(optimized_agents),
        },
        {
            "name": "optimized_agents_within_byte_budget",
            "passed": optimized_agents.exists() and optimized_agents.stat().st_size <= max_agents_bytes,
            "detail": f"{optimized_agents.stat().st_size if optimized_agents.exists() else 0}/{max_agents_bytes} bytes",
        },
        {
            "name": "optimized_skills_index_exists",
            "passed": optimized_skills.exists(),
            "detail": str(optimized_skills),
        },
        {
            "name": "catalog_record_paths_exist",
            "passed": not integrity["catalog_missing_record_paths"],
            "detail": f"{len(integrity['catalog_missing_record_paths'])} missing path(s)",
        },
        {
            "name": "harvested_repos_have_core_records",
            "passed": not integrity["missing_required_record_families"],
            "detail": f"{len(integrity['missing_required_record_families'])} repo(s) missing required families",
        },
        {
            "name": "optimized_tokens_materially_below_legacy",
            "passed": token_delta["materially_below_legacy"],
            "detail": f"delta={token_delta['delta_tokens']}",
        },
        {
            "name": "no_dirty_blockers",
            "passed": not integrity["dirty_blockers"],
            "detail": f"{len(integrity['dirty_blockers'])} dirty blocker(s)",
        },
    ]
    cutover_allowed = all(gate["passed"] for gate in gates)
    result = {
        "generated_at": utc_now(),
        "applied": False,
        "cutover_allowed": cutover_allowed,
        "decision": "GO" if cutover_allowed else "NO-GO",
        "optimized_agents_exists": optimized_agents.exists(),
        "optimized_agents_sha256": sha256_file(optimized_agents) if optimized_agents.exists() else "",
        "gates": gates,
        "catalog_integrity": integrity,
        "token_delta": token_delta,
        "requires_explicit_user_approval": True,
    }
    reports_dir.mkdir(parents=True, exist_ok=True)
    write_json(reports_dir / "optimized-cutover-plan.json", result)
    write_json(reports_dir / "optimized-cutover-readiness.json", result)
    write_readiness_markdown(reports_dir / "optimized-cutover-readiness.md", result)
    write_readiness_markdown(reports_dir / "optimized-cutover-plan.md", result)
    return result


def write_readiness_markdown(path: Path, result: dict[str, Any]) -> None:
    lines = [
        "# Optimized Cutover Readiness",
        "",
        f"Generated: {result['generated_at']}",
        "",
        f"- Decision: {result['decision']}",
        "- Applied: false",
        "- Explicit approval required before global publication: true",
        "",
        "| Gate | Result | Detail |",
        "| --- | --- | --- |",
    ]
    for gate in result["gates"]:
        lines.append(f"| `{gate['name']}` | {'PASS' if gate['passed'] else 'FAIL'} | {gate['detail']} |")
    dirty = result["catalog_integrity"]["dirty_blockers"]
    lines.extend(["", "## Dirty Blockers", ""])
    if dirty:
        lines.extend(f"- `{item['id']}` dirty_count={item['dirty_count']}" for item in dirty)
    else:
        lines.append("None.")
    missing = result["catalog_integrity"]["missing_required_record_families"]
    if missing:
        lines.extend(["", "## Missing Core Records", ""])
        for repo_id, ids in missing.items():
            lines.append(f"- `{repo_id}`: " + ", ".join(f"`{item}`" for item in ids))
    write_text(path, "\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate GO/NO-GO gates for optimized global cutover.")
    parser.add_argument("--master-root", type=Path, default=REPO_ROOT / "master")
    parser.add_argument("--reports-dir", type=Path, default=REPO_ROOT / "reports")
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "config" / "context-optimization.toml")
    args = parser.parse_args()
    result = plan_optimized_cutover(master_root=args.master_root, reports_dir=args.reports_dir, config_path=args.config)
    print(f"Optimized cutover readiness: {result['decision']}")
    print(f"Report: {args.reports_dir / 'optimized-cutover-readiness.md'}")
    return 0 if result["cutover_allowed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
