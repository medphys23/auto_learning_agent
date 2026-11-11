"""Read-only Windows development storage inventory; writes reports only."""

from __future__ import annotations

import argparse
import csv
import os
import shutil
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn


GIB = 1024 ** 3
REPARSE_POINT = 0x400
MANIFESTS = ("requirements.txt", "pyproject.toml", "uv.lock", "poetry.lock", "Pipfile", "Pipfile.lock", "environment.yml", "environment.yaml", "conda-lock.yml", "setup.py", "setup.cfg")


def safe_walk(root: Path, errors: list[str]):
    """Yield directories without following links or Windows reparse points."""
    stack = [root]
    while stack:
        path = stack.pop()
        try:
            with os.scandir(path) as entries:
                items = list(entries)
        except OSError as exc:
            errors.append(f"{path}: {exc.strerror or exc}")
            continue
        dirs, files = [], []
        for item in items:
            try:
                stat = item.stat(follow_symlinks=False)
                if getattr(stat, "st_file_attributes", 0) & REPARSE_POINT or item.is_symlink():
                    continue
                if item.is_dir(follow_symlinks=False):
                    dirs.append(Path(item.path))
                elif item.is_file(follow_symlinks=False):
                    files.append((item.name.lower(), Path(item.path), stat))
            except OSError as exc:
                errors.append(f"{item.path}: {exc.strerror or exc}")
        yield path, files
        stack.extend(dirs)


def discover(root: Path, errors: list[str], progress: Progress, task: int):
    envs, disks, development = [], [], []
    development_set = set()
    count = 0
    for directory, files in safe_walk(root, errors):
        count += 1
        if directory.name.lower() in {"node_modules", ".next", "target", "graphify-out"} and not any(parent in development_set for parent in directory.parents):
            development.append(directory)
            development_set.add(directory)
        if count % 500 == 0:
            progress.update(task, current=str(directory)[-70:])
        for name, path, stat in files:
            if name == "pyvenv.cfg":
                envs.append(directory)
            elif name.endswith(".vhdx") and ("docker" in str(path).lower() or "wsl" in str(path).lower() or name == "ext4.vhdx"):
                disks.append((path, stat.st_size, stat.st_mtime))
    return envs, disks, development, count


def project_for(env: Path, root: Path):
    for parent in (env.parent, *env.parents):
        if parent == env:
            continue
        try:
            names = {p.name.lower() for p in parent.iterdir() if p.is_file()}
        except OSError:
            names = set()
        found = [name for name in MANIFESTS if name.lower() in names]
        if found:
            return parent, found
        if parent == root or parent == parent.parent:
            break
    return env.parent, []


def cache_roots(home: Path):
    local = home / "AppData" / "Local"
    roaming = home / "AppData" / "Roaming"
    candidates = {
        "pip": [local / "pip" / "Cache", home / ".cache" / "pip", Path(os.environ.get("PIP_CACHE_DIR", home / ".cache" / "pip"))],
        "uv": [local / "uv" / "cache", home / ".cache" / "uv", Path(os.environ.get("UV_CACHE_DIR", local / "uv" / "cache"))],
        "Conda": [home / "miniconda3" / "pkgs", home / "anaconda3" / "pkgs", home / ".conda" / "pkgs", local / "conda" / "conda" / "pkgs"],
        "Poetry": [local / "pypoetry" / "Cache", roaming / "pypoetry" / "Cache", home / ".cache" / "pypoetry"],
        "Hugging Face": [home / ".cache" / "huggingface", local / "huggingface", Path(os.environ.get("HF_HOME", home / ".cache" / "huggingface"))],
        "PyTorch": [home / ".cache" / "torch", home / ".cache" / "torch_extensions", Path(os.environ.get("TORCH_HOME", home / ".cache" / "torch"))],
        "Docker": [local / "Docker" / "wsl", local / "DockerDesktop"],
        "npm": [local / "npm-cache", home / "AppData" / "Roaming" / "npm-cache"],
        "pnpm": [local / "pnpm" / "store"],
        "Gradle": [home / ".gradle" / "caches"],
        "Cargo": [home / ".cargo" / "registry"],
    }
    seen = set()
    found = []
    for kind, paths in candidates.items():
        for path in paths:
            if path not in seen and path.is_dir() and not path.is_symlink():
                found.append((kind, path))
                seen.add(path)
    return found


def size_tree(root: Path, errors: list[str]):
    logical = exclusive = linked = files = 0
    newest = root.stat().st_mtime
    for _, entries in safe_walk(root, errors):
        for _, path, _ in entries:
            try:
                stat = os.stat(path, follow_symlinks=False)
            except OSError as exc:
                errors.append(f"{path}: {exc.strerror or exc}")
                continue
            files += 1
            logical += stat.st_size
            if stat.st_nlink == 1:
                exclusive += stat.st_size
            else:
                linked += stat.st_size
            newest = max(newest, stat.st_mtime)
    return logical, exclusive, linked, files, newest


def date(timestamp: float):
    return datetime.fromtimestamp(timestamp).astimezone().isoformat(timespec="seconds")


def run(root: Path, output: Path, home: Path):
    console = Console()
    errors: list[str] = []
    progress = Progress(SpinnerColumn(), TextColumn("{task.description} {task.fields[current]}"), BarColumn(), TaskProgressColumn(), MofNCompleteColumn(), TimeElapsedColumn(), TimeRemainingColumn(), TextColumn("saved={task.fields[saved]} deferred={task.fields[deferred]}"), console=console)
    with progress:
        task = progress.add_task("Discovering", total=1, current=str(root), saved=0, deferred=0)
        console.print(f"Start discovery: {root}", style="cyan")
        envs, disks, development, directories = discover(root, errors, progress, task)
        progress.update(task, completed=1, saved=len(envs), deferred=len(errors))
        console.print(f"Status: saved={len(envs)} environments, deferred={len(errors)} paths; next=size inventory", style="cyan")
        caches = [(kind, path) for kind, path in cache_roots(home) if path.is_relative_to(root)]
        entities = [("environment", path) for path in envs] + [(f"cache:{kind}", path) for kind, path in caches] + [("development", path) for path in development]
        task = progress.add_task("Measuring", total=max(1, len(entities)), current="", saved=0, deferred=len(errors))
        rows = []
        for index, (kind, path) in enumerate(entities):
            progress.update(task, current=str(path)[-70:])
            console.print(f"Start: {path}", style="cyan")
            try:
                logical, exclusive, linked, file_count, modified = size_tree(path, errors)
                project, manifests = project_for(path, root) if kind == "environment" else ("", [])
                rows.append({"kind": kind, "path": str(path), "project": str(project), "metadata": ", ".join(manifests), "logical_bytes": logical, "exclusive_logical_bytes": exclusive, "hardlinked_logical_bytes": linked, "files": file_count, "last_modified": date(modified)})
                console.print(f"Saved: {path} ({logical / GIB:.2f} GiB logical)", style="green")
            except OSError as exc:
                errors.append(f"{path}: {exc.strerror or exc}")
                console.print(f"Deferred: {path}: {exc}", style="yellow")
            progress.advance(task)
            progress.update(task, saved=len(rows), deferred=len(errors))
            console.print(f"Status: saved={len(rows)} deferred={len(errors)} next={entities[index + 1][1] if index + 1 < len(entities) else 'report'}", style="cyan")
    for path, logical, modified in disks:
        rows.append({"kind": "virtual_disk", "path": str(path), "project": "Docker/WSL", "metadata": "", "logical_bytes": logical, "exclusive_logical_bytes": 0, "hardlinked_logical_bytes": 0, "files": 1, "last_modified": date(modified)})
    rows.sort(key=lambda row: row["exclusive_logical_bytes"], reverse=True)
    output.mkdir(parents=True, exist_ok=True)
    csv_path, md_path = output / "windows-storage-inventory.csv", output / "windows-storage-audit.md"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["kind", "path", "project", "metadata", "logical_bytes", "exclusive_logical_bytes", "hardlinked_logical_bytes", "files", "last_modified"])
        writer.writeheader()
        writer.writerows(rows)
    env_rows = [row for row in rows if row["kind"] == "environment"]
    cache_rows = [row for row in rows if row["kind"].startswith("cache:")]
    lines = ["# Windows development storage audit", "", f"Generated: {date(datetime.now().timestamp())}", f"Scanned: `{root}` ({directories:,} accessible directories)", f"Drive free: {shutil.disk_usage(root).free / GIB:.2f} GiB", "", "Sizes are logical file lengths. 'Exclusive' counts files with one hardlink and is a conservative logical proxy, not measured physical reclaimable bytes. Hardlinked files may remain in uv/Conda caches or other projects. Category totals can overlap when one inventoried folder contains another. Virtual disk file size is not an estimate of space reclaimed by deleting content inside WSL/Docker. Access-denied paths make totals incomplete.", "", f"Environments: {len(env_rows)}; logical {sum(r['logical_bytes'] for r in env_rows)/GIB:.2f} GiB; exclusive logical {sum(r['exclusive_logical_bytes'] for r in env_rows)/GIB:.2f} GiB.", f"Caches: {len(cache_rows)}; logical {sum(r['logical_bytes'] for r in cache_rows)/GIB:.2f} GiB; exclusive logical {sum(r['exclusive_logical_bytes'] for r in cache_rows)/GIB:.2f} GiB.", "", "## Ranked inventory", "", "| Type | Logical GiB | Exclusive logical GiB | Linked GiB | Modified | Project / metadata | Path |", "| --- | ---: | ---: | ---: | --- | --- | --- |"]
    project_root = home / "Documents" / "GitHub"
    if project_root.is_relative_to(root):
        project_rows = [row for row in rows if Path(row["path"]).is_relative_to(project_root)]
        lines[lines.index("## Ranked inventory"):lines.index("## Ranked inventory")] = [
            "## GitHub project scope", "", f"Project root: `{project_root}`", "",
            *(
                f"{label}: {sum(row['kind'] == kind for row in project_rows)}; "
                f"logical {sum(row['logical_bytes'] for row in project_rows if row['kind'] == kind)/GIB:.2f} GiB; "
                f"single-link logical {sum(row['exclusive_logical_bytes'] for row in project_rows if row['kind'] == kind)/GIB:.2f} GiB."
                for kind, label in (("environment", "Environments"), ("development", "Development folders"))
            ),
            "", "Caches outside GitHub appear in the full inventory. Category totals can overlap.", "",
        ]
    for row in rows:
        lines.append(f"| {row['kind']} | {row['logical_bytes']/GIB:.2f} | {row['exclusive_logical_bytes']/GIB:.2f} | {row['hardlinked_logical_bytes']/GIB:.2f} | {row['last_modified'][:10]} | {row['project']} {row['metadata']} | `{row['path']}` |")
    lines += ["", "## Conservative cleanup shortlist (approval required)", "", "Review inactive environments with reproducibility metadata first, then cache directories. Check project activity and backup needs before removing anything. Shared hardlinked files will not free space until all links are removed. Treat Docker and WSL virtual disks separately; use their own supported maintenance workflows after reviewing contents.", ""]
    for row in rows[:20]:
        if row["kind"] == "environment" and row["metadata"]:
            lines.append(f"- Review `{row['path']}` ({row['exclusive_logical_bytes']/GIB:.2f} GiB exclusive logical; {row['metadata']}).")
        elif row["kind"].startswith("cache:"):
            lines.append(f"- Review `{row['path']}` ({row['exclusive_logical_bytes']/GIB:.2f} GiB exclusive logical; cached data may need redownloading).")
    lines += ["", "## Incomplete paths", "", f"{len(errors)} paths could not be inspected.", ""]
    lines.extend(f"- `{error}`" for error in errors[:200])
    if len(errors) > 200:
        lines.append(f"- ... {len(errors) - 200} more omitted")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    console.print(f"Saved: {md_path} and {csv_path}", style="green")
    return rows, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(os.environ.get("SystemDrive", "C:") + "\\"))
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "reports")
    args = parser.parse_args()
    run(args.root.resolve(), args.output, args.home)


if __name__ == "__main__":
    main()
