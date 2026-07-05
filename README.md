# auto_learning_agent

`auto_learning_agent` is the local master repository for governed Codex/Cursor orchestration on this machine. It stores the repository registry, safe knowledge extraction tools, candidate knowledge records, retrieval policy, promotion policy, global publication previews, and the operator documentation needed to keep those pieces auditable.

The repository is deliberately not a raw mirror of every project. It captures safe, reusable knowledge from local Git checkouts: architecture maps, workflows, verification commands, stack and dependency signals, safety constraints, tests/CI/deployment signals, and concise source summaries. It excludes secrets, credentials, PHI, private datasets, scraped contact exports, SQLite/runtime state, caches, dependencies, binaries, and generated artifacts.

## Current Phase

The repo is in the master knowledge expansion phase.

- Global Codex/Cursor activation is already wired through generated top-level instructions under `master/`.
- The local registry tracks 10 GitHub checkouts under `C:\Users\ppyxe\Documents\GitHub`.
- Clean repositories can be deep-harvested into `knowledge/pending/`.
- Dirty repositories are registered and reported, but blocked from candidate extraction until their worktrees are clean.
- Knowledge remains candidate-first unless validation and promotion rules explicitly allow a status change.

## Repository Layout

- `AGENTS.md` and `skills.md` define repo-local agent policy and repeatable workflows.
- `config/repositories.toml` is the enabled local repository registry.
- `config/retrieval-policy.toml` defines index-first retrieval budgets.
- `config/promotion-policy.toml` defines candidate-first promotion rules and high-impact approval gates.
- `knowledge/INDEX.md` is the generated high-level index.
- `knowledge/catalog.jsonl` is the concise retrieval catalog.
- `knowledge/pending/` stores full candidate records.
- `knowledge/schemas/knowledge-record.schema.json` defines required knowledge-record fields.
- `scripts/` contains stdlib-only tools for discovery, harvesting, retrieval, promotion, audit, synthesis, publication preview/apply, and TOML validation.
- `reports/` receives ignored local Markdown reports.
- `master/` contains generated Codex/Cursor top-level instruction previews.
- `backups/global-sync/` stores global publication backups when publication is explicitly applied.

## Local Setup

Use the repo-local environment. The startup pipeline requires `tqdm` for real terminal progress bars.

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

This README/knowledge expansion work does not require another global publication. Publish again only when a new global instruction change is intentionally approved.

## Startup Pipeline

The startup pipeline runs the local orchestrator workflow with `tqdm` progress and writes logs under `reports/`.

Preview mode performs validation, audit, discovery, harvest, retrieval smoke, synthesis, and publication preview without writing global folders:

```powershell
.\.venv\Scripts\python.exe scripts\run_orchestrator_pipeline.py --preview
```

Official global apply mode performs the same local checks and then writes the generated top-level instructions into `C:\Users\ppyxe\.codex` and `C:\Users\ppyxe\.cursor`:

```powershell
.\.venv\Scripts\python.exe scripts\run_orchestrator_pipeline.py --apply-global --confirm-global-write
```

Pipeline outputs:

- `reports/orchestrator-pipeline.log`
- `reports/orchestrator-pipeline-summary.md`
- `reports/orchestrator-pipeline-summary.json`
- `reports/publication-applied.md` when global publication is applied
- `reports/global-publication-rollback.md` with backup restore notes

The pipeline uses local Python scripts and local clones. It does not call GitHub APIs or consume Codex model tokens.

## Repository Registry And Clean Gate

The registry is local-first. `scripts/discover_repositories.py` scans `C:\Users\ppyxe\Documents\GitHub`, reports branch/remote/dirty state/markers, and can update `config/repositories.toml`.

Harvesting uses local clones as source of truth and keeps a strict clean gate:

- Clean repo: fingerprint tracked safe files, generate candidate knowledge records, update catalog and reports.
- Unchanged clean repo: skip extraction when the stored fingerprint and harvester schema version still match.
- Dirty repo: update state and coverage reports, but write no candidate records.
- Missing or disabled repo: do not harvest.

Dirty repos are not treated as reusable knowledge because uncommitted work can be experimental, partial, user-owned, or unsafe to generalize.

## Knowledge Lifecycle

The intended lifecycle is:

1. Discover repositories with `scripts/discover_repositories.py`.
2. Harvest clean repositories with `scripts/harvest_repositories.py`.
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
- `reports/global-publication-diff.md`: global publication diff preview.
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
.\.venv\Scripts\python.exe scripts\discover_repositories.py
.\.venv\Scripts\python.exe scripts\harvest_repositories.py
.\.venv\Scripts\python.exe scripts\retrieve_knowledge.py --query orsi --status candidate
.\.venv\Scripts\python.exe scripts\promote_knowledge.py
.\.venv\Scripts\python.exe scripts\synthesize_top_level_instructions.py --preview
.\.venv\Scripts\python.exe scripts\publish_global_rules.py --preview
.\.venv\Scripts\python.exe scripts\run_orchestrator_pipeline.py --preview
```

Use `--apply` on promotion or global publication only when the requested state change is intentional and allowed by policy.

## Verification

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe scripts\validate_codex_config.py
.\.venv\Scripts\python.exe scripts\audit_global_instructions.py
.\.venv\Scripts\python.exe scripts\discover_repositories.py
.\.venv\Scripts\python.exe scripts\harvest_repositories.py
.\.venv\Scripts\python.exe scripts\retrieve_knowledge.py --query orsi --status candidate
.\.venv\Scripts\python.exe scripts\synthesize_top_level_instructions.py --preview
.\.venv\Scripts\python.exe scripts\publish_global_rules.py --preview
.\.venv\Scripts\python.exe scripts\run_orchestrator_pipeline.py --preview
git status --short --ignored
```

## Troubleshooting And Rollback

- If a repo is blocked, inspect `git status --short` in that repo. Clean or intentionally preserve the work before harvesting.
- If a catalog entry points to a missing file, rerun `scripts/harvest_repositories.py` after confirming the source repo is clean.
- If TOML validation fails, run `scripts/validate_codex_config.py` and fix syntax or missing local agent config references before publication.
- If global publication must be rolled back, use `reports/global-publication-rollback.md` and copy files from the listed `backups/global-sync/<timestamp>/` folder back to the matching global paths.
- If a record looks too broad, leave it as `candidate` and narrow applicability before promotion.

## Operating Principles

- Prefer index-first retrieval over loading full records.
- Prefer local repository instructions over generalized knowledge.
- Treat harvested lessons as candidates until verification and promotion rules are satisfied.
- Keep global rules small; put detailed reusable knowledge in this repo.
- Never declare production success without traceable production evidence.
