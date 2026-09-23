#!/usr/bin/env python3
"""
FTFL - Group Review Batch Into Dialogue Families

Reads one exported review batch, for example:
    reference/aligned/review_batch_full_foreign_translation_001.csv

Groups rows by normalized English_display text so repeated localization keys
for the same displayed subtitle can be reviewed and translated once.

This is intentionally conservative:
- It groups exact normalized display-text matches only.
- It does NOT fuzzy-merge similar sentences.
- It preserves every member localization key.
- It does NOT auto-translate or auto-approve anything.

Example:
    python .\tools\group_review_batch.py ^
        --input reference\aligned\review_batch_full_foreign_translation_001.csv

Default output:
    reference/aligned/review_families_full_foreign_translation_001.csv
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
from collections import OrderedDict
from pathlib import Path


WS_RE = re.compile(r"\s+")
BATCH_NAME_RE = re.compile(r"^review_batch_(.+)\.csv$", re.IGNORECASE)


def clean(text: str) -> str:
    """Collapse whitespace but preserve punctuation, accents, and capitalization."""
    return WS_RE.sub(" ", (text or "").strip())


def normalized_display(text: str) -> str:
    """
    Conservative family key:
    - collapse whitespace
    - casefold for comparison
    - preserve punctuation/wording otherwise
    """
    return clean(text).casefold()


def family_id(display: str) -> str:
    digest = hashlib.sha1(
        normalized_display(display).encode("utf-8")
    ).hexdigest()[:12]
    return f"family_{digest}"


def default_output_path(input_path: Path) -> Path:
    match = BATCH_NAME_RE.match(input_path.name)

    if match:
        name = match.group(1)
        return input_path.with_name(
            f"review_families_{name}.csv"
        )

    return input_path.with_name(
        f"{input_path.stem}_families.csv"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Group an FTFL review batch into exact normalized "
            "dialogue-text families."
        )
    )

    parser.add_argument(
        "--input",
        default=(
            "reference/aligned/"
            "review_batch_full_foreign_translation_001.csv"
        ),
        help="Input review batch CSV.",
    )

    parser.add_argument(
        "--output",
        default="",
        help=(
            "Optional output CSV path. If omitted, the output name "
            "is derived from the input filename."
        ),
    )

    args = parser.parse_args()

    input_path = Path(args.input)

    if not input_path.exists():
        print(
            f"ERROR: Missing input: {input_path}",
            file=sys.stderr,
        )
        return 2

    output_path = (
        Path(args.output)
        if args.output
        else default_output_path(input_path)
    )

    try:
        csv.field_size_limit(sys.maxsize)
    except OverflowError:
        csv.field_size_limit(2_147_483_647)

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

        rows = list(reader)

    if not rows:
        print(
            "ERROR: Input CSV contains no rows.",
            file=sys.stderr,
        )
        return 5

    families: OrderedDict[str, list[dict[str, str]]] = OrderedDict()

    for row in rows:
        display = clean(
            row.get("English_display", "")
        )

        if not display:
            # Keep blank-display rows separate so unrelated blanks
            # never collapse into one fake family.
            key = (
                "__blank__:"
                + clean(
                    row.get(
                        "localization_key",
                        "",
                    )
                )
            )
        else:
            key = normalized_display(display)

        families.setdefault(
            key,
            [],
        ).append(row)

    family_rows: list[dict[str, str]] = []

    for members in families.values():
        representative = members[0]

        display = clean(
            representative.get(
                "English_display",
                "",
            )
        )

        localization_keys = [
            clean(
                member.get(
                    "localization_key",
                    "",
                )
            )
            for member in members
            if clean(
                member.get(
                    "localization_key",
                    "",
                )
            )
        ]

        references = list(
            dict.fromkeys(
                clean(
                    member.get(
                        "English_reference",
                        "",
                    )
                )
                for member in members
                if clean(
                    member.get(
                        "English_reference",
                        "",
                    )
                )
            )
        )

        detected_languages = list(
            dict.fromkeys(
                clean(
                    member.get(
                        "detected_languages",
                        member.get(
                            "detected_language",
                            "",
                        ),
                    )
                )
                for member in members
                if clean(
                    member.get(
                        "detected_languages",
                        member.get(
                            "detected_language",
                            "",
                        ),
                    )
                )
            )
        )

        classifications = list(
            dict.fromkeys(
                clean(
                    member.get(
                        "classification",
                        "",
                    )
                )
                for member in members
                if clean(
                    member.get(
                        "classification",
                        "",
                    )
                )
            )
        )

        review_buckets = list(
            dict.fromkeys(
                clean(
                    member.get(
                        "review_bucket",
                        "",
                    )
                )
                for member in members
                if clean(
                    member.get(
                        "review_bucket",
                        "",
                    )
                )
            )
        )

        priorities = list(
            dict.fromkeys(
                clean(
                    member.get(
                        "priority",
                        "",
                    )
                )
                for member in members
                if clean(
                    member.get(
                        "priority",
                        "",
                    )
                )
            )
        )

        family_rows.append({
            "family_id":
                family_id(display)
                if display
                else family_id(
                    localization_keys[0]
                    if localization_keys
                    else "blank"
                ),

            "member_count":
                str(len(members)),

            "localization_keys":
                "; ".join(
                    localization_keys
                ),

            "English_display":
                display,

            "English_references":
                " || ".join(
                    references
                ),

            "detected_languages":
                " || ".join(
                    detected_languages
                ),

            "classifications":
                " || ".join(
                    classifications
                ),

            "review_buckets":
                " || ".join(
                    review_buckets
                ),

            "priorities":
                " || ".join(
                    priorities
                ),

            # Human-review fields.
            "review_decision":
                "",

            "verified_source_language":
                "",

            "verified_foreign_span":
                "",

            "verified_meaning":
                "",

            "translation_notes":
                "",
        })

    # Put repeated families first because they yield the biggest payoff.
    family_rows.sort(
        key=lambda row: (
            -int(
                row.get(
                    "member_count",
                    "0",
                )
                or 0
            ),
            row.get(
                "English_display",
                "",
            ).casefold(),
        )
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = [
        "family_id",
        "member_count",
        "localization_keys",
        "English_display",
        "English_references",
        "detected_languages",
        "classifications",
        "review_buckets",
        "priorities",
        "review_decision",
        "verified_source_language",
        "verified_foreign_span",
        "verified_meaning",
        "translation_notes",
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
        writer.writerows(
            family_rows
        )

    repeated_families = sum(
        1
        for row in family_rows
        if int(
            row["member_count"]
        ) > 1
    )

    repeated_rows = sum(
        int(
            row["member_count"]
        )
        for row in family_rows
        if int(
            row["member_count"]
        ) > 1
    )

    print(
        "FTFL review-family grouping complete."
    )
    print(
        f"Input rows:              "
        f"{len(rows):,}"
    )
    print(
        f"Unique dialogue families:"
        f" {len(family_rows):,}"
    )
    print(
        f"Repeated families:       "
        f"{repeated_families:,}"
    )
    print(
        f"Rows inside repeats:     "
        f"{repeated_rows:,}"
    )
    print(
        f"Translation decisions "
        f"saved: {len(rows) - len(family_rows):,}"
    )
    print(
        f"Output: {output_path}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
