from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from orchestrator_common import git_dirty_lines, read_toml, run_git, slugify, utc_now


KNOWN_REPO_TAGS: dict[str, dict[str, list[str] | str]] = {
    "auto_learning_agent": {
        "scope": "orchestrator",
        "risk_tags": ["global_config_preview", "read_only_audit"],
        "stack_tags": ["python", "stdlib", "codex", "cursor"],
    },
    "campania_transplant": {
        "scope": "health_economics_research",
        "risk_tags": ["research", "health_economics", "not_clinical_decision_support"],
        "stack_tags": ["python", "streamlit", "matplotlib", "numpy", "graphviz", "docx"],
    },
    "general_work": {
        "scope": "sandbox",
        "risk_tags": ["sandbox"],
        "stack_tags": [],
    },
    "Investment_binance": {
        "scope": "finance_research",
        "risk_tags": ["finance", "read_only_market_data", "no_real_trading"],
        "stack_tags": ["python", "streamlit", "sqlite", "binance_public_api", "pandas", "numpy", "plotly"],
    },
    "kidney_federico": {
        "scope": "clinical_database",
        "risk_tags": ["clinical_data", "phi", "mysql", "php", "remote_portal"],
        "stack_tags": ["php", "mysql", "python", "mamp"],
    },
    "ORSI": {
        "scope": "research_training",
        "risk_tags": ["research", "office_com", "not_robot_control", "not_clinical"],
        "stack_tags": ["python", "office_com", "streamlit", "docx", "pptx"],
    },
    "practice-ops-dashboard": {
        "scope": "medical_practice_operations",
        "risk_tags": ["medical_practice_data", "auth", "database"],
        "stack_tags": ["nextjs", "typescript", "react", "tailwind", "postgres", "vercel"],
    },
    "PS_robot_adaptor": {
        "scope": "simulation_research",
        "risk_tags": ["simulation_only", "robotics", "no_real_robot_control"],
        "stack_tags": ["python", "pyside6", "pygame", "pytest"],
    },
    "X_booking": {
        "scope": "lead_scraper",
        "risk_tags": ["scraper", "contact_data", "branch_sensitive", "no_patient_data"],
        "stack_tags": ["python", "playwright", "openpyxl", "beautifulsoup4", "tqdm"],
    },
    "Xenios_FInances": {
        "scope": "personal_finance",
        "risk_tags": ["finance", "local_only", "mysql"],
        "stack_tags": ["php", "mysql", "bootstrap", "chartjs"],
    },
}


MARKER_FILES = (
    "AGENTS.md",
    "skills.md",
    "README.md",
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "renv.lock",
    "composer.json",
    "go.mod",
    "Cargo.toml",
)


def infer_stack_tags(repo_path: Path, existing: list[str]) -> list[str]:
    tags = set(existing)
    if (repo_path / "package.json").exists():
        tags.add("node")
    if (repo_path / "requirements.txt").exists() or (repo_path / "pyproject.toml").exists():
        tags.add("python")
    if (repo_path / "composer.json").exists():
        tags.add("php")
    if (repo_path / "renv.lock").exists():
        tags.add("r")
    return sorted(tags)


def discover_repository(repo_path: Path) -> dict[str, Any]:
    name = repo_path.name
    known = KNOWN_REPO_TAGS.get(name, {})
    marker_files = [marker for marker in MARKER_FILES if (repo_path / marker).exists()]
    dirty = git_dirty_lines(repo_path)
    stack_tags = infer_stack_tags(repo_path, list(known.get("stack_tags", [])))
    return {
        "id": slugify(name),
        "name": name,
        "path": str(repo_path),
        "remote": run_git(repo_path, "remote", "get-url", "origin") or "",
        "current_branch": run_git(repo_path, "branch", "--show-current") or "",
        "enabled": True,
        "scope": known.get("scope", "unclassified"),
        "risk_tags": list(known.get("risk_tags", [])),
        "stack_tags": stack_tags,
        "harvest_mode": "deep_when_clean",
        "dirty_count": len(dirty),
        "marker_files": marker_files,
        "has_agents": "AGENTS.md" in marker_files,
        "has_skills": "skills.md" in marker_files,
    }


def discover_repositories(root: Path) -> list[dict[str, Any]]:
    repositories = []
    for child in sorted(root.iterdir(), key=lambda item: item.name.lower()):
        if child.is_dir() and (child / ".git").exists():
            repositories.append(discover_repository(child))
    return repositories


def toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    if isinstance(value, int):
        return str(value)
    text = str(value)
    if "'" not in text:
        return f"'{text}'"
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def registry_text(repositories: list[dict[str, Any]]) -> str:
    fields = (
        "id",
        "name",
        "path",
        "remote",
        "current_branch",
        "enabled",
        "scope",
        "risk_tags",
        "stack_tags",
        "harvest_mode",
        "notes",
    )
    lines: list[str] = []
    for repo in sorted(repositories, key=lambda item: str(item["id"])):
        lines.append("[[repositories]]")
        for field in fields:
            if field in repo:
                lines.append(f"{field} = {toml_value(repo[field])}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def merge_registry(existing_path: Path, discovered: list[dict[str, Any]]) -> list[dict[str, Any]]:
    existing_by_id: dict[str, dict[str, Any]] = {}
    if existing_path.exists():
        existing = read_toml(existing_path).get("repositories", [])
        if isinstance(existing, list):
            existing_by_id = {str(item.get("id")): dict(item) for item in existing}
    for repo in discovered:
        merged = existing_by_id.get(str(repo["id"]), {})
        merged.update(
            {
                "id": repo["id"],
                "name": repo["name"],
                "path": repo["path"],
                "remote": repo["remote"],
                "current_branch": repo["current_branch"],
                "enabled": repo["enabled"],
                "scope": repo["scope"],
                "risk_tags": repo["risk_tags"],
                "stack_tags": repo["stack_tags"],
                "harvest_mode": repo["harvest_mode"],
            }
        )
        existing_by_id[str(repo["id"])] = merged
    return list(existing_by_id.values())


def write_registry(path: Path, discovered: list[dict[str, Any]]) -> None:
    merged = merge_registry(path, discovered)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(registry_text(merged), encoding="utf-8")


def write_inventory_report(path: Path, repositories: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = [repo for repo in repositories if repo["dirty_count"] == 0]
    dirty = [repo for repo in repositories if repo["dirty_count"] > 0]
    lines = [
        "# Repository Inventory",
        "",
        f"Generated: {utc_now()}",
        "",
        f"- Repositories discovered: {len(repositories)}",
        f"- Clean repositories: {len(clean)}",
        f"- Dirty repositories: {len(dirty)}",
        "- Source of truth: local clones under `C:\\Users\\ppyxe\\Documents\\GitHub`",
        "",
        "| Repository | Branch | Dirty files | Scope | Stack tags | Risk tags |",
        "| --- | --- | ---: | --- | --- | --- |",
    ]
    for repo in repositories:
        lines.append(
            f"| {repo['name']} | {repo['current_branch']} | {repo['dirty_count']} | {repo['scope']} | "
            f"{', '.join(repo['stack_tags'])} | {', '.join(repo['risk_tags'])} |"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover local GitHub checkouts and optionally update the registry.")
    parser.add_argument("--root", type=Path, default=Path.home() / "Documents" / "GitHub")
    parser.add_argument("--registry", type=Path, default=Path("config/repositories.toml"))
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    parser.add_argument("--write-registry", action="store_true")
    args = parser.parse_args()

    repositories = discover_repositories(args.root)
    if args.write_registry:
        write_registry(args.registry, repositories)
    write_inventory_report(args.reports_dir / "repository-inventory.md", repositories)
    for repo in repositories:
        print(f"{repo['name']}: branch={repo['current_branch']} dirty={repo['dirty_count']} scope={repo['scope']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
