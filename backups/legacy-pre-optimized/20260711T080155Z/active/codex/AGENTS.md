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

## Orchestrator Knowledge
- Use `C:\Users\ppyxe\Documents\GitHub\auto_learning_agent` only for non-trivial cross-repo, migration, review, global-config, or repeatable-workflow tasks.
- Query `knowledge/INDEX.md` and `knowledge/catalog.jsonl` before opening full records.
- Open the minimum relevant records and apply compatibility checks for repository, stack, OS, runtime, data sensitivity, and risk.
- Treat dirty repositories as advisory only; never promote uncommitted work as reusable knowledge.
- Repository-specific instructions override generalized reusable knowledge.

## Adaptive GPT-5.6 Model Routing
- The active parent model is GPT-5.6 Terra. The parent owns requirements, routing, integration, validation, final response, and reusable learning decisions.
- Execute directly for small, conversational, or localized tasks where delegation overhead exceeds benefit.
- Use `luna_worker` for explicit, deterministic, repetitive, low-risk, easily validated work with no architectural decisions.
- Use `terra_worker` for bounded routine engineering, noisy investigation, or independent non-overlapping parallel work.
- Use `sol_specialist` for materially ambiguous, high-risk, security-sensitive, architecture-critical, repeated-failure, difficult-rollback, or production-significant work.
- Escalate Luna to Terra when hidden complexity appears; escalate Luna or Terra to Sol when risk or ambiguity crosses the Sol threshold.
- Prefer read-heavy parallelism. Do not permit concurrent writes to overlapping files; assign explicit file or module ownership.
- Use the least expensive model capable of safely completing the work. Do not invoke all models by default, do not use Sol for mechanical work, and keep agent depth at one unless explicitly authorized.
- No agent may claim completion without reporting files inspected or changed, validation commands, validation results, and residual risks or uncertainty.
