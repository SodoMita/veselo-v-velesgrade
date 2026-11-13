import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
import json

from velesgrad_v2.engine import Engine


def test_save_load_roundtrip():
    e1 = Engine(seed=1)
    for _ in range(5):
        e1.turn()
    state = e1.save_state()
    json.dumps(state)
    e2 = Engine(seed=99)
    e2.load_state(state)
    assert e2.clock.hour == e1.clock.hour
    assert e2.world.locations == e1.world.locations


def test_conversation_no_repeat():
    e = Engine(seed=42)
    for _ in range(30):
        e.turn()
    mem = e.dialogue.memory.history
    seen = set()
    for u in mem:
        key = (u.speaker, u.listener, tuple(u.facts_conveyed))
        assert key not in seen, "ToM should prevent repeat spam"
        seen.add(key)


def test_atomspace_grows():
    e = Engine(seed=42)
    initial = len(list(e.aspace))
    for _ in range(20):
        e.turn()
    assert len(list(e.aspace)) > initial


def test_multiple_seeds_differ():
    e1 = Engine(seed=1)
    e2 = Engine(seed=2)
    for _ in range(10):
        e1.turn()
        e2.turn()
    assert e1.clock.tick_n == e2.clock.tick_n
