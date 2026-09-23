#!/usr/bin/env python3
"""
FTFL - Build Translation Review Queue

Reads:
    reference/aligned/code_switch_candidates.csv

Writes:
    reference/aligned/translation_need_review.csv

Purpose:
    Turn the global detector output into a smaller, structured review queue.
    This tool does NOT auto-approve or auto-translate anything.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path


WORD_RE = re.compile(
    r"[A-Za-zÀ-ÖØ-öø-ÿĀ-ž]+(?:['’-][A-Za-zÀ-ÖØ-öø-ÿĀ-ž]+)?"
)
WS_RE = re.compile(r"\s+")


def clean(text: str) -> str:
    return WS_RE.sub(" ", (text or "").strip())


def words(text: str) -> list[str]:
    return [m.group(0).casefold() for m in WORD_RE.finditer(text or "")]


def similarity(a: str, b: str) -> float:
    a = clean(a).casefold()
    b = clean(b).casefold()

    if not a or not b:
        return 0.0

    return SequenceMatcher(None, a, b).ratio()


def word_overlap_ratio(a: str, b: str) -> float:
    a_words = set(words(a))
    b_words = set(words(b))

    if not a_words or not b_words:
        return 0.0

    overlap = len(a_words & b_words)
    return overlap / max(1, len(a_words | b_words))


def choose_bucket(row: dict[str, str]) -> tuple[str, str, list[str]]:
    classification = clean(row.get("classification", ""))
    language_status = clean(row.get("language_status", "single"))
    display = clean(row.get("English_display", ""))
    reference = clean(row.get("English_reference", ""))
    suppressed = clean(row.get("suppressed_name_signals", ""))

    try:
        score = int(row.get("foreign_score", "0") or 0)
    except ValueError:
        score = 0

    ref_differs = bool(reference and reference != display)
    sim = similarity(display, reference)
    overlap = word_overlap_ratio(display, reference)

    notes: list[str] = []

    if language_status != "single":
        notes.append("multiple/ambiguous language-family evidence")
        return "language_review", "high", notes

    if suppressed:
        notes.append("proper-name/title suppression evidence present")
        return "name_title_review", "high", notes

    # A differing English reference is valuable evidence because it may contain
    # an official English rendering of the foreign material.
    if ref_differs:
        notes.append("English reference differs from displayed subtitle")

        # If the display already shares a large amount of English wording with
        # the reference, the foreign material may already be paraphrased or
        # explained in the same subtitle. Flag for review; do not auto-skip.
        if overlap >= 0.55 or sim >= 0.72:
            notes.append(
                f"high display/reference overlap "
                f"(word={overlap:.2f}, sequence={sim:.2f})"
            )
            return "possible_self_glossed", "high", notes

        if classification == "likely_full_foreign":
            return "reference_translation_candidate", "highest", notes

        if classification == "mixed_language":
            return "reference_translation_candidate", "highest", notes

        return "reference_translation_candidate", "high", notes

    if classification == "likely_full_foreign":
        notes.append("full-foreign candidate without differing English reference")
        return "manual_translation_needed", "highest", notes

    if classification == "mixed_language":
        notes.append("mixed-language candidate without differing English reference")
        return "manual_translation_needed", "high", notes

    if score >= 4:
        notes.append("strong foreign-fragment score")
        return "manual_translation_needed", "medium", notes

    notes.append("low-confidence fragment; manual review first")
    return "general_review", "low", notes


def priority_rank(priority: str) -> int:
    return {
        "highest": 0,
        "high": 1,
        "medium": 2,
        "low": 3,
    }.get(priority, 9)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the FTFL translation/review queue."
    )
    parser.add_argument(
        "--input",
        default="reference/aligned/code_switch_candidates.csv",
    )
    parser.add_argument(
        "--output",
        default="reference/aligned/translation_need_review.csv",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"ERROR: Missing input: {input_path}", file=sys.stderr)
        return 2

    try:
        csv.field_size_limit(sys.maxsize)
    except OverflowError:
        csv.field_size_limit(2_147_483_647)

    rows: list[dict[str, str]] = []

    with input_path.open("r", encoding="utf-8-sig", newline="") as src:
        reader = csv.DictReader(src)

        if not reader.fieldnames:
            print("ERROR: Input CSV has no header.", file=sys.stderr)
            return 3

        required = {
            "localization_key",
            "classification",
            "English_reference",
            "English_display",
        }

        missing = required - set(reader.fieldnames)

        if missing:
            print(
                "ERROR: Missing required columns: "
                + ", ".join(sorted(missing)),
                file=sys.stderr,
            )
            return 4

        for row in reader:
            bucket, priority, notes = choose_bucket(row)

            reference = clean(row.get("English_reference", ""))
            display = clean(row.get("English_display", ""))

            out = dict(row)
            out["review_bucket"] = bucket
            out["priority"] = priority
            out["reference_differs"] = "yes" if reference != display else "no"
            out["display_reference_similarity"] = f"{similarity(display, reference):.3f}"
            out["display_reference_word_overlap"] = f"{word_overlap_ratio(display, reference):.3f}"
            out["review_notes"] = " | ".join(notes)

            rows.append(out)

    rows.sort(
        key=lambda row: (
            priority_rank(row.get("priority", "")),
            row.get("review_bucket", ""),
            -int(row.get("foreign_score", "0") or 0),
            row.get("localization_key", ""),
        )
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    base_fields = list(rows[0].keys()) if rows else []
    preferred_tail = [
        "review_bucket",
        "priority",
        "reference_differs",
        "display_reference_similarity",
        "display_reference_word_overlap",
        "review_notes",
    ]

    fieldnames = [
        field
        for field in base_fields
        if field not in preferred_tail
    ] + preferred_tail

    with output_path.open("w", encoding="utf-8-sig", newline="") as dst:
        writer = csv.DictWriter(dst, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    bucket_counts: dict[str, int] = {}
    for row in rows:
        bucket = row["review_bucket"]
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1

    print("Translation review queue complete.")
    print(f"Rows written: {len(rows):,}")
    print()
    print("Review buckets:")
    for bucket, count in sorted(
        bucket_counts.items(),
        key=lambda item: (-item[1], item[0]),
    ):
        print(f"  {bucket:<34} {count:>7,}")

    print()
    print(f"Output: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
