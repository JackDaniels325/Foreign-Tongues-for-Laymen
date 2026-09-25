# Foreign Tongues for Laymen

Translation support mod for Warhorse Studios' **Kingdom Come: Deliverance II**.

## Goal

Preserve the game's original multilingual dialogue while adding readable English translations for players who cannot comfortably follow every spoken language.

The mod is intended to **add understanding without erasing identity**. Accents, dialects, slang, transliteration, broken grammar, repetitions, jokes, and culture-specific phrasing remain intact. The translation layer explains meaning; it does not rewrite the speaker.

> **Project principle:** Preserve the performance. Supply the understanding.

---

# Development Guardrails

These rules are here to keep the project simple, repeatable, and resistant to regression.

## 1. The localization PAKs are the primary source of truth

The official localization packs under:

```text
localization/
```

are the authoritative discovery source for authored dialogue.

The normal discovery path is:

```text
official localization PAKs
-> extract authored dialogue
-> align by localization key
-> compare official languages
-> identify foreign/code-switched families
-> group sibling/duplicate keys
-> review only genuinely uncertain meaning
-> build the mod
```

Do **not** make gameplay the primary method for discovering untranslated authored dialogue.

Gameplay is for:

- verifying subtitle rendering
- checking compatibility
- confirming a small regression sample
- reporting an unexpected miss back to the discovery pipeline

If an untranslated authored line is found in gameplay, treat it as evidence that the discovery pipeline needs investigation. Do not simply patch that one line and resume manual hunting.

## 2. Do not turn the tester into the scanner

The project should not require repeated quest replay, merchant hopping, random NPC fishing, or screenshot whack-a-mole to build coverage.

The toolbox exists to remove that burden.

A normal corpus update should come from the source localization data first. Human gameplay testing should be small and deliberate.

## 3. Signal files are hints, not the universe

Files such as:

```text
reference/glossaries/*_signals.txt
```

are secondary detection aids.

They may improve confidence for German, Romani, Yiddish/Hebrew, Latin, Hungarian, Czech, Polish, French, Italian, Arabic, Slovak, and other language families, but they must **not** define the complete set of foreign dialogue.

A line must not be missed simply because its spelling or transliteration is absent from a hand-written signal list.

Examples of variations that should be treated as related evidence where appropriate:

```text
T'aves bachtalo
T-aves bakhtalo
Taves baxtalo
T'aves baxtalo
```

The source-driven localization comparison has priority over literal signal matching.

## 4. Family-first translation

KCD2 may use multiple localization keys for the same visible subtitle.

A verified full-foreign subtitle should be approved once as a dialogue family, then safely propagated to sibling keys that share the same source text.

Do not require separate manual approval for every duplicate key unless the wording or meaning actually differs.

Mixed-language subtitles remain more conservative because the foreign fragment can vary inside otherwise similar English sentences.

## 5. Review ambiguity, not routine duplication

Human review is intended for:

- uncertain meaning
- ambiguous language identification
- mixed-language fragment boundaries
- idioms
- culture-specific wording
- conflicting official-localization evidence
- genuinely novel phrases

Human review should **not** be spent rediscovering duplicate keys or routinely re-verifying already approved families.

## 6. Keep the workflow one-command whenever practical

The normal FTFL workflow should begin with:

```powershell
python .\tools\ftfl.py all --version 0.2.x
```

Specialist scripts under `tools/` remain available for debugging and development, but routine operation should not require the user to remember a chain of individual Python commands.

## 7. Version numbers are the primary release identifier

Use numeric versioning as the main project reference.

Example:

```text
0.2.4 = family propagation
0.2.5 = consolidated toolbox / inline-safe rendering
0.2.6 = source-driven discovery expansion
```

Descriptive names may be added as notes, but instructions, builds, tests, and regression reports should lead with the version number.

---

# Subtitle Display Rules

These rules are based on how subtitles are actually presented **on screen to the player**, not on XML/localization row order.

## 1. English sentence with a foreign word or phrase

If the subtitle is primarily English and contains a foreign word or phrase, keep the subtitle in the same subtitle block and place the English gloss immediately after the foreign fragment.

Example:

```text
You will djal chooches! [English: leave empty-handed]
```

Another example:

```text
Borekh ha-shem! [English: Blessed be the Name!] I can't complain...
```

## 2. Entire subtitle is non-English

Preserve the original spoken subtitle first, then provide the English translation.

### Current tested-safe fallback

KCD2 field testing showed that inserting an XML child `<br/>` does **not** create a reliable second subtitle line. The renderer flattens the content.

Therefore the current safe fallback is inline:

```text
So rodes, goro? — [English] What are you looking for, non-Roma?
```

Do not describe `<br/>` as a working subtitle hard break unless a future renderer test proves otherwise.

### Long-term presentation target

The desired design remains:

```text
Original foreign subtitle
[English] Translation
```

with the translation visually secondary.

A genuine second-line solution should be adopted only after it is proven in-game.

## 3. Multiple foreign fragments inside an English sentence

If an otherwise English sentence contains multiple foreign fragments, keep the original sentence intact.

Avoid turning the subtitle into a chain of repetitive annotations. Where several adjacent foreign expressions form one semantic unit, prefer one grouped translation rather than repeating `[English: ...]` after every word.

## 4. Translation color hierarchy

The project may test a subtle silver/light-gray translation hue so the translation is visually secondary to the original spoken dialogue.

Design target:

```text
Original spoken subtitle -> normal KCD2 subtitle appearance
Translation / gloss       -> soft silver-gray
```

Readability and compatibility take priority over styling.

Do not deploy hue/color markup broadly until the game renderer has been tested with a small known-working sample.

## 5. Preserve the speaker

- Preserve the game's exact spelling and transliteration.
- Preserve accent, dialect, slang, broken grammar, repetitions, interruptions, jokes, and intentional nonsense.
- Do not silently rewrite or "correct" the speaker.
- Do not infer spoken scene order from XML/localization row order.
- Use confirmed in-game presentation order only when scene context actually matters.

## 6. Verification rule

Uncertain meaning is held for review rather than guessed into a release build.

A translation may enter the approved corpus when the meaning is supported by one or more of:

- the game's own localization data
- aligned official translations for the same localization key
- confirmed in-game context
- a reliable linguistic reference

Exact-key knowledge is useful, but verified full-foreign families may propagate to safe sibling keys automatically.

---

# Cross-Language "Rosetta" Workflow

The repository includes the game's available localization packs under:

```text
localization/
```

These are used as a parallel reference system.

The same localization key can be compared across available official packs including English, Czech, German, French, Polish, Russian, Spanish, Portuguese, Italian, Japanese, Korean, Chinese, Turkish, Ukrainian, Vietnamese, and others stored in the repository.

The purpose is **not** to translate from geography alone.

Useful questions include:

> Does another official localization resolve the meaning of the same foreign phrase more clearly?

> Does the same unusual wording remain preserved across multiple official languages?

> Does the English display differ from its English reference in a way that exposes deliberate code-switching?

Agreement across multiple official localizations can be strong evidence for intended foreignness or intended meaning, but Rosetta evidence does not automatically replace linguistic verification when the meaning remains uncertain.

---

# Discovery Priority

For authored dialogue, use this order:

```text
1. official localization PAK comparison
2. exact localization-key alignment
3. duplicate/sibling family grouping
4. direct English reference/display differences
5. multilingual Rosetta evidence
6. signal/glossary hints
7. manual linguistic review for unresolved cases
8. gameplay regression check
```

Gameplay is intentionally last for discovery.

---

# Current Scope

## v0.1.x — Architecture / proof of concept

- localization PAK discovery
- exact-key overrides
- Vortex packaging
- initial in-game subtitle rendering tests

## v0.2.x — Global authored-dialogue corpus

This phase covers **all authored dialogue regions and all deliberately untranslated/code-switched language families**, not only the Nomad camp or Trosky.

Primary goals:

1. source-driven discovery from the official localization packs
2. exact-key alignment across official languages
3. safe dialogue-family propagation
4. mixed-language fragment handling
5. idioms and ambiguous lines held for review
6. regression sampling across Trosecko and Kutnohorsko
7. subtitle presentation experiments only after coverage is stable

The Nomad camp remains a useful regression test bench, but it is **not** the scope boundary and should not be repeatedly replayed as the main discovery method.

## v0.3.x — IPL / open-world dialogue

Planned after authored dialogue is substantially stabilized:

- overhead NPC dialogue
- ambient lines
- battle barks
- combat chatter
- crime reactions
- regional open-world speech
- broader Cuman coverage

IPL work is intentionally separated from v0.2 so authored dialogue and ambient dialogue can be audited independently.

---

# Toolbox Workflow

## Normal operation

Use:

```powershell
python .\tools\ftfl.py all --version 0.2.x
```

The front-end should coordinate routine operations such as:

```text
scan source data
-> rebuild candidate evidence
-> remove already approved families
-> generate unresolved review output
-> propagate known family translations
-> build numbered Vortex package
-> print concise status summary
```

Specialist scripts are implementation details unless debugging is required.

## Expected human interaction

The user should normally need to do only three things:

```text
1. update or review genuinely unresolved translation families
2. run the numbered FTFL toolbox build
3. perform a small in-game regression check
```

If the workflow starts requiring repeated manual NPC hunting, repeated individual-key patching, or many one-off scripts, treat that as a tooling regression.

---

# Repository Visibility

The repository should remain small enough for normal GitHub use while still exposing enough project state for collaboration and review.

## Track in GitHub

Examples:

```text
tools/
corpus/
docs/
reference/glossaries/
reference/status/
small review/family summaries
README.md
.gitignore
.gitattributes
```

## Keep local/generated

Examples:

```text
reference/localization/*/text_ui_dialog.xml
reference/aligned/localization_alignment.csv
large generated candidate/review scans
build/
dist/*.zip
generated English_xml.pak
Python cache
```

The toolbox should prefer producing compact tracked status summaries so another collaborator can understand the current project state without requiring the full local 293 MB alignment file.

---

# Regression Testing

Regression testing should be **small, deterministic, and versioned**.

A field test does not need to replay the same quest branch repeatedly.

Useful confirmation can come from different speakers, regions, quests, and languages as long as it verifies one of the core behaviors:

- an already approved full-foreign family receives its English translation
- a known sibling key inherits a family translation
- an inline mixed-language gloss renders correctly
- original accent/dialect/transliteration remains untouched
- the inline-safe fallback remains readable
- a presentation experiment does not break subtitle rendering
- previously translated families remain intact

If gameplay exposes an unexpected untranslated authored line:

```text
1. record the phrase/key if convenient
2. treat it as a discovery-pipeline regression
3. investigate the source corpus/toolbox
4. fix the systemic cause
5. do not restart one-line whack-a-mole patching
```

---

# Project Principles

**Preserve the performance. Supply the understanding.**

**Automate discovery. Review ambiguity. Test presentation.**

The mod should help the player understand the speaker without flattening the speaker into generic English.

The tooling should make that goal easier to achieve, not create additional manual work.
