# Domain Dictionary schema and contracts

Ground truth: `supervoice/src/supervoice/domain_dictionary.py`,
`supervoice/src/supervoice/platform/routers/domain_dictionaries.py`,
`supervoice/src/supervoice/dictionaries/*.yaml`.

This document is a snapshot and will drift as the codebase does. If a field, cap, or
path here looks stale, or you have working-directory access to the supervoice repo,
open the actual source above rather than trust this file from memory, the same way
you would not generate a row for a YAML you have not read.

## Shape

```yaml
domain: <key>                    # canonical key; stem of the seed filename
vocabulary:                      # STT
  - key: <term>
    value: <variant / misheard-as>   # may be "" when the term needs no alias
pronunciation:                   # TTS
  - key: <term>
    value: <grapheme respelling>     # required; empty value = row is dropped
fillers:                         # latency
  - key: <language code>
    value: |
      <phrase>
      <phrase>
settings: {}                     # filler knobs; see below
```

Every section is a list of `{key, value}` pairs (`KVItem`). Both fields are strings
and are stripped on load. `agent_ids` exists on the stored document but is written by
the platform (attach/detach), never by hand.

Seed files under `src/supervoice/dictionaries/` carry `vocabulary` and
`pronunciation` only, fillers there are user-authored, per product decision. A file
produced by this skill is a **tenant** artifact pasted through the panel, so it may
carry all three sections.

## Domain name normalization

`normalize_domain()` lower-cases, then maps through an alias table, then falls back to
substring matching (longest alias first). Unmapped names return `None`.

| Input contains | Canonical key |
|---|---|
| `real estate`, `realestate`, `real-estate`, `realty`, `property`, `housing` | `real_estate` |
| `banking`, `bank`, `finance`, `financial`, `fintech`, `lending`, `loan`, `insurance` | `banking` |
| `hospital`, `healthcare`, `health care`, `health`, `medical`, `clinic` | `hospital` |

Consequences worth stating to the user:

- `insurance` resolves to the **banking** seed. Insurance-specific rows are additive
  on top of banking's, so do not restate banking terms the seed already has.
- An unmapped domain (`logistics`, `edtech`) gets `resolved_key: null` and an empty
  seed. Your file is then the entire dictionary, so it must be self-sufficient.

## Runtime projections

| Method | Produces | Notes |
|---|---|---|
| `to_keyterms()` | flat keyterm list | emits **key and value** of every row, order-preserving, case-insensitively deduped |
| `to_pronunciation_entries()` | `{term, say, ipa}` | rows with an empty `value` are **skipped**; `ipa` is always `None` |
| `to_filler_pool()` | `{phrase, lang, kind}` per phrase | language normalized, `(lang, phrase)` deduped across rows |

`merge_dictionaries()` layers tenant rows over seed rows by key: a tenant row with
the same key replaces the seed's value rather than duplicating it.

## Keyterm budget

`DEEPGRAM_KEYTERM_CAP = 50` (`speech/languages.py`), applied in `speech/failover.py`
for the Deepgram provider. Because `to_keyterms()` emits key *and* value, a row with
a non-empty value costs **2** tokens, a row with `value: ""` costs 1. Dictionary
keyterms are also merged with other sources (agent-level keyterms, language defaults),
so the dictionary should not spend the whole cap.

**Target ≤ 40 tokens**: roughly 15 to 20 rows with values, or up to 40 bare rows.

The 50-token cap above is Deepgram's specifically. If the agent's STT provider for
this domain is not Deepgram, for example Sarvam, Soniox, smallestai, or gnani in the
failover pool, check that provider's own keyterm/vocabulary limit in
`speech/languages.py` before assuming 50 applies. Don't carry the Deepgram number over
silently to a different provider.

## Filler settings

`FILLER_SETTINGS_DEFAULTS`:

```yaml
settings:
  enabled: true
  selection: llm          # falls back to rotation in the media worker (no LLM there)
  deferred_ms: 700        # wait this long before speaking a filler
  backchannel_after_ms: 5000
  kinds: {ack: true, hold: true, backchannel: true}
```

`kinds` merges one level deep, so disabling one kind leaves the other two at their
defaults. Two contracts:

- On upsert, an **absent** `settings` key means "keep the stored knobs". Sending `{}`
  wipes them. Omit the block entirely unless you are deliberately changing a knob.
- `selection: llm` is aspirational on the worker path: the media worker has no LLM and
  logs a fallback to rotation. Do not promise LLM-chosen fillers.

## Attachment invariant

One playbook = one domain. `attach_agent_exclusive()` is the single writer of
`agent_ids` and pulls the agent out of every other domain before adding it. Attaching
an agent to a new domain therefore detaches it from its previous one. Clearing a
playbook's domain detaches it everywhere.

## The write path that actually reaches a call

The supervoice worker builds its `SpeechConfig` from the Mongo `sv_voice_profiles`
document, **not** from the playbook YAML. Vocabulary and fillers reach a call only
once the dictionary is saved *and the agent attached*, so the publish path can bake
them into that document. A dictionary that is saved but never attached changes
nothing on a call. Say so when handing the file over.