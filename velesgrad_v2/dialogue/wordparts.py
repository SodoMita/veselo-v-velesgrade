"""
dialogue/wordparts.py – Word parts and single symbols.

Three kinds of question:

  Symbols and letters   "what is @?", "what does % mean?", "what is the letter q?"
                        → the Unicode character name (unicodedata, the Unicode Character Database).

  Affixes               "what does the prefix un- mean?", "what does -ness mean?"
                        → the gloss from Wiktionary (via kaikki.org, CC BY-SA), and examples
                          taken from words Mira knows.

  Unknown words         "what does unvaluable mean?"
                        → split into a known root plus known affixes, using the lexicon
                          (the words Mira already knows). Only reported when the parts are known.

Public API:
    answer(text, lexicon) -> str | None
    decompose(word, lexicon) -> dict | None
    symbol_name(ch) -> str | None
    affix_table() -> dict  (prefixes and suffixes → {'gloss', 'kind'})
"""

import json
import os
import re
import unicodedata
from functools import lru_cache

AFFIX_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "raw_external",
                          "wiktionary_affixes", "affixes.jsonl")
MAX_GLOSS = 180
# Glosses for marginal senses are skipped in favour of the standard one.
_MARGINAL = re.compile(r"informal|jocular|nonce|slang|colloquial|diminutive|hypocoristic|alternative form|alternative spelling|stylistic|Junior|child", re.I)


@lru_cache(maxsize=1)
def affix_table() -> dict:
    """Affixes from Wiktionary: {'un': {'kind': 'prefix', 'gloss': '...'}, 'ness': {...}}.

    Source: kaikki.org English extraction of Wiktionary (CC BY-SA). For each affix, the first
    standard sense is used, skipping marginal senses (informal, slang, alternative forms).
    """
    table = {}
    if not os.path.exists(AFFIX_PATH):
        return table
    senses_by_key = {}
    with open(AFFIX_PATH, encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            if rec.get("lang_code") != "en" or rec.get("pos") not in ("prefix", "suffix"):
                continue
            word = rec.get("word", "")
            if rec["pos"] == "prefix" and word.endswith("-") and not word.startswith("-"):
                key, kind = word[:-1], "prefix"
            elif rec["pos"] == "suffix" and word.startswith("-") and not word.endswith("-"):
                key, kind = word[1:], "suffix"
            else:
                continue
            if not key or not re.fullmatch(r"[a-z]+", key):
                continue
            glosses = [g for sense in rec.get("senses", [])[:3]
                       for g in sense.get("glosses", [])[:1]]
            glosses = [g.strip() for g in glosses if g and len(g) <= MAX_GLOSS]
            glosses = [g for g in glosses if not _MARGINAL.search(g)] or glosses
            if not glosses:
                continue
            senses_by_key.setdefault((key, kind), []).extend(glosses)
    for (key, kind), glosses in senses_by_key.items():
        # Keep the first entry per key; prefer the prefix/suffix entry with most glosses.
        if key in table:
            continue
        gloss = glosses[0].rstrip(".")       # first standard sense, in source order
        table[key] = {"kind": kind, "gloss": gloss}
    return table


DEFN_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "raw_external",
                         "wiktionary_definitions", "definitions.tsv.gz")


@lru_cache(maxsize=1)
def definitions() -> dict:
    """word → (part of speech, first standard gloss), from Wiktionary (kaikki.org, CC BY-SA)."""
    import gzip
    table = {}
    if not os.path.exists(DEFN_PATH):
        return table
    with gzip.open(DEFN_PATH, "rt", encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) == 3 and parts[0] not in table:
                table[parts[0]] = (parts[1], parts[2])
    return table


def definition(word: str) -> str | None:
    """A dictionary sentence for a word: "'kindness' means the quality of being kind."."""
    hit = definitions().get(word.lower())
    if not hit:
        return None
    gloss = hit[1][:1].lower() + hit[1][1:]
    return f"According to Wiktionary, '{word.lower()}' means {gloss}."


def _affix(kind: str, key: str):
    entry = affix_table().get(key)
    return entry if entry and entry["kind"] == kind else None


def _prefixes():
    return [k for k, v in affix_table().items() if v["kind"] == "prefix" and len(k) >= 2]


def _suffixes():
    return [k for k, v in affix_table().items() if v["kind"] == "suffix" and len(k) >= 2]


def _examples(kind: str, key: str, lexicon, n: int = 2) -> list[str]:
    """Words Mira knows that use this affix (only where the root is also known)."""
    out = []
    for w in sorted(lexicon, key=len):
        if kind == "prefix" and w.startswith(key) and len(w) > len(key) + 2 and w[len(key):] in lexicon:
            out.append(w)
        elif kind == "suffix" and w.endswith(key) and len(w) > len(key) + 2 and w[:-len(key)] in lexicon:
            out.append(w)
        if len(out) >= n:
            break
    return out


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
            return f"According to the Unicode database, '{ch}' is the capital {kind} {name.split()[-1].upper()}."
        return f"According to the Unicode database, '{ch}' is the {kind} {ch.upper()}."
    return f"According to the Unicode database, '{ch}' is called {name}."


class _Known:
    """Words Mira knows: her lexicon, or any word in the Wiktionary definitions."""

    def __init__(self, lexicon):
        self.lexicon = lexicon

    def __contains__(self, w):
        return w in self.lexicon or w in definitions()


def decompose(word: str, lexicon) -> dict | None:
    """Split an unknown word into a known root plus affixes.

    Returns {'prefix': 'un', 'root': 'valuable', 'suffix': None, 'parts': [...]} or None.
    Only reports a split when every part is known: the root in the lexicon, the affix in the table.
    """
    from .morph import analyze

    w = word.lower()
    # Only Mira's own words count as known here; a Wiktionary headword is still worth splitting.
    if w in lexicon:
        return None
    known = _Known(lexicon)
    # Suffix first: 'relicness' is 'relic' + '-ness', not 're-' + 'licness'.
    for s_ in sorted(_suffixes(), key=len, reverse=True):
        if w.endswith(s_) and len(w) > len(s_) + 2:
            root = w[: -len(s_)]
            if root in lexicon or analyze(root, known):
                return {"prefix": None, "root": root, "suffix": s_, "parts": [root, s_]}
    for p in sorted(_prefixes(), key=len, reverse=True):
        if w.startswith(p) and len(w) > len(p) + 2:
            rest = w[len(p):]
            # Root may itself be derived ('unvaluable' → 'un' + 'valuable').
            if rest in lexicon or analyze(rest, known):
                return {"prefix": p, "root": rest, "suffix": None, "parts": [p, rest]}
            for s_ in sorted(_suffixes(), key=len, reverse=True):      # 'unrelicable' → un + relic + able
                if rest.endswith(s_) and len(rest) > len(s_) + 2:
                    root = rest[: -len(s_)]
                    if root in lexicon:
                        return {"prefix": p, "root": root, "suffix": s_, "parts": [p, root, s_]}
    return None


def _affix_answer(kind: str, a: str, lexicon=frozenset()) -> str | None:
    entry = _affix(kind, a)
    if entry is None:
        return None
    gloss = entry["gloss"][:1].lower() + entry["gloss"][1:]
    entry = {**entry, "gloss": gloss}
    ex = _examples(kind, a, lexicon)
    tail = f", as in {', '.join(ex)}" if ex else ""
    if kind == "prefix":
        return f"According to Wiktionary, the prefix '{a}-' means {entry['gloss']}{tail}."
    return f"According to Wiktionary, the suffix '-{a}' means {entry['gloss']}{tail}."


def answer(text: str, lexicon) -> str | None:
    """Answer a question about a symbol, letter, affix, or the parts of an unknown word."""
    raw = text.strip()
    d = re.fullmatch(r"(?:define|what is the meaning of)\s+(\S+?)[?.!]?", raw, re.I)
    if d and d.group(1).lower() not in _AFFIX_WORDS and len(d.group(1)) > 1:
        dfn = definition(d.group(1))
        if dfn:
            return dfn
    if not raw.endswith("?"):
        return None
    orig = raw[:-1].strip()          # keep case: 'Q' and 'q' are different letters
    # "what is a fragilely?" about a word Mira does not know is a word-meaning question.
    na = re.fullmatch(r"what is (?:a|an) (\w+)", orig, re.I)
    if na and na.group(1).lower() not in lexicon:
        orig = f"what does {na.group(1)} mean"
    q = orig.lower()

    # "what is the prefix un-" / "what does the suffix -ness mean" / "what is the letter Q"
    m = re.fullmatch(r"(?:what|which) (?:is|does|are) (?:the )?(prefix|suffix|letter|symbol|sign|character|digit|number)\s+(\S+?)(?:\s+(?:mean|means|stand for))?", orig, re.I)
    if m:
        kind, arg = m.group(1).lower(), m.group(2)
        if kind in _AFFIX_WORDS:
            a = arg.strip("-").lower()
            return _affix_answer(kind, a, lexicon) or f"I do not know the {kind} '{arg}'."
        ch = arg.strip("'\"")
        return _describe_symbol(ch) or "I have no name for that symbol."

    # "what does un- mean?" / "what does -ness mean?" / "what does % mean?" / "what does unvaluable mean?"
    m = re.fullmatch(r"what (?:does|is) (\S+?)\s+(?:mean|stand for)", q)
    if m:
        arg = orig.split()[2] if len(orig.split()) >= 3 else m.group(1)
        if arg.endswith("-") and len(arg) > 1:
            return _affix_answer("prefix", arg[:-1].lower(), lexicon) or f"I do not know the prefix '{arg}'."
        if arg.startswith("-") and len(arg) > 1:
            return _affix_answer("suffix", arg[1:].lower(), lexicon) or f"I do not know the suffix '{arg}'."
        if len(arg) == 1:
            return _describe_symbol(arg) or "I have no name for that symbol."
        word = arg.lower()
        dfn = definition(word)
        if dfn:
            return dfn                     # a dictionary word: its real definition
        if word in lexicon:
            return None                    # a known word with no definition: the normal path answers it
        d = decompose(word, lexicon)
        if d:
            return _explain(d)
        return f"I do not know the word '{word}'. Tell me what it means, and I will remember it."

    m = re.fullmatch(r"(?:define|what is the meaning of|what does) (\S+?)(?: mean)?", q)
    if m and m.group(1) not in _AFFIX_WORDS and len(m.group(1)) > 1:
        dfn = definition(m.group(1))
        if dfn:
            return dfn

    # "what is @?" / "what is Q?"
    m = re.fullmatch(r"what (?:is|does) (\S)", orig, re.I)
    if m:
        return _describe_symbol(m.group(1))
    return None


def _explain(d: dict) -> str:
    bits = []
    if d.get("prefix"):
        meaning = affix_table()[d["prefix"]]["gloss"]
        bits.append(f"'{d['prefix']}-' ({meaning})")
    bits.append(f"'{d['root']}'")
    if d.get("suffix"):
        meaning = affix_table()[d["suffix"]]["gloss"]
        bits.append(f"'-{d['suffix']}' ({meaning})")
    word = "".join(d["parts"])
    text = (f"I do not know '{word}' as a whole. According to Wiktionary, it breaks into "
            + ", ".join(bits) + ".")
    root_def = definition(d["root"])
    if root_def:
        text += " " + root_def.replace("According to Wiktionary, ", "", 1)[0].upper() \
            + root_def.replace("According to Wiktionary, ", "", 1)[1:]
    return text


_POS = None


def _pos_table() -> dict:
    """word -> set of Wiktionary parts of speech (first column of definitions.tsv.gz is the word)."""
    global _POS
    if _POS is None:
        import gzip
        _POS = {}
        try:
            with gzip.open(DEFN_PATH, "rt", encoding="utf-8") as f:
                for line in f:
                    parts = line.rstrip("\n").split("\t")
                    if len(parts) >= 2:
                        _POS.setdefault(parts[0].lower(), set()).add(parts[1])
        except OSError:
            pass
    return _POS


# Colour and material words are used as adjectives ("a brown dog"); the POS file often lists only the noun.
_COLOR_ADJ = {"red", "green", "blue", "brown", "black", "white", "yellow", "grey", "gray", "pink",
              "purple", "orange", "golden", "silver", "bronze", "dark", "bright", "pale"}


def is_adjective_word(phrase: str) -> bool:
    """True if the phrase's head word (its last word) is an adjective: Wiktionary POS, or a colour."""
    head = phrase.replace("_", " ").strip().split(" ")[-1].lower() if phrase.strip() else ""
    if not head:
        return False
    return head in _COLOR_ADJ or "adj" in _pos_table().get(head, set())
