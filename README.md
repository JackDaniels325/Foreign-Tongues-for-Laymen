# Foreign Tongues for Laymen

Translation support mod for Warhorse Studios' **Kingdom Come: Deliverance II**.

## Goal

Preserve the game's original multilingual dialogue while adding readable translations for players who cannot comfortably follow every spoken language.

The mod is intended to **add understanding without erasing identity**. Accents, dialects, slang, transliteration, broken grammar, repetitions, jokes, and culture-specific phrasing remain intact. The translation layer explains meaning; it does not rewrite the speaker.

## Subtitle Display Rules

These rules are based on how subtitles are presented **on screen to the player**, not on XML/localization row order.

### 1. English sentence with a foreign word or phrase

If the subtitle is primarily English and contains only a foreign word or phrase, keep the subtitle on the same subtitle block and place the English gloss immediately after the foreign fragment.

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

Use the game's explicit subtitle hard break (`<br/>`) rather than relying on a plain newline.

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

If an otherwise English sentence contains multiple foreign fragments, keep the original sentence intact.

Avoid turning the subtitle into a chain of repetitive annotations. Where several adjacent foreign expressions form one semantic unit, prefer one grouped translation rather than repeating `[English: ...]` after every word.

### 4. Translation color hierarchy

The project is testing a **subtle silver/light-gray translation hue** so the translation is visually secondary to the original spoken dialogue.

Design target:

```text
Original spoken subtitle -> normal KCD2 subtitle appearance
Translation / gloss       -> soft silver-gray
```

The goal is a small visual separation, not a neon UI effect.

This color treatment is also useful as a QA signal: foreign dialogue that appears with no matching translation treatment can be spotted quickly as a likely missed entry.

Until the color implementation is fully field-tested across cutscenes and overhead dialogue, readability and compatibility take priority over styling.

### 5. Preserve the speaker

- Preserve the game's exact spelling and transliteration.
- Preserve accent, dialect, slang, broken grammar, repetitions, interruptions, jokes, and intentional nonsense.
- Do not silently rewrite or "correct" the speaker.
- Do not infer spoken scene order from XML/localization row order.
- Use confirmed in-game presentation order when scene context matters.

### 6. Verification rule

Uncertain meaning is held for review rather than guessed into a release build.

A translation enters the release corpus only after the exact localization key is known and the meaning is supported by one or more of:

- the game's own localization data
- aligned official translations for the same localization key
- confirmed in-game context
- a reliable linguistic reference

## Cross-Language "Rosetta" Workflow

The repository includes the game's available localization packs under:

```text
localization/
```

These are used as a parallel reference system. The same localization key can be compared across English, Czech, German, French, Polish, Russian, Spanish, Portuguese, Italian, Japanese, Korean, Chinese, Turkish, Ukrainian, Vietnamese, and other included official packs.

The purpose is **not** to translate from geography alone. The useful question is:

> Does another official localization resolve the meaning of the same foreign phrase more clearly?

Agreement across multiple official localizations is strong evidence for intended meaning.

## Current Scope

### v0.1.x — Architecture / proof of concept

- sparse localization patching
- PAK discovery
- exact-key overrides
- in-game subtitle rendering tests

### v0.2.x — Global authored-dialogue corpus

This phase covers **all authored dialogue regions and all deliberately untranslated/code-switched language families**, not only the Nomad camp or Trosky.

Current work is divided into bite-sized corpus passes:

1. verified direct-reference pairs across all languages
2. lexical-family and spelling-variant expansion across all languages
3. full-foreign subtitle alignment and hard-break validation
4. mixed-language cleanup and grouped-gloss cleanup
5. idioms / ambiguous lines held for manual review
6. regional regression sampling in Trosecko and Kutnohorsko

The Nomad camp remains a useful regression test bench, but it is **not** the scope boundary.

### v0.3.x — IPL / open-world dialogue

Planned after authored dialogue is substantially stabilized:

- overhead NPC dialogue
- ambient lines
- battle barks
- combat chatter
- crime reactions
- regional open-world speech
- broader Cuman coverage

IPL work is intentionally separated from v0.2 so authored dialogue and ambient dialogue can be audited independently.

## Repository Layout

```text
corpus/        verified and review translation data
docs/          workflow and project documentation
localization/  raw official game localization reference packs
reference/     extracted/aligned Rosetta material and glossaries
```

The repository root is kept intentionally small.

## Regression Testing

A field test does not need to replay the same quest branch repeatedly.

Useful confirmation can come from different speakers, regions, quests, and languages as long as it verifies one of the core behaviors:

- inline mixed-language gloss renders correctly
- full foreign subtitle receives a true secondary line
- translation styling remains readable
- original accent/dialect remains untouched
- previously translated language families remain intact
- a newly discovered foreign phrase is correctly marked as a corpus miss

## Project Principle

**Preserve the performance. Supply the understanding.**

The mod should help the player understand the speaker without flattening the speaker into generic English.
