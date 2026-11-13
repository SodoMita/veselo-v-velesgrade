"""
dialogue/morph.py – English word morphology for Mira.

Three jobs:

  inflect(word, form)       correct forms of a known word
                            ("guard" → "guards", "guarded", "guarding", "guardian")
  analyze(word, lexicon)    recover a known root from an inflected word, checked against
                            the lexicon so that "veil" is never cut down to "vei"
  derive(root, kind)        propose a NEW word from a known root ("archive" → "archivist",
                            "relic" → "relic-keeper"). Derived words are marked coined so
                            Mira can say she is coining them.

Forms for inflect(): "s", "past", "pp", "ing", "agent", "state", "ly", "un".
"""

import re

IRREG = {
    # verb: (past, past participle)
    "be": ("was", "been"), "have": ("had", "had"), "do": ("did", "done"), "go": ("went", "gone"),
    "see": ("saw", "seen"), "take": ("took", "taken"), "give": ("gave", "given"),
    "make": ("made", "made"), "say": ("said", "said"), "tell": ("told", "told"),
    "find": ("found", "found"), "know": ("knew", "known"), "think": ("thought", "thought"),
    "keep": ("kept", "kept"), "leave": ("left", "left"), "lose": ("lost", "lost"),
    "hold": ("held", "held"), "steal": ("stole", "stolen"), "write": ("wrote", "written"),
    "speak": ("spoke", "spoken"), "break": ("broke", "broken"), "choose": ("chose", "chosen"),
    "come": ("came", "come"), "run": ("ran", "run"), "begin": ("began", "begun"),
    "build": ("built", "built"), "send": ("sent", "sent"), "spend": ("spent", "spent"),
    "sell": ("sold", "sold"), "teach": ("taught", "taught"), "catch": ("caught", "caught"),
    "fight": ("fought", "fought"), "lead": ("led", "led"), "read": ("read", "read"),
    "lie": ("lay", "lain"), "rise": ("rose", "risen"), "sing": ("sang", "sung"),
    "draw": ("drew", "drawn"), "throw": ("threw", "thrown"), "fly": ("flew", "flown"),
    "grow": ("grew", "grown"), "bring": ("brought", "brought"), "buy": ("bought", "bought"),
    "fall": ("fell", "fallen"), "feel": ("felt", "felt"), "meet": ("met", "met"),
    "pay": ("paid", "paid"), "sleep": ("slept", "slept"), "understand": ("understood", "understood"),
}
IRREG_PAST = {p: v for v, (p, _) in IRREG.items()}
IRREG_PP = {pp: v for v, (_, pp) in IRREG.items()}
IRREG_ALL = {**{p: v for v, (p, _) in IRREG.items()},
             **{pp: v for v, (_, pp) in IRREG.items()}}

_VOWELS = "aeiou"
_NOUN_IRREG = {"man": "men", "woman": "women", "child": "children", "person": "people",
               "foot": "feet", "tooth": "teeth", "mouse": "mice", "ox": "oxen"}


def _double_final(w: str) -> bool:
    """CVC ending that doubles before -ed/-ing (stop → stopped, but visit → visited)."""
    return (len(w) >= 3 and w[-1] not in _VOWELS + "wxy" and w[-2] in _VOWELS
            and w[-3] not in _VOWELS and len(w) <= 4)


def _drop_e(w: str) -> str:
    return w[:-1] if w.endswith("e") and not w.endswith(("ee", "ye", "oe")) else w


def plural(noun: str) -> str:
    if noun in _NOUN_IRREG:
        return _NOUN_IRREG[noun]
    if noun.endswith(("s", "x", "z", "ch", "sh")):
        return noun + "es"
    if noun.endswith("y") and len(noun) > 1 and noun[-2] not in _VOWELS:
        return noun[:-1] + "ies"
    if noun.endswith("f") and len(noun) > 2 and noun[-2] not in _VOWELS:
        return noun[:-1] + "ves"
    return noun + "s"


def third_person(verb: str) -> str:
    return plural(verb)  # same spelling rules


def past(verb: str) -> str:
    if verb in IRREG:
        return IRREG[verb][0]
    if verb.endswith("e"):
        return verb + "d"
    if verb.endswith("y") and len(verb) > 1 and verb[-2] not in _VOWELS:
        return verb[:-1] + "ied"
    if _double_final(verb):
        return verb + verb[-1] + "ed"
    return verb + "ed"


def past_participle(verb: str) -> str:
    if verb in IRREG:
        return IRREG[verb][1]
    return past(verb)


def ing(verb: str) -> str:
    if verb.endswith("ie"):
        return verb[:-2] + "ying"
    if verb.endswith("ee"):
        return verb + "ing"
    if _double_final(verb):
        return verb + verb[-1] + "ing"
    return _drop_e(verb) + "ing"


def agent(verb: str) -> str:
    """Agent noun by the simplest rule: keep → keeper, archive → archiver.
    Coinages, not dictionary words. Irregular agents (archivist) need a lexicon entry."""
    if verb.endswith("e"):
        return verb + "r"
    if verb.endswith("y") and len(verb) > 1 and verb[-2] not in _VOWELS:
        return verb[:-1] + "ier"
    return verb + "er"


def state(adj_or_noun: str) -> str:
    """'calm' → 'calmness'; 'curious' → 'curiousness' (acceptable coinage)."""
    if adj_or_noun.endswith("y") and len(adj_or_noun) > 1 and adj_or_noun[-2] not in _VOWELS:
        return adj_or_noun[:-1] + "iness"
    return adj_or_noun + "ness"


def adverb(adj: str) -> str:
    if adj.endswith("y") and len(adj) > 1 and adj[-2] not in _VOWELS:
        return adj[:-1] + "ily"
    if adj.endswith("le"):
        return adj[:-1] + "y"
    if adj.endswith("ic"):
        return adj + "ally"
    return adj + "ly"


def _negate(word: str) -> str:
    return "un" + word


FORMS = {
    "s": plural, "3sg": third_person, "past": past, "pp": past_participle,
    "ing": ing, "agent": agent, "state": state, "ly": adverb, "un": _negate,
}


def inflect(word: str, form: str) -> str:
    """Return the form of a known word, e.g. inflect('guard', 'past') → 'guarded'."""
    if form not in FORMS:
        raise ValueError(f"unknown form {form!r}")
    return FORMS[form](word.lower())


# ── Analysis: recover a known root ──────────────────────────────────────

_SUFFIX_RULES = [
    # (suffix, replacement, kind) – tried longest first
    ("iers", "y", "agent"), ("ies", "y", "s"), ("ied", "y", "past"),
    ("ying", "ie", "ing"), ("ing", "", "ing"), ("ing", "e", "ing"), ("ings", "", "ing"),
    ("ness", "", "state"), ("iness", "y", "state"),
    ("ally", "ic", "ly"), ("ily", "y", "ly"), ("ly", "", "ly"),
    ("ed", "", "past"), ("ed", "e", "past"), ("d", "", "past"),
    ("ers", "", "agent"), ("er", "", "agent"), ("er", "e", "agent"),
    ("es", "", "s"), ("es", "e", "s"), ("s", "", "s"),
    ("ful", "", "adj"), ("less", "", "adj"),
]


def analyze(word: str, lexicon) -> list[tuple[str, str]]:
    """Return candidate (root, form) pairs for an inflected word. Only roots found in `lexicon`
    (a set of lower-case words) count, so this never invents a root.

    'guarded' → [('guard', 'past')]; 'veil' → []; 'holds' → [('hold', 's')].
    """
    w = word.lower()
    out = []
    if w in lexicon:
        return [(w, "base")]
    if w in IRREG_ALL and IRREG_ALL[w] in lexicon:
        out.append((IRREG_ALL[w], "irregular"))
    for suf, rep, kind in _SUFFIX_RULES:
        if w.endswith(suf) and len(w) - len(suf) >= 1:  # the lexicon check guards the root
            root = w[: -len(suf)] + rep
            if root in lexicon and (root, kind) not in out:
                out.append((root, kind))
            # doubled consonant: stopped → stop, planned → plan
            if rep == "" and len(root) >= 3 and root[-1] == root[-2] and root[:-1] in lexicon:
                out.append((root[:-1], kind))
    return out


# ── Derivation: propose new words ──────────────────────────────────────

_DERIVED_KINDS = {"agent", "state", "ly", "un", "ing", "s", "3sg", "past", "pp"}


def derive(root: str, kind: str, lexicon=frozenset()) -> dict:
    """Propose a new word from a known root. Returns {'word', 'kind', 'coined': True}.

    The word is checked against `lexicon`: if it already exists, it is not new and the
    result says so. Nothing is produced for kinds that do not fit the root.
    """
    if kind not in FORMS:
        raise ValueError(f"unknown derivation {kind!r}")
    word = FORMS[kind](root.lower())
    return {"word": word, "kind": kind, "coined": True,
            "exists": word in lexicon}


def coin_compound(head: str, modifier: str) -> dict:
    """A compound such as 'relic keeper'. Two known words joined with a hyphen."""
    return {"word": f"{modifier.lower()}-{head.lower()}", "kind": "compound", "coined": True,
            "exists": False}
