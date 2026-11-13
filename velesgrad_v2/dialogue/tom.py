# Velesgrad v2 – Theory of Mind + Dialogue Manager
# Real conversational dynamics: ToM prevents repeats, AtomeseGenerator
# produces speech FROM the knowledge graph, not from templates.

from dataclasses import dataclass, field
from enum import Enum
from .realizer import AtomeseGenerator

try:
    from . import speech_acts as _sa
except ImportError:
    _sa = None


class SpeechAct(Enum):
    STATEMENT = "statement"
    QUESTION = "question"
    COMMAND = "command"
    GREETING = "greeting"
    FAREWELL = "farewell"


@dataclass
class Utterance:
    speaker: str
    listener: str
    text: str
    act: SpeechAct
    facts_conveyed: list[str] = field(default_factory=list)
    turn: int = 0
    grounded: bool = False


class ConversationMemory:
    def __init__(self):
        self.history: list[Utterance] = []

    def add(self, u: Utterance):
        self.history.append(u)

    def recent(self, n: int = 10) -> list[Utterance]:
        return self.history[-n:]

    def has_heard(self, listener: str, fact: str) -> bool:
        return any(fact in u.facts_conveyed and u.listener == listener for u in self.history)

    def last_speaker_to(self, listener: str) -> str | None:
        for u in reversed(self.history):
            if u.listener == listener:
                return u.speaker
        return None


class TheoryOfMind:
    """Models what each agent knows."""
    def __init__(self):
        self.knowledge: dict[str, set[str]] = {}
        self.common_ground: dict[tuple[str, str], set[str]] = {}

    def knows(self, agent: str, fact: str) -> bool:
        return fact in self.knowledge.get(agent, set())

    def learn(self, agent: str, fact: str):
        self.knowledge.setdefault(agent, set()).add(fact)

    def forget(self, agent: str, fact: str):
        if agent in self.knowledge:
            self.knowledge[agent].discard(fact)

    def mark_common(self, a: str, b: str, fact: str):
        key = tuple(sorted([a, b]))
        self.common_ground.setdefault(key, set()).add(fact)

    def is_common_ground(self, a: str, b: str, fact: str) -> bool:
        key = tuple(sorted([a, b]))
        return fact in self.common_ground.get(key, set())

    def novel_for(self, speaker: str, listener: str, facts: list[str]) -> list[str]:
        return [f for f in facts if not self.knows(listener, f)]

    def what_doesnt_know(self, agent: str, facts: list[str]) -> list[str]:
        return [f for f in facts if not self.knows(agent, f)]

    def to_dict(self) -> dict:
        return {
            "knowledge": {k: list(v) for k, v in self.knowledge.items()},
        }

    def from_dict(self, d: dict):
        for k, v in d.get("knowledge", {}).items():
            self.knowledge[k] = set(v)


class DialogueManager:
    def __init__(self, tom: TheoryOfMind, generator: AtomeseGenerator | None = None):
        self.tom = tom
        self.memory = ConversationMemory()
        self.turn_holder: str | None = None
        self.generator = generator
        self.recently_said: set[str] = set()  # track what's been said recently

    # Imperative led-verb heuristic. COMMAND is deliberately NOT learned:
    # the NPS Chat corpus (training data for the act model) has no
    # directive class, so commands stay rule-based and honest.
    _IMPERATIVE_VERBS = ("go ", "take ", "give ", "tell ", "move ", "open ",
                         "close ", "wait", "look ", "ask ", "help", "find ",
                         "bring ", "return ", "leave", "stop")

    def recognize_act(self, text: str) -> SpeechAct:
        """Recognize the dialogue act of an utterance.

        Pipeline: deterministic fast paths → data-driven classifier (NPS
        Chat naive Bayes, 80.5% held-out accuracy) → word-list fallback.
        Fast paths keep behavior stable for the game's fixed vocabulary;
        the model handles everything else (e.g. "morning, archivist"
        → GREETING, "i'm off then" → FAREWELL).
        """
        t = text.strip()
        low = t.lower()
        words = low.replace(",", " ").replace(".", " ").split()

        # 1. Short greeting/parting: word list + corpus-verified patterns
        if not t.endswith("?"):
            if any(w in ("hello", "hi", "hey", "greetings", "privet") for w in words):
                return SpeechAct.GREETING
            if any(w in ("bye", "farewell", "goodbye", "dosvidaniya") for w in words):
                return SpeechAct.FAREWELL
            if _sa is not None:
                if _sa.farewell_pattern(t):
                    return SpeechAct.FAREWELL
                if _sa.greeting_pattern(t):
                    return SpeechAct.GREETING

        # 2. Questions by punctuation
        if t.endswith("?"):
            return SpeechAct.QUESTION

        # 3. Commands by imperative lead verb (heuristic; see note above)
        if low.startswith(self._IMPERATIVE_VERBS):
            return SpeechAct.COMMAND

        # 4. Learned classifier
        if _sa is not None:
            label = _sa.classify(t)
            if label:
                return SpeechAct(label.lower())

        # 5. Last-resort word lists
        if any(w in ("hello", "hi", "hey", "greetings") for w in words):
            return SpeechAct.GREETING
        if any(w in ("bye", "farewell", "goodbye") for w in words):
            return SpeechAct.FAREWELL
        return SpeechAct.STATEMENT

    def speak(self, speaker: str, listener: str, candidate_facts: list[str], turn: int) -> Utterance | None:
        # ToM filter
        novel = self.tom.novel_for(speaker, listener, candidate_facts)
        if not novel:
            return None

        fact = novel[0]
        act = self.recognize_act(fact)
        u = Utterance(speaker, listener, fact, act, [fact], turn)
        self.memory.add(u)
        self.tom.learn(listener, fact)
        self.tom.mark_common(speaker, listener, fact)
        self.turn_holder = listener
        return u

    def generate_utterance(self, speaker: str, listener: str, turn: int,
                           room: str = "", agents_present: list[str] = None,
                           hour: int = 12) -> Utterance | None:
        """Generate speech FROM the AtomSpace knowledge graph."""
        if not self.generator:
            return None

        utterances = self.generator.generate_speech(
            speaker, listener, tom=self.tom, limit=3,
            recently_said=self.recently_said
        )

        if not utterances:
            # Try generating an observation
            if agents_present:
                obs = self.generator.generate_observation(room, agents_present, hour)
                if obs and not self.tom.knows(listener, obs):
                    utterances = [obs]

        if not utterances:
            return None

        text = utterances[0]
        act = self.recognize_act(text)
        u = Utterance(speaker, listener, text, act, utterances, turn)
        self.memory.add(u)
        # Listener learns the expressed facts
        for fact in utterances:
            self.tom.learn(listener, fact)
            self.tom.mark_common(speaker, listener, fact)
        self.turn_holder = listener
        return u

    def reply(self, speaker: str, listener: str, heard_text: str, turn: int) -> Utterance | None:
        """Generate a response to heard text, based on what the speaker knows."""
        if not self.generator:
            return None

        response = self.generator.generate_response(heard_text, speaker)
        if not response:
            return None

        if self.tom.knows(listener, response):
            return None

        act = self.recognize_act(response)
        u = Utterance(speaker, listener, response, act, [response], turn)
        self.memory.add(u)
        self.tom.learn(listener, response)
        self.tom.mark_common(speaker, listener, response)
        self.turn_holder = listener
        return u

    def decay_recent(self):
        """Clear recently_said every ~20 turns so topics can return."""
        if len(self.recently_said) > 15:
            self.recently_said.clear()

    def can_take_turn(self, agent: str) -> bool:
        return self.turn_holder is None or self.turn_holder == agent
