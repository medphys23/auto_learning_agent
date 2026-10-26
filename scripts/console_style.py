"""Rich event colors for orchestrator pipeline logs.

Color is reserved for meaning:
  green  = success / clean / saved
  yellow = warning / dirty / deferred
  red    = failure / blocked
  cyan   = phase and status markers
  dim    = secondary detail
"""

from __future__ import annotations

import re

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

STEP_TIP = {
    "discover repositories": "Scanning Documents\\GitHub and updating the registry.",
    "refresh repository graphs": "Long step: live per-repo extract/cluster/diagnose lines follow.",
    "harvest repositories": "Extracting candidate knowledge from registered repos.",
    "audit dependency catalog": "Comparing repo manifests against the stack catalog.",
    "synthesize optimized instructions": "Building master/optimized Codex and Cursor previews.",
    "audit context budget": "Estimating persistent instruction token pressure.",
    "readiness gates": "Evaluating cutover readiness from cycle reports.",
}


def ensure_colors() -> None:
    """Kept so older callers can ask for color setup. Rich configures itself."""
    return None


def strip_ansi(value: str) -> str:
    return ANSI_RE.sub("", value)


def cprint(text: str, level: str = "plain") -> None:
    from operator_progress import emit

    emit(text, level)


def _dirty_count(line: str) -> int | None:
    match = re.search(r"\bdirty=(\d+)\b", line)
    if not match:
        return None
    return int(match.group(1))


def style_child_line(step_name: str, line: str) -> tuple[str, str]:
    """Return plain text and the Rich level for a streamed child line."""
    plain = strip_ansi(line)
    lower = plain.lower()

    if lower.startswith("error") or " failed" in lower or lower.startswith("traceback"):
        return plain, "fail"
    if "blocked" in lower or "no-go" in lower:
        return plain, "fail"
    if "registry:" in lower:
        return plain, "phase"

    if step_name == "discover repositories":
        dirty = _dirty_count(plain)
        if dirty is None:
            return plain, "plain"
        return plain, "ok" if dirty == 0 else "warn"

    if step_name == "harvest repositories":
        if "blocked" in lower or "failed" in lower:
            return plain, "fail"
        if "skipped" in lower or "dirty" in lower:
            return plain, "warn"
        if ": harvested" in lower or "candidates=" in lower:
            return plain, "ok"
        return plain, "plain"

    if step_name == "refresh repository graphs":
        if "failed" in lower or "excluded" in lower:
            return plain, "fail"
        if "skipped" in lower or "empty" in lower:
            return plain, "warn"
        if ": built" in lower or "health=ok" in lower or "cycle status: completed" in lower:
            return plain, "ok"
        return plain, "plain"

    if step_name in {"audit dependency catalog", "audit context budget", "synthesize optimized instructions"}:
        if "report:" in lower:
            return plain, "dim"
        if "synthesized" in lower or "audit:" in lower or "budget" in lower:
            return plain, "ok"
        return plain, "plain"

    return plain, "plain"


def phase_banner(index: int, total: int, name: str, *, done_so_far: int, phase_total: int) -> list[tuple[str, str]]:
    lines = [
        (
            f"[start {index}/{total}] {name}  ({done_so_far}/{phase_total} phases done)",
            "phase",
        )
    ]
    tip = STEP_TIP.get(name, "")
    if tip:
        lines.append((f"  {tip}", "dim"))
    return lines


def phase_done(index: int, total: int, name: str, *, exit_code: int, elapsed: float, lines: int) -> tuple[str, str]:
    level = "ok" if exit_code == 0 else "fail"
    text = f"[done {index}/{total}] {name}  exit={exit_code} elapsed={elapsed}s lines={lines}"
    return text, level
