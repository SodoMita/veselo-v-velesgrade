import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from velesgrad_v2.cog.atomspace import AtomSpace, TruthValue, init_atomspace, types, ConceptNode, InheritanceLink, ImplicationLink, get_tv, set_tv
from velesgrad_v2.cog.pln import deduction_tv, modus_ponens_tv, and_tv, or_tv, not_tv, Reasoner, BeliefStore


def _make_asp():
    asp = AtomSpace()
    init_atomspace(asp)
    return asp


def test_deduction_formula():
    ab = TruthValue(0.8, 0.111)
    bc = TruthValue(0.7, 0.111)
    ac = deduction_tv(ab, bc)
    assert abs(ac.mean - 0.56) < 1e-6


def test_deduction_on_atomspace():
    asp = _make_asp()
    r = Reasoner(asp)
    a = ConceptNode("A")
    b = ConceptNode("B")
    c = ConceptNode("C")
    ab = InheritanceLink(a, b)
    set_tv(ab, TruthValue(0.8, 0.111))
    bc = InheritanceLink(b, c)
    set_tv(bc, TruthValue(0.7, 0.111))
    derived = r.step()
    assert len(derived) >= 1
    assert derived[0].rule == "deduction"
    assert abs(derived[0].tv.mean - 0.56) < 0.01


def test_mp_prior_matters():
    p = TruthValue(0.9, 0.1)
    impl = TruthValue(0.8, 0.1)
    prior_low = TruthValue(0.2, 0.5)
    prior_high = TruthValue(0.8, 0.5)
    q_low = modus_ponens_tv(p, impl, prior_low)
    q_high = modus_ponens_tv(p, impl, prior_high)
    assert q_low.mean != q_high.mean


def test_modus_ponens_on_atomspace():
    asp = _make_asp()
    r = Reasoner(asp)
    p = ConceptNode("theft")
    q = ConceptNode("alert")
    impl = ImplicationLink(p, q)
    set_tv(p, TruthValue(0.9, 0.1))
    set_tv(impl, TruthValue(0.8, 0.1))
    derived = r.step()
    mp_results = [d for d in derived if d.rule == "modus_ponens"]
    assert len(mp_results) >= 1


def test_tms_invalidation():
    asp = _make_asp()
    r = Reasoner(asp)
    a = ConceptNode("A")
    b = ConceptNode("B")
    r.record_dependency(b, [a])
    set_tv(b, TruthValue(0.9, 0.38))
    invalidated = r.invalidate(a)
    assert b in invalidated
    assert get_tv(b).confidence < 0.38


def test_boolean_ops():
    a = TruthValue(0.8, 0.9)
    b = TruthValue(0.6, 0.9)
    assert abs(and_tv(a, b).mean - 0.48) < 1e-6
    assert abs(or_tv(a, b).mean - 0.92) < 1e-6
    assert abs(not_tv(a).mean - 0.2) < 1e-6


def test_belief_store_revise():
    asp = _make_asp()
    r = Reasoner(asp)
    bs = BeliefStore(asp, r)
    b1 = bs.revise_belief("Mira", "knows_relic", 0.9)
    assert get_tv(b1).mean > 0.5
