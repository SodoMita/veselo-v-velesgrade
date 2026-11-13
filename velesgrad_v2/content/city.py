# Velesgrad v2 – Hardcoded city (honestly documented)
from ..world.model import Room, WorldState

def build_world() -> WorldState:
    rooms = {
        "square": Room("square", "Veles Square", ["public", "open"], ["archive", "tavern", "bell_tower", "market"]),
        "archive": Room("archive", "Archive", ["quiet", "knowledge"], ["square", "sanctum"]),
        "tavern": Room("tavern", "Tavern", ["social", "warm"], ["square", "alley"]),
        "bell_tower": Room("bell_tower", "Bell Tower", ["high", "watch"], ["square"]),
        "market": Room("market", "Market", ["trade", "crowd"], ["square", "alley"]),
        "sanctum": Room("sanctum", "Sanctum", ["magic", "quiet"], ["archive"]),
        "alley": Room("alley", "Alley", ["shadow", "narrow"], ["market", "tavern"]),
    }
    # bidirectional neighbors
    for r in rooms.values():
        for n in list(r.neighbors):
            if n in rooms and r.id not in rooms[n].neighbors:
                rooms[n].neighbors.append(r.id)
    return WorldState(rooms, {})


NPC_ROSTER = [
    {"name": "Mira", "faction": "veles", "home": "archive"},
    {"name": "Yuri", "faction": "veche", "home": "tavern"},
    {"name": "Hound", "faction": "hounds", "home": "square"},
    {"name": "Zorya", "faction": "veles", "home": "sanctum"},
    {"name": "Boris", "faction": "veche", "home": "market"},
    {"name": "Kostya", "faction": "hounds", "home": "bell_tower"},
    {"name": "Vasilisa", "faction": "veche", "home": "alley"},
]

TEACHABLE_SPELLS = {
    "Mira": [("ward", 0.5), ("reveal", 0.7)],
    "Zorya": [("veil_walk", 0.6)],
    "Yuri": [("gossip", 0.3)],
    "Boris": [("barter", 0.4)],
    "Vasilisa": [("shadow_step", 0.8)],
    "Hound": [],
    "Kostya": [],
}

# Known world facts for seeding
SEED_FACTS = [
    "the relic was stolen",
    "the archive holds ancient knowledge",
    "the hounds patrol at night",
    "the Veil thins at the edges",
    "the bell signals gathering",
    "the Velespriests guard the sanctum",
    "trade flows through the market",
]
