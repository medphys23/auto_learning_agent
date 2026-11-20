---
name: ui-design-engineering
description: Audit, plan, implement, and verify substantial web UI changes using the project's design system and local browser evidence. Use for dashboards, component consistency, responsive layouts, themes, accessibility, and visual regressions.
---

# UI Design Engineering

Choose the parent-assigned mode. AUDIT prioritizes defects and DESIGN specifies the brief and acceptance criteria. Both keep source files read-only. IMPLEMENT requires explicit frontend ownership and permits scoped edits and two correction passes. Escalate overlapping ownership or changes to behavior, permissions, or backend contracts.

Read the repository's instructions and any existing design guide. Use Graphify for orientation where governed, verify against source, and look up only compatible knowledge records. Establish the product purpose, users, approved visual language, stack, accessibility and localization requirements, and workflows before selecting the smallest meaningful change.

- Use the [design brief](references/design-brief.md) to identify the design system and decide which patterns to reuse.
- Use the [visual workflow](references/visual-workflow.md) for browser inspection, comparison, responsive checks, and regression tests.
- Use the [quality rubric](references/quality-rubric.md) to rank defects and report readiness.

Keep screenshots local and use synthetic data. Return verified reusable lessons to the parent as candidate evidence with provenance, applicability, and rollback. Keep brand assets, private data, screenshots, and unverified preferences out of shared knowledge.
