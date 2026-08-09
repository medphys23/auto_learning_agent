from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> int:
    print(" ".join(f'"{item}"' if " " in item else item for item in command))
    process = subprocess.run(command, cwd=ROOT)
    return int(process.returncode)


def ensure_venv(python_executable: str) -> str:
    venv_python = ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return str(venv_python)
    print("Bootstrapping repo-local .venv with uv ...")
    bootstrap = subprocess.run(["uv", "venv", "--python", "3.11", ".venv"], cwd=ROOT)
    if bootstrap.returncode != 0:
        return python_executable
    install = subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(venv_python),
            "--link-mode",
            "hardlink",
            "-r",
            "requirements.txt",
        ],
        cwd=ROOT,
    )
    if install.returncode != 0:
        return python_executable
    return str(venv_python)


def build_cycle_command(
    *,
    python_executable: str,
    strict: bool,
    skip_graphify: bool,
    skip_dependency_audit: bool,
    verbose: bool,
) -> list[str]:
    command = [python_executable, "scripts/run_optimized_knowledge_cycle.py"]
    if strict:
        command.append("--strict")
    else:
        command.append("--continue-on-dirty")
    if skip_graphify:
        command.append("--skip-graphify")
    if skip_dependency_audit:
        command.append("--skip-dependency-audit")
    if verbose:
        command.append("--verbose")
    return command


def build_publish_command(
    *,
    python_executable: str,
    apply: bool,
    confirm_global_write: bool,
    runtime_smoke: bool,
    skip_runtime_smoke: bool,
    force_parent_model: bool,
) -> list[str]:
    command = [python_executable, "scripts/publish_global_rules.py", "--profile", "optimized"]
    if apply:
        command.append("--apply")
        if confirm_global_write:
            command.append("--confirm-global-write")
    else:
        command.append("--preview")
    if runtime_smoke:
        command.append("--runtime-smoke")
    if skip_runtime_smoke:
        command.append("--skip-runtime-smoke")
    if force_parent_model:
        command.append("--force-parent-model")
    return command


def main() -> int:
    parser = argparse.ArgumentParser(
        description="One-command orchestrator startup: graph refresh, harvest, synthesis, and optional global publication."
    )
    parser.add_argument("--apply-global", action="store_true", help="Apply optimized global rules after readiness passes.")
    parser.add_argument("--confirm-global-write", action="store_true", help="Required with --apply-global.")
    parser.add_argument("--apply-repo-hints", action="store_true", help="Apply orchestrator retrieval hints to registered repos.")
    parser.add_argument("--confirm-repo-write", action="store_true", help="Required with --apply-repo-hints.")
    parser.add_argument("--strict", action="store_true", help="Fail when dirty repositories block readiness.")
    parser.add_argument("--skip-graphify", action="store_true", help="Skip per-repository and federated graph refresh.")
    parser.add_argument("--skip-dependency-audit", action="store_true")
    parser.add_argument("--runtime-smoke", action="store_true", help="Require GPT-5.6 runtime smoke before parent model switch.")
    parser.add_argument("--skip-runtime-smoke", action="store_true", help="Skip parent model switch on global apply.")
    parser.add_argument("--force-parent-model", action="store_true", help="Apply GPT-5.6 Terra even when runtime smoke fails.")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.apply_global and not args.confirm_global_write:
        print("ERROR: --apply-global requires --confirm-global-write")
        return 2
    if args.apply_repo_hints and not args.confirm_repo_write:
        print("ERROR: --apply-repo-hints requires --confirm-repo-write")
        return 2

    python_executable = ensure_venv(sys.executable)

    validate_exit = run([python_executable, "scripts/validate_codex_config.py"])
    if validate_exit != 0:
        return validate_exit

    # Always stream child-step logs during startup so Graphify/harvest activity is visible.
    # Pass --quiet through the knowledge cycle only when the operator opts out later.
    cycle_exit = run(
        build_cycle_command(
            python_executable=python_executable,
            strict=args.strict,
            skip_graphify=args.skip_graphify,
            skip_dependency_audit=args.skip_dependency_audit,
            verbose=True,
        )
    )
    if cycle_exit != 0:
        print("ERROR: optimized knowledge cycle failed.")
        print(r"Review reports\optimized-cutover-readiness.md and reports\optimized-knowledge-cycle.log")
        return cycle_exit

    publish_exit = run(
        build_publish_command(
            python_executable=python_executable,
            apply=args.apply_global,
            confirm_global_write=args.confirm_global_write,
            runtime_smoke=args.runtime_smoke,
            skip_runtime_smoke=args.skip_runtime_smoke,
            force_parent_model=args.force_parent_model,
        )
    )
    if publish_exit != 0:
        print("ERROR: optimized publication failed.")
        return publish_exit

    if args.apply_global and args.apply_repo_hints:
        hints_exit = run(
            [
                python_executable,
                "scripts/propagate_orchestrator_retrieval_hints.py",
                "--apply",
                "--confirm-repo-write",
            ]
        )
        if hints_exit != 0:
            print("ERROR: repository hint propagation failed.")
            return hints_exit

    if args.apply_global:
        print("Startup completed with global publication applied.")
        if args.apply_repo_hints:
            print("Repository retrieval hints applied.")
    else:
        print("Startup preview completed. No global files were changed.")
        print("To publish globals: .\\scripts\\run-startup.ps1 -ApplyGlobal -ConfirmGlobalWrite")
    print(r"Reports: reports\optimized-knowledge-cycle-summary.md, reports\optimized-cutover-readiness.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
