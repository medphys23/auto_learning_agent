# Governed Graphify Use

Graphify provides a local architectural index for code relationships. It helps Codex and Cursor orient themselves before broad exploration; it does not replace source-of-truth verification.

## Install and generate

```powershell
uv tool install graphifyy
$graphify = Join-Path (uv tool dir --bin) 'graphify.exe'
& $graphify extract . --code-only
```

The graph remains local under `graphify-out/` and is ignored by Git. `.graphifyignore` and `.gitignore` exclude secrets, credentials, data stores, exports, caches, logs, dependency folders, and build output.

## Federated learning workflow

Bootstrap registered repositories once, then refresh their code-only graphs and the federated graph:

```powershell
.\.venv\Scripts\python.exe scripts\propagate_graphify_integration.py --apply --confirm-repo-write
.\.venv\Scripts\python.exe scripts\run_graphify_cycle.py
.\.venv\Scripts\python.exe scripts\run_graphify_cycle.py --repo orsi --force
```

Targeted `--repo` runs refresh only that repository and leave the existing federation unchanged; the next full cycle incorporates it.

The standard orchestrator pipeline and optimized knowledge cycle run the graph cycle after repository discovery and before harvesting. Use `--skip-graphify` only for diagnostics.

Query the federated graph by default, or select local/repository scope:

```powershell
.\.venv\Scripts\python.exe scripts\query_graph.py query "Which repositories share authentication components?"
.\.venv\Scripts\python.exe scripts\query_graph.py query "How is harvesting implemented?" --scope local
.\.venv\Scripts\python.exe scripts\query_graph.py explain "DatabaseService" --repo practice-ops-dashboard
```

Then open actual source and use `rg` for exact code behavior, values, contracts, security-sensitive logic, migrations, tests, and edits. Dirty repository graphs are available for navigation but remain ineligible evidence for knowledge promotion.

Do not use URL ingestion, live database extraction, media processing, cloud backends, semantic-document extraction, or `graphify global` here without separate approval.

## Propagation

Preview eligible registered repositories:

```powershell
.\.venv\Scripts\python.exe scripts\propagate_graphify_integration.py
```

Application requires both `--apply --confirm-repo-write` and `allow_other_repository_writes = true`. Dirty and risk-tagged repositories may receive code-only Graphify integration, but conflicting custom Graphify rules remain review-required and are never overwritten.

## Upgrade and rollback

```powershell
uv tool upgrade graphifyy
graphify uninstall --project --platform codex
graphify cursor uninstall
```

Remove local artifacts with `Remove-Item -Recurse -Force graphify-out` only when they are no longer needed. Do not modify `~/.codex/config.toml` as part of this integration.
