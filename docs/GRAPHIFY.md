# Governed Graphify Use

Graphify provides a local architectural index for code (and, on opted-in repositories, document) relationships. It helps Codex and Cursor orient themselves before broad exploration; it does not replace source-of-truth verification.

Upstream source: [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) (Apache-2.0, with MIT-licensed portions; see upstream `LICENSE`, `LICENSE-MIT`, and `NOTICE`). A read-only clone lives at `C:\Users\ppyxe\Documents\GitHub\graphify` and is registered in `config/repositories.toml` with `graphify_cycle = false`: it is harvestable learning material, never a federation input and never a propagation target.

## Install and generate

```powershell
uv tool install graphifyy          # or: uv tool upgrade graphifyy
$graphify = Join-Path (uv tool dir --bin) 'graphify.exe'
& $graphify --version              # cycle requires >= 0.9.34
& $graphify extract . --code-only
```

The graph remains local under `graphify-out/` and is ignored by Git. `.graphifyignore` and `.gitignore` exclude secrets, credentials, data stores, exports, caches, logs, dependency folders, and build output.

## One-command startup

The recommended operator entrypoint is [`scripts/run-startup.ps1`](../scripts/run-startup.ps1):

```powershell
cd C:\Users\ppyxe\Documents\GitHub\auto_learning_agent
.\scripts\run-startup.ps1
```

That runs validation, Graphify refresh, harvest, optimized synthesis, readiness reporting, and global publication preview. Apply globals with `-ApplyGlobal -ConfirmGlobalWrite`. See the root [`README.md`](../README.md) for flags such as `-SkipGraphify` and `-SkipRuntimeSmoke`.

## Federated learning workflow

Bootstrap registered repositories once, then refresh their graphs and the federated graph:

```powershell
.\.venv\Scripts\python.exe scripts\propagate_graphify_integration.py --apply --confirm-repo-write
.\.venv\Scripts\python.exe scripts\run_graphify_cycle.py
.\.venv\Scripts\python.exe scripts\run_graphify_cycle.py --repo orsi --force
```

Refresh behavior:

- **Repo-level skip-unchanged.** After a successful build, the cycle writes `graphify-out/.orchestrator-fingerprint.json` (git commit + dirty-status hash + extract profile + Graphify version + `graph.json` hash). On the next run, matching fingerprints skip extract/cluster entirely (`status=unchanged`). This is what keeps large repos like OmniRoute from being rebuilt every startup.
- **File-level incremental inside Graphify.** When a rebuild *is* needed, `graphify extract` still only re-reads changed files (upstream cache/manifest) and enforces shrink-guard (#479).
- **`--force` is the intentional full rebuild.** Ignores fingerprints, skips the incremental gate, and permits a legitimate shrink. Also use `--force` when a cycle reports `cross-project-graph-pollution`.
- **Federated merge skip.** If every input graph's structural hash matches the last federation provenance, the federated merge is skipped too.
- **Health checks.** Built graphs (not unchanged skips) get an advisory `graphify diagnose` pass; warnings appear in `reports/graphify-cycle-summary.md`.
- **Reference repositories are skipped.** Registry entries with `graphify_cycle = false` (the upstream Graphify clone) are excluded from the default cycle and federation; an explicit `--repo graphify` can still build one for local study.

### Semantic documents (opt-in, risk-gated)

Semantic-document extraction is approved for repositories that opt in via `graphify_semantic = true` in `config/repositories.toml`. Enable it per run with:

```powershell
.\.venv\Scripts\python.exe scripts\run_graphify_cycle.py --semantic
```

Gates, all enforced by the cycle:

1. The repository must set `graphify_semantic = true` (default `false`).
2. Repositories with sensitive risk tags (`phi`, `clinical_data`, `medical_practice_data`, `contact_data`, `scraper`, `finance`, `credentials`, `auth`) always stay code-only.
3. An LLM backend key must already be set (`GEMINI_API_KEY`, `GOOGLE_API_KEY`, `MOONSHOT_API_KEY`, or `DEEPSEEK_API_KEY`); the cycle never prompts for keys. Without one, the run records `semantic-skipped-no-backend` and stays code-only.
4. `--code-only` forces AST-only for the whole run regardless of `--semantic`.

The post-build security scan and `.graphifyignore` preflight apply to semantic graphs exactly as to code graphs. Semantic edges from dirty repositories remain ineligible evidence for knowledge promotion.

### Wiki export

```powershell
.\.venv\Scripts\python.exe scripts\run_graphify_cycle.py --wiki
```

Writes agent-crawlable wikis (`index.md` plus one article per community) to `graphify-out/wiki/` in each built repository and next to the federated graph. Wikis live under ignored `graphify-out/` and are never committed. Startup and optimized cycles do not export wikis unless the flag is passed explicitly.

## Query the graphs

Query the federated graph by default, or select local/repository scope:

```powershell
.\.venv\Scripts\python.exe scripts\query_graph.py query "Which repositories share authentication components?"
.\.venv\Scripts\python.exe scripts\query_graph.py query "How is harvesting implemented?" --scope local
.\.venv\Scripts\python.exe scripts\query_graph.py explain "DatabaseService" --repo practice-ops-dashboard
.\.venv\Scripts\python.exe scripts\query_graph.py path "run_cycle" "merge_graphs" --scope local --directed
```

`path` supports `--directed`/`--undirected`. Headless `graphify extract` (0.9.34) writes undirected on-disk graphs and stores canonical caller→callee direction in per-edge `_src`/`_tgt` slots; the cycle namespaces those slots during federation so directed traces work on federated graphs too. `query` stays undirected by upstream design. Rebuilding with `--force` refreshes those direction slots after large refactors.

### MCP stdio server

For interactive agent sessions that prefer MCP tools over the CLI wrapper:

```powershell
.\.venv\Scripts\python.exe scripts\run_graphify_mcp.py                 # federated graph
.\.venv\Scripts\python.exe scripts\run_graphify_mcp.py --scope local
.\.venv\Scripts\python.exe scripts\run_graphify_mcp.py --repo orsi
```

The launcher serves only local graph files over the stdio transport and is never started by the harvest or startup pipelines. HTTP transport and remote graphs remain gated.

After any graph answer, open actual source and use `rg` for exact code behavior, values, contracts, security-sensitive logic, migrations, tests, and edits. Dirty repository graphs are available for navigation but remain ineligible evidence for knowledge promotion.

## Still gated (separate approval required)

- URL/remote ingestion (`graphify add`, clone-as-corpus)
- Live database extraction (`--postgres`)
- Media processing and transcription (video/Whisper/yt-dlp)
- Neo4j / FalkorDB export or push
- Cloud backends and `graphify global`
- Always-on `--watch` daemons in startup

## Propagation

Preview eligible registered repositories:

```powershell
.\.venv\Scripts\python.exe scripts\propagate_graphify_integration.py
```

Application requires both `--apply --confirm-repo-write` and `allow_other_repository_writes = true`. Dirty and risk-tagged repositories may receive code-only Graphify integration, but conflicting custom Graphify rules remain review-required and are never overwritten. Reference-only repositories (`graphify_cycle = false`) are always review-required and never written.

## Upgrade and rollback

```powershell
uv tool upgrade graphifyy
graphify uninstall --project --platform codex
graphify cursor uninstall
```

After a CLI upgrade, refresh the vendored skill by copying `skill-codex.md` and `skills/codex/references/` from the installed package into `.codex/skills/graphify/` and updating `.codex/skills/graphify/.graphify_version`, then confirm `MIN_GRAPHIFY_VERSION` in `scripts/run_graphify_cycle.py` still matches the verified floor.

Remove local artifacts with `Remove-Item -Recurse -Force graphify-out` only when they are no longer needed. Do not modify `~/.codex/config.toml` as part of this integration.
