from __future__ import annotations

import argparse
import json
from pathlib import Path

from orchestrator_common import retrieve_records


def main() -> int:
    parser = argparse.ArgumentParser(description="Retrieve a budgeted shortlist from the local knowledge catalog.")
    parser.add_argument("--catalog", type=Path, default=Path("knowledge/catalog.jsonl"))
    parser.add_argument("--policy", type=Path, default=Path("config/retrieval-policy.toml"))
    parser.add_argument("--query", default="")
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--type", dest="record_type")
    parser.add_argument("--scope")
    parser.add_argument("--status")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    records = retrieve_records(
        args.catalog,
        args.policy,
        query=args.query,
        tags=args.tag,
        record_type=args.record_type,
        scope=args.scope,
        status=args.status,
        limit=args.limit,
    )
    print(json.dumps({"count": len(records), "records": records}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
