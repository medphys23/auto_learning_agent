from __future__ import annotations

import argparse
from pathlib import Path

from orchestrator_common import utc_now


def preview_publication(reports_dir: Path, *, apply: bool = False) -> Path:
    if apply:
        raise RuntimeError("global publication is preview-only in the local MVP")
    reports_dir.mkdir(parents=True, exist_ok=True)
    report = reports_dir / "publication-preview.md"
    report.write_text(
        "\n".join(
            [
                "# Publication Preview",
                "",
                f"Generated: {utc_now()}",
                "",
                "- Mode: preview-only",
                "- Global writes performed: false",
                "- Target folders: `C:\\Users\\ppyxe\\.codex`, `C:\\Users\\ppyxe\\.cursor`",
                "- Required before any future publication: explicit user approval, backups, diffs, syntax validation, conflict checks, and rollback notes.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview-only global rules publication for the local MVP.")
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    parser.add_argument("--apply", action="store_true", help="Unsupported in MVP; returns an error.")
    args = parser.parse_args()
    try:
        report = preview_publication(args.reports_dir, apply=args.apply)
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return 2
    print(f"Preview written to {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
