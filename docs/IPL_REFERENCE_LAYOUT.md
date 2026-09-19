# IPL English Reference Layout

The IPL reference set supports **overhead dialogue, ambient speech, combat chatter, crime reactions, regional barks, and full Cuman/Nomad coverage** without requiring the entire `IPL_english.pak` to live in the repository.

## Recommended extracted layout

```text
reference/
└─ IPL_english/
   ├─ trosecko/
   │  ├─ README.md
   │  └─ <relevant extracted dialogue trees>
   ├─ kutnohorsko/
   │  ├─ README.md
   │  └─ <relevant extracted dialogue trees>
   └─ open_world/
      ├─ battle_barks/
      ├─ combat/
      ├─ crime_reaction_barks/
      ├─ dog/
      ├─ minihry/
      └─ other_relevant_dialogue/
```

## Priority order

1. **Trosecko / Nomad-Cuman cluster**
   - Voivode
   - Aranka
   - Mikolai
   - Mordecai
   - nearby Nomad/Cuman NPCs
   - camp quests, greetings, wagers, races, incidental responses
2. **Open-world overhead dialogue**
   - battle barks
   - crime reactions
   - generic combat/search chatter
3. **Kutnohorsko regional dialogue**
4. Remaining IPL dialogue families

## Extraction rule

Do not commit the entire `IPL_english.pak` unless the repository is deliberately moved to a large-file solution. Extract only useful dialogue trees and preserve their original relative paths.

## Why preserve paths?

This lets another language maintainer compare:

```text
English IPL path
<-> target-language IPL path
```

without guessing where corresponding bark/dialogue families live.

## Corpus admission rule

A row enters the release patch only after:
- exact localization key is known,
- original text is preserved,
- translation is verified,
- line type is classified as mixed-language or full-foreign,
- representative in-game behavior is tested in a batch/regression pass when practical.
