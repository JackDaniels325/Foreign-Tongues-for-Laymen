#!/usr/bin/env python3
"""
FTFL - Global Code-Switch Detector

Scans the COMPLETE Rosetta alignment corpus for dialogue containing
foreign-language material inside the English localization.

This detector is deliberately independent from the older candidate score
threshold. Its purpose is coverage.

Input:
    reference/aligned/localization_alignment.csv

Glossaries:
    reference/glossaries/*_signals.txt
    reference/glossaries/proper_nouns.txt

Output:
    reference/aligned/code_switch_candidates.csv

Nothing is automatically translated or approved.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path


WORD_RE = re.compile(
    r"[A-Za-zÀ-ÖØ-öø-ÿĀ-ž]+(?:['’-][A-Za-zÀ-ÖØ-öø-ÿĀ-ž]+)?"
)

WS_RE = re.compile(r"\s+")


COMMON_ENGLISH = {
    "a", "about", "after", "again", "all", "am", "an", "and",
    "any", "are", "around", "as", "at", "away", "be", "because",
    "been", "before", "being", "big", "but", "by", "can", "could",
    "day", "did", "do", "does", "either", "everyone", "far", "for",
    "forest", "from", "go", "goods", "had", "has", "have", "he",
    "here", "her", "him", "his", "how", "i", "if", "in", "into",
    "is", "it", "its", "just", "know", "like", "me", "more", "my",
    "no", "not", "of", "oh", "on", "one", "only", "or", "other",
    "others", "out", "pay", "plenty", "recently", "sell", "she",
    "should", "so", "something", "that", "the", "their", "them",
    "then", "there", "they", "this", "through", "time", "to", "too",
    "up", "us", "want", "war", "was", "we", "were", "what", "when",
    "where", "who", "why", "will", "with", "woods", "would", "you",
    "young", "your",
}


def clean(text: str) -> str:
    return WS_RE.sub(" ", (text or "").strip())


def words(text: str) -> list[str]:
    return [
        match.group(0)
        for match in WORD_RE.finditer(text or "")
    ]


def load_simple_terms(path: Path) -> set[str]:
    result: set[str] = set()

    if not path.exists():
        return result

    with path.open(
        "r",
        encoding="utf-8-sig",
    ) as handle:

        for raw in handle:
            value = clean(raw)

            if not value:
                continue

            if value.startswith("#"):
                continue

            result.add(value.casefold())

    return result


def load_language_signals(
    glossary_dir: Path,
) -> dict[str, set[str]]:

    languages: dict[str, set[str]] = {}

    for path in sorted(
        glossary_dir.glob("*_signals.txt")
    ):
        language = path.stem.removesuffix(
            "_signals"
        )

        terms = load_simple_terms(path)

        if terms:
            languages[language] = terms

    return languages


def phrase_present(
    phrase: str,
    text: str,
) -> bool:

    phrase = phrase.casefold()
    text = text.casefold()

    if " " in phrase:
        pattern = (
            r"(?<!\w)"
            + re.escape(phrase)
            + r"(?!\w)"
        )
    else:
        pattern = (
            r"(?<!\w)"
            + re.escape(phrase)
            + r"(?!\w)"
        )

    return bool(
        re.search(
            pattern,
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
        Grüß Gott, mein Herr
    """

    low = token.casefold()

    if low != "herr":
        return False

    remaining = [
        item.casefold()
        for item in token_list[
            token_index + 1:
            token_index + 4
        ]
    ]

    if not remaining:
        return False

    if remaining[0] == "von":

        if len(remaining) >= 2:
            if remaining[1] in proper_nouns:
                return True

        # Even if the proper-noun glossary has not learned the surname yet,
        # "Herr von X" is much more likely to be a title/name construction.
        return True

    return False


def analyze_language(
    display: str,
    language: str,
    signals: set[str],
    proper_nouns: set[str],
) -> tuple[
    int,
    list[str],
    list[str],
]:
    """
    Returns:
        signal_score
        matched signals
        suppressed proper-name/title signals
    """

    token_list = words(display)

    matched: list[str] = []
    suppressed: list[str] = []

    score = 0

    # Strong multi-word phrases first.
    multi_word = sorted(
        (
            term
            for term in signals
            if " " in term
        ),
        key=len,
        reverse=True,
    )

    for phrase in multi_word:

        if phrase_present(
            phrase,
            display,
        ):
            matched.append(phrase)

            token_count = len(
                words(phrase)
            )

            score += max(
                3,
                token_count + 1,
            )

    # Individual word signals.
    signal_words = {
        term
        for term in signals
        if " " not in term
    }

    for index, token in enumerate(
        token_list
    ):
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

        # Standalone proper nouns should not become foreign evidence.
        if low in proper_nouns:
            suppressed.append(token)
            continue

        matched.append(token)

        # Accented/non-ASCII foreign words are strong evidence.
        if any(
            ord(ch) > 127
            for ch in token
        ):
            score += 2
        else:
            score += 1

    # Reward adjacent foreign-language words.
    lows = [
        token.casefold()
        for token in token_list
    ]

    adjacent_pairs = 0

    for left, right in zip(
        lows,
        lows[1:],
    ):
        if (
            left in signal_words
            and right in signal_words
        ):
            adjacent_pairs += 1

    if adjacent_pairs:
        score += min(
            6,
            adjacent_pairs * 2,
        )

    # Deduplicate while retaining order.
    matched = list(
        dict.fromkeys(matched)
    )

    suppressed = list(
        dict.fromkeys(suppressed)
    )

    return (
        score,
        matched,
        suppressed,
    )


def english_signal_count(
    display: str,
) -> int:

    return sum(
        1
        for token in words(display)
        if token.casefold() in COMMON_ENGLISH
    )


def classify(
    foreign_score: int,
    foreign_hits: list[str],
    english_hits: int,
) -> str:

    if not foreign_hits:
        return "none"

    if (
        english_hits >= 2
        and foreign_score >= 2
    ):
        return "mixed_language"

    if (
        english_hits >= 1
        and foreign_score >= 3
    ):
        return "mixed_language"

    if (
        english_hits == 0
        and foreign_score >= 4
    ):
        return "likely_full_foreign"

    if foreign_score >= 2:
        return "foreign_fragment"

    return "weak_signal"


def main() -> int:

    parser = argparse.ArgumentParser(
        description=(
            "Scan the entire FTFL Rosetta corpus "
            "for mixed-language dialogue."
        )
    )

    parser.add_argument(
        "--input",
        default=(
            "reference/aligned/"
            "localization_alignment.csv"
        ),
    )

    parser.add_argument(
        "--glossary-dir",
        default=(
            "reference/glossaries"
        ),
    )

    parser.add_argument(
        "--proper-nouns",
        default=(
            "reference/glossaries/"
            "proper_nouns.txt"
        ),
    )

    parser.add_argument(
        "--output",
        default=(
            "reference/aligned/"
            "code_switch_candidates.csv"
        ),
    )

    parser.add_argument(
        "--min-score",
        type=int,
        default=2,
    )

    args = parser.parse_args()

    input_path = Path(
        args.input
    )

    glossary_dir = Path(
        args.glossary_dir
    )

    proper_path = Path(
        args.proper_nouns
    )

    output_path = Path(
        args.output
    )

    if not input_path.exists():
        print(
            f"ERROR: Missing alignment: "
            f"{input_path}",
            file=sys.stderr,
        )
        return 2

    language_signals = (
        load_language_signals(
            glossary_dir
        )
    )

    if not language_signals:
        print(
            "ERROR: No *_signals.txt "
            "glossaries found.",
            file=sys.stderr,
        )
        return 3

    proper_nouns = load_simple_terms(
        proper_path
    )

    print(
        "Language signal sets:"
    )

    for language, signals in (
        language_signals.items()
    ):
        print(
            f"  {language:<16} "
            f"{len(signals):>5,}"
        )

    print(
        f"Proper noun entries: "
        f"{len(proper_nouns):,}"
    )

    try:
        csv.field_size_limit(
            sys.maxsize
        )
    except OverflowError:
        csv.field_size_limit(
            2_147_483_647
        )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    out_fields = [
        "localization_key",
        "classification",
        "detected_language",
        "foreign_score",
        "english_signal_count",
        "matched_foreign_signals",
        "suppressed_name_signals",
        "English_reference",
        "English_display",
    ]

    scanned = 0
    written = 0

    class_counts = Counter()
    language_counts = Counter()

    with input_path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as src:

        reader = csv.DictReader(
            src
        )

        if not reader.fieldnames:
            print(
                "ERROR: alignment has no header",
                file=sys.stderr,
            )
            return 4

        required = {
            "localization_key",
            "English_reference",
            "English_display",
        }

        missing = (
            required
            - set(reader.fieldnames)
        )

        if missing:
            print(
                "ERROR: Missing columns: "
                + ", ".join(
                    sorted(missing)
                ),
                file=sys.stderr,
            )
            return 5

        with output_path.open(
            "w",
            encoding="utf-8-sig",
            newline="",
        ) as dst:

            writer = csv.DictWriter(
                dst,
                fieldnames=out_fields,
            )

            writer.writeheader()

            for row in reader:

                scanned += 1

                display = clean(
                    row.get(
                        "English_display",
                        "",
                    )
                )

                if not display:
                    continue

                english_hits = (
                    english_signal_count(
                        display
                    )
                )

                best_language = ""
                best_score = 0
                best_matches: list[str] = []
                best_suppressed: list[str] = []

                for (
                    language,
                    signals,
                ) in language_signals.items():

                    (
                        score,
                        matches,
                        suppressed,
                    ) = analyze_language(
                        display,
                        language,
                        signals,
                        proper_nouns,
                    )

                    if score > best_score:
                        best_language = language
                        best_score = score
                        best_matches = matches
                        best_suppressed = suppressed

                classification = classify(
                    best_score,
                    best_matches,
                    english_hits,
                )

                if best_score < args.min_score:
                    continue

                if classification == "none":
                    continue

                writer.writerow({
                    "localization_key":
                        row.get(
                            "localization_key",
                            "",
                        ),

                    "classification":
                        classification,

                    "detected_language":
                        best_language,

                    "foreign_score":
                        best_score,

                    "english_signal_count":
                        english_hits,

                    "matched_foreign_signals":
                        "; ".join(
                            best_matches
                        ),

                    "suppressed_name_signals":
                        "; ".join(
                            best_suppressed
                        ),

                    "English_reference":
                        clean(
                            row.get(
                                "English_reference",
                                "",
                            )
                        ),

                    "English_display":
                        display,
                })

                written += 1

                class_counts[
                    classification
                ] += 1

                language_counts[
                    best_language
                ] += 1

                if scanned % 25000 == 0:
                    print(
                        f"Scanned "
                        f"{scanned:,} rows..."
                    )

    print()
    print(
        "Global code-switch scan complete."
    )

    print(
        f"Rows scanned:     "
        f"{scanned:,}"
    )

    print(
        f"Candidates found: "
        f"{written:,}"
    )

    print()
    print(
        "Classification counts:"
    )

    for label, count in (
        class_counts.most_common()
    ):
        print(
            f"  {label:<24} "
            f"{count:>7,}"
        )

    print()
    print(
        "Detected languages:"
    )

    for language, count in (
        language_counts.most_common()
    ):
        print(
            f"  {language:<16} "
            f"{count:>7,}"
        )

    print()
    print(
        f"Output: "
        f"{output_path}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )