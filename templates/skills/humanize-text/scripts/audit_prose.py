#!/usr/bin/env python3
"""Zero-dependency stdlib prose auditor, paraphrase overlap checker, and meaning-preservation gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

NON_PROSE_EXTENSIONS = {
    ".py",
    ".ps1",
    ".sh",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".json",
    ".jsonl",
    ".toml",
    ".yaml",
    ".yml",
    ".csv",
    ".tsv",
    ".lock",
    ".sql",
    ".css",
    ".html",
    ".xml",
}

PROFILES = (
    "general",
    "academic",
    "clinical-protocol",
    "grant-proposal",
    "technical-docs",
    "commit",
)

TIER_1A_PATTERNS = {
    "delve": re.compile(r"\bdelv(?:e|es|ed|ing)\b", re.I),
    "tapestry": re.compile(r"\btapestr(?:y|ies)\b", re.I),
    "testament": re.compile(r"\btestament\b", re.I),
    "multifaceted": re.compile(r"\bmultifaceted\b", re.I),
    "realm": re.compile(r"\brealms?\b", re.I),
    "interplay": re.compile(r"\binterplay\b", re.I),
    "in today's landscape": re.compile(r"\bin today['’]s\b[^.\n]{0,40}\blandscape\b", re.I),
}

TIER_1B_PATTERNS = {
    "underscore": re.compile(r"\bunderscor(?:e|es|ed|ing)\b", re.I),
    "leverage": re.compile(r"\bleverag(?:e|es|ed|ing)\b", re.I),
    "it's worth noting": re.compile(r"\bit(?:'s| is) worth noting\b", re.I),
    "it's important to note": re.compile(r"\bit(?:'s| is) important to note\b", re.I),
}

TIER_2_PATTERNS = {
    "crucial": re.compile(r"\bcrucial(?:ly)?\b", re.I),
    "pivotal": re.compile(r"\bpivotal\b", re.I),
    "vibrant": re.compile(r"\bvibrant\b", re.I),
    "robust": re.compile(r"\brobust(?:ness)?\b", re.I),
    "seamless": re.compile(r"\bseamless(?:ly)?\b", re.I),
    "foster": re.compile(r"\bfoster(?:s|ed|ing)?\b", re.I),
    "enhance": re.compile(r"\benhanc(?:e|es|ed|ing)\b", re.I),
    "showcase": re.compile(r"\bshowcas(?:e|es|ed|ing)\b", re.I),
    "notably": re.compile(r"\bnotably\b", re.I),
    "moreover": re.compile(r"\bmoreover\b", re.I),
    "furthermore": re.compile(r"\bfurthermore\b", re.I),
    "garner": re.compile(r"\bgarner(?:s|ed|ing)?\b", re.I),
    "bolster": re.compile(r"\bbolster(?:s|ed|ing)?\b", re.I),
    "align with": re.compile(r"\balign(?:s|ed|ing)? with\b", re.I),
    "utilize": re.compile(r"\butiliz(?:e|es|ed|ing)\b", re.I),
}

STAGING_AND_BOILERPLATE_PATTERNS = {
    "not_only_but_also": re.compile(r"\bnot (?:just|only|merely)\b[^.!?\n]{1,100}\bbut\b", re.I),
    "copula_serves_as": re.compile(r"\b(?:serves|stands|functions|operates) as\b", re.I),
    "superficial_ing": re.compile(
        r",\s+(?:highlighting|underscoring|emphasizing|ensuring|symbolizing|fostering|showcasing)\b",
        re.I,
    ),
    "staged_opener": re.compile(r"\b(?:let['’]s dive in|here['’]s what you need to know|without further ado)\b", re.I),
    "chatbot_residue": re.compile(
        r"\b(?:i hope this helps|great question!|you['’]re absolutely right|let me know if you['’]d like)\b",
        re.I,
    ),
    "cutoff_disclaimer": re.compile(
        r"\b(?:as of my last training|up to my last knowledge|while specific details are limited)\b",
        re.I,
    ),
    "generic_conclusion": re.compile(
        r"\b(?:the future looks bright|exciting times lie ahead|a step in the right direction)\b",
        re.I,
    ),
}

ACADEMIC_PATTERNS = {
    "citation_laundering": re.compile(
        r"\b(?:studies show|research suggests|the literature reports|experts argue|it is widely believed)\b",
        re.I,
    ),
    "manuscript_boilerplate": re.compile(
        r"\b(?:to the best of our knowledge|fills a critical gap|of paramount importance|paves the way for|bridges the gap|sheds light on)\b",
        re.I,
    ),
    "methodology_pseudo_precision": re.compile(
        r"\b(?:careful evaluation|rigorous analysis|comprehensive study|thorough examination|meticulous review|exhaustive review)\b",
        re.I,
    ),
    "overclaiming_verb": re.compile(r"\b(?:proves|guarantees)\b", re.I),
}

LEAKED_ARTIFACT_PATTERNS = {
    "openai_citation_token": re.compile(r"(?:citeturn\d+\w*|oai_citation|oaicite:\d+)", re.I),
    "gemini_citation_token": re.compile(r"\[cite:\s*\d+\]|\[span_\d+\]\(start_span\)", re.I),
    "grok_or_perplexity_token": re.compile(r"\b(?:grok_card|grok_render_citation_card_json|ppl-ai-file-upload)\b", re.I),
    "ai_utm_param": re.compile(r"(?:utm_source=(?:chatgpt\.com|openai|copilot\.com)|referrer=grok\.com)", re.I),
}

ZERO_WIDTH_CHARS = {
    "\u200b": "U+200B",
    "\u200c": "U+200C",
    "\u200d": "U+200D",
    "\ufeff": "U+FEFF",
    "\u00ad": "U+00AD",
    "\u2060": "U+2060",
}

CYRILLIC_GREEK_HOMOGLYPHS = set("АВЕЗКМНОРСТХаеорсухіАΒΕΖΗΙΚΜΝΟΡΤΧαεορι")

YAML_FRONTMATTER_RE = re.compile(r"\A---\s*\r?\n.*?\r?\n---\s*(?:\r?\n|\Z)", re.S)
FENCED_CODE_RE = re.compile(r"(^|\n)(```+|~~~+)[^\n]*\n.*?\n\2[ \t]*(?=\n|\Z)", re.S)
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
URL_RE = re.compile(r"https?://[^\s)>\]]+")
MD_LINK_TARGET_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
BOLD_COLON_LIST_RE = re.compile(r"^\s*(?:[-*]|\d+\.)\s+\*\*[^*\n]{2,60}:\*\*", re.M)
EM_DASH_RE = re.compile(r"—| -- ")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")
CONNECTIVE_OPENER_RE = re.compile(r"^(?:Moreover|Furthermore|Additionally|Consequently|Notably|Importantly)\b[, ]")
REFERENCES_HEADING_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:References|Bibliography|Works Cited)\s*$",
    re.I,
)
TOP_HEADING_RE = re.compile(r"^\s*#{1,2}\s+\S")
DOUBLE_QUOTED_SPAN_RE = re.compile(r'"[^"\n]{2,}"|“[^”\n]{2,}”')

# Factual token extractors for --compare and --source checks
DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b")
PMID_RE = re.compile(r"\b(?:PMID|PMCID)\s*:?\s*(?:PMC)?\d+\b", re.I)
BRACKET_CITE_RE = re.compile(r"\[(?:\d+(?:\s*[-–,]\s*\d+)*)\]")
AUTHOR_YEAR_CITE_RE = re.compile(
    r"\b[A-Z][A-Za-z'’-]+(?:\s+et\s+al\.?)?\s*\(\s*(?:19|20)\d{2}[a-z]?\s*\)"
    r"|\([A-Z][A-Za-z'’-]+(?:\s+et\s+al\.?)?,?\s+(?:19|20)\d{2}[a-z]?\)"
)
NUMBER_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9_/.-])\d+(?:,\d{3})*(?:\.\d+)?%?(?![A-Za-z0-9_/.-])")

SPELLED_UNITS = {
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}
SPELLED_TENS = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}
SPELLED_SCALES = {
    "hundred": 100,
    "thousand": 1000,
    "million": 1000000,
}
_COMPOUND_NUMBER_WORD_RE = re.compile(
    r"\b(?:"
    + "|".join(sorted(SPELLED_TENS))
    + r")[-\s]+(?:"
    + "|".join(k for k, v in SPELLED_UNITS.items() if v < 10)
    + r")\b",
    re.I,
)
_SINGLE_NUMBER_WORD_RE = re.compile(
    r"\b(?:" + "|".join(sorted({**SPELLED_UNITS, **SPELLED_TENS, **SPELLED_SCALES})) + r")\b",
    re.I,
)

NEGATION_RE = re.compile(
    r"\b(?:not|no|never|without|neither|nor|cannot|can['’]t|won['’]t|don['’]t|doesn['’]t|"
    r"didn['’]t|isn['’]t|aren['’]t|wasn['’]t|weren['’]t|haven['’]t|hasn['’]t|hadn['’]t|"
    r"shouldn['’]t|wouldn['’]t|couldn['’]t|unable to|fails? to|failed to|lacks?|lacked)\b",
    re.I,
)

HEDGE_WORDS = {
    "may",
    "might",
    "could",
    "suggest",
    "suggests",
    "suggested",
    "suggesting",
    "appear",
    "appears",
    "appeared",
    "seem",
    "seems",
    "seemed",
    "indicate",
    "indicates",
    "indicated",
    "likely",
    "unlikely",
    "possible",
    "possibly",
    "potential",
    "potentially",
    "probably",
    "unclear",
    "uncertain",
}

SCOPE_RANK_WORDS = {
    "only",
    "solely",
    "merely",
    "single most",
    "most",
    "all",
    "every",
    "each",
    "always",
    "simultaneously",
    "at least",
    "at most",
    "unless",
    "exclusively",
}

CAUSATION_WORDS = {
    "causes",
    "caused",
    "causing",
    "drives",
    "drove",
    "induces",
    "induced",
    "produces",
    "produced",
    "proves",
    "proved",
    "proven",
    "guarantees",
    "guaranteed",
    "prevents",
    "prevented",
}

ASSOCIATION_PHRASES = {
    "associated with",
    "correlated with",
    "correlates with",
    "linked to",
    "related to",
}

ATTRIBUTION_VERBS = {
    "reported",
    "reports",
    "allege",
    "alleges",
    "alleged",
    "claimed",
    "claims",
    "found",
    "observed",
    "described",
    "describe",
    "noted",
    "notes",
}

ALL_CLAIM_HEDGE_TERMS = sorted(
    HEDGE_WORDS | SCOPE_RANK_WORDS | CAUSATION_WORDS | ASSOCIATION_PHRASES | ATTRIBUTION_VERBS,
    key=len,
    reverse=True,
)
CLAIM_HEDGE_RE = re.compile(r"\b(?:" + "|".join(re.escape(term) for term in ALL_CLAIM_HEDGE_TERMS) + r")\b", re.I)


def short_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def strip_references_section(text: str) -> str:
    """Drop trailing numbered References/Bibliography section until next top-level heading or EOF."""
    lines = text.splitlines()
    out: list[str] = []
    in_refs = False
    for line in lines:
        if not in_refs and REFERENCES_HEADING_RE.match(line):
            in_refs = True
            continue
        if in_refs:
            if TOP_HEADING_RE.match(line) and not REFERENCES_HEADING_RE.match(line):
                in_refs = False
                out.append(line)
            continue
        out.append(line)
    return "\n".join(out)


def mask_code_and_frontmatter(raw_text: str) -> str:
    """Mask YAML frontmatter, fenced code, and inline code while preserving URLs for UTM leak checks."""
    masked = YAML_FRONTMATTER_RE.sub("\n", raw_text)
    masked = FENCED_CODE_RE.sub("\n", masked)
    return INLINE_CODE_RE.sub(" code_span ", masked)


def mask_prose(text: str, *, ignore_quotes: bool = False, ignore_references: bool = False) -> str:
    """Mask YAML frontmatter, code blocks, inline code, tables, URLs, and optional quotes/references."""
    masked = mask_code_and_frontmatter(text)
    if ignore_references:
        masked = strip_references_section(masked)
    masked = MD_LINK_TARGET_RE.sub(lambda m: m.group(1), masked)
    masked = URL_RE.sub(" url_ref ", masked)

    lines: list[str] = []
    for line in masked.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("|") and "|" in stripped[1:]:
            continue
        if ignore_quotes and stripped.startswith(">"):
            continue
        if line.startswith("    ") or line.startswith("\t"):
            continue
        lines.append(line)
    return "\n".join(lines)


def count_patterns(text: str, patterns: dict[str, re.Pattern[str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for label, pattern in patterns.items():
        hits = len(pattern.findall(text))
        if hits:
            counts[label] = hits
    return counts


def detect_mixed_script_homoglyphs(text: str) -> list[str]:
    flagged: list[str] = []
    for token in re.findall(r"\b\w+\b", text):
        has_latin = any("a" <= ch.lower() <= "z" for ch in token)
        has_homoglyph = any(ch in CYRILLIC_GREEK_HOMOGLYPHS for ch in token)
        if has_latin and has_homoglyph:
            flagged.append(token)
    return flagged[:10]


def detect_scripts(text: str, *, min_chars: int = 3) -> set[str]:
    """Identify primary Unicode script blocks appearing with >= min_chars characters."""
    counts: Counter[str] = Counter()
    for ch in text:
        code = ord(ch)
        if ("A" <= ch <= "Z") or ("a" <= ch <= "z"):
            counts["Latin"] += 1
        elif 0x0400 <= code <= 0x04FF:
            counts["Cyrillic"] += 1
        elif 0x0370 <= code <= 0x03FF:
            counts["Greek"] += 1
        elif 0x0900 <= code <= 0x097F:
            counts["Devanagari"] += 1
        elif 0x0600 <= code <= 0x06FF:
            counts["Arabic"] += 1
        elif 0x0590 <= code <= 0x05FF:
            counts["Hebrew"] += 1
        elif 0x0E00 <= code <= 0x0E7F:
            counts["Thai"] += 1
        elif 0xAC00 <= code <= 0xD7AF:
            counts["Hangul"] += 1
        elif (0x4E00 <= code <= 0x9FFF) or (0x3040 <= code <= 0x30FF):
            counts["CJK"] += 1
    return {script for script, count in counts.items() if count >= min_chars}


def sentence_metrics(text: str, *, em_dashes: int = 0) -> dict[str, Any]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    lengths: list[int] = []
    connective_streaks = 0
    connective_openers = 0
    uniform_streaks = 0

    for para in paragraphs:
        if para.startswith("#"):
            continue
        flat = re.sub(r"\s+", " ", para)
        sentences = [s.strip() for s in SENTENCE_SPLIT_RE.split(flat) if len(s.strip().split()) >= 2]
        para_lengths = [len(s.split()) for s in sentences]
        lengths.extend(para_lengths)

        run = 0
        for sent in sentences:
            if CONNECTIVE_OPENER_RE.match(sent):
                connective_openers += 1
                run += 1
                if run >= 2:
                    connective_streaks += 1
            else:
                run = 0

        if len(para_lengths) >= 3:
            for idx in range(len(para_lengths) - 2):
                window = para_lengths[idx : idx + 3]
                if all(12 <= n <= 26 for n in window) and (max(window) - min(window) <= 4):
                    uniform_streaks += 1

    word_count = len(text.split())
    em_dashes_per_1k = round(em_dashes * 1000.0 / word_count, 2) if word_count > 0 else 0.0

    if not lengths:
        return {
            "sentence_count": 0,
            "word_count": word_count,
            "mean_sentence_words": 0.0,
            "stdev_sentence_words": 0.0,
            "burstiness_cov": 0.0,
            "pct_short_sentences_lt8": 0.0,
            "pct_long_sentences_gt25": 0.0,
            "em_dashes_per_1k_words": em_dashes_per_1k,
            "repeated_connective_openers": connective_openers,
            "uniform_streaks": 0,
            "connective_streaks": 0,
        }

    mean = sum(lengths) / len(lengths)
    variance = sum((n - mean) ** 2 for n in lengths) / len(lengths)
    stdev = math.sqrt(variance)
    cov = round(stdev / mean, 3) if mean > 0 else 0.0
    short_pct = round(sum(1 for n in lengths if n < 8) * 100.0 / len(lengths), 1)
    long_pct = round(sum(1 for n in lengths if n > 25) * 100.0 / len(lengths), 1)
    return {
        "sentence_count": len(lengths),
        "word_count": word_count,
        "mean_sentence_words": round(mean, 1),
        "stdev_sentence_words": round(stdev, 1),
        "burstiness_cov": cov,
        "pct_short_sentences_lt8": short_pct,
        "pct_long_sentences_gt25": long_pct,
        "em_dashes_per_1k_words": em_dashes_per_1k,
        "repeated_connective_openers": connective_openers,
        "uniform_streaks": uniform_streaks,
        "connective_streaks": connective_streaks,
    }


def analyze_text(
    raw_text: str,
    *,
    profile: str = "general",
    ignore_quotes: bool = False,
    ignore_references: bool = False,
) -> dict[str, Any]:
    if profile not in PROFILES:
        raise ValueError(f"Unsupported profile: {profile}")

    code_masked = mask_code_and_frontmatter(raw_text)
    if ignore_references:
        code_masked_for_leaks = strip_references_section(code_masked)
    else:
        code_masked_for_leaks = code_masked
    leaks = count_patterns(code_masked_for_leaks, LEAKED_ARTIFACT_PATTERNS)
    masked = mask_prose(raw_text, ignore_quotes=ignore_quotes, ignore_references=ignore_references)
    zero_width = {label: masked.count(ch) for ch, label in ZERO_WIDTH_CHARS.items() if masked.count(ch) > 0}
    homoglyphs = detect_mixed_script_homoglyphs(masked)

    tier_1a = count_patterns(masked, TIER_1A_PATTERNS)
    tier_1b = count_patterns(masked, TIER_1B_PATTERNS)
    tier_2 = count_patterns(masked, TIER_2_PATTERNS)
    staging = count_patterns(masked, STAGING_AND_BOILERPLATE_PATTERNS)
    academic = count_patterns(masked, ACADEMIC_PATTERNS) if profile in {"academic", "clinical-protocol", "grant-proposal"} else {}

    em_dashes = len(EM_DASH_RE.findall(masked))
    bold_colon_lists = len(BOLD_COLON_LIST_RE.findall(masked))
    rhythm = sentence_metrics(masked, em_dashes=em_dashes)

    # Hard strict gate failures ONLY (never gate on the advisory editing-signal score)
    gate_failures: list[str] = []
    if leaks:
        gate_failures.append(f"leaked AI tokens: {', '.join(sorted(leaks))}")
    if zero_width or homoglyphs:
        gate_failures.append("zero-width or mixed-script homoglyph Unicode detected")
    if tier_1a:
        gate_failures.append(f"Tier 1A AI vocabulary: {', '.join(sorted(tier_1a))}")
    if staging.get("chatbot_residue") or staging.get("cutoff_disclaimer"):
        gate_failures.append("chatbot residue or knowledge-cutoff disclaimer detected")
    if profile in {"general", "technical-docs", "commit", "clinical-protocol"} and em_dashes > 0:
        gate_failures.append(f"em-dash policy violation ({em_dashes} em-dash/spaced-dash hit(s))")
    elif profile in {"academic", "grant-proposal"} and em_dashes > max(2, rhythm["sentence_count"] // 6):
        gate_failures.append(f"excessive em-dashes for {profile} ({em_dashes})")
    if profile in {"academic", "clinical-protocol"} and academic.get("citation_laundering"):
        gate_failures.append("citation laundering detected ('studies show'/vague authority without citation)")
    if profile == "academic" and academic.get("manuscript_boilerplate"):
        gate_failures.append("manuscript boilerplate detected")

    # Advisory editing-signal score (0 = clean, 100 = heavy AI-style tells; never a strict gate)
    tier2_total = sum(tier_2.values())
    tier2_penalty = 0 if tier2_total <= 1 else (tier2_total - 1) * 4
    cov_penalty = 15 if (rhythm["word_count"] >= 40 and rhythm["burstiness_cov"] < 0.25) else 0
    editing_signal = min(
        100,
        sum(tier_1a.values()) * 14
        + sum(tier_1b.values()) * 6
        + tier2_penalty
        + sum(staging.values()) * 10
        + sum(academic.values()) * 10
        + sum(leaks.values()) * 20
        + (len(zero_width) + len(homoglyphs)) * 20
        + em_dashes * (5 if profile in {"general", "technical-docs", "commit"} else 2)
        + rhythm["uniform_streaks"] * 6
        + rhythm["connective_streaks"] * 6
        + bold_colon_lists * 2
        + cov_penalty,
    )

    return {
        "profile": profile,
        "ignore_references": ignore_references,
        "short_sample_warning": rhythm["word_count"] < 40,
        "rhythm": rhythm,
        "editing_signal": editing_signal,
        "heuristic_score": editing_signal,
        "findings": {
            "leaked_artifacts": leaks,
            "zero_width_unicode": zero_width,
            "mixed_script_homoglyphs": homoglyphs,
            "tier_1a": tier_1a,
            "tier_1b": tier_1b,
            "tier_2": tier_2,
            "staging_and_boilerplate": staging,
            "academic_extensions": academic,
            "em_dashes": em_dashes,
            "bold_colon_list_items": bold_colon_lists,
        },
        "gate_failures": gate_failures,
        "passed_strict_gate": len(gate_failures) == 0,
    }


def _extract_spelled_numbers(text: str) -> Counter[str]:
    counts: Counter[str] = Counter()

    def _replace_compound(match: re.Match[str]) -> str:
        parts = re.split(r"[-\s]+", match.group(0).lower())
        if len(parts) == 2 and parts[0] in SPELLED_TENS and parts[1] in SPELLED_UNITS:
            counts[str(SPELLED_TENS[parts[0]] + SPELLED_UNITS[parts[1]])] += 1
        return " "

    remainder = _COMPOUND_NUMBER_WORD_RE.sub(_replace_compound, text)
    for match in _SINGLE_NUMBER_WORD_RE.finditer(remainder):
        word = match.group(0).lower()
        val = SPELLED_UNITS.get(word) or SPELLED_TENS.get(word) or SPELLED_SCALES.get(word)
        if val is not None:
            counts[str(val)] += 1
    return counts


def extract_factual_tokens(raw_text: str) -> dict[str, Counter[str]]:
    """Extract numbers (digits + spelled-out cardinals), DOIs, PMIDs, and citations excluding code/URLs."""
    cleaned = YAML_FRONTMATTER_RE.sub("\n", raw_text)
    cleaned = FENCED_CODE_RE.sub("\n", cleaned)
    cleaned = INLINE_CODE_RE.sub(" ", cleaned)

    dois = Counter(m.lower().rstrip(".,;)") for m in DOI_RE.findall(cleaned))
    pmids = Counter(re.sub(r"\s+", "", m.upper()) for m in PMID_RE.findall(cleaned))
    bracket_cites = Counter(re.sub(r"\s+", "", m) for m in BRACKET_CITE_RE.findall(cleaned))
    author_year = Counter(re.sub(r"\s+", " ", m) for m in AUTHOR_YEAR_CITE_RE.findall(cleaned))

    without_urls_and_ids = URL_RE.sub(" ", cleaned)
    without_urls_and_ids = DOI_RE.sub(" ", without_urls_and_ids)
    without_urls_and_ids = PMID_RE.sub(" ", without_urls_and_ids)
    without_urls_and_ids = BRACKET_CITE_RE.sub(" ", without_urls_and_ids)
    numbers = Counter(m.replace(",", "") for m in NUMBER_TOKEN_RE.findall(without_urls_and_ids))
    numbers.update(_extract_spelled_numbers(without_urls_and_ids))

    return {
        "numbers": numbers,
        "dois": dois,
        "pmids": pmids,
        "bracket_citations": bracket_cites,
        "author_year_citations": author_year,
    }


def _extract_claim_hedges(text: str) -> Counter[str]:
    return Counter(m.group(0).lower() for m in CLAIM_HEDGE_RE.finditer(text))


def compare_fact_preservation(
    before_text: str,
    after_text: str,
    *,
    ignore_references: bool = False,
) -> dict[str, Any]:
    before_tokens = extract_factual_tokens(before_text)
    after_tokens = extract_factual_tokens(after_text)

    missing: dict[str, list[str]] = {}
    added: dict[str, list[str]] = {}
    for category in before_tokens:
        if category == "numbers":
            before_set = set(before_tokens[category].keys())
            after_set = set(after_tokens[category].keys())
            diff_missing = sorted(before_set - after_set)
            diff_added = sorted(after_set - before_set)
        else:
            diff_missing = sorted((before_tokens[category] - after_tokens[category]).elements())
            diff_added = sorted((after_tokens[category] - before_tokens[category]).elements())
        if diff_missing:
            missing[category] = diff_missing
        if diff_added:
            added[category] = diff_added

    before_prose = mask_prose(before_text, ignore_references=ignore_references)
    after_prose = mask_prose(after_text, ignore_references=ignore_references)

    neg_before = len(NEGATION_RE.findall(before_prose))
    neg_after = len(NEGATION_RE.findall(after_prose))
    negation_delta = neg_after - neg_before

    ch_before = _extract_claim_hedges(before_prose)
    ch_after = _extract_claim_hedges(after_prose)
    claim_hedge_diff: dict[str, dict[str, int]] = {}
    for term in sorted(set(ch_before) | set(ch_after)):
        if ch_before[term] != ch_after[term]:
            claim_hedge_diff[term] = {"before": ch_before[term], "after": ch_after[term]}

    dropped_hedges = sorted(
        term for term in HEDGE_WORDS if ch_before[term] > ch_after[term]
    )
    dropped_scope_words = sorted(
        term for term in SCOPE_RANK_WORDS if ch_before[term] > ch_after[term]
    )
    added_causation = sorted(
        term for term in CAUSATION_WORDS if ch_after[term] > ch_before[term]
    )
    dropped_association = sorted(
        term for term in ASSOCIATION_PHRASES if ch_before[term] > ch_after[term]
    )
    attr_before_total = sum(ch_before[t] for t in ATTRIBUTION_VERBS)
    attr_after_total = sum(ch_after[t] for t in ATTRIBUTION_VERBS)
    attribution_dropped = attr_before_total > 0 and attr_after_total == 0

    before_words = len(before_prose.split())
    after_words = len(after_prose.split())
    length_ratio = round(after_words / before_words, 3) if before_words > 0 else 1.0
    length_ratio_warning = before_words > 0 and (length_ratio < 0.7 or length_ratio > 1.3)

    scripts_before = sorted(detect_scripts(before_prose))
    scripts_after = sorted(detect_scripts(after_prose))
    script_preserved = scripts_before == scripts_after

    meaning_drift_warnings: list[str] = []
    strict_drift_failures: list[str] = []

    if added.get("numbers"):
        strict_drift_failures.append(f"numbers appeared in rewrite: {added['numbers']}")
    if missing.get("numbers"):
        strict_drift_failures.append(f"numbers missing from rewrite: {missing['numbers']}")
    if negation_delta != 0:
        msg = f"negation count changed ({neg_before} -> {neg_after})"
        meaning_drift_warnings.append(msg)
        strict_drift_failures.append(msg)
    if dropped_hedges:
        msg = f"hedge words decreased: {dropped_hedges}"
        meaning_drift_warnings.append(msg)
        strict_drift_failures.append(msg)
    if dropped_scope_words:
        msg = f"scope/ranking words decreased: {dropped_scope_words}"
        meaning_drift_warnings.append(msg)
        strict_drift_failures.append(msg)
    if added_causation:
        msg = f"causal verbs increased: {added_causation}"
        if dropped_association:
            msg += f" (while association phrases decreased: {dropped_association})"
        meaning_drift_warnings.append(msg)
        strict_drift_failures.append(msg)
    if attribution_dropped:
        meaning_drift_warnings.append(
            f"attribution verbs dropped ({attr_before_total} -> {attr_after_total})"
        )
    elif attr_before_total != attr_after_total:
        meaning_drift_warnings.append(
            f"attribution verb count shifted ({attr_before_total} -> {attr_after_total})"
        )
    if length_ratio_warning:
        meaning_drift_warnings.append(
            f"length ratio {length_ratio} outside [0.70, 1.30] ({before_words} -> {after_words} words)"
        )
    if not script_preserved:
        msg = f"script change detected ({scripts_before} -> {scripts_after})"
        meaning_drift_warnings.append(msg)
        strict_drift_failures.append(msg)

    return {
        "facts_preserved": not missing and not added,
        "meaning_preserved": len(strict_drift_failures) == 0 and not missing and not added,
        "missing_from_after": missing,
        "added_in_after": added,
        "numbers_appeared": added.get("numbers", []),
        "digests": {
            "before": short_sha256(before_text),
            "after": short_sha256(after_text),
        },
        "negations": {
            "before": neg_before,
            "after": neg_after,
            "delta": negation_delta,
        },
        "claim_hedge_diff": claim_hedge_diff,
        "dropped_hedges": dropped_hedges,
        "dropped_scope_words": dropped_scope_words,
        "added_causation": added_causation,
        "attribution_counts": {"before": attr_before_total, "after": attr_after_total},
        "length_ratio": length_ratio,
        "length_ratio_warning": length_ratio_warning,
        "scripts_before": scripts_before,
        "scripts_after": scripts_after,
        "script_preserved": script_preserved,
        "meaning_drift_warnings": meaning_drift_warnings,
        "strict_drift_failures": strict_drift_failures,
    }


def _non_quoted_words(text: str, *, ignore_references: bool = False) -> list[str]:
    prose = mask_prose(text, ignore_quotes=True, ignore_references=ignore_references)
    prose = DOUBLE_QUOTED_SPAN_RE.sub(" ", prose)
    return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?", prose.lower())


def _longest_shared_run(source_words: list[str], target_words: list[str]) -> tuple[int, list[str]]:
    if not source_words or not target_words:
        return 0, []
    index: dict[str, list[int]] = {}
    for pos, tok in enumerate(source_words):
        index.setdefault(tok, []).append(pos)

    best_len = 0
    best_span: list[str] = []
    n_src = len(source_words)
    n_tgt = len(target_words)
    for j, tok in enumerate(target_words):
        if tok not in index:
            continue
        for i in index[tok]:
            # Only start from the beginning of a maximal match
            if i > 0 and j > 0 and source_words[i - 1] == target_words[j - 1]:
                continue
            k = 1
            while i + k < n_src and j + k < n_tgt and source_words[i + k] == target_words[j + k]:
                k += 1
            if k > best_len:
                best_len = k
                best_span = target_words[j : j + k]
    return best_len, best_span


def compare_source_overlap(
    source_text: str,
    target_text: str,
    *,
    ignore_references: bool = False,
) -> dict[str, Any]:
    src_words = _non_quoted_words(source_text, ignore_references=ignore_references)
    tgt_words = _non_quoted_words(target_text, ignore_references=ignore_references)

    longest_run, longest_span = _longest_shared_run(src_words, tgt_words)

    src_4grams = {tuple(src_words[i : i + 4]) for i in range(max(0, len(src_words) - 3))}
    tgt_4grams = [tuple(tgt_words[i : i + 4]) for i in range(max(0, len(tgt_words) - 3))]
    shared_4grams = sum(1 for g in tgt_4grams if g in src_4grams)
    shared_4gram_ratio = round(shared_4grams / len(tgt_4grams), 3) if tgt_4grams else 0.0

    src_vocab = set(src_words)
    tgt_vocab = set(tgt_words)
    union_size = len(src_vocab | tgt_vocab)
    jaccard_overlap = round(len(src_vocab & tgt_vocab) / union_size, 3) if union_size else 0.0

    src_cites = extract_factual_tokens(source_text)
    tgt_cites = extract_factual_tokens(target_text)
    missing_citations: dict[str, list[str]] = {}
    for category in ("dois", "pmids", "bracket_citations", "author_year_citations"):
        diff = sorted((src_cites[category] - tgt_cites[category]).elements())
        if diff:
            missing_citations[category] = diff

    source_failures: list[str] = []
    if longest_run >= 8:
        source_failures.append(
            f"near-verbatim run of {longest_run} words outside quotes: \"{' '.join(longest_span[:12])}\""
        )
    if missing_citations:
        source_failures.append(f"missing source citations: {missing_citations}")

    return {
        "longest_shared_run_words": longest_run,
        "longest_shared_excerpt": " ".join(longest_span[:16]),
        "shared_4gram_ratio": shared_4gram_ratio,
        "jaccard_overlap": jaccard_overlap,
        "missing_citations": missing_citations,
        "citations_retained": len(missing_citations) == 0,
        "passed_source_gate": len(source_failures) == 0,
        "source_gate_failures": source_failures,
    }


def format_human_report(
    report: dict[str, Any],
    comparison: dict[str, Any] | None = None,
    source_overlap: dict[str, Any] | None = None,
) -> str:
    rhythm = report["rhythm"]
    lines: list[str] = []
    if comparison is not None and comparison.get("numbers_appeared"):
        lines.append(
            f"[!] BANNER - NUMBERS APPEARED IN REWRITE (possible invented data): {comparison['numbers_appeared']}"
        )
    lines.extend(
        [
            f"Profile: {report['profile']} | Editing signal: {report['editing_signal']}/100 (advisory; lower = fewer AI-style tells)",
            f"Words: {rhythm['word_count']} | Sentences: {rhythm['sentence_count']} | "
            f"Mean len: {rhythm['mean_sentence_words']} | CoV: {rhythm['burstiness_cov']} | "
            f"<8w: {rhythm['pct_short_sentences_lt8']}% | >25w: {rhythm['pct_long_sentences_gt25']}% | "
            f"Em-dashes/1k: {rhythm['em_dashes_per_1k_words']} | "
            f"Uniform streaks: {rhythm['uniform_streaks']} | Connective openers: {rhythm['repeated_connective_openers']} (streaks: {rhythm['connective_streaks']})",
        ]
    )
    if report["short_sample_warning"]:
        lines.append("Warning: sample under 40 words; burstiness and editing signal are unreliable.")
    findings = report["findings"]
    for group_name, values in findings.items():
        if values:
            lines.append(f"- {group_name}: {values}")
    if report["gate_failures"]:
        lines.append("Strict gate failures:")
        lines.extend(f"  * {item}" for item in report["gate_failures"])
    else:
        lines.append("Strict gate: PASS")
    if comparison is not None:
        lines.append(
            f"Fact/citation preservation (--compare): {'PASS' if comparison['facts_preserved'] else 'FAIL'} | "
            f"Meaning checks: {'PASS' if not comparison['strict_drift_failures'] else 'FAIL'}"
        )
        lines.append(
            f"Digests (sha256[:16]): before={comparison['digests']['before']} after={comparison['digests']['after']} | "
            f"Negations: {comparison['negations']['before']}->{comparison['negations']['after']} | "
            f"Length ratio: {comparison['length_ratio']} | Scripts: {comparison['scripts_before']}->{comparison['scripts_after']}"
        )
        if comparison["missing_from_after"]:
            lines.append(f"  * Missing factual tokens: {comparison['missing_from_after']}")
        if comparison["added_in_after"]:
            lines.append(f"  * Added/altered factual tokens: {comparison['added_in_after']}")
        if comparison["claim_hedge_diff"]:
            lines.append(f"  * Claim/hedge diff: {comparison['claim_hedge_diff']}")
        if comparison["meaning_drift_warnings"]:
            lines.append(f"  * Advisory/drift notices: {comparison['meaning_drift_warnings']}")
    if source_overlap is not None:
        lines.append(
            f"Source overlap (--source): longest_run={source_overlap['longest_shared_run_words']} words | "
            f"4-gram={source_overlap['shared_4gram_ratio']} | Jaccard={source_overlap['jaccard_overlap']} | "
            f"Citations retained: {'PASS' if source_overlap['citations_retained'] else 'FAIL'}"
        )
        if source_overlap["source_gate_failures"]:
            lines.extend(f"  * Source failure: {item}" for item in source_overlap["source_gate_failures"])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit prose for AI-style tells, paraphrase overlap, and factual/meaning drift.")
    parser.add_argument("target", type=Path, help="Path to the prose file to audit.")
    parser.add_argument("--profile", choices=PROFILES, default="general")
    parser.add_argument("--ignore-quotes", action="store_true", help="Mask Markdown blockquotes before scanning.")
    parser.add_argument(
        "--ignore-references",
        action="store_true",
        help="Mask trailing numbered References/Bibliography section from style/AI-tell scanning (factual/citation checks still inspect the full file).",
    )
    parser.add_argument("--compare", type=Path, default=None, help="Optional pre-rewrite file to check numeric/citation/meaning preservation.")
    parser.add_argument("--source", type=Path, default=None, help="Optional source file for paraphrase overlap and citation checks.")
    parser.add_argument("--strict", action="store_true", help="Exit 1 if hard strict gate failures, meaning/fact drift, or source copying occur.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args()

    target = args.target
    if not target.exists() or not target.is_file():
        print(f"ERROR: target file not found: {target}", file=sys.stderr)
        return 2
    if target.suffix.lower() in NON_PROSE_EXTENSIONS:
        print(f"Refused non-prose target ({target.suffix}): {target}", file=sys.stderr)
        return 2

    after_text = target.read_text(encoding="utf-8", errors="replace")
    report = analyze_text(
        after_text,
        profile=args.profile,
        ignore_quotes=args.ignore_quotes,
        ignore_references=args.ignore_references,
    )

    comparison: dict[str, Any] | None = None
    if args.compare is not None:
        if not args.compare.exists() or not args.compare.is_file():
            print(f"ERROR: comparison file not found: {args.compare}", file=sys.stderr)
            return 2
        before_text = args.compare.read_text(encoding="utf-8", errors="replace")
        comparison = compare_fact_preservation(
            before_text,
            after_text,
            ignore_references=args.ignore_references,
        )

    source_overlap: dict[str, Any] | None = None
    if args.source is not None:
        if not args.source.exists() or not args.source.is_file():
            print(f"ERROR: source file not found: {args.source}", file=sys.stderr)
            return 2
        source_text = args.source.read_text(encoding="utf-8", errors="replace")
        source_overlap = compare_source_overlap(
            source_text,
            after_text,
            ignore_references=args.ignore_references,
        )

    if args.json:
        payload = dict(report)
        if comparison is not None:
            payload["comparison"] = comparison
        if source_overlap is not None:
            payload["source_overlap"] = source_overlap
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(format_human_report(report, comparison, source_overlap))

    failed = False
    if comparison is not None and not comparison["facts_preserved"]:
        failed = True
    if args.strict:
        if not report["passed_strict_gate"]:
            failed = True
        if comparison is not None and not comparison["meaning_preserved"]:
            failed = True
        if source_overlap is not None and not source_overlap["passed_source_gate"]:
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
