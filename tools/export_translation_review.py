#!/usr/bin/env python3
"""
FTFL - Export Translation Review Queue

Reads:
    reference/aligned/foreign_candidates_classified.csv

Writes:
    reference/aligned/translation_review.csv

Purpose:
    Produce a compact review queue from the classifier output so confirmed
    localization keys can be promoted into corpus/approved.csv.

This script does NOT automatically approve or translate anything.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


DEFAULT_CLASSES = {
    "likely_foreign_phrase",
    "mixed_or_ambiguous",
}


def safe_int(value: str) -> int:
    try:
        return int(value or 0)
    except ValueError:
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export FTFL classified candidates into a compact translation review queue."
    )

    parser.add_argument(
        "--input",
        default="reference/aligned/foreign_candidates_classified.csv",
        help="Classifier output CSV.",
    )

    parser.add_argument(
        "--output",
        default="reference/aligned/translation_review.csv",
        help="Compact review CSV.",
    )

    parser.add_argument(
        "--min-score",
        type=int,
        default=9,
        help="Minimum revised score to export (default: 9).",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Maximum number of review rows to export (default: 200).",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"ERROR: Input not found: {input_path}", file=sys.stderr)
        return 2

    try:
        csv.field_size_limit(sys.maxsize)
    except OverflowError:
        csv.field_size_limit(2_147_483_647)

    selected = []

    with input_path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as src:

        reader = csv.DictReader(src)

        if not reader.fieldnames:
            print("ERROR: Input CSV has no header.", file=sys.stderr)
            return 3

        required = {
            "localization_key",
            "score",
            "English_reference",
            "English_display",
            "preserved_tokens",
            "classification",
            "revised_score",
            "classification_notes",
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
            classification = (
                row.get("classification", "")
                .strip()
            )

            revised_score = safe_int(
                row.get("revised_score", "0")
            )

            if classification not in DEFAULT_CLASSES:
                continue

            if revised_score < args.min_score:
                continue

            selected.append(row)

    selected.sort(
        key=lambda row: (
            -safe_int(row.get("revised_score", "0")),
            -safe_int(row.get("score", "0")),
            row.get("localization_key", ""),
        )
    )

    if args.limit > 0:
        selected = selected[:args.limit]

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fields = [
        "localization_key",
        "classification",
        "revised_score",
        "score",
        "English_reference",
        "English_display",
        "preserved_tokens",
        "classification_notes",
        "review_language",
        "review_meaning",
        "review_line_type",
        "review_status",
        "review_notes",
    ]

    with output_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as dst:

        writer = csv.DictWriter(
            dst,
            fieldnames=fields,
        )

        writer.writeheader()

        for row in selected:
            writer.writerow({
                "localization_key":
                    row.get("localization_key", ""),

                "classification":
                    row.get("classification", ""),

                "revised_score":
                    row.get("revised_score", ""),

                "score":
                    row.get("score", ""),

                "English_reference":
                    row.get("English_reference", ""),

                "English_display":
                    row.get("English_display", ""),

                "preserved_tokens":
                    row.get("preserved_tokens", ""),

                "classification_notes":
                    row.get("classification_notes", ""),

                "review_language": "",
                "review_meaning": "",
                "review_line_type": "",
                "review_status": "",
                "review_notes": "",
            })

    print("Translation review export complete.")
    print(f"Rows exported: {len(selected):,}")
    print(f"Minimum revised score: {args.min_score}")
    print(f"Output: {output_path}")

    if selected:
        print()
        print("Top review candidates:")

        for row in selected[:20]:
            print(
                f"  [{row.get('revised_score', '')}] "
                f"{row.get('localization_key', '')}"
            )
            print(
                "      "
                + row.get("English_display", "")[:140]
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())