"""Shared colorama helpers for orchestrator pipeline logs.

Color is reserved for meaning, not decoration:
  green  = success / clean
  yellow = warning / dirty / skipped
  red    = failure / blocked
  cyan   = phase markers only ([start N/M])
  dim    = secondary meta (tips, paths, elapsed noise)

Routine progress lines stay mostly uncolored so the terminal is readable.
"""

from __future__ import annotations

import re
from typing import Any

_READY = False
_FORE: Any = None
_STYLE: Any = None

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
    global _READY, _FORE, _STYLE
    if _READY:
        return
    try:
        from colorama import Fore, Style, init as colorama_init

        colorama_init()
        _FORE = Fore
        _STYLE = Style
    except ModuleNotFoundError:
        _FORE = None
        _STYLE = None
    _READY = True


def strip_ansi(value: str) -> str:
    return ANSI_RE.sub("", value)


def paint(text: str, level: str = "plain") -> str:
    ensure_colors()
    if level in {"plain", "none"} or _FORE is None or _STYLE is None:
        return text
    palette = {
        "ok": _FORE.GREEN,
        "warn": _FORE.YELLOW,
        "fail": _FORE.RED,
        "skip": _FORE.YELLOW,
        "phase": _FORE.CYAN,
        "dim": getattr(_FORE, "LIGHTBLACK_EX", _FORE.WHITE),
        "muted": getattr(_FORE, "LIGHTBLACK_EX", _FORE.WHITE),
        # Legacy aliases used by callers — map to the status palette above.
        "info": getattr(_FORE, "LIGHTBLACK_EX", _FORE.WHITE),
        "start": _FORE.CYAN,
        "cyan": _FORE.CYAN,
        "blue": _FORE.CYAN,
        "magenta": _FORE.YELLOW,
        "yellow": _FORE.YELLOW,
        "green": _FORE.GREEN,
        "red": _FORE.RED,
        "white": _FORE.WHITE,
    }
    color = palette.get(level)
    if color is None:
        return text
    return f"{color}{text}{_STYLE.RESET_ALL}"


def cprint(text: str, level: str = "plain") -> None:
    print(paint(text, level), flush=True)


def _dirty_count(line: str) -> int | None:
    match = re.search(r"\bdirty=(\d+)\b", line)
    if not match:
        return None
    return int(match.group(1))


def style_child_line(step_name: str, line: str) -> str:
    """Color a streamed child line only when status warrants it."""
    ensure_colors()
    plain = strip_ansi(line)
    lower = plain.lower()

    if lower.startswith("error") or " failed" in lower or lower.startswith("traceback"):
        return paint(plain, "fail")
    if "blocked" in lower or "no-go" in lower:
        return paint(plain, "fail")
    if "registry:" in lower:
        return paint(plain, "phase")

    if step_name == "discover repositories":
        dirty = _dirty_count(plain)
        if dirty is None:
            return plain
        return paint(plain, "ok" if dirty == 0 else "warn")

    if step_name == "harvest repositories":
        if "blocked" in lower or "failed" in lower:
            return paint(plain, "fail")
        if "skipped" in lower or "dirty" in lower:
            return paint(plain, "warn")
        if ": harvested" in lower or "candidates=" in lower:
            return paint(plain, "ok")
        return plain

    if step_name == "refresh repository graphs":
        # Graphify already styles its tag; if ANSI present keep it, else status-color only.
        if "\x1b[" in line:
            return line
        if "failed" in lower or "excluded" in lower:
            return paint(plain, "fail")
        if "skipped" in lower or "empty" in lower:
            return paint(plain, "warn")
        if ": built" in lower or "health=ok" in lower or "cycle status: completed" in lower:
            return paint(plain, "ok")
        return plain

    if step_name in {"audit dependency catalog", "audit context budget", "synthesize optimized instructions"}:
        if "report:" in lower:
            return paint(plain, "dim")
        if "synthesized" in lower or "audit:" in lower or "budget" in lower:
            return paint(plain, "ok")
        return plain

    return plain


def phase_banner(index: int, total: int, name: str, *, done_so_far: int, phase_total: int) -> str:
    tip = STEP_TIP.get(name, "")
    head = paint(f"[start {index}/{total}]", "phase")
    body = f" {name}"
    meta = paint(f"  ({done_so_far}/{phase_total} phases done)", "dim")
    lines = [f"{head}{body}{meta}"]
    if tip:
        lines.append(paint(f"  {tip}", "dim"))
    return "\n".join(lines)


def phase_done(index: int, total: int, name: str, *, exit_code: int, elapsed: float, lines: int) -> str:
    level = "ok" if exit_code == 0 else "fail"
    badge = paint(f"[done {index}/{total}]", level)
    meta = paint(f" exit={exit_code} elapsed={elapsed}s lines={lines}", "dim")
    return f"{badge} {name}{meta}"
