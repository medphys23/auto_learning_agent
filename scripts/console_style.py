"""Shared colorama helpers for orchestrator pipeline logs."""

from __future__ import annotations

import re
from typing import Any

_READY = False
_FORE: Any = None
_STYLE: Any = None

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

STEP_THEME = {
    "discover repositories": "cyan",
    "refresh repository graphs": "blue",
    "harvest repositories": "magenta",
    "audit dependency catalog": "yellow",
    "synthesize optimized instructions": "cyan",
    "audit context budget": "yellow",
    "readiness gates": "green",
}

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


def paint(text: str, level: str = "info") -> str:
    ensure_colors()
    if _FORE is None or _STYLE is None:
        return text
    palette = {
        "info": _FORE.CYAN,
        "start": _FORE.BLUE,
        "ok": _FORE.GREEN,
        "warn": _FORE.YELLOW,
        "fail": _FORE.RED,
        "skip": _FORE.MAGENTA,
        "muted": _FORE.WHITE,
        "cyan": _FORE.CYAN,
        "blue": _FORE.BLUE,
        "magenta": _FORE.MAGENTA,
        "yellow": _FORE.YELLOW,
        "green": _FORE.GREEN,
        "red": _FORE.RED,
        "white": _FORE.WHITE,
    }
    color = palette.get(level, _FORE.CYAN)
    return f"{color}{text}{_STYLE.RESET_ALL}"


def cprint(text: str, level: str = "info") -> None:
    print(paint(text, level), flush=True)


def _dirty_count(line: str) -> int | None:
    match = re.search(r"\bdirty=(\d+)\b", line)
    if not match:
        return None
    return int(match.group(1))


def style_child_line(step_name: str, line: str) -> str:
    """Color a streamed child-process line for the optimized knowledge cycle."""
    ensure_colors()
    if "\x1b[" in line:
        return line  # already styled (e.g. Graphify)
    lower = line.lower()
    theme = STEP_THEME.get(step_name, "info")

    if lower.startswith("error") or " failed" in lower or lower.startswith("traceback"):
        return paint(line, "fail")
    if "blocked" in lower or "no-go" in lower:
        return paint(line, "fail")
    if "registry:" in lower:
        return paint(line, "start")

    if step_name == "discover repositories":
        dirty = _dirty_count(line)
        if dirty is None:
            return paint(line, theme)
        return paint(line, "ok" if dirty == 0 else "warn")

    if step_name == "harvest repositories":
        if ": harvested" in lower or ": updated" in lower or "candidates=" in lower and "blocked" not in lower:
            if "dirty" in lower or "skipped" in lower:
                return paint(line, "warn")
            return paint(line, "ok")
        if "skipped" in lower or "dirty" in lower:
            return paint(line, "warn")
        return paint(line, theme)

    if step_name in {"audit dependency catalog", "audit context budget", "synthesize optimized instructions"}:
        if "report:" in lower or "synthesized" in lower or "audit:" in lower or "budget" in lower:
            return paint(line, "ok")
        return paint(line, theme)

    return paint(line, theme)


def phase_banner(index: int, total: int, name: str, *, done_so_far: int, phase_total: int) -> str:
    theme = STEP_THEME.get(name, "cyan")
    tip = STEP_TIP.get(name, "")
    head = paint(f"[start {index}/{total}]", "start")
    body = paint(f" {name}", theme)
    meta = paint(f"  ({done_so_far}/{phase_total} phases done)", "muted")
    lines = [f"{head}{body}{meta}"]
    if tip:
        lines.append(paint(f"[info] {tip}", "warn"))
    return "\n".join(lines)


def phase_done(index: int, total: int, name: str, *, exit_code: int, elapsed: float, lines: int) -> str:
    level = "ok" if exit_code == 0 else "fail"
    return paint(
        f"[done {index}/{total}] {name} exit={exit_code} elapsed={elapsed}s lines={lines}",
        level,
    )
