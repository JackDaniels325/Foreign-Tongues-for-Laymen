#!/usr/bin/env python3
"""
FTFL - Translation Family Summarizer

Reads:
    reference/aligned/translation_review.csv

Writes:
    reference/aligned/translation_families.csv

Groups identical player-facing English_display strings so repeated greetings,
merchant lines, and other reused dialogue can be reviewed as families instead
of one localization key at a time.

No translations are approved automatically.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path


WS_RE = re.compile(r"\s+")


def clean(value: str) -> str:
    return WS_RE.sub(" ", (value or "").strip())


def safe_int(value: str) -> int:
    try:
        return int(value or 0)
    except ValueError:
        return 0


def split_semicolon(value: str) -> list[str]:
    return [
        item.strip()
        for item in (value or "").split(";")
        if item.strip()
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Group FTFL translation-review candidates by identical "
            "player-facing subtitle text."
        )
    )

    parser.add_argument(
        "--input",
        default="reference/aligned/translation_review.csv",
    )

    parser.add_argument(
        "--output",
        default="reference/aligned/translation_families.csv",
    )

    parser.add_argument(
        "--sample-keys",
        type=int,
        default=12,
        help="Maximum localization keys shown per family.",
    )

    parser.add_argument(
        "--console-limit",
        type=int,
        default=40,
        help="Number of top families printed to PowerShell.",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(
            f"ERROR: Input not found: {input_path}",
            file=sys.stderr,
        )
        return 2

    try:
        csv.field_size_limit(sys.maxsize)
    except OverflowError:
        csv.field_size_limit(2_147_483_647)

    groups: dict[str, list[dict[str, str]]] = defaultdict(list)

    with input_path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as src:

        reader = csv.DictReader(src)

        if not reader.fieldnames:
            print(
                "ERROR: Input CSV has no header.",
                file=sys.stderr,
            )
            return 3

        required = {
            "localization_key",
            "classification",
            "revised_score",
            "English_reference",
            "English_display",
            "preserved_tokens",
        }

        missing = required - set(reader.fieldnames)

        if missing:
            print(
                "ERROR: Missing columns: "
                + ", ".join(sorted(missing)),
                file=sys.stderr,
            )
            return 4

        for row in reader:
            display = clean(
                row.get("English_display", "")
            )

            if not display:
                continue

            groups[display].append(row)

    families = []

    for display, rows in groups.items():

        scores = [
            safe_int(row.get("revised_score", "0"))
            for row in rows
        ]

        keys = sorted({
            clean(row.get("localization_key", ""))
            for row in rows
            if clean(row.get("localization_key", ""))
        })

        classifications = sorted({
            clean(row.get("classification", ""))
            for row in rows
            if clean(row.get("classification", ""))
        })

        references = sorted({
            clean(row.get("English_reference", ""))
            for row in rows
            if clean(row.get("English_reference", ""))
        })

        preserved = sorted({
            token
            for row in rows
            for token in split_semicolon(
                row.get("preserved_tokens", "")
            )
        })

        distinct_reference_diffs = [
            ref
            for ref in references
            if ref != display
        ]

        direct_reference_candidate = (
            "yes"
            if distinct_reference_diffs
            else "no"
        )

        families.append({
            "occurrence_count": len(rows),
            "max_revised_score": max(scores) if scores else 0,
            "min_revised_score": min(scores) if scores else 0,
            "classification":
                "; ".join(classifications),
            "English_display": display,
            "English_reference":
                " || ".join(references),
            "direct_reference_candidate":
                direct_reference_candidate,
            "preserved_tokens":
                "; ".join(preserved),
            "sample_localization_keys":
                "; ".join(keys[:args.sample_keys]),
            "total_localization_keys":
                len(keys),
        })

    families.sort(
        key=lambda row: (
            row["direct_reference_candidate"] != "yes",
            -row["max_revised_score"],
            -row["occurrence_count"],
            row["English_display"],
        )
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = [
        "occurrence_count",
        "total_localization_keys",
        "max_revised_score",
        "min_revised_score",
        "classification",
        "direct_reference_candidate",
        "English_display",
        "English_reference",
        "preserved_tokens",
        "sample_localization_keys",
    ]

    with output_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as dst:

        writer = csv.DictWriter(
            dst,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(families)

    print("Translation family summary complete.")
    print(f"Review rows: {sum(len(v) for v in groups.values()):,}")
    print(f"Unique subtitle families: {len(families):,}")
    print(f"Output: {output_path}")

    direct_count = sum(
        1
        for row in families
        if row["direct_reference_candidate"] == "yes"
    )

    print(
        f"Families with differing English reference: "
        f"{direct_count:,}"
    )

    print()
    print("Top translation families:")

    for row in families[:args.console_limit]:

        print()
        print(
            f"[{row['max_revised_score']}] "
            f"x{row['occurrence_count']} "
            f"{row['English_display']}"
        )

        if row["English_reference"]:
            print(
                "    REF: "
                + row["English_reference"][:220]
            )

        print(
            "    TOKENS: "
            + row["preserved_tokens"]
        )

        print(
            "    KEYS: "
            + row["sample_localization_keys"]
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())