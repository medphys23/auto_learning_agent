from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from orchestrator_common import read_json, utc_now
from plan_optimized_cutover import plan_optimized_cutover


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class CycleStep:
    name: str
    command: list[str]


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def command_text(command: list[str]) -> str:
    return " ".join(f'"{item}"' if " " in item else item for item in command)


def build_steps(*, python_executable: str, reports_dir: Path, skip_dependency_audit: bool, skip_graphify: bool = False) -> list[CycleStep]:
    steps = [
        CycleStep("discover repositories", [python_executable, "scripts/discover_repositories.py"]),
    ]
    if not skip_graphify:
        steps.append(CycleStep("refresh repository graphs", [python_executable, "scripts/run_graphify_cycle.py", "--reports-dir", str(reports_dir)]))
    steps.append(CycleStep("harvest repositories", [python_executable, "scripts/harvest_repositories.py"]))
    if not skip_dependency_audit:
        steps.append(CycleStep("audit dependency catalog", [python_executable, "scripts/audit_dependency_catalog.py", "--reports-dir", str(reports_dir)]))
    steps.extend(
        [
            CycleStep(
                "synthesize optimized instructions",
                [
                    python_executable,
                    "scripts/synthesize_top_level_instructions.py",
                    "--preview",
                    "--profile",
                    "optimized",
                    "--reports-dir",
                    str(reports_dir),
                ],
            ),
            CycleStep("audit context budget", [python_executable, "scripts/audit_context_budget.py", "--reports-dir", str(reports_dir)]),
        ]
    )
    return steps


def run_step(step: CycleStep, *, log_handle: Any, progress: Any, verbose: bool) -> dict[str, Any]:
    started = utc_now()
    start = time.monotonic()
    log_handle.write(f"\n## {step.name}\n")
    log_handle.write(f"Started: {started}\n")
    log_handle.write(f"Command: {command_text(step.command)}\n\n")
    log_handle.flush()
    process = subprocess.Popen(
        step.command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert process.stdout is not None
    output_lines = 0
    for line in process.stdout:
        output_lines += 1
        log_handle.write(line)
        if verbose:
            progress.write(line.rstrip())
    exit_code = process.wait()
    elapsed = round(time.monotonic() - start, 3)
    finished = utc_now()
    log_handle.write(f"\nFinished: {finished}\nExit code: {exit_code}\nElapsed seconds: {elapsed}\n")
    log_handle.flush()
    return {
        "name": step.name,
        "command": step.command,
        "started_at": started,
        "finished_at": finished,
        "elapsed_seconds": elapsed,
        "exit_code": exit_code,
        "output_lines": output_lines,
    }


def strict_failures(readiness: dict[str, Any], continue_on_dirty: bool) -> list[str]:
    failures = [str(gate["name"]) for gate in readiness.get("gates", []) if not gate.get("passed")]
    if continue_on_dirty:
        failures = [name for name in failures if name != "no_dirty_blockers"]
    return failures


def write_summary(reports_dir: Path, result: dict[str, Any]) -> None:
    write_text(reports_dir / "optimized-knowledge-cycle-summary.json", json.dumps(result, indent=2, sort_keys=True))
    lines = [
        "# Optimized Knowledge Cycle Summary",
        "",
        f"Started: {result['started_at']}",
        f"Finished: {result['finished_at']}",
        f"Status: {result['status']}",
        f"Strict: {str(result['strict']).lower()}",
        f"Continue on dirty: {str(result['continue_on_dirty']).lower()}",
        f"Readiness decision: {result['readiness'].get('decision', 'unknown')}",
        f"Log file: `{result['log_file']}`",
        "",
        "| Step | Exit | Seconds |",
        "| --- | ---: | ---: |",
    ]
    for step in result["steps"]:
        lines.append(f"| {step['name']} | {step['exit_code']} | {step['elapsed_seconds']} |")
    failures = result.get("strict_failures", [])
    if failures:
        lines.extend(["", "## Strict Failures", ""])
        lines.extend(f"- `{failure}`" for failure in failures)
    write_text(reports_dir / "optimized-knowledge-cycle-summary.md", "\n".join(lines))


def run_cycle(
    *,
    reports_dir: Path,
    log_file: Path,
    strict: bool,
    continue_on_dirty: bool,
    skip_dependency_audit: bool,
    skip_graphify: bool,
    verbose: bool,
) -> int:
    try:
        from colorama import Fore, Style, init as colorama_init
        from tqdm import tqdm
    except ModuleNotFoundError:
        print("ERROR: tqdm and colorama are required. Install repo requirements into .venv first.")
        return 3
    colorama_init()
    reports_dir.mkdir(parents=True, exist_ok=True)
    started = utc_now()
    steps = build_steps(
        python_executable=sys.executable,
        reports_dir=reports_dir,
        skip_dependency_audit=skip_dependency_audit,
        skip_graphify=skip_graphify,
    )
    results: list[dict[str, Any]] = []
    failed_step = ""
    with log_file.open("w", encoding="utf-8") as log_handle:
        log_handle.write("# Optimized Knowledge Cycle Log\n")
        log_handle.write(f"Started: {started}\n")
        with tqdm(total=len(steps) + 1, desc="optimized knowledge", unit="step", dynamic_ncols=True) as progress:
            for step in steps:
                progress.set_postfix_str(step.name[:40])
                progress.write(f"{Fore.CYAN}[start]{Style.RESET_ALL} {step.name}")
                result = run_step(step, log_handle=log_handle, progress=progress, verbose=verbose)
                results.append(result)
                color = Fore.GREEN if result["exit_code"] == 0 else Fore.RED
                progress.write(f"{color}[done]{Style.RESET_ALL} {step.name} exit={result['exit_code']}")
                progress.update(1)
                if result["exit_code"] != 0:
                    failed_step = step.name
                    break
            readiness: dict[str, Any] = {}
            if not failed_step:
                progress.set_postfix_str("readiness gates")
                readiness = plan_optimized_cutover(reports_dir=reports_dir)
                progress.write(f"{Fore.YELLOW if readiness['decision'] == 'NO-GO' else Fore.GREEN}[readiness]{Style.RESET_ALL} {readiness['decision']}")
                progress.update(1)
    finished = utc_now()
    failures = strict_failures(readiness, continue_on_dirty) if readiness else []
    status = "failed" if failed_step or (strict and failures) else "completed"
    result = {
        "started_at": started,
        "finished_at": finished,
        "status": status,
        "strict": strict,
        "continue_on_dirty": continue_on_dirty,
        "skip_dependency_audit": skip_dependency_audit,
        "skip_graphify": skip_graphify,
        "failed_step": failed_step,
        "strict_failures": failures,
        "readiness": readiness,
        "state_dirty_blockers": read_json(ROOT / "state" / "repository-snapshots.json", {}).get("repositories", {}),
        "log_file": str(log_file),
        "steps": results,
    }
    write_summary(reports_dir, result)
    print(f"Optimized knowledge cycle: {status}")
    print(f"Summary: {reports_dir / 'optimized-knowledge-cycle-summary.md'}")
    print(f"Readiness: {reports_dir / 'optimized-cutover-readiness.md'}")
    print(f"Log: {log_file}")
    return 1 if status == "failed" else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the manual optimized harvest, synthesis, budget, and readiness cycle.")
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    parser.add_argument("--log-file", type=Path, default=Path("reports") / "optimized-knowledge-cycle.log")
    parser.add_argument("--strict", action="store_true", help="Fail if readiness gates fail.")
    parser.add_argument("--continue-on-dirty", action="store_true", help="Allow dirty-repo readiness blockers in strict mode.")
    parser.add_argument("--skip-dependency-audit", action="store_true")
    parser.add_argument("--skip-graphify", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    return run_cycle(
        reports_dir=args.reports_dir,
        log_file=args.log_file,
        strict=args.strict,
        continue_on_dirty=args.continue_on_dirty,
        skip_dependency_audit=args.skip_dependency_audit,
        skip_graphify=args.skip_graphify,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    raise SystemExit(main())
