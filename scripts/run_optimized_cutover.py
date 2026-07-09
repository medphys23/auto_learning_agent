from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> int:
    print(" ".join(command))
    process = subprocess.run(command, cwd=ROOT)
    return int(process.returncode)


def build_cycle_command(
    *,
    python_executable: str,
    allow_dirty: bool,
    skip_dependency_audit: bool,
    verbose: bool,
) -> list[str]:
    command = [python_executable, "scripts/run_optimized_knowledge_cycle.py", "--strict"]
    if allow_dirty:
        command.append("--continue-on-dirty")
    if skip_dependency_audit:
        command.append("--skip-dependency-audit")
    if verbose:
        command.append("--verbose")
    return command


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run optimized harvest/readiness and optionally publish optimized global rules."
    )
    parser.add_argument("--apply", action="store_true", help="Publish optimized global rules after readiness passes.")
    parser.add_argument("--confirm-global-write", action="store_true", help="Required with --apply.")
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Allow dirty repository blockers during the readiness cycle. Other readiness failures still stop the cutover.",
    )
    parser.add_argument("--skip-dependency-audit", action="store_true", help="Skip the dependency catalog audit in the cycle.")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.apply and not args.confirm_global_write:
        print("ERROR: --apply requires --confirm-global-write")
        return 2

    cycle = build_cycle_command(
        python_executable=sys.executable,
        allow_dirty=args.allow_dirty,
        skip_dependency_audit=args.skip_dependency_audit,
        verbose=args.verbose,
    )
    cycle_exit = run(cycle)
    if cycle_exit != 0:
        print("ERROR: optimized knowledge cycle did not pass readiness gates.")
        print(r"Review reports\optimized-cutover-readiness.md before retrying.")
        return cycle_exit

    preview_exit = run([sys.executable, "scripts/publish_global_rules.py", "--preview", "--profile", "optimized"])
    if preview_exit != 0:
        print("ERROR: optimized publication preview failed.")
        return preview_exit

    if not args.apply:
        print("Optimized cutover preview completed. No global files were changed.")
        print("To publish, rerun with --apply --confirm-global-write.")
        return 0

    apply_exit = run(
        [
            sys.executable,
            "scripts/publish_global_rules.py",
            "--apply",
            "--confirm-global-write",
            "--profile",
            "optimized",
        ]
    )
    if apply_exit != 0:
        print("ERROR: optimized global publication failed.")
        return apply_exit

    print("Optimized global publication completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
