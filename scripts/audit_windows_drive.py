"""Inventory a Windows drive by storage category without reading file contents."""

from __future__ import annotations

import argparse
import csv
import heapq
import os
import shutil
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn

from audit_windows_storage import GIB, date, safe_walk


CATEGORIES = ("Windows and system", "Installed software", "Personal files", "Development", "Application data", "Virtual disks", "Recycle Bin", "Other")
VIRTUAL_DISKS = {".vhd", ".vhdx", ".vmdk", ".vdi", ".qcow2"}
SYSTEM_DIRS = {"windows", "recovery", "system volume information", "$winreagent", "boot", "efi"}
PROGRAM_DIRS = {"program files", "program files (x86)", "xboxgames", "msys64", "texlive", "xampp", "xamppserver", "mamp", "mamppro", "sql2022", "nvm4w"}
DEVELOPMENT_HOME = {".cache", ".codex", ".cursor", ".bun", ".cargo", ".rustup", ".gradle", ".npm", ".conda", ".venv", "venv", ".local", "vscode-remote-wsl"}
DEVELOPMENT_LOCAL = {"npm-cache", "pnpm", "pip", "uv", "nvm", "docker", "dockerdesktop", "huggingface"}
PERSONAL_HOME = {"desktop", "documents", "downloads", "pictures", "videos", "music", "onedrive"}
SYSTEM_FILES = {"pagefile.sys", "hiberfil.sys", "swapfile.sys", "dumpstack.log", "dumpstack.log.tmp"}


def category(relative: Path) -> str:
    parts = [part.lower() for part in relative.parts]
    if not parts:
        return "Other"
    if relative.suffix.lower() in VIRTUAL_DISKS:
        return "Virtual disks"
    head = parts[0]
    if head == "$recycle.bin":
        return "Recycle Bin"
    if head in SYSTEM_DIRS or (len(parts) == 1 and head in SYSTEM_FILES):
        return "Windows and system"
    if head in PROGRAM_DIRS:
        return "Installed software"
    if head == "programdata" or head in {"temp", "onedrivetemp", "config.msi"}:
        return "Application data"
    if head == "users" and len(parts) > 2:
        home = parts[2]
        if home in DEVELOPMENT_HOME or (home == "documents" and len(parts) > 3 and parts[3] == "github"):
            return "Development"
        if home == "appdata":
            if len(parts) > 4 and parts[3] == "local" and parts[4] in DEVELOPMENT_LOCAL:
                return "Development"
            return "Application data"
        if home in PERSONAL_HOME or len(parts) > 2:
            return "Personal files"
    return "Other"


def candidate_kind(directory: Path, root: Path, names: set[str]) -> str | None:
    relative = directory.relative_to(root)
    parts = [part.lower() for part in relative.parts]
    name = directory.name.lower()
    if category(relative) not in {"Development", "Application data"}:
        return None
    if "pyvenv.cfg" in names:
        return "Python environment"
    if name in {"node_modules", ".next", "graphify-out"} and len(parts) > 4 and parts[0] == "users" and parts[2:4] == ["documents", "github"]:
        return "Generated project files"
    if name in {"npm-cache", "huggingface"} or (name == "cache" and len(parts) > 1 and parts[-2] in {"uv", "pip", "pypoetry"}):
        return "Package or model cache"
    if parts[-3:] == ["appdata", "local", "temp"]:
        return "Temporary files"
    return None


def add(bucket: dict, key, size: int, single: int, modified: float):
    row = bucket.setdefault(key, [0, 0, 0, 0.0])
    row[0] += size
    row[1] += single
    row[2] += 1
    row[3] = max(row[3], modified)


def scan(root: Path, console: Console | None = None):
    root = root.resolve()
    console = console or Console()
    errors: list[str] = []
    categories, folders, candidates = {}, {}, {}
    candidate_roots: dict[Path, str] = {}
    largest: list[tuple[int, int, Path, str, float, int]] = []
    seen_links: set[tuple[int, int]] = set()
    logical = unique = single = files = directories = 0
    start_usage = shutil.disk_usage(root)
    roots = []
    with os.scandir(root) as entries:
        for entry in entries:
            try:
                if not entry.is_symlink() and not (getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0) & 0x400):
                    roots.append(Path(entry.path))
            except OSError as exc:
                errors.append(f"{entry.path}: {exc.strerror or exc}")
    roots.sort(key=lambda path: path.name.lower())
    progress = Progress(SpinnerColumn(), TextColumn("{task.description} {task.fields[current]}"), BarColumn(), TaskProgressColumn(), MofNCompleteColumn(), TimeElapsedColumn(), TimeRemainingColumn(), TextColumn("saved={task.fields[saved]} deferred={task.fields[deferred]}"), console=console)
    with progress:
        task = progress.add_task("Scanning C:", total=len(roots), current="", saved=0, deferred=0)
        for index, top in enumerate(roots):
            progress.update(task, current=top.name)
            console.print(f"Start: {top}", style="cyan")
            before = len(errors)
            try:
                walked = safe_walk(top, errors) if top.is_dir() else [(root, [(top.name.lower(), top, top.stat(follow_symlinks=False))])]
            except OSError as exc:
                errors.append(f"{top}: {exc.strerror or exc}")
                walked = []
            for directory, entries in walked:
                directories += directory != root
                names = {name for name, _, _ in entries}
                kind = candidate_kind(directory, root, names) if directory != root else None
                if kind:
                    candidate_roots[directory] = kind
                folder_keys = []
                for ancestor in (directory, *directory.parents):
                    if ancestor == root:
                        break
                    if len(ancestor.relative_to(root).parts) <= 5:
                        folder_keys.append(ancestor)
                candidate_owner = next((ancestor for ancestor in reversed(directory.parents) if ancestor in candidate_roots), None)
                if candidate_owner is None and directory in candidate_roots:
                    candidate_owner = directory
                directory_category = category(directory.relative_to(root)) if directory != root else None
                for _, path, _ in entries:
                    try:
                        stat = os.stat(path, follow_symlinks=False)
                    except OSError as exc:
                        errors.append(f"{path}: {exc.strerror or exc}")
                        continue
                    label = "Virtual disks" if path.suffix.lower() in VIRTUAL_DISKS else directory_category or category(path.relative_to(root))
                    size = stat.st_size
                    exclusive = size if stat.st_nlink == 1 else 0
                    logical += size
                    single += exclusive
                    files += 1
                    if stat.st_nlink == 1:
                        unique += size
                    else:
                        identity = (stat.st_dev, stat.st_ino)
                        if identity not in seen_links:
                            seen_links.add(identity)
                            unique += size
                    add(categories, label, size, exclusive, stat.st_mtime)
                    for ancestor in folder_keys:
                        add(folders, ancestor, size, exclusive, stat.st_mtime)
                    if candidate_owner is not None:
                        add(candidates, candidate_owner, size, exclusive, stat.st_mtime)
                    item = (size, files, path, label, stat.st_mtime, exclusive)
                    if len(largest) < 100:
                        heapq.heappush(largest, item)
                    elif size > largest[0][0]:
                        heapq.heapreplace(largest, item)
            top_bytes = folders.get(top, [0])[0]
            if not top_bytes:
                try:
                    top_bytes = top.stat(follow_symlinks=False).st_size if top.is_file() else 0
                except OSError as exc:
                    errors.append(f"{top}: {exc.strerror or exc}")
            if len(errors) > before:
                console.print(f"Deferred: {top} ({len(errors) - before} inaccessible or changed paths)", style="yellow")
            console.print(f"Saved: {top} ({top_bytes / GIB:.2f} GiB logical)", style="green")
            progress.advance(task)
            progress.update(task, saved=index + 1, deferred=len(errors), current=roots[index + 1].name if index + 1 < len(roots) else "report")
            console.print(f"Status: saved={index + 1} deferred={len(errors)} next={roots[index + 1].name if index + 1 < len(roots) else 'report'}", style="cyan")
    return {"root": root, "start": start_usage, "end": shutil.disk_usage(root), "logical": logical, "unique": unique, "single": single, "files": files, "directories": directories, "categories": categories, "folders": folders, "candidates": candidates, "candidate_kinds": candidate_roots, "largest": sorted(largest, reverse=True), "errors": errors}


def action(kind: str) -> str:
    return {
        "Python environment": "Confirm the project is inactive and its lockfile or requirements can recreate this environment.",
        "Generated project files": "Confirm the project is inactive and the build or dependencies can be recreated.",
        "Package or model cache": "Check offline needs, download cost, and active installs before using the package manager's cleanup command.",
        "Temporary files": "Check that no installer or application is using these files.",
    }[kind]


def write_reports(result: dict, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    csv_path = output / "windows-drive-inventory.csv"
    md_path = output / "windows-drive-audit.md"
    rows = []
    for kind, mapping in (("category", result["categories"]), ("folder", result["folders"])):
        for path, values in mapping.items():
            rows.append((kind, path if kind == "category" else "Mixed", str(path), *values))
    for size, _, path, label, modified, exclusive in result["largest"]:
        rows.append(("large_file", label, str(path), size, exclusive, 1, modified))
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("record_type", "category", "path", "logical_bytes", "single_link_logical_bytes", "file_count", "last_modified"))
        writer.writerows((kind, label, path, logical, single, files, date(modified)) for kind, label, path, logical, single, files, modified in rows)
    md = ["# Full C: storage audit", "", f"Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}", f"Scanned: `{result['root']}`; {result['directories']:,} directories and {result['files']:,} files", f"Free at start: {result['start'].free/GIB:.2f} GiB; free at end: {result['end'].free/GIB:.2f} GiB", f"Drive used at end: {result['end'].used/GIB:.2f} GiB", f"Accessible logical bytes: {result['logical']/GIB:.2f} GiB; hardlinks counted once within scan: {result['unique']/GIB:.2f} GiB; single-link logical bytes: {result['single']/GIB:.2f} GiB", f"Difference between drive used and unique logical bytes: {(result['end'].used-result['unique'])/GIB:+.2f} GiB. This is not a cleanup estimate: NTFS allocation, sparse or compressed files, protected paths, shadow copies, and changes during the scan affect reconciliation.", "", "## Categories", "", "| Category | Logical GiB | Single-link GiB |", "| --- | ---: | ---: |"]
    for label in CATEGORIES:
        values = result["categories"].get(label, [0, 0])
        md.append(f"| {label} | {values[0]/GIB:.2f} | {values[1]/GIB:.2f} |")
    md += ["", "## Largest top-level folders", "", "| Path | Logical GiB | Single-link GiB |", "| --- | ---: | ---: |"]
    top = [(path, values) for path, values in result["folders"].items() if len(path.relative_to(result["root"]).parts) == 1]
    for path, values in sorted(top, key=lambda item: item[1][0], reverse=True)[:30]:
        md.append(f"| `{path}` | {values[0]/GIB:.2f} | {values[1]/GIB:.2f} |")
    md += ["", "## Largest subfolders", "", "Folder rows overlap their ancestors; do not add them together.", "", "| Path | Logical GiB | Single-link GiB |", "| --- | ---: | ---: |"]
    nested = [(path, values) for path, values in result["folders"].items() if len(path.relative_to(result["root"]).parts) > 1]
    for path, values in sorted(nested, key=lambda item: item[1][0], reverse=True)[:40]:
        md.append(f"| `{path}` | {values[0]/GIB:.2f} | {values[1]/GIB:.2f} |")
    md += ["", "## Largest files", "", "| Path | Category | GiB | Modified |", "| --- | --- | ---: | --- |"]
    for size, _, path, label, modified, _ in result["largest"][:50]:
        md.append(f"| `{path}` | {label} | {size/GIB:.2f} | {date(modified)[:10]} |")
    md += ["", "## Review candidates; approval required before cleanup", "", "Single-link size is a logical proxy, not physical bytes guaranteed to be recovered. Do not delete folders directly when a package manager or application owns them.", "", "| Candidate | Type | Logical GiB | Single-link GiB | Check before action |", "| --- | --- | ---: | ---: | --- |"]
    reviews = [(path, result["candidate_kinds"][path], values[0], values[1], action(result["candidate_kinds"][path])) for path, values in result["candidates"].items() if values[0] >= GIB / 4]
    reviews.extend((path, "Personal file", size, exclusive, "Confirm it is no longer needed or backed up before removal.") for size, _, path, label, _, exclusive in result["largest"] if label == "Personal files" and size >= GIB)
    reviews.extend((path, "Installed application", values[0], values[1], "Confirm it is unused, then use Windows' uninstaller; do not delete its folder.") for path, values in result["folders"].items() if len(path.relative_to(result["root"]).parts) == 2 and category(path.relative_to(result["root"])) == "Installed software" and values[0] >= 2 * GIB)
    reviews.extend((path, "Application data", values[0], values[1], "Identify the owning app and check its storage controls or backups; do not delete its data folder directly.") for path, values in result["folders"].items() if len(parts := path.relative_to(result["root"]).parts) == 5 and parts[0].lower() == "users" and parts[2].lower() == "appdata" and parts[4].lower() != "programs" and values[0] >= 5 * GIB)
    for path, kind, logical, exclusive, check in sorted(reviews, key=lambda item: item[3], reverse=True)[:30]:
        md.append(f"| `{path}` | {kind} | {logical/GIB:.2f} | {exclusive/GIB:.2f} | {check} |")
    md += ["", "Windows page file, hibernation, restore storage, and virtual disks are informational here. Review installed programs and personal files before any approved action; no settings or files were changed.", "", "## Incomplete paths", "", f"{len(result['errors']):,} paths could not be inspected; protected shadow storage may require administrator access to quantify.", ""]
    md.extend(f"- `{error}`" for error in result["errors"][:200])
    if len(result["errors"]) > 200:
        md.append(f"- ... {len(result['errors']) - 200:,} more omitted")
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    return md_path, csv_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(os.environ.get("SystemDrive", "C:") + "\\"))
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "reports")
    args = parser.parse_args()
    console = Console()
    result = scan(args.root, console)
    report, inventory = write_reports(result, args.output)
    console.print(f"Saved: {report} and {inventory}", style="green")


if __name__ == "__main__":
    main()
