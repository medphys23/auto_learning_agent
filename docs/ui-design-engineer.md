# UI Design Engineer v1.0

`ui_design_engineer` is the Codex specialist for substantial frontend presentation work. Use it for dashboard redesign, mobile layout, theme consistency, component accessibility, and screenshot-based review. The workflow router keeps trivial edits with the parent and leaves backend, database, authentication, and manuscript tasks on their existing routes. The parent owns integration and release decisions.

## Invoke locally

In a fresh Codex session for this checkout, ask the parent to delegate a task such as “Use `ui_design_engineer` in AUDIT mode. Inspect the dashboard at mobile and desktop sizes and rank issues with evidence.” Choose one mode.

| Mode | Scope and output |
|---|---|
| AUDIT | Read-only inspection and a ranked defect list |
| DESIGN | Read-only brief, tradeoffs, proposed file scope, and acceptance checks |
| IMPLEMENT | Explicitly delegated frontend files or components, browser evidence, and regression checks |

For IMPLEMENT, name owned files or components and specify the workflows and permission conditions to preserve. Codex subagents inherit the parent's sandbox, approval settings, and provider. Use read-only parent permissions when you need enforced read-only execution. IMPLEMENT requires workspace write permissions from the parent. File ownership and mode are instructions within that sandbox. Escalate changes involving authentication, authorization, storage, clinical workflow logic, or production infrastructure to the parent. [Codex subagent permissions](https://developers.openai.com/codex/subagents)

## Maintain and verify

The project agent lives in `.codex/agents/` with a matching registration in `.codex/config.toml`. Edit [the canonical agent](../.codex/agents/ui_design_engineer.toml) and [the skill in `.agents/skills/`](../.agents/skills/ui-design-engineering/SKILL.md). Optimized synthesis produces the registration fragment, agent, and skill package under `master/optimized/`. For a new reusable reference, add it under the skill's `references/`, link it from `SKILL.md`, and add its relative path to `UI_SKILL_FILES` in the synthesis script. Keep repository-specific design decisions in the target repository, using its existing design guide or an optional `DESIGN.md`.

Run the first two commands for configuration and publisher changes. The optional browser smoke command uses an existing Playwright installation and Chromium to verify a synthetic dashboard. Inspect matching baseline and refined images in its output folder. On a real frontend, use its own test routes, documented development command, and approved fixtures.

```powershell
.\.venv\Scripts\python.exe scripts\validate_codex_config.py
.\.venv\Scripts\python.exe -m unittest discover -s tests
py -3.11 tests/fixtures/ui_design_browser_smoke.py --output reports/ui-design-engineer/screenshots
```

The skill format follows Agent Skills. The browser workflow uses Playwright's guidance on matching screenshot conditions. Anthropic's frontend-design skill offers ideas for visual direction on new interfaces under Apache 2.0. Jakub Krehel's MIT-licensed skills offer focused review examples for typography and accessibility. Both are optional references. Check current license and compatibility before reusing any material. This package contains original instructions and requires neither external skill. [Agent Skills specification](https://agentskills.io/specification) · [Playwright visual comparisons](https://playwright.dev/docs/test-snapshots) · [Anthropic frontend-design](https://github.com/anthropics/skills/tree/main/skills/frontend-design) · [Jakub Krehel skills](https://github.com/jakubkrehel/skills)

## Review, approve, and publish

1. Review the canonical files and test output. Run the scoped preview and inspect `publication-preview.md` for planned paths, hashes, and rollback actions. Review `ui-design-engineer-config-merge-preview.md` for the registration diff.
2. Obtain explicit approval for the listed Codex writes. Resolve any path or content collision with the file owner before rerunning the preview. Differing files in the same namespace stop the publisher.
3. After approval, run the second command and validate the installed settings with the third. Start a new Codex session and confirm the specialist can open the skill and complete a read-only AUDIT.

```powershell
.\.venv\Scripts\python.exe scripts\publish_global_rules.py --preview --profile optimized --ui-design-engineer --reports-dir reports/ui-design-engineer
.\.venv\Scripts\python.exe scripts\publish_global_rules.py --apply --confirm-global-write --profile optimized --ui-design-engineer --reports-dir reports/ui-design-engineer
.\.venv\Scripts\python.exe scripts\validate_codex_config.py --global
```

The scoped publisher targets Codex and adds only the specialist's registration. It stores rollback metadata under `backups/global-sync/` and marks newly created files with `.missing` entries. An identical repeat apply writes no global files. Use the scoped command for this rollout. The broader optimized publisher also includes the package, along with its existing Codex and Cursor targets.

For an approved rollback, open the applied report and the backup named in `global-publication-rollback.md`. If `codex/config.toml.registration.json` exists, compare the live config hash with `published_sha256`. On a match, restore the first `prior_bytes` bytes after verifying they match `prior_sha256`. Otherwise review subsequent edits and remove only the matching registration. For each `.missing` marker, verify the corresponding file matches its published hash before removing it. Validate the config and start a fresh session. The checkout retains its project-scoped agent after a global rollback. To suspend local use, stop delegating to it from this checkout.

## Pilot and reuse

1. **XMED.** Once the current development increment reaches its approved checkpoint, obtain separate approval for the pilot. Run AUDIT and DESIGN on one authorized scheduling or patient-list route using synthetic data. Preserve the Next.js/React design system, XMED's blue identity, clinical status semantics, and English and Greek localization.
2. **Scoped implementation.** Delegate one component or route with named ownership. Capture before and after at 390, 768, and 1440 px in light and dark themes. Exercise keyboard access, validation, permission-dependent controls, and the repository's existing functional and authorization suites. Record gaps and resolve critical regressions before accepting the pilot.
3. **Second repository.** Select a non-XMED frontend with its own brand and component conventions. Repeat AUDIT, then one approved IMPLEMENT task. Use the same rubric and compare scope, mobile behavior, accessibility, and functional outcomes. Confirm the skill adapts to the target design system.
4. **Knowledge review.** Submit reusable lessons as candidates with source commit, paths, stack and compatibility limits, verification, and rollback. Keep branding, screenshots, and private data local. Review evidence from both pilots before requesting broad distribution through the existing promotion policy.
