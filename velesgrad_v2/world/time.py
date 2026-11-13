# Velesgrad v2 – Clock with real hour attribute
# V1 had no hour, time-of-day learning never worked.

from dataclasses import dataclass

@dataclass
class Clock:
    tick_n: int = 0
    hour: int = 12  # 0-23

    @property
    def period(self) -> str:
        if 5 <= self.hour < 12:
            return "morning"
        if 12 <= self.hour < 17:
            return "day"
        if 17 <= self.hour < 21:
            return "evening"
        return "night"

    def tick(self):
        self.tick_n += 1
        self.hour = (self.hour + 1) % 24

    def to_dict(self):
        return {"tick_n": self.tick_n, "hour": self.hour}

    def from_dict(self, d):
        self.tick_n = d["tick_n"]
        self.hour = d["hour"]
