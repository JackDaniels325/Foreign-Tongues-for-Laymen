# FTFL Rosetta Toolbox v0.2 Notes

## Why v0.1 produced zero rows

KCD2's authored-dialogue XML uses positional cells rather than named `id=` / `text=` attributes:

```xml
<Table>
  <Row>
    <Cell>localization_key</Cell>
    <Cell>reference / meaning text</Cell>
    <Cell>player-facing display text</Cell>
  </Row>
</Table>
```

The v0.1 parser looked for named attributes and therefore extracted the XML correctly but parsed zero localization rows.

## v0.2 parser behavior

`build_alignment.py` now preserves both text cells for every language:

```text
localization_key
English_reference
English_display
Czech_reference
Czech_display
...
```

This is deliberate. The difference between the reference/meaning cell and the player-facing display cell is valuable evidence for Foreign Tongues for Laymen.

The toolbox also generates:

```text
reference/aligned/direct_reference_pairs.csv
```

This contains English rows where `English_reference != English_display`, which is a high-value pool for finding authored foreign phrases, dialect substitutions, and other lines that deserve review.

## Run

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_rosetta.ps1
```

A successful run should produce a non-zero alignment table and will now fail loudly if the aligned dataset contains zero rows.
