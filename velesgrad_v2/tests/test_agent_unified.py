import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from velesgrad_v2.cog.atomspace import AtomSpace, init_atomspace, ConceptNode, get_sti
from velesgrad_v2.cog.ecan import ECAN
from velesgrad_v2.cog.pln import Reasoner
from velesgrad_v2.cog.psi import PsiModule
from velesgrad_v2.agents.agent import Agent, PlayerAgent, NPCAgent


def _make_asp():
    asp = AtomSpace()
    init_atomspace(asp)
    return asp


def make_agent(name, cls=Agent):
    asp = _make_asp()
    ecan = ECAN(asp)
    r = Reasoner(asp)
    psi = PsiModule()
    if cls == NPCAgent:
        return cls(name, faction="test", home_room="square", atomspace=asp, ecan=ecan, reasoner=r, psi=psi)
    return cls(name, atomspace=asp, ecan=ecan, reasoner=r, psi=psi)


def test_player_is_agent():
    npc = make_agent("Mira", NPCAgent)
    player = make_agent("Player", PlayerAgent)
    assert hasattr(player, "perceive")
    assert hasattr(player, "deliberate")
    assert hasattr(player, "act")
    assert hasattr(npc, "perceive_text")


def test_perceive_writes_atomspace():
    a = make_agent("Test")
    a.perceive({"fact": "the bell rang"})
    found = [at for at in a.aspace if at.name == "the bell rang"]
    assert len(found) > 0


def test_plan_persistence():
    a = make_agent("Test")
    a.plan = [("move", "archive"), ("investigate", "relic")]
    saved = a.to_dict()
    a2 = make_agent("Test")
    a2.load_dict(saved)
    assert a2.plan == [("move", "archive"), ("investigate", "relic")]


def test_learn_updates_values():
    a = make_agent("Test")
    a.learn("move", 0.8)
    a.learn("move", 0.6)
    assert a.action_counts["move"] == 2
    assert abs(a.action_values["move"] - 0.7) < 0.01


def test_deliberate_uses_plan():
    a = make_agent("Test")
    a.plan = [("move", "archive"), ("observe", None)]
    a.plan_cursor = 0
    action = a.deliberate()
    assert action == ("move", "archive")
    action2 = a.deliberate()
    assert action2 == ("observe", None)


def test_salient_facts():
    a = make_agent("Test")
    a.perceive({"fact": "hot topic"})
    # Set high STI on the concept
    for at in a.aspace:
        if at.name == "hot topic":
            from velesgrad_v2.cog.atomspace import set_sti
            set_sti(at, 100.0)
    facts = a.get_salient_facts(3)
    assert "hot topic" in facts
