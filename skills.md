# auto_learning_agent - Codex repeatable workflows

Inherits cross-repo patterns from `~/.codex/skills.md`. Dual canonical: mirror each workflow in `.cursor/skills/<name>/SKILL.md` when formal skill tooling is needed.

### Local MVP orchestrator bootstrap

**Triggered by:** Requests to implement or refresh the local orchestrator bootstrap.

**Preconditions:**
- Work from `C:\Users\ppyxe\Documents\GitHub\auto_learning_agent`.
- Use the repo-local `.venv` interpreter.
- Install utility requirements with `uv pip install --python .\.venv\Scripts\python.exe --link-mode hardlink -r requirements.txt`.
- Treat global Codex/Cursor folders as read-only unless a separate approved publication task exists.

**Steps:**
1. Re-read `AGENTS.md`, `skills.md`, and the current git status.
2. Keep repo policy, config, schemas, scripts, tests, and reports local to this repository.
3. Run audit and validation scripts before reporting readiness.
4. Preserve generated reports as ignored local artifacts unless the user explicitly asks to track them.
5. For repository knowledge expansion, harvest only clean repos into candidate records and use coverage reports to explain blocked dirty repos.
6. Treat `auto_learning_agent` as the only dirty-harvest exception because orchestrator runs regenerate local state, reports, candidates, and master previews; the exception is configured with `allow_dirty_harvest = true`.
7. For unattended local operation, run `scripts\run_orchestrator_pipeline.py --preview`; use `--apply-global --confirm-global-write` only for explicit global publication.
8. Run `scripts\audit_dependency_catalog.py` when checking whether dependency manifests are reflected in repo/global stack catalogs; treat missing packages as review flags, not automatic promotion.
9. Use `--profile optimized` for the token-optimized profile; pair it with global apply only when `config/context-optimization.toml` allows it and the user explicitly provides `--confirm-global-write`.
10. Global publication keeps only the newest 2 backup roots under `backups/global-sync/` by default; override with `--backup-keep N` only when the user explicitly asks.
11. Read colorized pipeline output: green `CLEAN`, yellow `DIRTY`, red `BLOCKED`.

**Verification:**
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe scripts\validate_codex_config.py
.\.venv\Scripts\python.exe scripts\audit_global_instructions.py
.\.venv\Scripts\python.exe scripts\audit_context_budget.py
.\.venv\Scripts\python.exe scripts\discover_repositories.py
.\.venv\Scripts\python.exe scripts\harvest_repositories.py
.\.venv\Scripts\python.exe scripts\audit_dependency_catalog.py
.\.venv\Scripts\python.exe scripts\retrieve_knowledge.py --query orsi --status candidate
.\.venv\Scripts\python.exe scripts\retrieve_knowledge_for_repo.py --cwd .
.\.venv\Scripts\python.exe scripts\synthesize_top_level_instructions.py --preview --profile legacy
.\.venv\Scripts\python.exe scripts\synthesize_top_level_instructions.py --preview --profile optimized
.\.venv\Scripts\python.exe scripts\publish_global_rules.py --preview --profile legacy
.\.venv\Scripts\python.exe scripts\publish_global_rules.py --preview --profile optimized
.\.venv\Scripts\python.exe scripts\propagate_orchestrator_retrieval_hints.py
.\.venv\Scripts\python.exe scripts\run_optimized_knowledge_cycle.py --strict
.\.venv\Scripts\python.exe scripts\run_optimized_cutover.py --allow-dirty
.\.venv\Scripts\python.exe scripts\run_orchestrator_pipeline.py --preview --profile legacy
.\.venv\Scripts\python.exe scripts\run_orchestrator_pipeline.py --preview --profile optimized
git status --short --ignored
```

**Iteration notes:**
- 2026-07-04: Created the local MVP workflow with preview-only global publication and stdlib-only scripts.
- 2026-07-04: Added local GitHub repository discovery and deep-harvest workflow; dirty repositories are recorded but blocked from candidate extraction.
- 2026-07-05: Added top-level global instruction synthesis and guarded publication with backups, diffs, and explicit confirmation.
- 2026-07-05: Expanded safe repository knowledge harvesting with source maps, stack/dependency profiles, verification profiles, coverage reports, and a full README operator manual.
- 2026-07-05: Added the `run_orchestrator_pipeline.py` startup pipeline with tqdm phase logs and guarded global apply mode.
- 2026-07-05: Added colorama-backed clean/dirty/blocked repository status output to the pipeline log stream.
- 2026-07-05: User flagged excessive global-sync backups; publication now prunes older backup roots and retains the newest 2 by default.
- 2026-07-05: User noticed `colorama` was missing from published global stack catalog; synthesis now injects the orchestrator pipeline `tqdm`/`colorama` row into generated Codex and Cursor stack catalogs.
- 2026-07-05: Added dependency catalog audit report for `requirements.txt`, `pyproject.toml`, `package.json`, and common JS lockfiles; missing catalog mentions are review flags only.
- 2026-07-05: Added Shadow v1 token-optimization profile; legacy remains default, optimized writes preview artifacts under `master/optimized/` and refuses global apply.
- 2026-07-09: Optimized profile became the default local profile with guarded global apply, slim global skills index generation, repo-scoped retrieval, repo hint previews, and a manual optimized knowledge cycle.
- 2026-07-09: Added one-command optimized cutover wrapper for harvest, readiness, preview, and optional confirmed global publication.
- 2026-07-09: Added a local `auto_learning_agent` dirty-harvest exception; other dirty registered repos remain blocked unless explicitly approved and configured.

### Governed Graphify integration

**Triggered by:** Requests to install Graphify, generate a repository architecture graph, or add Graphify guidance to registered repositories.

**Steps:**
1. Install the user-local CLI with `uv tool install graphifyy` (>= 0.9.34); do not add it as a repository dependency. The sibling clone `C:\Users\ppyxe\Documents\GitHub\graphify` is a read-only upstream reference registered with `graphify_cycle = false`.
2. Bootstrap registered repositories with the guarded Graphify propagation command; keep all `graphify-out/` artifacts ignored and local. Reference-only repositories are never written.
3. Run `scripts\run_graphify_cycle.py` to update per-repository graphs and the federated graph with two concurrent repositories. Incremental refresh preserves the upstream shrink-guard; `--force` is the intentional full-rebuild escape hatch. Each built graph gets an advisory `diagnose multigraph` health check recorded in the cycle summary.
4. Opt-in surfaces: `--semantic` adds document extraction only for repositories with `graphify_semantic = true`, non-sensitive risk tags, and an LLM backend key in the environment; `--wiki` exports agent-crawlable wikis under `graphify-out/`.
5. Query federated scope by default with `scripts\query_graph.py`; use local or repository scope when exact context is needed, add `--directed` to `path` traces when call direction matters, then verify conclusions in source and tests. `scripts\run_graphify_mcp.py` serves a local graph over MCP stdio for interactive sessions.
6. Dirty and risk-tagged repositories may contribute code-only graphs, but dirty state remains ineligible for knowledge promotion. Remote/URL ingestion, live-database, media, cloud, and global-graph features remain gated behind separate approval.

**Verification:**
```powershell
graphify --version
.\.venv\Scripts\python.exe scripts\propagate_graphify_integration.py
.\.venv\Scripts\python.exe scripts\run_graphify_cycle.py
.\.venv\Scripts\python.exe scripts\query_graph.py query "How does repository knowledge propagation work?"
.\scripts\run-startup.ps1
```

**Iteration notes:**
- 2026-08-06: Cloned upstream `Graphify-Labs/graphify` as a sibling reference repo; upgraded `graphifyy` to 0.9.34; replaced the shrink-guard-bypassing `update --force` refresh with guarded incremental `extract`; added diagnose health checks, `--semantic`/`--wiki` opt-in surfaces, directed path traces, and an MCP stdio launcher.

### Federated orchestrator startup

**Triggered by:** Routine refresh of graphs, harvested knowledge, optimized globals, or cross-repo architecture queries.

**Steps:**
1. From repo root, run `.\scripts\run-startup.ps1` for preview-only cycle. Discovery auto-registers new GitHub checkouts into `config\repositories.toml` before graphify and harvest.
2. Review `reports\optimized-cutover-readiness.md` and `reports\graphify-cycle-summary.md`.
3. Apply globals with `.\scripts\run-startup.ps1 -ApplyGlobal -ConfirmGlobalWrite` when reports look correct.
4. Optionally add `-ApplyRepoHints -ConfirmRepoWrite` to refresh registered repo retrieval hints.
5. For a single drag-and-drop apply of cycle + globals + repo hints + Graphify policy files, drop `APPLY-EVERYTHING.cmd` into the terminal, press Enter, and type `APPLY` (or pass `-Yes`).
6. Query architecture with `scripts\query_graph.py`; verify exact behavior in source.

**Verification:**
```powershell
.\scripts\run-startup.ps1
.\.venv\Scripts\python.exe scripts\query_graph.py query "How does harvesting use graphs?" --scope local
```

**Iteration notes:**
- 2026-08-09: Added root `APPLY-EVERYTHING.cmd` / `scripts\apply-everything.ps1` as the drag-and-drop full-apply launcher (typed `APPLY` confirmation; includes Graphify propagation).
- 2026-08-03: Startup discovery now passes `--write-registry` so new folders under `Documents\GitHub` are registered automatically before graphify and harvest; existing registry scope, risk tags, enabled state, and notes are preserved.
- 2026-07-11: Added `run-startup.ps1` / `run_startup.py` as the one-command operator entrypoint; global publish now includes `07-graphify.mdc` and gates GPT-5.6 parent model on runtime smoke unless explicitly forced or skipped.

### Risk-triggered systems-engineering review

**Triggered by:** High-risk or cross-boundary architecture, reliability, security, quality, release, migration, provider, database, deployment, or supply-chain work; or an explicit request for the full systems-engineering panel.

**Steps:**
1. The parent reads active instructions and queries the governed Graphify index first, then verifies relevant claims in source.
2. `workflow_router` classifies the task and recommends no more than two relevant read-only specialists automatically.
3. Select from `systems_architect`, `reliability_operations_reviewer`, `security_boundary_reviewer`, and `quality_release_reviewer`. Run all four only when the user explicitly requests the full panel.
4. Keep specialist selection separate from Luna/Terra/Sol model-cost routing. Specialists inspect and report; they do not edit, publish, or spawn agents.
5. The parent integrates evidence, owns decisions and edits, runs target-repository verification, and sends the integrated result to `verifier`.
6. `verifier` returns the final `READY`, `CONDITIONALLY READY`, or `NOT READY` decision.
7. Record optional `specialist_roles` in routing history only when specialist review materially affected the task. Never invoke model-backed agents from deterministic startup harvesting.

**Verification:**
```powershell
.\.venv\Scripts\python.exe scripts\validate_codex_config.py
.\.venv\Scripts\python.exe scripts\validate_codex_routing.py
.\.venv\Scripts\python.exe scripts\publish_global_rules.py --preview --profile optimized --agents-only
```

**Iteration notes:**
- 2026-08-05: Added a read-only systems-engineering panel with bounded, risk-triggered routing and verifier-owned final readiness.

### Optimized knowledge cycle and cutover

**Triggered by:** Requests to refresh optimized orchestrator knowledge, evaluate optimized cutover readiness, publish optimized global rules, or add retrieval hints to registered repositories.

**Preconditions:**
- Work from `C:\Users\ppyxe\Documents\GitHub\auto_learning_agent`.
- Use `.\.venv\Scripts\python.exe`.
- Clean registered repositories before strict readiness runs; dirty repositories are listed as blockers.
- Global publication still requires explicit `--apply --confirm-global-write`.
- Cross-repo hint writes require both `--apply --confirm-repo-write` and `allow_other_repository_writes = true`.

**Steps:**
1. Run `scripts\run_optimized_knowledge_cycle.py` to refresh discovery, harvest, optimized synthesis, context budget, and readiness reports.
2. Review `reports\optimized-cutover-readiness.md`; treat `NO-GO` as a blocker for global cutover.
3. Preview optimized publication with `scripts\publish_global_rules.py --preview --profile optimized`.
4. Use `scripts\retrieve_knowledge_for_repo.py --cwd <repo>` from registered repositories when optimized instructions point to the central catalog.
5. Preview repo hint propagation with `scripts\propagate_orchestrator_retrieval_hints.py`; do not apply without explicit approval.
6. For approved global cutover, run `scripts\publish_global_rules.py --apply --confirm-global-write --profile optimized`; verify backups under `backups\global-sync\` and `backups\legacy-pre-optimized\`.
7. For the single-command path, run `scripts\run_optimized_cutover.py`; add `--allow-dirty` to bypass only dirty-repo blockers, and add `--apply --confirm-global-write` only when global publication and registered repo hint propagation are explicitly approved.

**Verification:**
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe scripts\run_optimized_knowledge_cycle.py --strict
.\.venv\Scripts\python.exe scripts\run_optimized_cutover.py --allow-dirty
.\.venv\Scripts\python.exe scripts\publish_global_rules.py --preview --profile optimized
.\.venv\Scripts\python.exe scripts\propagate_orchestrator_retrieval_hints.py
.\.venv\Scripts\python.exe scripts\audit_context_budget.py
```

**Iteration notes:**
- 2026-07-09: Added manual optimized harvest/readiness cycle, config-gated optimized publication, slim skills index, repo-scoped retrieval CLI, and preview-first repository hint propagation.
- 2026-07-09: Added `run_optimized_cutover.py` and PowerShell wrapper for one-command harvest, readiness, preview, optional confirmed global publication, and registered repo hint propagation.
