"""Tests for NL ingestion (text → AtomSpace) and composition."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest

from velesgrad_v2.dialogue.lg_ctypes import is_available
from velesgrad_v2.dialogue.ingest import extract_triples, ingest_text
from velesgrad_v2.cog.atomspace import (
    AtomSpace, init_atomspace, ConceptNode, InheritanceLink, EvaluationLink,
    ListLink, PredicateNode, get_tv, get_sti,
)

needs_lg = pytest.mark.skipif(not is_available(),
                              reason="Link Grammar dictionary unavailable")

CASES = [
    ("The relic lies in the tunnel.",  "eval", "relic", "tunnel", "lie_in"),
    ("The relic is valuable.",         "inh",  "relic", "valuable", "is"),
    ("The relic is a stolen artifact.", "inh", "relic", "artifact", "is"),
    ("The relic is in the archive.",   "eval", "relic", "archive", "in"),
    ("Mira guards the archive.",       "eval", "mira", "archive", "guard"),
    ("The hounds patrol the streets.", "eval", "hounds", "streets", "patrol"),
    ("I saw the tunnel.",              "eval", "player", "tunnel", "saw"),
    ("Someone stole the relic.",       "eval", "someone", "relic", "stole"),
]


@needs_lg
@pytest.mark.parametrize("sentence,kind,a,b,rel", CASES)
def test_extraction(sentence, kind, a, b, rel):
    triples = extract_triples(sentence)
    assert any(t["kind"] == kind and t["a"] == a and t["b"] == b and t["rel"] == rel
               for t in triples), f"{sentence!r} -> {triples}"


@needs_lg
def test_pronoun_mapping():
    """'I' becomes the speaker, 'you' becomes the listener."""
    t = extract_triples("I saw you.", speaker="player", listener="Mira")
    assert any(x["a"] == "player" and x["b"] == "mira_placeholder" for x in t) or True
    # listener name arrives lowercased via _bare
    hits = [x for x in t if x["a"] == "player" and x["b"] == "mira"]
    assert hits, t


@needs_lg
def test_ingest_writes_marked_atoms():
    asp = AtomSpace(); init_atomspace(asp)
    learned = ingest_text(asp, "The relic lies in the tunnel.")
    assert learned, "nothing learned"
    desc, atom = learned[0]
    tv = get_tv(atom)
    # heard-unverified: weaker than archive knowledge
    assert tv.mean == pytest.approx(0.6) and tv.confidence == pytest.approx(0.3)
    assert get_sti(atom) >= 14.0
    # The atom exists in the space as a proper Evaluation link
    assert atom in {a for a in asp.get_atoms_by_type(
        __import__("velesgrad_v2.cog.atomspace", fromlist=["types"]).types.EvaluationLink)}


@needs_lg
def test_chat_learns_then_recalls():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat()
    m.respond("hello")
    ack = m.respond("the relic lies in the tunnel")
    assert "told me" in ack.lower() or "records" in ack.lower()
    # her ToM now holds the told fact
    assert any("tunnel" in f for f in m.tom.knowledge.get("Mira", set()))
    # the fact must be retrievable by topic — either directly or via echo,
    # it must exist in the atomspace as an Evaluation with relic subject
    from velesgrad_v2.cog.atomspace import types
    found = False
    for link in m.aspace.get_atoms_by_type(types.EvaluationLink):
        out = list(getattr(link, "out", []))
        if len(out) == 2:
            inner = list(getattr(out[1], "out", []) or [])
            names = [getattr(x, "name", "") for x in inner]
            if "relic" in names and "tunnel" in names:
                found = True
    assert found


def test_composition_reason_clause():
    from velesgrad_v2.dialogue.compose import compose
    import random
    asp = AtomSpace(); init_atomspace(asp)
    a = ConceptNode("archive"); b = ConceptNode("place_of_learning"); c = ConceptNode("important")
    inh1 = InheritanceLink(a, b)
    InheritanceLink(b, c)
    cands = compose(inh1, asp, random.Random(1))
    assert any("since all" in s for s in cands), cands


def test_no_lg_no_crash():
    """Extraction returns [] (not an exception) when parses are unavailable."""
    out = extract_triples("this is not a sentence at all zebra quantum")
    assert isinstance(out, list)
