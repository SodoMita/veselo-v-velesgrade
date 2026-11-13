# Velesgrad v2 – Faction logic
from dataclasses import dataclass, field
from typing import Dict

@dataclass
class Faction:
    id: str
    name: str
    disposition: float = 0.0  # -1..1

DEFAULT_FACTIONS = [
    Faction("hounds", "Hounds", 0.0),
    Faction("veles", "Velespriests", 0.0),
    Faction("veche", "Veche", 0.0),
]

@dataclass
class FactionSignal:
    faction_id: str
    trigger: str
    delta: float
    once_per_turn: bool = True

FACTION_SIGNALS = [
    FactionSignal("hounds", "cast", -0.1),
    FactionSignal("veles", "cast", +0.05),
    FactionSignal("veche", "theft", -0.15),
    FactionSignal("hounds", "theft", +0.1),
    FactionSignal("veles", "pray", +0.1),
]


class FactionEngine:
    def __init__(self, factions: list[Faction] | None = None):
        self.factions: Dict[str, Faction] = {
            f.id: f for f in (factions or [Faction(f.id, f.name, f.disposition) for f in DEFAULT_FACTIONS])
        }
        self._fired_this_turn: set[tuple[str, str]] = set()

    def handle(self, event: str, source: str | None = None) -> list[tuple]:
        results = []
        for sig in FACTION_SIGNALS:
            if sig.trigger != event:
                continue
            key = (sig.faction_id, event)
            if sig.once_per_turn and key in self._fired_this_turn:
                continue
            fac = self.factions.get(sig.faction_id)
            if fac:
                fac.disposition = max(-1.0, min(1.0, fac.disposition + sig.delta))
                results.append((fac.id, fac.disposition))
                self._fired_this_turn.add(key)
        return results

    def end_turn(self):
        self._fired_this_turn.clear()

    def dispositions(self) -> dict[str, float]:
        return {fid: f.disposition for fid, f in self.factions.items()}


# ── BeliefStore (uses PLN Reasoner) ─────────────────────────────────────
# Must import from cog.pln to avoid circular import
class BeliefStore:
    def __init__(self, atomspace, reasoner):
        self.aspace = atomspace
        self.reasoner = reasoner
        self._index: dict[tuple, object] = {}

    def revise_belief(self, subject: str, predicate: str, truth_strength: float):
        from ..cog.atomspace import tv_from_count, ConceptNode, EvaluationLink
        key = (subject, predicate)
        subj = ConceptNode(subject)
        pred = ConceptNode(predicate)
        belief = EvaluationLink(pred, subj)
        tv = tv_from_count(truth_strength, 10.0)
        self.reasoner.revise(belief, tv)
        self._index[key] = belief
        return belief

    def get_belief(self, subject: str, predicate: str):
        key = (subject, predicate)
        atom = self._index.get(key)
        if atom:
            return self.aspace.get_tv(atom)
        return None
