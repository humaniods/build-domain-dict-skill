# The admission test: what earns a row

A Domain Dictionary is a **budget**, not a glossary. The STT keyterm list is capped at
50 tokens and every row spends 1 to 2 of them (`references/schema.md`). A term that "might
come up" does not sit harmlessly in the file; it evicts a term that does come up.

So each row is admitted, one at a time, by a test it either passes or fails.

## Vocabulary: the four gates

A vocabulary row is admitted when it passes **at least one** gate:

| Gate | Admits | Example |
|---|---|---|
| **G1: spelled aloud** | acronyms and initialisms callers say letter-by-letter | `EMI`, `IFSC`, `IRDAI`, `OPD`, `RERA` |
| **G2: jargon STT gets wrong** | domain words rare in general speech, or homophone-prone | `amortization`, `moratorium`, `fiduciary`, `cholecystectomy`, `encumbrance` |
| **G3: proper noun** | brands, products, schemes, regulators, plan names named in the input | `Ayushman Bharat`, `Jan Dhan`, a specific plan or branch name |
| **G4: spoken code format** | number/ID formats read out on calls | policy prefix `PL-`, account-number grouping |

G2's "homophone-prone" covers two different situations, and only one of them belongs in
`vocabulary`. `rider` vs `writer` is a **true collision**: two different words that sound
alike, where STT's default output favors the wrong one, and boosting `rider` shifts the
odds toward the right one. A term like `SIP` (investment plan) vs `sip` (drink) is **not**
a collision, it is the same word, case-insensitively identical, said the same way. There
is no alternate correct transcription for a keyterm to boost toward, so adding it as a
vocabulary row does nothing (`to_keyterms()` dedupes it against its own key). That kind
of ambiguity is resolved by conversational context downstream, not by this file. If the
term still needs to be said correctly out loud, give it a `pronunciation` row instead;
that is a real, separate fix.

Everything else fails. In particular these fail even though they are "domain-related":

- Common words the STT already transcribes correctly: `account`, `payment`, `doctor`,
  `rent`, `appointment`. Domain-relevant, zero recognition benefit, real cost.
- Terms from a neighbouring domain the input never mentions. A hospital dictionary does
  not get `EMI` because the clinic happens to offer instalments, unless the input says
  it does.
- Synonyms of a row already present. `KYC` is one row; `know your customer` is the
  `value` on that row, not a second row.
- Inflections. `mortgage` covers `mortgages`.

## The `# why:` comment is the test

Write the comment before the row. It names the gate and the evidence:

```yaml
vocabulary:
  - key: IRDAI                   # why: G1+G3 regulator, spelled aloud; named in brief
    value: I R D A I
  - key: encumbrance             # why: G2 jargon, misheard as "incumbrance"
    value: ""
```

If the comment needs a hedge to write, phrases like "may be relevant" or "commonly used
in this sector", the row fails. Hedging in the comment *is* the failure signal.

## Evidence by input type

| Input | What counts as evidence |
|---|---|
| Domain name only | Terms a caller in that domain demonstrably says. Prefer the domain's regulators, statutory acronyms, and core products over vocabulary an agent would use *about* the domain. |
| Prose brief | Terms, products, and names occurring in the brief, plus their spoken variants. The brief is the boundary: a term outside it needs a G1/G2 justification of its own. |
| YAML file | Terms occurring in the file: persona prose, node/prompt text, tool names, existing rows. Open the file first. Rows citing text you did not read are fabricated evidence. |

When the input is thin (a bare domain name), produce a **short** dictionary and say it is
a starting set, rather than padding to look complete. 8 well-gated rows beat 30 guesses.

## Pronunciation: a narrower gate

Pronunciation rows are a subset, admitted only when the default TTS reading is *wrong*:

- Acronyms read as words: `IRDAI` → `eye-ar-dee-ay-eye`, `EMI` → `ee-em-eye`.
- Loanwords and non-English proper nouns.
- Terms with a contested stress or a silent letter.

Do not mirror the whole vocabulary section. A word the TTS already says correctly gets
no row; a row with an empty `value` is dropped by the runtime anyway.

Respelling style: lowercase, hyphen-separated syllables, ordinary English graphemes
(`ee-em-eye`, `am-or-ti-ZAY-shun`). No IPA: the runtime's `ipa` field is always `None`.

## Fillers stay out of the domain

Fillers are the one section that must *not* carry domain terms. They play before the
answer exists, so a filler naming a specific fact or action can contradict the reply that
follows. Match the domain's **register** (a hospital's calm, a bank's formality), never
its vocabulary. Details in `references/fillers.md`.

## Self-check before saving

- Every vocabulary and pronunciation row has a hedge-free `# why:`.
- Keyterm tokens (non-empty keys + non-empty values) ≤ 40.
- No row is a synonym, inflection, or common word.
- Pronunciation rows all have non-empty values.
- Fillers name no domain object.
- Filler phrases are written for *this* domain's register, not pasted from
  `references/fillers.md` or from another domain's example file.
- Each language row has 3-5 phrases per kind (backchannel / ack / hold).
- `en` and `hi` filler rows both present, plus a row for any other caller language the
  input names.
- No vocabulary or pronunciation row was carried over from another domain's dictionary;
  each one traces to *this* input.
- Keyterm budget, dead pronunciation rows, and filler-language coverage verified with
  `scripts/count_keyterms.py`, not counted by hand.