from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from orchestrator_common import load_repository_registry
from run_graphify_cycle import ROOT, find_graphify, graphify_version


def resolve_graph(*, scope: str, repo_id: str) -> Path:
    if repo_id:
        repositories = {str(repo["id"]): repo for repo in load_repository_registry(ROOT / "config" / "repositories.toml")}
        if repo_id not in repositories:
            raise ValueError(f"unknown repository id: {repo_id}")
        return Path(str(repositories[repo_id]["path"])) / "graphify-out" / "graph.json"
    if scope == "local":
        return ROOT / "graphify-out" / "graph.json"
    return ROOT / "graphify-out" / "federated" / "graph.json"


def build_query_command(*, executable: Path, operation: str, values: list[str], graph: Path, budget: int) -> list[str]:
    command = [str(executable), operation, *values, "--graph", str(graph)]
    if operation == "query":
        command.extend(["--budget", str(budget)])
    return command


def main() -> int:
    parser = argparse.ArgumentParser(description="Query the governed federated, local, or repository-specific Graphify graph.")
    parser.add_argument("operation", choices=("query", "path", "explain"))
    parser.add_argument("values", nargs="+")
    parser.add_argument("--scope", choices=("federated", "local"), default="federated")
    parser.add_argument("--repo", default="")
    parser.add_argument("--budget", type=int, default=2000)
    args = parser.parse_args()
    expected_values = 2 if args.operation == "path" else 1
    if len(args.values) != expected_values:
        parser.error(f"{args.operation} requires {expected_values} value(s)")
    try:
        graph = resolve_graph(scope=args.scope, repo_id=args.repo)
        if not graph.exists():
            raise ValueError(f"graph not found: {graph}; run scripts/run_graphify_cycle.py first")
        executable = find_graphify()
        graphify_version(executable)
    except (RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2
    command = build_query_command(executable=executable, operation=args.operation, values=args.values, graph=graph, budget=args.budget)
    print(f"Graph scope: {'repository:' + args.repo if args.repo else args.scope}")
    return int(subprocess.run(command, cwd=ROOT).returncode)


if __name__ == "__main__":
    raise SystemExit(main())
