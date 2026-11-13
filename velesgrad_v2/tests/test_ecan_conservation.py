import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from velesgrad_v2.cog.atomspace import AtomSpace, init_atomspace, ConceptNode, get_sti, set_sti, get_lti, set_lti
from velesgrad_v2.cog.ecan import ECAN, ECANConfig


def _make_asp():
    asp = AtomSpace()
    init_atomspace(asp)
    return asp


def test_sti_conservation():
    asp = _make_asp()
    a = ConceptNode("A")
    b = ConceptNode("B")
    set_sti(a, 100.0)
    set_sti(b, 0.0)
    ecan = ECAN(asp, ECANConfig(spread_fraction=0.2))
    total_before = get_sti(a) + get_sti(b)
    ecan.spread([(a, b, 1.0)])
    total_after = get_sti(a) + get_sti(b)
    assert abs(total_before - total_after) < 1e-6, "STI must be conserved"
    assert get_sti(a) < 100.0
    assert get_sti(b) > 0.0


def test_bank_balances():
    asp = _make_asp()
    for i in range(5):
        ConceptNode(f"N{i}")
    ecan = ECAN(asp, ECANConfig(rent_per_atom=0.01, focus_wage=0.05, focus_capacity=1))
    for _ in range(10):
        ecan.rent_collect_wages(ecan.focus_atoms())
    assert abs(ecan.sti_bank) < 1.0


def test_focus_atoms():
    asp = _make_asp()
    nodes = []
    for i in range(10):
        n = ConceptNode(f"N{i}")
        set_sti(n, float(i * 10))
        nodes.append(n)
    ecan = ECAN(asp)
    focus = ecan.focus_atoms(3)
    assert len(focus) == 3
    assert get_sti(focus[0]) >= get_sti(focus[1])


def test_stimulate():
    asp = _make_asp()
    a = ConceptNode("A")
    ecan = ECAN(asp)
    ecan.stimulate(a, 50.0)
    assert get_sti(a) == 50.0


def test_forget():
    asp = _make_asp()
    a = ConceptNode("A")
    set_lti(a, -48.0)
    ecan = ECAN(asp, ECANConfig(forget_lti_rate=2.0, min_lti=-50.0))
    evicted = ecan.forget_tick()
    assert a in evicted
