#!/usr/bin/env python3
"""
FTFL Rosetta - Foreign Candidate Triage

Takes the output from find_foreign_candidates.py and splits it into review tiers.
Also produces a token-frequency summary to help identify false positives such as
proper names, place names, and commonly preserved localization terms.

Default input:
    reference/aligned/foreign_candidates.csv

Outputs:
    reference/aligned/foreign_candidates_high.csv
    reference/aligned/foreign_candidates_medium.csv
    reference/aligned/foreign_candidate_token_summary.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path


def split_tokens(value: str) -> list[str]:
    return [x.strip() for x in (value or "").split(";") if x.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Split FTFL foreign-language candidates into review tiers and summarize repeated preserved tokens."
    )
    parser.add_argument(
        "--input",
        default="reference/aligned/foreign_candidates.csv",
        help="Input candidate CSV produced by find_foreign_candidates.py."
    )
    parser.add_argument(
        "--high-min",
        type=int,
        default=9,
        help="Minimum score for high-confidence review tier (default: 9)."
    )
    parser.add_argument(
        "--medium-min",
        type=int,
        default=7,
        help="Minimum score for medium-confidence review tier (default: 7)."
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    out_dir = input_path.parent

    if not input_path.exists():
        print(f"ERROR: Input not found: {input_path}", file=sys.stderr)
        return 2

    try:
        csv.field_size_limit(sys.maxsize)
    except OverflowError:
        csv.field_size_limit(2_147_483_647)

    high_path = out_dir / "foreign_candidates_high.csv"
    medium_path = out_dir / "foreign_candidates_medium.csv"
    token_path = out_dir / "foreign_candidate_token_summary.csv"

    token_counts = Counter()
    token_high_counts = Counter()
    score_counts = Counter()

    total = 0
    high_count = 0
    medium_count = 0

    with input_path.open("r", encoding="utf-8-sig", newline="") as src:
        reader = csv.DictReader(src)
        if not reader.fieldnames:
            print("ERROR: Candidate CSV has no header.", file=sys.stderr)
            return 3

        required = {"localization_key", "score", "preserved_tokens"}
        missing = required - set(reader.fieldnames)
        if missing:
            print(f"ERROR: Missing required columns: {', '.join(sorted(missing))}", file=sys.stderr)
            return 4

        with high_path.open("w", encoding="utf-8-sig", newline="") as high_file,              medium_path.open("w", encoding="utf-8-sig", newline="") as medium_file:

            high_writer = csv.DictWriter(high_file, fieldnames=reader.fieldnames)
            medium_writer = csv.DictWriter(medium_file, fieldnames=reader.fieldnames)
            high_writer.writeheader()
            medium_writer.writeheader()

            for row in reader:
                total += 1

                try:
                    score = int(row.get("score", "0"))
                except ValueError:
                    score = 0

                score_counts[score] += 1

                toks = split_tokens(row.get("preserved_tokens", ""))
                for tok in toks:
                    token_counts[tok] += 1

                if score >= args.high_min:
                    high_writer.writerow(row)
                    high_count += 1
                    for tok in toks:
                        token_high_counts[tok] += 1
                elif score >= args.medium_min:
                    medium_writer.writerow(row)
                    medium_count += 1

    with token_path.open("w", encoding="utf-8-sig", newline="") as dst:
        fieldnames = [
            "token",
            "all_candidate_occurrences",
            "high_confidence_occurrences",
        ]
        writer = csv.DictWriter(dst, fieldnames=fieldnames)
        writer.writeheader()

        for token, count in token_counts.most_common():
            writer.writerow({
                "token": token,
                "all_candidate_occurrences": count,
                "high_confidence_occurrences": token_high_counts[token],
            })

    print("Candidate triage complete.")
    print(f"Input rows: {total:,}")
    print(f"High confidence (score >= {args.high_min}): {high_count:,}")
    print(f"Medium confidence ({args.medium_min} <= score < {args.high_min}): {medium_count:,}")
    print()
    print("Score distribution:")
    for score in sorted(score_counts):
        print(f"  {score}: {score_counts[score]:,}")
    print()
    print(f"High tier:   {high_path}")
    print(f"Medium tier: {medium_path}")
    print(f"Token summary: {token_path}")

    if token_counts:
        print()
        print("Top preserved tokens:")
        for token, count in token_counts.most_common(20):
            print(f"  {token:<30} {count:>6} total | {token_high_counts[token]:>6} high")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
