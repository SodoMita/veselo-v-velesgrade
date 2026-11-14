"""
dialogue/inference.py – Logical inference over Mira's inheritance facts.

Rules implemented (all over the AtomSpace, nothing hard-coded about the world):

  Transitivity (generalization):  X inh A  and  A inh B   ⊢  X inh B
  Property inheritance:           X inh A  and  A has property P   ⊢  X has property P

Every conclusion carries its proof: the chain of facts that produced it. Answers can
therefore say *why* (the chain), not only *that*. A conclusion is weaker than a stored
fact, so inferred answers are marked as inferred. Negation is not inferred: if no proof
exists, the answer is "I cannot confirm that", never "no".

Public API:
    proof(aspace, subject, target, lexicon) -> list[str] | None   chain of names, e.g. ['relic', 'stolen artifact', 'valuable']
    ancestors(aspace, subject, lexicon) -> list[list[str]]        every class reachable from subject, with its chain
    explain(chain) -> str                                          "the relic is a stolen artifact, and stolen artifacts are valuable"
"""

from collections import deque


def _name(n: str) -> str:
    return n.replace("_", " ").strip().lower()


def _inh_graph(aspace) -> dict:
    """a → [b, ...] for every Inheritance link a inh b."""
    from .understand import _triples
    graph = {}
    for _link, kind, a, _pred, b in _triples(aspace):
        if kind == "inh":
            graph.setdefault(_name(a), []).append(_name(b))
    return graph


def _same(x: str, y: str, lexicon) -> bool:
    from .understand import canon
    return x == y or canon(x, lexicon) == canon(y, lexicon)


def proof(aspace, subject: str, target: str, lexicon=None, max_depth: int = 4,
          require_intermediate: bool = False) -> list[str] | None:
    """Shortest chain of inheritance facts from subject to target, or None.

    require_intermediate: skip the direct fact, so the chain has a real reasoning step.
    """
    graph = _inh_graph(aspace)
    start = _name(subject)
    goal = _name(target)
    queue = deque([[start]])
    seen = {start}
    while queue:
        path = queue.popleft()
        if len(path) - 1 > max_depth:
            continue
        here = path[-1]
        if len(path) > 1 and _same(here, goal, lexicon) \
                and not (require_intermediate and len(path) == 2):
            return path
        for nxt in graph.get(here, []):
            if require_intermediate and len(path) == 1 and _same(nxt, goal, lexicon):
                continue                    # the direct edge does not count; keep the route open
            if nxt not in seen:
                seen.add(nxt)
                queue.append(path + [nxt])
    return None


def ancestors(aspace, subject: str, lexicon=None, max_depth: int = 4) -> list[list[str]]:
    """Every class reachable from subject by inheritance, each with the chain that reaches it."""
    graph = _inh_graph(aspace)
    start = _name(subject)
    out = []
    queue = deque([[start]])
    while queue:
        path = queue.popleft()
        if len(path) - 1 >= max_depth:
            continue
        for nxt in graph.get(path[-1], []):
            if nxt in path:                 # cycle guard per route, not global, so no route is lost
                continue
            out.append(path + [nxt])
            queue.append(path + [nxt])
    return out


def explain_plural(chain: list[str]) -> str:
    """'relics are stolen artifacts, and stolen artifacts are valuable' (plural subject)."""
    if len(chain) < 2:
        return ""
    first = chain[1] if is_adjective(chain[1]) else _plural(chain[1])
    parts = [f"{_plural(chain[0])} are {first}"]
    for prev, nxt in zip(chain[1:], chain[2:]):
        if is_adjective(nxt):
            parts.append(f"{_plural(prev)} are {nxt}")
        else:
            parts.append(f"{_plural(prev)} are {_plural(nxt)}")
    return ", and ".join(parts)


def explain(chain: list[str]) -> str:
    """Turn a chain into a sentence: relic → stolen artifact → valuable becomes
    'the relic is a stolen artifact, and stolen artifacts are valuable'."""
    if len(chain) < 2:
        return ""
    parts = [f"the {chain[0]} is {_a_or_bare(chain[1])}"]
    for prev, nxt in zip(chain[1:], chain[2:]):
        if is_adjective(nxt):
            parts.append(f"{_plural(prev)} are {nxt}")
        else:
            parts.append(f"{_plural(prev)} are {_plural(nxt)}")
    return ", and ".join(parts)


_ADJ_HINT = {"valuable", "ancient", "fragile", "dangerous", "trustworthy", "important",
             "irreplaceable", "inside job", "layered history", "source of power", "clue"}


def is_adjective(word: str) -> bool:
    if word in _ADJ_HINT or word.endswith(("ous", "ful", "ant", "ent", "able", "ible", "ive", "less", "ic")):
        return True
    from .wordparts import is_adjective_word
    return is_adjective_word(word)


def _a_or_bare(word: str) -> str:
    return word if is_adjective(word) else _a(word)


def _a(noun: str) -> str:
    return ("an " if noun[:1] in "aeiou" else "a ") + noun


def _plural(noun: str) -> str:
    """Pluralize the head noun, which is the last word: 'stolen artifact' → 'stolen artifacts'."""
    from .morph import plural
    words = noun.split(" ")
    words[-1] = plural(words[-1])
    return " ".join(words)
