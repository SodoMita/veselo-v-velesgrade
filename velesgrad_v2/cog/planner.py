# Velesgrad v2 – Multi-step planner
# Plans persist across turns and are executed step by step.

from dataclasses import dataclass, field

Action = tuple[str, str | None]

@dataclass
class Plan:
    goal: str
    steps: list[Action] = field(default_factory=list)
    cursor: int = 0

    @property
    def current(self) -> Action:
        if self.cursor < len(self.steps):
            return self.steps[self.cursor]
        return ("wait", None)

    def advance(self):
        if self.cursor < len(self.steps):
            self.cursor += 1

    def done(self) -> bool:
        return self.cursor >= len(self.steps)

    def to_dict(self):
        return {"goal": self.goal, "steps": self.steps, "cursor": self.cursor}

    @staticmethod
    def from_dict(d):
        return Plan(d["goal"], [tuple(s) for s in d["steps"]], d["cursor"])


# ── Planning Knowledge ──────────────────────────────────────────────────
# Maps goals to action sequences. Honest lookup table, not "generative."

PLAN_LIBRARY: dict[str, list[Action]] = {
    "investigate_relic": [("move", "archive"), ("investigate", "relic"), ("observe", None)],
    "talk_to_hound": [("move", "square"), ("converse", "hound")],
    "rest": [("wait", None)],
    "explore": [("move", None), ("observe", None)],
    "find_food": [("move", "market"), ("take", "bread")],
    "pray": [("move", "sanctum"), ("observe", None)],
    "patrol": [("move", "square"), ("move", "market"), ("move", "tavern"), ("observe", None)],
    "gather_info": [("move", "tavern"), ("converse", None), ("move", "archive"), ("investigate", None)],
}


class Planner:
    def __init__(self, library: dict[str, list[Action]] | None = None):
        self.library = library or PLAN_LIBRARY

    def plan_for(self, goal: str, world_state: dict | None = None) -> Plan:
        """Create a plan for the given goal. Honest lookup, not generation."""
        steps = self.library.get(goal, [("observe", None)])
        return Plan(goal, list(steps))

    def revise_plan(self, plan: Plan, feedback: str) -> Plan:
        """Adjust plan based on feedback. Simple: restart if stuck."""
        if feedback == "blocked":
            # try alternative path
            return Plan(plan.goal, [("observe", None), ("wait", None)])
        if feedback == "satisfied":
            return Plan(plan.goal, [])  # done
        return plan
