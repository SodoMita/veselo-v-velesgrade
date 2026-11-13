# Velesgrad v2 – Magic system (deterministic, seeded)
import random
from dataclasses import dataclass

@dataclass
class Veil:
    thickness: float = 1.0
    drain: float = 0.0

    def tick(self):
        self.thickness = min(1.0, self.thickness + 0.01)

def attempt_cast(spell: str, veil: Veil, rng: random.Random) -> tuple[bool, str, float]:
    power = 1.0 - veil.thickness
    roll = rng.random()
    success = roll < (0.3 + power * 0.5)
    cost = 1.0 + veil.drain / 50.0
    veil.drain += cost
    veil.thickness = max(0.0, veil.thickness - 0.05)
    msg = "Cast succeeded" if success else "Veil resists"
    return success, msg, cost
