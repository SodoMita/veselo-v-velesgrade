#!/usr/bin/env python3
"""
chat.py – Single-character CLI chat with Mira the Archivist.

The minimal Velesgrad: one character, one conversation, same cognitive stack:
  - her knowledge lives in the AtomSpace (real OpenCog or dev shim)
  - responses are generated FROM the knowledge graph (not templates)
  - every sentence is validated by the Link Grammar parser
  - Theory of Mind: she never repeats a fact she already told you
  - she reacts to greetings, questions, farewells

Usage:
  VELESGRAD_DEV=1 python -m velesgrad_v2.chat     # no compilation needed
  python -m velesgrad_v2.chat                     # on real OpenCog

Commands: quit / exit  — leave.  facts — what she has told you.
"""

import random
import re
import sys

from .cog.atomspace import (
    AtomSpace, TruthValue, ConceptNode, PredicateNode,
    InheritanceLink, ImplicationLink, EvaluationLink, ListLink,
    set_tv, set_sti, init_atomspace,
)
from .cog.pln import Reasoner
from .dialogue import speech_acts
from .dialogue.compose import compose
from .dialogue.ingest import ingest_text
from .dialogue.lg_ctypes import parse_count, is_available as lg_available, get_dictionary
from .dialogue.realizer import AtomeseGenerator
from .dialogue.tom import TheoryOfMind, DialogueManager


# ── Mira's knowledge ─────────────────────────────────────────────────────
# Everything she can talk about is seeded here as proper Atomese.
# She speaks by converting these atoms back into English.

def seed_mira(aspace):
    def inh(a, b, s=0.9, c=0.85):
        link = InheritanceLink(ConceptNode(a), ConceptNode(b))
        set_tv(link, TruthValue(s, c))
        return link

    def evl(pred, a, b, s=0.85, c=0.8):
        link = EvaluationLink(PredicateNode(pred),
                              ListLink(ConceptNode(a), ConceptNode(b)))
        set_tv(link, TruthValue(s, c))
        return link

    def imp(a, b, s=0.8, c=0.75):
        link = ImplicationLink(ConceptNode(a), ConceptNode(b))
        set_tv(link, TruthValue(s, c))
        return link

    # ── Herself ──────────────────────────────────────────────────────────
    inh("mira", "velespriest")
    inh("mira", "archivist")
    inh("mira", "keeper_of_records")
    evl("resides_in", "mira", "archive")
    evl("serves", "mira", "veles")
    evl("guards", "mira", "the_relic_catalogue")
    inh("mira", "patient")
    inh("mira", "careful_with_words")

    # ── The archive ──────────────────────────────────────────────────────
    inh("archive", "knowledge_repository")
    evl("holds", "archive", "ancient_manuscripts")
    evl("holds", "archive", "prophecy_records")
    evl("holds", "archive", "the_relic_catalogue")
    inh("ancient_manuscripts", "irreplaceable")
    inh("archive", "quiet_place")

    # ── The stolen relic ─────────────────────────────────────────────────
    inh("relic", "stolen_artifact")
    inh("relic", "sacred_object")
    inh("relic", "veil_relic")
    evl("was_located_in", "relic", "archive")
    evl("stolen_by", "relic", "unknown_thief")
    evl("searched_by", "relic", "hounds")
    inh("veil_relic", "source_of_power")
    evl("left_behind", "thief", "broken_ward")
    inh("broken_ward", "clue")
    evl("happened_at", "theft", "deep_night")
    inh("theft", "inside_job", 0.5, 0.4)

    # ── The Veil ─────────────────────────────────────────────────────────
    inh("veil", "magical_boundary")
    evl("separates", "veil", "material_world")
    evl("separates", "veil", "spirit_world")
    inh("thinning_veil", "dangerous")
    evl("practiced_by", "veil_magic", "velespriests")
    imp("thinning_veil", "spirits_restless")
    imp("relic_returned", "veil_restored")

    # ── The city and its powers ──────────────────────────────────────────
    inh("hounds", "enforcer")
    inh("hounds", "suspicious")
    evl("suspects", "hounds", "velespriests")
    evl("patrols", "hounds", "night_streets")
    inh("velespriests", "guardians")
    inh("velespriests", "keepers_of_veil")
    inh("merchants", "traders")
    evl("spread", "merchants", "rumors")
    inh("velesgrad", "ancient_city")
    evl("founded_by", "velesgrad", "veles")
    inh("veles", "old_god")

    # ── Hierarchy so she can reason a step further ───────────────────────
    inh("stolen_artifact", "valuable")
    inh("sacred_object", "ancient")
    inh("enforcer", "dangerous")
    inh("guardians", "trustworthy")
    inh("knowledge_repository", "important")
    inh("magical_boundary", "fragile")
    inh("ancient_city", "layered_history")

    # Attention: what she'd naturally talk about first
    for a in ("relic", "archive", "veil", "mira"):
        set_sti(ConceptNode(a), 12.0)


# ── Speech handling ──────────────────────────────────────────────────────

# Words that can never be the topic of a "I know little of X" reply.
_TOPIC_STOP = {"what", "when", "where", "which", "whom", "whose", "about", "tell", "know", "remember",
               "told", "find", "found", "does", "have", "some", "that", "this", "there", "they", "them",
               "your", "with", "from", "into", "please", "could", "would", "should"}

GREETINGS = ("hello", "hi", "hey", "greetings", "good day", "privet", "zdravstvuy")
FAREWELLS = ("bye", "farewell", "goodbye", "dosvidaniya", "good night", "see you")

QUESTION_WORDS = ("what", "who", "where", "when", "why", "how", "which", "tell me about",
                  "do you know", "can you tell", "what about")


_THANKS = re.compile(r"\s*(thank you|thanks|thank|cheers|much appreciated)\b", re.I)


class MiraChat:
    def __init__(self, seed: int = 7, knowledge: str | None = None):
        """knowledge: None (archive only) or "books" (also the Gutenberg-derived
        human-life facts from data/book_facts.json, see dialogue/book_knowledge)."""
        self.rng = random.Random(seed)
        self.aspace = AtomSpace()
        init_atomspace(self.aspace)
        seed_mira(self.aspace)
        self.book_facts = 0
        if knowledge == "books":
            from .dialogue.book_knowledge import seed_books
            self.book_facts = seed_books(self.aspace)

        # One deduction pass up front: she reasons from what she knows.
        # e.g. relic→stolen_artifact→valuable gives her "the relic is valuable"
        # even though nobody told her the word "valuable".
        self.reasoner = Reasoner(self.aspace)
        self.reasoner.step()

        self.tom = TheoryOfMind()
        self.generator = AtomeseGenerator(self.aspace)
        self.dialogue = DialogueManager(self.tom, self.generator)
        self.turn = 0
        self.greeted = False
        self.farewelled = False
        # Atoms she has already voiced. Stored as atoms (not id()):
        # Cython re-wraps C++ handles in fresh Python objects, but Atom
        # hash/eq is handle-based, so set membership is stable on both
        # the real AtomSpace and the shim.
        self.said_atoms = set()
        self.learned_atoms = set()   # facts the player taught her this session
        self.last_topic = None       # pronoun-resolution slot (see _pronoun_resolve)
        self.last_frame = None       # the last understood question, for "why?" follow-ups

        # She starts knowing her own domain; the player starts knowing nothing.
        for fact in ("she is Mira the archivist",):
            self.tom.learn("Mira", fact)

    # -- knowledge lookup --------------------------------------------------
    def _topic_atoms(self, text: str):
        """Find her knowledge atoms relevant to words in the player's text.

        Matches on whole underscore-separated tokens, so "veil" matches
        "veil" and "the_veil" but NOT "veil_relic" (the player asked about
        one thing; a compound concept is a different thing).
        """
        import re
        stop = {"what", "about", "tell", "know", "does", "have", "with",
                "this", "that", "your", "there", "they", "them", "from",
                "would", "could", "should", "please", "anything", "something",
                "the", "and", "who", "for", "are", "you", "her", "him",
                "its", "was", "were", "any", "can", "say", "said", "ask"}
        words = set(
            w for w in re.findall(r"[a-z]+", text.lower())
            if len(w) > 2 and w not in stop
        )
        # Light plural normalization: archives→archive, cities→city
        words |= {w[:-1] for w in words if w.endswith("s") and len(w) > 4}
        words |= {w[:-3] + "y" for w in words if w.endswith("ies")}
        hits = []
        for atom in self.aspace:
            type_name = getattr(atom, "type_name", "")
            if not any(t in type_name for t in ("Inheritance", "Evaluation", "Implication")):
                continue
            out = list(getattr(atom, "out", []))
            if not out:
                continue
            # The subject of the knowledge: for Evaluation links it's the
            # first list argument; for Inheritance/Implication it's out[0].
            subj_tokens = set()
            obj_tokens = set()
            for i, o in enumerate(out):
                child_tokens = set(getattr(o, "name", "").lower().split("_"))
                for oo in getattr(o, "out", []) or []:
                    child_tokens |= set(getattr(oo, "name", "").lower().split("_"))
                child_tokens.discard("")
                if i == 0 and "Evaluation" in type_name:
                    # predicate name — skip it as subject markers
                    continue
                if i <= 1 and not subj_tokens:
                    subj_tokens |= child_tokens
                else:
                    obj_tokens |= child_tokens
            # Subject matches count double; object matches count once and
            # never double-count a word that is already in the subject
            # (e.g. "relic" in Inheritance(relic, veil_relic)).
            score = 2 * len(words & subj_tokens) + len(words & (obj_tokens - subj_tokens))
            if score:
                # Tie-break: prefer the simplest subject (fewest tokens).
                hits.append((score, -len(subj_tokens), atom))
        hits.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [a for _, _, a in hits]

    def _novel_fact(self, preferred_topic: str | None = None,
                    exclude_learned: bool = False):
        """One fact the player hasn't heard yet, preferably on-topic.
        exclude_learned: skip facts the player just taught her (they are
        not 'what I already knew')."""
        from .dialogue.realizer import atom_to_text

        candidates = []
        if preferred_topic:
            candidates = self._topic_atoms(preferred_topic)
        if not candidates:
            candidates = self.generator.select_salient_atoms("Mira", limit=25)

        for atom in candidates:
            if atom in self.said_atoms:
                continue
            if exclude_learned and atom in self.learned_atoms:
                continue
            text = self._best_sentence(atom)
            if not text or len(text.split()) < 3:
                continue
            if self.tom.knows("Player", text):
                continue
            self.said_atoms.add(atom)
            return text
        return None

    def _best_sentence(self, atom, player_tokens=None):
        """Compose candidates for an atom; keep the most grammatical.
        Adds an echo prefix when the player's own word appears in the fact."""
        cands = compose(atom, self.aspace, self.rng)
        if not cands:
            return None
        best, best_n = cands[0], -1
        if lg_available():
            d = get_dictionary()
            for c in cands:
                n = parse_count(c, d)
                if n > best_n:
                    best, best_n = c, n
        text = best
        # Attributed recall: she marks facts *you* told her
        if atom in self.learned_atoms:
            text = "You told me — " + text[0].lower() + text[1:]
        return text

    # ── Question routing tables ─────────────────────────────────────────
    _SPATIAL_RELS = {"in", "at", "on", "lie_in", "reside_in", "was_located_in",
                     "kept_in", "stored_in", "housed_in", "inside", "near"}
    _WHO_RELS = {"guard", "guards", "patrol", "patrols", "suspect", "suspects",
                 "member_of", "serve", "serves", "lead", "leads", "rule", "rules",
                 "stole", "stolen_by", "searched_by", "founded_by"}
    _WH_WORDS = ("where", "who", "why", "when", "what", "which", "how")

    def _pronoun_resolve(self, text: str) -> str:
        """Replace it/them/that/they with the last discussed concept.
        Documented limit: one-slot memory, no gender/number agreement."""
        if not self.last_topic:
            return text
        import re
        topic = self.last_topic.replace("_", " ")
        def repl(m):
            return f"the {topic}"              # "is relic valuable?" will not parse; "is the relic valuable?" does
        return re.sub(r"\b(it|them|that|those|they|she|he)\b", repl, text,
                      flags=re.IGNORECASE)

    def _relation_of(self, atom):
        """Predicate/prep name for an Evaluation, or 'is' for Inheritance."""
        t = getattr(atom, "type_name", "")
        out = list(getattr(atom, "out", []))
        if "Evaluation" in t and len(out) >= 2:
            return getattr(out[0], "name", "")
        if "Inheritance" in t:
            return "is"
        return ""

    def _subject_name(self, atom):
        t = getattr(atom, "type_name", "")
        out = list(getattr(atom, "out", []))
        if "Evaluation" in t and len(out) >= 2:
            inner = list(getattr(out[1], "out", []) or [])
            if inner:
                return getattr(inner[0], "name", "")
        elif out:
            return getattr(out[0], "name", "")
        return ""

    def _object_name(self, atom):
        t = getattr(atom, "type_name", "")
        out = list(getattr(atom, "out", []))
        if "Evaluation" in t and len(out) >= 2:
            inner = list(getattr(out[1], "out", []) or [])
            if len(inner) >= 2:
                return getattr(inner[1], "name", "")
        elif len(out) == 2:
            return getattr(out[1], "name", "")
        return ""

    _DEFN = re.compile(r"^\s*(?:(?:a|an|the)\s+)?([a-z][a-z'-]*)\s+(?:is|are|means)\s+(?:(?:a|an|the|kind of)\s+)?([a-z][a-z' -]*?)\s*[.!]?\s*$", re.I)

    def _is_definition(self, text: str) -> bool:
        """'X is a Y.' / 'X means Y.' with a word Mira does not know yet, and no question mark."""
        if text.strip().endswith("?"):
            return False
        m = self._DEFN.match(text)
        if not m:
            return False
        from .dialogue.understand import _lexicon, canon
        lex = _lexicon(self.aspace)
        return canon(m.group(1).lower(), lex) not in lex and m.group(1).lower() not in lex

    def _answer_self(self, low_q: str):
        """Answer questions about Mira from her own knowledge atoms."""
        from .cog.atomspace import types as _t
        mine = []
        for link in self.aspace.get_atoms_by_type(_t.EvaluationLink):
            out = list(getattr(link, "out", []))
            if len(out) == 2:
                inner = list(getattr(out[1], "out", []) or [])
                if inner and (getattr(inner[0], "name", "") == "mira"):
                    mine.append(link)
        for link in self.aspace.get_atoms_by_type(_t.InheritanceLink):
            out = list(getattr(link, "out", []))
            if out and getattr(out[0], "name", "") == "mira":
                mine.append(link)
        if not mine:
            return None
        if "where" in low_q:
            for link in mine:
                if self._relation_of(link) in ("reside_in", "is_at", "lives_in"):
                    t = self._best_sentence(link)
                    if t:
                        return self.rng.choice(["I am here, of course. ", ""]) + t
        for link in mine:
            if link not in self.said_atoms:
                t = self._best_sentence(link)
                if t and len(t.split()) >= 3:
                    self.said_atoms.add(link)
                    return t
        t = self._best_sentence(mine[0])
        return t

    def _wh_of(self, text: str):
        low = text.lower()
        for w in self._WH_WORDS:
            if low.startswith(w + " ") or f" {w} " in " " + low:
                return w
        return None

    def _filter_by_wh(self, atoms, wh):
        """Rank topic atoms for the question type."""
        if wh == "where":
            # 'live_in', 'work_at' are places too; within each group, what the player taught comes first.
            def _spatial(a):
                rel = str(self._relation_of(a) or "")
                return rel in self._SPATIAL_RELS or rel.split("_")[-1] in ("in", "at", "on", "near", "from")
            # A 'where' question takes only places (or what the player taught); "separates the world" is not a place.
            ranked = sorted(atoms, key=lambda a: (not _spatial(a), a not in self.learned_atoms))
            return [a for a in ranked if _spatial(a) or a in self.learned_atoms]
        if wh == "who":
            def who_rank(a):
                subj = self._subject_name(a).lower()
                obj = self._object_name(a).lower()
                score = 0
                if self._relation_of(a) in self._WHO_RELS:
                    score += 2
                if any(p in subj or p in obj for p in
                       ("mira", "hounds", "velespriests", "merchants", "someone",
                        "thief", "player", "veles", "guardians")):
                    score += 1
                return -score
            return sorted(atoms, key=who_rank)
        if wh == "why":
            from .cog.atomspace import types as _types
            impls = list(self.aspace.get_atoms_by_type(_types.ImplicationLink))
            return impls + atoms
        # what/which/when: definitions first (Inheritance), then the rest
        def def_rank(a):
            return 0 if "Inheritance" in getattr(a, "type_name", "") else 1
        return sorted(atoms, key=def_rank)

    def _is_yes_no(self, text: str) -> bool:
        low = text.lower().strip()
        if self._wh_of(low):
            return False
        firsts = ("is ", "are ", "was ", "were ", "does ", "do ", "did ",
                  "can ", "could ", "will ", "would ", "has ", "have ")
        return low.startswith(firsts) or (
            low.endswith("?") and len(low.split()) <= 8)

    def _implication_sentence(self, impl_atom):
        """Read ImplicationLink(A,B) as 'If A, then B (they say).'"""
        out = list(getattr(impl_atom, "out", []))
        if len(out) != 2:
            return None
        from .dialogue.realizer import atom_to_text, _np
        a = atom_to_text(out[0], self.rng) if getattr(out[0], "out", None) else None
        b = atom_to_text(out[1], self.rng) if getattr(out[1], "out", None) else None
        if not a:
            a = _np(getattr(out[0], "name", "")).replace("the ", "", 1) + " happens"
        if not b:
            b = _np(getattr(out[1], "name", ""))
        a = a.rstrip(".").replace(", they say", "")
        return f"If {a[0].lower()}{a[1:]}, then {b}."

    def _answer_yes_no(self, player_text: str):
        """Confirm or deny by direct match, with TV-based hedging."""
        import re
        words = set(w for w in re.findall(r"[a-z]+", player_text.lower())
                    if len(w) > 2 and w not in
                    ("the", "and", "for", "are", "was", "were", "does",
                     "can", "has", "have", "did", "will", "would", "you"))
        # A confirmation needs the stored fact to cover every content word of the question.
        # A negated question cannot be confirmed by a positive fact.
        negated = bool(re.search(r"\bnot\b|n't\b|\bnever\b", player_text.lower()))
        best = None
        for atom in self.aspace:
            t = getattr(atom, "type_name", "")
            if not any(x in t for x in ("Inheritance", "Evaluation")):
                continue
            subj = self._subject_name(atom).lower()
            obj = self._object_name(atom).lower()
            rel = self._relation_of(atom).lower().replace("_", " ")
            hay = f"{subj} {obj} {rel}"
            hay_words = set(re.findall(r"[a-z]+", hay))
            covered = sum(1 for w in words if w in hay_words or w in hay.split())
            if negated or not words or covered < len(words):
                continue
            score = covered
            if score >= 2 and (best is None or score > best[0]):
                best = (score, atom)
        if not best:
            # Nothing matched: answer with an explicit uncertainty line
            # instead of silently falling through to topic scan.
            return self.rng.choice([
                "I cannot confirm that from the records.",
                "The archive holds nothing on that claim.",
                "I have not heard that, and will not assert it.",
            ])
        atom = best[1]
        from .cog.atomspace import get_tv
        tv = get_tv(atom)
        text = self._best_sentence(atom)
        if not text:
            return None
        if tv.mean >= 0.5:
            lead = self.rng.choice(["Yes. ", "As far as the records say, yes. ",
                                    "That is so. "])
        else:
            lead = self.rng.choice(["I doubt it. ",
                                    "The records suggest otherwise. "])
        return lead + text[0].upper() + text[1:]

    # -- main response -----------------------------------------------------
    def respond(self, player_text: str) -> str:
        if not hasattr(self, "proper_seen"):
            self.proper_seen = set()
        for _w in re.findall(r"(?<=[a-z,] )([A-Z][a-z]{2,})\b", player_text):   # capitalised mid-sentence: a name
            if not re.search(rf"\bthe {_w}\b", player_text):                    # 'the Volga' keeps its article
                self.proper_seen.add(_w)
        # "What is the archive like?" asks what the archive is: answer as "What is the archive?"
        _lk = re.match(r"\s*what(?:'s| is) (the |a |an )?([A-Za-z][\w-]*) like\s*[?.!]*\s*$", player_text, re.I)
        if _lk and _lk.group(2).lower() not in ("i", "you", "it", "he", "she", "they", "we", "this", "that"):
            player_text = f"What is {(_lk.group(1) or '').strip() + ' ' if _lk.group(1) else ''}{_lk.group(2)}?"
        # a greeting sentence before a real one ("Good afternoon. My name is Yuri.") is dropped
        _g = re.match(r"\s*(?:good (?:morning|evening|afternoon|day)|hello|hi|hey|greetings)(?:,?\s*mira)?[.!,]\s+(?=\S)(?!mira[.!]*\s*$)", player_text, re.I)
        if _g and player_text[_g.end():].strip():
            player_text = player_text[_g.end():]
        # The article the player used for a noun after a verb or preposition is kept in later replies:
        # 'I like tea.' → 'the tea' becomes 'tea'; 'I have a garden.' → 'the garden' becomes 'a garden'.
        if not hasattr(self, "noun_det"):
            self.noun_det = {}
        _NOTN = {"the", "and", "his", "her", "our", "their", "its", "this", "that", "one", "day", "time", "good", "very", "not", "more"}
        for _v, _d, _n in re.findall(r"\b(like|love|enjoy|drink|eat|have|has|study|sell|trade in|at|in|near|on)\s+(a|an|the)?\s*([a-z]{3,})\b", player_text):
            if _n not in _NOTN:
                self.noun_det[_n] = _d.lower()
        out = self._respond_main(player_text)
        _vp = r"(like|love|enjoy|drink|eat|have|has|study|sell|trade in|at|in|near|on)"
        for _n, _d in self.noun_det.items():
            if _d == "":
                out = re.sub(rf"\b{_vp} the {_n}\b", lambda m: f"{m.group(1)} {_n}", out)
            elif _d in ("a", "an"):
                _art = "an" if _n[0] in "aeiou" else "a"
                out = re.sub(rf"\b{_vp} the {_n}\b", lambda m: f"{m.group(1)} {_art} {_n}", out)
                out = re.sub(rf"\b(have|has|like|love|enjoy|study|sell) {_n}\b", lambda m: f"{m.group(1)} {_art} {_n}", out)
        for _n in ("night", "noon", "morning", "evening", "summer", "winter", "spring", "autumn"):
            if re.search(rf"\b(?:at|in|on) {_n}\b", player_text):
                out = re.sub(rf"\bthe {_n}\b", _n, out)
        # the player wrote 'I am a student': 'you are student' in the reply gets its article back
        for _art, _w in re.findall(r"(?i)\b(a|an) ([a-z]{3,})\b", player_text):
            out = re.sub(rf"\b(are|is) {re.escape(_w)}\b", lambda mm: f"{mm.group(1)} {_art.lower()} {_w}", out)
        # 'you studies' → 'you study' (the third-person ending does not belong after 'you')
        out = re.sub(r"\byou (\w+)ies\b", lambda mm: f"you {mm.group(1)}y", out, flags=re.I)
        # the player wrote 'divides the world': an object after a verb in the reply gets its 'the' back
        for _w in re.findall(r"(?i)\bthe ([a-z]{3,})\b", player_text):
            out = re.sub(rf"\b(divides|separates|keeps|holds|guards|serves|has|have|sees|guard|hold|keep) ({re.escape(_w)})\b",
                         lambda mm: f"{mm.group(1)} the {mm.group(2)}", out)
        # the player wrote 'The farm is big': a clause-initial 'farm is big' in the reply gets its 'the' back
        for _w in re.findall(r"(?i)\bthe ([a-z]{3,})\b", player_text):
            out = re.sub(rf"((?:^|— |[Tt]hat |\. |, ))({re.escape(_w)}) (is|are|was|were|has|have|lives?|holds?)\b",
                         lambda mm: f"{mm.group(1)}the {mm.group(2)} {mm.group(3)}", out)
        # the player wrote 'the Volga': a reply that drops it to 'Volga' is restored
        for _w in re.findall(r"(?<=\bthe )([A-Z][a-z]{2,})\b", player_text):
            out = re.sub(rf"(?<![Tt]he )\b{_w}\b", f"the {_w}", out)
        for _w in re.findall(r"(?<=[a-z,] )([A-Z][a-z]{2,})\b", player_text):   # 'in Moscow' is not 'in the moscow'
            out = re.sub(rf"\bthe {_w.lower()}\b", _w, out)
            out = re.sub(rf"\b{_w.lower()}\b", _w, out)
        for _w in self.proper_seen:
            if _w.lower() not in ("veil", "velespriests", "velespriest", "veles", "velesgrad", "mira", "saint"):
                out = re.sub(rf"\bThe {_w}\b", _w, out)
                out = re.sub(rf"\bthe {_w}\b", _w, out)
        # Where the player said 'a river', a reply that says 'the river' is restored to 'a river'.
        for _m in re.finditer(r"\b(a|an)\s+([a-z]+)\b", player_text, re.I):
            out = re.sub(rf"\bthe {re.escape(_m.group(2).lower())}\b", f"{_m.group(1).lower()} {_m.group(2).lower()}",
                         out, flags=re.I)
        # Every reply: the player is 'you', and a book clause ', who is a baker,' is not part of what was said.
        out = re.sub(r"\bthe traveler,? who (?:is|are) [^,.]+?,\s*", "you ", out, flags=re.I)
        out = re.sub(r"\bthe traveler\b", "you", out, flags=re.I)
        # names that take no article: 'The Velesgrad is' → 'Velesgrad is'
        out = re.sub(r"\b[Tt]he (Velesgrad|Veles|Pepys|Mira|Petersburg)\b", r"\1", out)
        # 'a' before a vowel sound: 'a old god' → 'an old god'
        out = re.sub(r"([.!?] )([a-z])", lambda mm: mm.group(1) + mm.group(2).upper(), out)   # sentence starts
        if out[:1].islower():
            out = out[:1].upper() + out[1:]                                                 # the reply's first letter
        out = re.sub(r"\b([Aa]) (old|ancient|honest|important|evil|angry|open|easy|ideal|only|odd|early|eternal|"
                     r"enormous|icy|upper|inner|outer|unknown|uncertain|urgent|useful|unusual|elderly)\b",
                     lambda mm: ("An " if mm.group(1) == "A" else "an ") + mm.group(2), out)
        out = re.sub(r",\s*which (?:are|is) [a-z ]+?,", "", out)     # book clause, not the player's words
        # 'you' takes the base verb: 'you lives' → 'you live', 'you is' → 'you are'
        out = re.sub(r"\byou (lives|is|has|works|goes|comes|does|was|knows|keeps|needs|wants|likes)\b",
                     lambda mm: "you " + {"lives": "live", "is": "are", "has": "have", "works": "work", "goes": "go",
                                          "comes": "come", "does": "do", "was": "were", "knows": "know",
                                          "keeps": "keep", "needs": "need", "wants": "want",
                                          "likes": "like"}[mm.group(1).lower()], out, flags=re.I)
        out = re.sub(r"(^|[.!?]\s+)you\b", lambda mm: mm.group(1) + "You", out)
        # Plural subjects take 'are': 'The Velespriests is a guardians' → 'The Velespriests are guardians'.
        from .dialogue.realizer import _is_plural as _plu

        def _agree(mm):
            det, subj, art, rest = mm.group(1) or "", mm.group(2), mm.group(3), mm.group(4)
            if subj.lower() in ("this", "his", "its", "yes", "us", "always", "perhaps", "thus", "it", "is", "has"):
                return mm.group(0)
            if not _plu(subj.lower()):
                return mm.group(0)
            return f"{det}{subj} are {rest}"
        out = re.sub(r"\b((?:The |the )?)([A-Za-z]+s) is (?:(a |an ))?([a-z]+)", _agree, out)
        return out

    def _respond_main(self, player_text: str) -> str:
        # "Hi. My name is Anna." : the greeting is only a greeting; the content still needs an answer.
        g = re.match(r"^\s*(hi|hello|hey|greetings|good (?:morning|evening|day))\b(?:\s+(?:again|there|everyone|all))?[\s,!.]*(.+)$",
                     player_text, re.I | re.S)
        if g and g.group(2).strip() and not re.fullmatch(r"(mira|mira,?)[\s!.?]*", g.group(2).strip(), re.I):
            if not self.greeted:
                self.greeted = True
            player_text = re.sub(r"^mira[\s,!.]+", "", g.group(2).strip(), flags=re.I) or g.group(2).strip()
        # "I have a dog named Rex." → "Rex is a dog", and Rex is recorded as the player's dog.
        if not hasattr(self, "kin"):
            self.kin = {}
        _nm = re.search(r"\b(?:[Ii] have |[Mm]y |[Ii]'ve got )?(?:a |an |my )?([a-z]+) (?:named|called) ([A-Z][a-z]+)\b", player_text)
        if _nm and _nm.group(1).lower() not in ("name", "person", "man", "woman", "place", "city"):
            self.kin[_nm.group(1).lower()] = _nm.group(2)
            player_text = f"{_nm.group(2)} is a {_nm.group(1).lower()}."
        _called = re.match(r"\s*what (?:is|was) my ([a-z]+) (?:called|named)\s*[?.!]*\s*$", player_text, re.I)
        if _called and _called.group(1).lower() in self.kin:
            return f"You told me your {_called.group(1).lower()} is called {self.kin[_called.group(1).lower()]}."
        # Kinship: "my sister Olga lives in Tver" is learned as "Olga lives in Tver", and Olga is recorded
        # as the player's sister. Questions that say "my sister" are then answered about Olga.
        if not hasattr(self, "kin"):
            self.kin = {}
        _KIN = r"(sister|brother|mother|father|wife|husband|son|daughter|cousin|aunt|uncle|grandmother|grandfather|friend)"
        km = re.match(rf"\s*(?:[Mm]y|[Oo]ur)\s+{_KIN}\s+([A-Z][a-z]+)\s+(.+)$", player_text, re.S)
        if km and not player_text.rstrip().endswith("?"):
            self.kin[km.group(1).lower()] = km.group(2)
            player_text = f"{km.group(2)} {re.sub(r'[ ,]+too[.!]?$', '.', km.group(3).rstrip())}"
            if not player_text.endswith("."):
                player_text += "."
        elif player_text.rstrip().endswith("?") and not re.match(r"\s*who (?:is|am) ", player_text, re.I):
            def _kin_sub(mm):
                return self.kin.get(mm.group(1).lower(), mm.group(0)) if mm.group(1).lower() in self.kin else mm.group(0)
            player_text = re.sub(rf"\b(?:[Mm]y|[Oo]ur)\s+{_KIN}\b", lambda mm: _kin_sub(mm), player_text, flags=re.I)
        # A filler word on its own ("Hmm.", "Okay.", "Interesting.") is not a statement to learn.
        if re.fullmatch(r"\s*(?:(?:hmm+|mm+|uh+|um+|okay|ok|well|interesting|i see|right|yes|no|oh|ah|wow)[,\s]*)+[.!?]*\s*",
                        player_text, re.I):
            return self.rng.choice(["I am listening.", "Go on, I am listening.", "Mm. Tell me more, or ask me something."])
        # A greeting alone ("Good evening, Mira.") is answered as a greeting.
        if re.fullmatch(r"\s*(?:good (?:morning|evening|afternoon|day)|hello|hi|hey|greetings)[,\s]*(?:mira)?[.!]*\s*",
                        player_text, re.I):
            return "Good day to you. Ask me what the records hold."
        # "Okay, thanks." / "Thanks a lot." are acknowledgements, not statements.
        if re.fullmatch(r"\s*(?:(?:okay|ok|alright|fine|well|great|good)[,\s]*)?(?:thanks|thank you)(?: a lot| very much| again)?"
                        r"[,\s]*(?:mira)?[.!]*\s*", player_text, re.I):
            return "You are welcome."
        # The clock is not in the records.
        if re.match(r"\s*(do you know|can you tell me|tell me) what time it is|what time is it\s*[?.!]*\s*$", player_text, re.I):
            return "I keep no clock. The records do not hold the hour."
        # Questions about herself: honest, short answers.
        if re.match(r"\s*are you (?:alive|real|conscious|sentient|awake|human|sure)\b", player_text, re.I):
            return "I keep records, and I do not claim feelings of my own. Ask me what the records hold."
        if re.match(r"\s*what(?:'s| is) your name\s*[?.!]*\s*$", player_text, re.I):
            return "I am Mira, keeper of the archive of Velesgrad."
        # "Where do I live?" with two taught places: name both, not only the latest.
        _wl = re.match(r"\s*where (?:do|does) (I|you|[A-Z][a-z]+) live\s*[?.!]*\s*$", player_text, re.I)
        if _wl and getattr(self, "all_claims", None):
            _subj = "player" if _wl.group(1) in ("I", "you") else _wl.group(1).lower()
            _places = []
            for (_a, _rel), _bs in self.all_claims.items():
                if "live" in str(_rel) and str(_a).lower() == _subj:
                    _places += _bs
            _places = list(dict.fromkeys(_places))
            if len(_places) > 1:
                return "You told me you live in " + ", and also in ".join(p.title() if p.islower() else p for p in _places) + "."
        # "Do you remember my name?" is the same question as "What is my name?"
        if re.match(r"\s*(?:do you|can you|did you) (?:remember|recall|know) my name\s*[?.!]*\s*$", player_text, re.I):
            player_text = "What is my name?"
        # "What did I tell you about Vologda?" is a question about Vologda: answer as "What is Vologda?"
        _told = re.match(r"\s*what did i (?:tell|say to) you about (.+?)\s*[?.!]*\s*$", player_text, re.I)
        if _told:
            player_text = f"What is {_told.group(1).strip()}?"
        # "I am a baker." → remembered; "What do I do?" → "You told me you are a baker."
        if not hasattr(self, "player_job"):
            self.player_job = None
        _job = re.search(r"(?:^|[.;,]\s*|\band\s+)(?:[Ii] am|[Ii]'m) (?:a|an) ([A-Za-z]+)\b", player_text)
        if _job:
            self.player_job = _job.group(1).lower()
        if re.match(r"\s*(?:what (?:do|did) i do|what am i|what(?:'s| is) my (?:job|occupation|profession|work))\s*[?.!]*\s*$", player_text, re.I) and self.player_job:
            return f"You told me you are a {self.player_job}."
        # "Who is Pavel?" (the player's own name) and "Who is my brother?" (a kin the player named).
        if not hasattr(self, "kin"):
            self.kin = {}
        _who = re.match(r"\s*who (?:is|am) (my |your )?(\w+)\s*[?.!]*\s*$", player_text, re.I)
        if _who:
            _w = _who.group(2)
            if _who.group(1) is None and getattr(self, "player_name", None) and _w.lower() == self.player_name.lower():
                return f"You told me your name is {self.player_name}."
            _named = [k for k, v in self.kin.items() if v.lower() == _w.lower()]
            if _who.group(1) is None and _named:
                return f"You told me {self.kin[_named[0]]} is your {_named[0]}."
            if _who.group(1) and _w.lower() in self.kin:
                return f"You told me {self.kin[_w.lower()]} is your {_w.lower()}."
        # "Describe the Velespriests." / "Define the relic." are requests for what the records hold.
        dsc = re.match(r"\s*(?:please\s+|could you\s+|can you\s+)?(describe|define|explain)\s+(?:to me\s+)?(.+?)[.?!]*\s*$",
                       player_text, re.I)
        if dsc and len(dsc.group(2).split()) <= 5:
            player_text = f"What is {dsc.group(2).strip()}?"
        if re.fullmatch(r"\s*mira\s*[?!.]*\s*", player_text, re.I):     # a bare call of her name
            return self.rng.choice(["I am here, and listening.", "Yes? I am here.", "I am here. Ask me anything."])
        # "The bridge is old. Who built it?": learn the statements first, then answer the question.
        _sents = [x.strip() for x in re.split(r"(?<=[.!?])\s+", player_text.strip()) if x.strip()]
        if len(_sents) > 1 and any(x.endswith("?") for x in _sents) and any(not x.endswith("?") for x in _sents):
            for st in [x for x in _sents if not x.endswith("?")]:
                for _desc, _atom in ingest_text(self.aspace, st, speaker="player", listener="Mira",
                                                antecedent=self.last_topic):
                    self.learned_atoms.add(_atom)
            player_text = " ".join(x for x in _sents if x.endswith("?"))
        # "Do you know who Pepys is?" is the question "Who is Pepys?"; the frame must be the embedded question.
        emb = re.match(r"^\s*(?:please\s+)?(?:(?:do|can|could) you (?:know|tell me)|tell me|please tell me|"
                       r"(?:can|could) you tell me) (who|what|where|when|why|how) (.+?)\??\s*$",
                       player_text, re.I | re.S)
        if emb:
            wh_w, rest = emb.group(1).capitalize(), emb.group(2).strip()
            cop = re.match(r"^(.+?)\s+(is|are|was|were)$", rest, re.I)     # 'Pepys is' → 'is Pepys'
            player_text = (f"{wh_w} {cop.group(2).lower()} {cop.group(1)}?" if cop
                           else f"{wh_w} {rest}?")
        # Capitalized words inside a sentence (not the first word, not "I") are names the player uses.
        from .dialogue import realizer as _rz
        # Also a capitalized first word that is not an ordinary sentence opener ('Oleg works…').
        _openers = {"the", "and", "but", "what", "who", "where", "when", "why", "how", "hi", "hello", "hey",
                    "good", "yes", "no", "thank", "thanks", "please", "tell", "do", "does", "did", "is", "are",
                    "was", "were", "can", "could", "would", "should", "will", "my", "your", "our", "this",
                    "that", "there", "here", "it", "its", "if", "so", "okay", "ok", "sorry", "i", "we", "you",
                    "he", "she", "they", "me", "him", "her", "us", "them", "maybe", "perhaps", "really", "well",
                    # imperatives open many requests; they are not names
                    "name", "describe", "explain", "give", "show", "define", "list", "find", "write", "say",
                    "speak", "answer", "help", "remember", "forget", "keep", "let", "make", "bring", "imagine",
                    "consider", "suppose", "recall", "repeat", "count", "compare", "translate", "summarize"}
        for w in re.findall(r"(?:(?<=[a-z,] )|(?<=^))([A-Z][a-z]{2,})\b", player_text):
            if w.lower() not in _openers:
                _rz.PROPER_NAMES.add(w.lower())
        out = self._respond(player_text)
        # Proper names are stored in lower case; capitalize them wherever they appear as whole words.
        names = "|".join(sorted((re.escape(n) for n in _rz.PROPER_NAMES), key=len, reverse=True))
        out = re.sub(rf"\b({names})\b", lambda m: m.group(1).capitalize(), out, flags=re.I)
        out = re.sub(r",\s*\.", ".", out)                             # stray ', .' from echoes
        # one hedge per reply: "The records say: They say X" → "The records say: X"
        out = re.sub(r"((?:the records say|they say|i can tell you this|that much i know)[:—,]?\s+)"
                     r"(?:they say|everyone knows|the records hold that|the records say:?|i can tell you this|"
                     r"it is well known that)\s+",
                     r"\1", out, flags=re.I)
        if out and out[0].islower():
            out = out[0].upper() + out[1:]
        if re.search(r"you told me", out, re.I):     # a reply that credits the player is not common knowledge
            out = re.sub(r"everyone knows\s+", "", out, flags=re.I)
            out = re.sub(r"(You told me\s*[—-]\s*)(?:you told me\s*[—-]\s*)+", r"\1", out, flags=re.I)
            out = re.sub(r"(You told me\s*[—-]\s*)(?:the records hold that |they say |the records say:? )",
                         r"\1", out, flags=re.I)
            out = re.sub(r",? they say(?=[.!?]|$)", "", out, flags=re.I)
        out = re.sub(r"\b(is|are|was|were) a kind of\b", r"\1 a", out)   # "is a kind of doctor" → "is a doctor"
        if out and out[0].islower():
            out = out[0].upper() + out[1:]          # every reply starts a sentence
        return out

    def _respond(self, player_text: str) -> str:
        self.turn += 1
        act = self.dialogue.recognize_act(player_text).value  # data-driven act
        # Thanks and acknowledgements are not facts to learn ("thank you, that was helpful").
        if _THANKS.match(player_text) and "?" not in player_text:
            return self.rng.choice(["You are welcome.", "Gladly.", "The archive is glad to help."])
        # Who she is, asked directly.
        if re.search(r"\bwho are you\b", player_text, re.I):
            return ("I am Mira, keeper of the archive of Velesgrad. I answer from what I have read "
                    "and what the records hold, and I say when I do not know.")
        # "define X" is a question even without a question mark (before the greeting branch).
        if re.match(r"\s*(define|what is the meaning of)\s", player_text, re.I):
            act = "question"
        # A sentence with no "?" that does not open like a question is a statement ("The sky is blue.").
        if act == "question" and not player_text.strip().endswith("?") and not re.match(
                r"\s*(what|who|where|when|why|how|which|is|are|was|were|do|does|did|can|could|will|would|"
                r"should|have|has|define|tell|name|give|list)\b", player_text, re.I):
            act = "statement"
        self.tom.learn("Player", f"(heard) {player_text[:60]}")

        # A farewell does not lock the channel: a later real message reopens the talk.
        if self.farewelled and act == "farewell":
            return "Until next time."
        if self.farewelled:
            self.farewelled = False

        # ── FAREWELL ────────────────────────────────────────────────────
        if act == "farewell":
            self.farewelled = True
            mined = speech_acts.phrase("farewells", limit=3)
            base = self.rng.choice([
                "Walk in wisdom. The archive will keep your words.",
                "May the Veil protect you. Come back when you have more questions.",
                "Farewell. I will be here, among the records.",
            ])
            # Occasionally borrow one short mined parting word (register-safe)
            if mined and self.rng.random() < 0.5:
                w = mined[0]
                if w in ("good night", "see you", "take care", "bye"):
                    return f"{base} {w.capitalize()}."
            return base

        # ── GREETING ────────────────────────────────────────────────────
        if act == "greeting":
            if not self.greeted:
                self.greeted = True
                return self.rng.choice([
                    "Peace upon you. I am Mira — I keep the archive.",
                    "Well met. Mira, keeper of the records. Ask, and I will answer what I can.",
                    "The Veil watches. You have found the archive. I am Mira.",
                ])
            # A repeated greeting is only a greeting; attaching a random fact read as noise.
            return self.rng.choice(["Again, well met.", "You return. Good.", "The bells marked your coming."])

        # A definition of an unknown word ("the moonstone is a gem.") is teaching,
        # whatever the act classifier thinks. It goes to the statement branch below.
        if act in ("question", "command") and self._is_definition(player_text):
            act = "statement"

        # ── SMALL TALK: "how are you?" is not a request for records ─────
        if re.search(r"\bhow (are|r) (you|u)\b|\bhow('s| is) it going\b|\bhow do you do\b", player_text.lower()):
            return self.rng.choice([
                "I am well, thank you. And you?",
                "I am well enough, and glad of the company. How are you?",
                "Well, as far as a keeper of records can be. How are you?",
            ])

        # An insult is an opinion of the player's, not a fact about her; it is not recorded.
        if re.match(r"\s*(you are|you're|you is)\s+(stupid|dumb|useless|a fool|boring|annoying|wrong|bad|ugly)\b",
                    player_text, re.I):
            return "That is your opinion, and I will not write it into the records as fact."
        # "Are you a robot?" / "Are you human?": what she is, honestly.
        if re.search(r"\bare you (a |an )?(robot|machine|human|real|person|bot|ai|computer|program)\b", player_text, re.I):
            return ("I am Mira, keeper of the archive of Velesgrad. I answer from what the records hold, "
                    "and I say when I do not know.")
        # "What is your opinion of Pepys?" / "What is your view on the Veil?": she keeps no opinions.
        op = re.search(r"\b(?:your (?:opinion|view|views|thoughts|feelings)|your (?:opinion|view) on)\s+(?:of|on|about)?\s*(.+?)\??$",
                       player_text, re.I)
        if op:
            topic = re.sub(r"^(the|a|an)\s+", "", op.group(1).strip(), flags=re.I).strip()
            if topic:
                return (f"I keep records, and I hold no opinion of my own about {topic}. "
                        f"Ask me what the records hold, and I will answer that.")
        if re.search(r"\bdo you (feel|like|love|hate|think|dream|want|fear|enjoy|believe|prefer)\b|"
                     r"\bwhat do you (feel|think|like|want|believe)\b|\bhow do you feel\b", player_text, re.I):
            return ("I keep records, and I do not claim feelings of my own. "
                    "Ask me what the records hold, and I will answer that.")
        if re.search(r"\bhow (to|do i|can i|should i|do we)\b", player_text, re.I) and not re.search(
                r"\bdo you\b|\bhow (are|is|old|far|long|big|many|much)\b", player_text, re.I):
            return ("I keep the records of the city and of human words, not instructions. "
                    "I cannot tell you how to do that from them.")
        if re.search(r"\bopposite of\b|\bantonym\b", player_text, re.I):
            return "I keep no antonyms on file, so I will not guess at an opposite."
        if re.fullmatch(r"\s*can you help( me)?\s*[?.!]?\s*", player_text, re.I) \
                or re.fullmatch(r"\s*could you help( me)?\s*[?.!]?\s*", player_text, re.I):
            return "Yes. Ask me what you wish to know, and I will answer from the records, and say when I do not know."
        if re.fullmatch(r"\s*tell me (something|a fact|anything)( interesting)?\s*[?.!]?\s*", player_text, re.I):
            fact = self._novel_fact()
            return (f"Here is one: {fact}" if fact else
                    "The archive holds more than I have voice for. Ask me of the relic, the Veil, or the city.")

        # The player's name: "My name is Anna." / "What is my name?"
        nm = re.match(r"\s*(?:(?:actually|no|well|oh|so|also|sorry)[,\s]+)?(?:my name is|i am called|call me)\s+([A-Za-z][A-Za-z'-]*)(.*)$", player_text, re.I | re.S) \
            or re.match(r"\s*I am\s+([A-Z][a-z][A-Za-z'-]*)\b(.*)$", player_text, re.S)   # "I am Dmitry" (capitalized)
        if nm:
            self.player_name = nm.group(1).capitalize()
            rest = re.sub(r"^\s*(and|but|,)\s*", "", nm.group(2)).strip()
            if not re.search(r"[A-Za-z]", rest):                # punctuation alone is not a message
                rest = ""
            if not rest:
                return f"I will remember your name, {self.player_name}."
            player_text = rest[:1].upper() + rest[1:]    # the rest of the message is still said to her
        if re.search(r"\bwhat is my name\b|\bdo you know my name\b|\bwho am i\b", player_text, re.I):
            return (f"Your name is {self.player_name}." if getattr(self, "player_name", None)
                    else "You have not told me your name.")

        # "what did I tell you?" is about what the player taught her this session.
        if re.search(r"\bwhat (did|do) i (tell|said|say|told)\b|\bremember what i (told|said)\b", player_text, re.I):
            if self.learned_atoms:
                last = list(self.learned_atoms)[-1]
                said = self._best_sentence(last)
                if said:
                    _lead = r"^(you told me\s*[—-]\s*|they say |everyone knows |the records hold that |" \
                            r"it is well known that |the records say:?\s*)"
                    while re.match(_lead, said, flags=re.I):
                        said = re.sub(_lead, "", said, count=1, flags=re.I).strip()
                    return f"You told me that {said[0].lower()}{said[1:].rstrip('.')}."
            return "You have not told me anything I can recall in this session."

        # ── TRANSLATION: Mira keeps English records; she does not translate ─
        tr = re.search(r"\bhow (do|would|can) (you|i|we) (say|write|translate)\b.*\b(in|into) (\w+)\b", player_text.lower())
        if tr:
            return (f"I keep English records, and I have no {tr.group(5).capitalize()} words on file. "
                    "I cannot translate that.")

        # ── QUESTION / COMMAND (requests for knowledge) ─────────────────
        if act in ("question", "command"):
            resolved = self._pronoun_resolve(player_text)
            # "why?" after an answer asks for the reason behind the last claim.
            if re.fullmatch(r"\s*why\s*\??\s*", resolved, re.I) and self.last_frame \
                    and self.last_frame.subject and (self.last_frame.adj or self.last_frame.obj):
                pred = self.last_frame.adj or self.last_frame.obj
                resolved = f"why is {self.last_frame.subject.replace('_', ' ')} {pred}?"
            # "and the veil?" / "what about the veil?" ask about the veil.
            fu = re.fullmatch(r"\s*(?:and|what about)\s+(?:the |a |an )?(.+?)\s*\??\s*", resolved, re.I)
            if fu and not re.search(r"\b(is|are|was|does|do)\b", resolved, re.I) \
                    and not re.match(r"(who|what|where|when|why|how|which)\b", fu.group(1), re.I):
                resolved = f"what is the {fu.group(1)}?"
            # First person in a question refers to the player, the concept stored in her records.
            parse_text = resolved                        # the grammar parses "I"; the records say "player"
            resolved = re.sub(r"\bI\b", "player", resolved)
            low_q = resolved.lower()
            # "what do you know about X" / "do you remember X" are topic questions, not self-description.
            m_about = re.match(r"\s*(?:what|tell me) (?:do you know|you know) about (.+?)\s*\??$", low_q) \
                or re.match(r"\s*do you (?:remember|know) (?:about )?(?:the |a |an )?(.+?)\s*\??$", low_q)
            if m_about:
                low_q = f"what is {m_about.group(1)}?"
                resolved = low_q
            elif re.search(r"\byour\b|\b(who|what) (are|do) you\b|\bare you\b", low_q):
                self_answer = self._answer_self(low_q)
                if self_answer:
                    return self_answer
            # Understanding first: parse the question (Link Grammar) into a frame and
            # answer from a matching AtomSpace fact. Falls back to keyword lookup below.
            # Remember the parsed question so a later "why?" can refer back to it.
            try:
                from .dialogue.understand import build_frame as _bf
                fr = _bf(resolved)
                if fr is not None and fr.subject and (fr.adj or fr.obj):
                    self.last_frame = fr
            except Exception:
                pass
            try:
                from .dialogue.understand import understand as _understand
                ua = _understand(self.aspace, parse_text)
            except Exception:
                ua = None
            if ua is not None:
                if ua.frame is not None:
                    self.last_topic = ua.frame.subject or ua.frame.obj or self.last_topic
                    if ua.frame.subject and (ua.frame.adj or ua.frame.obj):
                        self.last_frame = ua.frame
                text = ua.text or ""
                # the player is 'the traveler' in the records; a book clause ', who is a baker,' is not what was said
                text = re.sub(r"\bthe traveler,? who (?:is|are) [^,.]+?,\s*", "you ", text)
                text = re.sub(r"\bthe traveler\b", "you", text)
                if getattr(ua, "atom", None) is not None and ua.atom in self.learned_atoms and text \
                        and not re.search(r"you told me|^yes", text, re.I):
                    # answered from what the player taught: say so, without hearsay leads
                    bare = re.sub(r"^(everyone knows|they say|the records hold that|the records say:|"
                                  r"the records say|i can tell you this)\s*[—:,]?\s*", "", text, flags=re.I)
                    bare = re.sub(r",? they say\.?$", ".", bare)
                    if bare:
                        text = f"You told me — {bare[0].lower()}{bare[1:]}"
                return text
            # Yes/no first: "is the relic valuable?" → confirm/deny with hedging
            if self._is_yes_no(resolved):
                yn = self._answer_yes_no(resolved)
                if yn:
                    return yn
            wh = self._wh_of(resolved)
            atoms = self._topic_atoms(resolved)
            # Learned-this-session facts first: they are the newest knowledge
            # and answer pronoun/catch-up questions naturally.
            atoms = ([a for a in atoms if a in self.learned_atoms] +
                     [a for a in atoms if a not in self.learned_atoms])
            if wh:
                atoms = self._filter_by_wh(atoms, wh)
            if wh == "where" and not atoms and not re.search(r"\b(i|my|me|you|your)\b", resolved, re.I):
                return "The records do not say where that is."     # no place on record; no unrelated fact instead
            answer = None
            for atom in atoms:
                if atom in self.said_atoms:
                    continue
                if "Implication" in getattr(atom, "type_name", ""):
                    t = self._implication_sentence(atom)
                else:
                    t = self._best_sentence(atom)
                # A recorded (non-learned) fact must share two content words with the question,
                # or it is a different subject that happens to contain one word.
                q_content = {w for w in re.findall(r"[a-z]+", resolved.lower())
                             if len(w) > 3 and w not in _TOPIC_STOP
                             and w not in ("where", "what", "when", "which", "whose", "does", "about", "tell")}
                fact_words = set(re.findall(r"[a-z]+", (t or "").lower()))
                # crude stem: 'patrols' and 'patrol' share 'patro'
                shared = {w for w in q_content if any(w[:4] == f[:4] for f in fact_words if len(f) >= 4)}
                from .dialogue.realizer import PROPER_NAMES as _names
                name_hit = {w for w in q_content if w in _names and w in fact_words}
                if len(shared) < min(2, len(q_content)) and not name_hit:   # a shared proper name is the topic itself
                    continue
                if t and len(t.split()) >= 3:
                    self.said_atoms.add(atom)
                    subj = self._subject_name(atom) or self._object_name(atom)
                    if subj:
                        self.last_topic = subj
                    answer = t
                    if atom in self.learned_atoms:          # the player taught it: say so, without hearsay leads
                        bare = re.sub(r"^(everyone knows|they say|the records hold that|the records say:)\s*",
                                      "", t, flags=re.I)
                        answer = f"You told me — {bare[0].lower()}{bare[1:]}" if bare else t
                    break
            if answer:
                lead = self.rng.choice(["", "I can tell you this — ", "The records say: ", "That much I know. "])
                if answer.startswith("You told me"):
                    lead = ""                  # already attributed to the player; no second hedge
                return (lead + answer).strip()
            fallback = self._novel_fact()
            # Only offer an unrelated fact if it shares a content word with the question;
            # otherwise say plainly that she does not know.
            q_words = {w for w in re.findall(r"[a-z]+", resolved.lower())
                       if len(w) > 3 and w not in _TOPIC_STOP}
            if fallback and len(q_words & set(re.findall(r"[a-z]+", fallback.lower()))) >= 2:
                return f"I know little of that. What I do know — {fallback.lower()}"
            if fallback and q_words:
                options = ["I have no record of that. I know little of that.",
                           "I have no record of that, and I will not guess.",
                           "That is beyond what the records hold.",
                           "I cannot tell you that from the archive."]
                used = getattr(self, "_fallback_used", set())
                self._fallback_used = used
                fresh = [o for o in options if o not in used] or options
                pick = fresh[len(used) % len(fresh)]     # deterministic: no extra draw on the seeded rng
                used.add(pick)
                return pick
            stems = speech_acts.phrase("dont_know", limit=3)
            stem = self.rng.choice(stems) if stems else "i don't know"
            return self.rng.choice([
                f"{stem.capitalize()}. Ask me of the relic, the Veil, the city.",
                f"{stem.capitalize()} — but the archive holds more than I have voice for.",
            ])

        # ── STATEMENT ───────────────────────────────────────────────────
        # First: learn from it. Natural-language ingestion writes the
        # player's facts into her AtomSpace (LG-parsed triples).
        # Multi-sentence input is split and each sentence ingested.
        import re as _re
        sentences_in = [s.strip() for s in _re.split(r"(?<=[.!?;])\s+", player_text)
                        if s.strip()]
        if not sentences_in:
            sentences_in = [player_text]
        # "The guards are tired and the merchants are kind." → two clauses, each learned.
        _split = []
        for s in sentences_in:
            parts = _re.split(r",?\s+and\s+(?=(?:(?:the|a|an|my|your|our)\s+)?(?:i|he|she|they|it|\w+)\s+(?:is|are|was|were|am|has|have)\b"
                              r"|(?:i|he|she|they|we)\s+(?!and\b)\w+)",
                              s, flags=_re.I)
            _split.extend(p.strip() for p in parts if p.strip())
        sentences_in = _split or sentences_in
        # "The archive is old and dusty." → "The archive is old." and "The archive is dusty."
        _two = []
        for s_ in sentences_in:
            mh = _re.match(r"^\s*(.+?) (has|have|is|are) (a|an) ([A-Za-z]+) and (?:a |an )?([A-Za-z]+)\s*([.!?]?)\s*$", s_, _re.I)
            if mh and mh.group(4).lower() not in ("not",):
                _two.append(f"{mh.group(1)} {mh.group(2)} {mh.group(3)} {mh.group(4)}.")
                _two.append(f"{mh.group(1)} {mh.group(2)} {mh.group(3) if mh.group(3).lower() == 'an' else 'a'} {mh.group(5)}{mh.group(6) or '.'}")
                continue
            m2 = _re.match(r"^\s*((?:the |a |an |my |your )?[A-Za-z]+(?: [A-Za-z]+)?) (is|are) ([a-z]+) and ([a-z]+)\s*([.!?]?)\s*$",
                           s_, _re.I)
            if m2 and m2.group(3).lower() not in ("a", "an", "the", "not") and m2.group(4).lower() not in ("a", "an", "the", "not"):
                _two.append(f"{m2.group(1)} {m2.group(2)} {m2.group(3)}.")
                _two.append(f"{m2.group(1)} {m2.group(2)} {m2.group(4)}{m2.group(5) or '.'}")
            else:
                _two.append(s_)
        sentences_in = _two
        # A negated statement ("the bridge is not safe", "I do not like rain") cannot be stored as a positive
        # fact: the records hold no denials yet. Say so, rather than record the opposite.
        _neg = [x for x in sentences_in if _re.search(r"\b(not|never|no longer|cannot)\b|n't\b", x, _re.I)]
        if _neg and len(_neg) == len(sentences_in):
            return ("I cannot record a denial yet, so I will not write that down as fact. "
                    "Ask me what the records hold, and I will answer that.")
        sentences_in = [x for x in sentences_in if x not in _neg] or sentences_in
        learned = []
        contradictions = []
        if not hasattr(self, "player_claims"):
            self.player_claims = {}
        from .dialogue.ingest import extract_triples as _xt
        for s in sentences_in:
            # Track what the player claimed; a new object for the same subject and relation contradicts it.
            for tr in _xt(s, speaker="player", listener="Mira", antecedent=self.last_topic) or []:
                if tr.get("kind") != "eval":        # 'is tall' / 'is kind' can both hold; only places, jobs, materials clash
                    continue
                if str(tr.get("rel", "")).split("_")[0] in ("has", "have", "hold", "holds", "contain", "contains"):
                    continue                         # a city has a river AND a harbor: two possessions, not a clash
                key = (tr["a"], tr["rel"])
                if not hasattr(self, "all_claims"):
                    self.all_claims = {}
                _lst = self.all_claims.setdefault(key, [])
                if tr["b"] not in _lst:
                    _lst.append(tr["b"])
                old_b = self.player_claims.get(key)
                if old_b and old_b != tr["b"]:
                    contradictions.append((tr["a"], old_b, tr["b"]))
                self.player_claims[key] = tr["b"]
            learned.extend(ingest_text(self.aspace, s,
                                       speaker="player", listener="Mira",
                                       antecedent=self.last_topic))
        if learned:
            echoes = []
            for desc, atom in learned:
                self.learned_atoms.add(atom)
                self.tom.learn("Mira", f"(told) {desc}")
                echoes.append(atom)
            subj = self._subject_name(echoes[0])
            if subj:
                self.last_topic = subj
            ack = self.rng.choice([
                "I will add it to the records.",
                "Noted, and kept.",
                "The archive accepts it.",
            ])
            echo = self._best_sentence(echoes[0]) or desc
            echo = re.sub(r"(everyone knows|they say|the records hold that|the records say:)\s*", "", echo, flags=re.I)
            lead = self.rng.choice(["", "So — ", "Then this is true: "])
            if echo.startswith("You told me") or "told me" in echo:
                lead = ""                      # the echo already says it was told
            follow = self._novel_fact(player_text, exclude_learned=True)
            tail = ""
            # The follow-up must share a content word with what was just said; otherwise it reads as noise.
            said_words = {w for w in re.findall(r"[a-z]+", player_text.lower()) if len(w) > 3}
            if follow and not follow.startswith("You told me") and \
                    len(said_words & set(re.findall(r"[a-z]+", follow.lower()))) >= 2:
                tail = f" And this much I already knew — {follow[0].lower()}{follow[1:]}"
            if contradictions:
                a, old_b, new_b = contradictions[0]
                return (f"You said {old_b} before, and now {new_b}. I will keep both, "
                        f"and I cannot tell which is true from the records.")
            # Book knowledge leaks into echoes as a clause ("merchants, which are traders, trade in furs");
            # the player said only what was in their sentence, so echo that.
            echo = re.sub(r",\s*which (?:are|is) [a-z ]+?,", "", echo)
            # The realizer renders objects with 'the'; where the player said 'a river', echo 'a river'.
            for _m in re.finditer(r"\b(a|an)\s+([a-z]+)\b", " ".join(sentences_in), re.I):
                echo = re.sub(rf"\bthe {re.escape(_m.group(2).lower())}\b", f"{_m.group(1).lower()} {_m.group(2).lower()}",
                              echo, flags=re.I)
            return f"{lead}{echo[0].upper()}{echo[1:]} {ack}{tail}"

        answer = self._novel_fact(player_text)
        said = {w for w in re.findall(r"[a-z]+", player_text.lower()) if len(w) > 3}
        if answer and len({w for w in said if w in set(re.findall(r"[a-z]+", answer.lower()))}) < 2:
            answer = None                    # a fact that shares one word with the statement is not a reply to it
        if answer:
            backs = speech_acts.phrase("backchannels", limit=5)
            back = ""
            if backs and self.rng.random() < 0.35:
                back = backs[0].capitalize()
                back = {"I see": "I see. ", "Well": "Well — ", "Really": "Really? "}.get(back, "Aye. ")
            lead = self.rng.choice([
                "And there is more — ",
                "You speak of old things. Listen — ",
                "That brings something to mind. ",
                "",
            ])
            return (back + lead + answer).strip()

        if learned == [] and re.search(r"\b(i|my|me)\b", player_text, re.I):
            return ("I did not catch a fact in that. Say it more simply, as 'the X is Y', "
                    "and I will keep it.")
        return self.rng.choice([
            "I have told you all I can. Ask me something specific — the relic, the Veil, the city.",
            "My tongue is not a bell, to ring the same note. Ask of something else.",
            "The records are open to you, but I have said what I know.",
        ])


# ── CLI ─────────────────────────────────────────────────────────────────

def main():
    mir = MiraChat()

    print()
    print("  ╔═══════════════════════════════════════════╗")
    print("  ║  THE ARCHIVE — a conversation with Mira   ║")
    print("  ╚═══════════════════════════════════════════╝")
    print()
    print("  You step into the archive. A woman looks up from a")
    print("  half-copied manuscript — sharp eyes, ink-stained fingers.")
    print()
    print("  Ask her about the relic, the Veil, the city...  ('quit' to leave)")
    print()

    while True:
        try:
            line = input("  you: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Mira: Farewell.")
            break

        if not line:
            continue
        if line.lower() in ("quit", "exit", "q"):
            print("  Mira: Walk in wisdom.")
            break
        if line.lower() == "facts":
            known = [f for f in sorted(mir.tom.knowledge.get("Player", set()))
                     if not f.startswith("(heard)")]
            if known:
                print("\n  You know:")
                for f in known:
                    print(f"    - {f}")
            else:
                print("  You know nothing yet.")
            print()
            continue

        reply = mir.respond(line)
        print(f"  Mira: {reply}\n")


if __name__ == "__main__":
    main()
