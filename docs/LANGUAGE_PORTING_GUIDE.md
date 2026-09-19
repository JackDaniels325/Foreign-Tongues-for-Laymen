# Language Porting Guide

This project is designed so other language maintainers can reproduce the same approach without adopting a script layer.

## Core architecture

Each supported UI language should use its own sparse localization override PAK containing only changed rows.

Conceptually:

```text
Localization/
└─ <Language>_xml.pak
   └─ text_ui_dialog__foreign_tongues_for_laymen.xml
```

The core mod should remain localization-only wherever possible.

## Contributor workflow

1. Obtain that language's base `*_xml.pak`.
2. Extract the corresponding dialogue localization table.
3. Use the English verified corpus as a **key map**, not as permission to blindly machine-translate.
4. Match by exact localization key.
5. Preserve the original foreign fragment spoken in-game.
6. Translate only the explanatory gloss into the player's selected UI language.
7. Keep the same two display rules:
   - mixed-language phrase -> inline bracketed gloss
   - fully foreign line -> translation on a secondary line
8. Test representative lines before publishing the language pack.

## Shared corpus fields

Long-term verified entries should track:

```text
localization_key
speaker_context
original_display_text
foreign_fragment
source_language
verified_meaning
line_type
reference_source
test_status
notes
```

This lets one verified discovery support many UI-language packs.

## Important

Do not "correct" character speech, transliteration, dialect, broken grammar, or deliberate jokes. The mod explains the foreign language; it does not rewrite the performance.
