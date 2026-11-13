# Velesgrad v2 – Unified agent loop
# All agents operate on the REAL OpenCog AtomSpace.

from ..cog.atomspace import (
    AtomSpace, TruthValue, ConceptNode, EvaluationLink,
    tv_from_count, get_sti, set_sti, add_sti, get_tv, set_tv,
    _ensure_keys,
)
from ..cog.ecan import ECAN
from ..cog.pln import Reasoner
from ..cog.psi import PsiModule, Goal
from ..cog.planner import Plan, Planner
from ..dialogue.tom import TheoryOfMind, DialogueManager


class Agent:
    def __init__(self, name: str, atomspace: AtomSpace, ecan: ECAN,
                 reasoner: Reasoner, psi: PsiModule, llm=None):
        self.name = name
        self.aspace = atomspace
        self.ecan = ecan
        self.reasoner = reasoner
        self.psi = psi
        self.llm = llm
        self.room: str = "square"
        self.plan: list[tuple[str, str | None]] = []
        self.plan_cursor: int = 0
        self.action_values: dict[str, float] = {}
        self.action_counts: dict[str, int] = {}
        # Create self-concept in the real AtomSpace
        self._self_node = ConceptNode(name)
        _ensure_keys(atomspace)

    def perceive(self, world_event: dict):
        """Write perceived facts to the real AtomSpace."""
        if "fact" in world_event:
            fact = world_event["fact"]
            node = ConceptNode(fact)
            count = self.action_counts.get(fact, 0) + 1
            self.action_counts[fact] = count
            strength = min(0.95, 0.5 + count * 0.05)
            set_tv(node, tv_from_count(strength, float(count)))
            self.ecan.stimulate(node, 5.0)

    def perceive_text(self, text: str, speaker: str):
        """Record heard text in the real AtomSpace."""
        node = ConceptNode(f"heard:{speaker}:{text[:60]}")
        set_tv(node, tv_from_count(0.8, 3.0))
        self.ecan.stimulate(node, 3.0)
        return node

    def learn(self, action: str, outcome: float) -> float:
        n = self.action_counts.get(action, 0)
        v = self.action_values.get(action, 0.5)
        v = (v * n + outcome) / (n + 1)
        self.action_values[action] = v
        self.action_counts[action] = n + 1
        return v

    def speak(self, text: str) -> str:
        if self.llm and hasattr(self.llm, "is_available"):
            if not self.llm.is_available():
                return text
            try:
                return self.llm.generate(text, max_tokens=64)
            except Exception:
                return text
        return text

    def get_salient_facts(self, top_k: int = 5) -> list[str]:
        """Get most salient ConceptNodes by STI from the real AtomSpace."""
        atoms = list(self.aspace.get_atoms_by_type(types.ConceptNode))
        atoms.sort(key=lambda a: get_sti(a), reverse=True)
        return [a.name for a in atoms[:top_k]]

    def deliberate(self, dialogue_mgr=None) -> tuple[str, str | None]:
        if self.plan_cursor < len(self.plan):
            action = self.plan[self.plan_cursor]
            self.plan_cursor += 1
            return action
        if self.psi.goals:
            goal = self.psi.select_goal()
            if goal:
                return goal.action
        return ("observe", None)

    def act(self, action, world) -> str:
        verb, target = action
        return f"{self.name} {verb} {target or ''}".strip()

    def to_dict(self) -> dict:
        return {
            "name": self.name, "room": self.room,
            "plan": self.plan, "plan_cursor": self.plan_cursor,
            "action_values": self.action_values, "action_counts": self.action_counts,
        }

    def load_dict(self, d: dict):
        self.room = d.get("room", "square")
        self.plan = [tuple(s) for s in d.get("plan", [])]
        self.plan_cursor = d.get("plan_cursor", 0)
        self.action_values = d.get("action_values", {})
        self.action_counts = d.get("action_counts", {})


# Need types for get_salient_facts
from ..cog.atomspace import types


class NPCAgent(Agent):
    def __init__(self, name: str, faction: str, home_room: str, **kwargs):
        super().__init__(name, **kwargs)
        self.faction = faction
        self.home_room = home_room
        self.room = home_room


class PlayerAgent(Agent):
    pass
