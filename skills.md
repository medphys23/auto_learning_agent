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
