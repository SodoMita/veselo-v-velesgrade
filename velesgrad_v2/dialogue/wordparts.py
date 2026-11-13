"""
dialogue/wordparts.py – Word parts and single symbols.

Three kinds of question:

  Symbols and letters   "what is @?", "what does % mean?", "what is the letter q?"
                        → the Unicode character name (unicodedata, the Unicode Character Database).

  Affixes               "what does the prefix un- mean?", "what does -ness mean?"
                        → a meaning from AFFIXES below (a curated table, with examples).

  Unknown words         "what does unvaluable mean?"
                        → split into a known root plus known affixes, using the lexicon
                          (the words Mira already knows). Only reported when the parts are known.

Public API:
    answer(text, lexicon) -> str | None
    decompose(word, lexicon) -> dict | None
    symbol_name(ch) -> str | None
"""

import re
import unicodedata

# Curated affix table. Meanings are standard English usage. Each entry: (meaning, examples).
PREFIXES = {
    "un": ("not, the reverse of", "unknown, unsafe"),
    "in": ("not", "invisible, incorrect"),
    "im": ("not", "impossible"),
    "non": ("not", "nonexistent"),
    "dis": ("not, apart, the reverse of", "disagree, dislike"),
    "mis": ("wrongly", "misread, mislead"),
    "re": ("again, back", "rewrite, return"),
    "pre": ("before", "preview, prehistoric"),
    "post": ("after", "postwar"),
    "over": ("too much, above", "overtired, overlook"),
    "under": ("too little, below", "underestimate"),
    "out": ("beyond, more than", "outrun"),
    "sub": ("under, below", "submarine"),
    "super": ("above, beyond", "superhuman"),
    "inter": ("between", "international"),
    "trans": ("across", "transport"),
    "anti": ("against", "antisocial"),
    "de": ("reverse, remove", "defrost"),
    "co": ("together, with", "coexist"),
    "ex": ("former, out of", "ex-wife, exit"),
    "bi": ("two", "bicycle"),
    "multi": ("many", "multicolored"),
    "semi": ("half", "semicircle"),
}

SUFFIXES = {
    "ness": ("the state or quality of being", "kindness, darkness"),
    "ity": ("the state or quality of being", "ability, curiosity"),
    "ion": ("the act or result of", "creation, action"),
    "tion": ("the act or result of", "creation, action"),
    "ment": ("the result or act of", "agreement, enjoyment"),
    "ist": ("a person who practises or follows", "botanist, archivist"),
    "ism": ("a belief or practice", "realism"),
    "er": ("a person or thing that does the action of the verb", "keeper, teacher"),
    "or": ("a person or thing that does the action of the verb", "governor, visitor"),
    "ful": ("full of, having", "hopeful, careful"),
    "less": ("without", "hopeless, careless"),
    "able": ("able to be, worth", "valuable, readable"),
    "ible": ("able to be", "visible"),
    "ous": ("full of, having the quality of", "famous, nervous"),
    "ive": ("tending to, having the quality of", "active, creative"),
    "al": ("relating to", "national, central"),
    "ic": ("relating to", "poetic, magic"),
    "ly": ("in the manner of", "quickly, softly"),
    "ize": ("to make or become", "modernize"),
    "ise": ("to make or become", "modernise"),
    "ish": ("somewhat, like", "reddish"),
    "ward": ("in the direction of", "backward, homeward"),
    "dom": ("the state or domain of", "kingdom, freedom"),
    "hood": ("the state or period of", "childhood"),
    "ship": ("the state or skill of", "friendship"),
    "ed": ("past tense or past participle", "guarded, stolen"),
    "ing": ("the continuing action of, or a noun from a verb", "guarding, keeping"),
    "s": ("plural, or third person singular", "veils, holds"),
    "es": ("plural, or third person singular", "glasses, guesses"),
}

_AFFIX_WORDS = {"prefix", "suffix"}
_SYMBOL_WORDS = {"letter", "symbol", "sign", "character", "digit", "number"}


def symbol_name(ch: str) -> str | None:
    """The Unicode name of a single character, in lower case, or None."""
    if len(ch) != 1:
        return None
    try:
        return unicodedata.name(ch).lower()
    except ValueError:
        return None


def _describe_symbol(ch: str) -> str | None:
    name = symbol_name(ch)
    if name is None:
        return None
    if ch.isalpha():
        kind = "letter"
        if ch.isupper():
            return f"'{ch}' is the capital {kind} {name.split()[-1].upper()}."
        return f"'{ch}' is the {kind} {ch.upper()}."
    return f"'{ch}' is called {name}."


def decompose(word: str, lexicon) -> dict | None:
    """Split an unknown word into a known root plus affixes.

    Returns {'prefix': 'un', 'root': 'valuable', 'suffix': None, 'parts': [...]} or None.
    Only reports a split when every part is known: the root in the lexicon, the affix in the table.
    """
    from .morph import analyze

    w = word.lower()
    if w in lexicon:
        return None
    for p in sorted(PREFIXES, key=len, reverse=True):
        if w.startswith(p) and len(w) > len(p) + 2:
            rest = w[len(p):]
            # Root may itself be a derived word ('unvaluable' → 'un' + 'valuable' → 'value'+'able').
            if rest in lexicon or analyze(rest, lexicon):
                return {"prefix": p, "root": rest, "suffix": None, "parts": [p, rest]}
            for s in sorted(SUFFIXES, key=len, reverse=True):
                if rest.endswith(s) and len(rest) > len(s) + 2:
                    root = rest[: -len(s)]
                    if root in lexicon:
                        return {"prefix": p, "root": root, "suffix": s, "parts": [p, root, s]}
    for s in sorted(SUFFIXES, key=len, reverse=True):
        if w.endswith(s) and len(w) > len(s) + 2:
            root = w[: -len(s)]
            if root in lexicon:
                return {"prefix": None, "root": root, "suffix": s, "parts": [root, s]}
            # 'kindness' → 'kind' + 'ness' via analysis of the root
            if analyze(root, lexicon):
                return {"prefix": None, "root": root, "suffix": s, "parts": [root, s]}
    return None


def _affix_answer(kind: str, a: str) -> str | None:
    table = PREFIXES if kind == "prefix" else SUFFIXES
    if a not in table:
        return None
    meaning, examples = table[a]
    if kind == "prefix":
        return f"The prefix '{a}-' means {meaning}, as in {examples}."
    return f"The suffix '-{a}' means {meaning}, as in {examples}."


def answer(text: str, lexicon) -> str | None:
    """Answer a question about a symbol, letter, affix, or the parts of an unknown word."""
    raw = text.strip()
    if not raw.endswith("?"):
        return None
    orig = raw[:-1].strip()          # keep case: 'Q' and 'q' are different letters
    q = orig.lower()

    # "what is the prefix un-" / "what does the suffix -ness mean" / "what is the letter Q"
    m = re.fullmatch(r"(?:what|which) (?:is|does|are) (?:the )?(prefix|suffix|letter|symbol|sign|character|digit|number)\s+(\S+?)(?:\s+(?:mean|means|stand for))?", orig, re.I)
    if m:
        kind, arg = m.group(1).lower(), m.group(2)
        if kind in _AFFIX_WORDS:
            a = arg.strip("-").lower()
            return _affix_answer(kind, a) or f"I do not know the {kind} '{arg}'."
        ch = arg.strip("'\"")
        return _describe_symbol(ch) or "I have no name for that symbol."

    # "what does un- mean?" / "what does -ness mean?" / "what does % mean?" / "what does unvaluable mean?"
    m = re.fullmatch(r"what (?:does|is) (\S+?)\s+(?:mean|stand for)", q)
    if m:
        arg = orig.split()[2] if len(orig.split()) >= 3 else m.group(1)
        if arg.endswith("-") and len(arg) > 1:
            return _affix_answer("prefix", arg[:-1].lower()) or f"I do not know the prefix '{arg}'."
        if arg.startswith("-") and len(arg) > 1:
            return _affix_answer("suffix", arg[1:].lower()) or f"I do not know the suffix '{arg}'."
        if len(arg) == 1:
            return _describe_symbol(arg) or "I have no name for that symbol."
        word = arg.lower()
        if word in lexicon:
            return None                    # a known word: the normal path answers it
        d = decompose(word, lexicon)
        if d:
            return _explain(d)
        suffix = next((s for s in sorted(SUFFIXES, key=len, reverse=True)
                       if word.endswith(s) and len(word) > len(s) + 2), None)
        if suffix:
            meaning = SUFFIXES[suffix][0]
            return (f"I do not know '{word}' as a whole, but it ends in '-{suffix}' ({meaning}). "
                    f"Tell me what its root means, and I will work it out.")
        return f"I do not know the word '{word}'. Tell me what it means, and I will remember it."

    # "what is @?" / "what is Q?"
    m = re.fullmatch(r"what (?:is|does) (\S)", orig, re.I)
    if m:
        return _describe_symbol(m.group(1))
    return None


def _explain(d: dict) -> str:
    bits = []
    if d.get("prefix"):
        meaning = PREFIXES[d["prefix"]][0]
        bits.append(f"'{d['prefix']}-' ({meaning})")
    bits.append(f"'{d['root']}'")
    if d.get("suffix"):
        meaning = SUFFIXES[d["suffix"]][0]
        bits.append(f"'-{d['suffix']}' ({meaning})")
    word = "".join(d["parts"])
    return (f"I do not know '{word}' as a whole, but it breaks into " + ", ".join(bits)
            + ". Put the parts together to get the meaning.")
