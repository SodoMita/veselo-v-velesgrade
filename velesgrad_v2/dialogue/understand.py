"""
dialogue/understand.py – Understand a question from its Link Grammar structure.

Keyword matching asks "which of my atoms share a word with this?". That answers
"the veil" when asked about the veil and misses "who guards the city". This module
reads the sentence's grammatical links and works out what is being asked:

  "who guards the city?"       subject = WH, verb = guard, object = city
                               → facts  guard(?, city)            → "Mira guards the ..."
  "what does the archive hold?" subject = archive, verb = hold, object = WH
                               → facts  hold(archive, ?)          → "The archive holds ..."
  "what is the veil?"          subject = veil, copula, WH complement
                               → facts  veil(?)                   → "The veil is a magical boundary."
  "where was the relic kept?"  subject = relic, locative WH
                               → facts  locative(relic, ?)        → "The relic was located in the archive."
  "is the relic valuable?"     yes/no: subject = relic, complement = valuable
                               → fact   inh(relic, valuable)?     → "Yes. The relic is valuable."

Each answer is an existing AtomSpace fact, realized into a sentence by the same
realizer that the rest of the chat uses. Nothing is invented: if no matching fact
exists the function returns None (for yes/no: "I have no record of that").

Names are compared through a light stemmer, so "holds", "hold" and "held" match, and
"stolen artifacts" matches "stolen_artifact". Predicates and nouns use the same rule.

Public API:
    understand(aspace, text) -> Answer | None
"""

import re
from dataclasses import dataclass

from .lg_ctypes import parse_sentence, get_dictionary, is_available
from .ingest import _bare, _is_verb_word, _lemma
from .morph import analyze

COPULAS = {"is", "are", "was", "were", "be", "am"}
AUX = {"do", "does", "did"}
WH_BASE = {"what": "what", "who": "who", "whom": "who", "whose": "who",
           "which": "what", "where": "where", "when": "when", "why": "why", "how": "how"}
LOCATIVE_PREDS = ("in", "at", "on", "locat", "reside", "lie", "kept", "stay", "within",
                  "inside", "under", "dwell", "live", "hold")

_IRREG = {"stole": "steal", "stolen": "steal", "held": "hold", "holds": "hold",
          "led": "lead", "left": "leave", "kept": "keep", "had": "have", "has": "have",
          "found": "find", "made": "make", "went": "go", "gave": "give", "took": "take",
          "taken": "take", "wrote": "write", "written": "write", "saw": "see", "seen": "see",
          "knew": "know", "known": "know", "told": "tell", "said": "say", "was": "be",
          "were": "be", "is": "be", "are": "be", "lay": "lie", "lies": "lie", "lain": "lie"}


def stem(word: str, lexicon=None) -> str:
    """Root of a word. With a lexicon, use morph.analyze (only roots that exist count);
    without one, keep the word as it is."""
    w = word.lower().replace("_", " ").strip()
    if lexicon is not None:
        found = analyze(w, lexicon)
        if found:
            return found[0][0]
    return _IRREG.get(w, w)


def canon(name: str, lexicon=None) -> str:
    return " ".join(stem(w, lexicon) for w in name.replace("_", " ").split() if w)


@dataclass
class Frame:
    kind: str                 # "wh" or "yn"
    wh: str | None            # "what" | "who" | "where" | ...
    wh_slot: str | None       # "subject" | "object" | "complement"
    verb: str | None          # main verb lemma (content verb), if any
    copula: bool
    subject: str | None       # concept name, underscore-joined
    obj: str | None           # object or complement noun
    adj: str | None           # predicate adjective


@dataclass
class Answer:
    text: str
    atom: object
    frame: Frame


# ── Frame from the parse ────────────────────────────────────────────────

def _wh_of(bare_word: str) -> str | None:
    if bare_word in WH_BASE:
        return WH_BASE[bare_word]
    if bare_word.endswith("ever") and bare_word[:-4] in WH_BASE:
        return WH_BASE[bare_word[:-4]]
    return None


def build_frame(text: str, dictionary=None, lexicon=None) -> Frame | None:
    d = dictionary or get_dictionary()
    parsed = parse_sentence(text, d)
    if not parsed:
        return None
    words = list(parsed.words)
    bare = [_bare(w) for w in words]
    links = []
    for left, label, right in parsed.links:
        if left in words and right in words:
            links.append((words.index(left), label, words.index(right)))

    def out_of(i):   # (label, target) for links leaving word i
        return [(lab, r) for (l, lab, r) in links if l == i]

    def into(i):     # (label, source) for links arriving at word i
        return [(lab, l) for (l, lab, r) in links if r == i]

    def noun_phrase(i):
        mods = [bare[j] for (lab, j) in into(i)
                if lab.startswith(("A", "AN")) and bare[j] not in ("the", "a", "an", "some", "")]
        return "_".join(mods + [bare[i]]) if bare[i] else None

    wh_idx = next((i for i, b in enumerate(bare) if _wh_of(b)), None)
    wh = _wh_of(bare[wh_idx]) if wh_idx is not None else None

    content = [i for i, w in enumerate(words)
               if _is_verb_word(w) and bare[i] not in COPULAS and bare[i] not in AUX]
    copula_idx = next((i for i, b in enumerate(bare) if b in COPULAS), None)
    aux_idx = next((i for i, b in enumerate(bare) if b in AUX), None)

    # 1. Main verb. "does X hold": the verb hangs off the auxiliary. The parser
    #    may tag it as a noun ("hold.s"), so accept any word the aux governs.
    main, copula = None, False
    if aux_idx is not None:
        for lab, c in out_of(aux_idx):
            if lab[:1] in ("I", "O") and c != wh_idx and c not in (aux_idx, copula_idx):
                main = c
                break
    if main is None and content:
        main = content[0]
    if main is None and copula_idx is not None:
        main, copula = copula_idx, True
    if main is None:
        return None

    # 2. Subject. Normal order: S-link into the verb. Inverted questions put it
    #    after the verb, or after the auxiliary/copula ("does mira reside",
    #    "was the relic kept"). The wh-word is never the subject here.
    def not_wh(i):
        return i is not None and i != wh_idx and not _is_verb_word(words[i])

    subject = next((s_ for lab, s_ in into(main) if lab.startswith("S") and not_wh(s_)), None)
    if subject is None:
        for head in (main, aux_idx, copula_idx):
            if head is None:
                continue
            subject = next((r for lab, r in out_of(head) if lab.startswith("S") and not_wh(r)), None)
            if subject is not None:
                break
    if subject is None and aux_idx is not None:
        subject = next((s_ for lab, s_ in into(aux_idx) if lab.startswith("S") and not_wh(s_)), None)
    if subject is None and aux_idx is not None:
        # "what does the archive hold": the parser attaches the subject to the verb as a modifier
        subject = next((s_ for lab, s_ in into(main) if lab.startswith("A") and not_wh(s_)), None)

    # 3. Object, complement, predicate adjective.
    obj = next((o for lab, o in out_of(main)
                if lab[:1] == "O" and not _is_verb_word(words[o]) and o != wh_idx), None)
    adj = next((a for lab, a in out_of(main)
                if lab.startswith("Pa") and not _is_verb_word(words[a])), None)

    # 4. Which slot does the wh-word fill?
    wh_slot = None
    if wh_idx is not None:
        if copula and any(lab.startswith("S") and t == main for lab, t in out_of(wh_idx)):
            wh_slot = "complement"                  # "what is the veil": the noun is what we ask about
        elif any(lab.startswith("S") and t == main for lab, t in out_of(wh_idx)) and not aux_idx:
            wh_slot = "subject"                     # "who guards the city"
        elif aux_idx is not None and any(lab.startswith("S") and t == aux_idx
                                         for lab, t in out_of(wh_idx)):
            wh_slot = "object"                      # "what does the archive hold"
        elif copula:
            wh_slot = "complement"                  # "who is mira"
        elif wh == "where":
            wh_slot = "place"                       # "where was the relic kept"
        else:
            wh_slot = "object"
    if wh_slot == "complement" and copula and subject is None and obj is not None:
        subject, obj = obj, None                    # the copula's object is the topic

    return Frame(kind="wh" if wh else "yn", wh=wh, wh_slot=wh_slot,
                 verb=None if copula else canon(bare[main], lexicon),
                 copula=copula,
                 subject=noun_phrase(subject) if subject is not None else None,
                 obj=noun_phrase(obj) if obj is not None else None,
                 adj=bare[adj] if adj is not None else None)


# ── Querying the AtomSpace ──────────────────────────────────────────────

def _triples(aspace):
    """Yield (link, kind, a, pred, b) for every Inheritance and Evaluation link."""
    from ..cog.atomspace import types as _t
    for link in aspace.get_atoms_by_type(_t.InheritanceLink):
        out = list(getattr(link, "out", []))
        if len(out) == 2:
            yield link, "inh", out[0].name, None, out[1].name
    for link in aspace.get_atoms_by_type(_t.EvaluationLink):
        out = list(getattr(link, "out", []))
        if len(out) == 2:
            args = list(getattr(out[1], "out", []) or [])
            if len(args) == 2:
                yield link, "eval", args[0].name, out[0].name, args[1].name


def _score(link):
    from ..cog.atomspace import get_tv
    tv = get_tv(link)
    return (tv.mean or 0.0) * (tv.confidence or 0.0) if tv else 0.0


def _match(name, want, lex=None):
    return want is not None and canon(name, lex) == canon(want, lex)


def _pred_match(pred, verb, lex=None):
    return verb is not None and canon(pred, lex) == canon(verb, lex)


def _locative(pred, lex=None):
    p = canon(pred, lex)
    return any(h in p for h in LOCATIVE_PREDS)


def _candidates(aspace, frame: Frame, lex=None):
    """Facts that answer the frame, best first."""
    subj, obj, verb = frame.subject, frame.obj, frame.verb
    hits = []
    for link, kind, a, pred, b in _triples(aspace):
        if frame.wh and frame.wh_slot == "subject" and not frame.copula:
            # who VERB OBJ  →  VERB(?, OBJ)
            if kind == "eval" and _pred_match(pred, verb, lex) and _match(b, obj, lex):
                hits.append(link)
        elif frame.wh_slot == "object" and subj is not None:
            # what does SUBJ VERB  →  VERB(SUBJ, ?)
            if kind == "eval" and _pred_match(pred, verb, lex) and _match(a, subj, lex):
                hits.append(link)
        elif frame.wh_slot == "place":
            if _match(a, subj, lex) and kind == "eval" and _locative(pred, lex):
                hits.append(link)
        elif frame.copula and frame.wh and subj is not None:
            # what/who is SUBJ  →  everything we know about SUBJ
            if _match(a, subj, lex):
                hits.append(link)
    hits.sort(key=_score, reverse=True)
    return hits


def _yes_no(aspace, frame: Frame, lex=None):
    subj, obj, adj, verb = frame.subject, frame.obj, frame.adj, frame.verb
    want_b = adj or obj
    if subj is None or (want_b is None and verb is None):
        return None
    for link, kind, a, pred, b in _triples(aspace):
        if not _match(a, subj, lex):
            continue
        if verb is not None and not frame.copula:
            if kind == "eval" and _pred_match(pred, verb, lex) and (obj is None or _match(b, obj, lex)):
                return link
        elif kind == "inh" and want_b and _match(b, want_b, lex):
            return link
    return None


def _lexicon(aspace) -> set:
    """Single-word names in the AtomSpace: the words Mira knows, lower-cased."""
    words = set()
    for _link, _kind, a, pred, b in _triples(aspace):
        for name in (a, pred, b):
            if name:
                words.update(w.lower() for w in name.replace("_", " ").split())
    return words


def understand(aspace, text: str, dictionary=None) -> Answer | None:
    """Answer a question from the AtomSpace, or None if it is not a question we can parse."""
    if not is_available():
        return None
    if not text.strip().endswith("?"):
        return None         # statements and commands are not handled here
    lex = _lexicon(aspace)
    frame = build_frame(text, dictionary, lex)
    if frame is None:
        return None
    from .realizer import atom_to_text

    if frame.kind == "yn":
        link = _yes_no(aspace, frame, lex)
        if link is None:
            return None     # no matching fact: let the keyword path answer
        sentence = atom_to_text(link) or ""
        if not sentence:
            return None
        body = sentence.rstrip(".!?") 
        return Answer("Yes, " + body[0].lower() + body[1:] + ".", link, frame)

    hits = _candidates(aspace, frame, lex)
    if not hits:
        return None
    best = hits[0]
    sentence = atom_to_text(best)
    if not sentence:
        return None
    sentence = sentence[0].upper() + sentence[1:].rstrip(".")
    sentence += "."
    return Answer(sentence, best, frame)
