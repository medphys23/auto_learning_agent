from __future__ import annotations

import argparse
import json
from pathlib import Path

from orchestrator_common import approval_required, validate_knowledge_record, write_json


def promotion_decision(record: dict[str, object]) -> dict[str, object]:
    errors = validate_knowledge_record(record)
    if errors:
        return {"id": record.get("id", "<unknown>"), "decision": "invalid", "errors": errors}
    if approval_required(record):
        return {
            "id": record["id"],
            "decision": "blocked",
            "reason": "explicit approval metadata is required before global, canonical, security, config, or other high-impact promotion",
        }
    if record.get("status") != "candidate":
        return {"id": record["id"], "decision": "unchanged", "reason": "only candidate records are promoted by this MVP script"}
    return {"id": record["id"], "decision": "promote_to_validated"}


def evaluate_pending(pending_dir: Path, *, apply: bool = False) -> list[dict[str, object]]:
    decisions: list[dict[str, object]] = []
    for path in sorted(pending_dir.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        decision = promotion_decision(record)
        if apply and decision["decision"] == "promote_to_validated":
            record["status"] = "validated"
            write_json(path, record)
            decision["applied"] = True
        else:
            decision["applied"] = False
        decisions.append(decision)
    return decisions


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and optionally promote low-risk local candidate records.")
    parser.add_argument("--pending-dir", type=Path, default=Path("knowledge/pending"))
    parser.add_argument("--apply", action="store_true", help="Apply candidate-to-validated updates when allowed.")
    args = parser.parse_args()
    decisions = evaluate_pending(args.pending_dir, apply=args.apply)
    print(json.dumps({"count": len(decisions), "decisions": decisions}, indent=2, sort_keys=True))
    return 1 if any(item["decision"] == "invalid" for item in decisions) else 0


if __name__ == "__main__":
    raise SystemExit(main())
