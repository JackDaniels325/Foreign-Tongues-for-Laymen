#!/usr/bin/env python3
"""
FTFL - Priority Language / Scene Sweep

Purpose:
    Pull every likely Romani and Yiddish/Hebrew dialogue row from the COMPLETE
    English localization alignment into one review file, including rows that
    may have been missed by the normal detector.

Reads:
    reference/aligned/localization_alignment.csv
    reference/glossaries/romani_signals.txt
    reference/glossaries/yiddish_hebrew_signals.txt

Writes:
    reference/aligned/priority_nomad_yiddish_sweep.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path


WORD_RE = re.compile(
    r"[A-Za-zÀ-ÖØ-öø-ÿĀ-ž]+(?:['’-][A-Za-zÀ-ÖØ-öø-ÿĀ-ž]+)?"
)
WS_RE = re.compile(r"\s+")

FORCE_KEY_STEMS = (
    "vajd_",
    "aranka",
    "mordecai",
    "haim",
    "nomad",
)

FORCE_TEXT_ANCHORS = (
    "mizerere",
    "tuke",
    "goro",
    "yandre",
    "jandre",
    "sar tuke",
    "vos is los",
    "oy, oy",
    "oy oy",
    "mordecai",
    "aranka",
)


def clean(text: str) -> str:
    return WS_RE.sub(" ", (text or "").strip())


def load_terms(path: Path) -> set[str]:
    terms: set[str] = set()
    if not path.exists():
        return terms

    with path.open("r", encoding="utf-8-sig") as fh:
        for raw in fh:
            value = clean(raw)
            if not value or value.startswith("#"):
                continue
            terms.add(value.casefold())

    return terms


def word_tokens(text: str) -> set[str]:
    return {
        match.group(0).casefold()
        for match in WORD_RE.finditer(text or "")
    }


def term_hits(text: str, terms: set[str]) -> list[str]:
    folded = text.casefold()
    tokens = word_tokens(text)
    hits: list[str] = []

    for term in sorted(terms):
        if " " in term:
            if term in folded:
                hits.append(term)
        elif term in tokens:
            hits.append(term)

    return hits


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export a complete Romani/Yiddish priority sweep from FTFL alignment."
    )
    parser.add_argument(
        "--input",
        default="reference/aligned/localization_alignment.csv",
    )
    parser.add_argument(
        "--romani",
        default="reference/glossaries/romani_signals.txt",
    )
    parser.add_argument(
        "--yiddish",
        default="reference/glossaries/yiddish_hebrew_signals.txt",
    )
    parser.add_argument(
        "--output",
        default="reference/aligned/priority_nomad_yiddish_sweep.csv",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    romani_path = Path(args.romani)
    yiddish_path = Path(args.yiddish)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"ERROR: Missing alignment: {input_path}", file=sys.stderr)
        return 2

    romani_terms = load_terms(romani_path)
    yiddish_terms = load_terms(yiddish_path)

    if not romani_terms:
        print(f"ERROR: No Romani signals loaded from {romani_path}", file=sys.stderr)
        return 3

    if not yiddish_terms:
        print(f"ERROR: No Yiddish/Hebrew signals loaded from {yiddish_path}", file=sys.stderr)
        return 4

    try:
        csv.field_size_limit(sys.maxsize)
    except OverflowError:
        csv.field_size_limit(2_147_483_647)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    out_fields = [
        "localization_key",
        "match_reason",
        "romani_hits",
        "yiddish_hebrew_hits",
        "forced_key_match",
        "forced_text_match",
        "English_reference",
        "English_display",
    ]

    scanned = 0
    written = 0
    romani_rows = 0
    yiddish_rows = 0
    forced_rows = 0

    with input_path.open("r", encoding="utf-8-sig", newline="") as src, \
         output_path.open("w", encoding="utf-8-sig", newline="") as dst:

        reader = csv.DictReader(src)

        if not reader.fieldnames:
            print("ERROR: Alignment has no header.", file=sys.stderr)
            return 5

        required = {
            "localization_key",
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
            return 6

        writer = csv.DictWriter(dst, fieldnames=out_fields)
        writer.writeheader()

        for row in reader:
            scanned += 1

            key = clean(row.get("localization_key", ""))
            reference = clean(row.get("English_reference", ""))
            display = clean(row.get("English_display", ""))

            combined = f"{reference} {display}".strip()

            r_hits = term_hits(combined, romani_terms)
            y_hits = term_hits(combined, yiddish_terms)

            key_fold = key.casefold()
            combined_fold = combined.casefold()

            key_matches = [
                stem for stem in FORCE_KEY_STEMS if stem in key_fold
            ]

            text_matches = [
                anchor for anchor in FORCE_TEXT_ANCHORS if anchor in combined_fold
            ]

            if not (r_hits or y_hits or key_matches or text_matches):
                continue

            reasons: list[str] = []

            if r_hits:
                reasons.append("romani_signal")
            if y_hits:
                reasons.append("yiddish_hebrew_signal")
            if key_matches:
                reasons.append("forced_key")
            if text_matches:
                reasons.append("forced_text")

            writer.writerow({
                "localization_key": key,
                "match_reason": "; ".join(reasons),
                "romani_hits": "; ".join(r_hits),
                "yiddish_hebrew_hits": "; ".join(y_hits),
                "forced_key_match": "; ".join(key_matches),
                "forced_text_match": "; ".join(text_matches),
                "English_reference": reference,
                "English_display": display,
            })

            written += 1
            if r_hits:
                romani_rows += 1
            if y_hits:
                yiddish_rows += 1
            if key_matches or text_matches:
                forced_rows += 1

            if scanned % 25000 == 0:
                print(
                    f"Scanned {scanned:,} rows... "
                    f"{written:,} priority matches"
                )

    print()
    print("FTFL priority language / scene sweep complete.")
    print(f"Rows scanned:              {scanned:,}")
    print(f"Rows exported:             {written:,}")
    print(f"Rows with Romani signals:  {romani_rows:,}")
    print(f"Rows with Yiddish signals: {yiddish_rows:,}")
    print(f"Forced scene/text rows:    {forced_rows:,}")
    print()
    print(f"Output: {output_path}")
    print()
    print("NEXT:")
    print("Upload priority_nomad_yiddish_sweep.csv for corpus review.")
    print("Do NOT rebuild the game mod yet.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
