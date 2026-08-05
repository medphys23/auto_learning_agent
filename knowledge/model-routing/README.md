# Adaptive Model Routing Knowledge

This directory stores selective routing evidence for the Codex GPT-5.6 Sol/Terra/Luna architecture.

Record an event only when a subagent was used, an escalation happened, routing materially affected quality or cost, a routing failure exposed a reusable lesson, a recurring task pattern appeared, or the task was production-significant.

Events may include optional `specialist_roles` when one or more read-only systems-engineering reviewers materially contributed. This field is independent of the Luna/Terra/Sol cost route. Existing records without it remain valid.

Do not record trivial conversational work. Do not store secrets, credentials, full prompts, raw source files, private data, PHI, production payloads, unredacted environment variables, or excessive command output.

Promotion remains candidate-first:

- Candidate: one supported observation.
- Provisional: two consistent validated observations.
- Validated: three or more consistent successful uses with no contradictory failure.
- Deprecated: later evidence shows the rule is stale, harmful, or inefficient.

Routing knowledge should describe task patterns, not repository-specific private details.
