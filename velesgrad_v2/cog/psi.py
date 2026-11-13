# Velesgrad v2 – OpenPsi demand system
# Drives agent behavior via internal demands. No sqrt(activation) hacks.

from dataclasses import dataclass, field
import random
import math

@dataclass
class Demand:
    name: str
    activation: float = 0.5
    drift: float = 0.0
    weight: float = 1.0

    def tick(self, rng: random.Random):
        self.activation += self.drift + rng.uniform(-0.01, 0.01)
        self.activation = max(0.0, min(1.0, self.activation))


@dataclass
class Goal:
    demand: str
    payoff: float
    estimate: float
    cost: float = 0.1
    action: tuple = ("wait", None)

    def utility(self) -> float:
        return self.payoff * self.estimate - self.cost


class PsiModule:
    def __init__(self, demands: list[Demand] | None = None, rng: random.Random | None = None):
        if demands is None:
            demands = [
                Demand("competence", 0.5, 0.01, 1.0),
                Demand("certainty", 0.5, 0.01, 1.0),
                Demand("affiliation", 0.5, 0.02, 1.0),
                Demand("autonomy", 0.5, 0.0, 1.0),
            ]
        self.demands = {d.name: d for d in demands}
        self.rng = rng or random.Random()
        self.goals: list[Goal] = []

    def tick(self):
        for d in self.demands.values():
            d.tick(self.rng)

    def add_goal(self, goal: Goal):
        self.goals.append(goal)

    def select_goal(self, candidates: list[Goal] | None = None, epsilon: float = 0.1) -> Goal | None:
        pool = candidates or self.goals
        if not pool:
            return None
        scored = []
        for g in pool:
            demand_act = self.demands.get(g.demand, Demand(g.demand)).activation
            score = g.utility() * (0.5 + 0.5 * demand_act)
            scored.append((score, g))
        scored.sort(key=lambda x: x[0], reverse=True)
        if self.rng.random() < epsilon and len(scored) > 1:
            return self.rng.choice([g for _, g in scored[1:]])
        return scored[0][1]

    def satisfy(self, demand_name: str, amount: float):
        if demand_name in self.demands:
            d = self.demands[demand_name]
            d.activation = max(0.0, d.activation - amount)

    def most_urgent(self) -> Demand:
        return max(self.demands.values(), key=lambda d: d.activation * d.weight)
