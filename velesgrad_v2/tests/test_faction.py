import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from velesgrad_v2.world.factions import FactionEngine, BeliefStore, Faction, FACTION_SIGNALS
from velesgrad_v2.cog.atomspace import AtomSpace, init_atomspace
from velesgrad_v2.cog.pln import Reasoner


def test_faction_signals_data_driven():
    fe = FactionEngine()
    from velesgrad_v2.world.factions import FactionSignal
    assert all(isinstance(s, FactionSignal) for s in FACTION_SIGNALS)


def test_once_per_turn():
    fe = FactionEngine()
    r1 = fe.handle("cast")
    r2 = fe.handle("cast")
    assert len(r2) == 0
    fe.end_turn()
    r3 = fe.handle("cast")
    assert len(r3) > 0


def test_disposition_clamping():
    fe = FactionEngine()
    for _ in range(100):
        fe.handle("cast")
        fe.end_turn()
    for f in fe.factions.values():
        assert -1.0 <= f.disposition <= 1.0


def test_belief_index_per_atomspace():
    asp1 = AtomSpace()
    init_atomspace(asp1)
    asp2 = AtomSpace()
    init_atomspace(asp2)
    r1 = Reasoner(asp1)
    r2 = Reasoner(asp2)
    b1 = BeliefStore(asp1, r1)
    b2 = BeliefStore(asp2, r2)
    b1.revise_belief("Mira", "knows_relic", 0.9)
    b2.revise_belief("Mira", "knows_relic", 0.2)
    assert b1 is not b2
