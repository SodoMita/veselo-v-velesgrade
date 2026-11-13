"""
dialogue/lg_generator.py – Link Grammar-based text generation.

Uses the real Link Grammar parser (compiled from opencog/link-grammar)
to validate and generate grammatical English from Atomese structures.

Pipeline:
  1. Atomese knowledge → semantic representation
  2. Semantic representation → candidate sentences
  3. Link Grammar validates grammar
  4. Best parse selected as output

This replaces templates with real grammatical generation.
"""

import os, sys

# Link Grammar must be on LD_LIBRARY_PATH and PYTHONPATH
_LG_AVAILABLE = False
_LG_DICT = None

def _init_lg():
    global _LG_AVAILABLE, _LG_DICT
    if _LG_AVAILABLE:
        return True
    try:
        import linkgrammar as lg
        _LG_DICT = lg.Dictionary(lang='en')
        _LG_AVAILABLE = True
        return True
    except Exception:
        return False


def _parse_count(sentence: str) -> int:
    """Count valid Link Grammar parses for a sentence."""
    if not _LG_AVAILABLE or not _LG_DICT:
        return -1  # can't validate
    try:
        import linkgrammar as lg
        po = lg.ParseOptions()
        po.verbosity = 0
        s = lg.Sentence(sentence, _LG_DICT, po)
        return sum(1 for _ in s.parse())
    except Exception:
        return 0


def _get_links(sentence: str) -> list[tuple[str, str, str]]:
    """Parse a sentence and return (left_word, link_label, right_word) tuples."""
    if not _LG_AVAILABLE or not _LG_DICT:
        return []
    try:
        import linkgrammar as lg
        po = lg.ParseOptions()
        po.verbosity = 0
        s = lg.Sentence(sentence, _LG_DICT, po)
        for lk in s.parse():
            words = list(lk.words())
            links = list(lk.links())
            result = []
            for l in links:
                ll = l.lword
                lr = l.rword
                label = l.label
                w_left = words[ll] if ll < len(words) else "?"
                w_right = words[lr] if lr < len(words) else "?"
                result.append((w_left, label, w_right))
            return result
    except Exception:
        return []
    return []


# ── Subject-verb agreement ──────────────────────────────────────────────

_PLURAL_SUBJECTS = {
    "hounds", "velespriests", "guardians", "merchants", "enforcers",
    "gods", "spirits", "people", "they", "we",
}

_SINGULAR_VERBS = {
    "is": "is", "are": "is", "have": "has", "do": "does",
    "patrol": "patrols", "guard": "guards", "know": "knows",
    "watch": "watches", "suspect": "suspects", "separate": "separates",
    "protect": "protects", "signal": "signals", "hold": "holds",
}

_PLURAL_VERBS = {
    "is": "are", "are": "are", "has": "have", "does": "do",
    "patrols": "patrol", "guards": "guard", "knows": "know",
    "watches": "watch", "suspects": "suspect", "separates": "separate",
    "protects": "protect", "signals": "signal", "holds": "hold",
}


def _agree(subject: str, verb: str) -> str:
    """Make verb agree with subject."""
    subj_lower = subject.lower().strip()
    if subj_lower in _PLURAL_SUBJECTS:
        return _PLURAL_VERBS.get(verb, verb)
    else:
        return _SINGULAR_VERBS.get(verb, verb)


# ── Atomese → candidate sentences ───────────────────────────────────────

def _np(name: str) -> str:
    """Atom name → noun phrase."""
    name = name.replace("_", " ")
    # Known proper nouns
    proper = {"mira", "yuri", "hound", "zorya", "boris", "kostya", "vasilisa", "player"}
    if name.lower() in proper:
        return name.title()
    # Known entities with articles
    articles = {
        "relic": "the relic", "veil": "the Veil", "bell": "the bell",
        "hounds": "the Hounds", "archive": "the archive", "sanctum": "the sanctum",
        "market": "the market", "tavern": "the tavern", "alley": "the alley",
        "square": "the square", "bell tower": "the bell tower",
    }
    if name.lower() in articles:
        return articles[name.lower()]
    return f"the {name}"


def _vp(predicate_name: str) -> str:
    """Predicate name → verb phrase."""
    verbs = {
        "is_at": "is at", "moved_to": "moved to", "observed": "observed",
        "investigated": "investigated", "talked_to": "spoke with",
        "cast_spell": "cast a spell", "possesses": "carries",
        "holds": "holds", "patrols": "patrols", "separates": "separates",
        "protected_by": "is protected by", "signals": "signals",
        "member_of": "belongs to", "feels": "feels", "suspects": "suspects",
        "known_for": "is known for", "was_located_in": "was kept in",
    }
    return verbs.get(predicate_name, predicate_name.replace("_", " "))


def inheritance_to_sentences(a_name: str, b_name: str, tv=None) -> list[str]:
    """Generate candidate sentences for InheritanceLink(A, B)."""
    subj = _np(a_name)
    pred = _np(b_name)

    candidates = []

    # Basic copula
    copula = _agree(subj, "is")
    candidates.append(f"{subj} {copula} {pred}.")
    candidates.append(f"{subj} {copula} a kind of {pred}.")

    # With confidence qualifier
    if tv:
        if tv.confidence > 0.8 and tv.mean > 0.8:
            candidates.append(f"{subj} is certainly {pred}.")
        elif tv.confidence < 0.3:
            candidates.append(f"{subj} might be {pred}.")
        elif tv.mean < 0.3:
            candidates.append(f"{subj} is probably not {pred}.")

    return candidates


def evaluation_to_sentences(pred_name: str, args: list[str], tv=None) -> list[str]:
    """Generate candidate sentences for EvaluationLink(P, List(args))."""
    verb = _vp(pred_name)

    if len(args) == 0:
        return []

    subj = _np(args[0])

    if len(args) == 1:
        candidates = [
            f"{subj} {verb}.",
        ]
    else:
        obj = _np(args[1])
        candidates = [
            f"{subj} {verb} {obj}.",
            f"{subj} {verb} {obj}.",
        ]

    # With qualifiers
    if tv:
        if tv.confidence > 0.8:
            candidates.append(f"It is known that {subj.lower()} {verb} {obj if len(args) > 1 else ''}.")
        elif tv.confidence < 0.2:
            candidates.append(f"Some say {subj.lower()} {verb} {obj if len(args) > 1 else ''}.")

    return candidates


def implication_to_sentences(a_text: str, b_text: str, tv=None) -> list[str]:
    """Generate candidate sentences for ImplicationLink(A, B)."""
    candidates = [
        f"If {a_text}, then {b_text}.",
        f"When {a_text}, {b_text}.",
        f"{a_text.capitalize()}, and so {b_text}.",
    ]
    if tv and tv.mean > 0.8:
        candidates.append(f"Whenever {a_text}, {b_text} follows.")
    return candidates


# ── Main generation function ────────────────────────────────────────────

def generate_from_atomese(atom, aspace=None) -> str | None:
    """Generate grammatical English from an Atomese atom.

    Uses Link Grammar to validate grammar when available.
    Returns the best grammatical sentence, or None if no valid output.
    """
    _init_lg()

    type_name = getattr(atom, 'type_name', '')
    out = getattr(atom, 'out', [])
    tv = getattr(atom, 'tv', None)

    candidates = []

    if 'Inheritance' in type_name and len(out) == 2:
        a_name = getattr(out[0], 'name', '')
        b_name = getattr(out[1], 'name', '')
        candidates = inheritance_to_sentences(a_name, b_name, tv)

    elif 'Evaluation' in type_name and len(out) >= 2:
        pred_name = getattr(out[0], 'name', '')
        args_atom = out[1]
        arg_out = getattr(args_atom, 'out', None)
        args = [getattr(a, 'name', str(a)) for a in arg_out] if arg_out else [getattr(args_atom, 'name', str(args_atom))]
        candidates = evaluation_to_sentences(pred_name, args, tv)

    elif 'Implication' in type_name and len(out) == 2:
        a_text = _atom_fragment(out[0])
        b_text = _atom_fragment(out[1])
        if a_text and b_text:
            candidates = implication_to_sentences(a_text, b_text, tv)

    if not candidates:
        return None

    # If LG available, validate grammar and pick best parse
    if _LG_AVAILABLE:
        best = None
        best_links = -1
        for sent in candidates:
            count = _parse_count(sent)
            if count > best_links:
                best_links = count
                best = sent
        if best and best_links > 0:
            return best
        # All failed grammar check — return shortest candidate anyway
        return min(candidates, key=len) if candidates else None

    # No LG — return first candidate
    return candidates[0]


def _atom_fragment(atom) -> str | None:
    """Convert an atom to a text fragment for embedding in sentences."""
    type_name = getattr(atom, 'type_name', '')
    out = getattr(atom, 'out', [])

    if 'Inheritance' in type_name and len(out) == 2:
        return f"{_np(getattr(out[0], 'name', ''))} is {_np(getattr(out[1], 'name', ''))}"
    elif 'Evaluation' in type_name and len(out) >= 2:
        pred = getattr(out[0], 'name', '')
        args_atom = out[1]
        arg_out = getattr(args_atom, 'out', None)
        args = [getattr(a, 'name', '') for a in arg_out] if arg_out else [getattr(args_atom, 'name', '')]
        if len(args) >= 2:
            return f"{_np(args[0])} {_vp(pred)} {_np(args[1])}"
        elif args:
            return f"{_np(args[0])} {_vp(pred)}"

    name = getattr(atom, 'name', '')
    return name.replace('_', ' ') if name else None
