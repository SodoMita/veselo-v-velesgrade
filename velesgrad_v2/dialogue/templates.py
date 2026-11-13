"""
dialogue/templates.py – Rich dialogue templates for LLM-free operation.

NPCs speak based on: who they are, who they're talking to, what they know,
what faction they belong to, what's happening in the world, and their mood.

No LLM required. All prose is template-driven but context-sensitive.
"""

import random


# ── Faction voice profiles ──────────────────────────────────────────────

FACTION_VOICE = {
    "hounds": {
        "greetings": ["Stay sharp.", "What do you want?", "Speak quick."],
        "farewells": ["Watch yourself.", "Don't get caught.", "Move along."],
        "threats": ["The city has teeth.", "We remember faces.", "Cross us and find out."],
        "observations": ["Something stirs in the {room}.", "The streets whisper tonight.", "Trust nothing you hear."],
        "knowledge": ["We know about {fact}.", "Word reached us: {fact}.", "Our eyes saw {fact}."],
        "questions": ["What do you know about {topic}?", "Have you seen anything in the {room}?", "Who told you that?"],
        "mood_cold": ["I have nothing to say to you.", "Keep walking.", "You're not welcome here."],
        "mood_warm": ["Listen carefully.", "I'll tell you something.", "Between us—" ],
    },
    "veles": {
        "greetings": ["Peace upon you.", "The Veil watches.", "Blessings, traveler."],
        "farewells": ["May the Veil protect you.", "Walk in wisdom.", "Until we meet again."],
        "threats": ["The Veil sees all.", "Even the shadows have ears.", "Pray you don't anger the old ones."],
        "observations": ["The {room} holds memories.", "I sense a shift in the Veil.", "The old ways persist here."],
        "knowledge": ["The archives speak of {fact}.", "It is written: {fact}.", "I have studied {fact}."],
        "questions": ["What brings you to the {room}?", "Do you seek wisdom?", "Have you prayed today?"],
        "mood_cold": ["The Veil is thin between us.", "I must meditate.", "Not now."],
        "mood_warm": ["Come, sit.", "I have much to share.", "The spirits favor you."],
    },
    "veche": {
        "greetings": ["Good day!", "Well met!", "Business or pleasure?"],
        "farewells": ["Fair dealing!", "Come back with coin!", "Until next trade!"],
        "threats": ["Bad for business, that.", "The market has a long memory.", "Debts always come due."],
        "observations": ["The {room} is busy today.", "Trade flows through here.", "Coin changes hands."],
        "knowledge": ["Word on the street: {fact}.", "I heard from a merchant that {fact}.", "The market knows {fact}."],
        "questions": ["Looking to buy?", "What's your price?", "Have you heard the latest?"],
        "mood_cold": ["No deals today.", "I'm busy.", "Find another seller."],
        "mood_warm": ["For you, a special price!", "Let's talk business.", "I like your style."],
    },
}

# ── Context-sensitive speech generation ─────────────────────────────────

def generate_speech(speaker: str, listener: str, faction: str,
                    known_facts: list[str], room: str, disposition: float,
                    rng: random.Random, topic: str = None) -> str | None:
    """Generate a context-appropriate utterance. Returns None if nothing to say."""

    voice = FACTION_VOICE.get(faction, FACTION_VOICE["veche"])

    # Choose category based on context
    if disposition < -0.3:
        category = "mood_cold"
    elif disposition > 0.3:
        category = "mood_warm"
    elif known_facts and rng.random() < 0.5:
        category = "knowledge"
    elif rng.random() < 0.3:
        category = "observations"
    elif rng.random() < 0.4:
        category = "questions"
    else:
        category = "greetings"

    templates = voice.get(category, voice["greetings"])
    template = rng.choice(templates)

    # Fill in template
    fact = rng.choice(known_facts) if known_facts else "nothing"
    result = template.format(
        fact=fact,
        room=room,
        topic=topic or "the relic",
        speaker=speaker,
        listener=listener,
    )
    return result


# ── World event descriptions ────────────────────────────────────────────

EVENT_DESCRIPTIONS = {
    "bell_ring": [
        "The great bell tolls from the tower, its echo rolling across the rooftops.",
        "A deep bronze note shivers through the air—the bell calls gathering.",
        "The bell tower sounds. All who hear it feel the pull of ceremony.",
    ],
    "veil_thin": [
        "The Veil shimmers and thins near the {room}. Shadows move differently.",
        "Something stirs beyond the Veil. The air grows heavy with old magic.",
        "The boundary between worlds grows gossamer-thin. Can you feel it?",
    ],
    "relic_mentioned": [
        "Whispers of the stolen relic surface again, like a stone in troubled water.",
        "Someone mentions the relic. Heads turn. Ears perk.",
        "The matter of the missing relic weighs on every conversation.",
    ],
    "hound_patrol": [
        "Hounds move through the {room}, eyes sharp, hands near blades.",
        "A Hound patrol passes. The crowd parts without being asked.",
        "The Hounds are watching. They always are.",
    ],
    "market_buzz": [
        "The market hums with rumor and barter.",
        "A new shipment arrives at the market. Fingers count coin.",
        "Deals are struck in whispers at the market stalls.",
    ],
    "night_falls": [
        "Dusk settles over the city. Lanterns bloom like orange flowers.",
        "Night creeps in. The Veil grows stronger in the darkness.",
        "The city puts on its night face. Different rules apply now.",
    ],
    "morning_dawn": [
        "Dawn breaks. The city stirs from uneasy sleep.",
        "Morning light reveals what darkness concealed.",
        "A new day begins. The cycle continues.",
    ],
    "festival": [
        "The Veche have declared market day! Banners flutter in the breeze.",
        "A small festival breaks out in the {room}. Music and laughter.",
        "Celebration! Someone has opened a barrel of mead.",
    ],
    "tension_rising": [
        "The air crackles with unspoken grievances.",
        "People speak in shorter sentences today. Something is building.",
        "Tension coils through the city like a spring.",
    ],
}


def describe_event(event_type: str, room: str, rng: random.Random) -> str:
    templates = EVENT_DESCRIPTIONS.get(event_type, ["Something happens."])
    return rng.choice(templates).format(room=room)


# ── Agent internal monologue (for chronicle) ────────────────────────────

INTERNAL_THOUGHTS = {
    "curiosity": [
        "{name} wonders about {topic}.",
        "{name}'s thoughts circle back to {topic}.",
        "Something about {topic} doesn't add up, {name} thinks.",
    ],
    "safety": [
        "{name} checks the exits.",
        "{name} keeps close to the wall.",
        "Better safe than sorry, {name} figures.",
    ],
    "affiliation": [
        "{name} looks for familiar faces.",
        "{name} misses the old days.",
        "Who can {name} trust?",
    ],
    "autonomy": [
        "{name} resents being told what to do.",
        "{name} decides to go their own way.",
        "No one tells {name} where to walk.",
    ],
}


def generate_thought(agent_name: str, demand: str, topic: str, rng: random.Random) -> str:
    templates = INTERNAL_THOUGHTS.get(demand, ["{name} thinks."])
    return rng.choice(templates).format(name=agent_name, topic=topic or "the city")
