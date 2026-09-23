#!/usr/bin/env python3
"""
FTFL - Export Review Batch
"""
from __future__ import annotations
import argparse
import csv
import re
import sys
from pathlib import Path

SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")

def safe_name(value: str) -> str:
    value = SAFE_NAME_RE.sub("_", value.strip())
    return value.strip("_") or "review"

def main() -> int:
    parser = argparse.ArgumentParser(description="Export a manageable FTFL review batch.")
    parser.add_argument("--input", default="reference/aligned/translation_need_review.csv")
    parser.add_argument("--bucket", default="full_foreign_translation")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    if args.limit <= 0:
        print("ERROR: --limit must be greater than 0.", file=sys.stderr)
        return 2
    if args.batch <= 0:
        print("ERROR: --batch must be 1 or greater.", file=sys.stderr)
        return 3

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: Missing input: {input_path}", file=sys.stderr)
        return 4

    try:
        csv.field_size_limit(sys.maxsize)
    except OverflowError:
        csv.field_size_limit(2_147_483_647)

    with input_path.open("r", encoding="utf-8-sig", newline="") as src:
        reader = csv.DictReader(src)
        if not reader.fieldnames:
            print("ERROR: Input CSV has no header.", file=sys.stderr)
            return 5
        if "review_bucket" not in reader.fieldnames:
            print("ERROR: Input CSV has no review_bucket column.", file=sys.stderr)
            return 6
        fieldnames = list(reader.fieldnames)
        matching_rows = [
            row for row in reader
            if (row.get("review_bucket") or "").strip() == args.bucket
        ]

    total = len(matching_rows)
    start = (args.batch - 1) * args.limit
    end = start + args.limit
    batch_rows = matching_rows[start:end]

    if not batch_rows:
        print("No rows available for that batch.")
        print(f"Bucket: {args.bucket}")
        print(f"Total rows in bucket: {total:,}")
        return 7

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.parent / f"review_batch_{safe_name(args.bucket)}_{args.batch:03d}.csv"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8-sig", newline="") as dst:
        writer = csv.DictWriter(dst, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(batch_rows)

    total_batches = (total + args.limit - 1) // args.limit
    print("FTFL review batch export complete.")
    print(f"Bucket:          {args.bucket}")
    print(f"Bucket rows:     {total:,}")
    print(f"Batch:           {args.batch}/{total_batches}")
    print(f"Rows exported:   {len(batch_rows):,}")
    print(f"Bucket position: {start + 1:,}-{start + len(batch_rows):,}")
    print(f"Output:          {output_path}")

    if args.batch < total_batches:
        print()
        print("Next batch command:")
        print(
            "python .\\tools\\export_review_batch.py "
            f"--bucket {args.bucket} --limit {args.limit} --batch {args.batch + 1}"
        )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
