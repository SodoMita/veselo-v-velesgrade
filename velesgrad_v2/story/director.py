# Velesgrad v2 – Director: manages story threads
from dataclasses import dataclass, field
import random

@dataclass
class StoryThread:
    id: str
    tension: float = 0.5
    active: bool = True
    age: int = 0

@dataclass
class Director:
    rng: random.Random = field(default_factory=random.Random)
    threads: list[StoryThread] = field(default_factory=list)
    ongoing: bool = True
    tick_n: int = 0

    def establish_beginning(self):
        self.threads = [
            StoryThread("relic_theft", tension=0.6),
            StoryThread("city_unrest", tension=0.5),
        ]

    def spawn_thread(self, static_pool: list[str] | None = None) -> StoryThread:
        if static_pool and self.rng.random() > 0.4:
            tid = self.rng.choice(static_pool)
        else:
            nouns = ["bell", "veil", "hound", "archive", "shadow"]
            verbs = ["stirs", "thins", "watches", "burns", "calls"]
            tid = f"{self.rng.choice(nouns)}_{self.rng.choice(verbs)}"
        t = StoryThread(tid, tension=self.rng.uniform(0.3, 0.7))
        self.threads.append(t)
        return t

    def hottest_thread(self, ecan_sti: dict[str, float] | None = None) -> StoryThread | None:
        active = [t for t in self.threads if t.active]
        if not active:
            return None
        def score(t: StoryThread):
            sti = (ecan_sti or {}).get(t.id, 0.0)
            return t.tension + sti * 0.1
        return max(active, key=score)

    def tick(self):
        self.tick_n += 1
        for t in self.threads:
            if t.active:
                t.tension += self.rng.uniform(-0.05, 0.05)
                t.tension = max(0.0, min(1.0, t.tension))
                t.age += 1
                # threads can expire
                if t.age > 50 and t.tension < 0.2:
                    t.active = False
