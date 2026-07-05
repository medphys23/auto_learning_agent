<!-- BEGIN ORCHESTRATOR-MANAGED: global-knowledge-layer -->

## Orchestrator Knowledge Layer

Use `C:\Users\ppyxe\Documents\GitHub\auto_learning_agent` as the governed knowledge control plane for non-trivial work.

Activate this layer for multi-file changes, unclear bugs, cross-repo work, reviews, migrations, repeatable workflows, stack propagation, or global instruction changes. Skip it for tiny direct edits and simple factual questions unless the user explicitly asks for orchestrator behavior.

When active:

1. Read active global and repository instructions first.
2. Classify the task by repository, domain, stack, risk, and verification target.
3. Query the orchestrator `knowledge/INDEX.md` and `knowledge/catalog.jsonl` before opening full records.
4. Retrieve only the relevant records: default maximum is 3 primary, 2 supporting, and 1 failure/anti-pattern.
5. Check compatibility before reuse: stack, runtime, OS, deployment, interface, data sensitivity, and repository rules.
6. Respect repository risk tags from `config/repositories.toml`, especially clinical/PHI, finance, scraper/contact-data, simulation-only robotics, auth/database, and global-config changes.
7. Treat dirty repositories as advisory only. Do not harvest or promote their current state as reusable knowledge until clean.
8. Keep repository-local knowledge local unless promotion criteria and evidence justify wider reuse.
9. Require explicit approval before global/canonical/security/auth/network/database/deployment/cost/model/provider/MCP/sandbox/approval-policy changes.
10. Verify using the target repository's `AGENTS.md -> ## Verification` section before reporting readiness.
11. Record reusable, non-obvious lessons as local candidates in the orchestrator repository after successful work.

This layer is a retrieval and governance system, not opaque memory and not a prompt dump. Existing explicit user instructions and safety constraints remain higher priority.

<!-- END ORCHESTRATOR-MANAGED: global-knowledge-layer -->
