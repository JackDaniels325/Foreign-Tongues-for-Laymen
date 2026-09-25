#!/usr/bin/env python3
"""
Foreign Tongues for Laymen - routine toolbox front end.

v0.2.6 changes the default authored-dialogue workflow from signal-first
scanning to source-driven discovery from localization_alignment.csv.

Normal use:
    python .\tools\ftfl.py scan
    python .\tools\ftfl.py build --version 0.2.6
    python .\tools\ftfl.py all --version 0.2.6

The signal/glossary files are supporting evidence only. They are not the
primary discovery gate.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import re
import sys
import unicodedata
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
REPO = TOOLS_DIR.parent

ALIGNMENT = REPO / "reference" / "aligned" / "localization_alignment.csv"
SOURCE_CANDIDATES = REPO / "reference" / "aligned" / "source_discovery_candidates.csv"
UNRESOLVED = REPO / "reference" / "aligned" / "unresolved_families.csv"
STATUS_DIR = REPO / "reference" / "status"
REGRESSION_STATUS = STATUS_DIR / "regression_review.csv"
APPROVED = REPO / "corpus" / "approved.csv"
PROPER_NOUNS = REPO / "reference" / "glossaries" / "proper_nouns.txt"
GLOSSARY_DIR = REPO / "reference" / "glossaries"

TOKEN_RE = re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*", re.UNICODE)

# These are regression alarms only. They do not teach discovery what a
# foreign phrase is and they do not provide translations. If a phrase exists
# in the source corpus but source-driven discovery fails to surface it, scan
# exits with an error instead of sending the tester into the game.
REGRESSION_PHRASES = (
    "Gut margn!",
    "T-aves bakhtalo, Henry! You are the best!",
    "T'aves bachtalo!",
    "Te del o Del lacho dives!",
    "Kames vareso?",
    "Masa u-matan tov!",
    "Oh Devla!",
    "So rodes?",
)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("’", "'").replace("‐", "-").replace("‑", "-")
    return " ".join(text.split()).casefold()


def normalize_token(token: str) -> str:
    return normalize(token).strip("'-")


def tokens(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall(text or "") if normalize_token(t)]


def load_word_list(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    out: set[str] = set()
    with path.open("r", encoding="utf-8-sig") as handle:
        for raw in handle:
            value = raw.split("#", 1)[0].strip()
            if value:
                out.add(normalize(value))
    return out


def load_signal_phrases() -> dict[str, set[str]]:
    signals: dict[str, set[str]] = {}
    if not GLOSSARY_DIR.is_dir():
        return signals
    for path in sorted(GLOSSARY_DIR.glob("*_signals.txt")):
        language = path.stem.removesuffix("_signals")
        values = load_word_list(path)
        if values:
            signals[language] = values
    return signals


def load_approved() -> tuple[set[str], set[str], dict[str, dict[str, str]]]:
    if not APPROVED.is_file():
        raise SystemExit(f"Missing approved corpus: {APPROVED}")

    keys: set[str] = set()
    full_families: set[str] = set()
    rows: dict[str, dict[str, str]] = {}

    with APPROVED.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise SystemExit("approved.csv has no header")

        for row in reader:
            key = (row.get("localization_key") or "").strip()
            display = (row.get("original_display_text") or "").strip()
            line_type = (row.get("line_type") or "").strip().lower()
            if not key:
                continue
            keys.add(key)
            rows[key] = row
            if display and line_type in {"full", "full_foreign", "full-foreign", "foreign"}:
                full_families.add(normalize(display))

    return keys, full_families, rows


def signal_evidence(display: str, signals: dict[str, set[str]]) -> list[str]:
    haystack = f" {normalize(display)} "
    hits: list[str] = []
    for language, phrases in signals.items():
        for phrase in phrases:
            if not phrase:
                continue
            # Phrase matching is deliberately secondary evidence. Word-like
            # boundaries reduce common substring false positives.
            if f" {phrase} " in haystack or haystack.startswith(f" {phrase} ") or haystack.endswith(f" {phrase} "):
                hits.append(language)
                break
    return sorted(set(hits))


def source_discovery() -> tuple[int, dict[str, str]]:
    if not ALIGNMENT.is_file():
        raise SystemExit(
            "Missing localization_alignment.csv.\n"
            "Rebuild the extracted localization alignment first."
        )

    proper_nouns = load_word_list(PROPER_NOUNS)
    signals = load_signal_phrases()
    rows_out: list[dict[str, str]] = []
    corpus_by_normalized_display: dict[str, tuple[str, str]] = {}

    with ALIGNMENT.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise SystemExit("localization_alignment.csv has no header")

        fields = set(reader.fieldnames)
        required = {"localization_key", "English_display", "English_reference"}
        missing = required - fields
        if missing:
            raise SystemExit(
                "localization_alignment.csv missing columns: "
                + ", ".join(sorted(missing))
            )

        other_display_fields = [
            name for name in reader.fieldnames
            if name.endswith("_display") and name != "English_display"
        ]

        if not other_display_fields:
            raise SystemExit("No non-English *_display columns found in alignment")

        for row in reader:
            key = (row.get("localization_key") or "").strip()
            display = (row.get("English_display") or "").strip()
            reference = (row.get("English_reference") or "").strip()
            if not key or not display:
                continue

            display_norm = normalize(display)
            corpus_by_normalized_display.setdefault(display_norm, (key, display))

            display_tokens = tokens(display)
            if not display_tokens:
                continue

            normalized_display_tokens = [normalize_token(t) for t in display_tokens]
            preservation: Counter[str] = Counter()
            preserving_languages: defaultdict[str, list[str]] = defaultdict(list)

            for field in other_display_fields:
                foreign_display = (row.get(field) or "").strip()
                if not foreign_display:
                    continue
                foreign_tokens = {normalize_token(t) for t in tokens(foreign_display)}
                language = field[:-8]
                for token in normalized_display_tokens:
                    if token and token in foreign_tokens:
                        preservation[token] += 1
                        preserving_languages[token].append(language)

            preserved: list[str] = []
            for original_token, token in zip(display_tokens, normalized_display_tokens):
                count = preservation[token]
                if not token:
                    continue
                if token in proper_nouns:
                    continue
                if len(token) <= 2 and count < 5:
                    continue
                if count >= 3:
                    preserved.append(original_token)

            # Keep order, remove repeats.
            preserved = list(dict.fromkeys(preserved))
            preserved_norm = [normalize_token(t) for t in preserved]
            max_preservation = max((preservation[t] for t in preserved_norm), default=0)
            total_preservation = sum(preservation[t] for t in set(preserved_norm))
            direct_reference_diff = bool(reference and normalize(reference) != display_norm)
            signal_hits = signal_evidence(display, signals)

            # Source-driven admission rules. Signal evidence can strengthen a
            # row but is not required. Cross-language preservation is the gate.
            admitted = False
            reasons: list[str] = []

            if len(preserved) >= 2 and max_preservation >= 3:
                admitted = True
                reasons.append("multi_token_cross_language_preservation")
            elif len(preserved) == 1 and max_preservation >= 6:
                admitted = True
                reasons.append("strong_single_token_preservation")
            elif direct_reference_diff and preserved and max_preservation >= 2:
                admitted = True
                reasons.append("reference_difference_plus_preservation")

            if not admitted:
                continue

            if direct_reference_diff:
                reasons.append("english_reference_differs")
            if signal_hits:
                reasons.append("signal_support")

            score = (
                len(preserved) * 4
                + min(max_preservation, 10)
                + min(total_preservation // 3, 10)
                + (3 if direct_reference_diff else 0)
                + len(signal_hits)
            )

            language_evidence: set[str] = set()
            for token in set(preserved_norm):
                language_evidence.update(preserving_languages[token])

            rows_out.append({
                "localization_key": key,
                "English_display": display,
                "English_reference": reference,
                "preserved_tokens": "; ".join(preserved),
                "preserved_in_languages": "; ".join(sorted(language_evidence)),
                "max_language_preservation": str(max_preservation),
                "source_score": str(score),
                "direct_reference_diff": "yes" if direct_reference_diff else "no",
                "signal_languages": "; ".join(signal_hits),
                "discovery_reasons": "; ".join(reasons),
            })

    rows_out.sort(
        key=lambda r: (
            -int(r["source_score"]),
            r["English_display"].casefold(),
            r["localization_key"],
        )
    )

    SOURCE_CANDIDATES.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "localization_key",
        "English_display",
        "English_reference",
        "preserved_tokens",
        "preserved_in_languages",
        "max_language_preservation",
        "source_score",
        "direct_reference_diff",
        "signal_languages",
        "discovery_reasons",
    ]
    with SOURCE_CANDIDATES.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)

    candidate_displays = {normalize(row["English_display"]) for row in rows_out}
    regression_status: dict[str, str] = {}
    regression_rows: list[dict[str, str]] = []
    failures: list[str] = []

    for phrase in REGRESSION_PHRASES:
        needle = normalize(phrase)
        exact = corpus_by_normalized_display.get(needle)
        contained = [
            (display_norm, value)
            for display_norm, value in corpus_by_normalized_display.items()
            if needle and needle in display_norm
        ]
        match = exact or (contained[0][1] if contained else None)
        exists = match is not None
        surfaced = any(needle in candidate for candidate in candidate_displays)
        if not exists:
            status = "NOT_FOUND_IN_ALIGNMENT"
        elif surfaced:
            status = "SURFACED"
        else:
            status = "MISSED_BY_SOURCE_DISCOVERY"
            failures.append(phrase)
        regression_status[phrase] = status
        regression_rows.append({
            "phrase": phrase,
            "status": status,
            "localization_key": match[0] if match else "",
            "matched_display": match[1] if match else "",
        })

    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    with REGRESSION_STATUS.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["phrase", "status", "localization_key", "matched_display"],
        )
        writer.writeheader()
        writer.writerows(regression_rows)

    print()
    print("=" * 72)
    print("FTFL SOURCE-DRIVEN DISCOVERY")
    print("=" * 72)
    print(f"Candidates: {len(rows_out):,}")
    print(f"Output: {SOURCE_CANDIDATES.relative_to(REPO)}")
    print(f"Status: {REGRESSION_STATUS.relative_to(REPO)}")
    print()
    print("Regression discovery gate:")
    for phrase, status in regression_status.items():
        print(f"  {status:28} {phrase}")

    if failures:
        raise SystemExit(
            "\nSOURCE DISCOVERY REGRESSION: known authored-dialogue phrases exist "
            "in the alignment but were not surfaced.\n"
            "Do not play-test. Fix source discovery first.\n  - "
            + "\n  - ".join(failures)
        )

    return len(rows_out), regression_status


def write_unresolved_report() -> int:
    approved_keys, approved_full_families, _ = load_approved()
    if not SOURCE_CANDIDATES.is_file():
        raise SystemExit("Run source discovery before building unresolved report")

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    with SOURCE_CANDIDATES.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            key = (row.get("localization_key") or "").strip()
            display = (row.get("English_display") or "").strip()
            if not key or not display:
                continue
            family = normalize(display)
            if key in approved_keys or family in approved_full_families:
                continue
            grouped[family].append(row)

    output_rows: list[dict[str, str]] = []
    for family, members in grouped.items():
        members.sort(key=lambda r: r["localization_key"])
        rep = members[0]
        max_score = max(int(m.get("source_score") or 0) for m in members)
        tokens_seen: list[str] = []
        language_seen: set[str] = set()
        reasons_seen: set[str] = set()
        signal_seen: set[str] = set()

        for member in members:
            for token in (member.get("preserved_tokens") or "").split(";"):
                token = token.strip()
                if token and token not in tokens_seen:
                    tokens_seen.append(token)
            for language in (member.get("preserved_in_languages") or "").split(";"):
                if language.strip():
                    language_seen.add(language.strip())
            for reason in (member.get("discovery_reasons") or "").split(";"):
                if reason.strip():
                    reasons_seen.add(reason.strip())
            for language in (member.get("signal_languages") or "").split(";"):
                if language.strip():
                    signal_seen.add(language.strip())

        output_rows.append({
            "representative_key": rep["localization_key"],
            "family_size": str(len(members)),
            "source_score": str(max_score),
            "preserved_tokens": "; ".join(tokens_seen),
            "preserved_in_languages": "; ".join(sorted(language_seen)),
            "signal_languages": "; ".join(sorted(signal_seen)),
            "discovery_reasons": "; ".join(sorted(reasons_seen)),
            "English_display": rep["English_display"],
            "English_reference": rep.get("English_reference") or "",
            "review_status": "NEEDS_REVIEW",
            "source_language": "",
            "verified_meaning": "",
            "notes": "",
        })

    output_rows.sort(
        key=lambda r: (
            -int(r["family_size"]),
            -int(r["source_score"]),
            r["English_display"].casefold(),
        )
    )

    fields = [
        "representative_key",
        "family_size",
        "source_score",
        "preserved_tokens",
        "preserved_in_languages",
        "signal_languages",
        "discovery_reasons",
        "English_display",
        "English_reference",
        "review_status",
        "source_language",
        "verified_meaning",
        "notes",
    ]
    UNRESOLVED.parent.mkdir(parents=True, exist_ok=True)
    with UNRESOLVED.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)

    print()
    print("=" * 72)
    print("FTFL UNRESOLVED FAMILY REPORT")
    print("=" * 72)
    print(f"Approved explicit keys: {len(approved_keys):,}")
    print(f"Approved full families: {len(approved_full_families):,}")
    print(f"New unresolved families: {len(output_rows):,}")
    print(f"Output: {UNRESOLVED.relative_to(REPO)}")
    return len(output_rows)


def run_scan() -> int:
    source_discovery()
    return write_unresolved_report()


def run_build(version: str, allow_source_mismatch: bool) -> int:
    if str(TOOLS_DIR) not in sys.path:
        sys.path.insert(0, str(TOOLS_DIR))
    builder = importlib.import_module("build_mod_patch")

    # Keep the tested inline-safe presentation in the front end until the
    # builder itself is cleaned up in a later maintenance pass. KCD2 flattened
    # XML <br/> in actual subtitle rendering.
    def apply_full_foreign_inline(display_cell, original: str, meaning: str) -> str:
        rendered = f"{original} — [English] {meaning}"
        builder.clear_cell(display_cell)
        display_cell.text = rendered
        return rendered

    builder.apply_full_foreign = apply_full_foreign_inline

    old_argv = sys.argv[:]
    try:
        sys.argv = [
            str(TOOLS_DIR / "build_mod_patch.py"),
            "--repo", str(REPO),
            "--version", version,
        ]
        if allow_source_mismatch:
            sys.argv.append("--allow-source-mismatch")

        print()
        print("=" * 72)
        print(f"FTFL NUMBERED BUILD: v{version}")
        print("Full-foreign presentation: INLINE SAFE MODE")
        print("=" * 72)
        result = builder.main()
    finally:
        sys.argv = old_argv

    return int(result or 0)


def audit_package(version: str) -> int:
    safe_version = re.sub(r"[^A-Za-z0-9._-]+", "_", version)
    zip_path = REPO / "dist" / f"Foreign-Tongues-for-Laymen-{safe_version}.zip"
    if not zip_path.is_file():
        raise SystemExit(f"Expected build package not found: {zip_path}")

    with zipfile.ZipFile(zip_path, "r") as outer:
        pak_name = next((n for n in outer.namelist() if n.endswith("Localization/English_xml.pak")), None)
        if not pak_name:
            raise SystemExit("Built Vortex ZIP does not contain Localization/English_xml.pak")
        pak_bytes = outer.read(pak_name)

    import io
    with zipfile.ZipFile(io.BytesIO(pak_bytes), "r") as pak:
        xml_bytes = pak.read("text_ui_dialog.xml")

    xml_text = xml_bytes.decode("utf-8-sig", errors="replace")
    xml_norm = normalize(xml_text)
    unresolved: list[str] = []

    print()
    print("=" * 72)
    print("FTFL STATIC PACKAGE REGRESSION AUDIT")
    print("=" * 72)

    for phrase in REGRESSION_PHRASES:
        needle = normalize(phrase)
        pos = xml_norm.find(needle)
        if pos < 0:
            status = "NOT_FOUND_IN_PACKAGE"
        else:
            window = xml_norm[pos:pos + len(needle) + 240]
            translated = "[english]" in window or "[english:" in window
            status = "TRANSLATED" if translated else "UNTRANSLATED"
            if not translated:
                unresolved.append(phrase)
        print(f"  {status:24} {phrase}")

    if unresolved:
        print()
        print("NOT READY FOR PLAYTEST")
        print("The package still contains known regression phrases without English output.")
        print("Fix/approve them from the source review queue first; do not chase NPCs in-game.")
        return len(unresolved)

    print()
    print("STATIC GATE PASSED - package is eligible for a small rendering regression test.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="FTFL one-command toolbox")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("scan", help="Run source-driven discovery and unresolved-family generation")

    build_parser = sub.add_parser("build", help="Build numbered Vortex package from approved.csv")
    build_parser.add_argument("--version", required=True)
    build_parser.add_argument("--allow-source-mismatch", action="store_true")

    all_parser = sub.add_parser("all", help="Run source discovery, unresolved report, then build")
    all_parser.add_argument("--version", required=True)
    all_parser.add_argument("--allow-source-mismatch", action="store_true")

    args = parser.parse_args()
    print("Foreign Tongues for Laymen")
    print("FTFL Toolbox - source-driven authored dialogue")
    print(f"Repository: {REPO}")

    if args.command == "scan":
        unresolved = run_scan()
        print(f"\nSCAN COMPLETE - {unresolved:,} unresolved families")
        return 0

    if args.command == "build":
        rc = run_build(args.version, args.allow_source_mismatch)
        if rc != 0:
            return rc
        audit_package(args.version)
        return 0

    unresolved = run_scan()
    print(f"\nScan complete. {unresolved:,} unresolved families remain.")
    rc = run_build(args.version, args.allow_source_mismatch)
    if rc != 0:
        return rc
    audit_package(args.version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
