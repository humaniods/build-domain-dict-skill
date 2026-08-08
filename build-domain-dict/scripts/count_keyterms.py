#!/usr/bin/env python3
"""
Deterministic checks for a supervoice Domain Dictionary YAML.

Why this exists: keyterm-token counting (to_keyterms: key and value of every
vocabulary row, order-preserving, case-insensitively deduped) is arithmetic,
not judgment, so it should not be eyeballed against a written-out budget.
Run this before handing a dictionary over.

Usage:
    python scripts/count_keyterms.py <path-to-dictionary.yaml>
"""
import sys

try:
    import yaml
except ImportError:
    print("PyYAML is required: pip install pyyaml --break-system-packages", file=sys.stderr)
    sys.exit(1)

DEEPGRAM_KEYTERM_CAP = 50
TARGET_BUDGET = 40
REQUIRED_FILLER_LANGS = {"en", "hi"}
MIN_PER_KIND = 3
MAX_PER_KIND = 5

# The worked rows in references/fillers.md, which are a shape reference and not a
# pool to paste. Reusing them wholesale means the file carries no domain register,
# so a large overlap is flagged rather than silently shipped. Neither shipped
# example draws on this set: both write their own pool for their own register.
REFERENCE_PHRASES = {
    "mm-hmm", "right", "got it", "yes, please go ahead",
    "sure, i can help with that", "absolutely, let me confirm that",
    "let me check…", "one moment…", "just pulling that up…",
    "ji", "achha", "hmm", "ji, bataiye", "haan ji, sun rahi hoon",
    "ji bilkul, batati hoon", "theek hai, main dekh leti hoon",
    "ek second…", "main check karti hoon…", "zara dekh leti hoon…",
}
REFERENCE_OVERLAP_LIMIT = 0.5


def to_keyterms(vocabulary_rows):
    """Mirrors to_keyterms(): key and value of every row, order-preserving,
    case-insensitively deduped, across the whole section."""
    seen = set()
    terms = []
    for row in vocabulary_rows:
        for field in ("key", "value"):
            raw = (row.get(field) or "").strip()
            if not raw:
                continue
            norm = raw.lower()
            if norm in seen:
                continue
            seen.add(norm)
            terms.append(raw)
    return terms


def check_pronunciation(rows):
    """Rows with an empty value are dropped by to_pronunciation_entries() at
    runtime, so they are dead weight in the file."""
    return [r.get("key", "?") for r in rows if not (r.get("value") or "").strip()]


def classify_filler(phrase):
    """Mirrors classify_filler(): shape decides kind, checked top to bottom,
    first match wins (fillers.md)."""
    text = phrase.strip()
    if text.endswith("…") or text.endswith("..."):
        return "hold"
    if len(text.split()) <= 2:
        return "backchannel"
    return "ack"


def check_fillers(rows):
    issues = []
    langs = set()
    kind_counts = {}
    all_phrases = []
    for row in rows:
        key = (row.get("key") or "").strip()
        value = row.get("value") or ""
        lang = key.split("-")[0].lower() if key else "?"
        if key:
            langs.add(lang)
        lines = [ln.strip() for ln in value.split("\n") if ln.strip()]
        counts = kind_counts.setdefault(lang, {"backchannel": 0, "ack": 0, "hold": 0})
        for line in lines:
            all_phrases.append(line.lower())
            counts[classify_filler(line)] += 1
            # crude heuristic: a single "line" that is really several
            # comma-separated phrases glued together (parser splits on
            # newline, not comma, per fillers.md)
            if line.count(",") >= 2:
                issues.append(
                    f"key={key!r}: line has {line.count(',')} commas, check it "
                    f"is not several phrases collapsed into one: {line!r}"
                )

    # 3-5 phrases per kind per language, so rotation does not repeat audibly.
    for lang, counts in sorted(kind_counts.items()):
        for kind, n in counts.items():
            if n < MIN_PER_KIND:
                issues.append(
                    f"key={lang!r}: only {n} {kind} phrase(s), need "
                    f"{MIN_PER_KIND}-{MAX_PER_KIND}"
                )
            elif n > MAX_PER_KIND:
                issues.append(
                    f"key={lang!r}: {n} {kind} phrases, more than {MAX_PER_KIND}"
                )

    # Copied straight from the reference/example rows = no domain register.
    if all_phrases:
        reused = [p for p in all_phrases if p in REFERENCE_PHRASES]
        if len(reused) / len(all_phrases) > REFERENCE_OVERLAP_LIMIT:
            issues.append(
                f"{len(reused)}/{len(all_phrases)} filler phrases are copied from the "
                f"reference rows in fillers.md; rewrite them in this domain's register"
            )

    missing_required = REQUIRED_FILLER_LANGS - langs
    return issues, missing_required, langs, kind_counts


def main():
    if len(sys.argv) != 2:
        print("usage: count_keyterms.py <dictionary.yaml>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path) as f:
        doc = yaml.safe_load(f) or {}

    vocabulary = doc.get("vocabulary") or []
    pronunciation = doc.get("pronunciation") or []
    fillers = doc.get("fillers") or []

    terms = to_keyterms(vocabulary)
    token_count = len(terms)

    print(f"domain: {doc.get('domain', '?')}")
    print(f"vocabulary rows: {len(vocabulary)}")
    print(
        f"keyterm tokens after dedupe: {token_count} "
        f"(target <= {TARGET_BUDGET}, hard cap {DEEPGRAM_KEYTERM_CAP} on Deepgram)"
    )
    if token_count > TARGET_BUDGET:
        print(f"  OVER TARGET by {token_count - TARGET_BUDGET}: trim rows or drop values")
    if token_count > DEEPGRAM_KEYTERM_CAP:
        print("  OVER HARD CAP: rows past this point are effectively wasted at runtime")

    dead_pron = check_pronunciation(pronunciation)
    if dead_pron:
        print(f"pronunciation rows with empty value (dead weight, drop these): {dead_pron}")

    filler_issues, missing_required, langs, kind_counts = check_fillers(fillers)
    print(f"filler languages present: {sorted(langs) if langs else '(none)'}")
    for lang, counts in sorted(kind_counts.items()):
        print(
            f"  {lang}: {counts['backchannel']} backchannel / {counts['ack']} ack "
            f"/ {counts['hold']} hold"
        )
    if missing_required:
        print(f"MISSING required filler language row(s): {sorted(missing_required)}")
    for issue in filler_issues:
        print(f"filler warning: {issue}")

    if token_count <= TARGET_BUDGET and not dead_pron and not missing_required and not filler_issues:
        print("\nAll deterministic checks pass.")


if __name__ == "__main__":
    main()
