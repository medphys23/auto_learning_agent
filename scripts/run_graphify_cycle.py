from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from orchestrator_common import git_dirty_lines, load_repository_registry, run_git, utc_now


ROOT = Path(__file__).resolve().parents[1]
MIN_GRAPHIFY_VERSION = (0, 9, 34)
BRIDGE_SCHEMA_VERSION = "federated-graph-v1"
# Risk tags that keep a repository on the code-only (AST) profile even when the
# registry opts it into semantic-document extraction.
SEMANTIC_BLOCKED_RISK_TAGS = {
    "auth",
    "clinical_data",
    "contact_data",
    "credentials",
    "finance",
    "medical_practice_data",
    "phi",
    "scraper",
}
# Env vars Graphify's headless extract accepts as a semantic LLM backend; when
# none is set, semantic extraction is skipped and the run stays code-only.
SEMANTIC_BACKEND_ENV_VARS = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "MOONSHOT_API_KEY", "DEEPSEEK_API_KEY")
# Advisory graph-health counters surfaced by `graphify diagnose multigraph --json`.
HEALTH_WARNING_KEYS = (
    "dangling_endpoint_edges",
    "missing_endpoint_edges",
    "self_loop_edges",
    "directed_same_endpoint_collapsed_edges",
    "undirected_same_endpoint_collapsed_edges",
)
SECRET_PATTERNS = (
    # Match OpenAI-style keys; ignore hyphenated skill/feature ids like sk-notice-acknowledged.
    re.compile(r"sk-(?:proj-[A-Za-z0-9_-]{16,}|[A-Za-z0-9]{32,})"),
    re.compile(r"(?i)password\s*[:=]\s*[\"'][^\"']+"),
    re.compile(r"(?i)(?:postgres|mysql|mongodb(?:\+srv)?)://[^\s\"']+"),
    re.compile(r"(?i)api[_-]?key\s*[:=]\s*[\"'][^\"']+"),
)
# Directory-name denylist for harvested graph sources. Prefer dotted cache dirs (`.cache`), not
# application routes/modules named `cache` (e.g. dashboard/cache pages).
PROHIBITED_SOURCE_PARTS = {".env", ".venv", ".cache", "backups", "data", "logs", "node_modules", "reports", "sessions", "vendor"}
PROHIBITED_SOURCE_SUFFIXES = {".csv", ".db", ".key", ".parquet", ".pem", ".pfx", ".sqlite", ".tsv", ".xls", ".xlsx"}
BRIDGE_NODE_TYPES = {"class", "enum", "interface", "module", "namespace", "package"}
GENERIC_BRIDGE_LABELS = {"app", "config", "data", "index", "main", "model", "service", "test", "tests", "type", "utils"}
REQUIRED_GRAPHIFYIGNORE = {".env", ".env.*", "*.key", "*.pem", "data/", "graphify-out/", "*.sqlite"}
FINGERPRINT_NAME = ".orchestrator-fingerprint.json"


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    write_text(path, json.dumps(data, indent=2, sort_keys=True))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def structural_graph_sha256(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    volatile = {"community", "community_name", "built_at", "built_at_commit"}
    nodes = [{key: value for key, value in node.items() if key not in volatile} for node in data.get("nodes", [])]
    links = [{key: value for key, value in link.items() if key not in volatile} for link in data.get("links", data.get("edges", []))]
    canonical = {
        "nodes": sorted(nodes, key=lambda item: str(item.get("id", ""))),
        "links": sorted(links, key=lambda item: (str(item.get("source", "")), str(item.get("target", "")), str(item.get("relation", item.get("type", ""))))),
    }
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def parse_version(value: str) -> tuple[int, int, int]:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", value)
    if not match:
        raise ValueError(f"unable to parse Graphify version: {value!r}")
    return tuple(int(part) for part in match.groups())


def find_graphify() -> Path:
    found = shutil.which("graphify")
    if found:
        return Path(found)
    uv = shutil.which("uv")
    if uv:
        result = subprocess.run([uv, "tool", "dir", "--bin"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode == 0:
            candidate = Path(result.stdout.strip()) / ("graphify.exe" if os.name == "nt" else "graphify")
            if candidate.exists():
                return candidate
    raise RuntimeError("Graphify is not installed or discoverable through uv tool dir --bin")


def graphify_version(executable: Path) -> str:
    result = subprocess.run([str(executable), "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "graphify --version failed")
    version = result.stdout.strip()
    if parse_version(version) < MIN_GRAPHIFY_VERSION:
        raise RuntimeError(f"Graphify {version} is too old; require >= {'.'.join(map(str, MIN_GRAPHIFY_VERSION))}")
    return version


def git_ignores_path(repo_path: Path, candidate: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "check-ignore", "--quiet", "--", candidate],
            cwd=repo_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return False
    return result.returncode == 0


def preflight_repository(repo_path: Path) -> list[str]:
    problems: list[str] = []
    graphifyignore = repo_path / ".graphifyignore"
    if not graphifyignore.exists():
        problems.append("missing-.graphifyignore")
    else:
        lines = {line.strip() for line in graphifyignore.read_text(encoding="utf-8", errors="replace").splitlines()}
        missing = sorted(REQUIRED_GRAPHIFYIGNORE - lines)
        if missing:
            problems.append("missing-exclusions=" + ",".join(missing))
    if not git_ignores_path(repo_path, "graphify-out/graph.json"):
        problems.append("graphify-out-not-ignored")
    return problems


def scan_graph(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    secret_counts = [len(pattern.findall(text)) for pattern in SECRET_PATTERNS]
    prohibited_sources: set[str] = set()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return {"passed": False, "secret_pattern_count": sum(secret_counts), "prohibited_source_count": 0, "error": str(exc)}
    for node in data.get("nodes", []):
        source = str(node.get("source_file", "")).replace("\\", "/")
        parts = {part.lower() for part in Path(source).parts}
        suffix = Path(source).suffix.lower()
        if parts & PROHIBITED_SOURCE_PARTS or suffix in PROHIBITED_SOURCE_SUFFIXES:
            prohibited_sources.add(source)
    return {
        "passed": sum(secret_counts) == 0 and not prohibited_sources,
        "secret_pattern_count": sum(secret_counts),
        "prohibited_source_count": len(prohibited_sources),
    }


def run_command(command: list[str], *, cwd: Path, env: dict[str, str]) -> tuple[int, str]:
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    output = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
    return int(result.returncode), output


def fingerprint_path(repo_path: Path) -> Path:
    return repo_path / "graphify-out" / FINGERPRINT_NAME


def source_fingerprint(repo_path: Path) -> dict[str, str]:
    """Cheap git-level fingerprint for skip-unchanged decisions."""
    commit = run_git(repo_path, "rev-parse", "HEAD") or ""
    dirty_lines = git_dirty_lines(repo_path)
    dirty_blob = "\n".join(dirty_lines).encode("utf-8")
    return {
        "commit": commit,
        "dirty_sha256": hashlib.sha256(dirty_blob).hexdigest(),
        "dirty": "true" if dirty_lines else "false",
    }


def build_fingerprint(*, source: dict[str, str], profile: str, graphify_version: str, graph_sha256: str) -> dict[str, str]:
    return {
        **source,
        "extract_profile": profile,
        "graphify_version": graphify_version.strip(),
        "graph_sha256": graph_sha256,
    }


def load_fingerprint(repo_path: Path) -> dict[str, str] | None:
    path = fingerprint_path(repo_path)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return {str(key): str(value) for key, value in data.items()}


def save_fingerprint(repo_path: Path, fingerprint: dict[str, str]) -> None:
    write_json(fingerprint_path(repo_path), fingerprint)


def should_skip_unchanged(
    repo_path: Path,
    *,
    force: bool,
    profile: str,
    graphify_version: str,
) -> tuple[bool, str, dict[str, str]]:
    """Return (skip, reason, current_source_fingerprint)."""
    source = source_fingerprint(repo_path)
    if force:
        return False, "force-rebuild", source
    graph = repo_path / "graphify-out" / "graph.json"
    if not graph.exists():
        return False, "missing-graph", source
    previous = load_fingerprint(repo_path)
    if previous is None:
        return False, "missing-fingerprint", source
    expected = build_fingerprint(
        source=source,
        profile=profile,
        graphify_version=graphify_version,
        graph_sha256=previous.get("graph_sha256", ""),
    )
    # Compare the skip-relevant fields; graph hash is validated separately against the file.
    for key in ("commit", "dirty_sha256", "extract_profile", "graphify_version"):
        if previous.get(key) != expected.get(key):
            return False, f"changed:{key}", source
    try:
        current_graph_hash = sha256_file(graph)
    except OSError:
        return False, "unreadable-graph", source
    if previous.get("graph_sha256") != current_graph_hash:
        return False, "graph-hash-mismatch", source
    return True, "fingerprint-unchanged", source


def write_empty_repository_graph(repo_path: Path, repo_id: str) -> Path:
    out = repo_path / "graphify-out"
    graph = out / "graph.json"
    data = {
        "directed": False,
        "multigraph": False,
        "graph": {"empty_code_graph": True},
        "nodes": [{
            "id": f"repo::{repo_id}",
            "label": repo_id,
            "file_type": "repository",
            "source_file": "AGENTS.md",
            "source_location": "",
            "community": 0,
        }],
        "links": [],
        "hyperedges": [],
    }
    write_json(graph, data)
    write_text(
        out / "GRAPH_REPORT.md",
        f"# {repo_id} Code Graph\n\nNo supported code files were found during governed code-only extraction. Documentation and data files were intentionally excluded.",
    )
    write_text(
        out / "graph.html",
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>Empty code graph</title></head>"
        f"<body><h1>{repo_id}</h1><p>No supported code files were found. Documentation and data were excluded.</p></body></html>",
    )
    return graph


def cycle_enabled(repo: dict[str, Any]) -> bool:
    return bool(repo.get("graphify_cycle", True))


def semantic_allowed(repo: dict[str, Any]) -> bool:
    if not bool(repo.get("graphify_semantic", False)):
        return False
    risk_tags = {str(tag).lower() for tag in repo.get("risk_tags", [])}
    return not (risk_tags & SEMANTIC_BLOCKED_RISK_TAGS)


def semantic_backend_available(env: dict[str, str]) -> bool:
    return any(env.get(name) for name in SEMANTIC_BACKEND_ENV_VARS)


def select_extract_profile(repo: dict[str, Any], *, semantic: bool, env: dict[str, str]) -> tuple[str, str]:
    """Return (profile, reason). Profile is 'code' or 'code+docs'."""
    if not semantic:
        return "code", "semantic-not-requested"
    if not semantic_allowed(repo):
        return "code", "semantic-not-allowed"
    if not semantic_backend_available(env):
        return "code", "semantic-skipped-no-backend"
    return "code+docs", "semantic-enabled"


def build_extract_command(executable: Path, *, profile: str, force: bool) -> list[str]:
    # `graphify extract` is incremental by default and enforces the upstream
    # shrink-guard (#479) itself: a partial rebuild that would shrink graph.json
    # is refused with a non-zero exit instead of silently overwriting a good
    # graph. `--force` is the intentional full-rebuild escape hatch.
    command = [str(executable), "extract", "."]
    if profile != "code+docs":
        command.append("--code-only")
    if force:
        command.append("--force")
    return command


def diagnose_graph(executable: Path, graph: Path, *, cwd: Path, env: dict[str, str]) -> dict[str, Any]:
    """Run the read-only graph health check; advisory only, never fails a build."""
    command = [str(executable), "diagnose", "multigraph", "--graph", str(graph), "--json"]
    try:
        code, output = run_command(command, cwd=cwd, env=env)
    except OSError as exc:
        return {"available": False, "error": str(exc)}
    if code != 0:
        return {"available": False, "error": output.splitlines()[-1] if output else f"exit-code-{code}"}
    try:
        payload = json.loads(output[output.index("{"):]) if "{" in output else {}
    except (json.JSONDecodeError, ValueError):
        return {"available": False, "error": "diagnose-output-not-json"}
    warnings = {key: int(payload.get(key, 0) or 0) for key in HEALTH_WARNING_KEYS if int(payload.get(key, 0) or 0)}
    return {"available": True, "warnings": warnings, "healthy": not warnings}


def export_wiki(executable: Path, graph: Path, *, cwd: Path, env: dict[str, str]) -> dict[str, Any]:
    command = [str(executable), "export", "wiki", "--graph", str(graph)]
    code, output = run_command(command, cwd=cwd, env=env)
    return {
        "command": command,
        "exit_code": code,
        "output_tail": output.splitlines()[-4:],
        "wiki_path": str(graph.parent / "wiki") if code == 0 else "",
    }


_COLORAMA_READY = False
_FORE: Any = None
_STYLE: Any = None


def ensure_colorama() -> None:
    global _COLORAMA_READY, _FORE, _STYLE
    if _COLORAMA_READY:
        return
    try:
        from colorama import Fore, Style, init as colorama_init

        colorama_init()
        _FORE = Fore
        _STYLE = Style
    except ModuleNotFoundError:
        _FORE = None
        _STYLE = None
    _COLORAMA_READY = True


def log_graphify(message: str, *, level: str = "info") -> None:
    """Print a Graphify progress line; color only the tag / terminal status."""
    ensure_colorama()
    tag = "[graphify]"
    if _FORE is None or _STYLE is None:
        print(f"{tag} {message}", flush=True)
        return
    dim = getattr(_FORE, "LIGHTBLACK_EX", _FORE.WHITE)
    # Routine progress: dim tag, plain message. Outcomes: color the whole line.
    if level == "ok":
        print(f"{_FORE.GREEN}{tag} {message}{_STYLE.RESET_ALL}", flush=True)
    elif level in {"warn", "skip"}:
        print(f"{_FORE.YELLOW}{tag} {message}{_STYLE.RESET_ALL}", flush=True)
    elif level == "fail":
        print(f"{_FORE.RED}{tag} {message}{_STYLE.RESET_ALL}", flush=True)
    else:
        print(f"{dim}{tag}{_STYLE.RESET_ALL} {message}", flush=True)


def build_repository_graph(
    repo: dict[str, Any],
    executable: Path,
    *,
    force: bool,
    ast_workers: int,
    graphify_version: str,
    semantic: bool = False,
    wiki: bool = False,
) -> dict[str, Any]:
    repo_id = str(repo["id"])
    repo_path = Path(str(repo["path"]))
    started = time.monotonic()
    result: dict[str, Any] = {
        "id": repo_id,
        "status": "failed",
        "dirty": bool(git_dirty_lines(repo_path)),
        "branch": run_git(repo_path, "branch", "--show-current") or "",
        "commit": run_git(repo_path, "rev-parse", "HEAD") or "",
        "preflight": [],
        "commands": [],
    }
    problems = preflight_repository(repo_path)
    result["preflight"] = problems
    if problems:
        result.update(status="skipped", reason=",".join(problems), elapsed_seconds=round(time.monotonic() - started, 3))
        log_graphify(f"{repo_id}: skipped ({result['reason']})", level="skip")
        return result
    graph = repo_path / "graphify-out" / "graph.json"
    env = dict(os.environ)
    env["GRAPHIFY_MAX_WORKERS"] = str(max(1, ast_workers))
    # Large codebases exceed Graphify's default 5k HTML viz cap; keep graphs browsable unless overridden.
    env.setdefault("GRAPHIFY_VIZ_NODE_LIMIT", "250000")
    profile, profile_reason = select_extract_profile(repo, semantic=semantic, env=env)
    result["extract_profile"] = profile
    result["extract_profile_reason"] = profile_reason
    skip, skip_reason, source_fp = should_skip_unchanged(
        repo_path,
        force=force,
        profile=profile,
        graphify_version=graphify_version,
    )
    if skip:
        scan = scan_graph(graph)
        result["security_scan"] = scan
        if not scan["passed"]:
            result.update(status="excluded", reason="security-scan-failed", elapsed_seconds=round(time.monotonic() - started, 3))
            log_graphify(f"{repo_id}: excluded by security scan", level="fail")
            return result
        graph_hash = sha256_file(graph)
        result.update(
            status="unchanged",
            reason=skip_reason,
            graph_path=str(graph),
            graph_sha256=graph_hash,
            structural_sha256=structural_graph_sha256(graph),
            elapsed_seconds=round(time.monotonic() - started, 3),
        )
        if wiki:
            wiki_dir = graph.parent / "wiki"
            if not wiki_dir.exists():
                log_graphify(f"{repo_id}: wiki export (unchanged graph)", level="info")
                result["wiki"] = export_wiki(executable, graph, cwd=repo_path, env=env)
        log_graphify(f"{repo_id}: unchanged — skipped extract ({skip_reason})", level="ok")
        return result

    mode = "force-full" if force else "incremental"
    log_graphify(f"{repo_id}: extract start profile={profile} mode={mode} reason={skip_reason}", level="start")
    command = build_extract_command(executable, profile=profile, force=force)
    code, output = run_command(command, cwd=repo_path, env=env)
    result["commands"].append({"command": command, "exit_code": code, "output_tail": output.splitlines()[-8:]})
    if code != 0 or not graph.exists():
        if "found 0 code" in output or "graph is empty" in output:
            graph = write_empty_repository_graph(repo_path, repo_id)
            graph_hash = sha256_file(graph)
            save_fingerprint(
                repo_path,
                build_fingerprint(
                    source=source_fp,
                    profile=profile,
                    graphify_version=graphify_version,
                    graph_sha256=graph_hash,
                ),
            )
            result.update(
                status="empty",
                reason="no-supported-code",
                graph_path=str(graph),
                graph_sha256=graph_hash,
                structural_sha256=structural_graph_sha256(graph),
                security_scan={"passed": True, "secret_pattern_count": 0, "prohibited_source_count": 0},
                elapsed_seconds=round(time.monotonic() - started, 3),
            )
            log_graphify(f"{repo_id}: empty (no supported code) in {result['elapsed_seconds']}s", level="warn")
            return result
        reason = "graph-build-failed"
        lowered = output.lower()
        if "refusing to overwrite" in lowered or ("refused" in lowered and "shrink" in lowered):
            reason = "shrink-guard-refused"
        elif "cross-project dedup is disabled" in lowered or "nodes span multiple repos" in lowered:
            # Stale/polluted graphify-out can leave multi-repo tags in the
            # incremental merge; a full --force rebuild clears it.
            reason = "cross-project-graph-pollution"
        result.update(reason=reason, elapsed_seconds=round(time.monotonic() - started, 3))
        log_graphify(f"{repo_id}: failed extract ({reason}) in {result['elapsed_seconds']}s", level="fail")
        return result
    log_graphify(f"{repo_id}: cluster start", level="start")
    cluster = [str(executable), "cluster-only", ".", "--no-label"]
    code, output = run_command(cluster, cwd=repo_path, env=env)
    result["commands"].append({"command": cluster, "exit_code": code, "output_tail": output.splitlines()[-8:]})
    if code != 0:
        result.update(reason="graph-cluster-failed", elapsed_seconds=round(time.monotonic() - started, 3))
        log_graphify(f"{repo_id}: failed cluster in {result['elapsed_seconds']}s", level="fail")
        return result
    scan = scan_graph(graph)
    result["security_scan"] = scan
    if not scan["passed"]:
        result.update(status="excluded", reason="security-scan-failed", elapsed_seconds=round(time.monotonic() - started, 3))
        log_graphify(f"{repo_id}: excluded by security scan", level="fail")
        return result
    log_graphify(f"{repo_id}: diagnose", level="info")
    result["health"] = diagnose_graph(executable, graph, cwd=repo_path, env=env)
    if wiki:
        log_graphify(f"{repo_id}: wiki export", level="info")
        result["wiki"] = export_wiki(executable, graph, cwd=repo_path, env=env)
    graph_hash = sha256_file(graph)
    # Refresh source fingerprint after build so dirty-state matches post-build reality.
    source_fp = source_fingerprint(repo_path)
    save_fingerprint(
        repo_path,
        build_fingerprint(
            source=source_fp,
            profile=profile,
            graphify_version=graphify_version,
            graph_sha256=graph_hash,
        ),
    )
    result.update(
        status="built",
        graph_path=str(graph),
        graph_sha256=graph_hash,
        structural_sha256=structural_graph_sha256(graph),
        elapsed_seconds=round(time.monotonic() - started, 3),
    )
    health = health_summary(result)
    health_level = "ok" if (not health or health == "ok") else "warn"
    log_graphify(f"{repo_id}: built in {result['elapsed_seconds']}s health={health or 'ok'}", level=health_level)
    return result


def normalized_bridge_key(node: dict[str, Any], imported_ids: set[str]) -> tuple[str, str] | None:
    node_id = str(node.get("id", ""))
    label = str(node.get("label", "")).strip()
    normalized = str(node.get("norm_label", label)).strip().lower()
    node_type = str(node.get("type") or node.get("node_type") or "").lower()
    metadata = node.get("metadata", {}) if isinstance(node.get("metadata"), dict) else {}
    qualified = str(metadata.get("fqn") or metadata.get("qualified_name") or metadata.get("full_name") or "").strip().lower()
    if qualified:
        return (node_type or "symbol", qualified)
    if node_type in BRIDGE_NODE_TYPES and len(normalized) >= 4 and normalized not in GENERIC_BRIDGE_LABELS:
        return (node_type, normalized)
    if node_id in imported_ids and len(normalized) >= 3 and normalized not in GENERIC_BRIDGE_LABELS:
        return ("import", normalized)
    return None


def merge_graphs(repositories: list[dict[str, Any]], output_path: Path, provenance_path: Path, version: str) -> dict[str, Any]:
    merged_nodes: list[dict[str, Any]] = []
    merged_links: list[dict[str, Any]] = []
    bridge_members: dict[tuple[str, str], list[tuple[str, str]]] = {}
    input_meta: list[dict[str, Any]] = []
    for repo in sorted(repositories, key=lambda item: str(item["id"])):
        repo_id = str(repo["id"])
        graph_path_value = str(repo.get("graph_path", ""))
        data = json.loads(Path(graph_path_value).read_text(encoding="utf-8")) if graph_path_value else {"nodes": [], "links": []}
        links = data.get("links", data.get("edges", []))
        imported_ids = {
            str(link.get("target"))
            for link in links
            if str(link.get("relation") or link.get("type") or "").lower() in {"import", "imports"}
        }
        repo_node_id = f"repo::{repo_id}"
        merged_nodes.append({
            "id": repo_node_id,
            "label": repo_id,
            "file_type": "repository",
            "repo": repo_id,
            "community": -1,
            "source_file": "config/repositories.toml",
            "source_location": "",
        })
        for node in data.get("nodes", []):
            local_id = str(node["id"])
            new_id = f"{repo_id}::{local_id}"
            copied = dict(node)
            copied.update(id=new_id, local_id=local_id, repo=repo_id)
            merged_nodes.append(copied)
            merged_links.append({"source": repo_node_id, "target": new_id, "relation": "contains", "confidence": "EXTRACTED"})
            bridge_key = normalized_bridge_key(node, imported_ids)
            if bridge_key:
                bridge_members.setdefault(bridge_key, []).append((repo_id, new_id))
        for link in links:
            copied = dict(link)
            copied["source"] = f"{repo_id}::{link['source']}"
            copied["target"] = f"{repo_id}::{link['target']}"
            # Graphify stores the canonical caller->callee direction in _src/_tgt
            # slots so directed traversal (path/explain) can recover it from an
            # undirected on-disk graph. Namespace them too or federation would
            # orphan the direction metadata.
            for slot in ("_src", "_tgt"):
                if slot in copied and copied[slot] is not None:
                    copied[slot] = f"{repo_id}::{copied[slot]}"
            copied["repo"] = repo_id
            merged_links.append(copied)
        input_meta.append({
            "id": repo_id,
            "branch": repo.get("branch", ""),
            "commit": repo.get("commit", ""),
            "dirty": bool(repo.get("dirty")),
            "graph_sha256": repo["graph_sha256"],
            "structural_sha256": repo.get("structural_sha256", repo["graph_sha256"]),
        })
    bridge_count = 0
    for (kind, label), members in sorted(bridge_members.items()):
        repos = {repo_id for repo_id, _ in members}
        if len(repos) < 2:
            continue
        digest = hashlib.sha256(f"{kind}:{label}".encode("utf-8")).hexdigest()[:16]
        bridge_id = f"shared::{kind}::{digest}"
        merged_nodes.append({
            "id": bridge_id,
            "label": label,
            "file_type": "shared_symbol",
            "bridge_kind": kind,
            "community": -1,
            "source_file": "federated/shared-symbols",
            "source_location": "",
        })
        for repo_id, node_id in members:
            merged_links.append({
                "source": node_id,
                "target": bridge_id,
                "relation": "shared_symbol",
                "confidence": "INFERRED",
                "context": "cross_repo",
                "repo": repo_id,
            })
        bridge_count += 1
    graph = {"directed": False, "multigraph": False, "graph": {"bridge_schema_version": BRIDGE_SCHEMA_VERSION}, "nodes": merged_nodes, "links": merged_links, "hyperedges": []}
    write_json(output_path, graph)
    provenance = {
        "generated_at": utc_now(),
        "graphify_version": version,
        "bridge_schema_version": BRIDGE_SCHEMA_VERSION,
        "inputs": input_meta,
        "node_count": len(merged_nodes),
        "edge_count": len(merged_links),
        "bridge_count": bridge_count,
    }
    write_json(provenance_path, provenance)
    return provenance


def input_signature(results: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {"id": str(item["id"]), "structural_sha256": str(item.get("structural_sha256", item["graph_sha256"]))}
        for item in sorted(results, key=lambda value: str(value["id"]))
    ]


def existing_signature(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if data.get("bridge_schema_version") != BRIDGE_SCHEMA_VERSION:
        return []
    return [
        {"id": str(item.get("id")), "structural_sha256": str(item.get("structural_sha256", item.get("graph_sha256")))}
        for item in data.get("inputs", [])
    ]


def health_summary(item: dict[str, Any]) -> str:
    health = item.get("health")
    if not isinstance(health, dict):
        return ""
    if not health.get("available"):
        return "unavailable"
    if health.get("healthy"):
        return "ok"
    warnings = health.get("warnings", {})
    return "; ".join(f"{count} {key}" for key, count in sorted(warnings.items()))


def write_cycle_report(path: Path, result: dict[str, Any]) -> None:
    lines = ["# Graphify Cycle Summary", "", f"Generated: {result['generated_at']}", f"Status: {result['status']}", "", "| Repository | Status | Dirty | Profile | Health | Reason |", "| --- | --- | --- | --- | --- | --- |"]
    for item in result["repositories"]:
        lines.append(
            f"| {item['id']} | {item['status']} | {str(item.get('dirty', False)).lower()} | "
            f"{item.get('extract_profile', '')} | {health_summary(item)} | {item.get('reason', '')} |"
        )
    lines.extend(["", f"- Federated graph: `{result.get('federated_graph', '')}`", f"- Merge skipped unchanged: {str(result.get('merge_skipped', False)).lower()}"])
    federated_health = result.get("federated_health")
    if isinstance(federated_health, dict):
        lines.append(f"- Federated graph health: {health_summary({'health': federated_health}) or 'ok'}")
    if result.get("federated_wiki"):
        lines.append(f"- Federated wiki: `{result['federated_wiki']}`")
    write_text(path, "\n".join(lines))


def run_cycle(
    *,
    repository_ids: list[str],
    force: bool,
    max_parallel: int,
    skip_merge: bool,
    strict: bool,
    reports_dir: Path,
    merge_selected: bool = False,
    semantic: bool = False,
    wiki: bool = False,
) -> int:
    executable = find_graphify()
    version = graphify_version(executable)
    repositories = load_repository_registry(ROOT / "config" / "repositories.toml")
    if repository_ids:
        selected = set(repository_ids)
        repositories = [repo for repo in repositories if str(repo.get("id")) in selected]
        missing = sorted(selected - {str(repo.get("id")) for repo in repositories})
        if missing:
            raise RuntimeError("unknown repository id(s): " + ", ".join(missing))
    else:
        # Reference-only registrations (graphify_cycle = false) stay out of the
        # default cycle and federation; they remain reachable via explicit --repo.
        repositories = [repo for repo in repositories if cycle_enabled(repo)]
    if not repositories:
        raise RuntimeError("no enabled repositories selected")
    ast_workers = max(1, (os.cpu_count() or 2) // max(1, max_parallel))
    try:
        from tqdm.auto import tqdm
    except ModuleNotFoundError:
        tqdm = None  # type: ignore[assignment]
    ensure_colorama()
    results: list[dict[str, Any]] = []
    log_graphify(
        f"building {len(repositories)} repo graph(s) with max_parallel={max_parallel} "
        f"graphify={version.strip()}",
        level="info",
    )
    with ThreadPoolExecutor(max_workers=max(1, max_parallel)) as executor:
        futures = {
            executor.submit(
                build_repository_graph,
                repo,
                executable,
                force=force,
                ast_workers=ast_workers,
                graphify_version=version,
                semantic=semantic,
                wiki=wiki,
            ): repo
            for repo in repositories
        }
        if tqdm is None:
            for future in as_completed(futures):
                results.append(future.result())
        else:
            with tqdm(total=len(futures), desc="graphify repos", unit="repo", dynamic_ncols=True, leave=True) as bar:
                for future in as_completed(futures):
                    item = future.result()
                    results.append(item)
                    bar.set_postfix_str(f"{item['id']}:{item['status']}"[:40])
                    bar.update(1)
    current = [item for item in results if item["status"] in {"built", "empty", "unchanged"}]
    failed = [item for item in results if item["status"] not in {"built", "empty", "unchanged"}]
    federated = ROOT / "graphify-out" / "federated" / "graph.json"
    provenance = federated.parent / "provenance.json"
    merge_skipped = False
    aggregate_ready = bool(current)
    effective_skip_merge = skip_merge or (bool(repository_ids) and not merge_selected)
    if effective_skip_merge and federated.exists():
        merge_skipped = True
        log_graphify("federated merge skipped (unchanged selection or --skip-merge)", level="warn")
    if not effective_skip_merge and current:
        signature = input_signature(current)
        if not force and federated.exists() and existing_signature(provenance) == signature:
            merge_skipped = True
            log_graphify("federated merge skipped (input signature unchanged)", level="warn")
        else:
            log_graphify(f"federated merge starting ({len(current)} graphs)", level="start")
            staging = federated.parent / ".staging" / "graphify-out" / "graph.json"
            staging_provenance = federated.parent / ".staging" / "provenance.json"
            merge_graphs(current, staging, staging_provenance, version)
            env = dict(os.environ)
            env["GRAPHIFY_MAX_WORKERS"] = str(ast_workers)
            log_graphify("federated cluster-only start", level="start")
            code, output = run_command([str(executable), "cluster-only", str(ROOT), "--graph", str(staging), "--no-label"], cwd=ROOT, env=env)
            if code != 0:
                log_graphify("federated cluster-only failed", level="fail")
                failed.append({"id": "federated", "status": "failed", "reason": "federated-cluster-failed", "output_tail": output.splitlines()[-8:]})
                for stale in (federated, federated.parent / "GRAPH_REPORT.md", federated.parent / "graph.html", provenance):
                    if stale.exists():
                        stale.unlink()
                aggregate_ready = False
            else:
                staged_html = staging.parent / "graph.html"
                if not staged_html.exists():
                    log_graphify("federated tree visualization start", level="start")
                    tree_command = [
                        str(executable),
                        "tree",
                        "--graph",
                        str(staging),
                        "--output",
                        str(staged_html),
                        "--root",
                        str(ROOT.parent),
                        "--label",
                        "Federated Repository Graph",
                    ]
                    tree_code, tree_output = run_command(tree_command, cwd=ROOT, env=env)
                    if tree_code != 0 or not staged_html.exists():
                        failed.append({
                            "id": "federated",
                            "status": "failed",
                            "reason": "federated-visualization-failed",
                            "output_tail": tree_output.splitlines()[-8:],
                        })
                        for stale in (federated, federated.parent / "GRAPH_REPORT.md", federated.parent / "graph.html", provenance):
                            if stale.exists():
                                stale.unlink()
                        aggregate_ready = False
                if not aggregate_ready:
                    pass
                else:
                    federated.parent.mkdir(parents=True, exist_ok=True)
                    for name in ("graph.json", "GRAPH_REPORT.md", "graph.html"):
                        shutil.copy2(staging.parent / name, federated.parent / name)
                    shutil.copy2(staging_provenance, provenance)
    federated_health: dict[str, Any] | None = None
    federated_wiki = ""
    if federated.exists() and not merge_skipped and not effective_skip_merge and aggregate_ready and current:
        env = dict(os.environ)
        env["GRAPHIFY_MAX_WORKERS"] = str(ast_workers)
        log_graphify("federated diagnose", level="info")
        federated_health = diagnose_graph(executable, federated, cwd=ROOT, env=env)
        if wiki:
            log_graphify("federated wiki export", level="info")
            wiki_result = export_wiki(executable, federated, cwd=ROOT, env=env)
            federated_wiki = wiki_result.get("wiki_path", "")
        log_graphify("federated graph ready", level="ok")
    status = "completed"
    if not current or (not effective_skip_merge and not aggregate_ready):
        status = "failed"
    elif failed:
        status = "degraded"
    result = {
        "generated_at": utc_now(),
        "status": status,
        "graphify_version": version,
        "repositories": sorted(results, key=lambda item: str(item["id"])),
        "federated_graph": str(federated) if federated.exists() else "",
        "merge_skipped": merge_skipped,
        "federated_health": federated_health,
        "federated_wiki": federated_wiki,
    }
    reports_dir.mkdir(parents=True, exist_ok=True)
    write_json(reports_dir / "graphify-cycle-summary.json", result)
    write_cycle_report(reports_dir / "graphify-cycle-summary.md", result)
    ensure_colorama()
    status_level = {"completed": "ok", "degraded": "warn", "failed": "fail"}.get(status, "info")
    for item in result["repositories"]:
        reason = item.get("reason", "")
        suffix = f" reason={reason}" if reason else ""
        item_level = {
            "built": "ok",
            "unchanged": "ok",
            "empty": "warn",
            "skipped": "skip",
            "excluded": "fail",
            "failed": "fail",
        }.get(str(item["status"]), "plain")
        log_graphify(
            f"{item['id']}: {item['status']} dirty={str(item.get('dirty', False)).lower()}"
            f" profile={item.get('extract_profile', '')}{suffix}",
            level=item_level,
        )
    log_graphify(f"cycle status: {status}", level=status_level)
    log_graphify(f"federated graph: {result['federated_graph']}", level="info")
    if result.get("federated_health"):
        fed_health = health_summary({"health": result["federated_health"]}) or "ok"
        log_graphify(f"federated health: {fed_health}", level="ok" if fed_health == "ok" else "warn")
    if status == "failed" or (strict and failed):
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh per-repository Graphify graphs and build a governed federated graph.")
    parser.add_argument("--repo", action="append", default=[], help="Registered repository id; repeat to select multiple repositories.")
    parser.add_argument("--force", action="store_true", help="Full rebuild (skips the incremental gate; permits an intentional shrink).")
    parser.add_argument("--max-parallel", type=int, default=2)
    parser.add_argument("--skip-merge", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    parser.add_argument(
        "--semantic",
        action="store_true",
        help="Include semantic-document extraction for repositories opted in with graphify_semantic = true (requires an LLM backend key).",
    )
    parser.add_argument(
        "--code-only",
        action="store_true",
        help="Force AST-only extraction for this run even when --semantic is present.",
    )
    parser.add_argument("--wiki", action="store_true", help="Export agent-crawlable wikis for built graphs and the federated graph.")
    args = parser.parse_args()
    ensure_colorama()
    try:
        return run_cycle(
            repository_ids=args.repo,
            force=args.force,
            max_parallel=args.max_parallel,
            skip_merge=args.skip_merge,
            strict=args.strict,
            reports_dir=args.reports_dir,
            semantic=args.semantic and not args.code_only,
            wiki=args.wiki,
        )
    except (RuntimeError, ValueError) as exc:
        log_graphify(f"ERROR: {exc}", level="fail")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
