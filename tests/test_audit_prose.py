from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = ROOT / "templates" / "skills" / "humanize-text" / "scripts" / "audit_prose.py"
sys.path.insert(0, str(AUDIT_SCRIPT.parent))

import audit_prose  # noqa: E402


# Synthetic fixtures (faithful, hard meaning-drifting, human-written; no manuscript text)
SYNTHETIC_FAITHFUL_BEFORE = (
    "In a randomized simulation trial, 40 surgical trainees completed three suturing modules "
    "at two centers [1]. Real-time coaching was associated with fewer errors (12% vs 24%, p = 0.02), "
    "which may suggest improved retention without replacing faculty debriefing. "
    "Only candidates passing both safety checks simultaneously advanced [1].\n"
)
SYNTHETIC_FAITHFUL_AFTER = (
    "Across 2 centers in a randomized simulation trial, 40 surgical trainees finished 3 suturing modules [1]. "
    "Fewer errors (12% vs 24%, p = 0.02) were associated with real-time coaching, and the pattern may suggest "
    "stronger retention without replacing faculty debriefing. "
    "Candidates advanced only when passing both safety checks simultaneously [1].\n"
)
SYNTHETIC_HUMAN_WRITTEN = (
    "The benchtop rig leaked twice before we tightened the silicone gasket. "
    "Once the seal held, pressure stabilized at 18 mmHg across four runs. "
    "Short checks caught the drift early. Later runs stayed clean, though the tubing still needs replacement.\n"
)


class AuditProseTests(unittest.TestCase):
    def test_detects_ai_tells_leaked_tokens_and_unicode(self) -> None:
        sample = (
            "Great question! Let's dive in.\n\n"
            "This multifaceted framework serves as a testament to how teams delve into "
            "intricate workflows — ensuring seamless alignment. "
            "Studies show this proves everything [cite: 1] citeturn0search0 "
            "https://example.com/?utm_source=chatgpt.com.\n"
            "Hidden\u200bspace and c\u0430nvas homoglyph.\n"
        )
        report = audit_prose.analyze_text(sample, profile="academic")

        self.assertFalse(report["passed_strict_gate"])
        self.assertIn("delve", report["findings"]["tier_1a"])
        self.assertIn("testament", report["findings"]["tier_1a"])
        self.assertIn("multifaceted", report["findings"]["tier_1a"])
        self.assertIn("citation_laundering", report["findings"]["academic_extensions"])
        self.assertIn("openai_citation_token", report["findings"]["leaked_artifacts"])
        self.assertIn("gemini_citation_token", report["findings"]["leaked_artifacts"])
        self.assertIn("ai_utm_param", report["findings"]["leaked_artifacts"])
        self.assertIn("U+200B", report["findings"]["zero_width_unicode"])
        self.assertTrue(report["findings"]["mixed_script_homoglyphs"])

    def test_masks_code_tables_urls_and_quotes(self) -> None:
        sample = (
            "---\ntitle: Test\n---\n\n"
            "```python\n# delve into tapestry — citeturn0search0\nvar = 'delve'\n```\n\n"
            "| Column | Note |\n| --- | --- |\n| A | delve into tapestry |\n\n"
            "> We must delve into the multifaceted tapestry — quoted text.\n\n"
            "The parser reads `delve_count` from [the guide](https://example.com/delve) in 12 ms.\n"
        )
        report = audit_prose.analyze_text(sample, profile="technical-docs", ignore_quotes=True)

        self.assertTrue(report["passed_strict_gate"], report["gate_failures"])
        self.assertEqual(report["findings"]["tier_1a"], {})
        self.assertEqual(report["findings"]["em_dashes"], 0)

    def test_academic_profile_allows_single_em_dash_and_preserves_hedging(self) -> None:
        sample = (
            "Simulation scores differed by 14% between groups (95% CI 9-19%, p = 0.004). "
            "This pattern suggests improved instrument economy — though prospective transfer remains untested (Smith et al., 2024). "
            "Samples were scored by two blinded raters.\n"
        )
        academic_report = audit_prose.analyze_text(sample, profile="academic")
        general_report = audit_prose.analyze_text(sample, profile="general")

        self.assertTrue(academic_report["passed_strict_gate"], academic_report["gate_failures"])
        self.assertFalse(general_report["passed_strict_gate"])

    def test_compare_fact_preservation_passes_and_catches_drift(self) -> None:
        before = (
            "To the best of our knowledge, this multifaceted study proves that error rates dropped "
            "from 24.5% to 11.0% (n = 40, p < 0.01, DOI: 10.1000/test.2024, PMID: 12345678) [1, 2] (Smith et al., 2024)."
        )
        clean_after = (
            "Error rates fell from 24.5% to 11.0% across 40 participants (n = 40, p < 0.01; "
            "DOI: 10.1000/test.2024; PMID: 12345678) [1, 2] (Smith et al., 2024)."
        )
        drifted_after = (
            "Error rates fell from 24.5% to 12.0% across 40 participants (n = 40, p < 0.01; "
            "PMID: 12345678) [1] (Smith et al., 2024)."
        )

        pass_result = audit_prose.compare_fact_preservation(before, clean_after)
        self.assertTrue(pass_result["facts_preserved"], pass_result)

        fail_result = audit_prose.compare_fact_preservation(before, drifted_after)
        self.assertFalse(fail_result["facts_preserved"])
        self.assertIn("11.0%", fail_result["missing_from_after"]["numbers"])
        self.assertIn("12.0%", fail_result["added_in_after"]["numbers"])
        self.assertIn("10.1000/test.2024", fail_result["missing_from_after"]["dois"])

    def test_faithful_rewrite_and_human_sample_stay_clean(self) -> None:
        comp = audit_prose.compare_fact_preservation(SYNTHETIC_FAITHFUL_BEFORE, SYNTHETIC_FAITHFUL_AFTER)
        self.assertTrue(comp["facts_preserved"], comp)
        self.assertTrue(comp["meaning_preserved"], comp["strict_drift_failures"])
        self.assertEqual(len(comp["digests"]["before"]), 16)
        self.assertEqual(len(comp["digests"]["after"]), 16)

        human_report = audit_prose.analyze_text(SYNTHETIC_HUMAN_WRITTEN, profile="general")
        self.assertTrue(human_report["passed_strict_gate"], human_report["gate_failures"])
        self.assertGreater(human_report["rhythm"]["pct_short_sentences_lt8"], 0.0)
        self.assertIn("em_dashes_per_1k_words", human_report["rhythm"])

    def test_group_g_meaning_drift_traps_flagged(self) -> None:
        # 1. Negation flip
        neg_drift = audit_prose.compare_fact_preservation(
            "Simulator completion does not establish clinical readiness.",
            "Simulator completion establishes clinical readiness.",
        )
        self.assertFalse(neg_drift["meaning_preserved"])
        self.assertEqual(neg_drift["negations"]["delta"], -1)

        # 2. Spelled-out quantity drift (three -> five)
        qty_drift = audit_prose.compare_fact_preservation(
            "Three centers enrolled 40 participants.",
            "Five centers enrolled 40 participants.",
        )
        self.assertFalse(qty_drift["facts_preserved"])
        self.assertIn("5", qty_drift["numbers_appeared"])
        rendered = audit_prose.format_human_report(
            audit_prose.analyze_text("Five centers enrolled 40 participants."),
            qty_drift,
        )
        self.assertIn("BANNER - NUMBERS APPEARED", rendered)

        # 3. Dropped hedge + association turned into causation
        causal_drift = audit_prose.compare_fact_preservation(
            "Coaching was associated with lower errors and may suggest faster learning.",
            "Coaching causes lower errors and guarantees faster learning.",
        )
        self.assertFalse(causal_drift["meaning_preserved"])
        self.assertIn("may", causal_drift["dropped_hedges"])
        self.assertIn("causes", causal_drift["added_causation"])

        # 4. Deleted scope/ranking word
        scope_drift = audit_prose.compare_fact_preservation(
            "Only trainees passing both checks simultaneously advanced.",
            "Trainees passing both checks advanced.",
        )
        self.assertFalse(scope_drift["meaning_preserved"])
        self.assertIn("only", scope_drift["dropped_scope_words"])
        self.assertIn("simultaneously", scope_drift["dropped_scope_words"])

        # 5. Dropped attribution advisory notice
        attr_drift = audit_prose.compare_fact_preservation(
            "Smith et al. reported lower error rates in the cohort [4].",
            "The cohort has lower error rates [4].",
        )
        self.assertEqual(attr_drift["attribution_counts"], {"before": 1, "after": 0})
        self.assertTrue(any("attribution" in w for w in attr_drift["meaning_drift_warnings"]))

    def test_length_ratio_and_script_preservation_warnings(self) -> None:
        long_before = (
            "Structured simulation curricula decompose operative procedures into observable steps, "
            "explicit error definitions, and critical-error boundaries before trainees practice independently."
        )
        short_after = "Simulation curricula define steps and errors."
        len_comp = audit_prose.compare_fact_preservation(long_before, short_after)
        self.assertTrue(len_comp["length_ratio_warning"])
        self.assertLess(len_comp["length_ratio"], 0.7)

        dev_before = "यह परीक्षण प्रक्रिया की सटीकता को मापता है।"
        latin_after = "This test measures procedure accuracy."
        script_comp = audit_prose.compare_fact_preservation(dev_before, latin_after)
        self.assertFalse(script_comp["script_preserved"])
        self.assertFalse(script_comp["meaning_preserved"])

    def test_source_overlap_flags_copy_and_passes_paraphrase(self) -> None:
        source = (
            "Structured simulation training links observable performance metrics to expert benchmarks "
            "and requires trainees to avoid predefined critical errors before clinical advancement [7]."
        )
        copied = (
            "Structured simulation training links observable performance metrics to expert benchmarks "
            "before trainees advance clinically [7]."
        )
        paraphrased = (
            "Before advancing to clinical practice, learners train against expert benchmarks "
            "using measurable tasks and strict avoidance of critical errors [7]."
        )
        quoted_ok = (
            'The policy states that learners must "links observable performance metrics to expert benchmarks" '
            "prior to clinical advancement [7]."
        )
        missing_cite = (
            "Before advancing to clinical practice, learners train against expert benchmarks "
            "using measurable tasks and strict avoidance of critical errors."
        )

        copy_res = audit_prose.compare_source_overlap(source, copied)
        self.assertFalse(copy_res["passed_source_gate"])
        self.assertGreaterEqual(copy_res["longest_shared_run_words"], 8)

        para_res = audit_prose.compare_source_overlap(source, paraphrased)
        self.assertTrue(para_res["passed_source_gate"], para_res)
        self.assertLess(para_res["longest_shared_run_words"], 8)

        quote_res = audit_prose.compare_source_overlap(source, quoted_ok)
        self.assertTrue(quote_res["passed_source_gate"], quote_res)

        cite_res = audit_prose.compare_source_overlap(source, missing_cite)
        self.assertFalse(cite_res["passed_source_gate"])
        self.assertFalse(cite_res["citations_retained"])

    def test_ignore_references_masks_published_titles(self) -> None:
        manuscript = (
            "# Discussion\n\n"
            "Automated assessment tools remain task specific and require validation [1].\n\n"
            "# References\n\n"
            "1. Author A, Author B. Real-time multifaceted assessment in simulation training. J Surg Educ. 2024;10:1-8.\n"
        )
        unmasked = audit_prose.analyze_text(manuscript, profile="academic", ignore_references=False)
        masked = audit_prose.analyze_text(manuscript, profile="academic", ignore_references=True)

        self.assertFalse(unmasked["passed_strict_gate"])
        self.assertIn("multifaceted", unmasked["findings"]["tier_1a"])
        self.assertTrue(masked["passed_strict_gate"], masked["gate_failures"])
        self.assertEqual(masked["findings"]["tier_1a"], {})

    def test_score_is_editing_signal_never_strict_gate(self) -> None:
        # High Tier 2 cluster raises editing_signal, but without Tier 1A / leaks / boilerplate strict passes
        prose = (
            "This pivotal and crucial approach can bolster and enhance outcomes while aligning with goals. "
            "Moreover, teams utilize robust methods to foster and showcase progress."
        )
        report = audit_prose.analyze_text(prose, profile="general")
        self.assertGreater(report["editing_signal"], 0)
        self.assertTrue(report["passed_strict_gate"], report["gate_failures"])

    def test_cli_strict_compare_source_and_non_prose_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            before = base / "before.md"
            after = base / "after.md"
            source = base / "source.md"
            copied = base / "copied.md"
            code = base / "script.py"
            before.write_text("Accuracy reached 91.2% (n = 25) [3].\n", encoding="utf-8")
            after.write_text("Accuracy reached 91.2% across 25 cases (n = 25) [3].\n", encoding="utf-8")
            source.write_text(
                "Observational data confirm that automated metrics require external validation before certification [3].\n",
                encoding="utf-8",
            )
            copied.write_text(
                "Observational data confirm that automated metrics require external validation before certification [3].\n",
                encoding="utf-8",
            )
            code.write_text("print('ok')\n", encoding="utf-8")

            ok_run = subprocess.run(
                [sys.executable, str(AUDIT_SCRIPT), str(after), "--profile", "academic", "--compare", str(before), "--strict"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(ok_run.returncode, 0, ok_run.stdout + ok_run.stderr)

            copy_run = subprocess.run(
                [sys.executable, str(AUDIT_SCRIPT), str(copied), "--profile", "academic", "--source", str(source), "--strict"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(copy_run.returncode, 1, copy_run.stdout + copy_run.stderr)

            refused_run = subprocess.run(
                [sys.executable, str(AUDIT_SCRIPT), str(code)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(refused_run.returncode, 2)


if __name__ == "__main__":
    unittest.main()
