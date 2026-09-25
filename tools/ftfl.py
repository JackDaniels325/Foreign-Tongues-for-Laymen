#!/usr/bin/env python3
"""
Foreign Tongues for Laymen - routine toolbox front end.

v0.2.6 authored-dialogue workflow:
    source alignment
    -> conservative foreign/code-switch discovery
    -> unresolved family review
    -> approved.csv
    -> numbered build
    -> static package audit

Normal use:
    python .\tools\ftfl.py scan
    python .\tools\ftfl.py build --version 0.2.6
    python .\tools\ftfl.py all --version 0.2.6

Signal/glossary files are supporting evidence only. They are not the primary
discovery gate.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import io
import re
import sys
import unicodedata
import zipfile
from collections import Counter, defaultdict
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
REPO = TOOLS_DIR.parent

ALIGNMENT = REPO / "reference" / "aligned" / "localization_alignment.csv"
SOURCE_CANDIDATES = REPO / "reference" / "aligned" / "source_discovery_candidates.csv"
UNRESOLVED = REPO / "reference" / "aligned" / "unresolved_families.csv"

STATUS_DIR = REPO / "reference" / "status"
REGRESSION_STATUS = STATUS_DIR / "regression_review.csv"
DISCOVERY_SUMMARY = STATUS_DIR / "discovery_summary.csv"
CANDIDATE_SAMPLE = STATUS_DIR / "candidate_sample.csv"
TRANSLATION_WORKLIST = STATUS_DIR / "translation_worklist.csv"

APPROVED = REPO / "corpus" / "approved.csv"
PROPER_NOUNS = REPO / "reference" / "glossaries" / "proper_nouns.txt"
GLOSSARY_DIR = REPO / "reference" / "glossaries"

TOKEN_RE = re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*", re.UNICODE)

COMMON_ENGLISH = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by",
    "best", "can", "come", "did", "do", "does", "for", "from", "get", "go", "good",
    "had", "has", "have", "he", "hello", "her", "here", "him", "his", "how",
    "i", "if", "in", "is", "it", "its", "me", "my", "no", "not", "of", "oh",
    "on", "or", "our", "out", "please", "she", "so", "some", "that", "the",
    "their", "them", "there", "they", "this", "to", "up", "us", "was", "we",
    "were", "what", "when", "where", "who", "why", "will", "with", "yes",
    "you", "your",
}

# Regression alarms only. They do not teach the detector vocabulary and they
# do not provide translations.
REGRESSION_PHRASES = (
    "Gut margn!",
    "T-aves bakhtalo, Henry! You are the best!",
    "T'aves bachtalo!",
    "Te del o Del lacho dives!",
    "Kames vareso?",
    "Masa u-matan tov!",
    "Oh Devla!",
    "So rodes?",
)


# Pass 8 is a scope cleanup rather than another threshold squeeze.
# ui_* rows are internal/menu/script helper text, not authored spoken subtitles.
NON_DIALOGUE_KEY_PREFIXES = (
    "ui_",
)

# These openings identify short English questions/statements whose only
# preserved token is usually a name or game term. They should not become
# translation work merely because that name survives every localization.
SHORT_ENGLISH_OPENINGS = (
    "who is ",
    "who's ",
    "who’s ",
    "what is ",
    "what's ",
    "what’s ",
    "where is ",
    "where's ",
    "where’s ",
    "you're ",
    "you’re ",
    "are you ",
    "is this ",
    "is that ",
)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = (
        text.replace("’", "'")
        .replace("‘", "'")
        .replace("‐", "-")
        .replace("‑", "-")
        .replace("–", "-")
        .replace("—", "-")
    )
    return " ".join(text.split()).casefold()


def normalize_token(token: str) -> str:
    return normalize(token).strip("'-")


def tokens(text: str) -> list[str]:
    return [
        token
        for token in TOKEN_RE.findall(text or "")
        if normalize_token(token)
    ]


def load_word_list(path: Path) -> set[str]:
    if not path.is_file():
        return set()

    result: set[str] = set()

    with path.open("r", encoding="utf-8-sig") as handle:
        for raw in handle:
            value = raw.split("#", 1)[0].strip()
            if value:
                result.add(normalize(value))

    return result


def load_signal_phrases() -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}

    if not GLOSSARY_DIR.is_dir():
        return result

    for path in sorted(GLOSSARY_DIR.glob("*_signals.txt")):
        language = path.stem.removesuffix("_signals")
        values = load_word_list(path)
        if values:
            result[language] = values

    return result


def load_approved() -> tuple[set[str], set[str], dict[str, dict[str, str]]]:
    if not APPROVED.is_file():
        raise SystemExit(f"Missing approved corpus: {APPROVED}")

    keys: set[str] = set()
    full_families: set[str] = set()
    rows: dict[str, dict[str, str]] = {}

    with APPROVED.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)

        if not reader.fieldnames:
            raise SystemExit("approved.csv has no header")

        for row in reader:
            key = (row.get("localization_key") or "").strip()
            display = (row.get("original_display_text") or "").strip()
            line_type = (row.get("line_type") or "").strip().lower()

            if not key:
                continue

            keys.add(key)
            rows[key] = row

            if (
                display
                and line_type
                in {"full", "full_foreign", "full-foreign", "foreign"}
            ):
                full_families.add(normalize(display))

    return keys, full_families, rows


def signal_evidence(
    display: str,
    signals: dict[str, set[str]],
) -> list[str]:
    haystack = f" {normalize(display)} "
    hits: list[str] = []

    for language, phrases in signals.items():
        for phrase in phrases:
            if not phrase:
                continue

            needle = f" {phrase} "

            if (
                needle in haystack
                or haystack.startswith(f" {phrase} ")
                or haystack.endswith(f" {phrase} ")
            ):
                hits.append(language)
                break

    return sorted(set(hits))


def looks_english_only(display: str, signal_hits: list[str]) -> bool:
    """
    Conservative English-only guard for the translation worklist.

    This does NOT remove rows from source discovery. It only keeps obvious
    English-only lines out of the high-confidence translation queue.
    """
    if signal_hits:
        return False

    norm = normalize(display)
    words = [normalize_token(t) for t in tokens(display)]
    if not words:
        return True

    english_markers = {
        "the", "and", "you", "your", "this", "that", "with", "from", "what",
        "who", "where", "when", "why", "how", "was", "were", "are", "is",
        "have", "has", "had", "will", "would", "could", "should", "not", "for",
        "to", "of", "in", "on", "at", "it", "he", "she", "they", "we", "i",
        "me", "my", "our", "their", "them", "his", "her", "just", "like",
        "don't", "didn't", "can't", "won't", "it's", "i'll", "you'll",
    }

    marker_count = sum(1 for w in words if w in english_markers)
    ascii_only = all(ord(ch) < 128 for ch in display)

    # Long ASCII lines containing several common English function words are
    # overwhelmingly ordinary English dialogue in the current audit sample.
    return ascii_only and len(words) >= 5 and marker_count >= 2


def build_translation_worklist(rows_out: list[dict[str, str]]) -> list[dict[str, str]]:
    """
    Build a compact, high-confidence family-first queue from discovery output.
    This is where translation work begins; it is not another detector pass.
    """
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)

    for row in rows_out:
        grouped[normalize(row["English_display"])].append(row)

    work: list[dict[str, str]] = []

    for family, members in grouped.items():
        members.sort(key=lambda r: r["localization_key"])
        rep = members[0]

        signal_hits = [
            x.strip()
            for x in (rep.get("signal_languages") or "").split(";")
            if x.strip()
        ]
        reasons = rep.get("discovery_reasons") or ""
        display = rep.get("English_display") or ""

        if looks_english_only(display, signal_hits):
            continue

        very_ratio = float(rep.get("very_strong_content_ratio") or 0)
        strong_ratio = float(rep.get("strong_content_ratio") or 0)
        score = int(rep.get("source_score") or 0)

        high_confidence = (
            bool(signal_hits)
            or very_ratio >= 0.75
            or strong_ratio >= 0.80
            or "dense_mixed_two_token_preservation" in reasons
        )

        if not high_confidence:
            continue

        work.append({
            "representative_key": rep["localization_key"],
            "family_size": str(len(members)),
            "source_score": str(score),
            "signal_languages": "; ".join(signal_hits),
            "strong_preserved_tokens": rep.get("strong_preserved_tokens", ""),
            "very_strong_content_ratio": rep.get("very_strong_content_ratio", ""),
            "strong_content_ratio": rep.get("strong_content_ratio", ""),
            "English_display": display,
            "English_reference": rep.get("English_reference", ""),
            "translation_status": "NEEDS_TRANSLATION",
            "source_language": "",
            "verified_meaning": "",
            "notes": "",
        })

    work.sort(
        key=lambda r: (
            -int(r["family_size"]),
            -int(r["source_score"]),
            r["English_display"].casefold(),
        )
    )
    return work


def source_discovery() -> tuple[int, dict[str, str]]:
    if not ALIGNMENT.is_file():
        raise SystemExit(
            "Missing localization_alignment.csv.\n"
            "Rebuild the extracted localization alignment first."
        )

    proper_nouns = load_word_list(PROPER_NOUNS)
    signals = load_signal_phrases()

    rows_out: list[dict[str, str]] = []
    corpus_by_normalized_display: dict[str, tuple[str, str]] = {}
    reason_counts: Counter[str] = Counter()
    excluded_counts: Counter[str] = Counter()

    with ALIGNMENT.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)

        if not reader.fieldnames:
            raise SystemExit("localization_alignment.csv has no header")

        required = {
            "localization_key",
            "English_display",
            "English_reference",
        }

        missing = required - set(reader.fieldnames)

        if missing:
            raise SystemExit(
                "localization_alignment.csv missing columns: "
                + ", ".join(sorted(missing))
            )

        other_display_fields = [
            name
            for name in reader.fieldnames
            if name.endswith("_display")
            and name != "English_display"
        ]

        if not other_display_fields:
            raise SystemExit(
                "No non-English *_display columns found in alignment"
            )

        for row in reader:
            key = (row.get("localization_key") or "").strip()
            display = (row.get("English_display") or "").strip()
            reference = (row.get("English_reference") or "").strip()

            if not key or not display:
                continue

            display_norm = normalize(display)

            corpus_by_normalized_display.setdefault(
                display_norm,
                (key, display),
            )

            if key.casefold().startswith(NON_DIALOGUE_KEY_PREFIXES):
                excluded_counts["non_dialogue_ui_key"] += 1
                continue

            display_tokens = tokens(display)

            if not display_tokens:
                continue

            normalized_display_tokens = [
                normalize_token(token)
                for token in display_tokens
            ]

            preservation: Counter[str] = Counter()
            preserving_languages: defaultdict[str, list[str]] = defaultdict(list)
            available_language_count = 0

            for field in other_display_fields:
                foreign_display = (row.get(field) or "").strip()

                if not foreign_display:
                    continue

                available_language_count += 1

                foreign_tokens = {
                    normalize_token(token)
                    for token in tokens(foreign_display)
                }

                language = field[:-8]

                for token in normalized_display_tokens:
                    if token and token in foreign_tokens:
                        preservation[token] += 1
                        preserving_languages[token].append(language)

            # Diagnostic preservation list. This is broader than admission.
            preserved: list[str] = []

            for original_token, token in zip(
                display_tokens,
                normalized_display_tokens,
            ):
                count = preservation[token]

                if not token:
                    continue

                if token in proper_nouns:
                    continue

                if len(token) <= 2 and count < 5:
                    continue

                if count >= 3:
                    preserved.append(original_token)

            preserved = list(dict.fromkeys(preserved))

            preserved_norm = [
                normalize_token(token)
                for token in preserved
            ]

            max_preservation = max(
                (
                    preservation[token]
                    for token in preserved_norm
                ),
                default=0,
            )

            direct_reference_diff = bool(
                reference
                and normalize(reference) != display_norm
            )

            signal_hits = signal_evidence(
                display,
                signals,
            )

            available = max(
                available_language_count,
                1,
            )

            # Roughly 35% / 55% agreement across the available official
            # localizations. The absolute floors keep sparse rows conservative.
            strong_threshold = max(
                4,
                (available * 35 + 99) // 100,
            )

            very_strong_threshold = max(
                6,
                (available * 55 + 99) // 100,
            )

            meaningful_preserved = [
                token
                for token in preserved_norm
                if (
                    token
                    and len(token) >= 3
                    and token not in COMMON_ENGLISH
                    and token not in proper_nouns
                )
            ]

            meaningful_preserved = list(
                dict.fromkeys(
                    meaningful_preserved
                )
            )

            strong_meaningful = [
                token
                for token in meaningful_preserved
                if preservation[token] >= strong_threshold
            ]

            very_strong_meaningful = [
                token
                for token in meaningful_preserved
                if preservation[token] >= very_strong_threshold
            ]

            # Measure how much of the meaningful subtitle content is strongly
            # preserved. This helps separate real foreign/code-switched lines
            # from ordinary English sentences that happen to share two words
            # across several official localizations.
            content_tokens = [
                token
                for token in normalized_display_tokens
                if (
                    token
                    and len(token) >= 3
                    and token not in COMMON_ENGLISH
                    and token not in proper_nouns
                )
            ]
            content_tokens = list(dict.fromkeys(content_tokens))
            very_strong_ratio = (
                len(set(very_strong_meaningful)) / len(content_tokens)
                if content_tokens
                else 0.0
            )
            strong_ratio = (
                len(set(strong_meaningful)) / len(content_tokens)
                if content_tokens
                else 0.0
            )

            # Short English questions/statements whose only distinctive
            # preserved token is a name or game term are not translation work.
            # Examples include "Who's Hanka?" or "What is chovgan?"
            short_english_single_token = (
                len(display_tokens) <= 6
                and len(very_strong_meaningful) <= 1
                and not signal_hits
                and normalize(display).startswith(SHORT_ENGLISH_OPENINGS)
            )
            if short_english_single_token:
                excluded_counts["short_english_name_or_term"] += 1
                continue

            admitted = False
            reasons: list[str] = []

            # Pass 7: compact foreign phrases still qualify when two tokens
            # are very strongly preserved and make up at least half of the
            # meaningful subtitle content.
            if (
                len(very_strong_meaningful) >= 2
                and very_strong_ratio >= 0.50
            ):
                admitted = True
                reasons.append(
                    "dense_two_very_strong_preserved_tokens"
                )

            # Mixed-language lines can legitimately contain a short foreign
            # phrase followed by ordinary English. Preserve that case when two
            # distinctive tokens are strongly preserved, at least one is very
            # strongly preserved, and the strong tokens dominate the
            # meaningful non-common-word content. This is generic and does not
            # hardcode any regression phrase.
            elif (
                len(strong_meaningful) >= 2
                and len(very_strong_meaningful) >= 1
                and strong_ratio >= 0.67
            ):
                admitted = True
                reasons.append(
                    "dense_mixed_two_token_preservation"
                )

            # A language signal can still corroborate a two-token mixed line
            # even when the subtitle also contains substantial English text.
            elif (
                len(strong_meaningful) >= 2
                and signal_hits
            ):
                admitted = True
                reasons.append(
                    "signal_supported_two_token_preservation"
                )

            # Longer source-driven foreign phrases qualify when at least three
            # distinctive tokens are strongly preserved AND they represent a
            # meaningful share of the subtitle.
            elif (
                len(strong_meaningful) >= 3
                and (
                    len(strong_meaningful) / max(len(content_tokens), 1)
                ) >= 0.50
            ):
                admitted = True
                reasons.append(
                    "dense_three_strong_preserved_tokens"
                )

            # Signal lists remain secondary evidence, but they can corroborate
            # a single strongly preserved token in mixed-language dialogue.
            elif (
                signal_hits
                and strong_meaningful
            ):
                admitted = True
                reasons.append(
                    "signal_support_plus_strong_preservation"
                )

            # English reference/display differences are retained only for a
            # very-strong token that occupies a substantial share of the
            # meaningful subtitle content. This protects genuine one-fragment
            # code-switches without reopening the broad reference-diff flood.
            elif (
                direct_reference_diff
                and very_strong_meaningful
                and very_strong_ratio >= 0.50
            ):
                admitted = True
                reasons.append(
                    "dense_reference_difference_plus_very_strong_preservation"
                )

            # Short greetings/exclamations can contain one distinctive foreign
            # token plus an interjection. Demand very strong preservation.
            elif (
                len(display_tokens) <= 4
                and very_strong_meaningful
            ):
                admitted = True
                reasons.append(
                    "short_line_very_strong_preservation"
                )

            if not admitted:
                continue

            if direct_reference_diff:
                reasons.append(
                    "english_reference_differs"
                )

            if signal_hits:
                reasons.append(
                    "signal_support"
                )

            for reason in reasons:
                reason_counts[reason] += 1

            score = (
                len(strong_meaningful) * 8
                + len(very_strong_meaningful) * 4
                + min(max_preservation, 16)
                + (5 if direct_reference_diff else 0)
                + (2 * len(signal_hits))
            )

            language_evidence: set[str] = set()

            for token in set(strong_meaningful):
                language_evidence.update(
                    preserving_languages[token]
                )

            rows_out.append({
                "localization_key": key,
                "English_display": display,
                "English_reference": reference,
                "preserved_tokens": "; ".join(preserved),
                "strong_preserved_tokens": "; ".join(strong_meaningful),
                "preserved_in_languages": "; ".join(
                    sorted(language_evidence)
                ),
                "available_languages": str(
                    available_language_count
                ),
                "strong_threshold": str(
                    strong_threshold
                ),
                "very_strong_threshold": str(
                    very_strong_threshold
                ),
                "very_strong_content_ratio": f"{very_strong_ratio:.3f}",
                "strong_content_ratio": f"{strong_ratio:.3f}",
                "max_language_preservation": str(
                    max_preservation
                ),
                "source_score": str(score),
                "direct_reference_diff": (
                    "yes"
                    if direct_reference_diff
                    else "no"
                ),
                "signal_languages": "; ".join(
                    signal_hits
                ),
                "discovery_reasons": "; ".join(
                    reasons
                ),
            })

    rows_out.sort(
        key=lambda row: (
            -int(row["source_score"]),
            row["English_display"].casefold(),
            row["localization_key"],
        )
    )

    SOURCE_CANDIDATES.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    candidate_fields = [
        "localization_key",
        "English_display",
        "English_reference",
        "preserved_tokens",
        "strong_preserved_tokens",
        "preserved_in_languages",
        "available_languages",
        "strong_threshold",
        "very_strong_threshold",
        "very_strong_content_ratio",
        "strong_content_ratio",
        "max_language_preservation",
        "source_score",
        "direct_reference_diff",
        "signal_languages",
        "discovery_reasons",
    ]

    with SOURCE_CANDIDATES.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=candidate_fields,
        )
        writer.writeheader()
        writer.writerows(rows_out)

    # Compact deterministic audit sample for GitHub review.
    # No randomization: repeated scans produce the same sample for the same
    # candidate set, making it easy to compare filter revisions.
    sample_rows: list[dict[str, str]] = []
    sample_size = min(50, len(rows_out))

    if rows_out:
        top = rows_out[:sample_size]
        bottom = rows_out[-sample_size:] if len(rows_out) > sample_size else []

        middle: list[dict[str, str]] = []
        if len(rows_out) > sample_size * 2:
            mid_start = max(0, (len(rows_out) // 2) - (sample_size // 2))
            middle = rows_out[mid_start:mid_start + sample_size]

        seen_keys: set[str] = set()

        def add_sample(bucket: str, rows: list[dict[str, str]]) -> None:
            for row in rows:
                key = row["localization_key"]
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                sample_rows.append({
                    "sample_bucket": bucket,
                    "localization_key": key,
                    "source_score": row.get("source_score", ""),
                    "discovery_reasons": row.get("discovery_reasons", ""),
                    "signal_languages": row.get("signal_languages", ""),
                    "strong_preserved_tokens": row.get("strong_preserved_tokens", ""),
                    "very_strong_content_ratio": row.get("very_strong_content_ratio", ""),
                    "strong_content_ratio": row.get("strong_content_ratio", ""),
                    "English_display": row.get("English_display", ""),
                    "English_reference": row.get("English_reference", ""),
                })

        add_sample("TOP", top)
        add_sample("MIDDLE", middle)
        add_sample("BOTTOM", bottom)

    STATUS_DIR.mkdir(parents=True, exist_ok=True)

    with CANDIDATE_SAMPLE.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        sample_fields = [
            "sample_bucket",
            "localization_key",
            "source_score",
            "discovery_reasons",
            "signal_languages",
            "strong_preserved_tokens",
            "very_strong_content_ratio",
            "strong_content_ratio",
            "English_display",
            "English_reference",
        ]
        writer = csv.DictWriter(handle, fieldnames=sample_fields)
        writer.writeheader()
        writer.writerows(sample_rows)

    worklist_rows = build_translation_worklist(rows_out)

    with TRANSLATION_WORKLIST.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        worklist_fields = [
            "representative_key",
            "family_size",
            "source_score",
            "signal_languages",
            "strong_preserved_tokens",
            "very_strong_content_ratio",
            "strong_content_ratio",
            "English_display",
            "English_reference",
            "translation_status",
            "source_language",
            "verified_meaning",
            "notes",
        ]
        writer = csv.DictWriter(handle, fieldnames=worklist_fields)
        writer.writeheader()
        writer.writerows(worklist_rows)

    candidate_displays = {
        normalize(row["English_display"])
        for row in rows_out
    }

    regression_status: dict[str, str] = {}
    regression_rows: list[dict[str, str]] = []
    failures: list[str] = []

    for phrase in REGRESSION_PHRASES:
        needle = normalize(phrase)

        exact = corpus_by_normalized_display.get(
            needle
        )

        contained = [
            (display_norm, value)
            for display_norm, value
            in corpus_by_normalized_display.items()
            if needle and needle in display_norm
        ]

        match = (
            exact
            or (
                contained[0][1]
                if contained
                else None
            )
        )

        exists = match is not None

        surfaced = any(
            needle in candidate
            for candidate in candidate_displays
        )

        if not exists:
            status = "NOT_FOUND_IN_ALIGNMENT"

        elif surfaced:
            status = "SURFACED"

        else:
            status = "MISSED_BY_SOURCE_DISCOVERY"
            failures.append(phrase)

        regression_status[phrase] = status

        regression_rows.append({
            "phrase": phrase,
            "status": status,
            "localization_key": (
                match[0]
                if match
                else ""
            ),
            "matched_display": (
                match[1]
                if match
                else ""
            ),
        })

    STATUS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with REGRESSION_STATUS.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "phrase",
                "status",
                "localization_key",
                "matched_display",
            ],
        )
        writer.writeheader()
        writer.writerows(
            regression_rows
        )

    with DISCOVERY_SUMMARY.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "metric",
            "value",
        ])
        writer.writerow([
            "candidate_rows",
            len(rows_out),
        ])
        writer.writerow([
            "regression_phrases",
            len(REGRESSION_PHRASES),
        ])
        writer.writerow([
            "regression_failures",
            len(failures),
        ])
        writer.writerow([
            "translation_worklist_families",
            len(worklist_rows),
        ])

        for reason, count in sorted(
            reason_counts.items()
        ):
            writer.writerow([
                f"reason:{reason}",
                count,
            ])

        for reason, count in sorted(
            excluded_counts.items()
        ):
            writer.writerow([
                f"excluded:{reason}",
                count,
            ])

    print()
    print("=" * 72)
    print("FTFL SOURCE DISCOVERY + TRANSLATION WORKLIST")
    print("=" * 72)
    print(f"Candidates: {len(rows_out):,}")
    print(
        f"Output: "
        f"{SOURCE_CANDIDATES.relative_to(REPO)}"
    )
    print(
        f"Status: "
        f"{REGRESSION_STATUS.relative_to(REPO)}"
    )
    print(
        f"Summary: "
        f"{DISCOVERY_SUMMARY.relative_to(REPO)}"
    )
    print(
        f"Audit sample: "
        f"{CANDIDATE_SAMPLE.relative_to(REPO)} "
        f"({len(sample_rows):,} rows)"
    )
    print(
        f"Translation worklist: "
        f"{TRANSLATION_WORKLIST.relative_to(REPO)} "
        f"({len(worklist_rows):,} families)"
    )

    print()
    print("Admission reasons:")

    for reason, count in reason_counts.most_common():
        print(
            f"  {reason:48} "
            f"{count:>7,}"
        )

    print()
    print("Scope exclusions:")
    for reason, count in excluded_counts.most_common():
        print(
            f"  {reason:48} "
            f"{count:>7,}"
        )

    print()
    print("Regression discovery gate:")

    for phrase, status in regression_status.items():
        print(
            f"  {status:28} "
            f"{phrase}"
        )

    if failures:
        raise SystemExit(
            "\nSOURCE DISCOVERY REGRESSION: known authored-dialogue phrases "
            "exist in the alignment but were not surfaced.\n"
            "Do not build or play-test. Tighten the filter without losing "
            "known coverage.\n  - "
            + "\n  - ".join(failures)
        )

    return len(rows_out), regression_status


def write_unresolved_report() -> int:
    approved_keys, approved_full_families, _ = load_approved()

    if not SOURCE_CANDIDATES.is_file():
        raise SystemExit(
            "Run source discovery before building unresolved report"
        )

    grouped: dict[
        str,
        list[dict[str, str]],
    ] = defaultdict(list)

    with SOURCE_CANDIDATES.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)

        for row in reader:
            key = (
                row.get("localization_key")
                or ""
            ).strip()

            display = (
                row.get("English_display")
                or ""
            ).strip()

            if not key or not display:
                continue

            family = normalize(display)

            if key in approved_keys:
                continue

            if family in approved_full_families:
                continue

            grouped[family].append(row)

    output_rows: list[dict[str, str]] = []

    for family, members in grouped.items():
        members.sort(
            key=lambda row: row[
                "localization_key"
            ]
        )

        representative = members[0]

        max_score = max(
            int(
                member.get(
                    "source_score"
                )
                or 0
            )
            for member in members
        )

        tokens_seen: list[str] = []
        language_seen: set[str] = set()
        reasons_seen: set[str] = set()
        signal_seen: set[str] = set()

        for member in members:
            for token in (
                member.get(
                    "strong_preserved_tokens"
                )
                or ""
            ).split(";"):
                token = token.strip()

                if (
                    token
                    and token not in tokens_seen
                ):
                    tokens_seen.append(token)

            for language in (
                member.get(
                    "preserved_in_languages"
                )
                or ""
            ).split(";"):
                language = language.strip()

                if language:
                    language_seen.add(language)

            for reason in (
                member.get(
                    "discovery_reasons"
                )
                or ""
            ).split(";"):
                reason = reason.strip()

                if reason:
                    reasons_seen.add(reason)

            for language in (
                member.get(
                    "signal_languages"
                )
                or ""
            ).split(";"):
                language = language.strip()

                if language:
                    signal_seen.add(language)

        output_rows.append({
            "representative_key": representative[
                "localization_key"
            ],
            "family_size": str(
                len(members)
            ),
            "source_score": str(
                max_score
            ),
            "strong_preserved_tokens": "; ".join(
                tokens_seen
            ),
            "preserved_in_languages": "; ".join(
                sorted(language_seen)
            ),
            "signal_languages": "; ".join(
                sorted(signal_seen)
            ),
            "discovery_reasons": "; ".join(
                sorted(reasons_seen)
            ),
            "English_display": representative[
                "English_display"
            ],
            "English_reference": (
                representative.get(
                    "English_reference"
                )
                or ""
            ),
            "review_status": "NEEDS_REVIEW",
            "source_language": "",
            "verified_meaning": "",
            "notes": "",
        })

    output_rows.sort(
        key=lambda row: (
            -int(row["family_size"]),
            -int(row["source_score"]),
            row["English_display"].casefold(),
        )
    )

    fields = [
        "representative_key",
        "family_size",
        "source_score",
        "strong_preserved_tokens",
        "preserved_in_languages",
        "signal_languages",
        "discovery_reasons",
        "English_display",
        "English_reference",
        "review_status",
        "source_language",
        "verified_meaning",
        "notes",
    ]

    UNRESOLVED.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with UNRESOLVED.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
        )
        writer.writeheader()
        writer.writerows(
            output_rows
        )

    print()
    print("=" * 72)
    print("FTFL UNRESOLVED FAMILY REPORT")
    print("=" * 72)
    print(
        f"Approved explicit keys: "
        f"{len(approved_keys):,}"
    )
    print(
        f"Approved full families: "
        f"{len(approved_full_families):,}"
    )
    print(
        f"New unresolved families: "
        f"{len(output_rows):,}"
    )
    print(
        f"Output: "
        f"{UNRESOLVED.relative_to(REPO)}"
    )

    return len(output_rows)


def run_scan() -> int:
    source_discovery()
    return write_unresolved_report()


def run_build(
    version: str,
    allow_source_mismatch: bool,
) -> int:
    if str(TOOLS_DIR) not in sys.path:
        sys.path.insert(
            0,
            str(TOOLS_DIR),
        )

    builder = importlib.import_module(
        "build_mod_patch"
    )

    # KCD2 field testing showed child <br/> is flattened in subtitles.
    def apply_full_foreign_inline(
        display_cell,
        original: str,
        meaning: str,
    ) -> str:
        rendered = (
            f"{original} — "
            f"[English] {meaning}"
        )

        builder.clear_cell(
            display_cell
        )

        display_cell.text = rendered

        return rendered

    builder.apply_full_foreign = (
        apply_full_foreign_inline
    )

    old_argv = sys.argv[:]

    try:
        sys.argv = [
            str(
                TOOLS_DIR
                / "build_mod_patch.py"
            ),
            "--repo",
            str(REPO),
            "--version",
            version,
        ]

        if allow_source_mismatch:
            sys.argv.append(
                "--allow-source-mismatch"
            )

        print()
        print("=" * 72)
        print(
            f"FTFL NUMBERED BUILD: "
            f"v{version}"
        )
        print(
            "Full-foreign presentation: "
            "INLINE SAFE MODE"
        )
        print("=" * 72)

        result = builder.main()

    finally:
        sys.argv = old_argv

    return int(
        result or 0
    )


def audit_package(version: str) -> int:
    safe_version = re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        version,
    )

    zip_path = (
        REPO
        / "dist"
        / (
            "Foreign-Tongues-for-Laymen-"
            f"{safe_version}.zip"
        )
    )

    if not zip_path.is_file():
        raise SystemExit(
            f"Expected build package not found: "
            f"{zip_path}"
        )

    with zipfile.ZipFile(
        zip_path,
        "r",
    ) as outer:
        pak_name = next(
            (
                name
                for name in outer.namelist()
                if name.endswith(
                    "Localization/English_xml.pak"
                )
            ),
            None,
        )

        if not pak_name:
            raise SystemExit(
                "Built Vortex ZIP does not contain "
                "Localization/English_xml.pak"
            )

        pak_bytes = outer.read(
            pak_name
        )

    with zipfile.ZipFile(
        io.BytesIO(pak_bytes),
        "r",
    ) as pak:
        xml_bytes = pak.read(
            "text_ui_dialog.xml"
        )

    xml_text = xml_bytes.decode(
        "utf-8-sig",
        errors="replace",
    )

    xml_norm = normalize(
        xml_text
    )

    unresolved: list[str] = []

    print()
    print("=" * 72)
    print(
        "FTFL STATIC PACKAGE REGRESSION AUDIT"
    )
    print("=" * 72)

    for phrase in REGRESSION_PHRASES:
        needle = normalize(
            phrase
        )

        position = xml_norm.find(
            needle
        )

        if position < 0:
            status = "NOT_FOUND_IN_PACKAGE"

        else:
            window = xml_norm[
                position:
                position + len(needle) + 240
            ]

            translated = (
                "[english]" in window
                or "[english:" in window
            )

            status = (
                "TRANSLATED"
                if translated
                else "UNTRANSLATED"
            )

            if not translated:
                unresolved.append(
                    phrase
                )

        print(
            f"  {status:24} "
            f"{phrase}"
        )

    if unresolved:
        print()
        print(
            "NOT READY FOR PLAYTEST"
        )
        print(
            "Known regression phrases are still "
            "untranslated in the package."
        )
        return len(unresolved)

    print()
    print(
        "STATIC GATE PASSED - package is eligible "
        "for a small rendering regression test."
    )

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "FTFL one-command toolbox"
        )
    )

    sub = parser.add_subparsers(
        dest="command",
        required=True,
    )

    sub.add_parser(
        "scan",
        help=(
            "Run conservative source-driven discovery "
            "and unresolved-family generation"
        ),
    )

    build_parser = sub.add_parser(
        "build",
        help=(
            "Build numbered Vortex package "
            "from approved.csv"
        ),
    )

    build_parser.add_argument(
        "--version",
        required=True,
    )

    build_parser.add_argument(
        "--allow-source-mismatch",
        action="store_true",
    )

    all_parser = sub.add_parser(
        "all",
        help=(
            "Run source discovery, unresolved report, "
            "then build"
        ),
    )

    all_parser.add_argument(
        "--version",
        required=True,
    )

    all_parser.add_argument(
        "--allow-source-mismatch",
        action="store_true",
    )

    args = parser.parse_args()

    print(
        "Foreign Tongues for Laymen"
    )
    print(
        "FTFL Toolbox - source-driven authored dialogue"
    )
    print(
        f"Repository: {REPO}"
    )

    if args.command == "scan":
        unresolved = run_scan()

        print(
            f"\nSCAN COMPLETE - "
            f"{unresolved:,} unresolved families"
        )

        return 0

    if args.command == "build":
        rc = run_build(
            args.version,
            args.allow_source_mismatch,
        )

        if rc != 0:
            return rc

        audit_package(
            args.version
        )

        return 0

    unresolved = run_scan()

    print(
        f"\nScan complete. "
        f"{unresolved:,} unresolved families remain."
    )

    rc = run_build(
        args.version,
        args.allow_source_mismatch,
    )

    if rc != 0:
        return rc

    audit_package(
        args.version
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
