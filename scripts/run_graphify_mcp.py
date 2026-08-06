"""Start the Graphify MCP stdio server against a governed local graph.

Thin launcher around the `graphify-mcp` executable installed by
`uv tool install graphifyy`. It serves the federated graph by default, or a
local/repository-scoped graph, over the MCP stdio transport for interactive
agent use. It is never started automatically by the harvest or startup
pipelines; run it explicitly when an agent session should query graphs through
MCP tools instead of `scripts/query_graph.py`.

Only the stdio transport against local graph files is governed here. HTTP
transport, remote graphs, and database backends remain out of scope without a
separate approval task.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

from query_graph import resolve_graph
from run_graphify_cycle import ROOT, find_graphify, graphify_version


def find_graphify_mcp() -> Path:
    found = shutil.which("graphify-mcp")
    if found:
        return Path(found)
    # Fall back to the uv tool bin directory the graphify CLI resolves from.
    sibling = find_graphify().parent / ("graphify-mcp.exe" if os.name == "nt" else "graphify-mcp")
    if sibling.exists():
        return sibling
    raise RuntimeError("graphify-mcp is not installed; run `uv tool install graphifyy`")


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve a governed Graphify graph over the MCP stdio transport.")
    parser.add_argument("--scope", choices=("federated", "local"), default="federated")
    parser.add_argument("--repo", default="", help="Registered repository id; overrides --scope.")
    args = parser.parse_args()
    try:
        graph = resolve_graph(scope=args.scope, repo_id=args.repo)
        if not graph.exists():
            raise ValueError(f"graph not found: {graph}; run scripts/run_graphify_cycle.py first")
        graphify_version(find_graphify())
        executable = find_graphify_mcp()
    except (RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(f"Serving MCP (stdio) for {'repository:' + args.repo if args.repo else args.scope} graph: {graph}")
    return int(subprocess.run([str(executable), "--graph", str(graph)], cwd=ROOT).returncode)


if __name__ == "__main__":
    raise SystemExit(main())
