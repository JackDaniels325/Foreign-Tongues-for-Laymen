# Authored Dialogue Workplan

This document defines the working scope for **v0.2.x** of Foreign Tongues for Laymen.

The goal is to keep corpus work broad enough to cover all languages, but small enough that each pass can be audited before the next one begins.

## Scope Boundary

Included in v0.2.x:

- authored quest dialogue
- authored merchant dialogue
- authored cutscene dialogue
- authored optional conversation branches
- deliberately untranslated words and phrases
- fully foreign subtitles
- code-switched dialogue
- dialect and transliteration variants

Deferred to v0.3.x:

- IPL/open-world ambient dialogue
- overhead NPC barks
- combat chatter
- crime reaction barks
- open-world battle barks

## Batch Strategy

Each batch scans the **global authored-dialogue corpus**. Batches are separated by confidence/method, not by language or region.

### Batch A — Direct Rosetta Pairs

Find rows where the game itself supplies a clear English meaning beside or parallel to a foreign spoken form.

Requirements:

- exact localization key known
- foreign display text preserved exactly
- English meaning directly supported by game data
- all language families included

### Batch B — Cross-Localization Agreement

For unresolved English rows, compare the same key across official localization packs.

Priority:

- two or more official localizations independently resolve the same meaning
- note disagreements instead of forcing a consensus
- preserve game-specific transliteration

### Batch C — Lexical Families / Variants

Expand verified terms across spelling and transliteration variants.

Examples of the method:

```text
bachtalo / bakhtalo / baxtalo
T’aves / T-aves / Te aves
gadjo / gadjos
dikhes / deekhes / dikeh...
```

These are examples only, not a whitelist.

Rules:

- scan globally
- do not restrict to one NPC, quest, language, or region
- exact source spelling remains untouched
- variant relationship must be supported before release

### Batch D — Full-Foreign Subtitle Formatting

Audit every known full-foreign authored subtitle.

Required form:

```text
Original foreign subtitle
[English] Translation
```

Implementation rule:

- use explicit `<br/>` hard break
- never collapse the translation inline for convenience

### Batch E — Mixed-Language Cleanup

Clean up subtitles that technically translate correctly but read poorly.

Targets:

- repeated `[English: ...]` clutter
- adjacent foreign fragments that should be grouped
- duplicated meanings
- overlong explanatory wording
- translations that visually overpower the speaker

The original dialogue must remain unchanged.

### Batch F — Idioms and Manual Review

Hold uncertain idioms, puns, cultural references, and ambiguous lines.

Do not release a guessed translation.

Record:

- exact key
- exact game text
- possible language
- candidate meanings
- sources checked
- reason for hold

### Batch G — Regional Regression Sampling

Test a sample across both major authored-dialogue regions.

Suggested coverage:

- Trosecko
- Kutnohorsko
- Nomad camp
- merchants
- religious/learned dialogue
- race/wager dialogue
- cutscenes
- optional quest branches

The goal is broad confirmation, not repeated replay of one quest branch.

## Presentation Standard

### Mixed English + foreign phrase

Keep the sentence intact and gloss the foreign material inline.

### Entirely foreign subtitle

Original line first, English translation on a forced secondary line.

### Visual hierarchy

Target presentation:

- original speech: normal game subtitle appearance
- translation/gloss: subtle silver/light-gray treatment

The translation should be noticeable when needed and easy to ignore when not needed.

## Release Gate

A candidate can enter the live patch only when:

1. exact localization key is known
2. exact game text is preserved
3. meaning is verified
4. display type is classified
5. formatting rule is correct
6. duplicate-key check passes

Uncertain candidates remain in review data.

## Guiding Principle

**Preserve the performance. Supply the understanding.**
