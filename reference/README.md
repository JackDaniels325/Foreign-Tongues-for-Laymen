# FTFL Reference Workspace

This folder is the project's translation-reference layer. It exists to reduce repeated rediscovery of foreign terms and to support cross-localization comparison by exact KCD2 localization key.

## Priority order

1. Official KCD2 localization data (same localization key across languages)
2. Confirmed in-game context and presentation order
3. Project glossary entries already verified
4. Reliable external linguistic references for unresolved gaps

## Folder layout

- `localization/` — official game localization sources or extracted text/XML grouped by UI language.
- `glossaries/` — verified project-native word/phrase references and spelling variants.
- `aligned/` — cross-language key alignment tables.
- `IPL_english/` — extracted open-world / overhead / bark reference material from `IPL_english.pak`.

Preserve the game's exact spelling/transliteration in `game_form`. Put normalized dictionary/root forms separately in `normalized_form`.
