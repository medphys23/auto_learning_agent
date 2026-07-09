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
    read_catalog,
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

HARVEST_SCHEMA_VERSION = "safe-repo-knowledge-v3"
EXPECTED_RECORD_SUFFIXES = (
    "repository-profile",
    "source-map",
    "stack-dependency-profile",
    "verification-profile",
)
MANIFEST_FILENAMES = {
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "composer.json",
    "renv.lock",
    "go.mod",
    "cargo.toml",
    "package-lock.json",
}
DEPLOYMENT_FILENAMES = {
    "vercel.json",
    "netlify.toml",
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "next.config.js",
    "next.config.ts",
    "vite.config.js",
    "vite.config.ts",
}


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


def read_json_object(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def source_map_summary(repo_path: Path) -> dict[str, Any]:
    files = harvestable_text_files(repo_path)
    by_area: dict[str, dict[str, Any]] = {}
    for path in files:
        rel = relative_source(repo_path, path)
        parts = rel.split("/")
        area = parts[0] if len(parts) > 1 else "."
        entry = by_area.setdefault(area, {"file_count": 0, "suffixes": {}, "examples": []})
        entry["file_count"] += 1
        suffix = path.suffix.lower() or path.name.lower()
        entry["suffixes"][suffix] = entry["suffixes"].get(suffix, 0) + 1
        if len(entry["examples"]) < 8:
            entry["examples"].append(rel)
    areas = [
        {"area": area, **details}
        for area, details in sorted(by_area.items(), key=lambda item: (-int(item[1]["file_count"]), item[0]))
    ]
    return {"harvestable_text_file_count": len(files), "areas": areas[:20]}


def manifest_signals(repo_path: Path) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    for path in harvestable_text_files(repo_path):
        name = path.name.lower()
        if name not in MANIFEST_FILENAMES:
            continue
        rel = relative_source(repo_path, path)
        signal: dict[str, Any] = {"path": rel, "name": path.name}
        if name == "package.json":
            data = read_json_object(path)
            scripts = data.get("scripts", {})
            dependencies = data.get("dependencies", {})
            dev_dependencies = data.get("devDependencies", {})
            signal["scripts"] = sorted(scripts)[:20] if isinstance(scripts, dict) else []
            signal["dependencies"] = sorted(dependencies)[:40] if isinstance(dependencies, dict) else []
            signal["dev_dependencies"] = sorted(dev_dependencies)[:40] if isinstance(dev_dependencies, dict) else []
        elif name == "requirements.txt":
            lines = []
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    lines.append(stripped)
            signal["requirements"] = lines[:40]
        elif name == "pyproject.toml":
            text = path.read_text(encoding="utf-8", errors="replace")
            signal["sections"] = [line.strip("[] ") for line in text.splitlines() if line.startswith("[")][:30]
        else:
            signal["summary"] = f"Tracked manifest file `{rel}` is present."
        signals.append(signal)
    return signals


def test_ci_deployment_signals(repo_path: Path) -> dict[str, list[str]]:
    tests: list[str] = []
    ci: list[str] = []
    deployment: list[str] = []
    for path in harvestable_text_files(repo_path):
        rel = relative_source(repo_path, path)
        lower = rel.lower()
        name = path.name.lower()
        parts = lower.split("/")
        if parts[0] in {"tests", "test"} or name.startswith("test_") or ".test." in name or ".spec." in name:
            tests.append(rel)
        if lower.startswith(".github/workflows/") or lower.startswith(".gitlab-ci"):
            ci.append(rel)
        if name in DEPLOYMENT_FILENAMES or lower.startswith("deploy") or "/deploy" in lower:
            deployment.append(rel)
    return {"tests": sorted(tests)[:80], "ci": sorted(ci)[:40], "deployment": sorted(deployment)[:40]}


def expected_record_ids(repo_id: str) -> set[str]:
    prefix = slugify(repo_id)
    return {f"{prefix}-{suffix}" for suffix in EXPECTED_RECORD_SUFFIXES}


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


def source_map_record(repo: dict[str, Any], fingerprint: dict[str, Any], repo_path: Path) -> dict[str, Any]:
    repo_id = slugify(str(repo["id"]))
    display_name = repo_name(repo)
    source_map = source_map_summary(repo_path)
    area_names = [str(area["area"]) for area in source_map["areas"][:8]]
    source_paths = []
    for area in source_map["areas"]:
        source_paths.extend(str(example) for example in area.get("examples", [])[:3])
    record = sample_candidate_record(f"{repo_id}-source-map")
    return update_record_common(
        record,
        repo=repo,
        fingerprint=fingerprint,
        title=f"{display_name} source and architecture map",
        record_type="reference",
        summary=f"Safe source map for {display_name}: {len(source_map['areas'])} harvestable areas, led by {', '.join(area_names) or 'root files'}.",
        tags=["architecture-map", "source-map", "local-github-analysis"],
        trigger_phrases=[display_name, "architecture", "source map", "where code lives"],
        source_paths=sorted(set(source_paths))[:40],
        procedure=[
            "Use this map to choose entry points before opening source files.",
            "Open only the listed areas relevant to the current task.",
            "Do not treat generated, data, cache, dependency, or secret paths as harvested knowledge.",
        ],
        verification=["Confirm source paths still exist and the repository fingerprint matches the candidate provenance."],
        confidence_score=0.72,
    ) | {"source_map": source_map}


def stack_dependency_record(repo: dict[str, Any], fingerprint: dict[str, Any], repo_path: Path) -> dict[str, Any]:
    repo_id = slugify(str(repo["id"]))
    display_name = repo_name(repo)
    manifests = manifest_signals(repo_path)
    manifest_paths = [str(item["path"]) for item in manifests]
    stack_tags = [str(tag) for tag in repo.get("stack_tags", [])]
    summary = (
        f"Stack and dependency profile for {display_name}: registry tags {', '.join(stack_tags) or 'none'}; "
        f"{len(manifests)} tracked manifest file(s)."
    )
    record = sample_candidate_record(f"{repo_id}-stack-dependency-profile")
    return update_record_common(
        record,
        repo=repo,
        fingerprint=fingerprint,
        title=f"{display_name} stack and dependency profile",
        record_type="reference",
        summary=summary,
        tags=["stack-profile", "dependency-profile", "manifest-profile"],
        trigger_phrases=[display_name, "dependencies", "stack", "package scripts", "requirements"],
        source_paths=manifest_paths,
        procedure=[
            "Use registry stack tags and manifest signals to select tools and verification commands.",
            "Before adding dependencies, follow repo AGENTS.md dependency-isolation rules.",
            "Do not infer approval to install new dependencies from this profile.",
        ],
        verification=["Parse tracked manifests again before changing dependencies or package scripts."],
        confidence_score=0.74 if manifests else 0.58,
    ) | {"manifest_signals": manifests, "registry_stack_tags": stack_tags}


def verification_profile_record(repo: dict[str, Any], fingerprint: dict[str, Any], repo_path: Path) -> dict[str, Any]:
    repo_id = slugify(str(repo["id"]))
    display_name = repo_name(repo)
    agents_path = repo_path / "AGENTS.md"
    agents_text = read_text_if_exists(agents_path)
    verification = extract_markdown_section(agents_text, "verification")
    commands = extract_code_block_commands(verification)
    signals = test_ci_deployment_signals(repo_path)
    source_paths = []
    if agents_path.exists():
        source_paths.append(relative_source(repo_path, agents_path))
    source_paths.extend(signals["tests"][:20])
    source_paths.extend(signals["ci"][:20])
    source_paths.extend(signals["deployment"][:20])
    record = sample_candidate_record(f"{repo_id}-verification-profile")
    return update_record_common(
        record,
        repo=repo,
        fingerprint=fingerprint,
        title=f"{display_name} verification, tests, CI, and deployment signals",
        record_type="reference",
        summary=(
            f"Verification profile for {display_name}: {len(commands)} AGENTS command(s), "
            f"{len(signals['tests'])} test signal(s), {len(signals['ci'])} CI signal(s), "
            f"{len(signals['deployment'])} deployment signal(s)."
        ),
        tags=["verification-profile", "tests", "ci", "deployment-signals"],
        trigger_phrases=[display_name, "test", "verification", "ci", "deployment"],
        source_paths=sorted(set(source_paths))[:80],
        procedure=[
            "Use AGENTS.md verification commands first.",
            "Use test and CI signals to broaden verification when touching shared behavior.",
            "Do not claim production readiness from deployment files alone.",
        ],
        verification=["Run applicable AGENTS.md verification commands before reporting readiness."],
        confidence_score=0.78 if commands or signals["tests"] or signals["ci"] else 0.55,
    ) | {"verification_commands": commands, "test_ci_deployment_signals": signals}


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
    candidates = [
        repository_profile_record(repo, fingerprint, repo_path),
        source_map_record(repo, fingerprint, repo_path),
        stack_dependency_record(repo, fingerprint, repo_path),
        verification_profile_record(repo, fingerprint, repo_path),
    ]
    candidates.extend(verification_command_records(repo, fingerprint, repo_path))
    constraints = constraint_record(repo, fingerprint, repo_path)
    if constraints:
        candidates.append(constraints)
    candidates.extend(workflow_records(repo, fingerprint, repo_path))
    return candidates


def catalog_record_exists(record_path: str, catalog_path: Path) -> bool:
    path = Path(record_path)
    if path.is_absolute():
        return path.exists()
    bases = [Path.cwd(), catalog_path.parent, catalog_path.parent.parent]
    return any((base / path).exists() for base in bases)


def repo_record_counts(repo_id: str, pending_dir: Path) -> dict[str, Any]:
    prefix = f"{slugify(repo_id)}-"
    ids = {path.stem for path in pending_dir.glob(f"{prefix}*.json")}
    return {
        "ids": ids,
        "profile": f"{prefix}repository-profile" in ids,
        "source_map": f"{prefix}source-map" in ids,
        "stack_dependency": f"{prefix}stack-dependency-profile" in ids,
        "verification_profile": f"{prefix}verification-profile" in ids,
        "workflow_count": len([item for item in ids if item.startswith(f"{prefix}workflow-")]),
        "command_count": len([item for item in ids if item.startswith(f"{prefix}verification-command-")]),
        "constraints": f"{prefix}repository-constraints" in ids,
    }


def status_mark(value: bool) -> str:
    return "yes" if value else "no"


def write_knowledge_index(
    index_path: Path,
    repositories: list[dict[str, Any]],
    results: list[dict[str, Any]],
    catalog_path: Path,
    pending_dir: Path,
) -> None:
    result_by_id = {str(result["id"]): result for result in results}
    catalog = read_catalog(catalog_path)
    status_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    for entry in catalog:
        status_counts[str(entry.get("status", "unknown"))] = status_counts.get(str(entry.get("status", "unknown")), 0) + 1
        type_counts[str(entry.get("type", "unknown"))] = type_counts.get(str(entry.get("type", "unknown")), 0) + 1

    lines = [
        "# Knowledge Index",
        "",
        "This index is the first stop for orchestrator knowledge retrieval. It summarizes safe, reusable repository knowledge and points to catalog records rather than loading raw repository contents.",
        "",
        f"Generated: {utc_now()}",
        "",
        "## Coverage",
        "",
        "| Repository | Status | Candidates | Profile | Source map | Stack/deps | Verification | Workflows | Commands | Constraints |",
        "| --- | --- | ---: | --- | --- | --- | --- | ---: | ---: | --- |",
    ]
    for repo in repositories:
        repo_id = str(repo["id"])
        result = result_by_id.get(repo_id, {})
        counts = repo_record_counts(repo_id, pending_dir)
        lines.append(
            f"| {repo_id} | {result.get('status', 'not-run')} | {result.get('candidate_count', len(counts['ids']))} | "
            f"{status_mark(counts['profile'])} | {status_mark(counts['source_map'])} | "
            f"{status_mark(counts['stack_dependency'])} | {status_mark(counts['verification_profile'])} | "
            f"{counts['workflow_count']} | {counts['command_count']} | {status_mark(counts['constraints'])} |"
        )

    lines.extend(["", "## Catalog Summary", ""])
    if catalog:
        lines.append("Status counts: " + ", ".join(f"{key}={value}" for key, value in sorted(status_counts.items())) + ".")
        lines.append("Type counts: " + ", ".join(f"{key}={value}" for key, value in sorted(type_counts.items())) + ".")
        if not any(entry.get("status") in {"validated", "production_proven", "canonical"} for entry in catalog):
            lines.append("")
            lines.append("No promoted knowledge records exist yet; current reusable knowledge remains candidate-first.")
    else:
        lines.append("No catalog entries exist yet.")

    lines.extend(["", "## Retrieval Rule", ""])
    lines.append("Query `knowledge/catalog.jsonl` first, then open only the minimum relevant full records under `knowledge/pending/` or promoted category folders.")
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_harvest_reports(
    results: list[dict[str, Any]],
    reports_dir: Path,
    pending_dir: Path,
    catalog_path: Path,
    repositories: list[dict[str, Any]],
    index_path: Path,
) -> None:
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

    catalog = read_catalog(catalog_path)
    missing_records = [
        str(entry.get("record_path", ""))
        for entry in catalog
        if entry.get("record_path") and not catalog_record_exists(str(entry["record_path"]), catalog_path)
    ]
    coverage_lines = [
        "# Knowledge Coverage",
        "",
        f"Generated: {utc_now()}",
        "",
        f"- Enabled repositories: {len(repositories)}",
        f"- Catalog entries: {len(catalog)}",
        f"- Catalog entries missing full records: {len(missing_records)}",
        f"- Dirty repositories blocked: {sum(1 for result in results if result['status'] == 'blocked_dirty_worktree')}",
        "",
        "## Repository Status",
        "",
        "| Repository | Status | Candidates | Dirty files |",
        "| --- | --- | ---: | ---: |",
    ]
    for result in results:
        coverage_lines.append(
            f"| {result['id']} | {result['status']} | {result.get('candidate_count', 0)} | {result.get('dirty_count', 0)} |"
        )
    coverage_lines.extend(
        [
            "",
            "## Dirty Worktree Blockers",
            "",
        ]
    )
    dirty_results = [result for result in results if result["status"] == "blocked_dirty_worktree"]
    if dirty_results:
        for result in dirty_results:
            coverage_lines.append(f"- `{result['id']}`: {result.get('dirty_count', 0)} dirty path(s); harvest blocked until clean.")
    else:
        coverage_lines.append("No dirty worktree blockers.")
    if missing_records:
        coverage_lines.extend(["", "## Missing Catalog Targets", ""])
        coverage_lines.extend(f"- `{path}`" for path in missing_records)
    (reports_dir / "knowledge-coverage.md").write_text("\n".join(coverage_lines) + "\n", encoding="utf-8")

    result_by_id = {str(result["id"]): result for result in results}
    matrix_lines = [
        "# Repository Knowledge Matrix",
        "",
        f"Generated: {utc_now()}",
        "",
        "| Repository | Status | Candidates | Profile | Source map | Stack/deps | Verification | Workflows | Commands | Constraints |",
        "| --- | --- | ---: | --- | --- | --- | --- | ---: | ---: | --- |",
    ]
    for repo in repositories:
        repo_id = str(repo["id"])
        result = result_by_id.get(repo_id, {})
        counts = repo_record_counts(repo_id, pending_dir)
        matrix_lines.append(
            f"| {repo_id} | {result.get('status', 'not-run')} | {result.get('candidate_count', len(counts['ids']))} | "
            f"{status_mark(counts['profile'])} | {status_mark(counts['source_map'])} | "
            f"{status_mark(counts['stack_dependency'])} | {status_mark(counts['verification_profile'])} | "
            f"{counts['workflow_count']} | {counts['command_count']} | {status_mark(counts['constraints'])} |"
        )
    (reports_dir / "repository-knowledge-matrix.md").write_text("\n".join(matrix_lines) + "\n", encoding="utf-8")
    write_knowledge_index(index_path, repositories, results, catalog_path, pending_dir)


def harvest_repositories(
    repositories: list[dict[str, Any]],
    state_path: Path,
    pending_dir: Path,
    catalog_path: Path = Path("knowledge/catalog.jsonl"),
    reports_dir: Path = Path("reports"),
    index_path: Path = Path("knowledge/INDEX.md"),
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
        snapshot["harvest_schema_version"] = HARVEST_SCHEMA_VERSION
        previous = state["repositories"].get(repo_id, {})
        allow_dirty_harvest = bool(repo.get("allow_dirty_harvest", False))

        if dirty and not allow_dirty_harvest:
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
                    "dirty_paths": dirty[:20],
                }
            )
            continue

        existing_ids = {path.stem for path in pending_dir.glob(f"{slugify(repo_id)}-*.json")}
        missing_expected = expected_record_ids(repo_id) - existing_ids
        if (
            previous.get("digest") == fingerprint["digest"]
            and previous.get("harvest_status") == "harvested"
            and previous.get("harvest_schema_version") == HARVEST_SCHEMA_VERSION
            and not missing_expected
        ):
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
                "reason": "dirty worktree allowed by registry" if dirty else "clean worktree",
                "dirty_count": len(dirty),
                "digest": fingerprint["digest"],
                "candidate_count": len(candidates),
                "dirty_paths": dirty[:20],
            }
        )

    if catalog_entries:
        merge_catalog_entries(catalog_path, catalog_entries)
    write_json(state_path, state)
    write_harvest_reports(results, reports_dir, pending_dir, catalog_path, repositories, index_path)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only harvest of registered repositories into local candidates.")
    parser.add_argument("--repositories", type=Path, default=Path("config/repositories.toml"))
    parser.add_argument("--state", type=Path, default=Path("state/repository-snapshots.json"))
    parser.add_argument("--pending-dir", type=Path, default=Path("knowledge/pending"))
    parser.add_argument("--catalog", type=Path, default=Path("knowledge/catalog.jsonl"))
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    parser.add_argument("--index", type=Path, default=Path("knowledge/INDEX.md"))
    args = parser.parse_args()
    repositories = load_repository_registry(args.repositories)
    results = harvest_repositories(repositories, args.state, args.pending_dir, args.catalog, args.reports_dir, args.index)
    for result in results:
        print(
            f"{result['id']}: {result['status']} "
            f"({result.get('reason', result['digest'][:12])}, candidates={result.get('candidate_count', 0)})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
