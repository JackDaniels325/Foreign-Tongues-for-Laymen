#!/usr/bin/env python3
"""
FTFL - Build Vortex-installable KCD2 playtest mod

Input:
    corpus/approved.csv
    reference/localization/English/text_ui_dialog.xml

Outputs:
    mod/foreign_tongues_for_laymen/
        mod.manifest
        Localization/English_xml.pak

    dist/Foreign-Tongues-for-Laymen-v0.2-playtest.zip

The outer ZIP is ready to drag into Vortex.
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
import sys
import zipfile
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape


MODID_RE = re.compile(r"^[a-z_]+$")

MIXED_TYPES = {
    "mixed",
    "mixed_language",
    "mixed-language",
    "inline",
}

FULL_TYPES = {
    "full",
    "full_foreign",
    "full-foreign",
    "foreign",
}


def visible_text(cell: ET.Element) -> str:
    return "".join(cell.itertext()).strip()


def row_cells(row: ET.Element) -> list[ET.Element]:
    return [
        c for c in list(row)
        if c.tag.rsplit("}", 1)[-1] == "Cell"
    ]


def load_approved(path: Path) -> dict[str, dict[str, str]]:
    required = {
        "localization_key",
        "speaker_context",
        "original_display_text",
        "foreign_fragment",
        "source_language",
        "verified_meaning",
        "line_type",
        "reference_source",
        "test_status",
        "notes",
    }

    if not path.exists():
        raise SystemExit(f"Missing approved corpus: {path}")

    approved: dict[str, dict[str, str]] = {}
    duplicates: list[str] = []

    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)

        if not reader.fieldnames:
            raise SystemExit("approved.csv has no header")

        missing = required - set(reader.fieldnames)

        if missing:
            raise SystemExit(
                "approved.csv missing columns: "
                + ", ".join(sorted(missing))
            )

        for row in reader:
            key = (row.get("localization_key") or "").strip()

            if not key:
                continue

            if key in approved:
                duplicates.append(key)
                continue

            line_type = (
                row.get("line_type") or ""
            ).strip().lower()

            meaning = (
                row.get("verified_meaning") or ""
            ).strip()

            if not meaning:
                raise SystemExit(
                    f"{key}: verified_meaning is blank"
                )

            if line_type not in MIXED_TYPES | FULL_TYPES:
                raise SystemExit(
                    f"{key}: unsupported line_type '{line_type}'"
                )

            approved[key] = {
                k: (v or "").strip()
                for k, v in row.items()
            }

    if duplicates:
        raise SystemExit(
            "Duplicate localization keys in approved.csv:\n"
            + "\n".join(sorted(set(duplicates)))
        )

    if not approved:
        raise SystemExit(
            "approved.csv contains no approved localization rows"
        )

    return approved


def clear_cell(cell: ET.Element) -> None:
    cell.text = None

    for child in list(cell):
        cell.remove(child)


def apply_mixed(
    display_cell: ET.Element,
    original: str,
    fragment: str,
    meaning: str,
) -> str:

    if not fragment:
        raise ValueError(
            "mixed-language line requires foreign_fragment"
        )

    if fragment not in original:
        raise ValueError(
            f"foreign_fragment not found in original text: {fragment!r}"
        )

    rendered = original.replace(
        fragment,
        f"{fragment} [English: {meaning}]",
        1,
    )

    clear_cell(display_cell)
    display_cell.text = rendered

    return rendered


def apply_full_foreign(
    display_cell: ET.Element,
    original: str,
    meaning: str,
) -> str:

    clear_cell(display_cell)

    display_cell.text = original

    br = ET.SubElement(
        display_cell,
        "br",
    )

    br.tail = f"[English] {meaning}"

    return (
        f"{original}"
        f"<br/>"
        f"[English] {meaning}"
    )


def patch_xml(
    base_xml: Path,
    output_xml: Path,
    approved: dict[str, dict[str, str]],
    allow_source_mismatch: bool,
) -> list[tuple[str, str]]:

    if not base_xml.exists():
        raise SystemExit(
            f"Missing extracted English XML: {base_xml}"
        )

    print("Loading base localization:")
    print(f"  {base_xml}")

    tree = ET.parse(base_xml)
    root = tree.getroot()

    found: set[str] = set()
    applied: list[tuple[str, str]] = []

    for row in root.iter():

        if row.tag.rsplit("}", 1)[-1] != "Row":
            continue

        cells = row_cells(row)

        if len(cells) < 3:
            continue

        key = visible_text(cells[0])

        if key not in approved:
            continue

        entry = approved[key]

        base_display = visible_text(cells[2])

        expected = entry[
            "original_display_text"
        ]

        if (
            expected
            and base_display != expected
            and not allow_source_mismatch
        ):
            raise SystemExit(
                "\nSource mismatch detected.\n"
                f"Key:      {key}\n"
                f"Expected: {expected}\n"
                f"Current:  {base_display}\n\n"
                "Verify the game line before building, "
                "or use --allow-source-mismatch "
                "for deliberate testing."
            )

        original = expected or base_display

        meaning = entry[
            "verified_meaning"
        ]

        line_type = entry[
            "line_type"
        ].lower()

        try:

            if line_type in MIXED_TYPES:

                rendered = apply_mixed(
                    cells[2],
                    original,
                    entry["foreign_fragment"],
                    meaning,
                )

            else:

                rendered = apply_full_foreign(
                    cells[2],
                    original,
                    meaning,
                )

        except ValueError as exc:
            raise SystemExit(
                f"{key}: {exc}"
            )

        found.add(key)

        applied.append(
            (
                key,
                rendered,
            )
        )

    missing = sorted(
        set(approved) - found
    )

    if missing:
        raise SystemExit(
            "Approved localization keys were not found "
            "in English text_ui_dialog.xml:\n"
            + "\n".join(missing)
        )

    output_xml.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    tree.write(
        output_xml,
        encoding="utf-8",
        xml_declaration=True,
        short_empty_elements=True,
    )

    return applied


def write_manifest(
    path: Path,
    modid: str,
    name: str,
    version: str,
    author: str,
) -> None:

    manifest = f"""<?xml version="1.0" encoding="utf-8"?>
<kcd_mod>
  <info>
    <name>{escape(name)}</name>
    <modid>{escape(modid)}</modid>
    <description>Foreign-language subtitle translation support for Kingdom Come: Deliverance II.</description>
    <author>{escape(author)}</author>
    <version>{escape(version)}</version>
    <created_on>{date.today().isoformat()}</created_on>
  </info>
</kcd_mod>
"""

    # Ensure the mod root exists before creating mod.manifest.
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        manifest,
        encoding="utf-8",
        newline="\n",
    )


def build_localization_pak(
    source_xml: Path,
    pak_path: Path,
) -> None:

    pak_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if pak_path.exists():
        pak_path.unlink()

    with zipfile.ZipFile(
        pak_path,
        "w",
        compression=zipfile.ZIP_STORED,
    ) as pak:

        pak.write(
            source_xml,
            arcname="text_ui_dialog.xml",
        )


def build_vortex_zip(
    mod_root: Path,
    zip_path: Path,
) -> None:

    zip_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(
        zip_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
    ) as archive:

        for file in sorted(
            mod_root.rglob("*")
        ):

            if not file.is_file():
                continue

            relative = file.relative_to(
                mod_root.parent
            )

            archive.write(
                file,
                arcname=str(
                    relative
                ).replace("\\", "/"),
            )


def main() -> int:

    parser = argparse.ArgumentParser(
        description=(
            "Build a Vortex-installable "
            "Foreign Tongues for Laymen "
            "KCD2 playtest package."
        )
    )

    parser.add_argument(
        "--repo",
        default=".",
    )

    parser.add_argument(
        "--approved",
        default="corpus/approved.csv",
    )

    parser.add_argument(
        "--base",
        default=(
            "reference/localization/"
            "English/text_ui_dialog.xml"
        ),
    )

    parser.add_argument(
        "--modid",
        default="foreign_tongues_for_laymen",
    )

    parser.add_argument(
        "--name",
        default="Foreign Tongues for Laymen",
    )

    parser.add_argument(
        "--version",
        default="0.2-playtest",
    )

    parser.add_argument(
        "--author",
        default="JackDaniels325",
    )

    parser.add_argument(
        "--allow-source-mismatch",
        action="store_true",
    )

    args = parser.parse_args()

    repo = Path(
        args.repo
    ).resolve()

    if not MODID_RE.fullmatch(
        args.modid
    ):
        raise SystemExit(
            "modid must contain lowercase "
            "letters and underscores only"
        )

    approved_path = (
        repo
        / args.approved
    )

    base_xml = (
        repo
        / args.base
    )

    mod_root = (
        repo
        / "mod"
        / args.modid
    )

    staging_xml = (
        repo
        / "build"
        / args.modid
        / "English_xml"
        / "text_ui_dialog.xml"
    )

    pak_path = (
        mod_root
        / "Localization"
        / "English_xml.pak"
    )

    safe_version = re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        args.version,
    )

    dist_zip = (
        repo
        / "dist"
        / (
            "Foreign-Tongues-for-Laymen-"
            f"{safe_version}.zip"
        )
    )

    print("FTFL Mod Patch Builder")
    print(f"Repository: {repo}")
    print()

    approved = load_approved(
        approved_path
    )

    print(
        f"Approved corpus rows: "
        f"{len(approved):,}"
    )

    # Clean previous generated mod.
    if mod_root.exists():
        shutil.rmtree(
            mod_root
        )

    # Clean previous staging output.
    build_root = (
        repo
        / "build"
        / args.modid
    )

    if build_root.exists():
        shutil.rmtree(
            build_root
        )

    # Explicitly recreate root directories.
    mod_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    staging_xml.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Build patched localization XML.
    applied = patch_xml(
        base_xml,
        staging_xml,
        approved,
        args.allow_source_mismatch,
    )

    # Create mod.manifest.
    write_manifest(
        mod_root
        / "mod.manifest",
        args.modid,
        args.name,
        args.version,
        args.author,
    )

    # Pack localization PAK.
    build_localization_pak(
        staging_xml,
        pak_path,
    )

    # Build Vortex-installable outer ZIP.
    build_vortex_zip(
        mod_root,
        dist_zip,
    )

    print()
    print("Patch build complete.")

    print(
        f"Patched localization keys: "
        f"{len(applied):,}"
    )

    print()
    print("Mod folder:")
    print(
        f"  {mod_root}"
    )

    print()
    print("Localization PAK:")
    print(
        f"  {pak_path}"
    )

    print()
    print("Vortex ZIP:")
    print(
        f"  {dist_zip}"
    )

    print()
    print("Patched lines:")

    for key, rendered in applied:

        print(
            f"  {key}"
        )

        print(
            f"    {rendered}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )