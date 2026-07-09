from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from orchestrator_common import load_repository_registry, read_json, read_toml, retrieve_records
from synthesize_top_level_instructions import REPO_ROOT


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4) if text else 0


def resolve_repository(cwd: Path, repositories: list[dict[str, Any]]) -> dict[str, Any]:
    resolved = cwd.resolve()
    matches: list[tuple[int, dict[str, Any]]] = []
    for repo in repositories:
        repo_path = Path(str(repo.get("path", ""))).resolve()
        try:
            common = os.path.commonpath([str(resolved), str(repo_path)])
        except ValueError:
            continue
        if common == str(repo_path):
            matches.append((len(str(repo_path)), repo))
    if not matches:
        raise RuntimeError(f"No enabled repository registry entry contains cwd: {resolved}")
    matches.sort(key=lambda item: item[0], reverse=True)
    return matches[0][1]


def compact_record(entry: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    record_path = Path(str(entry.get("record_path", "")))
    if not record_path.is_absolute():
        record_path = repo_root / record_path
    record = read_json(record_path, {})
    return {
        "id": entry.get("id"),
        "title": entry.get("title"),
        "type": entry.get("type"),
        "status": entry.get("status"),
        "summary": record.get("summary", entry.get("summary", "")),
        "procedure": list(record.get("procedure", []))[:5],
        "verification": list(record.get("verification", []))[:5],
        "source_paths": record.get("evidence", {}).get("source_paths", entry.get("source_paths", [])),
    }


def retrieve_for_repo(
    *,
    cwd: Path,
    repositories_path: Path,
    catalog_path: Path,
    policy_path: Path,
    context_config_path: Path,
    query: str,
    status: str | None,
    include_records: bool,
    limit: int | None,
) -> dict[str, Any]:
    repositories = load_repository_registry(repositories_path)
    repo = resolve_repository(cwd, repositories)
    context = read_toml(context_config_path)
    configured_limit = int(context.get("maximum_retrieved_records", 3))
    record_limit = min(limit if limit is not None else configured_limit, configured_limit)
    repo_id = str(repo["id"])
    tags = [repo_id]
    records = retrieve_records(catalog_path, policy_path, query=query, tags=tags, status=status, limit=record_limit)
    result_records: list[dict[str, Any]] = []
    if include_records:
        token_budget = int(context.get("maximum_retrieved_knowledge_estimated_tokens", 4000))
        used = 0
        for entry in records:
            compact = compact_record(entry, REPO_ROOT)
            encoded = json.dumps(compact, sort_keys=True)
            estimated = estimate_tokens(encoded)
            if used + estimated > token_budget and result_records:
                break
            used += estimated
            result_records.append(compact)
    else:
        result_records = records
    return {
        "repository": {"id": repo_id, "path": repo.get("path"), "scope": repo.get("scope")},
        "query": query,
        "status": status,
        "count": len(result_records),
        "records": result_records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Retrieve budgeted orchestrator knowledge for the current registered repository.")
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    parser.add_argument("--repositories", type=Path, default=REPO_ROOT / "config" / "repositories.toml")
    parser.add_argument("--catalog", type=Path, default=REPO_ROOT / "knowledge" / "catalog.jsonl")
    parser.add_argument("--policy", type=Path, default=REPO_ROOT / "config" / "retrieval-policy.toml")
    parser.add_argument("--context-config", type=Path, default=REPO_ROOT / "config" / "context-optimization.toml")
    parser.add_argument("--query", default="")
    parser.add_argument("--status", default="candidate")
    parser.add_argument("--include-records", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    try:
        result = retrieve_for_repo(
            cwd=args.cwd,
            repositories_path=args.repositories,
            catalog_path=args.catalog,
            policy_path=args.policy,
            context_config_path=args.context_config,
            query=args.query,
            status=args.status,
            include_records=args.include_records,
            limit=args.limit,
        )
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
