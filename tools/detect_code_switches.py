#!/usr/bin/env python3
"""
FTFL - Global Code-Switch Detector

Scans the COMPLETE Rosetta alignment corpus for dialogue containing
foreign-language material inside the English localization.

This is a discovery tool, not an automatic translator. It deliberately keeps
ambiguous language-family evidence instead of forcing every row into one
language.

Input:
    reference/aligned/localization_alignment.csv

Glossaries:
    reference/glossaries/*_signals.txt
    reference/glossaries/proper_nouns.txt

Output:
    reference/aligned/code_switch_candidates.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


WORD_RE = re.compile(
    r"[A-Za-zÀ-ÖØ-öø-ÿĀ-ž]+(?:['’-][A-Za-zÀ-ÖØ-öø-ÿĀ-ž]+)?"
)
WS_RE = re.compile(r"\s+")

# Words that can be ordinary English should never qualify a row by themselves.
COMMON_ENGLISH = {
    "a", "about", "after", "again", "all", "also", "am", "an", "and",
    "any", "are", "around", "as", "at", "away", "be", "because",
    "been", "before", "being", "big", "but", "by", "can", "could",
    "day", "did", "die", "do", "does", "either", "everyone", "far",
    "for", "forest", "from", "go", "goods", "had", "has", "have",
    "he", "here", "her", "him", "his", "how", "i", "if", "in",
    "into", "is", "it", "its", "just", "know", "like", "man", "me",
    "more", "my", "no", "not", "of", "oh", "on", "one", "only",
    "or", "other", "others", "out", "pay", "plenty", "recently",
    "sell", "she", "should", "so", "something", "that", "the",
    "their", "them", "then", "there", "they", "this", "through",
    "time", "to", "too", "up", "us", "want", "war", "was", "we",
    "were", "what", "when", "where", "who", "why", "will", "with",
    "woods", "would", "you", "young", "your",
}


def clean(text: str) -> str:
    return WS_RE.sub(" ", (text or "").strip())


def words(text: str) -> list[str]:
    return [m.group(0) for m in WORD_RE.finditer(text or "")]


def load_simple_terms(path: Path) -> set[str]:
    terms: set[str] = set()
    if not path.exists():
        return terms

    with path.open("r", encoding="utf-8-sig") as handle:
        for raw in handle:
            value = clean(raw)
            if not value or value.startswith("#"):
                continue
            terms.add(value.casefold())

    return terms


def load_language_signals(glossary_dir: Path) -> dict[str, set[str]]:
    languages: dict[str, set[str]] = {}

    for path in sorted(glossary_dir.glob("*_signals.txt")):
        language = path.stem.removesuffix("_signals")
        terms = load_simple_terms(path)
        if terms:
            languages[language] = terms

    return languages


def build_signal_owners(
    language_signals: dict[str, set[str]],
) -> dict[str, set[str]]:
    owners: dict[str, set[str]] = defaultdict(set)

    for language, terms in language_signals.items():
        for term in terms:
            owners[term].add(language)

    return dict(owners)


def phrase_present(phrase: str, text: str) -> bool:
    return bool(
        re.search(
            r"(?<!\w)" + re.escape(phrase) + r"(?!\w)",
            text,
            flags=re.IGNORECASE,
        )
    )


def proper_name_title_exception(
    token: str,
    token_index: int,
    token_list: list[str],
    proper_nouns: set[str],
) -> bool:
    """
    Suppress obvious title/name constructions such as:
        Herr von Bergow
    while still allowing:
        mein Herr
    """
    if token.casefold() != "herr":
        return False

    remaining = [
        item.casefold()
        for item in token_list[token_index + 1:token_index + 4]
    ]

    if not remaining:
        return False

    if remaining[0] == "von":
        return True

    if remaining[0] in proper_nouns:
        return True

    return False


def analyze_language(
    display: str,
    language: str,
    signals: set[str],
    proper_nouns: set[str],
    signal_owners: dict[str, set[str]],
) -> dict[str, object]:
    token_list = words(display)
    token_lows = [token.casefold() for token in token_list]

    matched: list[str] = []
    strong: list[str] = []
    weak: list[str] = []
    shared: list[str] = []
    suppressed: list[str] = []

    score = 0
    phrase_hits = 0

    multi_word = sorted(
        (term for term in signals if " " in term),
        key=len,
        reverse=True,
    )

    for phrase in multi_word:
        if not phrase_present(phrase, display.casefold()):
            continue

        matched.append(phrase)
        strong.append(phrase)
        phrase_hits += 1
        score += max(4, len(words(phrase)) + 1)

    signal_words = {term for term in signals if " " not in term}
    strong_token_count = 0

    for index, token in enumerate(token_list):
        low = token.casefold()

        if low not in signal_words:
            continue

        if proper_name_title_exception(
            token,
            index,
            token_list,
            proper_nouns,
        ):
            suppressed.append(token)
            continue

        if low in proper_nouns:
            suppressed.append(token)
            continue

        matched.append(token)

        owners = signal_owners.get(low, {language})
        is_shared = len(owners) > 1
        is_non_ascii = any(ord(ch) > 127 for ch in token)
        is_common_english = low in COMMON_ENGLISH

        if is_shared:
            shared.append(token)

        if is_common_english:
            weak.append(token)
            continue

        if is_non_ascii:
            strong.append(token)
            strong_token_count += 1
            score += 2
            continue

        if len(low) >= 5 and not is_shared:
            strong.append(token)
            strong_token_count += 1
            score += 2
            continue

        if len(low) >= 4 and not is_shared:
            strong.append(token)
            strong_token_count += 1
            score += 1
            continue

        weak.append(token)
        score += 1

    adjacent_pairs = 0

    for left, right in zip(token_lows, token_lows[1:]):
        if left not in signal_words or right not in signal_words:
            continue

        if left in COMMON_ENGLISH and right in COMMON_ENGLISH:
            continue

        adjacent_pairs += 1

    if adjacent_pairs:
        score += min(6, adjacent_pairs * 2)

    matched = list(dict.fromkeys(matched))
    strong = list(dict.fromkeys(strong))
    weak = list(dict.fromkeys(weak))
    shared = list(dict.fromkeys(shared))
    suppressed = list(dict.fromkeys(suppressed))

    qualifies = bool(
        phrase_hits
        or (strong_token_count >= 1 and score >= 2)
        or (adjacent_pairs >= 1 and score >= 2)
    )

    return {
        "language": language,
        "score": score,
        "matched": matched,
        "strong": strong,
        "weak": weak,
        "shared": shared,
        "suppressed": suppressed,
        "phrase_hits": phrase_hits,
        "adjacent_pairs": adjacent_pairs,
        "qualifies": qualifies,
    }


def english_signal_count(display: str) -> int:
    return sum(
        1
        for token in words(display)
        if token.casefold() in COMMON_ENGLISH
    )


def language_status(results: list[dict[str, object]]) -> str:
    if len(results) <= 1:
        return "single"

    hit_sets = [
        {str(x).casefold() for x in result["matched"]}
        for result in results
    ]

    shared_evidence = set.intersection(*hit_sets) if hit_sets else set()

    if shared_evidence:
        return "ambiguous_overlap"

    return "multiple_language_evidence"


def classify(best_score: int, english_hits: int) -> str:
    if english_hits >= 2:
        return "mixed_language"

    if english_hits == 0 and best_score >= 4:
        return "likely_full_foreign"

    return "foreign_fragment"


def evidence_text(result: dict[str, object]) -> str:
    language = str(result["language"])
    score = int(result["score"])
    matched = ", ".join(str(x) for x in result["matched"])
    return f"{language}={score}[{matched}]"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Scan the entire FTFL Rosetta corpus for mixed/foreign dialogue "
            "without forcing ambiguous language-family matches."
        )
    )

    parser.add_argument(
        "--input",
        default="reference/aligned/localization_alignment.csv",
    )
    parser.add_argument(
        "--glossary-dir",
        default="reference/glossaries",
    )
    parser.add_argument(
        "--proper-nouns",
        default="reference/glossaries/proper_nouns.txt",
    )
    parser.add_argument(
        "--output",
        default="reference/aligned/code_switch_candidates.csv",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=2,
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    glossary_dir = Path(args.glossary_dir)
    proper_path = Path(args.proper_nouns)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"ERROR: Missing alignment: {input_path}", file=sys.stderr)
        return 2

    language_signals = load_language_signals(glossary_dir)

    if not language_signals:
        print(
            "ERROR: No *_signals.txt glossaries found.",
            file=sys.stderr,
        )
        return 3

    proper_nouns = load_simple_terms(proper_path)
    signal_owners = build_signal_owners(language_signals)

    print("Language signal sets:")
    for language, signals in language_signals.items():
        print(f"  {language:<16} {len(signals):>5,}")

    overlapping_terms = {
        term: owners
        for term, owners in signal_owners.items()
        if len(owners) > 1
    }

    print(f"Proper noun entries: {len(proper_nouns):,}")
    print(f"Cross-language signal overlaps: {len(overlapping_terms):,}")

    try:
        csv.field_size_limit(sys.maxsize)
    except OverflowError:
        csv.field_size_limit(2_147_483_647)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    out_fields = [
        "localization_key",
        "classification",
        "detected_language",
        "detected_languages",
        "language_status",
        "foreign_score",
        "english_signal_count",
        "matched_foreign_signals",
        "strong_foreign_signals",
        "weak_foreign_signals",
        "shared_foreign_signals",
        "suppressed_name_signals",
        "language_evidence",
        "English_reference",
        "English_display",
    ]

    scanned = 0
    written = 0
    class_counts = Counter()
    language_counts = Counter()
    status_counts = Counter()

    with input_path.open("r", encoding="utf-8-sig", newline="") as src:
        reader = csv.DictReader(src)

        if not reader.fieldnames:
            print("ERROR: alignment has no header", file=sys.stderr)
            return 4

        required = {
            "localization_key",
            "English_reference",
            "English_display",
        }

        missing = required - set(reader.fieldnames)

        if missing:
            print(
                "ERROR: Missing columns: "
                + ", ".join(sorted(missing)),
                file=sys.stderr,
            )
            return 5

        with output_path.open(
            "w",
            encoding="utf-8-sig",
            newline="",
        ) as dst:
            writer = csv.DictWriter(dst, fieldnames=out_fields)
            writer.writeheader()

            for row in reader:
                scanned += 1

                display = clean(row.get("English_display", ""))

                if not display:
                    continue

                english_hits = english_signal_count(display)
                analyses: list[dict[str, object]] = []

                for language, signals in language_signals.items():
                    result = analyze_language(
                        display,
                        language,
                        signals,
                        proper_nouns,
                        signal_owners,
                    )

                    if (
                        bool(result["qualifies"])
                        and int(result["score"]) >= args.min_score
                    ):
                        analyses.append(result)

                if not analyses:
                    continue

                analyses.sort(
                    key=lambda item: (
                        -int(item["score"]),
                        str(item["language"]),
                    )
                )

                best_score = int(analyses[0]["score"])
                detected_languages = [
                    str(result["language"])
                    for result in analyses
                ]

                status = language_status(analyses)
                classification = classify(
                    best_score,
                    english_hits,
                )

                all_matched = list(
                    dict.fromkeys(
                        str(signal)
                        for result in analyses
                        for signal in result["matched"]
                    )
                )
                all_strong = list(
                    dict.fromkeys(
                        str(signal)
                        for result in analyses
                        for signal in result["strong"]
                    )
                )
                all_weak = list(
                    dict.fromkeys(
                        str(signal)
                        for result in analyses
                        for signal in result["weak"]
                    )
                )
                all_shared = list(
                    dict.fromkeys(
                        str(signal)
                        for result in analyses
                        for signal in result["shared"]
                    )
                )
                all_suppressed = list(
                    dict.fromkeys(
                        str(signal)
                        for result in analyses
                        for signal in result["suppressed"]
                    )
                )

                writer.writerow({
                    "localization_key": row.get("localization_key", ""),
                    "classification": classification,
                    "detected_language": detected_languages[0],
                    "detected_languages": "; ".join(detected_languages),
                    "language_status": status,
                    "foreign_score": best_score,
                    "english_signal_count": english_hits,
                    "matched_foreign_signals": "; ".join(all_matched),
                    "strong_foreign_signals": "; ".join(all_strong),
                    "weak_foreign_signals": "; ".join(all_weak),
                    "shared_foreign_signals": "; ".join(all_shared),
                    "suppressed_name_signals": "; ".join(all_suppressed),
                    "language_evidence": " | ".join(
                        evidence_text(result)
                        for result in analyses
                    ),
                    "English_reference": clean(
                        row.get("English_reference", "")
                    ),
                    "English_display": display,
                })

                written += 1
                class_counts[classification] += 1
                status_counts[status] += 1

                for language in detected_languages:
                    language_counts[language] += 1

                if scanned % 25000 == 0:
                    print(
                        f"Scanned {scanned:,} rows... "
                        f"{written:,} candidates"
                    )

    print()
    print("Global code-switch scan complete.")
    print(f"Rows scanned:     {scanned:,}")
    print(f"Candidates found: {written:,}")

    print()
    print("Classification counts:")
    for label, count in class_counts.most_common():
        print(f"  {label:<28} {count:>7,}")

    print()
    print("Language-status counts:")
    for status, count in status_counts.most_common():
        print(f"  {status:<28} {count:>7,}")

    print()
    print("Detected language evidence:")
    for language, count in language_counts.most_common():
        print(f"  {language:<16} {count:>7,}")

    print()
    print(f"Output: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
