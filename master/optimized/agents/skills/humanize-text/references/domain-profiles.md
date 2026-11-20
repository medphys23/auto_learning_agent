# Domain Profiles, Intensity, and Preservation Rules

Select one profile before editing. Never apply casual-blog heuristics to scientific manuscripts, clinical protocols, or technical specs.

| Pattern / Construct | `academic` | `clinical-protocol` | `grant-proposal` | `technical-docs` | `general` | `commit` |
| --- | --- | --- | --- | --- | --- | --- |
| **Default `--intensity`** | `light` | `light` | `standard` | `standard` | `standard` | `standard` |
| **Default `paraphrase --level`** | `conservative` | `conservative` | `fluent` | `fluent` | `fluent` | n/a |
| **Epistemic hedging (`suggests`, `may indicate`)** | **Preserve** when evidence-tied | **Preserve** | Keep in Approach; sharpen central hypothesis | Flag if vague | Flag if stacked | Flag hard |
| **Passive voice** | **Preserve** in IMRaD Methods | **Preserve** in procedures/endpoints | Prefer active in Aims | Prefer active | Prefer active | Active/imperative |
| **First-person plural (`we`)** | **Preserve** | Match template style | **Preserve** | Prefer `you` / system | Allowed | Omit |
| **Em-dashes (`—` / ` -- `)** | Max 1/paragraph (prefer commas/parentheses) | Flag (replace with commas/parentheses) | Max 1/paragraph | **Ban** | **Ban** | **Ban** |
| **Citation laundering (`studies show` uncited)** | **Flag hard** | **Flag hard** | **Flag hard** | Flag | Flag | n/a |
| **Manuscript boilerplate (`To the best of our knowledge`)** | **Flag hard** | **Flag hard** | Trim generic filler; keep vision | n/a | n/a | n/a |
| **Methodology pseudo-precision (`rigorous`, `comprehensive`)** | **Flag hard** | **Flag hard** | Replace with concrete pilot/design | Flag | Flag | Flag |
| **Stat parade (p-value without effect size/CI)** | **Flag hard** | **Flag** in rationale | **Flag** in preliminary data | Flag | n/a | n/a |
| **Sentence case headings** | Follow target journal style | Follow protocol master | Follow sponsor headings | Sentence case | Sentence case | n/a |
| **Vision / ambition framing** | Trim hype | Trim hype | **Preserve** if paired with feasibility | Trim hype | Trim hype | Ban |

---

## Intensity Dial (`rewrite` / `edit` / Pre-Deliverable Gate)

- **`light` (default for `academic`, `clinical-protocol`):** Fix leaked tokens, Group A staging (`not X, but Y`, staged openers), Tier 1A words, Group F academic slop, and dense Tier 1B/2 clusters. Leave clean, concise sentences untouched ("no change" is valid).
- **`standard` (default for `grant-proposal`, `technical-docs`, `general`, `commit`):** All `light` rules plus rhythm variation, nominalization tightening, and decorative bold-colon list conversion.
- **`deep`:** Structural sentence/paragraph reordering to fix paragraph-reshuffling immunity and metronomic rhythm; verify every claim against `--compare`.

## Paraphrase Levels (`paraphrase` Mode)

- **`conservative` (default for `academic`, `clinical-protocol`):** Change clause order, voice (where allowed), and non-technical phrasing while preserving all technical terms, hedging, attribution, citations, and paragraph boundaries.
- **`fluent` (default for `grant-proposal`, `technical-docs`, `general`):** Restructure multi-sentence logic and topic progression freely from a key-point outline while keeping every factual span, negation, and citation attached.
- **`creative`:** Broad discourse restructuring for narrative or exploratory prose. **Never** use `creative` on cited clinical, statistical, or regulatory facts.

---

## Profile-Specific Guardrails

### `academic` (Manuscripts, Systematic Reviews, Xenophon Syntheses, `AD_Astra`)
- **Human voice:** Neutral, precise, restrained, evidence-bound. Do **not** inject casual contractions, humor, fragments, or personal anecdotes.
- **Reference-list masking:** Pass `--ignore-references` to `audit_prose.py` when auditing manuscripts with numbered Vancouver/APA reference sections so published article titles (e.g. containing `"multifaceted"`) are not falsely flagged as body-text AI tells.
- **Xenophon invariants:**
  - Keep **A (directly supported)**, **B (evidence-informed inference)**, and **C (proposed design)** distinctions explicit.
  - Reject unjustified `systematic`, `exhaustive`, `validated`, `reliable`, `effective`, `causes`, or `generalizable` claims unless the evidence record justifies them.
  - Keep `not reported`, `unclear`, `not retrieved`, and `conflicting evidence` explicit.
- **Preservation:** Exact numbers, units, denominators, confidence intervals, p-values, statistical test names, equations, symbols, and citation keys must remain byte-for-byte consistent (verify with `audit_prose.py --compare`).

### `clinical-protocol` (Study Protocols, SAPs, Delphi Masters, Questionnaires)
- **Human voice:** Formal, unambiguous, regulatory/ethics-ready.
- **Do NOT touch:** Binary PBP step definitions, error/critical-error event wording, inclusion/exclusion criteria lists, endpoint formulas, or verbatim regulatory clauses. Edit only narrative rationale, background, and discussion prose.

### `grant-proposal` (Funding Proposals, Specific Aims, Project Summaries)
- **Key rule:** `claim <-> feasibility`. Keep concrete vision and ambition statements when paired with preliminary data, pilot metrics, collaborators, or formal methods.
- Fix vague significance claims ("this is an important problem"), method-as-aim phrasing, and boilerplate broader-impacts paragraphs.

### `technical-docs` (READMEs, Architecture Docs, `DART` Guides, PR Bodies)
- **Human voice:** Direct, concrete, scannable, active subject. Name the exact file, command, flag, or component.
- Never alter fenced code blocks, inline code, CLI flags, environment variable names, API paths, or Markdown link targets.
- Repeat exact symbol names rather than varying terminology for style.

### `general` (Reports, Memos, Emails, Essays)
- Match an author writing sample when available. Remove staging, triads, em-dashes, and chatbot residue. Prefer specific concrete facts over abstract summaries.

### `commit` (Commit Messages, Changelogs)
- Imperative mood, concrete component and behavior, zero AI-flavored filler verbs (`enhances`, `improves robustness`, `streamlines`).
