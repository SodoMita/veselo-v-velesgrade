"""
dialogue/ingest.py – Natural-language ingestion: English text → AtomSpace.

A rule-based *subset* of OpenCog's RelEx2Logic pipeline, operating on the
real Link Grammar parse (ctypes; same dictionary the realizer validates
against). Upstream lg-atomese requires an AtomSpaceStorage build we don't
have; this extractor covers the shapes below and documents the rest as
out of scope (see BOUNDARIES).

Supported sentence shapes (labels observed from LG 5.13 parses):

  "The relic is valuable."            Ss* + is + Paf(adjective)
      → InheritanceLink(relic, valuable)
  "The relic is a stolen artifact."   Ss* + is + Os(noun)
      → InheritanceLink(relic, stolen_artifact)
  "The relic is in the archive."      Ss* + is + Pp/Js prepositional
      → EvaluationLink(in, List(relic, archive))
  "Mira guards the archive."          Ss* + Os
      → EvaluationLink(guard, List(mira, archive))
  "The hounds patrol the streets."    Sp + Op (plural agreement)
      → EvaluationLink(patrol, List(hounds, streets))
  "The relic lies in the tunnel."     Ss* + MVp→Js prepositional
      → EvaluationLink(lie, List(relic, tunnel))

BOUNDARIES (measured, not guessed):
  - No nested clauses, no relative clauses in input, no passive→active
    conversion, no quantifiers, no tense logic (verb lemma is surface form
    minus LG suffix tags).
  - Pronouns: first person → "player" (the speaker), second person →
    the listener's name when provided; otherwise dropped.
  - Factual TV for told facts: strength 0.6, confidence 0.3 — the system
    marks them "heard, unverified"; they are NOT equal in status to the
    seeded archive knowledge (0.85–0.95).
"""

import re

from .lg_ctypes import is_available, get_dictionary, parse_sentence

_POS_SUFFIX = re.compile(r"\.(n|v|a|r|f|d|p|s|c|i|x)(-[a-z]+)?$")
_SKIP_WORDS = {"left-wall", "right-wall", ".", ",", "and", "or", "but",
               "the", "a", "an", "some", "this", "that", "these", "those"}

_SUBJ_LABELS = {"Ss", "Ss*s", "Sp", "SI", "SX", "SX*s", "SIs", "SIp"}
_OBJ_LABELS = {"Os", "Op", "O2", "Od", "OI", "OF"}
_COPULAS = {"is", "are", "was", "were", "be", "been", "am"}

_IRREGULAR = {"lies": "lie", "runs": "run", "keeps": "keep", "holds": "hold",
              "guards": "guard", "patrols": "patrol", "signals": "signal",
              "separates": "separate", "suspects": "suspect"}


def _bare(word: str) -> str:
    """Strip LG tags: POS suffix and bracketed markers.
    'relic.n' → 'relic'; 'Veil[!<CAPITALIZED-WORDS>]' → 'veil'.
    """
    w = re.sub(r"\[.*$", "", word)
    w = _POS_SUFFIX.sub("", w)
    return w.strip().lower()


def _is_verb_word(w: str) -> bool:
    """True for LG verb tokens incl. tenses: 'lies.v', 'saw.v-d'."""
    return bool(re.search(r"\.v(-[a-z]+)?$", w))


def _lemma(verb: str) -> str:
    v = _bare(verb)
    if v in _IRREGULAR:
        return _IRREGULAR[v]
    # Strip 3sg "s" only when it is safe: not a copula/auxiliary and not
    # a word that merely ends in s/is/us/as.
    if v in _COPULAS or v in ("has", "does", "us", "his", "hers", "always"):
        return v
    if v.endswith("s") and not v.endswith(("ss", "is", "us", "as")):
        return v[:-1]
    return v


def _content(w: str) -> bool:
    return bool(w) and w not in _SKIP_WORDS


def _map_pronoun(w: str, speaker: str, listener: str) -> str | None:
    if w in ("i", "me", "my", "myself"):
        return speaker.lower() if speaker else None
    if w in ("you", "your", "yourself"):
        return listener.lower() if listener else None
    if w in ("he", "she", "it", "they", "him", "her", "them"):
        return None  # unresolved reference — out of scope
    return w


def extract_triples(sentence: str, speaker: str = "player",
                    listener: str = "", dictionary=None) -> list[dict]:
    """Parse one sentence; return knowledge triples.

    Each triple: {"kind": "inh"|"eval", "a": subj, "b": obj/pred, "rel": verb/prep}
    """
    if not is_available():
        return []
    d = dictionary or get_dictionary()
    parsed = parse_sentence(sentence, d)
    if not parsed:
        return []

    words = parsed.words
    # Normalize per-word: raw surface, bare lemma-ish form
    bare = [_bare(w) for w in words]
    raw = [w for w in words]

    # Collect labelled edges into structure, using label CLASSES observed
    # from real LG 5.13 parses:
    #   subjects:  Ss*s, Sp, Sp*i, SI*...  (label starts with "S")
    #   objects:   Os, Osm, Op, O2, Od     (starts with "O", left is verb)
    #   adj comp:  Paf                     (copula → adjective)
    #   verb→prep: MVp, Pp, OFj            (copula/prep-object phrasals)
    #   prep→obj:  Js, Ju, Jp              (starts with "J")
    subj = {}          # verb_index -> subject word
    obj = {}           # verb_index -> object word
    adj = {}           # verb_index -> adjective
    prep_of_verb = {}  # verb_index -> prep index
    prep_obj = {}      # prep_index -> object word

    def _idx(word_str, start=0):
        """Index of a word string, preferring occurrences at/after start."""
        try:
            return raw.index(word_str, start)
        except ValueError:
            try:
                return raw.index(word_str)
            except ValueError:
                return None

    for left, label, right in parsed.links:
        li = _idx(left)
        ri = _idx(right)
        if li is None or ri is None:
            continue
        if label.startswith("S") and not _is_verb_word(left):
            subj[ri] = bare[li]
        elif (label.startswith("MV") or label in ("Pp",) or label.startswith("OF")) \
                and _is_verb_word(left):
            prep_of_verb[li] = ri          # verb → preposition
        elif label.startswith("O") and not label.startswith("OF") \
                and _is_verb_word(left):
            obj[li] = bare[ri]             # verb → object
        elif label == "Paf" and _is_verb_word(left):
            adj[li] = bare[ri]             # copula → adjective
        elif label.startswith("J"):
            prep_obj[li] = bare[ri]        # preposition → object

    triples = []
    # Find finite verbs, including tense-tagged ones ('saw.v-d')
    for vi, w in enumerate(words):
        if not _is_verb_word(w):
            continue
        v = _lemma(w)
        s_raw = subj.get(vi)
        s = _map_pronoun(s_raw, speaker, listener) if s_raw else None

        # copula + adjective:  X is <adj>
        if v in _COPULAS and vi in adj and s:
            a = _map_pronoun(adj[vi], speaker, listener)
            if a:
                triples.append({"kind": "inh", "a": s, "b": a, "rel": "is"})
                continue
        # copula + noun object:  X is a <noun>
        if v in _COPULAS and vi in obj and s:
            o = _map_pronoun(obj[vi], speaker, listener)
            if o:
                triples.append({"kind": "inh", "a": s, "b": o, "rel": "is"})
                continue
        # copula + prepositional:  X is in <place>
        if v in _COPULAS and vi in prep_of_verb and s:
            pi = prep_of_verb[vi]
            o = prep_obj.get(pi)
            o = _map_pronoun(o, speaker, listener) if o else None
            if o:
                triples.append({"kind": "eval", "a": s, "b": o,
                                "rel": _bare(words[pi])})
                continue
        # transitive:  X verbs <obj>
        if vi in obj and s:
            o = _map_pronoun(obj[vi], speaker, listener)
            if o:
                triples.append({"kind": "eval", "a": s, "b": o, "rel": v})
                continue
        # intransitive + preposition:  X verbs in <place>
        if vi in prep_of_verb and s:
            pi = prep_of_verb[vi]
            o = prep_obj.get(pi)
            o = _map_pronoun(o, speaker, listener) if o else None
            if o:
                prep = _bare(words[pi])
                triples.append({"kind": "eval", "a": s, "b": o,
                                "rel": f"{v}_{prep}"})

    # Cleanup: drop junk (short tokens, pure numbers, stopwords)
    cleaned = []
    for t in triples:
        if not (_content(t["a"]) and _content(t["b"]) and _content(t["rel"])):
            continue
        if len(t["a"]) < 2 or len(t["b"]) < 2:
            continue
        cleaned.append(t)
    return cleaned


def ingest_text(aspace, sentence: str, speaker: str = "player",
                listener: str = "", sti_boost: float = 14.0) -> list[str]:
    """Extract triples from a sentence and write them into the AtomSpace.

    Returns a list of (description, atom) pairs for acknowledgment text.
    Truth values: strength 0.6 / confidence 0.3 — "heard, unverified" —
    deliberately weaker than archive knowledge.
    """
    from ..cog.atomspace import (
        ConceptNode, PredicateNode, InheritanceLink, EvaluationLink,
        ListLink, TruthValue, set_tv, set_sti, get_sti,
    )

    triples = extract_triples(sentence, speaker=speaker, listener=listener)
    learned = []
    for t in triples:
        if t["kind"] == "inh":
            link = InheritanceLink(ConceptNode(t["a"]), ConceptNode(t["b"]))
        else:
            link = EvaluationLink(
                PredicateNode(t["rel"]),
                ListLink(ConceptNode(t["a"]), ConceptNode(t["b"])),
            )
        set_tv(link, TruthValue(0.6, 0.3))
        # Make newly-heard facts salient so they surface in dialogue
        set_sti(link, max(get_sti(link), sti_boost))
        learned.append((f"{t['a']} {t['rel']} {t['b']}", link))
    return learned
