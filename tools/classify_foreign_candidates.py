#!/usr/bin/env python3
"""
FTFL Rosetta - Foreign Candidate Classifier

Reads the candidate CSV plus two editable glossary files, then classifies rows
into conservative review buckets.

Glossaries:
    reference/glossaries/proper_nouns.txt
    reference/glossaries/foreign_lexicon.txt

Default input:
    reference/aligned/foreign_candidates.csv

Output:
    reference/aligned/foreign_candidates_classified.csv

This tool does NOT delete candidates and does NOT perform translation.
It only adds review-oriented classification signals.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

TOKEN_SPLIT_RE = re.compile(r"\s*;\s*")
WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿĀ-ž]+(?:['’-][A-Za-zÀ-ÖØ-öø-ÿĀ-ž]+)?")

LIKELY_FOREIGN_LABEL = "likely_foreign_phrase"
LIKELY_PROPER_LABEL = "likely_proper_noun"
MIXED_LABEL = "mixed_or_ambiguous"
REVIEW_LABEL = "needs_review"


def load_terms(path: Path) -> set[str]:
    if not path.exists():
        return set()

    terms = set()
    with path.open("r", encoding="utf-8-sig") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            terms.add(line.casefold())
    return terms


def split_preserved_tokens(value: str) -> list[str]:
    if not value:
        return []
    return [x.strip() for x in TOKEN_SPLIT_RE.split(value) if x.strip()]


def words(text: str) -> list[str]:
    return [m.group(0) for m in WORD_RE.finditer(text or "")]


def classify_row(
    row: dict[str, str],
    proper_nouns: set[str],
    foreign_lexicon: set[str],
) -> tuple[str, int, int, int, list[str]]:
    preserved = split_preserved_tokens(row.get("preserved_tokens", ""))

    proper_hits = [t for t in preserved if t.casefold() in proper_nouns]
    foreign_hits = [t for t in preserved if t.casefold() in foreign_lexicon]

    proper_hit_count = len(proper_hits)
    foreign_hit_count = len(foreign_hits)

    try:
        original_score = int(row.get("score", "0") or 0)
    except ValueError:
        original_score = 0

    revised_score = original_score
    notes: list[str] = []

    if proper_hit_count and not foreign_hit_count:
        revised_score -= min(3, proper_hit_count)
        notes.append("proper-noun preservation hit(s): " + ", ".join(proper_hits[:8]))

    if foreign_hit_count:
        revised_score += min(4, foreign_hit_count)
        notes.append("foreign-lexicon hit(s): " + ", ".join(foreign_hits[:8]))

    if len(preserved) >= 2:
        revised_score += 1
        notes.append("multiple preserved tokens")

    all_preserved_are_proper = bool(preserved) and all(
        t.casefold() in proper_nouns for t in preserved
    )

    display_words = [w.casefold() for w in words(row.get("English_display", ""))]
    visible_foreign_hits = sorted({
        w for w in display_words if w in foreign_lexicon
    })

    if visible_foreign_hits:
        revised_score += min(3, len(visible_foreign_hits))
        notes.append(
            "foreign lexicon visible in English display: "
            + ", ".join(visible_foreign_hits[:8])
        )

    if foreign_hit_count >= 2 or len(visible_foreign_hits) >= 2:
        label = LIKELY_FOREIGN_LABEL
    elif foreign_hit_count >= 1 and proper_hit_count == 0:
        label = LIKELY_FOREIGN_LABEL
    elif all_preserved_are_proper and not visible_foreign_hits:
        label = LIKELY_PROPER_LABEL
    elif proper_hit_count and (foreign_hit_count or visible_foreign_hits):
        label = MIXED_LABEL
    elif proper_hit_count:
        label = LIKELY_PROPER_LABEL
    elif foreign_hit_count or visible_foreign_hits:
        label = LIKELY_FOREIGN_LABEL
    else:
        label = REVIEW_LABEL

    return label, revised_score, proper_hit_count, foreign_hit_count, notes


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Classify FTFL Rosetta foreign-language candidates using editable glossaries."
    )
    parser.add_argument(
        "--input",
        default="reference/aligned/foreign_candidates.csv",
        help="Candidate CSV produced by find_foreign_candidates.py."
    )
    parser.add_argument(
        "--proper-nouns",
        default="reference/glossaries/proper_nouns.txt",
        help="Case-insensitive proper noun suppression glossary."
    )
    parser.add_argument(
        "--foreign-lexicon",
        default="reference/glossaries/foreign_lexicon.txt",
        help="Case-insensitive foreign-language lexicon seed list."
    )
    parser.add_argument(
        "--output",
        default="reference/aligned/foreign_candidates_classified.csv",
        help="Output classified review CSV."
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    proper_path = Path(args.proper_nouns)
    foreign_path = Path(args.foreign_lexicon)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"ERROR: Input not found: {input_path}", file=sys.stderr)
        return 2

    proper_nouns = load_terms(proper_path)
    foreign_lexicon = load_terms(foreign_path)

    print(f"Proper noun glossary entries: {len(proper_nouns):,}")
    print(f"Foreign lexicon entries:      {len(foreign_lexicon):,}")

    if not proper_nouns:
        print(f"WARNING: Proper noun glossary is empty or missing: {proper_path}")
    if not foreign_lexicon:
        print(f"WARNING: Foreign lexicon is empty or missing: {foreign_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        csv.field_size_limit(sys.maxsize)
    except OverflowError:
        csv.field_size_limit(2_147_483_647)

    label_counts = Counter()
    total = 0

    with input_path.open("r", encoding="utf-8-sig", newline="") as src:
        reader = csv.DictReader(src)
        if not reader.fieldnames:
            print("ERROR: Candidate CSV has no header.", file=sys.stderr)
            return 3

        required = {
            "localization_key",
            "score",
            "English_reference",
            "English_display",
            "preserved_tokens",
        }
        missing = required - set(reader.fieldnames)
        if missing:
            print(
                f"ERROR: Missing required columns: {', '.join(sorted(missing))}",
                file=sys.stderr,
            )
            return 4

        out_fields = list(reader.fieldnames) + [
            "classification",
            "revised_score",
            "proper_noun_hits",
            "foreign_lexicon_hits",
            "classification_notes",
        ]

        with output_path.open("w", encoding="utf-8-sig", newline="") as dst:
            writer = csv.DictWriter(dst, fieldnames=out_fields)
            writer.writeheader()

            for row in reader:
                total += 1
                label, revised_score, proper_hit_count, foreign_hit_count, notes = classify_row(
                    row, proper_nouns, foreign_lexicon
                )

                label_counts[label] += 1

                out = dict(row)
                out.update({
                    "classification": label,
                    "revised_score": revised_score,
                    "proper_noun_hits": proper_hit_count,
                    "foreign_lexicon_hits": foreign_hit_count,
                    "classification_notes": " | ".join(notes),
                })
                writer.writerow(out)

                if total % 25000 == 0:
                    print(f"Classified {total:,} rows...")

    print()
    print("Candidate classification complete.")
    print(f"Rows classified: {total:,}")
    print("Classification counts:")
    for label, count in label_counts.most_common():
        print(f"  {label:<24} {count:>7,}")
    print(f"Output: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
