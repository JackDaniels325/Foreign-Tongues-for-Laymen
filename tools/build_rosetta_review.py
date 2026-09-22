#!/usr/bin/env python3
"""
FTFL - Rosetta Translation Review Builder

Reads:
    reference/aligned/translation_review.csv
    reference/aligned/localization_alignment.csv

Writes:
    reference/aligned/translation_rosetta_review.csv

Purpose:
    Take the strongest foreign-language candidates and attach the official
    localization text for the exact same localization key across every
    available language.

This allows us to determine whether another official localization resolves
the intended meaning before anything is promoted to corpus/approved.csv.

Nothing is automatically approved or translated.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


def safe_int(value: str) -> int:
    try:
        return int(value or 0)
    except ValueError:
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Join FTFL translation candidates against the full "
            "cross-language Rosetta alignment."
        )
    )

    parser.add_argument(
        "--review",
        default="reference/aligned/translation_review.csv",
        help="Candidate review CSV.",
    )

    parser.add_argument(
        "--alignment",
        default="reference/aligned/localization_alignment.csv",
        help="Full Rosetta alignment CSV.",
    )

    parser.add_argument(
        "--output",
        default="reference/aligned/translation_rosetta_review.csv",
        help="Cross-language review output.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Maximum review rows to process.",
    )

    parser.add_argument(
        "--console-limit",
        type=int,
        default=25,
        help="Maximum rows shown in PowerShell.",
    )

    args = parser.parse_args()

    review_path = Path(args.review)
    alignment_path = Path(args.alignment)
    output_path = Path(args.output)

    if not review_path.exists():
        print(
            f"ERROR: Review file not found: {review_path}",
            file=sys.stderr,
        )
        return 2

    if not alignment_path.exists():
        print(
            f"ERROR: Alignment file not found: {alignment_path}",
            file=sys.stderr,
        )
        return 3

    try:
        csv.field_size_limit(sys.maxsize)
    except OverflowError:
        csv.field_size_limit(2_147_483_647)

    # ---------------------------------------------------------
    # Load requested review candidates.
    # ---------------------------------------------------------

    review_rows: list[dict[str, str]] = []

    with review_path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as src:

        reader = csv.DictReader(src)

        if not reader.fieldnames:
            print(
                "ERROR: Review CSV has no header.",
                file=sys.stderr,
            )
            return 4

        required = {
            "localization_key",
            "classification",
            "revised_score",
            "English_display",
        }

        missing = required - set(reader.fieldnames)

        if missing:
            print(
                "ERROR: Review CSV missing columns: "
                + ", ".join(sorted(missing)),
                file=sys.stderr,
            )
            return 5

        for row in reader:
            review_rows.append(row)

            if (
                args.limit > 0
                and len(review_rows) >= args.limit
            ):
                break

    wanted_keys = {
        row["localization_key"].strip()
        for row in review_rows
        if row.get("localization_key", "").strip()
    }

    print(
        f"Review candidates requested: "
        f"{len(wanted_keys):,}"
    )

    # ---------------------------------------------------------
    # Scan large alignment once and retain only wanted keys.
    # ---------------------------------------------------------

    alignment_rows: dict[str, dict[str, str]] = {}

    with alignment_path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as src:

        reader = csv.DictReader(src)

        if not reader.fieldnames:
            print(
                "ERROR: Alignment CSV has no header.",
                file=sys.stderr,
            )
            return 6

        alignment_fields = list(reader.fieldnames)

        if "localization_key" not in alignment_fields:
            print(
                "ERROR: Alignment CSV has no localization_key.",
                file=sys.stderr,
            )
            return 7

        for row in reader:
            key = row.get(
                "localization_key",
                "",
            ).strip()

            if key in wanted_keys:
                alignment_rows[key] = row

                if len(alignment_rows) == len(wanted_keys):
                    break

    missing_keys = sorted(
        wanted_keys - set(alignment_rows)
    )

    if missing_keys:
        print()
        print(
            f"WARNING: {len(missing_keys):,} review keys "
            "were not found in alignment."
        )

        for key in missing_keys[:20]:
            print(f"  {key}")

    # ---------------------------------------------------------
    # Determine all Rosetta language columns.
    # ---------------------------------------------------------

    language_fields = [
        field
        for field in alignment_fields
        if field != "localization_key"
    ]

    review_prefix_fields = [
        "localization_key",
        "classification",
        "revised_score",
        "score",
        "preserved_tokens",
        "classification_notes",
    ]

    output_fields = (
        review_prefix_fields
        + language_fields
        + [
            "review_source_language",
            "review_verified_meaning",
            "review_line_type",
            "review_status",
            "review_notes",
        ]
    )

    # ---------------------------------------------------------
    # Join review rows to Rosetta rows.
    # ---------------------------------------------------------

    joined: list[dict[str, str]] = []

    for review in review_rows:

        key = review.get(
            "localization_key",
            "",
        ).strip()

        alignment = alignment_rows.get(key)

        if not alignment:
            continue

        out: dict[str, str] = {}

        for field in review_prefix_fields:
            out[field] = review.get(
                field,
                "",
            )

        for field in language_fields:
            out[field] = alignment.get(
                field,
                "",
            )

        out["review_source_language"] = ""
        out["review_verified_meaning"] = ""
        out["review_line_type"] = ""
        out["review_status"] = ""
        out["review_notes"] = ""

        joined.append(out)

    joined.sort(
        key=lambda row: (
            -safe_int(
                row.get(
                    "revised_score",
                    "0",
                )
            ),
            row.get(
                "localization_key",
                "",
            ),
        )
    )

    # ---------------------------------------------------------
    # Write output.
    # ---------------------------------------------------------

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as dst:

        writer = csv.DictWriter(
            dst,
            fieldnames=output_fields,
        )

        writer.writeheader()
        writer.writerows(joined)

    print()
    print("Rosetta translation review complete.")
    print(
        f"Rows written: {len(joined):,}"
    )
    print(
        f"Output: {output_path}"
    )

    # ---------------------------------------------------------
    # Console preview.
    # ---------------------------------------------------------

    preview_languages = [
        "English",
        "Czech",
        "German",
        "Polish",
        "French",
        "Spanish",
        "Italian",
    ]

    print()
    print("Cross-localization preview:")

    for row in joined[:args.console_limit]:

        print()
        print(
            f"[{row.get('revised_score', '')}] "
            f"{row.get('localization_key', '')}"
        )

        for language in preview_languages:

            ref_field = (
                f"{language}_reference"
            )

            display_field = (
                f"{language}_display"
            )

            reference = (
                row.get(
                    ref_field,
                    "",
                )
                or ""
            ).strip()

            display = (
                row.get(
                    display_field,
                    "",
                )
                or ""
            ).strip()

            if not reference and not display:
                continue

            print(
                f"  {language}:"
            )

            if reference:
                print(
                    "    REF: "
                    + reference[:260]
                )

            if display:
                print(
                    "    DSP: "
                    + display[:260]
                )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())