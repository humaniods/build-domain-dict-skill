# Fillers: the recipe

A filler is what the agent says while the real reply is still being generated. It buys
~700ms (`deferred_ms`) of natural-sounding time and is cancelled if the reply lands
first.

Two rows are a **required floor**: `key: en` and `key: hi`. If the input names another
caller language (a brief that says "Tamil + English callers", a regional domain), add
that language's row too, using the same recipe as `en`/`hi`. Language fallback goes
user pool → built-in pool for that language → built-in default → **silence**. It never
substitutes English, so a missing row for a language the input actually calls for
means those callers get the built-in phrases or nothing.

## Value format

One phrase per line, using a YAML block scalar:

```yaml
fillers:
  - key: en
    value: |
      Mm-hmm
      Yes, please go ahead
      One moment, let me check…
```

The parser splits on **newline or `|`**. It also accepts a quoted list
(`"Haan…", "Ji, batayiye."`) because that is what people paste. It does **not** split on
commas: filler phrases routinely contain them. A comma-separated row becomes one giant
"phrase" and the agent reads the commas out loud.

`key` is normalized to the primary subtag, so `hi-IN` and `hi` are the same row and
phrases are deduped across them.

## Kind is derived from shape

Never declared, computed by `classify_filler()`:

| Shape | Kind | Plays when |
|---|---|---|
| ends in `…` or `...` | **hold** | work is in progress, reply not ready |
| ≤ 2 words | **backchannel** | caller is still talking (after `backchannel_after_ms`) |
| everything else | **ack** | heard you, answering now |

Checked top to bottom, first match wins. A phrase that is both short and trailing `…`
("Ek second…" is two words) is a **hold**, not a backchannel, because the ellipsis row
is checked first.

The ellipsis is functional, not cosmetic: the sentence flusher sends a chunk to TTS as
soon as it looks terminal, so a hold line ending in `…` plays *during* the wait instead
of being glued onto the front of the real reply. **A hold line without the ellipsis is
not a hold line.**

Write **3 to 5 phrases per kind per language**, enough that rotation does not repeat
audibly within a call.

## The content rule

A filler is spoken before the answer is known. So it may describe *activity*, never the
*object* of the activity.

| Write | Not |
|---|---|
| `Let me check…` | `Let me check your balance…` |
| `Ek second, main dekh leti hoon…` | `Ek second, main aapka claim status dekh leti hoon…` |

The right-hand column lies whenever the caller asked about something else, and the
filler fires before anything knows what they asked. Same reason fillers carry no domain
jargon: the register should match the domain (calm for a hospital, formal for a bank,
warm for real estate), the words should not.

Also avoid: promises (`I'll fix that for you…`), apologies for latency (`Sorry for the
delay…`, which draws attention to the wait), and questions (a filler that asks something
collides with the reply).

## Register is per domain, so the phrases are too

Two dictionaries for different domains must not ship the same filler pool. The words
carry no jargon, but they do carry a register, and register is domain-specific:

| Domain | Register | Reads like |
|---|---|---|
| hospital / clinic | calm, unhurried, never brisk | `Take your time`, `Let me look that up…` |
| banking / insurance | formal, precise, money-serious | `Understood`, `Let me verify that…` |
| real estate | warm, personal, helpful | `Of course`, `Just checking that for you…` |
| telecom / support | brisk, efficient | `Got it`, `Right away…` |

Write the pool for the domain in front of you. The rows below are a **shape** reference,
not a pool to paste: copying them verbatim into a domain dictionary is the single most
common way this file ends up domain-neutral, and `scripts/count_keyterms.py` flags it
when more than half the phrases match. `examples/insurance-dictionary.yaml` and
`examples/real-estate-dictionary.yaml` show the same recipe producing two different pools.

## Worked row pair

```yaml
fillers:
  - key: en
    value: |
      Mm-hmm
      Right
      Got it
      Yes, please go ahead
      Sure, I can help with that
      Absolutely, let me confirm that
      Let me check…
      One moment…
      Just pulling that up…
  - key: hi
    value: |
      Ji
      Achha
      Hmm
      Ji, bataiye
      Haan ji, sun rahi hoon
      Ji bilkul, batati hoon
      Theek hai, main dekh leti hoon
      Ek second…
      Main check karti hoon…
      Zara dekh leti hoon…
```

Verify the split by shape rather than by intent: **count the words**. `Ji, bataiye`
reads like an acknowledgement but is two words, so it lands in `backchannel`; the row
needs a longer phrase to have any ack at all. The rows above resolve to 3 backchannels
/ 3 acks / 3 holds for `en` and 4 / 3 / 3 for `hi`.

Grammatical gender in the Hindi phrases should match the agent's persona voice:
`karti` for a female persona, `karta` for male. Read the persona before writing them.

## Settings

Omit the `settings:` block unless changing a knob. An absent key preserves stored
values, while `{}` wipes them. Defaults, and the caveat that `selection: llm` falls back
to rotation on the worker path, are in `references/schema.md`.