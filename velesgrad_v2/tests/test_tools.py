import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from velesgrad_v2.cog.atomspace import AtomSpace, init_atomspace
from velesgrad_v2.tools.registry import ToolContext, execute_tool, REGISTRY
from velesgrad_v2.dialogue.tom import TheoryOfMind, DialogueManager
from velesgrad_v2.world.time import Clock
from velesgrad_v2.world.factions import FactionEngine
from velesgrad_v2.content.city import build_world


def make_ctx():
    world = build_world()
    asp = AtomSpace()
    init_atomspace(asp)
    tom = TheoryOfMind()
    dm = DialogueManager(tom)
    factions = FactionEngine()
    clock = Clock()
    ctx = ToolContext(world, asp, dm, factions, clock)
    world.locations["A"] = "square"
    world.locations["B"] = "square"
    return ctx


def test_all_tools_mutate():
    for name in ["move", "take", "investigate", "observe", "cast"]:
        ctx = make_ctx()
        arg = {"move": "square", "take": "coin",
               "investigate": "relic", "observe": None, "cast": "ward"}[name]
        if arg is None:
            res = REGISTRY[name](ctx, "A")
        else:
            res = execute_tool(ctx, name, "A", arg)
        assert res.applied == res.ok, f"{name}: applied must equal ok"
        assert len(list(ctx.aspace)) > 0, f"{name} should write to atomspace"
        assert len(ctx.chronicle) > 0, f"{name} should write to chronicle"


def test_converse_writes_chronicle():
    """Converse writes to chronicle even if ToM has nothing novel."""
    ctx = make_ctx()
    res = execute_tool(ctx, "converse", "A", "B")
    # converse may return "nothing novel" if ToM has no facts
    assert res.ok  # it's ok to have nothing novel
    assert len(ctx.chronicle) > 0


def test_cast_honest_applied():
    ctx = make_ctx()
    res = execute_tool(ctx, "cast", "Mira", "ward")
    assert res.applied == res.ok


def test_execute_no_leak():
    ctx = make_ctx()
    res = execute_tool(ctx, "nope", "A", "x")
    assert not res.ok
    assert "traceback" not in res.message.lower()


def test_converse_requires_copresence():
    ctx = make_ctx()
    ctx.world.locations["A"] = "square"
    ctx.world.locations["B"] = "tavern"
    res = execute_tool(ctx, "converse", "A", "B")
    assert not res.ok
    assert "not co-present" in res.message
