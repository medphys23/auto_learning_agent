from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from orchestrator_common import (
    catalog_entry,
    extract_code_block_commands,
    extract_constraint_lines,
    extract_markdown_section,
    extract_skill_sections,
    fingerprint_repository,
    git_dirty_lines,
    harvestable_text_files,
    load_repository_registry,
    merge_catalog_entries,
    read_json,
    read_text_if_exists,
    sample_candidate_record,
    slugify,
    summarize_markdown,
    update_record_common,
    utc_now,
    validate_knowledge_record,
    write_json,
)


def relative_source(repo_path: Path, source: Path) -> str:
    try:
        return source.relative_to(repo_path).as_posix()
    except ValueError:
        return source.as_posix()


def repo_name(repo: dict[str, Any]) -> str:
    return str(repo.get("name") or repo.get("id") or "repository")


def write_record(record: dict[str, Any], pending_dir: Path) -> tuple[Path, dict[str, Any]]:
    errors = validate_knowledge_record(record)
    if errors:
        raise ValueError(f"generated candidate {record.get('id')} is invalid: {errors}")
    record_path = pending_dir / f"{record['id']}.json"
    write_json(record_path, record)
    return record_path, catalog_entry(record, record_path)


def existing_candidate_count(repo_id: str, pending_dir: Path) -> int:
    prefix = f"{slugify(repo_id)}-"
    return len(list(pending_dir.glob(f"{prefix}*.json")))


def repository_profile_record(repo: dict[str, Any], fingerprint: dict[str, Any], repo_path: Path) -> dict[str, Any]:
    repo_id = slugify(str(repo["id"]))
    display_name = repo_name(repo)
    agents_path = repo_path / "AGENTS.md"
    agents_text = read_text_if_exists(agents_path)
    purpose = extract_markdown_section(agents_text, "purpose") if agents_text else ""
    stack = extract_markdown_section(agents_text, "stack") if agents_text else ""
    text_files = harvestable_text_files(repo_path)
    record = sample_candidate_record(f"{repo_id}-repository-profile")
    summary = summarize_markdown(purpose, f"{display_name} repository profile from local Git checkout.")
    procedure = [
        f"Use local checkout `{repo_path}` as the first source of truth for this repository.",
        "Read AGENTS.md and skills.md before planning implementation work.",
        "Apply risk tags before reusing knowledge in another repository.",
    ]
    if stack:
        procedure.append("Use the stack section in AGENTS.md to route verification and dependency handling.")
    return update_record_common(
        record,
        repo=repo,
        fingerprint=fingerprint,
        title=f"{display_name} repository profile",
        record_type="reference",
        summary=summary,
        tags=["repository-profile", "local-github-analysis"],
        trigger_phrases=[display_name, str(repo["id"]), "repository profile"],
        source_paths=[relative_source(repo_path, agents_path)] if agents_path.exists() else [],
        procedure=procedure,
        verification=["Confirm the repository branch, dirty state, and AGENTS.md before reuse."],
        confidence_score=0.75 if agents_text else 0.55,
    ) | {
        "repository_metadata": {
            "branch": fingerprint.get("branch", ""),
            "remote": fingerprint.get("remote", ""),
            "file_count": fingerprint.get("file_count", 0),
            "harvestable_text_file_count": len(text_files),
            "purpose_excerpt": summarize_markdown(purpose, ""),
            "stack_excerpt": summarize_markdown(stack, ""),
        }
    }


def verification_command_records(repo: dict[str, Any], fingerprint: dict[str, Any], repo_path: Path) -> list[dict[str, Any]]:
    display_name = repo_name(repo)
    agents_path = repo_path / "AGENTS.md"
    agents_text = read_text_if_exists(agents_path)
    verification = extract_markdown_section(agents_text, "verification")
    commands = extract_code_block_commands(verification)
    records: list[dict[str, Any]] = []
    repo_id = slugify(str(repo["id"]))
    for index, command in enumerate(commands, 1):
        record = sample_candidate_record(f"{repo_id}-verification-command-{index}")
        records.append(
            update_record_common(
                record,
                repo=repo,
                fingerprint=fingerprint,
                title=f"{display_name} verification command {index}",
                record_type="command",
                summary=f"Canonical verification command from {display_name}: {command}",
                tags=["verification-command", "repo-agents"],
                trigger_phrases=[display_name, "verification", command],
                source_paths=[relative_source(repo_path, agents_path)],
                procedure=[command],
                verification=["Run only when the repository AGENTS.md says the command applies to touched files."],
                confidence_score=0.8,
            )
        )
    return records


def constraint_record(repo: dict[str, Any], fingerprint: dict[str, Any], repo_path: Path) -> dict[str, Any] | None:
    display_name = repo_name(repo)
    agents_path = repo_path / "AGENTS.md"
    agents_text = read_text_if_exists(agents_path)
    rules = extract_markdown_section(agents_text, "repo-specific rules")
    constraints = extract_constraint_lines(rules)
    if not constraints and not repo.get("risk_tags"):
        return None
    repo_id = slugify(str(repo["id"]))
    record = sample_candidate_record(f"{repo_id}-repository-constraints")
    return update_record_common(
        record,
        repo=repo,
        fingerprint=fingerprint,
        title=f"{display_name} repository constraints",
        record_type="constraint",
        summary=f"Safety and applicability constraints for {display_name}.",
        tags=["repository-constraints", "repo-agents"],
        trigger_phrases=[display_name, "constraints", "safety", "risk"],
        source_paths=[relative_source(repo_path, agents_path)] if agents_path.exists() else [],
        procedure=constraints or [f"Apply risk tags before reusing knowledge: {', '.join(repo.get('risk_tags', []))}"],
        verification=["Check AGENTS.md constraints before reusing this repository pattern elsewhere."],
        confidence_score=0.8 if constraints else 0.6,
    )


def workflow_records(repo: dict[str, Any], fingerprint: dict[str, Any], repo_path: Path) -> list[dict[str, Any]]:
    display_name = repo_name(repo)
    skills_path = repo_path / "skills.md"
    skills_text = read_text_if_exists(skills_path)
    sections = extract_skill_sections(skills_text)
    repo_id = slugify(str(repo["id"]))
    records: list[dict[str, Any]] = []
    for section in sections:
        heading = str(section["title"])
        body = str(section["body"])
        procedure = []
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith(("-", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")):
                procedure.append(stripped[:240])
        if not procedure:
            procedure = [f"Follow the `{heading}` workflow documented in skills.md."]
        record = sample_candidate_record(f"{repo_id}-workflow-{slugify(heading)}")
        records.append(
            update_record_common(
                record,
                repo=repo,
                fingerprint=fingerprint,
                title=f"{display_name} workflow: {heading}",
                record_type="workflow",
                summary=summarize_markdown(body, f"Workflow documented under `{heading}` in skills.md."),
                tags=["repo-workflow", "skills-md"],
                trigger_phrases=[display_name, heading],
                source_paths=[relative_source(repo_path, skills_path)],
                procedure=procedure[:20],
                verification=["Follow the Verification section in the same skills.md workflow before promotion."],
                confidence_score=0.75,
            )
        )
    return records


def generate_candidates(repo: dict[str, Any], fingerprint: dict[str, Any]) -> list[dict[str, Any]]:
    repo_path = Path(str(repo["path"])).resolve()
    candidates = [repository_profile_record(repo, fingerprint, repo_path)]
    candidates.extend(verification_command_records(repo, fingerprint, repo_path))
    constraints = constraint_record(repo, fingerprint, repo_path)
    if constraints:
        candidates.append(constraints)
    candidates.extend(workflow_records(repo, fingerprint, repo_path))
    return candidates


def write_harvest_reports(results: list[dict[str, Any]], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    ready_lines = [
        "# Harvest Readiness",
        "",
        f"Generated: {utc_now()}",
        "",
        "| Repository | Status | Dirty files | Candidate count |",
        "| --- | --- | ---: | ---: |",
    ]
    harvest_lines = [
        "# Repository Harvest",
        "",
        f"Generated: {utc_now()}",
        "",
        "| Repository | Status | Reason | Candidate count |",
        "| --- | --- | --- | ---: |",
    ]
    for result in results:
        ready_lines.append(
            f"| {result['id']} | {result['status']} | {result.get('dirty_count', 0)} | {result.get('candidate_count', 0)} |"
        )
        harvest_lines.append(
            f"| {result['id']} | {result['status']} | {result.get('reason', '')} | {result.get('candidate_count', 0)} |"
        )
    (reports_dir / "harvest-readiness.md").write_text("\n".join(ready_lines) + "\n", encoding="utf-8")
    (reports_dir / "repository-harvest.md").write_text("\n".join(harvest_lines) + "\n", encoding="utf-8")


def harvest_repositories(
    repositories: list[dict[str, Any]],
    state_path: Path,
    pending_dir: Path,
    catalog_path: Path = Path("knowledge/catalog.jsonl"),
    reports_dir: Path = Path("reports"),
) -> list[dict[str, Any]]:
    state = read_json(state_path, {"repositories": {}})
    state.setdefault("repositories", {})
    results: list[dict[str, Any]] = []
    catalog_entries: list[dict[str, Any]] = []
    pending_dir.mkdir(parents=True, exist_ok=True)

    for repo in repositories:
        repo_id = str(repo["id"])
        repo_path = Path(str(repo["path"]))
        fingerprint = fingerprint_repository(repo_path)
        dirty = git_dirty_lines(repo_path)
        snapshot = dict(fingerprint)
        snapshot["harvest_status"] = "pending"
        snapshot["dirty_count"] = len(dirty)
        previous = state["repositories"].get(repo_id, {})

        if dirty:
            snapshot["harvest_status"] = "blocked_dirty_worktree"
            state["repositories"][repo_id] = snapshot
            results.append(
                {
                    "id": repo_id,
                    "status": "blocked_dirty_worktree",
                    "reason": "uncommitted changes present",
                    "dirty_count": len(dirty),
                    "digest": fingerprint["digest"],
                    "candidate_count": 0,
                }
            )
            continue

        if previous.get("digest") == fingerprint["digest"] and previous.get("harvest_status") == "harvested":
            candidate_count = existing_candidate_count(repo_id, pending_dir)
            results.append(
                {
                    "id": repo_id,
                    "status": "skipped",
                    "reason": "unchanged",
                    "dirty_count": 0,
                    "digest": fingerprint["digest"],
                    "candidate_count": candidate_count,
                }
            )
            continue

        candidates = generate_candidates(repo, fingerprint)
        repo_entries: list[dict[str, Any]] = []
        for record in candidates:
            _, entry = write_record(record, pending_dir)
            repo_entries.append(entry)
        catalog_entries.extend(repo_entries)
        snapshot["harvest_status"] = "harvested"
        snapshot["candidate_count"] = len(candidates)
        state["repositories"][repo_id] = snapshot
        results.append(
            {
                "id": repo_id,
                "status": "harvested",
                "reason": "clean worktree",
                "dirty_count": 0,
                "digest": fingerprint["digest"],
                "candidate_count": len(candidates),
            }
        )

    if catalog_entries:
        merge_catalog_entries(catalog_path, catalog_entries)
    write_json(state_path, state)
    write_harvest_reports(results, reports_dir)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only harvest of registered repositories into local candidates.")
    parser.add_argument("--repositories", type=Path, default=Path("config/repositories.toml"))
    parser.add_argument("--state", type=Path, default=Path("state/repository-snapshots.json"))
    parser.add_argument("--pending-dir", type=Path, default=Path("knowledge/pending"))
    parser.add_argument("--catalog", type=Path, default=Path("knowledge/catalog.jsonl"))
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    args = parser.parse_args()
    repositories = load_repository_registry(args.repositories)
    results = harvest_repositories(repositories, args.state, args.pending_dir, args.catalog, args.reports_dir)
    for result in results:
        print(
            f"{result['id']}: {result['status']} "
            f"({result.get('reason', result['digest'][:12])}, candidates={result.get('candidate_count', 0)})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
