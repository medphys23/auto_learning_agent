from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from console_style import cprint, ensure_colors, paint, phase_banner, phase_done, style_child_line
from orchestrator_common import read_json, utc_now
from plan_optimized_cutover import plan_optimized_cutover


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class CycleStep:
    name: str
    command: list[str]
    index: int = 0
    total: int = 0


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def command_text(command: list[str]) -> str:
    return " ".join(f'"{item}"' if " " in item else item for item in command)


def build_steps(*, python_executable: str, reports_dir: Path, skip_dependency_audit: bool, skip_graphify: bool = False) -> list[CycleStep]:
    raw = [
        CycleStep(
            "discover repositories",
            [python_executable, "scripts/discover_repositories.py", "--write-registry"],
        ),
    ]
    if not skip_graphify:
        raw.append(CycleStep("refresh repository graphs", [python_executable, "scripts/run_graphify_cycle.py", "--reports-dir", str(reports_dir)]))
    raw.append(CycleStep("harvest repositories", [python_executable, "scripts/harvest_repositories.py"]))
    if not skip_dependency_audit:
        raw.append(CycleStep("audit dependency catalog", [python_executable, "scripts/audit_dependency_catalog.py", "--reports-dir", str(reports_dir)]))
    raw.extend(
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
    total = len(raw)
    return [
        CycleStep(name=step.name, command=step.command, index=index, total=total)
        for index, step in enumerate(raw, start=1)
    ]


def run_step(step: CycleStep, *, log_handle: Any, progress: Any, stream_output: bool) -> dict[str, Any]:
    started = utc_now()
    start = time.monotonic()
    log_handle.write(f"\n## {step.name}\n")
    log_handle.write(f"Started: {started}\n")
    log_handle.write(f"Command: {command_text(step.command)}\n\n")
    log_handle.flush()
    env = dict(os.environ)
    # Unbuffered child Python so per-repo Graphify/harvest lines appear live.
    env["PYTHONUNBUFFERED"] = "1"
    process = subprocess.Popen(
        step.command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        bufsize=1,
    )
    assert process.stdout is not None
    output_lines = 0
    for line in process.stdout:
        output_lines += 1
        log_handle.write(line)
        if stream_output:
            text = line.rstrip()
            if text:
                progress.write(style_child_line(step.name, text))
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
    quiet: bool,
) -> int:
    try:
        from tqdm import tqdm
    except ModuleNotFoundError:
        print("ERROR: tqdm and colorama are required. Install repo requirements into .venv first.")
        return 3
    ensure_colors()
    # Live child logs are on by default; --quiet restores the old top-level-only view.
    stream_output = not quiet or verbose
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
        log_handle.write(f"Stream child output: {str(stream_output).lower()}\n")
        phase_total = len(steps) + 1
        cprint(f"optimized knowledge cycle: {len(steps)} work steps + readiness", "info")
        with tqdm(total=phase_total, desc="optimized knowledge", unit="step", dynamic_ncols=True) as progress:
            for step in steps:
                progress.set_postfix_str(f"{step.index}/{step.total} {step.name[:32]}")
                for banner_line in phase_banner(
                    step.index,
                    step.total,
                    step.name,
                    done_so_far=progress.n,
                    phase_total=phase_total,
                ).splitlines():
                    progress.write(banner_line)
                result = run_step(step, log_handle=log_handle, progress=progress, stream_output=stream_output)
                results.append(result)
                progress.write(
                    phase_done(
                        step.index,
                        step.total,
                        step.name,
                        exit_code=int(result["exit_code"]),
                        elapsed=float(result["elapsed_seconds"]),
                        lines=int(result["output_lines"]),
                    )
                )
                progress.update(1)
                if result["exit_code"] != 0:
                    failed_step = step.name
                    break
            readiness: dict[str, Any] = {}
            if not failed_step:
                progress.set_postfix_str(f"{phase_total}/{phase_total} readiness gates")
                for banner_line in phase_banner(
                    phase_total,
                    phase_total,
                    "readiness gates",
                    done_so_far=progress.n,
                    phase_total=phase_total,
                ).splitlines():
                    progress.write(banner_line)
                readiness = plan_optimized_cutover(reports_dir=reports_dir)
                decision = str(readiness.get("decision", "unknown"))
                progress.write(paint(f"[readiness] {decision}", "fail" if decision == "NO-GO" else "ok"))
                for gate in readiness.get("gates", []):
                    passed = bool(gate.get("passed"))
                    progress.write(
                        paint(
                            f"  gate {gate.get('name')}: {'pass' if passed else 'fail'} — {gate.get('detail', '')}",
                            "ok" if passed else "warn",
                        )
                    )
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
    cprint(f"Optimized knowledge cycle: {status}", "ok" if status == "completed" else "fail")
    cprint(f"Summary: {reports_dir / 'optimized-knowledge-cycle-summary.md'}", "muted")
    cprint(f"Readiness: {reports_dir / 'optimized-cutover-readiness.md'}", "muted")
    cprint(f"Log: {log_file}", "muted")
    return 1 if status == "failed" else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the manual optimized harvest, synthesis, budget, and readiness cycle.")
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    parser.add_argument("--log-file", type=Path, default=Path("reports") / "optimized-knowledge-cycle.log")
    parser.add_argument("--strict", action="store_true", help="Fail if readiness gates fail.")
    parser.add_argument("--continue-on-dirty", action="store_true", help="Allow dirty-repo readiness blockers in strict mode.")
    parser.add_argument("--skip-dependency-audit", action="store_true")
    parser.add_argument("--skip-graphify", action="store_true")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Stream child-step stdout (default behavior; kept for compatibility).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Hide child-step stdout; show only the top-level phase bar.",
    )
    args = parser.parse_args()
    return run_cycle(
        reports_dir=args.reports_dir,
        log_file=args.log_file,
        strict=args.strict,
        continue_on_dirty=args.continue_on_dirty,
        skip_dependency_audit=args.skip_dependency_audit,
        skip_graphify=args.skip_graphify,
        verbose=args.verbose,
        quiet=args.quiet,
    )


if __name__ == "__main__":
    raise SystemExit(main())
