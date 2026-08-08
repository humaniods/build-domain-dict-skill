# build-domain-dict

[![Claude Code](https://img.shields.io/badge/Claude%20Code-compatible-D97757?logo=anthropic&logoColor=white)](https://github.com/humaniods/build-domain-dict-skill)
[![Codex](https://img.shields.io/badge/Codex-compatible-412991?logo=openai&logoColor=white)](https://github.com/humaniods/build-domain-dict-skill)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Built by **Sanyam Sharma** — Voice AI Engineer, [Unpod AI](https://unpod.ai)

A skill for authoring **supervoice Domain Dictionaries** — the per-domain STT vocabulary,
TTS pronunciation, and latency filler sets that a voice agent uses on a call.

You give it a domain name, a prose brief, or an existing playbook/dictionary YAML. It
produces one `<domain>-dictionary.yaml` file to paste into the playground's Dictionaries
pane.

Works identically in **Claude Code and Codex** — both load the same `SKILL.md` +
`references/` format natively, no conversion needed.

```mermaid
flowchart LR
    input(["domain name / prose brief / playbook YAML"]) --> dict[Domain Dictionary YAML]
    dict --> voc[vocabulary]
    dict --> pron[pronunciation]
    dict --> fill[fillers]
    voc -->|to_keyterms| stt["STT keyterm list, fixes mishears"]
    pron -->|to_pronunciation_entries| tts["TTS respelling, fixes mispronunciation"]
    fill -->|to_filler_pool| lat["filler phrase pool, fills the dead air"]
    stt --> call(["live call"])
    tts --> call
    lat --> call
```

## The problem it solves

Three separate call failures come from the same missing artifact:

- The agent **mishears** domain jargon (`IFSC` → "if sec", `rider` → "writer") because
  nothing told the STT which terms to expect.
- The agent **mispronounces** acronyms, reading `IRDAI` as a word.
- The agent leaves **dead air** while the LLM generates, because it has no filler pool in
  the caller's language.

Hand-written dictionaries then fail a second way: they get padded with plausible-sounding
domain words. That is not harmless: the STT keyterm list is capped (50 for Deepgram) and
every row spends 1 to 2 tokens of it, so speculative terms **evict the real ones**. Most of
this skill is the admission test that keeps that from happening.

## How each section works

### `vocabulary` → fixes what the agent *hears* (STT)

An STT model decodes audio into the most probable word sequence given its general
language model. "General" is the problem: `rider` is a rare word, `writer` is a common
one, so on a policy call the acoustically-identical input comes back as the wrong one.
The model is not broken, it is correctly applying the wrong prior.

A keyterm list re-weights that decision. Terms you send get boosted during decoding, so
the domain word wins the tie it was losing:

```yaml
vocabulary:
  - key: rider        # the term you want back
    value: writer     # what the STT returns today
  - key: IRDAI
    value: I R D A I  # how callers actually say it — letter by letter
```

Both fields are sent to the STT. `key` is the term to boost; `value` is a second surface
form worth boosting too — either the mishearing you are correcting (`writer`) or the
spoken-out variant (`I R D A I`, `no claim bonus`). Leave `value` empty when the term has
only one form:

```yaml
  - key: subrogation  # claims jargon; general STT mangles it, no common confusion to name
    value: ""
```

**The cap is why the admission test exists.** Deepgram accepts 50 keyterms. Every non-empty
field spends one. A row for `premium` or `policy` — words the STT already gets right —
spends budget and returns nothing, and at the cap it pushes out a term that needed the
help. So each row must pass four gates in [`references/relevance.md`](build-domain-dict/references/relevance.md)
and carry a `# why:` comment naming which gate it passed. A row whose comment you cannot
write does not go in the file.

### `pronunciation` → fixes what the agent *says* (TTS)

Separate failure, opposite direction. TTS applies letter-to-sound rules to whatever text
the LLM produced. `IRDAI` looks pronounceable, so it gets read as a word — "ird-eye".
`TPA` becomes "tpah". `subrogation` gets stress on the wrong syllable.

A pronunciation row replaces the reading:

```yaml
pronunciation:
  - key: IRDAI                 # written form the LLM emits
    value: eye-ar-dee-ay-eye   # how to SAY it
  - key: subrogation
    value: sub-ro-GAY-shun     # caps mark the stressed syllable
```

Grapheme respelling, never IPA — the TTS reads the value as text.

**Two independent problems, so two independent sections.** Fixing the STT does nothing for
the TTS. `IRDAI` appears in both because callers mis-say it *and* the agent mis-reads it.
`rider` appears only in `vocabulary` (heard wrong, said fine). `subrogation` needs a
pronunciation row for stress but no `value` in vocabulary because nothing else sounds like
it. Only add a pronunciation row when the default reading is actually wrong — a row with an
empty value is dropped at runtime and is dead weight in the file.

### `fillers` → hides the latency you cannot remove

After the caller stops speaking, the turn still has to finish endpointing, run the LLM to
its first token, and get audio back from the TTS. That gap is real and mostly not
removable. What you *can* remove is the **silence**, because silence is what makes the gap
feel like a fault — callers repeat themselves, say "hello?", or hang up.

```
caller stops ──▶ [ endpoint ][ LLM thinking ][ TTS ]──▶ reply
                              ▲
                              └── ~700ms in: filler plays ("Let me verify that…")
                                  cancelled if the reply lands first
```

The filler occupies the gap with something a human would say there. Same wall-clock
latency, no dead air. Three kinds cover three moments:

| Kind | Plays when | Example |
|---|---|---|
| **backchannel** | caller is still talking | `Mm-hmm`, `Jee` |
| **ack** | heard you, answering now | `Yes, I can help you with that` |
| **hold** | work in progress, reply not ready | `Let me verify that…` |

**Kind is never declared — it is derived from the phrase's shape**, first match wins:
trailing `…` → hold, ≤ 2 words → backchannel, everything else → ack. So `Ek second…` is a
hold, not a backchannel, despite being two words. And a hold line written without the
ellipsis is not a hold line: the ellipsis makes the sentence flusher send that chunk to TTS
immediately, so it plays *during* the wait instead of getting glued onto the front of the
real reply.

Two rules that are easy to get wrong:

- **Describe the activity, never its object.** `Let me check…` is safe; `Let me check your
  balance…` fires before anything knows what the caller asked, so it lies whenever they
  asked about something else.
- **`en` and `hi` are a floor, not a ceiling.** Language fallback goes user pool → built-in
  pool for that language → built-in default → **silence**. It never substitutes English, so
  a Marathi caller with no `mr` row gets built-in phrases or nothing.

### Same recipe, different output per domain

Fillers carry no jargon, but they do carry a **register**, and register is domain-specific.
A hospital agent should not sound like a collections call. The two shipped examples were
built by the same recipe and share nothing:

| | insurance | real estate | shared |
|---|---|---|---|
| `fillers` en / hi | 9 / 9 | 9 / 9 | **0** |
| `vocabulary` (keyterm tokens) | 19 | 6 | **0** |
| `pronunciation` | IRDAI, ULIP, TPA, NCB, PED, subrogation | RERA | **0** |

That is enforced, not hoped for: vocabulary and pronunciation rows must trace to *this*
input, and `count_keyterms.py` flags a dictionary whose filler phrases are more than half
copied from the reference rows. Insurance reads formal and money-serious (`Understood`,
`Let me verify that…`); real estate reads warm (`Of course`, `Just checking that for
you…`). Same shape, different voice.

## Three bugs that look fine in review and only fail on a call

This is most of why the skill exists. Each of these passes a YAML linter, passes a human
skim, and then misbehaves live.

**1. The missing ellipsis.** These two lines are not the same thing:

```yaml
Let me verify that…    # hold — plays DURING the wait
Let me verify that     # ack — glued onto the front of the real reply
```

Kind is derived from shape, never declared. The sentence flusher sends a chunk to TTS as
soon as it looks terminal, and the ellipsis is what makes it look terminal. Drop it and
the phrase stops covering the gap it was written for — the dead air is still there, and
the caller now hears a redundant preamble on the answer instead.

**2. Commas instead of newlines.** The parser splits on newline, not comma, because filler
phrases routinely contain commas:

```yaml
value: "Mm-hmm, Right, Got it"   # ONE phrase; the agent reads the commas out loud
value: |                          # three phrases
  Mm-hmm
  Right
  Got it
```

**3. A missing language row is silence, not English.** Language fallback goes user pool →
built-in pool for that language → built-in default → **silence**. It never falls back to
English. So a brief that says "Marathi and English callers" and a dictionary with only
`en` + `hi` means Marathi callers get built-in phrases or nothing at all — while the file
looks complete, because the required floor is satisfied.

All three are arithmetic once you know to look, which is why `count_keyterms.py` checks
them mechanically instead of leaving them to a careful reader.

## Install

### Codex

Its built-in `skill-installer` skill installs directly from this repo — no manual clone:

```
scripts/install-skill-from-github.py --repo humaniods/build-domain-dict-skill --path build-domain-dict
```

(or just ask Codex to "install the build-domain-dict skill from
`humaniods/build-domain-dict-skill`" — the installer is already there.)

### Claude Code

This repo is both a plugin and a single-plugin marketplace (`.claude-plugin/plugin.json`
and `.claude-plugin/marketplace.json` at the root):

```
/plugin marketplace add humaniods/build-domain-dict-skill
/plugin install build-domain-dict-skill
```

Or without the plugin system, copy the skill folder directly:

```bash
git clone https://github.com/humaniods/build-domain-dict-skill
cp -r build-domain-dict-skill/build-domain-dict ~/.claude/skills/

# project-scoped instead
cp -r build-domain-dict-skill/build-domain-dict <repo>/.claude/skills/
```

Both tools auto-discover the skill from `SKILL.md`'s frontmatter once installed. A copy
into `~/.claude/skills/` is normally picked up without a restart; restart the CLI if it
does not show up.

### One requirement

`scripts/count_keyterms.py` needs PyYAML:

```bash
pip install pyyaml
```

Without it the skill still writes the dictionary, but the deterministic keyterm-budget
check is skipped — and that check is the part that catches a padded file.

## Use it

A skill isn't a program you run — it's instructions the assistant loads into context so it
follows this exact workflow and admission test instead of whatever it would normally do.
Ask any assistant for "a dictionary for a hospital voice agent" without the skill and you
get a plausible, padded list with no `# why:` trace and no keyterm budget. That is the
difference the skill makes.

Once installed, there are two ways to bring it in.

**Describe the task in plain language.** Both tools read the skill's description and
auto-load it when what you're asking matches — no command needed:

```
build a dictionary for a hospital voice agent
the agent keeps saying IRDAI wrong
callers keep getting dead air before the answer
add vocabulary for this insurance playbook
```

Note the third one: you never have to know the phrase "domain dictionary" to reach it.
Describing the *symptom* is enough.

**Or call it directly with the slash command**, in either Claude Code or Codex, if you
want to be explicit:

```
/build-domain-dict for insurance
```

Type that (the skill's name, from `build-domain-dict/SKILL.md`), then say what you want.
Installed via the plugin system, the command is namespaced:
`/build-domain-dict-skill:build-domain-dict`.

Either way the assistant now works through the same steps: read the input and build an
evidence set → admit vocabulary rows only through the four gates → add pronunciation rows
only where the default TTS reading is wrong → write fillers in this domain's register →
run the deterministic check before handing the file over.

### Which input should you give it?

All three work; they differ in how much the skill has to assume.

| You have | Give it | What it grounds rows in |
|---|---|---|
| Only a domain name | `for hospital` | Terms a caller in that domain demonstrably says. Thinnest evidence, so expect a short file — that is correct behaviour, not laziness. |
| A description of the agent | The brief, in prose | The products, actions, brand names, and languages named in your text. |
| An existing playbook / dictionary YAML | The file path | Terms that literally appear in the persona, prompts, and node text. **Strongest evidence.** The skill reads the file first and will not generate for a path it has not opened. |

Naming your caller languages in the brief matters: "Marathi and English callers" adds an
`mr` row on top of the `en` + `hi` floor. Leave it out and those callers may hit silence.

### End to end

```bash
mkdir -p ~/dicts && cd ~/dicts   # the file is written to the working directory
claude
```

```
/build-domain-dict outbound renewal agent for a health insurer, Hindi + English callers
```

You get `insurance-dictionary.yaml`, with a `# why:` comment on every vocabulary and
pronunciation row naming the gate it passed, and a header comment listing what was
**excluded** and why. The skill then runs the checker itself; you can re-run it any time:

```bash
python3 ~/.claude/skills/build-domain-dict/scripts/count_keyterms.py insurance-dictionary.yaml
```

```
domain: insurance
vocabulary rows: 12
keyterm tokens after dedupe: 19 (target <= 40, hard cap 50 on Deepgram)
filler languages present: ['en', 'hi']
  en: 3 backchannel / 3 ack / 3 hold
  hi: 3 backchannel / 3 ack / 3 hold

All deterministic checks pass.
```

The script checks only what is arithmetic — keyterm budget, dead pronunciation rows,
missing filler languages, kind counts, and copied reference phrases. Read the `# why:`
comments yourself; that is the part no script can verify.

### Then install it on the agent

Playground → the agent's **Dictionaries** pane → pick or create the domain → paste each
section → save → **attach the dictionary to the agent**.

A dictionary that is saved but never attached changes nothing on a call. This is the most
common reason a correct file appears to do nothing.

### Extending an existing dictionary

Point the skill at the dictionary you already have. It reads the current rows as evidence
and adds to them rather than regenerating from scratch:

```
/build-domain-dict the agent keeps mispronouncing our product names, here's the current file: insurance-dictionary.yaml
```

## Contents

| File | Purpose |
|---|---|
| `.claude-plugin/plugin.json` | Plugin manifest for `/plugin install` |
| `.claude-plugin/marketplace.json` | Marketplace manifest, so `/plugin marketplace add humaniods/build-domain-dict-skill` resolves this repo |
| `build-domain-dict/SKILL.md` | Trigger, workflow, quick reference |
| `build-domain-dict/references/schema.md` | Exact YAML shape, runtime projections, keyterm budget, settings knobs, alias table |
| `build-domain-dict/references/relevance.md` | The admission test: four gates, evidence rules, exclusions |
| `build-domain-dict/references/fillers.md` | Filler recipe: `en` + `hi` rows plus any language the input names, shape-derived kinds, the content rule |
| `build-domain-dict/scripts/count_keyterms.py` | Deterministic keyterm-budget, dead-pronunciation-row, and filler-language check, run before handing the file over |
| `build-domain-dict/examples/insurance-dictionary.yaml` | Worked example: acronym-heavy domain, built from a prose brief |
| `build-domain-dict/examples/real-estate-dictionary.yaml` | Worked example: ordinary-word-phrase domain, built by reading an existing playbook file |
| `evals/evals.json` | Test prompts for the skill-creator eval loop, plus the sample playbook the third one reads |

## Author

**Sanyam Sharma** — Voice AI Engineer, [Unpod AI](https://unpod.ai)

This skill came out of production voice-agent failures rather than from a spec: STT
mishearing domain jargon, TTS reading acronyms as words, and dead air before the LLM's
first token. Each of the three sections maps to one of those.

The part worth reading is the admission test in `references/relevance.md`. It exists
because the STT keyterm list is capped at 50 on Deepgram and every row spends 1-2 tokens
of it, so a dictionary padded with plausible domain words silently **evicts the terms that
actually needed boosting**. The four gates, the `# why:` comment requirement on every row,
and the deterministic `count_keyterms.py` check are all there to make that failure
impossible to ship by accident.

## License

MIT © 2026 Sanyam Sharma, Unpod AI