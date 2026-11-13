# Velesgrad v2 – Action tools registry
# All tools operate on the REAL OpenCog AtomSpace.

from dataclasses import dataclass
from typing import Callable, Dict
from ..cog.atomspace import AtomSpace, ConceptNode, EvaluationLink, tv_from_count, get_tv, set_tv


@dataclass
class ToolResult:
    ok: bool
    message: str
    applied: bool
    data: dict | None = None


class ToolContext:
    def __init__(self, world, aspace, dialogue, factions, clock):
        self.world = world
        self.aspace = aspace
        self.dialogue = dialogue
        self.factions = factions
        self.clock = clock
        self.chronicle: list[str] = []
        self._veil = None


def t_move(ctx: ToolContext, agent: str, target_room: str) -> ToolResult:
    if target_room not in ctx.world.rooms:
        return ToolResult(False, f"no such room: {target_room}", False)
    ok = ctx.world.move(agent, target_room)
    if ok:
        n = ConceptNode(f"{agent}_at_{target_room}")
        set_tv(n, tv_from_count(1.0, 5.0))
        ctx.chronicle.append(f"{agent} moved to {target_room}")
    return ToolResult(ok, f"moved to {target_room}" if ok else "move failed", ok)


def t_take(ctx: ToolContext, agent: str, item: str) -> ToolResult:
    n = ConceptNode(f"{agent}_has_{item}")
    set_tv(n, tv_from_count(1.0, 5.0))
    ctx.chronicle.append(f"{agent} took {item}")
    return ToolResult(True, f"took {item}", True, {"item": item})


def t_converse(ctx: ToolContext, agent: str, target: str) -> ToolResult:
    if not ctx.world.co_present(agent, target):
        return ToolResult(False, "not co-present", False)
    from ..dialogue.surface import TemplateRealizer
    realizer = TemplateRealizer(ctx.aspace)
    facts = realizer.salient_concepts(agent)
    if not facts:
        facts = [f"{agent} greets {target}"]
    u = ctx.dialogue.speak(agent, target, facts, ctx.clock.tick_n)
    if u:
        ctx.chronicle.append(f"{agent} -> {target}: {u.text}")
        return ToolResult(True, u.text, True, {"act": u.act.value})
    return ToolResult(True, "(nothing novel to say)", True)


def t_investigate(ctx: ToolContext, agent: str, target: str) -> ToolResult:
    room = ctx.world.locations.get(agent, "")
    n = ConceptNode(f"investigated_{target}_in_{room}")
    set_tv(n, tv_from_count(0.8, 3.0))
    ctx.chronicle.append(f"{agent} investigated {target} in {room}")
    return ToolResult(True, f"found clues about {target}", True)


def t_observe(ctx: ToolContext, agent: str, target: str = "") -> ToolResult:
    room = ctx.world.locations.get(agent, "")
    n = ConceptNode(f"observed_{room}_t{ctx.clock.tick_n}")
    set_tv(n, tv_from_count(0.7, 2.0))
    ctx.chronicle.append(f"{agent} observed {room}")
    return ToolResult(True, f"observed {room}", True)


def t_cast(ctx: ToolContext, agent: str, spell: str) -> ToolResult:
    from ..world.magic import attempt_cast, Veil
    if ctx._veil is None:
        ctx._veil = Veil()
    import random
    rng = random.Random(ctx.clock.tick_n + hash(agent))
    success, msg, cost = attempt_cast(spell, ctx._veil, rng)
    ctx.factions.handle("cast", agent)
    n = ConceptNode(f"cast_{spell}_by_{agent}_t{ctx.clock.tick_n}")
    set_tv(n, tv_from_count(1.0 if success else 0.3, 3.0))
    ctx.chronicle.append(f"{agent} cast {spell}: {msg}")
    return ToolResult(success, msg, applied=success, data={"cost": cost})


REGISTRY: Dict[str, Callable] = {
    "move": t_move,
    "take": t_take,
    "converse": t_converse,
    "investigate": t_investigate,
    "observe": t_observe,
    "cast": t_cast,
}


def execute_tool(ctx: ToolContext, name: str, agent: str, arg: str | None = None) -> ToolResult:
    fn = REGISTRY.get(name)
    if not fn:
        return ToolResult(False, f"unknown tool: {name}", False)
    try:
        if arg is None and name == "observe":
            return fn(ctx, agent)
        if arg is None:
            return ToolResult(False, "missing argument", False)
        return fn(ctx, agent, arg)
    except Exception as e:
        return ToolResult(False, "tool execution failed", False, {"error_type": type(e).__name__})
