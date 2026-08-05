from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]

AUDIT_EXTENSIONS = {".md", ".mdc", ".toml", ".json", ".yaml", ".yml"}
AUDIT_FILENAMES = {"agents.md", "skills.md", "skill.md", "default.rules", "mcp.json"}

EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".cache",
    "cache",
    "node_modules",
    ".sandbox",
    ".sandbox-bin",
    ".sandbox-secrets",
    ".tmp",
    "tmp",
    "sessions",
    "browser",
    "browser-logs",
    "node_repl",
    "generated_images",
    "attachments",
    "computer-use",
    "process_manager",
    "sqlite",
    "logs",
    "ai-tracking",
    "extensions",
    "plans",
    "plugins",
    "projects",
    "skills-cursor",
    "dist",
    "build",
    ".next",
    ".pytest_cache",
    "data",
    "data.backup",
    "scraper_outputs",
    "site-packages",
    "vendor",
}

EXCLUDED_FILENAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    "auth.json",
    "cap_sid",
    "installation_id",
}

EXCLUDED_SUFFIXES = (
    ".sqlite",
    ".sqlite-shm",
    ".sqlite-wal",
    ".db",
    ".db-shm",
    ".db-wal",
    ".pem",
    ".key",
    ".pfx",
    ".p12",
    ".xlsx",
    ".xls",
    ".csv",
    ".parquet",
)
SENSITIVE_NAME_FRAGMENTS = ("secret", "credential", "token", "password", "cache")

HARVEST_TEXT_SUFFIXES = {
    ".md",
    ".mdc",
    ".txt",
    ".toml",
    ".json",
    ".yaml",
    ".yml",
    ".py",
    ".ps1",
    ".php",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".css",
    ".sql",
}
HARVEST_FILENAMES = {
    "agents.md",
    "skills.md",
    "readme.md",
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "composer.json",
    "renv.lock",
    "go.mod",
    "cargo.toml",
    "package-lock.json",
    "dockerfile",
}
MAX_HARVEST_TEXT_BYTES = 256 * 1024

REQUIRED_RECORD_FIELDS = [
    "id",
    "title",
    "type",
    "scope",
    "status",
    "summary",
    "trigger_phrases",
    "tags",
    "applicability",
    "incompatible_when",
    "procedure",
    "verification",
    "rollback",
    "evidence",
    "provenance",
    "confidence",
    "reuse",
]

RECORD_TYPES = {
    "workflow",
    "pattern",
    "decision",
    "failure",
    "command",
    "constraint",
    "preference",
    "reference",
    "anti_pattern",
}
RECORD_SCOPES = {"global", "domain", "stack", "repository"}
RECORD_STATUSES = {"candidate", "validated", "production_proven", "canonical", "deprecated", "rejected"}
APPROVAL_REQUIRED_TAGS = {
    "architecture",
    "dependency_selection",
    "security",
    "authentication",
    "network_access",
    "database_migration",
    "production_deployment",
    "cost_bearing_service",
    "data_retention",
    "regulated_domain",
    "destructive_command",
    "global_output_style",
    "agent_permission",
    "approval_policy",
    "sandbox_policy",
    "mcp_server",
    "model_provider_configuration",
}


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "record"


def read_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)
    path.write_text(content, encoding="utf-8")


def path_parts_lower(path: Path | str) -> list[str]:
    return [part.lower() for part in Path(path).parts]


def is_excluded_path(path: Path | str) -> bool:
    p = Path(path)
    parts = path_parts_lower(p)
    name = p.name.lower()
    if any(part in EXCLUDED_PARTS for part in parts):
        return True
    if any(part.startswith("data.backup") for part in parts):
        return True
    if name in EXCLUDED_FILENAMES:
        return True
    if any(name.endswith(suffix) for suffix in EXCLUDED_SUFFIXES):
        return True
    if any(fragment in name for fragment in SENSITIVE_NAME_FRAGMENTS):
        return True
    return False


def should_audit_file(path: Path | str) -> bool:
    p = Path(path)
    if is_excluded_path(p):
        return False
    name = p.name.lower()
    return p.suffix.lower() in AUDIT_EXTENSIONS or name in AUDIT_FILENAMES or name.endswith(".rules")


def should_harvest_text_file(path: Path | str, repo_root: Path | None = None) -> bool:
    p = Path(path)
    if is_excluded_path(p):
        return False
    if not p.exists() or not p.is_file():
        return False
    if p.stat().st_size > MAX_HARVEST_TEXT_BYTES:
        return False
    name = p.name.lower()
    if name in HARVEST_FILENAMES:
        return True
    if p.suffix.lower() not in HARVEST_TEXT_SUFFIXES:
        return False
    if repo_root is None:
        return True
    try:
        rel_parts = p.relative_to(repo_root).parts
    except ValueError:
        return False
    top = rel_parts[0].lower() if rel_parts else ""
    return top in {
        ".github",
        ".codex",
        ".cursor",
        "app",
        "components",
        "config",
        "frontend",
        "model",
        "public",
        "scripts",
        "src",
        "tests",
        "test",
        "scraping",
        "kyd_scraping",
        "orsimetrics",
    } or len(rel_parts) == 1


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_git(repo_path: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), *args],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def git_dirty_lines(repo_path: Path) -> list[str]:
    status = run_git(repo_path, "status", "--short")
    if not status:
        return []
    return [line for line in status.splitlines() if line.strip()]


def tracked_or_walked_files(repo_path: Path) -> list[Path]:
    listed = run_git(repo_path, "ls-files", "-z")
    if listed is not None:
        files = [repo_path / item for item in listed.split("\0") if item]
    else:
        files = [path for path in repo_path.rglob("*") if path.is_file()]
    return sorted(path for path in files if path.exists() and not is_excluded_path(path))


def fingerprint_repository(repo_path: Path) -> dict[str, Any]:
    repo_path = repo_path.resolve()
    digest = hashlib.sha256()
    files = tracked_or_walked_files(repo_path)
    for path in files:
        rel = path.relative_to(repo_path).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return {
        "path": str(repo_path),
        "commit": run_git(repo_path, "rev-parse", "HEAD"),
        "branch": run_git(repo_path, "branch", "--show-current"),
        "remote": run_git(repo_path, "remote", "get-url", "origin"),
        "dirty": run_git(repo_path, "status", "--short"),
        "file_count": len(files),
        "digest": digest.hexdigest(),
        "fingerprinted_at": utc_now(),
    }


def harvestable_text_files(repo_path: Path) -> list[Path]:
    repo_path = repo_path.resolve()
    return sorted(path for path in tracked_or_walked_files(repo_path) if should_harvest_text_file(path, repo_path))


def load_repository_registry(config_path: Path) -> list[dict[str, Any]]:
    data = read_toml(config_path)
    repositories = data.get("repositories", [])
    if not isinstance(repositories, list):
        raise ValueError("config/repositories.toml must contain [[repositories]] entries")
    return [repo for repo in repositories if repo.get("enabled", True)]


def iter_audit_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file() and should_audit_file(path))


def validate_knowledge_record(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_RECORD_FIELDS:
        if field not in record:
            errors.append(f"missing required field: {field}")
    if errors:
        return errors

    if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", str(record["id"])):
        errors.append("id must be stable kebab-case")
    if record["type"] not in RECORD_TYPES:
        errors.append(f"type must be one of: {', '.join(sorted(RECORD_TYPES))}")
    if record["scope"] not in RECORD_SCOPES:
        errors.append(f"scope must be one of: {', '.join(sorted(RECORD_SCOPES))}")
    if record["status"] not in RECORD_STATUSES:
        errors.append(f"status must be one of: {', '.join(sorted(RECORD_STATUSES))}")
    if not isinstance(record["verification"], list) or not record["verification"]:
        errors.append("verification must be a non-empty list")
    for object_field in ("applicability", "evidence", "provenance", "confidence", "reuse"):
        if not isinstance(record[object_field], dict):
            errors.append(f"{object_field} must be an object")
    for list_field in ("trigger_phrases", "tags", "incompatible_when", "procedure", "rollback"):
        if not isinstance(record[list_field], list):
            errors.append(f"{list_field} must be a list")
    return errors


def read_catalog(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.exists():
        return records
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSONL: {exc}") from exc
        if isinstance(record, dict):
            records.append(record)
    return records


def catalog_entry(record: dict[str, Any], record_path: Path) -> dict[str, Any]:
    evidence = record.get("evidence", {})
    confidence = record.get("confidence", {})
    return {
        "id": record.get("id"),
        "title": record.get("title"),
        "type": record.get("type"),
        "scope": record.get("scope"),
        "status": record.get("status"),
        "summary": record.get("summary"),
        "tags": record.get("tags", []),
        "record_path": record_path.as_posix(),
        "source_repository": evidence.get("source_repository", ""),
        "source_paths": evidence.get("source_paths", []),
        "confidence": confidence,
    }


def merge_catalog_entries(catalog_path: Path, entries: list[dict[str, Any]]) -> None:
    existing = read_catalog(catalog_path)
    replacement_ids = {entry["id"] for entry in entries}
    merged = [entry for entry in existing if entry.get("id") not in replacement_ids]
    merged.extend(entries)
    merged.sort(key=lambda item: str(item.get("id", "")))
    write_jsonl(catalog_path, merged)


def retrieval_budget(policy_path: Path) -> int:
    policy = read_toml(policy_path)
    budgets = policy.get("budgets", {})
    return int(budgets.get("primary_records", 3)) + int(budgets.get("supporting_records", 2)) + int(
        budgets.get("failure_records", 1)
    )


def retrieve_records(
    catalog_path: Path,
    policy_path: Path,
    *,
    query: str = "",
    tags: list[str] | None = None,
    record_type: str | None = None,
    scope: str | None = None,
    status: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    tags = tags or []
    budget = min(limit if limit is not None else retrieval_budget(policy_path), retrieval_budget(policy_path))
    query_terms = [term.lower() for term in query.split() if term.strip()]
    wanted_tags = {tag.lower() for tag in tags}

    scored: list[tuple[int, dict[str, Any]]] = []
    for record in read_catalog(catalog_path):
        if record_type and record.get("type") != record_type:
            continue
        if scope and record.get("scope") != scope:
            continue
        if status and record.get("status") != status:
            continue
        record_tags = {str(tag).lower() for tag in record.get("tags", [])}
        if wanted_tags and not wanted_tags.issubset(record_tags):
            continue
        text = " ".join(
            str(record.get(field, "")) for field in ("id", "title", "summary", "type", "scope", "status")
        ).lower()
        text += " " + " ".join(record_tags)
        if query_terms and not all(term in text for term in query_terms):
            continue
        score = 0
        score += 10 if record.get("status") in {"canonical", "production_proven"} else 0
        score += 5 if wanted_tags else 0
        score += int(float(record.get("confidence", {}).get("score", 0)) * 10)
        scored.append((score, record))
    scored.sort(key=lambda item: (-item[0], str(item[1].get("id", ""))))
    return [record for _, record in scored[:budget]]


def sample_candidate_record(record_id: str = "sample-record") -> dict[str, Any]:
    now = utc_now()
    return {
        "id": record_id,
        "title": "Sample record",
        "type": "reference",
        "scope": "repository",
        "status": "candidate",
        "summary": "Sample valid knowledge record.",
        "trigger_phrases": ["sample"],
        "tags": ["sample"],
        "applicability": {
            "languages": ["python"],
            "frameworks": [],
            "runtimes": ["python-3.11"],
            "operating_systems": ["windows"],
            "deployment_targets": [],
            "repository_markers": [".git"],
        },
        "incompatible_when": [],
        "procedure": ["Inspect the source record."],
        "verification": ["Validate this record against the local schema."],
        "rollback": ["Keep the record as candidate or delete it before promotion."],
        "evidence": {
            "source_repository": str(REPO_ROOT),
            "source_commit": "",
            "source_paths": [],
            "task_or_issue": "",
            "tests_executed": [],
            "deployment_environment": "",
            "deployment_evidence": "",
            "accepted_by_user": False,
            "production_observation_window": "",
        },
        "provenance": {
            "created_at": now,
            "updated_at": now,
            "created_by": "auto_learning_agent",
            "supersedes": [],
            "derived_from": [],
        },
        "confidence": {"score": 0.5, "rationale": "Synthetic sample for validation."},
        "reuse": {
            "retrieval_count": 0,
            "successful_reuse_count": 0,
            "failed_reuse_count": 0,
            "last_retrieved_at": None,
        },
    }


def update_record_common(
    record: dict[str, Any],
    *,
    repo: dict[str, Any],
    fingerprint: dict[str, Any],
    title: str,
    record_type: str,
    summary: str,
    tags: list[str],
    trigger_phrases: list[str],
    source_paths: list[str],
    procedure: list[str],
    verification: list[str],
    confidence_score: float = 0.7,
) -> dict[str, Any]:
    now = utc_now()
    repo_path = str(repo.get("path", ""))
    stack_tags = [str(tag) for tag in repo.get("stack_tags", [])]
    risk_tags = [str(tag) for tag in repo.get("risk_tags", [])]
    record.update(
        {
            "title": title,
            "type": record_type,
            "scope": "repository",
            "status": "candidate",
            "summary": summary,
            "trigger_phrases": trigger_phrases,
            "tags": sorted(set(tags + stack_tags + risk_tags + [str(repo.get("id", ""))])),
            "applicability": {
                "languages": stack_tags,
                "frameworks": stack_tags,
                "runtimes": [],
                "operating_systems": ["windows"],
                "deployment_targets": [],
                "repository_markers": [".git"],
            },
            "procedure": procedure,
            "verification": verification or ["Review the source paths and validate the candidate before promotion."],
            "evidence": {
                "source_repository": repo_path,
                "source_commit": fingerprint.get("commit") or "",
                "source_paths": source_paths,
                "task_or_issue": "local-github-repository-analysis",
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
                "derived_from": source_paths,
            },
            "confidence": {"score": confidence_score, "rationale": "Deterministic extraction from repository policy files."},
        }
    )
    return record


def read_text_if_exists(path: Path) -> str:
    if not path.exists() or is_excluded_path(path):
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def extract_markdown_section(text: str, heading_prefix: str, level: int = 2) -> str:
    marker = "#" * level + " "
    wanted = heading_prefix.lower()
    lines = text.splitlines()
    start: int | None = None
    for index, line in enumerate(lines):
        lower = line.lower()
        if lower.startswith(marker) and lower[len(marker) :].strip().startswith(wanted):
            start = index + 1
            break
    if start is None:
        return ""
    end = len(lines)
    for index in range(start, len(lines)):
        if lines[index].startswith(marker):
            end = index
            break
    return "\n".join(lines[start:end]).strip()


def extract_markdown_sections(text: str, heading_prefixes: tuple[str, ...], level: int = 2) -> str:
    sections = [extract_markdown_section(text, heading, level=level) for heading in heading_prefixes]
    return "\n\n".join(section for section in sections if section)


def extract_code_block_commands(section_text: str) -> list[str]:
    commands: list[str] = []
    in_block = False
    for line in section_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_block = not in_block
            continue
        if not in_block:
            continue
        if not stripped or stripped.startswith("#"):
            continue
        commands.append(stripped)
    return commands


SAFE_INLINE_COMMAND_PREFIXES = (
    ".\\",
    "./",
    "bun ",
    "cargo ",
    "composer ",
    "docker ",
    "dotnet ",
    "go ",
    "gradle ",
    "make ",
    "mvn ",
    "node ",
    "npm ",
    "npx ",
    "php ",
    "pnpm ",
    "poetry ",
    "powershell ",
    "pwsh ",
    "py ",
    "pytest ",
    "python ",
    "python3 ",
    "ruff ",
    "sh ",
    "uv ",
    "yarn ",
)
UNSAFE_INLINE_COMMAND_FRAGMENTS = (
    " --force",
    " deploy",
    " destroy",
    " publish",
    " release",
    " remove",
    " reset",
    " clean",
    " delete",
    " push",
)
SAFE_GIT_SUBCOMMANDS = ("check-ignore", "diff", "grep", "log", "ls-files", "show", "status")


def is_safe_inline_command(value: str) -> bool:
    command = value.strip()
    lower = command.lower()
    if not command or len(command) > 500 or "\n" in command:
        return False
    if any(fragment in lower for fragment in UNSAFE_INLINE_COMMAND_FRAGMENTS):
        return False
    if lower.startswith("git "):
        parts = lower.split()
        return len(parts) > 1 and parts[1] in SAFE_GIT_SUBCOMMANDS
    return lower.startswith(SAFE_INLINE_COMMAND_PREFIXES)


def extract_inline_code_commands(section_text: str) -> list[str]:
    commands: list[str] = []
    for match in re.finditer(r"(?<!\`)\`([^\`\r\n]+)\`(?!\`)", section_text):
        candidate = match.group(1).strip()
        if is_safe_inline_command(candidate):
            commands.append(candidate)
    return commands


def extract_verification_commands(section_text: str) -> list[str]:
    commands: list[str] = []
    seen: set[str] = set()
    for command in [*extract_code_block_commands(section_text), *extract_inline_code_commands(section_text)]:
        if command not in seen:
            commands.append(command)
            seen.add(command)
    return commands


def extract_constraint_lines(section_text: str) -> list[str]:
    items: list[str] = []
    current = ""
    for line in section_text.splitlines():
        stripped = line.strip()
        if not stripped:
            if current:
                items.append(current)
                current = ""
            continue
        if re.match(r"^(?:[-*+] |\d+[.)] )", stripped):
            if current:
                items.append(current)
            current = re.sub(r"^(?:[-*+] |\d+[.)] )", "", stripped).strip()
        elif current:
            current += " " + stripped
        else:
            current = stripped
    if current:
        items.append(current)

    constraints: list[str] = []
    keywords = (
        "never",
        "do not",
        "must",
        "forbidden",
        "not clinical",
        "simulation",
        "phi",
        "read-only",
        "keep fork-only",
    )
    for item in items:
        lower = item.lower()
        if any(keyword in lower for keyword in keywords):
            constraints.append(item)
    return constraints[:20]


def extract_skill_sections(skills_text: str) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    lines = skills_text.splitlines()
    current_title: str | None = None
    current: list[str] = []
    for line in lines:
        if line.startswith("### "):
            if current_title:
                sections.append({"title": current_title, "body": "\n".join(current).strip()})
            current_title = line[4:].strip()
            current = []
        elif current_title:
            current.append(line)
    if current_title:
        sections.append({"title": current_title, "body": "\n".join(current).strip()})
    return sections


def summarize_markdown(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip(" -")
        if stripped and not stripped.startswith("#") and not stripped.startswith("```"):
            return stripped[:240]
    return fallback


def approval_required(record: dict[str, Any]) -> bool:
    tags = {str(tag) for tag in record.get("tags", [])}
    return (
        record.get("scope") == "global"
        or record.get("status") == "canonical"
        or bool(tags.intersection(APPROVAL_REQUIRED_TAGS))
    )


def ensure_within(path: Path, parent: Path) -> None:
    resolved = path.resolve()
    resolved_parent = parent.resolve()
    if os.path.commonpath([str(resolved), str(resolved_parent)]) != str(resolved_parent):
        raise ValueError(f"refusing to write outside {resolved_parent}: {resolved}")
