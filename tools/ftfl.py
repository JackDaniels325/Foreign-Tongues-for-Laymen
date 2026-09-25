#!/usr/bin/env python3
"""
FTFL Toolbox Front End

One command for the routine Foreign Tongues for Laymen workflow.

Examples:
    python .\tools\ftfl.py scan
    python .\tools\ftfl.py build --version 0.2.5
    python .\tools\ftfl.py all --version 0.2.5

What "scan" does:
    1. Runs the global code-switch detector.
    2. Runs the Romani/Yiddish priority sweep.
    3. Rebuilds the translation review queue.
    4. Creates ONE unresolved-family report after removing already approved
       keys/families.

What "build" does:
    1. Uses corpus/approved.csv.
    2. Uses the existing family-propagating build_mod_patch.py.
    3. Replaces the failed <br/> presentation with a safe inline separator:
           Original — [English] Translation
    4. Produces the numbered Vortex ZIP.

This file is intentionally a front end. Existing specialist tools remain
available for debugging, but normal FTFL work should start here.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import subprocess
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
REPO = TOOLS_DIR.parent

ALIGNMENT = REPO / "reference" / "aligned" / "localization_alignment.csv"
CANDIDATES = REPO / "reference" / "aligned" / "code_switch_candidates.csv"
PRIORITY = REPO / "reference" / "aligned" / "priority_nomad_yiddish_sweep.csv"
REVIEW = REPO / "reference" / "aligned" / "translation_need_review.csv"
UNRESOLVED = REPO / "reference" / "aligned" / "unresolved_families.csv"
APPROVED = REPO / "corpus" / "approved.csv"


def normalize(text: str) -> str:
    return " ".join(
        unicodedata.normalize(
            "NFKC",
            text or "",
        ).split()
    ).casefold()


def run_tool(filename: str, *args: str) -> None:
    path = TOOLS_DIR / filename

    if not path.is_file():
        raise SystemExit(
            f"Missing required FTFL tool: {path}"
        )

    command = [
        sys.executable,
        str(path),
        *args,
    ]

    print()
    print("=" * 72)
    print(f"RUNNING: {filename}")
    print("=" * 72)

    completed = subprocess.run(
        command,
        cwd=REPO,
        check=False,
    )

    if completed.returncode != 0:
        raise SystemExit(
            f"{filename} failed with exit code "
            f"{completed.returncode}"
        )


def load_approved() -> tuple[set[str], set[str]]:
    if not APPROVED.is_file():
        raise SystemExit(
            f"Missing approved corpus: {APPROVED}"
        )

    approved_keys: set[str] = set()
    approved_full_families: set[str] = set()

    with APPROVED.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)

        if not reader.fieldnames:
            raise SystemExit(
                "approved.csv has no header"
            )

        for row in reader:
            key = (
                row.get("localization_key")
                or ""
            ).strip()

            display = (
                row.get("original_display_text")
                or ""
            ).strip()

            line_type = (
                row.get("line_type")
                or ""
            ).strip().lower()

            if key:
                approved_keys.add(key)

            if (
                display
                and line_type
                in {
                    "full",
                    "full_foreign",
                    "full-foreign",
                    "foreign",
                }
            ):
                approved_full_families.add(
                    normalize(display)
                )

    return (
        approved_keys,
        approved_full_families,
    )


def collect_rows(
    path: Path,
    source_name: str,
) -> list[dict[str, str]]:
    if not path.is_file():
        return []

    rows: list[dict[str, str]] = []

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)

        for row in reader:
            display = (
                row.get("English_display")
                or ""
            ).strip()

            key = (
                row.get("localization_key")
                or ""
            ).strip()

            if not display or not key:
                continue

            rows.append({
                "localization_key": key,
                "English_display": display,
                "English_reference": (
                    row.get("English_reference")
                    or ""
                ).strip(),
                "classification": (
                    row.get("classification")
                    or ""
                ).strip(),
                "detected_languages": (
                    row.get("detected_languages")
                    or row.get("detected_language")
                    or ""
                ).strip(),
                "foreign_score": (
                    row.get("foreign_score")
                    or ""
                ).strip(),
                "source": source_name,
            })

    return rows


def write_unresolved_report() -> int:
    approved_keys, approved_full_families = (
        load_approved()
    )

    discovered = (
        collect_rows(
            CANDIDATES,
            "global_detector",
        )
        + collect_rows(
            PRIORITY,
            "priority_sweep",
        )
    )

    grouped: dict[
        str,
        list[dict[str, str]],
    ] = defaultdict(list)

    seen_pairs: set[tuple[str, str]] = set()

    for row in discovered:
        key = row["localization_key"]
        display = row["English_display"]
        family = normalize(display)

        if key in approved_keys:
            continue

        if family in approved_full_families:
            # The family-propagating builder already covers this.
            continue

        pair = (
            key,
            family,
        )

        if pair in seen_pairs:
            continue

        seen_pairs.add(pair)
        grouped[family].append(row)

    output_rows: list[dict[str, str]] = []

    for family, members in grouped.items():
        members.sort(
            key=lambda item: (
                item["localization_key"]
            )
        )

        representative = members[0]

        languages = sorted({
            language.strip()
            for member in members
            for language in member[
                "detected_languages"
            ].split(";")
            if language.strip()
        })

        classifications = sorted({
            member["classification"]
            for member in members
            if member["classification"]
        })

        sources = sorted({
            member["source"]
            for member in members
        })

        references = [
            member["English_reference"]
            for member in members
            if member["English_reference"]
        ]

        max_score = 0

        for member in members:
            try:
                max_score = max(
                    max_score,
                    int(
                        member["foreign_score"]
                        or "0"
                    ),
                )
            except ValueError:
                pass

        output_rows.append({
            "representative_key": representative[
                "localization_key"
            ],
            "family_size": str(len(members)),
            "detected_languages": "; ".join(
                languages
            ),
            "classifications": "; ".join(
                classifications
            ),
            "max_foreign_score": str(max_score),
            "sources": "; ".join(sources),
            "English_display": representative[
                "English_display"
            ],
            "English_reference": (
                references[0]
                if references
                else ""
            ),
            "review_status": "NEEDS_REVIEW",
            "verified_meaning": "",
            "notes": "",
        })

    def score(row: dict[str, str]) -> tuple:
        try:
            foreign_score = int(
                row["max_foreign_score"]
            )
        except ValueError:
            foreign_score = 0

        try:
            family_size = int(
                row["family_size"]
            )
        except ValueError:
            family_size = 1

        priority = (
            0
            if "priority_sweep"
            in row["sources"]
            else 1
        )

        return (
            priority,
            -family_size,
            -foreign_score,
            row["English_display"].casefold(),
        )

    output_rows.sort(
        key=score
    )

    UNRESOLVED.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fields = [
        "representative_key",
        "family_size",
        "detected_languages",
        "classifications",
        "max_foreign_score",
        "sources",
        "English_display",
        "English_reference",
        "review_status",
        "verified_meaning",
        "notes",
    ]

    with UNRESOLVED.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
        )

        writer.writeheader()
        writer.writerows(
            output_rows
        )

    print()
    print("=" * 72)
    print("FTFL UNRESOLVED FAMILY REPORT")
    print("=" * 72)
    print(
        f"Approved explicit keys: "
        f"{len(approved_keys):,}"
    )
    print(
        f"Approved full families: "
        f"{len(approved_full_families):,}"
    )
    print(
        f"New unresolved families: "
        f"{len(output_rows):,}"
    )
    print(
        f"Output: "
        f"{UNRESOLVED.relative_to(REPO)}"
    )

    return len(output_rows)


def run_scan() -> int:
    if not ALIGNMENT.is_file():
        raise SystemExit(
            "Missing localization_alignment.csv.\n"
            "Run the Rosetta extraction/alignment stage first."
        )

    run_tool(
        "detect_code_switches.py",
    )

    run_tool(
        "export_priority_language_sweep.py",
    )

    run_tool(
        "build_translation_review_queue.py",
    )

    return write_unresolved_report()


def run_build(
    version: str,
    allow_source_mismatch: bool,
) -> int:
    # Import the existing builder from tools/.
    if str(TOOLS_DIR) not in sys.path:
        sys.path.insert(
            0,
            str(TOOLS_DIR),
        )

    builder = importlib.import_module(
        "build_mod_patch"
    )

    # KCD2 proved that XML child <br/> is flattened in the subtitle renderer.
    # For the numbered 0.2.x line we use a safe inline separator until the
    # later presentation/hue experiment establishes supported markup.
    def apply_full_foreign_inline(
        display_cell,
        original: str,
        meaning: str,
    ) -> str:
        rendered = (
            f"{original} — "
            f"[English] {meaning}"
        )

        builder.clear_cell(
            display_cell
        )

        display_cell.text = rendered

        return rendered

    builder.apply_full_foreign = (
        apply_full_foreign_inline
    )

    old_argv = sys.argv[:]

    try:
        sys.argv = [
            str(
                TOOLS_DIR
                / "build_mod_patch.py"
            ),
            "--repo",
            str(REPO),
            "--version",
            version,
        ]

        if allow_source_mismatch:
            sys.argv.append(
                "--allow-source-mismatch"
            )

        print()
        print("=" * 72)
        print(
            f"FTFL NUMBERED BUILD: "
            f"v{version}"
        )
        print(
            "Full-foreign presentation: "
            "INLINE SAFE MODE"
        )
        print("=" * 72)

        result = builder.main()

    finally:
        sys.argv = old_argv

    return int(
        result or 0
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "FTFL one-command toolbox front end."
        )
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    subparsers.add_parser(
        "scan",
        help=(
            "Run detection/review generation and "
            "write unresolved_families.csv."
        ),
    )

    build_parser = subparsers.add_parser(
        "build",
        help=(
            "Build the numbered Vortex package "
            "from approved.csv."
        ),
    )

    build_parser.add_argument(
        "--version",
        required=True,
    )

    build_parser.add_argument(
        "--allow-source-mismatch",
        action="store_true",
    )

    all_parser = subparsers.add_parser(
        "all",
        help=(
            "Run the full scan/report pipeline, "
            "then build the numbered package."
        ),
    )

    all_parser.add_argument(
        "--version",
        required=True,
    )

    all_parser.add_argument(
        "--allow-source-mismatch",
        action="store_true",
    )

    args = parser.parse_args()

    print()
    print("Foreign Tongues for Laymen")
    print("FTFL Toolbox")
    print(f"Repository: {REPO}")

    if args.command == "scan":
        unresolved = run_scan()

        print()
        print(
            "SCAN COMPLETE — "
            f"{unresolved:,} unresolved families"
        )
        return 0

    if args.command == "build":
        return run_build(
            args.version,
            args.allow_source_mismatch,
        )

    unresolved = run_scan()

    print()
    print(
        "Scan complete. "
        f"{unresolved:,} unresolved families remain."
    )
    print(
        "Known approved translations will still be built; "
        "unresolved rows remain review-only."
    )

    return run_build(
        args.version,
        args.allow_source_mismatch,
    )


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
