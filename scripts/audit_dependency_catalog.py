from __future__ import annotations

import argparse
import json
import re
import tomllib
from pathlib import Path
from typing import Any

from orchestrator_common import git_dirty_lines, load_repository_registry, utc_now, write_json


REPO_ROOT = Path(__file__).resolve().parents[1]
CODEX_HOME = Path.home() / ".codex"
CURSOR_HOME = Path.home() / ".cursor"
DEFAULT_REGISTRY = REPO_ROOT / "config" / "repositories.toml"
DEFAULT_REPORTS_DIR = REPO_ROOT / "reports"
MAX_MANIFEST_BYTES = 4 * 1024 * 1024

MANIFEST_NAMES = {
    "requirements.txt",
    "pyproject.toml",
    "package.json",
    "package-lock.json",
    "npm-shrinkwrap.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "bun.lock",
}

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".cache",
    "node_modules",
    "dist",
    "build",
    ".next",
    "site-packages",
    "vendor",
    "data",
    "logs",
}

REQUIREMENT_NAME = re.compile(r"^\s*([A-Za-z0-9_.-]+)(?:\[[^\]]+\])?\s*(?:[<>=!~;]|$)")
YARN_PACKAGE = re.compile(r'^"?((?:@[^/\s"]+/)?[^@\s":]+)@')
PNPM_PACKAGE = re.compile(r"^\s*/((?:@[^/\s:]+/)?[^@\s:]+)@")


def normalize_package_name(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def dependency(name: str, *, source: str, family: str, kind: str, section: str = "") -> dict[str, str]:
    return {
        "name": normalize_package_name(name),
        "source": source,
        "family": family,
        "kind": kind,
        "section": section,
    }


def safe_manifest_paths(repo_path: Path) -> list[Path]:
    paths: list[Path] = []
    for path in repo_path.rglob("*"):
        if not path.is_file():
            continue
        try:
            rel_parts = path.relative_to(repo_path).parts
        except ValueError:
            continue
        if any(part.lower() in SKIP_DIRS for part in rel_parts):
            continue
        if path.name.lower() not in MANIFEST_NAMES:
            continue
        if path.stat().st_size > MAX_MANIFEST_BYTES:
            continue
        paths.append(path)
    return sorted(paths)


def relative_source(repo_path: Path, path: Path) -> str:
    try:
        return path.relative_to(repo_path).as_posix()
    except ValueError:
        return path.as_posix()


def parse_requirement_line(line: str, source: str) -> dict[str, str] | None:
    stripped = line.split("#", 1)[0].strip()
    if not stripped or stripped.startswith(("-", "git+", "http://", "https://")):
        return None
    match = REQUIREMENT_NAME.match(stripped)
    if not match:
        return None
    return dependency(match.group(1), source=source, family="python", kind="direct", section="requirements")


def parse_requirements(path: Path, repo_path: Path) -> list[dict[str, str]]:
    source = relative_source(repo_path, path)
    dependencies: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        item = parse_requirement_line(line, source)
        if item:
            dependencies.append(item)
    return dependencies


def parse_pyproject_dependency(value: str, source: str, section: str) -> dict[str, str] | None:
    match = REQUIREMENT_NAME.match(value)
    if not match:
        return None
    name = normalize_package_name(match.group(1))
    if name == "python":
        return None
    return dependency(name, source=source, family="python", kind="direct", section=section)


def parse_pyproject(path: Path, repo_path: Path) -> list[dict[str, str]]:
    source = relative_source(repo_path, path)
    data = tomllib.loads(path.read_text(encoding="utf-8", errors="replace"))
    dependencies: list[dict[str, str]] = []

    project = data.get("project", {})
    if isinstance(project, dict):
        for item in project.get("dependencies", []) if isinstance(project.get("dependencies"), list) else []:
            if isinstance(item, str):
                parsed = parse_pyproject_dependency(item, source, "project.dependencies")
                if parsed:
                    dependencies.append(parsed)
        optional = project.get("optional-dependencies", {})
        if isinstance(optional, dict):
            for group, values in optional.items():
                if isinstance(values, list):
                    for item in values:
                        if isinstance(item, str):
                            parsed = parse_pyproject_dependency(item, source, f"project.optional-dependencies.{group}")
                            if parsed:
                                dependencies.append(parsed)

    poetry = data.get("tool", {}).get("poetry", {}) if isinstance(data.get("tool"), dict) else {}
    if isinstance(poetry, dict):
        for section in ("dependencies", "dev-dependencies"):
            values = poetry.get(section, {})
            if isinstance(values, dict):
                for name in values:
                    if normalize_package_name(name) != "python":
                        dependencies.append(dependency(name, source=source, family="python", kind="direct", section=f"tool.poetry.{section}"))
    return dependencies


def parse_package_json(path: Path, repo_path: Path) -> list[dict[str, str]]:
    source = relative_source(repo_path, path)
    data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    dependencies: list[dict[str, str]] = []
    for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        values = data.get(section, {})
        if isinstance(values, dict):
            for name in values:
                dependencies.append(dependency(name, source=source, family="javascript", kind="direct", section=section))
    return dependencies


def package_from_node_modules_key(key: str) -> str:
    marker = "node_modules/"
    if marker not in key:
        return ""
    return key.rsplit(marker, 1)[1].strip("/")


def parse_package_lock(path: Path, repo_path: Path) -> list[dict[str, str]]:
    source = relative_source(repo_path, path)
    data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    dependencies: list[dict[str, str]] = []
    for section, values in (("dependencies", data.get("dependencies", {})), ("devDependencies", data.get("devDependencies", {}))):
        if isinstance(values, dict):
            for name in values:
                dependencies.append(dependency(name, source=source, family="javascript", kind="direct", section=section))
    packages = data.get("packages", {})
    if isinstance(packages, dict):
        for key in packages:
            name = package_from_node_modules_key(str(key))
            if name:
                dependencies.append(dependency(name, source=source, family="javascript", kind="lock", section="packages"))
    locked = data.get("dependencies", {})
    if isinstance(locked, dict):
        for name in locked:
            dependencies.append(dependency(name, source=source, family="javascript", kind="lock", section="dependencies"))
    return dependencies


def parse_pnpm_lock(path: Path, repo_path: Path) -> list[dict[str, str]]:
    source = relative_source(repo_path, path)
    dependencies: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = PNPM_PACKAGE.match(line)
        if match:
            dependencies.append(dependency(match.group(1), source=source, family="javascript", kind="lock", section="packages"))
    return dependencies


def parse_yarn_lock(path: Path, repo_path: Path) -> list[dict[str, str]]:
    source = relative_source(repo_path, path)
    dependencies: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith((" ", "\t")):
            continue
        match = YARN_PACKAGE.match(line.strip())
        if match:
            dependencies.append(dependency(match.group(1), source=source, family="javascript", kind="lock", section="entries"))
    return dependencies


def parse_manifest(path: Path, repo_path: Path) -> list[dict[str, str]]:
    name = path.name.lower()
    try:
        if name == "requirements.txt":
            return parse_requirements(path, repo_path)
        if name == "pyproject.toml":
            return parse_pyproject(path, repo_path)
        if name == "package.json":
            return parse_package_json(path, repo_path)
        if name in {"package-lock.json", "npm-shrinkwrap.json"}:
            return parse_package_lock(path, repo_path)
        if name == "pnpm-lock.yaml":
            return parse_pnpm_lock(path, repo_path)
        if name in {"yarn.lock", "bun.lock"}:
            return parse_yarn_lock(path, repo_path)
    except (json.JSONDecodeError, tomllib.TOMLDecodeError, OSError, UnicodeDecodeError) as exc:
        return [dependency(f"parse-error:{type(exc).__name__}", source=relative_source(repo_path, path), family="unknown", kind="error")]
    return []


def unique_dependencies(dependencies: list[dict[str, str]]) -> list[dict[str, Any]]:
    by_name: dict[str, dict[str, Any]] = {}
    for item in dependencies:
        name = item["name"]
        entry = by_name.setdefault(
            name,
            {
                "name": name,
                "families": set(),
                "kinds": set(),
                "sources": set(),
                "sections": set(),
            },
        )
        entry["families"].add(item["family"])
        entry["kinds"].add(item["kind"])
        entry["sources"].add(item["source"])
        if item.get("section"):
            entry["sections"].add(item["section"])
    return [
        {
            "name": name,
            "families": sorted(entry["families"]),
            "kinds": sorted(entry["kinds"]),
            "sources": sorted(entry["sources"]),
            "sections": sorted(entry["sections"]),
        }
        for name, entry in sorted(by_name.items())
    ]


def catalog_text(paths: list[Path]) -> str:
    parts = []
    for path in paths:
        if path.exists() and path.is_file():
            parts.append(path.read_text(encoding="utf-8", errors="replace").lower())
    return "\n".join(parts)


def package_mentioned(name: str, text: str) -> bool:
    if not text:
        return False
    lowered = name.lower()
    variants = {lowered, lowered.replace("-", "_"), lowered.replace("-", ""), lowered.replace("js", ".js")}
    return any(variant and variant in text for variant in variants)


def repo_catalog_paths(repo_path: Path) -> list[Path]:
    paths = [repo_path / "AGENTS.md", repo_path / "skills.md"]
    cursor_rules = repo_path / ".cursor" / "rules"
    if cursor_rules.exists():
        paths.extend(sorted(cursor_rules.glob("*.mdc")))
    return paths


def audit_repository(repo: dict[str, Any], global_text: str) -> dict[str, Any]:
    repo_path = Path(str(repo["path"]))
    manifests = safe_manifest_paths(repo_path) if repo_path.exists() else []
    raw_dependencies: list[dict[str, str]] = []
    for manifest in manifests:
        raw_dependencies.extend(parse_manifest(manifest, repo_path))
    packages = unique_dependencies(raw_dependencies)
    local_text = catalog_text(repo_catalog_paths(repo_path))
    dirty = git_dirty_lines(repo_path) if repo_path.exists() else []
    for package in packages:
        package["in_repo_catalog"] = package_mentioned(package["name"], local_text)
        package["in_global_catalog"] = package_mentioned(package["name"], global_text)
    return {
        "id": repo.get("id"),
        "name": repo.get("name"),
        "path": str(repo_path),
        "dirty_count": len(dirty),
        "manifest_paths": [relative_source(repo_path, path) for path in manifests],
        "package_count": len(packages),
        "packages": packages,
        "missing_from_repo_catalog": [item["name"] for item in packages if not item["in_repo_catalog"]],
        "missing_from_global_catalog": [item["name"] for item in packages if not item["in_global_catalog"]],
    }


def write_markdown_report(report_path: Path, result: dict[str, Any], max_missing: int) -> None:
    lines = [
        "# Dependency Catalog Audit",
        "",
        f"Generated: {result['generated_at']}",
        "",
        "This report inventories dependency manifests and flags packages that are not mentioned in repo-local or global stack catalogs. Missing does not mean the package should be globally promoted.",
        "",
        "| Repository | Dirty | Manifests | Packages | Missing repo catalog | Missing global catalog |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for repo in result["repositories"]:
        lines.append(
            f"| `{repo['id']}` | {repo['dirty_count']} | {len(repo['manifest_paths'])} | {repo['package_count']} | "
            f"{len(repo['missing_from_repo_catalog'])} | {len(repo['missing_from_global_catalog'])} |"
        )
    lines.extend(["", "## Repository Details", ""])
    for repo in result["repositories"]:
        lines.extend(
            [
                f"### {repo['id']}",
                "",
                f"- Manifests: {', '.join(f'`{path}`' for path in repo['manifest_paths']) or 'none'}",
                f"- Packages found: {repo['package_count']}",
                f"- Missing from repo catalog: {len(repo['missing_from_repo_catalog'])}",
                f"- Missing from global catalog: {len(repo['missing_from_global_catalog'])}",
            ]
        )
        missing = repo["missing_from_global_catalog"][:max_missing]
        if missing:
            lines.append(f"- First missing global entries: {', '.join(f'`{name}`' for name in missing)}")
        lines.append("")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def audit_dependency_catalog(
    *,
    registry_path: Path,
    reports_dir: Path,
    codex_home: Path = CODEX_HOME,
    cursor_home: Path = CURSOR_HOME,
    max_missing: int = 20,
) -> dict[str, Any]:
    registry = [repo for repo in load_repository_registry(registry_path) if repo.get("enabled", True)]
    global_text = catalog_text(
        [
            codex_home / "AGENTS.md",
            codex_home / "skills.md",
            cursor_home / "rules" / "03-stack-catalog.mdc",
        ]
    )
    repositories = [audit_repository(repo, global_text) for repo in registry]
    result = {
        "generated_at": utc_now(),
        "registry_path": str(registry_path),
        "repositories": repositories,
    }
    reports_dir.mkdir(parents=True, exist_ok=True)
    write_json(reports_dir / "dependency-catalog-audit.json", result)
    write_markdown_report(reports_dir / "dependency-catalog-audit.md", result, max_missing=max_missing)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit dependency manifests against repo and global stack catalogs.")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    parser.add_argument("--codex-home", type=Path, default=CODEX_HOME)
    parser.add_argument("--cursor-home", type=Path, default=CURSOR_HOME)
    parser.add_argument("--max-missing", type=int, default=20)
    args = parser.parse_args()
    result = audit_dependency_catalog(
        registry_path=args.registry,
        reports_dir=args.reports_dir,
        codex_home=args.codex_home,
        cursor_home=args.cursor_home,
        max_missing=args.max_missing,
    )
    from console_style import cprint

    package_count = sum(repo["package_count"] for repo in result["repositories"])
    manifest_count = sum(len(repo["manifest_paths"]) for repo in result["repositories"])
    cprint(
        f"Dependency catalog audit: repos={len(result['repositories'])} "
        f"manifests={manifest_count} packages={package_count}",
        "ok",
    )
    cprint(f"Report: {args.reports_dir / 'dependency-catalog-audit.md'}", "dim")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
