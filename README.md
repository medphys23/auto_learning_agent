# auto_learning_agent

`auto_learning_agent` is the local master repository for governed Codex/Cursor orchestration on this machine. It stores the repository registry, safe knowledge extraction tools, candidate knowledge records, retrieval policy, promotion policy, global publication previews, and the operator documentation needed to keep those pieces auditable.

The repository is deliberately not a raw mirror of every project. It captures safe, reusable knowledge from local Git checkouts: architecture maps, workflows, verification commands, stack and dependency signals, safety constraints, tests/CI/deployment signals, and concise source summaries. It excludes secrets, credentials, PHI, private datasets, scraped contact exports, SQLite/runtime state, caches, dependencies, binaries, and generated artifacts.

## Current Phase

The repo is in the **optimized orchestrator + federated Graphify** phase.

- Global Codex/Cursor rules publish from `master/optimized/` with guarded apply and backups.
- The local registry tracks GitHub checkouts under `C:\Users\ppyxe\Documents\GitHub`, including a read-only upstream Graphify clone (`graphify_cycle = false`).
- Each registered repository can maintain a local Graphify graph under `<repo>/graphify-out/` (AST code graphs by default; semantic docs only when opted in).
- This orchestrator builds a federated graph at `graphify-out/federated/` for cross-repo architecture queries, with optional wiki export and MCP stdio serving.
- Knowledge harvesting remains candidate-first; dirty graphs may guide discovery but cannot justify promotion.
- `auto_learning_agent` has a configured dirty-harvest exception; other registered repos stay on the clean harvest gate unless explicitly approved.

## One-Command Startup

Run the full local cycle from PowerShell without invoking an agent:

```powershell
cd C:\Users\ppyxe\Documents\GitHub\auto_learning_agent
.\scripts\run-startup.ps1
```

Preview only (default): discover → Graphify refresh → harvest → optimized synthesis → readiness report → global publication preview.

Apply globals after reviewing reports:

```powershell
.\scripts\run-startup.ps1 -ApplyGlobal -ConfirmGlobalWrite
```

Also apply orchestrator retrieval hints to registered repos:

```powershell
.\scripts\run-startup.ps1 -ApplyGlobal -ConfirmGlobalWrite -ApplyRepoHints -ConfirmRepoWrite
```

**Drag-and-drop apply-all:** use [`APPLY-EVERYTHING.cmd`](APPLY-EVERYTHING.cmd) (CMD) or [`APPLY-EVERYTHING.ps1`](APPLY-EVERYTHING.ps1) (PowerShell: type `&` then drop the file). Press Enter, then type `APPLY`. That runs the full cycle, publishes optimized globals, applies repo retrieval hints, and applies Graphify policy files to registered repos. Pass `-Yes` to skip the typed confirmation.

Useful flags:

- `-Strict` — fail when dirty repositories block readiness (default allows `--continue-on-dirty`).
- `-SkipGraphify` — skip graph refresh for diagnostics.
- `-SkipRuntimeSmoke` — do not switch the global parent model to GPT-5.6 Terra on apply.
- `-ForceParentModel` — switch to GPT-5.6 Terra even when runtime smoke fails (use only after upgrading Codex).

Startup reports:

- `reports/optimized-knowledge-cycle-summary.md`
- `reports/optimized-cutover-readiness.md`
- `reports/graphify-cycle-summary.md`
- `reports/publication-preview.md` or `reports/publication-applied.md`

See also [`docs/GRAPHIFY.md`](docs/GRAPHIFY.md) for Graphify install, query, and safety rules.

## Repository Layout

- `AGENTS.md` and `skills.md` define repo-local agent policy and repeatable workflows.
- `config/repositories.toml` is the enabled local repository registry.
- `config/retrieval-policy.toml` defines index-first retrieval budgets.
- `config/promotion-policy.toml` defines candidate-first promotion rules and high-impact approval gates.
- `knowledge/INDEX.md` is the generated high-level index.
- `knowledge/catalog.jsonl` is the concise retrieval catalog.
- `knowledge/pending/` stores full candidate records.
- `knowledge/schemas/knowledge-record.schema.json` defines required knowledge-record fields.
- `scripts/` contains stdlib-only tools for discovery, Graphify cycles, harvesting, retrieval, promotion, audit, synthesis, publication preview/apply, and TOML validation.
- `graphify-out/` stores local federated graph artifacts (ignored by git).
- `docs/GRAPHIFY.md` documents the governed Graphify integration.
- `reports/` receives ignored local Markdown reports.
- `master/` contains generated Codex/Cursor top-level instruction previews.
- `backups/global-sync/` stores global publication backups when publication is explicitly applied.

## Local Setup

Use the repo-local environment. The startup pipeline requires `tqdm` for real terminal progress bars and `colorama` for readable Windows console colors.

```powershell
if (-not (Test-Path .\.venv\Scripts\python.exe)) { uv venv --python 3.11 .venv }
uv pip install --python .\.venv\Scripts\python.exe --link-mode hardlink -r requirements.txt
```

## Master Publication Model

Global publication is guarded and explicit.

1. `scripts/synthesize_top_level_instructions.py --preview` reads current global Codex/Cursor instructions and writes merged previews under `master/`.
2. `scripts/publish_global_rules.py --preview` produces publication reports without global writes.
3. `scripts/publish_global_rules.py --apply --confirm-global-write` writes to `C:\Users\ppyxe\.codex` and `C:\Users\ppyxe\.cursor` only after explicit user approval.
4. Every apply creates backups under `backups/global-sync/<timestamp>/`, writes rollback notes, and verifies source/target hashes.

This README/knowledge expansion work does not require another global publication. Publish again only when a new global instruction change is intentionally approved. After Graphify or routing changes, rerun `.\scripts\run-startup.ps1 -ApplyGlobal -ConfirmGlobalWrite`.

## Federated Graphify Layer

Graphify provides a local architectural index (code by default; opted-in semantic docs). It is not source of truth. See [`docs/GRAPHIFY.md`](docs/GRAPHIFY.md).

1. One-time bootstrap for registered repos: `scripts\propagate_graphify_integration.py --apply --confirm-repo-write`
2. Refresh all repository graphs and merge federated output: `scripts\run_graphify_cycle.py` (add `--semantic`, `--wiki`, or `--force` as needed)
3. Query federated scope by default: `scripts\query_graph.py query "<question>"` (use `path ... --directed` for call direction; `scripts\run_graphify_mcp.py` for MCP stdio)
4. Query this repo only: `scripts\query_graph.py query "<question>" --scope local`
5. Query one registered repo: `scripts\query_graph.py explain "<symbol>" --repo orsi`

Graph outputs stay under ignored `graphify-out/` directories. Dirty repositories may still contribute graphs for navigation, but dirty state remains ineligible for knowledge promotion.

The standard startup script runs Graphify refresh before harvesting so source maps can use fresh graph shortlists.

## Startup Pipeline

The startup pipeline runs the local orchestrator workflow with `tqdm` progress, colorized clean/dirty repository status, and saved logs under `reports/`.

**Recommended entrypoint:**

```powershell
.\scripts\run-startup.ps1
```

Legacy full pipeline (includes unit tests and broader audits):

```powershell
.\.venv\Scripts\python.exe scripts\run_orchestrator_pipeline.py --preview --profile optimized
```

Official global apply mode:

```powershell
.\scripts\run-startup.ps1 -ApplyGlobal -ConfirmGlobalWrite
```

Or via the legacy pipeline:

```powershell
.\.venv\Scripts\python.exe scripts\run_orchestrator_pipeline.py --apply-global --confirm-global-write --profile optimized
```

Pipeline outputs:

- `reports/orchestrator-pipeline.log`
- `reports/orchestrator-pipeline-summary.md`
- `reports/orchestrator-pipeline-summary.json`
- `reports/publication-applied.md` when global publication is applied
- `reports/global-publication-rollback.md` with backup restore notes

The pipeline uses local Python scripts and local clones. It does not call GitHub APIs or consume Codex model tokens.

Terminal colors:

- Green `CLEAN`: repository is clean or safely harvested/skipped as unchanged.
- Yellow `DIRTY`: repository discovery found local uncommitted changes.
- Red `BLOCKED`: harvest refused candidate extraction because the worktree is dirty.

## Repository Registry And Clean Gate

The registry is local-first. `scripts/discover_repositories.py` scans `C:\Users\ppyxe\Documents\GitHub`, reports branch/remote/dirty state/markers, and can update `config/repositories.toml`.

Harvesting uses local clones as source of truth:

- Clean repo: fingerprint tracked safe files, generate candidate knowledge records, update catalog and reports.
- Unchanged clean repo: skip extraction when the stored fingerprint and harvester schema version still match.
- Dirty repo: update state and coverage reports; skip candidate extraction unless the repo has an explicit dirty-harvest exception.
- Missing or disabled repo: do not harvest.

Graphify graphs may be built for dirty or risk-tagged repositories to support architecture queries. That does not override the promotion gate: dirty graphs cannot justify knowledge promotion.

## Knowledge Lifecycle

The intended lifecycle is:

1. Discover repositories with `scripts/discover_repositories.py`.
2. Refresh Graphify graphs with `scripts/run_graphify_cycle.py` (included in startup).
3. Harvest clean repositories with `scripts/harvest_repositories.py`.
3. Store full records under `knowledge/pending/`.
4. Store concise retrieval metadata in `knowledge/catalog.jsonl`.
5. Query the catalog first with `scripts/retrieve_knowledge.py`.
6. Open only the minimum relevant full records.
7. Validate and optionally promote low-risk records with `scripts/promote_knowledge.py`.
8. Keep global/canonical/security/config records blocked until explicit approval metadata exists.

Candidate records include provenance, source commit/fingerprint, source paths, applicability, incompatible conditions, verification, rollback, confidence, and reuse counters.

## What Harvesting Extracts

For each clean repository, the harvester produces deterministic candidate families:

- Repository profile: purpose, stack excerpt, branch, remote, and safe local source-of-truth guidance.
- Source map: harvestable top-level areas, file counts, suffix counts, and representative source paths.
- Stack/dependency profile: registry stack tags plus package/requirements/manifest signals.
- Verification profile: AGENTS verification commands, test files, CI workflows, and deployment signals.
- Verification command records: individual canonical commands from `AGENTS.md`.
- Constraint record: safety/domain boundaries from `AGENTS.md` and registry risk tags.
- Workflow records: repeatable `###` sections from `skills.md`.

Records are concise summaries, not raw source dumps.

## Safety Boundaries

The exclusion policy is part of the design, not an implementation detail.

Never ingest or copy:

- `.env`, credentials, tokens, keys, auth files, or credential-like filenames.
- PHI, private datasets, production payloads, scraped contact exports, or raw data folders.
- SQLite/database files, sessions, logs, caches, generated artifacts, dependency directories, or build outputs.
- Office exports, spreadsheets, binaries, and large files.

High-risk domains such as clinical data, finance, scrapers, simulation robotics, auth/database, deployment, and global config are tagged in the registry so retrieval can apply stricter reuse rules.

## Reports

The main generated reports are:

- `reports/repository-inventory.md`: current local GitHub checkout inventory.
- `reports/harvest-readiness.md`: harvest status by repo.
- `reports/repository-harvest.md`: harvest outcome and candidate counts.
- `reports/knowledge-coverage.md`: enabled repo count, catalog coverage, missing catalog targets, and dirty blockers.
- `reports/repository-knowledge-matrix.md`: per-repo matrix of profile/source-map/stack/verification/workflow/command/constraint coverage.
- `reports/graphify-cycle-summary.md`: Graphify build/merge outcomes by repository.
- `reports/optimized-runtime-smoke-gate.md`: parent model switch decision after global apply.
- `reports/publication-preview.md` and `reports/publication-applied.md`: publication mode and targets.
- `reports/global-publication-rollback.md`: backup-based rollback notes after apply.

Reports are ignored by git because they are generated local state.

## How To Know Whether A Repo Is Known

A repo is known at metadata level when it appears in `config/repositories.toml` and `reports/repository-inventory.md`.

A repo is known at reusable-knowledge level when:

- `reports/repository-knowledge-matrix.md` shows `yes` for profile, source map, stack/deps, and verification.
- `knowledge/catalog.jsonl` has entries whose `id` starts with that repo slug.
- The catalog entries point to existing files under `knowledge/pending/` or promoted knowledge folders.
- `knowledge/INDEX.md` lists the repo with candidate coverage.
- The repo is clean or was harvested before becoming dirty.

If a repo is listed as `blocked_dirty_worktree`, the orchestrator knows the repo exists but does not treat its current local state as reusable knowledge.

## Command Reference

Run from the repository root:

```powershell
.\scripts\run-startup.ps1
.\.venv\Scripts\python.exe scripts\run_graphify_cycle.py
.\.venv\Scripts\python.exe scripts\query_graph.py query "Which repositories share authentication components?"
.\.venv\Scripts\python.exe scripts\discover_repositories.py
.\.venv\Scripts\python.exe scripts\harvest_repositories.py
.\.venv\Scripts\python.exe scripts\retrieve_knowledge.py --query orsi --status candidate
.\.venv\Scripts\python.exe scripts\publish_global_rules.py --preview --profile optimized
```

Use `--apply` on promotion or global publication only when the requested state change is intentional and allowed by policy.

## Verification

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\scripts\run-startup.ps1
.\.venv\Scripts\python.exe scripts\validate_codex_config.py
.\.venv\Scripts\python.exe scripts\run_graphify_cycle.py
.\.venv\Scripts\python.exe scripts\query_graph.py query "How does harvesting use graphs?" --scope local
.\.venv\Scripts\python.exe scripts\publish_global_rules.py --preview --profile optimized
git status --short --ignored
```

## Troubleshooting And Rollback

- If a repo is blocked, inspect `git status --short` in that repo. Clean or intentionally preserve the work before harvesting.
- If a catalog entry points to a missing file, rerun `scripts/harvest_repositories.py` after confirming the source repo is clean.
- If TOML validation fails, run `scripts/validate_codex_config.py` and fix syntax or missing local agent config references before publication.
- If GPT-5.6 Terra fails in terminal with “requires a newer version of Codex”, upgrade the Codex app/CLI or publish with `-SkipRuntimeSmoke` until smoke passes.
- If global publication must be rolled back, use `reports/global-publication-rollback.md` and copy files from the listed `backups/global-sync/<timestamp>/` folder back to the matching global paths.
- If a record looks too broad, leave it as `candidate` and narrow applicability before promotion.

## Operating Principles

- Prefer index-first retrieval over loading full records.
- Prefer local repository instructions over generalized knowledge.
- Treat harvested lessons as candidates until verification and promotion rules are satisfied.
- Keep global rules small; put detailed reusable knowledge in this repo.
- Never declare production success without traceable production evidence.
