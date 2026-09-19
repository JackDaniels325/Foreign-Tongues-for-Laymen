# Foreign Tongues for Laymen

Translation support mod for Warhorse Studios' **Kingdom Come: Deliverance II**.

## Goal

Preserve the game's original multilingual dialogue while adding readable translations for players who cannot comfortably follow every spoken language.

## Subtitle Display Rules

These rules are based on how subtitles are presented **on screen to the player**, not on XML/localization row order.

### 1. English sentence with a foreign word or phrase

If the subtitle is primarily English and contains only a foreign word or phrase, keep the subtitle on **one line** and insert the English gloss immediately after the foreign fragment.

Example:

```text
You will djal chooches! [English: leave empty-handed]
```

Another example:

```text
Borekh ha-shem! [English: Blessed be the Name!] I can't complain...
```

### 2. Entire subtitle is non-English

If the full spoken subtitle is non-English, keep the original spoken line as the **primary subtitle** and place the English translation on an **exclusive secondary line directly underneath it**.

Example:

```text
T’aves bachtalo!
[English] Good fortune to you!
```

Another example:

```text
Ha zavarba hozol előtte, megkeserülöd!
[English] If you embarrass me in front of her, you'll regret it!
```

### 3. Multiple foreign fragments inside an English sentence

If an otherwise English sentence contains multiple foreign fragments, annotate each foreign fragment immediately after that fragment.

Do **not** move the whole sentence into a second-line translation.

### 4. Uncertain line-break or display behavior

If the intended display of a phrase or full line is uncertain, preserve the intended rule in the XML and include an explicit line break so it can be tested in game.

Do **not** collapse a fully non-English subtitle into an inline translation merely because rendering behavior is uncertain.

### 5. Preserve the speaker

- Preserve the game's original spelling and transliteration.
- Preserve slang, broken grammar, repetitions, interruptions, jokes, and intentional nonsense.
- Do not silently rewrite or "correct" the speaker.
- Do not infer spoken scene order from XML/localization row order.
- Use confirmed in-game presentation order when scene context matters.

## Translation Classification

Use the following display classification when building or reviewing corpus entries:

```text
English + foreign sprinkle  -> Inline translation on the same subtitle line
Fully non-English subtitle  -> English translation on a second line underneath
Multiple foreign fragments -> Inline gloss immediately after each fragment
Intentional nonsense        -> Preserve untouched
Uncertain meaning           -> Hold for verification
Uncertain rendering         -> Preserve/test explicit line break
```

## Project Phases

- **v0.1.x** — localization architecture / proof of concept
- **v0.2.x** — authored dialogue corpus
- **v0.3.x** — IPL/open-world dialogue, overhead barks, combat chatter, crime reactions, ambient lines
- Later passes — broader language coverage, compatibility, and optional convenience features

## Reference Data

`English_xml.pak` is the primary English localization reference.

`IPL_english.pak` is the large open-world / IPL reference archive. Where practical, useful extracted dialogue trees should also be placed under `reference/IPL_english/` so they can be searched and audited without repeatedly unpacking the full archive.

See:

- `docs/IPL_REFERENCE_LAYOUT.md`
- `docs/LANGUAGE_PORTING_GUIDE.md`

## Verification Rule

A translation enters the release corpus only after the exact localization key is known and the meaning is verified from localization data, confirmed in-game context, or reliable linguistic reference material.

When file order and player-visible scene order disagree, **confirmed in-game presentation order wins for contextual interpretation**.

## Regression Testing

The Nomad camp is the first concentrated regression zone because it includes:

- full non-English dialogue
- mixed-language subtitles
- Romani/Nomad speech
- Yiddish/Hebrew speech
- greetings and farewells
- merchant dialogue
- wagers and race dialogue
- incidental NPC responses

The Nomad camp is a test bench, not the scope boundary. The authored-dialogue sweep should scan globally for any deliberately untranslated or code-switched dialogue that could benefit from translation support.
