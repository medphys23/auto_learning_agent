# AI-Writing Pattern Catalog and Meaning-Drift Traps (58 Patterns)

Grounded in Wikipedia's *Signs of AI Writing* (WikiProject AI Cleanup), `blader/humanizer`, `devswha/patina` (MIT), `ssamba1/untell`, `kevin-burns/claude-skills` (`clear-and-human`), `keshavbhatt/paraphrase`, `Aboudjem/humanizer-skill`, `AIScientists-Dev/academic-humanizer`, and `kimhons/humanize`.

**Action rule:** Patterns in **Group A, E, F, and G** justify action on a single sighting. Patterns in **Group B, C, and D** marked *(cluster)* require multiple co-occurring tells before rewriting, unless the active domain profile explicitly bans them.

---

## Group A — Staging Instead of Stating

1. **Not-X-but-Y contrasts (and reversed `Y rather than X`):** `not just X, but Y`, `it's not X, it's Y`, `This does not mean X. It means Y.`, clipped `..., no guessing`, or unmotivated `Y rather than X` contrast framing *(Wikipedia Signs of AI Writing)*. Fix: state Y directly unless X corrects a real misconception held by the reader.
2. **One-line closers and dramatic fragments:** Standalone recap sentences (`That is the real win.`, `Let that sink in.`, `This underscores the importance of...`) or fragment chains (`No nostalgia. No prior.`). Fix: cut recaps that add no new fact; merge fragments into one concrete sentence.
3. **Pseudo-profound aphorisms and definitional-metaphor equations:** `at its core`, `what really matters`, `the deeper issue`, `X is the currency/architecture/backbone/DNA/cornerstone/lifeblood of Y` *(devswha/patina #33, MIT)*. Fix: recover and state the underlying concrete mechanism instead of equating abstractions. *(Distinct from #22 Copula Avoidance: #22 restores `is`; #3 dismantles empty `is the [noun] of` metaphors.)*
4. **Staged run-ups, throat-clearing, and faux-insight setups:** `Let's dive in`, `Here's what you need to know`, `Honestly?`, `Here's the thing:`, `Real talk:`, `What nobody tells you:`, `Most people don't realize` *(devswha/patina #35–#36, MIT)*. Fix: delete the stage-setting and open on the claim.
5. **Phantom objections and false nuance:** `While some might argue...`, `To be clear, I'm not saying...`, `Actually, it's more nuanced than that`, `That said, the reality is more complex` *(devswha/patina #29, MIT)* when no new evidence follows. Fix: delete the phantom defense or keep only the concrete condition.
6. **Heading-echo openers and rhetorical-question openers:** A heading followed by a one-sentence restatement (`## Latency` / `Speed matters.`), or paragraphs opening with `"Why did X happen? The answer is simple."` *(devswha/patina #30, MIT)*. Fix: open directly on the cause or concrete fact.
7. **Self-referential narration:** `This section is organized by...`, `The table below compares...`, `was added to replace...` outside changelogs. Fix: describe the current system or evidence directly.
8. **Colon-reveal / plot-twist setups:** Short noun phrases before a colon staging a dramatic reveal in prose: `The best part: ...`, `The kicker: ...`, `The catch: ...`, `Translation: ...` *(devswha/patina #37, MIT)*. Fix: integrate into a plain sentence.

## Group B — Rhythm, Structure, and Discourse

9. **Forced triads (Rule of Three):** Abstract nouns or parallel examples always arriving in threes (`innovation, inspiration, and insights`). *(Cluster)* Fix: use the true count (two or four is fine) or develop one concrete example.
10. **Metronomic sentence length and 2026 short-cadence flattening:** 3+ consecutive sentences all 12–26 words with identical clause structure, or runs of 4+ clipped <=8-word sentences / identical clause templates (`subject-verb-object` with zero punctuation variety) *(devswha/patina #25, #38; Wikipedia Signs of AI Writing)*. *(Cluster)* Fix: vary sentence length and clause architecture naturally.
11. **Paragraph-reshuffling immunity:** Self-contained paragraphs you could reorder without breaking flow. Fix: tie each paragraph to the prior claim, contrast, or causal link.
12. **Em-dash overuse:** `—` or ` -- ` used repeatedly as a universal connector. Ban completely in `general` and `technical-docs`; allow at most 1 per paragraph in `academic` only when clearer than commas/parentheses.
13. **Connective-opener ladders and conclusion signal words:** Consecutive sentences starting with `Moreover,`, `Furthermore,`, `Additionally,`, `Consequently,`, `Notably,`, or final paragraphs opening with `In conclusion,`, `Ultimately,`, `In summary,`, `All in all,` *(devswha/patina #31, MIT)*. Fix: let logical progression or semantic noun echoes carry transitions.
14. **Repeated sentence openings:** 3+ consecutive sentences starting with the exact same subject (`She... She... She...` or `The system... The system...`). *(Cluster)* Fix: combine clauses or vary syntax.
15. **Stacked qualifiers / leftover hedge debris:** `could potentially possibly`, `might arguably`, `to some extent` paired with an otherwise flat claim. Fix: keep one calibrated qualifier when evidence is uncertain, or commit cleanly.
16. **Post-noun hyphenated pairs:** `the report is high-quality`, `the process is well-documented`. *(Cluster)* Fix: hyphenate before the noun (`a high-quality report`), drop after the verb (`the report is high quality`).
17. **Agentless passive outside Methods and false agency (inanimate actors):** `changes were made`, `it is recommended that`, or promoting abstractions into human actors (`the data tells us`, `the decision emerged`, `the culture shifted`, `this unlocks`, `the strategy demands`) *(devswha/patina #34, MIT)*. *(Allowed: IMRaD Methods passive and standard scientific metonymy like `"the study found"` or `"the trial reported"`.)* Never invent an unstated actor when repairing agency.
18. **Passive nominalization chains and zombie nouns:** `conduct an analysis of`, `give consideration to`, `perform an evaluation of`, `reach a conclusion regarding`, `make an improvement to` *(devswha/patina #26–#27, MIT)*. *(Cluster)* Fix: replace with direct verbs (`analyze`, `consider`, `evaluate`, `conclude`, `improve`).
19. **Stacked subordinate clauses:** Single sentences packing 3+ embedded relative clauses, appositives, or 4+ commas before reaching the main object *(devswha/patina #28, MIT)*. Fix: split into two clear sentences.

## Group C — Inflation and Tiered AI Vocabulary

20. **Tier 1A AI vocabulary (always flag):** `delve`, `tapestry` (figurative), `testament` (figurative), `multifaceted`, `realm`, `interplay`, `in today's ... landscape`.
21. **Tier 1B AI vocabulary (flag + simplify):** `underscore` (verb), `leverage` (figurative verb), `it's worth noting`, `it's important to note`.
22. **Tier 2 AI vocabulary (flag at 2+ per paragraph):** `crucial`, `pivotal`, `vibrant`, `robust` (figurative), `seamless`, `foster`, `enhance`, `showcase`, `notably`, `moreover`, `furthermore`, `garner`, `bolster`, `align with`, `utilize`. *(Keep technical terms like `robust variance` or `gating`.)*
23. **Unanchored comparison adverbs:** `more specific`, `more concrete`, `more efficient`, `more comprehensive`, `more robust`, `more meaningful`, `more strategic`, `more impactful`, `more nuanced` without a named baseline or metric *(devswha/patina #32, MIT)*. *(Cluster)* Fix: name the baseline or state the concrete change.
24. **Significance inflation:** `marks a pivotal moment`, `evolving landscape`, `indelible mark`, `setting the stage for`, `reflects a broader trend`. Fix: keep the dated event and drop the grand commentary.
25. **Superficial `-ing` participle tails:** `..., highlighting its importance`, `..., underscoring the need`, `..., fostering collaboration`. Fix: delete unless backed by a cited mechanism, in which case state it as a direct clause.
26. **Copula avoidance:** `serves as`, `stands as`, `functions as`, `operates as`, `boasts`, `features` replacing simple `is`, `are`, `has`. *(Cluster)*
27. **Promotional / travel-brochure adjectives:** `nestled`, `in the heart of`, `groundbreaking`, `cutting-edge`, `state-of-the-art`, `world-class`, `breathtaking`, `stunning`.
28. **False ranges:** `from X to Y` where X and Y do not form a meaningful continuum. Fix: name the specific items.
29. **Synonym cycling (elegant variation):** Swapping different labels for one entity (`the model` -> `the architecture` -> `the framework`) in consecutive sentences. Fix: repeat the exact technical term.
30. **Generic positive conclusions and "Challenges/Outlook" templates:** `The future looks bright`, `exciting times lie ahead`, `Despite these challenges, X continues to thrive`. Fix: end on the last concrete finding, limitation, or next step.

## Group D — Formatting by Rule

31. **Bold-colon labeled list syndrome:** Turning normal prose into `- **Performance:** Performance improved...`. *(Cluster)* Fix: write flowing prose unless scannable reference items genuinely require labels.
32. **Erratic inline bolding:** Random 1–4 word bold spans mid-paragraph with no structural role. *(Cluster)*
33. **Title Case and decorative headings:** `## Strategic Negotiations And Global Partnerships` or emoji-prefixed headers (`🚀 Launch`). Fix: use sentence case (unless journal/style guide mandates title case) and remove decorative emojis/rules.
34. **Markdown bleeding and quote mismatch:** Raw `**bold**` inside plain-text emails/Word strings, or curly/straight quote switching mid-document (especially curly quotes inside code spans).

## Group E — Leaked Chat, Reference, and Unicode Artifacts (Always Strip)

35. **Chatbot wrapper residue and prompt refusals:** `Great question!`, `Certainly!`, `Of course!`, `I hope this helps`, `Let me know if you'd like...`, `Here is an overview`, `As an AI language model...` *(Wikipedia Signs of AI Writing)*.
36. **Knowledge-cutoff disclaimers and invented guesses:** `as of my last training update`, `while specific details are limited`, `maintains a low profile`, `likely grew up`. Fix: state explicitly what the source does not report (`Not reported in the source`), or omit.
37. **Placeholder / Mad-Libs leftovers:** `[Your Name]`, `[INSERT URL]`, `2026-XX-XX`.
38. **Leaked AI citation and search tokens:** `citeturn0search0`, `contentReference[oaicite:0]{index=0}`, `oai_citation`, `[cite: 1]`, `[span_1](start_span)`, `grok_card`, `ppl-ai-file-upload`, `attributionIndex`.
39. **AI UTM tracking parameters:** `utm_source=chatgpt.com`, `utm_source=openai`, `utm_source=copilot.com`, `referrer=grok.com`.
40. **Zero-width & homoglyph Unicode:** U+200B, U+200C, U+200D, U+FEFF, U+00AD, U+2060, bidi override marks, or Cyrillic/Greek look-alikes embedded inside Latin words.

## Group F — Academic, Clinical, and Engineering Extensions

41. **Citation laundering / vague authority:** `Studies show`, `research suggests`, `experts argue`, `widely believed` with no named citation. Fix: cite the exact primary source (with author/year or key) or delete.
42. **Manuscript boilerplate:** `To the best of our knowledge`, `fills a critical gap in the literature`, `represents a significant advance`, `of paramount importance`, `constitutes the first comprehensive`. Fix: state the exact scope prior work did not cover.
43. **Over-claiming verbs:** Using `proves`, `guarantees`, `confirms universally`, or unqualified `significantly` without a test/estimate. Fix: match verb strength to design (`observed`, `associated with`, `differed by ...`).
44. **Methodology pseudo-precision:** `rigorous analysis`, `careful evaluation`, `exhaustive review`, `meticulous examination`, `comprehensive study` without specifying the method. Fix: name the sample, instrument, bootstrap/statistical model, or inclusion boundary.
45. **Stat parade without effect size or denominator:** Reporting `p < 0.001` alone without raw counts, effect estimate, or confidence interval. Fix: preserve or surface exact effect size, CI, and denominator from source data.
46. **Vague commit/PR verbs:** `improves robustness`, `enhances functionality`, `streamlines workflow` with no concrete change named. Fix: name the component, behavior, and check (`fix(parser): handle CRLF line endings`).
47. **Non-English / mixed-script corruption or silent translation:** Switching language or script unintentionally, or changing date/number formats (`14 March` -> `March 14`, `2` -> `two`) *(keshavbhatt/paraphrase)*.
48. **Truncated rewrite / dropped points:** Omitting sentences, clauses, questions, or list items from the input during proofreading or paraphrasing *(keshavbhatt/paraphrase)*.
49. **Lead defining a generic title as a proper noun:** `"List of X refers to..."` or `"Surgical readiness refers to..."` when awkward or circular *(Wikipedia Signs of AI Writing)*.
50. **Synonym-spinner paraphrasing (near-verbatim copying):** Keeping the source sentence skeleton and replacing isolated adjectives/verbs with thesaurus synonyms (`>=8` shared consecutive non-quoted words) *(websymphony/paraphrasing-tool)*.

---

## Group G — Meaning-Drift Traps (Never Introduce During Rewrite or Paraphrase)

Informed by `ssamba1/untell`, `kevin-burns/claude-skills` (`clear-and-human/scripts/fidelity_check.py`), `devswha/patina` (MIT), and `keshavbhatt/paraphrase`. Check every rewritten or paraphrased passage against these eight failure modes:

51. **Role or agent swap:** Permuting subject and object when changing voice or word order.
    - *Before:* `"The supervisor corrected the trainee before incision."`
    - *Drifted (BAD):* `"The trainee corrected the supervisor before incision."`
    - *Preserved:* `"Before incision, the trainee was corrected by the supervisor."`
52. **Negation flip:** Dropping or shifting `not`, `no`, `never`, `without`, `neither`, `cannot`, or `fails to`.
    - *Before:* `"Simulator completion does not establish clinical readiness."`
    - *Drifted (BAD):* `"Simulator completion establishes clinical readiness."`
    - *Preserved:* `"Completing a simulator module leaves clinical readiness unestablished."` *(or keep `does not`)*
53. **Altered quantity (including spelled-out numbers):** Changing digits, percentages, decimals, or number words (`three` -> `five`, `two` -> `several`).
    - *Before:* `"Three centers enrolled 40 participants over 12 weeks."`
    - *Drifted (BAD):* `"Several centers enrolled roughly 40 participants over 12 weeks."`
    - *Preserved:* `"Across three centers, 40 participants were enrolled during a 12-week period."`
54. **Dropped hedge or added certainty:** Removing calibrated uncertainty (`may`, `suggests`, `appears`, `could`, `likely`) or upgrading it to fact (`demonstrates`, `proves`, `will`).
    - *Before:* `"These findings suggest that spaced refreshers may slow skill decay."`
    - *Drifted (BAD):* `"Spaced refreshers prevent skill decay."`
    - *Preserved:* `"Spaced refreshers may slow skill decay, according to these findings."`
55. **Association written as causation:** Turning correlation or co-occurrence into causal mechanism.
    - *Before:* `"Higher error counts were associated with prolonged console time."`
    - *Drifted (BAD):* `"Higher error counts caused prolonged console time."`
    - *Preserved:* `"Prolonged console time correlated with higher error counts."`
56. **Dropped attribution:** Stripping `"X reported"` or `"Critics allege"` so an attributed claim reads as consensus fact.
    - *Before:* `"Smith et al. reported lower knot-tying errors in the PBP group [4]."`
    - *Drifted (BAD):* `"The PBP group has lower knot-tying errors."`
    - *Preserved:* `"Lower knot-tying error rates in the PBP group were reported by Smith et al. [4]."`
57. **Tense shift generalizing a bounded finding:** Turning a past-tense study observation into a present-tense universal rule.
    - *Before:* `"In that cohort, trainees using real-time guidance achieved higher scores."`
    - *Drifted (BAD):* `"Real-time guidance achieves higher scores."`
    - *Preserved:* `"Trainees in that cohort scored higher when given real-time guidance."`
58. **Deleted ranking, scope, or joint-truth words:** Tightening away load-bearing modifiers such as `single most`, `only`, `solely`, `all`, `every`, `simultaneously`, `at least`, `at most`, or `unless`.
    - *Before:* `"The protocol requires both critical-error avoidance and simultaneous benchmark attainment."`
    - *Drifted (BAD):* `"The protocol requires critical-error avoidance and benchmark attainment."`
    - *Preserved:* `"Under the protocol, operators must avoid critical errors while simultaneously meeting the benchmark."`
