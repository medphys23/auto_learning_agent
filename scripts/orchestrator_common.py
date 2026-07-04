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

EXCLUDED_SUFFIXES = (".sqlite", ".sqlite-shm", ".sqlite-wal", ".pem", ".key", ".pfx", ".p12")
SENSITIVE_NAME_FRAGMENTS = ("secret", "credential", "token", "password", "cache")

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


def path_parts_lower(path: Path | str) -> list[str]:
    return [part.lower() for part in Path(path).parts]


def is_excluded_path(path: Path | str) -> bool:
    p = Path(path)
    parts = path_parts_lower(p)
    name = p.name.lower()
    if any(part in EXCLUDED_PARTS for part in parts):
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
        "dirty": run_git(repo_path, "status", "--short"),
        "file_count": len(files),
        "digest": digest.hexdigest(),
        "fingerprinted_at": utc_now(),
    }


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
