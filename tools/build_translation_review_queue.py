#!/usr/bin/env python3
"""
FTFL - Build Translation Review Queue (conservative v2)

Reads:
    reference/aligned/code_switch_candidates.csv

Writes:
    reference/aligned/translation_need_review.csv

Important:
    English_reference is treated as an alternate/source-side reference string,
    NOT automatically as an English translation.

    This tool does NOT auto-approve translations and does NOT auto-declare a
    subtitle "self-glossed". Those decisions require actual semantic review.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path


def clean(text: str) -> str:
    return " ".join((text or "").split())


def safe_int(value: str) -> int:
    try:
        return int(value or 0)
    except ValueError:
        return 0


def choose_bucket(row: dict[str, str]) -> tuple[str, str, list[str]]:
    classification = clean(row.get("classification", ""))
    language_status = clean(row.get("language_status", "single"))
    suppressed = clean(row.get("suppressed_name_signals", ""))
    reference = clean(row.get("English_reference", ""))
    display = clean(row.get("English_display", ""))
    score = safe_int(row.get("foreign_score", "0"))

    notes: list[str] = []

    if language_status != "single":
        notes.append("multiple or ambiguous language-family evidence")
        return "language_review", "highest", notes

    if suppressed:
        notes.append("proper-name/title suppression evidence present")
        return "name_title_review", "high", notes

    if reference and reference != display:
        notes.append(
            "English_reference differs from English_display; "
            "treat as variant/reference evidence, not as a translation"
        )

    if classification == "likely_full_foreign":
        notes.append("display is likely fully foreign")
        return "full_foreign_translation", "highest", notes

    if classification == "mixed_language":
        notes.append(
            "mixed English/foreign display; determine exact foreign span "
            "and whether the line already paraphrases it"
        )
        return "mixed_language_review", "high", notes

    if classification == "foreign_fragment":
        if score >= 4:
            notes.append("strong foreign-fragment evidence")
            return "foreign_fragment_review", "medium", notes

        notes.append("lower-confidence foreign fragment")
        return "general_review", "low", notes

    notes.append("unrecognized detector classification")
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
        description="Build conservative FTFL translation review queue."
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

        source_fields = list(reader.fieldnames)

        for row in reader:
            bucket, priority, notes = choose_bucket(row)

            out = dict(row)
            out["review_bucket"] = bucket
            out["priority"] = priority
            out["reference_differs"] = (
                "yes"
                if clean(row.get("English_reference", ""))
                != clean(row.get("English_display", ""))
                else "no"
            )
            out["review_decision"] = ""
            out["verified_foreign_span"] = ""
            out["verified_meaning"] = ""
            out["review_notes"] = " | ".join(notes)

            rows.append(out)

    rows.sort(
        key=lambda row: (
            priority_rank(row.get("priority", "")),
            row.get("review_bucket", ""),
            -safe_int(row.get("foreign_score", "0")),
            row.get("localization_key", ""),
        )
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    added_fields = [
        "review_bucket",
        "priority",
        "reference_differs",
        "review_decision",
        "verified_foreign_span",
        "verified_meaning",
        "review_notes",
    ]

    fieldnames = [
        field for field in source_fields if field not in added_fields
    ] + added_fields

    with output_path.open("w", encoding="utf-8-sig", newline="") as dst:
        writer = csv.DictWriter(dst, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    bucket_counts = Counter(
        row["review_bucket"]
        for row in rows
    )

    priority_counts = Counter(
        row["priority"]
        for row in rows
    )

    print("Conservative translation review queue complete.")
    print(f"Rows written: {len(rows):,}")
    print()

    print("Review buckets:")
    for bucket, count in bucket_counts.most_common():
        print(f"  {bucket:<30} {count:>7,}")

    print()
    print("Priorities:")
    for priority in ("highest", "high", "medium", "low"):
        count = priority_counts.get(priority, 0)
        print(f"  {priority:<10} {count:>7,}")

    print()
    print(
        "NOTE: No rows were automatically marked self-glossed or translated."
    )
    print(f"Output: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
