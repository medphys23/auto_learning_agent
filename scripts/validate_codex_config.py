from __future__ import annotations

import argparse
from pathlib import Path

from orchestrator_common import read_toml


EXPECTED_AGENT_MODELS = {
    "luna_worker": ("gpt-5.6-luna", "low"),
    "terra_worker": ("gpt-5.6-terra", "medium"),
    "sol_specialist": ("gpt-5.6-sol", "xhigh"),
}
REQUIRED_AGENT_FIELDS = ("name", "description", "developer_instructions")


def toml_files(root: Path, *, global_mode: bool = False) -> list[Path]:
    if global_mode:
        candidates = [root / "config.toml", *sorted((root / "agents").glob("*.toml"))]
        return [path for path in candidates if path.exists()]
    candidates = [
        root / ".codex" / "config.toml",
        *sorted((root / ".codex" / "agents").glob("*.toml")),
        *sorted((root / "config").glob("*.toml")),
        *sorted((root / "master" / "codex").glob("*.toml")),
        *sorted((root / "master" / "codex" / "agents").glob("*.toml")),
        *sorted((root / "master" / "optimized" / "codex" / "agents").glob("*.toml")),
        *sorted((root / "master" / "optimized" / "codex" / "config").glob("*.toml")),
    ]
    return [path for path in candidates if path.exists()]


def validate_files(files: list[Path]) -> list[str]:
    errors: list[str] = []
    for path in files:
        try:
            read_toml(path)
        except Exception as exc:  # noqa: BLE001 - surface exact parser failure.
            errors.append(f"{path}: {exc}")
    return errors


def validate_references(root: Path, *, global_mode: bool = False) -> list[str]:
    errors: list[str] = []
    config = root / "config.toml" if global_mode else root / ".codex" / "config.toml"
    if not config.exists():
        return [f"{config}: missing"]
    data = read_toml(config)
    agents = data.get("agents", {})
    if isinstance(agents, dict):
        for name, value in agents.items():
            if not isinstance(value, dict):
                continue
            config_file = value.get("config_file")
            if config_file:
                base = root if global_mode else root / ".codex"
                if not (base / str(config_file)).exists():
                    errors.append(f"agent {name} references missing {base / str(config_file)}")
    return errors


def validate_agent_files(root: Path, *, global_mode: bool = False) -> list[str]:
    errors: list[str] = []
    agent_dirs = [root / "agents"] if global_mode else [root / ".codex" / "agents", root / "master" / "codex" / "agents", root / "master" / "optimized" / "codex" / "agents"]
    for agent_dir in agent_dirs:
        if not agent_dir.exists():
            continue
        seen: dict[str, Path] = {}
        for path in sorted(agent_dir.glob("*.toml")):
            try:
                data = read_toml(path)
            except Exception:
                continue
            name = data.get("name")
            if isinstance(name, str):
                if name in seen and seen[name] != path:
                    errors.append(f"duplicate agent name {name}: {seen[name]} and {path}")
                seen[name] = path
            for field in REQUIRED_AGENT_FIELDS:
                if not data.get(field):
                    errors.append(f"{path}: missing required custom-agent field {field}")
            if name in EXPECTED_AGENT_MODELS:
                expected_model, expected_effort = EXPECTED_AGENT_MODELS[name]
                if data.get("model") != expected_model:
                    errors.append(f"{path}: expected model {expected_model}")
                if data.get("model_reasoning_effort") != expected_effort:
                    errors.append(f"{path}: expected model_reasoning_effort {expected_effort}")
    return errors


def validate_global_config_policy(root: Path) -> list[str]:
    config = root / "config.toml"
    if not config.exists():
        return []
    errors: list[str] = []
    data = read_toml(config)
    agents = data.get("agents", {})
    if isinstance(agents, dict):
        if agents.get("max_depth") != 1:
            errors.append("agents.max_depth must remain 1")
        for preserved in ("job_max_runtime_seconds",):
            if preserved not in agents:
                errors.append(f"agents.{preserved} is missing")
    for key in ("notify", "windows", "plugins", "mcp_servers"):
        if key not in data:
            errors.append(f"global config missing preserved {key} section")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local or global Codex TOML files for the orchestrator MVP.")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--global", dest="global_mode", action="store_true", help="Treat --root as CODEX_HOME.")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.global_mode and args.root == Path("."):
        root = Path.home() / ".codex"
    files = toml_files(root, global_mode=args.global_mode)
    errors = validate_files(files) + validate_references(root, global_mode=args.global_mode) + validate_agent_files(root, global_mode=args.global_mode)
    if args.global_mode:
        errors += validate_global_config_policy(root)
    if errors:
        print("TOML validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"TOML validation OK: {len(files)} files parsed.")
    print("Schema validation note: no live Codex JSON schema validator is bundled; this script validates parseability and local references only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
