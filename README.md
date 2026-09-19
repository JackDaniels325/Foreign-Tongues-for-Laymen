# Foreign Tongues for Laymen

Translation support mod for Warhorse Studios' **Kingdom Come: Deliverance II**.

## Goal

Preserve the game's original multilingual dialogue while adding readable translations for players who cannot comfortably follow every spoken language.

### Display rules

- **Mixed-language sentence:** preserve the original foreign phrase and append an inline gloss.
  - Example: `djal chooches! [English: leave empty-handed]`
- **Fully foreign line:** preserve the original line, then add a secondary translated line.
  - Example:
    ```text
    Original foreign sentence.
    [English] Translation.
    ```
- Preserve slang, broken grammar, repetitions, interruptions, transliteration, jokes, and intentional nonsense.
- Do not silently rewrite the speaker.
- No Lua is required for the core translation patch.

## Project phases

- **v0.1.x** — localization architecture / proof of concept
- **v0.2.x** — authored dialogue corpus
- **v0.3.x** — IPL/open-world dialogue, overhead barks, combat chatter, crime reactions, ambient lines
- Later passes — broader language coverage, compatibility, and optional convenience features

## Reference data

`English_xml.pak` is the primary English localization reference.

Large `IPL_english.pak` content should be extracted selectively into `reference/IPL_english/` rather than committed as one giant archive.

See:
- `docs/IPL_REFERENCE_LAYOUT.md`
- `docs/LANGUAGE_PORTING_GUIDE.md`

## Verification rule

A translation enters the release corpus only after the exact localization key is known and the meaning is verified from localization data, context, or reliable linguistic reference material.
