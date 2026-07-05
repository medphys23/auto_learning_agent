from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from orchestrator_common import utc_now


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class PipelineStep:
    name: str
    command: list[str]
    global_write: bool = False


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def command_text(command: list[str]) -> str:
    return " ".join(f'"{item}"' if " " in item else item for item in command)


def strip_ansi(value: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", value)


def colorize(value: str, color: str, reset: str) -> str:
    return f"{color}{value}{reset}" if color else value


def parse_discovery_lines(lines: list[str]) -> list[dict[str, Any]]:
    repos: list[dict[str, Any]] = []
    pattern = re.compile(r"^(?P<name>.+?): branch=(?P<branch>.*?) dirty=(?P<dirty>\d+) scope=(?P<scope>.*)$")
    for line in lines:
        match = pattern.match(strip_ansi(line).strip())
        if not match:
            continue
        dirty_count = int(match.group("dirty"))
        repos.append(
            {
                "name": match.group("name"),
                "branch": match.group("branch"),
                "dirty_count": dirty_count,
                "scope": match.group("scope"),
                "clean": dirty_count == 0,
            }
        )
    return repos


def parse_harvest_lines(lines: list[str]) -> list[dict[str, Any]]:
    repos: list[dict[str, Any]] = []
    pattern = re.compile(r"^(?P<id>[^:]+): (?P<status>[a-z_]+) \((?P<reason>.*?), candidates=(?P<candidates>\d+)\)$")
    for line in lines:
        match = pattern.match(strip_ansi(line).strip())
        if not match:
            continue
        status = match.group("status")
        repos.append(
            {
                "id": match.group("id"),
                "status": status,
                "reason": match.group("reason"),
                "candidate_count": int(match.group("candidates")),
                "clean": status in {"harvested", "skipped"},
            }
        )
    return repos


def repo_status_insights(step_name: str, output: list[str]) -> dict[str, Any]:
    if step_name == "discover local repositories":
        repos = parse_discovery_lines(output)
        return {
            "kind": "discovery",
            "clean": [repo for repo in repos if repo["clean"]],
            "dirty": [repo for repo in repos if not repo["clean"]],
        }
    if step_name == "harvest clean repositories":
        repos = parse_harvest_lines(output)
        return {
            "kind": "harvest",
            "clean": [repo for repo in repos if repo["clean"]],
            "dirty": [repo for repo in repos if not repo["clean"]],
        }
    return {}


def emit_repo_status(
    insights: dict[str, Any],
    *,
    log_handle: Any,
    progress: Any,
    green: str,
    yellow: str,
    red: str,
    cyan: str,
    reset: str,
) -> None:
    if not insights:
        return
    kind = str(insights.get("kind", "repositories"))
    clean = list(insights.get("clean", []))
    dirty = list(insights.get("dirty", []))
    header = f"[repos:{kind}] clean={len(clean)} dirty={len(dirty)}"
    progress.write(colorize(header, cyan, reset))
    log_handle.write(f"\n{strip_ansi(header)}\n")
    for repo in clean:
        if kind == "discovery":
            line = f"  CLEAN {repo['name']} branch={repo['branch']} scope={repo['scope']}"
        else:
            line = f"  CLEAN {repo['id']} status={repo['status']} candidates={repo['candidate_count']}"
        progress.write(colorize(line, green, reset))
        log_handle.write(strip_ansi(line) + "\n")
    for repo in dirty:
        if kind == "discovery":
            line = f"  DIRTY {repo['name']} branch={repo['branch']} dirty={repo['dirty_count']} scope={repo['scope']}"
            color = yellow
        else:
            line = f"  BLOCKED {repo['id']} status={repo['status']} candidates={repo['candidate_count']}"
            color = red
        progress.write(colorize(line, color, reset))
        log_handle.write(strip_ansi(line) + "\n")


def build_steps(
    *,
    python_executable: str,
    apply_global: bool,
    confirm_global_write: bool,
    reports_dir: Path,
    master_root: Path,
    backup_base: Path,
    backup_keep: int,
    retrieval_query: str,
    retrieval_status: str,
) -> list[PipelineStep]:
    if apply_global and not confirm_global_write:
        raise ValueError("--apply-global requires --confirm-global-write")

    py = python_executable
    steps = [
        PipelineStep("unit tests", [py, "-m", "unittest", "discover", "-s", "tests"]),
        PipelineStep("validate local Codex TOML", [py, "scripts/validate_codex_config.py"]),
        PipelineStep("audit global instructions", [py, "scripts/audit_global_instructions.py", "--reports-dir", str(reports_dir)]),
        PipelineStep("discover local repositories", [py, "scripts/discover_repositories.py"]),
        PipelineStep("harvest clean repositories", [py, "scripts/harvest_repositories.py"]),
        PipelineStep("audit dependency catalogs", [py, "scripts/audit_dependency_catalog.py", "--reports-dir", str(reports_dir)]),
        PipelineStep(
            "retrieve knowledge smoke",
            [
                py,
                "scripts/retrieve_knowledge.py",
                "--query",
                retrieval_query,
                "--status",
                retrieval_status,
            ],
        ),
        PipelineStep(
            "synthesize top-level instructions",
            [
                py,
                "scripts/synthesize_top_level_instructions.py",
                "--preview",
                "--reports-dir",
                str(reports_dir),
                "--master-root",
                str(master_root),
            ],
        ),
    ]
    publish_command = [
        py,
        "scripts/publish_global_rules.py",
        "--reports-dir",
        str(reports_dir),
        "--master-root",
        str(master_root),
        "--backup-base",
        str(backup_base),
        "--backup-keep",
        str(backup_keep),
    ]
    if apply_global:
        publish_command.extend(["--apply", "--confirm-global-write"])
    else:
        publish_command.append("--preview")
    steps.append(PipelineStep("publish global rules" if apply_global else "preview global publication", publish_command, apply_global))
    if apply_global:
        steps.append(PipelineStep("validate global Codex TOML", [py, "scripts/validate_codex_config.py", "--global"]))
    return steps


def run_step(
    step: PipelineStep,
    *,
    log_handle: Any,
    verbose: bool,
    progress: Any,
    green: str = "",
    yellow: str = "",
    red: str = "",
    cyan: str = "",
    reset: str = "",
) -> dict[str, Any]:
    started = utc_now()
    start_time = time.monotonic()
    log_handle.write(f"\n## {step.name}\n")
    log_handle.write(f"Started: {started}\n")
    log_handle.write(f"Command: {command_text(step.command)}\n\n")
    log_handle.flush()
    progress.write(f"[start] {step.name}")
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
    output: list[str] = []
    for line in process.stdout:
        output_lines += 1
        output.append(line.rstrip())
        log_handle.write(line)
        if verbose:
            progress.write(line.rstrip())
    return_code = process.wait()
    insights = repo_status_insights(step.name, output)
    emit_repo_status(
        insights,
        log_handle=log_handle,
        progress=progress,
        green=green,
        yellow=yellow,
        red=red,
        cyan=cyan,
        reset=reset,
    )
    elapsed = round(time.monotonic() - start_time, 3)
    finished = utc_now()
    log_handle.write(f"\nFinished: {finished}\n")
    log_handle.write(f"Exit code: {return_code}\n")
    log_handle.write(f"Elapsed seconds: {elapsed}\n")
    log_handle.flush()
    progress.write(f"[done] {step.name} exit={return_code} elapsed={elapsed}s")
    return {
        "name": step.name,
        "command": step.command,
        "global_write": step.global_write,
        "started_at": started,
        "finished_at": finished,
        "elapsed_seconds": elapsed,
        "exit_code": return_code,
        "output_lines": output_lines,
        "repository_status": insights,
    }


def write_summary(reports_dir: Path, result: dict[str, Any]) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    write_text(reports_dir / "orchestrator-pipeline-summary.json", json.dumps(result, indent=2, sort_keys=True))
    lines = [
        "# Orchestrator Pipeline Summary",
        "",
        f"Started: {result['started_at']}",
        f"Finished: {result['finished_at']}",
        f"Mode: {result['mode']}",
        f"Status: {result['status']}",
        f"Global writes requested: {str(result['apply_global']).lower()}",
        f"Log file: `{result['log_file']}`",
        "",
        "| Step | Exit | Seconds | Global write |",
        "| --- | ---: | ---: | --- |",
    ]
    for step in result["steps"]:
        lines.append(
            f"| {step['name']} | {step['exit_code']} | {step['elapsed_seconds']} | {str(step['global_write']).lower()} |"
        )
    if result.get("failed_step"):
        lines.extend(["", f"Failed step: `{result['failed_step']}`"])
    repository_sections = [
        step for step in result["steps"] if step.get("repository_status", {}).get("kind") in {"discovery", "harvest"}
    ]
    if repository_sections:
        lines.extend(["", "## Repository Status", ""])
        for step in repository_sections:
            status = step["repository_status"]
            lines.append(f"### {step['name']}")
            lines.append("")
            lines.append(f"- Clean: {len(status.get('clean', []))}")
            lines.append(f"- Dirty/blocked: {len(status.get('dirty', []))}")
            for repo in status.get("clean", []):
                name = repo.get("name") or repo.get("id")
                detail = repo.get("branch") or repo.get("status")
                lines.append(f"- CLEAN `{name}` {detail}")
            for repo in status.get("dirty", []):
                name = repo.get("name") or repo.get("id")
                detail = f"dirty={repo.get('dirty_count')}" if "dirty_count" in repo else str(repo.get("status"))
                lines.append(f"- DIRTY/BLOCKED `{name}` {detail}")
            lines.append("")
    write_text(reports_dir / "orchestrator-pipeline-summary.md", "\n".join(lines))


def run_pipeline(
    *,
    steps: list[PipelineStep],
    reports_dir: Path,
    log_file: Path,
    apply_global: bool,
    verbose: bool,
) -> int:
    try:
        from tqdm import tqdm
        from colorama import Fore, Style, init as colorama_init
    except ModuleNotFoundError:
        print("ERROR: tqdm and colorama are required for this pipeline.")
        print(r"Install locally with: uv pip install --python .\.venv\Scripts\python.exe --link-mode hardlink -r requirements.txt")
        return 3
    colorama_init()

    reports_dir.mkdir(parents=True, exist_ok=True)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    started_at = utc_now()
    results: list[dict[str, Any]] = []
    failed_step = ""
    mode = "apply-global" if apply_global else "preview"

    with log_file.open("w", encoding="utf-8") as log_handle:
        log_handle.write("# Orchestrator Pipeline Log\n")
        log_handle.write(f"Started: {started_at}\n")
        log_handle.write(f"Mode: {mode}\n")
        with tqdm(total=len(steps), desc="orchestrator pipeline", unit="step", dynamic_ncols=True) as progress:
            for step in steps:
                progress.set_postfix_str(step.name[:40])
                result = run_step(
                    step,
                    log_handle=log_handle,
                    verbose=verbose,
                    progress=progress,
                    green=Fore.GREEN,
                    yellow=Fore.YELLOW,
                    red=Fore.RED,
                    cyan=Fore.CYAN,
                    reset=Style.RESET_ALL,
                )
                results.append(result)
                progress.update(1)
                if result["exit_code"] != 0:
                    failed_step = step.name
                    break

    finished_at = utc_now()
    status = "failed" if failed_step else "completed"
    summary = {
        "started_at": started_at,
        "finished_at": finished_at,
        "mode": mode,
        "status": status,
        "apply_global": apply_global,
        "log_file": str(log_file),
        "failed_step": failed_step,
        "steps": results,
    }
    write_summary(reports_dir, summary)
    print(f"Pipeline status: {status}")
    print(f"Summary: {reports_dir / 'orchestrator-pipeline-summary.md'}")
    print(f"Log: {log_file}")
    return 1 if failed_step else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local orchestrator pipeline with tqdm progress logs.")
    parser.add_argument("--preview", action="store_true", help="Run without global writes. This is the default.")
    parser.add_argument("--apply-global", action="store_true", help="Apply final generated instructions to global Codex/Cursor folders.")
    parser.add_argument("--confirm-global-write", action="store_true", help="Required with --apply-global.")
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    parser.add_argument("--master-root", type=Path, default=Path("master"))
    parser.add_argument("--backup-base", type=Path, default=Path("backups") / "global-sync")
    parser.add_argument("--backup-keep", type=int, default=2, help="Number of newest backup roots to retain after global apply.")
    parser.add_argument("--retrieval-query", default="orsi")
    parser.add_argument("--retrieval-status", default="candidate")
    parser.add_argument("--log-file", type=Path, default=Path("reports") / "orchestrator-pipeline.log")
    parser.add_argument("--verbose", action="store_true", help="Echo subprocess output through tqdm.write while logging.")
    args = parser.parse_args()
    if args.preview and args.apply_global:
        print("ERROR: choose either --preview or --apply-global, not both")
        return 2

    try:
        steps = build_steps(
            python_executable=sys.executable,
            apply_global=args.apply_global,
            confirm_global_write=args.confirm_global_write,
            reports_dir=args.reports_dir,
            master_root=args.master_root,
            backup_base=args.backup_base,
            backup_keep=args.backup_keep,
            retrieval_query=args.retrieval_query,
            retrieval_status=args.retrieval_status,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2
    return run_pipeline(
        steps=steps,
        reports_dir=args.reports_dir,
        log_file=args.log_file,
        apply_global=args.apply_global,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    raise SystemExit(main())
