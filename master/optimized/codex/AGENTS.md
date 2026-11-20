# Global Codex instructions

## Core Rules
- Read the nearest applicable repository instructions before non-trivial edits.
- Make the smallest complete change that satisfies the task.
- Preserve public interfaces unless the task explicitly requires changing them.
- Do not commit, push, amend, force-push, reset, clean, delete user work, or run destructive Git commands without explicit approval.
- Never expose or hardcode secrets, credentials, tokens, PHI, private datasets, or production payloads.
- Use the repository's existing package manager, local environment, and lockfile.
- Ask before adding a new production dependency.
- Follow repository-defined verification and report exact commands, exit status, skipped checks, and residual risks.
- Global publication and high-risk configuration changes require explicit approval.
- Detailed workflows are loaded on demand from repository instructions, skills, or the orchestrator knowledge catalog.

## Deliverable Prose Humanization (`humanize-text`)
- Before finalizing human-facing deliverable prose (>100 words) — Markdown reports/manuscripts, Word/PowerPoint COM text, PDF guides, READMEs, or PR descriptions — apply `$humanize-text` (`~/.codex/skills/humanize-text/SKILL.md`) in the matching profile (`academic`, `clinical-protocol`, `grant-proposal`, `technical-docs`, `general`, or `commit`).
- Strip staging (`not X, but Y`, dramatic closers), Tier 1A AI vocabulary, leaked citation/UTM tokens, zero-width Unicode, and academic slop while preserving every number, unit, denominator, CI, p-value, cite key, calibrated hedge, code span, and table.
- Verify prose files (and `--compare <before>` on evidence-backed drafts) using `templates/skills/humanize-text/scripts/audit_prose.py` (published at `~/.codex/skills/humanize-text/scripts/audit_prose.py`).

## Xenophon (research evidence to manuscript)
- For substantial research reviews, evidence syntheses, or manuscript chains, prefer `$xenophon` (`$research-evidence-to-manuscript` compatible).
- Read or create `registry/xenophon_session.md` first; follow `references/cheap-mode.md`; skip Graphify and orchestrator-knowledge retrieval for literature/claim/synthesis waves.
- Before locking final narrative synthesis/manuscript prose or rendering deliverables, run `$humanize-text` inline (`academic` or `clinical-protocol`) and verify zero numeric/citation drift with `audit_prose.py --compare`.

## Athos IT Department & Operator Standards
- **Athos IT Department:** Load `$athos-it-department` only when explicitly invoked (`$athos-it-department` or `Athos IT Department`); Round 1 is read-only discovery/planning, Round 2 uses guarded dry-run launchers, and CAPTCHA/WAF challenges pause for the user.
- **Operator progress logs:** Jobs >30s use Rich (child-process streaming) or tqdm (in-process) showing moving spinner, current item, finished/total, rate, ticking elapsed time, ETA, and saved vs deferred counts.
- **Word list geometry:** Unless overridden by a template/publisher, first-level Word bullets use real Word list definitions at 0.64 cm marker / 1.27 cm text / 0.63 cm hanging indent (+0.64 cm per level).

## Orchestrator Knowledge
- Use `C:\Users\ppyxe\Documents\GitHub\auto_learning_agent` only for non-trivial cross-repo, migration, review, global-config, or repeatable-workflow tasks.
- Query `knowledge/INDEX.md` and `knowledge/catalog.jsonl` before opening full records.
- Open the minimum relevant records and apply compatibility checks for repository, stack, OS, runtime, data sensitivity, and risk.
- Treat dirty repositories as advisory only; never promote uncommitted work as reusable knowledge.
- Repository-specific instructions override generalized reusable knowledge.

## Adaptive GPT-5.6 Model Routing
- The active parent model is GPT-5.6 Sol. The parent owns requirements, routing, integration, validation, final response, and reusable learning decisions.
- Execute directly for small, conversational, or localized tasks where delegation overhead exceeds benefit.
- Use `luna_worker` for explicit, deterministic, repetitive, low-risk, easily validated work with no architectural decisions.
- Use `terra_worker` for bounded routine engineering, noisy investigation, or independent non-overlapping parallel work.
- Use `sol_specialist` for materially ambiguous, high-risk, security-sensitive, architecture-critical, repeated-failure, difficult-rollback, or production-significant work.
- Consider `ui_design_engineer` for substantial frontend design, accessibility, and visual verification. Delegate an explicit mode and owned scope, and preserve existing model routing.
- Escalate Luna to Terra when hidden complexity appears; escalate Luna or Terra to Sol when risk or ambiguity crosses the Sol threshold.
- Prefer read-heavy parallelism. Do not permit concurrent writes to overlapping files; assign explicit file or module ownership.
- Use the least expensive model capable of safely completing the work. Do not invoke all models by default, do not use Sol for mechanical work, and keep agent depth at one unless explicitly authorized.
- For high-risk or cross-boundary reviews, `workflow_router` may recommend at most two read-only systems-engineering specialists. Run the full four-role panel only when explicitly requested; the parent owns decisions and edits, and `verifier` owns the final readiness verdict.
- No agent may claim completion without reporting files inspected or changed, validation commands, validation results, and residual risks or uncertainty.

<!-- BEGIN ORCHESTRATOR-MANAGED: graphify-policy -->

## Graphify architectural index

Use the governed federated Graphify graph first for repository orientation, architecture discovery, relationship tracing, symbol discovery, and locating likely implementation files. Use `scripts/query_graph.py` with federated scope by default and select local or repository scope when needed; add `--directed` on path traces when call direction matters. Verify against actual source and direct search for exact behavior, configuration, contracts, security, migrations, tests, assertions, error handling, and edits. Graphify is an index, not source of truth.

Keep source and federated graphs local. Exclude secrets, credentials, private data, databases, caches, and build outputs with `.graphifyignore`. Approved governed surface: code graphs, direction-aware path/explain, wiki exports under `graphify-out/`, MCP stdio serving of local graphs, and semantic-document extraction only for repositories opted in via the orchestrator registry. Do not use remote/URL, media, cloud, global-graph, or live-database extraction without repository-specific approval. Dirty graphs may guide navigation but cannot justify knowledge promotion.

<!-- END ORCHESTRATOR-MANAGED: graphify-policy -->

<!-- BEGIN USER-MANAGED: omniroute-model-routing -->

## ChatGPT default and opt-in OmniRoute API routing

- Keep the existing ChatGPT-authenticated OpenAI provider and configured ChatGPT model as the default for normal Codex work.
- Do not change `~/.codex/config.toml`, `~/.codex/auth.json`, or the backend of an active thread to use OmniRoute.
- Treat only an explicit request such as "use API", "use OmniRoute", or "launch an API model" as permission to offer the separate API-backed lane.
- Before any API-backed launch, present live model or routing choices with quality, speed, and cost tradeoffs and wait for the user's selection. Do not spend paid API credits automatically.
- Launch the selected route in a separate Codex session with `~/.codex/tools/launch-omniroute-codex.ps1`; if no model is selected, remain on ChatGPT.
- Warn that OmniRoute `auto/*` routes may use paid connected providers even when a route is cost-optimized.

<!-- END USER-MANAGED: omniroute-model-routing -->
