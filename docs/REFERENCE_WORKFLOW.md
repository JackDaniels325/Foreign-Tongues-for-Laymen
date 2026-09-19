# Reference / Rosetta Workflow

## Purpose

Build a KCD2-specific "Rosetta Stone" that lets Foreign Tongues for Laymen compare the same localization key across official UI languages before relying on external dictionaries.

## Discovery workflow

1. Scan the full authored dialogue corpus, not only known words or nearby character rows.
2. Flag fully foreign lines, mixed-language fragments, and suspicious transliterations.
3. Match by exact localization key across available official localization packs.
4. Compare English, Czech, German, French, and later additional languages.
5. Record verified lexical roots and spelling variants in `reference/glossaries/`.
6. Record aligned rows in `reference/aligned/localization_alignment.csv`.
7. Only release a translation when the exact key and intended meaning are sufficiently verified.

## Display rule reminder

- English sentence with a foreign sprinkle: inline gloss immediately after the foreign fragment.
- Fully non-English subtitle: preserve the original as the primary subtitle and put `[English] ...` on an explicit second line.
- If rendering is uncertain, preserve/test the explicit line break rather than collapsing a full foreign line inline.

## Context rule

Localization/XML row order is not guaranteed to equal player-visible scene order. Confirmed in-game presentation order wins when context changes interpretation.
