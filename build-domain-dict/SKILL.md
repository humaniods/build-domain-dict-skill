---
name: build-domain-dict
description: Use when a voice agent mishears domain jargon, mispronounces acronyms, or leaves dead air before it answers, meaning a supervoice Domain Dictionary (STT vocabulary, TTS pronunciation, latency fillers) needs to be authored or extended for a domain such as banking, hospital, or real estate, starting from a bare domain name, a prose brief, or an existing playbook/dictionary YAML. Trigger on requests like "build a dictionary for a hospital voice agent," "the agent keeps saying IRDAI wrong," "add vocabulary for this insurance playbook," or "callers keep getting dead air before the answer," even if the user never says "domain dictionary" by name.
---

# Build Domain Dictionary

Author a supervoice **Domain Dictionary**: three sections that fix three distinct
call failures:

| Section | Fixes | Runtime path |
|---|---|---|
| `vocabulary` | STT mishears jargon | keyterms sent to the STT provider |
| `pronunciation` | TTS mangles acronyms/names | `{term, say}` respellings |
| `fillers` | dead air while the LLM thinks | phrase pool, bucketed by kind |

Output is **one YAML file** the user pastes into the playground's Dictionaries pane.
This skill does not call the API and does not write into the product repo.

## Workflow

1. **Read the input and build an evidence set.** Three input shapes:
   - *domain name* (`banking`, `hospital`, `real estate`) → evidence = standard terms
     a caller says in that domain.
   - *prose brief* → evidence = the terms, products, and brand names in the text.
   - *YAML file* (playbook or existing dictionary) → evidence = terms that actually
     appear in it (personas, prompts, node text, existing rows). Read the file first;
     never generate for a YAML you have not opened.
2. **Name the domain.** Free text is normalized by `normalize_domain()`. Check
   `references/schema.md` for the alias table: `insurance` resolves to `banking`,
   `clinic` to `hospital`. An unmapped name is fine: it just means no seed exists and
   your file is the whole dictionary.
3. **Write `vocabulary`.** Every row must pass the admission test in
   `references/relevance.md`. Stay inside the keyterm budget stated there.
4. **Write `pronunciation`.** Only terms whose default TTS reading is wrong.
   Grapheme respelling, never IPA.
5. **Write `fillers`.** `en` and `hi` rows are a REQUIRED floor, not a ceiling: if the
   input names another caller language (a brief that says "Tamil + English callers",
   a domain that is regional), add that language's row too, same recipe. Each row
   covers all three kinds. Recipe and kind rules: `references/fillers.md`.
6. **Save `<domain>-dictionary.yaml`** in the working directory, with a `# why:`
   comment on every vocabulary and pronunciation row. Then run the checker, whose
   path is relative to *this file's* directory, not the working directory:
   `python3 <dir-of-SKILL.md>/scripts/count_keyterms.py <domain>-dictionary.yaml`.
   The keyterm count, dead pronunciation rows, and missing filler languages are all
   arithmetic, not judgment, so verify them with the script instead of counting by
   hand. Needs PyYAML (`pip install pyyaml`); if it is missing, say so rather than
   skipping the check.
7. **Tell the user to add it**: playground → agent's **Dictionaries** pane → pick or
   create the domain → paste each section → save, then attach the agent.

## Every row is grounded

A row is admitted only when it is traceable to the input: a term present in the
supplied text/YAML, or a term a caller in the named domain demonstrably says. The
`# why:` comment is where that trace goes; a row whose comment you cannot write is a
row that does not belong in the file.

The budget makes this load-bearing, not stylistic: the STT keyterm list is capped
(50 for Deepgram) and **both** key and value of every row consume it. Speculative
terms do not sit harmlessly in the file: they evict real ones.

## Quick reference

```yaml
domain: insurance
vocabulary:                      # STT, key = term, value = variant / misheard-as
  - key: IRDAI                   # why: regulator, said letter-by-letter on calls
    value: I R D A I
pronunciation:                   # TTS, key = term, value = how to SAY it
  - key: IRDAI                   # why: TTS reads it as a word
    value: eye-ar-dee-ay-eye
fillers:                         # key = language code, value = one phrase per line
  - key: en
    value: |
      Mm-hmm
      Yes, please go ahead
      One moment, let me check…
```

Kind is derived from phrase **shape**, not declared, checked top to bottom, first
match wins: trailing `…` → hold, ≤2 words → backchannel, else ack. A two-word phrase
that also ends in `…` ("Ek second…") is still a hold, because the ellipsis check runs
first. A hold line without the ellipsis is not a hold line.

See `examples/insurance-dictionary.yaml` for a complete file, built from a prose
brief for a health+motor renewal agent. It shows what gets admitted (`IRDAI`, `ULIP`,
`TPA`...) and, just as importantly, what gets excluded in a comment (`premium`,
`policy`, `RERA`) with the reason each one failed the admission test.
`examples/real-estate-dictionary.yaml` covers the harder case: a domain where the
jargon is mostly ordinary-word phrases (`carpet area`, `builder-buyer agreement`)
rather than acronyms, built from reading an existing playbook file's persona and
prompts rather than a bare brief.

## Common mistakes

| Mistake | Consequence |
|---|---|
| Comma-separating filler phrases | The whole row becomes one phrase; the agent reads the commas out loud. Use one per line. |
| Padding vocabulary with common words | Evicts real keyterms at the 50-token cap. |
| Pronunciation row with an empty value | Dropped by `to_pronunciation_entries()`, dead weight. |
| Hold filler that names the action's object ("checking your balance…") | Plays before the answer exists, so it lies when the question was about something else. |
| Only `en` fillers, or missing a language the input clearly names | That language's callers get built-in fallback or silence, never English. `en`+`hi` are the required floor; add more when the input calls for them. |
| Pasting the worked filler rows from `references/fillers.md` into every domain | Every domain ships the same voice. Register is domain-specific (calm hospital, formal bank, warm real estate); `count_keyterms.py` flags a >50% match against the reference rows. |
| Reusing another domain's vocabulary/pronunciation rows because the domains "feel similar" | Rows must trace to *this* input. Overlap is legitimate only through the seed merge (`insurance`→`banking`), which happens at runtime and is not restated in the file. |
| Vocabulary row where key and value are the same word, different case (`SIP`/`sip`) | `to_keyterms()` dedupes case-insensitively, so it boosts nothing. Real collisions (`rider`/`writer`) are two different words; same-word ambiguity needs a `pronunciation` row, not this. |
| Generating from a YAML path without reading it | Rows cite evidence that isn't there. |