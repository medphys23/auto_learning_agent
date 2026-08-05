from __future__ import annotations

import argparse
import json
import subprocess
import tomllib
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
CODEX_HOME = Path.home() / ".codex"
EXPECTED_MODELS = {
    "luna_worker": ("gpt-5.6-luna", "low"),
    "terra_worker": ("gpt-5.6-terra", "medium"),
    "sol_specialist": ("gpt-5.6-sol", "xhigh"),
    "systems_architect": ("gpt-5.6-sol", "high"),
    "reliability_operations_reviewer": ("gpt-5.6-terra", "high"),
    "security_boundary_reviewer": ("gpt-5.6-sol", "high"),
    "quality_release_reviewer": ("gpt-5.6-terra", "high"),
}
SPECIALIST_ROLES = (
    "systems_architect",
    "reliability_operations_reviewer",
    "security_boundary_reviewer",
    "quality_release_reviewer",
)
SPECIALIST_KEYWORDS = {
    "security_boundary_reviewer": {
        "auth",
        "authorization",
        "credential",
        "identity",
        "secret",
        "security",
        "ssrf",
        "subprocess",
        "trust",
    },
    "systems_architect": {
        "architecture",
        "boundary",
        "cross-boundary",
        "database",
        "deployment",
        "interface",
        "migration",
        "provider",
        "state",
    },
    "reliability_operations_reviewer": {
        "backpressure",
        "cancellation",
        "distributed",
        "health",
        "network",
        "operations",
        "readiness",
        "recovery",
        "reliability",
        "retry",
        "shutdown",
        "timeout",
    },
    "quality_release_reviewer": {
        "artifact",
        "ci",
        "dependency",
        "documentation",
        "provenance",
        "quality",
        "release",
        "rollback",
        "supply-chain",
        "test",
    },
}
ROUTES = {"direct", "luna_worker", "terra_worker", "sol_specialist"}
RISK_LEVELS = {"low", "medium", "high", "critical"}
VALIDATION_STATUSES = {"passed", "failed", "partial"}
OUTCOMES = {"success", "failure", "partial"}
SENSITIVE_NOTE_FRAGMENTS = ("secret", "credential", "token", "password", "api_key", "apikey", "bearer ", "private key")


def read_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def validate_agent_file(path: Path) -> list[str]:
    errors: list[str] = []
    data = read_toml(path)
    for field in ("name", "description", "developer_instructions"):
        if not data.get(field):
            errors.append(f"{path}: missing {field}")
    name = data.get("name")
    if name in EXPECTED_MODELS:
        expected_model, expected_effort = EXPECTED_MODELS[str(name)]
        if data.get("model") != expected_model:
            errors.append(f"{path}: expected model {expected_model}")
        if data.get("model_reasoning_effort") != expected_effort:
            errors.append(f"{path}: expected model_reasoning_effort {expected_effort}")
    if name in SPECIALIST_ROLES and data.get("sandbox_mode") != "read-only":
        errors.append(f"{path}: expected sandbox_mode read-only")
    return errors


def validate_agent_dir(agent_dir: Path, *, require_expected: bool) -> list[str]:
    errors: list[str] = []
    names: dict[str, Path] = {}
    for path in sorted(agent_dir.glob("*.toml")):
        try:
            data = read_toml(path)
        except Exception as exc:  # noqa: BLE001 - exact parser error belongs in output.
            errors.append(f"{path}: {exc}")
            continue
        name = data.get("name")
        if isinstance(name, str):
            if name in names:
                errors.append(f"duplicate agent name {name}: {names[name]} and {path}")
            names[name] = path
        errors.extend(validate_agent_file(path))
    if require_expected:
        for name in EXPECTED_MODELS:
            if name not in names:
                errors.append(f"{agent_dir}: missing expected agent {name}")
    return errors


def validate_config(config_path: Path) -> list[str]:
    errors: list[str] = []
    data = read_toml(config_path)
    agents = data.get("agents", {})
    if not isinstance(agents, dict):
        return ["[agents] is missing or is not a TOML table"]
    if agents.get("max_depth") != 1:
        errors.append("agents.max_depth must be 1")
    if agents.get("max_threads") != 4:
        errors.append("agents.max_threads must be 4")
    if agents.get("interrupt_message") is not True:
        errors.append("agents.interrupt_message must be true")
    for name in EXPECTED_MODELS:
        registration = agents.get(name)
        if not isinstance(registration, dict):
            errors.append(f"agents.{name} registration is missing")
        elif registration.get("config_file") != f"agents/{name}.toml":
            errors.append(f"agents.{name}.config_file must be agents/{name}.toml")
    return errors


def select_specialist_roles(
    task_category: str,
    risk_level: str,
    risk_tags: list[str] | tuple[str, ...] = (),
) -> list[str]:
    terms = {
        token
        for value in (task_category, *risk_tags)
        for token in str(value).lower().replace("_", "-").split("-")
        if token
    }
    normalized_values = {
        str(task_category).lower().replace("_", "-"),
        *(str(tag).lower().replace("_", "-") for tag in risk_tags),
    }
    cross_boundary = bool(
        {"architecture", "boundary", "cross-boundary", "migration", "provider", "deployment", "database"}
        & (terms | normalized_values)
    )
    if risk_level not in {"high", "critical"} and not cross_boundary:
        return []
    selected: list[str] = []
    search_terms = terms | normalized_values
    for role in SPECIALIST_ROLES:
        if SPECIALIST_KEYWORDS[role] & search_terms:
            selected.append(role)
        if len(selected) == 2:
            break
    if not selected:
        selected.append("systems_architect")
    return selected


def validate_routing_event(event: dict[str, Any]) -> list[str]:
    required = {
        "timestamp_utc",
        "repository",
        "task_category",
        "risk_level",
        "initial_route",
        "final_route",
        "escalated",
        "escalation_reason",
        "validation_status",
        "outcome",
        "reusable_pattern",
        "notes",
    }
    errors = [f"missing field: {field}" for field in sorted(required - set(event))]
    if errors:
        return errors
    if event["risk_level"] not in RISK_LEVELS:
        errors.append("risk_level is invalid")
    if event["initial_route"] not in ROUTES:
        errors.append("initial_route is invalid")
    if event["final_route"] not in ROUTES:
        errors.append("final_route is invalid")
    if event["validation_status"] not in VALIDATION_STATUSES:
        errors.append("validation_status is invalid")
    if event["outcome"] not in OUTCOMES:
        errors.append("outcome is invalid")
    if not isinstance(event["escalated"], bool):
        errors.append("escalated must be boolean")
    if not isinstance(event["reusable_pattern"], bool):
        errors.append("reusable_pattern must be boolean")
    specialist_roles = event.get("specialist_roles")
    if specialist_roles is not None:
        if not isinstance(specialist_roles, list):
            errors.append("specialist_roles must be an array")
        else:
            if len(specialist_roles) > 4:
                errors.append("specialist_roles may contain at most 4 roles")
            if len(specialist_roles) != len(set(str(role) for role in specialist_roles)):
                errors.append("specialist_roles must be unique")
            invalid_roles = [role for role in specialist_roles if not isinstance(role, str) or role not in SPECIALIST_ROLES]
            if invalid_roles:
                errors.append("specialist_roles contains an unknown role")
    notes = str(event.get("notes", "")).lower()
    if any(fragment in notes for fragment in SENSITIVE_NOTE_FRAGMENTS):
        errors.append("notes contain sensitive-looking text")
    return errors


def validate_routing_history(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{path}:{line_number}: invalid JSONL: {exc}")
            continue
        if not isinstance(event, dict):
            errors.append(f"{path}:{line_number}: event must be object")
            continue
        errors.extend(f"{path}:{line_number}: {error}" for error in validate_routing_event(event))
    return errors


def model_smoke(codex_cli: Path, model: str, cwd: Path) -> tuple[bool, str]:
    command = [
        str(codex_cli),
        "exec",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--model",
        model,
        "--cd",
        str(cwd),
        "Return exactly MODEL_OK.",
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    output = (result.stdout + "\n" + result.stderr).strip()
    sanitized = "\n".join(line for line in output.splitlines() if "token" not in line.lower() and "auth" not in line.lower())
    return result.returncode == 0 and "MODEL_OK" in output, sanitized[-1000:]


def validate_static(repo_root: Path, codex_home: Path) -> list[str]:
    errors: list[str] = []
    canonical_agents = repo_root / "master" / "optimized" / "codex" / "agents"
    runtime_agents = codex_home / "agents"
    if canonical_agents.exists():
        errors.extend(validate_agent_dir(canonical_agents, require_expected=True))
    if runtime_agents.exists():
        errors.extend(validate_agent_dir(runtime_agents, require_expected=False))
    canonical_config = repo_root / "master" / "optimized" / "codex" / "config" / "orchestrator-managed.toml"
    if canonical_config.exists():
        errors.extend(validate_config(canonical_config))
    runtime_config = codex_home / "config.toml"
    if runtime_config.exists():
        data = read_toml(runtime_config)
        if data.get("model") == "gpt-5.6-terra":
            errors.extend(validate_config(runtime_config))
    errors.extend(validate_routing_history(repo_root / "knowledge" / "model-routing" / "routing-history.jsonl"))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate adaptive GPT-5.6 Codex routing artifacts.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--codex-home", type=Path, default=CODEX_HOME)
    parser.add_argument("--runtime-smoke", action="store_true", help="Run Codex CLI smoke tests for GPT-5.6 models.")
    parser.add_argument("--codex-cli", type=Path, default=None)
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    codex_home = args.codex_home.resolve()
    errors = validate_static(repo_root, codex_home)
    if args.runtime_smoke:
        codex_cli = args.codex_cli
        if codex_cli is None:
            config = read_toml(codex_home / "config.toml")
            env = config.get("mcp_servers", {}).get("node_repl", {}).get("env", {})
            codex_cli_value = env.get("CODEX_CLI_PATH")
            codex_cli = Path(str(codex_cli_value)) if codex_cli_value else Path("codex")
        for model in dict.fromkeys(model for model, _ in EXPECTED_MODELS.values()):
            ok, summary = model_smoke(codex_cli, model, repo_root)
            print(f"{model}: {'MODEL_OK' if ok else 'FAILED'}")
            if not ok:
                errors.append(f"{model} smoke test failed: {summary}")
    if errors:
        print("Codex routing validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Codex routing validation OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
