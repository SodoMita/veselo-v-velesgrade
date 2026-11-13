"""
dialogue/realizer.py – Atomese → English surface realization.

Generates varied, grammatical sentences from AtomSpace knowledge.
Uses multiple sentence patterns per atom type for diversity.
"""

import random
from ..cog.atomspace import (
    AtomSpace, TruthValue, get_sti,
    ConceptNode, PredicateNode,
    InheritanceLink, EvaluationLink, ImplicationLink,
)

# Link Grammar for grammatical validation
try:
    from .lg_ctypes import is_available as _lg_available, get_dictionary as _lg_dict, parse_count as _lg_parse_count
except ImportError:
    _lg_available = lambda: False
    _lg_dict = lambda: None
    _lg_parse_count = lambda t, d: -1


# ── Noun phrases ────────────────────────────────────────────────────────

_ARTICLES = {
    "relic": "the relic", "veil": "the Veil", "bell": "the bell",
    "hounds": "the Hounds", "archive": "the archive", "sanctum": "the sanctum",
    "market": "the market", "tavern": "the tavern", "alley": "the alley",
    "square": "the square", "bell_tower": "the bell tower",
    "stolen_artifact": "a stolen artifact", "sacred_object": "something sacred",
    "ancient_knowledge": "ancient knowledge", "knowledge_repository": "a place of learning",
    "magical_boundary": "a magical boundary", "sacred_place": "a sacred place",
    "trade_hub": "a place of trade", "signal": "a signal",
    "enforcer": "an enforcer", "guardians": "guardians",
    "gossip_hub": "a place of gossip", "crowded": "a crowded place",
    "valuable": "valuable", "ancient": "ancient", "dangerous": "dangerous",
    "trustworthy": "trustworthy", "important": "important", "fragile": "fragile",
    "well_protected": "well protected", "urgent": "urgent",
    "place_of_rumors": "a place of rumors", "mystery": "a mystery",
    "worth_investigating": "worth investigating", "worlds": "the worlds",
    "city_streets": "the streets", "rumors": "rumors",
    "traveler": "a traveler", "spellcaster": "a spellcaster",
    "velespriests": "the Velespriests",
    "veil_relic": "the veil relic", "material_world": "the material world",
    "spirit_world": "the spirit world", "thinning_veil": "the thinning Veil",
    "veil_magic": "veil magic", "ancient_manuscripts": "ancient manuscripts",
    "prophecy_records": "prophecy records", "unknown_thief": "an unknown thief",
    "ancient_artifact": "an ancient artifact", "source_of_power": "a source of power",
    "deep_night": "deep night", "inside_job": "an inside job", "outside_job": "an outside job",
    "broken_ward": "a broken ward", "clue": "a clue",
    "commander": "the commander", "night_streets": "the night streets",
    "keepers_of_veil": "keepers of the Veil", "market_district": "the market district",
    "merchant_guild": "a merchant guild", "spice_road": "the spice road",
    "ancient_wards": "ancient wards", "veil_shrine": "the veil shrine",
    "place_of_prayer": "a place of prayer", "shadowed_place": "a shadowed place",
    "dangerous_at_night": "dangerous at night", "busy_place": "a busy place",
    "warm_place": "a warm place", "exotic_goods": "exotic goods",
    "stranger_sighting": "a stranger sighting", "ancient_city": "an ancient city",
    "city_of_veils": "the City of Veils", "old_god": "an old god",
    "forgotten": "forgotten", "ancient_burden": "an ancient burden",
    "irreplaceable": "irreplaceable", "layered_history": "layered history",
    "hound_loyalty": "Hound loyalty", "unwavering": "unwavering",
    "suspicious": "suspicious", "opportunistic": "opportunistic",
    "distrusted": "distrusted", "landmark": "a landmark", "watchman": "a watchman",
    "spices": "spices", "mead": "mead", "forge": "the forge",
    "temple_gardens": "the temple gardens", "spice_sellers": "spice sellers",
    "lantern_makers": "lantern makers", "tanners": "tanners",
    "old_families": "old families", "sailors": "sailors",
}

_PROPER = {
    "mira", "yuri", "hound", "zorya", "boris", "kostya", "vasilisa", "player",
    # narrators of the Gutenberg books (dialogue/book_knowledge.py)
    "pepys", "montaigne", "thoreau", "aurelius",
}


_PLURAL_NOUNS = {
    "hounds", "velespriests", "guardians", "merchants", "traders", "travelers",
    "worlds", "streets", "rumors", "manuscripts", "records", "spirits",
    "wards", "gods", "keepers", "secrets", "goods",
}

def _is_plural(name: str) -> bool:
    low = name.lower().replace("_", " ")
    if low in _PLURAL_NOUNS:
        return True
    first_word = low.split()[0] if low else ""
    return first_word in _PLURAL_NOUNS

def _np(name: str, with_article: bool = False) -> str:
    if not name:
        return "something"
    low = name.lower().replace("_", " ")
    if low == "player":
        return "the traveler"     # in-fiction rendering of the player concept
    if low in _PROPER:
        return name.replace("_", " ").title()
    if low.replace(" ", "_") in _ARTICLES:
        return _ARTICLES[low.replace(" ", "_")]
    base = name.replace("_", " ").lower()
    if with_article and base not in ("something",):
        return f"the {base}"
    return base


# ── Verb forms ──────────────────────────────────────────────────────────

_VERBS = {
    "is_at": ("is at", "was at"),
    "moved_to": ("moved to", "went to"),
    "observed": ("observed", "noticed", "saw"),
    "investigated": ("investigated", "looked into", "examined"),
    "talked_to": ("spoke with", "talked to", "had words with"),
    "cast_spell": ("cast", "performed"),
    "possesses": ("carries", "holds", "has"),
    "holds": ("holds", "contains", "keeps"),
    "patrols": ("patrols", "watches over", "guards"),
    "separates": ("separates", "divides", "keeps apart"),
    "protected_by": ("is protected by", "is guarded by", "is watched by"),
    "guarded_by": ("is guarded by", "is watched by", "is kept by"),
    "watched_by": ("is watched by", "is observed by"),
    "signals": ("signals", "announces", "calls"),
    "suspects": ("suspects", "is wary of", "distrusts"),
    "known_for": ("is known for", "is famous for"),
    "was_located_in": ("was kept in", "was stored in", "was housed in"),
    "member_of": ("belongs to", "is part of", "serves"),
    "feels": ("feels", "senses"),
    "stolen_by": ("was stolen by", "was taken by"),
    "searched_by": ("is sought by", "is searched for by"),
    "answers_to": ("answers to", "reports to"),
    "reside_in": ("resides in", "lives in", "dwells in"),
    "practice": ("practices", "performs", "engages in"),
    "control": ("controls", "dominates"),
    "spread": ("spreads", "circulates"),
    "serves": ("serves", "pours"),
    "hosts": ("hosts", "welcomes"),
    "contains": ("contains", "holds"),
    "rung_by": ("is rung by", "is rung for"),
    "caused_by": ("is caused by", "comes from"),
    "practiced_by": ("is practiced by", "is used by"),
    "founded_by": ("was founded by", "was established by"),
    "protects": ("protects", "shields", "guards"),
    "sells": ("sells", "offers"),
    "happened_at": ("happened at", "occurred at"),
    "witnessed_by": ("was witnessed by", "was seen by"),
    "left_behind": ("left behind", "abandoned"),
    "rumored_at": ("is rumored at", "is whispered about in"),
}


def _vp(pred: str, rng: random.Random = None) -> str:
    r = rng or random.Random()
    if pred in _VERBS:
        return r.choice(_VERBS[pred])
    return pred.replace("_", " ")


# ── Sentence patterns ───────────────────────────────────────────────────
# Each atom type has multiple patterns. Random selection → variety.


_ADJ_SUFFIXES = ("ous", "ful", "ive", "able", "ible", "worthy", "ent",
                 "ant", "ile", "ing", "ed", "al", "ic")


def _pluralize_word(w: str) -> str:
    low = w.lower()
    if low.endswith(("ies", "ses", "xes", "ches", "shes")):
        return w
    if low.endswith(_ADJ_SUFFIXES):
        return w  # adjectives don't take plurals
    if low.endswith("y") and len(low) > 1 and low[-2] not in "aeiou":
        return w[:-1] + "ies"
    if low.endswith(("s", "x", "ch", "sh")):
        return w + "es"
    return w + "s"


def _pluralize_pred(pred: str) -> str:
    """'an enforcer' → 'enforcers'; 'a place of learning' → 'places of learning'."""
    words = pred.split()
    stripped = pred
    for art in ("the ", "a ", "an ", "some "):
        if stripped.startswith(art):
            stripped = stripped[len(art):]
            break
    if not stripped:
        return pred
    parts = stripped.split()
    parts[0] = _pluralize_word(parts[0])
    joined = " ".join(parts)
    return f"the {joined}" if pred.startswith("the ") else joined


_COMMON_ADJ = {"quiet", "clean", "calm", "dark", "cold", "warm", "old",
               "young", "small", "large", "empty", "full", "safe"}


def _looks_adjective(phrase: str) -> bool:
    words = phrase.split()
    last = words[-1] if words else ""
    return last.endswith(_ADJ_SUFFIXES) or last in _COMMON_ADJ


def _inh_sentences(a_name, b_name, tv, rng) -> list[str]:
    """InheritanceLink(A, B) → multiple candidate sentences."""
    subj = _np(a_name)
    pred = _np(b_name)
    # Bare count-noun predicates need an article: 'quiet place' → 'a quiet place'
    if (_ARTICLES.get(b_name.lower().replace(" ", "_")) is None
            and not pred.startswith(("the ", "a ", "an ", "some ", "something"))
            and b_name.lower() not in _PROPER
            and not _looks_adjective(pred)
            and not _is_plural(b_name)):
        pred = ("an " if pred[0:1] in "aeiou" else "a ") + pred
    plural = _is_plural(a_name)
    copula = "are" if plural else "is"
    if plural:
        pred = _pluralize_pred(pred)

    # Strip article for "a kind of" pattern
    pred_bare = pred
    for art in ("the ", "a ", "an ", "some "):
        if pred_bare.startswith(art):
            pred_bare = pred_bare[len(art):]
            break

    patterns = [
        f"{subj} {copula} {pred}.",
        f"Everyone knows {subj.lower()} {copula} {pred}.",
        f"They say {subj.lower()} {copula} {pred}.",
    ]
    if not _is_plural(a_name) and not _looks_adjective(pred_bare):
        patterns.append(f"{subj} {copula} a kind of {pred_bare}.")

    if tv:
        if tv.confidence > 0.8 and tv.mean > 0.8:
            patterns.extend([
                f"{subj} {copula} certainly {pred}.",
                f"It is well known that {subj.lower()} {copula} {pred}.",
            ])
        elif tv.confidence < 0.3:
            patterns.extend([
                f"{subj} might be {pred}.",
                f"Some think {subj.lower()} {copula} {pred}.",
            ])
        elif tv.mean > 0.6:
            patterns.extend([
                f"Word has it {subj.lower()} {copula} {pred}.",
                f"{subj}? {pred.capitalize()}, they say.",
            ])

    return patterns


_PLURAL_CONJ = {
    "is at": "are at", "was at": "were at",
    "patrols": "patrol", "guards": "guard", "signals": "signal",
    "suspects": "suspect", "separates": "separate", "spreads": "spread",
    "holds": "hold", "contains": "contain", "serves": "serve",
    "is known for": "are known for", "is guarded by": "are guarded by",
    "is watched by": "are watched by", "was kept in": "were kept in",
    "was stored in": "were stored in", "was housed in": "were housed in",
    "watches over": "watch over", "resides in": "reside in",
    "lives in": "live in", "dwells in": "dwell in",
    "practices": "practice", "performs": "perform",
    "controls": "control", "dominates": "dominate",
    "answers to": "answer to", "was stolen by": "were stolen by",
    "was taken by": "were taken by", "is sought by": "are sought by",
}


_PREPS = {"in", "at", "on", "of", "from", "with", "near", "under",
          "over", "into", "inside", "outside", "above", "below"}


# Irregular simple-past forms. Without this set, _conjugate would add "s"
# ("lost" → "losts"). Common verbs only; regular pasts end in "-ed".
_IRREG_PAST = set("""went came saw took gave made said told found knew thought
felt kept left lost had got sat stood wrote ate drank spoke held brought bought
caught taught met led fell fought sent spent built sold heard understood meant ran
began drew grew threw flew rode hid won laid paid shook sought stole struck swore
wore woke wept dug fed fled hung lit slept swept bent bled bound bred cast clung
crept dealt forgot forgave froze knelt lent quit rang rose sang sank slid spun
split spread sprang stuck stung strode swung tore wound became forgave""".split())


def _conjugate(verb_phrase: str, subject_name: str) -> str:
    """Agree a verb phrase with its subject, inflecting unknown verbs.

    'lie in' + singular → 'lies in';  'lie in' + plural → 'lie in';
    'watch over' + plural → 'watch over'; 'is' handled by _PLURAL_CONJ.
    """
    plural = _is_plural(subject_name)
    words = verb_phrase.split()
    if not words:
        return verb_phrase
    head, rest = words[0], words[1:]

    # Irregular / auxiliaries first
    table = _PLURAL_CONJ if plural else {}
    if head in table:
        head = table[head]
    elif not plural:
        # singular: 3sg inflection on base forms
        if head in ("is", "are", "has", "have", "does", "do", "was", "were"):
            head = {"is": "is", "are": "is", "has": "has", "have": "has",
                    "does": "does", "do": "does", "was": "was",
                    "were": "was"}[head]
        elif head.endswith("ed") or head in _IRREG_PAST:
            pass  # past tense ('happened', 'lost') — no 3sg inflection
        elif head.endswith(("sh", "ch", "x", "o")):
            head = head + "es"
        elif head.endswith("s"):
            pass  # already 3rd-person singular ('holds', 'signals')
        elif head.endswith("y") and len(head) > 1 and head[-2] not in "aeiou":
            head = head[:-1] + "ies"
        else:
            head = head + "s"
    return " ".join([head] + rest)


def _agree_verb(verb: str, subject_atom_name: str) -> str:
    return _conjugate(verb, subject_atom_name)


def _evl_sentences(pred_name, args, tv, rng) -> list[str]:
    """EvaluationLink(P, List(args)) → multiple candidate sentences."""
    if not args:
        return []
    if pred_name in _PREPS:
        verb = _conjugate("is " + pred_name, args[0])
    else:
        verb = _vp(pred_name, rng)
        verb = _agree_verb(verb, args[0])

    subj = _np(args[0], with_article=True)
    patterns = []

    if len(args) == 1:
        patterns = [
            f"{subj} {verb}.",
            f"{subj} {verb} here.",
        ]
    else:
        obj = _np(args[1], with_article=True)
        patterns = [
            f"{subj} {verb} {obj}.",
            f"{subj} {verb} {obj}, they say.",
            f"Word is {subj.lower()} {verb} {obj}.",
        ]

    if tv and tv.confidence > 0.8:
        patterns.append(f"It is known that {subj.lower()} {verb} {obj if len(args) > 1 else ''}.")

    return patterns


def _imp_sentences(a_text, b_text, tv, rng) -> list[str]:
    """ImplicationLink(A, B) → multiple candidate sentences."""
    patterns = [
        f"If {a_text}, then {b_text}.",
        f"When {a_text}, {b_text}.",
        f"{a_text.capitalize()}, and so {b_text}.",
        f"Whenever {a_text}, {b_text} follows.",
    ]
    return patterns


def _atom_fragment(atom) -> str | None:
    type_name = getattr(atom, 'type_name', '')
    out = getattr(atom, 'out', [])
    if 'Inheritance' in type_name and len(out) == 2:
        return f"{_np(getattr(out[0], 'name', ''))} is {_np(getattr(out[1], 'name', ''))}"
    elif 'Evaluation' in type_name and len(out) >= 2:
        pred = getattr(out[0], 'name', '')
        args_atom = out[1]
        arg_out = getattr(args_atom, 'out', None)
        args = [getattr(a, 'name', '') for a in arg_out] if arg_out else [getattr(args_atom, 'name', '')]
        verb = _vp(pred)
        if len(args) >= 2:
            return f"{_np(args[0])} {verb} {_np(args[1])}"
        elif args:
            return f"{_np(args[0])} {verb}"
    name = getattr(atom, 'name', '')
    return name.replace('_', ' ') if name else None


# ── Main atom → text function ───────────────────────────────────────────

def atom_to_text(atom, rng: random.Random = None) -> str | None:
    """Convert any atom to an English sentence. Random pattern selection for variety."""
    r = rng or random.Random()
    type_name = getattr(atom, 'type_name', '')
    out = getattr(atom, 'out', [])
    tv = getattr(atom, 'tv', None)

    candidates = []

    if 'Inheritance' in type_name and len(out) == 2:
        a_name = getattr(out[0], 'name', '')
        b_name = getattr(out[1], 'name', '')
        candidates = _inh_sentences(a_name, b_name, tv, r)

    elif 'Evaluation' in type_name and len(out) >= 2:
        pred_name = getattr(out[0], 'name', '')
        args_atom = out[1]
        arg_out = getattr(args_atom, 'out', None)
        args = [getattr(a, 'name', '') for a in arg_out] if arg_out else [getattr(args_atom, 'name', '')]
        candidates = _evl_sentences(pred_name, args, tv, r)

    elif 'Implication' in type_name and len(out) == 2:
        a_text = _atom_fragment(out[0])
        b_text = _atom_fragment(out[1])
        if a_text and b_text:
            candidates = _imp_sentences(a_text, b_text, tv, r)

    if not candidates:
        name = getattr(atom, 'name', '')
        if name and len(name) > 3 and not name.startswith(('observed_', 'heard:', 'cast_')):
            candidates = [f"There is talk of {name.replace('_', ' ')}."]

    if not candidates:
        return None

    return r.choice(candidates)


# ── Generator class ─────────────────────────────────────────────────────

class AtomeseGenerator:
    """Generates natural language from AtomSpace knowledge."""

    def __init__(self, atomspace: AtomSpace):
        self.aspace = atomspace
        self.rng = random.Random()

    # Ephemeral event predicates — not conversational topics
    _EPHEMERAL_PREDS = {'moved_to', 'is_at', 'observed', 'talked_to', 'heard_from'}

    def _is_expressible(self, atom) -> bool:
        type_name = getattr(atom, 'type_name', '')
        if any(t in type_name for t in ['Inheritance', 'Evaluation', 'Implication', 'Associate']):
            out = getattr(atom, 'out', [])
            if len(out) < 2:
                return False
            # Skip bare NPC names as predicates
            name0 = getattr(out[0], 'name', '').lower()
            if name0 in ('mira','yuri','hound','zorya','boris','kostya','vasilisa','player'):
                return False
            # Skip ephemeral movement/observation events
            if name0 in self._EPHEMERAL_PREDS:
                return False
            return True
        return False

    def select_salient_atoms(self, speaker: str, limit: int = 20) -> list:
        """Select atoms weighted by STI with randomness for diversity.
        Not just top-k — uses weighted sampling so lower-STI atoms get a chance.
        """
        candidates = []
        for atom in self.aspace:
            if self._is_expressible(atom):
                sti = get_sti(atom)
                type_name = getattr(atom, 'type_name', '')
                bonus = 10.0 if 'Link' in type_name else 0.0
                weight = max(0.1, sti + bonus)
                candidates.append((weight, atom))

        if not candidates:
            return []

        # Weighted sampling without replacement
        import random
        selected = []
        pool = list(candidates)
        for _ in range(min(limit, len(pool))):
            weights = [w for w, _ in pool]
            total = sum(weights)
            if total <= 0:
                break
            r = random.random() * total
            cumulative = 0
            for i, (w, atom) in enumerate(pool):
                cumulative += w
                if cumulative >= r:
                    selected.append(atom)
                    pool.pop(i)
                    break
        return selected

    def generate_speech(self, speaker: str, listener: str,
                        tom=None, limit: int = 3,
                        recently_said: set[str] = None) -> list[str]:
        atoms = self.select_salient_atoms(speaker, limit=limit * 5)
        utterances = []
        said = recently_said if recently_said is not None else set()

        for atom in atoms:
            text = atom_to_text(atom, self.rng)
            if not text or len(text.split()) < 3:
                continue
            if tom and tom.knows(listener, text):
                continue
            if text in said:
                continue
            utterances.append(text)
            said.add(text)
            if len(utterances) >= limit:
                break

        return utterances

    def generate_observation(self, room: str, agents_present: list[str],
                             hour: int) -> str | None:
        room_name = room.replace("_", " ")
        for atom in self.aspace:
            type_name = getattr(atom, 'type_name', '')
            if 'Inheritance' not in type_name:
                continue
            out = getattr(atom, 'out', [])
            if len(out) != 2:
                continue
            a_name = getattr(out[0], 'name', '').lower()
            b_name = getattr(out[1], 'name', '').lower()
            if room.lower() in a_name or room.lower() in b_name:
                text = atom_to_text(atom, self.rng)
                if text:
                    return text
        if agents_present:
            names = ", ".join(agents_present[:3])
            return f"{names} {'are' if len(agents_present) > 1 else 'is'} in the {room_name}."
        return None

    def generate_response(self, heard_text: str, speaker: str) -> str | None:
        words = set(heard_text.lower().replace('.', '').replace('?', '').replace('"', '').split())
        relevant = []
        for atom in self.aspace:
            if not self._is_expressible(atom):
                continue
            name = getattr(atom, 'name', '').lower()
            out = getattr(atom, 'out', [])
            match = any(w in name for w in words if len(w) > 3)
            if not match:
                for o in out:
                    o_name = getattr(o, 'name', '').lower()
                    if any(w in o_name for w in words if len(w) > 3):
                        match = True
                        break
            if match:
                relevant.append((get_sti(atom), atom))

        if not relevant:
            return None

        relevant.sort(reverse=True)
        return atom_to_text(relevant[0][1], self.rng)
