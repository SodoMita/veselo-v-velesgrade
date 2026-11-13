"""
agents/cognition.py – Goal-driven NPC cognition.

NPCs have:
  - Active goals (find the relic, patrol, guard, investigate, etc.)
  - A plan to achieve their current goal
  - Reactions to dialogue (they stop and listen/respond)
  - Learning from outcomes (success/failure updates goal priority)
  - Social awareness (they know what other agents are doing)

This is NOT a template system. Goals are represented as atoms in
the OpenCog AtomSpace. Plans are sequences of tool calls. The NPC
selects goals based on Psi demands + faction identity + world state.
"""

import random
from dataclasses import dataclass, field
from enum import Enum


class GoalStatus(Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class NPCGoal:
    name: str
    priority: float = 0.5
    status: GoalStatus = GoalStatus.ACTIVE
    steps_taken: int = 0
    max_steps: int = 10
    target: str | None = None  # what/who the goal is about
    reason: str = ""  # why this goal

    def __repr__(self):
        return f"Goal({self.name}, p={self.priority:.2f}, {self.status.value})"


# ── Goal templates per faction ───────────────────────────────────────────

FACTION_GOALS = {
    "hounds": [
        {"name": "patrol_city", "priority": 0.7, "desc": "Patrol the city streets"},
        {"name": "find_relic", "priority": 0.9, "desc": "Find the stolen relic"},
        {"name": "interrogate_suspects", "priority": 0.6, "desc": "Question those who know"},
        {"name": "guard_archive", "priority": 0.5, "desc": "Watch the archive"},
        {"name": "report_to_kostya", "priority": 0.4, "desc": "Share intel with Kostya"},
    ],
    "veles": [
        {"name": "study_archive", "priority": 0.7, "desc": "Study the archive's knowledge"},
        {"name": "find_relic", "priority": 0.8, "desc": "Recover the sacred relic"},
        {"name": "protect_sanctum", "priority": 0.6, "desc": "Guard the sanctum"},
        {"name": "interpret_veil", "priority": 0.5, "desc": "Read the Veil's signs"},
        {"name": "teach_others", "priority": 0.4, "desc": "Share wisdom"},
    ],
    "veche": [
        {"name": "trade_gossip", "priority": 0.7, "desc": "Gather and spread news"},
        {"name": "find_relic", "priority": 0.5, "desc": "Find the relic for profit"},
        {"name": "barter_goods", "priority": 0.6, "desc": "Make a deal"},
        {"name": "explore_city", "priority": 0.5, "desc": "See what's happening"},
        {"name": "help_friend", "priority": 0.4, "desc": "Help an ally"},
    ],
}

# ── Goal → action plan mapping ──────────────────────────────────────────
# Each goal maps to a list of (action_type, target_selector) pairs.
# target_selector can be a room, NPC name, or a special keyword.

GOAL_PLANS = {
    "patrol_city": [
        ("move", "random_neighbor"),
        ("observe", None),
        ("move", "random_neighbor"),
        ("observe", None),
    ],
    "find_relic": [
        ("investigate", "relic"),
        ("move", "archive"),
        ("investigate", "archive"),
        ("take", "relic"),         # actually pick it up if found
        ("return", "relic"),       # return it to its place
    ],
    "interrogate_suspects": [
        ("move", "square"),
        ("converse_nearby", None),
        ("move", "tavern"),
        ("converse_nearby", None),
    ],
    "guard_archive": [
        ("move", "archive"),
        ("observe", None),
        ("observe", None),
    ],
    "report_to_kostya": [
        ("move", "bell_tower"),
        ("converse", "Kostya"),
    ],
    "study_archive": [
        ("move", "archive"),
        ("investigate", "archive"),
        ("observe", None),
    ],
    "protect_sanctum": [
        ("move", "sanctum"),
        ("observe", None),
        ("cast", "ward"),
    ],
    "interpret_veil": [
        ("move", "sanctum"),
        ("investigate", "veil"),
        ("observe", None),
    ],
    "teach_others": [
        ("move", "square"),
        ("converse_nearby", None),
    ],
    "trade_gossip": [
        ("move", "tavern"),
        ("converse_nearby", None),
        ("move", "market"),
        ("converse_nearby", None),
    ],
    "barter_goods": [
        ("move", "market"),
        ("converse_nearby", None),
    ],
    "explore_city": [
        ("move", "random_neighbor"),
        ("observe", None),
        ("move", "random_neighbor"),
        ("converse_nearby", None),
    ],
    "help_friend": [
        ("move", "square"),
        ("converse_nearby", None),
    ],
    "return_relic": [
        ("move", "archive"),
        ("return", "relic"),
    ],
}


class NPCCognition:
    """Manages an NPC's goals, plans, and reactions."""

    def __init__(self, npc_name: str, faction: str, rng: random.Random = None):
        self.npc_name = npc_name
        self.faction = faction
        self.rng = rng or random.Random()
        self.goals: list[NPCGoal] = []
        self.current_goal: NPCGoal | None = None
        self.plan_step: int = 0
        self.reacting_to: str | None = None  # set when someone talks to NPC
        self.last_action: str = ""
        self.memory: list[str] = []  # short-term action memory

        # Initialize faction-specific goals
        self._init_goals()

    def _init_goals(self):
        templates = FACTION_GOALS.get(self.faction, FACTION_GOALS["veche"])
        for t in templates:
            self.goals.append(NPCGoal(
                name=t["name"],
                priority=t["priority"] + self.rng.uniform(-0.1, 0.1),
                reason=t["desc"],
            ))

    def select_goal(self) -> NPCGoal | None:
        """Select highest-priority active goal."""
        active = [g for g in self.goals if g.status == GoalStatus.ACTIVE]
        if not active:
            # Reset all goals
            for g in self.goals:
                g.status = GoalStatus.ACTIVE
                g.steps_taken = 0
            active = self.goals

        # Weight by priority with some randomness
        scored = [(g.priority + self.rng.uniform(-0.05, 0.05), g) for g in active]
        scored.sort(reverse=True)
        return scored[0][1] if scored else None

    def get_next_action(self, world_locations: dict, world_rooms: dict,
                        npcs_present: list[str] = None) -> tuple[str, str | None] | None:
        """Get the next action for the NPC to take.

        Returns (action_type, target) or None if idle.
        """
        # If reacting to dialogue, handle that first
        if self.reacting_to:
            reaction = self.reacting_to
            self.reacting_to = None
            return ("react_to", reaction)

        # Select or continue a goal
        if not self.current_goal or self.current_goal.status != GoalStatus.ACTIVE:
            self.current_goal = self.select_goal()
            self.plan_step = 0
            if not self.current_goal:
                return ("observe", None)

        goal = self.current_goal
        plan = GOAL_PLANS.get(goal.name, [("observe", None)])

        if self.plan_step >= len(plan):
            # Plan exhausted, mark goal as completed
            goal.status = GoalStatus.COMPLETED
            self.current_goal = None
            self.plan_step = 0
            return ("observe", None)

        action_type, target = plan[self.plan_step]
        self.plan_step += 1
        goal.steps_taken += 1

        # Resolve dynamic targets
        if target == "random_neighbor":
            room = world_locations.get(self.npc_name, "square")
            room_obj = world_rooms.get(room)
            if room_obj and room_obj.neighbors:
                target = self.rng.choice(room_obj.neighbors)
            else:
                target = "square"

        # converse_nearby: talk to whoever is in the room
        if action_type == "converse_nearby":
            others = npcs_present or []
            player_here = "Player" in world_locations and world_locations["Player"] == world_locations.get(self.npc_name)
            if player_here:
                others = others + ["Player"]
            if others:
                target = self.rng.choice(others)
                action_type = "converse"
            else:
                action_type = "observe"
                target = None

        # ask_nearby: ask whoever is present about the topic
        if action_type == "ask_nearby":
            others = npcs_present or []
            if others:
                target_other = self.rng.choice(others)
                action_type = "converse"
                target = target_other
            else:
                action_type = "investigate"

        return (action_type, target)

    def on_dialogue_received(self, speaker: str, text: str):
        """Called when someone talks to this NPC. Sets reaction state."""
        self.reacting_to = speaker
        self.memory.append(f"heard from {speaker}: {text[:50]}")
        # Trim memory
        if len(self.memory) > 10:
            self.memory = self.memory[-10:]

    def on_action_result(self, action: str, success: bool):
        """Learn from action outcomes. Adjust goal priorities."""
        if self.current_goal:
            if success:
                self.current_goal.priority = min(1.0, self.current_goal.priority + 0.02)
            else:
                self.current_goal.priority = max(0.1, self.current_goal.priority - 0.05)
                if self.current_goal.steps_taken >= self.current_goal.max_steps:
                    self.current_goal.status = GoalStatus.BLOCKED

    def apply_faction_disposition(self, dispositions: dict[str, float]):
        """Faction dispositions drive goal priorities.

        High disposition → cooperative goals favored
        Low disposition → hostile/watchful goals favored
        """
        own = dispositions.get(self.faction, 0.0)

        for goal in self.goals:
            base = goal.priority

            if self.faction == "hounds":
                if own < -0.1:
                    # Hounds are angry: patrol harder, interrogate more
                    if goal.name in ("patrol_city", "interrogate_suspects"):
                        goal.priority = min(1.0, base + 0.15)
                    elif goal.name == "report_to_kostya":
                        goal.priority = min(1.0, base + 0.1)
                elif own > 0.1:
                    # Hounds are content: less aggressive
                    if goal.name == "interrogate_suspects":
                        goal.priority = max(0.1, base - 0.1)

            elif self.faction == "veles":
                if own < -0.1:
                    # Velespriests feel threatened: protect sanctum, study harder
                    if goal.name in ("protect_sanctum", "interpret_veil"):
                        goal.priority = min(1.0, base + 0.15)
                elif own > 0.1:
                    # Favored: teach more
                    if goal.name == "teach_others":
                        goal.priority = min(1.0, base + 0.1)

            elif self.faction == "veche":
                if own < -0.1:
                    # Veche losing money: trade aggressively, gossip less
                    if goal.name in ("barter_goods",):
                        goal.priority = min(1.0, base + 0.15)
                    elif goal.name == "trade_gossip":
                        goal.priority = max(0.1, base - 0.1)
                elif own > 0.1:
                    # Veche prospering: gossip and explore
                    if goal.name in ("trade_gossip", "explore_city"):
                        goal.priority = min(1.0, base + 0.1)

    def has_item(self, item: str) -> bool:
        """Check if NPC has an item (from memory)."""
        return any(f"took {item}" in m for m in self.memory)

    def should_return_relic(self) -> bool:
        """Check if NPC should try to return the relic."""
        if self.has_item("relic"):
            return True
        return False

    def at_archive(self, world_locations: dict) -> bool:
        return world_locations.get(self.npc_name, "") == "archive"
