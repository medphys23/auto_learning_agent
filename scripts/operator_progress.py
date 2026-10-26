"""Rich live line for jobs the operator waits on.

Event lines print above the bar. The bar shows a spinner, the job and current
item, percent, finished/total, items per minute, a ticking elapsed time,
remaining time, and separate saved and deferred counts.
"""

from __future__ import annotations

import sys
import threading
from typing import Any

_STACK: list["OperatorProgress"] = []
_CONSOLE: Any = None


def console() -> Any:
    global _CONSOLE
    if _CONSOLE is None:
        from rich.console import Console

        _CONSOLE = Console(highlight=False)
    return _CONSOLE


LEVEL_STYLE = {
    "ok": "green",
    "warn": "yellow",
    "fail": "red",
    "skip": "yellow",
    "phase": "cyan",
    "dim": "dim",
    "muted": "dim",
    "info": "dim",
    "start": "cyan",
    "cyan": "cyan",
    "yellow": "yellow",
    "green": "green",
    "red": "red",
}


def _active() -> "OperatorProgress | None":
    return _STACK[-1] if _STACK else None


def emit(text: str, level: str = "plain") -> None:
    style = LEVEL_STYLE.get(level)
    active = _active()
    if active is not None:
        active.event(text, style)
        return
    console().print(text, style=style, highlight=False, markup=False)


def note_current(item: str) -> None:
    active = _active()
    if active is not None:
        active.set_item(item)


class _PlainColumn:
    """Render task text without treating square brackets as Rich markup."""

    def __init__(self, kind: str) -> None:
        self.kind = kind

    def __call__(self) -> Any:
        from rich.progress import ProgressColumn
        from rich.text import Text

        kind = self.kind

        class Column(ProgressColumn):
            def render(self, task: Any) -> Text:
                if kind == "job":
                    return Text(str(task.description or ""))
                saved = int(task.fields.get("saved", 0))
                deferred = int(task.fields.get("deferred", 0))
                line = Text()
                line.append(f"saved {saved}", style="green")
                line.append("  ")
                line.append(f"deferred {deferred}", style="yellow")
                return line

        return Column()


class _PerMinuteColumn:
    def __call__(self) -> Any:
        from rich.progress import ProgressColumn
        from rich.text import Text

        class Column(ProgressColumn):
            def render(self, task: Any) -> Text:
                elapsed = task.elapsed
                if not elapsed or task.completed <= 0:
                    rate = 0.0
                else:
                    rate = float(task.completed) / float(elapsed) * 60.0
                return Text(f"{rate:.1f}/min", style="cyan")

        return Column()


class OperatorProgress:
    def __init__(self, job: str, total: int, *, live: bool | None = None) -> None:
        self.job = job
        self.total = max(0, total)
        self.saved = 0
        self.deferred = 0
        self.finished = 0
        self.current = ""
        self.live = sys.stdout.isatty() if live is None else live
        self._progress: Any = None
        self._task_id: Any = None
        self._lock = threading.RLock()

    def __enter__(self) -> "OperatorProgress":
        self.open()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def open(self) -> None:
        _STACK.append(self)
        if not self.live or self.total <= 0:
            return
        from rich.progress import (
            BarColumn,
            MofNCompleteColumn,
            Progress,
            SpinnerColumn,
            TaskProgressColumn,
            TimeElapsedColumn,
            TimeRemainingColumn,
        )

        self._progress = Progress(
            SpinnerColumn(),
            _PlainColumn("job")(),
            BarColumn(bar_width=24),
            TaskProgressColumn(),
            MofNCompleteColumn(),
            _PerMinuteColumn()(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            _PlainColumn("counts")(),
            console=console(),
            refresh_per_second=8,
            transient=False,
        )
        self._progress.start()
        self._task_id = self._progress.add_task(
            self._description(),
            total=self.total,
            saved=0,
            deferred=0,
        )

    def close(self) -> None:
        progress = self._progress
        self._progress = None
        self._task_id = None
        if self in _STACK:
            _STACK.remove(self)
        if progress is not None:
            progress.stop()

    def set_item(self, item: str) -> None:
        self.current = " ".join(item.split())[:80]
        self._redraw()

    def event(self, text: str, style: str | None) -> None:
        with self._lock:
            progress = self._progress
            if progress is not None:
                progress.console.print(text, style=style, highlight=False, markup=False)
            else:
                console().print(text, style=style, highlight=False, markup=False)

    def finish(self, *, saved: bool) -> None:
        if saved:
            self.saved += 1
        else:
            self.deferred += 1
        self.finished += 1
        self._redraw()

    def _description(self) -> str:
        item = self.current or "waiting"
        return f"{self.job}  {item}"

    def _redraw(self) -> None:
        with self._lock:
            if self._progress is None or self._task_id is None:
                return
            self._progress.update(
                self._task_id,
                completed=min(self.finished, self.total),
                description=self._description(),
                saved=self.saved,
                deferred=self.deferred,
            )
