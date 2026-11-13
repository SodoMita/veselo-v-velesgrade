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

GREETINGS = ("hello", "hi", "hey", "greetings", "good day", "privet", "zdravstvuy")
FAREWELLS = ("bye", "farewell", "goodbye", "dosvidaniya", "good night", "see you")

QUESTION_WORDS = ("what", "who", "where", "when", "why", "how", "which", "tell me about",
                  "do you know", "can you tell", "what about")


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
            return topic
        return re.sub(r"\b(it|them|that|those|they)\b", repl, text,
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
            return [a for a in atoms if self._relation_of(a) in self._SPATIAL_RELS] + \
                   [a for a in atoms if self._relation_of(a) not in self._SPATIAL_RELS]
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
        best = None
        for atom in self.aspace:
            t = getattr(atom, "type_name", "")
            if not any(x in t for x in ("Inheritance", "Evaluation")):
                continue
            subj = self._subject_name(atom).lower()
            obj = self._object_name(atom).lower()
            rel = self._relation_of(atom).lower().replace("_", " ")
            hay = f"{subj} {obj} {rel}"
            score = sum(1 for w in words if w in hay)
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
        self.turn += 1
        act = self.dialogue.recognize_act(player_text).value  # data-driven act
        self.tom.learn("Player", f"(heard) {player_text[:60]}")

        if self.farewelled:
            return "Until next time."

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
            topic = self._novel_fact()
            base = self.rng.choice(["Again, well met.", "You return. Good.", "The bells marked your coming."])
            return f"{base} {topic}" if topic else base

        # ── QUESTION / COMMAND (requests for knowledge) ─────────────────
        if act in ("question", "command"):
            resolved = self._pronoun_resolve(player_text)
            low_q = resolved.lower()
            # Questions about Mira herself answer from her own atoms
            if re.search(r"\b(you|your)\b", low_q) or low_q.startswith(("who are", "what are")):
                self_answer = self._answer_self(low_q)
                if self_answer:
                    return self_answer
            # Understanding first: parse the question (Link Grammar) into a frame and
            # answer from a matching AtomSpace fact. Falls back to keyword lookup below.
            try:
                from .dialogue.understand import understand as _understand
                ua = _understand(self.aspace, resolved)
            except Exception:
                ua = None
            if ua is not None:
                return ua.text
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
            answer = None
            for atom in atoms:
                if atom in self.said_atoms:
                    continue
                if "Implication" in getattr(atom, "type_name", ""):
                    t = self._implication_sentence(atom)
                else:
                    t = self._best_sentence(atom)
                if t and len(t.split()) >= 3:
                    self.said_atoms.add(atom)
                    subj = self._subject_name(atom) or self._object_name(atom)
                    if subj:
                        self.last_topic = subj
                    answer = t
                    break
            if answer:
                lead = self.rng.choice(["", "I can tell you this — ", "The records say: ", "That much I know. "])
                return (lead + answer).strip()
            fallback = self._novel_fact()
            if fallback:
                return f"I know little of that. What I do know — {fallback.lower()}"
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
        learned = []
        for s in sentences_in:
            learned.extend(ingest_text(self.aspace, s,
                                       speaker="player", listener="Mira"))
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
            lead = self.rng.choice(["", "So — ", "Then this is true: "])
            follow = self._novel_fact(player_text, exclude_learned=True)
            tail = ""
            if follow and not follow.startswith("You told me"):
                tail = f" And this much I already knew — {follow[0].lower()}{follow[1:]}"
            return f"{lead}{echo[0].upper()}{echo[1:]} {ack}{tail}"

        answer = self._novel_fact(player_text)
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
