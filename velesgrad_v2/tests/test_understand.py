"""Tests for dialogue/understand.py: question frames from the Link Grammar parse,
answered from AtomSpace facts."""
import pytest

from velesgrad_v2.dialogue.lg_ctypes import is_available

needs_lg = pytest.mark.skipif(not is_available(), reason="Link Grammar not available")


@needs_lg
@pytest.mark.parametrize("q,wh,slot,copula", [
    ("who guards the city?", "who", "subject", False),
    ("what is the veil?", "what", "complement", True),
    ("what does the archive hold?", "what", "object", False),
    ("where was the relic kept?", "where", "place", False),
])
def test_wh_frames(q, wh, slot, copula):
    from velesgrad_v2.dialogue.understand import build_frame
    f = build_frame(q)
    assert f is not None
    assert f.kind == "wh" and f.wh == wh and f.wh_slot == slot and f.copula == copula


@needs_lg
def test_yes_no_frame():
    from velesgrad_v2.dialogue.understand import build_frame
    f = build_frame("is the relic valuable?")
    assert f.kind == "yn" and f.subject == "relic" and f.adj == "valuable"


@needs_lg
def test_understanding_answers_from_facts():
    from velesgrad_v2.chat import MiraChat
    from velesgrad_v2.dialogue.understand import understand
    m = MiraChat("seed", knowledge="books")
    a = understand(m.aspace, "what is the veil?")
    assert a is not None and "veil" in a.text.lower() and a.text.endswith(".")
    yn = understand(m.aspace, "is the relic valuable?")
    assert yn is not None and yn.text.startswith("Yes")
    assert yn.text.count(".") == 1


@needs_lg
def test_statements_and_unknowns_are_not_handled():
    from velesgrad_v2.chat import MiraChat
    from velesgrad_v2.dialogue.understand import understand
    m = MiraChat("seed", knowledge="books")
    assert understand(m.aspace, "The bell signals danger.") is None
    assert understand(m.aspace, "who stole the moon?") is None
