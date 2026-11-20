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

## Athos IT Department

- Load `$athos-it-department` only when the user explicitly invokes `$athos-it-department` or says `Athos IT Department` for the task.
- Use it for substantial browser automation, scraping, imports, migrations, or repeatable jobs that need read-only discovery followed by phased implementation and verification.
- Round one is read-only browser discovery and decision-complete planning. Do not submit, upload, send, or mutate the external system.
- Round two creates project-specific numbered launchers with dry-run defaults, explicit apply gates, resumable state, operator logs, throttling controls, and read-back verification.
- Never bypass CAPTCHA, WAF, bot detection, access controls, or site security. Pause for user-completed challenges and revalidate state before resuming.

Canonical skill: `~/.codex/skills/athos-it-department/SKILL.md`. Cursor mirror: `~/.cursor/skills/athos-it-department/SKILL.md`; routing rule: `~/.cursor/rules/09-athos-it-department.mdc`.

## Operator progress logs

When producing a capture, scrape, export, migration, transcription, or other job the user waits on, keep a live terminal log. Use Rich for streamed child-process jobs. tqdm is acceptable for an in-process Python loop only when it shows the same fields.

The live line shows a moving spinner, the job name, the current item, a bar with percentage and finished/total, items per minute, elapsed time that keeps ticking during waits, remaining time, and separate saved and deferred counts. Finished includes deferred or failed items, so a failing run does not stay at 0.

Print event lines above that bar: item start; green success with the saved identity; yellow deferral with the item and the reason, without discarding earlier good results; a cyan status line with saved, deferred, and next; and a red fatal stop. Do not say "write" unless a record was saved.

Skip this display for a few-second command, a unit test, or a one-line check.

Cursor mirror: `~/.cursor/rules/08-operator-progress-logs.mdc`. Skill: `~/.cursor/skills/operator-progress-logs/SKILL.md`.

## Word list geometry

- Unless a user-supplied template or publisher specification overrides it, first-level Word bullets use a marker at exactly 0.64 cm, text at 1.27 cm, and a 0.63 cm hanging indent.
- Increment marker and text positions by 0.64 cm for each nested level while preserving the 0.63 cm hanging indent.
- Use real Word list definitions, never typed bullet characters.

## Orchestrator Knowledge
- Use `C:\Users\ppyxe\Documents\GitHub\auto_learning_agent` only for non-trivial cross-repo, migration, review, global-config, or repeatable-workflow tasks.
- Query `knowledge/INDEX.md` and `knowledge/catalog.jsonl` before opening full records.
- Open the minimum relevant records and apply compatibility checks for repository, stack, OS, runtime, data sensitivity, and risk.
- Treat dirty repositories as advisory only; never promote uncommitted work as reusable knowledge.
- Repository-specific instructions override generalized reusable knowledge.

## Xenophon (research evidence to manuscript)
- For a substantial research review, evidence synthesis, or manuscript evidence chain, prefer the explicit `$xenophon` entrypoint. `$research-evidence-to-manuscript` remains supported for compatibility and natural-language Xenophon routing.
- Read or create `registry/xenophon_session.md` first; follow cheap-mode budgets; do not send overlapping agents the same full question.
- Skip Graphify and orchestrator-knowledge retrieval for literature, claim, synthesis, and manuscript waves.
- Do not invoke for single-article extraction, citation lookups, scrapers, Office rebuilds, Slack, or app UI work.

## Adaptive GPT-5.6 Model Routing
- The active parent model is GPT-5.6 Sol. The parent owns requirements, routing, integration, validation, final response, and reusable learning decisions.
- Execute directly for small, conversational, or localized tasks where delegation overhead exceeds benefit.
- Use `luna_worker` for explicit, deterministic, repetitive, low-risk, easily validated work with no architectural decisions.
- Use `terra_worker` for bounded routine engineering, noisy investigation, or independent non-overlapping parallel work.
- Use `sol_specialist` for materially ambiguous, high-risk, security-sensitive, architecture-critical, repeated-failure, difficult-rollback, or production-significant work.
- Escalate Luna to Terra when hidden complexity appears; escalate Luna or Terra to Sol when risk or ambiguity crosses the Sol threshold.
- Prefer read-heavy parallelism. Do not permit concurrent writes to overlapping files; assign explicit file or module ownership.
- Use the least expensive model capable of safely completing the work. Do not invoke all models by default, do not use Sol for mechanical work, and keep agent depth at one unless explicitly authorized.
- No agent may claim completion without reporting files inspected or changed, validation commands, validation results, and residual risks or uncertainty.

<!-- BEGIN ORCHESTRATOR-MANAGED: graphify-policy -->

## Graphify architectural index

Use the governed federated Graphify graph first for repository orientation, architecture discovery, relationship tracing, symbol discovery, and locating likely implementation files. Use `scripts/query_graph.py` with federated scope by default and select local or repository scope when needed. Verify against actual source and direct search for exact behavior, configuration, contracts, security, migrations, tests, assertions, error handling, and edits. Graphify is an index, not source of truth.

Keep source and federated graphs local. Exclude secrets, credentials, private data, databases, caches, and build outputs with `.graphifyignore`; do not use remote/document/media/database extraction without repository-specific approval. Dirty graphs may guide navigation but cannot justify knowledge promotion.

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
