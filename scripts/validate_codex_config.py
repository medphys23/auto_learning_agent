from __future__ import annotations

import argparse
from pathlib import Path

from orchestrator_common import read_toml


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local or global Codex TOML files for the orchestrator MVP.")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--global", dest="global_mode", action="store_true", help="Treat --root as CODEX_HOME.")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.global_mode and args.root == Path("."):
        root = Path.home() / ".codex"
    files = toml_files(root, global_mode=args.global_mode)
    errors = validate_files(files) + validate_references(root, global_mode=args.global_mode)
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
