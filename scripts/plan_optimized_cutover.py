from __future__ import annotations

import argparse
from pathlib import Path

from orchestrator_common import sha256_file, utc_now, write_json
from synthesize_top_level_instructions import REPO_ROOT


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def plan_optimized_cutover(*, master_root: Path, reports_dir: Path) -> dict[str, object]:
    optimized_agents = master_root / "optimized" / "codex" / "AGENTS.md"
    result = {
        "generated_at": utc_now(),
        "applied": False,
        "cutover_allowed": False,
        "reason": "Shadow v1 is preview-only. Global cutover requires a separate explicit task.",
        "optimized_agents_exists": optimized_agents.exists(),
        "optimized_agents_sha256": sha256_file(optimized_agents) if optimized_agents.exists() else "",
        "rollback_required": False,
    }
    reports_dir.mkdir(parents=True, exist_ok=True)
    write_json(reports_dir / "optimized-cutover-plan.json", result)
    write_text(
        reports_dir / "optimized-cutover-plan.md",
        "# Optimized Cutover Plan\n\n"
        f"Generated: {result['generated_at']}\n\n"
        "- Status: preview only\n"
        "- Applied: false\n"
        "- Cutover allowed: false\n"
        "- Reason: Shadow v1 requires a separate explicit canary cutover task.\n",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan optimized cutover without applying it.")
    parser.add_argument("--master-root", type=Path, default=REPO_ROOT / "master")
    parser.add_argument("--reports-dir", type=Path, default=REPO_ROOT / "reports")
    args = parser.parse_args()
    result = plan_optimized_cutover(master_root=args.master_root, reports_dir=args.reports_dir)
    print(f"Optimized cutover plan: applied={str(result['applied']).lower()} cutover_allowed={str(result['cutover_allowed']).lower()}")
    print(f"Report: {args.reports_dir / 'optimized-cutover-plan.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
