from __future__ import annotations

import argparse
from pathlib import Path

from orchestrator_common import read_toml


def toml_files(root: Path) -> list[Path]:
    candidates = [root / ".codex" / "config.toml", *sorted((root / ".codex" / "agents").glob("*.toml")), *sorted((root / "config").glob("*.toml"))]
    return [path for path in candidates if path.exists()]


def validate_files(files: list[Path]) -> list[str]:
    errors: list[str] = []
    for path in files:
        try:
            read_toml(path)
        except Exception as exc:  # noqa: BLE001 - surface exact parser failure.
            errors.append(f"{path}: {exc}")
    return errors


def validate_references(root: Path) -> list[str]:
    errors: list[str] = []
    config = root / ".codex" / "config.toml"
    if not config.exists():
        return [f"{config}: missing"]
    data = read_toml(config)
    agents = data.get("agents", {})
    if isinstance(agents, dict):
        for name, value in agents.items():
            if not isinstance(value, dict):
                continue
            config_file = value.get("config_file")
            if config_file and not (root / ".codex" / str(config_file)).exists():
                errors.append(f"agent {name} references missing .codex/{config_file}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local Codex TOML files for the orchestrator MVP.")
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    root = args.root.resolve()
    files = toml_files(root)
    errors = validate_files(files) + validate_references(root)
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
