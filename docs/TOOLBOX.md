# FTFL Rosetta Toolbox

This toolbox turns the official KCD2 localization PAK library into a persistent, text-searchable comparison layer for **Foreign Tongues for Laymen**.

## Purpose

The raw PAKs remain under:

```text
localization/
```

The toolbox extracts only the authored-dialogue localization file from each pack and builds one key-aligned reference table.

```text
reference/localization/<Language>/text_ui_dialog.xml
reference/aligned/localization_alignment.csv
```

This lets the project compare the **same exact localization key** across every available official language without repeatedly opening binary PAKs.

## One-click Windows run

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_rosetta.ps1
```

Or right-click `tools/run_rosetta.ps1` and run it with PowerShell.

## What the scripts do

1. `extract_dialogue.py`
   - finds every `localization/*_xml.pak`
   - extracts only `text_ui_dialog.xml`
   - first tries Python's ZIP reader
   - falls back to a local 7-Zip installation when needed

2. `build_alignment.py`
   - parses each extracted dialogue XML
   - aligns rows by exact localization key
   - writes a UTF-8 CSV for GitHub/search use

3. `validate_alignment.py`
   - checks row count
   - checks duplicate keys
   - reports populated rows per language

## Important rule

The alignment CSV is **reference evidence**, not an automatic translation authority.

A line still needs verification before entering the release corpus. Agreement among official localizations is strong evidence, but disagreements and idioms belong in review rather than being guessed into the mod.

## Recommended GitHub contents

Commit:

```text
tools/
docs/TOOLBOX.md
reference/aligned/localization_alignment.csv
```

The extracted XML files under `reference/localization/` are useful to retain if repository size remains reasonable. If they become unwieldy, keep the aligned CSV plus the raw localization PAKs and regenerate extracted XML locally as needed.
