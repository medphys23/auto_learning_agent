from __future__ import annotations

import argparse
import json
from pathlib import Path

from orchestrator_common import (
    fingerprint_repository,
    load_repository_registry,
    read_json,
    sample_candidate_record,
    slugify,
    utc_now,
    validate_knowledge_record,
    write_json,
)


def candidate_from_repository(repo: dict[str, object], fingerprint: dict[str, object]) -> dict[str, object]:
    repo_id = slugify(str(repo["id"]))
    record = sample_candidate_record(f"{repo_id}-repository-inventory")
    now = utc_now()
    record.update(
        {
            "id": f"{repo_id}-repository-inventory",
            "title": f"{repo['id']} repository inventory",
            "type": "reference",
            "scope": "repository",
            "status": "candidate",
            "summary": "Repository fingerprint and instruction inventory candidate produced by read-only harvesting.",
            "trigger_phrases": [str(repo["id"]), "repository harvest", "orchestrator inventory"],
            "tags": ["repository-harvest", "local-mvp"],
            "procedure": [
                "Read only files from the registered repository.",
                "Compare the fingerprint with the stored repository snapshot.",
                "Keep any reusable lessons as candidates until separately validated.",
            ],
            "verification": ["Re-run harvest and confirm unchanged repositories are skipped."],
            "evidence": {
                "source_repository": str(repo["path"]),
                "source_commit": fingerprint.get("commit") or "",
                "source_paths": [],
                "task_or_issue": "local-mvp-bootstrap",
                "tests_executed": [],
                "deployment_environment": "",
                "deployment_evidence": "",
                "accepted_by_user": False,
                "production_observation_window": "",
            },
            "provenance": {
                "created_at": now,
                "updated_at": now,
                "created_by": "harvest_repositories.py",
                "supersedes": [],
                "derived_from": [],
            },
        }
    )
    return record


def harvest_repositories(
    repositories: list[dict[str, object]],
    state_path: Path,
    pending_dir: Path,
) -> list[dict[str, object]]:
    state = read_json(state_path, {"repositories": {}})
    state.setdefault("repositories", {})
    results: list[dict[str, object]] = []
    pending_dir.mkdir(parents=True, exist_ok=True)

    for repo in repositories:
        repo_id = str(repo["id"])
        repo_path = Path(str(repo["path"]))
        fingerprint = fingerprint_repository(repo_path)
        previous = state["repositories"].get(repo_id, {})
        if previous.get("digest") == fingerprint["digest"]:
            results.append({"id": repo_id, "status": "skipped", "reason": "unchanged", "digest": fingerprint["digest"]})
            continue

        record = candidate_from_repository(repo, fingerprint)
        errors = validate_knowledge_record(record)
        if errors:
            raise ValueError(f"generated candidate for {repo_id} is invalid: {errors}")
        record_path = pending_dir / f"{record['id']}.json"
        record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        state["repositories"][repo_id] = fingerprint
        results.append(
            {
                "id": repo_id,
                "status": "updated",
                "digest": fingerprint["digest"],
                "candidate": str(record_path),
            }
        )

    write_json(state_path, state)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only harvest of registered repositories into local candidates.")
    parser.add_argument("--repositories", type=Path, default=Path("config/repositories.toml"))
    parser.add_argument("--state", type=Path, default=Path("state/repository-snapshots.json"))
    parser.add_argument("--pending-dir", type=Path, default=Path("knowledge/pending"))
    args = parser.parse_args()
    repositories = load_repository_registry(args.repositories)
    results = harvest_repositories(repositories, args.state, args.pending_dir)
    for result in results:
        print(f"{result['id']}: {result['status']} ({result.get('reason', result['digest'][:12])})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
