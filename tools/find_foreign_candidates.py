#!/usr/bin/env python3
"""
FTFL Rosetta - Foreign Phrase Candidate Finder

Scans reference/aligned/localization_alignment.csv and writes a smaller review
queue containing English dialogue rows that may include intentionally preserved
foreign-language text.

This is a heuristic candidate finder, not an automatic translator.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from collections import Counter

WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿĀ-ž]+(?:['’-][A-Za-zÀ-ÖØ-öø-ÿĀ-ž]+)?")
NON_ASCII_ALPHA_RE = re.compile(r"[^\x00-\x7F]")
WS_RE = re.compile(r"\s+")

# Common English words are weak evidence when they appear unchanged in other locales.
COMMON_ENGLISH = {
    "a","an","and","are","as","at","be","been","but","by","can","could","did","do","does",
    "for","from","had","has","have","he","her","here","hers","him","his","how","i","if",
    "in","into","is","it","its","me","my","no","not","of","on","or","our","out","she",
    "so","that","the","their","them","then","there","they","this","to","too","up","us",
    "was","we","were","what","when","where","who","why","will","with","would","you","your"
}

def clean(text: str) -> str:
    return WS_RE.sub(" ", (text or "").strip())

def tokens(text: str) -> list[str]:
    return [m.group(0) for m in WORD_RE.finditer(text or "")]

def candidate_preserved_tokens(english_text: str, other_displays: dict[str, str]) -> tuple[list[str], list[str]]:
    """
    Find distinctive English-display tokens that survive unchanged in several
    non-English localized display strings. This is useful for names, Latin,
    German, Romani, etc. that localization intentionally preserves.
    """
    eng_tokens = tokens(english_text)
    distinctive = []

    for tok in eng_tokens:
        low = tok.lower()
        if len(tok) < 4:
            continue
        if low in COMMON_ENGLISH:
            continue
        distinctive.append(tok)

    counts = Counter()
    locales_for = {}

    for tok in distinctive:
        pattern = re.compile(rf"(?<!\w){re.escape(tok)}(?!\w)", re.IGNORECASE)
        matched_locales = [
            locale for locale, text in other_displays.items()
            if text and pattern.search(text)
        ]
        if matched_locales:
            counts[tok] = len(matched_locales)
            locales_for[tok] = matched_locales

    strong = [tok for tok, n in counts.items() if n >= 3]
    locales = sorted({loc for tok in strong for loc in locales_for.get(tok, [])})
    return strong, locales

def score_row(row: dict[str, str], display_cols: list[str]) -> tuple[int, list[str], list[str], list[str]]:
    eng_ref = clean(row.get("English_reference", ""))
    eng_disp = clean(row.get("English_display", ""))

    if not eng_disp:
        return 0, [], [], []

    score = 0
    reasons = []

    if NON_ASCII_ALPHA_RE.search(eng_disp):
        score += 3
        reasons.append("non-ASCII character(s) in English display")

    if eng_ref and eng_ref != eng_disp:
        score += 1
        reasons.append("English reference/display differ")

    other = {
        col.removesuffix("_display"): clean(row.get(col, ""))
        for col in display_cols
        if col != "English_display"
    }

    preserved, locales = candidate_preserved_tokens(eng_disp, other)
    if preserved:
        score += min(6, 2 + len(preserved))
        reasons.append(
            f"token(s) preserved across 3+ localized displays: {', '.join(preserved[:8])}"
        )

    # Stronger signal if the same unusual token is also present in English reference.
    ref_low = eng_ref.lower()
    in_ref = [tok for tok in preserved if tok.lower() in ref_low]
    if in_ref:
        score += 1
        reasons.append("preserved token(s) also present in English reference")

    return score, reasons, preserved, locales

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Find likely foreign-language dialogue candidates in the FTFL Rosetta alignment corpus."
    )
    parser.add_argument(
        "--input",
        default="reference/aligned/localization_alignment.csv",
        help="Input Rosetta alignment CSV."
    )
    parser.add_argument(
        "--output",
        default="reference/aligned/foreign_candidates.csv",
        help="Output candidate review CSV."
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=3,
        help="Minimum heuristic score to include (default: 3)."
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"ERROR: Input not found: {input_path}", file=sys.stderr)
        return 2

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Large XML-derived fields can exceed the default CSV field limit on some systems.
    try:
        csv.field_size_limit(sys.maxsize)
    except OverflowError:
        csv.field_size_limit(2_147_483_647)

    scanned = 0
    written = 0
    score_counts = Counter()

    with input_path.open("r", encoding="utf-8-sig", newline="") as src:
        reader = csv.DictReader(src)
        if not reader.fieldnames:
            print("ERROR: CSV has no header.", file=sys.stderr)
            return 3

        required = {"localization_key", "English_reference", "English_display"}
        missing = required - set(reader.fieldnames)
        if missing:
            print(f"ERROR: Missing required columns: {', '.join(sorted(missing))}", file=sys.stderr)
            return 4

        display_cols = [c for c in reader.fieldnames if c.endswith("_display")]

        out_fields = [
            "localization_key",
            "score",
            "reasons",
            "English_reference",
            "English_display",
            "preserved_tokens",
            "preserved_in_locales",
        ]

        with output_path.open("w", encoding="utf-8-sig", newline="") as dst:
            writer = csv.DictWriter(dst, fieldnames=out_fields)
            writer.writeheader()

            for row in reader:
                scanned += 1
                score, reasons, preserved, locales = score_row(row, display_cols)

                if score >= args.min_score:
                    writer.writerow({
                        "localization_key": row.get("localization_key", ""),
                        "score": score,
                        "reasons": " | ".join(reasons),
                        "English_reference": clean(row.get("English_reference", "")),
                        "English_display": clean(row.get("English_display", "")),
                        "preserved_tokens": "; ".join(preserved),
                        "preserved_in_locales": "; ".join(locales),
                    })
                    written += 1
                    score_counts[score] += 1

                if scanned % 25000 == 0:
                    print(f"Scanned {scanned:,} rows... {written:,} candidates")

    print()
    print("Foreign candidate scan complete.")
    print(f"Rows scanned: {scanned:,}")
    print(f"Candidates written: {written:,}")
    print(f"Minimum score: {args.min_score}")
    if score_counts:
        print("Score distribution:")
        for score in sorted(score_counts):
            print(f"  {score}: {score_counts[score]:,}")
    print(f"Output: {output_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
