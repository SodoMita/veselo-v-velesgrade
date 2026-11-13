# Velesgrad v2 – World model
from dataclasses import dataclass, field

@dataclass
class Room:
    id: str
    name: str
    tags: list[str] = field(default_factory=list)
    neighbors: list[str] = field(default_factory=list)
    items: list[str] = field(default_factory=list)

@dataclass
class WorldState:
    rooms: dict[str, Room] = field(default_factory=dict)
    locations: dict[str, str] = field(default_factory=dict)  # agent -> room_id

    def move(self, agent: str, room_id: str) -> bool:
        if room_id in self.rooms:
            self.locations[agent] = room_id
            return True
        return False

    def co_present(self, a: str, b: str) -> bool:
        return self.locations.get(a) == self.locations.get(b)

    def agents_at(self, room_id: str) -> list[str]:
        return [a for a, r in self.locations.items() if r == room_id]

    def neighbors_of(self, room_id: str) -> list[str]:
        room = self.rooms.get(room_id)
        return room.neighbors if room else []

    def random_neighbor(self, room_id: str, rng=None) -> str | None:
        import random
        room = self.rooms.get(room_id)
        if not room or not room.neighbors:
            return None
        r = rng or random.Random()
        return r.choice(room.neighbors)
