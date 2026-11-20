# Design brief

Fill in the following items before proposing changes. Keep the brief in the handoff unless the repository already maintains one or explicitly requests a file.

- Product, users, and the task they need to complete.
- Target routes, owned files, approved references, and current frontend stack.
- Existing colors, type, spacing, and components, including theme and interaction states.
- Accessibility and localization requirements, including required themes and languages.
- Workflows, server contracts, and permission conditions to preserve.
- Proposed change, tradeoffs, and acceptance checks.

Inspect any `DESIGN.md`, component stories, token and theme files, CSS utilities, and representative screens. Use the repository's lockfile and source to identify the installed stack and libraries.

| Design system | Approach |
|---|---|
| Established | Reuse approved tokens, components, typography, and theme settings. Fix divergence at the existing source where the change stays within scope. |
| Partial | Identify recurring patterns. Consolidate duplication safely and add a token or component only when it fills a demonstrated gap. |
| None | Base the brief on real workflows, density, existing assets, and approved references. Agree on direction before a broad redesign. |

Use typography, alignment, spacing, and semantic color to clarify hierarchy. Distinguish primary actions and keep components predictable across contexts. Preserve the product's identity and avoid decorative elements that compete with the user's task.
